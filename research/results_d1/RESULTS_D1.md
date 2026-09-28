# Experiment D1 Donchian Results

## 1. Data source, spot vs perp, cost assumptions
Binance spot BTCUSDT daily UTC klines from earliest available cache/download through the latest completed candle. Spot is used, so no funding is applied. Cost A is 0.05% fee each side with no slippage. Cost B is 0.05% fee plus 5 bps slippage each side on next-open fills.

## 2. Why this is not the killed 5m/HTF/grid work
This is a separate daily Donchian 20/10 long-only breakout system. It does not retune the killed 5m adaptive scalp, B1/B2 pullbacks, or Experiment C grid, and it adds no extra indicators.

## 3. Bar counts + trade counts (circuit breaker)
- Daily bars: 3307
- Full-sample trades: 43
- 2024+ trades: 15
- Channel sanity failures: 0

## 4. Table D1 Cost A/B x train/validate/holdout + BH

| split    | cost_model         |   n_trades |   net_profit_pct |   profit_factor |   win_rate |   avg_win_pct |   avg_loss_pct |   payoff_ratio |   max_equity_dd_pct |   time_in_market_pct |   avg_hold_days |   expectancy_pct |   worst_month_pct |   fees_pct_start_equity |   channel_exits |   rail20_exits |   mtm_exits |   bh_net_profit_pct |   bh_max_dd_pct |   bh_time_in_market_pct |
|:---------|:-------------------|-----------:|-----------------:|----------------:|-----------:|--------------:|---------------:|---------------:|--------------------:|---------------------:|----------------:|-----------------:|------------------:|------------------------:|----------------:|---------------:|------------:|--------------------:|----------------:|------------------------:|
| train    | A_optimistic_daily |          7 |          75.5046 |       4.7351    |    42.8571 |      32.0679  |       -4.41909 |       7.25667  |             30.0011 |              50.6399 |         37      |         11.2182  |         -12.454   |                22.1877  |               7 |              0 |           0 |            153.146  |         28.0953 |                     100 |
| validate | A_optimistic_daily |          5 |         -26.0116 |       0.0631597 |    20      |       1.75365 |       -7.54518 |       0.232419 |             31.3561 |              34.9794 |         17      |         -5.68542 |         -10.5458  |                19.497   |               5 |              0 |           0 |            -37.5562 |         49.5343 |                     100 |
| holdout  | A_optimistic_daily |          3 |          19.9988 |     nan         |    66.6667 |      13.7598  |       -6.70955 |       2.05078  |             10.2222 |              54.4974 |         34.3333 |          6.93669 |          -6.70955 |                 9.69471 |               2 |              0 |           1 |             19.0803 |         28.6891 |                     100 |
| train    | B_decision_daily   |          7 |          74.1932 |       4.61177   |    42.8571 |      31.9358  |       -4.51462 |       7.07387  |             30.3502 |              50.6399 |         37      |         11.107   |         -12.5415  |                21.4955  |               7 |              0 |           0 |            152.893  |         28.0953 |                     100 |
| validate | B_decision_daily   |          5 |         -26.3806 |       0.0589294 |    20      |       1.65194 |       -7.63759 |       0.216291 |             31.6643 |              34.9794 |         17      |         -5.77968 |         -10.6799  |                18.7824  |               5 |              0 |           0 |            -37.6187 |         49.5343 |                     100 |
| holdout  | B_decision_daily   |          3 |          19.6394 |     nan         |    66.6667 |      13.6461  |       -6.80279 |       2.00596  |             10.3119 |              54.4974 |         34.3333 |          6.82981 |          -6.80279 |                 9.30008 |               2 |              0 |           1 |             18.9612 |         28.6891 |                     100 |

## 5. Appendix table 2017+

| split   | cost_model         |   n_trades |   net_profit_pct |   profit_factor |   win_rate |   avg_win_pct |   avg_loss_pct |   payoff_ratio |   max_equity_dd_pct |   time_in_market_pct |   avg_hold_days |   expectancy_pct |   worst_month_pct |   fees_pct_start_equity |   channel_exits |   rail20_exits |   mtm_exits |   bh_net_profit_pct |   bh_max_dd_pct |   bh_time_in_market_pct |
|:--------|:-------------------|-----------:|-----------------:|----------------:|-----------:|--------------:|---------------:|---------------:|--------------------:|---------------------:|----------------:|-----------------:|------------------:|------------------------:|----------------:|---------------:|------------:|--------------------:|----------------:|------------------------:|
| full    | A_optimistic_daily |         43 |          3761.93 |         1.91716 |    48.8372 |       40.3061 |       -8.14572 |        4.94813 |             53.6492 |              45.6994 |         34.7209 |          15.5168 |          -18.7743 |                 87.0484 |              40 |              2 |           1 |             1726.45 |         83.1871 |                     100 |
| full    | B_decision_daily   |         43 |          3599.39 |         1.89036 |    48.8372 |       40.1658 |       -8.23753 |        4.87595 |             53.9495 |              45.6994 |         34.7209 |          15.4013 |          -18.8554 |                 84.5963 |              40 |              2 |           1 |             1724.63 |         83.1871 |                     100 |

