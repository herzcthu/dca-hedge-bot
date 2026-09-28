# Range-anchored DCA SOs (isolated)

Not a scalp. Do not wire into `main.py`. F6 geometric default is unchanged.

## Frozen spec

Same isolated runner otherwise (clip, MR, SL-from-liq, TP, 15m or 1h).

- **No ATH entry:** skip a new basket if close is in the top 25% of the prior **7d** high–low, or if the 7d low is **<6%** under close. Still require close > EMA55 and the 12h resist buffer.
- **SOs:** next limit is `1 / remaining_slots` of the gap from last fill down to the current 7d low. Do not arm if that rung is <0.6% below last fill (too tight). Max 5. Size = leftover MR room / slots. One fill per bar.

## Isolated Cost B (this run)

15m, MR 0.4% (~1×), TP 5%, SL-from-liq 90%. Wallet = idle + open mark (not flatten).

USD-M: BTC **$12,161** (21 trades) · ETH **$12,543** (25) · DOGE **$8,770** (44) · SOL **$10,812** (38).

ETH no longer sits on a near-ATH 1.9 ETH bag at $4.6k average with idle $2.8k; idle is **$5,209** and the open pocket is **$7,334**. Geometric F6 default is unchanged (`SO_STYLE=geometric`).
