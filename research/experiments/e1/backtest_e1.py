#!/usr/bin/env python3
"""Experiment E1: sparse 15m range-extreme rejection fade.

Frozen choices (do not retune inside this file after the first recorded run):
  - BTCUSDT perp 15m, next-open fills, 60-minute max hold.
  - Fade a 12h range break that also prints a rejection close.
  - ATR is used only to scale expansion and event-bar size. No ADX/EMA/VWAP/RSI.

Research-only. Reuses the public HTF kline cache. Does not load credentials
or place orders.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from math import sqrt

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from experiments.htf.data import SYMBOL, load_klines
from experiments.htf.indicators import atr


RESULTS_DIR = "results_e1"
START_EQUITY = 10_000.0
RISK_FRACTION = 0.0035
MAX_LEVERAGE = 5.0
DAILY_STOP = 0.02
FUNDING_PLACEHOLDER = 0.0001
LOOKBACK = 48
ATR_PERIOD = 14
RANGE_ATR_MULT = 1.5
EXPANSION_ATR_MULT = 0.75
CLOSE_LOC_LONG = 0.65
CLOSE_LOC_SHORT = 0.35
STOP_BUFFER = 0.0005
MIN_STOP_PCT = 0.0025
MAX_STOP_PCT = 0.012
TP_R = 2.0
MAX_HOLD_BARS = 4
DAILY_TRADE_CAP = 2
LOSS_STREAK_COOLDOWN = 2
COOLDOWN_BARS = 4
FULL_TRADE_CAP = 400
BARS_PER_YEAR = 365 * 24 * 4

SPLITS = {
    "train": (pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2025-07-01", tz="UTC")),
    "validate": (pd.Timestamp("2025-07-01", tz="UTC"), pd.Timestamp("2026-03-01", tz="UTC")),
    "holdout": (pd.Timestamp("2026-03-01", tz="UTC"), pd.Timestamp.max.tz_localize("UTC")),
}


@dataclass(frozen=True)
class CostModel:
    name: str
    entry_fee: float
    entry_slip: float
    stop_fee: float
    stop_slip: float
    tp_fee: float
    tp_slip: float
    time_fee: float
    time_slip: float


COST_A = CostModel("A_maker_maker", 0.0002, 0.00005, 0.0002, 0.00005, 0.0002, 0.000025, 0.0002, 0.00005)
COST_B = CostModel("B_realistic", 0.0005, 0.00010, 0.0005, 0.00010, 0.0002, 0.000025, 0.0005, 0.00010)


def slipped(price: float, side: int, is_entry: bool, slip: float) -> float:
    return price * (1 + side * slip) if is_entry else price * (1 - side * slip)


def funding_crossings(start: pd.Timestamp, end: pd.Timestamp) -> int:
    count = 0
    cursor = start.ceil("h")
    while cursor <= end:
        if cursor.hour in (0, 8, 16) and cursor.minute == 0:
            count += 1
        cursor += pd.Timedelta(hours=1)
    return count


def prepare_data() -> pd.DataFrame:
    df = load_klines("15m").copy()
    df["atr14"] = atr(df, ATR_PERIOD)
    df["prior_high"] = df.high.shift(1).rolling(LOOKBACK, min_periods=LOOKBACK).max()
    df["prior_low"] = df.low.shift(1).rolling(LOOKBACK, min_periods=LOOKBACK).min()
    df["bar_range"] = df.high - df.low
    df["close_loc"] = np.where(df.bar_range > 0, (df.close - df.low) / df.bar_range, np.nan)
    return df.dropna().reset_index(drop=True)


def signal_at(row) -> dict | None:
    if pd.isna(row.atr14) or pd.isna(row.prior_high) or pd.isna(row.close_loc) or row.bar_range <= 0:
        return None
    if row.bar_range < RANGE_ATR_MULT * row.atr14:
        return None
    side = 0
    if row.low < row.prior_low - EXPANSION_ATR_MULT * row.atr14 and row.close_loc >= CLOSE_LOC_LONG:
        side = 1
    elif row.high > row.prior_high + EXPANSION_ATR_MULT * row.atr14 and row.close_loc <= CLOSE_LOC_SHORT:
        side = -1
    if side == 0:
        return None
    return {"side": side, "signal_time": row.close_time, "extreme": float(row.low if side > 0 else row.high)}


def size_trade(equity: float, stop_distance_pct: float) -> float | None:
    notional = equity * RISK_FRACTION / stop_distance_pct
    return None if notional > equity * MAX_LEVERAGE else notional


def run_e1(df: pd.DataFrame, cost: CostModel) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = list(df.itertuples(index=False))
    equity = START_EQUITY
    day = None
    day_start_equity = START_EQUITY
    day_trades = 0
    cooldown_until = -1
    consecutive_losses = 0
    trades: list[dict] = []
    skipped: list[dict] = []
    equity_rows: list[dict] = []
    i = 0
    while i < len(rows) - MAX_HOLD_BARS - 1:
        row = rows[i]
        row_day = row.open_time.date()
        if row_day != day:
            day = row_day
            day_start_equity = equity
            day_trades = 0
        equity_rows.append({"time": row.close_time, "equity": equity, "cost_model": cost.name})
        if i < cooldown_until or equity <= day_start_equity * (1 - DAILY_STOP) or day_trades >= DAILY_TRADE_CAP:
            i += 1
            continue
        signal = signal_at(row)
        if signal is None:
            i += 1
            continue
        entry_i = i + 1
        entry_raw = float(rows[entry_i].open)
        side = signal["side"]
        stop = signal["extreme"] * (1 - STOP_BUFFER) if side > 0 else signal["extreme"] * (1 + STOP_BUFFER)
        stop_distance_pct = abs(entry_raw - stop) / entry_raw
        if stop_distance_pct < MIN_STOP_PCT:
            skipped.append({"time": row.close_time, "cost_model": cost.name, "reason": "too_tight_stop"})
            i += 1
            continue
        if stop_distance_pct > MAX_STOP_PCT:
            skipped.append({"time": row.close_time, "cost_model": cost.name, "reason": "too_wide_stop"})
            i += 1
            continue
        notional = size_trade(equity, stop_distance_pct)
        if notional is None:
            skipped.append({"time": row.close_time, "cost_model": cost.name, "reason": "unsizable"})
            i += 1
            continue
        entry = slipped(entry_raw, side, True, cost.entry_slip)
        target = entry + side * TP_R * abs(entry - stop)
        exit_i = min(entry_i + MAX_HOLD_BARS - 1, len(rows) - 1)
        exit_reason = "TIME"
        exit_price = float(rows[exit_i].close)
        exit_fee, exit_slip = cost.time_fee, cost.time_slip
        for j in range(entry_i, exit_i + 1):
            bar = rows[j]
            if side > 0:
                if bar.low <= stop:
                    exit_i, exit_reason, exit_price = j, "SL", stop
                    exit_fee, exit_slip = cost.stop_fee, cost.stop_slip
                    break
                if bar.high >= target:
                    exit_i, exit_reason, exit_price = j, "TP", target
                    exit_fee, exit_slip = cost.tp_fee, cost.tp_slip
                    break
            else:
                if bar.high >= stop:
                    exit_i, exit_reason, exit_price = j, "SL", stop
                    exit_fee, exit_slip = cost.stop_fee, cost.stop_slip
                    break
                if bar.low <= target:
                    exit_i, exit_reason, exit_price = j, "TP", target
                    exit_fee, exit_slip = cost.tp_fee, cost.tp_slip
                    break
        exit_exec = slipped(exit_price, side, False, exit_slip)
        funding = funding_crossings(rows[entry_i].open_time, rows[exit_i].close_time) * FUNDING_PLACEHOLDER
        fee_pct = cost.entry_fee + exit_fee + funding
        net_pct = (exit_exec / entry - 1.0) * side - fee_pct
        pnl = notional * net_pct
        fees = notional * fee_pct
        equity += pnl
        day_trades += 1
        if pnl <= 0:
            consecutive_losses += 1
            if consecutive_losses >= LOSS_STREAK_COOLDOWN:
                cooldown_until = exit_i + COOLDOWN_BARS
                consecutive_losses = 0
        else:
            consecutive_losses = 0
        trades.append({
            "experiment": "E1_15m_rejection_fade", "tf": "15m", "cost_model": cost.name,
            "entry_time": rows[entry_i].open_time, "signal_time": signal["signal_time"],
            "side": "long" if side > 0 else "short", "entry": entry, "sl": stop, "tp": target,
            "exit_time": rows[exit_i].close_time, "exit_reason": exit_reason, "pnl_net": pnl,
            "pnl_net_pct": net_pct, "fees": fees, "stop_distance_pct": stop_distance_pct,
            "notional": notional, "hold_bars": exit_i - entry_i + 1, "atr14": float(row.atr14),
            "close_loc": float(row.close_loc),
        })
        for j in range(i + 1, exit_i + 1):
            mark = (float(rows[j].close) / entry - 1.0) * side - cost.entry_fee
            equity_rows.append({"time": rows[j].close_time, "equity": equity - pnl + notional * mark, "cost_model": cost.name})
        i = exit_i + 1
    equity_rows.append({"time": rows[-1].close_time, "equity": equity, "cost_model": cost.name})
    return pd.DataFrame(trades), pd.DataFrame(equity_rows).drop_duplicates("time").sort_values("time"), pd.DataFrame(skipped)


def max_dd(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    return abs(float((equity / equity.cummax() - 1.0).min())) * 100


def max_consecutive_losses(pnls: pd.Series) -> int:
    best = cur = 0
    for pnl in pnls:
        if pnl <= 0:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def summarize(trades: pd.DataFrame, equity: pd.DataFrame, skipped: pd.DataFrame, split: str, cost_name: str) -> dict:
    start, end = SPLITS[split]
    t = trades[(trades.entry_time >= start) & (trades.entry_time < end)].copy() if not trades.empty else trades
    e = equity[(equity.time >= start) & (equity.time < end)].copy() if not equity.empty else equity
    s = skipped[(skipped.time >= start) & (skipped.time < end)].copy() if not skipped.empty else skipped
    empty = {
        "experiment": "E1_15m_rejection_fade", "tf": "15m", "cost_model": cost_name, "split": split,
        "net_profit_pct": 0.0, "profit_factor": 0.0, "win_rate": 0.0, "trades": 0, "trades_per_week": 0.0,
        "avg_win_pct": 0.0, "avg_loss_pct": 0.0, "payoff": 0.0, "max_dd_pct": max_dd(e.equity) if not e.empty else 0.0,
        "max_consecutive_losses": 0, "time_in_market_pct": 0.0, "avg_hold_bars": 0.0, "avg_hold_minutes": 0.0,
        "expectancy_pct": 0.0, "expectancy_usdt": 0.0, "sharpe_ann": 0.0, "worst_month_pct": 0.0,
        "fees_pct_start_equity": 0.0, "skip_pct": 0.0, "long_pf": 0.0, "long_wr": 0.0, "short_pf": 0.0, "short_wr": 0.0,
        "tp_exits": 0, "sl_exits": 0, "time_exits": 0,
    }
    if t.empty:
        return empty
    wins = t[t.pnl_net > 0]
    losses = t[t.pnl_net <= 0]
    pf = wins.pnl_net.sum() / abs(losses.pnl_net.sum()) if not losses.empty and losses.pnl_net.sum() != 0 else np.inf
    avg_win = wins.pnl_net_pct.mean() * 100 if not wins.empty else 0.0
    avg_loss = losses.pnl_net_pct.mean() * 100 if not losses.empty else 0.0
    days = max((min(end, t.exit_time.max()) - t.entry_time.min()).days + 1, 1)
    t = t.copy()
    t["month"] = t.entry_time.dt.tz_convert(None).dt.to_period("M").astype(str)
    monthly = t.groupby("month").pnl_net.sum() / START_EQUITY * 100
    returns = e.equity.pct_change().fillna(0) if not e.empty else pd.Series(dtype=float)
    sharpe = returns.mean() / returns.std(ddof=0) * sqrt(BARS_PER_YEAR) if len(returns) > 2 and returns.std(ddof=0) > 0 else 0.0
    total_skips = len(s)

    def side_stats(side: str) -> tuple[float, float]:
        rows = t[t.side == side]
        if rows.empty:
            return 0.0, 0.0
        w = rows[rows.pnl_net > 0].pnl_net.sum()
        l = abs(rows[rows.pnl_net <= 0].pnl_net.sum())
        return (w / l if l else np.inf), (rows.pnl_net > 0).mean() * 100

    long_pf, long_wr = side_stats("long")
    short_pf, short_wr = side_stats("short")
    hold_minutes = 0.0
    for trade in t.itertuples(index=False):
        overlap_start = max(trade.entry_time, start)
        overlap_end = min(trade.exit_time, end)
        if overlap_end > overlap_start:
            hold_minutes += (overlap_end - overlap_start).total_seconds() / 60
    return {
        "experiment": "E1_15m_rejection_fade", "tf": "15m", "cost_model": cost_name, "split": split,
        "net_profit_pct": t.pnl_net.sum() / START_EQUITY * 100, "profit_factor": pf,
        "win_rate": (t.pnl_net > 0).mean() * 100, "trades": len(t), "trades_per_week": len(t) / (days / 7),
        "avg_win_pct": avg_win, "avg_loss_pct": avg_loss, "payoff": avg_win / abs(avg_loss) if avg_loss else np.inf,
        "max_dd_pct": max_dd(e.equity) if not e.empty else 0.0, "max_consecutive_losses": max_consecutive_losses(t.pnl_net),
        "time_in_market_pct": hold_minutes / (days * 24 * 60) * 100, "avg_hold_bars": float(t.hold_bars.mean()),
        "avg_hold_minutes": float(t.hold_bars.mean()) * 15.0, "expectancy_pct": t.pnl_net_pct.mean() * 100,
        "expectancy_usdt": t.pnl_net.mean(), "sharpe_ann": sharpe,
        "worst_month_pct": float(monthly.min()) if not monthly.empty else 0.0,
        "fees_pct_start_equity": t.fees.sum() / START_EQUITY * 100,
        "skip_pct": total_skips / max(len(t) + total_skips, 1) * 100, "long_pf": long_pf, "long_wr": long_wr,
        "short_pf": short_pf, "short_wr": short_wr, "tp_exits": int((t.exit_reason == "TP").sum()),
        "sl_exits": int((t.exit_reason == "SL").sum()), "time_exits": int((t.exit_reason == "TIME").sum()),
    }


def decision(summary: pd.DataFrame, full_trades: int) -> tuple[str, str]:
    if full_trades <= 0 or full_trades > FULL_TRADE_CAP:
        return "KILL", "Circuit breaker: event is missing or not sparse."
    rows = summary[summary.cost_model == COST_B.name]
    train = rows[rows.split == "train"].iloc[0]
    validate = rows[rows.split == "validate"].iloc[0]
    hold = rows[rows.split == "holdout"].iloc[0]
    if hold.trades < 8:
        if train.expectancy_pct > 0 and validate.expectancy_pct > 0 and hold.expectancy_pct >= 0:
            return "PAPER", "Holdout is thin; train/validate Cost B expectancy is positive."
        return "INCONCLUSIVE", "Holdout has fewer than 8 Cost B trades; cannot pass."
    if hold.expectancy_pct <= 0 or hold.net_profit_pct < 0:
        return "KILL", "Cost B holdout average net P&L is not positive."
    if train.expectancy_pct <= 0 or validate.expectancy_pct <= 0:
        return "KILL", "Cost B train or validate expectancy is non-positive."
    if hold.profit_factor >= 1.15 and hold.max_dd_pct <= 20 and train.profit_factor >= 1.15:
        return "PASS", "Cost B expectancy, PF, and holdout drawdown clear the scalp bar."
    return "PAPER", "Cost B expectancy is positive but PF/drawdown are not ship-ready."


def save_outputs(trades: pd.DataFrame, equities: pd.DataFrame, summary: pd.DataFrame, skipped: pd.DataFrame) -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    summary.to_csv(os.path.join(RESULTS_DIR, "summary.csv"), index=False)
    trades.to_csv(os.path.join(RESULTS_DIR, "trades.csv"), index=False)
    skipped.to_csv(os.path.join(RESULTS_DIR, "skipped.csv"), index=False)
    equities.to_csv(os.path.join(RESULTS_DIR, "equity_E1.csv"), index=False)
    monthly = equities.copy()
    monthly["month"] = monthly.time.dt.tz_convert(None).dt.to_period("M").astype(str)
    monthly.groupby(["cost_model", "month"]).equity.last().pct_change().reset_index(name="net_return").assign(
        net_pct=lambda frame: frame.net_return * 100
    ).to_csv(os.path.join(RESULTS_DIR, "monthly_returns.csv"), index=False)
    eq = equities[equities.cost_model == COST_B.name]
    if not eq.empty:
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(eq.time, eq.equity, label="E1 Cost B")
        ax.legend()
        ax.set_title("E1 15m rejection fade equity - Cost B")
        fig.tight_layout()
        fig.savefig(os.path.join(RESULTS_DIR, "equity_e1.png"))
        plt.close(fig)
        fig, ax = plt.subplots(figsize=(12, 4))
        ax.plot(eq.time, (eq.equity / eq.equity.cummax() - 1) * 100)
        ax.set_title("E1 underwater - Cost B")
        fig.tight_layout()
        fig.savefig(os.path.join(RESULTS_DIR, "underwater_e1.png"))
        plt.close(fig)
    cost_b_trades = trades[trades.cost_model == COST_B.name] if not trades.empty else trades
    if not cost_b_trades.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.hist(cost_b_trades.pnl_net_pct * 100, bins=30)
        ax.set_title("E1 trade PnL % histogram - Cost B")
        fig.tight_layout()
        fig.savefig(os.path.join(RESULTS_DIR, "pnl_hist_e1.png"))
        plt.close(fig)


def write_memo(summary: pd.DataFrame, trades: pd.DataFrame, result: str, reason: str, counts: dict) -> None:
    sample = trades[trades.cost_model == COST_A.name][
        ["signal_time", "entry_time", "side", "entry", "sl", "tp", "exit_time", "exit_reason", "pnl_net", "hold_bars"]
    ].head(10) if not trades.empty else pd.DataFrame()
    text = "\n".join([
        "# Experiment E1 Sparse 15m Rejection Fade", "",
        "## 1. Frozen spec",
        "BTCUSDT perp 15m. Fade a completed 12h range break that also rejects (close in the opposite 35% of the bar). Next-open entry, 2R, 60-minute cap, stop-wins on collision. Cost A is optimistic maker-ish; Cost B is the decision model (taker entry/stop, maker TP if touched). Funding placeholder -0.01% per 00:00/08:00/16:00 UTC crossing.",
        "",
        "## 2. Why this is not a killed system",
        "This is not V1-V4, 5m impulse/dump fade, B1/B2 pullback, grid C, or D1 Donchian. No ADX/EMA/VWAP/RSI. The bet is rare expansion-plus-rejection, not frequent pullbacks.",
        "",
        "## 3. Counts",
        f"- 15m bars used: {counts['bars']}",
        f"- Cost A full-sample trades: {counts['full_trades']} (cap {FULL_TRADE_CAP})",
        f"- Cost A skips: {counts['skips']}",
        "",
        "## 4. Train / validate / holdout",
        "",
        summary.to_markdown(index=False),
        "",
        "## 5. Decision: PASS / PAPER / INCONCLUSIVE / KILL",
        result,
        "",
        "## 6. One sentence",
        reason,
        "",
        "## 7. Next step",
        "If KILL or INCONCLUSIVE, do not add indicators. Stop this rejection-fade line. If PAPER, freeze the same rules for a paper execution study. If PASS, keep main.py inert until a separate testnet plan is written.",
        "",
        "## 8. Sample trades (Cost A)",
        "",
        sample.to_markdown(index=False) if not sample.empty else "No trades.",
        "",
    ]) + "\n"
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "RESULTS_E1.md"), "w") as f:
        f.write(text)
    try:
        with open("RESULTS_E1.md", "w") as f:
            f.write(text)
    except PermissionError:
        pass


def main() -> None:
    df = prepare_data()
    print(f"BAR_COUNTS 15m={len(df)} source=Binance perp {SYMBOL}")
    all_trades = []
    all_equity = []
    all_skipped = []
    summary_rows = []
    full_trades = 0
    skips = 0
    for cost in (COST_A, COST_B):
        trades, equity, skipped = run_e1(df, cost)
        all_trades.append(trades)
        all_equity.append(equity)
        all_skipped.append(skipped)
        if cost == COST_A:
            full_trades = len(trades)
            skips = len(skipped)
            print(f"FULL_SAMPLE_TRADE_COUNT={full_trades} SKIPS={skips}")
            if full_trades > FULL_TRADE_CAP:
                print("CIRCUIT_BREAKER_FAIL trades > 400")
            if full_trades == 0:
                print("CIRCUIT_BREAKER_FAIL trades == 0")
        for split in ("train", "validate", "holdout"):
            summary_rows.append(summarize(trades, equity, skipped, split, cost.name))
    trades_df = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    equity_df = pd.concat(all_equity, ignore_index=True)
    skipped_df = pd.concat(all_skipped, ignore_index=True) if all_skipped else pd.DataFrame()
    summary = pd.DataFrame(summary_rows)
    result, reason = decision(summary, full_trades)
    print("\nSUMMARY")
    print(summary.to_string(index=False, float_format=lambda value: f"{value:.4f}"))
    print(f"\nDECISION {result}: {reason}")
    save_outputs(trades_df, equity_df, summary, skipped_df)
    write_memo(summary, trades_df, result, reason, {"bars": len(df), "full_trades": full_trades, "skips": skips})


if __name__ == "__main__":
    main()
