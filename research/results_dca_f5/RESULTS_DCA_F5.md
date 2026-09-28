# Product F5_dca_mr2_sl80 Leveraged DCA Results

## 1. This is not the scalp bot
Long-only BTCUSDT perp DCA with technical limit adds and a 2% maintenance-margin-ratio cap. Start equity $10,000. Holds until +2% from average entry. A 50% *price* stop is past liquidation on this leverage, so F3 (if enabled) flattens when wallet falls to 50% of equity at the first fill of that basket. Do not wire into main.py.

## 2. Margin-ratio meaning
MR = qty * mark * 0.4% / wallet, capped at 2% after every fill. That is not a 2% stop. With ~0 UPNL it allows about 5.00× notional and roughly a 19.6% further decline to liquidation.

## 3. Remaining balance (last completed 1h, path-dependent)

| cost_model   | as_of                            |   btc_close | liquidated   | in_position   |   remaining_mark_usdt |   qty |   avg_entry |   unrealized_usdt |   mr_pct |   start_equity_usdt |   if_flatten_today_usdt |
|:-------------|:---------------------------------|------------:|:-------------|:--------------|----------------------:|------:|------------:|------------------:|---------:|--------------------:|------------------------:|
| A_optimistic | 2026-09-08 00:59:59.999000+00:00 |    79286.90 | False        | False         |                 91.23 |  0.00 |         nan |              0.00 |     0.00 |            10000.00 |                   91.23 |
| B_decision   | 2026-09-08 00:59:59.999000+00:00 |    79286.90 | False        | False         |                 88.83 |  0.00 |         nan |              0.00 |     0.00 |            10000.00 |                   88.83 |

remaining_mark_usdt is the live wallet at that candle (open inventory marked). if_flatten_today_usdt is if you taker-close now. Split tables do not chain: each split adds its own trades onto a fresh $10,000.

## 4. First risk exit (SL50 or liquidation)

| cost_model   | risk_exit   |   liquidations |   baskets_before_liq |   pnl_before_liq_usdt |   equity_before_doomed_usdt |   liq_basket_pnl_usdt |   liq_fees_usdt |   ending_usdt | doomed_entry              | liq_time                         |   doomed_hold_days |   days_first_entry_to_liq |   days_last_tp_to_liq | last_tp_time                     |
|:-------------|:------------|---------------:|---------------------:|----------------------:|----------------------------:|----------------------:|----------------:|--------------:|:--------------------------|:---------------------------------|-------------------:|--------------------------:|----------------------:|:---------------------------------|
| A_optimistic | SL50        |              0 |                   47 |              27786.56 |                    37786.56 |             -27262.16 |           52.90 |      10524.40 | 2024-06-07 14:00:00+00:00 | 2024-07-04 08:59:59.999000+00:00 |              26.79 |                    182.92 |                 26.83 | 2024-06-07 12:59:59.999000+00:00 |
| B_decision   | SL50        |              0 |                   47 |              27716.52 |                    37716.52 |             -27218.73 |           65.98 |      10497.79 | 2024-06-07 14:00:00+00:00 | 2024-07-04 08:59:59.999000+00:00 |              26.79 |                    182.92 |                 26.83 | 2024-06-07 12:59:59.999000+00:00 |

PnL before that exit is realized round-trips only.

## 5. Counts
- 1h bars: 23491
- Cost A baskets: 184
- Cost A events: 704

## 6. Train / validate / holdout (dollars and %)

