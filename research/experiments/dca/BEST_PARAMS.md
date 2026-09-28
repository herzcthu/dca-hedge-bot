# Best parameters

Cost B ending wallet, start $10,000. Use the row for that symbol. Do not copy one coin's spec onto another.

The machine-readable copy is `experiments/dca/best_params.py`.

## Hedge, USD-M 1-minute

Fixed on every row: $10,000 clip, 10% MR, range safety orders (max 10) with reclaim, peak-skip 15%, stale exit 40% / 180 days.

Source: `results_dca_run_1m_so_reclaim/hedge_tune/REPORT.md`.

| Symbol | Memory | TP | SL | Wallet | Use it |
|---|---:|---:|---:|---:|---|
| SOLUSDT | 90d | 5% | 90% (tied with 95%, no stop fired) | $223,783 | yes |
| DOGEUSDT | 180d | 8% | 90% (tied with 95%, no stop fired) | $208,700 | yes |
| BTCUSDT | 30d | 5% | 90% | $5,463 | no — every grid point finished under $10,000 |
| ETHUSDT | 180d | 5% | 90% | $45 | no — every grid point finished under $10,000 |

## Long-only, USD-M

Highest saved ending wallet for each symbol. These are different books.

| Symbol | Bar | Wallet | Spec | Source |
|---|---|---:|---|---|
| BTCUSDT | 1h | $20,903 | geometric safety orders, 1% MR, stop is 80% of the $10k clip, take-profit 2% | `RESULTS_DCA_SO.md` |
| ETHUSDT | 5m | $15,745 | range safety orders, 1% MR, stop 90% of the path to liquidation, take-profit 5%, 1h entry TTL | `results_dca_run_5m_ttl/REPORT.md` |
| SOLUSDT | 5m | $25,139 | range safety orders, 1% MR, stop 90% of the path to liquidation, take-profit 5% | `results_dca_run_5m/REPORT.md` |
| DOGEUSDT | 1m | $82,233 | range safety orders with reclaim, 10% MR, peak-skip 15% / 180d, take-profit 8%, stop 95% of the path to liquidation | `results_dca_run_1m_so_reclaim/lookback20/tune_DOGE/REPORT.md` |

## 15-minute long-only

Same range book on all four: 15m bars, 1% MR, take-profit 5%, stop 90% of the path to liquidation, no peak-skip. Source: `results_dca_run/REPORT.md`. Last bar 2026-09-10.

| Symbol | Ending wallet | Highest wallet during the run |
|---|---:|---:|
| BTCUSDT | $14,800 | $18,976 |
| ETHUSDT | $15,702 | $18,967 |
| SOLUSDT | $15,058 | $20,953 |
| DOGEUSDT | $105 | $20,953 |

No saved BTC run, 15-minute or otherwise, ends above $50,000. The 15-minute Coin-M BTC book peaked at $38,594 and ended at $22,748.
