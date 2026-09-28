#!/usr/bin/env python3
"""Indicator calculations for the adaptive BTCUSDT scalp backtest."""

from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    previous_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - previous_close).abs(),
        (df["low"] - previous_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    up_move = df["high"].diff()
    down_move = -df["low"].diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index)
    tr_atr = atr(df, period) * period
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() * period / tr_atr
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() * period / tr_atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    return dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    change = series.diff()
    gain = change.clip(lower=0)
    loss = -change.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(100)


def bollinger(series: pd.Series, period: int = 20, width: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = series.rolling(period, min_periods=period).mean()
    std = series.rolling(period, min_periods=period).std(ddof=0)
    return mid, mid + width * std, mid - width * std


def session_vwap(df: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    session = df["open_time"].dt.floor("D")
    typical = (df["high"] + df["low"] + df["close"]) / 3
    volume = df["volume"].replace(0, np.nan)
    pv = typical * volume
    cum_pv = pv.groupby(session).cumsum()
    cum_vol = volume.groupby(session).cumsum()
    vwap = cum_pv / cum_vol
    diff = typical - vwap
    cum_var = ((diff ** 2) * volume).groupby(session).cumsum() / cum_vol
    sigma = np.sqrt(cum_var).fillna(0)
    return vwap, vwap + sigma, vwap - sigma


def add_indicators(df5: pd.DataFrame, df15: pd.DataFrame) -> pd.DataFrame:
    df = df5.copy()
    df["ema9"] = ema(df["close"], 9)
    df["ema21"] = ema(df["close"], 21)
    df["ema55"] = ema(df["close"], 55)
    df["atr14"] = atr(df, 14)
    df["adx14"] = adx(df, 14)
    df["rsi14"] = rsi(df["close"], 14)
    df["bb_mid"], df["bb_upper"], df["bb_lower"] = bollinger(df["close"], 20, 2.0)
    df["vwap"], df["vwap_upper_1s"], df["vwap_lower_1s"] = session_vwap(df)

    info = df15.copy()
    info["ema21_15m"] = ema(info["close"], 21)
    info["vwap_15m"], _, _ = session_vwap(info)
    info = info.rename(columns={"close": "close_15m", "close_time": "info_close_time"})
    info = info[["info_close_time", "close_15m", "ema21_15m", "vwap_15m"]].dropna()
    df = pd.merge_asof(
        df.sort_values("close_time"),
        info.sort_values("info_close_time"),
        left_on="close_time",
        right_on="info_close_time",
        direction="backward",
    )
    return df.reset_index(drop=True)
