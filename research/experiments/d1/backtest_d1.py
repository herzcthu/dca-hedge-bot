#!/usr/bin/env python3
"""Experiment D1: daily Donchian 20/10 BTCUSDT spot long-only backtest."""

from __future__ import annotations

import os
from dataclasses import dataclass
from math import sqrt

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from experiments.d1.data import SYMBOL, load_daily
from experiments.d1.indicators import add_donchian


RESULTS_DIR = "results_d1"
START_EQUITY = 10_000.0
FULL_START = pd.Timestamp("2017-09-01", tz="UTC")
SPLITS = {
    "train": (pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2025-07-01", tz="UTC")),
    "validate": (pd.Timestamp("2025-07-01", tz="UTC"), pd.Timestamp("2026-03-01", tz="UTC")),
    "holdout": (pd.Timestamp("2026-03-01", tz="UTC"), pd.Timestamp.max.tz_localize("UTC")),
}


@dataclass(frozen=True)
class CostModel:
    name: str
    fee_side: float
    slippage_side: float


COST_A = CostModel("A_optimistic_daily", 0.0005, 0.0)
COST_B = CostModel("B_decision_daily", 0.0005, 0.0005)


def _split_for_entry(ts: pd.Timestamp) -> str:
    for name, (start, end) in SPLITS.items():
        if start <= ts < end:
            return name
    return "full_only"


def _slip(price: float, side: str, cost: CostModel) -> float:
    if side == "buy":
        return price * (1 + cost.slippage_side)
    return price * (1 - cost.slippage_side)


def run_d1(df: pd.DataFrame, cost: CostModel) -> tuple[pd.DataFrame, pd.DataFrame]:
    equity = START_EQUITY
    btc = 0.0
    cash = START_EQUITY
    in_pos = False
    entry = 0.0
    entry_time = None
    entry_signal_date = None
    entry_high_20 = np.nan
    entry_equity = START_EQUITY
    rail_flag = False
    trades: list[dict] = []
    equity_rows: list[dict] = []
    rows = list(df.itertuples(index=False))
    i = 20
    while i < len(rows) - 1:
        row = rows[i]
        mark_equity = cash + btc * row.close
        equity_rows.append({"time": row.close_time, "equity": mark_equity, "cost_model": cost.name, "position": btc > 0, "close": row.close})
        if not in_pos:
            if row.open_time >= FULL_START and row.close > row.high_20:
                fill = rows[i + 1]
                entry = _slip(fill.open, "buy", cost)
                fee = cash * cost.fee_side
                btc = (cash - fee) / entry
                cash = 0.0
                in_pos = True
                entry_time = fill.open_time
                entry_signal_date = row.close_time
                entry_high_20 = row.high_20
                entry_equity = mark_equity
                rail_flag = False
                i += 1
                continue
        else:
            rail_hit = row.low <= entry * 0.80
            channel_exit = row.close < row.low_10
            if rail_hit:
                rail_flag = True
            if channel_exit or rail_hit:
                fill = rows[i + 1]
                exit_price = _slip(fill.open, "sell", cost)
                gross = btc * exit_price
                fee = gross * cost.fee_side
                cash = gross - fee
                pnl = cash - entry_equity
                trades.append({
                    "split": _split_for_entry(entry_time), "cost_model": cost.name, "entry_time": entry_time,
                    "signal_date": entry_signal_date, "exit_time": fill.open_time,
                    "entry": entry, "exit": exit_price, "exit_reason": "rail20" if rail_hit else "channel",
                    "pnl_net": pnl, "pnl_net_pct": cash / entry_equity - 1.0,
                    "fees": fee + entry_equity * cost.fee_side, "hold_days": (fill.open_time - entry_time).days,
                    "high_20_at_signal": entry_high_20, "low_10_at_exit": row.low_10,
                })
                equity = cash
                btc = 0.0
                in_pos = False
                i += 1
                continue
        i += 1
    if in_pos:
        final = rows[-1]
        exit_price = _slip(final.close, "sell", cost)
        gross = btc * exit_price
        fee = gross * cost.fee_side
        cash = gross - fee
        trades.append({
            "split": _split_for_entry(entry_time), "cost_model": cost.name, "entry_time": entry_time,
            "signal_date": pd.NaT, "exit_time": final.close_time, "entry": entry, "exit": exit_price,
            "exit_reason": "mtm", "pnl_net": cash - entry_equity, "pnl_net_pct": cash / entry_equity - 1.0,
            "fees": fee + entry_equity * cost.fee_side, "hold_days": (final.close_time - entry_time).days,
            "high_20_at_signal": entry_high_20, "low_10_at_exit": final.low_10,
        })
        equity_rows.append({"time": final.close_time, "equity": cash, "cost_model": cost.name, "position": False, "close": final.close})
    return pd.DataFrame(trades), pd.DataFrame(equity_rows)


def run_bh(df: pd.DataFrame, cost: CostModel, label: str, start: pd.Timestamp, end: pd.Timestamp) -> dict:
    window = df[(df.open_time >= start) & (df.open_time < end)].copy()
    if window.empty:
        return {"split": label, "bh_net_profit_pct": 0.0, "bh_max_dd_pct": 0.0}
    entry = _slip(float(window.iloc[0].open), "buy", cost)
    btc = START_EQUITY * (1 - cost.fee_side) / entry
    equity_curve = btc * window.close
    exit_value = btc * _slip(float(window.iloc[-1].close), "sell", cost) * (1 - cost.fee_side)
    dd = abs(float((equity_curve / equity_curve.cummax() - 1).min())) * 100
    return {"split": label, "bh_net_profit_pct": (exit_value / START_EQUITY - 1) * 100, "bh_max_dd_pct": dd, "bh_time_in_market_pct": 100.0}


def max_dd(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    return abs(float((equity / equity.cummax() - 1).min())) * 100


def summarize(trades: pd.DataFrame, equity: pd.DataFrame, df: pd.DataFrame, cost: CostModel, split: str) -> dict:
    if split == "full":
        start, end = FULL_START, pd.Timestamp.max.tz_localize("UTC")
    else:
        start, end = SPLITS[split]
    t = trades[(trades.entry_time >= start) & (trades.entry_time < end)].copy() if not trades.empty else trades
    e = equity[(equity.time >= start) & (equity.time < end)].copy() if not equity.empty else equity
    bh = run_bh(df, cost, split, start, end)
    if t.empty:
        return {"split": split, "cost_model": cost.name, "n_trades": 0, "net_profit_pct": 0.0, "profit_factor": np.nan, "win_rate": 0.0, "avg_win_pct": 0.0, "avg_loss_pct": 0.0, "payoff_ratio": np.nan, "max_equity_dd_pct": max_dd(e.equity) if not e.empty else 0.0, "time_in_market_pct": e.position.mean() * 100 if not e.empty else 0.0, "avg_hold_days": 0.0, "expectancy_pct": 0.0, "worst_month_pct": 0.0, "fees_pct_start_equity": 0.0, "channel_exits": 0, "rail20_exits": 0, "mtm_exits": 0, **bh}
    wins = t[t.pnl_net > 0]
    losses = t[t.pnl_net <= 0]
    pf = wins.pnl_net.sum() / abs(losses.pnl_net.sum()) if len(t) >= 5 and not losses.empty else np.nan
    start_equity = float(e.iloc[0].equity) if not e.empty else START_EQUITY
    end_equity = float(e.iloc[-1].equity) if not e.empty else start_equity + t.pnl_net.sum()
    month_equity = e.copy()
    month_equity["month"] = month_equity.time.dt.tz_convert(None).dt.to_period("M").astype(str)
    monthly = month_equity.groupby("month").equity.last().pct_change().fillna((month_equity.groupby("month").equity.last().iloc[0] / start_equity) - 1) * 100
    return {
        "split": split, "cost_model": cost.name, "n_trades": len(t), "net_profit_pct": (end_equity / start_equity - 1) * 100,
        "profit_factor": pf, "win_rate": (t.pnl_net > 0).mean() * 100,
        "avg_win_pct": wins.pnl_net_pct.mean() * 100 if not wins.empty else 0.0,
        "avg_loss_pct": losses.pnl_net_pct.mean() * 100 if not losses.empty else 0.0,
        "payoff_ratio": (wins.pnl_net_pct.mean() / abs(losses.pnl_net_pct.mean())) if not wins.empty and not losses.empty else np.nan,
        "max_equity_dd_pct": max_dd(e.equity), "time_in_market_pct": e.position.mean() * 100 if not e.empty else 0.0,
        "avg_hold_days": t.hold_days.mean(), "expectancy_pct": t.pnl_net_pct.mean() * 100,
        "worst_month_pct": float(monthly.min()) if not monthly.empty else 0.0,
        "fees_pct_start_equity": t.fees.sum() / START_EQUITY * 100,
        "channel_exits": int((t.exit_reason == "channel").sum()), "rail20_exits": int((t.exit_reason == "rail20").sum()),
        "mtm_exits": int((t.exit_reason == "mtm").sum()), **bh,
    }


def decision(summary: pd.DataFrame) -> tuple[str, str]:
    cost_b = summary[summary.cost_model == COST_B.name]
    train = cost_b[cost_b.split == "train"].iloc[0]
    validate = cost_b[cost_b.split == "validate"].iloc[0]
    holdout = cost_b[cost_b.split == "holdout"].iloc[0]
    if holdout.n_trades < 8:
        if train.expectancy_pct > 0 and validate.expectancy_pct > 0 and holdout.net_profit_pct >= 0 and train.max_equity_dd_pct < train.bh_max_dd_pct and validate.max_equity_dd_pct < validate.bh_max_dd_pct:
            return "PAPER", "Holdout is thin, but train/validate expectancy and DD beat the benchmark."
        return "INCONCLUSIVE", "Holdout has fewer than 8 trades, so this cannot pass; train/validate evidence is insufficient for paper."
    if holdout.expectancy_pct <= 0:
        return "KILL", "Holdout expectancy is non-positive after Cost B."
    if holdout.net_profit_pct < 0 and holdout.max_equity_dd_pct >= holdout.bh_max_dd_pct:
        return "KILL", "Holdout loses money and drawdown is not better than buy-and-hold."
    if train.expectancy_pct <= 0 and validate.expectancy_pct <= 0:
        return "KILL", "Train and validate expectancy are both non-positive."
    if train.expectancy_pct > 0 and validate.expectancy_pct > 0 and holdout.expectancy_pct > 0 and holdout.net_profit_pct > 0 and (holdout.max_equity_dd_pct <= 45 or holdout.max_equity_dd_pct <= holdout.bh_max_dd_pct - 10):
        return "PASS", "Ship-candidate rules are met."
    return "PAPER", "Mixed results: risk reducer only, not a scalp bot."


def save_outputs(df: pd.DataFrame, trades: pd.DataFrame, equities: pd.DataFrame, summary: pd.DataFrame) -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    summary.to_csv(os.path.join(RESULTS_DIR, "summary.csv"), index=False)
    trades.to_csv(os.path.join(RESULTS_DIR, "trades.csv"), index=False)
    equities.to_csv(os.path.join(RESULTS_DIR, "equity_D1.csv"), index=False)
    bh_rows = []
    for split, (start, end) in {"full": (FULL_START, pd.Timestamp.max.tz_localize("UTC")), **SPLITS}.items():
        window = df[(df.open_time >= start) & (df.open_time < end)].copy()
        if window.empty:
            continue
        entry = _slip(float(window.iloc[0].open), "buy", COST_B)
        btc = START_EQUITY * (1 - COST_B.fee_side) / entry
        for row in window.itertuples(index=False):
            bh_rows.append({"split": split, "time": row.close_time, "equity": btc * row.close, "position": True})
    bh = pd.DataFrame(bh_rows)
    bh.to_csv(os.path.join(RESULTS_DIR, "equity_BH.csv"), index=False)
    monthly = equities.copy()
    monthly["month"] = monthly.time.dt.tz_convert(None).dt.to_period("M").astype(str)
    monthly_returns = monthly.groupby(["cost_model", "month"]).equity.last().pct_change().reset_index(name="net_return")
    monthly_returns["net_pct"] = monthly_returns.net_return * 100
    monthly_returns.to_csv(os.path.join(RESULTS_DIR, "monthly_returns.csv"), index=False)
    plot_outputs(df, trades, equities, bh)


def plot_outputs(df: pd.DataFrame, trades: pd.DataFrame, equities: pd.DataFrame, bh: pd.DataFrame) -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    for name, start in (("full", FULL_START), ("2024", pd.Timestamp("2024-01-01", tz="UTC"))):
        fig, ax = plt.subplots(figsize=(12, 6))
        eq = equities[(equities.cost_model == COST_B.name) & (equities.time >= start)]
        bench = bh[(bh.split == ("full" if name == "full" else "train"))] if name != "full" else bh[bh.split == "full"]
        ax.plot(eq.time, eq.equity, label="D1 Cost B")
        if not bench.empty:
            ax.plot(bench.time, bench.equity, label="BH Cost B", alpha=0.65)
        ax.legend()
        ax.set_title(f"D1 vs BH equity - {name}")
        fig.tight_layout()
        fig.savefig(os.path.join(RESULTS_DIR, f"equity_d1_bh_{name}.png"))
        plt.close(fig)
    eq = equities[equities.cost_model == COST_B.name]
    if not eq.empty:
        fig, ax = plt.subplots(figsize=(12, 4))
        ax.plot(eq.time, (eq.equity / eq.equity.cummax() - 1) * 100, label="D1")
        ax.set_title("D1 underwater drawdown - Cost B")
        fig.tight_layout()
        fig.savefig(os.path.join(RESULTS_DIR, "underwater_d1.png"))
        plt.close(fig)
    if not trades.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.hist(trades[trades.cost_model == COST_B.name].pnl_net_pct * 100, bins=30)
        ax.set_title("D1 trade PnL histogram - Cost B")
        fig.tight_layout()
        fig.savefig(os.path.join(RESULTS_DIR, "pnl_hist_d1.png"))
        plt.close(fig)


def write_memo(df: pd.DataFrame, summary: pd.DataFrame, trades: pd.DataFrame, result: str, reason: str, counts: dict) -> None:
    text = "\n".join([
        "# Experiment D1 Donchian Results", "",
        "## 1. Data source, spot vs perp, cost assumptions", "Binance spot BTCUSDT daily UTC klines from earliest available cache/download through the latest completed candle. Spot is used, so no funding is applied. Cost A is 0.05% fee each side with no slippage. Cost B is 0.05% fee plus 5 bps slippage each side on next-open fills.", "",
        "## 2. Why this is not the killed 5m/HTF/grid work", "This is a separate daily Donchian 20/10 long-only breakout system. It does not retune the killed 5m adaptive scalp, B1/B2 pullbacks, or Experiment C grid, and it adds no extra indicators.", "",
        "## 3. Bar counts + trade counts (circuit breaker)", f"- Daily bars: {counts['bars']}", f"- Full-sample trades: {counts['full_trades']}", f"- 2024+ trades: {counts['recent_trades']}", f"- Channel sanity failures: {counts['channel_sanity_failures']}", "",
        "## 4. Table D1 Cost A/B x train/validate/holdout + BH", "", summary[summary.split != "full"].to_markdown(index=False), "",
        "## 5. Appendix table 2017+", "", summary[summary.split == "full"].to_markdown(index=False), "",
        "## 6. Failure modes", "Whipsaw months and monthly returns are saved in results_d1/monthly_returns.csv. This daily breakout can sit out long stretches and can miss chop; it is not a scalp. Trade samples below show next-day fills after completed signal bars.", "",
        "## 7. Decision: PASS / PAPER / INCONCLUSIVE / KILL", result, "",
        "## 8. One sentence recommendation", reason, "",
        "## 9. Next step", "If KILL or INCONCLUSIVE-thin, do not add indicators. D2 (4h + compression gate) is allowed only if D1 train+validate expectancy is positive; otherwise stop the breakout program.", "",
        "## 10 sample trades", "", trades.head(10).to_markdown(index=False) if not trades.empty else "No trades.", "",
    ]) + "\n"
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "RESULTS_D1.md"), "w") as f:
        f.write(text)
    try:
        with open("RESULTS_D1.md", "w") as f:
            f.write(text)
    except PermissionError:
        pass


