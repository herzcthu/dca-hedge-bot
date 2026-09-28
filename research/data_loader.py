#!/usr/bin/env python3
"""Deterministic Binance public-kline loader for the adaptive scalp backtest."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

import pandas as pd
import requests

from config import BASE_URL, DATA_DIR, END_DATE_EXCLUSIVE, INTERVAL_15M, INTERVAL_5M, START_DATE, SYMBOL


INTERVAL_MS = {INTERVAL_5M: 5 * 60_000, INTERVAL_15M: 15 * 60_000}


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _start_ms() -> int:
    return _ms(datetime(START_DATE.year, START_DATE.month, START_DATE.day, tzinfo=timezone.utc))


def _end_ms() -> int:
    return _ms(datetime(END_DATE_EXCLUSIVE.year, END_DATE_EXCLUSIVE.month, END_DATE_EXCLUSIVE.day, tzinfo=timezone.utc))


def _cache_path(interval: str) -> str:
    return os.path.join(DATA_DIR, f"{SYMBOL}_{interval}.jsonl")


def _load_cached(interval: str) -> list[list]:
    path = _cache_path(interval)
    if not os.path.exists(path):
        return []
    candles: list[list] = []
    with open(path) as f:
        for line in f:
            try:
                candles.extend(json.loads(line))
            except json.JSONDecodeError:
                break
    return candles


def _save_batch(interval: str, batch: list[list]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(_cache_path(interval), "a") as f:
        json.dump(batch, f)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def download_klines(interval: str) -> pd.DataFrame:
    candles = _load_cached(interval)
    end_ms = min(_end_ms(), _ms(datetime.now(timezone.utc)))
    interval_ms = INTERVAL_MS[interval]
    cursor = candles[-1][0] + interval_ms if candles else _start_ms()
    print(f"Fetching {SYMBOL} {interval} public klines from {START_DATE.isoformat()} to {END_DATE_EXCLUSIVE.isoformat()} into {DATA_DIR}...")
    while cursor < end_ms - interval_ms:
        response = requests.get(
            BASE_URL + "/fapi/v1/klines",
            params={"symbol": SYMBOL, "interval": interval, "startTime": cursor, "endTime": end_ms, "limit": 1500},
            timeout=20,
        )
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        candles.extend(batch)
        _save_batch(interval, batch)
        cursor = batch[-1][0] + interval_ms
        print(f"  {interval}: {len(candles)} candles", flush=True)
        if len(batch) < 1500:
            break
        time.sleep(0.15)
    return klines_to_frame(candles, interval)


def klines_to_frame(candles: list[list], interval: str) -> pd.DataFrame:
    columns = [
        "open_time", "open", "high", "low", "close", "volume", "close_time",
        "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore",
    ]
    df = pd.DataFrame(candles, columns=columns)
    numeric_cols = ["open", "high", "low", "close", "volume"]
    df[numeric_cols] = df[numeric_cols].astype(float)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
    cutoff = min(pd.Timestamp.now(tz="UTC"), pd.Timestamp(END_DATE_EXCLUSIVE, tz="UTC")) - pd.Timedelta(milliseconds=INTERVAL_MS[interval])
    df = df[df["close_time"] <= cutoff].drop_duplicates("open_time").sort_values("open_time").reset_index(drop=True)
    return df[["open_time", "close_time", "open", "high", "low", "close", "volume"]]


def load_market_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    return download_klines(INTERVAL_5M), download_klines(INTERVAL_15M)
