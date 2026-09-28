# Isolated DCA — start vs end

- Run: 2026-09-28 08:22 UTC
- Window: 2024-01-08 through each symbol's last cached bar on 2026-09-28
- Start: $1,000. Clip starts at $1,000.
- Sizing: every $5,000 of wallet, the clip becomes that step. $5,000 wallet sizes off $5,000. $12,000 sizes off $10,000. $15,000 sizes off $15,000.
- If the wallet shrinks, the clip steps down the same $5,000 ladder. Under $5,000 it is $1,000 again.
- An order uses min(clip, wallet). MR cap 10% of that amount.
- SL, memory, and TP are each symbol's recorded hedge. Stale: 40% adverse after 180d.
- Safety orders: range, max 10, reclaim. Bar: 1m. Entry TTL: 1h.
- Possible liq = SL fired and holding that basket would have liquidated before TP
- SL cut TP = stop fired and that basket would have hit TP if held
- Idle = cash. Open basket = unrealized P&L of whatever is still open.
- Wallet = Idle + Open. Not a taker flatten. SL is the price stop only.

## USD-M (USDT)

| Asset | Start | Final clip | Idle | Open basket | Wallet | Trades | TP | SL | Liq | Possible liq | SL cut TP |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| BTC | $1,000 | $1,000 | $546 | — | $546 | 21 | 19 | 2 | 0 | 0 | 0 |
| ETH | $1,000 | $1,000 | $38 | — | $38 | 9 | 7 | 2 | 0 | 0 | 0 |
| SOL | $1,000 | $1,000 | $24 | — | $24 | 33 | 28 | 2 | 3 | 0 | 0 |
| DOGE | $1,000 | $1,000 | $8 | — | $8 | 20 | 16 | 3 | 1 | 0 | 0 |

| Asset | Memory | TP | SL | Train | Validate | Holdout |
|---|---:|---:|---:|---:|---:|---:|
| BTC | 30d | 5% | 90% | -$756 | $89 | $247 |
| ETH | 180d | 5% | 90% | -$1,004 | $0 | $0 |
| SOL | 90d | 5% | 90% | -$983 | $0 | $0 |
| DOGE | 180d | 8% | 90% | -$549 | -$212 | $0 |

