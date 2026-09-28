"""Live DCA rules (USD-M). Same math as the isolated experiment; no backtest I/O."""

from __future__ import annotations

import pandas as pd

MMR = 0.004
MR_EMERGENCY = 0.80
MAX_SAFETY = 10
VOLUME_SCALE = 1.25
GEO_STEP = 0.010
GEO_SCALE = 1.15
MIN_DIP = 0.003
MIN_SO_DIP = 0.006
RESIST_BUFFER = 0.003
MIN_NOTIONAL = 100.0
HEADROOM = 0.90
SWING = 12
BAR_SCALE = {"1h": 1, "15m": 4, "5m": 12, "1m": 60}
RANGE_DAYS = 7
RANGE_TOP_FRAC = 0.75
MIN_RANGE_FRAC = 0.06
RANGE_DUMP_EXPAND = 0.02
SO_GEOMETRIC = "geometric"
SO_TECHNICAL = "technical"
SO_RANGE = "range"

_raw = [VOLUME_SCALE ** i for i in range(1 + MAX_SAFETY)]
_wsum = sum(_raw)
WEIGHTS = [w / _wsum for w in _raw]


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def notional_cap(wallet: float, mr_cap: float) -> float:
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


def unit_loss_stop_price(qty: float, avg: float, unit_equity: float, loss_frac: float) -> float | None:
    if qty <= 0 or unit_equity <= 0 or loss_frac <= 0:
        return None
    return avg - (loss_frac * unit_equity) / qty


def tighter_stop(*levels: float | None) -> float | None:
    ok = [float(x) for x in levels if x is not None and x > 0]
    return max(ok) if ok else None


def hard_stop_from_avg(avg: float, pct: float | None) -> float | None:
    if pct is None or pct <= 0 or pct >= 1.0 or avg <= 0:
        return None
    px = avg * (1.0 - pct)
    return px if px > 0 else None


def hard_stop_from_basket(qty: float, avg: float, clip: float, frac: float | None) -> float | None:
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
    if liq is None or avg <= 0 or loss_frac <= 0:
        return None
    if liq >= avg:
        return None
    sl = avg - loss_frac * (avg - liq)
    if sl <= liq + 1e-12 or sl >= avg:
        return None
    return sl


def add_dca_features(df: pd.DataFrame, interval: str = "1h") -> pd.DataFrame:
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


def range_near_ath(close: float, range_low: float, range_high: float) -> bool:
    if not pd.notna(range_low) or not pd.notna(range_high) or range_high <= range_low or close <= 0:
        return True
    return close > range_low + RANGE_TOP_FRAC * (range_high - range_low)


def range_too_tight(ceiling: float, range_low: float, min_frac: float = MIN_RANGE_FRAC) -> bool:
    if not pd.notna(range_low) or ceiling <= 0 or range_low <= 0:
        return True
    return (ceiling - range_low) / ceiling < min_frac


def peak_skip_reason(marked: float, peak: float | None, pct: float | None) -> str | None:
    """Sit out new baskets when marked pocket is pct below the rolling peak."""
    if pct is None or pct <= 0 or peak is None or peak <= 0 or marked <= 0:
        return None
    if marked < peak * (1.0 - float(pct)):
        dd = 1.0 - marked / peak
        return f"peak_skip marked={marked:.2f} peak={peak:.2f} dd={dd:.1%}"
    return None


def account_liq(cash: float, long_qty: float, long_avg: float, short_qty: float, short_avg: float) -> float | None:
    """Price where shared equity equals maintenance on both notionals."""
    if long_qty <= 0 and short_qty <= 0:
        return None
    k = cash - long_qty * long_avg + short_qty * short_avg
    denom = (long_qty + short_qty) * MMR - (long_qty - short_qty)
    if abs(denom) < 1e-12:
        return None
    px = k / denom
    if px <= 0:
        return None
    return px


def side_stop(avg: float, liq: float | None, loss_frac: float, short: bool) -> float | None:
    if liq is None or avg <= 0 or loss_frac <= 0:
        return None
    if not short:
        if liq >= avg:
            return None
        sl = avg - loss_frac * (avg - liq)
        if sl <= liq or sl >= avg:
            return None
        return sl
    if liq <= avg:
        return None
    sl = avg + loss_frac * (liq - avg)
    if sl >= liq or sl <= avg:
        return None
    return sl


def range_near_atl(close: float, range_low: float, range_high: float) -> bool:
    if not pd.notna(range_low) or not pd.notna(range_high) or range_high <= range_low or close <= 0:
        return True
    return close < range_low + (1.0 - RANGE_TOP_FRAC) * (range_high - range_low)


