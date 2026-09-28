#!/usr/bin/env python3
"""Product F1: leveraged BTCUSDT DCA with technical limit rest prices.

Separate product from the minutes-to-one-hour scalp bot. Research-only.
Uses public 1h klines via experiments.htf.data. Does not load credentials.
"""

from __future__ import annotations

import os
from collections import deque
from dataclasses import dataclass
from datetime import timedelta
from math import sqrt

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from experiments.htf.data import SYMBOL, load_klines
from experiments.htf.indicators import ema


RESULTS_DIR = "results_dca"
START_EQUITY = 10_000.0
MMR = 0.004
MR_CAP = 0.03
MR_EMERGENCY = 0.80
MAX_SAFETY = 5
VOLUME_SCALE = 1.25
GEO_STEP = 0.010
GEO_SCALE = 1.15
MIN_DIP = 0.003
MIN_SO_DIP = 0.006
RESIST_BUFFER = 0.003
TP_PCT = 0.020
MIN_NOTIONAL = 100.0
HEADROOM = 0.90
SWING = 12
BAR_SCALE = {"1h": 1, "15m": 4, "5m": 12, "1m": 60}
RANGE_DAYS = 7
RANGE_TOP_FRAC = 0.75
MIN_RANGE_FRAC = 0.06
RANGE_DUMP_EXPAND = 0.02
BARS_PER_YEAR = 365 * 24
FULL_BASKET_CAP = 800
FUNDING_PLACEHOLDER = 0.0001
PEAK_LOOKBACK_DAYS = 90.0


class SlEntryBrake:
    """After a stop, block or shrink the next basket until time and/or 7d-high reclaim.

    30d peak-skip re-enters a dump as soon as the wallet high rolls off. This brake
    is independent: it keys off the SL itself, not the decaying peak.
    """

    RISK = frozenset({"SL50", "HARD", "LIQUIDATION", "EMERGENCY"})

    def __init__(
        self,
        cooldown_days: float | None = None,
        high_reclaim: bool = False,
        after_sl_clip: float | None = None,
        dump_reclaim: bool = False,
    ):
        days = 0.0 if cooldown_days is None else float(cooldown_days)
        self.cooldown = timedelta(days=days) if days > 0 else None
        self.high_reclaim = bool(high_reclaim)
        self.dump_reclaim = bool(dump_reclaim)
        probe = None if after_sl_clip is None else float(after_sl_clip)
        self.probe = probe if probe is not None and probe > 0 else None
        self.until = None
        self.need_px = None

    def enabled(self) -> bool:
        return self.cooldown is not None or self.high_reclaim or self.dump_reclaim

    def on_exit(
        self,
        reason: str,
        exit_time,
        range_high: float | None,
        marked: float | None = None,
        peak: float | None = None,
        skip_pct: float | None = None,
        dump_high: float | None = None,
    ) -> None:
        if not self.enabled() or reason not in self.RISK:
            return
        if self.dump_reclaim:
            if dump_high is not None and dump_high > 0:
                self.need_px = float(dump_high)
            return
        # Wallet-hole gate is only for clip-shrink / calendar sit. A dump
        # is defined by price vs the frozen high, not by 15% wallet dd.
        if skip_pct is not None and float(skip_pct) > 0 and peak and marked is not None:
            if marked >= float(peak) * (1.0 - float(skip_pct)):
                return
        if self.cooldown is not None:
            self.until = exit_time + self.cooldown
        if self.high_reclaim:
            self.need_px = float(range_high) if range_high is not None and range_high > 0 else None

    def _clear(self, ts, close: float) -> None:
        if self.until is not None and ts >= self.until:
            self.until = None
        if self.need_px is not None and close >= self.need_px:
            self.need_px = None

    def clip_scale(self, ts, close: float) -> float | None:
        """1.0 = full clip. None = skip new basket. 0<x<1 = probe size until clear."""
        if not self.enabled():
            return 1.0
        self._clear(ts, close)
        if self.until is None and self.need_px is None:
            return 1.0
        if self.probe is None:
            return None
        return self.probe


class AfterTpGate:
    """After a TP, block the next basket if price is reversing or the 7d low is dumping.

    Dip entries that hold the TP-bar 7d low still pass. A breakdown after a win does not.
    """

    def __init__(self, dump: bool = False, giveback_pct: float | None = None):
        self.dump = bool(dump)
        gb = None if giveback_pct is None else float(giveback_pct)
        self.giveback = gb if gb is not None and gb > 0 else None
        self.tp_low = None
        self.tp_exit = None

    def enabled(self) -> bool:
        return self.dump or self.giveback is not None

    def on_exit(self, reason: str, exit_px: float, range_low: float | None) -> None:
        if not self.enabled():
            return
        if reason != "TP":
            return
        self.tp_exit = float(exit_px) if exit_px else None
        self.tp_low = float(range_low) if range_low is not None and range_low > 0 else None

    def blocked(self, close: float, range_low: float | None) -> bool:
        if not self.enabled() or self.tp_exit is None:
            return False
        if self.giveback is not None and close < self.tp_exit * (1.0 - self.giveback):
            return True
        if (
            self.dump
            and range_low is not None
            and range_low > 0
            and self.tp_low is not None
            and range_low < self.tp_low * (1.0 - RANGE_DUMP_EXPAND)
        ):
            return True
        return False


class RollingMax:
    """Max of values whose timestamps fall inside lookback. lookback<=0 is all-time."""

    def __init__(self, lookback_days: float | None):
        days = 0.0 if lookback_days is None else float(lookback_days)
        self.lookback = None if days <= 0 else timedelta(days=days)
        self.hist: deque = deque()
        self.maxq: deque = deque()
        self.all_time: float | None = None

    def update(self, ts, value: float) -> float:
        if self.all_time is None or value > self.all_time:
            self.all_time = value
        if self.lookback is None:
            return float(self.all_time)
        self.hist.append((ts, value))
        while self.maxq and self.maxq[-1][1] <= value:
            self.maxq.pop()
        self.maxq.append((ts, value))
        cutoff = ts - self.lookback
        while self.hist and self.hist[0][0] < cutoff:
            self.hist.popleft()
        while self.maxq and self.maxq[0][0] < cutoff:
            self.maxq.popleft()
        if self.maxq:
            return float(self.maxq[0][1])
        return float(value)

WEIGHTS = np.array([VOLUME_SCALE ** i for i in range(1 + MAX_SAFETY)], dtype=float)
WEIGHTS = WEIGHTS / WEIGHTS.sum()

