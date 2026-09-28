#!/usr/bin/env python3
"""G1: Coin-M twin of F6 (1% MR + SL80, frozen $10k USD clip).

Binance BTCUSD_PERP inverse. Wallet starts as $10,000 of BTC at the first
tradable 1h open. Margin and P&L are in BTC; reports also mark that wallet
to USD. Idle BTC still changes USD value when the coin moves (unlike USD-M).

F6–F8 are not retuned. Not a scalp; do not wire into main.py.
"""

from __future__ import annotations

import os

import matplotlib.pyplot as plt
import pandas as pd

from experiments.dca import coinm_data
from experiments.dca.backtest_dca import (
    COST_A,
    COST_B,
    CostModel,
    FUNDING_PLACEHOLDER,
    HEADROOM,
    MAX_SAFETY,
    MMR,
    MR_EMERGENCY,
    PEAK_LOOKBACK_DAYS,
    RollingMax,
    SlEntryBrake,
    AfterTpGate,
    SO_GEOMETRIC,
    SO_RANGE,
    START_EQUITY,
    TP_PCT,
    add_dca_features,
    decision,
    funding_hit,
    hard_stop_from_avg,
    liquidation_stats,
    new_basket_blocked,
    new_basket_limit,
    notional_cap,
    planned_notional,
    safety_limit,
    safety_order_plan,
    slipped,
    stale_exit_reason,
    stop_from_liq,
    summarize,
    tighter_stop,
)


CONTRACT_SIZE = 100.0
PRODUCT = "G1_dca_coinm_10k_sl80"
RESULTS_DIR = "results_dca_coinm"
MR_CAP = 0.01
EQUITY_STOP_FRAC = 0.20


def prepare_data(symbol: str | None = None, interval: str = "1h") -> pd.DataFrame:
    df = coinm_data.load_klines(interval, symbol=symbol or coinm_data.SYMBOL).copy()
    return add_dca_features(df, interval)


def upnl_btc(contracts: int, avg: float, mark: float) -> float:
    if contracts <= 0 or avg <= 0 or mark <= 0:
        return 0.0
    return contracts * CONTRACT_SIZE * (1.0 / avg - 1.0 / mark)


def mark_btc(wallet_btc: float, contracts: int, avg: float, mark: float) -> float:
    return wallet_btc + upnl_btc(contracts, avg, mark)


def mark_usd(wallet_btc: float, contracts: int, avg: float, mark: float) -> float:
    return mark_btc(wallet_btc, contracts, avg, mark) * mark


def fee_btc(contracts: int, price: float, rate: float) -> float:
    if contracts <= 0 or price <= 0:
        return 0.0
    return (contracts * CONTRACT_SIZE / price) * rate


def margin_ratio(contracts: int, mark: float, wallet_btc: float, avg: float) -> float:
    if contracts <= 0:
        return 0.0
    wallet = mark_btc(wallet_btc, contracts, avg, mark)
    if wallet <= 0 or mark <= 0:
        return 1.0
    return (contracts * CONTRACT_SIZE * MMR) / (wallet * mark)


def liq_price(contracts: int, avg: float, wallet_btc: float) -> float | None:
    if contracts <= 0 or avg <= 0:
        return None
    denom = wallet_btc + contracts * CONTRACT_SIZE / avg
    if denom <= 0:
        return None
    return contracts * CONTRACT_SIZE * (1.0 + MMR) / denom


def sl_price(contracts: int, avg: float, clip_usd: float, loss_frac: float) -> float | None:
    notional = contracts * CONTRACT_SIZE
    if contracts <= 0 or avg <= 0 or notional <= 0 or clip_usd <= 0 or loss_frac <= 0:
        return None
    px = avg - (loss_frac * clip_usd) * avg / notional
    return px if px > 0 else None


