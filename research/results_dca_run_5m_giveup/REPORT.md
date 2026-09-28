# Isolated DCA — start vs end

- Run: 2026-09-12 07:21 UTC
- Last bar: 2026-09-12 07:14:59.999000+00:00
- Isolated wallet / clip: $10,000 each
- MR cap: 1%   SL: 90% of the drop from avg down to current liq (always above liq)
- Safety orders: range (7d range rungs; no new basket in top quartile / <6% to 7d low); SOs only if close and limit stay above 55h EMA
- Bar: 5m (one fill per bar; EMA/swing still 21h / 55h / 12h)
- Entry TTL: cancel unfilled base after 1h; sit out that bar (matches live DCA_ENTRY_TTL_SEC / ghost-GTC cancel). Safety orders keep working.
- Take-profit: 5% from average entry
- Stale bag: flatten if still ≥40% below average after 180d (ETH 4.6k→2.4k). Flatten then re-enter lower (skip ema55 / 7d-top until the next fill).
- Give-up: flatten if ≥3 fills and still ≥12% below avg after 14d (cuts laddered crash bags before the 90%-to-liq SL).
- Possible liq = SL fired and holding that basket would have liquidated before +5% TP
- SL cut TP = stop fired and that basket would have hit TP if held
- Idle = USDT (USD-M) or coin not in the trade. It does not change if the open basket moves.
- Open basket = isolated pocket (margin + uPnL) at last close. At price P: open USD ≈ Open USD + qty × (P − last close).
- Wallet = Idle + Open. Not a taker flatten.
- Trades = Cost B closed baskets (TP, SL, emergency). Open MTM is not a trade

## USD-M (USDT)

| Asset | Start | Idle | Open basket | Wallet | Trades | SL | Possible liq | SL cut TP |
|---|---:|---:|---|---:|---:|---:|---:|
| BTC | $10,000 | $10,202 | — | $10,202 | 31 | 4 | 0 | 3 |
| ETH | $10,000 | $11,257 | — | $11,257 | 56 | 7 | 0 | 6 |
| DOGE | $10,000 | $0 | 62,794 DOGE ($8,783) | $8,783 | 126 | 14 | 1 | 10 |
| SOL | $10,000 | $0 | 40.53 SOL ($6,733) | $6,733 | 109 | 11 | 0 | 9 |

## Coin-M (coin wallet)

| Asset | Start | Idle | Open basket | Wallet | Trades | SL | Possible liq | SL cut TP |
|---|---|---:|---|---:|---:|---:|---:|---:|
| BTC | 0.2276 BTC ($10,000) | 0.2779 BTC ($21,481) | — | $21,481 | 30 | 2 | 0 | 2 |
| ETH | 4.501 ETH ($10,000) | 3.963 ETH ($9,999) | — | $9,999 | 57 | 8 | 2 | 6 |
| DOGE | 127,779 DOGE ($10,000) | 0 DOGE ($0) | 77,731 DOGE ($6,569) | $6,569 | 123 | 16 | 7 | 8 |
| SOL | 111.80 SOL ($10,000) | 0.00 SOL ($0) | 77.87 SOL ($7,921) | $7,921 | 106 | 12 | 4 | 8 |
