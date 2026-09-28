#!/usr/bin/env python3
"""Frozen B1/B2 HTF BTCUSDT trend-pullback experiments."""

from __future__ import annotations

import os
from dataclasses import dataclass
from math import sqrt

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from experiments.htf.data import SYMBOL, load_all
from experiments.htf.indicators import add_core, align_bias


RESULTS_DIR = "results_htf"
START_EQUITY = 10_000.0
RISK_FRACTION = 0.0035
MAX_LEVERAGE = 5.0
DAILY_STOP = 0.02
FUNDING_PLACEHOLDER = 0.0001
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


COST_A = CostModel("A_maker_maker", 0.0002, 0.00005, 0.0002, 0.00005, 0.0002, 0.00005)
COST_B = CostModel("B_realistic", 0.0005, 0.00010, 0.0005, 0.00010, 0.0002, 0.000025)


@dataclass(frozen=True)
class Experiment:
    name: str
    tf: str
    bias_prefix: str
    bias_deadzone: float
    adx_min: float
    full_trade_cap: int
    cooldown_bars: int
    daily_trade_cap: int
    touch_lookback: int
    required_prior_holds: int
    touch_tolerance: float
    stop_atr_mult: float
    stop_cap: float
    min_stop: float
    tp_r: float
    require_ema55: bool
    bars_per_year: int


B1 = Experiment("B1_15m_trend_pullback", "15m", "h1", 0.0005, 20.0, 800, 6, 6, 8, 3, 0.0008, 1.4, 0.0090, 0.0025, 2.0, True, 365 * 24 * 4)
B2 = Experiment("B2_1h_trend_pullback", "1h", "h4", 0.0008, 18.0, 250, 3, 3, 6, 2, 0.0012, 1.6, 0.0140, 0.0035, 2.2, False, 365 * 24)


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


def bias_side(row, exp: Experiment) -> int:
    close = getattr(row, f"{exp.bias_prefix}_close")
    ema21 = getattr(row, f"{exp.bias_prefix}_ema21")
    if pd.isna(close) or pd.isna(ema21):
        return 0
    diff = close / ema21 - 1.0
    if abs(diff) <= exp.bias_deadzone:
        return 0
    return 1 if diff > 0 else -1


def signal_at(rows: list, i: int, exp: Experiment) -> dict | None:
    row = rows[i]
    prev = rows[i - 1]
    if pd.isna(row.adx14) or pd.isna(row.atr14) or row.adx14 < exp.adx_min:
        return None
    side = bias_side(row, exp)
    if side == 0:
        return None
    if side > 0:
        ema_ok = row.ema9 > row.ema21 and (row.ema21 > row.ema55 if exp.require_ema55 else True)
        if not ema_ok or row.close <= row.vwap:
            return None
        tagged = min(row.low, prev.low) <= row.ema21 * (1 + exp.touch_tolerance)
        reclaimed = row.close > row.ema21
        prior = rows[max(0, i - exp.touch_lookback):i]
        prior_touches = [bar for bar in prior if bar.low <= bar.ema21 * (1 + exp.touch_tolerance)]
        prior_holds = sum(1 for bar in prior if bar.low > bar.ema21)
    else:
        ema_ok = row.ema9 < row.ema21 and (row.ema21 < row.ema55 if exp.require_ema55 else True)
        if not ema_ok or row.close >= row.vwap:
            return None
        tagged = max(row.high, prev.high) >= row.ema21 * (1 - exp.touch_tolerance)
        reclaimed = row.close < row.ema21
        prior = rows[max(0, i - exp.touch_lookback):i]
        prior_touches = [bar for bar in prior if bar.high >= bar.ema21 * (1 - exp.touch_tolerance)]
        prior_holds = sum(1 for bar in prior if bar.high < bar.ema21)
    if not tagged or not reclaimed or prior_touches or prior_holds < exp.required_prior_holds:
        return None
    entry_i = i + 1
    entry = rows[entry_i].open
    atr_stop = row.ema21 - side * exp.stop_atr_mult * row.atr14
    cap_stop = entry * (1 - side * exp.stop_cap)
    stop = min(atr_stop, cap_stop) if side > 0 else max(atr_stop, cap_stop)
    stop_distance_pct = abs(entry - stop) / entry
    if stop_distance_pct < exp.min_stop:
        return {"skip": "too_tight_stop"}
    target = entry + side * exp.tp_r * abs(entry - stop)
    return {"side": side, "entry_i": entry_i, "entry": entry, "sl": stop, "tp": target, "adx": row.adx14, "stop_distance_pct": stop_distance_pct, "signal_time": row.close_time}


