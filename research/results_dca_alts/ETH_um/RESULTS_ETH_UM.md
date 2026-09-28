# Product F6_ETH_um Leveraged DCA Results

## 1. This is not the scalp bot
Long-only BTCUSDT perp DCA with technical limit adds and a 1% maintenance-margin-ratio cap. Start equity $10,000. Holds until +2% from average entry. A 50% *price* stop is past liquidation on this leverage, so F3 (if enabled) flattens when wallet falls to 50% of equity at the first fill of that basket. Do not wire into main.py.

## 2. Margin-ratio meaning
MR = qty * mark * 0.4% / wallet, capped at 1% after every fill. That is not a 1% stop. With ~0 UPNL it allows about 2.50× notional and roughly a 39.6% further decline to liquidation.

## 3. Remaining balance (last completed 1h, path-dependent)

| cost_model   | as_of                            |   btc_close | liquidated   | in_position   |   remaining_mark_usdt |   if_flatten_today_usdt |   qty |   avg_entry |   unrealized_usdt |   mr_pct |   start_equity_usdt |
|:-------------|:---------------------------------|------------:|:-------------|:--------------|----------------------:|------------------------:|------:|------------:|------------------:|---------:|--------------------:|
| A_optimistic | 2026-09-10 02:59:59.999000+00:00 |     2473.99 | True         | False         |                  0.00 |                    0.00 |  0.00 |         nan |              0.00 |     0.00 |            10000.00 |
| B_decision   | 2026-09-10 02:59:59.999000+00:00 |     2473.99 | True         | False         |                  0.00 |                    0.00 |  0.00 |         nan |              0.00 |     0.00 |            10000.00 |

remaining_mark_usdt is the live wallet at that candle (open inventory marked). if_flatten_today_usdt is if you taker-close now. Split tables do not chain: each split adds its own trades onto a fresh $10,000.

## 4. First risk exit (SL50 or liquidation)

| cost_model   | risk_exit   |   liquidations |   baskets_before_liq |   pnl_before_liq_usdt |   equity_before_doomed_usdt |   liq_basket_pnl_usdt |   liq_fees_usdt |   ending_usdt | doomed_entry              | liq_time                         |   doomed_hold_days |   days_first_entry_to_liq |   days_last_tp_to_liq | last_tp_time                     |
|:-------------|:------------|---------------:|---------------------:|----------------------:|----------------------------:|----------------------:|----------------:|--------------:|:--------------------------|:---------------------------------|-------------------:|--------------------------:|----------------------:|:---------------------------------|
| A_optimistic | SL50        |              0 |                   30 |               5004.05 |                    15004.05 |              -8006.52 |            5.80 |       6997.53 | 2024-06-06 19:00:00+00:00 | 2024-08-05 01:59:59.999000+00:00 |              59.29 |                    214.67 |                 60.29 | 2024-06-05 18:59:59.999000+00:00 |
| B_decision   | SL50        |              0 |                   30 |               4997.61 |                    14997.61 |              -8008.70 |            7.25 |       6988.91 | 2024-06-06 19:00:00+00:00 | 2024-08-05 01:59:59.999000+00:00 |              59.29 |                    214.67 |                 60.29 | 2024-06-05 18:59:59.999000+00:00 |

PnL before that exit is realized round-trips only.

## 5. Counts
- 1h bars: 23541
- Cost A baskets: 88
- Cost A events: 337

## 6. Train / validate / holdout (dollars and %)

