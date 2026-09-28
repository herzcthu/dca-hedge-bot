#!/usr/bin/env python3
"""Research-only BTCUSDT daily 50-SMA long-or-flat backtest.

Status: historical pass; preserve as a paper-only candidate. Do not deploy
until independently revalidated on a fresh out-of-sample period.

Frozen specification:
- Long only when yesterday's completed daily close crosses above its 50-day SMA.
- Flat when yesterday's completed daily close crosses below its 50-day SMA.
- Trades at the next daily open, 1x, with 0.08% round-trip taker fees.
- One unit of current equity per trade; no stop other than the opposing SMA cross.

Uses only public Binance Futures daily candles. It never loads credentials, starts
Docker, or places orders.
"""

from __future__ import annotations

import time

import requests

BASE_URL = "https://fapi.binance.com"
SYMBOL = "BTCUSDT"
INTERVAL = "1d"
SMA_PERIOD = 50
ROUND_TRIP_FEE = 0.0008


def get_klines() -> list[list]:
    end_time = int(time.time() * 1000)
    candles = []
    # Binance Futures BTCUSDT begins in 2019; fetch from a point safely before it.
    start_time = 1_545_000_000_000
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
        start_time = batch[-1][0] + 1
        if len(batch) < 1500:
            break
        time.sleep(0.15)
    return candles


def sma(values: list[float], period: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    for index in range(period - 1, len(values)):
        result[index] = sum(values[index - period + 1:index + 1]) / period
    return result


def max_drawdown(equity_curve: list[float]) -> float:
    peak = equity_curve[0]
    worst = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        worst = min(worst, equity / peak - 1.0)
    return worst


def simulate(candles: list[list]) -> tuple[list[dict], list[float]]:
    opens = [float(candle[1]) for candle in candles]
    closes = [float(candle[4]) for candle in candles]
    times = [int(candle[0]) for candle in candles]
    averages = sma(closes, SMA_PERIOD)
    trades = []
    equity = 1.0
    curve = [equity]
    entry_price = None
    entry_time = None

    # Signal uses yesterday's close. A position therefore enters/exits at today's open.
    for today in range(SMA_PERIOD + 1, len(candles)):
        yesterday = today - 1
        day_before = yesterday - 1
        yesterday_sma = averages[yesterday]
        day_before_sma = averages[day_before]
        if yesterday_sma is None or day_before_sma is None:
            curve.append(equity)
            continue
        crossed_above = closes[day_before] <= day_before_sma and closes[yesterday] > yesterday_sma
        crossed_below = closes[day_before] >= day_before_sma and closes[yesterday] < yesterday_sma

        if entry_price is None and crossed_above:
            entry_price = opens[today]
            entry_time = times[today]
        elif entry_price is not None and crossed_below:
            exit_price = opens[today]
            gross_return = exit_price / entry_price - 1.0
            net_return = gross_return - ROUND_TRIP_FEE
            equity *= 1.0 + net_return
            trades.append({
                "entry_time": entry_time,
                "exit_time": times[today],
                "gross_return": gross_return,
                "net_return": net_return,
                "hold_days": (times[today] - entry_time) / 86_400_000,
            })
            entry_price = entry_time = None
        if entry_price is None:
            curve.append(equity)
        else:
            curve.append(equity * (closes[today] / entry_price - ROUND_TRIP_FEE / 2))
    return trades, curve


def percentile(values: list[float], ratio: float) -> float:
    values = sorted(values)
    return values[int((len(values) - 1) * ratio)] if values else 0.0


def main() -> None:
    print(f"Fetching all available public {SYMBOL} daily candles...")
    candles = get_klines()
    years = len(candles) / 365.25
    print(f"Received {len(candles)} daily candles ({years:.1f} years).")
    print(f"Frozen spec: yesterday 50-SMA cross, trade next open, long/flat, 1x, {ROUND_TRIP_FEE * 100:.02f}% round-trip taker fee.\n")
    trades, equity_curve = simulate(candles)
    if not trades:
        print("No completed trades. Decision: FAIL: remain flat")
        return
    net_returns = [trade["net_return"] for trade in trades]
    gross_returns = [trade["gross_return"] for trade in trades]
    winning = [trade for trade in trades if trade["net_return"] > 0]
    starting_price = float(candles[SMA_PERIOD + 1][1])
    ending_price = float(candles[-1][4])
    buy_hold = ending_price / starting_price - 1.0 - ROUND_TRIP_FEE

    print(f"Completed trades: {len(trades)}")
    print(f"Win rate after fees: {len(winning) / len(trades) * 100:.1f}%")
    print(f"Average gross return/trade: {sum(gross_returns) / len(trades) * 100:+.3f}%")
    print(f"Average net return/trade: {sum(net_returns) / len(trades) * 100:+.3f}%")
    print(f"Median / p25 net trade: {percentile(net_returns, .50) * 100:+.3f}% / {percentile(net_returns, .25) * 100:+.3f}%")
    print(f"Average holding period: {sum(trade['hold_days'] for trade in trades) / len(trades):.1f} days")
    print(f"Strategy compounded net return: {(equity_curve[-1] - 1.0) * 100:+.2f}%")
    print(f"Strategy max drawdown: {max_drawdown(equity_curve) * 100:.2f}%")
    print(f"Buy-and-hold return (context only): {buy_hold * 100:+.2f}%")
    print()
    print("Decision:", "PASS: paper-only candidate" if sum(net_returns) / len(net_returns) > 0 else "FAIL: remain flat")


if __name__ == "__main__":
    main()
