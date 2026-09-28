#!/usr/bin/env python3
"""
Isolates whether the negative expected value found by backtest_grid_search.py is a
FEE problem or a SIGNAL problem: reruns the best-performing configurations with the
per-fill fee hypothetically lowered toward zero. If performance turns solidly positive
at low/zero fees, the edge is real but currently eaten by costs (fixable via lower fee
tier / rebates). If it stays flat/negative even at zero fees, there is no real
reversion edge at this timeframe (not fixable by cost reduction alone).
Read-only research tool; uses the cached klines, does not touch the live service.
"""
import json

from backtest_gap_reversion import CACHE_PATH, simulate

with open(CACHE_PATH) as f:
    klines = json.load(f)

closes = {s: {c[0]: float(c[4]) for c in candles} for s, candles in klines.items()}
common_times = sorted(set.intersection(*(set(closes[s].keys()) for s in closes)))
series = {s: [closes[s][t] for t in common_times] for s in closes}

configs = [
    ("BTCUSDT", "ETHUSDT", 0.0040, 0.0030, 0.0030),
    ("BTCUSDT", "ETHUSDT", 0.0030, 0.0025, 0.0030),
    ("BTCUSDT", "ETHUSDT", 0.0020, 0.0020, 0.0042),
    ("BTCUSDT", "SOLUSDT", 0.0040, 0.0030, 0.0030),
]
fee_rates = [0.0004, 0.0002, 0.0001, 0.0]

print(f"{'pair':12s} {'thr':>6s} {'tp':>6s} {'sl':>6s} {'fee/fill':>9s} {'n':>4s} {'win%':>6s} {'total_pnl%':>11s}")
for leg1, leg2, thr, tp, sl in configs:
    for fee in fee_rates:
        trades = simulate(series[leg1], series[leg2], thr, fee_rate=fee, tp=tp, sl=sl)
        complete = [t for t in trades if t[2] != "INCOMPLETE"]
        if not complete:
            continue
        total_pct = sum(t[3] for t in complete)
        wins = sum(1 for t in complete if t[3] > 0)
        print(f"{leg1[:3]}/{leg2[:3]:8s} {thr*100:5.2f}% {tp*100:5.2f}% {sl*100:5.2f}% {fee*100:8.3f}% "
              f"{len(complete):4d} {100*wins/len(complete):5.1f}% {100*total_pct:10.3f}%")
    print()
