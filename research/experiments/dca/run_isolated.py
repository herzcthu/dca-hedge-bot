#!/usr/bin/env python3
"""Isolated DCA backtest runner — edit CONFIG, then run.

Each symbol is its own $START_USD wallet (isolated). USD-M reports USDT.
Coin-M starts as $START_USD of that coin and reports coin + USD.

SO_STYLE:
  geometric — F6 ladder (1%×1.15^n vs last fill, 1.25^n size). Frozen F6 default.
  range — skip new basket in the top 25% of the last 7d range, or if 7d low
    is <6% under close. SOs split the remaining gap to that 7d low (not 1% steps).
    Size = leftover MR / remaining SO slots.

Not a scalp. Live bot is main.py; this runner does not stop it.
Use: docker compose --profile backtest run --rm --no-deps dca-backtest
"""

from __future__ import annotations

import csv
import os
import sys
from datetime import datetime, timezone

from experiments.dca import coinm_data
from experiments.dca.backtest_dca import SO_GEOMETRIC, SO_RANGE, run_suite
from experiments.dca.backtest_dca_alts import _b, prepare_um
from experiments.dca.backtest_dca_coinm import run_coinm_suite


# ---------------------------------------------------------------------------
# CONFIG — baseline first, then per-coin overlays
# ---------------------------------------------------------------------------
# Baseline = run on a new coin with no history. Cost B so far: $10k clip, 1% MR,
# range SOs, +5% TP, 90%-to-liq SL, 1m, 1h entry TTL, freeze 7d low at first fill,
# no SO if that low expands or 12h support breaks, next SO only after 21h EMA reclaim.
# Keep +5% TP in the baseline. Do not raise TP to "protect" a run. Do not put
# peak-halt / max-2-SO / hard-20% here (coin overlays after their own Cost B).
#
# ASSET_TUNE keys match ASSETS[0]. Safe overlays: tp_pct, range_so_max,
# range_weight_size, peak_skip_pct, peak_lookback_days, sl_cooldown_days,
# sl_high_reclaim, after_sl_clip, price_dd_skip_pct, price_dd_lookback_days,
# sl_dump_lookback_days, after_tp_dump, after_tp_giveback_pct,
# giveup_pct, giveup_days, hard_sl_pct.
# Nested um / coinm dicts apply to one venue only. Leave MR_CAP / SL_LOSS /
# SO_STYLE / stale / entry TTL on the baseline unless that coin's Cost B says otherwise.
# COMPARE_BASELINE runs the same coin twice (baseline vs overlay) so REPORT.md
# shows the wallet difference. Coins with {} stay baseline-only.

# Set TUNE_ASSET to one name to skip the other coins. None = all ASSETS.
# SWEEP is extra overlays for that coin (baseline is always included).
# Example: TUNE_ASSET = "DOGE" then docker compose --profile backtest run --rm --no-deps dca-backtest
# Or: python -m experiments.dca.run_isolated DOGE

ASSETS = [
    ("BTC", "BTCUSDT", "BTCUSD_PERP"),
    ("ETH", "ETHUSDT", "ETHUSD_PERP"),
    ("DOGE", "DOGEUSDT", "DOGEUSD_PERP"),
    ("SOL", "SOLUSDT", "SOLUSD_PERP"),
]

TUNE_ASSET = "DOGE"  # None = all four coins; "DOGE" to sweep one

# 20d peak lookback vs 30d (reference) and the live 180d overlay.
SWEEP: list[dict] = [
    {"peak_skip_pct": 0.15, "peak_lookback_days": 20},
    {
        "peak_skip_pct": 0.15,
        "peak_lookback_days": 20,
        "sl_loss": 0.95,
        "tp_pct": 0.08,
    },
    {"peak_skip_pct": 0.15, "peak_lookback_days": 30},
]

# Cost B sources for overlays:
# - BTC USD-M ~$20k: 1h geometric SOs, F6 clip-dollar SL80, +5% TP (USD-M only).
# - SOL USD-M ~$25k: 5m range without dump/reclaim (TTL live-twin).
# - DOGE / ETH Coin-M: peak_skip 15% (keeps the TP pile).
ASSET_TUNE: dict[str, dict] = {
    "BTC": {
        "um": {
            "so_style": SO_GEOMETRIC,
            "interval": "1h",
            "sl_from_liq": False,
            "sl_loss": 0.90,
        },
    },
    "ETH": {"coinm": {"peak_skip_pct": 0.15}},
    "DOGE": {
        "um": {
            "peak_skip_pct": 0.15,
            "peak_lookback_days": 180,
            "sl_loss": 0.95,
            "tp_pct": 0.08,
        },
        "coinm": {"peak_skip_pct": 0.15, "peak_lookback_days": 30},
    },
    "SOL": {"so_reclaim": False},
}
COMPARE_BASELINE = True

