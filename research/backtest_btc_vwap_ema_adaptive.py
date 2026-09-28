#!/usr/bin/env python3
"""Research-only BTCUSDT 5-minute Adaptive VWAP-EMA Scalper backtest.

Frozen composite spec (as specified by the user, no parameter tuning):

Regime gate (every 5m bar):
  - ADX(14) >= 22 and EMA9 vs EMA21 stacked -> Trend engine
  - ADX(14) <= 18 -> Range engine
  - Between 18-22 -> flat, no new trades

Trend engine (VWAP + EMA pullback):
  - Bias: last CLOSED 15m bar's close must be above both 15m VWAP and 15m EMA21 for
    longs (mirrored for shorts). Built by aggregating 5m candles into 15m buckets.
  - Long: 9 EMA > 21 EMA, a bar's low tags the 21 EMA, the next bar closes back above
    the 21 EMA -> resting limit at the tag level, canceled if unfilled after 2 candles.
  - Stop: 1.2x ATR(14) beyond the 21 EMA, capped at 0.28% from entry.
  - Target: whichever is nearer of 1.6x ATR(14) or a 1-sigma VWAP band (20-bar rolling
    stdev of close-vwap). No trailing stop (kept out of this first honest pass).
  - Time stop: 12 bars (60 minutes), matching every other scalp test in this repo.

Range engine (Bollinger fade):
  - ADX(14) <= 18 only.
  - Long: close <= lower BB(20,2) and RSI(14) < 32; next bar closes back inside the
    band -> entry at following bar's open.
  - Stop: beyond the extreme wick of the two signal bars, +0.04% buffer.
  - Target: the middle band (20-SMA) at the confirmation bar. No runner.
  - Time stop: 12 bars (60 minutes) safety cap.

Costs: 0.06% round trip (maker+maker 0.02% x2 plus 0.5-1 tick slippage), the upper end
of the user's own "0.04-0.06% all-in" budget, so this is not a best-case number.

Uses public Binance Futures klines only; it never loads credentials, starts Docker,
or places orders.
"""

from __future__ import annotations

from datetime import datetime, timezone

from btc_klines_5m import SYMBOL, get_klines
from backtest_btc_bollinger_fade import bollinger_bands
from backtest_btc_ema_momentum import ema
from backtest_btc_rsi_reversion import rsi
from backtest_btc_vwap_reversion import session_vwap

DAYS_HISTORY = 730
CACHE_DIR = "data/.btc_5m_pages_24mo"

ADX_PERIOD = 14
ADX_TREND_MIN = 22.0
ADX_RANGE_MAX = 18.0
EMA_FAST, EMA_SLOW = 9, 21
ATR_PERIOD = 14
VWAP_SIGMA_WINDOW = 20
TREND_STOP_ATR_MULT = 1.2
TREND_STOP_CAP = 0.0028
TREND_TARGET_ATR_MULT = 1.6
TREND_TARGET_VWAP_SIGMA = 1.0
LIMIT_FILL_WINDOW = 2
RSI_OVERSOLD, RSI_OVERBOUGHT = 32.0, 68.0
RANGE_STOP_BUFFER = 0.0004
HOLD_BARS = 12
FEE_ROUND_TRIP = 0.0006


def true_range_and_adx(highs: list[float], lows: list[float], closes: list[float], period: int = ADX_PERIOD):
    n = len(highs)
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    tr = [0.0] * n
    for i in range(1, n):
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        plus_dm[i] = up_move if (up_move > down_move and up_move > 0) else 0.0
        minus_dm[i] = down_move if (down_move > up_move and down_move > 0) else 0.0
        tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))

    atr: list[float | None] = [None] * n
    adx_values: list[float | None] = [None] * n
    if n <= period * 2:
        return adx_values, atr

    smoothed_tr = sum(tr[1:period + 1])
    smoothed_plus = sum(plus_dm[1:period + 1])
    smoothed_minus = sum(minus_dm[1:period + 1])
    atr[period] = smoothed_tr / period
    dx_values: list[float | None] = [None] * n

    for i in range(period + 1, n):
        smoothed_tr = smoothed_tr - smoothed_tr / period + tr[i]
        smoothed_plus = smoothed_plus - smoothed_plus / period + plus_dm[i]
        smoothed_minus = smoothed_minus - smoothed_minus / period + minus_dm[i]
        atr[i] = smoothed_tr / period
        plus_di = 100 * (smoothed_plus / smoothed_tr) if smoothed_tr else 0.0
        minus_di = 100 * (smoothed_minus / smoothed_tr) if smoothed_tr else 0.0
        di_sum = plus_di + minus_di
        dx_values[i] = 100 * abs(plus_di - minus_di) / di_sum if di_sum > 0 else 0.0

    first_adx_index = period * 2
    if first_adx_index < n:
        seed_values = [v for v in dx_values[period + 1:first_adx_index + 1] if v is not None]
        adx_values[first_adx_index] = sum(seed_values) / period
        for i in range(first_adx_index + 1, n):
            adx_values[i] = (adx_values[i - 1] * (period - 1) + dx_values[i]) / period
    return adx_values, atr


