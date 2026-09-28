#!/usr/bin/env python3
"""Public Binance kline loader for HTF BTCUSDT experiments."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

import pandas as pd
import requests


BASE_URL = "https://fapi.binance.com"
SYMBOL = "BTCUSDT"
START = datetime(2024, 1, 1, tzinfo=timezone.utc)
END_EXCLUSIVE = datetime(2027, 1, 1, tzinfo=timezone.utc)
CACHE_DIR = "data/htf"
INTERVAL_MS = {"15m": 15 * 60_000, "1h": 60 * 60_000, "4h": 4 * 60 * 60_000}


def _cache_path(interval: str) -> str:
    return os.path.join(CACHE_DIR, f"{SYMBOL}_{interval}.jsonl")


def _to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _load_jsonl(interval: str) -> list[list]:
    path = _cache_path(interval)
    if not os.path.exists(path):
        return []
    rows: list[list] = []
    with open(path) as f:
        for line in f:
            try:
                rows.extend(json.loads(line))
            except json.JSONDecodeError:
                break
    return rows


def _write_page(interval: str, batch: list[list]) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(_cache_path(interval), "a") as f:
        json.dump(batch, f)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def _frame(candles: list[list], interval: str) -> pd.DataFrame:
    columns = [
        "open_time", "open", "high", "low", "close", "volume", "close_time",
        "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore",
    ]
    df = pd.DataFrame(candles, columns=columns)
    df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
    end = min(pd.Timestamp.now(tz="UTC"), pd.Timestamp(END_EXCLUSIVE)) - pd.Timedelta(milliseconds=INTERVAL_MS[interval])
    return (
        df[(df.open_time >= pd.Timestamp(START)) & (df.close_time <= end)]
        .drop_duplicates("open_time")
        .sort_values("open_time")
        .reset_index(drop=True)[["open_time", "close_time", "open", "high", "low", "close", "volume"]]
    )


def load_klines(interval: str) -> pd.DataFrame:
    if interval not in INTERVAL_MS:
        raise ValueError(f"unsupported interval: {interval}")
    candles = _load_jsonl(interval)
    start_ms = _to_ms(START)
    end_ms = min(_to_ms(END_EXCLUSIVE), _to_ms(datetime.now(timezone.utc)))
    step_ms = INTERVAL_MS[interval]
    cursor = candles[-1][0] + step_ms if candles else start_ms
    print(f"Fetching {SYMBOL} {interval} klines from {START.date()} to {min(datetime.now(timezone.utc), END_EXCLUSIVE).date()}...")
    try:
        while cursor < end_ms - step_ms:
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
            _write_page(interval, batch)
            cursor = batch[-1][0] + step_ms
            print(f"  {interval}: {len(candles)} candles", flush=True)
            if len(batch) < 1500:
                break
            time.sleep(0.15)
    except requests.RequestException as exc:
        print(f"  kline fetch failed ({exc}); using cache through last stored candle")
    return _frame(candles, interval)


def load_all() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return load_klines("15m"), load_klines("1h"), load_klines("4h")
