# Experiment E1: Sparse 15m Rejection Fade

Frozen BTCUSDT perpetual scalp. Not a retune of the killed 5m adaptive,
impulse-fade, HTF pullback, grid, or daily Donchian systems.

## Frozen spec

- Signal on **completed 15m** bars only. Fill the **next 15m open**.
- Prior range: 48 completed bars (12h), excluding the signal bar.
- Event bar must have range ≥ 1.5 × ATR(14).
- Expansion: signal low (high) beyond the prior range by ≥ 0.75 × ATR(14).
- Rejection: close in the opposite 35% of the bar (close location ≥ 0.65 for longs, ≤ 0.35 for shorts).
- Fade the expansion (long dumps, short spikes).
- Stop: signal-bar extreme ± 5 bps. Skip if stop distance < 0.25% or > 1.2%.
- Target: 2R. Max hold: 4 bars (60 minutes). Same-bar SL/TP: stop wins.
- Cost B is the decision model. Funding placeholder −0.01% per 00:00/08:00/16:00 UTC crossing.
- Risk 0.35% of equity; max 5× leverage; 2% daily halt; 2 trades/day; 4-bar cooldown after 2 losses.
- Circuit breaker: Cost A full-sample trades 0 or > 400 → KILL (not sparse / not an event).

## Run

```bash
docker compose build
docker compose run --rm btc-eth-hedge python -m experiments.e1.backtest_e1
```

Outputs: `results_e1/` and `RESULTS_E1.md`.
