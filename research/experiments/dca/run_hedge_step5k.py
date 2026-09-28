#!/usr/bin/env python3
"""H1 hedge, clip follows the wallet in $5,000 steps. Research only.

Frozen spec: start $1,000. Below $5,000 the clip stays $1,000. At each
$5,000 the clip becomes that step ($5,000, $10,000, $15,000, ...), which
is the wallet size at the boundary. A smaller wallet steps the clip back
down the same ladder. An order sizes off min(clip, wallet). Same recorded
1m hedge per symbol. Stale is 180 days. Cost B.
"""

from __future__ import annotations

import gc
import os
from datetime import datetime, timezone

import pandas as pd

from experiments.dca.backtest_dca import COST_B, SPLITS
from experiments.dca.backtest_dca_alts import prepare_um
from experiments.dca.backtest_dca_hedge import account_liq, run_hedge, step_wallet_clip
from experiments.dca.best_params import HEDGE_1M


START = 1_000.0
STEP = 5_000.0
RESULTS = "results_dca_run_1m_so_reclaim/hedge_step5k"
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT")
_SL_REASONS = {"SL", "SL50", "HARD"}


def _check() -> None:
    lone = account_liq(10_000.0, 1_000_000.0, 0.10, 0.0, 0.0)
    if lone is None or abs(lone - 0.09036144578) > 1e-6:
        raise RuntimeError(f"account liq drifted: {lone}")
    if step_wallet_clip(4_000, START, STEP) != START:
        raise RuntimeError("below $5,000 the clip stays at the start")
    if step_wallet_clip(5_000, START, STEP) != 5_000:
        raise RuntimeError("at $5,000 the clip becomes the wallet")
    if step_wallet_clip(12_000, START, STEP) != 10_000:
        raise RuntimeError("between steps the clip stays on the last $5,000")
    if step_wallet_clip(7_000, START, STEP) != 5_000:
        raise RuntimeError("a shrink from $12,000 to $7,000 returns the $5,000 clip")


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
        f"H1 step5k  {symbol}  memory={spec['peak_lookback_days']}d  "
        f"TP={spec['tp_pct']}  SL={spec['sl_loss']}",
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
        clip_step_usd=STEP,
    )
    del df
    gc.collect()
    os.makedirs(RESULTS, exist_ok=True)
    trades.to_csv(os.path.join(RESULTS, f"trades_{symbol}.csv"), index=False)
    counts = _counts(trades)
    row = {
        "symbol": symbol,
        "spec": spec,
        "rem": rem,
        "counts": counts,
        "splits": _splits(trades),
        "open": _open_txt(symbol, rem),
    }
    print(
        f"  {symbol} {_usd(START)} → {_usd(float(rem['equity']))}  "
        f"clip {_usd(float(rem['clip']))}  downs {rem['clip_downs']}  "
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
        "- Start: $1,000. Clip starts at $1,000.",
        "- Sizing: every $5,000 of wallet, the clip becomes that step. $5,000 wallet sizes off $5,000. $12,000 sizes off $10,000. $15,000 sizes off $15,000.",
        "- If the wallet shrinks, the clip steps down the same $5,000 ladder. Under $5,000 it is $1,000 again.",
        "- An order uses min(clip, wallet). MR cap 10% of that amount.",
        "- SL, memory, and TP are each symbol's recorded hedge. Stale: 40% adverse after 180d.",
        "- Safety orders: range, max 10, reclaim. Bar: 1m. Entry TTL: 1h.",
        "- Possible liq = SL fired and holding that basket would have liquidated before TP",
        "- SL cut TP = stop fired and that basket would have hit TP if held",
        "- Idle = cash. Open basket = unrealized P&L of whatever is still open.",
        "- Wallet = Idle + Open. Not a taker flatten. SL is the price stop only.",
        "",
        "## USD-M (USDT)",
        "",
        "| Asset | Start | Final clip | Idle | Open basket | Wallet | Trades | TP | SL | Liq | Possible liq | SL cut TP |",
        "|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        asset = row["symbol"].replace("USDT", "")
        rem = row["rem"]
        counts = row["counts"]
        lines.append(
            f"| {asset} | {_usd(START)} | {_usd(float(rem['clip']))} | {_usd(float(rem['cash']))} | "
            f"{row['open']} | {_usd(float(rem['equity']))} | {counts['n']} | {counts['tp']} | "
            f"{counts['sl']} | {counts['liq']} | {counts['saved']} | {counts['cut_tp']} |"
        )
    lines += [
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
