#!/usr/bin/env python3
"""F6/G1 twin on ETH, DOGE, SOL — USD-M and Coin-M.

Same frozen rules: 1% MR, SL80, $10k USD clip. USD-M starts with $10,000 USDT.
Coin-M starts with $10,000 of the coin. F6/G1 BTC are not retuned.
Not a scalp; do not wire into main.py.
"""

from __future__ import annotations

import os

import pandas as pd

from experiments.dca import coinm_data, um_data
from experiments.dca.backtest_dca import START_EQUITY, add_dca_features, run_suite
from experiments.dca.backtest_dca_coinm import run_coinm_suite


ASSETS = (
    ("BTC", "BTCUSDT", "BTCUSD_PERP"),
    ("ETH", "ETHUSDT", "ETHUSD_PERP"),
    ("DOGE", "DOGEUSDT", "DOGEUSD_PERP"),
    ("SOL", "SOLUSDT", "SOLUSD_PERP"),
)
RESULTS_ROOT = "results_dca_alts"


def prepare_um(symbol: str, interval: str = "1h") -> pd.DataFrame:
    try:
        df = um_data.load_klines(symbol, interval).copy()
    except RuntimeError:
        if symbol != "BTCUSDT":
            raise
        from experiments.htf.data import load_klines as load_btc
        df = load_btc(interval).copy()
    return add_dca_features(df, interval)


def _b(remaining: pd.DataFrame) -> pd.Series:
    return remaining[remaining.cost_model == "B_decision"].iloc[0]


def main(isolated: bool = False, results_root: str = RESULTS_ROOT) -> None:
    os.makedirs(results_root, exist_ok=True)
    rows = []
    for asset, um_symbol, cm_symbol in ASSETS:
        print(f"\n===== USD-M {um_symbol} isolated={isolated} =====")
        um_dir = os.path.join(results_root, f"{asset}_um")
        um_df = prepare_um(um_symbol)
        rem_um, _ = run_suite(
            mr_cap=0.01,
            product=f"F6_{asset}_um" + ("_iso" if isolated else ""),
            results_dir=um_dir,
            tag=f"{asset}_um",
            memo_name=f"RESULTS_{asset}_UM.md",
            equity_stop_frac=0.20,
            size_equity=START_EQUITY,
            df=um_df,
            market_label=um_symbol,
            write_root_memo=False,
            isolated=isolated,
        )
        b = _b(rem_um)
        rows.append({
            "asset": asset, "venue": "USD-M", "symbol": um_symbol,
            "as_of": b.as_of, "mark": float(b.btc_close),
            "liquidated": bool(b.liquidated), "in_position": bool(b.in_position),
            "start_usd": float(b.start_equity_usdt),
            "remaining_usd": float(b.if_flatten_today_usdt),
            "remaining_usd_mark": float(b.remaining_mark_usdt),
            "start_coin": float("nan"), "remaining_coin": float("nan"),
            "coin_multiple": float("nan"),
            "usd_multiple": float(b.if_flatten_today_usdt) / float(b.start_equity_usdt),
            "buy_hold_usd": float("nan"),
        })

        print(f"\n===== Coin-M {cm_symbol} isolated={isolated} =====")
        cm_dir = os.path.join(results_root, f"{asset}_coinm")
        cs = coinm_data.contract_size(cm_symbol)
        rem_cm, _, start_coin = run_coinm_suite(
            symbol=cm_symbol,
            contract_size=cs,
            results_dir=cm_dir,
            product=f"G1_{asset}_coinm" + ("_iso" if isolated else ""),
            tag=f"{asset}_cm",
            write_root_memo=False,
            isolated=isolated,
        )
        c = _b(rem_cm)
        start_c = float(c.start_coin) if "start_coin" in c.index else start_coin
        rem_c = float(c.remaining_coin) if "remaining_coin" in c.index else float(c.remaining_btc)
        rows.append({
            "asset": asset, "venue": "Coin-M", "symbol": cm_symbol,
            "as_of": c.as_of, "mark": float(c.btc_close),
            "liquidated": bool(c.liquidated), "in_position": bool(c.in_position),
            "start_usd": float(c.start_equity_usdt),
            "remaining_usd": float(c.if_flatten_today_usdt),
            "remaining_usd_mark": float(c.remaining_mark_usdt),
            "start_coin": start_c, "remaining_coin": rem_c,
            "coin_multiple": rem_c / start_c if start_c else float("nan"),
            "usd_multiple": float(c.if_flatten_today_usdt) / float(c.start_equity_usdt),
            "buy_hold_usd": float(c.buy_hold_usdt),
        })

    comparison = pd.DataFrame(rows)
    path = os.path.join(results_root, "comparison.csv")
    comparison.to_csv(path, index=False)
    print("\n===== COMPARISON Cost B flatten-today =====")
    print(comparison.to_string(index=False))
    memo = os.path.join(results_root, "RESULTS_DCA_ALTS.md")
    with open(memo, "w") as f:
        f.write("# ETH / DOGE / SOL F6+G1 twins\n\n")
        f.write("Same 1% MR, SL80, frozen $10k USD clip as BTC F6 / G1. ")
        f.write("USD-M remaining is USDT. Coin-M remaining is coin plus USD mark. ")
        f.write(f"Margin mode: {'isolated' if isolated else 'cross (shared wallet)'}. ")
        f.write("Do not wire into main.py.\n\n")
        f.write(comparison.to_markdown(index=False, floatfmt=".6f"))
        f.write("\n")
    root_name = "RESULTS_DCA_ALTS_ISO.md" if isolated else "RESULTS_DCA_ALTS.md"
    try:
        with open(root_name, "w") as f:
            with open(memo) as src:
                f.write(src.read())
    except PermissionError:
        pass


if __name__ == "__main__":
    main()
