#!/usr/bin/env python3
"""CLI runner for the adaptive BTCUSDT 5-minute scalper backtest matrix."""

from __future__ import annotations

import argparse
import os

import pandas as pd

from config import COST_A, COST_B, RESULTS_DIR
from data_loader import load_market_data
from indicators import add_indicators
from report import rolling_90d_pf, save_outputs, summarize_split
from strategy import FILL_MODELS, V1, V2, V3, V4, VARIANTS, run_backtest


def _period(df: pd.DataFrame, name: str) -> pd.DataFrame:
    if name == "train":
        return df[(df.open_time >= pd.Timestamp("2024-01-01", tz="UTC")) & (df.open_time < pd.Timestamp("2025-07-01", tz="UTC"))].copy()
    if name == "validate":
        return df[(df.open_time >= pd.Timestamp("2025-07-01", tz="UTC")) & (df.open_time < pd.Timestamp("2026-03-01", tz="UTC"))].copy()
    if name == "holdout":
        return df[df.open_time >= pd.Timestamp("2026-03-01", tz="UTC")].copy()
    return df.copy()


def run_matrix(df: pd.DataFrame, quick: bool = False) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    variants = [V1, V2, V3] if quick else VARIANTS
    fills = ["F-OPEN"] if quick else FILL_MODELS
    if quick:
        jobs = [(COST_A, variant, "F-OPEN") for variant in variants]
    else:
        jobs = [(COST_A, variant, fill) for variant in variants for fill in fills]
        jobs.extend((COST_B, V3, fill) for fill in fills)
    all_trades = []
    all_equity = []
    all_skipped = []
    for cost, variant, fill in jobs:
        trades, equity, skipped = run_backtest(df, variant, fill, cost)
        for frame in (trades, equity, skipped):
            if not frame.empty:
                frame["variant"] = variant.name
                frame["fill_model"] = fill
                frame["cost_model"] = cost.name
        print(f"ran {variant.name} {fill} {cost.name}: trades={len(trades)} skipped={len(skipped)}")
        all_trades.append(trades)
        all_equity.append(equity)
        all_skipped.append(skipped)
    return (
        pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame(),
        pd.concat(all_equity, ignore_index=True) if all_equity else pd.DataFrame(),
        pd.concat(all_skipped, ignore_index=True) if all_skipped else pd.DataFrame(),
    )


def build_summary(trades: pd.DataFrame, equity: pd.DataFrame, skipped: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if trades.empty:
        return pd.DataFrame(rows)
    for key, group in trades.groupby(["variant", "fill_model", "cost_model"]):
        eq = equity[(equity.variant == key[0]) & (equity.fill_model == key[1]) & (equity.cost_model == key[2])]
        sk = skipped[(skipped.variant == key[0]) & (skipped.fill_model == key[1]) & (skipped.cost_model == key[2])] if not skipped.empty else skipped
        for split in ("train", "validate", "holdout"):
            row = summarize_split(group, eq, split, sk)
            row.update({"variant": key[0], "fill_model": key[1], "cost_model": key[2]})
            rows.append(row)
    summary = pd.DataFrame(rows)
    return summary[["variant", "fill_model", "cost_model", "split"] + [c for c in summary.columns if c not in ("variant", "fill_model", "cost_model", "split")]]


def print_summary(summary: pd.DataFrame) -> None:
    cols = ["variant", "fill_model", "cost_model", "split", "net_profit_pct", "profit_factor", "win_rate", "trades", "trades_per_week", "expectancy_pct", "max_drawdown_pct", "fees_pct_start_equity", "unsizable_skip_pct"]
    print("\nSUMMARY")
    print(summary[cols].to_string(index=False, float_format=lambda x: f"{x:.3f}"))


def write_results_md(summary: pd.DataFrame, trades: pd.DataFrame, equity: pd.DataFrame) -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    v3b = summary[(summary.variant == "V3_combined") & (summary.cost_model == "B_realistic_mix")]
    engine = trades[(trades.variant == "V3_combined") & (trades.cost_model == "B_realistic_mix")]
    contrib = engine.groupby(["fill_model", "engine"]).pnl_net.sum().reset_index() if not engine.empty else pd.DataFrame()
    holdout = summary[(summary.split == "holdout") & (summary.cost_model == "B_realistic_mix")]
    lines = [
        "# Adaptive BTCUSDT Scalper Results", "",
        "## Data Range And Source", "Binance USDT-M public BTCUSDT 5m and 15m klines from 2024-01-01 through the latest completed candle. Incomplete last candles are dropped.", "",
        "## Fill Model And Cost Assumptions", "F-OPEN enters on next 5m open. F-LIMIT rests at the tagged trend level or re-entry close and cancels after 2 bars. Cost A is optimistic maker-style; Cost B is the realistic mixed model with taker exits/stops and placeholder funding of -0.01% per funding crossing.", "",
        "## Table Of All Variants On Train / Validate / Holdout", "", summary.to_markdown(index=False), "",
        "## Which Engine Made The Money", "", contrib.to_markdown(index=False) if not contrib.empty else "No V3 trades.", "",
        "## Failure Modes", "Trend-engine losses dominate because EMA/VWAP pullbacks often continue through the capped ATR stop or fail to pay enough before fees. Range-engine trades are fewer, but Bollinger fades also fail when volatility expansion continues after the first re-entry close.", "",
        "## PASS/FAIL Vs Kill Criteria", "",
    ]
    for _, row in holdout.iterrows():
        fail = row.profit_factor < 1.15 or row.net_profit_pct < 0 or row.max_drawdown_pct > 20 or row.expectancy_pct <= 0
        lines.append(f"- {row.variant} {row.fill_model}: {'FAIL' if fail else 'PASS'} (PF={row.profit_factor:.2f}, net={row.net_profit_pct:.2f}%, DD={row.max_drawdown_pct:.2f}%, expectancy={row.expectancy_pct:.4f}%)")
    lines += ["", "## Recommendation: Ship V? / Paper Only / Kill", "Kill for live deployment unless a future baseline clears holdout under Cost B. Do not ship a bot from these baseline results.", "", "## Exact Next Experiment If Mixed Results", "The least invasive next experiment is not another indicator: rerun only V3 with stricter execution assumptions that model true maker-only entries and maker exits where possible, aborting unfilled orders rather than falling back to market. If that still fails, stop this BTC candle-only scalp line."]
    with open("RESULTS.md", "w") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Run V1/V2/V3 F-OPEN Cost A on the train split only.")
    args = parser.parse_args()
    df5, df15 = load_market_data()
    df = add_indicators(df5, df15).dropna().reset_index(drop=True)
    if args.quick:
        df = _period(df, "train")
    trades, equity, skipped = run_matrix(df, quick=args.quick)
    summary = build_summary(trades, equity, skipped)
    print_summary(summary)
    if not args.quick:
        save_outputs(summary, trades, equity)
        v3 = trades[(trades.variant == "V3_combined") & (trades.fill_model == "F-OPEN") & (trades.cost_model == "B_realistic_mix")]
        rolling_90d_pf(v3).to_csv(os.path.join(RESULTS_DIR, "rolling_90d_pf_V3.csv"), index=False)
        write_results_md(summary, trades, equity)


if __name__ == "__main__":
    main()
