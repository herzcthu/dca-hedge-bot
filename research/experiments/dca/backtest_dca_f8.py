#!/usr/bin/env python3
"""Product F8: F6 rules with $20,000 start and a matching $20k clip.

1% MR, SL80 vs the $20k clip. Does not compound. F6/F7 are not retuned.
Not a scalp; do not wire into main.py.
"""

from experiments.dca.backtest_dca import run_suite

START_20K = 20_000.0


def main() -> None:
    run_suite(
        mr_cap=0.01,
        product="F8_dca_fixed20k_sl80",
        results_dir="results_dca_f8",
        tag="F8",
        memo_name="RESULTS_DCA_F8.md",
        equity_stop_frac=0.20,
        size_equity=START_20K,
        start_equity=START_20K,
    )


if __name__ == "__main__":
    main()
