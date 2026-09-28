# Isolated DCA — start vs end

- Run: 2026-09-12 07:35 UTC
- Last bar: 2026-09-12 07:24:59.999000+00:00
- Isolated wallet / clip: $10,000 each
- MR cap: 1%   SL: 90% of the drop from avg down to current liq (always above liq)
- Safety orders: range (7d range rungs; no new basket in top quartile / <6% to 7d low); max 2 SOs sized like F6 weights
- Bar: 5m (one fill per bar; EMA/swing still 21h / 55h / 12h)
- Entry TTL: cancel unfilled base after 1h; sit out that bar (matches live DCA_ENTRY_TTL_SEC / ghost-GTC cancel). Safety orders keep working.
- Take-profit: 5% from average entry
- Hard SL: off
- Stale bag: flatten if still ≥40% below average after 180d (ETH 4.6k→2.4k). Flatten then re-enter lower (skip ema55 / 7d-top until the next fill).
- Give-up: off
- Possible liq = SL fired and holding that basket would have liquidated before +5% TP
- SL cut TP = stop fired and that basket would have hit TP if held
- Idle = USDT (USD-M) or coin not in the trade. It does not change if the open basket moves.
- Open basket = isolated pocket (margin + uPnL) at last close. At price P: open USD ≈ Open USD + qty × (P − last close).
- Wallet = Idle + Open. Not a taker flatten.
- Trades = Cost B closed baskets (TP, SL, emergency). Open MTM is not a trade

## USD-M (USDT)

| Asset | Start | Idle | Open basket | Wallet | Trades | SL | Possible liq | SL cut TP |
|---|---:|---:|---|---:|---:|---:|---:|
| BTC | $10,000 | $2,296 | 0.0478 BTC ($8,957) | $11,254 | 15 | 0 | 0 | 0 |
| ETH | $10,000 | $10,014 | — | $10,014 | 24 | 1 | 0 | 0 |
| DOGE | $10,000 | $0 | 38,064 DOGE ($8,321) | $8,321 | 61 | 3 | 0 | 2 |
| SOL | $10,000 | $5,611 | 43.95 SOL ($9,972) | $15,583 | 60 | 1 | 0 | 0 |

## Coin-M (coin wallet)

| Asset | Start | Idle | Open basket | Wallet | Trades | SL | Possible liq | SL cut TP |
|---|---|---:|---|---:|---:|---:|---:|---:|
| BTC | 0.2276 BTC ($10,000) | 0.2302 BTC ($17,787) | — | $17,787 | 17 | 1 | 0 | 0 |
| ETH | 4.501 ETH ($10,000) | 4.303 ETH ($10,853) | — | $10,853 | 22 | 1 | 0 | 0 |
| DOGE | 127,779 DOGE ($10,000) | 10,199 DOGE ($862) | 72,603 DOGE ($6,139) | $7,001 | 68 | 4 | 2 | 1 |
| SOL | 111.80 SOL ($10,000) | 16.35 SOL ($1,664) | 96.32 SOL ($9,801) | $11,464 | 69 | 2 | 2 | 0 |
