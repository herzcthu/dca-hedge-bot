#!/usr/bin/env python3
"""Per-symbol H1 hedge parameter search. Research only. Does not touch main.py.

Frozen book (same on every symbol and every grid point):
  USD-M 1m, Cost B, start $10,000, clip $10,000, MR cap 10%,
  range safety orders max 10 with reclaim, peak-skip 15%,
  stale exit 40% / 180d, entry TTL 1h.
  Long and short share one wallet. Short is the mirror of the long rules.

Grid (the three knobs that changed the DOGE dollar score):
  peak memory (lookback days): 30, 90, 180
  take-profit: 5%, 8%
  stop: 90%, 95% of the path from average to account liquidation

Each symbol is loaded once from the on-disk 1m cache and every grid point
runs on that same frame. Best = highest Cost B ending wallet. Train+validate
leader is recorded beside it when it is a different point. Holdout is shown
and is not used to break ties.
"""

from __future__ import annotations

import gc
import os
import time
from datetime import datetime, timezone

import pandas as pd

from experiments.dca.backtest_dca import COST_B, SPLITS
from experiments.dca.backtest_dca_alts import prepare_um
from experiments.dca.backtest_dca_hedge import account_liq, run_hedge


RESULTS = "results_dca_run_1m_so_reclaim/hedge_tune"
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT")
LOOKBACKS = (30.0, 90.0, 180.0)
TAKE_PROFITS = (0.05, 0.08)
STOPS = (0.90, 0.95)


def _usd(n: float) -> str:
    return f"${n:,.0f}"


def _specs() -> list[dict]:
    out = []
    for lookback in LOOKBACKS:
        for tp in TAKE_PROFITS:
            for sl in STOPS:
                out.append({
                    "peak_lookback_days": lookback,
                    "tp_pct": tp,
                    "sl_loss": sl,
                })
    return out


def _splits(trades: pd.DataFrame) -> dict[str, float]:
    if trades.empty:
        return {name: 0.0 for name in SPLITS}
    exit_time = pd.to_datetime(trades["exit_time"], utc=True)
    out = {}
    for name, (start, end) in SPLITS.items():
        part = trades[(exit_time >= start) & (exit_time < end)]
        out[name] = float(part.pnl_net.sum()) if len(part) else 0.0
    return out


def _sl_count(trades: pd.DataFrame) -> int:
    if trades.empty:
        return 0
    return int((trades.exit_reason == "SL").sum())


def _run_one(df: pd.DataFrame, spec: dict) -> dict:
    t0 = time.perf_counter()
    trades, rem = run_hedge(
        df,
        COST_B,
        tp_pct=spec["tp_pct"],
        sl_loss=spec["sl_loss"],
        peak_lookback_days=spec["peak_lookback_days"],
    )
    splits = _splits(trades)
    row = {
        "peak_lookback_days": spec["peak_lookback_days"],
        "tp_pct": spec["tp_pct"],
        "sl_loss": spec["sl_loss"],
        "equity": float(rem["equity"]),
        "trades": int(len(trades)),
        "sl": _sl_count(trades),
        "liquidated": bool(rem["liquidated"]),
        "train": splits["train"],
        "validate": splits["validate"],
        "holdout": splits["holdout"],
        "decision": splits["train"] + splits["validate"],
        "seconds": time.perf_counter() - t0,
    }
    del trades
    return row


def _best(rows: list[dict]) -> dict:
    return max(rows, key=lambda row: (row["equity"], row["decision"]))


def _decision_best(rows: list[dict]) -> dict:
    return max(rows, key=lambda row: (row["decision"], row["equity"]))


def _label(row: dict) -> str:
    return (
        f"memory={row['peak_lookback_days']:.0f}d  "
        f"TP={row['tp_pct'] * 100:.0f}%  SL={row['sl_loss'] * 100:.0f}%"
    )


def _write_symbol(symbol: str, rows: list[dict]) -> None:
    os.makedirs(RESULTS, exist_ok=True)
    pd.DataFrame(rows).to_csv(os.path.join(RESULTS, f"grid_{symbol}.csv"), index=False)


