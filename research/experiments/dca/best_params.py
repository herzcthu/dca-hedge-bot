"""Best Cost B specs already measured, one record per symbol.

Import this instead of copying DOGE's knobs onto BTC or ETH.
Wallet is the ending marked account from $10,000. Research only.
"""

from __future__ import annotations


# Hedge book, USD-M 1m. Grid: memory 30/90/180 × TP 5/8% × SL 90/95%.
# Fixed: clip $10k, MR 10%, range SO max 10, reclaim, peak-skip 15%, stale 40%/180d.
# Source: results_dca_run_1m_so_reclaim/hedge_tune/REPORT.md
# SL 90% and 95% tied on SOL and DOGE because that book never stopped.
HEDGE_1M = {
    "SOLUSDT": {
        "interval": "1m",
        "peak_lookback_days": 90,
        "tp_pct": 0.05,
        "sl_loss": 0.90,
        "sl_from_liq": True,
        "peak_skip_pct": 0.15,
        "wallet": 223_783,
        "above_start": True,
    },
    "DOGEUSDT": {
        "interval": "1m",
        "peak_lookback_days": 180,
        "tp_pct": 0.08,
        "sl_loss": 0.90,
        "sl_from_liq": True,
        "peak_skip_pct": 0.15,
        "wallet": 208_700,
        "above_start": True,
    },
    "BTCUSDT": {
        "interval": "1m",
        "peak_lookback_days": 30,
        "tp_pct": 0.05,
        "sl_loss": 0.90,
        "sl_from_liq": True,
        "peak_skip_pct": 0.15,
        "wallet": 5_463,
        "above_start": False,
    },
    "ETHUSDT": {
        "interval": "1m",
        "peak_lookback_days": 180,
        "tp_pct": 0.05,
        "sl_loss": 0.90,
        "sl_from_liq": True,
        "peak_skip_pct": 0.15,
        "wallet": 45,
        "above_start": False,
    },
}


# Long-only USD-M. Highest saved ending wallet for that symbol.
# These are different books. Do not mix them into the hedge runner.
LONG_ONLY = {
    "BTCUSDT": {
        "interval": "1h",
        "so_style": "geometric",
        "mr_cap": 0.01,
        "tp_pct": 0.02,
        "sl_loss": 0.80,
        "sl_from_liq": False,
        "peak_skip_pct": 0.0,
        "wallet": 20_903,
        "source": "RESULTS_DCA_SO.md",
    },
    "ETHUSDT": {
        "interval": "5m",
        "so_style": "range",
        "mr_cap": 0.01,
        "tp_pct": 0.05,
        "sl_loss": 0.90,
        "sl_from_liq": True,
        "peak_skip_pct": 0.0,
        "entry_ttl_sec": 3600,
        "wallet": 15_745,
        "source": "results_dca_run_5m_ttl/REPORT.md",
    },
    "SOLUSDT": {
        "interval": "5m",
        "so_style": "range",
        "mr_cap": 0.01,
        "tp_pct": 0.05,
        "sl_loss": 0.90,
        "sl_from_liq": True,
        "peak_skip_pct": 0.0,
        "wallet": 25_139,
        "source": "results_dca_run_5m/REPORT.md",
    },
    "DOGEUSDT": {
        "interval": "1m",
        "so_style": "range",
        "so_reclaim": True,
        "mr_cap": 0.10,
        "tp_pct": 0.08,
        "sl_loss": 0.95,
        "sl_from_liq": True,
        "peak_skip_pct": 0.15,
        "peak_lookback_days": 180,
        "wallet": 82_233,
        "source": "results_dca_run_1m_so_reclaim/lookback20/tune_DOGE/REPORT.md",
    },
}


# 15m long-only range book, MR 1%, TP 5%, SL 90% of the path to liquidation.
# Source: results_dca_run/REPORT.md. Not the best wallet for any symbol.
M15_RANGE = {
    "BTCUSDT": {"wallet": 14_800, "peak_wallet": 18_976},
    "ETHUSDT": {"wallet": 15_702, "peak_wallet": 18_967},
    "SOLUSDT": {"wallet": 15_058, "peak_wallet": 20_953},
    "DOGEUSDT": {"wallet": 105, "peak_wallet": 20_953},
}
