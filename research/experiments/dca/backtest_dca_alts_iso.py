#!/usr/bin/env python3
"""ETH/DOGE/SOL F6+G1 twins with isolated margin (not cross)."""

from experiments.dca.backtest_dca_alts import main


if __name__ == "__main__":
    main(isolated=True, results_root="results_dca_alts_iso")
