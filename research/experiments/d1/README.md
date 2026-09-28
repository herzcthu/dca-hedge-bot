# Experiment D1: Daily Donchian 20/10

Classic Turtle-style BTCUSDT daily breakout, long-only, spot data, all-in/all-out.

Command:

```bash
docker compose build
docker compose run --rm btc-eth-hedge python -m experiments.d1.backtest_d1
```

Outputs:

- `results_d1/summary.csv`
- `results_d1/trades.csv`
- `results_d1/equity_D1.csv`
- `results_d1/equity_BH.csv`
- `results_d1/monthly_returns.csv`
- `results_d1/equity_d1_bh_full.png`
- `results_d1/equity_d1_bh_2024.png`
- `results_d1/underwater_d1.png`
- `results_d1/pnl_hist_d1.png`
- `RESULTS_D1.md`