def size_trade(equity: float, stop_distance_pct: float) -> float | None:
    notional = equity * RISK_FRACTION / stop_distance_pct
    return None if notional > equity * MAX_LEVERAGE else notional


def run_experiment(df: pd.DataFrame, exp: Experiment, cost: CostModel, collect_sample: bool = False) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
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
    i = max(70, exp.touch_lookback + 2)
    while i < len(rows) - 3:
        row = rows[i]
        row_day = row.open_time.date()
        if row_day != day:
            day = row_day
            day_start_equity = equity
            day_trades = 0
        equity_rows.append({"time": row.close_time, "equity": equity, "experiment": exp.name, "cost_model": cost.name})
        if i < cooldown_until or equity <= day_start_equity * (1 - DAILY_STOP) or day_trades >= exp.daily_trade_cap:
            i += 1
            continue
        signal = signal_at(rows, i, exp)
        if signal is None:
            i += 1
            continue
        if "skip" in signal:
            skipped.append({"time": row.close_time, "experiment": exp.name, "cost_model": cost.name, "reason": signal["skip"]})
            i += 1
            continue
        notional = size_trade(equity, signal["stop_distance_pct"])
        if notional is None:
            skipped.append({"time": row.close_time, "experiment": exp.name, "cost_model": cost.name, "reason": "unsizable"})
            i += 1
            continue
        side = signal["side"]
        entry_i = signal["entry_i"]
        entry = slipped(signal["entry"], side, True, cost.entry_slip)
        stop = signal["sl"]
        target = signal["tp"]
        exit_i = len(rows) - 1
        exit_reason = "MTM"
        exit_price = rows[-1].close
        exit_fee = cost.stop_fee
        exit_slip = cost.stop_slip
        max_exit = min(entry_i + 96, len(rows) - 1)
        for j in range(entry_i, max_exit + 1):
            bar = rows[j]
            if side > 0:
                if bar.low <= stop:
                    exit_i, exit_reason, exit_price, exit_fee, exit_slip = j, "SL", stop, cost.stop_fee, cost.stop_slip
                    break
                if bar.high >= target:
                    exit_i, exit_reason, exit_price, exit_fee, exit_slip = j, "TP", target, cost.tp_fee, cost.tp_slip
                    break
            else:
                if bar.high >= stop:
                    exit_i, exit_reason, exit_price, exit_fee, exit_slip = j, "SL", stop, cost.stop_fee, cost.stop_slip
                    break
                if bar.low <= target:
                    exit_i, exit_reason, exit_price, exit_fee, exit_slip = j, "TP", target, cost.tp_fee, cost.tp_slip
                    break
        if exit_reason == "MTM" and exit_i != len(rows) - 1:
            exit_reason = "TIME"
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
            if consecutive_losses >= 3:
                cooldown_until = exit_i + exp.cooldown_bars
                consecutive_losses = 0
        else:
            consecutive_losses = 0
        trades.append({
            "experiment": exp.name, "tf": exp.tf, "cost_model": cost.name, "entry_time": rows[entry_i].open_time,
            "signal_time": signal["signal_time"], "side": "long" if side > 0 else "short", "entry": entry,
            "sl": stop, "tp": target, "exit_time": rows[exit_i].close_time, "exit_reason": exit_reason,
            "pnl_net": pnl, "pnl_net_pct": net_pct, "fees": fees, "adx": signal["adx"],
            "stop_distance_pct": signal["stop_distance_pct"], "notional": notional, "hold_bars": exit_i - entry_i + 1,
        })
        for j in range(i + 1, exit_i + 1):
            mark = (rows[j].close / entry - 1.0) * side - cost.entry_fee
            equity_rows.append({"time": rows[j].close_time, "equity": equity - pnl + notional * mark, "experiment": exp.name, "cost_model": cost.name})
        i = exit_i + 1
    return pd.DataFrame(trades), pd.DataFrame(equity_rows), pd.DataFrame(skipped)


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