SPLITS = {
    "train": (pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2025-07-01", tz="UTC")),
    "validate": (pd.Timestamp("2025-07-01", tz="UTC"), pd.Timestamp("2026-03-01", tz="UTC")),
    "holdout": (pd.Timestamp("2026-03-01", tz="UTC"), pd.Timestamp.max.tz_localize("UTC")),
}


@dataclass(frozen=True)
class CostModel:
    name: str
    maker_fee: float
    maker_slip: float
    taker_fee: float
    taker_slip: float


COST_A = CostModel("A_optimistic", 0.0002, 0.0, 0.0004, 0.00005)
COST_B = CostModel("B_decision", 0.0002, 0.000025, 0.0005, 0.00010)


def slipped(price: float, side: int, is_entry: bool, slip: float) -> float:
    return price * (1 + side * slip) if is_entry else price * (1 - side * slip)


def funding_hit(ts: pd.Timestamp) -> bool:
    return ts.minute == 0 and ts.hour in (0, 8, 16)


def notional_cap(wallet: float, mr_cap: float = MR_CAP) -> float:
    if wallet <= 0:
        return 0.0
    return mr_cap * wallet / MMR


def margin_ratio(qty: float, mark: float, wallet_cash: float, avg: float) -> float:
    if qty <= 0:
        return 0.0
    wallet = wallet_cash + qty * (mark - avg)
    if wallet <= 0:
        return 1.0
    return (qty * mark * MMR) / wallet


def liq_price(qty: float, avg: float, wallet_cash: float) -> float | None:
    if qty <= 0:
        return None
    denom = qty * (MMR - 1.0)
    if denom == 0:
        return None
    return (wallet_cash - qty * avg) / denom


def equity_stop_price(qty: float, avg: float, wallet_cash: float, start_equity: float, frac: float) -> float | None:
    if qty <= 0 or start_equity <= 0 or frac <= 0:
        return None
    return avg + (frac * start_equity - wallet_cash) / qty


def unit_loss_stop_price(qty: float, avg: float, unit_equity: float, loss_frac: float) -> float | None:
    if qty <= 0 or unit_equity <= 0 or loss_frac <= 0:
        return None
    return avg - (loss_frac * unit_equity) / qty


def tighter_stop(*levels: float | None) -> float | None:
    ok = [float(x) for x in levels if x is not None and x > 0]
    return max(ok) if ok else None


def hard_stop_from_avg(avg: float, pct: float | None) -> float | None:
    """Price stop pct below average. pct=0.50 → 50% off avg. pct>=1 is price 0 (ignored)."""
    if pct is None or pct <= 0 or pct >= 1.0 or avg <= 0:
        return None
    px = avg * (1.0 - pct)
    return px if px > 0 else None


def hard_stop_from_basket(qty: float, avg: float, clip: float, frac: float | None) -> float | None:
    """Flatten when dollar loss = frac of the opened pocket. frac=1.0 → 100% of basket_clip.
    At 1× (notional ≈ clip) this is price ~0 and is ignored. After SOs raise notional it binds."""
    if frac is None or frac <= 0 or qty <= 0 or clip <= 0 or avg <= 0:
        return None
    px = avg - (frac * clip) / qty
    return px if px > 0 else None


def stale_exit_reason(
    start,
    now,
    mark: float,
    avg: float,
    loss_pct: float | None,
    min_days: float | None,
    max_hold_days: float | None,
    fills: int = 0,
    giveup_pct: float | None = None,
    giveup_days: float | None = None,
    giveup_min_fills: int = 3,
) -> str | None:
    """TIME calendar cap; STALE deep+old; GIVEUP laddered and still underwater."""
    if start is None or avg <= 0 or mark <= 0:
        return None
    age = (now - start).total_seconds() / 86400.0
    if max_hold_days is not None and max_hold_days > 0 and age >= float(max_hold_days):
        return "TIME"
    if (
        giveup_pct is not None and giveup_days is not None
        and float(giveup_pct) > 0 and float(giveup_days) > 0
        and int(fills) >= int(giveup_min_fills)
        and age >= float(giveup_days)
        and mark <= avg * (1.0 - float(giveup_pct))
    ):
        return "GIVEUP"
    if (
        loss_pct is not None and min_days is not None
        and float(loss_pct) > 0 and float(min_days) > 0
        and age >= float(min_days)
        and mark <= avg * (1.0 - float(loss_pct))
    ):
        return "STALE"
    return None


def stop_from_liq(avg: float, liq: float | None, loss_frac: float) -> float | None:
    """SL between avg and liq. loss_frac=0.80 → 80% of the drop toward liq, always above liq."""
    if liq is None or avg <= 0 or loss_frac <= 0:
        return None
    if liq >= avg:
        return None
    sl = avg - loss_frac * (avg - liq)
    if sl <= liq + 1e-12 or sl >= avg:
        return None
    return sl


def sl_hold_outcome_um(
    rows: list,
    start_i: int,
    o: float,
    h: float,
    l: float,
    qty: float,
    avg: float,
    wallet_cash: float,
    take_profit: float,
) -> str:
    """If this SL is skipped, freeze size/avg (no more SOs): liq, tp, or neither."""
    tp = avg * (1.0 + take_profit)
    lp = liq_price(qty, avg, wallet_cash)
    if lp is not None and min(o, l) <= lp:
        return "liq"
    if margin_ratio(qty, l, wallet_cash, avg) >= MR_EMERGENCY:
        return "liq"
    if h >= tp:
        return "tp"
    cash = wallet_cash
    for row in rows[start_i + 1:]:
        o2, h2, l2, c2 = float(row.open), float(row.high), float(row.low), float(row.close)
        lp = liq_price(qty, avg, cash)
        if lp is not None and min(o2, l2) <= lp:
            return "liq"
        if margin_ratio(qty, l2, cash, avg) >= MR_EMERGENCY:
            return "liq"
        if h2 >= tp:
            return "tp"
        if funding_hit(row.open_time):
            cash -= qty * c2 * FUNDING_PLACEHOLDER
    return "neither"


def add_dca_features(df: pd.DataFrame, interval: str = "1h") -> pd.DataFrame:
    """EMA/swing use the same wall-clock as F6 1h (21h / 55h / 12h)."""
    if interval not in BAR_SCALE:
        raise ValueError(f"unsupported interval: {interval}")
    scale = BAR_SCALE[interval]
    out = df.copy()
    e21, e55, swing = 21 * scale, 55 * scale, SWING * scale
    out["ema21"] = ema(out.close, e21)
    out["ema55"] = ema(out.close, e55)
    out["support"] = out.low.shift(1).rolling(swing, min_periods=swing).min()
    out["resist"] = out.high.shift(1).rolling(swing, min_periods=swing).max()
    range_bars = RANGE_DAYS * 24 * scale
    out["range_high"] = out.high.shift(1).rolling(range_bars, min_periods=range_bars).max()
    out["range_low"] = out.low.shift(1).rolling(range_bars, min_periods=range_bars).min()
    return out.dropna().reset_index(drop=True)


def prepare_data() -> pd.DataFrame:
    return add_dca_features(load_klines("1h"), "1h")


def technical_dip(ema21: float, support: float, ceiling: float, min_frac: float) -> float | None:
    cap = ceiling * (1.0 - min_frac)
    levels = [level for level in (ema21, support) if pd.notna(level) and 0 < level <= cap]
    return max(levels) if levels else None


def safety_limit(last_fill: float, so_index: int, ema21: float, support: float) -> float:
    geo = last_fill * (1.0 - GEO_STEP * (GEO_SCALE ** so_index))
    tech = technical_dip(ema21, support, last_fill, MIN_SO_DIP)
    if tech is None:
        return geo
    return max(geo, tech)


def planned_notional(basket_cap: float, fill_index: int) -> float:
    return float(WEIGHTS[fill_index] * basket_cap)


SO_GEOMETRIC = "geometric"
SO_TECHNICAL = "technical"
SO_RANGE = "range"


def range_near_ath(close: float, range_low: float, range_high: float) -> bool:
    if not pd.notna(range_low) or not pd.notna(range_high) or range_high <= range_low or close <= 0:
        return True
    return close > range_low + RANGE_TOP_FRAC * (range_high - range_low)


def range_too_tight(ceiling: float, range_low: float, min_frac: float = MIN_RANGE_FRAC) -> bool:
    if not pd.notna(range_low) or ceiling <= 0 or range_low <= 0:
        return True
    return (ceiling - range_low) / ceiling < min_frac


def new_basket_blocked(
    close: float,
    ema55: float,
    resist: float,
    so_style: str,
    range_low: float,
    range_high: float,
    reenter: bool,
) -> bool:
    """Normal entries need trend + 7d room. After a stale cut, only skip the highs."""
    if close >= resist * (1.0 - RESIST_BUFFER):
        return True
    if reenter:
        return False
    if close <= ema55:
        return True
    if so_style == SO_RANGE:
        if range_near_ath(close, range_low, range_high) or range_too_tight(close, range_low):
            return True
    return False


def new_basket_limit(close: float, ema21: float, support: float, reenter: bool) -> float | None:
    limit = technical_dip(ema21, support, close, MIN_DIP)
    if limit is not None:
        return limit
    if reenter and close > 0:
        return close * (1.0 - MIN_DIP)
    return None


def range_so_limit(last_fill: float, range_low: float, so_count: int, max_so: int = MAX_SAFETY) -> float | None:
    """Next SO is 1/remaining_slots of the gap from last fill down to 7d low."""
    slots = max_so - so_count
    if slots < 1 or last_fill <= 0 or not pd.notna(range_low) or range_low <= 0:
        return None
    if range_low >= last_fill:
        return None
    gap = last_fill - range_low
    limit = last_fill - gap / slots
    if limit <= range_low or limit >= last_fill:
        return None
    if (last_fill - limit) / last_fill < MIN_SO_DIP:
        return None
    return limit


def range_so_dump_reason(
    close: float,
    support: float,
    live_range_low: float | None,
    so_floor: float | None,
) -> str | None:
    """Dump, not a dip: 7d low is making new lows, or 12h support is already broken."""
    if so_floor is not None and pd.notna(so_floor) and float(so_floor) > 0:
        live = float("nan") if live_range_low is None else float(live_range_low)
        if pd.notna(live) and live > 0 and live < float(so_floor) * (1.0 - RANGE_DUMP_EXPAND):
            return "dump_new_7d_low"
    if pd.notna(support) and close < float(support):
        return "dump_broke_12h_support"
    return None


def safety_order_plan(
    so_style: str,
    last_fill: float,
    so_count: int,
    fills: int,
    ema21: float,
    support: float,
    close: float,
    ema55: float,
    remaining: float,
    basket_cap: float,
    min_size: float = MIN_NOTIONAL,
    range_low: float | None = None,
    max_so: int | None = None,
    range_weight_size: bool = False,
    live_range_low: float | None = None,
    so_reclaim: bool = True,
) -> tuple[float, float] | None:
    """Limit and notional for the next SO, or None if no order this bar.

    geometric: F6 1%×1.15^n vs last fill, max() with structure, 1.25^n weights.
    technical: arm only on EMA21 / 12h support ≥0.6% below last fill.
    range: rungs vs frozen 7d low at first fill; skip if that low expands (dump)
    or 12h support is already broken.
    Size for technical/range = leftover MR / slots unless range_weight_size.
    """
    cap = MAX_SAFETY if max_so is None else max(1, int(max_so))
    if so_count >= cap or fills >= 1 + cap:
        return None
    if so_style == SO_TECHNICAL:
        if close <= ema55:
            return None
        if pd.notna(support) and close < float(support):
            return None
        limit = technical_dip(ema21, support, last_fill, MIN_SO_DIP)
        if limit is None:
            return None
        slots = MAX_SAFETY - so_count
        size = remaining * HEADROOM / slots
        if size < min_size:
            return None
        return limit, size
    if so_style == SO_RANGE:
        if so_reclaim:
            why = range_so_dump_reason(close, support, live_range_low, range_low)
            if why:
                return None
        lo = float("nan") if range_low is None else float(range_low)
        limit = range_so_limit(last_fill, lo, so_count, cap)
        if limit is None:
            return None
        if range_weight_size:
            size = min(planned_notional(basket_cap, fills), remaining * HEADROOM)
        else:
            slots = cap - so_count
            size = remaining * HEADROOM / slots
        if size < min_size:
            return None
        return limit, size
    limit = safety_limit(last_fill, so_count, ema21, support)
    size = min(planned_notional(basket_cap, fills), remaining * HEADROOM)
    if size < min_size:
        return None
    return limit, size


def run_dca(
    df: pd.DataFrame,
    cost: CostModel,
    mr_cap: float = MR_CAP,
    equity_stop_frac: float | None = None,
    size_equity: float | None = None,
    size_step_mult: float | None = None,
    start_equity: float = START_EQUITY,
    isolated: bool = False,
    so_style: str = SO_GEOMETRIC,
    tp_pct: float | None = None,
    sl_from_liq: bool = False,
    hard_sl_pct: float | None = None,
    hard_sl_basket: float | None = None,
    stale_loss_pct: float | None = None,
    stale_days: float | None = None,
    max_hold_days: float | None = None,
    entry_ttl_sec: float | None = None,
    giveup_pct: float | None = None,
    giveup_days: float | None = None,
    giveup_min_fills: int = 3,
    range_so_max: int | None = None,
    range_weight_size: bool = False,
    peak_skip_pct: float | None = None,
    so_reclaim: bool = True,
    peak_lookback_days: float | None = PEAK_LOOKBACK_DAYS,
    sl_cooldown_days: float | None = None,
    sl_high_reclaim: bool = False,
    after_sl_clip: float | None = None,
    price_dd_skip_pct: float | None = None,
    price_dd_lookback_days: float | None = None,
    sl_dump_lookback_days: float | None = None,
    after_tp_dump: bool = False,
    after_tp_giveback_pct: float | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    rows = list(df.itertuples(index=False))
    take_profit = TP_PCT if tp_pct is None else float(tp_pct)
    wallet_cash = 0.0 if isolated else start_equity
    idle = start_equity if isolated else 0.0
    qty = 0.0
    avg = 0.0
    last_fill = 0.0
    fills = 0
    so_count = 0
    basket_cap = 0.0
    basket_clip = 0.0
    basket_start = None
    basket_start_equity = 0.0
    pending_buy = None
    pending_kind = None
    pending_notional = 0.0
    pending_taker_gap = False
    pending_stale: str | None = None
    pending_armed_time = None
    basket_so_floor = None
    pending_so_floor = None
    await_so_reclaim = False
    reenter_from_stale = False
    wallet_peak = RollingMax(peak_lookback_days)
    dump_peak = RollingMax(sl_dump_lookback_days) if sl_dump_lookback_days is not None else None
    dump_px = 0.0
    sl_brake = SlEntryBrake(
        sl_cooldown_days, sl_high_reclaim, after_sl_clip,
        dump_reclaim=dump_peak is not None,
    )
    after_tp_gate = AfterTpGate(after_tp_dump, after_tp_giveback_pct)
    bar_range_high: float | None = None
    bar_range_low: float | None = None
    price_peak = RollingMax(price_dd_lookback_days) if (
        price_dd_skip_pct is not None and float(price_dd_skip_pct) > 0
        and price_dd_lookback_days is not None
    ) else None
    px_high = 0.0
    equity_peak = start_equity
    liquidated = False
    trades: list[dict] = []
    events: list[dict] = []
    equity_rows: list[dict] = []

    def mark_position(price: float) -> float:
        return wallet_cash + qty * (price - avg) if qty > 0 else wallet_cash

    def mark_wallet(price: float) -> float:
        return idle + mark_position(price) if isolated else mark_position(price)

    def close_basket(exit_time, exit_price: float, reason: str, fee_rate: float, slip: float, taker: bool) -> None:
        nonlocal wallet_cash, idle, qty, avg, last_fill, fills, so_count, basket_cap, basket_clip, basket_start
        nonlocal basket_start_equity, pending_buy, pending_kind, pending_notional, pending_taker_gap
        nonlocal pending_stale, reenter_from_stale, pending_armed_time, basket_so_floor, pending_so_floor
        nonlocal await_so_reclaim
        if qty <= 0:
            return
        px = slipped(exit_price, 1, False, slip)
        notional = qty * px
        fee = notional * fee_rate
        pnl = qty * (px - avg) - fee
        wallet_cash += qty * (px - avg) - fee
        trades.append({
            "cost_model": cost.name, "entry_time": basket_start, "exit_time": exit_time,
            "exit_reason": reason, "avg_entry": avg, "exit": px, "fills": fills,
            "safety_orders": so_count, "qty": qty, "pnl_net": pnl, "fees": fee,
            "hold_hours": max((exit_time - basket_start).total_seconds() / 3600, 0.0) if basket_start is not None else 0.0,
            "taker_exit": taker, "sl_hold": "",
        })
        events.append({"time": exit_time, "cost_model": cost.name, "event": reason, "price": px, "pnl": pnl})
        qty = 0.0
        avg = 0.0
        last_fill = 0.0
        fills = 0
        so_count = 0
        basket_cap = 0.0
        basket_clip = 0.0
        basket_start = None
        basket_start_equity = 0.0
        pending_buy = None
        pending_kind = None
        pending_notional = 0.0
        pending_taker_gap = False
        pending_stale = None
        pending_armed_time = None
        basket_so_floor = None
        pending_so_floor = None
        await_so_reclaim = False
        if reason in ("STALE", "TIME", "GIVEUP"):
            reenter_from_stale = True
        if isolated:
            if reason == "LIQUIDATION":
                wallet_cash = 0.0
            else:
                idle += max(wallet_cash, 0.0)
                wallet_cash = 0.0
        sl_brake.on_exit(
            reason, exit_time, bar_range_high,
            marked=idle + wallet_cash if isolated else wallet_cash,
            peak=equity_peak, skip_pct=peak_skip_pct,
            dump_high=dump_px if dump_peak is not None else None,
        )
        after_tp_gate.on_exit(reason, px, bar_range_low)

    def fill_buy(ts, raw_price: float, taker: bool) -> bool:
        nonlocal wallet_cash, idle, qty, avg, last_fill, fills, so_count, basket_cap, basket_clip, basket_start
        nonlocal basket_start_equity, pending_buy, pending_kind, pending_notional, pending_taker_gap
        nonlocal reenter_from_stale, pending_armed_time, basket_so_floor, pending_so_floor, await_so_reclaim
        if pending_buy is None or pending_notional < MIN_NOTIONAL:
            pending_armed_time = None
            return False
        fee_rate = cost.taker_fee if taker else cost.maker_fee
        slip = cost.taker_slip if taker else cost.maker_slip
        px = slipped(raw_price, 1, True, slip)
        add_qty = pending_notional / px
        fee = pending_notional * fee_rate
        if isolated and fills == 0:
            alloc = basket_clip if basket_clip > 0 else min(clip_for_wallet(idle), idle)
            if alloc < MIN_NOTIONAL or alloc > idle + 1e-9:
                pending_buy = None
                pending_kind = None
                pending_notional = 0.0
                pending_taker_gap = False
                pending_armed_time = None
                return False
            idle -= alloc
            wallet_cash = alloc
            basket_clip = alloc
        new_qty = qty + add_qty
        new_avg = (qty * avg + add_qty * px) / new_qty if new_qty else px
        new_cash = wallet_cash - fee
        post_mr = margin_ratio(new_qty, px, new_cash, new_avg)
        if post_mr > mr_cap + 1e-9:
            events.append({"time": ts, "cost_model": cost.name, "event": "skip_mr_cap", "price": px, "pnl": 0.0})
            if isolated and fills == 0:
                idle += wallet_cash
                wallet_cash = 0.0
            pending_buy = None
            pending_kind = None
            pending_notional = 0.0
            pending_taker_gap = False
            pending_armed_time = None
            return False
        wallet_cash = new_cash
        qty = new_qty
        avg = new_avg
        last_fill = px
        if fills == 0:
            basket_start = ts
            basket_start_equity = new_cash
            reenter_from_stale = False
            if pending_so_floor is not None:
                basket_so_floor = pending_so_floor
        fills += 1
        if pending_kind == "so":
            so_count += 1
            if so_reclaim:
                await_so_reclaim = True
        events.append({"time": ts, "cost_model": cost.name, "event": pending_kind or "buy", "price": px, "pnl": -fee})
        pending_buy = None
        pending_kind = None
        pending_notional = 0.0
        pending_taker_gap = False
        pending_armed_time = None
        return True

    def clip_for_wallet(wallet: float) -> float:
        if size_equity is None:
            return wallet
        clip = size_equity
        if size_step_mult is not None and wallet + 1e-9 >= size_step_mult * start_equity:
            clip = size_equity * size_step_mult
        return clip

    def arm_next_buy(row) -> None:
        nonlocal pending_buy, pending_kind, pending_notional, pending_taker_gap, basket_cap, basket_clip
        nonlocal pending_armed_time, pending_so_floor, await_so_reclaim
        pending_taker_gap = False
        pos_wallet = mark_position(float(row.close))
        plan_base = idle if isolated and qty <= 0 else (pos_wallet if isolated else mark_wallet(float(row.close)))
        remaining = notional_cap(plan_base, mr_cap) - qty * float(row.close)
        if remaining < MIN_NOTIONAL:
            pending_buy = None
            pending_armed_time = None
            return
        if qty <= 0:
            close = float(row.close)
            marked = mark_wallet(close)
            if (
                peak_skip_pct is not None and float(peak_skip_pct) > 0
                and equity_peak > 0
                and marked < equity_peak * (1.0 - float(peak_skip_pct))
            ):
                pending_buy = None
                pending_armed_time = None
                return
            sl_scale = sl_brake.clip_scale(row.close_time, close)
            if sl_scale is None:
                pending_buy = None
                pending_armed_time = None
                return
            live_lo = float(row.range_low) if hasattr(row, "range_low") else None
            if after_tp_gate.blocked(close, live_lo):
                pending_buy = None
                pending_armed_time = None
                return
            if (
                price_peak is not None
                and px_high > 0
                and close < px_high * (1.0 - float(price_dd_skip_pct))
            ):
                pending_buy = None
                pending_armed_time = None
                return
            if new_basket_blocked(
                close, float(row.ema55), float(row.resist), so_style,
                float(row.range_low), float(row.range_high), reenter_from_stale,
            ):
                pending_buy = None
                pending_armed_time = None
                return
            limit = new_basket_limit(close, float(row.ema21), float(row.support), reenter_from_stale)
            if limit is None:
                pending_buy = None
                pending_armed_time = None
                return
            plan_wallet = clip_for_wallet(plan_base)
            if isolated:
                plan_wallet = min(plan_wallet, idle)
            if sl_scale != 1.0:
                plan_wallet *= sl_scale
            basket_clip = plan_wallet
            basket_cap = notional_cap(plan_wallet, mr_cap) * HEADROOM
            size = min(planned_notional(basket_cap, 0), remaining * HEADROOM)
            if size < MIN_NOTIONAL:
                pending_buy = None
                pending_armed_time = None
                return
            prev = pending_buy
            pending_buy = limit
            pending_kind = "base"
            pending_notional = size
            pending_so_floor = float(row.range_low) if hasattr(row, "range_low") else None
            if prev is None or abs(float(prev) - limit) / limit >= 0.001:
                pending_armed_time = row.close_time
            return
        if so_reclaim and await_so_reclaim:
            if float(row.close) < float(row.ema21):
                pending_buy = None
                pending_armed_time = None
                return
            await_so_reclaim = False
        live_lo = float(row.range_low) if hasattr(row, "range_low") else None
        floor = live_lo if not so_reclaim else (basket_so_floor if basket_so_floor is not None else live_lo)
        plan = safety_order_plan(
            so_style, last_fill, so_count, fills,
            float(row.ema21), float(row.support), float(row.close), float(row.ema55),
            remaining, basket_cap, range_low=floor,
            max_so=range_so_max, range_weight_size=range_weight_size,
            live_range_low=live_lo,
            so_reclaim=so_reclaim,
        )
        if plan is None:
            pending_buy = None
            pending_armed_time = None
            return
        limit, size = plan
        pending_buy = limit
        pending_kind = "so"
        pending_notional = size

    for i, row in enumerate(rows):
        if liquidated:
            equity_rows.append({"time": row.close_time, "equity": max(wallet_cash, 0.0), "cost_model": cost.name, "mr": 1.0, "in_pos": False})
            continue
        o, h, l, c = float(row.open), float(row.high), float(row.low), float(row.close)
        if hasattr(row, "range_high") and pd.notna(row.range_high):
            bar_range_high = float(row.range_high)
        else:
            bar_range_high = None
        if hasattr(row, "range_low") and pd.notna(row.range_low):
            bar_range_low = float(row.range_low)
        else:
            bar_range_low = None
        skip_base_arm = False
        if (
            qty <= 0
            and pending_kind == "base"
            and pending_buy is not None
            and entry_ttl_sec is not None
            and float(entry_ttl_sec) > 0
            and pending_armed_time is not None
            and (row.open_time - pending_armed_time).total_seconds() >= float(entry_ttl_sec)
        ):
            pending_buy = None
            pending_kind = None
            pending_notional = 0.0
            pending_armed_time = None
            skip_base_arm = True
        if pending_stale and qty > 0:
            reason = stale_exit_reason(
                basket_start, row.open_time, o, avg, stale_loss_pct, stale_days, max_hold_days,
                fills=fills, giveup_pct=giveup_pct, giveup_days=giveup_days,
                giveup_min_fills=giveup_min_fills,
            ) or (pending_stale if pending_stale == "TIME" else None)
            pending_stale = None
            if reason:
                hold = sl_hold_outcome_um(
                    rows, i, o, h, l, qty, avg, wallet_cash, take_profit,
                )
                close_basket(row.close_time, o, reason, cost.taker_fee, cost.taker_slip, True)
                if trades:
                    trades[-1]["sl_hold"] = hold
        if qty > 0:
            lp = liq_price(qty, avg, wallet_cash)
            loss_frac = None if equity_stop_frac is None else (1.0 - equity_stop_frac)
            if loss_frac is None or loss_frac <= 0:
                sp = None
            elif sl_from_liq:
                sp = stop_from_liq(avg, lp, loss_frac)
            elif basket_clip > 0:
                sp = unit_loss_stop_price(qty, avg, basket_clip, loss_frac)
            elif size_equity is not None:
                sp = unit_loss_stop_price(qty, avg, size_equity, loss_frac)
            else:
                sp = equity_stop_price(qty, avg, wallet_cash, basket_start_equity, equity_stop_frac)
            hp = tighter_stop(
                hard_stop_from_avg(avg, hard_sl_pct),
                hard_stop_from_basket(qty, avg, basket_clip, hard_sl_basket),
            )
            sp = tighter_stop(sp, hp)
            hits = []
            if sp is not None and min(o, l) <= sp:
                kind = "HARD" if hp is not None and abs(sp - hp) <= 1e-9 else "SL50"
                hits.append((sp if o > sp else o, kind))
            if lp is not None and min(o, l) <= lp:
                hits.append((lp if o > lp else o, "LIQUIDATION"))
            if hits:
                px, reason = max(hits, key=lambda item: (item[0], item[1] != "LIQUIDATION"))
                hold = ""
                if reason in ("SL50", "HARD"):
                    hold = sl_hold_outcome_um(
                        rows, i, o, h, l, qty, avg, wallet_cash, take_profit,
                    )
                close_basket(row.close_time, px, reason, cost.taker_fee, cost.taker_slip, True)
                if reason in ("SL50", "HARD") and trades:
                    trades[-1]["sl_hold"] = hold
                if reason == "LIQUIDATION":
                    wallet_cash = 0.0
                    if isolated:
                        pass
                    else:
                        liquidated = True
                        equity_rows.append({"time": row.close_time, "equity": 0.0, "cost_model": cost.name, "mr": 1.0, "in_pos": False})
                        continue
            if qty > 0 and margin_ratio(qty, l, wallet_cash, avg) >= MR_EMERGENCY:
                close_basket(row.close_time, l, "EMERGENCY", cost.taker_fee, cost.taker_slip, True)
        tp = avg * (1.0 + take_profit) if qty > 0 else None
        so_hit = pending_buy is not None and qty >= 0 and l <= pending_buy
        tp_hit = tp is not None and h >= tp
        if so_hit and tp_hit and qty > 0:
            tp_hit = False
        gapped = pending_buy is not None and o < pending_buy
        if gapped:
            fill_buy(row.open_time, o, True)
        elif so_hit:
            fill_buy(row.open_time, pending_buy, False)
        if qty > 0 and tp_hit:
            close_basket(row.close_time, tp, "TP", cost.maker_fee, cost.maker_slip, False)
        if qty > 0 and funding_hit(row.open_time):
            fund = qty * c * FUNDING_PLACEHOLDER
            wallet_cash -= fund
        if skip_base_arm:
            pending_buy = None
            pending_kind = None
            pending_notional = 0.0
            pending_armed_time = None
        else:
            arm_next_buy(row)
        if qty > 0:
            sig = stale_exit_reason(
                basket_start, row.close_time, c, avg, stale_loss_pct, stale_days, max_hold_days,
                fills=fills, giveup_pct=giveup_pct, giveup_days=giveup_days,
                giveup_min_fills=giveup_min_fills,
            )
            if sig:
                if i == len(rows) - 1:
                    close_basket(row.close_time, c, sig, cost.taker_fee, cost.taker_slip, True)
                else:
                    pending_stale = sig
        mr = margin_ratio(qty, c, wallet_cash, avg) if qty > 0 else 0.0
        eq = mark_wallet(c)
        equity_peak = wallet_peak.update(row.close_time, eq)
        if price_peak is not None:
            px_high = price_peak.update(row.close_time, h)
        if dump_peak is not None:
            dump_px = dump_peak.update(row.close_time, h)
        equity_rows.append({"time": row.close_time, "equity": eq, "cost_model": cost.name, "mr": mr, "in_pos": qty > 0})

    last = rows[-1]
    last_px = float(last.close)
    if liquidated:
        remaining = {
            "cost_model": cost.name, "as_of": last.close_time, "btc_close": last_px,
            "liquidated": True, "in_position": False, "remaining_mark_usdt": 0.0,
            "if_flatten_today_usdt": 0.0, "qty": 0.0, "avg_entry": float("nan"),
            "unrealized_usdt": 0.0, "mr_pct": 0.0, "start_equity_usdt": start_equity,
            "isolated": isolated, "idle_usdt": 0.0,
        }
    else:
        mark = mark_wallet(last_px)
        remaining = {
            "cost_model": cost.name, "as_of": last.close_time, "btc_close": last_px,
            "liquidated": False, "in_position": qty > 0, "remaining_mark_usdt": mark,
            "qty": qty, "avg_entry": avg if qty > 0 else float("nan"),
            "unrealized_usdt": qty * (last_px - avg) if qty > 0 else 0.0,
            "mr_pct": margin_ratio(qty, last_px, wallet_cash, avg) * 100 if qty > 0 else 0.0,
            "start_equity_usdt": start_equity, "isolated": isolated, "idle_usdt": idle if isolated else 0.0,
        }
        if qty > 0:
            px = slipped(last_px, 1, False, cost.taker_slip)
            fee = qty * px * cost.taker_fee
            remaining["if_flatten_today_usdt"] = (idle if isolated else 0.0) + wallet_cash + qty * (px - avg) - fee
            # leave the basket open; do not MTM-close for the trade list
        else:
            remaining["if_flatten_today_usdt"] = (idle if isolated else wallet_cash)
    equity_rows.append({
        "time": last.close_time, "equity": remaining["remaining_mark_usdt"],
        "cost_model": cost.name, "mr": remaining["mr_pct"] / 100.0, "in_pos": remaining["in_position"],
    })
    return pd.DataFrame(trades), pd.DataFrame(equity_rows), pd.DataFrame(events), remaining


def max_dd(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    return abs(float((equity / equity.cummax() - 1.0).min())) * 100


def _days(start, end) -> float:
    return (end - start).total_seconds() / 86400.0


def liquidation_stats(trades: pd.DataFrame, start_equity: float = START_EQUITY) -> pd.DataFrame:
    rows = []
    if trades.empty:
        return pd.DataFrame()
    for cost_name, group in trades.groupby("cost_model"):
        g = group.sort_values(["exit_time", "entry_time"]).reset_index(drop=True)
        risk = g[g.exit_reason.isin(["LIQUIDATION", "SL50"])]
        first_entry = g.entry_time.min()
        if risk.empty:
            rows.append({
                "cost_model": cost_name, "risk_exit": "", "liquidations": 0, "baskets_before_liq": len(g),
                "pnl_before_liq_usdt": float(g.pnl_net.sum()),
                "equity_before_doomed_usdt": start_equity + float(g.pnl_net.sum()),
                "liq_basket_pnl_usdt": 0.0, "liq_fees_usdt": 0.0,
                "ending_usdt": start_equity + float(g.pnl_net.sum()),
                "doomed_entry": "", "liq_time": "", "doomed_hold_days": 0.0,
                "days_first_entry_to_liq": 0.0, "days_last_tp_to_liq": 0.0, "last_tp_time": "",
            })
            continue
        liq = risk.iloc[0]
        prior = g[g.exit_time < liq.exit_time]
        prior_pnl = float(prior.pnl_net.sum()) if not prior.empty else 0.0
        tps = prior[prior.exit_reason == "TP"] if not prior.empty else prior
        last_tp = tps.iloc[-1] if not tps.empty else None
        rows.append({
            "cost_model": cost_name, "risk_exit": str(liq.exit_reason),
            "liquidations": int(liq.exit_reason == "LIQUIDATION"), "baskets_before_liq": len(prior),
            "pnl_before_liq_usdt": prior_pnl, "equity_before_doomed_usdt": start_equity + prior_pnl,
            "liq_basket_pnl_usdt": float(liq.pnl_net), "liq_fees_usdt": float(liq.fees),
            "ending_usdt": start_equity + prior_pnl + float(liq.pnl_net),
            "doomed_entry": str(liq.entry_time), "liq_time": str(liq.exit_time),
            "doomed_hold_days": float(liq.hold_hours) / 24.0,
            "days_first_entry_to_liq": _days(first_entry, liq.exit_time),
            "days_last_tp_to_liq": _days(last_tp.exit_time, liq.exit_time) if last_tp is not None else 0.0,
            "last_tp_time": str(last_tp.exit_time) if last_tp is not None else "",
        })
    return pd.DataFrame(rows)


def summarize(
    trades: pd.DataFrame, equity: pd.DataFrame, split: str, cost_name: str, product: str = "F1_dca_leverage",
    start_equity: float = START_EQUITY,
) -> dict:
    start, end = SPLITS[split]
    t = trades[(trades.entry_time >= start) & (trades.entry_time < end)].copy() if not trades.empty else trades
    e = equity[(equity.time >= start) & (equity.time < end)].copy() if not equity.empty else equity
    liq = int((t.exit_reason == "LIQUIDATION").sum()) if not t.empty else 0
    if t.empty:
        return {
            "product": product, "cost_model": cost_name, "split": split, "baskets": 0,
            "net_profit_usdt": 0.0, "ending_equity_usdt": start_equity, "net_profit_pct": 0.0,
            "profit_factor": 0.0, "win_rate": 0.0, "avg_hold_hours": 0.0,
            "avg_fills": 0.0, "max_dd_pct": max_dd(e.equity) if not e.empty else 0.0,
            "expectancy_usdt": 0.0, "fees_pct_start_equity": 0.0, "liquidations": 0,
            "tp_exits": 0, "sl50_exits": 0, "emergency_exits": 0, "mtm_exits": 0, "time_in_market_pct": 0.0,
            "max_mr": float(e.mr.max()) * 100 if not e.empty else 0.0, "sharpe_ann": 0.0,
        }
    wins = t[t.pnl_net > 0]
    losses = t[t.pnl_net <= 0]
    pf = wins.pnl_net.sum() / abs(losses.pnl_net.sum()) if not losses.empty and losses.pnl_net.sum() != 0 else np.inf
    days = max((min(end, t.exit_time.max()) - t.entry_time.min()).days + 1, 1)
    returns = e.equity.pct_change().fillna(0) if not e.empty else pd.Series(dtype=float)
    sharpe = returns.mean() / returns.std(ddof=0) * sqrt(BARS_PER_YEAR) if len(returns) > 2 and returns.std(ddof=0) > 0 else 0.0
    return {
        "product": product, "cost_model": cost_name, "split": split, "baskets": len(t),
        "net_profit_usdt": float(t.pnl_net.sum()), "ending_equity_usdt": start_equity + float(t.pnl_net.sum()),
        "net_profit_pct": t.pnl_net.sum() / start_equity * 100, "profit_factor": pf,
        "win_rate": (t.pnl_net > 0).mean() * 100, "avg_hold_hours": float(t.hold_hours.mean()),
        "avg_fills": float(t.fills.mean()), "max_dd_pct": max_dd(e.equity) if not e.empty else 0.0,
        "expectancy_usdt": float(t.pnl_net.mean()), "fees_pct_start_equity": t.fees.sum() / start_equity * 100,
        "liquidations": liq, "tp_exits": int((t.exit_reason == "TP").sum()),
        "sl50_exits": int((t.exit_reason == "SL50").sum()),
        "emergency_exits": int((t.exit_reason == "EMERGENCY").sum()),
        "mtm_exits": int((t.exit_reason == "MTM").sum()),
        "time_in_market_pct": (e.in_pos.mean() * 100) if not e.empty else 0.0,
        "max_mr": float(e.mr.max()) * 100 if not e.empty else 0.0, "sharpe_ann": sharpe,
    }


def decision(summary: pd.DataFrame, full_baskets: int) -> tuple[str, str]:
    if full_baskets <= 0 or full_baskets > FULL_BASKET_CAP:
        return "KILL", "Circuit breaker: no baskets or not a sparse DCA."
    rows = summary[summary.cost_model == COST_B.name]
    hold = rows[rows.split == "holdout"].iloc[0]
    train = rows[rows.split == "train"].iloc[0]
    validate = rows[rows.split == "validate"].iloc[0]
    if int(rows.liquidations.sum()) > 0:
        return "KILL", "Cost B path includes a liquidation."
    if hold.baskets < 8:
        return "INCONCLUSIVE", "Holdout baskets < 8; cannot pass this product."
    if hold.net_profit_pct < 0 or hold.expectancy_usdt <= 0:
        return "KILL", "Cost B holdout round-trip expectancy is not positive."
    if train.net_profit_pct < 0 or validate.net_profit_pct < 0:
        return "KILL", "Cost B train or validate lost money."
    return "PAPER-OTHER-PRODUCT", "Positive Cost B splits, but this is not a scalp and must not go into main.py."


def save_outputs(
    trades: pd.DataFrame,
    equities: pd.DataFrame,
    events: pd.DataFrame,
    summary: pd.DataFrame,
    results_dir: str,
    tag: str,
    mr_cap: float,
    remaining: pd.DataFrame | None = None,
    plots: bool = True,
) -> None:
    os.makedirs(results_dir, exist_ok=True)
    summary.to_csv(os.path.join(results_dir, "summary.csv"), index=False)
    if remaining is not None and not remaining.empty:
        remaining.to_csv(os.path.join(results_dir, "remaining_balance.csv"), index=False)
    liq = liquidation_stats(trades)
    if not liq.empty:
        liq.to_csv(os.path.join(results_dir, "liquidation.csv"), index=False)
    trades.to_csv(os.path.join(results_dir, "trades.csv"), index=False)
    events.to_csv(os.path.join(results_dir, "events.csv"), index=False)
    equities.to_csv(os.path.join(results_dir, f"equity_{tag}.csv"), index=False)
    if not plots:
        return
    eq = equities[equities.cost_model == COST_B.name]
    cap_pct = mr_cap * 100
    if not eq.empty:
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(eq.time, eq.equity, label=f"{tag} Cost B")
        ax.legend()
        ax.set_title(f"{tag} leveraged DCA equity - Cost B")
        fig.tight_layout()
        fig.savefig(os.path.join(results_dir, f"equity_{tag}.png"))
        plt.close(fig)
        fig, ax = plt.subplots(figsize=(12, 4))
        ax.plot(eq.time, (eq.equity / eq.equity.cummax() - 1) * 100)
        ax.set_title(f"{tag} underwater - Cost B")
        fig.tight_layout()
        fig.savefig(os.path.join(results_dir, f"underwater_{tag}.png"))
        plt.close(fig)
        fig, ax = plt.subplots(figsize=(12, 4))
        ax.plot(eq.time, eq.mr * 100)
        ax.axhline(cap_pct, color="red", linestyle="--", linewidth=1, label=f"{cap_pct:g}% MR cap")
        ax.set_title(f"{tag} margin ratio % - Cost B")
        ax.legend()
        fig.tight_layout()
        fig.savefig(os.path.join(results_dir, f"margin_ratio_{tag}.png"))
        plt.close(fig)


def write_memo(
    summary: pd.DataFrame,
    trades: pd.DataFrame,
    result: str,
    reason: str,
    counts: dict,
    results_dir: str,
    product: str,
    mr_cap: float,
    memo_name: str,
    remaining: pd.DataFrame | None = None,
    start_equity: float = START_EQUITY,
    write_root_memo: bool = True,
) -> None:
    sample = trades[trades.cost_model == COST_A.name].head(10) if not trades.empty else pd.DataFrame()
    liq = liquidation_stats(trades, start_equity=start_equity)
    remaining = remaining if remaining is not None else pd.DataFrame()
    cap_pct = mr_cap * 100
    notional_x = mr_cap / MMR
    liq_drop = (1.0 - mr_cap) / notional_x * 100 if notional_x else 0.0
    text = "\n".join([
        f"# Product {product} Leveraged DCA Results", "",
        "## 1. This is not the scalp bot",
        f"Long-only BTCUSDT perp DCA with technical limit adds and a {cap_pct:g}% maintenance-margin-ratio cap. Start equity ${start_equity:,.0f}. Holds until +2% from average entry. A 50% *price* stop is past liquidation on this leverage, so F3 (if enabled) flattens when wallet falls to 50% of equity at the first fill of that basket. Do not wire into main.py.",
        "",
        "## 2. Margin-ratio meaning",
        f"MR = qty * mark * 0.4% / wallet, capped at {cap_pct:g}% after every fill. That is not a {cap_pct:g}% stop. With ~0 UPNL it allows about {notional_x:.2f}× notional and roughly a {liq_drop:.1f}% further decline to liquidation.",
        "",
        "## 3. Remaining balance (last completed 1h, path-dependent)",
        "",
        remaining.to_markdown(index=False, floatfmt=".2f") if not remaining.empty else "No snapshot.",
        "",
        f"remaining_mark_usdt is the live wallet at that candle (open inventory marked). if_flatten_today_usdt is if you taker-close now. Split tables do not chain: each split adds its own trades onto a fresh ${start_equity:,.0f}.",
        "",
        "## 4. First risk exit (SL50 or liquidation)",
        "",
        liq.to_markdown(index=False, floatfmt=".2f") if not liq.empty else "No baskets.",
        "",
        "PnL before that exit is realized round-trips only.",
        "",
        "## 5. Counts",
        f"- 1h bars: {counts['bars']}",
        f"- Cost A baskets: {counts['baskets']}",
        f"- Cost A events: {counts['events']}",
        "",
        "## 6. Train / validate / holdout (dollars and %)",
        "",
        summary.to_markdown(index=False),
        "",
        "## 7. Decision",
        result,
        "",
        "## 8. One sentence",
        reason,
        "",
        "## 9. Next step",
        "If KILL, do not add more indicators. If PAPER-OTHER-PRODUCT, keep it off the scalp Docker path.",
        "",
        "## 10. Sample baskets (Cost A)",
        "",
        sample.to_markdown(index=False) if not sample.empty else "No baskets.",
        "",
    ]) + "\n"
    os.makedirs(results_dir, exist_ok=True)
    with open(os.path.join(results_dir, memo_name), "w") as f:
        f.write(text)
    try:
        if write_root_memo:
            with open(memo_name, "w") as f:
                f.write(text)
    except PermissionError:
        pass


def run_suite(
    mr_cap: float = MR_CAP,
    product: str = "F1_dca_leverage",
    results_dir: str = RESULTS_DIR,
    tag: str = "F1",
    memo_name: str = "RESULTS_DCA.md",
    equity_stop_frac: float | None = None,
    size_equity: float | None = None,
    size_step_mult: float | None = None,
    start_equity: float = START_EQUITY,
    df: pd.DataFrame | None = None,
    market_label: str | None = None,
    write_root_memo: bool = True,
    isolated: bool = False,
    quiet: bool = False,
    so_style: str = SO_GEOMETRIC,
    tp_pct: float | None = None,
    sl_from_liq: bool = False,
    hard_sl_pct: float | None = None,
    hard_sl_basket: float | None = None,
    stale_loss_pct: float | None = None,
    stale_days: float | None = None,
    max_hold_days: float | None = None,
    entry_ttl_sec: float | None = None,
    giveup_pct: float | None = None,
    giveup_days: float | None = None,
    giveup_min_fills: int = 3,
    range_so_max: int | None = None,
    range_weight_size: bool = False,
    peak_skip_pct: float | None = None,
    so_reclaim: bool = True,
    peak_lookback_days: float | None = PEAK_LOOKBACK_DAYS,
    sl_cooldown_days: float | None = None,
    sl_high_reclaim: bool = False,
    after_sl_clip: float | None = None,
    price_dd_skip_pct: float | None = None,
    price_dd_lookback_days: float | None = None,
    sl_dump_lookback_days: float | None = None,
    after_tp_dump: bool = False,
    after_tp_giveback_pct: float | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if df is None:
        df = prepare_data()
    label = market_label or SYMBOL
    if not quiet:
        print(
            f"BAR_COUNTS 1h={len(df)} source=Binance perp {label} mr_cap={mr_cap} "
            f"equity_stop={equity_stop_frac} size_equity={size_equity} size_step_mult={size_step_mult} "
            f"start_equity={start_equity} isolated={isolated} so_style={so_style}"
        )
    all_trades, all_eq, all_ev, all_rem = [], [], [], []
    summary_rows = []
    baskets = 0
    events_n = 0
    for cost in (COST_A, COST_B):
        trades, equity, events, remaining = run_dca(
            df, cost, mr_cap=mr_cap, equity_stop_frac=equity_stop_frac,
            size_equity=size_equity, size_step_mult=size_step_mult, start_equity=start_equity,
            isolated=isolated, so_style=so_style, tp_pct=tp_pct, sl_from_liq=sl_from_liq,
            hard_sl_pct=hard_sl_pct, hard_sl_basket=hard_sl_basket,
            stale_loss_pct=stale_loss_pct, stale_days=stale_days, max_hold_days=max_hold_days,
            entry_ttl_sec=entry_ttl_sec,
            giveup_pct=giveup_pct, giveup_days=giveup_days, giveup_min_fills=giveup_min_fills,
            range_so_max=range_so_max, range_weight_size=range_weight_size,
            peak_skip_pct=peak_skip_pct, so_reclaim=so_reclaim,
            peak_lookback_days=peak_lookback_days,
            sl_cooldown_days=sl_cooldown_days, sl_high_reclaim=sl_high_reclaim,
            after_sl_clip=after_sl_clip,
            price_dd_skip_pct=price_dd_skip_pct,
            price_dd_lookback_days=price_dd_lookback_days,
            sl_dump_lookback_days=sl_dump_lookback_days,
            after_tp_dump=after_tp_dump,
            after_tp_giveback_pct=after_tp_giveback_pct,
        )
        all_trades.append(trades)
        all_eq.append(equity)
        all_ev.append(events)
        all_rem.append(remaining)
        if cost == COST_A:
            baskets = len(trades)
            events_n = len(events)
            if not quiet:
                print(f"FULL_SAMPLE_BASKETS={baskets} EVENTS={events_n}")
        for split in ("train", "validate", "holdout"):
            summary_rows.append(summarize(
                trades, equity, split, cost.name, product=product, start_equity=start_equity,
            ))
    trades_df = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    equity_df = pd.concat(all_eq, ignore_index=True)
    events_df = pd.concat(all_ev, ignore_index=True) if all_ev else pd.DataFrame()
    remaining_df = pd.DataFrame(all_rem)
    summary = pd.DataFrame(summary_rows)
    result, reason = decision(summary, baskets)
    if not quiet:
        print("\nSUMMARY")
        print(summary.to_string(index=False, float_format=lambda value: f"{value:.4f}"))
        print("\nREMAINING_BALANCE")
        print(remaining_df.to_string(index=False, float_format=lambda value: f"{value:.2f}"))
        print("\nLIQUIDATION_DOLLARS")
        print(liquidation_stats(trades_df, start_equity=start_equity).to_string(index=False, float_format=lambda value: f"{value:.2f}"))
        print(f"\nDECISION {result}: {reason}")
    save_outputs(
        trades_df, equity_df, events_df, summary, results_dir, tag, mr_cap, remaining_df,
        plots=not quiet,
    )
    if not quiet:
        write_memo(
            summary, trades_df, result, reason,
            {"bars": len(df), "baskets": baskets, "events": events_n},
            results_dir, product, mr_cap, memo_name, remaining_df,
            start_equity=start_equity, write_root_memo=write_root_memo,
        )
    return remaining_df, summary


def main() -> None:
    run_suite()


if __name__ == "__main__":
    main()

