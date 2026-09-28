# Product F1_dca_leverage Leveraged DCA Results

## 1. This is not the scalp bot
Long-only BTCUSDT perp DCA with technical limit adds and a 3% maintenance-margin-ratio cap. Start equity $10,000. Holds until +2% from average entry. Do not wire into main.py.

## 2. Margin-ratio meaning
MR = qty * mark * 0.4% / wallet, capped at 3% after every fill. That is not a 3% stop. With ~0 UPNL it allows about 7.50× notional and roughly a 12.9% further decline to liquidation.

## 3. Dollar path to liquidation

| cost_model   |   liquidations |   baskets_before_liq |   pnl_before_liq_usdt |   equity_before_doomed_usdt |   liq_basket_pnl_usdt |   liq_fees_usdt |   ending_usdt | doomed_entry              | liq_time                         |   doomed_hold_days |   days_first_entry_to_liq |   days_last_tp_to_liq | last_tp_time                     |
|:-------------|---------------:|---------------------:|----------------------:|----------------------------:|----------------------:|----------------:|--------------:|:--------------------------|:---------------------------------|-------------------:|--------------------------:|----------------------:|:---------------------------------|
| A_optimistic |              1 |                   40 |              37798.80 |                    47798.80 |             -44230.01 |           91.29 |       3568.80 | 2024-04-11 11:00:00+00:00 | 2024-05-01 08:59:59.999000+00:00 |              19.92 |                    118.92 |                 20.42 | 2024-04-10 22:59:59.999000+00:00 |
| B_decision   |              1 |                   40 |              37687.54 |                    47687.54 |             -44141.71 |          113.75 |       3545.82 | 2024-04-11 11:00:00+00:00 | 2024-05-01 08:59:59.999000+00:00 |              19.92 |                    118.92 |                 20.42 | 2024-04-10 22:59:59.999000+00:00 |

PnL before liquidation is realized round-trips only (almost all TPs). The doomed basket is the open stack that hit liquidation. The sim then zeros leftover margin, so the equity chart can go to $0 even if basket-sum ending_usdt is not exactly $0.

## 4. Counts
- 1h bars: 23489
- Cost A baskets: 41
- Cost A events: 155

## 5. Train / validate / holdout (dollars and %)

| product         | cost_model   | split    |   baskets |   net_profit_usdt |   ending_equity_usdt |   net_profit_pct |   profit_factor |   win_rate |   avg_hold_hours |   avg_fills |   max_dd_pct |   expectancy_usdt |   fees_pct_start_equity |   liquidations |   tp_exits |   emergency_exits |   mtm_exits |   time_in_market_pct |   max_mr |   sharpe_ann |
|:----------------|:-------------|:---------|----------:|------------------:|---------------------:|-----------------:|----------------:|-----------:|-----------------:|------------:|-------------:|------------------:|------------------------:|---------------:|-----------:|------------------:|------------:|---------------------:|---------:|-------------:|
| F1_dca_leverage | A_optimistic | train    |        41 |          -6431.2  |              3568.8  |         -64.312  |        0.854596 |     97.561 |          46.7561 |     2.65854 |          100 |          -156.859 |                 4.80808 |              1 |         40 |                 0 |           0 |              14.3491 |      100 |   -0.0778956 |
| F1_dca_leverage | A_optimistic | validate |         0 |              0    |             10000    |           0      |        0        |      0     |           0      |     0       |          nan |             0     |                 0       |              0 |          0 |                 0 |           0 |               0      |      100 |    0         |
| F1_dca_leverage | A_optimistic | holdout  |         0 |              0    |             10000    |           0      |        0        |      0     |           0      |     0       |          nan |             0     |                 0       |              0 |          0 |                 0 |           0 |               0      |      100 |    0         |
| F1_dca_leverage | B_decision   | train    |        41 |          -6454.18 |              3545.82 |         -64.5418 |        0.853785 |     97.561 |          46.7561 |     2.65854 |          100 |          -157.419 |                 5.02619 |              1 |         40 |                 0 |           0 |              14.3491 |      100 |   -0.0786981 |
| F1_dca_leverage | B_decision   | validate |         0 |              0    |             10000    |           0      |        0        |      0     |           0      |     0       |          nan |             0     |                 0       |              0 |          0 |                 0 |           0 |               0      |      100 |    0         |
| F1_dca_leverage | B_decision   | holdout  |         0 |              0    |             10000    |           0      |        0        |      0     |           0      |     0       |          nan |             0     |                 0       |              0 |          0 |                 0 |           0 |               0      |      100 |    0         |

