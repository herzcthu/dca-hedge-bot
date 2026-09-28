# HTF BTCUSDT Experiments

Runs two frozen higher-timeframe BTCUSDT perpetual scalp experiments without
mutating the killed 5m strategy code.

Commands:

```bash
docker compose build
docker compose run --rm btc-eth-hedge python -m experiments.htf.backtest_htf
```

Outputs:

- `results_htf/summary.csv`
- `results_htf/trades.csv`
- `results_htf/equity_B1.csv`
- `results_htf/equity_B2.csv`
- `results_htf/monthly_returns.csv`
- `results_htf/equity_b1_b2_buyhold.png`
- `results_htf/underwater_B1_15m_trend_pullback.png`
- `results_htf/underwater_B2_1h_trend_pullback.png`
- `results_htf/pnl_hist_B1_15m_trend_pullback.png`
- `results_htf/pnl_hist_B2_1h_trend_pullback.png`
- `RESULTS_HTF.md`
