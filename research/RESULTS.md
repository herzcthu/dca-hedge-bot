# Adaptive BTCUSDT Scalper Results

## Data Range and Source

Source: Binance USDT-M public BTCUSDT perpetual klines.

Range: 2024-01-01 through the latest completed candle available during the 2026-09-06 run. The deterministic loader caps requests at 2026-09-07 00:00 UTC and drops incomplete last candles.

Timeframes: 5-minute primary candles and 15-minute informative candles. 15m features are aligned onto 5m rows using completed 15m candles only. No exchange credentials, Docker service, or live order path is used by this research harness.

## Fill Model and Cost Assumptions

F-OPEN: entries execute on the next 5m open after the signal.

F-LIMIT: trend entries rest at the tagged EMA21/VWAP level and cancel after 2 bars if unfilled; range entries rest at the re-entry close and cancel after 2 bars if unfilled.

Cost model A, optimistic maker-maker:
- Fee: 0.02% per side.
- Slippage: 0.5 bps per side on market/next-open fills; 0 on resting limit fills.

Cost model B, realistic mix:
- Next-open entries and stop/TP exits: 0.05% taker fee + 1.0 bp slippage.
- Limit entries touched: 0.02% maker fee + 0.25 bp slippage.
- Stops always taker.

Funding: historical funding was not fetched; the backtest applies a conservative placeholder of -0.01% per funding timestamp crossing (00:00, 08:00, 16:00 UTC).

Sharpe convention: annualized from the 5m equity curve using sqrt(365 * 24 * 12).

## Table of All Variants on Train / Validate / Holdout

Full metric output, including avg win/loss, payoff ratio, max consecutive losses, time in market, expectancy, Sharpe, worst month, fees, unsizable skips, and long/short breakdowns, is saved in `results/summary.csv`.

| Variant | Fill | Cost | Split | Net % | PF | WR % | Trades | Trades/Wk | Exp % | Max DD % | Fees % Eq | Unsizable % |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V1 trend only | F-LIMIT | A | Train | -93.353 | 0.758 | 43.533 | 4631 | 59.263 | -0.029 | 93.369 | 120.189 | 3.500 |
| V1 trend only | F-LIMIT | A | Validate | -5.420 | 0.618 | 42.091 | 1865 | 53.724 | -0.043 | 82.065 | 5.419 | 9.253 |
| V1 trend only | F-LIMIT | A | Holdout | -0.905 | 0.643 | 42.968 | 1543 | 56.847 | -0.038 | 73.989 | 0.901 | 10.620 |
| V1 trend only | F-OPEN | A | Train | -99.820 | 0.599 | 41.118 | 6457 | 82.631 | -0.052 | 99.820 | 76.926 | 14.170 |
| V1 trend only | F-OPEN | A | Validate | -0.172 | 0.505 | 40.851 | 2678 | 77.144 | -0.055 | 95.851 | 0.142 | 21.534 |
| V1 trend only | F-OPEN | A | Holdout | -0.007 | 0.599 | 42.013 | 2235 | 82.342 | -0.056 | 92.804 | 0.006 | 23.145 |
| V2 range only | F-LIMIT | A | Train | -16.223 | 0.588 | 41.837 | 196 | 2.545 | -0.068 | 17.213 | 12.329 | 5.263 |
| V2 range only | F-LIMIT | A | Validate | -7.055 | 0.545 | 41.379 | 87 | 2.548 | -0.051 | 8.860 | 5.672 | 4.714 |
| V2 range only | F-LIMIT | A | Holdout | -8.923 | 0.387 | 36.250 | 80 | 2.963 | -0.073 | 12.998 | 4.947 | 4.724 |
| V2 range only | F-OPEN | A | Train | -19.258 | 0.528 | 41.414 | 198 | 2.571 | -0.079 | 20.173 | 13.677 | 5.263 |
| V2 range only | F-OPEN | A | Validate | -8.102 | 0.483 | 40.230 | 87 | 2.548 | -0.061 | 10.439 | 6.098 | 4.682 |
| V2 range only | F-OPEN | A | Holdout | -9.524 | 0.339 | 36.250 | 80 | 2.963 | -0.083 | 14.425 | 5.221 | 4.700 |
| V3 combined | F-LIMIT | A | Train | -94.659 | 0.747 | 43.232 | 4758 | 60.888 | -0.032 | 94.672 | 115.450 | 3.543 |
| V3 combined | F-LIMIT | A | Validate | -4.453 | 0.609 | 41.792 | 1931 | 55.626 | -0.045 | 83.842 | 4.321 | 9.012 |
| V3 combined | F-LIMIT | A | Holdout | -0.674 | 0.636 | 42.812 | 1600 | 58.947 | -0.039 | 76.072 | 0.657 | 10.374 |
| V3 combined | F-OPEN | A | Train | -99.841 | 0.588 | 40.984 | 6527 | 83.527 | -0.053 | 99.841 | 74.301 | 13.926 |
| V3 combined | F-OPEN | A | Validate | -0.152 | 0.501 | 40.969 | 2724 | 78.469 | -0.055 | 95.993 | 0.126 | 21.409 |
| V3 combined | F-OPEN | A | Holdout | -0.006 | 0.596 | 41.933 | 2225 | 81.974 | -0.055 | 92.891 | 0.005 | 22.856 |
| V4 combined + BE | F-LIMIT | A | Train | -93.415 | 0.717 | 44.213 | 5037 | 64.459 | -0.027 | 93.431 | 124.599 | 3.433 |
| V4 combined + BE | F-LIMIT | A | Validate | -5.238 | 0.604 | 43.701 | 2032 | 58.535 | -0.037 | 79.988 | 5.976 | 8.964 |
| V4 combined + BE | F-LIMIT | A | Holdout | -0.991 | 0.623 | 42.610 | 1678 | 61.821 | -0.034 | 73.769 | 1.074 | 10.118 |
| V4 combined + BE | F-OPEN | A | Train | -99.834 | 0.559 | 41.720 | 6860 | 87.788 | -0.050 | 99.833 | 78.712 | 13.362 |
| V4 combined + BE | F-OPEN | A | Validate | -0.159 | 0.494 | 42.140 | 2869 | 82.646 | -0.051 | 95.717 | 0.141 | 20.644 |
| V4 combined + BE | F-OPEN | A | Holdout | -0.007 | 0.546 | 41.081 | 2332 | 85.916 | -0.055 | 93.683 | 0.006 | 21.950 |
| V3 combined | F-LIMIT | B | Train | -99.750 | 0.530 | 42.259 | 4489 | 57.446 | -0.072 | 99.750 | 97.853 | 3.633 |
| V3 combined | F-LIMIT | B | Validate | -0.240 | 0.361 | 41.053 | 1805 | 51.996 | -0.084 | 96.002 | 0.220 | 9.439 |
| V3 combined | F-LIMIT | B | Holdout | -0.009 | 0.413 | 40.884 | 1426 | 52.537 | -0.081 | 92.299 | 0.008 | 10.967 |
| V3 combined | F-OPEN | B | Train | -99.998 | 0.299 | 37.911 | 4624 | 59.282 | -0.127 | 99.998 | 79.548 | 15.156 |
| V3 combined | F-OPEN | B | Validate | -0.002 | 0.149 | 34.894 | 1837 | 52.918 | -0.129 | 99.360 | 0.002 | 25.168 |
| V3 combined | F-OPEN | B | Holdout | -0.000013 | 0.281 | 35.614 | 1491 | 54.932 | -0.133 | 98.437 | 0.000011 | 27.571 |

