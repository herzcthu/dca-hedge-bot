# Product F3_dca_sl50 Leveraged DCA Results

## 1. This is not the scalp bot
Long-only BTCUSDT perp DCA with technical limit adds and a 1% maintenance-margin-ratio cap. Start equity $10,000. Holds until +2% from average entry. A 50% *price* stop is past liquidation on this leverage, so F3 (if enabled) flattens when wallet falls to 50% of equity at the first fill of that basket. Do not wire into main.py.

## 2. Margin-ratio meaning
MR = qty * mark * 0.4% / wallet, capped at 1% after every fill. That is not a 1% stop. With ~0 UPNL it allows about 2.50× notional and roughly a 39.6% further decline to liquidation.

## 3. Remaining balance (last completed 1h, path-dependent)

| cost_model   | as_of                            |   btc_close | liquidated   | in_position   |   remaining_mark_usdt |   qty |   avg_entry |   unrealized_usdt |   mr_pct |   start_equity_usdt |   if_flatten_today_usdt |
|:-------------|:---------------------------------|------------:|:-------------|:--------------|----------------------:|------:|------------:|------------------:|---------:|--------------------:|------------------------:|
| A_optimistic | 2026-09-08 00:59:59.999000+00:00 |    79286.90 | False        | True          |               4026.95 |  0.04 |    79735.40 |            -17.35 |     0.30 |            10000.00 |                 4025.57 |
| B_decision   | 2026-09-08 00:59:59.999000+00:00 |    79286.90 | False        | True          |               3988.70 |  0.04 |    79738.05 |            -17.29 |     0.30 |            10000.00 |                 3986.88 |

remaining_mark_usdt is the live wallet at that candle (open inventory marked). if_flatten_today_usdt is if you taker-close now. Split tables do not chain: each split adds its own trades onto a fresh $10,000.

## 4. First risk exit (SL50 or liquidation)

| cost_model   | risk_exit   |   liquidations |   baskets_before_liq |   pnl_before_liq_usdt |   equity_before_doomed_usdt |   liq_basket_pnl_usdt |   liq_fees_usdt |   ending_usdt | doomed_entry              | liq_time                         |   doomed_hold_days |   days_first_entry_to_liq |   days_last_tp_to_liq | last_tp_time                     |
|:-------------|:------------|---------------:|---------------------:|----------------------:|----------------------------:|----------------------:|----------------:|--------------:|:--------------------------|:---------------------------------|-------------------:|--------------------------:|----------------------:|:---------------------------------|
| A_optimistic | SL50        |              0 |                   47 |               9757.19 |                    19757.19 |              -9190.37 |           13.42 |      10566.82 | 2024-06-07 14:00:00+00:00 | 2024-07-05 04:59:59.999000+00:00 |              27.62 |                    183.75 |                 27.67 | 2024-06-07 12:59:59.999000+00:00 |
| B_decision   | SL50        |              0 |                   47 |               9739.20 |                    19739.20 |              -9184.58 |           16.75 |      10554.62 | 2024-06-07 14:00:00+00:00 | 2024-07-05 04:59:59.999000+00:00 |              27.62 |                    183.75 |                 27.67 | 2024-06-07 12:59:59.999000+00:00 |

PnL before that exit is realized round-trips only.

## 5. Counts
- 1h bars: 23491
- Cost A baskets: 229
- Cost A events: 885

## 6. Train / validate / holdout (dollars and %)