def build_15m_bias(candles: list[list]):
    """Aggregates 5m candles into 15m buckets and returns (closes, vwaps, ema21) per bucket."""
    buckets = []
    for start in range(0, len(candles) - 2, 3):
        group = candles[start:start + 3]
        if len(group) < 3:
            break
        high = max(float(c[2]) for c in group)
        low = min(float(c[3]) for c in group)
        close = float(group[-1][4])
        volume = sum(float(c[5]) for c in group)
        buckets.append([group[0][0], group[0][1], high, low, close, volume])
    closes_15m = [b[4] for b in buckets]
    vwaps_15m = session_vwap(buckets)
    ema21_15m = ema(closes_15m, 21)
    return closes_15m, vwaps_15m, ema21_15m


def rolling_stdev(values: list[float], window: int) -> list[float | None]:
    result: list[float | None] = [None] * len(values)
    for i in range(window - 1, len(values)):
        chunk = values[i - window + 1:i + 1]
        mean = sum(chunk) / window
        variance = sum((v - mean) ** 2 for v in chunk) / window
        result[i] = variance ** 0.5
    return result


def simulate(candles: list[list]) -> list[dict]:
    highs = [float(c[2]) for c in candles]
    lows = [float(c[3]) for c in candles]
    closes = [float(c[4]) for c in candles]
    opens = [float(c[1]) for c in candles]

    adx_values, atr_values = true_range_and_adx(highs, lows, closes)
    ema_fast = ema(closes, EMA_FAST)
    ema_slow = ema(closes, EMA_SLOW)
    vwap_5m = session_vwap(candles)
    vwap_deviation = [c / v - 1.0 if v else 0.0 for c, v in zip(closes, vwap_5m)]
    vwap_sigma = rolling_stdev(vwap_deviation, VWAP_SIGMA_WINDOW)
    closes_15m, vwaps_15m, ema21_15m = build_15m_bias(candles)
    upper_bb, lower_bb = bollinger_bands(closes)
    mid_bb = [
        (u + l) / 2 if u is not None and l is not None else None
        for u, l in zip(upper_bb, lower_bb)
    ]
    rsi_values = rsi(closes)

    trades: list[dict] = []
    index = max(EMA_SLOW, ADX_PERIOD * 2, 20) + 1

    def bias_direction(i: int) -> int:
        bucket_index = i // 3 - 1
        if bucket_index < 0 or bucket_index >= len(closes_15m):
            return 0
        close_15m, vwap15, ema15 = closes_15m[bucket_index], vwaps_15m[bucket_index], ema21_15m[bucket_index]
        if ema15 is None:
            return 0
        if close_15m > vwap15 and close_15m > ema15:
            return 1
        if close_15m < vwap15 and close_15m < ema15:
            return -1
        return 0

    while index + HOLD_BARS + 3 < len(candles):
        adx = adx_values[index]
        if adx is None:
            index += 1
            continue

        traded = False

        if adx >= ADX_TREND_MIN and ema_fast[index] is not None and ema_slow[index] is not None:
            trend_dir = 1 if ema_fast[index] > ema_slow[index] else -1
            bias = bias_direction(index)
            if trend_dir == bias and bias != 0 and index + 1 < len(candles):
                level = ema_slow[index]
                confirm_ok = (
                    (trend_dir > 0 and lows[index] <= level and closes[index + 1] > ema_slow[index + 1])
                    or (trend_dir < 0 and highs[index] >= level and closes[index + 1] < ema_slow[index + 1])
                )
                if confirm_ok:
                    fill_index = None
                    for offset in range(1, LIMIT_FILL_WINDOW + 1):
                        candidate = index + 1 + offset
                        if candidate >= len(candles):
                            break
                        touched = lows[candidate] <= level if trend_dir > 0 else highs[candidate] >= level
                        if touched:
                            fill_index = candidate
                            break
                    if fill_index is not None:
                        entry = level
                        atr = atr_values[index] or 0.0
                        stop_distance = min(TREND_STOP_ATR_MULT * atr, TREND_STOP_CAP * entry)
                        sigma = vwap_sigma[index] or 0.0
                        vwap_target_level = vwap_5m[index] * (1 + TREND_TARGET_VWAP_SIGMA * sigma * trend_dir)
                        atr_target_level = entry + TREND_TARGET_ATR_MULT * atr * trend_dir
                        # Only a target on the favorable side of entry is a valid candidate; a
                        # VWAP band that has already been overtaken by the pullback is discarded
                        # rather than clamped, which would otherwise create a near-zero-distance
                        # "target" that fires immediately and loses to fees.
                        if trend_dir > 0:
                            stop_price = entry - stop_distance
                            candidates = [atr_target_level] + ([vwap_target_level] if sigma and vwap_target_level > entry else [])
                            target_price = min(candidates)
                        else:
                            stop_price = entry + stop_distance
                            candidates = [atr_target_level] + ([vwap_target_level] if sigma and vwap_target_level < entry else [])
                            target_price = max(candidates)

                        outcome, held, exit_price = "TIME", HOLD_BARS, closes[min(fill_index + HOLD_BARS - 1, len(candles) - 1)]
                        for offset in range(1, HOLD_BARS + 1):
                            exit_index = fill_index + offset
                            if exit_index >= len(candles):
                                break
                            if trend_dir > 0:
                                if lows[exit_index] <= stop_price:
                                    outcome, exit_price, held = "SL", stop_price, offset
                                    break
                                if highs[exit_index] >= target_price:
                                    outcome, exit_price, held = "TP", target_price, offset
                                    break
                            else:
                                if highs[exit_index] >= stop_price:
                                    outcome, exit_price, held = "SL", stop_price, offset
                                    break
                                if lows[exit_index] <= target_price:
                                    outcome, exit_price, held = "TP", target_price, offset
                                    break

                        gross_return = (exit_price / entry - 1.0) * trend_dir
                        trades.append({
                            "engine": "trend",
                            "outcome": outcome,
                            "net_pct": gross_return - FEE_ROUND_TRIP,
                            "held_bars": held,
                            "entry_time": candles[fill_index][0],
                        })
                        index = fill_index + held
                        traded = True

        if not traded and adx <= ADX_RANGE_MAX:
            lower, upper, mid, rsi_val = lower_bb[index], upper_bb[index], mid_bb[index], rsi_values[index]
            if lower is not None and upper is not None:
                direction = 0
                if closes[index] <= lower and rsi_val is not None and rsi_val < RSI_OVERSOLD:
                    direction = 1
                elif closes[index] >= upper and rsi_val is not None and rsi_val > RSI_OVERBOUGHT:
                    direction = -1
                if direction != 0 and index + 2 < len(candles):
                    confirm_index = index + 1
                    confirmed = (
                        (direction > 0 and closes[confirm_index] > lower_bb[confirm_index])
                        or (direction < 0 and closes[confirm_index] < upper_bb[confirm_index])
                    )
                    if confirmed:
                        entry_index = confirm_index + 1
                        entry = opens[entry_index]
                        extreme = min(lows[index], lows[confirm_index]) if direction > 0 else max(highs[index], highs[confirm_index])
                        stop_price = extreme * (1 - RANGE_STOP_BUFFER) if direction > 0 else extreme * (1 + RANGE_STOP_BUFFER)
                        target_price = mid_bb[confirm_index]

                        outcome, held = "TIME", HOLD_BARS
                        exit_price = closes[min(entry_index + HOLD_BARS - 1, len(candles) - 1)]
                        for offset in range(0, HOLD_BARS):
                            exit_index = entry_index + offset
                            if exit_index >= len(candles):
                                break
                            if direction > 0:
                                if lows[exit_index] <= stop_price:
                                    outcome, exit_price, held = "SL", stop_price, offset + 1
                                    break
                                if target_price is not None and highs[exit_index] >= target_price:
                                    outcome, exit_price, held = "TP", target_price, offset + 1
                                    break
                            else:
                                if highs[exit_index] >= stop_price:
                                    outcome, exit_price, held = "SL", stop_price, offset + 1
                                    break
                                if target_price is not None and lows[exit_index] <= target_price:
                                    outcome, exit_price, held = "TP", target_price, offset + 1
                                    break

                        gross_return = (exit_price / entry - 1.0) * direction
                        trades.append({
                            "engine": "range",
                            "outcome": outcome,
                            "net_pct": gross_return - FEE_ROUND_TRIP,
                            "held_bars": held,
                            "entry_time": candles[entry_index][0],
                        })
                        index = entry_index + held
                        traded = True

        if not traded:
            index += 1

    return trades


