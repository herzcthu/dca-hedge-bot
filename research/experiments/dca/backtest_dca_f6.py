#!/usr/bin/env python3
"""Product F6: 1% MR + SL80 with entry size frozen to the original $10,000.

Does not compound basket notional when the wallet grows. Live 1% MR cap can
still shrink or skip adds if the current wallet cannot support the fixed clip.
F1–F5 are not retuned. Not a scalp; do not wire into main.py.
"""

from experiments.dca.backtest_dca import START_EQUITY, run_suite


def main() -> None:
    run_suite(
        mr_cap=0.01,
        product="F6_dca_fixed10k_sl80",
        results_dir="results_dca_f6",
        tag="F6",
        memo_name="RESULTS_DCA_F6.md",
        equity_stop_frac=0.20,
        size_equity=START_EQUITY,
    )


if __name__ == "__main__":
    main()
