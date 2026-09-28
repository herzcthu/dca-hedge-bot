# Isolated DCA — start vs end

- Run: 2026-09-28 01:47 UTC
- Last bar: 2026-09-28 01:36:59.999000+00:00
- Isolated wallet / clip: $10,000 each
- Tune coin: DOGE  sweep=3
- MR cap: 10%   SL: 90% of the drop from avg down to current liq (always above liq)
- Safety orders: range (7d range rungs; freeze 7d low at first fill; no SO if 7d low expands >2% or 12h support breaks; next SO only after close reclaims 21h EMA); max 10 SOs
- Bar: 1m (one fill per bar; EMA/swing still 21h / 55h / 12h)
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
| USD-M | DOGE | peak_skip_pct=15%, lookback=20d | $24,425 | $41 | $-24,384 |
| USD-M | DOGE | peak_skip_pct=15%, lookback=20d, SL95, tp_pct=8% | $24,425 | $28,801 | $+4,377 |
| USD-M | DOGE | peak_skip_pct=15%, lookback=30d | $24,425 | $20,802 | $-3,623 |
| USD-M | DOGE | peak_skip_pct=15%, lookback=180d, SL95, tp_pct=8% | $24,425 | $82,233 | $+57,808 |

## Ranked USD-M

| Rank | Setup | Wallet | vs best | Trades | SL |
|---:|---|---:|---:|---:|---:|
| 1 | peak_skip_pct=15%, lookback=180d, SL95, tp_pct=8% | $82,233 | — | 44 | 8 |
| 2 | peak_skip_pct=15%, lookback=20d, SL95, tp_pct=8% | $28,801 | $-53,432 | 65 | 19 |
| 3 | baseline | $24,425 | $-57,808 | 46 | 8 |
| 4 | peak_skip_pct=15%, lookback=30d | $20,802 | $-61,431 | 73 | 14 |
| 5 | peak_skip_pct=15%, lookback=20d | $41 | $-82,192 | 76 | 17 |

## USD-M (USDT)

| Asset | Setup | Start | Idle | Open basket | Wallet | Trades | SL | Possible liq | SL cut TP |
|---|---|---|---:|---|---:|---:|---:|---:|
| DOGE | baseline | $10,000 | $14,497 | 416,190 DOGE ($9,927) | $24,425 | 46 | 8 | 8 | 0 |
| DOGE | peak_skip_pct=15%, lookback=20d | $10,000 | $41 | — | $41 | 76 | 17 | 16 | 1 |
| DOGE | peak_skip_pct=15%, lookback=20d, SL95, tp_pct=8% | $10,000 | $28,801 | — | $28,801 | 65 | 19 | 19 | 0 |
| DOGE | peak_skip_pct=15%, lookback=30d | $10,000 | $20,802 | — | $20,802 | 73 | 14 | 14 | 0 |
| DOGE | peak_skip_pct=15%, lookback=180d, SL95, tp_pct=8% | $10,000 | $71,720 | 604,991 DOGE ($10,513) | $82,233 | 44 | 8 | 8 | 0 |
