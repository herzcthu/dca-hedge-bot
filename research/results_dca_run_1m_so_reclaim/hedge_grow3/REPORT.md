# Isolated DCA — start vs end

- Run: 2026-09-28 07:38 UTC
- Window: 2024-01-08 through each symbol's last cached bar on 2026-09-28
- Start: $1,000. Initial clip: $1,000.
- Sizing: the clip grows by the percent in that section only when the marked wallet triples. A doubled wallet stays on the old clip.
- A losing close puts the clip back to $1,000. The next increase waits until the wallet triples from that post-loss wallet.
- An order uses min(clip, wallet). The 10% margin cap is applied to that amount, same as day one.
- Example, +50%: $1,000 clip at $1,000 and at $2,000. $1,500 at $3,000. $2,250 at $9,000.
- Example, +20%: $1,000 until $3,000, then $1,200, then $1,440 at $9,000.
- MR cap: 10%. SL, memory, and TP are each symbol's recorded hedge.
- Safety orders: range, max 10, reclaim. Bar: 1m. Entry TTL: 1h. Stale: 40% adverse after 180d.
- Possible liq = SL fired and holding that basket would have liquidated before TP
- SL cut TP = stop fired and that basket would have hit TP if held
- Idle = cash. Open basket = unrealized P&L of whatever is still open.
- Wallet = Idle + Open. Not a taker flatten. SL is the price stop only.

## Clip +50% at each triple

| Asset | Start | Final clip | Idle | Open basket | Wallet | Trades | TP | SL | Liq | Possible liq | SL cut TP |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| BTC | $1,000 | $1,000 | $546 | — | $546 | 21 | 19 | 2 | 0 | 0 | 0 |
| ETH | $1,000 | $1,000 | $38 | — | $38 | 9 | 7 | 2 | 0 | 0 | 0 |
| SOL | $1,000 | $1,000 | $8 | — | $8 | 47 | 42 | 5 | 0 | 0 | 0 |
| DOGE | $1,000 | $1,000 | $21,904 | 64,786.11 DOGE long ($66), 85,697.23 DOGE short ($0) | $21,970 | 56 | 52 | 0 | 2 | 0 | 0 |

| Asset | Memory | TP | SL | Train | Validate | Holdout |
|---|---:|---:|---:|---:|---:|---:|
| BTC | 30d | 5% | 90% | -$756 | $89 | $247 |
| ETH | 180d | 5% | 90% | -$1,004 | $0 | $0 |
| SOL | 90d | 5% | 90% | -$42 | -$1,084 | -$55 |
| DOGE | 180d | 8% | 90% | $20,729 | $8,310 | -$5,994 |

## Clip +20% at each triple

| Asset | Start | Final clip | Idle | Open basket | Wallet | Trades | TP | SL | Liq | Possible liq | SL cut TP |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| BTC | $1,000 | $1,000 | $546 | — | $546 | 21 | 19 | 2 | 0 | 0 | 0 |
| ETH | $1,000 | $1,000 | $38 | — | $38 | 9 | 7 | 2 | 0 | 0 | 0 |
| SOL | $1,000 | $1,000 | $27,168 | 28.05 SOL short (-$1,374) | $25,794 | 82 | 81 | 0 | 0 | 0 | 0 |
| DOGE | $1,000 | $1,000 | $3,522 | — | $3,522 | 56 | 53 | 1 | 0 | 0 | 0 |

| Asset | Memory | TP | SL | Train | Validate | Holdout |
|---|---:|---:|---:|---:|---:|---:|
| BTC | 30d | 5% | 90% | -$756 | $89 | $247 |
| ETH | 180d | 5% | 90% | -$1,004 | $0 | $0 |
| SOL | 90d | 5% | 90% | $24,595 | -$4,194 | $5,170 |
| DOGE | 180d | 8% | 90% | $4,342 | $9,294 | -$9,356 |