def summarize(trades: pd.DataFrame, equity: pd.DataFrame, skipped: pd.DataFrame, exp: Experiment, split: str, cost_name: str) -> dict:
    start, end = SPLITS[split]
    t = trades[(trades.entry_time >= start) & (trades.entry_time < end)].copy() if not trades.empty else trades
    e = equity[(equity.time >= start) & (equity.time < end)].copy() if not equity.empty else equity
    s = skipped[(skipped.time >= start) & (skipped.time < end)].copy() if not skipped.empty else skipped
    if t.empty:
        return {"experiment": exp.name, "tf": exp.tf, "cost_model": cost_name, "split": split, "net_profit_pct": 0.0, "profit_factor": 0.0, "win_rate": 0.0, "trades": 0, "trades_per_week": 0.0, "avg_win_pct": 0.0, "avg_loss_pct": 0.0, "payoff": 0.0, "max_dd_pct": max_dd(e.equity) if not e.empty else 0.0, "max_consecutive_losses": 0, "time_in_market_pct": 0.0, "avg_hold_bars": 0.0, "avg_hold_hours": 0.0, "expectancy_pct": 0.0, "expectancy_usdt": 0.0, "sharpe_ann": 0.0, "worst_month_pct": 0.0, "fees_pct_start_equity": 0.0, "unsizable_skip_pct": 0.0, "long_pf": 0.0, "long_wr": 0.0, "short_pf": 0.0, "short_wr": 0.0}
    wins = t[t.pnl_net > 0]
    losses = t[t.pnl_net <= 0]
    pf = wins.pnl_net.sum() / abs(losses.pnl_net.sum()) if not losses.empty and losses.pnl_net.sum() != 0 else np.inf
    avg_win = wins.pnl_net_pct.mean() * 100 if not wins.empty else 0.0
    avg_loss = losses.pnl_net_pct.mean() * 100 if not losses.empty else 0.0
    days = max((min(end, t.exit_time.max()) - t.entry_time.min()).days + 1, 1)
    t["month"] = t.entry_time.dt.tz_convert(None).dt.to_period("M").astype(str)
    monthly = t.groupby("month").pnl_net.sum() / START_EQUITY * 100
    returns = e.equity.pct_change().fillna(0) if not e.empty else pd.Series(dtype=float)
    sharpe = returns.mean() / returns.std(ddof=0) * sqrt(exp.bars_per_year) if len(returns) > 2 and returns.std(ddof=0) > 0 else 0.0
    total_skips = len(s)
    unsizable = int((s.reason == "unsizable").sum()) if not s.empty and "reason" in s else 0
    def side_stats(side: str) -> tuple[float, float]:
        rows = t[t.side == side]
        if rows.empty:
            return 0.0, 0.0
        w = rows[rows.pnl_net > 0].pnl_net.sum()
        l = abs(rows[rows.pnl_net <= 0].pnl_net.sum())
        return (w / l if l else np.inf), (rows.pnl_net > 0).mean() * 100
    long_pf, long_wr = side_stats("long")
    short_pf, short_wr = side_stats("short")
    clipped_hold_minutes = 0.0
    for trade in t.itertuples(index=False):
        overlap_start = max(trade.entry_time, start)
        overlap_end = min(trade.exit_time, end)
        if overlap_end > overlap_start:
            clipped_hold_minutes += (overlap_end - overlap_start).total_seconds() / 60
    return {
        "experiment": exp.name, "tf": exp.tf, "cost_model": cost_name, "split": split,
        "net_profit_pct": t.pnl_net.sum() / START_EQUITY * 100, "profit_factor": pf,
        "win_rate": (t.pnl_net > 0).mean() * 100, "trades": len(t), "trades_per_week": len(t) / (days / 7),
        "avg_win_pct": avg_win, "avg_loss_pct": avg_loss, "payoff": avg_win / abs(avg_loss) if avg_loss else np.inf,
        "max_dd_pct": max_dd(e.equity) if not e.empty else 0.0, "max_consecutive_losses": max_consecutive_losses(t.pnl_net),
        "time_in_market_pct": clipped_hold_minutes / (days * 24 * 60) * 100,
        "avg_hold_bars": t.hold_bars.mean(), "avg_hold_hours": t.hold_bars.mean() * (0.25 if exp.tf == "15m" else 1.0),
        "expectancy_pct": t.pnl_net_pct.mean() * 100, "expectancy_usdt": t.pnl_net.mean(), "sharpe_ann": sharpe,
        "worst_month_pct": monthly.min() if not monthly.empty else 0.0, "fees_pct_start_equity": t.fees.sum() / START_EQUITY * 100,
        "unsizable_skip_pct": unsizable / max(len(t) + total_skips, 1) * 100, "long_pf": long_pf, "long_wr": long_wr,
        "short_pf": short_pf, "short_wr": short_wr,
    }


