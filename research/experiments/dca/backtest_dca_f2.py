#!/usr/bin/env python3
"""Product F2: same leveraged DCA as F1, frozen at a 1% MR cap.

F1 (3% MR) is not retuned. This is a new spec. Still not a scalp; do not
wire into main.py.
"""

from experiments.dca.backtest_dca import run_suite


def main() -> None:
    run_suite(
        mr_cap=0.01,
        product="F2_dca_mr1pct",
        results_dir="results_dca_f2",
        tag="F2",
        memo_name="RESULTS_DCA_F2.md",
    )


if __name__ == "__main__":
    main()
