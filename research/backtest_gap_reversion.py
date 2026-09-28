#!/usr/bin/env python3
"""
Research-only backtest: simulates the bot's gap-entry / TP-SL-TIME-exit rules against
real historical Binance Futures klines (public endpoint, no auth). Does NOT touch the
live service, does NOT place orders. Answers: of the times |gap| >= threshold, what
fraction actually reverts far enough to profit (TP) vs. keeps widening into a stop-loss
(SL) vs. sits in the dead zone until time-based exit (TIME / TIME_MAX)?

Usage: python3 backtest_gap_reversion.py
"""
import json
import os
import time
import urllib.request

BASE = "https://fapi.binance.com"
CACHE_PATH = "data/.klines_cache.json"

# Mirrors the live bot's current config (see .env) so results are directly comparable.
FEE_RATE = 0.0004          # per fill; 4 fills per round trip assumed (worst case, all-taker)
TP_PNL_FRACTION = 0.0020
SL_PNL_FRACTION = 0.0042
LOOKBACK_MIN = 15          # matches WINDOW_SEC=900s anchor window
TIME_STOP_MIN = 30         # matches TIME_STOP_SEC=1800s
MAX_HOLD_MIN = 60          # matches MAX_HOLD_SEC=3600s
DAYS_HISTORY = 5


def get_klines(symbol: str, interval: str, start_ms: int, end_ms: int) -> list:
    candles = []
    cur = start_ms
    while cur < end_ms:
        url = (f"{BASE}/fapi/v1/klines?symbol={symbol}&interval={interval}"
               f"&startTime={cur}&endTime={end_ms}&limit=1500")
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read())
        if not data:
            break
        candles.extend(data)
        cur = data[-1][0] + 60_000
        if len(data) < 1500:
            break
        time.sleep(0.2)
    return candles


def simulate(prices1, prices2, gap_enter, fee_rate=FEE_RATE, tp=TP_PNL_FRACTION, sl=SL_PNL_FRACTION,
             lookback=LOOKBACK_MIN, time_stop=TIME_STOP_MIN, max_hold=MAX_HOLD_MIN):
    n = len(prices1)
    trades = []
    i = lookback
    while i < n:
        p1_0, p2_0 = prices1[i - lookback], prices2[i - lookback]
        p1_t, p2_t = prices1[i], prices2[i]
        g = (p2_t / p2_0 - 1.0) - (p1_t / p1_0 - 1.0)
        if abs(g) >= gap_enter:
            side1, side2 = (1, -1) if g >= gap_enter else (-1, 1)
            entry1, entry2, entry_idx = p1_t, p2_t, i
            outcome = pnl_pct = exit_idx = None
            for j in range(i + 1, min(i + 1 + max_hold, n)):
                q1, q2 = prices1[j], prices2[j]
                r1 = (q1 / entry1 - 1.0) * side1
                r2 = (q2 / entry2 - 1.0) * side2
                gross_pct = r1 + r2
                net_pct = gross_pct - 4 * fee_rate
                held = j - entry_idx
                if net_pct >= tp:
                    outcome, exit_idx, pnl_pct = "TP", j, net_pct
                    break
                if net_pct <= -sl:
                    outcome, exit_idx, pnl_pct = "SL", j, net_pct
                    break
                if held >= time_stop and net_pct >= 0:
                    outcome, exit_idx, pnl_pct = "TIME", j, net_pct
                    break
                if held >= max_hold:
                    outcome, exit_idx, pnl_pct = "TIME_MAX", j, net_pct
                    break
            if outcome is None:
                exit_idx = min(i + max_hold, n - 1)
                q1, q2 = prices1[exit_idx], prices2[exit_idx]
                r1 = (q1 / entry1 - 1.0) * side1
                r2 = (q2 / entry2 - 1.0) * side2
                outcome, pnl_pct = "INCOMPLETE", (r1 + r2) - 4 * fee_rate
            trades.append((entry_idx, exit_idx, outcome, pnl_pct))
            i = exit_idx + 1
        else:
            i += 1
    return trades


def summarize(label, trades):
    complete = [t for t in trades if t[2] != "INCOMPLETE"]
    n = len(complete)
    if n == 0:
        print(f"{label}: 0 simulated trades")
        return
    wins = [t for t in complete if t[3] > 0]
    by_outcome = {}
    for t in complete:
        by_outcome.setdefault(t[2], []).append(t[3])
    total_pct = sum(t[3] for t in complete)
    print(f"{label}: n={n}  win_rate={100*len(wins)/n:.1f}%  avg_pnl_pct={100*total_pct/n:.4f}%  "
          f"total_pnl_pct={100*total_pct:.3f}%")
    for reason, vals in sorted(by_outcome.items()):
        print(f"    {reason:10s} count={len(vals):3d}  avg_pnl_pct={100*sum(vals)/len(vals):+.4f}%")


def main():
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AVAXUSDT"]
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - DAYS_HISTORY * 24 * 3600 * 1000

    if os.path.exists(CACHE_PATH):
        print(f"Loading cached klines from {CACHE_PATH} ...")
        with open(CACHE_PATH) as f:
            klines = json.load(f)
    else:
        print(f"Fetching {DAYS_HISTORY} days of 1m klines for {symbols} ...")
        klines = {s: get_klines(s, "1m", start_ms, end_ms) for s in symbols}
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w") as f:
            json.dump(klines, f)
    for s in symbols:
        print(f"  {s}: {len(klines[s])} candles")

    closes = {s: {c[0]: float(c[4]) for c in klines[s]} for s in symbols}
    common_times = sorted(set.intersection(*(set(closes[s].keys()) for s in symbols)))
    print(f"Common aligned candles: {len(common_times)}\n")

    series = {s: [closes[s][t] for t in common_times] for s in symbols}

    pairs = [
        ("BTCUSDT", "ETHUSDT", [0.0014, 0.0020, 0.0030]),
        ("BTCUSDT", "SOLUSDT", [0.0020, 0.0030, 0.0040]),
        ("ETHUSDT", "SOLUSDT", [0.0020, 0.0030, 0.0040]),
        ("SOLUSDT", "AVAXUSDT", [0.0020, 0.0030, 0.0040]),
    ]
    for leg1, leg2, thresholds in pairs:
        print(f"=== {leg1}/{leg2} ===")
        for thr in thresholds:
            trades = simulate(series[leg1], series[leg2], thr)
            summarize(f"  thr={thr*100:.2f}%", trades)
        print()


if __name__ == "__main__":
    main()
