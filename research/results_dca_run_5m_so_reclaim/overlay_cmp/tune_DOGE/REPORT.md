# Isolated DCA — start vs end

- Run: 2026-09-13 00:59 UTC
- Last bar: 2026-09-12 11:19:59.999000+00:00
- Isolated wallet / clip: $10,000 each
- Tune coin: DOGE  sweep=4
- MR cap: 10%   SL: 90% of the drop from avg down to current liq (always above liq)
- Safety orders: range (7d range rungs; freeze 7d low at first fill; no SO if 7d low expands >2% or 12h support breaks; next SO only after close reclaims 21h EMA); max 10 SOs
- Bar: 5m (one fill per bar; EMA/swing still 21h / 55h / 12h)
- Entry TTL: cancel unfilled base after 1h; sit out that bar (matches live DCA_ENTRY_TTL_SEC / ghost-GTC cancel). Safety orders keep working.
- Take-profit: 5% from average entry (baseline; per-coin overlay in ASSET_TUNE)
- Overlays: DOGE {'um': {'peak_skip_pct': 0.15, 'peak_lookback_days': 180, 'sl_loss': 0.95, 'tp_pct': 0.08}, 'coinm': {'peak_skip_pct': 0.15, 'peak_lookback_days': 30}}
- Compare: each overlay book is also run on the same baseline in this report
- Hard SL: off
- Stale bag: flatten if still ≥40% below average after 180d (ETH 4.6k→2.4k). Flatten then re-enter lower (skip ema55 / 7d-top until the next fill).
- Give-up: off
- Peak brake: no new basket while wallet is ≥15% under the 90d rolling marked-wallet high
- After-SL brake: only after a ≥15% wallet hole (same as peak-skip). sl_cd / sl_high_reclaim hold the brake; after_sl_clip probes at that fraction until it clears. Small SLs in a hot book stay full clip.
- Price-dd skip (sweep): no new basket while close is ≥X under the rolling price high (completed bars).
- Dump gate (sweep): after SL, no new basket until close recaptures the frozen N-day price high at the stop.
- After-TP gate (sweep): after a TP, no new basket if the 7d low expands >2% (dump) or close gives back after_tp_giveback_pct (reversal).
- Possible liq = SL fired and holding that basket would have liquidated before +5% TP
- SL cut TP = stop fired and that basket would have hit TP if held
- Idle = USDT (USD-M) or coin not in the trade. It does not change if the open basket moves.
- Open basket = isolated pocket (margin + uPnL) at last close. At price P: open USD ≈ Open USD + qty × (P − last close).
- Wallet = Idle + Open. Not a taker flatten.
- Trades = Cost B closed baskets (TP, SL, emergency). Open MTM is not a trade

## Overlay vs baseline (Cost B wallet)

| Venue | Asset | Overlay | Baseline wallet | Overlay wallet | Δ |
|---|---|---|---:|---:|---:|
| USD-M | DOGE | peak_skip_pct=15%, lookback=30d | $33,316 | $51,196 | $+17,881 |
| USD-M | DOGE | peak_skip_pct=15%, lookback=30d, SL95, tp_pct=8% | $33,316 | $31,635 | $-1,681 |
| USD-M | DOGE | peak_skip_pct=15%, lookback=180d | $33,316 | $59,041 | $+25,725 |
| USD-M | DOGE | peak_skip_pct=15%, lookback=180d, SL95, tp_pct=8% | $33,316 | $70,413 | $+37,097 |
| Coin-M | DOGE | peak_skip_pct=15%, lookback=30d | $20,574 | $38,831 | $+18,258 |
| Coin-M | DOGE | peak_skip_pct=15%, lookback=30d, SL95, tp_pct=8% | $20,574 | $37,723 | $+17,149 |
| Coin-M | DOGE | peak_skip_pct=15%, lookback=180d | $20,574 | $14,899 | $-5,674 |
| Coin-M | DOGE | peak_skip_pct=15%, lookback=180d, SL95, tp_pct=8% | $20,574 | $4,783 | $-15,790 |

