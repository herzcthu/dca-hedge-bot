# Product F6_DOGE_um_iso Leveraged DCA Results

## 1. This is not the scalp bot
Long-only BTCUSDT perp DCA with technical limit adds and a 1% maintenance-margin-ratio cap. Start equity $10,000. Holds until +2% from average entry. A 50% *price* stop is past liquidation on this leverage, so F3 (if enabled) flattens when wallet falls to 50% of equity at the first fill of that basket. Do not wire into main.py.

## 2. Margin-ratio meaning
MR = qty * mark * 0.4% / wallet, capped at 1% after every fill. That is not a 1% stop. With ~0 UPNL it allows about 2.50× notional and roughly a 39.6% further decline to liquidation.

## 3. Remaining balance (last completed 1h, path-dependent)

| cost_model   | as_of                            |   btc_close | liquidated   | in_position   |   remaining_mark_usdt |   qty |   avg_entry |   unrealized_usdt |   mr_pct |   start_equity_usdt | isolated   |   idle_usdt |   if_flatten_today_usdt |
|:-------------|:---------------------------------|------------:|:-------------|:--------------|----------------------:|------:|------------:|------------------:|---------:|--------------------:|:-----------|------------:|------------------------:|
| A_optimistic | 2026-09-10 03:59:59.999000+00:00 |        0.09 | False        | False         |                223.46 |  0.00 |         nan |              0.00 |     0.00 |            10000.00 | True       |      223.46 |                  223.46 |
| B_decision   | 2026-09-10 03:59:59.999000+00:00 |        0.09 | False        | False         |                202.41 |  0.00 |         nan |              0.00 |     0.00 |            10000.00 | True       |      202.41 |                  202.41 |

remaining_mark_usdt is the live wallet at that candle (open inventory marked). if_flatten_today_usdt is if you taker-close now. Split tables do not chain: each split adds its own trades onto a fresh $10,000.

## 4. First risk exit (SL50 or liquidation)

| cost_model   | risk_exit   |   liquidations |   baskets_before_liq |   pnl_before_liq_usdt |   equity_before_doomed_usdt |   liq_basket_pnl_usdt |   liq_fees_usdt |   ending_usdt | doomed_entry              | liq_time                         |   doomed_hold_days |   days_first_entry_to_liq |   days_last_tp_to_liq | last_tp_time                     |
|:-------------|:------------|---------------:|---------------------:|----------------------:|----------------------------:|----------------------:|----------------:|--------------:|:--------------------------|:---------------------------------|-------------------:|--------------------------:|----------------------:|:---------------------------------|
| A_optimistic | SL50        |              0 |                   68 |              10167.08 |                    20167.08 |              -8006.52 |            5.80 |      12160.55 | 2024-04-12 12:00:00+00:00 | 2024-05-01 08:59:59.999000+00:00 |              18.87 |                    118.92 |                 19.25 | 2024-04-12 02:59:59.999000+00:00 |
| B_decision   | SL50        |              0 |                   68 |              10153.93 |                    20153.93 |              -8008.70 |            7.25 |      12145.23 | 2024-04-12 12:00:00+00:00 | 2024-05-01 08:59:59.999000+00:00 |              18.87 |                    118.92 |                 19.25 | 2024-04-12 02:59:59.999000+00:00 |

PnL before that exit is realized round-trips only.

## 5. Counts
- 1h bars: 23542
- Cost A baskets: 298
- Cost A events: 1114

## 6. Train / validate / holdout (dollars and %)