def to_contracts(notional_usd: float) -> int:
    return int(notional_usd // CONTRACT_SIZE)


def sl_hold_outcome_coinm(
    rows: list,
    start_i: int,
    o: float,
    h: float,
    l: float,
    n: int,
    avg: float,
    wallet_btc: float,
    take_profit: float,
) -> str:
    tp = avg * (1.0 + take_profit)
    lp = liq_price(n, avg, wallet_btc)
    if lp is not None and min(o, l) <= lp:
        return "liq"
    if margin_ratio(n, l, wallet_btc, avg) >= MR_EMERGENCY:
        return "liq"
    if h >= tp:
        return "tp"
    cash = wallet_btc
    for row in rows[start_i + 1:]:
        o2, h2, l2, c2 = float(row.open), float(row.high), float(row.low), float(row.close)
        lp = liq_price(n, avg, cash)
        if lp is not None and min(o2, l2) <= lp:
            return "liq"
        if margin_ratio(n, l2, cash, avg) >= MR_EMERGENCY:
            return "liq"
        if h2 >= tp:
            return "tp"
        if funding_hit(row.open_time):
            cash -= n * CONTRACT_SIZE / c2 * FUNDING_PLACEHOLDER
    return "neither"


def run_dca(
    df: pd.DataFrame,
    cost: CostModel,
    start_btc: float,
    isolated: bool = False,
    clip_usd: float | None = None,
    mr_cap: float | None = None,
    equity_stop_frac: float | None = None,
    so_style: str | None = None,
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
    clip = START_EQUITY if clip_usd is None else float(clip_usd)
    mr_limit = MR_CAP if mr_cap is None else float(mr_cap)
    sl_keep = EQUITY_STOP_FRAC if equity_stop_frac is None else float(equity_stop_frac)
    so_mode = SO_GEOMETRIC if so_style is None else str(so_style)
    take_profit = TP_PCT if tp_pct is None else float(tp_pct)
    rows = list(df.itertuples(index=False))
    wallet_btc = 0.0 if isolated else start_btc
    idle_coin = start_btc if isolated else 0.0
    contracts = 0
    avg = 0.0
    last_fill = 0.0
    fills = 0
    so_count = 0
    basket_cap = 0.0
    basket_clip = 0.0
    basket_start = None
    pending_buy = None
    pending_kind = None
    pending_notional = 0.0
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
    equity_peak = clip
    liquidated = False
    trades: list[dict] = []
    events: list[dict] = []
    equity_rows: list[dict] = []

    def close_basket(exit_time, exit_price: float, reason: str, fee_rate: float, slip: float, taker: bool) -> None:
        nonlocal wallet_btc, idle_coin, contracts, avg, last_fill, fills, so_count, basket_cap, basket_clip
        nonlocal basket_start, pending_buy, pending_kind, pending_notional, pending_stale, reenter_from_stale
        nonlocal pending_armed_time, basket_so_floor, pending_so_floor, await_so_reclaim
        if contracts <= 0:
            return
        px = slipped(exit_price, 1, False, slip)
        fee = fee_btc(contracts, px, fee_rate)
        pnl_coin = upnl_btc(contracts, avg, px) - fee
        pnl_usd = pnl_coin * px
        wallet_btc += upnl_btc(contracts, avg, px) - fee
        trades.append({
            "cost_model": cost.name, "entry_time": basket_start, "exit_time": exit_time,
            "exit_reason": reason, "avg_entry": avg, "exit": px, "fills": fills,
            "safety_orders": so_count, "qty": contracts, "pnl_net": pnl_usd,
            "pnl_btc": pnl_coin, "fees": fee * px, "fees_btc": fee,
            "hold_hours": max((exit_time - basket_start).total_seconds() / 3600, 0.0) if basket_start is not None else 0.0,
            "taker_exit": taker, "sl_hold": "",
        })
        events.append({"time": exit_time, "cost_model": cost.name, "event": reason, "price": px, "pnl": pnl_usd})
        contracts = 0
        avg = 0.0
        last_fill = 0.0
        fills = 0
        so_count = 0
        basket_cap = 0.0
        basket_clip = 0.0
        basket_start = None
        pending_buy = None
        pending_kind = None
        pending_notional = 0.0
        pending_stale = None
        pending_armed_time = None
        basket_so_floor = None
        pending_so_floor = None
        await_so_reclaim = False
        if reason in ("STALE", "TIME", "GIVEUP"):
            reenter_from_stale = True
        if isolated:
            if reason == "LIQUIDATION":
                wallet_btc = 0.0
            else:
                idle_coin += max(wallet_btc, 0.0)
                wallet_btc = 0.0
        marked = (idle_coin * px) if isolated else mark_usd(wallet_btc, 0, 0.0, px)
        sl_brake.on_exit(
            reason, exit_time, bar_range_high,
            marked=marked, peak=equity_peak, skip_pct=peak_skip_pct,
            dump_high=dump_px if dump_peak is not None else None,
        )
        after_tp_gate.on_exit(reason, px, bar_range_low)

    def fill_buy(ts, raw_price: float, taker: bool) -> bool:
        nonlocal wallet_btc, idle_coin, contracts, avg, last_fill, fills, so_count
        nonlocal basket_start, basket_clip, pending_buy, pending_kind, pending_notional
        nonlocal reenter_from_stale, pending_armed_time, basket_so_floor, pending_so_floor, await_so_reclaim
        add_n = to_contracts(pending_notional)
        if pending_buy is None or add_n < 1:
            pending_buy = None
            pending_kind = None
            pending_notional = 0.0
            pending_armed_time = None
            return False
        fee_rate = cost.taker_fee if taker else cost.maker_fee
        slip = cost.taker_slip if taker else cost.maker_slip
        px = slipped(raw_price, 1, True, slip)
        if isolated and fills == 0:
            want_usd = basket_clip if basket_clip > 0 else clip
            alloc_coin = min(want_usd / px, idle_coin)
            alloc_usd = alloc_coin * px
            max_notional = notional_cap(alloc_usd, mr_limit) * HEADROOM
            add_n = to_contracts(min(pending_notional, max_notional))
            if add_n < 1 or alloc_usd < CONTRACT_SIZE:
                pending_buy = None
                pending_kind = None
                pending_notional = 0.0
                pending_armed_time = None
                return False
            pending_notional = add_n * CONTRACT_SIZE
            idle_coin -= alloc_coin
            wallet_btc = alloc_coin
            basket_clip = alloc_usd
        fee = fee_btc(add_n, px, fee_rate)
        new_n = contracts + add_n
        new_avg = (contracts * avg + add_n * px) / new_n if new_n else px
        new_cash = wallet_btc - fee
        post_mr = margin_ratio(new_n, px, new_cash, new_avg)
        if post_mr > mr_limit + 1e-9:
            events.append({"time": ts, "cost_model": cost.name, "event": "skip_mr_cap", "price": px, "pnl": 0.0})
            if isolated and fills == 0:
                idle_coin += wallet_btc
                wallet_btc = 0.0
            pending_buy = None
            pending_kind = None
            pending_notional = 0.0
            pending_armed_time = None
            return False
        wallet_btc = new_cash
        contracts = new_n
        avg = new_avg
        last_fill = px
        if fills == 0:
            basket_start = ts
            reenter_from_stale = False
            if pending_so_floor is not None:
                basket_so_floor = pending_so_floor
        fills += 1
        if pending_kind == "so":
            so_count += 1
            if so_reclaim:
                await_so_reclaim = True
        events.append({"time": ts, "cost_model": cost.name, "event": pending_kind or "buy", "price": px, "pnl": -fee * px})
        pending_buy = None
        pending_kind = None
        pending_notional = 0.0
        pending_armed_time = None
        return True

    def arm_next_buy(row) -> None:
        nonlocal pending_buy, pending_kind, pending_notional, basket_cap, basket_clip
        nonlocal pending_armed_time, pending_so_floor, await_so_reclaim
        mark = float(row.close)
        if isolated and contracts <= 0:
            usd = idle_coin * mark
        elif isolated:
            usd = mark_usd(wallet_btc, contracts, avg, mark)
        else:
            usd = mark_usd(wallet_btc, contracts, avg, mark)
        pos_notional = contracts * CONTRACT_SIZE
        remaining = notional_cap(usd, mr_limit) - pos_notional
        if remaining < CONTRACT_SIZE:
            pending_buy = None
            pending_armed_time = None
            return
        if contracts <= 0:
            close = float(row.close)
            marked = (idle_coin * close + mark_usd(wallet_btc, contracts, avg, close)) if isolated else mark_usd(wallet_btc, contracts, avg, close)
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
                close, float(row.ema55), float(row.resist), so_mode,
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
            basket_clip = clip if not isolated else min(clip, idle_coin * float(row.close))
            if sl_scale != 1.0:
                basket_clip *= sl_scale
            basket_cap = notional_cap(basket_clip, mr_limit) * HEADROOM
            size = min(planned_notional(basket_cap, 0), remaining * HEADROOM)
            if to_contracts(size) < 1:
                pending_buy = None
                pending_armed_time = None
                return
            prev = pending_buy
            pending_buy = limit
            pending_kind = "base"
            pending_notional = to_contracts(size) * CONTRACT_SIZE
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
            so_mode, last_fill, so_count, fills,
            float(row.ema21), float(row.support), float(row.close), float(row.ema55),
            remaining, basket_cap, min_size=CONTRACT_SIZE,
            range_low=floor,
            max_so=range_so_max, range_weight_size=range_weight_size,
            live_range_low=live_lo,
            so_reclaim=so_reclaim,
        )
        if plan is None:
            pending_buy = None
            pending_armed_time = None
            return
        limit, size = plan
        if to_contracts(size) < 1:
            pending_buy = None
            pending_armed_time = None
            return
        pending_buy = limit
        pending_kind = "so"
        pending_notional = to_contracts(size) * CONTRACT_SIZE

    for i, row in enumerate(rows):
        if liquidated:
            equity_rows.append({
                "time": row.close_time, "equity": 0.0, "equity_btc": max(wallet_btc, 0.0),
                "cost_model": cost.name, "mr": 1.0, "in_pos": False,
            })
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
            contracts <= 0
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
        if pending_stale and contracts > 0:
            reason = stale_exit_reason(
                basket_start, row.open_time, o, avg, stale_loss_pct, stale_days, max_hold_days,
                fills=fills, giveup_pct=giveup_pct, giveup_days=giveup_days,
                giveup_min_fills=giveup_min_fills,
            ) or (pending_stale if pending_stale == "TIME" else None)
            pending_stale = None
            if reason:
                hold = sl_hold_outcome_coinm(
                    rows, i, o, h, l, contracts, avg, wallet_btc, take_profit,
                )
                close_basket(row.close_time, o, reason, cost.taker_fee, cost.taker_slip, True)
                if trades:
                    trades[-1]["sl_hold"] = hold
        if contracts > 0:
            lp = liq_price(contracts, avg, wallet_btc)
            loss_frac = 1.0 - sl_keep
            if loss_frac <= 0:
                sp = None
            elif sl_from_liq:
                sp = stop_from_liq(avg, lp, loss_frac)
            else:
                sp = sl_price(contracts, avg, basket_clip, loss_frac) if basket_clip > 0 else None
            hp = tighter_stop(
                hard_stop_from_avg(avg, hard_sl_pct),
                sl_price(contracts, avg, basket_clip, hard_sl_basket) if hard_sl_basket else None,
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
                    hold = sl_hold_outcome_coinm(
                        rows, i, o, h, l, contracts, avg, wallet_btc, take_profit,
                    )
                close_basket(row.close_time, px, reason, cost.taker_fee, cost.taker_slip, True)
                if reason in ("SL50", "HARD") and trades:
                    trades[-1]["sl_hold"] = hold
                if reason == "LIQUIDATION":
                    wallet_btc = 0.0
                    if not isolated:
                        liquidated = True
                        equity_rows.append({
                            "time": row.close_time, "equity": 0.0, "equity_btc": 0.0,
                            "cost_model": cost.name, "mr": 1.0, "in_pos": False,
                        })
                        continue
            if contracts > 0 and margin_ratio(contracts, l, wallet_btc, avg) >= MR_EMERGENCY:
                close_basket(row.close_time, l, "EMERGENCY", cost.taker_fee, cost.taker_slip, True)
        tp = avg * (1.0 + take_profit) if contracts > 0 else None
        so_hit = pending_buy is not None and l <= pending_buy
        tp_hit = tp is not None and h >= tp
        if so_hit and tp_hit and contracts > 0:
            tp_hit = False
        gapped = pending_buy is not None and o < pending_buy
        if gapped:
            fill_buy(row.open_time, o, True)
        elif so_hit:
            fill_buy(row.open_time, pending_buy, False)
        if contracts > 0 and tp_hit:
            close_basket(row.close_time, tp, "TP", cost.maker_fee, cost.maker_slip, False)
        if contracts > 0 and funding_hit(row.open_time):
            wallet_btc -= contracts * CONTRACT_SIZE / c * FUNDING_PLACEHOLDER
        if skip_base_arm:
            pending_buy = None
            pending_kind = None
            pending_notional = 0.0
            pending_armed_time = None
        else:
            arm_next_buy(row)
        if contracts > 0:
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
        mr = margin_ratio(contracts, c, wallet_btc, avg) if contracts > 0 else 0.0
        eq = (idle_coin * c + mark_usd(wallet_btc, contracts, avg, c)) if isolated else mark_usd(wallet_btc, contracts, avg, c)
        equity_peak = wallet_peak.update(row.close_time, eq)
        if price_peak is not None:
            px_high = price_peak.update(row.close_time, h)
        if dump_peak is not None:
            dump_px = dump_peak.update(row.close_time, h)
        equity_rows.append({
            "time": row.close_time,
            "equity": eq,
            "equity_btc": (idle_coin + mark_btc(wallet_btc, contracts, avg, c)) if isolated else mark_btc(wallet_btc, contracts, avg, c),
            "cost_model": cost.name, "mr": mr, "in_pos": contracts > 0,
        })

    last = rows[-1]
    last_px = float(last.close)
    hold_usd = start_btc * last_px
    if liquidated:
        remaining = {
            "cost_model": cost.name, "as_of": last.close_time, "btc_close": last_px,
            "liquidated": True, "in_position": False, "remaining_mark_usdt": 0.0,
            "if_flatten_today_usdt": 0.0, "remaining_btc": 0.0, "qty": 0.0,
            "avg_entry": float("nan"), "unrealized_usdt": 0.0, "mr_pct": 0.0,
            "start_equity_usdt": clip, "start_btc": start_btc, "start_coin": start_btc,
            "remaining_btc": 0.0, "remaining_coin": 0.0,
            "buy_hold_usdt": hold_usd,
            "idle_coin": 0.0,
        }
    else:
        mark_u = (idle_coin * last_px if isolated else 0.0) + mark_usd(wallet_btc, contracts, avg, last_px)
        upnl_u = upnl_btc(contracts, avg, last_px) * last_px
        coin_mark = (idle_coin if isolated else 0.0) + mark_btc(wallet_btc, contracts, avg, last_px)
        remaining = {
            "cost_model": cost.name, "as_of": last.close_time, "btc_close": last_px,
            "liquidated": False, "in_position": contracts > 0, "remaining_mark_usdt": mark_u,
            "qty": float(contracts), "avg_entry": avg if contracts > 0 else float("nan"),
            "unrealized_usdt": upnl_u,
            "mr_pct": margin_ratio(contracts, last_px, wallet_btc, avg) * 100 if contracts > 0 else 0.0,
            "start_equity_usdt": clip, "start_btc": start_btc, "start_coin": start_btc,
            "remaining_btc": coin_mark, "remaining_coin": coin_mark,
            "buy_hold_usdt": hold_usd, "isolated": isolated,
            "idle_coin": idle_coin if isolated else 0.0,
        }
        if contracts > 0:
            px = slipped(last_px, 1, False, cost.taker_slip)
            fee = fee_btc(contracts, px, cost.taker_fee)
            flatten_btc = (idle_coin if isolated else 0.0) + wallet_btc + upnl_btc(contracts, avg, px) - fee
            remaining["if_flatten_today_usdt"] = flatten_btc * px
            # leave the basket open; do not MTM-close for the trade list
        else:
            remaining["if_flatten_today_usdt"] = ((idle_coin if isolated else wallet_btc) * last_px)
    equity_rows.append({
        "time": last.close_time, "equity": remaining["remaining_mark_usdt"],
        "equity_btc": remaining.get("remaining_btc", 0.0),
        "cost_model": cost.name, "mr": remaining["mr_pct"] / 100.0, "in_pos": remaining["in_position"],
    })
    return pd.DataFrame(trades), pd.DataFrame(equity_rows), pd.DataFrame(events), remaining


def write_memo(summary, trades, result, reason, counts, remaining, start_btc) -> None:
    sample = trades[trades.cost_model == COST_A.name].head(10) if not trades.empty else pd.DataFrame()
    liq = liquidation_stats(trades)
    rem = remaining if remaining is not None else pd.DataFrame()
    text = "\n".join([
        f"# Product {PRODUCT} Coin-M DCA Results", "",
        "## 1. This is not the scalp bot",
        "Long-only Binance BTCUSD_PERP (COIN-M inverse) with F6 rules: 1% MR cap, "
        "SL80 vs a frozen $10,000 USD clip, TP +2% from average entry. Start wallet is "
        f"${START_EQUITY:,.0f} of BTC ({start_btc:.8f} BTC at the first tradable open). "
        "Idle BTC is still marked to USD when price moves. Do not wire into main.py.",
        "",
        "## 2. Inverse margin",
        "Contracts are $100 notional. MR = (contracts * 100 * 0.4%) / (wallet_btc * mark). "
        "That matches USD-M MR when wallet is expressed in USD. Liquidation uses the inverse formula.",
        "",
        "## 3. Remaining vs buy-and-hold BTC",
        "",
        rem.to_markdown(index=False, floatfmt=".2f") if not rem.empty else "No snapshot.",
        "",
        "buy_hold_usdt is start BTC marked at the last close with no futures. "
        "Split tables still attribute only futures round-trip USD P&L onto a fresh $10,000; "
        "they do not include idle-BTC USD drift.",
        "",
        "## 4. First risk exit",
        "",
        liq.to_markdown(index=False, floatfmt=".2f") if not liq.empty else "No baskets.",
        "",
        "## 5. Counts",
        f"- 1h bars: {counts['bars']}",
        f"- Cost A baskets: {counts['baskets']}",
        f"- Cost A events: {counts['events']}",
        f"- start_btc: {start_btc:.8f}",
        "",
        "## 6. Train / validate / holdout (futures USD P&L only)",
        "",
        summary.to_markdown(index=False),
        "",
        "## 7. Decision",
        result,
        "",
        "## 8. One sentence",
        reason,
        "",
        "## 9. Sample baskets (Cost A)",
        "",
        sample.to_markdown(index=False) if not sample.empty else "No baskets.",
        "",
    ]) + "\n"
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "RESULTS_DCA_COINM.md"), "w") as f:
        f.write(text)
    try:
        with open("RESULTS_DCA_COINM.md", "w") as f:
            f.write(text)
    except PermissionError:
        pass


