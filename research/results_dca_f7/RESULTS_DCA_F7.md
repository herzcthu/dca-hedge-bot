# Product F7_dca_step20k_sl80 Leveraged DCA Results

## 1. This is not the scalp bot
Long-only BTCUSDT perp DCA with technical limit adds and a 1% maintenance-margin-ratio cap. Start equity $10,000. Holds until +2% from average entry. A 50% *price* stop is past liquidation on this leverage, so F3 (if enabled) flattens when wallet falls to 50% of equity at the first fill of that basket. Do not wire into main.py.

## 2. Margin-ratio meaning
MR = qty * mark * 0.4% / wallet, capped at 1% after every fill. That is not a 1% stop. With ~0 UPNL it allows about 2.50× notional and roughly a 39.6% further decline to liquidation.

## 3. Remaining balance (last completed 1h, path-dependent)

| cost_model   | as_of                            |   btc_close | liquidated   | in_position   |   remaining_mark_usdt |   qty |   avg_entry |   unrealized_usdt |   mr_pct |   start_equity_usdt |   if_flatten_today_usdt |
|:-------------|:---------------------------------|------------:|:-------------|:--------------|----------------------:|------:|------------:|------------------:|---------:|--------------------:|------------------------:|
| A_optimistic | 2026-09-08 00:59:59.999000+00:00 |    79286.90 | False        | True          |              16007.06 |  0.10 |    79735.40 |            -42.86 |     0.19 |            10000.00 |                16003.65 |
| B_decision   | 2026-09-08 00:59:59.999000+00:00 |    79286.90 | False        | True          |              15950.03 |  0.10 |    79738.05 |            -43.11 |     0.19 |            10000.00 |                15945.49 |

remaining_mark_usdt is the live wallet at that candle (open inventory marked). if_flatten_today_usdt is if you taker-close now. Split tables do not chain: each split adds its own trades onto a fresh $10,000.

## 4. First risk exit (SL50 or liquidation)

| cost_model   | risk_exit   |   liquidations |   baskets_before_liq |   pnl_before_liq_usdt |   equity_before_doomed_usdt |   liq_basket_pnl_usdt |   liq_fees_usdt |   ending_usdt | doomed_entry              | liq_time                         |   doomed_hold_days |   days_first_entry_to_liq |   days_last_tp_to_liq | last_tp_time                     |
|:-------------|:------------|---------------:|---------------------:|----------------------:|----------------------------:|----------------------:|----------------:|--------------:|:--------------------------|:---------------------------------|-------------------:|--------------------------:|----------------------:|:---------------------------------|
| A_optimistic | SL50        |              0 |                  103 |              21477.27 |                    31477.27 |             -16013.05 |           11.60 |      15464.22 | 2025-10-06 21:00:00+00:00 | 2026-01-31 18:59:59.999000+00:00 |             116.92 |                    759.33 |                117.12 | 2025-10-06 15:59:59.999000+00:00 |
| B_decision   | SL50        |              0 |                  103 |              21449.61 |                    31449.61 |             -16017.40 |           14.50 |      15432.21 | 2025-10-06 21:00:00+00:00 | 2026-01-31 18:59:59.999000+00:00 |             116.92 |                    759.33 |                117.12 | 2025-10-06 15:59:59.999000+00:00 |

PnL before that exit is realized round-trips only.

## 5. Counts
- 1h bars: 23491
- Cost A baskets: 141
- Cost A events: 552

## 6. Train / validate / holdout (dollars and %)

