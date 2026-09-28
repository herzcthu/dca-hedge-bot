# Product G1_dca_coinm_10k_sl80 Coin-M DCA Results

## 1. This is not the scalp bot
Long-only Binance BTCUSD_PERP (COIN-M inverse) with F6 rules: 1% MR cap, SL80 vs a frozen $10,000 USD clip, TP +2% from average entry. Start wallet is $10,000 of BTC (0.22115380 BTC at the first tradable open). Idle BTC is still marked to USD when price moves. Do not wire into main.py.

## 2. Inverse margin
Contracts are $100 notional. MR = (contracts * 100 * 0.4%) / (wallet_btc * mark). That matches USD-M MR when wallet is expressed in USD. Liquidation uses the inverse formula.

## 3. Remaining vs buy-and-hold BTC

| cost_model   | as_of                            |   btc_close | liquidated   | in_position   |   remaining_mark_usdt |    qty |   avg_entry |   unrealized_usdt |   mr_pct |   start_equity_usdt |   start_btc |   remaining_btc |   buy_hold_usdt |   if_flatten_today_usdt |
|:-------------|:---------------------------------|------------:|:-------------|:--------------|----------------------:|-------:|------------:|------------------:|---------:|--------------------:|------------:|----------------:|----------------:|------------------------:|
| A_optimistic | 2026-09-10 02:59:59.999000+00:00 |    78292.80 | False        | True          |              25803.52 | 161.00 |    78987.66 |           -141.63 |     0.25 |            10000.00 |        0.22 |            0.33 |        17314.75 |                25794.99 |
| B_decision   | 2026-09-10 02:59:59.999000+00:00 |    78292.80 | False        | True          |              25761.16 | 161.00 |    78989.93 |           -142.09 |     0.25 |            10000.00 |        0.22 |            0.33 |        17314.75 |                25748.92 |

buy_hold_usdt is start BTC marked at the last close with no futures. Split tables still attribute only futures round-trip USD P&L onto a fresh $10,000; they do not include idle-BTC USD drift.

## 4. First risk exit

| cost_model   | risk_exit   |   liquidations |   baskets_before_liq |   pnl_before_liq_usdt |   equity_before_doomed_usdt |   liq_basket_pnl_usdt |   liq_fees_usdt |   ending_usdt | doomed_entry              | liq_time                         |   doomed_hold_days |   days_first_entry_to_liq |   days_last_tp_to_liq | last_tp_time                     |
|:-------------|:------------|---------------:|---------------------:|----------------------:|----------------------------:|----------------------:|----------------:|--------------:|:--------------------------|:---------------------------------|-------------------:|--------------------------:|----------------------:|:---------------------------------|
| A_optimistic | SL50        |              0 |                  107 |              18631.80 |                    28631.80 |              -8009.55 |            8.84 |      20622.26 | 2025-10-06 21:00:00+00:00 | 2026-01-31 18:59:59.999000+00:00 |             116.92 |                    759.33 |                117.12 | 2025-10-06 15:59:59.999000+00:00 |
| B_decision   | SL50        |              0 |                  107 |              18607.80 |                    28607.80 |              -8012.46 |           11.05 |      20595.34 | 2025-10-06 21:00:00+00:00 | 2026-01-31 18:59:59.999000+00:00 |             116.92 |                    759.33 |                117.12 | 2025-10-06 15:59:59.999000+00:00 |

## 5. Counts
- 1h bars: 23541
- Cost A baskets: 124
- Cost A events: 503
- start_btc: 0.22115380

## 6. Train / validate / holdout (futures USD P&L only)

