# Finbot

One Binance USD-M futures bot, plus a research harness for DCA ideas. The live process is a single symbol. Research never places orders.

There is no approved production strategy. `BASE_URL` stays on testnet unless you deliberately switch it and set `DCA_CONFIRM_PRODUCTION=true`.

## Live bot

`main.py` and `dca_rules.py` trade **one USD-M symbol**. The default is `DOGEUSDT` in hedge mode: a long basket and a short basket share the account. The Docker service name is still `btc-eth-hedge`.

Signals use completed candles. Klines are read from public `https://fapi.binance.com` even when orders go to testnet. The bot polls every 15 seconds and acts once per completed bar. Live posts a resting limit and waits. Research fills that limit on the next bar.

### Book

Defaults from `.env.example` and `dca_rules.py`. The hedge loop is the live path.

| Setting | Value | Name |
|---|---|---|
| Symbol | DOGEUSDT | `DCA_SYMBOL` |
| Bar | 1 minute, completed bar only | `DCA_INTERVAL` |
| Mode | Hedge, one long and one short | `DCA_HEDGE` |
| Sizing wallet | `min(wallet, $10,000)` | `DCA_CLIP_USD` |
| Margin cap | 10% of the sizing wallet | `DCA_MR_CAP` |
| Maintenance margin | 0.4% of notional | `MMR` |
| Notional cap | `0.10 / 0.004 × sizing wallet` = 25× | `notional_cap` |
| Headroom | 90% of that cap, so a full ladder approaches 22.5× | `HEADROOM` |
| Minimum order | $100 notional | `MIN_NOTIONAL` |
| Leverage / margin | 25×, cross | `DCA_LEVERAGE`, `DCA_MARGIN_TYPE` |
| Poll | 15 seconds | `DCA_POLL_SEC` |

The clip does not grow when the wallet grows past $10,000, and it does not step down on a stop. Below $10,000 the whole wallet is the sizing base.

### Indicators

On a 1-minute chart the periods are wall-clock. Every feature uses completed bars only (`shift(1)` on the swings and the range).

| Feature | Window | 1-minute bars |
|---|---|---|
| EMA 21 | 21 hours | 1,260 |
| EMA 55 | 55 hours | 3,300 |
| Support | lowest low of the prior 12 hours | 720 |
| Resistance | highest high of the prior 12 hours | 720 |
| 7-day range | high and low of the prior 7 days | 10,080 |

Warmup is 7 days plus 2 bars. The 7-day range is the safety-order ladder and the quartile filter.

### Long entry

A new long is skipped when any of these is true:

| Filter | Rule |
|---|---|
| Peak-skip | Marked wallet is 15% or more under its 180-day high |
| Near resistance | Close is within 0.3% under the 12-hour resistance |
| Below trend | Close is at or under the 55-hour EMA |
| Top of range | Close is in the top quarter of the prior 7-day range |
| Range too tight | 7-day low is less than 6% under the close |

The limit is the higher of the 21-hour EMA and the 12-hour support, and it must be at least 0.3% under the close. If neither level qualifies, no order is posted.

### Short entry

A new short is the mirror:

| Filter | Rule |
|---|---|
| Peak-skip | Same 15% / 180-day rule on the shared wallet |
| Near support | Close is within 0.3% above the 12-hour support |
| Above trend | Close is at or above the 55-hour EMA |
| Bottom of range | Close is in the bottom quarter of the prior 7-day range |
| Range too tight | 7-day low is less than 6% under the close |

The limit is the lower of the 21-hour EMA and the 12-hour resistance, and it must be at least 0.3% above the close.

A skip on either side cancels that side's resting entry. If both sides skip, the symbol is left with no open orders. An unchanged rounded price is kept; a one-tick change of the EMA replaces the order. Quantity drift alone does not. An unfilled entry is cancelled after 1 hour (`DCA_ENTRY_TTL_SEC`). Safety orders are not on that timer.

