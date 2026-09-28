# Isolated DCA — start vs end

- Run: 2026-09-12 10:02 UTC
- Last bar: 2026-09-12 09:54:59.999000+00:00
- Isolated wallet / clip: $10,000 each
- MR cap: 1%   SL: 90% of the drop from avg down to current liq (always above liq)
- Safety orders: range (7d range rungs; freeze 7d low at first fill; no more SOs if that low expands >2% or 12h support breaks)
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
| BTC | $10,000 | $10,629 | 0.2053 BTC ($5,800) | $16,429 | 19 | 0 | 0 | 0 |
| ETH | $10,000 | $12,123 | — | $12,123 | 48 | 2 | 2 | 0 |
| DOGE | $10,000 | $389 | — | $389 | 75 | 4 | 3 | 1 |
| SOL | $10,000 | $25,003 | — | $25,003 | 86 | 2 | 2 | 0 |

## Coin-M (coin wallet)

| Asset | Start | Idle | Open basket | Wallet | Trades | SL | Possible liq | SL cut TP |
|---|---|---:|---|---:|---:|---:|---:|---:|
| BTC | 0.2276 BTC ($10,000) | 0.3837 BTC ($29,653) | — | $29,653 | 26 | 0 | 0 | 0 |
| ETH | 4.501 ETH ($10,000) | 0.020 ETH ($50) | — | $50 | 56 | 5 | 5 | 0 |
| DOGE | 127,779 DOGE ($10,000) | 0 DOGE ($0) | 2,410 DOGE ($204) | $204 | 128 | 10 | 10 | 0 |
| SOL | 111.80 SOL ($10,000) | 34.99 SOL ($3,565) | 98.42 SOL ($10,030) | $13,595 | 97 | 5 | 4 | 1 |
