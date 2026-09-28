#!/usr/bin/env python3
"""SL-loss sensitivity for the F3 DCA engine. Does not retune F3.

equity_stop_frac is remaining wallet vs basket-start equity.
User SL20 (lose 20%) => frac 0.80; SL50 => 0.50; SL90 (lose 90%) => 0.10.
"""

from __future__ import annotations

import os

import pandas as pd

from experiments.dca.backtest_dca import COST_B, prepare_data, run_dca


RESULTS_DIR = "results_dca_sl_sweep"
# (label, remaining-wallet fraction)
SWEEP = [
    ("SL20", 0.80),
    ("SL30", 0.70),
    ("SL50", 0.50),
    ("SL80", 0.20),
    ("SL90", 0.10),
]


def main() -> None:
    df = prepare_data()
    rows = []
    for label, frac in SWEEP:
        trades, equity, _events, remaining = run_dca(df, COST_B, mr_cap=0.01, equity_stop_frac=frac)
        sl = trades[trades.exit_reason == "SL50"] if not trades.empty else trades
        tp = trades[trades.exit_reason == "TP"] if not trades.empty else trades
        liq = trades[trades.exit_reason == "LIQUIDATION"] if not trades.empty else trades
        rows.append({
            "stop": label,
            "keep_frac": frac,
            "loss_allowed_pct": (1.0 - frac) * 100,
            "baskets": len(trades),
            "tp_n": len(tp),
            "tp_usdt": float(tp.pnl_net.sum()) if not tp.empty else 0.0,
            "sl_n": len(sl),
            "sl_usdt": float(sl.pnl_net.sum()) if not sl.empty else 0.0,
            "liq_n": len(liq),
            "remaining_mark_usdt": remaining["remaining_mark_usdt"],
            "if_flatten_today_usdt": remaining["if_flatten_today_usdt"],
            "as_of": remaining["as_of"],
            "in_position": remaining["in_position"],
            "liquidated": remaining["liquidated"],
        })
        print(f"{label} remaining ${remaining['if_flatten_today_usdt']:.2f} sl_n={len(sl)} liq={len(liq)}", flush=True)
    out = pd.DataFrame(rows)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    out.to_csv(os.path.join(RESULTS_DIR, "summary.csv"), index=False)
    print("\nSWEEP")
    print(out.to_string(index=False, float_format=lambda v: f"{v:.2f}"))


if __name__ == "__main__":
    main()