| product        | cost_model   | split    |   baskets |   net_profit_usdt |   ending_equity_usdt |   net_profit_pct |   profit_factor |   win_rate |   avg_hold_hours |   avg_fills |   max_dd_pct |   expectancy_usdt |   fees_pct_start_equity |   liquidations |   tp_exits |   sl50_exits |   emergency_exits |   mtm_exits |   time_in_market_pct |   max_mr |   sharpe_ann |
|:---------------|:-------------|:---------|----------:|------------------:|---------------------:|-----------------:|----------------:|-----------:|-----------------:|------------:|-------------:|------------------:|------------------------:|---------------:|-----------:|-------------:|------------------:|------------:|---------------------:|---------:|-------------:|
| F6_DOGE_um_iso | A_optimistic | train    |       269 |         -7002.57  |              2997.43 |        -70.0257  |        0.838453 |    97.7695 |          37.368  |     2.75465 |      96.5728 |          -26.0319 |               4.05934   |              0 |        263 |            6 |                 0 |           0 |              74.5372 |  2.68404 |    -0.291758 |
| F6_DOGE_um_iso | A_optimistic | validate |        29 |          -562.372 |              9437.63 |         -5.62372 |        0.415269 |    96.5517 |          72.9655 |     2.58621 |      81.6609 |          -19.3921 |               0.0481243 |              0 |         28 |            1 |                 0 |           0 |              36.4369 |  1.61278 |    -0.248598 |
| F6_DOGE_um_iso | A_optimistic | holdout  |         0 |             0     |             10000    |          0       |        0        |     0      |           0      |     0       |       0      |            0      |               0         |              0 |          0 |            0 |                 0 |           0 |               0      |  0       |     0        |
| F6_DOGE_um_iso | B_decision   | train    |       268 |         -7078.95  |              2921.05 |        -70.7895  |        0.83559  |    97.7612 |          37.5896 |     2.75746 |      96.8497 |          -26.414  |               4.10198   |              0 |        262 |            6 |                 0 |           0 |              74.7132 |  2.6857  |    -0.304611 |
| F6_DOGE_um_iso | B_decision   | validate |        29 |          -510.593 |              9489.41 |         -5.10593 |        0.414731 |    96.5517 |          72.9655 |     2.58621 |      81.6808 |          -17.6067 |               0.0452294 |              0 |         28 |            1 |                 0 |           0 |              36.4369 |  1.61304 |    -0.249454 |
| F6_DOGE_um_iso | B_decision   | holdout  |         0 |             0     |             10000    |          0       |        0        |     0      |           0      |     0       |       0      |            0      |               0         |              0 |          0 |            0 |                 0 |           0 |               0      |  0       |     0        |

## 7. Decision
INCONCLUSIVE

## 8. One sentence
Holdout baskets < 8; cannot pass this product.

## 9. Next step
If KILL, do not add more indicators. If PAPER-OTHER-PRODUCT, keep it off the scalp Docker path.

## 10. Sample baskets (Cost A)

| cost_model   | entry_time                | exit_time                        | exit_reason   |   avg_entry |      exit |   fills |   safety_orders |      qty |   pnl_net |     fees |   hold_hours | taker_exit   |
|:-------------|:--------------------------|:---------------------------------|:--------------|------------:|----------:|--------:|----------------:|---------:|----------:|---------:|-------------:|:-------------|
| A_optimistic | 2024-01-03 11:00:00+00:00 | 2024-01-10 23:59:59.999000+00:00 | TP            |   0.0831155 | 0.0847779 |       6 |               5 | 270707   |  445.41   | 4.59     |          181 | False        |
| A_optimistic | 2024-01-11 16:00:00+00:00 | 2024-01-11 20:59:59.999000+00:00 | TP            |   0.0838031 | 0.0854792 |       1 |               0 |  23846.8 |   39.5611 | 0.407681 |            5 | False        |
| A_optimistic | 2024-01-11 21:00:00+00:00 | 2024-01-12 12:59:59.999000+00:00 | TP            |   0.0836776 | 0.0853512 |       2 |               1 |  53735.8 |   89.0125 | 0.917283 |           16 | False        |
| A_optimistic | 2024-01-12 15:00:00+00:00 | 2024-01-14 07:59:59.999000+00:00 | TP            |   0.0810155 | 0.0826358 |       5 |               4 | 202446   |  324.679  | 3.34585  |           41 | False        |
| A_optimistic | 2024-01-16 01:00:00+00:00 | 2024-01-16 09:59:59.999000+00:00 | TP            |   0.080635  | 0.0822477 |       2 |               1 |  55763.5 |   89.0125 | 0.917283 |            9 | False        |
| A_optimistic | 2024-01-16 13:00:00+00:00 | 2024-01-20 18:59:59.999000+00:00 | TP            |   0.0786708 | 0.0802442 |       6 |               5 | 286002   |  445.41   | 4.59     |          102 | False        |
| A_optimistic | 2024-01-21 16:00:00+00:00 | 2024-02-14 17:59:59.999000+00:00 | TP            |   0.0830092 | 0.0846694 |       6 |               5 | 271054   |  445.41   | 4.59     |          578 | False        |
| A_optimistic | 2024-02-15 07:00:00+00:00 | 2024-02-15 15:59:59.999000+00:00 | TP            |   0.0852682 | 0.0869735 |       1 |               0 |  23437.1 |   39.5611 | 0.407681 |            9 | False        |
| A_optimistic | 2024-02-15 17:00:00+00:00 | 2024-02-16 02:59:59.999000+00:00 | TP            |   0.08463   | 0.0863226 |       1 |               0 |  23613.8 |   39.5611 | 0.407681 |           10 | False        |
| A_optimistic | 2024-02-16 07:00:00+00:00 | 2024-02-16 12:59:59.999000+00:00 | TP            |   0.0852883 | 0.0869941 |       2 |               1 |  52721   |   89.0125 | 0.917283 |            6 | False        |

