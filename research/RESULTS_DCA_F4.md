# Product F4_dca_mr05_sl80 Leveraged DCA Results

## 1. This is not the scalp bot
Long-only BTCUSDT perp DCA with technical limit adds and a 0.5% maintenance-margin-ratio cap. Start equity $10,000. Holds until +2% from average entry. A 50% *price* stop is past liquidation on this leverage, so F3 (if enabled) flattens when wallet falls to 50% of equity at the first fill of that basket. Do not wire into main.py.

## 2. Margin-ratio meaning
MR = qty * mark * 0.4% / wallet, capped at 0.5% after every fill. That is not a 0.5% stop. With ~0 UPNL it allows about 1.25× notional and roughly a 79.6% further decline to liquidation.

## 3. Remaining balance (last completed 1h, path-dependent)

| cost_model   | as_of                            |   btc_close | liquidated   | in_position   |   remaining_mark_usdt |   qty |   avg_entry |   unrealized_usdt |   mr_pct |   start_equity_usdt |   if_flatten_today_usdt |
|:-------------|:---------------------------------|------------:|:-------------|:--------------|----------------------:|------:|------------:|------------------:|---------:|--------------------:|------------------------:|
| A_optimistic | 2026-09-08 00:59:59.999000+00:00 |    79286.90 | False        | True          |              10693.87 |  0.18 |   120601.52 |          -7623.36 |     0.55 |            10000.00 |                10687.29 |
| B_decision   | 2026-09-08 00:59:59.999000+00:00 |    79286.90 | False        | True          |              10677.31 |  0.18 |   120607.18 |          -7613.28 |     0.55 |            10000.00 |                10668.55 |

remaining_mark_usdt is the live wallet at that candle (open inventory marked). if_flatten_today_usdt is if you taker-close now. Split tables do not chain: each split adds its own trades onto a fresh $10,000.

## 4. First risk exit (SL50 or liquidation)

| cost_model   | risk_exit   |   liquidations |   baskets_before_liq |   pnl_before_liq_usdt |   equity_before_doomed_usdt |   liq_basket_pnl_usdt |   liq_fees_usdt |   ending_usdt | doomed_entry   | liq_time   |   doomed_hold_days |   days_first_entry_to_liq |   days_last_tp_to_liq | last_tp_time   |
|:-------------|:------------|---------------:|---------------------:|----------------------:|----------------------------:|----------------------:|----------------:|--------------:|:---------------|:-----------|-------------------:|--------------------------:|----------------------:|:---------------|
| A_optimistic |             |              0 |                  104 |               4410.25 |                    14410.25 |                  0.00 |            0.00 |      14410.25 |                |            |               0.00 |                      0.00 |                  0.00 |                |
| B_decision   |             |              0 |                  104 |               4393.49 |                    14393.49 |                  0.00 |            0.00 |      14393.49 |                |            |               0.00 |                      0.00 |                  0.00 |                |

PnL before that exit is realized round-trips only.

## 5. Counts
- 1h bars: 23491
- Cost A baskets: 104
- Cost A events: 397

## 6. Train / validate / holdout (dollars and %)

| product          | cost_model   | split    |   baskets |   net_profit_usdt |   ending_equity_usdt |   net_profit_pct |   profit_factor |   win_rate |   avg_hold_hours |   avg_fills |   max_dd_pct |   expectancy_usdt |   fees_pct_start_equity |   liquidations |   tp_exits |   sl50_exits |   emergency_exits |   mtm_exits |   time_in_market_pct |   max_mr |   sharpe_ann |
|:-----------------|:-------------|:---------|----------:|------------------:|---------------------:|-----------------:|----------------:|-----------:|-----------------:|------------:|-------------:|------------------:|------------------------:|---------------:|-----------:|-------------:|------------------:|------------:|---------------------:|---------:|-------------:|
| F4_dca_mr05_sl80 | A_optimistic | train    |        93 |          10326    |             20326    |         103.26   |      inf        |   100      |          122.194 |     2.76344 |      34.0579 |           111.032 |                1.06411  |              0 |         93 |            0 |                 0 |           0 |              85.911  | 0.485798 |      1.08966 |
| F4_dca_mr05_sl80 | A_optimistic | validate |        11 |          -5915.75 |              4084.25 |         -59.1575 |        0.224666 |    90.9091 |          920.091 |     3.27273 |      57.6938 |          -537.796 |                0.235166 |              0 |         10 |            0 |                 0 |           1 |              95.4218 | 0.550992 |     -1.86545 |
| F4_dca_mr05_sl80 | A_optimistic | holdout  |         0 |              0    |             10000    |           0      |        0        |     0      |            0     |     0       |      39.7057 |             0     |                0        |              0 |          0 |            0 |                 0 |           0 |               0      | 0.60723  |      0       |
| F4_dca_mr05_sl80 | B_decision   | train    |        93 |          10305.9  |             20305.9  |         103.059  |      inf        |   100      |          122.258 |     2.76344 |      34.0642 |           110.816 |                1.06337  |              0 |         93 |            0 |                 0 |           0 |              85.9569 | 0.485925 |      1.0878  |
| F4_dca_mr05_sl80 | B_decision   | validate |        11 |          -5912.36 |              4087.64 |         -59.1236 |        0.224308 |    90.9091 |          920.091 |     3.27273 |      57.699  |          -537.487 |                0.249444 |              0 |         10 |            0 |                 0 |           1 |              95.4218 | 0.551056 |     -1.86612 |
| F4_dca_mr05_sl80 | B_decision   | holdout  |         0 |              0    |             10000    |           0      |        0        |     0      |            0     |     0       |      39.709  |             0     |                0        |              0 |          0 |            0 |                 0 |           0 |               0      | 0.607313 |      0       |