def _write_report(all_rows: list[dict], as_of: str) -> None:
    lines = [
        "# H1 hedge — best parameters per symbol",
        "",
        f"- Run: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"- Last bar: {as_of}",
        "- USD-M 1m from the on-disk kline cache. One load per symbol. Cost B.",
        "- Fixed: $10,000 start, $10,000 clip, 10% MR, range SO max 10, reclaim, peak-skip 15%, stale 40%/180d.",
        "- Grid: peak memory 30/90/180 days × TP 5/8% × SL 90/95% of the path to account liquidation.",
        "- Best = highest ending wallet. Ties break on train+validate dollars.",
        "- Decision = highest train+validate dollars. Shown when it is a different point. Holdout is not used to pick.",
        "",
        "| Symbol | Best memory | TP | SL | Wallet | Trades | SL n | Train | Validate | Holdout |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    notes = []
    for symbol in SYMBOLS:
        rows = [row for row in all_rows if row["symbol"] == symbol]
        if not rows:
            continue
        best = _best(rows)
        decision = _decision_best(rows)
        lines.append(
            f"| {symbol} | {best['peak_lookback_days']:.0f}d | {best['tp_pct'] * 100:.0f}% | "
            f"{best['sl_loss'] * 100:.0f}% | {_usd(best['equity'])} | {best['trades']} | {best['sl']} | "
            f"{_usd(best['train'])} | {_usd(best['validate'])} | {_usd(best['holdout'])} |"
        )
        if (decision["peak_lookback_days"], decision["tp_pct"], decision["sl_loss"]) != (
            best["peak_lookback_days"], best["tp_pct"], best["sl_loss"],
        ):
            notes.append(
                f"- {symbol} train+validate leader is {_label(decision)} "
                f"(decision {_usd(decision['decision'])}, wallet {_usd(decision['equity'])}). "
                f"Full-sample wallet leader is {_label(best)}."
            )
    lines.append("")
    lines.extend(notes)
    lines.append("")
    lines.append("## Full grid")
    lines.append("")
    lines.append("| Symbol | Memory | TP | SL | Wallet | Trades | SL n | Train | Validate | Holdout |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in all_rows:
        lines.append(
            f"| {row['symbol']} | {row['peak_lookback_days']:.0f}d | {row['tp_pct'] * 100:.0f}% | "
            f"{row['sl_loss'] * 100:.0f}% | {_usd(row['equity'])} | {row['trades']} | {row['sl']} | "
            f"{_usd(row['train'])} | {_usd(row['validate'])} | {_usd(row['holdout'])} |"
        )
    lines.append("")
    text = "\n".join(lines) + "\n"
    path = os.path.join(RESULTS, "REPORT.md")
    with open(path, "w") as handle:
        handle.write(text)
    print(text, flush=True)
    print(f"Wrote {path}", flush=True)


def _load_done(symbol: str, n_specs: int) -> list[dict] | None:
    path = os.path.join(RESULTS, f"grid_{symbol}.csv")
    if not os.path.exists(path):
        return None
    frame = pd.read_csv(path)
    if len(frame) != n_specs:
        return None
    rows = frame.to_dict("records")
    for row in rows:
        row["liquidated"] = str(row["liquidated"]).lower() == "true"
        row["trades"] = int(row["trades"])
        row["sl"] = int(row["sl"])
    return rows


def main() -> None:
    lone = account_liq(10_000.0, 1_000_000.0, 0.10, 0.0, 0.0)
    if lone is None or abs(lone - 0.09036144578) > 1e-6:
        raise RuntimeError(f"account liq drifted: {lone}")
    specs = _specs()
    all_rows: list[dict] = []
    as_of = ""
    for symbol in SYMBOLS:
        done = _load_done(symbol, len(specs))
        if done is not None:
            print(f"H1 tune  {symbol}  reuse {len(done)} cached grid rows", flush=True)
            all_rows.extend(done)
            continue
        print(f"H1 tune  {symbol} 1m  loading cached klines...", flush=True)
        df = prepare_um(symbol, "1m")
        as_of = str(df.iloc[-1].close_time)
        print(f"  bars={len(df)}  {df.iloc[0].open_time} → {as_of}  specs={len(specs)}", flush=True)
        rows = []
        for spec in specs:
            row = _run_one(df, spec)
            row["symbol"] = symbol
            rows.append(row)
            print(
                f"  {_label(row)}  {_usd(10_000)} → {_usd(row['equity'])}  "
                f"n={row['trades']} sl={row['sl']}  decision={_usd(row['decision'])}  "
                f"{row['seconds']:.0f}s",
                flush=True,
            )
            _write_symbol(symbol, rows)
        _write_symbol(symbol, rows)
        all_rows.extend(rows)
        _write_report(all_rows, as_of)
        del df
        gc.collect()


if __name__ == "__main__":
    main()
