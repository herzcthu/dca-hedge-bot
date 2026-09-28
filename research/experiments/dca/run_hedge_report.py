#!/usr/bin/env python3
"""Full Cost B report for one hedge symbol, using experiments.dca.best_params."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pandas as pd

from experiments.dca.backtest_dca import COST_B
from experiments.dca.backtest_dca_alts import prepare_um
from experiments.dca.backtest_dca_hedge import account_liq, run_hedge
from experiments.dca.best_params import HEDGE_1M


SYMBOL = "SOLUSDT"
OUT = "results_dca_run_1m_so_reclaim/hedge_sol"


def _usd(n: float) -> str:
    sign = "-" if n < 0 else ""
    return f"{sign}${abs(n):,.0f}"


_SL_REASONS = {"SL", "SL50", "HARD"}


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


def main() -> None:
    lone = account_liq(10_000.0, 1_000_000.0, 0.10, 0.0, 0.0)
    if lone is None or abs(lone - 0.09036144578) > 1e-6:
        raise RuntimeError(f"account liq drifted: {lone}")
    spec = HEDGE_1M[SYMBOL]
    print(f"H1 report  {SYMBOL}  memory={spec['peak_lookback_days']}d  TP={spec['tp_pct']}  SL={spec['sl_loss']}", flush=True)
    df = prepare_um(SYMBOL, spec["interval"])
    print(f"  bars={len(df)}  {df.iloc[0].open_time} → {df.iloc[-1].close_time}", flush=True)
    trades, rem = run_hedge(
        df,
        COST_B,
        tp_pct=spec["tp_pct"],
        sl_loss=spec["sl_loss"],
        peak_lookback_days=spec["peak_lookback_days"],
        peak_skip_pct=spec["peak_skip_pct"],
    )
    del df
    os.makedirs(OUT, exist_ok=True)
    trades.to_csv(os.path.join(OUT, "trades.csv"), index=False)

    counts = _counts(trades)
    open_bits = []
    if rem["long_qty"] > 0:
        open_bits.append(f"{rem['long_qty']:,.2f} SOL long ({_usd(float(rem['long_upnl']))})")
    if rem["short_qty"] > 0:
        open_bits.append(f"{rem['short_qty']:,.2f} SOL short ({_usd(float(rem['short_upnl']))})")
    open_txt = ", ".join(open_bits) if open_bits else "—"
    lines = [
        "# Isolated DCA — start vs end",
        "",
        f"- Run: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"- Last bar: {rem['as_of']}",
        "- Isolated wallet / clip: $10,000",
        "- MR cap: 10%   SL: 90% of the path from avg to account liquidation",
        "- Safety orders: range (7d range rungs; freeze 7d low at first fill; no SO if 7d low expands >2% or 12h support breaks; next SO only after close reclaims 21h EMA); max 10 SOs",
        f"- Bar: {spec['interval']} (one fill per bar; EMA/swing still 21h / 55h / 12h)",
        "- Entry TTL: cancel unfilled base after 1h. Safety orders keep working.",
        f"- Take-profit: {spec['tp_pct'] * 100:.0f}% from average entry",
        f"- Peak brake: no new basket while wallet is ≥{spec['peak_skip_pct'] * 100:.0f}% under the {spec['peak_lookback_days']:.0f}d rolling marked-wallet high",
        "- Stale bag: flatten if still ≥40% adverse after 180d",
        "- Book: hedge, long and short, one wallet. SOLUSDT.",
        f"- Possible liq = SL fired and holding that basket would have liquidated before +{spec['tp_pct'] * 100:.0f}% TP",
        "- SL cut TP = stop fired and that basket would have hit TP if held",
        "- Idle = cash. Open basket = unrealized P&L of whatever is still open.",
        "- Wallet = Idle + Open. Not a taker flatten.",
        "- Trades = Cost B closed baskets. Open mark is not a trade.",
        "",
        "## USD-M (USDT)",
        "",
        "| Asset | Start | Idle | Open basket | Wallet | Trades | TP | SL | Liq | Possible liq | SL cut TP |",
        "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|",
        f"| SOL | $10,000 | {_usd(float(rem['cash']))} | {open_txt} | {_usd(float(rem['equity']))} | "
        f"{counts['n']} | {counts['tp']} | {counts['sl']} | {counts['liq']} | {counts['saved']} | {counts['cut_tp']} |",
        "",
    ]
    text = "\n".join(lines) + "\n"
    path = os.path.join(OUT, "REPORT.md")
    with open(path, "w") as handle:
        handle.write(text)
    print(text, flush=True)
    print(f"Wrote {path}", flush=True)


if __name__ == "__main__":
    main()
