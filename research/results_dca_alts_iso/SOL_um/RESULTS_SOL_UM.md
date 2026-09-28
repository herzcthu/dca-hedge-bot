# Product F6_SOL_um_iso Leveraged DCA Results

## 1. This is not the scalp bot
Long-only BTCUSDT perp DCA with technical limit adds and a 1% maintenance-margin-ratio cap. Start equity $10,000. Holds until +2% from average entry. A 50% *price* stop is past liquidation on this leverage, so F3 (if enabled) flattens when wallet falls to 50% of equity at the first fill of that basket. Do not wire into main.py.

## 2. Margin-ratio meaning
MR = qty * mark * 0.4% / wallet, capped at 1% after every fill. That is not a 1% stop. With ~0 UPNL it allows about 2.50× notional and roughly a 39.6% further decline to liquidation.

## 3. Remaining balance (last completed 1h, path-dependent)

| cost_model   | as_of                            |   btc_close | liquidated   | in_position   |   remaining_mark_usdt |    qty |   avg_entry |   unrealized_usdt |   mr_pct |   start_equity_usdt | isolated   |   idle_usdt |   if_flatten_today_usdt |
|:-------------|:---------------------------------|------------:|:-------------|:--------------|----------------------:|-------:|------------:|------------------:|---------:|--------------------:|:-----------|------------:|------------------------:|
| A_optimistic | 2026-09-10 03:59:59.999000+00:00 |      101.78 | False        | True          |               7491.78 | 121.33 |      102.39 |            -74.07 |     0.66 |            10000.00 | True       |        0.00 |                 7486.23 |
| B_decision   | 2026-09-10 03:59:59.999000+00:00 |      101.78 | False        | True          |               6512.92 | 105.48 |      102.40 |            -64.89 |     0.66 |            10000.00 | True       |        0.00 |                 6506.48 |

remaining_mark_usdt is the live wallet at that candle (open inventory marked). if_flatten_today_usdt is if you taker-close now. Split tables do not chain: each split adds its own trades onto a fresh $10,000.

## 4. First risk exit (SL50 or liquidation)

| cost_model   | risk_exit   |   liquidations |   baskets_before_liq |   pnl_before_liq_usdt |   equity_before_doomed_usdt |   liq_basket_pnl_usdt |   liq_fees_usdt |   ending_usdt | doomed_entry              | liq_time                         |   doomed_hold_days |   days_first_entry_to_liq |   days_last_tp_to_liq | last_tp_time                     |
|:-------------|:------------|---------------:|---------------------:|----------------------:|----------------------------:|----------------------:|----------------:|--------------:|:--------------------------|:---------------------------------|-------------------:|--------------------------:|----------------------:|:---------------------------------|
| A_optimistic | SL50        |              0 |                   73 |              11654.57 |                    21654.57 |              -8006.52 |            5.80 |      13648.04 | 2024-04-01 05:00:00+00:00 | 2024-04-13 20:59:59.999000+00:00 |              12.67 |                     99.87 |                 13.08 | 2024-03-31 18:59:59.999000+00:00 |
| B_decision   | SL50        |              0 |                   74 |              11790.19 |                    21790.19 |              -8008.70 |            7.25 |      13781.49 | 2024-04-01 05:00:00+00:00 | 2024-04-13 20:59:59.999000+00:00 |              12.67 |                     99.87 |                 13.08 | 2024-03-31 18:59:59.999000+00:00 |

PnL before that exit is realized round-trips only.

## 5. Counts
- 1h bars: 23542
- Cost A baskets: 378
- Cost A events: 1468

## 6. Train / validate / holdout (dollars and %)

| product       | cost_model   | split    |   baskets |   net_profit_usdt |   ending_equity_usdt |   net_profit_pct |   profit_factor |   win_rate |   avg_hold_hours |   avg_fills |   max_dd_pct |   expectancy_usdt |   fees_pct_start_equity |   liquidations |   tp_exits |   sl50_exits |   emergency_exits |   mtm_exits |   time_in_market_pct |   max_mr |   sharpe_ann |
|:--------------|:-------------|:---------|----------:|------------------:|---------------------:|-----------------:|----------------:|-----------:|-----------------:|------------:|-------------:|------------------:|------------------------:|---------------:|-----------:|-------------:|------------------:|------------:|---------------------:|---------:|-------------:|
| F6_SOL_um_iso | A_optimistic | train    |       222 |         12751.4   |            22751.4   |        127.514   |        1.53088  |    98.6486 |          50.018  |     2.87838 |      64.6854 |          57.4388  |                3.96328  |              0 |        219 |            3 |                 0 |           0 |              80.3503 |  2.71728 |  0.87931     |
| F6_SOL_um_iso | A_optimistic | validate |        87 |        -10318     |             -318.011 |       -103.18    |        0.570433 |    96.5517 |          49.4023 |     2.98851 |      77.4384 |        -118.598   |                1.58595  |              0 |         84 |            3 |                 0 |           0 |              78.6694 |  2.8332  | -0.738827    |
| F6_SOL_um_iso | A_optimistic | holdout  |        69 |          -534.235 |             9465.76  |         -5.34235 |        0.933932 |    97.1014 |          51.7681 |     2.76812 |      68.551  |          -7.74254 |                0.885623 |              0 |         67 |            1 |                 0 |           1 |              75.5877 |  2.93042 |  0.129834    |
| F6_SOL_um_iso | B_decision   | train    |       222 |         12808.7   |            22808.7   |        128.087   |        1.53311  |    98.6486 |          50.027  |     2.88739 |      64.3996 |          57.6967  |                4.01814  |              0 |        219 |            3 |                 0 |           0 |              80.3656 |  2.71915 |  0.879599    |
| F6_SOL_um_iso | B_decision   | validate |        86 |        -10805.5   |             -805.48  |       -108.055   |        0.550261 |    96.5116 |          50.1395 |     2.96512 |      78.3606 |        -125.645   |                1.5816   |              0 |         83 |            3 |                 0 |           0 |              78.9266 |  2.834   | -0.801326    |
| F6_SOL_um_iso | B_decision   | holdout  |        69 |         -1074.53  |             8925.47  |        -10.7453  |        0.867014 |    97.1014 |          51.7681 |     2.78261 |      71.5438 |         -15.5729  |                0.849003 |              0 |         67 |            1 |                 0 |           1 |              75.5877 |  2.93121 | -0.000421867 |

## 7. Decision
KILL

## 8. One sentence
Cost B holdout round-trip expectancy is not positive.

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