START_USD = 10_000.0          # isolated wallet + clip for every symbol
MR_CAP = 0.10                 # 1% maintenance-margin-ratio cap after each fill
SL_LOSS = 0.90                # 0.80 = stop 80% of the way from avg down to current liq. 0/None = off
SL_FROM_LIQ = True            # SL is always above liq (F6 clip-dollar stop is False)
SO_STYLE = SO_RANGE           # 7d range SOs (not F6 geometric ladder)
TP_PCT = 0.05                 # take-profit vs average entry — baseline, do not drop this
HARD_SL_PCT = None            # optional extra: fraction below average (0.50 = 50% price). None = off
HARD_SL_BASKET = 1.0          # 100% of opened pocket — inert at ~1× (price ~0)
STALE_LOSS_PCT = 0.40         # 0.40 = close still ≤ 60% of average
STALE_DAYS = 180.0            # both this and the loss must hold
MAX_HOLD_DAYS = None          # e.g. 365 = flatten any basket that old, even if not -40%
RANGE_SO_MAX = 10
RANGE_WEIGHT_SIZE = False
GIVEUP_PCT = None
GIVEUP_DAYS = None
GIVEUP_MIN_FILLS = 3
INTERVAL = "1m"
ENTRY_TTL_SEC = 3600.0
PEAK_SKIP_PCT = 0.15          # all coins; pair with PEAK_LOOKBACK_DAYS (not lifetime high)
PEAK_LOOKBACK_DAYS = 90.0     # rolling wallet high over this many days; 0 = all-time (old sit-out)
SO_RECLAIM = True             # freeze 7d low + dump skip + EMA reclaim; SOL overlay turns this off
RUN_USD_M = True
RUN_COIN_M = False
RESULTS_DIR = "results_dca_run_1m_so_reclaim/lookback20"

# ---------------------------------------------------------------------------


_VENUE_KEYS = ("um", "coinm")


def _asset_overlay(asset: str, venue: str) -> dict:
    raw = dict(ASSET_TUNE.get(asset) or {})
    nested = {}
    for key in _VENUE_KEYS:
        if key in raw:
            val = raw.pop(key)
            if val is None:
                continue
            if not isinstance(val, dict):
                raise ValueError(f"{asset} ASSET_TUNE[{key!r}] must be a dict")
            nested[key] = val
    overlay = dict(raw)
    overlay.update(nested.get(venue, {}) or {})
    return overlay


def _overlay_label(overlay: dict) -> str:
    if not overlay:
        return "baseline"
    parts = []
    for key, value in overlay.items():
        if value is None:
            continue
        if key.endswith("_pct") and isinstance(value, (int, float)):
            parts.append(f"{key}={float(value)*100:g}%")
        elif key == "so_reclaim" and value is False:
            parts.append("so_reclaim=off")
        elif key == "sl_from_liq" and value is False:
            parts.append("sl=clip")
        elif key == "peak_lookback_days" and isinstance(value, (int, float)):
            parts.append("lookback=all" if float(value) <= 0 else f"lookback={float(value):g}d")
        elif key == "sl_high_reclaim" and value:
            parts.append("sl_high_reclaim")
        elif key == "after_sl_clip" and isinstance(value, (int, float)):
            parts.append(f"after_sl_clip={float(value)*100:g}%")
        elif key == "sl_cooldown_days" and isinstance(value, (int, float)):
            parts.append(f"sl_cd={float(value):g}d")
        elif key == "sl_loss" and isinstance(value, (int, float)):
            parts.append(f"SL{float(value)*100:g}")
        elif key == "after_tp_dump" and value:
            parts.append("after_tp_dump")
        elif key == "after_tp_giveback_pct" and isinstance(value, (int, float)):
            parts.append(f"tp_giveback={float(value)*100:g}%")
        elif key == "price_dd_skip_pct" and isinstance(value, (int, float)):
            parts.append(f"px_dd={float(value)*100:g}%")
        else:
            parts.append(f"{key}={value}")
    return ", ".join(parts) if parts else "baseline"


