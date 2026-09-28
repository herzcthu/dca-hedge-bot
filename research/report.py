#!/usr/bin/env python3
"""Reporting utilities for adaptive scalp backtest results."""

from __future__ import annotations

import os
from math import sqrt

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import RESULTS_DIR, START_EQUITY


SPLITS = {
    "train": (pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2025-07-01", tz="UTC")),
    "validate": (pd.Timestamp("2025-07-01", tz="UTC"), pd.Timestamp("2026-03-01", tz="UTC")),
    "holdout": (pd.Timestamp("2026-03-01", tz="UTC"), pd.Timestamp.max.tz_localize("UTC")),
}


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    return abs(float((equity / equity.cummax() - 1.0).min()))


def max_consecutive_losses(pnls: pd.Series) -> int:
    longest = current = 0
    for pnl in pnls:
        if pnl <= 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def summarize_split(trades: pd.DataFrame, equity: pd.DataFrame, split_name: str, skipped: pd.DataFrame) -> dict:
    start, end = SPLITS[split_name]
    split_trades = trades[(trades.entry_time >= start) & (trades.entry_time < end)].copy() if not trades.empty else trades.copy()
    split_equity = equity[(equity.time >= start) & (equity.time < end)].copy() if not equity.empty else equity.copy()
    split_skipped = skipped[(skipped.time >= start) & (skipped.time < end)].copy() if not skipped.empty and "time" in skipped else skipped.copy()
    if split_trades.empty:
        return {"split": split_name, "net_profit_pct": 0.0, "profit_factor": 0.0, "win_rate": 0.0, "trades": 0,
                "trades_per_week": 0.0, "avg_win_pct": 0.0, "avg_loss_pct": 0.0, "payoff_ratio": 0.0,
                "max_drawdown_pct": max_drawdown(split_equity.equity) * 100 if not split_equity.empty else 0.0,
                "max_consecutive_losses": 0, "time_in_market_pct": 0.0, "avg_hold_bars": 0.0, "avg_hold_minutes": 0.0,
                "expectancy_usdt": 0.0, "expectancy_pct": 0.0, "sharpe_5m_ann": 0.0, "worst_month_pct": 0.0,
                "fees_pct_start_equity": 0.0, "unsizable_skip_pct": 0.0, "long_pf": 0.0, "long_wr": 0.0,
                "short_pf": 0.0, "short_wr": 0.0}
    wins = split_trades[split_trades.pnl_net > 0]
    losses = split_trades[split_trades.pnl_net <= 0]
    gross_wins = wins.pnl_net.sum()
    gross_losses = abs(losses.pnl_net.sum())
    pf = gross_wins / gross_losses if gross_losses > 0 else np.inf
    avg_win_pct = wins.pnl_net_pct.mean() * 100 if not wins.empty else 0.0
    avg_loss_pct = losses.pnl_net_pct.mean() * 100 if not losses.empty else 0.0
    payoff = avg_win_pct / abs(avg_loss_pct) if avg_loss_pct else np.inf
    days = max((min(end, split_trades.exit_time.max()) - split_trades.entry_time.min()).days + 1, 1)
    weekly = len(split_trades) / (days / 7)
    total_hold_minutes = split_trades.hold_bars.sum() * 5
    time_in_market = total_hold_minutes / (days * 24 * 60) * 100
    split_trades["month"] = split_trades.entry_time.dt.to_period("M").astype(str)
    monthly = split_trades.groupby("month").pnl_net.sum() / START_EQUITY * 100
    worst_month = monthly.min() if not monthly.empty else 0.0
    returns = split_equity.equity.pct_change().fillna(0) if not split_equity.empty else pd.Series(dtype=float)
    sharpe = returns.mean() / returns.std(ddof=0) * sqrt(365 * 24 * 12) if len(returns) > 2 and returns.std(ddof=0) > 0 else 0.0
    total_signals = split_trades.total_signals.max() if "total_signals" in split_trades else len(split_trades)
    unsizable = split_trades.unsizable_signals.max() if "unsizable_signals" in split_trades else 0
    if not split_skipped.empty and "reason" in split_skipped:
        unsizable += int((split_skipped.reason == "unsizable").sum())
    unsizable_skip_pct = unsizable / max(total_signals + len(split_skipped), 1) * 100

    def side_stats(side: str) -> tuple[float, float]:
        rows = split_trades[split_trades.side == side]
        if rows.empty:
            return 0.0, 0.0
        side_wins = rows[rows.pnl_net > 0].pnl_net.sum()
        side_losses = abs(rows[rows.pnl_net <= 0].pnl_net.sum())
        side_pf = side_wins / side_losses if side_losses > 0 else np.inf
        side_wr = (rows.pnl_net > 0).mean() * 100
        return side_pf, side_wr

    long_pf, long_wr = side_stats("long")
    short_pf, short_wr = side_stats("short")
    net_profit_pct = (split_trades.pnl_net.sum() / START_EQUITY) * 100
    return {
        "split": split_name, "net_profit_pct": net_profit_pct, "profit_factor": pf,
        "win_rate": (split_trades.pnl_net > 0).mean() * 100, "trades": len(split_trades),
        "trades_per_week": weekly, "avg_win_pct": avg_win_pct, "avg_loss_pct": avg_loss_pct,
        "payoff_ratio": payoff, "max_drawdown_pct": max_drawdown(split_equity.equity) * 100 if not split_equity.empty else 0.0,
        "max_consecutive_losses": max_consecutive_losses(split_trades.pnl_net), "time_in_market_pct": time_in_market,
        "avg_hold_bars": split_trades.hold_bars.mean(), "avg_hold_minutes": split_trades.hold_bars.mean() * 5,
        "expectancy_usdt": split_trades.pnl_net.mean(), "expectancy_pct": split_trades.pnl_net_pct.mean() * 100,
        "sharpe_5m_ann": sharpe, "worst_month_pct": worst_month,
        "fees_pct_start_equity": split_trades.fees.sum() / START_EQUITY * 100,
        "unsizable_skip_pct": unsizable_skip_pct, "long_pf": long_pf, "long_wr": long_wr,
        "short_pf": short_pf, "short_wr": short_wr,
    }


def rolling_90d_pf(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["window_start", "window_end", "profit_factor"])
    rows = []
    start = trades.entry_time.min().floor("D")
    end = trades.entry_time.max().floor("D")
    while start + pd.Timedelta(days=90) <= end:
        stop = start + pd.Timedelta(days=90)
        window = trades[(trades.entry_time >= start) & (trades.entry_time < stop)]
        wins = window[window.pnl_net > 0].pnl_net.sum()
        losses = abs(window[window.pnl_net <= 0].pnl_net.sum())
        rows.append({"window_start": start, "window_end": stop, "profit_factor": wins / losses if losses else np.inf})
        start += pd.Timedelta(days=30)
    return pd.DataFrame(rows)


def save_outputs(summary: pd.DataFrame, trades: pd.DataFrame, equity: pd.DataFrame) -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    summary.to_csv(os.path.join(RESULTS_DIR, "summary.csv"), index=False)
    trades.to_csv(os.path.join(RESULTS_DIR, "trades.csv"), index=False)
    v3_equity = equity[equity.variant == "V3_combined"] if "variant" in equity else equity
    v3_equity.to_csv(os.path.join(RESULTS_DIR, "equity_V3.csv"), index=False)
    if not trades.empty:
        monthly = trades.assign(month=trades.entry_time.dt.to_period("M").astype(str)).groupby(["variant", "fill_model", "cost_model", "month"]).pnl_net.sum().reset_index()
        monthly["net_pct"] = monthly.pnl_net / START_EQUITY * 100
        monthly.to_csv(os.path.join(RESULTS_DIR, "monthly_returns.csv"), index=False)
    plot_results(trades, equity)


def plot_results(trades: pd.DataFrame, equity: pd.DataFrame) -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    if equity.empty:
        return
    fig, ax = plt.subplots(figsize=(12, 6))
    for key, grp in equity.groupby(["variant", "fill_model", "cost_model"]):
        if key[2] == "A_maker_maker":
            ax.plot(grp.time, grp.equity, label="/".join(key), alpha=0.75)
    ax.set_title("Equity curves - cost model A")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(RESULTS_DIR, "equity_curves.png"))
    plt.close(fig)

    v3 = equity[(equity.variant == "V3_combined") & (equity.fill_model == "F-OPEN") & (equity.cost_model == "B_realistic_mix")]
    if not v3.empty:
        dd = v3.equity / v3.equity.cummax() - 1
        fig, ax = plt.subplots(figsize=(12, 4))
        ax.plot(v3.time, dd * 100)
        ax.set_title("V3 F-OPEN cost B underwater drawdown")
        fig.tight_layout()
        fig.savefig(os.path.join(RESULTS_DIR, "underwater_V3.png"))
        plt.close(fig)

    v3_trades = trades[(trades.variant == "V3_combined") & (trades.fill_model == "F-OPEN") & (trades.cost_model == "B_realistic_mix")]
    if not v3_trades.empty:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.hist(v3_trades.pnl_net_pct * 100, bins=60)
        ax.set_title("V3 F-OPEN cost B trade PnL histogram")
        fig.tight_layout()
        fig.savefig(os.path.join(RESULTS_DIR, "pnl_histogram_V3.png"))
        plt.close(fig)
