#!/usr/bin/env python3
"""Research-only BTCUSDT 4h-trend / 1h-breakout-pullback backtest.

Frozen specification:
- Long only: completed 4h close is above its 50-period EMA and the EMA is rising.
- Setup: a completed 1h candle closed above the prior 20 completed 1h highs.
- Entry: a later completed 1h candle pulls back to that breakout level, closes above it,
  and is still inside the same 4h uptrend. Entry is the following 1h candle open.
- Stop: lowest low of the last five completed 1h candles before entry.
- Target: 2R. Maximum holding period: 24 hours.
- Execution: two taker fills, 0.08% round-trip fee, deducted from every trade.
- Same-candle stop/target collision: the stop wins (conservative).

This script fetches public Binance Futures candles only. It does not load credentials,
use Docker, or place orders.
"""

from __future__ import annotations

import time

import requests

BASE_URL = "https://fapi.binance.com"
SYMBOL = "BTCUSDT"
DAYS = 365
EMA_PERIOD = 50
BREAKOUT_LOOKBACK = 20
SWING_LOOKBACK = 5
RISK_REWARD = 2.0
MAX_HOLD_HOURS = 24
ROUND_TRIP_FEE = 0.0008


def get_klines(interval: str, start_time: int, end_time: int) -> list[list]:
    candles = []
    while start_time < end_time:
        response = requests.get(
            BASE_URL + "/fapi/v1/klines",
            params={
                "symbol": SYMBOL,
                "interval": interval,
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
        start_time = batch[-1][0] + 1
        if len(batch) < 1500:
            break
        time.sleep(0.15)
    return candles


def ema(values: list[float], period: int) -> list[float | None]:
    multiplier = 2 / (period + 1)
    result: list[float | None] = [None] * len(values)
    if len(values) < period:
        return result
    current = sum(values[:period]) / period
    result[period - 1] = current
    for index in range(period, len(values)):
        current = (values[index] - current) * multiplier + current
        result[index] = current
    return result


def four_hour_uptrend(one_hour_open_time: int, four_hour_opens: list[int], four_hour_ema: list[float | None], four_hour_closes: list[float]) -> bool:
    completed_index = None
    for index, open_time in enumerate(four_hour_opens):
        if open_time + 4 * 60 * 60 * 1000 <= one_hour_open_time:
            completed_index = index
        else:
            break
    if completed_index is None or completed_index < EMA_PERIOD:
        return False
    current_ema = four_hour_ema[completed_index]
    prior_ema = four_hour_ema[completed_index - 1]
    return current_ema is not None and prior_ema is not None and four_hour_closes[completed_index] > current_ema and current_ema > prior_ema


def simulate(one_hour: list[list], four_hour: list[list]) -> list[dict]:
    opens = [float(candle[1]) for candle in one_hour]
    highs = [float(candle[2]) for candle in one_hour]
    lows = [float(candle[3]) for candle in one_hour]
    closes = [float(candle[4]) for candle in one_hour]
    times = [int(candle[0]) for candle in one_hour]
    four_hour_opens = [int(candle[0]) for candle in four_hour]
    four_hour_closes = [float(candle[4]) for candle in four_hour]
    four_hour_ema = ema(four_hour_closes, EMA_PERIOD)
    trades = []
    pending_level: float | None = None
    pending_expiry = -1
    index = max(BREAKOUT_LOOKBACK, SWING_LOOKBACK, 1)

    while index + 1 < len(one_hour):
        uptrend = four_hour_uptrend(times[index], four_hour_opens, four_hour_ema, four_hour_closes)
        prior_high = max(highs[index - BREAKOUT_LOOKBACK:index])
        if uptrend and closes[index] > prior_high:
            pending_level = prior_high
            pending_expiry = index + BREAKOUT_LOOKBACK

        if pending_level is None or index > pending_expiry or not uptrend:
            if index > pending_expiry:
                pending_level = None
            index += 1
            continue

        pulled_back = lows[index] <= pending_level and closes[index] > pending_level
        if not pulled_back:
            index += 1
            continue

        entry_index = index + 1
        entry = opens[entry_index]
        stop = min(lows[entry_index - SWING_LOOKBACK:entry_index])
        risk = entry - stop
        if risk <= 0 or risk / entry > 0.02:
            pending_level = None
            index += 1
            continue
        target = entry + risk * RISK_REWARD
        exit_index = min(entry_index + MAX_HOLD_HOURS, len(one_hour) - 1)
        exit_price = closes[exit_index]
        reason = "TIME"
        for candidate in range(entry_index + 1, exit_index + 1):
            if lows[candidate] <= stop:
                exit_price, exit_index, reason = stop, candidate, "SL"
                break
            if highs[candidate] >= target:
                exit_price, exit_index, reason = target, candidate, "TP"
                break
        gross_return = exit_price / entry - 1
        net_return = gross_return - ROUND_TRIP_FEE
        trades.append({
            "entry_time": times[entry_index],
            "exit_time": times[exit_index],
            "reason": reason,
            "gross_return": gross_return,
            "net_return": net_return,
            "risk_return": risk / entry,
            "hold_hours": exit_index - entry_index,
        })
        pending_level = None
        index = exit_index + 1
    return trades


def percentile(values: list[float], ratio: float) -> float:
    values = sorted(values)
    return values[int((len(values) - 1) * ratio)] if values else 0.0


def main() -> None:
    end_time = int(time.time() * 1000)
    start_time = end_time - DAYS * 24 * 60 * 60 * 1000
    print(f"Fetching {DAYS} days of public BTCUSDT 1h and 4h candles...")
    one_hour = get_klines("1h", start_time, end_time)
    four_hour = get_klines("4h", start_time, end_time)
    print(f"Received {len(one_hour)} 1h candles and {len(four_hour)} 4h candles.")
    print(f"Frozen spec: 4h 50-EMA uptrend, 1h 20h breakout then pullback; 2R target; 24h max hold; {ROUND_TRIP_FEE * 100:.02f}% round-trip taker fee.\n")

    trades = simulate(one_hour, four_hour)
    if not trades:
        print("No qualifying trades.")
        return
    net_returns = [trade["net_return"] for trade in trades]
    gross_returns = [trade["gross_return"] for trade in trades]
    wins = [trade for trade in trades if trade["net_return"] > 0]
    reasons = {reason: [trade for trade in trades if trade["reason"] == reason] for reason in ("TP", "SL", "TIME")}
    max_drawdown = 0.0
    equity = peak = 0.0
    for value in net_returns:
        equity += value
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)

    print(f"Trades: {len(trades)}")
    print(f"Win rate after fees: {len(wins) / len(trades) * 100:.1f}%")
    print(f"Average gross return: {sum(gross_returns) / len(trades) * 100:+.3f}%")
    print(f"Average net return: {sum(net_returns) / len(trades) * 100:+.3f}%")
    print(f"Total net return (one-unit sequential model): {sum(net_returns) * 100:+.3f}%")
    print(f"Maximum sequential drawdown: {max_drawdown * 100:.3f}%")
    print(f"Median / p25 net return: {percentile(net_returns, .50) * 100:+.3f}% / {percentile(net_returns, .25) * 100:+.3f}%")
    print(f"Average hold: {sum(trade['hold_hours'] for trade in trades) / len(trades):.1f}h")
    print()
    for reason, reason_trades in reasons.items():
        average = sum(trade["net_return"] for trade in reason_trades) / len(reason_trades) if reason_trades else 0.0
        print(f"{reason}: count={len(reason_trades)} avg_net={average * 100:+.3f}%")
    print()
    print("Decision:", "PASS: paper-only candidate" if sum(net_returns) / len(net_returns) > 0 else "FAIL: remain flat")


if __name__ == "__main__":
    main()
