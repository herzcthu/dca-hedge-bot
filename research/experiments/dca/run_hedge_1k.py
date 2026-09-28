#!/usr/bin/env python3
"""H1 hedge with a fixed $1,000 clip. Research only. Not main.py.

Frozen spec: start $1,000, clip $1,000, no step-up. An order sizes off
min(clip, wallet). Everything else is that symbol's recorded 1m hedge
in experiments.dca.best_params. Cost B.
"""

from __future__ import annotations

import gc
import os
from datetime import datetime, timezone

import pandas as pd

from experiments.dca.backtest_dca import COST_B, SPLITS
from experiments.dca.backtest_dca_alts import prepare_um
from experiments.dca.backtest_dca_hedge import account_liq, run_hedge
from experiments.dca.best_params import HEDGE_1M


START = 1_000.0
RESULTS = "results_dca_run_1m_so_reclaim/hedge_1k"
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT")
_SL_REASONS = {"SL", "SL50", "HARD"}


def _check() -> None:
    lone = account_liq(10_000.0, 1_000_000.0, 0.10, 0.0, 0.0)
    if lone is None or abs(lone - 0.09036144578) > 1e-6:
        raise RuntimeError(f"account liq drifted: {lone}")


def _usd(n: float) -> str:
    sign = "-" if n < 0 else ""
    return f"{sign}${abs(n):,.0f}"


def _qty(symbol: str, qty: float) -> str:
    asset = symbol.replace("USDT", "")
    text = f"{qty:,.2f}" if qty >= 1 else f"{qty:.6f}"
    return f"{text} {asset}"


def _counts(trades: pd.DataFrame) -> dict[str, int]:
    if trades.empty:
        return {"n": 0, "tp": 0, "sl": 0, "liq": 0, "saved": 0, "cut_tp": 0}
    reasons = trades["exit_reason"]
    hold = trades["sl_hold"] if "sl_hold" in trades.columns else pd.Series("", index=trades.index)
    sl = reasons.isin(_SL_REASONS)
    return {
        "n": int((reasons != "MTM").sum()),
        "tp": int((reasons == "TP").sum()),
        "sl": int(sl.sum()),
        "liq": int((reasons == "LIQUIDATION").sum()),
        "saved": int((sl & (hold == "liq")).sum()),
        "cut_tp": int((sl & (hold == "tp")).sum()),
    }


def _splits(trades: pd.DataFrame) -> dict[str, float]:
    if trades.empty:
        return {name: 0.0 for name in SPLITS}
    frame = trades.copy()
    frame["exit_time"] = pd.to_datetime(frame["exit_time"], utc=True)
    out = {}
    for name, (a, b) in SPLITS.items():
        part = frame[(frame.exit_time >= a) & (frame.exit_time < b)]
        out[name] = float(part.pnl_net.sum()) if len(part) else 0.0
    return out


def _open_txt(symbol: str, rem: dict) -> str:
    bits = []
    if rem["long_qty"] > 0:
        bits.append(f"{_qty(symbol, rem['long_qty'])} long ({_usd(float(rem['long_upnl']))})")
    if rem["short_qty"] > 0:
        bits.append(f"{_qty(symbol, rem['short_qty'])} short ({_usd(float(rem['short_upnl']))})")
    return ", ".join(bits) if bits else "—"


