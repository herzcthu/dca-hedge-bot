#!/usr/bin/env python3
"""One-symbol USD-M DCA. Hedge mode holds a long and a short on that symbol.

Research stays in research/experiments/dca (not imported). Testnet unless production is confirmed.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

import pandas as pd
import requests

import binance_client as um
from dca_rules import (
    BAR_SCALE,
    HEADROOM,
    MAX_SAFETY,
    MIN_NOTIONAL,
    MR_EMERGENCY,
    RANGE_DAYS,
    RANGE_DUMP_EXPAND,
    SO_RANGE,
    add_dca_features,
    binding_stop,
    margin_ratio,
    new_basket_limit,
    new_basket_skip_reason,
    notional_cap,
    peak_skip_reason,
    planned_notional,
    range_so_short,
    safety_order_plan,
    short_basket_limit,
    short_basket_skip_reason,
    side_stop,
    stale_exit_reason,
    account_liq,
)
from trade_log import CsvLogger, DEFAULT_EVENT_FIELDS


def _env(name: str, default: str) -> str:
    raw = os.getenv(name)
    return default if raw is None or raw.strip() == "" else raw.strip()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes")


def _env_float(name: str, default: float | None) -> float | None:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "" or raw.strip().lower() in ("none", "off"):
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    return int(float(_env(name, str(default))))


@dataclass(frozen=True)
class BotConfig:
    market: str
    symbol: str
    interval: str
    mr_cap: float
    sl_loss: float | None
    sl_from_liq: bool
    so_style: str
    tp_pct: float
    hard_sl_pct: float | None
    hard_sl_basket: float | None
    stale_loss_pct: float | None
    stale_days: float | None
    max_hold_days: float | None
    leverage: int
    margin_type: str
    wallet_field: str
    poll_sec: float
    state_path: str
    dry_run: bool
    allow_orders: bool
    confirm_production: bool
    flatten_on_start: bool
    entry_ttl_sec: float
    giveup_pct: float | None
    giveup_days: float | None
    giveup_min_fills: int
    clip_usd: float | None
    peak_skip_pct: float | None
    peak_lookback_days: float
    range_so_max: int
    hedge: bool


def load_config() -> BotConfig:
    market = _env("DCA_MARKET", "um").lower()
    return BotConfig(
        market=market,
        symbol=_env("DCA_SYMBOL", "DOGEUSDT").upper(),
        interval=_env("DCA_INTERVAL", "1m"),
        mr_cap=float(_env("DCA_MR_CAP", "0.10")),
        sl_loss=_env_float("DCA_SL_LOSS", 0.95),
        sl_from_liq=_env_bool("DCA_SL_FROM_LIQ", True),
        so_style=_env("DCA_SO_STYLE", SO_RANGE),
        tp_pct=float(_env("DCA_TP_PCT", "0.08")),
        hard_sl_pct=_env_float("DCA_HARD_SL_PCT", None),
        hard_sl_basket=_env_float("DCA_HARD_SL_BASKET", 1.0),
        stale_loss_pct=_env_float("DCA_STALE_LOSS_PCT", 0.40),
        stale_days=_env_float("DCA_STALE_DAYS", 180.0),
        max_hold_days=_env_float("DCA_MAX_HOLD_DAYS", None),
        leverage=_env_int("DCA_LEVERAGE", 25),
        margin_type=_env("DCA_MARGIN_TYPE", "CROSSED").upper(),
        wallet_field=_env("DCA_WALLET_FIELD", "wallet"),
        poll_sec=float(_env("DCA_POLL_SEC", "15")),
        state_path=_env("DCA_STATE_PATH", "data/dca_bot_state.json"),
        dry_run=_env_bool("DRY_RUN", True),
        allow_orders=_env_bool("DCA_ALLOW_ORDERS", False),
        confirm_production=_env_bool("DCA_CONFIRM_PRODUCTION", False),
        flatten_on_start=_env_bool("DCA_FLATTEN_ON_START", False),
        entry_ttl_sec=float(_env("DCA_ENTRY_TTL_SEC", "3600")),
        giveup_pct=_env_float("DCA_GIVEUP_PCT", None),
        giveup_days=_env_float("DCA_GIVEUP_DAYS", None),
        giveup_min_fills=_env_int("DCA_GIVEUP_MIN_FILLS", 3),
        clip_usd=_env_float("DCA_CLIP_USD", 10000.0),
        peak_skip_pct=_env_float("DCA_PEAK_SKIP_PCT", 0.15),
        peak_lookback_days=float(_env("DCA_PEAK_LOOKBACK_DAYS", "180")),
        range_so_max=_env_int("DCA_RANGE_SO_MAX", MAX_SAFETY),
        hedge=_env_bool("DCA_HEDGE", True),
    )


def _production_url(url: str) -> bool:
    u = url.lower()
    return "testnet" not in u and ("fapi.binance.com" in u or "dapi.binance.com" in u)


def _feature_warmup_bars(interval: str) -> int:
    scale = BAR_SCALE[interval]
    return RANGE_DAYS * 24 * scale + 2


def _fetch_klines_pages(url: str, symbol: str, interval: str, min_bars: int) -> list:
    """Walk backward until we have enough completed candles for 7d range + EMAs."""
    page = 1500
    need = min_bars + 2
    end_ms = int(time.time() * 1000)
    by_open: dict[int, list] = {}
    while len(by_open) < need:
        r = requests.get(
            url,
            params={"symbol": symbol, "interval": interval, "endTime": end_ms, "limit": page},
            timeout=15,
        )
        r.raise_for_status()
        batch = r.json()
        if not isinstance(batch, list) or not batch:
            break
        for item in batch:
            by_open[int(item[0])] = item
        first_open = int(batch[0][0])
        if len(batch) < page or first_open <= 0:
            break
        next_end = first_open - 1
        if next_end >= end_ms:
            break
        end_ms = next_end
    return [by_open[k] for k in sorted(by_open)]


def _klines_frame(raw: list, interval: str, label: str) -> pd.DataFrame:
    now = pd.Timestamp.now(tz="UTC")
    rows = []
    for item in raw:
        close_time = pd.to_datetime(int(item[6]), unit="ms", utc=True)
        if close_time > now:
            continue
        rows.append({
            "open_time": pd.to_datetime(int(item[0]), unit="ms", utc=True),
            "close_time": close_time,
            "open": float(item[1]),
            "high": float(item[2]),
            "low": float(item[3]),
            "close": float(item[4]),
            "volume": float(item[5]),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError(f"no completed {label} klines")
    out = add_dca_features(df, interval)
    if out.empty:
        raise RuntimeError(
            f"{label} klines={len(df)} but features empty (need ~{_feature_warmup_bars(interval)} {interval} bars)"
        )
    return out


def klines_um(symbol: str, interval: str) -> pd.DataFrame:
    kline_base = _env("DCA_KLINE_BASE", "https://fapi.binance.com")
    url = kline_base.rstrip("/") + "/fapi/v1/klines"
    raw = _fetch_klines_pages(url, symbol, interval, _feature_warmup_bars(interval))
    return _klines_frame(raw, interval, "um")


def load_state(path: str) -> dict:
    if not os.path.exists(path):
        return {
            "fills": 0,
            "so_count": 0,
            "last_fill": 0.0,
            "basket_start": None,
            "basket_so_floor": None,
            "await_so_reclaim": False,
            "reenter_from_stale": False,
            "last_signal_open": None,
            "basket_clip": None,
            "wallet_peak_hist": [],
        }
    with open(path) as f:
        return json.load(f)


def save_state(path: str, state: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2, default=str)
    os.replace(tmp, path)


def clip_from_wallet(cfg: BotConfig) -> float:
    paper = _env_float("DCA_PAPER_WALLET", None)
    if not um.API_KEY:
        if paper is None or paper <= 0:
            raise RuntimeError("no API key: set DCA_PAPER_WALLET or BINANCE_API_KEY")
        print(f"WALLET paper={paper:.4f} (no API key)", flush=True)
        return paper
    w = um.usdt_futures_wallet()
    field = cfg.wallet_field if cfg.wallet_field in w else "wallet"
    clip = float(w[field])
    print(
        f"WALLET wallet={w['wallet']:.4f} available={w['available']:.4f} "
        f"margin={w['margin']:.4f} clip_field={field} clip={clip:.4f}",
        flush=True,
    )
    if clip <= 0:
        raise RuntimeError("futures USDT wallet is not positive")
    return clip


def _size_clip(wallet: float, cfg: BotConfig) -> float:
    cap = cfg.clip_usd
    if cap is None or cap <= 0:
        return wallet
    return min(wallet, cap)


def _px(value: float) -> str:
    text = f"{float(value):.8f}".rstrip("0").rstrip(".")
    return text if text else "0"


def _idle_basket(state: dict, open_key: str | None, reenter: bool = False) -> dict:
    return {
        "fills": 0,
        "so_count": 0,
        "last_fill": 0.0,
        "basket_start": None,
        "basket_so_floor": None,
        "await_so_reclaim": False,
        "reenter_from_stale": reenter,
        "last_signal_open": open_key,
        "entry_armed_at": None,
        "entry_limit": None,
        "basket_clip": None,
        "wallet_peak_hist": list(state.get("wallet_peak_hist") or []),
    }


def rolling_wallet_peak(state: dict, ts, marked: float, lookback_days: float) -> float:
    hist = list(state.get("wallet_peak_hist") or [])
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    else:
        t = t.tz_convert("UTC")
    hist.append({"t": t.isoformat(), "v": float(marked)})
    days = float(lookback_days) if lookback_days and lookback_days > 0 else 36500.0
    cutoff = t - pd.Timedelta(days=days)
    by_hour: dict[str, float] = {}
    for row in hist:
        rt = pd.Timestamp(row["t"])
        if rt.tzinfo is None:
            rt = rt.tz_localize("UTC")
        else:
            rt = rt.tz_convert("UTC")
        if rt < cutoff:
            continue
        hour = rt.floor("h").isoformat()
        by_hour[hour] = max(by_hour.get(hour, 0.0), float(row["v"]))
    state["wallet_peak_hist"] = [{"t": k, "v": v} for k, v in sorted(by_hour.items())]
    return max(by_hour.values()) if by_hour else float(marked)


def _iso(ts) -> str | None:
    if ts is None:
        return None
    if hasattr(ts, "isoformat"):
        return ts.isoformat()
    return str(ts)


def _parse_ts(value):
    if value is None or value == "":
        return None
    return pd.Timestamp(value)


def report_account(cfg: BotConfig) -> dict:
    if not um.API_KEY:
        print("STARTUP_ACCOUNT skipped (no API key)", flush=True)
        return {"symbol": cfg.symbol, "positionAmt": "0", "entryPrice": "0", "isolatedWallet": "0"}
    positions = um.signed_get("/fapi/v2/positionRisk")
    orders = um.signed_get("/fapi/v1/openOrders")
    ours = [p for p in positions if abs(float(p.get("positionAmt") or 0)) > 0]
    print("STARTUP_ACCOUNT", "positions", len(ours), "open_orders", len(orders), flush=True)
    for row in ours:
        print(
            f"  POS {row.get('symbol')} amt={row.get('positionAmt')} "
            f"entry={row.get('entryPrice')} isol={row.get('isolatedWallet')}",
            flush=True,
        )
    foreign = [p for p in ours if p.get("symbol") != cfg.symbol]
    if foreign:
        print("WARN other-symbol exposure left untouched", [p.get("symbol") for p in foreign], flush=True)
    return um.position_risk(cfg.symbol)


def maybe_flatten_testnet(cfg: BotConfig, pos: dict) -> dict:
    qty = abs(float(pos.get("positionAmt") or 0))
    if qty <= 0 or not cfg.flatten_on_start:
        return pos
    if _production_url(um.BASE) and not cfg.confirm_production:
        raise RuntimeError("refusing DCA_FLATTEN_ON_START on production without DCA_CONFIRM_PRODUCTION")
    print("FLATTEN_ON_START", cfg.symbol, qty, flush=True)
    if not cfg.dry_run and cfg.allow_orders:
        um.cancel_symbol_orders(cfg.symbol)
        side = "SELL" if float(pos["positionAmt"]) > 0 else "BUY"
        um.place(cfg.symbol, side, qty, None, True, "MARKET")
    return um.position_risk(cfg.symbol)


def qty_from_notional(symbol: str, notional: float, price: float) -> float:
    rules = um._symbol_rules[symbol]
    qty = um.round_down(notional / price, rules.quantity_step)
    if qty < rules.min_quantity:
        return 0.0
    if rules.min_notional and qty * Decimal(str(price)) < rules.min_notional:
        return 0.0
    return float(qty)


def flatten_long(cfg: BotConfig, qty: float, reason: str, log: CsvLogger) -> None:
    print("FLATTEN", reason, cfg.symbol, qty, flush=True)
    log.log("flatten", symbol=cfg.symbol, reason=reason, quantity=qty)
    if cfg.dry_run or not cfg.allow_orders:
        return
    um.cancel_symbol_orders(cfg.symbol)
    um.place(cfg.symbol, "SELL", qty, None, True, "MARKET")


def _cancel_working(cfg: BotConfig, live: bool, reason: str, log: CsvLogger | None = None) -> None:
    print("CANCEL_ORDERS", reason, flush=True)
    if log is not None:
        log.log("cancel_orders", symbol=cfg.symbol, reason=reason)
    if live:
        um.cancel_symbol_orders(cfg.symbol)


def _entry_age_sec(state: dict) -> float:
    raw = state.get("entry_armed_at")
    if not raw:
        return 0.0
    armed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    if armed.tzinfo is None:
        armed = armed.replace(tzinfo=timezone.utc)
    return max((datetime.now(timezone.utc) - armed).total_seconds(), 0.0)


def arm_orders(cfg: BotConfig, row, qty: float, avg: float, clip: float, state: dict, log: CsvLogger) -> None:
    close = float(row.close)
    remaining = notional_cap(clip, cfg.mr_cap) - qty * close
    live = (not cfg.dry_run) and cfg.allow_orders
    if qty <= 0:
        why = peak_skip_reason(
            float(state.get("marked_pocket") or clip),
            state.get("wallet_peak"),
            cfg.peak_skip_pct,
        )
        if why is None:
            why = new_basket_skip_reason(
                close, float(row.ema55), float(row.resist), cfg.so_style,
                float(row.range_low), float(row.range_high), bool(state.get("reenter_from_stale")),
            )
        if why:
            print("SKIP_ENTRY", why, flush=True)
            _cancel_working(cfg, live, f"signal_dead {why}", log)
            state["entry_armed_at"] = None
            state["entry_limit"] = None
            return
        limit = new_basket_limit(close, float(row.ema21), float(row.support), bool(state.get("reenter_from_stale")))
        if limit is None:
            print(
                "SKIP_ENTRY no_dip ema21=", _px(float(row.ema21)),
                "support=", _px(float(row.support)), "need>=0.3% below close",
                flush=True,
            )
            _cancel_working(cfg, live, "no_dip", log)
            state["entry_armed_at"] = None
            state["entry_limit"] = None
            return
        cap = notional_cap(clip, cfg.mr_cap) * HEADROOM
        size = min(planned_notional(cap, 0), remaining * HEADROOM)
        q = qty_from_notional(cfg.symbol, size, limit)
        if q <= 0 or size < MIN_NOTIONAL:
            print("SKIP_ENTRY unsizable size=", size, "qty=", q, flush=True)
            _cancel_working(cfg, live, "unsizable", log)
            state["entry_armed_at"] = None
            state["entry_limit"] = None
            return
        age = _entry_age_sec(state)
        prev = state.get("entry_limit")
        same = prev is not None and abs(float(prev) - limit) / limit < 0.001
        if cfg.entry_ttl_sec > 0 and same and age >= cfg.entry_ttl_sec:
            print(
                f"SKIP_ENTRY unfilled_ttl age={age:.0f}s limit={_px(float(prev))} "
                f"(price never tagged; cancel, wait next bar)",
                flush=True,
            )
            _cancel_working(cfg, live, "unfilled_ttl", log)
            state["entry_armed_at"] = None
            state["entry_limit"] = None
            return
        print(
            f"{'WOULD_ARM' if not live else 'ARM_BASE'} limit={_px(limit)} qty={q} "
            f"notional={size:.2f} dry={cfg.dry_run} orders={cfg.allow_orders}",
            flush=True,
        )
        if not live:
            if not same:
                state["entry_armed_at"] = datetime.now(timezone.utc).isoformat()
            state["entry_limit"] = limit
            return
        um.cancel_symbol_orders(cfg.symbol)
        um.place_limit(cfg.symbol, "BUY", q, limit, False, "GTC")
        if not same:
            state["entry_armed_at"] = datetime.now(timezone.utc).isoformat()
        state["entry_limit"] = limit
        return
    if qty > 0 and state.get("await_so_reclaim") and close < float(row.ema21):
        plan = None
    else:
        if qty > 0 and close >= float(row.ema21):
            state["await_so_reclaim"] = False
        plan = safety_order_plan(
            cfg.so_style, float(state.get("last_fill") or avg), int(state.get("so_count") or 0),
            int(state.get("fills") or 1),
            float(row.ema21), float(row.support), close, float(row.ema55),
            remaining, notional_cap(clip, cfg.mr_cap) * HEADROOM,
            range_low=float(state["basket_so_floor"]) if state.get("basket_so_floor") else float(row.range_low),
            live_range_low=float(row.range_low),
            max_so=cfg.range_so_max,
        )
    if plan is not None:
        limit, size = plan
        q = qty_from_notional(cfg.symbol, size, limit)
        if q > 0 and size >= MIN_NOTIONAL:
            print(
                f"{'WOULD_ARM_SO' if not live else 'ARM_SO'} limit={_px(limit)} qty={q}",
                flush=True,
            )
        else:
            q = 0.0
            size = 0.0
    else:
        q = 0.0
        size = 0.0
        limit = None
    tp = avg * (1.0 + cfg.tp_pct)
    print(f"{'WOULD_ARM_TP' if not live else 'ARM_TP'} tp={_px(tp)} qty={qty}", flush=True)
    if not live:
        return
    um.cancel_symbol_orders(cfg.symbol)
    if plan is not None and q > 0:
        um.place_limit(cfg.symbol, "BUY", q, limit, False, "GTC")
        state["await_so_reclaim"] = True
    um.place_limit(cfg.symbol, "SELL", qty, tp, True, "GTC")


def on_completed_bar(cfg: BotConfig, row, state: dict, log: CsvLogger) -> dict:
    if um.API_KEY:
        pos = um.position_risk(cfg.symbol)
    else:
        pos = {"positionAmt": "0", "entryPrice": "0", "isolatedWallet": "0"}
    qty = float(pos.get("positionAmt") or 0)
    avg = float(pos.get("entryPrice") or 0)
    mark = float(row.close)
    open_key = str(row.open_time)
    if state.get("last_signal_open") == open_key:
        return state
    wallet = clip_from_wallet(cfg)
    isol = float(pos.get("isolatedWallet") or 0)
    exchange_pocket = isol if isol > 0 else wallet
    cap = _size_clip(wallet, cfg)
    if qty < 0:
        print("REFUSE short position", qty, flush=True)
        return state
    if qty > 0 and avg <= 0:
        avg = mark
    state["last_signal_open"] = open_key

    if qty > 0:
        state["entry_armed_at"] = None
        state["entry_limit"] = None
        if not state.get("basket_start"):
            state["basket_start"] = _iso(row.close_time)
        if state.get("basket_clip") is None:
            state["basket_clip"] = cap
        if int(state.get("fills") or 0) < 1:
            state["fills"] = 1
            state["last_fill"] = avg
            if state.get("basket_so_floor") is None:
                state["basket_so_floor"] = float(row.range_low)
        unit = float(state["basket_clip"])
        sp, kind = binding_stop(
            qty, avg, unit, unit, cfg.sl_loss, cfg.sl_from_liq,
            cfg.hard_sl_pct, cfg.hard_sl_basket,
        )
        if sp is not None and min(float(row.open), float(row.low)) <= sp:
            flatten_long(cfg, qty, kind, log)
            state = _idle_basket(state, open_key)
            qty = 0.0
        elif margin_ratio(qty, float(row.low), exchange_pocket, avg) >= MR_EMERGENCY:
            flatten_long(cfg, qty, "EMERGENCY", log)
            state = _idle_basket(state, open_key)
            qty = 0.0
        else:
            sig = stale_exit_reason(
                _parse_ts(state.get("basket_start")),
                row.close_time,
                mark,
                avg,
                cfg.stale_loss_pct,
                cfg.stale_days,
                cfg.max_hold_days,
                fills=int(state.get("fills") or 0),
                giveup_pct=cfg.giveup_pct,
                giveup_days=cfg.giveup_days,
                giveup_min_fills=cfg.giveup_min_fills,
            )
            if sig:
                flatten_long(cfg, qty, sig, log)
                state = _idle_basket(state, open_key, reenter=True)
                qty = 0.0
                avg = 0.0

    if qty > 0:
        state["reenter_from_stale"] = False
        clip = float(state.get("basket_clip") or cap)
        marked = clip + qty * (mark - avg)
    else:
        clip = cap
        marked = cap
    peak = rolling_wallet_peak(state, row.close_time, marked, cfg.peak_lookback_days)
    state["marked_pocket"] = marked
    state["wallet_peak"] = peak
    print(
        f"BAR {row.close_time} close={_px(mark)} qty={qty:.6f} avg={_px(avg)} "
        f"clip={clip:.2f} wallet={wallet:.2f} marked={marked:.2f} peak={peak:.2f} "
        f"fills={state.get('fills')} so={state.get('so_count')} "
        f"reenter={state.get('reenter_from_stale')}",
        flush=True,
    )
    arm_orders(cfg, row, qty, avg, clip, state, log)
    return state


def refuse_if_unsafe(cfg: BotConfig) -> None:
    if cfg.market != "um":
        raise RuntimeError("one-bot one-symbol: DCA_MARKET must be um (Coin-M is not wired)")
    if cfg.interval not in BAR_SCALE:
        raise RuntimeError(f"unsupported DCA_INTERVAL={cfg.interval}")
    if cfg.dry_run:
        return
    if not cfg.allow_orders:
        raise RuntimeError("DRY_RUN=false requires DCA_ALLOW_ORDERS=true")
    if _production_url(um.BASE) and not cfg.confirm_production:
        raise RuntimeError("production fapi URL requires DCA_CONFIRM_PRODUCTION=true")


def _empty_leg() -> dict:
    return {
        "fills": 0,
        "so_count": 0,
        "last_fill": 0.0,
        "basket_start": None,
        "anchor": None,
        "await_so_reclaim": False,
        "reenter_from_stale": False,
        "entry_armed_at": None,
        "entry_limit": None,
        "basket_clip": None,
    }


def _ensure_legs(state: dict) -> dict:
    if "long" not in state:
        state = {
            "long": {
                "fills": int(state.get("fills") or 0),
                "so_count": int(state.get("so_count") or 0),
                "last_fill": float(state.get("last_fill") or 0.0),
                "basket_start": state.get("basket_start"),
                "anchor": state.get("basket_so_floor"),
                "await_so_reclaim": bool(state.get("await_so_reclaim")),
                "reenter_from_stale": bool(state.get("reenter_from_stale")),
                "entry_armed_at": state.get("entry_armed_at"),
                "entry_limit": state.get("entry_limit"),
                "basket_clip": state.get("basket_clip"),
            },
            "short": _empty_leg(),
            "wallet_peak_hist": list(state.get("wallet_peak_hist") or []),
            "last_signal_open": state.get("last_signal_open"),
            "marked_pocket": state.get("marked_pocket"),
            "wallet_peak": state.get("wallet_peak"),
        }
    state.setdefault("short", _empty_leg())
    state.setdefault("wallet_peak_hist", [])
    return state


def _pos_qty(row: dict) -> float:
    return abs(float(row.get("positionAmt") or 0))


def _pos_avg(row: dict, mark: float, qty: float) -> float:
    avg = float(row.get("entryPrice") or 0)
    if qty > 0 and avg <= 0:
        return mark
    return avg


def ensure_hedge_mode() -> None:
    if not um.API_KEY:
        print("HEDGE_MODE skipped (no API key)", flush=True)
        return
    current = um.signed_get("/fapi/v1/positionSide/dual")
    if str(current.get("dualSidePosition")).lower() == "true":
        print("HEDGE_MODE on", flush=True)
        return
    try:
        um.signed_post("/fapi/v1/positionSide/dual", {"dualSidePosition": "true"})
    except requests.HTTPError as error:
        body = {}
        if error.response is not None:
            try:
                body = error.response.json()
            except Exception:
                body = {}
        if body.get("code") != -4059:
            raise RuntimeError(f"cannot enable hedge mode: {body or error}") from error
    print("HEDGE_MODE enabled", flush=True)


def _clear_leg(leg: dict, reenter: bool = False) -> None:
    fresh = _empty_leg()
    fresh["reenter_from_stale"] = reenter
    leg.clear()
    leg.update(fresh)


def _flatten_side(cfg: BotConfig, qty: float, reason: str, log: CsvLogger, position_side: str) -> None:
    order_side = "SELL" if position_side == "LONG" else "BUY"
    print("FLATTEN", position_side, reason, cfg.symbol, qty, flush=True)
    log.log("flatten", symbol=cfg.symbol, side=order_side, reason=reason, quantity=qty)
    if cfg.dry_run or not cfg.allow_orders:
        return
    um.place(cfg.symbol, order_side, qty, None, True, "MARKET", position_side=position_side)


def _arm_hedge_leg(
    cfg: BotConfig,
    row,
    leg: dict,
    qty: float,
    avg: float,
    clip: float,
    short: bool,
    marked: float,
    peak: float | None,
) -> list[dict]:
    """Orders for one side. Does not send them."""
    close = float(row.close)
    tag = "SHORT" if short else "LONG"
    orders: list[dict] = []
    if qty <= 0:
        why = peak_skip_reason(marked, peak, cfg.peak_skip_pct)
        if why is None:
            if short:
                why = short_basket_skip_reason(
                    close, float(row.ema55), float(row.support), cfg.so_style,
                    float(row.range_low), float(row.range_high), bool(leg.get("reenter_from_stale")),
                )
            else:
                why = new_basket_skip_reason(
                    close, float(row.ema55), float(row.resist), cfg.so_style,
                    float(row.range_low), float(row.range_high), bool(leg.get("reenter_from_stale")),
                )
        if why:
            print(f"SKIP_{tag}", why, flush=True)
            leg["entry_armed_at"] = None
            leg["entry_limit"] = None
            return orders
        if short:
            limit = short_basket_limit(close, float(row.ema21), float(row.resist), bool(leg.get("reenter_from_stale")))
        else:
            limit = new_basket_limit(close, float(row.ema21), float(row.support), bool(leg.get("reenter_from_stale")))
        if limit is None:
            print(f"SKIP_{tag} no_level", flush=True)
            leg["entry_armed_at"] = None
            leg["entry_limit"] = None
            return orders
        cap = notional_cap(clip, cfg.mr_cap) * HEADROOM
        size = min(planned_notional(cap, 0), cap)
        q = qty_from_notional(cfg.symbol, size, limit)
        if q <= 0 or size < MIN_NOTIONAL:
            print(f"SKIP_{tag} unsizable", size, flush=True)
            leg["entry_armed_at"] = None
            leg["entry_limit"] = None
            return orders
        held_age_state = {"entry_armed_at": leg.get("entry_armed_at")}
        age = _entry_age_sec(held_age_state)
        prev = leg.get("entry_limit")
        same = prev is not None and abs(float(prev) - limit) / limit < 0.001
        if cfg.entry_ttl_sec > 0 and same and age >= cfg.entry_ttl_sec:
            print(f"SKIP_{tag} unfilled_ttl age={age:.0f}s limit={_px(float(prev))}", flush=True)
            leg["entry_armed_at"] = None
            leg["entry_limit"] = None
            return orders
        if not same:
            leg["entry_armed_at"] = datetime.now(timezone.utc).isoformat()
        leg["entry_limit"] = limit
        leg["anchor"] = float(row.range_high) if short else float(row.range_low)
        print(f"ARM_{tag} limit={_px(limit)} qty={q} notional={size:.2f}", flush=True)
        orders.append({
            "side": "SELL" if short else "BUY",
            "qty": q,
            "price": limit,
            "position_side": tag,
        })
        return orders
    leg["entry_armed_at"] = None
    leg["entry_limit"] = None
    if int(leg.get("fills") or 0) < 1:
        leg["fills"] = 1
        leg["last_fill"] = avg
        if leg.get("anchor") is None:
            leg["anchor"] = float(row.range_high) if short else float(row.range_low)
        if leg.get("basket_clip") is None:
            leg["basket_clip"] = clip
    if not leg.get("basket_start"):
        leg["basket_start"] = _iso(row.close_time)
    so_limit = None
    so_qty = 0.0
    so_size = 0.0
    reclaimed = close <= float(row.ema21) if short else close >= float(row.ema21)
    if leg.get("await_so_reclaim") and not reclaimed:
        so_limit = None
    else:
        if reclaimed:
            leg["await_so_reclaim"] = False
        remaining = notional_cap(clip, cfg.mr_cap) - qty * close
        if short:
            anchor = leg.get("anchor")
            live_hi = float(row.range_high)
            blocked = False
            if anchor and live_hi > float(anchor) * (1.0 + RANGE_DUMP_EXPAND):
                blocked = True
            if pd.notna(row.resist) and close > float(row.resist):
                blocked = True
            if not blocked and remaining >= MIN_NOTIONAL:
                hi = float(anchor) if anchor else live_hi
                so_limit = range_so_short(
                    float(leg.get("last_fill") or avg), hi, int(leg.get("so_count") or 0), cfg.range_so_max,
                )
        else:
            plan = safety_order_plan(
                cfg.so_style, float(leg.get("last_fill") or avg), int(leg.get("so_count") or 0),
                int(leg.get("fills") or 1),
                float(row.ema21), float(row.support), close, float(row.ema55),
                remaining, notional_cap(clip, cfg.mr_cap) * HEADROOM,
                range_low=float(leg["anchor"]) if leg.get("anchor") else float(row.range_low),
                live_range_low=float(row.range_low),
                max_so=cfg.range_so_max,
            )
            if plan is not None:
                so_limit = plan[0]
                so_size = plan[1]
            else:
                so_size = 0.0
        if short and so_limit is not None and remaining >= MIN_NOTIONAL:
            slots = max(cfg.range_so_max - int(leg.get("so_count") or 0), 1)
            so_size = remaining * HEADROOM / slots
        elif short:
            so_size = 0.0
    if so_limit is not None and so_size >= MIN_NOTIONAL:
        so_qty = qty_from_notional(cfg.symbol, so_size, so_limit)
    if so_qty > 0:
        print(f"ARM_{tag}_SO limit={_px(so_limit)} qty={so_qty}", flush=True)
        orders.append({
            "side": "SELL" if short else "BUY",
            "qty": so_qty,
            "price": so_limit,
            "position_side": tag,
            "so": True,
        })
        leg["await_so_reclaim"] = True
    tp = avg * (1.0 - cfg.tp_pct) if short else avg * (1.0 + cfg.tp_pct)
    rules = um._symbol_rules[cfg.symbol]
    exit_qty = float(um.round_down(qty, rules.quantity_step))
    if exit_qty > 0 and tp > 0:
        print(f"ARM_{tag}_TP tp={_px(tp)} qty={exit_qty}", flush=True)
        orders.append({
            "side": "BUY" if short else "SELL",
            "qty": exit_qty,
            "price": tp,
            "position_side": tag,
        })
    return orders


def on_hedge_bar(cfg: BotConfig, row, state: dict, log: CsvLogger) -> dict:
    state = _ensure_legs(state)
    open_key = str(row.open_time)
    if state.get("last_signal_open") == open_key:
        return state
    state["last_signal_open"] = open_key
    mark = float(row.close)
    wallet = clip_from_wallet(cfg) if um.API_KEY or True else 0.0
    if um.API_KEY:
        book = um.position_book(cfg.symbol)
        cash = float(um.usdt_futures_wallet()["wallet"])
    else:
        book = {
            "LONG": {"positionAmt": "0", "entryPrice": "0"},
            "SHORT": {"positionAmt": "0", "entryPrice": "0"},
        }
        cash = wallet
    long_qty = _pos_qty(book["LONG"])
    short_qty = _pos_qty(book["SHORT"])
    long_avg = _pos_avg(book["LONG"], mark, long_qty)
    short_avg = _pos_avg(book["SHORT"], mark, short_qty)
    cap = _size_clip(max(cash, wallet), cfg)
    o, h, l = float(row.open), float(row.high), float(row.low)
    lp = account_liq(cash, long_qty, long_avg, short_qty, short_avg)
    loss = float(cfg.sl_loss or 0.0)
    flatten: list[tuple[str, float, str]] = []
    acct_long = lp is not None and long_qty > 0 and min(o, l) <= lp < long_avg
    acct_short = lp is not None and short_qty > 0 and max(o, h) >= lp > short_avg
    if acct_long or acct_short:
        if long_qty > 0:
            flatten.append(("LONG", long_qty, "LIQUIDATION"))
        if short_qty > 0:
            flatten.append(("SHORT", short_qty, "LIQUIDATION"))
    else:
        if long_qty > 0:
            sl = side_stop(long_avg, lp, loss, False)
            if sl is not None and min(o, l) <= sl:
                flatten.append(("LONG", long_qty, "SL"))
        if short_qty > 0:
            sl = side_stop(short_avg, lp, loss, True)
            if sl is not None and max(o, h) >= sl:
                flatten.append(("SHORT", short_qty, "SL"))
        for name, qty, avg, up in (
            ("LONG", long_qty, long_avg, False),
            ("SHORT", short_qty, short_avg, True),
        ):
            if qty <= 0 or any(item[0] == name for item in flatten):
                continue
            leg = state["short" if up else "long"]
            probe = (2.0 * avg - mark) if up else mark
            sig = stale_exit_reason(
                _parse_ts(leg.get("basket_start")),
                row.close_time,
                probe,
                avg,
                cfg.stale_loss_pct,
                cfg.stale_days,
                cfg.max_hold_days,
                fills=int(leg.get("fills") or 0),
            )
            if sig:
                flatten.append((name, qty, sig))
    live = (not cfg.dry_run) and cfg.allow_orders
    if flatten and live:
        um.cancel_symbol_orders(cfg.symbol)
    for name, qty, reason in flatten:
        _flatten_side(cfg, qty, reason, log, name)
        _clear_leg(state["long" if name == "LONG" else "short"], reenter=reason in ("STALE", "TIME", "GIVEUP"))
    if flatten and live and um.API_KEY:
        book = um.position_book(cfg.symbol)
        long_qty = _pos_qty(book["LONG"])
        short_qty = _pos_qty(book["SHORT"])
        long_avg = _pos_avg(book["LONG"], mark, long_qty)
        short_avg = _pos_avg(book["SHORT"], mark, short_qty)
        if long_qty > 0:
            state["long"]["basket_start"] = state["long"].get("basket_start") or _iso(row.close_time)
        if short_qty > 0:
            state["short"]["basket_start"] = state["short"].get("basket_start") or _iso(row.close_time)
    elif flatten:
        long_qty = 0.0 if any(item[0] == "LONG" for item in flatten) else long_qty
        short_qty = 0.0 if any(item[0] == "SHORT" for item in flatten) else short_qty
    if long_qty > 0:
        state["long"]["reenter_from_stale"] = False
    if short_qty > 0:
        state["short"]["reenter_from_stale"] = False
    long_upl = long_qty * (mark - long_avg) if long_qty > 0 else 0.0
    short_upl = short_qty * (short_avg - mark) if short_qty > 0 else 0.0
    marked = cash + long_upl + short_upl
    peak = rolling_wallet_peak(state, row.close_time, marked, cfg.peak_lookback_days)
    state["marked_pocket"] = marked
    state["wallet_peak"] = peak
    print(
        f"BAR {row.close_time} close={_px(mark)} long={long_qty:.4f}@{_px(long_avg) if long_qty else 0} "
        f"short={short_qty:.4f}@{_px(short_avg) if short_qty else 0} "
        f"wallet={cash:.2f} marked={marked:.2f} peak={peak:.2f}",
        flush=True,
    )
    orders = []
    orders += _arm_hedge_leg(cfg, row, state["long"], long_qty, long_avg, cap, False, marked, peak)
    orders += _arm_hedge_leg(cfg, row, state["short"], short_qty, short_avg, cap, True, marked, peak)
    if not live:
        return state
    rules = um._symbol_rules[cfg.symbol]
    wanted = []
    for order in orders:
        px = float(um.round_down(order["price"], rules.price_tick))
        wanted.append([order["position_side"], order["side"], px])
    if wanted and wanted == state.get("working_orders") and not flatten:
        print("KEEP_ORDERS", wanted, flush=True)
        return state
    if not flatten:
        um.cancel_symbol_orders(cfg.symbol)
    for order in orders:
        um.place_limit(
            cfg.symbol, order["side"], order["qty"], order["price"], False, "GTC",
            position_side=order["position_side"],
        )
    state["working_orders"] = wanted
    return state


def run_um(cfg: BotConfig) -> None:
    log = CsvLogger(_env("EVENT_CSV_PATH", "data/events.csv"), DEFAULT_EVENT_FIELDS)
    um.load_symbol_rules([cfg.symbol])
    try:
        if um.API_KEY:
            um.configure_symbol(cfg.symbol, cfg.leverage)
            if cfg.margin_type in ("ISOLATED", "CROSSED"):
                try:
                    um.signed_post("/fapi/v1/marginType", {"symbol": cfg.symbol, "marginType": cfg.margin_type})
                except requests.HTTPError as error:
                    body = {}
                    if error.response is not None:
                        try:
                            body = error.response.json()
                        except Exception:
                            body = {}
                    if body.get("code") != -4046:
                        raise
    except Exception as exc:
        print("CONFIGURE_WARN", type(exc).__name__, exc, flush=True)

    pos = report_account(cfg)
    pos = maybe_flatten_testnet(cfg, pos)
    state = load_state(cfg.state_path)
    if cfg.hedge:
        ensure_hedge_mode()
        state = _ensure_legs(state)
        if um.API_KEY:
            book = um.position_book(cfg.symbol)
            for name, row in (("long", book["LONG"]), ("short", book["SHORT"])):
                qty = _pos_qty(row)
                if qty > 0 and not state[name].get("basket_start"):
                    state[name]["basket_start"] = datetime.now(timezone.utc).isoformat()
                    state[name]["fills"] = max(int(state[name].get("fills") or 0), 1)
                    state[name]["last_fill"] = float(row.get("entryPrice") or 0)
                    if state[name].get("basket_clip") is None:
                        state[name]["basket_clip"] = _size_clip(clip_from_wallet(cfg), cfg)
                    print("ADOPT_POSITION", name, qty, state[name]["last_fill"], flush=True)
    else:
        qty = abs(float(pos.get("positionAmt") or 0))
        if qty > 0 and not state.get("basket_start"):
            state["basket_start"] = datetime.now(timezone.utc).isoformat()
            state["fills"] = max(int(state.get("fills") or 0), 1)
            state["last_fill"] = float(pos.get("entryPrice") or 0)
            if state.get("basket_clip") is None:
                state["basket_clip"] = _size_clip(clip_from_wallet(cfg), cfg)
            print("ADOPT_POSITION", qty, state["last_fill"], flush=True)
    save_state(cfg.state_path, state)

    print(
        f"DCA_BOT market=um symbol={cfg.symbol} interval={cfg.interval} hedge={cfg.hedge} "
        f"mr={cfg.mr_cap} tp={cfg.tp_pct} sl={cfg.sl_loss} so={cfg.so_style} "
        f"so_max={cfg.range_so_max} clip_usd={cfg.clip_usd} lev={cfg.leverage} "
        f"peak_skip={cfg.peak_skip_pct}/{cfg.peak_lookback_days}d "
        f"stale={cfg.stale_loss_pct}/{cfg.stale_days}d dry={cfg.dry_run} "
        f"orders={cfg.allow_orders} base={um.BASE}",
        flush=True,
    )
    while True:
        try:
            df = klines_um(cfg.symbol, cfg.interval)
            row = df.iloc[-1]
            if cfg.hedge:
                state = on_hedge_bar(cfg, row, state, log)
            else:
                state = on_completed_bar(cfg, row, state, log)
            save_state(cfg.state_path, state)
        except Exception as exc:
            print("LOOP_ERROR", type(exc).__name__, exc, flush=True)
            log.log("loop_error", reason=type(exc).__name__, response_body=str(exc)[:500])
        time.sleep(max(cfg.poll_sec, 5.0))


def main() -> None:
    cfg = load_config()
    refuse_if_unsafe(cfg)
    run_um(cfg)


if __name__ == "__main__":
    main()