## 6. Failure modes
Whipsaw months and monthly returns are saved in results_d1/monthly_returns.csv. This daily breakout can sit out long stretches and can miss chop; it is not a scalp. Trade samples below show next-day fills after completed signal bars.

## 7. Decision: PASS / PAPER / INCONCLUSIVE / KILL
INCONCLUSIVE

## 8. One sentence recommendation
Holdout has fewer than 8 trades, so this cannot pass; train/validate evidence is insufficient for paper.

## 9. Next step
If KILL or INCONCLUSIVE-thin, do not add indicators. D2 (4h + compression gate) is allowed only if D1 train+validate expectancy is positive; otherwise stop the breakout program.

## 10 sample trades

| split     | cost_model         | entry_time                | signal_date                      | exit_time                 |    entry |     exit | exit_reason   |   pnl_net |   pnl_net_pct |    fees |   hold_days |   high_20_at_signal |   low_10_at_exit |
|:----------|:-------------------|:--------------------------|:---------------------------------|:--------------------------|---------:|---------:|:--------------|----------:|--------------:|--------:|------------:|--------------------:|-----------------:|
| full_only | A_optimistic_daily | 2017-10-09 00:00:00+00:00 | 2017-10-08 23:59:59.999000+00:00 | 2017-11-12 00:00:00+00:00 |  4640    |  6245.05 | channel       |  3445.7   |     0.34457   | 11.7262 |          34 |             4561.63 |          6255.01 |
| full_only | A_optimistic_daily | 2017-11-17 00:00:00+00:00 | 2017-11-16 23:59:59.999000+00:00 | 2017-12-23 00:00:00+00:00 |  7876.98 | 13326.6  | channel       |  9279.57  |     0.690151  | 18.0912 |          36 |             7770.02 |         14022    |
| full_only | A_optimistic_daily | 2018-04-21 00:00:00+00:00 | 2018-04-20 23:59:59.999000+00:00 | 2018-05-12 00:00:00+00:00 |  8852.12 |  8405.94 | channel       | -1167.01  |    -0.0513531 | 22.1472 |          21 |             8429.54 |          8800.49 |
| full_only | A_optimistic_daily | 2018-07-18 00:00:00+00:00 | 2018-07-17 23:59:59.999000+00:00 | 2018-08-04 00:00:00+00:00 |  7317.44 |  7412.27 | channel       |   257.551 |     0.0119467 | 21.6925 |          17 |             6818.16 |          7430    |
| full_only | A_optimistic_daily | 2018-08-29 00:00:00+00:00 | 2018-08-28 23:59:59.999000+00:00 | 2018-09-07 00:00:00+00:00 |  7077    |  6516.84 | channel       | -1746.85  |    -0.0800728 | 20.9474 |           9 |             6940.51 |          6646.5  |
| full_only | A_optimistic_daily | 2019-02-19 00:00:00+00:00 | 2019-02-18 23:59:59.999000+00:00 | 2019-06-05 00:00:00+00:00 |  3897.35 |  7687.04 | channel       | 19475     |     0.970404  | 29.8163 |         106 |             3733.58 |          7833.42 |
| full_only | A_optimistic_daily | 2019-06-21 00:00:00+00:00 | 2019-06-20 23:59:59.999000+00:00 | 2019-07-15 00:00:00+00:00 |  9518.06 | 10174.2  | channel       |  2683.67  |     0.0678655 | 40.8964 |          24 |             9444    |         10796.4  |
| full_only | A_optimistic_daily | 2019-08-06 00:00:00+00:00 | 2019-08-05 23:59:59.999000+00:00 | 2019-08-15 00:00:00+00:00 | 11830    | 10055.2  | channel       | -6371.24  |    -0.150878  | 39.051  |           9 |            11069    |         10552    |
| full_only | A_optimistic_daily | 2019-10-27 00:00:00+00:00 | 2019-10-26 23:59:59.999000+00:00 | 2019-11-09 00:00:00+00:00 |  9230    |  8773.74 | channel       | -1806.54  |    -0.0503826 | 34.9616 |          13 |             8799    |          8913    |
| full_only | A_optimistic_daily | 2020-01-07 00:00:00+00:00 | 2020-01-06 23:59:59.999000+00:00 | 2020-02-26 00:00:00+00:00 |  7758.9  |  9316.48 | channel       |  6794.55  |     0.199547  | 37.4573 |          50 |             7695.38 |          9350    |