| product   | cost_model   | split    |   baskets |   net_profit_usdt |   ending_equity_usdt |   net_profit_pct |   profit_factor |   win_rate |   avg_hold_hours |   avg_fills |   max_dd_pct |   expectancy_usdt |   fees_pct_start_equity |   liquidations |   tp_exits |   sl50_exits |   emergency_exits |   mtm_exits |   time_in_market_pct |   max_mr |   sharpe_ann |
|:----------|:-------------|:---------|----------:|------------------:|---------------------:|-----------------:|----------------:|-----------:|-----------------:|------------:|-------------:|------------------:|------------------------:|---------------:|-----------:|-------------:|------------------:|------------:|---------------------:|---------:|-------------:|
| F6_ETH_um | A_optimistic | train    |        88 |          -7954.96 |              2045.04 |         -79.5496 |        0.615541 |    96.5909 |              109 |     2.80682 |          100 |          -90.3973 |                 1.45587 |              1 |         85 |            2 |                 0 |           0 |              72.6939 |      100 |    -0.601294 |
| F6_ETH_um | A_optimistic | validate |         0 |              0    |             10000    |           0      |        0        |     0      |                0 |     0       |          nan |            0      |                 0       |              0 |          0 |            0 |                 0 |           0 |               0      |      100 |     0        |
| F6_ETH_um | A_optimistic | holdout  |         0 |              0    |             10000    |           0      |        0        |     0      |                0 |     0       |          nan |            0      |                 0       |              0 |          0 |            0 |                 0 |           0 |               0      |      100 |     0        |
| F6_ETH_um | B_decision   | train    |        88 |          -7949.78 |              2050.22 |         -79.4978 |        0.615192 |    96.5909 |              109 |     2.80682 |          100 |          -90.3384 |                 1.49077 |              1 |         85 |            2 |                 0 |           0 |              72.6939 |      100 |    -0.507011 |
| F6_ETH_um | B_decision   | validate |         0 |              0    |             10000    |           0      |        0        |     0      |                0 |     0       |          nan |            0      |                 0       |              0 |          0 |            0 |                 0 |           0 |               0      |      100 |     0        |
| F6_ETH_um | B_decision   | holdout  |         0 |              0    |             10000    |           0      |        0        |     0      |                0 |     0       |          nan |            0      |                 0       |              0 |          0 |            0 |                 0 |           0 |               0      |      100 |     0        |

## 7. Decision
KILL

## 8. One sentence
Cost B path includes a liquidation.

## 9. Next step
If KILL, do not add more indicators. If PAPER-OTHER-PRODUCT, keep it off the scalp Docker path.

## 10. Sample baskets (Cost A)

| cost_model   | entry_time                | exit_time                        | exit_reason   |   avg_entry |    exit |   fills |   safety_orders |      qty |   pnl_net |     fees |   hold_hours | taker_exit   |
|:-------------|:--------------------------|:---------------------------------|:--------------|------------:|--------:|--------:|----------------:|---------:|----------:|---------:|-------------:|:-------------|
| A_optimistic | 2024-01-03 10:00:00+00:00 | 2024-01-08 17:59:59.999000+00:00 | TP            |     2255.54 | 2300.65 |       6 |               5 | 9.97544  |  445.41   | 4.59     |          128 | False        |
| A_optimistic | 2024-01-09 08:00:00+00:00 | 2024-01-09 21:59:59.999000+00:00 | TP            |     2269.65 | 2315.05 |       3 |               2 | 3.35692  |  150.827  | 1.55429  |           14 | False        |
| A_optimistic | 2024-01-10 12:00:00+00:00 | 2024-01-10 15:59:59.999000+00:00 | TP            |     2356.52 | 2403.65 |       1 |               0 | 0.848048 |   39.5611 | 0.407681 |            4 | False        |
| A_optimistic | 2024-01-11 16:00:00+00:00 | 2024-01-12 11:59:59.999000+00:00 | TP            |     2584.55 | 2636.24 |       1 |               0 | 0.773225 |   39.5611 | 0.407681 |           20 | False        |
| A_optimistic | 2024-01-12 16:00:00+00:00 | 2024-01-16 21:59:59.999000+00:00 | TP            |     2548.62 | 2599.59 |       6 |               5 | 8.82832  |  445.41   | 4.59     |          102 | False        |
| A_optimistic | 2024-01-17 07:00:00+00:00 | 2024-02-11 04:59:59.999000+00:00 | TP            |     2483.92 | 2533.6  |       6 |               5 | 9.05825  |  445.41   | 4.59     |          598 | False        |
| A_optimistic | 2024-02-11 13:00:00+00:00 | 2024-02-12 15:59:59.999000+00:00 | TP            |     2493.36 | 2543.23 |       3 |               2 | 3.05574  |  150.827  | 1.55429  |           27 | False        |
| A_optimistic | 2024-02-13 13:00:00+00:00 | 2024-02-14 08:59:59.999000+00:00 | TP            |     2623.16 | 2675.62 |       2 |               1 | 1.71415  |   89.0125 | 0.917283 |           20 | False        |
| A_optimistic | 2024-02-15 21:00:00+00:00 | 2024-02-18 18:59:59.999000+00:00 | TP            |     2769.92 | 2825.31 |       3 |               2 | 2.75064  |  150.827  | 1.55429  |           70 | False        |
| A_optimistic | 2024-02-20 01:00:00+00:00 | 2024-02-20 13:59:59.999000+00:00 | TP            |     2903.39 | 2961.45 |       2 |               1 | 1.5487   |   89.0125 | 0.917283 |           13 | False        |

