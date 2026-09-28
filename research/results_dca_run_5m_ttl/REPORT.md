# Isolated DCA — start vs end

- Run: 2026-09-12 07:02 UTC
- Last bar: 2026-09-12 06:54:59.999000+00:00
- Isolated wallet / clip: $10,000 each
- MR cap: 1%   SL: 90% of the drop from avg down to current liq (always above liq)
- Safety orders: range (7d range rungs; no new basket in top quartile / <6% to 7d low)
- Bar: 5m (one fill per bar; EMA/swing still 21h / 55h / 12h)
- Entry TTL: cancel unfilled base after 1h; sit out that bar (matches live DCA_ENTRY_TTL_SEC / ghost-GTC cancel). Safety orders keep working.
- Take-profit: 5% from average entry
- Stale bag: flatten if still ≥40% below average after 180d (ETH 4.6k→2.4k). Flatten then re-enter lower (skip ema55 / 7d-top until the next fill).
- Possible liq = SL fired and holding that basket would have liquidated before +5% TP
- SL cut TP = stop fired and that basket would have hit TP if held
- Idle = USDT (USD-M) or coin not in the trade. It does not change if the open basket moves.
- Open basket = isolated pocket (margin + uPnL) at last close. At price P: open USD ≈ Open USD + qty × (P − last close).
- Wallet = Idle + Open. Not a taker flatten.
- Trades = Cost B closed baskets (TP, SL, emergency). Open MTM is not a trade

## USD-M (USDT)

| Asset | Start | Idle | Open basket | Wallet | Trades | SL | Possible liq | SL cut TP |
|---|---:|---:|---|---:|---:|---:|---:|
| BTC | $10,000 | $8,739 | 0.2046 BTC ($5,740) | $14,478 | 16 | 0 | 0 | 0 |
| ETH | $10,000 | $15,745 | — | $15,745 | 49 | 2 | 2 | 0 |
| DOGE | $10,000 | $67 | — | $67 | 81 | 5 | 4 | 1 |
| SOL | $10,000 | $15,022 | 188.70 SOL ($10,034) | $25,056 | 84 | 2 | 2 | 0 |

## Coin-M (coin wallet)

| Asset | Start | Idle | Open basket | Wallet | Trades | SL | Possible liq | SL cut TP |
|---|---|---:|---|---:|---:|---:|---:|---:|
| BTC | 0.2276 BTC ($10,000) | 0.4058 BTC ($31,355) | — | $31,355 | 29 | 0 | 0 | 0 |
| ETH | 4.501 ETH ($10,000) | 0.041 ETH ($103) | — | $103 | 65 | 5 | 5 | 0 |
| DOGE | 127,779 DOGE ($10,000) | 0 DOGE ($0) | 1,774 DOGE ($150) | $150 | 135 | 11 | 11 | 0 |
| SOL | 111.80 SOL ($10,000) | 56.05 SOL ($5,699) | 96.82 SOL ($9,845) | $15,544 | 98 | 5 | 4 | 1 |