## Ranked USD-M

| Rank | Setup | Wallet | vs best | Trades | SL |
|---:|---|---:|---:|---:|---:|
| 1 | peak_skip_pct=15%, lookback=180d, SL95, tp_pct=8% | $70,413 | — | 46 | 9 |
| 2 | peak_skip_pct=15%, lookback=180d | $59,041 | $-11,372 | 69 | 10 |
| 3 | peak_skip_pct=15%, lookback=30d | $51,196 | $-19,217 | 89 | 15 |
| 4 | baseline | $33,316 | $-37,097 | 51 | 8 |
| 5 | peak_skip_pct=15%, lookback=30d, SL95, tp_pct=8% | $31,635 | $-38,778 | 67 | 18 |

## Ranked Coin-M

| Rank | Setup | Wallet | vs best | Trades | SL |
|---:|---|---:|---:|---:|---:|
| 1 | peak_skip_pct=15%, lookback=30d | $38,831 | — | 81 | 12 |
| 2 | peak_skip_pct=15%, lookback=30d, SL95, tp_pct=8% | $37,723 | $-1,109 | 53 | 13 |
| 3 | baseline | $20,574 | $-18,258 | 43 | 7 |
| 4 | peak_skip_pct=15%, lookback=180d | $14,899 | $-23,932 | 27 | 5 |
| 5 | peak_skip_pct=15%, lookback=180d, SL95, tp_pct=8% | $4,783 | $-34,048 | 14 | 5 |

## USD-M (USDT)

| Asset | Setup | Start | Idle | Open basket | Wallet | Trades | SL | Possible liq | SL cut TP |
|---|---|---|---:|---|---:|---:|---:|---:|
| DOGE | baseline | $10,000 | $25,914 | 823,723 DOGE ($7,401) | $33,316 | 51 | 8 | 8 | 0 |
| DOGE | peak_skip_pct=15%, lookback=30d | $10,000 | $43,795 | 823,723 DOGE ($7,401) | $51,196 | 89 | 15 | 15 | 0 |
| DOGE | peak_skip_pct=15%, lookback=30d, SL95, tp_pct=8% | $10,000 | $26,944 | 179,113 DOGE ($4,691) | $31,635 | 67 | 18 | 18 | 0 |
| DOGE | peak_skip_pct=15%, lookback=180d | $10,000 | $59,041 | — | $59,041 | 69 | 10 | 10 | 0 |
| DOGE | peak_skip_pct=15%, lookback=180d, SL95, tp_pct=8% | $10,000 | $63,012 | 823,723 DOGE ($7,401) | $70,413 | 46 | 9 | 9 | 0 |

## Coin-M (coin wallet)

| Asset | Setup | Start | Idle | Open basket | Wallet | Trades | SL | Possible liq | SL cut TP |
|---|---|---|---:|---|---:|---:|---:|---:|---:|
| DOGE | baseline | 127,779 DOGE ($10,000) | 159,986 DOGE ($13,594) | 82,142 DOGE ($6,980) | $20,574 | 43 | 7 | 6 | 1 |
| DOGE | peak_skip_pct=15%, lookback=30d | 127,779 DOGE ($10,000) | 374,861 DOGE ($31,852) | 82,142 DOGE ($6,980) | $38,831 | 81 | 12 | 11 | 1 |
| DOGE | peak_skip_pct=15%, lookback=30d, SL95, tp_pct=8% | 127,779 DOGE ($10,000) | 361,812 DOGE ($30,743) | 82,142 DOGE ($6,980) | $37,723 | 53 | 13 | 11 | 2 |
| DOGE | peak_skip_pct=15%, lookback=180d | 127,779 DOGE ($10,000) | 175,345 DOGE ($14,899) | — | $14,899 | 27 | 5 | 4 | 1 |
| DOGE | peak_skip_pct=15%, lookback=180d, SL95, tp_pct=8% | 127,779 DOGE ($10,000) | 56,296 DOGE ($4,783) | — | $4,783 | 14 | 5 | 3 | 2 |
