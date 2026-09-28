#!/usr/bin/env python3
"""Research-only BTCUSDT session-VWAP mean-reversion scalp backtest.

Frozen scalp spec:
  - BTCUSDT perp only, 5m candles
  - VWAP resets each UTC calendar day, cumulative typical-price * volume
  - signal: 5m close deviates from session VWAP by >= 0.50% -> fade back toward VWAP
    (close above VWAP -> short; close below VWAP -> long)
  - entry: next 5m open
  - stop: 0.30% adverse move from entry
  - target: 0.40% favorable move from entry
  - time stop: 12 bars (60 minutes)
  - fee: 0.08% round trip

Uses public Binance Futures klines only; it never loads credentials, starts Docker,
or places orders.
"""

from __future__ import annotations

from datetime import datetime, timezone

from btc_klines_5m import SYMBOL, get_klines

DEVIATION_TRIGGER = 0.0050
STOP = 0.0030
TARGET = 0.0040
HOLD_BARS = 12
FEE_ROUND_TRIP = 0.0008


def session_vwap(candles: list[list]) -> list[float]:
    vwaps: list[float] = [0.0] * len(candles)
    cumulative_pv = cumulative_volume = 0.0
    current_day = None
    for i, candle in enumerate(candles):
        day = datetime.fromtimestamp(candle[0] / 1000, tz=timezone.utc).date()
        if day != current_day:
            current_day = day
            cumulative_pv = cumulative_volume = 0.0
        high, low, close, volume = float(candle[2]), float(candle[3]), float(candle[4]), float(candle[5])
        typical = (high + low + close) / 3.0
        cumulative_pv += typical * volume
        cumulative_volume += volume
        vwaps[i] = cumulative_pv / cumulative_volume if cumulative_volume > 0 else typical
    return vwaps


def simulate(candles: list[list]) -> list[tuple[str, float, int]]:
    opens = [float(c[1]) for c in candles]
    highs = [float(c[2]) for c in candles]
    lows = [float(c[3]) for c in candles]
    closes = [float(c[4]) for c in candles]
    vwaps = session_vwap(candles)
    trades = []
    index = 1

    while index + HOLD_BARS + 1 < len(candles):
        vwap = vwaps[index]
        deviation = closes[index] / vwap - 1.0
        direction = -1 if deviation >= DEVIATION_TRIGGER else 1 if deviation <= -DEVIATION_TRIGGER else 0
        if direction == 0:
            index += 1
            continue

        entry_index = index + 1
        entry = opens[entry_index]
        stop_price = entry * (1 - STOP) if direction > 0 else entry * (1 + STOP)
        target_price = entry * (1 + TARGET) if direction > 0 else entry * (1 - TARGET)

        outcome = "TIME"
        held = HOLD_BARS
        exit_price = closes[entry_index + HOLD_BARS - 1]
        for exit_index in range(entry_index, entry_index + HOLD_BARS):
            if direction > 0:
                if lows[exit_index] <= stop_price:
                    outcome, exit_price, held = "SL", stop_price, exit_index - entry_index + 1
                    break
                if highs[exit_index] >= target_price:
                    outcome, exit_price, held = "TP", target_price, exit_index - entry_index + 1
                    break
            else:
                if highs[exit_index] >= stop_price:
                    outcome, exit_price, held = "SL", stop_price, exit_index - entry_index + 1
                    break
                if lows[exit_index] <= target_price:
                    outcome, exit_price, held = "TP", target_price, exit_index - entry_index + 1
                    break

        gross_return = (exit_price / entry - 1.0) * direction
        trades.append((outcome, gross_return - FEE_ROUND_TRIP, held))
        index = entry_index + held

    return trades


def report(trades: list[tuple[str, float, int]]) -> None:
    label = f"{SYMBOL} session-VWAP reversion: trigger={DEVIATION_TRIGGER*100:.2f}% stop={STOP*100:.2f}% target={TARGET*100:.2f}% hold={HOLD_BARS*5}m"
    if not trades:
        print(label, "no trades")
        return
    total = sum(pnl for _, pnl, _ in trades)
    winners = sum(1 for _, pnl, _ in trades if pnl > 0)
    average_hold = sum(held for _, _, held in trades) / len(trades) * 5
    by_reason = {r: sum(1 for o, _, _ in trades if o == r) for r in ("TP", "SL", "TIME")}
    print(
        f"{label}: n={len(trades)} win_rate={winners / len(trades) * 100:.1f}% "
        f"avg_net={total / len(trades) * 100:.4f}% total_net={total * 100:.3f}% avg_hold={average_hold:.1f}m"
    )
    print("  " + " ".join(f"{r}={c}" for r, c in by_reason.items()))
    print("  PASS" if total / len(trades) > 0 else "  FAIL")


def main() -> None:
    candles = get_klines()
    print(f"Received {len(candles)} candles; round-trip taker fee={FEE_ROUND_TRIP * 100:.02f}%.\n")
    report(simulate(candles))


if __name__ == "__main__":
    main()
