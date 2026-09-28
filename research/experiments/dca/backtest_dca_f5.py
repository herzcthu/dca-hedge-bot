#!/usr/bin/env python3
"""Product F5: 2% MR cap + SL80 (flatten at 20% of basket-start wallet).

F1–F4 are not retuned. 2% MR / 0.4% MMR is ~5× notional; liquidation is only
~20% further drop with UPNL≈0, so SL80 (~16% price if fully loaded) should
usually fire first. Not a scalp; do not wire into main.py.
"""

from experiments.dca.backtest_dca import run_suite


def main() -> None:
    run_suite(
        mr_cap=0.02,
        product="F5_dca_mr2_sl80",
        results_dir="results_dca_f5",
        tag="F5",
        memo_name="RESULTS_DCA_F5.md",
        equity_stop_frac=0.20,
    )


if __name__ == "__main__":
    main()
