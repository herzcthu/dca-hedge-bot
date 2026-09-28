# Isolated DCA — start vs end

- Run: 2026-09-28 07:23 UTC
- Window: 2024-01-08 through each symbol's last cached bar on 2026-09-28
- Start: $1,000. Initial clip: $1,000.
- Sizing: when the marked wallet doubles, the clip grows by the percent in that section. It does not double, and it does not step down.
- An order uses min(clip, wallet). The 10% margin cap is applied to that amount, same as day one. After the wallet has grown, the clip is a smaller share of the account than it was at the start.
- Example, +50%: $1,000 clip at the start, $1,500 at a $2,000 wallet, $2,250 at $4,000, $3,375 at $8,000.
- Example, +20%: $1,000, then $1,200, $1,440, $1,728 at those same wallet levels.
- MR cap: 10%. SL, memory, and TP are each symbol's recorded hedge.
- Safety orders: range, max 10, reclaim. Bar: 1m. Entry TTL: 1h. Stale: 40% adverse after 180d.
- Possible liq = SL fired and holding that basket would have liquidated before TP
- SL cut TP = stop fired and that basket would have hit TP if held
- Idle = cash. Open basket = unrealized P&L of whatever is still open.
- Wallet = Idle + Open. Not a taker flatten. SL is the price stop only.

## Clip +50% at each doubling

| Asset | Start | Final clip | Idle | Open basket | Wallet | Trades | TP | SL | Liq | Possible liq | SL cut TP |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| BTC | $1,000 | $1,000 | $546 | — | $546 | 21 | 19 | 2 | 0 | 0 | 0 |
| ETH | $1,000 | $1,000 | $38 | — | $38 | 9 | 7 | 2 | 0 | 0 | 0 |
| SOL | $1,000 | $2,250 | $14 | — | $14 | 28 | 24 | 4 | 0 | 0 | 0 |
| DOGE | $1,000 | $7,594 | $390 | — | $390 | 38 | 34 | 4 | 0 | 0 | 0 |

| Asset | Memory | TP | SL | Train | Validate | Holdout |
|---|---:|---:|---:|---:|---:|---:|
| BTC | 30d | 5% | 90% | -$756 | $89 | $247 |
| ETH | 180d | 5% | 90% | -$1,004 | $0 | $0 |
| SOL | 90d | 5% | 90% | -$956 | $0 | $0 |
| DOGE | 180d | 8% | 90% | $4,139 | -$2,117 | $190 |

## Clip +20% at each doubling

| Asset | Start | Final clip | Idle | Open basket | Wallet | Trades | TP | SL | Liq | Possible liq | SL cut TP |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| BTC | $1,000 | $1,000 | $546 | — | $546 | 21 | 19 | 2 | 0 | 0 | 0 |
| ETH | $1,000 | $1,000 | $38 | — | $38 | 9 | 7 | 2 | 0 | 0 | 0 |
| SOL | $1,000 | $1,440 | $46 | — | $46 | 42 | 36 | 4 | 2 | 0 | 0 |
| DOGE | $1,000 | $2,074 | $9,605 | — | $9,605 | 44 | 40 | 0 | 2 | 0 | 0 |

| Asset | Memory | TP | SL | Train | Validate | Holdout |
|---|---:|---:|---:|---:|---:|---:|
| BTC | 30d | 5% | 90% | -$756 | $89 | $247 |
| ETH | 180d | 5% | 90% | -$1,004 | $0 | $0 |
| SOL | 90d | 5% | 90% | -$486 | -$473 | $0 |
| DOGE | 180d | 8% | 90% | $16,953 | $13,471 | -$19,401 |

