#!/usr/bin/env python3
"""Research-only volume-confirmed BTC breakout backtest.

Extends backtest_btc_breakout.py with a high-relative-volume requirement. It uses
public Binance candle data only; it never loads credentials, starts Docker, or trades.
"""

from __future__ import annotations

from backtest_btc_breakout import (
    BREAKOUT_MIN,
    COOLDOWN_MIN,
    FEE_PER_FILL,
    LOOKBACK_MIN,
    get_klines,
    report,
)


def simulate(candles: list[list], burst: float, volume_multiple: float, target: float, stop: float, max_hold: int):
    closes = [float(candle[4]) for candle in candles]
    highs = [float(candle[2]) for candle in candles]
    lows = [float(candle[3]) for candle in candles]
    volumes = [float(candle[5]) for candle in candles]
    trades = []
    index = max(BREAKOUT_MIN, 30)

    while index + max_hold < len(candles):
        entry = closes[index]
        return_15m = entry / closes[index - LOOKBACK_MIN] - 1.0
        prior_high = max(highs[index - BREAKOUT_MIN:index])
        prior_low = min(lows[index - BREAKOUT_MIN:index])
        average_volume = sum(volumes[index - 30:index]) / 30
        direction = 1 if return_15m >= burst and entry > prior_high else -1 if return_15m <= -burst and entry < prior_low else 0
        if direction == 0 or volumes[index] < average_volume * volume_multiple:
            index += 1
            continue

        outcome = "TIME"
        exit_return = (closes[index + max_hold] / entry - 1.0) * direction
        held = max_hold
        for exit_index in range(index + 1, index + max_hold + 1):
            favorable = highs[exit_index] / entry - 1.0 if direction > 0 else entry / lows[exit_index] - 1.0
            adverse = lows[exit_index] / entry - 1.0 if direction > 0 else entry / highs[exit_index] - 1.0
            if adverse <= -stop:
                outcome, exit_return, held = "SL", -stop, exit_index - index
                break
            if favorable >= target:
                outcome, exit_return, held = "TP", target, exit_index - index
                break
        trades.append((outcome, exit_return - 2 * FEE_PER_FILL, held))
        index += held + COOLDOWN_MIN
    return trades


def main() -> None:
    candles = get_klines()
    print(f"Received {len(candles)} one-minute candles; round-trip taker fee={2 * FEE_PER_FILL * 100:.02f}%.\n")
    for volume_multiple in (1.5, 2.0, 3.0):
        for burst in (0.0025, 0.0030, 0.0040):
            report(
                f"volume={volume_multiple:.1f}x burst={burst * 100:.2f}% target=0.50% stop=0.30% hold=30m",
                simulate(candles, burst, volume_multiple, 0.0050, 0.0030, 30),
            )


if __name__ == "__main__":
    main()
