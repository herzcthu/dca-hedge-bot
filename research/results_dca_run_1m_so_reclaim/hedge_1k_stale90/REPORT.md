# Isolated DCA — start vs end

- Run: 2026-09-28 07:59 UTC
- Window: 2024-01-08 through each symbol's last cached bar on 2026-09-28
- Start: $1,000. Clip: $1,000 fixed. No step-up.
- MR cap: 10%   SL: from each symbol's recorded hedge, as a fraction of the path from avg to account liquidation
- Safety orders: range (7d range rungs; freeze 7d low at first fill; no SO if 7d low expands >2% or 12h support breaks; next SO only after close reclaims 21h EMA); max 10 SOs
- Bar: 1m (one fill per bar; EMA/swing still 21h / 55h / 12h)
- Entry TTL: cancel unfilled base after 1h. Safety orders keep working.
- Stale bag: flatten if still ≥40% adverse after 90d
- Book: hedge, long and short, one wallet. Each symbol uses its recorded memory, TP, and SL.
- Possible liq = SL fired and holding that basket would have liquidated before TP
- SL cut TP = stop fired and that basket would have hit TP if held
- Idle = cash. Open basket = unrealized P&L of whatever is still open.
- Wallet = Idle + Open. Not a taker flatten.
- Trades = Cost B closed baskets. Open mark is not a trade. SL is the price stop only.

## USD-M (USDT)

| Asset | Start | Idle | Open basket | Wallet | Trades | TP | SL | Stale | Liq | Possible liq | SL cut TP |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BTC | $1,000 | $50 | — | $50 | 18 | 15 | 2 | 1 | 0 | 0 | 0 |
| ETH | $1,000 | $38 | — | $38 | 9 | 7 | 2 | 0 | 0 | 0 | 0 |
| SOL | $1,000 | $13,000 | 16.34 SOL short ($34) | $13,034 | 92 | 87 | 0 | 5 | 0 | 0 | 0 |
| DOGE | $1,000 | $3,799 | 64,786.11 DOGE long ($66), 85,697.23 DOGE short ($0) | $3,865 | 59 | 55 | 1 | 3 | 0 | 0 | 0 |

## Closed-trade net by split

| Asset | Memory | TP | SL | Train | Validate | Holdout |
|---|---:|---:|---:|---:|---:|---:|
| BTC | 30d | 5% | 90% | -$756 | -$151 | $0 |
| ETH | 180d | 5% | 90% | -$1,004 | $0 | $0 |
| SOL | 90d | 5% | 90% | $17,983 | -$7,056 | $1,289 |
| DOGE | 180d | 8% | 90% | $5,771 | -$4,877 | $2,868 |