def short_basket_skip_reason(
    close: float,
    ema55: float,
    support: float,
    so_style: str,
    range_low: float,
    range_high: float,
    reenter: bool,
) -> str | None:
    if pd.notna(support) and support > 0 and close <= float(support) * (1.0 + RESIST_BUFFER):
        return f"near_support close={close:.6f} support={float(support):.6f}"
    if reenter:
        return None
    if close >= ema55:
        return f"above_ema55 close={close:.6f} ema55={ema55:.6f}"
    if so_style == SO_RANGE:
        if range_near_atl(close, range_low, range_high):
            return f"bottom_quartile_7d close={close:.6f} low={range_low:.6f} high={range_high:.6f}"
        if range_too_tight(close, range_low):
            return f"range_too_tight close={close:.6f} low={range_low:.6f}"
    return None


def short_basket_limit(close: float, ema21: float, resist: float, reenter: bool) -> float | None:
    floor = close * (1.0 + MIN_DIP)
    levels = [level for level in (ema21, resist) if pd.notna(level) and level >= floor]
    if levels:
        return min(levels)
    if reenter and close > 0:
        return floor
    return None


def range_so_short(last_fill: float, range_high: float, so_count: int, max_so: int = MAX_SAFETY) -> float | None:
    slots = max(int(max_so), 1) - so_count
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


def new_basket_skip_reason(
    close: float,
    ema55: float,
    resist: float,
    so_style: str,
    range_low: float,
    range_high: float,
    reenter: bool,
) -> str | None:
    if close >= resist * (1.0 - RESIST_BUFFER):
        return f"near_resist close={close:.2f} resist={resist:.2f}"
    if reenter:
        return None
    if close <= ema55:
        return f"below_ema55 close={close:.2f} ema55={ema55:.2f}"
    if so_style == SO_RANGE:
        if range_near_ath(close, range_low, range_high):
            loc = 0.0
            if range_high > range_low:
                loc = (close - range_low) / (range_high - range_low)
            return (
                f"top_quartile_7d loc={loc:.2f} low={range_low:.2f} high={range_high:.2f}"
            )
        if range_too_tight(close, range_low):
            dip = (close - range_low) / close if close else 0.0
            return f"range_too_tight dip_to_7d_low={dip:.2%}"
    return None


def new_basket_blocked(
    close: float,
    ema55: float,
    resist: float,
    so_style: str,
    range_low: float,
    range_high: float,
    reenter: bool,
) -> bool:
    return new_basket_skip_reason(
        close, ema55, resist, so_style, range_low, range_high, reenter,
    ) is not None


def new_basket_limit(close: float, ema21: float, support: float, reenter: bool) -> float | None:
    limit = technical_dip(ema21, support, close, MIN_DIP)
    if limit is not None:
        return limit
    if reenter and close > 0:
        return close * (1.0 - MIN_DIP)
    return None


def range_so_limit(last_fill: float, range_low: float, so_count: int, max_so: int = MAX_SAFETY) -> float | None:
    slots = max(int(max_so), 1) - so_count
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
    live_range_low: float | None = None,
    max_so: int = MAX_SAFETY,
) -> tuple[float, float] | None:
    cap = max(int(max_so), 1)
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
        slots = cap - so_count
        size = remaining * HEADROOM / slots
        if size < min_size:
            return None
        return limit, size
    if so_style == SO_RANGE:
        why = range_so_dump_reason(close, support, live_range_low, range_low)
        if why:
            return None
        lo = float("nan") if range_low is None else float(range_low)
        limit = range_so_limit(last_fill, lo, so_count, cap)
        if limit is None:
            return None
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


def binding_stop(
    qty: float,
    avg: float,
    wallet_cash: float,
    clip: float,
    sl_loss: float | None,
    sl_from_liq: bool,
    hard_sl_pct: float | None,
    hard_sl_basket: float | None,
) -> tuple[float | None, str]:
    lp = liq_price(qty, avg, wallet_cash)
    loss_frac = 0.0 if not sl_loss else float(sl_loss)
    sp = None
    if loss_frac > 0:
        if sl_from_liq:
            sp = stop_from_liq(avg, lp, loss_frac)
        else:
            sp = unit_loss_stop_price(qty, avg, clip, loss_frac)
    hp = tighter_stop(
        hard_stop_from_avg(avg, hard_sl_pct),
        hard_stop_from_basket(qty, avg, clip, hard_sl_basket),
    )
    bound = tighter_stop(sp, hp)
    kind = "HARD" if hp is not None and bound is not None and abs(bound - hp) <= 1e-9 else "SL"
    return bound, kind
