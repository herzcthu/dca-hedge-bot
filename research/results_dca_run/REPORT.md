# Isolated DCA — start vs end

- Run: 2026-09-10 12:16 UTC
- Last bar: 2026-09-10 11:59:59.999000+00:00
- Isolated wallet / clip: $10,000 each
- MR cap: 1%   SL: 90% of the drop from avg down to current liq (always above liq)
- Safety orders: range (7d range rungs; no new basket in top quartile / <6% to 7d low)
- Bar: 15m (one fill per bar; EMA/swing still 21h / 55h / 12h)
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
| BTC | $10,000 | $8,932 | 0.2045 BTC ($5,868) | $14,800 | 20 | 0 | 0 | 0 |
| ETH | $10,000 | $5,547 | 7.880 ETH ($10,155) | $15,702 | 49 | 2 | 2 | 0 |
| DOGE | $10,000 | $105 | — | $105 | 87 | 5 | 4 | 1 |
| SOL | $10,000 | $5,156 | 144.36 SOL ($9,901) | $15,058 | 75 | 3 | 3 | 0 |

## Coin-M (coin wallet)

| Asset | Start | Idle | Open basket | Wallet | Trades | SL | Possible liq | SL cut TP |
|---|---|---:|---|---:|---:|---:|---:|---:|
| BTC | 0.2276 BTC ($10,000) | 0.2923 BTC ($22,748) | — | $22,748 | 28 | 1 | 1 | 0 |
| ETH | 4.501 ETH ($10,000) | 0.007 ETH ($18) | — | $18 | 66 | 6 | 5 | 1 |
| DOGE | 127,779 DOGE ($10,000) | 0 DOGE ($0) | 4,241 DOGE ($361) | $361 | 144 | 11 | 11 | 0 |
| SOL | 111.80 SOL ($10,000) | 0.16 SOL ($16) | — | $16 | 77 | 8 | 6 | 2 |