def _tune(asset: str, venue: str, overlay: dict | None = None) -> dict:
    cfg = {
        "mr_cap": MR_CAP,
        "sl_loss": SL_LOSS,
        "sl_from_liq": SL_FROM_LIQ,
        "so_style": SO_STYLE,
        "tp_pct": TP_PCT,
        "hard_sl_pct": HARD_SL_PCT,
        "hard_sl_basket": HARD_SL_BASKET,
        "stale_loss_pct": STALE_LOSS_PCT,
        "stale_days": STALE_DAYS,
        "max_hold_days": MAX_HOLD_DAYS,
        "range_so_max": RANGE_SO_MAX,
        "range_weight_size": RANGE_WEIGHT_SIZE,
        "giveup_pct": GIVEUP_PCT,
        "giveup_days": GIVEUP_DAYS,
        "giveup_min_fills": GIVEUP_MIN_FILLS,
        "interval": INTERVAL,
        "entry_ttl_sec": ENTRY_TTL_SEC,
        "peak_skip_pct": PEAK_SKIP_PCT,
        "peak_lookback_days": PEAK_LOOKBACK_DAYS,
        "so_reclaim": SO_RECLAIM,
        "sl_cooldown_days": None,
        "sl_high_reclaim": False,
        "after_sl_clip": None,
        "price_dd_skip_pct": None,
        "price_dd_lookback_days": None,
        "sl_dump_lookback_days": None,
        "after_tp_dump": False,
        "after_tp_giveback_pct": None,
    }
    if overlay is None:
        overlay = _asset_overlay(asset, venue)
    unknown = sorted(k for k in overlay if k not in cfg)
    if unknown:
        raise ValueError(f"{asset} ASSET_TUNE unknown keys: {unknown}")
    cfg.update(overlay)
    return cfg


def _tune_name() -> str | None:
    for arg in sys.argv[1:]:
        if arg.startswith("-"):
            continue
        return arg.strip().upper()
    if TUNE_ASSET:
        return str(TUNE_ASSET).upper()
    return None


def _active_assets() -> list[tuple[str, str, str]]:
    want = _tune_name()
    if not want:
        return list(ASSETS)
    match = [row for row in ASSETS if row[0] == want]
    if not match:
        names = [row[0] for row in ASSETS]
        raise ValueError(f"TUNE_ASSET {want!r} not in {names}")
    return match


def _out_base() -> str:
    name = _tune_name()
    if name:
        return os.path.join(RESULTS_DIR, f"tune_{name}")
    return RESULTS_DIR


def _overlay_key(overlay: dict) -> tuple:
    return tuple(sorted((k, repr(v)) for k, v in overlay.items()))


def _runs_for(asset: str, venue: str) -> list[tuple[str, dict]]:
    runs: list[tuple[str, dict]] = [("baseline", {})]
    seen = {_overlay_key({})}
    def add(kind: str, overlay: dict) -> None:
        key = _overlay_key(overlay)
        if key in seen:
            return
        seen.add(key)
        runs.append((kind, overlay))

    tuned = _asset_overlay(asset, venue)
    if tuned and not SWEEP:
        add("overlay", tuned)
    if _tune_name() == asset:
        for i, spec in enumerate(SWEEP):
            add(f"sweep{i}", dict(spec))
        if tuned and SWEEP:
            add("overlay", tuned)
    elif tuned:
        add("overlay", tuned)
    if not COMPARE_BASELINE and len(runs) > 1:
        return [row for row in runs if row[0] != "baseline"]
    return runs


def _sl_on(sl_loss=None) -> bool:
    value = SL_LOSS if sl_loss is None else sl_loss
    return value is not None and float(value) > 0


def _equity_stop_frac(sl_loss=None) -> float | None:
    value = SL_LOSS if sl_loss is None else sl_loss
    if not _sl_on(value):
        return 1.0
    return 1.0 - float(value)


def _cost_b_exits(results_dir: str) -> tuple[int, int, int, int, int]:
    """Cost B: trades, SL, SL that would have liquidated, SL that would have TPed, liquidations."""
    path = os.path.join(results_dir, "trades.csv")
    n = sl_n = saved = cut_tp = liq_n = 0
    if not os.path.exists(path):
        return n, sl_n, saved, cut_tp, liq_n
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if row.get("cost_model") != "B_decision":
                continue
            n += 1
            reason = row.get("exit_reason")
            if reason == "MTM":
                n -= 1
                continue
            if reason in ("SL50", "HARD", "STALE", "TIME", "GIVEUP"):
                sl_n += 1
                hold = row.get("sl_hold") or ""
                if hold == "liq":
                    saved += 1
                elif hold == "tp":
                    cut_tp += 1
            elif reason == "LIQUIDATION":
                liq_n += 1
    return n, sl_n, saved, cut_tp, liq_n


