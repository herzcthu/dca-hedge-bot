# Isolated DCA — start vs end

- Run: 2026-09-12 07:30 UTC
- Last bar: 2026-09-12 07:19:59.999000+00:00
- Isolated wallet / clip: $10,000 each
- MR cap: 1%   SL: 90% of the drop from avg down to current liq (always above liq)
- Safety orders: range (7d range rungs; no new basket in top quartile / <6% to 7d low)
- Bar: 5m (one fill per bar; EMA/swing still 21h / 55h / 12h)
- Entry TTL: cancel unfilled base after 1h; sit out that bar (matches live DCA_ENTRY_TTL_SEC / ghost-GTC cancel). Safety orders keep working.
- Take-profit: 5% from average entry
- Hard SL: flatten at 20% below average (before the 90%-to-liq stop)
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
| BTC | $10,000 | $6,053 | — | $6,053 | 36 | 4 | 0 | 3 |
| ETH | $10,000 | $13,204 | — | $13,204 | 71 | 7 | 3 | 4 |
| DOGE | $10,000 | $429 | — | $429 | 133 | 16 | 6 | 10 |
| SOL | $10,000 | $7,331 | 188.70 SOL ($10,041) | $17,373 | 121 | 10 | 5 | 5 |

## Coin-M (coin wallet)

| Asset | Start | Idle | Open basket | Wallet | Trades | SL | Possible liq | SL cut TP |
|---|---|---:|---|---:|---:|---:|---:|---:|
| BTC | 0.2276 BTC ($10,000) | 0.3072 BTC ($23,741) | — | $23,741 | 36 | 2 | 0 | 2 |
| ETH | 4.501 ETH ($10,000) | 1.479 ETH ($3,728) | — | $3,728 | 67 | 7 | 6 | 1 |
| DOGE | 127,779 DOGE ($10,000) | 0 DOGE ($0) | 2,359 DOGE ($199) | $199 | 152 | 21 | 12 | 9 |
| SOL | 111.80 SOL ($10,000) | 72.10 SOL ($7,333) | 96.88 SOL ($9,853) | $17,187 | 115 | 10 | 6 | 4 |
