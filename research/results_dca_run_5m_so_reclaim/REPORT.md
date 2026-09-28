# Isolated DCA — start vs end

- Run: 2026-09-12 10:42 UTC
- Last bar: 2026-09-12 10:34:59.999000+00:00
- Isolated wallet / clip: $10,000 each
- MR cap: 1%   SL: 90% of the drop from avg down to current liq (always above liq)
- Safety orders: range (7d range rungs; freeze 7d low at first fill; no SO if 7d low expands >2% or 12h support breaks; next SO only after close reclaims 21h EMA)
- Bar: 5m (one fill per bar; EMA/swing still 21h / 55h / 12h)
- Entry TTL: cancel unfilled base after 1h; sit out that bar (matches live DCA_ENTRY_TTL_SEC / ghost-GTC cancel). Safety orders keep working.
- Take-profit: 5% from average entry (baseline; per-coin overlay in ASSET_TUNE)
- Overlays: none (every coin on baseline)
- Hard SL: off
- Stale bag: flatten if still ≥40% below average after 180d (ETH 4.6k→2.4k). Flatten then re-enter lower (skip ema55 / 7d-top until the next fill).
- Give-up: off
- Peak brake: off
- Possible liq = SL fired and holding that basket would have liquidated before +5% TP
- SL cut TP = stop fired and that basket would have hit TP if held
- Idle = USDT (USD-M) or coin not in the trade. It does not change if the open basket moves.
- Open basket = isolated pocket (margin + uPnL) at last close. At price P: open USD ≈ Open USD + qty × (P − last close).
- Wallet = Idle + Open. Not a taker flatten.
- Trades = Cost B closed baskets (TP, SL, emergency). Open MTM is not a trade

## USD-M (USDT)

| Asset | Start | Idle | Open basket | Wallet | Trades | SL | Possible liq | SL cut TP |
|---|---:|---:|---|---:|---:|---:|---:|
| BTC | $10,000 | $8,531 | 0.1100 BTC ($7,611) | $16,142 | 18 | 0 | 0 | 0 |
| ETH | $10,000 | $15,506 | — | $15,506 | 37 | 1 | 1 | 0 |
| DOGE | $10,000 | $0 | 84,266 DOGE ($3,947) | $3,947 | 85 | 4 | 3 | 1 |
| SOL | $10,000 | $12,196 | 144.87 SOL ($10,146) | $22,343 | 87 | 2 | 2 | 0 |

## Coin-M (coin wallet)

| Asset | Start | Idle | Open basket | Wallet | Trades | SL | Possible liq | SL cut TP |
|---|---|---:|---|---:|---:|---:|---:|---:|
| BTC | 0.2276 BTC ($10,000) | 0.3720 BTC ($28,767) | — | $28,767 | 26 | 0 | 0 | 0 |
| ETH | 4.501 ETH ($10,000) | 0.231 ETH ($584) | — | $584 | 54 | 4 | 3 | 1 |
| DOGE | 127,779 DOGE ($10,000) | 0 DOGE ($0) | 7,982 DOGE ($677) | $677 | 118 | 9 | 7 | 1 |
| SOL | 111.80 SOL ($10,000) | 0.00 SOL ($0) | 73.92 SOL ($7,542) | $7,542 | 71 | 4 | 3 | 1 |