def _usd(value: float) -> str:
    return f"${value:,.0f}"


def _coin(asset: str, value: float) -> str:
    if asset == "BTC":
        return f"{value:.4f} {asset}"
    if asset == "ETH":
        return f"{value:.3f} {asset}"
    if asset == "SOL":
        return f"{value:.2f} {asset}"
    return f"{value:,.0f} {asset}"


def _row_um(asset: str, remaining) -> dict:
    b = _b(remaining)
    start = float(b.start_equity_usdt)
    mark = float(b.remaining_mark_usdt)
    idle = float(b.idle_usdt) if "idle_usdt" in b.index else 0.0
    in_pos = bool(b.in_position)
    qty = float(b.qty) if in_pos else 0.0
    last_px = float(b.btc_close)
    open_usd = (mark - idle) if in_pos else 0.0
    return {
        "asset": asset,
        "venue": "USD-M",
        "as_of": str(b.as_of),
        "start_usd": start,
        "end_usd": mark,
        "last_px": last_px,
        "start_coin": None,
        "end_coin": None,
        "in_position": in_pos,
        "open_coin": qty,
        "open_usd": open_usd,
        "idle_usd": idle,
        "idle_txt": _usd(idle),
        "open_txt": f"{_coin(asset, qty)} ({_usd(open_usd)})" if in_pos else "—",
        "start_txt": _usd(start),
        "end_txt": _usd(mark),
        "setup": "baseline",
        "trades": 0,
        "sl": 0,
        "sl_saved": 0,
        "sl_cut_tp": 0,
        "liq": 0,
    }


def _row_cm(asset: str, remaining, start_coin: float) -> dict:
    c = _b(remaining)
    start_c = float(c.start_coin) if "start_coin" in c.index else start_coin
    end_c = float(c.remaining_coin) if "remaining_coin" in c.index else float(c.remaining_btc)
    mark_usd = float(c.remaining_mark_usdt)
    px = float(c.btc_close)
    in_pos = bool(c.in_position)
    idle_c = float(c.idle_coin) if "idle_coin" in c.index else None
    if idle_c is not None:
        idle_txt = f"{_coin(asset, idle_c)} ({_usd(idle_c * px)})"
    else:
        idle_txt = "—"
    if in_pos and idle_c is not None:
        open_c = max(end_c - idle_c, 0.0)
        open_usd = open_c * px
        open_txt = f"{_coin(asset, open_c)} ({_usd(open_usd)})"
    elif in_pos:
        open_c = float("nan")
        open_usd = float("nan")
        open_txt = "open (re-run for split)"
    else:
        open_c = 0.0
        open_usd = 0.0
        open_txt = "—"
    return {
        "asset": asset,
        "venue": "Coin-M",
        "as_of": str(c.as_of),
        "start_usd": float(c.start_equity_usdt),
        "end_usd": mark_usd,
        "last_px": px,
        "start_coin": start_c,
        "end_coin": end_c,
        "in_position": in_pos,
        "open_coin": open_c,
        "open_usd": open_usd,
        "idle_txt": idle_txt,
        "open_txt": open_txt,
        "start_txt": f"{_coin(asset, start_c)} ({_usd(float(c.start_equity_usdt))})",
        "end_txt": f"{_coin(asset, end_c)} ({_usd(mark_usd)})",
        "setup": "baseline",
        "trades": 0,
        "sl": 0,
        "sl_saved": 0,
        "sl_cut_tp": 0,
        "liq": 0,
    }


