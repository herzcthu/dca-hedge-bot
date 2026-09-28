# H1 hedge — long and short, one wallet

- Run: 2026-09-28 03:15 UTC
- Last bar: 2026-09-28 01:38:59.999000+00:00
- USD-M 1m. Cost B. One shared $10,000 wallet per symbol.
- Each new basket sizes off min($10,000, marked equity).
- Long: range SO, reclaim, TP 8%, peak-skip 15%/180d.
- Short is the mirror: below EMA55, not the 7d bottom quartile, SOs up to the frozen 7d high.
- SL is 95% of the way to the account liquidation price. Only the threatened side is stopped.
- Funding placeholder 0.01% per 8h: long pays, short receives.

| Symbol | Wallet | Trades | Long n / SL / PnL | Short n / SL / PnL | Train | Validate | Holdout |
|---|---:|---:|---:|---:|---:|---:|---:|
| BTCUSDT | $11 | 8 | 5 / 3 / $-11,555 | 3 / 0 / $1,808 | $-9,665 | $-82 | $0 |
| ETHUSDT | $2 | 5 | 3 / 0 / $3,545 | 2 / 2 / $-13,935 | $-10,390 | $0 | $0 |
| SOLUSDT | $46,729 | 30 | 17 / 0 / $-19,051 | 13 / 0 / $69,807 | $112,277 | $60,961 | $-122,483 |
| DOGEUSDT | $208,700 | 62 | 32 / 0 / $70,391 | 30 / 0 / $146,529 | $176,602 | $100,254 | $-59,936 |

- BTCUSDT open uPnL long=$0 short=$0 liquidated=False
- ETHUSDT open uPnL long=$0 short=$0 liquidated=False
- SOLUSDT open uPnL long=$1,485 short=$0 liquidated=False
- DOGEUSDT open uPnL long=$658 short=$4 liquidated=False