### First order and safety orders

The first order is the smallest geometric rung. Weights are `1.25^i` for `i = 0..10`, normalized. On the live 10-rung book that first order is about 0.53× the sizing wallet in notional.

After the first fill, up to 10 safety orders walk toward the 7-day extreme that was frozen at the fill. Longs walk down toward that low. Shorts walk up toward that high. Each rung splits the remaining gap into equal slots and must be at least 0.6% from the last fill. Size is `remaining × 0.90 / slots left`, where remaining is the notional cap minus the position already open.

The next safety order waits until price reclaims the 21-hour EMA (back above it for a long, back under it for a short). A long adds nothing if the 7-day low expands more than 2% past the frozen low, or if the close breaks the 12-hour support. A short adds nothing if the 7-day high expands more than 2%, or if the close breaks the 12-hour resistance.

### Exits

| Exit | Rule |
|---|---|
| Take-profit | Resting limit 8% above the long average, or 8% below the short average |
| Stop | 95% of the path from that side's average to the account liquidation price. Only the threatened side is closed |
| Liquidation | The bar trades through the account liquidation price. Both sides are closed |
| Stale | Still 40% adverse after 180 days. The short uses an inverted mark, `2 × average − price`. A stale exit may re-enter without waiting for the EMA filter |
| Emergency | Research hedge only: both sides flatten if margin ratio reaches 80%. The live hedge loop does not use this |

Account liquidation uses both sides and the shared cash:

`K = cash − long_qty × long_avg + short_qty × short_avg`

`price = K / ((long_qty + short_qty) × 0.004 − (long_qty − short_qty))`

The dollar basket stop (`DCA_HARD_SL_BASKET`) belongs to the long-only path. The live hedge does not read it.

A take-profit and the next safety order can both be resting. One side's stop does not close the other side. An account liquidation does.

Orders are off until `DCA_ALLOW_ORDERS=true`. Production also needs `DCA_CONFIRM_PRODUCTION=true`. Do not log API keys, private keys, signatures, or signed URLs.

```bash
docker compose up -d
docker compose logs -f
```

`main.py` is copied into the image. After a live-code change, rebuild and recreate. Leave the service stopped while editing order logic.

```bash
docker compose build
docker compose up -d --force-recreate
```

State is `data/dca_bot_state.json`. Events are `data/events.csv`.

## Research

Backtests live under `research/experiments/dca/` and do not import into `main.py`. The backtest container's working directory is `research/`. They use public klines only. Cost B is the decision model: taker 0.05% plus 0.01% slip, maker 0.02% plus 0.0025% slip. Cost A is the optimistic baseline and is not a pass. Funding in research is a placeholder of 0.01% each time a bar crosses 00:00, 08:00, or 16:00 UTC. The long pays it and the short receives it. The live exchange charges its own funding; the bot does not add this placeholder.

The research first order uses six geometric weights (`MAX_SAFETY = 5` in `backtest_dca.py`), so it is about 2× the sizing wallet. The live bot uses eleven weights and the first order is about 0.53×. Safety-order count is still 10 in both. Splits, in UTC:

| Window | Dates |
|---|---|
| Train | 2024-01-01 → 2025-07-01 |
| Validate | 2025-07-01 → 2026-03-01 |
| Holdout | 2026-03-01 → last bar |

A backtest container does not stop the live service:

```bash
docker compose --profile backtest run --rm --no-deps dca-backtest
```

That default command is the long-only isolated runner (`research/experiments/dca/run_isolated.py`). Other entry points:

```bash
# Hedge book, one shared wallet, symbols in research/experiments/dca/run_hedge.py
docker compose --profile backtest run --rm --no-deps dca-backtest \
  python -u -m experiments.dca.run_hedge

# Per-symbol grid: peak memory 30/90/180d × TP 5/8% × SL 90/95%
docker compose --profile backtest run --rm --no-deps dca-backtest \
  python -u -m experiments.dca.run_hedge_tune

# One-symbol summary report from research/experiments/dca/best_params.py
docker compose --profile backtest run --rm --no-deps dca-backtest \
  python -u -m experiments.dca.run_hedge_report
```