| product             | cost_model   | split    |   baskets |   net_profit_usdt |   ending_equity_usdt |   net_profit_pct |   profit_factor |   win_rate |   avg_hold_hours |   avg_fills |   max_dd_pct |   expectancy_usdt |   fees_pct_start_equity |   liquidations |   tp_exits |   sl50_exits |   emergency_exits |   mtm_exits |   time_in_market_pct |   max_mr |   sharpe_ann |
|:--------------------|:-------------|:---------|----------:|------------------:|---------------------:|-----------------:|----------------:|-----------:|-----------------:|------------:|-------------:|------------------:|------------------------:|---------------:|-----------:|-------------:|------------------:|------------:|---------------------:|---------:|-------------:|
| F7_dca_step20k_sl80 | A_optimistic | train    |        93 |          17888.2  |            27888.2   |         178.882  |      inf        |   100      |          122.194 |     2.76344 |      60.0212 |           192.346 |                1.8434   |              0 |         93 |            0 |                 0 |           0 |              85.911  | 1.56166  |      1.13528 |
| F7_dca_step20k_sl80 | A_optimistic | validate |        18 |         -10223.8  |             -223.84  |        -102.238  |        0.361531 |    94.4444 |          294.944 |     3.77778 |      65.8882 |          -567.991 |                0.712579 |              0 |         17 |            1 |                 0 |           0 |              91.3923 | 1.12226  |     -1.03116 |
| F7_dca_step20k_sl80 | A_optimistic | holdout  |        30 |           4743.41 |            14743.4   |          47.4341 |      103.527    |    96.6667 |          140.267 |     2.86667 |      38.0851 |           158.114 |                0.523885 |              0 |         29 |            0 |                 0 |           1 |              91.147  | 0.743462 |      1.22361 |
| F7_dca_step20k_sl80 | B_decision   | train    |        93 |          17865.1  |            27865.1   |         178.651  |      inf        |   100      |          122.258 |     2.76344 |      60.0916 |           192.098 |                1.84335  |              0 |         93 |            0 |                 0 |           0 |              85.9569 | 1.56603  |      1.13373 |
| F7_dca_step20k_sl80 | B_decision   | validate |        18 |         -10235.6  |             -235.645 |        -102.356  |        0.360967 |    94.4444 |          294.944 |     3.77778 |      66.0015 |          -568.647 |                0.741555 |              0 |         17 |            1 |                 0 |           0 |              91.3923 | 1.12656  |     -1.02196 |
| F7_dca_step20k_sl80 | B_decision   | holdout  |        30 |           4735.85 |            14735.9   |          47.3585 |      100.383    |    96.6667 |          140.3   |     2.86667 |      38.2208 |           157.862 |                0.531445 |              0 |         29 |            0 |                 0 |           1 |              91.1688 | 0.746756 |      1.22227 |

## 7. Decision
KILL

## 8. One sentence
Cost B train or validate lost money.

## 9. Next step
If KILL, do not add more indicators. If PAPER-OTHER-PRODUCT, keep it off the scalp Docker path.

## 10. Sample baskets (Cost A)

| cost_model   | entry_time                | exit_time                        | exit_reason   |   avg_entry |    exit |   fills |   safety_orders |       qty |   pnl_net |     fees |   hold_hours | taker_exit   |
|:-------------|:--------------------------|:---------------------------------|:--------------|------------:|--------:|--------:|----------------:|----------:|----------:|---------:|-------------:|:-------------|
| A_optimistic | 2024-01-03 11:00:00+00:00 | 2024-01-04 15:59:59.999000+00:00 | TP            |     43138.9 | 44001.7 |       4 |               3 | 0.267096  |  228.094  | 2.35054  |           29 | False        |
| A_optimistic | 2024-01-05 01:00:00+00:00 | 2024-01-05 20:59:59.999000+00:00 | TP            |     43554.5 | 44425.6 |       2 |               1 | 0.103238  |   89.0125 | 0.917283 |           20 | False        |
| A_optimistic | 2024-01-05 21:00:00+00:00 | 2024-01-07 13:59:59.999000+00:00 | TP            |     43533.9 | 44404.5 |       2 |               1 | 0.103287  |   89.0125 | 0.917283 |           41 | False        |
| A_optimistic | 2024-01-07 16:00:00+00:00 | 2024-01-08 11:59:59.999000+00:00 | TP            |     43678.2 | 44551.8 |       2 |               1 | 0.102946  |   89.0125 | 0.917283 |           20 | False        |
| A_optimistic | 2024-01-09 12:00:00+00:00 | 2024-01-10 17:59:59.999000+00:00 | TP            |     45443.2 | 46352.1 |       4 |               3 | 0.253553  |  228.094  | 2.35054  |           30 | False        |
| A_optimistic | 2024-01-10 20:00:00+00:00 | 2024-01-10 22:59:59.999000+00:00 | TP            |     45602.4 | 46514.5 |       2 |               1 | 0.098602  |   89.0125 | 0.917283 |            3 | False        |
| A_optimistic | 2024-01-11 03:00:00+00:00 | 2024-01-11 10:59:59.999000+00:00 | TP            |     45919.4 | 46837.8 |       2 |               1 | 0.0979212 |   89.0125 | 0.917283 |            8 | False        |
| A_optimistic | 2024-01-16 18:00:00+00:00 | 2024-01-26 18:59:59.999000+00:00 | TP            |     41357.9 | 42185   |       6 |               5 | 0.544032  |  445.41   | 4.59     |          241 | False        |
| A_optimistic | 2024-01-27 08:00:00+00:00 | 2024-01-28 04:59:59.999000+00:00 | TP            |     41538.4 | 42369.1 |       1 |               0 | 0.0481107 |   39.5611 | 0.407681 |           21 | False        |
| A_optimistic | 2024-01-28 13:00:00+00:00 | 2024-01-29 16:59:59.999000+00:00 | TP            |     42007.6 | 42847.8 |       2 |               1 | 0.10704   |   89.0125 | 0.917283 |           28 | False        |