def _print_table(title: str, rows: list[dict], coin: bool) -> str:
    sl_on = _sl_on()
    lines = [f"## {title}", ""]
    show_setup = any((row.get("setup") or "baseline") != "baseline" for row in rows)
    setup_h = " | Setup" if show_setup else ""
    setup_a = "|---" if show_setup else ""
    if coin:
        if sl_on:
            lines.append(f"| Asset{setup_h} | Start | Idle | Open basket | Wallet | Trades | SL | Possible liq | SL cut TP |")
            lines.append(f"|---{setup_a}|---|---:|---|---:|---:|---:|---:|---:|")
            for row in rows:
                extra = f" | {row['setup']}" if show_setup else ""
                lines.append(
                    f"| {row['asset']}{extra} | {row['start_txt']} | {row['idle_txt']} | "
                    f"{row['open_txt']} | {_usd(row['end_usd'])} | "
                    f"{row['trades']} | {row['sl']} | {row['sl_saved']} | {row['sl_cut_tp']} |"
                )
        else:
            lines.append(f"| Asset{setup_h} | Start | Idle | Open basket | Wallet | Trades | Liq |")
            lines.append(f"|---{setup_a}|---|---:|---|---:|---:|---:|")
            for row in rows:
                extra = f" | {row['setup']}" if show_setup else ""
                lines.append(
                    f"| {row['asset']}{extra} | {row['start_txt']} | {row['idle_txt']} | "
                    f"{row['open_txt']} | {_usd(row['end_usd'])} | "
                    f"{row['trades']} | {row['liq']} |"
                )
    else:
        if sl_on:
            lines.append(f"| Asset{setup_h} | Start | Idle | Open basket | Wallet | Trades | SL | Possible liq | SL cut TP |")
            lines.append(f"|---{setup_a}|---|---:|---|---:|---:|---:|---:|")
            for row in rows:
                extra = f" | {row['setup']}" if show_setup else ""
                lines.append(
                    f"| {row['asset']}{extra} | {row['start_txt']} | {row['idle_txt']} | "
                    f"{row['open_txt']} | {row['end_txt']} | "
                    f"{row['trades']} | {row['sl']} | {row['sl_saved']} | {row['sl_cut_tp']} |"
                )
        else:
            lines.append(f"| Asset{setup_h} | Start | Idle | Open basket | Wallet | Trades | Liq |")
            lines.append(f"|---{setup_a}|---|---:|---|---:|---:|")
            for row in rows:
                extra = f" | {row['setup']}" if show_setup else ""
                lines.append(
                    f"| {row['asset']}{extra} | {row['start_txt']} | {row['idle_txt']} | "
                    f"{row['open_txt']} | {row['end_txt']} | "
                    f"{row['trades']} | {row['liq']} |"
                )
    lines.append("")
    return "\n".join(lines)


def _print_delta(um_rows: list[dict], cm_rows: list[dict]) -> str:
    lines = ["## Overlay vs baseline (Cost B wallet)", ""]
    lines.append("| Venue | Asset | Overlay | Baseline wallet | Overlay wallet | Δ |")
    lines.append("|---|---|---|---:|---:|---:|")
    n = 0
    for venue, rows in (("USD-M", um_rows), ("Coin-M", cm_rows)):
        by_asset: dict[str, dict] = {}
        for row in rows:
            by_asset.setdefault(row["asset"], {})[row.get("setup") or "baseline"] = row
        for asset, setups in by_asset.items():
            base = setups.get("baseline")
            others = [k for k in setups if k != "baseline"]
            if not base or not others:
                continue
            for key in others:
                ov = setups[key]
                delta = ov["end_usd"] - base["end_usd"]
                lines.append(
                    f"| {venue} | {asset} | {key} | {_usd(base['end_usd'])} | "
                    f"{_usd(ov['end_usd'])} | ${delta:+,.0f} |"
                )
                n += 1
    if n == 0:
        return ""
    lines.append("")
    return "\n".join(lines)


def _print_rank(title: str, rows: list[dict]) -> str:
    if len(rows) < 2:
        return ""
    ordered = sorted(rows, key=lambda row: row["end_usd"], reverse=True)
    best = ordered[0]["end_usd"]
    lines = [f"## Ranked {title}", ""]
    lines.append("| Rank | Setup | Wallet | vs best | Trades | SL |")
    lines.append("|---:|---|---:|---:|---:|---:|")
    for i, row in enumerate(ordered, start=1):
        delta = row["end_usd"] - best
        vs = "—" if i == 1 else f"${delta:+,.0f}"
        lines.append(
            f"| {i} | {row.get('setup') or 'baseline'} | {_usd(row['end_usd'])} | "
            f"{vs} | {row['trades']} | {row['sl']} |"
        )
    lines.append("")
    return "\n".join(lines)


def _apply_exits(row: dict, results_dir: str) -> None:
    row["trades"], row["sl"], row["sl_saved"], row["sl_cut_tp"], row["liq"] = _cost_b_exits(results_dir)


def _exit_note(row: dict) -> str:
    extra = (
        f"  idle={row['idle_txt']}  open={row['open_txt']}  "
        f"wallet={row['end_txt']}  trades={row['trades']}"
    )
    if _sl_on():
        extra += f"  SL={row['sl']} possibleLiq={row['sl_saved']} cutTP={row['sl_cut_tp']}"
    else:
        extra += f"  liq={row['liq']}"
    setup = row.get("setup") or "baseline"
    if setup != "baseline":
        extra = f"  [{setup}]" + extra
    return extra


