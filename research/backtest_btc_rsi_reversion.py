#!/usr/bin/env python3
"""Research-only BTCUSDT RSI(14) mean-reversion scalp backtest.

Frozen scalp spec:
  - BTCUSDT perp only, 5m candles
  - signal: RSI(14) crosses below 20 (oversold) -> long; crosses above 80 (overbought) -> short
  - entry: next 5m open
  - stop: 0.30% adverse move from entry
  - target: 0.40% favorable move from entry
  - time stop: 12 bars (60 minutes)
  - fee: 0.08% round trip

Uses public Binance Futures klines only; it never loads credentials, starts Docker,
or places orders.
"""

from __future__ import annotations

from btc_klines_5m import SYMBOL, get_klines

RSI_PERIOD = 14
OVERSOLD = 20.0
OVERBOUGHT = 80.0
STOP = 0.0030
TARGET = 0.0040
HOLD_BARS = 12
FEE_ROUND_TRIP = 0.0008


def rsi(closes: list[float], period: int = RSI_PERIOD) -> list[float | None]:
    values: list[float | None] = [None] * len(closes)
    avg_gain = avg_loss = 0.0
    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        gain, loss = max(change, 0.0), max(-change, 0.0)
        if i < period:
            avg_gain += gain
            avg_loss += loss
            continue
        if i == period:
            avg_gain = (avg_gain + gain) / period
            avg_loss = (avg_loss + loss) / period
        else:
            avg_gain = (avg_gain * (period - 1) + gain) / period
            avg_loss = (avg_loss * (period - 1) + loss) / period
        values[i] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    return values


def simulate(candles: list[list]) -> list[tuple[str, float, int]]:
    opens = [float(c[1]) for c in candles]
    highs = [float(c[2]) for c in candles]
    lows = [float(c[3]) for c in candles]
    closes = [float(c[4]) for c in candles]
    rsi_values = rsi(closes)
    trades = []
    index = RSI_PERIOD + 1

    while index + HOLD_BARS + 1 < len(candles):
        previous_rsi, current_rsi = rsi_values[index - 1], rsi_values[index]
        if previous_rsi is None or current_rsi is None:
            index += 1
            continue
        direction = 0
        if previous_rsi >= OVERSOLD and current_rsi < OVERSOLD:
            direction = 1
        elif previous_rsi <= OVERBOUGHT and current_rsi > OVERBOUGHT:
            direction = -1
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
    label = f"{SYMBOL} RSI({RSI_PERIOD}) reversion: oversold<{OVERSOLD:g} overbought>{OVERBOUGHT:g} stop={STOP*100:.2f}% target={TARGET*100:.2f}% hold={HOLD_BARS*5}m"
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
