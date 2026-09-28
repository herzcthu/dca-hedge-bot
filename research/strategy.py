#!/usr/bin/env python3
"""Custom event-loop backtester for the adaptive BTCUSDT 5m scalper."""

from __future__ import annotations

from dataclasses import dataclass
import pandas as pd

from config import (
    ADX_RANGE, ADX_TREND, COOLDOWN_BARS, CostModel, DAILY_STOP_FRACTION,
    FUNDING_PLACEHOLDER, LIMIT_CANCEL_BARS, LOSS_COOLDOWN_COUNT, MAX_HOLD_BARS,
    MAX_LEVERAGE, PULLBACK_TOLERANCE, RANGE_RSI_LONG, RANGE_RSI_SHORT,
    RANGE_STOP_BUFFER, RISK_FRACTION, START_EQUITY, TREND_STOP_ATR_MULT,
    TREND_STOP_CAP, TREND_TP_ATR_MULT, VWAP_SIGMA_MULT,
)


@dataclass(frozen=True)
class Variant:
    name: str
    trend: bool
    range: bool
    breakeven: bool = False


V1 = Variant("V1_trend_only", trend=True, range=False)
V2 = Variant("V2_range_only", trend=False, range=True)
V3 = Variant("V3_combined", trend=True, range=True)
V4 = Variant("V4_combined_breakeven", trend=True, range=True, breakeven=True)
VARIANTS = [V1, V2, V3, V4]
FILL_MODELS = ["F-OPEN", "F-LIMIT"]


def trend_allowed(row: pd.Series, side: int, adx_trend: float = ADX_TREND) -> bool:
    return bool(row.adx14 >= adx_trend and ((side > 0 and row.ema9 > row.ema21) or (side < 0 and row.ema9 < row.ema21)))


def range_allowed(row: pd.Series, adx_range: float = ADX_RANGE) -> bool:
    return bool(row.adx14 <= adx_range)


def trend_bias(row: pd.Series, side: int) -> bool:
    if pd.isna(row.close_15m) or pd.isna(row.vwap_15m):
        return False
    return bool(row.close_15m > row.vwap_15m) if side > 0 else bool(row.close_15m < row.vwap_15m)


def funding_crossings(start: pd.Timestamp, end: pd.Timestamp) -> int:
    count = 0
    cursor = start.ceil("h")
    while cursor <= end:
        if cursor.hour in (0, 8, 16) and cursor.minute == 0:
            count += 1
        cursor += pd.Timedelta(hours=1)
    return count


def _slipped(price: float, side: int, is_entry: bool, cost: float) -> float:
    return price * (1 + side * cost) if is_entry else price * (1 - side * cost)


def _size_trade(equity: float, entry: float, stop: float) -> tuple[float, float] | None:
    stop_distance_pct = abs(entry - stop) / entry
    if stop_distance_pct <= 0:
        return None
    notional = equity * RISK_FRACTION / stop_distance_pct
    if notional > equity * MAX_LEVERAGE:
        return None
    return notional, stop_distance_pct


def _trend_signal(rows: list, i: int, fill_model: str, adx_trend: float, stop_mult: float, tp_mult: float) -> dict | None:
    row = rows[i]
    previous = rows[i - 1]
    for side in (1, -1):
        if not trend_allowed(row, side, adx_trend) or not trend_bias(row, side):
            continue
        if side > 0 and row.close <= row.vwap:
            continue
        if side < 0 and row.close >= row.vwap:
            continue
        levels = [("ema21", row.ema21), ("vwap", row.vwap)]
        for tag_name, level in levels:
            if pd.isna(level) or pd.isna(row.atr14):
                continue
            touched = (
                side > 0 and min(row.low, previous.low) <= level * (1 + PULLBACK_TOLERANCE)
            ) or (
                side < 0 and max(row.high, previous.high) >= level * (1 - PULLBACK_TOLERANCE)
            )
            reclaimed = row.close > level if side > 0 else row.close < level
            if not touched or not reclaimed:
                continue
            if fill_model == "F-OPEN":
                entry_i = i + 1
                entry = float(rows[entry_i].open)
                entry_type = "open"
            else:
                entry_i = None
                for j in range(i + 1, min(i + 1 + LIMIT_CANCEL_BARS, len(rows) - 1) + 1):
                    bar = rows[j]
                    if (side > 0 and bar.low <= level) or (side < 0 and bar.high >= level):
                        entry_i = j
                        break
                if entry_i is None:
                    return {"skipped": "unfilled_limit"}
                entry = float(level)
                entry_type = "limit"
            stop_distance = min(stop_mult * float(row.atr14), TREND_STOP_CAP * entry)
            stop = entry - stop_distance if side > 0 else entry + stop_distance
            atr_target = entry + side * tp_mult * float(row.atr14)
            vwap_band = row.vwap_upper_1s if side > 0 else row.vwap_lower_1s
            one_r = entry + side * abs(entry - stop)
            candidates = [atr_target]
            if side > 0 and not pd.isna(vwap_band) and vwap_band >= one_r:
                candidates.append(float(vwap_band))
            if side < 0 and not pd.isna(vwap_band) and vwap_band <= one_r:
                candidates.append(float(vwap_band))
            target = min(candidates) if side > 0 else max(candidates)
            return {"engine": "trend", "side": side, "entry_i": entry_i, "entry": entry, "entry_type": entry_type, "sl": stop, "tp": target, "adx": float(row.adx14), "tag": tag_name}
    return None