def _split_report(label: str, trades: list[dict], total_days: float) -> dict:
    if not trades:
        print(f"{label}: no trades")
        return {"label": label, "n": 0}
    net = [t["net_pct"] for t in trades]
    wins = [v for v in net if v > 0]
    losses = [v for v in net if v <= 0]
    total = sum(net)
    profit_factor = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else float("inf")
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    win_loss_ratio = (avg_win / abs(avg_loss)) if avg_loss != 0 else float("inf")
    held_minutes = sum(t["held_bars"] for t in trades) * 5
    time_in_market_pct = held_minutes / (total_days * 24 * 60) * 100 if total_days > 0 else 0.0
    trades_per_day = len(trades) / total_days if total_days > 0 else 0.0

    months: dict[str, float] = {}
    for t in trades:
        month_key = datetime.fromtimestamp(t["entry_time"] / 1000, tz=timezone.utc).strftime("%Y-%m")
        months[month_key] = months.get(month_key, 0.0) + t["net_pct"]
    worst_month = min(months.items(), key=lambda kv: kv[1]) if months else ("n/a", 0.0)

    print(
        f"{label}: n={len(trades)} win_rate={len(wins)/len(trades)*100:.1f}% "
        f"avg_net={total/len(trades)*100:.4f}% total_net={total*100:.3f}% "
        f"profit_factor={profit_factor:.2f} win/loss_ratio={win_loss_ratio:.2f} "
        f"trades/day={trades_per_day:.2f} time_in_market={time_in_market_pct:.2f}% "
        f"worst_month={worst_month[0]}({worst_month[1]*100:.2f}%)"
    )
    by_engine = {e: sum(1 for t in trades if t["engine"] == e) for e in ("trend", "range")}
    by_reason = {r: sum(1 for t in trades if t["outcome"] == r) for r in ("TP", "SL", "TIME")}
    print(f"  engines: {by_engine}  reasons: {by_reason}")
    return {
        "label": label, "n": len(trades), "avg_net": total / len(trades) * 100,
        "profit_factor": profit_factor, "win_loss_ratio": win_loss_ratio,
        "trades_per_day": trades_per_day,
    }