def _one(symbol: str) -> dict:
    spec = HEDGE_1M[symbol]
    print(
        f"H1 1k  {symbol}  memory={spec['peak_lookback_days']}d  "
        f"TP={spec['tp_pct']}  SL={spec['sl_loss']}  start={START:.0f}",
        flush=True,
    )
    df = prepare_um(symbol, spec["interval"])
    print(f"  bars={len(df)}  {df.iloc[0].open_time} → {df.iloc[-1].close_time}", flush=True)
    trades, rem = run_hedge(
        df,
        COST_B,
        start_equity=START,
        clip=START,
        tp_pct=spec["tp_pct"],
        sl_loss=spec["sl_loss"],
        peak_lookback_days=spec["peak_lookback_days"],
        peak_skip_pct=spec["peak_skip_pct"],
    )
    del df
    gc.collect()
    os.makedirs(RESULTS, exist_ok=True)
    trades.to_csv(os.path.join(RESULTS, f"trades_{symbol}.csv"), index=False)
    counts = _counts(trades)
    splits = _splits(trades)
    row = {
        "symbol": symbol,
        "spec": spec,
        "rem": rem,
        "counts": counts,
        "splits": splits,
        "open": _open_txt(symbol, rem),
    }
    print(
        f"  {symbol} {_usd(START)} → {_usd(float(rem['equity']))}  "
        f"TP {counts['tp']}  SL {counts['sl']}  liq {counts['liq']}",
        flush=True,
    )
    return row


def _report(rows: list[dict]) -> str:
    lines = [
        "# Isolated DCA — start vs end",
        "",
        f"- Run: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "- Window: 2024-01-08 through each symbol's last cached bar on 2026-09-28",
        "- Start: $1,000. Clip: $1,000 fixed. No step-up.",
        "- MR cap: 10%   SL: from each symbol's recorded hedge, as a fraction of the path from avg to account liquidation",
        "- Safety orders: range (7d range rungs; freeze 7d low at first fill; no SO if 7d low expands >2% or 12h support breaks; next SO only after close reclaims 21h EMA); max 10 SOs",
        "- Bar: 1m (one fill per bar; EMA/swing still 21h / 55h / 12h)",
        "- Entry TTL: cancel unfilled base after 1h. Safety orders keep working.",
        "- Stale bag: flatten if still ≥40% adverse after 180d",
        "- Book: hedge, long and short, one wallet. Each symbol uses its recorded memory, TP, and SL.",
        "- Possible liq = SL fired and holding that basket would have liquidated before TP",
        "- SL cut TP = stop fired and that basket would have hit TP if held",
        "- Idle = cash. Open basket = unrealized P&L of whatever is still open.",
        "- Wallet = Idle + Open. Not a taker flatten.",
        "- Trades = Cost B closed baskets. Open mark is not a trade. SL is the price stop only.",
        "",
        "## USD-M (USDT)",
        "",
        "| Asset | Start | Idle | Open basket | Wallet | Trades | TP | SL | Liq | Possible liq | SL cut TP |",
        "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        asset = row["symbol"].replace("USDT", "")
        rem = row["rem"]
        counts = row["counts"]
        lines.append(
            f"| {asset} | {_usd(START)} | {_usd(float(rem['cash']))} | {row['open']} | "
            f"{_usd(float(rem['equity']))} | {counts['n']} | {counts['tp']} | {counts['sl']} | "
            f"{counts['liq']} | {counts['saved']} | {counts['cut_tp']} |"
        )
    lines += [
        "",
        "## Closed-trade net by split",
        "",
        "| Asset | Memory | TP | SL | Train | Validate | Holdout |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        asset = row["symbol"].replace("USDT", "")
        spec = row["spec"]
        splits = row["splits"]
        lines.append(
            f"| {asset} | {spec['peak_lookback_days']:.0f}d | {spec['tp_pct'] * 100:.0f}% | "
            f"{spec['sl_loss'] * 100:.0f}% | {_usd(splits['train'])} | {_usd(splits['validate'])} | "
            f"{_usd(splits['holdout'])} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    _check()
    rows = [_one(symbol) for symbol in SYMBOLS]
    text = _report(rows)
    os.makedirs(RESULTS, exist_ok=True)
    path = os.path.join(RESULTS, "REPORT.md")
    with open(path, "w") as handle:
        handle.write(text)
    print(text, flush=True)
    print(f"Wrote {path}", flush=True)


if __name__ == "__main__":
    main()