## 7. Decision
INCONCLUSIVE

## 8. One sentence
Holdout baskets < 8; cannot pass this product.

## 9. Next step
If KILL, do not add more indicators. If PAPER-OTHER-PRODUCT, keep it off the scalp Docker path.

## 10. Sample baskets (Cost A)

| cost_model   | entry_time                | exit_time                        | exit_reason   |   avg_entry |    exit |   fills |   safety_orders |       qty |   pnl_net |     fees |   hold_hours | taker_exit   |
|:-------------|:--------------------------|:---------------------------------|:--------------|------------:|--------:|--------:|----------------:|----------:|----------:|---------:|-------------:|:-------------|
| A_optimistic | 2024-01-03 11:00:00+00:00 | 2024-01-04 15:59:59.999000+00:00 | TP            |     43138.9 | 44001.7 |       4 |               3 | 0.133548  |  114.047  | 1.17527  |           29 | False        |
| A_optimistic | 2024-01-05 01:00:00+00:00 | 2024-01-05 20:59:59.999000+00:00 | TP            |     43554.5 | 44425.6 |       2 |               1 | 0.0521901 |   44.9985 | 0.463715 |           20 | False        |
| A_optimistic | 2024-01-05 21:00:00+00:00 | 2024-01-07 13:59:59.999000+00:00 | TP            |     43533.9 | 44404.5 |       2 |               1 | 0.0524425 |   45.1948 | 0.465737 |           41 | False        |
| A_optimistic | 2024-01-07 16:00:00+00:00 | 2024-01-08 11:59:59.999000+00:00 | TP            |     43678.2 | 44551.8 |       2 |               1 | 0.0524942 |   45.3893 | 0.467742 |           20 | False        |
| A_optimistic | 2024-01-09 12:00:00+00:00 | 2024-01-10 17:59:59.999000+00:00 | TP            |     45443.2 | 46352.1 |       4 |               3 | 0.129856  |  116.818  | 1.20382  |           30 | False        |
| A_optimistic | 2024-01-10 20:00:00+00:00 | 2024-01-10 22:59:59.999000+00:00 | TP            |     45602.4 | 46514.5 |       2 |               1 | 0.0510614 |   46.0955 | 0.475019 |            3 | False        |
| A_optimistic | 2024-01-11 03:00:00+00:00 | 2024-01-11 10:59:59.999000+00:00 | TP            |     45919.4 | 46837.8 |       2 |               1 | 0.0509323 |   46.2985 | 0.477112 |            8 | False        |
| A_optimistic | 2024-01-16 18:00:00+00:00 | 2024-01-26 18:59:59.999000+00:00 | TP            |     41357.9 | 42185   |       6 |               5 | 0.284211  |  232.689  | 2.39789  |          241 | False        |
| A_optimistic | 2024-01-27 08:00:00+00:00 | 2024-01-28 04:59:59.999000+00:00 | TP            |     41538.4 | 42369.1 |       1 |               0 | 0.0256266 |   21.0726 | 0.217155 |           21 | False        |
| A_optimistic | 2024-01-28 13:00:00+00:00 | 2024-01-29 16:59:59.999000+00:00 | TP            |     42007.6 | 42847.8 |       2 |               1 | 0.0571256 |   47.5047 | 0.489541 |           28 | False        |