def _out_dir(asset: str, venue: str, kind: str) -> str:
    if kind == "baseline":
        return os.path.join(_out_base(), f"{asset}_{venue}")
    return os.path.join(_out_base(), f"{asset}_{venue}_{kind}")


def _kw(t: dict) -> dict:
    return dict(
        so_style=t["so_style"],
        tp_pct=t["tp_pct"],
        sl_from_liq=t["sl_from_liq"],
        hard_sl_pct=t["hard_sl_pct"],
        hard_sl_basket=t["hard_sl_basket"],
        stale_loss_pct=t["stale_loss_pct"],
        stale_days=t["stale_days"],
        max_hold_days=t["max_hold_days"],
        entry_ttl_sec=t["entry_ttl_sec"],
        giveup_pct=t["giveup_pct"],
        giveup_days=t["giveup_days"],
        giveup_min_fills=t["giveup_min_fills"],
        range_so_max=t["range_so_max"],
        range_weight_size=t["range_weight_size"],
        peak_skip_pct=t["peak_skip_pct"],
        peak_lookback_days=t["peak_lookback_days"],
        so_reclaim=t["so_reclaim"],
        sl_cooldown_days=t["sl_cooldown_days"],
        sl_high_reclaim=t["sl_high_reclaim"],
        after_sl_clip=t["after_sl_clip"],
        price_dd_skip_pct=t["price_dd_skip_pct"],
        price_dd_lookback_days=t["price_dd_lookback_days"],
        sl_dump_lookback_days=t["sl_dump_lookback_days"],
        after_tp_dump=t["after_tp_dump"],
        after_tp_giveback_pct=t["after_tp_giveback_pct"],
        quiet=True,
    )


def main() -> None:
    assets = _active_assets()
    out_root = _out_base()
    os.makedirs(out_root, exist_ok=True)
    try:
        os.chmod(out_root, 0o777)
    except OSError:
        pass
    um_rows, cm_rows = [], []
    as_of = None
    tune = _tune_name()

    print(
        f"Isolated DCA  baseline TP={TP_PCT*100:g}%  MR={MR_CAP*100:g}%  "
        f"SO={SO_STYLE}  bar={INTERVAL}  entry_ttl={ENTRY_TTL_SEC:g}s  "
        f"assets={[a[0] for a in assets]}"
        + (f"  sweep={len(SWEEP)}" if tune and SWEEP else ""),
        flush=True,
    )
    if tune:
        print(f"  TUNE_ASSET={tune}  results={out_root}", flush=True)
        for i, spec in enumerate(SWEEP):
            print(f"  sweep{i}: {spec}", flush=True)
    for name, _, _ in assets:
        for venue in ("um", "coinm"):
            ov = _asset_overlay(name, venue)
            if ov:
                print(f"  overlay {name} {venue}: {ov}", flush=True)

    for asset, um_symbol, cm_symbol in assets:
        if RUN_USD_M:
            for kind, overlay in _runs_for(asset, "um"):
                t = _tune(asset, "um", overlay)
                setup = _overlay_label(overlay)
                sl_keep = _equity_stop_frac(t["sl_loss"])
                out = _out_dir(asset, "um", kind)
                print(f"  USD-M {um_symbol} [{setup}] ...", flush=True)
                rem, _ = run_suite(
                    mr_cap=t["mr_cap"],
                    product=f"{asset}_um",
                    results_dir=out,
                    tag=f"{asset}_um",
                    memo_name=f"RESULTS_{asset}_UM.md",
                    equity_stop_frac=sl_keep,
                    size_equity=START_USD,
                    start_equity=START_USD,
                    df=prepare_um(um_symbol, t["interval"]),
                    market_label=um_symbol,
                    write_root_memo=False,
                    isolated=True,
                    **_kw(t),
                )
                row = _row_um(asset, rem)
                row["setup"] = setup
                _apply_exits(row, out)
                um_rows.append(row)
                as_of = row["as_of"]
                print(f"    {row['start_txt']} → {row['end_txt']}{_exit_note(row)}", flush=True)

        if RUN_COIN_M:
            cs = coinm_data.contract_size(cm_symbol)
            for kind, overlay in _runs_for(asset, "coinm"):
                t = _tune(asset, "coinm", overlay)
                setup = _overlay_label(overlay)
                sl_keep = _equity_stop_frac(t["sl_loss"])
                out = _out_dir(asset, "coinm", kind)
                print(f"  Coin-M {cm_symbol} [{setup}] ...", flush=True)
                rem, _, start_coin = run_coinm_suite(
                    symbol=cm_symbol,
                    contract_size=cs,
                    results_dir=out,
                    product=f"{asset}_cm",
                    tag=f"{asset}_cm",
                    write_root_memo=False,
                    isolated=True,
                    start_usd=START_USD,
                    mr_cap=t["mr_cap"],
                    equity_stop_frac=sl_keep,
                    interval=t["interval"],
                    **_kw(t),
                )
                row = _row_cm(asset, rem, start_coin)
                row["setup"] = setup
                _apply_exits(row, out)
                cm_rows.append(row)
                as_of = row["as_of"]
                print(f"    {row['start_txt']} → {row['end_txt']}{_exit_note(row)}", flush=True)

    _emit_report(um_rows, cm_rows, as_of)


