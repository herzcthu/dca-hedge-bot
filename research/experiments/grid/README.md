# Experiment C: BTCUSDT Inventory Grid

Runs the frozen BTCUSDT perpetual inventory grid with a completed-4h-ADX regime
kill-switch. This is separate from the killed directional signal experiments.

Command:

```bash
docker compose build
docker compose run --rm btc-eth-hedge python -m experiments.grid.backtest_grid
```

Outputs:

- `results_grid/summary.csv`
- `results_grid/events.csv`
- `results_grid/equity.csv`
- `results_grid/monthly_returns.csv`
- `results_grid/equity_grid_buyhold.png`
- `results_grid/underwater_grid.png`
- `results_grid/fill_histogram.png`
- `RESULTS_GRID.md`
