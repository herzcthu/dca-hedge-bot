#!/usr/bin/env python3
"""Runs every BTC-only scalp idea against the same 183-day 5m candle set and ranks
them by average net return per trade (fee-inclusive). Research-only; uses public
klines already cached by btc_klines_5m.py. Does not touch the live service.

Pass criterion (frozen, same as each individual script): avg_net per trade > 0.
"""

from __future__ import annotations

from btc_klines_5m import get_klines

import backtest_btc_15m_dump_fade as dump_fade
import backtest_btc_15m_impulse_fade as impulse_fade
import backtest_btc_bollinger_fade as bollinger_fade
import backtest_btc_ema_momentum as ema_momentum
import backtest_btc_rsi_reversion as rsi_reversion
import backtest_btc_vwap_reversion as vwap_reversion


def summarize(name: str, trades: list[tuple]) -> dict:
    if not trades:
        return {"name": name, "n": 0, "win_rate": 0.0, "avg_net": 0.0, "total_net": 0.0}
    total = sum(t[1] for t in trades)
    winners = sum(1 for t in trades if t[1] > 0)
    return {
        "name": name,
        "n": len(trades),
        "win_rate": winners / len(trades) * 100,
        "avg_net": total / len(trades) * 100,
        "total_net": total * 100,
    }


def main() -> None:
    candles = get_klines()
    print(f"Loaded {len(candles)} BTCUSDT 5m candles.\n")

    results = [
        summarize("RSI(14) reversion", rsi_reversion.simulate(candles)),
        summarize("Bollinger(20,2) fade", bollinger_fade.simulate(candles)),
        summarize("EMA(9/21) momentum", ema_momentum.simulate(candles)),
        summarize("Session-VWAP reversion", vwap_reversion.simulate(candles)),
        summarize("15m impulse fade (short)", impulse_fade.simulate(candles)[0]),
        summarize("15m dump fade (long)", dump_fade.simulate(candles)[0]),
    ]
    results.sort(key=lambda r: r["avg_net"], reverse=True)

    print(f"{'strategy':28s} {'n':>5s} {'win%':>7s} {'avg_net%':>10s} {'total_net%':>11s} {'verdict':>8s}")
    for r in results:
        verdict = "PASS" if r["avg_net"] > 0 and r["n"] > 0 else "FAIL"
        print(f"{r['name']:28s} {r['n']:5d} {r['win_rate']:6.1f}% {r['avg_net']:9.4f}% {r['total_net']:10.3f}% {verdict:>8s}")

    passing = [r for r in results if r["avg_net"] > 0 and r["n"] > 0]
    print()
    if passing:
        best = passing[0]
        print(f"Best passing strategy: {best['name']} (avg_net={best['avg_net']:.4f}% over n={best['n']})")
    else:
        print("No strategy passed. None of the tested scalp ideas had positive average net P&L after fees.")


if __name__ == "__main__":
    main()