def report(trades: list[dict], candles: list[list]) -> None:
    total_days = (candles[-1][0] - candles[0][0]) / (24 * 60 * 60 * 1000)
    print(f"Backtest span: {total_days:.1f} days, {len(candles)} candles, {len(trades)} total trades.\n")

    overall = _split_report("OVERALL", trades, total_days)

    n = len(trades)
    if n >= 10:
        train_end, validate_end = int(n * 0.6), int(n * 0.8)
        print()
        _split_report("TRAIN (first 60%)", trades[:train_end], total_days * 0.6)
        _split_report("VALIDATE (next 20%)", trades[train_end:validate_end], total_days * 0.2)
        _split_report("HOLDOUT (last 20%)", trades[validate_end:], total_days * 0.2)

    years: dict[int, float] = {}
    for t in trades:
        year = datetime.fromtimestamp(t["entry_time"] / 1000, tz=timezone.utc).year
        years[year] = years.get(year, 0.0) + t["net_pct"]
    print(f"\nPer-year net%: {{{', '.join(f'{y}: {v*100:.2f}%' for y, v in sorted(years.items()))}}}")

    print("\nKill criteria (from the frozen spec):")
    reasons = []
    if overall["n"] == 0:
        reasons.append("no trades generated")
    else:
        if overall["profit_factor"] < 1.2:
            reasons.append(f"profit factor {overall['profit_factor']:.2f} < 1.2")
        if overall["win_loss_ratio"] < 2.0:
            reasons.append(f"win/loss ratio {overall['win_loss_ratio']:.2f} < 2.0")
        if overall["trades_per_day"] > 15:
            reasons.append(f"trades/day {overall['trades_per_day']:.2f} > 15 (overfit/fee-death risk)")
        positive_years = sum(1 for v in years.values() if v > 0)
        if len(years) > 1 and positive_years <= 1:
            reasons.append("all net profit comes from a single calendar year")
    if reasons:
        print("  FAIL: " + "; ".join(reasons))
    else:
        print("  PASS: clears every stated kill criterion")


def main() -> None:
    candles = get_klines(days_history=DAYS_HISTORY, cache_dir=CACHE_DIR)
    print(f"Received {len(candles)} {SYMBOL} 5m candles; round-trip cost={FEE_ROUND_TRIP*100:.2f}%.\n")
    trades = simulate(candles)
    report(trades, candles)


if __name__ == "__main__":
    main()