def _range_signal(rows: list, i: int, fill_model: str, adx_range: float) -> dict | None:
    pierce = rows[i]
    confirm_i = i + 1
    confirm = rows[confirm_i]
    if not range_allowed(pierce, adx_range):
        return None
    side = 0
    if pierce.close <= pierce.bb_lower and pierce.rsi14 < RANGE_RSI_LONG and confirm.close > confirm.bb_lower:
        side = 1
    elif pierce.close >= pierce.bb_upper and pierce.rsi14 > RANGE_RSI_SHORT and confirm.close < confirm.bb_upper:
        side = -1
    if side == 0:
        return None
    if fill_model == "F-OPEN":
        entry_i = confirm_i + 1
        entry = float(rows[entry_i].open)
        entry_type = "open"
    else:
        level = float(confirm.close)
        entry_i = None
        for j in range(confirm_i + 1, min(confirm_i + LIMIT_CANCEL_BARS, len(rows) - 1) + 1):
            bar = rows[j]
            if (side > 0 and bar.low <= level) or (side < 0 and bar.high >= level):
                entry_i = j
                break
        if entry_i is None:
            return {"skipped": "unfilled_limit"}
        entry = level
        entry_type = "limit"
    extreme = min(pierce.low, confirm.low) if side > 0 else max(pierce.high, confirm.high)
    stop = extreme * (1 - RANGE_STOP_BUFFER) if side > 0 else extreme * (1 + RANGE_STOP_BUFFER)
    return {"engine": "range", "side": side, "entry_i": entry_i, "entry": entry, "entry_type": entry_type, "sl": float(stop), "tp": float(confirm.bb_mid), "adx": float(pierce.adx14), "tag": "bb_mid"}


