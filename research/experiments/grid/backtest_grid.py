#!/usr/bin/env python3
"""Experiment C: BTCUSDT perpetual inventory grid with regime kill-switch.

Frozen choices:
  - Grid center is 24h rolling VWAP built from 1h typical price * volume.
  - 1h candles simulate grid fills; completed 4h ADX(14) controls grid ON/OFF.
  - Arithmetic grid: 20 levels total, 10 buys below center and 10 sells above.

Research-only. Uses Binance public klines through experiments.htf.data. Does not
load credentials, start the service, or place orders.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from math import sqrt

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from experiments.htf.data import SYMBOL, load_klines
from experiments.htf.indicators import adx, atr


RESULTS_DIR = "results_grid"
START_EQUITY = 10_000.0
ALLOC_FRACTION = 0.30
INVENTORY_CAP_FRACTION = 0.15
GRID_BAND = 0.03
GRID_LEVELS_PER_SIDE = 10
MAKER_FEE = 0.0002
FLATTEN_FEE = 0.0005
FLATTEN_SLIPPAGE = 0.0001
ADX_ON = 18.0
ADX_OFF = 25.0
ATR_OFF_MULT = 1.5
DAILY_HALT = 0.02
DISABLE_HOURS_AFTER_CAP = 12

SPLITS = {
    "train": (pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2025-07-01", tz="UTC")),
    "validate": (pd.Timestamp("2025-07-01", tz="UTC"), pd.Timestamp("2026-03-01", tz="UTC")),
    "holdout": (pd.Timestamp("2026-03-01", tz="UTC"), pd.Timestamp.max.tz_localize("UTC")),
}


@dataclass
class State:
    cash: float = START_EQUITY
    btc: float = 0.0
    active: bool = False
    disabled_until: pd.Timestamp | None = None
    day = None
    day_start_equity: float = START_EQUITY


def rolling_vwap_24h(df: pd.DataFrame) -> pd.Series:
    typical = (df.high + df.low + df.close) / 3
    pv = typical * df.volume
    return pv.rolling(24, min_periods=24).sum() / df.volume.rolling(24, min_periods=24).sum()


def prepare_data() -> pd.DataFrame:
    df1h = load_klines("1h")
    df4h = load_klines("4h")
    df1h = df1h.copy()
    df4h = df4h.copy()
    df1h["atr14"] = atr(df1h, 14)
    df1h["vwap24"] = rolling_vwap_24h(df1h)
    df4h["adx4h"] = adx(df4h, 14)
    info = df4h[["close_time", "adx4h"]].dropna().rename(columns={"close_time": "close_time_4h"})
    merged = pd.merge_asof(
        df1h.sort_values("close_time"),
        info.sort_values("close_time_4h"),
        left_on="close_time",
        right_on="close_time_4h",
        direction="backward",
    )
    return merged.dropna(subset=["atr14", "vwap24", "adx4h"]).reset_index(drop=True)


def equity(state: State, price: float) -> float:
    return state.cash + state.btc * price


def flatten(state: State, price: float, time: pd.Timestamp, reason: str, events: list[dict]) -> float:
    if abs(state.btc) <= 0:
        return 0.0
    before = equity(state, price)
    qty = state.btc
    if qty > 0:
        exec_price = price * (1 - FLATTEN_SLIPPAGE)
        notional = qty * exec_price
        fee = notional * FLATTEN_FEE
        state.cash += notional - fee
    else:
        exec_price = price * (1 + FLATTEN_SLIPPAGE)
        notional = abs(qty) * exec_price
        fee = notional * FLATTEN_FEE
        state.cash -= notional + fee
    state.btc = 0.0
    after = equity(state, price)
    events.append({
        "time": time, "event": "flatten", "reason": reason, "side": "sell" if qty > 0 else "buy",
        "price": exec_price, "qty": abs(qty), "notional": notional, "fee": fee,
        "pnl": after - before, "equity": after,
    })
    return after - before


def grid_levels(center: float) -> tuple[list[float], list[float]]:
    step = GRID_BAND / GRID_LEVELS_PER_SIDE
    buys = [center * (1 - step * i) for i in range(1, GRID_LEVELS_PER_SIDE + 1)]
    sells = [center * (1 + step * i) for i in range(1, GRID_LEVELS_PER_SIDE + 1)]
    return buys, sells


def execute_fill(state: State, side: str, level: float, quote: float, time: pd.Timestamp, events: list[dict]) -> None:
    qty = quote / level
    fee = quote * MAKER_FEE
    if side == "buy":
        state.cash -= quote + fee
        state.btc += qty
    else:
        state.cash += quote - fee
        state.btc -= qty
    events.append({
        "time": time, "event": "grid_fill", "reason": "level_touch", "side": side,
        "price": level, "qty": qty, "notional": quote, "fee": fee, "pnl": 0.0,
        "equity": equity(state, level),
    })


def run_backtest(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    state = State()
    events: list[dict] = []
    equity_rows: list[dict] = []
    flatten_rows: list[dict] = []
    grid_on_pnl = 0.0
    flatten_pnl_by_day: dict[str, float] = {}
    for row in df.itertuples(index=False):
        mark = float(row.close)
        now_equity = equity(state, mark)
        row_day = row.open_time.date()
        if row_day != state.day:
            state.day = row_day
            state.day_start_equity = now_equity
        if state.active and now_equity <= state.day_start_equity * (1 - DAILY_HALT):
            pnl = flatten(state, mark, row.close_time, "daily_halt", events)
            flatten_pnl_by_day[str(row_day)] = flatten_pnl_by_day.get(str(row_day), 0.0) + pnl
            state.active = False
            state.disabled_until = pd.Timestamp(row.open_time).floor("D") + pd.Timedelta(days=1)
        if state.active:
            upper_off = row.vwap24 * (1 + GRID_BAND) + ATR_OFF_MULT * row.atr14
            lower_off = row.vwap24 * (1 - GRID_BAND) - ATR_OFF_MULT * row.atr14
            if row.adx4h > ADX_OFF or row.close > upper_off or row.close < lower_off:
                reason = "adx_off" if row.adx4h > ADX_OFF else "band_break"
                pnl = flatten(state, mark, row.close_time, reason, events)
                flatten_pnl_by_day[str(row_day)] = flatten_pnl_by_day.get(str(row_day), 0.0) + pnl
                flatten_rows.append({"time": row.close_time, "reason": reason, "pnl": pnl})
                state.active = False
        can_enable = state.disabled_until is None or row.open_time >= state.disabled_until
        if not state.active and can_enable and row.adx4h < ADX_ON and equity(state, mark) > state.day_start_equity * (1 - DAILY_HALT):
            state.active = True
            events.append({"time": row.close_time, "event": "grid_on", "reason": "adx_on", "side": "", "price": mark, "qty": 0.0, "notional": 0.0, "fee": 0.0, "pnl": 0.0, "equity": equity(state, mark)})
        start_equity = equity(state, mark)
        if state.active:
            allocated = equity(state, mark) * ALLOC_FRACTION
            quote = allocated / (GRID_LEVELS_PER_SIDE * 2)
            buys, sells = grid_levels(float(row.vwap24))
            for level in buys:
                if row.low <= level:
                    execute_fill(state, "buy", level, quote, row.close_time, events)
            for level in sells:
                if row.high >= level:
                    execute_fill(state, "sell", level, quote, row.close_time, events)
            cap = allocated * INVENTORY_CAP_FRACTION
            if abs(state.btc * mark) > cap:
                pnl = flatten(state, mark, row.close_time, "inventory_cap", events)
                flatten_pnl_by_day[str(row_day)] = flatten_pnl_by_day.get(str(row_day), 0.0) + pnl
                flatten_rows.append({"time": row.close_time, "reason": "inventory_cap", "pnl": pnl})
                state.active = False
                state.disabled_until = row.open_time + pd.Timedelta(hours=DISABLE_HOURS_AFTER_CAP)
        end_equity = equity(state, mark)
        if state.active:
            grid_on_pnl += end_equity - start_equity
        equity_rows.append({
            "time": row.close_time, "equity": end_equity, "cash": state.cash, "btc": state.btc,
            "price": mark, "active": state.active, "inventory_notional": abs(state.btc * mark),
            "adx4h": row.adx4h, "vwap24": row.vwap24, "atr14": row.atr14,
        })
    if abs(state.btc) > 0:
        pnl = flatten(state, float(df.iloc[-1].close), df.iloc[-1].close_time, "end_mtm", events)
        flatten_pnl_by_day[str(df.iloc[-1].open_time.date())] = flatten_pnl_by_day.get(str(df.iloc[-1].open_time.date()), 0.0) + pnl
    events_df = pd.DataFrame(events)
    equity_df = pd.DataFrame(equity_rows)
    flatten_df = pd.DataFrame(flatten_rows)
    if not equity_df.empty:
        equity_df.attrs["grid_on_pnl"] = grid_on_pnl
        equity_df.attrs["flatten_pnl_by_day"] = flatten_pnl_by_day
    return events_df, equity_df, flatten_df


def split_of(ts: pd.Timestamp) -> str:
    for name, (start, end) in SPLITS.items():
        if start <= ts < end:
            return name
    return "unknown"


def max_dd(series: pd.Series) -> float:
    if series.empty:
        return 0.0
    return abs(float((series / series.cummax() - 1.0).min())) * 100


def summarize(equity_df: pd.DataFrame, events_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    fills = events_df[events_df.event == "grid_fill"].copy() if not events_df.empty else pd.DataFrame()
    flattens = events_df[events_df.event == "flatten"].copy() if not events_df.empty else pd.DataFrame()
    for split, (start, end) in SPLITS.items():
        eq = equity_df[(equity_df.time >= start) & (equity_df.time < end)].copy()
        ev = events_df[(events_df.time >= start) & (events_df.time < end)].copy() if not events_df.empty else events_df
        split_fills = fills[(fills.time >= start) & (fills.time < end)] if not fills.empty else fills
        split_flattens = flattens[(flattens.time >= start) & (flattens.time < end)] if not flattens.empty else flattens
        if eq.empty:
            continue
        start_eq = float(eq.iloc[0].equity)
        end_eq = float(eq.iloc[-1].equity)
        active_eq = eq[eq.active]
        grid_on_profit = float(active_eq.equity.diff().fillna(0).sum()) if not active_eq.empty else 0.0
        flatten_loss = float(split_flattens.pnl.sum()) if not split_flattens.empty else 0.0
        month = eq.copy()
        month["month"] = month.time.dt.tz_convert(None).dt.to_period("M").astype(str)
        monthly = month.groupby("month").equity.last().pct_change().fillna((month.groupby("month").equity.last().iloc[0] / start_eq) - 1) * 100
        fees = split_fills.fee.sum() if not split_fills.empty else 0.0
        fees += split_flattens.fee.sum() if not split_flattens.empty else 0.0
        rows.append({
            "split": split, "net_profit_pct": (end_eq / start_eq - 1) * 100,
            "max_inventory_dd_pct": max_dd(eq.equity - eq.inventory_notional),
            "max_equity_dd_pct": max_dd(eq.equity), "time_in_grid_pct": eq.active.mean() * 100,
            "flatten_events": len(split_flattens), "grid_on_profit": grid_on_profit,
            "flatten_pnl": flatten_loss, "worst_month_pct": float(monthly.min()),
            "fees_pct_equity": fees / START_EQUITY * 100,
            "fills": len(split_fills), "ending_equity": end_eq,
        })
    return pd.DataFrame(rows)


def decision(summary: pd.DataFrame) -> str:
    hold = summary[summary.split == "holdout"].iloc[0]
    flatten_days_explain_loss = hold.flatten_pnl < 0 and abs(hold.flatten_pnl) > abs(hold.grid_on_profit)
    if hold.net_profit_pct < 0 or hold.max_equity_dd_pct > 25 or (flatten_days_explain_loss and hold.grid_on_profit <= 0):
        return "KILL"
    train = summary[summary.split == "train"].iloc[0]
    validate = summary[summary.split == "validate"].iloc[0]
    if train.net_profit_pct > 0 and validate.net_profit_pct > 0 and hold.net_profit_pct > 0 and hold.max_equity_dd_pct <= 25:
        return "SHIP-CANDIDATE"
    return "PAPER"


def save_outputs(df: pd.DataFrame, events: pd.DataFrame, equity_df: pd.DataFrame, summary: pd.DataFrame) -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    events.to_csv(os.path.join(RESULTS_DIR, "events.csv"), index=False)
    equity_df.to_csv(os.path.join(RESULTS_DIR, "equity.csv"), index=False)
    summary.to_csv(os.path.join(RESULTS_DIR, "summary.csv"), index=False)
    monthly = equity_df.copy()
    monthly["month"] = monthly.time.dt.tz_convert(None).dt.to_period("M").astype(str)
    monthly_returns = monthly.groupby("month").equity.last().pct_change().fillna((monthly.groupby("month").equity.last().iloc[0] / START_EQUITY) - 1).reset_index()
    monthly_returns.columns = ["month", "net_return"]
    monthly_returns["net_pct"] = monthly_returns.net_return * 100
    monthly_returns.to_csv(os.path.join(RESULTS_DIR, "monthly_returns.csv"), index=False)
    buy_hold = START_EQUITY * df.close / df.close.iloc[0]
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(equity_df.time, equity_df.equity, label="grid")
    ax.plot(df.close_time, buy_hold, label="BTC buy-hold", alpha=0.6)
    ax.legend()
    ax.set_title("Experiment C grid equity vs BTC buy-hold")
    fig.tight_layout()
    fig.savefig(os.path.join(RESULTS_DIR, "equity_grid_buyhold.png"))
    plt.close(fig)
    dd = equity_df.equity / equity_df.equity.cummax() - 1
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(equity_df.time, dd * 100)
    ax.set_title("Experiment C underwater drawdown")
    fig.tight_layout()
    fig.savefig(os.path.join(RESULTS_DIR, "underwater_grid.png"))
    plt.close(fig)
    fills = events[events.event == "grid_fill"] if not events.empty else pd.DataFrame()
    if not fills.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.hist(fills.notional, bins=30)
        ax.set_title("Experiment C fill notional histogram")
        fig.tight_layout()
        fig.savefig(os.path.join(RESULTS_DIR, "fill_histogram.png"))
        plt.close(fig)


def write_memo(summary: pd.DataFrame, events: pd.DataFrame, result: str) -> None:
    hold = summary[summary.split == "holdout"].iloc[0]
    lines = [
        "# Experiment C Grid Results", "",
        "## Data range and source", "Binance USDT-M public BTCUSDT perpetual 1h klines for grid marks and completed 4h klines for ADX(14), from 2024-01-01 through latest available during the run. Data is cached in data/htf via the shared public loader.", "",
        "## Frozen grid definition", "Center: 24h rolling VWAP from 1h typical price * volume. Band: +/-3%. Arithmetic levels: 10 buys below center and 10 sells above center. Allocated capital: 30% of equity, equal quote per level. Inventory cap: abs net BTC notional <= 15% of allocated capital. Grid ON requires completed 4h ADX < 18. Grid OFF/flatten triggers on completed 4h ADX > 25 or 1h close beyond the grid band by 1.5 * 1h ATR(14).", "",
        "## Metrics", "", summary.to_markdown(index=False), "",
        "## Holdout decision", f"Holdout net={hold.net_profit_pct:.4f}%, max equity DD={hold.max_equity_dd_pct:.4f}%, grid_on_profit={hold.grid_on_profit:.2f}, flatten_pnl={hold.flatten_pnl:.2f}.", "",
        "## PASS/PAPER/KILL", result, "",
        "## Final sentence", "no automated directional or grid bot from this research program." if result == "KILL" else "Grid is not live-ready without paper execution validation.", "",
    ]
    text = "\n".join(lines) + "\n"
    with open(os.path.join(RESULTS_DIR, "RESULTS_GRID.md"), "w") as f:
        f.write(text)
    try:
        with open("RESULTS_GRID.md", "w") as f:
            f.write(text)
    except PermissionError:
        pass


def main() -> None:
    df = prepare_data()
    print(f"BAR_COUNTS 1h={len(df)} source={SYMBOL} center=24h_vwap grid_levels=20")
    events, equity_df, _ = run_backtest(df)
    summary = summarize(equity_df, events)
    result = decision(summary)
    print("\nSUMMARY")
    print(summary.to_string(index=False, float_format=lambda value: f"{value:.4f}"))
    print("\nEVENT_SAMPLE")
    print(events.head(10).to_string(index=False) if not events.empty else "no events")
    print(f"\nDECISION {result}")
    save_outputs(df, events, equity_df, summary)
    write_memo(summary, events, result)


if __name__ == "__main__":
    main()