def save_outputs(trades, equities, events, summary, remaining, tag: str = "G1", plots: bool = True) -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    summary.to_csv(os.path.join(RESULTS_DIR, "summary.csv"), index=False)
    remaining.to_csv(os.path.join(RESULTS_DIR, "remaining_balance.csv"), index=False)
    liq = liquidation_stats(trades)
    if not liq.empty:
        liq.to_csv(os.path.join(RESULTS_DIR, "liquidation.csv"), index=False)
    trades.to_csv(os.path.join(RESULTS_DIR, "trades.csv"), index=False)
    events.to_csv(os.path.join(RESULTS_DIR, "events.csv"), index=False)
    equities.to_csv(os.path.join(RESULTS_DIR, f"equity_{tag}.csv"), index=False)
    if not plots:
        return
    eq = equities[equities.cost_model == COST_B.name]
    if eq.empty:
        return
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(eq.time, eq.equity, label=f"{tag} Coin-M Cost B USD")
    ax.legend()
    ax.set_title(f"{tag} Coin-M equity USD - Cost B")
    fig.tight_layout()
    fig.savefig(os.path.join(RESULTS_DIR, f"equity_{tag}.png"))
    plt.close(fig)


def run_coinm_suite(
    symbol: str = "BTCUSD_PERP",
    contract_size: float | None = None,
    results_dir: str = RESULTS_DIR,
    product: str = PRODUCT,
    tag: str = "G1",
    write_root_memo: bool = True,
    isolated: bool = False,
    start_usd: float | None = None,
    mr_cap: float | None = None,
    equity_stop_frac: float | None = None,
    quiet: bool = False,
    so_style: str | None = None,
    tp_pct: float | None = None,
    sl_from_liq: bool = False,
    interval: str = "1h",
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
) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    global CONTRACT_SIZE, RESULTS_DIR, PRODUCT
    CONTRACT_SIZE = float(contract_size if contract_size is not None else 100.0)
    RESULTS_DIR = results_dir
    PRODUCT = product
    clip = START_EQUITY if start_usd is None else float(start_usd)
    df = prepare_data(symbol, interval=interval)
    start_coin = clip / float(df.iloc[0].open)
    if not quiet:
        print(
            f"BAR_COUNTS {interval}={len(df)} source=Binance coin-m {symbol} cs={CONTRACT_SIZE:g} "
            f"mr_cap={mr_cap if mr_cap is not None else MR_CAP} start_coin={start_coin:.8f} "
            f"first_open={float(df.iloc[0].open):.6f} isolated={isolated} "
            f"so_style={so_style or SO_GEOMETRIC}"
        )
    all_trades, all_eq, all_ev, all_rem = [], [], [], []
    summary_rows = []
    baskets = 0
    events_n = 0
    for cost in (COST_A, COST_B):
        trades, equity, events, remaining = run_dca(
            df, cost, start_coin, isolated=isolated,
            clip_usd=clip, mr_cap=mr_cap, equity_stop_frac=equity_stop_frac,
            so_style=so_style, tp_pct=tp_pct, sl_from_liq=sl_from_liq,
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
            summary_rows.append(summarize(trades, equity, split, cost.name, product=product))
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
        print(remaining_df.to_string(index=False, float_format=lambda value: f"{value:.6f}"))
        print("\nLIQUIDATION_DOLLARS")
        print(liquidation_stats(trades_df).to_string(index=False, float_format=lambda value: f"{value:.2f}"))
        print(f"\nDECISION {result}: {reason}")
    save_outputs(trades_df, equity_df, events_df, summary, remaining_df, tag=tag, plots=not quiet)
    if write_root_memo:
        write_memo(
            summary, trades_df, result, reason,
            {"bars": len(df), "baskets": baskets, "events": events_n},
            remaining_df, start_coin,
        )
    else:
        os.makedirs(RESULTS_DIR, exist_ok=True)
        with open(os.path.join(RESULTS_DIR, f"RESULTS_{tag}.md"), "w") as f:
            f.write(f"# {product}\n\n{result}: {reason}\n")
    return remaining_df, summary, start_coin


def main() -> None:
    run_coinm_suite()


if __name__ == "__main__":
    main()