def run_backtest(
    df: pd.DataFrame,
    variant: Variant,
    fill_model: str,
    cost_model: CostModel,
    adx_trend: float = ADX_TREND,
    adx_range: float = ADX_RANGE,
    trend_stop_mult: float = TREND_STOP_ATR_MULT,
    trend_tp_mult: float = TREND_TP_ATR_MULT,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = list(df.itertuples(index=False))
    equity = START_EQUITY
    day_start_equity = START_EQUITY
    day = None
    cooldown_until = -1
    consecutive_losses = 0
    trades: list[dict] = []
    skipped: list[dict] = []
    equity_rows: list[dict] = []
    total_signals = 0
    unsizable = 0
    i = 60
    while i < len(rows) - MAX_HOLD_BARS - LIMIT_CANCEL_BARS - 3:
        row_day = rows[i].open_time.date()
        if day != row_day:
            day = row_day
            day_start_equity = equity
        equity_rows.append({"time": rows[i].close_time, "equity": equity})
        if i < cooldown_until or equity <= day_start_equity * (1 - DAILY_STOP_FRACTION):
            i += 1
            continue

        signal = None
        if variant.trend:
            signal = _trend_signal(rows, i, fill_model, adx_trend, trend_stop_mult, trend_tp_mult)
            if signal and signal.get("skipped"):
                skipped.append({"time": rows[i].close_time, "engine": "trend", "reason": signal["skipped"]})
                signal = None
        if signal is None and variant.range:
            signal = _range_signal(rows, i, fill_model, adx_range)
            if signal and signal.get("skipped"):
                skipped.append({"time": rows[i].close_time, "engine": "range", "reason": signal["skipped"]})
                signal = None
        if signal is None:
            i += 1
            continue

        total_signals += 1
        sized = _size_trade(equity, signal["entry"], signal["sl"])
        if sized is None:
            unsizable += 1
            skipped.append({"time": rows[i].close_time, "engine": signal["engine"], "reason": "unsizable"})
            i += 1
            continue
        notional, stop_distance_pct = sized
        entry_i = signal["entry_i"]
        side = signal["side"]
        entry_cost = cost_model.limit_fee + cost_model.limit_slippage if signal["entry_type"] == "limit" else cost_model.open_fee + cost_model.open_slippage
        entry = _slipped(signal["entry"], side, True, cost_model.limit_slippage if signal["entry_type"] == "limit" else cost_model.open_slippage)
        stop = signal["sl"]
        target = signal["tp"]
        breakeven_stop = None
        one_r_price = entry + side * abs(entry - stop)
        exit_i = min(entry_i + MAX_HOLD_BARS, len(rows) - 1)
        exit_reason = "TIME"
        exit_price = float(rows[exit_i].close)
        exit_fee = cost_model.exit_fee
        exit_slippage = cost_model.exit_slippage
        for j in range(entry_i, min(entry_i + MAX_HOLD_BARS, len(rows) - 1) + 1):
            bar = rows[j]
            active_stop = breakeven_stop if breakeven_stop is not None else stop
            if side > 0:
                if bar.low <= active_stop:
                    exit_i, exit_reason, exit_price = j, "SL" if breakeven_stop is None else "BE", active_stop
                    exit_fee, exit_slippage = cost_model.stop_fee, cost_model.stop_slippage
                    break
                if bar.high >= target:
                    exit_i, exit_reason, exit_price = j, "TP", target
                    break
                if variant.breakeven and signal["engine"] == "trend" and bar.high >= one_r_price:
                    breakeven_stop = entry * (1 + entry_cost + cost_model.stop_fee + cost_model.stop_slippage)
            else:
                if bar.high >= active_stop:
                    exit_i, exit_reason, exit_price = j, "SL" if breakeven_stop is None else "BE", active_stop
                    exit_fee, exit_slippage = cost_model.stop_fee, cost_model.stop_slippage
                    break
                if bar.low <= target:
                    exit_i, exit_reason, exit_price = j, "TP", target
                    break
                if variant.breakeven and signal["engine"] == "trend" and bar.low <= one_r_price:
                    breakeven_stop = entry * (1 - entry_cost - cost_model.stop_fee - cost_model.stop_slippage)

        exit_exec = _slipped(exit_price, side, False, exit_slippage)
        gross_pct = (exit_exec / entry - 1.0) * side
        funding_cost = funding_crossings(rows[entry_i].open_time, rows[exit_i].close_time) * FUNDING_PLACEHOLDER
        fees_pct = entry_cost + exit_fee + funding_cost
        net_pct = gross_pct - fees_pct
        pnl = notional * net_pct
        fees_usdt = notional * fees_pct
        equity += pnl
        if pnl < 0:
            consecutive_losses += 1
            if consecutive_losses >= LOSS_COOLDOWN_COUNT:
                cooldown_until = exit_i + COOLDOWN_BARS
                consecutive_losses = 0
        else:
            consecutive_losses = 0
        trades.append({
            "variant": variant.name, "fill_model": fill_model, "cost_model": cost_model.name,
            "entry_time": rows[entry_i].open_time, "engine": signal["engine"], "side": "long" if side > 0 else "short",
            "entry": entry, "sl": stop, "tp": target, "exit_time": rows[exit_i].close_time,
            "exit_reason": exit_reason, "pnl_net": pnl, "pnl_net_pct": net_pct, "fees": fees_usdt,
            "regime_adx": signal["adx"], "notional": notional, "hold_bars": exit_i - entry_i + 1,
            "stop_distance_pct": stop_distance_pct, "unsizable_signals": unsizable, "total_signals": total_signals,
        })
        for j in range(i + 1, exit_i + 1):
            if j < len(rows):
                mark_pct = (float(rows[j].close) / entry - 1.0) * side - entry_cost
                equity_rows.append({"time": rows[j].close_time, "equity": equity - pnl + notional * mark_pct})
        i = exit_i + 1

    equity_rows.append({"time": rows[-1].close_time, "equity": equity})
    skipped_df = pd.DataFrame(skipped)
    if not skipped_df.empty:
        skipped_df["variant"] = variant.name
        skipped_df["fill_model"] = fill_model
        skipped_df["cost_model"] = cost_model.name
    return pd.DataFrame(trades), pd.DataFrame(equity_rows).drop_duplicates("time").sort_values("time"), skipped_df
