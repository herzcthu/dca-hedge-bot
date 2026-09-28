"""H1: long and short in one USD-M wallet. Research only. Not main.py.

Same range-SO rules as the long winner, mirrored for the short.
One cash wallet. Each side sizes off a fixed clip, or a clip that grows
by clip_grow at each doubling of the wallet. Liquidation is the
account price (both sides' PnL), so the side that is not threatened
stays open.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from experiments.dca.backtest_dca import (
    FUNDING_PLACEHOLDER,
    HEADROOM,
    MIN_DIP,
    MIN_NOTIONAL,
    MIN_RANGE_FRAC,
    MIN_SO_DIP,
    MMR,
    MR_EMERGENCY,
    RANGE_DUMP_EXPAND,
    RANGE_TOP_FRAC,
    RESIST_BUFFER,
    CostModel,
    RollingMax,
    funding_hit,
    notional_cap,
    planned_notional,
    range_so_limit,
    range_too_tight,
    stale_exit_reason,
    technical_dip,
)


@dataclass
class Leg:
    name: str
    qty: float = 0.0
    avg: float = 0.0
    last_fill: float = 0.0
    fills: int = 0
    so_count: int = 0
    basket_cap: float = 0.0
    basket_start: object = None
    pending: float | None = None
    pending_kind: str | None = None
    pending_notional: float = 0.0
    pending_armed: object = None
    anchor: float | None = None
    pocket: float = 0.0
    await_reclaim: bool = False
    reenter: bool = False
    pending_stale: str | None = None


def account_liq(cash: float, lq: float, la: float, sq: float, sa: float) -> float | None:
    """Price where shared equity equals maintenance on both notionals."""
    if lq <= 0 and sq <= 0:
        return None
    k = cash - lq * la + sq * sa
    denom = (lq + sq) * MMR - (lq - sq)
    if abs(denom) < 1e-12:
        return None
    px = k / denom
    if px <= 0:
        return None
    return px


def equity_at(cash: float, long: Leg, short: Leg, px: float) -> float:
    eq = cash
    if long.qty > 0:
        eq += long.qty * (px - long.avg)
    if short.qty > 0:
        eq += short.qty * (short.avg - px)
    return eq


def _near_atl(close: float, range_low: float, range_high: float) -> bool:
    if not pd.notna(range_low) or not pd.notna(range_high) or range_high <= range_low or close <= 0:
        return True
    return close < range_low + (1.0 - RANGE_TOP_FRAC) * (range_high - range_low)


def _near_ath(close: float, range_low: float, range_high: float) -> bool:
    if not pd.notna(range_low) or not pd.notna(range_high) or range_high <= range_low or close <= 0:
        return True
    return close > range_low + RANGE_TOP_FRAC * (range_high - range_low)


def short_blocked(close: float, ema55: float, support: float, range_low: float, range_high: float, reenter: bool) -> bool:
    if pd.notna(support) and support > 0 and close <= float(support) * (1.0 + RESIST_BUFFER):
        return True
    if reenter:
        return False
    if close >= ema55:
        return True
    if _near_atl(close, range_low, range_high) or range_too_tight(close, range_low, MIN_RANGE_FRAC):
        return True
    return False


def long_blocked(close: float, ema55: float, resist: float, range_low: float, range_high: float, reenter: bool) -> bool:
    if pd.notna(resist) and resist > 0 and close >= float(resist) * (1.0 - RESIST_BUFFER):
        return True
    if reenter:
        return False
    if close <= ema55:
        return True
    if _near_ath(close, range_low, range_high) or range_too_tight(close, range_low, MIN_RANGE_FRAC):
        return True
    return False


def technical_rally(ema21: float, resist: float, floor_px: float, min_frac: float) -> float | None:
    floor = floor_px * (1.0 + min_frac)
    levels = [level for level in (ema21, resist) if pd.notna(level) and level >= floor]
    return min(levels) if levels else None


def range_so_short(last_fill: float, range_high: float, so_count: int, max_so: int) -> float | None:
    slots = max_so - so_count
    if slots < 1 or last_fill <= 0 or not pd.notna(range_high) or range_high <= 0:
        return None
    if range_high <= last_fill:
        return None
    gap = range_high - last_fill
    limit = last_fill + gap / slots
    if limit >= range_high or limit <= last_fill:
        return None
    if (limit - last_fill) / last_fill < MIN_SO_DIP:
        return None
    return limit


def grow_clip(equity: float, start: float, grow: float) -> tuple[float, float]:
    """Clip for this wallet, measured from the original start.

    Each triple of the start ($3,000, $9,000, $27,000, ...) multiplies the
    clip by 1 + grow. A smaller wallet steps back to the matching level.
    A $4,000 wallet with a 10% grow is one triple: clip $1,100, not the
    original $1,000 and not the $9,000 level.
    """
    milestone = float(start)
    clip = float(start)
    while milestone > 0.0 and equity >= 3.0 * milestone:
        milestone *= 3.0
        clip *= 1.0 + grow
    return milestone, clip


def step_wallet_clip(equity: float, start: float, step: float) -> float:
    """Set the clip to the wallet's $5k step, and step it back down too.

    Below $5,000 the clip stays at the start. At $5,000 it becomes $5,000.
    At $12,000 it is $10,000. A fall from $12,000 to $7,000 returns it to $5,000.
    """
    if step <= 0.0 or equity < step:
        return float(start)
    return float(int(equity // step) * step)


def _worse(price: float, buy: bool, slip: float) -> float:
    return price * (1.0 + slip) if buy else price * (1.0 - slip)


def run_hedge(
    df: pd.DataFrame,
    cost: CostModel,
    start_equity: float = 10_000.0,
    clip: float = 10_000.0,
    mr_cap: float = 0.10,
    tp_pct: float = 0.08,
    sl_loss: float = 0.95,
    range_so_max: int = 10,
    entry_ttl_sec: float = 3600.0,
    peak_skip_pct: float = 0.15,
    peak_lookback_days: float = 180.0,
    stale_loss_pct: float = 0.40,
    stale_days: float = 180.0,
    so_reclaim: bool = True,
    clip_grow: float = 0.0,
    clip_step_usd: float = 0.0,
) -> tuple[pd.DataFrame, dict]:
    rows = list(df.itertuples(index=False))
    cash = float(start_equity)
    long = Leg("long")
    short = Leg("short")
    peak = RollingMax(peak_lookback_days)
    equity_peak = start_equity
    trades: list[dict] = []
    liquidated = False
    sizing = {
        "clip": float(clip),
        "milestone": float(start_equity),
        "steps": [],
        "downs": 0,
    }

    def sizing_clip(eq: float, ts) -> float:
        if eq <= 0.0 or (clip_grow <= 0.0 and clip_step_usd <= 0.0):
            return sizing["clip"]
        if clip_step_usd > 0.0:
            new_clip = step_wallet_clip(eq, start_equity, clip_step_usd)
            milestone = new_clip
        else:
            milestone, new_clip = grow_clip(eq, start_equity, clip_grow)
        if abs(new_clip - sizing["clip"]) > 0.01:
            if new_clip < sizing["clip"]:
                sizing["downs"] += 1
            sizing["steps"].append({
                "time": ts,
                "equity": eq,
                "milestone": milestone,
                "clip": new_clip,
            })
            sizing["milestone"] = milestone
            sizing["clip"] = new_clip
        return sizing["clip"]

    def marked(px: float) -> float:
        return equity_at(cash, long, short, px)

    def close_leg(leg: Leg, other: Leg, ts, raw: float, reason: str, buy_to_exit: bool) -> None:
        nonlocal cash
        if leg.qty <= 0:
            return
        fee_rate = cost.taker_fee if reason != "TP" else cost.maker_fee
        slip = cost.taker_slip if reason != "TP" else cost.maker_slip
        px = _worse(raw, buy_to_exit, slip)
        if leg.name == "long":
            pnl = leg.qty * (px - leg.avg)
        else:
            pnl = leg.qty * (leg.avg - px)
        fee = leg.qty * px * fee_rate
        pnl -= fee
        cash += pnl
        trades.append({
            "cost_model": cost.name,
            "side": leg.name,
            "entry_time": leg.basket_start,
            "exit_time": ts,
            "exit_reason": reason,
            "avg_entry": leg.avg,
            "exit": px,
            "fills": leg.fills,
            "safety_orders": leg.so_count,
            "qty": leg.qty,
            "pnl_net": pnl,
            "fees": fee,
            "hold_hours": max((ts - leg.basket_start).total_seconds() / 3600, 0.0) if leg.basket_start is not None else 0.0,
        })
        leg.qty = 0.0
        leg.avg = 0.0
        leg.last_fill = 0.0
        leg.fills = 0
        leg.so_count = 0
        leg.basket_cap = 0.0
        leg.basket_start = None
        leg.pending = None
        leg.pending_kind = None
        leg.pending_notional = 0.0
        leg.pending_armed = None
        leg.anchor = None
        leg.pocket = 0.0
        leg.await_reclaim = False
        leg.pending_stale = None
        if reason in ("STALE", "TIME"):
            leg.reenter = True

    def fill_leg(leg: Leg, ts, raw: float, taker: bool, buy: bool) -> bool:
        nonlocal cash
        if leg.pending is None or leg.pending_notional < MIN_NOTIONAL:
            leg.pending_armed = None
            return False
        fee_rate = cost.taker_fee if taker else cost.maker_fee
        slip = cost.taker_slip if taker else cost.maker_slip
        px = _worse(raw, buy, slip)
        add = leg.pending_notional / px
        fee = leg.pending_notional * fee_rate
        new_qty = leg.qty + add
        new_avg = (leg.qty * leg.avg + add * px) / new_qty
        post_cash = cash - fee
        post_eq = post_cash
        if leg.name == "long":
            post_eq += new_qty * (px - new_avg)
            post_eq += short.qty * (short.avg - px) if short.qty > 0 else 0.0
        else:
            post_eq += long.qty * (px - long.avg) if long.qty > 0 else 0.0
            post_eq += new_qty * (new_avg - px)
        if post_eq <= 0:
            leg.pending = None
            leg.pending_kind = None
            leg.pending_notional = 0.0
            leg.pending_armed = None
            return False
        side_mr = (new_qty * px * MMR) / post_eq
        if side_mr > mr_cap + 1e-9:
            leg.pending = None
            leg.pending_kind = None
            leg.pending_notional = 0.0
            leg.pending_armed = None
            return False
        cash = post_cash
        leg.qty = new_qty
        leg.avg = new_avg
        leg.last_fill = px
        if leg.fills == 0:
            leg.basket_start = ts
            leg.reenter = False
            if leg.pocket <= 0:
                leg.pocket = min(sizing["clip"], max(post_eq, 0.0))
        leg.fills += 1
        if leg.pending_kind == "so":
            leg.so_count += 1
            if so_reclaim:
                leg.await_reclaim = True
        leg.pending = None
        leg.pending_kind = None
        leg.pending_notional = 0.0
        leg.pending_armed = None
        return True

    def arm(leg: Leg, row, up: bool) -> None:
        close = float(row.close)
        eq = marked(close)
        active = sizing_clip(eq, row.close_time)
        if leg.qty <= 0:
            if peak_skip_pct > 0 and equity_peak > 0 and eq < equity_peak * (1.0 - peak_skip_pct):
                leg.pending = None
                leg.pending_armed = None
                return
            if up:
                if short_blocked(close, float(row.ema55), float(row.support), float(row.range_low), float(row.range_high), leg.reenter):
                    leg.pending = None
                    leg.pending_armed = None
                    return
                limit = technical_rally(float(row.ema21), float(row.resist), close, MIN_DIP)
                if limit is None and leg.reenter and close > 0:
                    limit = close * (1.0 + MIN_DIP)
                anchor = float(row.range_high) if hasattr(row, "range_high") else None
            else:
                if long_blocked(close, float(row.ema55), float(row.resist), float(row.range_low), float(row.range_high), leg.reenter):
                    leg.pending = None
                    leg.pending_armed = None
                    return
                limit = technical_dip(float(row.ema21), float(row.support), close, MIN_DIP)
                if limit is None and leg.reenter and close > 0:
                    limit = close * (1.0 - MIN_DIP)
                anchor = float(row.range_low) if hasattr(row, "range_low") else None
            if limit is None:
                leg.pending = None
                leg.pending_armed = None
                return
            plan_wallet = min(active, eq) if eq > 0 else 0.0
            leg.pocket = plan_wallet
            leg.basket_cap = notional_cap(plan_wallet, mr_cap) * HEADROOM
            size = min(planned_notional(leg.basket_cap, 0), leg.basket_cap)
            if size < MIN_NOTIONAL:
                leg.pending = None
                leg.pending_armed = None
                return
            prev = leg.pending
            leg.pending = limit
            leg.pending_kind = "base"
            leg.pending_notional = size
            leg.anchor = anchor
            if prev is None or abs(float(prev) - limit) / limit >= 0.001:
                leg.pending_armed = row.close_time
            return
        if so_reclaim and leg.await_reclaim:
            reclaimed = float(row.close) <= float(row.ema21) if up else float(row.close) >= float(row.ema21)
            if not reclaimed:
                leg.pending = None
                return
            leg.await_reclaim = False
        plan_wallet = min(active, max(eq, 0.0))
        cap_n = notional_cap(plan_wallet, mr_cap)
        remaining = cap_n - leg.qty * close
        if remaining < MIN_NOTIONAL:
            leg.pending = None
            return
        live_lo = float(row.range_low) if hasattr(row, "range_low") else None
        live_hi = float(row.range_high) if hasattr(row, "range_high") else None
        if up:
            if so_reclaim:
                if leg.anchor and live_hi and live_hi > float(leg.anchor) * (1.0 + RANGE_DUMP_EXPAND):
                    leg.pending = None
                    return
                if pd.notna(row.resist) and close > float(row.resist):
                    leg.pending = None
                    return
            hi = live_hi if not so_reclaim else (leg.anchor if leg.anchor is not None else live_hi)
            limit = range_so_short(leg.last_fill, float(hi) if hi is not None else float("nan"), leg.so_count, range_so_max)
        else:
            if so_reclaim:
                if leg.anchor and live_lo and live_lo < float(leg.anchor) * (1.0 - RANGE_DUMP_EXPAND):
                    leg.pending = None
                    return
                if pd.notna(row.support) and close < float(row.support):
                    leg.pending = None
                    return
            lo = live_lo if not so_reclaim else (leg.anchor if leg.anchor is not None else live_lo)
            limit = range_so_limit(leg.last_fill, float(lo) if lo is not None else float("nan"), leg.so_count, range_so_max)
        if limit is None or leg.so_count >= range_so_max or leg.fills >= 1 + range_so_max:
            leg.pending = None
            return
        slots = range_so_max - leg.so_count
        size = remaining * HEADROOM / slots
        if size < MIN_NOTIONAL:
            leg.pending = None
            return
        leg.pending = limit
        leg.pending_kind = "so"
        leg.pending_notional = size

    def _emergency(px: float) -> bool:
        if long.qty <= 0 and short.qty <= 0:
            return False
        eq = equity_at(cash, long, short, px)
        if eq <= 0:
            return True
        return (long.qty + short.qty) * px * MMR / eq >= MR_EMERGENCY

    for i, row in enumerate(rows):
        if liquidated:
            continue
        o, h, l, c = float(row.open), float(row.high), float(row.low), float(row.close)
        for leg, up in ((long, False), (short, True)):
            if (
                leg.qty <= 0
                and leg.pending_kind == "base"
                and leg.pending is not None
                and entry_ttl_sec > 0
                and leg.pending_armed is not None
                and (row.open_time - leg.pending_armed).total_seconds() >= entry_ttl_sec
            ):
                leg.pending = None
                leg.pending_kind = None
                leg.pending_notional = 0.0
                leg.pending_armed = None
            if leg.pending_stale and leg.qty > 0:
                mark = o if leg.name == "long" else (2.0 * leg.avg - o)
                reason = stale_exit_reason(
                    leg.basket_start, row.open_time, mark, leg.avg,
                    stale_loss_pct, stale_days, None, fills=leg.fills,
                ) or (leg.pending_stale if leg.pending_stale == "TIME" else None)
                leg.pending_stale = None
                if reason:
                    close_leg(leg, short if leg is long else long, row.close_time, o, reason, buy_to_exit=up)

        if cash <= 0 and long.qty <= 0 and short.qty <= 0:
            liquidated = True
            continue

        lp = account_liq(cash, long.qty, long.avg, short.qty, short.avg)
        # Account liq flattens both. Per-side SL is 95% of the way there and closes only that side.
        if lp is not None and long.qty > 0 and min(o, l) <= lp < long.avg:
            px = lp if o > lp else o
            close_leg(long, short, row.close_time, px, "LIQUIDATION", buy_to_exit=False)
            if short.qty > 0:
                close_leg(short, long, row.close_time, px, "LIQUIDATION", buy_to_exit=True)
        elif lp is not None and short.qty > 0 and max(o, h) >= lp > short.avg:
            px = lp if o < lp else o
            close_leg(short, long, row.close_time, px, "LIQUIDATION", buy_to_exit=True)
            if long.qty > 0:
                close_leg(long, short, row.close_time, px, "LIQUIDATION", buy_to_exit=False)
        else:
            if long.qty > 0 and lp is not None and lp < long.avg:
                sl = long.avg - sl_loss * (long.avg - lp)
                if min(o, l) <= sl:
                    px = sl if o > sl else o
                    close_leg(long, short, row.close_time, px, "SL", buy_to_exit=False)
            if short.qty > 0:
                lp2 = account_liq(cash, long.qty, long.avg, short.qty, short.avg)
                if lp2 is not None and lp2 > short.avg:
                    sl = short.avg + sl_loss * (lp2 - short.avg)
                    if max(o, h) >= sl:
                        px = sl if o < sl else o
                        close_leg(short, long, row.close_time, px, "SL", buy_to_exit=True)

        if _emergency(l) or _emergency(h):
            eq_l = equity_at(cash, long, short, l)
            eq_h = equity_at(cash, long, short, h)
            worse_px = l if eq_l <= eq_h else h
            if long.qty > 0:
                close_leg(long, short, row.close_time, worse_px, "EMERGENCY", buy_to_exit=False)
            if short.qty > 0:
                close_leg(short, long, row.close_time, worse_px, "EMERGENCY", buy_to_exit=True)

        if cash <= 0 and long.qty <= 0 and short.qty <= 0:
            liquidated = True
            continue

        long_add = long.pending is not None and l <= long.pending
        short_add = short.pending is not None and h >= short.pending
        long_tp = long.qty > 0 and h >= long.avg * (1.0 + tp_pct)
        short_tp = short.qty > 0 and l <= short.avg * (1.0 - tp_pct)
        if long_add and long_tp:
            long_tp = False
        if short_add and short_tp:
            short_tp = False
        if long_add:
            taker = o < long.pending
            fill_leg(long, row.open_time, o if taker else long.pending, taker, buy=True)
        if short_add:
            taker = o > short.pending
            fill_leg(short, row.open_time, o if taker else short.pending, taker, buy=False)
        if long_tp and long.qty > 0:
            close_leg(long, short, row.close_time, long.avg * (1.0 + tp_pct), "TP", buy_to_exit=False)
        if short_tp and short.qty > 0:
            close_leg(short, long, row.close_time, short.avg * (1.0 - tp_pct), "TP", buy_to_exit=True)

        if funding_hit(row.open_time):
            if long.qty > 0:
                cash -= long.qty * c * FUNDING_PLACEHOLDER
            if short.qty > 0:
                cash += short.qty * c * FUNDING_PLACEHOLDER

        arm(long, row, up=False)
        arm(short, row, up=True)

        for leg, up in ((long, False), (short, True)):
            if leg.qty <= 0:
                continue
            mark = c if leg.name == "long" else (2.0 * leg.avg - c)
            sig = stale_exit_reason(
                leg.basket_start, row.close_time, mark, leg.avg,
                stale_loss_pct, stale_days, None, fills=leg.fills,
            )
            if sig:
                if i == len(rows) - 1:
                    close_leg(leg, short if leg is long else long, row.close_time, c, sig, buy_to_exit=up)
                else:
                    leg.pending_stale = sig

        eq = marked(c)
        if eq <= 0 and long.qty <= 0 and short.qty <= 0:
            liquidated = True
            cash = min(cash, 0.0)
            continue
        equity_peak = peak.update(row.close_time, eq)

    last = rows[-1]
    last_px = float(last.close)
    eq = 0.0 if liquidated else marked(last_px)
    return pd.DataFrame(trades), {
        "cost_model": cost.name,
        "as_of": last.close_time,
        "px": last_px,
        "liquidated": liquidated,
        "equity": max(eq, 0.0),
        "cash": cash,
        "long_qty": long.qty,
        "short_qty": short.qty,
        "long_avg": long.avg if long.qty > 0 else None,
        "short_avg": short.avg if short.qty > 0 else None,
        "long_upnl": long.qty * (last_px - long.avg) if long.qty > 0 else 0.0,
        "short_upnl": short.qty * (short.avg - last_px) if short.qty > 0 else 0.0,
        "clip": sizing["clip"],
        "clip_steps": len(sizing["steps"]),
        "clip_downs": sizing["downs"],
    }