def prepare_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    df15, df1h, df4h = load_all()
    b1 = align_bias(add_core(df15), add_core(df1h), "h1").dropna().reset_index(drop=True)
    b2 = align_bias(add_core(df1h), add_core(df4h), "h4").dropna().reset_index(drop=True)
    print(f"BAR_COUNTS 15m={len(df15)} 1h={len(df1h)} 4h={len(df4h)} B1_rows={len(b1)} B2_rows={len(b2)}")
    return b1, b2


def decision(summary: pd.DataFrame, exp: Experiment) -> str:
    rows = summary[(summary.experiment == exp.name) & (summary.cost_model == COST_B.name)]
    hold = rows[rows.split == "holdout"].iloc[0]
    profitable_splits = int(((rows.net_profit_pct > 0) & (rows.profit_factor >= 1.20)).sum())
    if hold.profit_factor < 1.20 or hold.net_profit_pct < 0 or hold.max_dd_pct > 25 or hold.expectancy_pct <= 0 or profitable_splits <= 1:
        return "KILL"
    if profitable_splits == 3 and hold.max_dd_pct <= 25:
        return "SHIP-CANDIDATE"
    return "PAPER"


def assign_split(timestamp: pd.Timestamp) -> str:
    for split, (start, end) in SPLITS.items():
        if start <= timestamp < end:
            return split
    return "unknown"


def save_plots(trades: pd.DataFrame, equities: pd.DataFrame, df15: pd.DataFrame) -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 6))
    for key, grp in equities.groupby(["experiment", "cost_model"]):
        if key[1] == COST_B.name:
            ax.plot(grp.time, grp.equity, label="/".join(key), alpha=0.8)
    bh = df15[["close_time", "close"]].dropna().copy()
    bh["equity"] = START_EQUITY * bh.close / bh.close.iloc[0]
    ax.plot(bh.close_time, bh.equity, label="BTC buy-hold", alpha=0.55)
    ax.legend(fontsize=8)
    ax.set_title("HTF experiment equity vs BTC buy-hold")
    fig.tight_layout()
    fig.savefig(os.path.join(RESULTS_DIR, "equity_b1_b2_buyhold.png"))
    plt.close(fig)
    for exp in (B1.name, B2.name):
        sub = equities[(equities.experiment == exp) & (equities.cost_model == COST_B.name)]
        if not sub.empty:
            dd = sub.equity / sub.equity.cummax() - 1
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.plot(sub.time, dd * 100)
            ax.set_title(f"{exp} underwater - Cost B")
            fig.tight_layout()
            fig.savefig(os.path.join(RESULTS_DIR, f"underwater_{exp}.png"))
            plt.close(fig)
        t = trades[(trades.experiment == exp) & (trades.cost_model == COST_B.name)]
        if not t.empty:
            fig, ax = plt.subplots(figsize=(8, 4))
            ax.hist(t.pnl_net_pct * 100, bins=50)
            ax.set_title(f"{exp} trade PnL - Cost B")
            fig.tight_layout()
            fig.savefig(os.path.join(RESULTS_DIR, f"pnl_hist_{exp}.png"))
            plt.close(fig)


def write_memo(summary: pd.DataFrame, trades: pd.DataFrame, counts: dict[str, int]) -> None:
    b1_decision = decision(summary, B1) if B1.name in set(summary.experiment) else "KILL"
    b2_decision = decision(summary, B2) if B2.name in set(summary.experiment) else "KILL"
    costb = summary[summary.cost_model == COST_B.name]
    lines = [
        "# HTF BTCUSDT Experiment Results", "",
        "## 1. Data range and source", "Binance USDT-M public BTCUSDT perpetual klines from 2024-01-01 through the latest completed candle, capped at 2026-09-08 for deterministic reruns. Data is cached in data/htf. Funding uses a labeled -0.01% placeholder per 00:00/08:00/16:00 UTC crossing.", "",
        "## 2. What changed vs the killed 5m spec", "The killed adaptive 5m dual-engine system was not retuned. These are separate frozen higher-timeframe single-engine trend-pullback experiments: B1 trades 15m with completed 1h EMA21 bias, and B2 trades 1h with completed 4h EMA21 bias. No new indicators were added.", "",
        "## 3. Full-sample trade counts (circuit breaker)", f"- B1 full sample Cost A next-open trades: {counts.get(B1.name, 0)} / cap {B1.full_trade_cap}", f"- B2 full sample Cost A next-open trades: {counts.get(B2.name, 0)} / cap {B2.full_trade_cap}", "",
        "## 4. Table: B1/B2 x Cost A/B x train/validate/holdout", "", summary.to_markdown(index=False), "",
        "## 5. Failure modes (which months, long vs short, trend vs chop)", "Monthly returns are saved in results_htf/monthly_returns.csv. Long/short PF and win rate are included in results_htf/summary.csv. Both experiments are single trend-pullback engines; failures come from scarce pullbacks not paying 2R often enough after realistic next-open entries, bracket costs, cooldowns, and risk sizing.", "",
        "## 6. PASS / PAPER / KILL per experiment", f"- B1: {b1_decision}", f"- B2: {b2_decision}", "",
        "## 7. Final recommendation: one sentence", f"{'Kill both B1 and B2; do not ship or paper either.' if b1_decision == 'KILL' and b2_decision == 'KILL' else 'Paper only the experiment marked PAPER; do not ship until Cost B train/validate/holdout all clear.'}", "",
        "## 8. Next experiment allowed", "If both are KILL, next step is grid/inventory (Experiment C), not another signal. If one is PAPER, run a strict paper-trading execution study with the same rules and no extra indicators.", "",
        "## 10-row trade sample for lookahead check", "", trades.head(10).to_markdown(index=False), "",
    ]
    with open(os.path.join(RESULTS_DIR, "RESULTS_HTF.md"), "w") as f:
        f.write("\n".join(lines))
    try:
        with open("RESULTS_HTF.md", "w") as f:
            f.write("\n".join(lines))
    except PermissionError:
        pass


