# Isolated DCA — start vs end

- Run: 2026-09-28 07:48 UTC
- Window: 2024-01-08 through each symbol's last cached bar on 2026-09-28
- Start: $1,000. Initial clip: $1,000.
- Sizing: the clip grows 10% at each triple of the starting wallet. A doubled wallet stays on the old clip.
- If the wallet falls, the clip steps down to the triple that wallet still clears. A $4,000 wallet uses the $3,000 clip ($1,100), not the original $1,000.
- An order uses min(clip, wallet). The 10% margin cap is applied to that amount, same as day one.
- Levels, +10%: $1,000 below $3,000. $1,100 from $3,000. $1,210 from $9,000. $1,331 from $27,000.
- MR cap: 10%. SL, memory, and TP are each symbol's recorded hedge.
- Safety orders: range, max 10, reclaim. Bar: 1m. Entry TTL: 1h. Stale: 40% adverse after 180d.
- Possible liq = SL fired and holding that basket would have liquidated before TP
- SL cut TP = stop fired and that basket would have hit TP if held
- Idle = cash. Open basket = unrealized P&L of whatever is still open.
- Wallet = Idle + Open. Not a taker flatten. SL is the price stop only.

## Clip +10% at each triple

| Asset | Start | Final clip | Idle | Open basket | Wallet | Trades | TP | SL | Liq | Possible liq | SL cut TP |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| BTC | $1,000 | $1,000 | $546 | — | $546 | 21 | 19 | 2 | 0 | 0 | 0 |
| ETH | $1,000 | $1,000 | $38 | — | $38 | 9 | 7 | 2 | 0 | 0 | 0 |
| SOL | $1,000 | $1,210 | $27,341 | 33.94 SOL short (-$1,662) | $25,678 | 82 | 81 | 0 | 0 | 0 | 0 |
| DOGE | $1,000 | $1,210 | $15,652 | — | $15,652 | 53 | 50 | 0 | 0 | 0 | 0 |

| Asset | Memory | TP | SL | Train | Validate | Holdout |
|---|---:|---:|---:|---:|---:|---:|
| BTC | 30d | 5% | 90% | -$756 | $89 | $247 |
| ETH | 180d | 5% | 90% | -$1,004 | $0 | $0 |
| SOL | 90d | 5% | 90% | $22,131 | -$2,573 | $6,256 |
| DOGE | 180d | 8% | 90% | $16,445 | $12,131 | -$11,658 |

