#!/usr/bin/env python3
"""Shared resumable loader for public BTCUSDT 5-minute Binance Futures klines.

Used by all BTC-only 5m scalp backtests so the ~183-day, ~52k-candle history is
downloaded once and reused. Public data only; no credentials, no Docker, no orders.
"""

from __future__ import annotations

import json
import os
import time

import requests

BASE_URL = "https://fapi.binance.com"
SYMBOL = "BTCUSDT"
INTERVAL = "5m"
DAYS_HISTORY = 183
CACHE_DIR = "data/.btc_5m_pages"
METADATA_PATH = CACHE_DIR + "/metadata.json"


def load_metadata(metadata_path: str, days_history: int) -> dict:
    if os.path.exists(metadata_path):
        with open(metadata_path) as f:
            return json.load(f)
    end_ms = int(time.time() * 1000)
    metadata = {
        "end_ms": end_ms,
        "start_ms": end_ms - days_history * 24 * 60 * 60 * 1000,
    }
    os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
    temporary_path = metadata_path + ".tmp"
    with open(temporary_path, "w") as f:
        json.dump(metadata, f)
    os.replace(temporary_path, metadata_path)
    return metadata


def load_pages(cache_dir: str) -> list[list]:
    path = f"{cache_dir}/{SYMBOL}.jsonl"
    if not os.path.exists(path):
        return []
    candles = []
    with open(path) as f:
        for line in f:
            try:
                candles.extend(json.loads(line))
            except json.JSONDecodeError:
                break
    return candles


def save_page(cache_dir: str, batch: list) -> None:
    path = f"{cache_dir}/{SYMBOL}.jsonl"
    with open(path, "a") as f:
        json.dump(batch, f)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def get_klines(days_history: int = DAYS_HISTORY, cache_dir: str = CACHE_DIR) -> list[list]:
    """Fetch (and resume-cache) `days_history` days of public 5m BTCUSDT candles.

    Each distinct (days_history, cache_dir) pair gets its own cache so extending the
    lookback window never silently truncates or corrupts previously-verified data.
    """
    metadata_path = f"{cache_dir}/metadata.json"
    metadata = load_metadata(metadata_path, days_history)
    candles = load_pages(cache_dir)
    cursor = candles[-1][0] + 5 * 60_000 if candles else metadata["start_ms"]
    print(f"Fetching {days_history} days of public {SYMBOL} {INTERVAL} candles into {cache_dir}...")
    while cursor < metadata["end_ms"]:
        response = requests.get(
            BASE_URL + "/fapi/v1/klines",
            params={
                "symbol": SYMBOL,
                "interval": INTERVAL,
                "startTime": cursor,
                "endTime": metadata["end_ms"],
                "limit": 1500,
            },
            timeout=15,
        )
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        candles.extend(batch)
        cursor = batch[-1][0] + 5 * 60_000
        save_page(cache_dir, batch)
        print(f"  {SYMBOL}: {len(candles)} candles", flush=True)
        if len(batch) < 1500:
            break
        time.sleep(0.2)
    return candles
