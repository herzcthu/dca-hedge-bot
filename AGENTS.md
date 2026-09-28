# Trading Bot Agent Rules

- Keep `BASE_URL` on Binance Futures testnet unless the user explicitly requests production and confirms the risk.
- Isolated DCA research stays in `research/experiments/dca` (backtests only). Live/paper path is `main.py` + `dca_rules.py`, **one USD-M symbol** (default `DOGEUSDT`). Do not import the experiment package from `main.py`. Keep `BASE_URL` on testnet; require `DCA_ALLOW_ORDERS` and `DCA_CONFIRM_PRODUCTION` before any production orders. Coin-M is not a live path.
- Do not revive the retired BTC/ETH gap-reversion scalp, pair variants, 1-30m breakout, volume breakout, or BTC 15m impulse-fade scalp without a new frozen specification and positive fee-inclusive test.
- Scalp candidates must use minutes-to-one-hour holding periods; strategies that require holding over a day are out of scope for this bot.
- For taker-fee scalps, require average net P&L > 0 after all fills and a clearly stated fee model before any paper/live implementation.
- Never treat a mark-price gap as realized profit. Entry and exit decisions must use executable bid/ask estimates and actual fills where available.
- For any future pair strategy, a gap-based take-profit may close only when estimated combined P&L is positive after the configured fee estimate.
- For any future pair strategy, both legs must be submitted, fill status must be checked, and partial or failed entries must be canceled and flattened.
- Reduce-only exit orders must be confirmed filled before resetting trade state or allowing the next entry.
- Startup must not trade on top of unknown positions or open orders. Query and report account state first; flatten only explicitly identified testnet exposure.
- Persist UTC timestamps, order requests, exchange responses, fill statuses, bid/ask data, estimated gross P&L, estimated fees, and estimated net P&L to `data/events.csv`.
- Do not log API keys, private keys, signatures, or signed URLs.
- Validate with `python3 -m py_compile main.py` and `docker compose config` after edits. Keep the service stopped while changing live-order logic, then verify testnet positions and open orders after any live test.