## Which Engine Made the Money

No engine made money in V3. Trend produced most trades and most losses; range also lost.

| Cost | Fill | Engine | Trades | Net PnL USDT | Win Rate % |
|---|---|---|---:|---:|---:|
| A | F-LIMIT | range | 345 | -634.28 | 40.87 |
| A | F-LIMIT | trend | 7944 | -9344.28 | 42.90 |
| A | F-OPEN | range | 299 | -311.51 | 39.46 |
| A | F-OPEN | trend | 11177 | -9688.45 | 41.21 |
| B | F-LIMIT | range | 325 | -467.08 | 37.23 |
| B | F-LIMIT | trend | 7395 | -9532.84 | 41.92 |
| B | F-OPEN | range | 213 | -318.38 | 29.58 |
| B | F-OPEN | trend | 7739 | -9681.62 | 36.98 |

## Failure Modes (trend days vs chop days)

Trend engine: the EMA/VWAP pullback idea fires frequently, but the average payoff is too small after fees and slippage. Even with F-LIMIT and optimistic Cost A, the trend engine loses across train, validation, and holdout. Cost B crushes it further.

Range engine: Bollinger/RSI fades trade much less often, which limits fee churn, but they still fail in every split. Range trades lose because the first re-entry into the bands is not enough confirmation; volatility expansion often continues into the wick-based stop, and winners do not compensate.

Combined adaptive gate: V3 does not rescue either engine. The ADX gate reduces regime mismatch but not enough to create positive expectancy. Rolling 90-day V3 Cost B profit factors are all below 1.0 in the saved `results/rolling_90d_pf_V3.csv` sample, ranging roughly from 0.12 to 0.39 in the printed rows.

## PASS/FAIL vs Kill Criteria

Cost B holdout kill criteria:
- V3 F-LIMIT: FAIL. PF 0.413 < 1.15, net profit is negative, expectancy is negative, max DD is 92.299%.
- V3 F-OPEN: FAIL. PF 0.281 < 1.15, net profit is negative, expectancy is negative, max DD is 98.437%.

Cost A holdout baselines also fail for every variant. The strongest-looking Cost A holdout PF is still only 0.643 for V1 F-LIMIT, far below the 1.15 threshold.

## Recommendation: ship V? / paper only / kill

Kill. Do not turn any baseline variant into a live bot. V3 F-LIMIT is the least bad combined variant on Cost B, but it still has negative expectancy, PF below 0.5, and catastrophic drawdown in the simulated equity path. This is not paper-only; it is rejected.

## Exact next experiment if mixed results

There are no mixed results here. The only reasonable next experiment, if continuing this line at all, is an execution-only study: true maker-only entries and exits with abort-on-no-fill, queue realism, and no market fallback. Do not add indicators until execution quality itself is measured.
