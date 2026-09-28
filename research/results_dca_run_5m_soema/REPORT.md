# Isolated DCA — start vs end

- Run: 2026-09-12 07:25 UTC
- Last bar: 2026-09-12 07:19:59.999000+00:00
- Isolated wallet / clip: $10,000 each
- MR cap: 1%   SL: 90% of the drop from avg down to current liq (always above liq)
- Safety orders: range (7d range rungs; no new basket in top quartile / <6% to 7d low); SOs only if close and limit stay above 55h EMA
- Bar: 5m (one fill per bar; EMA/swing still 21h / 55h / 12h)
- Entry TTL: cancel unfilled base after 1h; sit out that bar (matches live DCA_ENTRY_TTL_SEC / ghost-GTC cancel). Safety orders keep working.
- Take-profit: 5% from average entry
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
| BTC | $10,000 | $5,897 | 0.2037 BTC ($7,779) | $13,676 | 18 | 0 | 0 | 0 |
| ETH | $10,000 | $14,289 | — | $14,289 | 42 | 1 | 1 | 0 |
| DOGE | $10,000 | $1,546 | 165,443 DOGE ($6,587) | $8,132 | 87 | 2 | 2 | 0 |
| SOL | $10,000 | $0 | 32.86 SOL ($5,458) | $5,458 | 77 | 2 | 2 | 0 |

## Coin-M (coin wallet)

| Asset | Start | Idle | Open basket | Wallet | Trades | SL | Possible liq | SL cut TP |
|---|---|---:|---|---:|---:|---:|---:|---:|
| BTC | 0.2276 BTC ($10,000) | 0.3138 BTC ($24,257) | — | $24,257 | 24 | 0 | 0 | 0 |
| ETH | 4.501 ETH ($10,000) | 0.599 ETH ($1,511) | — | $1,511 | 48 | 3 | 2 | 1 |
| DOGE | 127,779 DOGE ($10,000) | 0 DOGE ($0) | 33,565 DOGE ($2,837) | $2,837 | 97 | 5 | 4 | 0 |
| SOL | 111.80 SOL ($10,000) | 44.65 SOL ($4,541) | 96.45 SOL ($9,810) | $14,351 | 71 | 2 | 2 | 0 |