1-minute caches are `research/data/dca_um/{SYMBOL}_1m.jsonl`. A cache younger than one day is reused.

The best measured spec for each symbol is `research/experiments/dca/BEST_PARAMS.md` (and `research/experiments/dca/best_params.py`). Do not copy one coin's parameters onto another.

### Report table

Research reports use this summary. Wallet is cash plus the open basket marked at the last price. It is not a taker flatten.

| Column | Meaning |
|---|---|
| Wallet | Idle cash + open unrealized P&L |
| TP | Closed at the take-profit |
| SL | Price stop only |
| Liq | Account liquidation |
| Possible liq | Price stop fired, and holding would have liquidated before the take-profit |
| SL cut TP | Price stop fired, and holding would have reached the take-profit |

A stale flatten (40% adverse for 180 days) is not an SL, so it is neither Possible liq nor SL cut TP.

### Current hedge results

USD-M 1-minute, Cost B, $10,000 start, $10,000 clip. Same rules on every coin except peak memory, take-profit, and stop. Source: `research/results_dca_run_1m_so_reclaim/hedge_tune/REPORT.md`.

| Symbol | Memory | TP | SL | Wallet |
|---|---:|---:|---:|---:|
| SOLUSDT | 90d | 5% | 90% | $223,783 |
| DOGEUSDT | 180d | 8% | 90% | $208,700 |
| BTCUSDT | — | — | — | under $10,000 on every point |
| ETHUSDT | — | — | — | under $10,000 on every point |

On SOL and DOGE the 95% stop matched the 90% stop because that book never stopped. SOL's full table is `research/results_dca_run_1m_so_reclaim/hedge_sol/REPORT.md`. Holdout for DOGE was negative. These wallets are research results, not a live pass.

Cutting start and clip together from $10,000 to $1,000 scales the SOL book to one tenth ($22,378). Starting at $1,000 while leaving the clip at $10,000 does not: each basket then uses the whole wallet until it reaches $10,000, and that run ended at $24.

## Layout

| Path | Role |
|---|---|
| `main.py`, `dca_rules.py` | Live bot |
| `binance_client.py`, `trade_log.py` | Exchange client and event log |
| `research/` | Backtests, old scripts, kline caches, and result reports |
| `research/experiments/dca/` | DCA research |
| `research/experiments/dca/BEST_PARAMS.md` | Best saved parameters per symbol |
| `research/data/dca_um/` | USD-M kline cache |
| `research/results_dca_run_1m_so_reclaim/` | Latest 1-minute hedge and long-only reports |
| `docker-compose.yml` | Live service `btc-eth-hedge`, research profile `dca-backtest` |

## Earlier research

These are closed. A new test needs a new frozen spec and a positive Cost B result. Do not retune them into `main.py`.

| Line | What it was | Result |
|---|---|---|
| Adaptive 5m (`research/backtest.py`) | ADX-gated VWAP/EMA and Bollinger fade | Killed. `research/RESULTS.md` |
| HTF B1/B2 | 15m and 1h trend pullback | Killed. `research/RESULTS_HTF.md` |
| Grid C | Inventory grid | Killed. `research/RESULTS_GRID.md` |
| D1 | Daily Donchian, spot | Inconclusive, not a scalp. `research/RESULTS_D1.md` |
| E1 | 15m rejection fade | Killed. `research/RESULTS_E1.md` |
| F1–F8, G1 | Leveraged long DCA, 1h | Frozen. `research/experiments/dca/README.md` |
| Gap fade | `research/main-gap-fading.py` | Retired |

F-suite commands and the isolated long-only runner are documented in `research/experiments/dca/README.md`.
