# Product F6_SOL_um Leveraged DCA Results

## 1. This is not the scalp bot
Long-only BTCUSDT perp DCA with technical limit adds and a 1% maintenance-margin-ratio cap. Start equity $10,000. Holds until +2% from average entry. A 50% *price* stop is past liquidation on this leverage, so F3 (if enabled) flattens when wallet falls to 50% of equity at the first fill of that basket. Do not wire into main.py.

## 2. Margin-ratio meaning
MR = qty * mark * 0.4% / wallet, capped at 1% after every fill. That is not a 1% stop. With ~0 UPNL it allows about 2.50× notional and roughly a 39.6% further decline to liquidation.

## 3. Remaining balance (last completed 1h, path-dependent)

| cost_model   | as_of                            |   btc_close | liquidated   | in_position   |   remaining_mark_usdt |    qty |   avg_entry |   unrealized_usdt |   mr_pct |   start_equity_usdt |   if_flatten_today_usdt |
|:-------------|:---------------------------------|------------:|:-------------|:--------------|----------------------:|-------:|------------:|------------------:|---------:|--------------------:|------------------------:|
| A_optimistic | 2026-09-10 02:59:59.999000+00:00 |      101.83 | False        | True          |               7700.27 | 160.18 |      102.39 |            -89.79 |     0.85 |            10000.00 |                 7692.93 |
| B_decision   | 2026-09-10 02:59:59.999000+00:00 |      101.83 | False        | True          |               7225.47 | 160.18 |      102.40 |            -90.54 |     0.90 |            10000.00 |                 7215.69 |

remaining_mark_usdt is the live wallet at that candle (open inventory marked). if_flatten_today_usdt is if you taker-close now. Split tables do not chain: each split adds its own trades onto a fresh $10,000.

## 4. First risk exit (SL50 or liquidation)

| cost_model   | risk_exit   |   liquidations |   baskets_before_liq |   pnl_before_liq_usdt |   equity_before_doomed_usdt |   liq_basket_pnl_usdt |   liq_fees_usdt |   ending_usdt | doomed_entry              | liq_time                         |   doomed_hold_days |   days_first_entry_to_liq |   days_last_tp_to_liq | last_tp_time                     |
|:-------------|:------------|---------------:|---------------------:|----------------------:|----------------------------:|----------------------:|----------------:|--------------:|:--------------------------|:---------------------------------|-------------------:|--------------------------:|----------------------:|:---------------------------------|
| A_optimistic | SL50        |              0 |                   73 |              11654.57 |                    21654.57 |              -8006.52 |            5.80 |      13648.04 | 2024-04-01 05:00:00+00:00 | 2024-04-13 20:59:59.999000+00:00 |              12.67 |                     99.87 |                 13.08 | 2024-03-31 18:59:59.999000+00:00 |
| B_decision   | SL50        |              0 |                   74 |              11790.19 |                    21790.19 |              -8008.70 |            7.25 |      13781.49 | 2024-04-01 05:00:00+00:00 | 2024-04-13 20:59:59.999000+00:00 |              12.67 |                     99.87 |                 13.08 | 2024-03-31 18:59:59.999000+00:00 |

PnL before that exit is realized round-trips only.

## 5. Counts
- 1h bars: 23541
- Cost A baskets: 366
- Cost A events: 1420

## 6. Train / validate / holdout (dollars and %)

