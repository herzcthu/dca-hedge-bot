#!/usr/bin/env python3
"""H1 hedge, clip follows the wallet's triple level. Research only.

Frozen spec: start $1,000, initial clip $1,000. Each triple of the
start ($3,000, $9,000, $27,000, ...) multiplies the clip by 1.10.
A doubled wallet does not step. If the wallet falls, the clip steps
down to the level that wallet still clears, not back to $1,000 unless
the wallet is under $3,000. An order sizes off min(clip, wallet).
Same recorded 1m hedge per symbol. Cost B.
"""

from __future__ import annotations

import gc
import os
from datetime import datetime, timezone

import pandas as pd

from experiments.dca.backtest_dca import COST_B, SPLITS
from experiments.dca.backtest_dca_alts import prepare_um
from experiments.dca.backtest_dca_hedge import account_liq, grow_clip, run_hedge
from experiments.dca.best_params import HEDGE_1M


START = 1_000.0
GROWS = (0.10,)
RESULTS = "results_dca_run_1m_so_reclaim/hedge_grow10"
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT")
_SL_REASONS = {"SL", "SL50", "HARD"}


def _check() -> None:
    lone = account_liq(10_000.0, 1_000_000.0, 0.10, 0.0, 0.0)
    if lone is None or abs(lone - 0.09036144578) > 1e-6:
        raise RuntimeError(f"account liq drifted: {lone}")
    if grow_clip(2_000, 1_000, 0.10) != (1_000, 1_000):
        raise RuntimeError("2× wallet must not step the clip")
    if grow_clip(3_000, 1_000, 0.10) != (3_000, 1_100):
        raise RuntimeError("10% grow at the first triple")
    if grow_clip(9_000, 1_000, 0.10) != (9_000, 1_210):
        raise RuntimeError("10% grow at the second triple")
    if grow_clip(4_000, 1_000, 0.10) != (3_000, 1_100):
        raise RuntimeError("a $4,000 wallet stays on the $3,000 clip")


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


def _one(symbol: str, df: pd.DataFrame, grow: float) -> dict:
    spec = HEDGE_1M[symbol]
    print(
        f"H1 grow {grow:.0%}  {symbol}  memory={spec['peak_lookback_days']}d  "
        f"TP={spec['tp_pct']}  SL={spec['sl_loss']}",
        flush=True,
    )
    trades, rem = run_hedge(
        df,
        COST_B,
        start_equity=START,
        clip=START,
        tp_pct=spec["tp_pct"],
        sl_loss=spec["sl_loss"],
        peak_lookback_days=spec["peak_lookback_days"],
        peak_skip_pct=spec["peak_skip_pct"],
        clip_grow=grow,
    )
    tag = f"g{int(round(grow * 100))}"
    os.makedirs(RESULTS, exist_ok=True)
    trades.to_csv(os.path.join(RESULTS, f"trades_{symbol}_{tag}.csv"), index=False)
    counts = _counts(trades)
    row = {
        "symbol": symbol,
        "grow": grow,
        "spec": spec,
        "rem": rem,
        "counts": counts,
        "splits": _splits(trades),
        "open": _open_txt(symbol, rem),
    }
    print(
        f"  {symbol} {_usd(START)} → {_usd(float(rem['equity']))}  "
        f"clip {_usd(float(rem['clip']))}  changes {rem['clip_steps']}  downs {rem['clip_downs']}  "
        f"TP {counts['tp']}  SL {counts['sl']}  liq {counts['liq']}",
        flush=True,
    )
    return row


def _section(rows: list[dict], grow: float) -> list[str]:
    lines = [
        f"## Clip +{grow:.0%} at each triple",
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
    return lines


def _report(rows: list[dict]) -> str:
    lines = [
        "# Isolated DCA — start vs end",
        "",
        f"- Run: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "- Window: 2024-01-08 through each symbol's last cached bar on 2026-09-28",
        "- Start: $1,000. Initial clip: $1,000.",
        "- Sizing: the clip grows 10% at each triple of the starting wallet. A doubled wallet stays on the old clip.",
        "- If the wallet falls, the clip steps down to the triple that wallet still clears. A $4,000 wallet uses the $3,000 clip ($1,100), not the original $1,000.",
        "- An order uses min(clip, wallet). The 10% margin cap is applied to that amount, same as day one.",
        "- Levels, +10%: $1,000 below $3,000. $1,100 from $3,000. $1,210 from $9,000. $1,331 from $27,000.",
        "- MR cap: 10%. SL, memory, and TP are each symbol's recorded hedge.",
        "- Safety orders: range, max 10, reclaim. Bar: 1m. Entry TTL: 1h. Stale: 40% adverse after 180d.",
        "- Possible liq = SL fired and holding that basket would have liquidated before TP",
        "- SL cut TP = stop fired and that basket would have hit TP if held",
        "- Idle = cash. Open basket = unrealized P&L of whatever is still open.",
        "- Wallet = Idle + Open. Not a taker flatten. SL is the price stop only.",
        "",
    ]
    for grow in GROWS:
        lines.extend(_section([row for row in rows if row["grow"] == grow], grow))
    return "\n".join(lines) + "\n"


def main() -> None:
    _check()
    rows: list[dict] = []
    for symbol in SYMBOLS:
        spec = HEDGE_1M[symbol]
        print(f"load {symbol} {spec['interval']}", flush=True)
        df = prepare_um(symbol, spec["interval"])
        print(f"  bars={len(df)}  {df.iloc[0].open_time} → {df.iloc[-1].close_time}", flush=True)
        for grow in GROWS:
            rows.append(_one(symbol, df, grow))
        del df
        gc.collect()
    text = _report(rows)
    os.makedirs(RESULTS, exist_ok=True)
    path = os.path.join(RESULTS, "REPORT.md")
    with open(path, "w") as handle:
        handle.write(text)
    print(text, flush=True)
    print(f"Wrote {path}", flush=True)


if __name__ == "__main__":
    main()