def _emit_report(um_rows: list[dict], cm_rows: list[dict], as_of) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    overlay_bits = []
    for name, _, _ in _active_assets():
        raw = ASSET_TUNE.get(name) or {}
        if raw:
            overlay_bits.append(f"{name} {raw}")
    tune = _tune_name()
    parts = [
        "# Isolated DCA — start vs end",
        "",
        f"- Run: {now}",
        f"- Last bar: {as_of}",
        f"- Isolated wallet / clip: {_usd(START_USD)} each",
        f"- Tune coin: {tune}  sweep={len(SWEEP)}" if tune else "- Tune coin: all ASSETS",
        (
            f"- MR cap: {MR_CAP*100:g}%   SL: {SL_LOSS*100:g}% of the drop from avg down to current liq (always above liq)"
            if _sl_on()
            else f"- MR cap: {MR_CAP*100:g}%   SL: off (liquidation still counted)"
        ),
        f"- Safety orders: {SO_STYLE}"
        + (
            " (7d range rungs; freeze 7d low at first fill; no SO if 7d low expands >2% or 12h support breaks; next SO only after close reclaims 21h EMA)"
            + (
                f"; max {RANGE_SO_MAX} SOs"
                + (" sized like F6 weights" if RANGE_WEIGHT_SIZE else "")
                if RANGE_SO_MAX
                else ""
            )
            if SO_STYLE == SO_RANGE
            else " (F6 1%×1.15 ladder)" if SO_STYLE == "geometric"
            else ""
        ),
        f"- Bar: {INTERVAL} (one fill per bar; EMA/swing still 21h / 55h / 12h)",
        (
            f"- Entry TTL: cancel unfilled base after {ENTRY_TTL_SEC/3600:g}h; sit out that bar "
            "(matches live DCA_ENTRY_TTL_SEC / ghost-GTC cancel). Safety orders keep working."
            if ENTRY_TTL_SEC
            else "- Entry TTL: off (base stays until skip, fill, or filter)"
        ),
        f"- Take-profit: {TP_PCT*100:g}% from average entry (baseline; per-coin overlay in ASSET_TUNE)",
        ("- Overlays: " + ", ".join(overlay_bits)) if overlay_bits else "- Overlays: none (every coin on baseline)",
        "- Compare: each overlay book is also run on the same baseline in this report" if COMPARE_BASELINE else "- Compare: overlay only (no paired baseline in this run)",
        (
            f"- Hard SL: flatten at {HARD_SL_PCT*100:g}% below average (before the 90%-to-liq stop)"
            if HARD_SL_PCT
            else "- Hard SL: off"
        ),
        (
            f"- Stale bag: flatten if still ≥{STALE_LOSS_PCT*100:g}% below average after {STALE_DAYS:g}d "
            "(ETH 4.6k→2.4k). Flatten then re-enter lower (skip ema55 / 7d-top until the next fill)."
            + (f" Calendar cap: {MAX_HOLD_DAYS:g}d." if MAX_HOLD_DAYS else "")
            if STALE_LOSS_PCT and STALE_DAYS
            else "- Stale bag: off"
        ),
        (
            f"- Give-up: flatten if ≥{GIVEUP_MIN_FILLS} fills and still ≥{GIVEUP_PCT*100:g}% below avg after {GIVEUP_DAYS:g}d "
            "(cuts laddered crash bags before the 90%-to-liq SL)."
            if GIVEUP_PCT and GIVEUP_DAYS
            else "- Give-up: off"
        ),
        (
            f"- Peak brake: no new basket while wallet is ≥{PEAK_SKIP_PCT*100:g}% under the "
            f"{'all-time' if not PEAK_LOOKBACK_DAYS else f'{PEAK_LOOKBACK_DAYS:g}d rolling'} marked-wallet high"
            if PEAK_SKIP_PCT
            else "- Peak brake (global): off — per-coin peak_skip is in ASSET_TUNE / Setup column"
        ),
        "- After-SL brake: only after a ≥15% wallet hole (same as peak-skip). sl_cd / sl_high_reclaim hold the brake; after_sl_clip probes at that fraction until it clears. Small SLs in a hot book stay full clip.",
        "- Price-dd skip (sweep): no new basket while close is ≥X under the rolling price high (completed bars).",
        "- Dump gate (sweep): after SL, no new basket until close recaptures the frozen N-day price high at the stop.",
        "- After-TP gate (sweep): after a TP, no new basket if the 7d low expands >2% (dump) or close gives back after_tp_giveback_pct (reversal).",
        f"- Possible liq = SL fired and holding that basket would have liquidated before +{TP_PCT*100:g}% TP",
        f"- SL cut TP = stop fired and that basket would have hit TP if held",
        f"- Idle = USDT (USD-M) or coin not in the trade. It does not change if the open basket moves.",
        f"- Open basket = isolated pocket (margin + uPnL) at last close. At price P: open USD ≈ Open USD + qty × (P − last close).",
        f"- Wallet = Idle + Open. Not a taker flatten.",
        f"- Trades = Cost B closed baskets (TP, SL, emergency). Open MTM is not a trade",
        "",
    ]
    delta = _print_delta(um_rows, cm_rows)
    if delta:
        parts.append(delta)
    rank_um = _print_rank("USD-M", um_rows)
    rank_cm = _print_rank("Coin-M", cm_rows)
    if rank_um:
        parts.append(rank_um)
    if rank_cm:
        parts.append(rank_cm)
    if um_rows:
        parts.append(_print_table("USD-M (USDT)", um_rows, coin=False))
    if cm_rows:
        parts.append(_print_table("Coin-M (coin wallet)", cm_rows, coin=True))
    report = "\n".join(parts).rstrip() + "\n"

    report_path = os.path.join(_out_base(), "REPORT.md")
    with open(report_path, "w") as f:
        f.write(report)
    print()
    print(report)
    print(f"Wrote {report_path}")


