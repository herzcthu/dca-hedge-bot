#!/usr/bin/env python3
"""
Grid-searches TP/SL/entry-threshold combinations against the same cached historical
data used by backtest_gap_reversion.py, to see whether ANY combination of these
parameters (not just the currently-configured ones) produces positive expected value
for BTC/ETH and the best-performing alt candidate (BTC/SOL). Read-only research tool;
does not touch the live service or place orders. Run backtest_gap_reversion.py first
to populate the klines cache.
"""
import json

from backtest_gap_reversion import CACHE_PATH, simulate

with open(CACHE_PATH) as f:
    klines = json.load(f)

closes = {s: {c[0]: float(c[4]) for c in candles} for s, candles in klines.items()}
common_times = sorted(set.intersection(*(set(closes[s].keys()) for s in closes)))
series = {s: [closes[s][t] for t in common_times] for s in closes}

thresholds = [0.0020, 0.0030, 0.0040]
tp_values = [0.0015, 0.0020, 0.0025, 0.0030]
sl_values = [0.0015, 0.0020, 0.0025, 0.0030]

pairs = [("BTCUSDT", "ETHUSDT"), ("BTCUSDT", "SOLUSDT")]

results = []
for leg1, leg2 in pairs:
    for thr in thresholds:
        for tp in tp_values:
            for sl in sl_values:
                trades = simulate(series[leg1], series[leg2], thr, tp=tp, sl=sl)
                complete = [t for t in trades if t[2] != "INCOMPLETE"]
                if len(complete) < 10:
                    continue
                total_pct = sum(t[3] for t in complete)
                wins = sum(1 for t in complete if t[3] > 0)
                results.append((leg1, leg2, thr, tp, sl, len(complete), wins / len(complete), total_pct))

results.sort(key=lambda r: r[7], reverse=True)
print(f"{'pair':16s} {'thr':>6s} {'tp':>6s} {'sl':>6s} {'n':>4s} {'win%':>6s} {'total_pnl%':>11s}")
for leg1, leg2, thr, tp, sl, n, win_rate, total_pct in results[:20]:
    print(f"{leg1[:3]}/{leg2[:3]:12s} {thr*100:5.2f}% {tp*100:5.2f}% {sl*100:5.2f}% {n:4d} {100*win_rate:5.1f}% {100*total_pct:10.3f}%")

print(f"\nTotal combinations tested: {len(results)}")
print(f"Combinations with positive total P&L: {sum(1 for r in results if r[7] > 0)}")
