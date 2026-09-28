# Experiment C Grid Results

## Data range and source
Binance USDT-M public BTCUSDT perpetual 1h klines for grid marks and completed 4h klines for ADX(14), from 2024-01-01 through latest available during the run. Data is cached in data/htf via the shared public loader.

## Frozen grid definition
Center: 24h rolling VWAP from 1h typical price * volume. Band: +/-3%. Arithmetic levels: 10 buys below center and 10 sells above center. Allocated capital: 30% of equity, equal quote per level. Inventory cap: abs net BTC notional <= 15% of allocated capital. Grid ON requires completed 4h ADX < 18. Grid OFF/flatten triggers on completed 4h ADX > 25 or 1h close beyond the grid band by 1.5 * 1h ATR(14).

## Metrics

| split    |   net_profit_pct |   max_inventory_dd_pct |   max_equity_dd_pct |   time_in_grid_pct |   flatten_events |   grid_on_profit |   flatten_pnl |   worst_month_pct |   fees_pct_equity |   fills |   ending_equity |
|:---------|-----------------:|-----------------------:|--------------------:|-------------------:|-----------------:|-----------------:|--------------:|------------------:|------------------:|--------:|----------------:|
| train    |         -4.60463 |                8.75438 |             4.64305 |            2.41917 |              188 |         -461.304 |      -81.8509 |         -0.7164   |          0.999197 |    1083 |         9539.54 |
| validate |         -1.32707 |                6.00333 |             1.59606 |            5.16118 |              107 |         -126.433 |      -38.1252 |         -0.713966 |          0.47133  |     541 |         9413.39 |
| holdout  |         -1.81892 |                6.26981 |             1.88918 |            2.82833 |               64 |         -172.754 |      -26.1668 |         -0.723518 |          0.318652 |     360 |         9242.17 |

## Holdout decision
Holdout net=-1.8189%, max equity DD=1.8892%, grid_on_profit=-172.75, flatten_pnl=-26.17.

## PASS/PAPER/KILL
KILL

## Final sentence
no automated directional or grid bot from this research program.