| product         | cost_model   | split    |   baskets |   net_profit_usdt |   ending_equity_usdt |   net_profit_pct |   profit_factor |   win_rate |   avg_hold_hours |   avg_fills |   max_dd_pct |   expectancy_usdt |   fees_pct_start_equity |   liquidations |   tp_exits |   sl50_exits |   emergency_exits |   mtm_exits |   time_in_market_pct |   max_mr |   sharpe_ann |
|:----------------|:-------------|:---------|----------:|------------------:|---------------------:|-----------------:|----------------:|-----------:|-----------------:|------------:|-------------:|------------------:|------------------------:|---------------:|-----------:|-------------:|------------------:|------------:|---------------------:|---------:|-------------:|
| F5_dca_mr2_sl80 | A_optimistic | train    |       150 |          -354.033 |              9645.97 |         -3.54033 |        0.991704 |    98      |           65.7   |     2.75333 |      97.5836 |          -2.36022 |                5.18376  |              0 |        147 |            3 |                 0 |           0 |              73.933  |  5.6712  |     0.762234 |
| F5_dca_mr2_sl80 | A_optimistic | validate |        34 |         -3936.62  |              6063.38 |        -39.3662  |        0.364246 |    91.1765 |          130.588 |     3.11765 |      98.5743 |        -115.783   |                0.351686 |              0 |         31 |            3 |                 0 |           0 |              76.2174 |  6.28517 |    -2.22238  |
| F5_dca_mr2_sl80 | A_optimistic | holdout  |         0 |             0     |             10000    |          0       |        0        |     0      |            0     |     0       |       0      |           0       |                0        |              0 |          0 |            0 |                 0 |           0 |               0      |  0       |     0        |
| F5_dca_mr2_sl80 | B_decision   | train    |       150 |          -428.646 |              9571.35 |         -4.28646 |        0.989918 |    98      |           65.72  |     2.75333 |      97.5898 |          -2.85764 |                5.36628  |              0 |        147 |            3 |                 0 |           0 |              73.9559 |  5.76249 |     0.757832 |
| F5_dca_mr2_sl80 | B_decision   | validate |        34 |         -3873.3   |              6126.7  |        -38.733   |        0.363748 |    91.1765 |          130.588 |     3.11765 |      98.5883 |        -113.921   |                0.374949 |              0 |         31 |            3 |                 0 |           0 |              76.2174 |  6.28988 |    -2.22733  |
| F5_dca_mr2_sl80 | B_decision   | holdout  |         0 |             0     |             10000    |          0       |        0        |     0      |            0     |     0       |       0      |           0       |                0        |              0 |          0 |            0 |                 0 |           0 |               0      |  0       |     0        |

## 7. Decision
INCONCLUSIVE

## 8. One sentence
Holdout baskets < 8; cannot pass this product.

## 9. Next step
If KILL, do not add more indicators. If PAPER-OTHER-PRODUCT, keep it off the scalp Docker path.

## 10. Sample baskets (Cost A)

| cost_model   | entry_time                | exit_time                        | exit_reason   |   avg_entry |    exit |   fills |   safety_orders |      qty |   pnl_net |     fees |   hold_hours | taker_exit   |
|:-------------|:--------------------------|:---------------------------------|:--------------|------------:|--------:|--------:|----------------:|---------:|----------:|---------:|-------------:|:-------------|
| A_optimistic | 2024-01-03 11:00:00+00:00 | 2024-01-04 15:59:59.999000+00:00 | TP            |     43138.9 | 44001.7 |       4 |               3 | 0.534193 |   456.189 |  4.70108 |           29 | False        |
| A_optimistic | 2024-01-05 01:00:00+00:00 | 2024-01-05 20:59:59.999000+00:00 | TP            |     43554.5 | 44425.6 |       2 |               1 | 0.215612 |   185.902 |  1.91574 |           20 | False        |
| A_optimistic | 2024-01-05 21:00:00+00:00 | 2024-01-07 13:59:59.999000+00:00 | TP            |     43533.9 | 44404.5 |       2 |               1 | 0.219477 |   189.144 |  1.94915 |           41 | False        |
| A_optimistic | 2024-01-07 16:00:00+00:00 | 2024-01-08 11:59:59.999000+00:00 | TP            |     43678.2 | 44551.8 |       2 |               1 | 0.222518 |   192.401 |  1.98272 |           20 | False        |
| A_optimistic | 2024-01-09 12:00:00+00:00 | 2024-01-10 17:59:59.999000+00:00 | TP            |     45443.2 | 46352.1 |       4 |               3 | 0.557621 |   501.633 |  5.16938 |           30 | False        |
| A_optimistic | 2024-01-10 20:00:00+00:00 | 2024-01-10 22:59:59.999000+00:00 | TP            |     45602.4 | 46514.5 |       2 |               1 | 0.226517 |   204.487 |  2.10726 |            3 | False        |
| A_optimistic | 2024-01-11 03:00:00+00:00 | 2024-01-11 10:59:59.999000+00:00 | TP            |     45919.4 | 46837.8 |       2 |               1 | 0.228917 |   208.091 |  2.1444  |            8 | False        |
| A_optimistic | 2024-01-16 18:00:00+00:00 | 2024-01-26 18:59:59.999000+00:00 | TP            |     41357.9 | 42185   |       6 |               5 | 1.29412  |  1059.52  | 10.9185  |          241 | False        |
| A_optimistic | 2024-01-27 08:00:00+00:00 | 2024-01-28 04:59:59.999000+00:00 | TP            |     41538.4 | 42369.1 |       1 |               0 | 0.12342  |   101.487 |  1.04584 |           21 | False        |
| A_optimistic | 2024-01-28 13:00:00+00:00 | 2024-01-29 16:59:59.999000+00:00 | TP            |     42007.6 | 42847.8 |       2 |               1 | 0.27671  |   230.107 |  2.37128 |           28 | False        |

