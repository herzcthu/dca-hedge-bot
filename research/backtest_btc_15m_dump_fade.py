#!/usr/bin/env python3
"""Research-only BTCUSDT 15-minute dump fade backtest (long side only).

Mirror of backtest_btc_15m_impulse_fade.py's frozen short spec, opposite direction,
kept in its own script (one side per script, no combined long/short test).

Frozen scalp spec:
  - BTCUSDT perp only
  - signal: 5m close is at least -0.80% below the close 3 bars ago (15m dump)
  - entry: next 5m open, long only (fade the dump)
  - stop: impulse low - 1 tick
  - target: 1R
  - time stop: 6 bars / 30 minutes
  - fee: 0.08% round trip

Uses public Binance Futures klines only; it never loads credentials, starts Docker,
or places orders.
"""

from __future__ import annotations

from btc_klines_5m import SYMBOL, get_klines

IMPULSE_BARS = 3
IMPULSE_RETURN = -0.0080
HOLD_BARS = 6
FEE_ROUND_TRIP = 0.0008
PRICE_TICK = 0.1


def simulate(candles: list[list]) -> tuple[list[tuple[str, float, int, float]], int]:
    opens = [float(candle[1]) for candle in candles]
    highs = [float(candle[2]) for candle in candles]
    lows = [float(candle[3]) for candle in candles]
    closes = [float(candle[4]) for candle in candles]
    trades = []
    skipped_invalid_risk = 0
    signal_index = IMPULSE_BARS

    while signal_index + HOLD_BARS + 1 < len(candles):
        impulse_return = closes[signal_index] / closes[signal_index - IMPULSE_BARS] - 1.0
        if impulse_return > IMPULSE_RETURN:
            signal_index += 1
            continue

        entry_index = signal_index + 1
        entry = opens[entry_index]
        impulse_low = min(lows[signal_index - IMPULSE_BARS + 1:entry_index])
        stop = impulse_low - PRICE_TICK
        risk = entry - stop
        if risk <= 0:
            skipped_invalid_risk += 1
            signal_index += 1
            continue
        target = entry + risk

        outcome = "TIME"
        held = HOLD_BARS
        exit_price = closes[entry_index + HOLD_BARS - 1]
        for exit_index in range(entry_index, entry_index + HOLD_BARS):
            if lows[exit_index] <= stop:
                outcome = "SL"
                exit_price = stop
                held = exit_index - entry_index + 1
                break
            if highs[exit_index] >= target:
                outcome = "TP"
                exit_price = target
                held = exit_index - entry_index + 1
                break

        gross_return = (exit_price - entry) / entry
        risk_return = risk / entry
        trades.append((outcome, gross_return - FEE_ROUND_TRIP, held, risk_return))
        signal_index = entry_index + held

    return trades, skipped_invalid_risk


def report(trades: list[tuple[str, float, int, float]], skipped_invalid_risk: int) -> None:
    label = (
        f"{SYMBOL} long dump fade: impulse={IMPULSE_RETURN * 100:.2f}%/15m "
        f"stop=impulse_low-{PRICE_TICK:g} target=1R hold={HOLD_BARS * 5}m"
    )
    if not trades:
        print(label, "no trades", f"skipped_invalid_risk={skipped_invalid_risk}")
        return
    total = sum(pnl for _, pnl, _, _ in trades)
    winners = sum(1 for _, pnl, _, _ in trades if pnl > 0)
    average_hold = sum(held for _, _, held, _ in trades) / len(trades) * 5
    average_risk = sum(risk for _, _, _, risk in trades) / len(trades)
    by_reason = {reason: sum(1 for outcome, _, _, _ in trades if outcome == reason) for reason in ("TP", "SL", "TIME")}
    print(
        f"{label}: n={len(trades)} win_rate={winners / len(trades) * 100:.1f}% "
        f"avg_net={total / len(trades) * 100:.4f}% total_net={total * 100:.3f}% "
        f"avg_hold={average_hold:.1f}m avg_risk={average_risk * 100:.3f}% "
        f"skipped_invalid_risk={skipped_invalid_risk}"
    )
    print("  " + " ".join(f"{reason}={count}" for reason, count in by_reason.items()))
    print("  PASS" if total / len(trades) > 0 else "  FAIL")


def main() -> None:
    candles = get_klines()
    print(f"Received {len(candles)} candles; round-trip taker fee={FEE_ROUND_TRIP * 100:.02f}%.\n")
    trades, skipped_invalid_risk = simulate(candles)
    report(trades, skipped_invalid_risk)


if __name__ == "__main__":
    main()
