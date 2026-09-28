#!/usr/bin/env python3
"""Binance spot daily BTCUSDT loader for Experiment D1."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

import pandas as pd
import requests


BASE_URL = "https://api.binance.com"
SYMBOL = "BTCUSDT"
INTERVAL = "1d"
START = datetime(2017, 1, 1, tzinfo=timezone.utc)
END_EXCLUSIVE = datetime(2026, 9, 8, tzinfo=timezone.utc)
CACHE_DIR = "data/d1"
CACHE_PATH = os.path.join(CACHE_DIR, f"{SYMBOL}_{INTERVAL}_spot.jsonl")
DAY_MS = 24 * 60 * 60 * 1000


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _load_cached() -> list[list]:
    if not os.path.exists(CACHE_PATH):
        return []
    rows: list[list] = []
    with open(CACHE_PATH) as f:
        for line in f:
            try:
                rows.extend(json.loads(line))
            except json.JSONDecodeError:
                break
    return rows


def _save_batch(batch: list[list]) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_PATH, "a") as f:
        json.dump(batch, f)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def _frame(candles: list[list]) -> pd.DataFrame:
    columns = [
        "open_time", "open", "high", "low", "close", "volume", "close_time",
        "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore",
    ]
    df = pd.DataFrame(candles, columns=columns)
    df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
    df["open_time"] = pd.to_datetime(df.open_time, unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df.close_time, unit="ms", utc=True)
    cutoff = min(pd.Timestamp.now(tz="UTC"), pd.Timestamp(END_EXCLUSIVE)) - pd.Timedelta(days=1)
    return (
        df[(df.open_time >= pd.Timestamp(START)) & (df.close_time <= cutoff)]
        .drop_duplicates("open_time")
        .sort_values("open_time")
        .reset_index(drop=True)[["open_time", "close_time", "open", "high", "low", "close", "volume"]]
    )


def load_daily() -> pd.DataFrame:
    candles = _load_cached()
    end_ms = min(_ms(END_EXCLUSIVE), _ms(datetime.now(timezone.utc)))
    cursor = candles[-1][0] + DAY_MS if candles else _ms(START)
    print(f"Fetching Binance spot {SYMBOL} daily klines from {START.date()} to {END_EXCLUSIVE.date()}...")
    while cursor < end_ms - DAY_MS:
        response = requests.get(
            BASE_URL + "/api/v3/klines",
            params={"symbol": SYMBOL, "interval": INTERVAL, "startTime": cursor, "endTime": end_ms, "limit": 1000},
            timeout=20,
        )
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        candles.extend(batch)
        _save_batch(batch)
        cursor = batch[-1][0] + DAY_MS
        print(f"  daily: {len(candles)} candles", flush=True)
        if len(batch) < 1000:
            break
        time.sleep(0.15)
    return _frame(candles)
