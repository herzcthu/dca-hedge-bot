# Isolated DCA — start vs end

- Run: 2026-09-28 06:20 UTC
- Last bar: 2026-09-28 03:08:59.999000+00:00
- Isolated wallet / clip: $10,000
- MR cap: 10%   SL: 90% of the path from avg to account liquidation
- Safety orders: range (7d range rungs; freeze 7d low at first fill; no SO if 7d low expands >2% or 12h support breaks; next SO only after close reclaims 21h EMA); max 10 SOs
- Bar: 1m (one fill per bar; EMA/swing still 21h / 55h / 12h)
- Entry TTL: cancel unfilled base after 1h. Safety orders keep working.
- Take-profit: 5% from average entry
- Peak brake: no new basket while wallet is ≥15% under the 90d rolling marked-wallet high
- Stale bag: flatten if still ≥40% adverse after 180d
- Book: hedge, long and short, one wallet. SOLUSDT.
- Possible liq = SL fired and holding that basket would have liquidated before +5% TP
- SL cut TP = stop fired and that basket would have hit TP if held
- Idle = cash. Open basket = unrealized P&L of whatever is still open.
- Wallet = Idle + Open. Not a taker flatten.
- Trades = Cost B closed baskets. Open mark is not a trade.
- SL is the price stop only. A stale flatten is not an SL, so it is not Possible liq and not SL cut TP.

## USD-M (USDT)

| Asset | Start | Idle | Open basket | Wallet | Trades | TP | SL | Liq | Possible liq | SL cut TP |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| SOL | $10,000 | $237,521 | 280.46 SOL short (−$13,738) | $223,783 | 82 | 81 | 0 | 0 | 0 | 0 |
