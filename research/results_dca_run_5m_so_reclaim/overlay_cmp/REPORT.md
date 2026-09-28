# Isolated DCA — start vs end

- Run: 2026-09-12 11:52 UTC
- Last bar: 2026-09-12 11:29:59.999000+00:00
- Isolated wallet / clip: $10,000 each
- MR cap: 10%   SL: 90% of the drop from avg down to current liq (always above liq)
- Safety orders: range (7d range rungs; freeze 7d low at first fill; no SO if 7d low expands >2% or 12h support breaks; next SO only after close reclaims 21h EMA); max 10 SOs
- Bar: 5m (one fill per bar; EMA/swing still 21h / 55h / 12h)
- Entry TTL: cancel unfilled base after 1h; sit out that bar (matches live DCA_ENTRY_TTL_SEC / ghost-GTC cancel). Safety orders keep working.
- Take-profit: 5% from average entry (baseline; per-coin overlay in ASSET_TUNE)
- Overlays: BTC {'um': {'so_style': 'geometric', 'interval': '1h', 'sl_from_liq': False, 'sl_loss': 0.9}}, ETH {'coinm': {'peak_skip_pct': 0.15}}, DOGE {'peak_skip_pct': 0.15}, SOL {'so_reclaim': False}
- Compare: each overlay book is also run on the same baseline in this report
- Hard SL: off
- Stale bag: flatten if still ≥40% below average after 180d (ETH 4.6k→2.4k). Flatten then re-enter lower (skip ema55 / 7d-top until the next fill).
- Give-up: off
- Peak brake (global): off — per-coin peak_skip is in ASSET_TUNE / Setup column
- Possible liq = SL fired and holding that basket would have liquidated before +5% TP
- SL cut TP = stop fired and that basket would have hit TP if held
- Idle = USDT (USD-M) or coin not in the trade. It does not change if the open basket moves.
- Open basket = isolated pocket (margin + uPnL) at last close. At price P: open USD ≈ Open USD + qty × (P − last close).
- Wallet = Idle + Open. Not a taker flatten.
- Trades = Cost B closed baskets (TP, SL, emergency). Open MTM is not a trade

## Overlay vs baseline (Cost B wallet)

| Venue | Asset | Overlay | Baseline wallet | Overlay wallet | Δ |
|---|---|---|---:|---:|---:|
| USD-M | BTC | so_style=geometric, interval=1h, sl=clip, SL90 | $14 | $18 | $+4 |
| USD-M | DOGE | peak_skip_pct=15% | $16 | $35,483 | $+35,467 |
| USD-M | SOL | so_reclaim=off | $20 | $27 | $+7 |
| Coin-M | ETH | peak_skip_pct=15% | $3 | $5,992 | $+5,990 |
| Coin-M | DOGE | peak_skip_pct=15% | $2 | $11,395 | $+11,392 |
| Coin-M | SOL | so_reclaim=off | $1 | $2 | $+1 |

## USD-M (USDT)

| Asset | Setup | Start | Idle | Open basket | Wallet | Trades | SL | Possible liq | SL cut TP |
|---|---|---|---:|---|---:|---:|---:|---:|
| BTC | baseline | $10,000 | $14 | — | $14 | 19 | 5 | 5 | 0 |
| BTC | so_style=geometric, interval=1h, sl=clip, SL90 | $10,000 | $18 | — | $18 | 17 | 5 | 5 | 0 |
| ETH | baseline | $10,000 | $33 | — | $33 | 11 | 4 | 4 | 0 |
| DOGE | baseline | $10,000 | $16 | — | $16 | 141 | 31 | 31 | 0 |
| DOGE | peak_skip_pct=15% | $10,000 | $35,483 | — | $35,483 | 11 | 1 | 1 | 0 |
| SOL | baseline | $10,000 | $20 | — | $20 | 28 | 6 | 5 | 1 |
| SOL | so_reclaim=off | $10,000 | $27 | — | $27 | 26 | 7 | 6 | 1 |

## Coin-M (coin wallet)

| Asset | Setup | Start | Idle | Open basket | Wallet | Trades | SL | Possible liq | SL cut TP |
|---|---|---|---:|---|---:|---:|---:|---:|---:|
| BTC | baseline | 0.2276 BTC ($10,000) | 0.0002 BTC ($12) | — | $12 | 20 | 6 | 6 | 0 |
| ETH | baseline | 4.501 ETH ($10,000) | 0.001 ETH ($3) | — | $3 | 42 | 10 | 9 | 1 |
| ETH | peak_skip_pct=15% | 4.501 ETH ($10,000) | 2.368 ETH ($5,992) | — | $5,992 | 3 | 1 | 1 | 0 |
| DOGE | baseline | 127,779 DOGE ($10,000) | 27 DOGE ($2) | — | $2 | 151 | 38 | 36 | 2 |
| DOGE | peak_skip_pct=15% | 127,779 DOGE ($10,000) | 134,101 DOGE ($11,395) | — | $11,395 | 18 | 4 | 3 | 1 |
| SOL | baseline | 111.80 SOL ($10,000) | 0.01 SOL ($1) | — | $1 | 32 | 8 | 8 | 0 |
| SOL | so_reclaim=off | 111.80 SOL ($10,000) | 0.02 SOL ($2) | — | $2 | 35 | 10 | 10 | 0 |
