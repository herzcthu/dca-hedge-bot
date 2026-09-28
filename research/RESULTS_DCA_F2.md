# Product F2_dca_mr1pct Leveraged DCA Results

## 1. This is not the scalp bot
Long-only BTCUSDT perp DCA with technical limit adds and a 1% maintenance-margin-ratio cap. Start equity $10,000. Holds until +2% from average entry. Do not wire into main.py.

## 2. Margin-ratio meaning
MR = qty * mark * 0.4% / wallet, capped at 1% after every fill. That is not a 1% stop. With ~0 UPNL it allows about 2.50× notional and roughly a 39.6% further decline to liquidation.

## 3. Dollar path to liquidation

| cost_model   |   liquidations |   baskets_before_liq |   pnl_before_liq_usdt |   equity_before_doomed_usdt |   liq_basket_pnl_usdt |   liq_fees_usdt |   ending_usdt | doomed_entry              | liq_time                         |   doomed_hold_days |   days_first_entry_to_liq |   days_last_tp_to_liq | last_tp_time                     |
|:-------------|---------------:|---------------------:|----------------------:|----------------------------:|----------------------:|----------------:|--------------:|:--------------------------|:---------------------------------|-------------------:|--------------------------:|----------------------:|:---------------------------------|
| A_optimistic |              1 |                  103 |              35907.44 |                    45907.44 |             -36119.91 |           20.47 |       9787.53 | 2025-10-06 21:00:00+00:00 | 2026-02-05 04:59:59.999000+00:00 |             121.33 |                    763.75 |                121.54 | 2025-10-06 15:59:59.999000+00:00 |
| B_decision   |              1 |                  103 |              35801.77 |                    45801.77 |             -36023.26 |           25.52 |       9778.51 | 2025-10-06 21:00:00+00:00 | 2026-02-05 04:59:59.999000+00:00 |             121.33 |                    763.75 |                121.54 | 2025-10-06 15:59:59.999000+00:00 |

PnL before liquidation is realized round-trips only (almost all TPs). The doomed basket is the open stack that hit liquidation. The sim then zeros leftover margin, so the equity chart can go to $0 even if basket-sum ending_usdt is not exactly $0.

## 4. Counts
- 1h bars: 23489
- Cost A baskets: 104
- Cost A events: 397

## 5. Train / validate / holdout (dollars and %)

| product       | cost_model   | split    |   baskets |   net_profit_usdt |   ending_equity_usdt |   net_profit_pct |   profit_factor |   win_rate |   avg_hold_hours |   avg_fills |   max_dd_pct |   expectancy_usdt |   fees_pct_start_equity |   liquidations |   tp_exits |   emergency_exits |   mtm_exits |   time_in_market_pct |    max_mr |   sharpe_ann |
|:--------------|:-------------|:---------|----------:|------------------:|---------------------:|-----------------:|----------------:|-----------:|-----------------:|------------:|-------------:|------------------:|------------------------:|---------------:|-----------:|------------------:|------------:|---------------------:|----------:|-------------:|
| F2_dca_mr1pct | A_optimistic | train    |        93 |           29409.6 |              39409.6 |          294.096 |      inf        |   100      |          122.194 |     2.76344 |      67.0937 |           316.232 |                3.03069  |              0 |         93 |                 0 |           0 |              85.911  |   1.91628 |      1.27601 |
| F2_dca_mr1pct | A_optimistic | validate |        11 |          -29622   |             -19622   |         -296.22  |        0.179897 |    90.9091 |          451.364 |     3.27273 |     100      |         -2692.91  |                0.874307 |              1 |         10 |                 0 |           0 |              85.6139 | 100       |     -2.0637  |
| F2_dca_mr1pct | A_optimistic | holdout  |         0 |               0   |              10000   |            0     |        0        |     0      |            0     |     0       |     nan      |             0     |                0        |              0 |          0 |                 0 |           0 |               0      | 100       |      0       |
| F2_dca_mr1pct | B_decision   | train    |        93 |           29329.5 |              39329.5 |          293.295 |      inf        |   100      |          122.258 |     2.76344 |      67.1941 |           315.371 |                3.02626  |              0 |         93 |                 0 |           0 |              85.9569 |   1.92501 |      1.27448 |
| F2_dca_mr1pct | B_decision   | validate |        11 |          -29551   |             -19551   |         -295.51  |        0.179669 |    90.9091 |          451.364 |     3.27273 |     100      |         -2686.46  |                0.922973 |              1 |         10 |                 0 |           0 |              85.6139 | 100       |     -2.06315 |
| F2_dca_mr1pct | B_decision   | holdout  |         0 |               0   |              10000   |            0     |        0        |     0      |            0     |     0       |     nan      |             0     |                0        |              0 |          0 |                 0 |           0 |               0      | 100       |      0       |

## 6. Decision
KILL

## 7. One sentence
Cost B path includes a liquidation.

## 8. Next step
If KILL, do not add more indicators. If PAPER-OTHER-PRODUCT, keep it off the scalp Docker path.

## 9. Sample baskets (Cost A)

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