def main() -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    b1_df, b2_df = prepare_data()
    experiments = [(B1, b1_df), (B2, b2_df)]
    counts: dict[str, int] = {}
    runnable: list[tuple[Experiment, pd.DataFrame]] = []
    for exp, df in experiments:
        trades, _, _ = run_experiment(df, exp, COST_A)
        counts[exp.name] = len(trades)
        print(f"FULL_SAMPLE_TRADE_COUNT {exp.name}={len(trades)} cap={exp.full_trade_cap}")
        if len(trades) > exp.full_trade_cap:
            print(f"CIRCUIT_BREAKER_FAIL {exp.name}: trades>{exp.full_trade_cap}; no metrics published for this experiment")
        else:
            runnable.append((exp, df))
    all_trades: list[pd.DataFrame] = []
    all_equity: list[pd.DataFrame] = []
    all_skipped: list[pd.DataFrame] = []
    rows: list[dict] = []
    for exp, df in runnable:
        for cost in (COST_A, COST_B):
            trades, equity, skipped = run_experiment(df, exp, cost)
            print(f"RUN {exp.name} {cost.name}: trades={len(trades)} skipped={len(skipped)}")
            for split in SPLITS:
                rows.append(summarize(trades, equity, skipped, exp, split, cost.name))
            all_trades.append(trades)
            all_equity.append(equity)
            all_skipped.append(skipped)
    summary = pd.DataFrame(rows)
    trades = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    equities = pd.concat(all_equity, ignore_index=True) if all_equity else pd.DataFrame()
    skipped = pd.concat(all_skipped, ignore_index=True) if all_skipped else pd.DataFrame()
    print("\nSUMMARY")
    print(summary.to_string(index=False, float_format=lambda value: f"{value:.4f}"))
    if not trades.empty:
        trades["split"] = trades.entry_time.apply(assign_split)
        trades.to_csv(os.path.join(RESULTS_DIR, "trades.csv"), index=False)
        equities[equities.experiment == B1.name].to_csv(os.path.join(RESULTS_DIR, "equity_B1.csv"), index=False)
        equities[equities.experiment == B2.name].to_csv(os.path.join(RESULTS_DIR, "equity_B2.csv"), index=False)
        summary.to_csv(os.path.join(RESULTS_DIR, "summary.csv"), index=False)
        if not skipped.empty:
            skipped.to_csv(os.path.join(RESULTS_DIR, "skipped.csv"), index=False)
        monthly = trades.assign(month=trades.entry_time.dt.tz_convert(None).dt.to_period("M").astype(str)).groupby(["experiment", "cost_model", "month"]).pnl_net.sum().reset_index()
        monthly["net_pct"] = monthly.pnl_net / START_EQUITY * 100
        monthly.to_csv(os.path.join(RESULTS_DIR, "monthly_returns.csv"), index=False)
        save_plots(trades, equities, b1_df)
    else:
        summary.to_csv(os.path.join(RESULTS_DIR, "summary.csv"), index=False)
    write_memo(summary, trades, counts)
    print("\nTRADE_SAMPLE")
    print(trades.head(10).to_string(index=False) if not trades.empty else "no trades")


if __name__ == "__main__":
    main()
