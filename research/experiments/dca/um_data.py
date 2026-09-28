#!/usr/bin/env python3
"""Public Binance USD-M kline loader for DCA alt experiments."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

import pandas as pd
import requests

from experiments.dca.kline_cache import CACHE_MAX_AGE_SEC, cache_fresh, last_open_utc, memo_get, memo_put


BASE_URL = "https://fapi.binance.com"
START = datetime(2024, 1, 1, tzinfo=timezone.utc)
END_EXCLUSIVE = datetime(2027, 1, 1, tzinfo=timezone.utc)
CACHE_DIR = "data/dca_um"
INTERVAL_MS = {"1m": 60_000, "5m": 5 * 60_000, "15m": 15 * 60_000, "1h": 60 * 60_000}


def _cache_path(symbol: str, interval: str) -> str:
    return os.path.join(CACHE_DIR, f"{symbol}_{interval}.jsonl")


def _to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _load_jsonl(symbol: str, interval: str) -> list[list]:
    path = _cache_path(symbol, interval)
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


def _write_page(symbol: str, interval: str, batch: list[list]) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(_cache_path(symbol, interval), "a") as f:
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


def load_klines(symbol: str, interval: str = "1h") -> pd.DataFrame:
    if interval not in INTERVAL_MS:
        raise ValueError(f"unsupported interval: {interval}")
    hit = memo_get("um", symbol, interval)
    if hit is not None:
        return hit
    candles = _load_jsonl(symbol, interval)
    if cache_fresh(candles):
        last = last_open_utc(candles)
        print(
            f"cache {symbol} {interval}  n={len(candles)}  last={last}  "
            f"(age<{CACHE_MAX_AGE_SEC:g}s, skip fetch)",
            flush=True,
        )
    else:
        start_ms = _to_ms(START)
        end_ms = min(_to_ms(END_EXCLUSIVE), _to_ms(datetime.now(timezone.utc)))
        step_ms = INTERVAL_MS[interval]
        cursor = candles[-1][0] + step_ms if candles else start_ms
        print(
            f"Fetching {symbol} {interval} klines from {START.date()} to "
            f"{min(datetime.now(timezone.utc), END_EXCLUSIVE).date()}..."
        )
        try:
            while cursor < end_ms - step_ms:
                response = requests.get(
                    BASE_URL + "/fapi/v1/klines",
                    params={
                        "symbol": symbol, "interval": interval,
                        "startTime": cursor, "endTime": end_ms, "limit": 1500,
                    },
                    timeout=20,
                )
                response.raise_for_status()
                batch = response.json()
                if not batch:
                    break
                candles.extend(batch)
                _write_page(symbol, interval, batch)
                cursor = batch[-1][0] + step_ms
                print(f"  {interval}: {len(candles)} candles", flush=True)
                if len(batch) < 1500:
                    break
                time.sleep(0.15)
        except requests.RequestException as exc:
            print(f"  kline fetch failed ({exc}); using cache through last stored candle")
    if not candles:
        raise RuntimeError(f"no {symbol} klines in cache and fetch failed")
    return memo_put("um", symbol, interval, _frame(candles, interval))
