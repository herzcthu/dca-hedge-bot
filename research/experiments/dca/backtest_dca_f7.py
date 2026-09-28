#!/usr/bin/env python3
"""Product F7: F6 plus a one-step clip upgrade at 2× wallet.

1% MR, SL80 vs the clip used for that basket. Plan from $10,000 until mark
wallet is at least $20,000, then plan from $20,000. Clip is re-checked only
when arming a new basket (not sticky after a drop). F6 is not retuned.
Not a scalp; do not wire into main.py.
"""

from experiments.dca.backtest_dca import START_EQUITY, run_suite


def main() -> None:
    run_suite(
        mr_cap=0.01,
        product="F7_dca_step20k_sl80",
        results_dir="results_dca_f7",
        tag="F7",
        memo_name="RESULTS_DCA_F7.md",
        equity_stop_frac=0.20,
        size_equity=START_EQUITY,
        size_step_mult=2.0,
    )


if __name__ == "__main__":
    main()
