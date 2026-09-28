"""Backtest kline freshness. Skip Binance if the last cached bar is < 1 day old.

Set DCA_KLINE_CACHE_MAX_AGE_SEC=0 to always fetch the tail.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone

import pandas as pd


CACHE_MAX_AGE_SEC = float(os.environ.get("DCA_KLINE_CACHE_MAX_AGE_SEC", "86400"))

_frames: dict[tuple[str, str, str], pd.DataFrame] = {}


def last_open_ms(candles: list) -> int | None:
    if not candles:
        return None
    return int(candles[-1][0])


def cache_fresh(candles: list, max_age_sec: float | None = None) -> bool:
    age = CACHE_MAX_AGE_SEC if max_age_sec is None else float(max_age_sec)
    if age <= 0:
        return False
    last = last_open_ms(candles)
    if last is None:
        return False
    return (time.time() - last / 1000.0) <= age


def last_open_utc(candles: list) -> datetime | None:
    last = last_open_ms(candles)
    if last is None:
        return None
    return datetime.fromtimestamp(last / 1000.0, tz=timezone.utc)


def memo_get(venue: str, symbol: str, interval: str) -> pd.DataFrame | None:
    frame = _frames.get((venue, symbol, interval))
    if frame is None:
        return None
    return frame.copy()


def memo_put(venue: str, symbol: str, interval: str, df: pd.DataFrame) -> pd.DataFrame:
    _frames[(venue, symbol, interval)] = df
    return df.copy()
