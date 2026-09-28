#!/usr/bin/env python3
"""Product F4: 0.5% MR cap + SL80 (flatten at 20% of basket-start wallet).

F1–F3 are not retuned. 0.5% MR / 0.4% MMR is ~1.25× notional; SL80 is an
~80% wallet loss on that basket (~64% price drop if fully loaded). Not a
scalp; do not wire into main.py.
"""

from experiments.dca.backtest_dca import run_suite


def main() -> None:
    run_suite(
        mr_cap=0.005,
        product="F4_dca_mr05_sl80",
        results_dir="results_dca_f4",
        tag="F4",
        memo_name="RESULTS_DCA_F4.md",
        equity_stop_frac=0.20,
    )


if __name__ == "__main__":
    main()
