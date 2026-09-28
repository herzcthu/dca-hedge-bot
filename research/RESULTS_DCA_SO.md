# Technical safety orders (isolated DCA)

Not a scalp. Do not wire into `main.py`. F6 geometric artifacts are unchanged
(`so_style=geometric` remains the default on F6/G1 suites).

## Frozen spec

Same as isolated F6 otherwise: 1h limits, 1 base + max 5 SOs, one fill per hour,
same-bar SO beats TP, 1% MR cap, SL80 vs $10k clip, Cost B decision model.

**SO change only:**

- No 1% × 1.15^n ladder and no `max(geo, tech)`.
- Arm an SO only if EMA21 or 12h swing support is at least 0.6% below the last fill.
- Do not arm if close ≤ EMA55 or close has taken out 12h support.
- Size = leftover 1% MR notional × 0.9 / remaining SO slots.

Runner: `experiments/dca/run_isolated.py` with `SO_STYLE = SO_TECHNICAL`.

## Isolated flatten-today (Cost B)

Start $10,000 each. Last bar 2026-09-10.

| Venue | Asset | Geometric SO (prior) | Technical SO |
|---|---|---:|---:|
| USD-M | BTC | $20,903 | **$14,837** |
| USD-M | ETH | $428 | **$483** |
| USD-M | DOGE | $202 | **$293** |
| USD-M | SOL | $6,506 | **$928** |
| Coin-M | BTC | 0.3379 BTC ($26,435) | **0.2872 BTC ($22,406)** |
| Coin-M | ETH / DOGE / SOL | $0 | **$0** |

USD-M BTC Cost B: 124 baskets, mean 1.20 SOs, 59% of baskets added at least once,
122 TP / 1 SL. Net round-trip P&L +$8,360 vs a higher geometric leftover.

Alts still fail. BTC is weaker than the geometric ladder on this path. Not a live candidate.