## 6. Decision
KILL

## 7. One sentence
Cost B path includes a liquidation.

## 8. Next step
If KILL, do not add more indicators. If PAPER-OTHER-PRODUCT, keep it off the scalp Docker path.

## 9. Sample baskets (Cost A)

| cost_model   | entry_time                | exit_time                        | exit_reason   |   avg_entry |    exit |   fills |   safety_orders |      qty |   pnl_net |     fees |   hold_hours | taker_exit   |
|:-------------|:--------------------------|:---------------------------------|:--------------|------------:|--------:|--------:|----------------:|---------:|----------:|---------:|-------------:|:-------------|
| A_optimistic | 2024-01-03 11:00:00+00:00 | 2024-01-04 15:59:59.999000+00:00 | TP            |     43138.9 | 44001.7 |       4 |               3 | 0.801289 |   684.283 |  7.05162 |           29 | False        |
| A_optimistic | 2024-01-05 01:00:00+00:00 | 2024-01-05 20:59:59.999000+00:00 | TP            |     43554.5 | 44425.6 |       2 |               1 | 0.33027  |   284.76  |  2.93449 |           20 | False        |
| A_optimistic | 2024-01-05 21:00:00+00:00 | 2024-01-07 13:59:59.999000+00:00 | TP            |     43533.9 | 44404.5 |       2 |               1 | 0.339072 |   292.211 |  3.01126 |           41 | False        |
| A_optimistic | 2024-01-07 16:00:00+00:00 | 2024-01-08 11:59:59.999000+00:00 | TP            |     43678.2 | 44551.8 |       2 |               1 | 0.34668  |   299.758 |  3.08904 |           20 | False        |
| A_optimistic | 2024-01-09 12:00:00+00:00 | 2024-01-10 17:59:59.999000+00:00 | TP            |     45443.2 | 46352.1 |       4 |               3 | 0.876216 |   788.239 |  8.12289 |           30 | False        |
| A_optimistic | 2024-01-10 20:00:00+00:00 | 2024-01-10 22:59:59.999000+00:00 | TP            |     45602.4 | 46514.5 |       2 |               1 | 0.363532 |   328.177 |  3.3819  |            3 | False        |
| A_optimistic | 2024-01-11 03:00:00+00:00 | 2024-01-11 10:59:59.999000+00:00 | TP            |     45919.4 | 46837.8 |       2 |               1 | 0.370566 |   336.852 |  3.4713  |            8 | False        |
| A_optimistic | 2024-01-16 18:00:00+00:00 | 2024-01-28 04:59:59.999000+00:00 | TP            |     41440.9 | 42269.7 |       6 |               5 | 1.93981  |  1591.35  | 16.3991  |          275 | False        |
| A_optimistic | 2024-01-28 13:00:00+00:00 | 2024-01-29 16:59:59.999000+00:00 | TP            |     42007.6 | 42847.8 |       2 |               1 | 0.459428 |   382.052 |  3.93709 |           28 | False        |
| A_optimistic | 2024-01-30 13:00:00+00:00 | 2024-02-05 13:59:59.999000+00:00 | TP            |     42699   | 43552.9 |       3 |               2 | 0.785863 |   664.266 |  6.84533 |          145 | False        |

