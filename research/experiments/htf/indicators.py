#!/usr/bin/env python3
"""Indicators for HTF experiments."""

from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev = df.close.shift(1)
    tr = pd.concat([(df.high - df.low), (df.high - prev).abs(), (df.low - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    up = df.high.diff()
    down = -df.low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    tr_atr = atr(df, period)
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / tr_atr
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / tr_atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    return dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def session_vwap(df: pd.DataFrame) -> pd.Series:
    session = df.open_time.dt.floor("D")
    typical = (df.high + df.low + df.close) / 3
    pv = typical * df.volume
    return pv.groupby(session).cumsum() / df.volume.groupby(session).cumsum()


def add_core(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["ema9"] = ema(out.close, 9)
    out["ema21"] = ema(out.close, 21)
    out["ema55"] = ema(out.close, 55)
    out["atr14"] = atr(out, 14)
    out["adx14"] = adx(out, 14)
    out["vwap"] = session_vwap(out)
    return out


def align_bias(primary: pd.DataFrame, informative: pd.DataFrame, prefix: str) -> pd.DataFrame:
    info = informative.copy()
    info[f"{prefix}_ema21"] = ema(info.close, 21)
    info = info.rename(columns={"close": f"{prefix}_close", "close_time": f"{prefix}_close_time"})
    info = info[[f"{prefix}_close_time", f"{prefix}_close", f"{prefix}_ema21"]].dropna()
    return pd.merge_asof(
        primary.sort_values("close_time"),
        info.sort_values(f"{prefix}_close_time"),
        left_on="close_time",
        right_on=f"{prefix}_close_time",
        direction="backward",
    ).reset_index(drop=True)
