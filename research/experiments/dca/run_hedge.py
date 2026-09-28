#!/usr/bin/env python3
"""H1 hedge backtest: DOGEUSDT long and short, one wallet.

Frozen vs the long winner: 1m, $10k start, $10k clip per side, 10% MR,
range SOs (max 10) with reclaim, TP 8%, SL 95% of the path to account
liquidation, peak-skip 15% / 180d on the combined wallet, 1h entry TTL.
Short uses the mirrored filters. Research only.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pandas as pd

from experiments.dca.backtest_dca import COST_B, SPLITS
from experiments.dca.backtest_dca_alts import prepare_um
from experiments.dca.backtest_dca_hedge import account_liq, run_hedge


RESULTS = "results_dca_run_1m_so_reclaim/hedge"
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT")


def _usd(n: float) -> str:
    return f"${n:,.0f}"


def _side_stats(trades: pd.DataFrame, side: str) -> tuple[int, int, float]:
    if trades.empty:
        return 0, 0, 0.0
    part = trades[trades.side == side]
    if part.empty:
        return 0, 0, 0.0
    sl = int((part.exit_reason == "SL").sum())
    return len(part), sl, float(part.pnl_net.sum())


def _one(symbol: str) -> dict:
    print(f"H1 hedge  {symbol} 1m  loading klines...", flush=True)
    df = prepare_um(symbol, "1m")
    print(f"  bars={len(df)}  {df.iloc[0].open_time} → {df.iloc[-1].close_time}", flush=True)
    trades, rem = run_hedge(df, COST_B)
    del df
    os.makedirs(RESULTS, exist_ok=True)
    trades.to_csv(os.path.join(RESULTS, f"trades_{symbol}.csv"), index=False)
    ln, lsl, lp = _side_stats(trades, "long")
    sn, ssl, sp = _side_stats(trades, "short")
    splits = {}
    if not trades.empty:
        trades = trades.copy()
        trades["exit_time"] = pd.to_datetime(trades["exit_time"], utc=True)
        for name, (a, b) in SPLITS.items():
            part = trades[(trades.exit_time >= a) & (trades.exit_time < b)]
            splits[name] = float(part.pnl_net.sum()) if len(part) else 0.0
    else:
        splits = {name: 0.0 for name in SPLITS}
    row = {
        "symbol": symbol,
        "equity": float(rem["equity"]),
        "liquidated": bool(rem["liquidated"]),
        "as_of": rem["as_of"],
        "long_n": ln,
        "long_sl": lsl,
        "long_pnl": lp,
        "short_n": sn,
        "short_sl": ssl,
        "short_pnl": sp,
        "trades": ln + sn,
        "open_long": float(rem["long_upnl"]),
        "open_short": float(rem["short_upnl"]),
        "splits": splits,
    }
    print(
        f"  {symbol} {_usd(10_000)} → {_usd(row['equity'])}  "
        f"long {ln}/{lsl} {_usd(lp)}  short {sn}/{ssl} {_usd(sp)}",
        flush=True,
    )
    return row


def main() -> None:
    lone = account_liq(10_000.0, 1_000_000.0, 0.10, 0.0, 0.0)
    if lone is None or abs(lone - 0.09036144578) > 1e-6:
        raise RuntimeError(f"account liq drifted: {lone}")
    short_only = account_liq(10_000.0, 0.0, 0.0, 1_000_000.0, 0.10)
    if short_only is None or short_only <= 0.10:
        raise RuntimeError(f"short liq drifted: {short_only}")

    rows = [_one(symbol) for symbol in SYMBOLS]
    as_of = rows[-1]["as_of"]
    lines = [
        "# H1 hedge — long and short, one wallet",
        "",
        f"- Run: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"- Last bar: {as_of}",
        "- USD-M 1m. Cost B. One shared $10,000 wallet per symbol.",
        "- Each new basket sizes off min($10,000, marked equity).",
        "- Long: range SO, reclaim, TP 8%, peak-skip 15%/180d.",
        "- Short is the mirror: below EMA55, not the 7d bottom quartile, SOs up to the frozen 7d high.",
        "- SL is 95% of the way to the account liquidation price. Only the threatened side is stopped.",
        "- Funding placeholder 0.01% per 8h: long pays, short receives.",
        "",
        "| Symbol | Wallet | Trades | Long n / SL / PnL | Short n / SL / PnL | Train | Validate | Holdout |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['symbol']} | {_usd(row['equity'])} | {row['trades']} | "
            f"{row['long_n']} / {row['long_sl']} / {_usd(row['long_pnl'])} | "
            f"{row['short_n']} / {row['short_sl']} / {_usd(row['short_pnl'])} | "
            f"{_usd(row['splits']['train'])} | {_usd(row['splits']['validate'])} | {_usd(row['splits']['holdout'])} |"
        )
    lines.append("")
    for row in rows:
        lines.append(
            f"- {row['symbol']} open uPnL long={_usd(row['open_long'])} short={_usd(row['open_short'])} "
            f"liquidated={row['liquidated']}"
        )
    text = "\n".join(lines) + "\n"
    path = os.path.join(RESULTS, "REPORT.md")
    os.makedirs(RESULTS, exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    print(text, flush=True)
    print(f"Wrote {path}", flush=True)


if __name__ == "__main__":
    main()