| product     | cost_model   | split    |   baskets |   net_profit_usdt |   ending_equity_usdt |   net_profit_pct |   profit_factor |   win_rate |   avg_hold_hours |   avg_fills |   max_dd_pct |   expectancy_usdt |   fees_pct_start_equity |   liquidations |   tp_exits |   sl50_exits |   emergency_exits |   mtm_exits |   time_in_market_pct |   max_mr |   sharpe_ann |
|:------------|:-------------|:---------|----------:|------------------:|---------------------:|-----------------:|----------------:|-----------:|-----------------:|------------:|-------------:|------------------:|------------------------:|---------------:|-----------:|-------------:|------------------:|------------:|---------------------:|---------:|-------------:|
| F3_dca_sl50 | A_optimistic | train    |       150 |          2292.66  |             12292.7  |         22.9266  |        1.10963  |    98      |          66.0867 |     2.75333 |      77.2525 |          15.2844  |                2.69407  |              0 |        147 |            3 |                 0 |           0 |              74.3766 |  1.35538 |   0.409055   |
| F3_dca_sl50 | A_optimistic | validate |        36 |         -4454.16  |              5545.84 |        -44.5416  |        0.519726 |    94.4444 |         137.861  |     3.38889 |      70.104  |        -123.727   |                0.632545 |              0 |         34 |            2 |                 0 |           0 |              85.1509 |  1.40383 |  -1.06223    |
| F3_dca_sl50 | A_optimistic | holdout  |        43 |          -185.789 |              9814.21 |         -1.85789 |        0.940644 |    95.3488 |          90.1628 |     2.81395 |      58.7951 |          -4.32068 |                0.360663 |              0 |         41 |            1 |                 0 |           1 |              83.6459 |  1.35812 |   0.010814   |
| F3_dca_sl50 | B_decision   | train    |       150 |          2244.42  |             12244.4  |         22.4442  |        1.1075   |    98      |          66.1067 |     2.75333 |      77.2356 |          14.9628  |                2.76349  |              0 |        147 |            3 |                 0 |           0 |              74.3996 |  1.35559 |   0.404753   |
| F3_dca_sl50 | B_decision   | validate |        36 |         -4437.47  |              5562.53 |        -44.3747  |        0.518758 |    94.4444 |         137.861  |     3.38889 |      70.1678 |        -123.263   |                0.662295 |              0 |         34 |            2 |                 0 |           0 |              85.1509 |  1.40404 |  -1.05584    |
| F3_dca_sl50 | B_decision   | holdout  |        43 |          -190.183 |              9809.82 |         -1.90183 |        0.938763 |    95.3488 |          90.186  |     2.81395 |      58.8181 |          -4.42286 |                0.37176  |              0 |         41 |            1 |                 0 |           1 |              83.6677 |  1.35831 |   0.00646075 |

## 7. Decision
KILL

## 8. One sentence
Cost B holdout round-trip expectancy is not positive.

## 9. Next step
If KILL, do not add more indicators. If PAPER-OTHER-PRODUCT, keep it off the scalp Docker path.

## 10. Sample baskets (Cost A)

| cost_model   | entry_time                | exit_time                        | exit_reason   |   avg_entry |    exit |   fills |   safety_orders |       qty |   pnl_net |     fees |   hold_hours | taker_exit   |
|:-------------|:--------------------------|:---------------------------------|:--------------|------------:|--------:|--------:|----------------:|----------:|----------:|---------:|-------------:|:-------------|
| A_optimistic | 2024-01-03 11:00:00+00:00 | 2024-01-04 15:59:59.999000+00:00 | TP            |     43138.9 | 44001.7 |       4 |               3 | 0.267096  |  228.094  | 2.35054  |           29 | False        |
| A_optimistic | 2024-01-05 01:00:00+00:00 | 2024-01-05 20:59:59.999000+00:00 | TP            |     43554.5 | 44425.6 |       2 |               1 | 0.105522  |   90.9817 | 0.937576 |           20 | False        |
| A_optimistic | 2024-01-05 21:00:00+00:00 | 2024-01-07 13:59:59.999000+00:00 | TP            |     43533.9 | 44404.5 |       2 |               1 | 0.106493  |   91.7751 | 0.945753 |           41 | False        |
| A_optimistic | 2024-01-07 16:00:00+00:00 | 2024-01-08 11:59:59.999000+00:00 | TP            |     43678.2 | 44551.8 |       2 |               1 | 0.107055  |   92.5653 | 0.953896 |           20 | False        |
| A_optimistic | 2024-01-09 12:00:00+00:00 | 2024-01-10 17:59:59.999000+00:00 | TP            |     45443.2 | 46352.1 |       4 |               3 | 0.265974  |  239.268  | 2.46569  |           30 | False        |
| A_optimistic | 2024-01-10 20:00:00+00:00 | 2024-01-10 22:59:59.999000+00:00 | TP            |     45602.4 | 46514.5 |       2 |               1 | 0.105738  |   95.4545 | 0.98367  |            3 | False        |
| A_optimistic | 2024-01-11 03:00:00+00:00 | 2024-01-11 10:59:59.999000+00:00 | TP            |     45919.4 | 46837.8 |       2 |               1 | 0.105933  |   96.2956 | 0.992337 |            8 | False        |
| A_optimistic | 2024-01-16 18:00:00+00:00 | 2024-01-26 18:59:59.999000+00:00 | TP            |     41357.9 | 42185   |       6 |               5 | 0.593705  |  486.078  | 5.00909  |          241 | False        |
| A_optimistic | 2024-01-27 08:00:00+00:00 | 2024-01-28 04:59:59.999000+00:00 | TP            |     41538.4 | 42369.1 |       1 |               0 | 0.0545624 |   44.8663 | 0.462352 |           21 | False        |
| A_optimistic | 2024-01-28 13:00:00+00:00 | 2024-01-29 16:59:59.999000+00:00 | TP            |     42007.6 | 42847.8 |       2 |               1 | 0.121862  |  101.338  | 1.0443   |           28 | False        |