| product               | cost_model   | split    |   baskets |   net_profit_usdt |   ending_equity_usdt |   net_profit_pct |   profit_factor |   win_rate |   avg_hold_hours |   avg_fills |   max_dd_pct |   expectancy_usdt |   fees_pct_start_equity |   liquidations |   tp_exits |   sl50_exits |   emergency_exits |   mtm_exits |   time_in_market_pct |   max_mr |   sharpe_ann |
|:----------------------|:-------------|:---------|----------:|------------------:|---------------------:|-----------------:|----------------:|-----------:|-----------------:|------------:|-------------:|------------------:|------------------------:|---------------:|-----------:|-------------:|------------------:|------------:|---------------------:|---------:|-------------:|
| G1_dca_coinm_10k_sl80 | A_optimistic | train    |        98 |          16917.1  |             26917.1  |         169.171  |      inf        |   100      |          114.48  |     2.97959 |      51.7659 |           172.624 |                  1.7088 |              0 |         98 |            0 |                 0 |           0 |              84.7637 | 1.12666  |      1.55176 |
| G1_dca_coinm_10k_sl80 | A_optimistic | validate |        11 |          -5857.28 |              4142.72 |         -58.5728 |        0.268712 |    90.9091 |          600.545 |     3.72727 |      70.2887 |          -532.48  |                  0.3058 |              0 |         10 |            1 |                 0 |           0 |              94.1872 | 0.551852 |     -1.4607  |
| G1_dca_coinm_10k_sl80 | A_optimistic | holdout  |        15 |           2104.37 |             12104.4  |          21.0437 |       15.1355   |    93.3333 |          217.067 |     3.06667 |      50.5663 |           140.291 |                  0.292  |              0 |         14 |            0 |                 0 |           1 |              94.5643 | 0.66578  |      1.18032 |
| G1_dca_coinm_10k_sl80 | B_decision   | train    |        98 |          16895.3  |             26895.3  |         168.953  |      inf        |   100      |          114.48  |     2.97959 |      51.785  |           172.401 |                  1.7088 |              0 |         98 |            0 |                 0 |           0 |              84.7637 | 1.12703  |      1.55083 |
| G1_dca_coinm_10k_sl80 | B_decision   | validate |        11 |          -5862.97 |              4137.03 |         -58.6297 |        0.268268 |    90.9091 |          600.545 |     3.72727 |      70.3163 |          -532.997 |                  0.3279 |              0 |         10 |            1 |                 0 |           0 |              94.1872 | 0.552897 |     -1.46102 |
| G1_dca_coinm_10k_sl80 | B_decision   | holdout  |        15 |           2098.6  |             12098.6  |          20.986  |       14.8304   |    93.3333 |          217.067 |     3.06667 |      50.6027 |           139.907 |                  0.3081 |              0 |         14 |            0 |                 0 |           1 |              94.5643 | 0.667308 |      1.18023 |

## 7. Decision
KILL

## 8. One sentence
Cost B train or validate lost money.

## 9. Sample baskets (Cost A)

| cost_model   | entry_time                | exit_time                        | exit_reason   |   avg_entry |    exit |   fills |   safety_orders |   qty |   pnl_net |     pnl_btc |   fees |    fees_btc |   hold_hours | taker_exit   |
|:-------------|:--------------------------|:---------------------------------|:--------------|------------:|--------:|--------:|----------------:|------:|----------:|------------:|-------:|------------:|-------------:|:-------------|
| A_optimistic | 2024-01-03 11:00:00+00:00 | 2024-01-04 15:59:59.999000+00:00 | TP            |     43148.5 | 44011.4 |       4 |               3 |   113 |    223.74 | 0.00508368  |   2.26 | 5.13503e-05 |           29 | False        |
| A_optimistic | 2024-01-05 01:00:00+00:00 | 2024-01-07 13:59:59.999000+00:00 | TP            |     43577.9 | 44449.5 |       2 |               1 |    43 |     85.14 | 0.00191543  |   0.86 | 1.93478e-05 |           61 | False        |
| A_optimistic | 2024-01-07 22:00:00+00:00 | 2024-01-08 11:59:59.999000+00:00 | TP            |     43557.2 | 44428.3 |       3 |               2 |    74 |    146.52 | 0.0032979   |   1.48 | 3.33121e-05 |           14 | False        |
| A_optimistic | 2024-01-09 12:00:00+00:00 | 2024-01-10 17:59:59.999000+00:00 | TP            |     45405.5 | 46313.6 |       4 |               3 |   113 |    223.74 | 0.00483097  |   2.26 | 4.87977e-05 |           30 | False        |
| A_optimistic | 2024-01-10 20:00:00+00:00 | 2024-01-10 22:59:59.999000+00:00 | TP            |     45607   | 46519.2 |       2 |               1 |    43 |     85.14 | 0.00183021  |   0.86 | 1.8487e-05  |            3 | False        |
| A_optimistic | 2024-01-11 03:00:00+00:00 | 2024-01-11 10:59:59.999000+00:00 | TP            |     45932   | 46850.7 |       2 |               1 |    43 |     85.14 | 0.00181726  |   0.86 | 1.83562e-05 |            8 | False        |
| A_optimistic | 2024-01-16 18:00:00+00:00 | 2024-01-26 18:59:59.999000+00:00 | TP            |     41337.7 | 42164.5 |       6 |               5 |   221 |    437.58 | 0.0103779   |   4.42 | 0.000104828 |          241 | False        |
| A_optimistic | 2024-01-27 08:00:00+00:00 | 2024-01-28 04:59:59.999000+00:00 | TP            |     41541.4 | 42372.2 |       1 |               0 |    19 |     37.62 | 0.000887845 |   0.38 | 8.96814e-06 |           21 | False        |
| A_optimistic | 2024-01-28 14:00:00+00:00 | 2024-01-29 16:59:59.999000+00:00 | TP            |     42037.7 | 42878.5 |       2 |               1 |    43 |     85.14 | 0.00198561  |   0.86 | 2.00567e-05 |           27 | False        |
| A_optimistic | 2024-01-30 13:00:00+00:00 | 2024-02-05 13:59:59.999000+00:00 | TP            |     42694.7 | 43548.5 |       3 |               2 |    74 |    146.52 | 0.00336452  |   1.48 | 3.39851e-05 |          145 | False        |

