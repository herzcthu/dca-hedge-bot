# Isolated DCA — start vs end

- Run: 2026-09-12 10:30 UTC
- Last bar: 2026-09-12 10:24:59.999000+00:00
- Isolated wallet / clip: $10,000 each
- MR cap: 1%   SL: 90% of the drop from avg down to current liq (always above liq)
- Safety orders: range (7d range rungs; freeze 7d low at first fill; no SO if 7d low expands >2% or 12h support breaks; next SO only after close reclaims 21h EMA)
- Bar: 5m (one fill per bar; EMA/swing still 21h / 55h / 12h)
- Entry TTL: cancel unfilled base after 1h; sit out that bar (matches live DCA_ENTRY_TTL_SEC / ghost-GTC cancel). Safety orders keep working.
- Take-profit: 5% from average entry
- Hard SL: off
- Stale bag: flatten if still ≥40% below average after 180d (ETH 4.6k→2.4k). Flatten then re-enter lower (skip ema55 / 7d-top until the next fill).
- Give-up: off
- Peak brake: no new basket while wallet is ≥15% under the running high-water (open basket still TP/SL)
- Possible liq = SL fired and holding that basket would have liquidated before +5% TP
- SL cut TP = stop fired and that basket would have hit TP if held
- Idle = USDT (USD-M) or coin not in the trade. It does not change if the open basket moves.
- Open basket = isolated pocket (margin + uPnL) at last close. At price P: open USD ≈ Open USD + qty × (P − last close).
- Wallet = Idle + Open. Not a taker flatten.
- Trades = Cost B closed baskets (TP, SL, emergency). Open MTM is not a trade

## USD-M (USDT)

| Asset | Start | Idle | Open basket | Wallet | Trades | SL | Possible liq | SL cut TP |
|---|---:|---:|---|---:|---:|---:|---:|
| BTC | $10,000 | $8,531 | 0.1100 BTC ($7,613) | $16,144 | 18 | 0 | 0 | 0 |
| ETH | $10,000 | $8,606 | — | $8,606 | 23 | 1 | 1 | 0 |
| DOGE | $10,000 | $15,406 | — | $15,406 | 23 | 1 | 0 | 1 |
| SOL | $10,000 | $14,271 | — | $14,271 | 45 | 1 | 1 | 0 |

## Coin-M (coin wallet)

| Asset | Start | Idle | Open basket | Wallet | Trades | SL | Possible liq | SL cut TP |
|---|---|---:|---|---:|---:|---:|---:|---:|
| BTC | 0.2276 BTC ($10,000) | 0.3177 BTC ($24,567) | — | $24,567 | 16 | 0 | 0 | 0 |
| ETH | 4.501 ETH ($10,000) | 2.975 ETH ($7,531) | — | $7,531 | 8 | 1 | 1 | 0 |
| DOGE | 127,779 DOGE ($10,000) | 135,172 DOGE ($11,484) | — | $11,484 | 29 | 2 | 1 | 1 |
| SOL | 111.80 SOL ($10,000) | 134.91 SOL ($13,762) | — | $13,762 | 28 | 1 | 1 | 0 |
