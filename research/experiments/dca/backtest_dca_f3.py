#!/usr/bin/env python3
"""Product F3: F2 DCA (1% MR) plus a 50% equity stop on each basket.

A 50% BTC-price stop sits beyond F2 liquidation (~41% from average), so this
stop is: flatten taker when wallet <= 50% of equity at the basket's first fill.
F1/F2 are not retuned. Not a scalp; do not wire into main.py.
"""

from experiments.dca.backtest_dca import run_suite


def main() -> None:
    run_suite(
        mr_cap=0.01,
        product="F3_dca_sl50",
        results_dir="results_dca_f3",
        tag="F3",
        memo_name="RESULTS_DCA_F3.md",
        equity_stop_frac=0.50,
    )


if __name__ == "__main__":
    main()