def main() -> None:
    raw = load_daily()
    df = add_donchian(raw).dropna().reset_index(drop=True)
    expected_high20 = df.high.shift(1).rolling(20, min_periods=20).max()
    channel_sanity_failures = int((df.high_20 - expected_high20).abs().fillna(0).gt(1e-9).sum())
    print(f"BAR_COUNTS daily_raw={len(raw)} daily_valid={len(df)} source=Binance spot {SYMBOL}")
    print(f"CHANNEL_SANITY high_20_excludes_current=True failures={channel_sanity_failures}")
    all_trades = []
    all_equity = []
    summary_rows = []
    counts = {"bars": len(raw), "channel_sanity_failures": channel_sanity_failures}
    for cost in (COST_A, COST_B):
        trades, equity = run_d1(df, cost)
        all_trades.append(trades)
        all_equity.append(equity)
        if cost == COST_A:
            counts["full_trades"] = len(trades)
            counts["recent_trades"] = int((trades.entry_time >= pd.Timestamp("2024-01-01", tz="UTC")).sum()) if not trades.empty else 0
            print(f"FULL_SAMPLE_TRADE_COUNT={counts['full_trades']} RECENT_2024_PLUS_TRADE_COUNT={counts['recent_trades']}")
            if counts["recent_trades"] > 80:
                print("CIRCUIT_BREAKER_FAIL recent trades > 80")
            if counts["recent_trades"] == 0:
                print("CIRCUIT_BREAKER_FAIL recent trades == 0")
        for split in ("train", "validate", "holdout", "full"):
            summary_rows.append(summarize(trades, equity, df, cost, split))
    trades_df = pd.concat(all_trades, ignore_index=True)
    equity_df = pd.concat(all_equity, ignore_index=True)
    summary = pd.DataFrame(summary_rows)
    if counts["recent_trades"] > 80 or counts["recent_trades"] == 0:
        result, reason = "KILL", "Circuit breaker failed; do not trust or deploy this implementation."
    else:
        result, reason = decision(summary)
    print("\nSUMMARY")
    print(summary.to_string(index=False, float_format=lambda value: f"{value:.4f}"))
    print("\nTRADE_SAMPLE")
    cols = ["signal_date", "entry_time", "high_20_at_signal", "exit_time", "exit_reason", "pnl_net_pct", "cost_model"]
    print(trades_df[cols].head(10).to_string(index=False) if not trades_df.empty else "no trades")
    print(f"\nDECISION {result}: {reason}")
    save_outputs(df, trades_df, equity_df, summary)
    write_memo(df, summary, trades_df, result, reason, counts)


if __name__ == "__main__":
    main()
