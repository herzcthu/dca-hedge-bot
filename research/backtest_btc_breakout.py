#!/usr/bin/env python3
"""Research-only BTCUSDT breakout backtest using public Binance Futures klines.

A long starts only after a 15-minute upward burst closes at a 30-minute breakout;
a short uses the inverse. Entries/exits are assessed on subsequent one-minute candle
highs/lows and include two taker fees. This does not use credentials, Docker, or place
orders.
"""

from __future__ import annotations

import time

import requests

BASE_URL = "https://fapi.binance.com"
SYMBOL = "BTCUSDT"
INTERVAL = "1m"
DAYS = 30
LOOKBACK_MIN = 15
BREAKOUT_MIN = 30
COOLDOWN_MIN = 10
FEE_PER_FILL = 0.0004


def get_klines() -> list[list]:
    end_time = int(time.time() * 1000)
    start_time = end_time - DAYS * 24 * 60 * 60 * 1000
    candles = []
    while start_time < end_time:
        response = requests.get(
            BASE_URL + "/fapi/v1/klines",
            params={
                "symbol": SYMBOL,
                "interval": INTERVAL,
                "startTime": start_time,
                "endTime": end_time,
                "limit": 1500,
            },
            timeout=15,
        )
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        candles.extend(batch)
        start_time = batch[-1][0] + 60_000
        if len(batch) < 1500:
            break
        time.sleep(0.15)
    return candles


def simulate(candles: list[list], burst: float, target: float, stop: float, max_hold: int) -> list[tuple[str, float, int]]:
    closes = [float(candle[4]) for candle in candles]
    highs = [float(candle[2]) for candle in candles]
    lows = [float(candle[3]) for candle in candles]
    trades = []
    index = BREAKOUT_MIN

    while index + max_hold < len(candles):
        entry = closes[index]
        return_15m = entry / closes[index - LOOKBACK_MIN] - 1.0
        prior_high = max(highs[index - BREAKOUT_MIN:index])
        prior_low = min(lows[index - BREAKOUT_MIN:index])
        direction = 1 if return_15m >= burst and entry > prior_high else -1 if return_15m <= -burst and entry < prior_low else 0
        if direction == 0:
            index += 1
            continue

        outcome = "TIME"
        exit_return = (closes[index + max_hold] / entry - 1.0) * direction
        held = max_hold
        for exit_index in range(index + 1, index + max_hold + 1):
            favorable = (highs[exit_index] / entry - 1.0) * direction if direction > 0 else (entry / lows[exit_index] - 1.0)
            adverse = (lows[exit_index] / entry - 1.0) * direction if direction > 0 else (entry / highs[exit_index] - 1.0)
            # Conservative: if both thresholds touched in the same one-minute candle,
            # assume the protective stop occurred before the profit target.
            if adverse <= -stop:
                outcome, exit_return, held = "SL", -stop, exit_index - index
                break
            if favorable >= target:
                outcome, exit_return, held = "TP", target, exit_index - index
                break
        trades.append((outcome, exit_return - 2 * FEE_PER_FILL, held))
        index += held + COOLDOWN_MIN
    return trades


def report(label: str, trades: list[tuple[str, float, int]]) -> None:
    if not trades:
        print(label, "no trades")
        return
    by_reason = {reason: [pnl for outcome, pnl, _ in trades if outcome == reason] for reason in ("TP", "SL", "TIME")}
    total = sum(pnl for _, pnl, _ in trades)
    winners = sum(1 for _, pnl, _ in trades if pnl > 0)
    average_hold = sum(held for _, _, held in trades) / len(trades)
    print(
        f"{label}: n={len(trades)} win_rate={winners / len(trades) * 100:.1f}% "
        f"avg_net={total / len(trades) * 100:.3f}% total_net={total * 100:.3f}% avg_hold={average_hold:.1f}m"
    )
    print("  " + " ".join(f"{reason}={len(values)}" for reason, values in by_reason.items()))


def main() -> None:
    print(f"Fetching {DAYS} days of public {SYMBOL} {INTERVAL} candles...")
    candles = get_klines()
    print(f"Received {len(candles)} candles; fees: {FEE_PER_FILL * 100:.02f}% per fill, {2 * FEE_PER_FILL * 100:.02f}% round trip.\n")
    for burst in (0.0015, 0.0020, 0.0025, 0.0030):
        for target, stop, hold in ((0.0030, 0.0020, 15), (0.0040, 0.0025, 20), (0.0050, 0.0030, 30)):
            report(
                f"burst={burst * 100:.2f}% target={target * 100:.2f}% stop={stop * 100:.2f}% hold={hold}m",
                simulate(candles, burst, target, stop, hold),
            )


if __name__ == "__main__":
    main()
