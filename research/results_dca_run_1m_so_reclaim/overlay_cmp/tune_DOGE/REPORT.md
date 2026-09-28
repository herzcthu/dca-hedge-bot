# Isolated DCA — start vs end

- Run: 2026-09-14 02:46 UTC
- Last bar: 2026-09-14 02:01:59.999000+00:00
- Isolated wallet / clip: $10,000 each
- Tune coin: DOGE  sweep=4
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
| USD-M | DOGE | peak_skip_pct=15%, lookback=30d | $22,525 | $25,308 | $+2,784 |
| USD-M | DOGE | peak_skip_pct=15%, lookback=30d, SL95, tp_pct=8% | $22,525 | $50,728 | $+28,204 |
| USD-M | DOGE | peak_skip_pct=15%, lookback=180d | $22,525 | $44,741 | $+22,216 |
| USD-M | DOGE | peak_skip_pct=15%, lookback=180d, SL95, tp_pct=8% | $22,525 | $83,507 | $+60,983 |

## Ranked USD-M

| Rank | Setup | Wallet | vs best | Trades | SL |
|---:|---|---:|---:|---:|---:|
| 1 | peak_skip_pct=15%, lookback=180d, SL95, tp_pct=8% | $83,507 | — | 42 | 7 |
| 2 | peak_skip_pct=15%, lookback=30d, SL95, tp_pct=8% | $50,728 | $-32,779 | 55 | 14 |
| 3 | peak_skip_pct=15%, lookback=180d | $44,741 | $-38,767 | 51 | 7 |
| 4 | peak_skip_pct=15%, lookback=30d | $25,308 | $-58,199 | 72 | 13 |
| 5 | baseline | $22,525 | $-60,983 | 44 | 8 |

## USD-M (USDT)

| Asset | Setup | Start | Idle | Open basket | Wallet | Trades | SL | Possible liq | SL cut TP |
|---|---|---|---:|---|---:|---:|---:|---:|
| DOGE | baseline | $10,000 | $22,525 | — | $22,525 | 44 | 8 | 8 | 0 |
| DOGE | peak_skip_pct=15%, lookback=30d | $10,000 | $19,536 | 1,166,275 DOGE ($5,772) | $25,308 | 72 | 13 | 13 | 0 |
| DOGE | peak_skip_pct=15%, lookback=30d, SL95, tp_pct=8% | $10,000 | $44,956 | 1,166,275 DOGE ($5,772) | $50,728 | 55 | 14 | 14 | 0 |
| DOGE | peak_skip_pct=15%, lookback=180d | $10,000 | $38,968 | 1,166,275 DOGE ($5,772) | $44,741 | 51 | 7 | 6 | 1 |
| DOGE | peak_skip_pct=15%, lookback=180d, SL95, tp_pct=8% | $10,000 | $77,735 | 1,166,275 DOGE ($5,772) | $83,507 | 42 | 7 | 7 | 0 |
