# Product F1: Leveraged DCA (not the scalp bot)

Isolated research. **Do not** put this in `main.py`. Holds can last many hours
or days. This is not a retune of Grid C.

## Frozen spec

- BTCUSDT USD-M perp, **1h** bars. Long-only baskets.
- **No time-interval buys.** Resting **limit** only, priced from completed-bar
  EMA21, 12h swing support, and a geometric floor so each add is a real dip.
- New basket only when completed close is above EMA55 and not jammed into
  12h resistance (close < 99.7% of prior 12h high).
- Base limit: nearest technical dip (`max` of EMA21 and support that is ≥0.3%
  below close). Safety orders: `max(geometric step, technical dip)` still at
  least 0.6% below last fill. Geometric step starts at 1.0% and scales 1.15×.
- 1 base + up to 5 safety orders. One fill per hour. Same-bar: liquidation
  first; if both SO and TP are possible, **fill the SO only** (no same-bar rescue).
- Gap through a limit: fill at the open as taker.
- **Margin ratio cap 3%** after every fill: Binance-style
  `MR = (qty * mark * 0.4% MMR) / wallet`. Size so post-fill MR ≤ 3%. If the
  next SO would breach, skip it. At 0.4% MMR this is ~7.5× notional vs wallet
  when UPNL is ~0, and roughly a **~13% further drop** from that mark to
  liquidation — not a 3% stop.
- Exit: **take-profit 2% above average entry** (limit). Hold until TP, 80% MR
  emergency flatten, or end-of-sample MTM. No time stop.
- Cost B is the decision model. Funding −0.01% per 00:00/08:00/16:00 UTC.

## Run F1 (frozen 3% MR)

```bash
docker compose build
docker compose --profile backtest run --rm --no-deps dca-backtest python -u -m experiments.dca.backtest_dca
```

## F2 (1% MR cap)

Same rules as F1 except post-fill MR ≤ **1%** (~2.5× notional, ~40% further
drop to liquidation). Do not retune F1.

```bash
docker compose --profile backtest run --rm --no-deps dca-backtest python -u -m experiments.dca.backtest_dca_f2
```

## F3 (1% MR + 50% equity stop)

Same as F2, plus flatten when wallet ≤ 50% of equity at the first fill of that
basket. A 50% *price* stop would be below F2's liquidation level.

```bash
docker compose --profile backtest run --rm --no-deps dca-backtest python -u -m experiments.dca.backtest_dca_f3
```

## F4 (0.5% MR + SL80)

Same DCA engine, post-fill MR ≤ **0.5%** and flatten at **20%** of basket-start
wallet (80% loss on that stack). Do not retune F3.

```bash
docker compose --profile backtest run --rm --no-deps dca-backtest python -u -m experiments.dca.backtest_dca_f4
```

## F5 (2% MR + SL80)

Same SL80 as F4, post-fill MR ≤ **2%**. Do not retune F4.

```bash
docker compose --profile backtest run --rm --no-deps dca-backtest python -u -m experiments.dca.backtest_dca_f5
```

## F6 (1% MR + SL80, fixed $10k clip)

Same as the 1% SL80 sweep, but basket notional is always planned from **$10,000**,
not from current equity. Live MR cap can still cut size after losses.

```bash
docker compose --profile backtest run --rm --no-deps dca-backtest python -u -m experiments.dca.backtest_dca_f6
```

## F7 (1% MR + SL80, step to $20k clip)

Same as F6 until mark wallet ≥ **$20,000**. New baskets then plan from **$20,000**.
SL80 is 80% of that basket’s clip. If wallet later falls below $20k, the next
new basket uses $10k again. Do not retune F6.

```bash
docker compose --profile backtest run --rm --no-deps dca-backtest python -u -m experiments.dca.backtest_dca_f7
```

## F8 (1% MR + SL80, $20k start and clip)

Same as F6 at **$20,000** start and a frozen **$20,000** clip. Do not retune F6/F7.

```bash
docker compose --profile backtest run --rm --no-deps dca-backtest python -u -m experiments.dca.backtest_dca_f8
```

## G1 (Coin-M BTCUSD_PERP, F6 rules)

Inverse perpetual. Start with **$10,000 of BTC** at the first tradable 1h open.
1% MR, SL80, frozen $10k USD clip. Idle BTC still moves in USD. Do not retune F6.

```bash
docker compose --profile backtest run --rm --no-deps dca-backtest python -u -m experiments.dca.backtest_dca_coinm
```

## Isolated runner (BTC + alts, start vs end)

Edit `research/experiments/dca/run_isolated.py` (`ASSETS`, `START_USD`, `MR_CAP`, `SL_LOSS`, `SO_STYLE`, `TP_PCT`). Isolated only.
`SO_STYLE=geometric` is the F6 ladder. Isolated `TP_PCT` defaults to 5% here; frozen F6 suites stay at 2%.

```bash
mkdir -p results_dca_run results_dca_run_5m
chmod 777 results_dca_run results_dca_run_5m
# Leaves the live bot (btc-eth-hedge) running:
docker compose --profile backtest run --rm --no-deps dca-backtest
```

Same thing without the extra service:

```bash
docker compose --profile backtest run --rm --no-deps dca-backtest python -u -m experiments.dca.run_isolated
```

Do not use `docker compose up` / `up -d` for a backtest — that recreates the bot container. Report: `results_dca_run/REPORT.md` or `results_dca_run_5m/` if `INTERVAL=5m`.

## Live/paper (`main.py`)

Docker image only copies root `*.py`. Research still bind-mounts `./experiments` for `run_isolated`.

`main.py` defaults: **BTCUSDT**, 15m range-SO, clip = **actual USD-M USDT wallet**. Coin-M: `DCA_MARKET=coinm` (signals). Experiment suites are unchanged.

```bash
docker compose up
```

Keep `DRY_RUN=true` and testnet `BASE_URL`. Orders need `DCA_ALLOW_ORDERS=true`. Production also needs `DCA_CONFIRM_PRODUCTION=true`.