| product   | cost_model   | split    |   baskets |   net_profit_usdt |   ending_equity_usdt |   net_profit_pct |   profit_factor |   win_rate |   avg_hold_hours |   avg_fills |   max_dd_pct |   expectancy_usdt |   fees_pct_start_equity |   liquidations |   tp_exits |   sl50_exits |   emergency_exits |   mtm_exits |   time_in_market_pct |   max_mr |   sharpe_ann |
|:----------|:-------------|:---------|----------:|------------------:|---------------------:|-----------------:|----------------:|-----------:|-----------------:|------------:|-------------:|------------------:|------------------------:|---------------:|-----------:|-------------:|------------------:|------------:|---------------------:|---------:|-------------:|
| F6_SOL_um | A_optimistic | train    |       222 |         12751.4   |            22751.4   |        127.514   |        1.53088  |    98.6486 |          50.018  |     2.87838 |      64.6854 |          57.4388  |                3.96328  |              0 |        219 |            3 |                 0 |           0 |              80.3503 |  1.08715 |     0.87931  |
| F6_SOL_um | A_optimistic | validate |        83 |        -10792     |             -791.967 |       -107.92    |        0.550701 |    96.3855 |          52.253  |     2.96386 |      78.3402 |        -130.024   |                1.53711  |              0 |         80 |            3 |                 0 |           0 |              79.4067 |  1.16911 |    -0.755391 |
| F6_SOL_um | A_optimistic | holdout  |        61 |           288.124 |            10288.1   |          2.88124 |        1.03555  |    96.7213 |          61.8197 |     2.70492 |      71.401  |           4.72334 |                0.988022 |              0 |         59 |            1 |                 0 |           1 |              80.069  |  1.50151 |     0.401813 |
| F6_SOL_um | B_decision   | train    |       222 |         12808.7   |            22808.7   |        128.087   |        1.53311  |    98.6486 |          50.027  |     2.88739 |      64.3996 |          57.6967  |                4.01814  |              0 |        219 |            3 |                 0 |           0 |              80.3656 |  1.08724 |     0.879599 |
| F6_SOL_um | B_decision   | validate |        82 |        -11202.2   |            -1202.19  |       -112.022   |        0.533749 |    96.3415 |          53.0732 |     2.92683 |      79.1416 |        -136.612   |                1.54067  |              0 |         79 |            3 |                 0 |           0 |              79.6811 |  1.15723 |    -0.805127 |
| F6_SOL_um | B_decision   | holdout  |        61 |           184.374 |            10184.4   |          1.84374 |        1.02274  |    96.7213 |          61.8525 |     2.72131 |      73.7044 |           3.02253 |                1.00976  |              0 |         59 |            1 |                 0 |           1 |              80.1122 |  1.68136 |     0.405194 |

## 7. Decision
KILL

## 8. One sentence
Cost B train or validate lost money.

## 9. Next step
If KILL, do not add more indicators. If PAPER-OTHER-PRODUCT, keep it off the scalp Docker path.

## 10. Sample baskets (Cost A)

| cost_model   | entry_time                | exit_time                        | exit_reason   |   avg_entry |     exit |   fills |   safety_orders |      qty |   pnl_net |     fees |   hold_hours | taker_exit   |
|:-------------|:--------------------------|:---------------------------------|:--------------|------------:|---------:|--------:|----------------:|---------:|----------:|---------:|-------------:|:-------------|
| A_optimistic | 2024-01-05 00:00:00+00:00 | 2024-01-09 04:59:59.999000+00:00 | TP            |     99.0933 | 101.075  |       6 |               5 | 227.059  |  445.41   | 4.59     |          101 | False        |
| A_optimistic | 2024-01-09 12:00:00+00:00 | 2024-01-09 13:59:59.999000+00:00 | TP            |     98.8992 | 100.877  |       1 |               0 |  20.2068 |   39.5611 | 0.407681 |            2 | False        |
| A_optimistic | 2024-01-09 14:00:00+00:00 | 2024-01-09 16:59:59.999000+00:00 | TP            |     99.0384 | 101.019  |       1 |               0 |  20.1784 |   39.5611 | 0.407681 |            3 | False        |
| A_optimistic | 2024-01-09 18:00:00+00:00 | 2024-01-09 22:59:59.999000+00:00 | TP            |     97.3852 |  99.3329 |       4 |               3 | 118.316  |  228.094  | 2.35054  |            5 | False        |
| A_optimistic | 2024-01-09 23:00:00+00:00 | 2024-01-10 04:59:59.999000+00:00 | TP            |     98.4174 | 100.386  |       2 |               1 |  45.6879 |   89.0125 | 0.917283 |            6 | False        |
| A_optimistic | 2024-01-10 06:00:00+00:00 | 2024-01-10 18:59:59.999000+00:00 | TP            |     96.1686 |  98.0919 |       5 |               4 | 170.547  |  324.679  | 3.34585  |           13 | False        |
| A_optimistic | 2024-01-10 19:00:00+00:00 | 2024-01-10 21:59:59.999000+00:00 | TP            |     96.2703 |  98.1957 |       2 |               1 |  46.7069 |   89.0125 | 0.917283 |            3 | False        |
| A_optimistic | 2024-01-11 06:00:00+00:00 | 2024-01-11 09:59:59.999000+00:00 | TP            |     99.0635 | 101.045  |       1 |               0 |  20.1733 |   39.5611 | 0.407681 |            4 | False        |
| A_optimistic | 2024-01-11 15:00:00+00:00 | 2024-01-11 20:59:59.999000+00:00 | TP            |    100.38   | 102.387  |       3 |               2 |  75.9021 |  150.827  | 1.55429  |            6 | False        |
| A_optimistic | 2024-01-12 01:00:00+00:00 | 2024-01-12 05:59:59.999000+00:00 | TP            |     97.6    |  99.552  |       1 |               0 |  20.4758 |   39.5611 | 0.407681 |            5 | False        |