def _load_dir(asset: str, venue: str, coin: bool, rows: list, as_of):
    import pandas as pd

    base_dir = _out_base()
    base = os.path.join(base_dir, f"{asset}_{venue}")
    candidates = []
    if os.path.isdir(base_dir):
        prefix = f"{asset}_{venue}"
        for name in sorted(os.listdir(base_dir)):
            path = os.path.join(base_dir, name)
            if name == prefix or name.startswith(prefix + "_"):
                candidates.append(path)
    if not candidates and os.path.isdir(base):
        candidates = [base]
    for out in candidates:
        path = os.path.join(out, "remaining_balance.csv")
        if not os.path.exists(path):
            continue
        rem = pd.read_csv(path)
        name = os.path.basename(out)
        prefix = f"{asset}_{venue}"
        if name == prefix:
            setup = "baseline"
        elif name.endswith("_overlay"):
            setup = _overlay_label(_asset_overlay(asset, venue))
        elif name.rsplit("_", 1)[-1].startswith("sweep"):
            idx = name.rsplit("_", 1)[-1].replace("sweep", "")
            try:
                setup = _overlay_label(dict(SWEEP[int(idx)]))
            except (ValueError, IndexError):
                setup = name[len(prefix) + 1 :]
        else:
            setup = name[len(prefix) + 1 :]
        if coin:
            start_coin = float(rem.iloc[0].start_coin) if "start_coin" in rem.columns else 0.0
            row = _row_cm(asset, rem, start_coin)
        else:
            row = _row_um(asset, rem)
        row["setup"] = setup
        _apply_exits(row, out)
        rows.append(row)
        as_of = row["as_of"]
    return as_of


def rebuild_from_existing() -> None:
    um_rows, cm_rows = [], []
    as_of = None
    for asset, _um, _cm in _active_assets():
        if RUN_USD_M:
            as_of = _load_dir(asset, "um", False, um_rows, as_of)
        if RUN_COIN_M:
            as_of = _load_dir(asset, "coinm", True, cm_rows, as_of)
    _emit_report(um_rows, cm_rows, as_of)


if __name__ == "__main__":
    if "--from-existing" in sys.argv:
        rebuild_from_existing()
    else:
        main()
