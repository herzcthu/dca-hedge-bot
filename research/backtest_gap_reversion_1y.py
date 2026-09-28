#!/usr/bin/env python3
"""Research-only one-year BTCUSDT/ETHUSDT gap-reversion backtest.

This repeats the retired strategy's actual 1-minute data, 15-minute anchor,
30-minute time-stop / 60-minute maximum-hold model and four-taker-fill cost.
It uses public data only; it does not load credentials, use Docker, or trade.
"""

from __future__ import annotations

import json
import os
import time

import requests

from backtest_gap_reversion import simulate, summarize

CACHE_DIR = "data/.btc_eth_gap_1y_1m_pages"
METADATA_PATH = CACHE_DIR + "/metadata.json"
DAYS_HISTORY = 365
SYMBOLS = ["BTCUSDT", "ETHUSDT"]
THRESHOLDS = [0.0014, 0.0020, 0.0030, 0.0040]


def load_metadata() -> dict:
    if os.path.exists(METADATA_PATH):
        with open(METADATA_PATH) as f:
            return json.load(f)
    end_ms = int(time.time() * 1000)
    metadata = {
        "end_ms": end_ms,
        "start_ms": end_ms - DAYS_HISTORY * 24 * 60 * 60 * 1000,
    }
    os.makedirs(CACHE_DIR, exist_ok=True)
    temporary_path = METADATA_PATH + ".tmp"
    with open(temporary_path, "w") as f:
        json.dump(metadata, f)
    os.replace(temporary_path, METADATA_PATH)
    return metadata


def load_symbol_pages(symbol: str) -> list[list]:
    path = f"{CACHE_DIR}/{symbol}.jsonl"
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


def save_page(symbol: str, batch: list) -> None:
    path = f"{CACHE_DIR}/{symbol}.jsonl"
    with open(path, "a") as f:
        json.dump(batch, f)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def load_klines() -> dict[str, list]:
    metadata = load_metadata()

    print(f"Fetching {DAYS_HISTORY} days of public 1m klines for {SYMBOLS}...")
    klines = {}
    for symbol in SYMBOLS:
        candles = load_symbol_pages(symbol)
        cursor = candles[-1][0] + 60_000 if candles else metadata["start_ms"]
        while cursor < metadata["end_ms"]:
            response = requests.get(
                "https://fapi.binance.com/fapi/v1/klines",
                params={"symbol": symbol, "interval": "1m", "startTime": cursor, "endTime": metadata["end_ms"], "limit": 1500},
                timeout=15,
            )
            response.raise_for_status()
            batch = response.json()
            if not batch:
                break
            candles.extend(batch)
            cursor = batch[-1][0] + 60_000
            save_page(symbol, batch)
            print(f"  {symbol}: {len(candles)} candles", flush=True)
            if len(batch) < 1500:
                break
            time.sleep(0.2)
        klines[symbol] = candles
    return klines


def main() -> None:
    klines = load_klines()
    for symbol in SYMBOLS:
        print(f"  {symbol}: {len(klines[symbol])} candles")

    closes = {symbol: {str(candle[0]): float(candle[4]) for candle in klines[symbol]} for symbol in SYMBOLS}
    common_times = sorted(set(closes["BTCUSDT"]) & set(closes["ETHUSDT"]), key=int)
    btc = [closes["BTCUSDT"][timestamp] for timestamp in common_times]
    eth = [closes["ETHUSDT"][timestamp] for timestamp in common_times]
    print(f"Common aligned candles: {len(common_times)}")
    print("Model: 15m anchor, 30m profitable time exit, 60m forced exit, 0.04% per fill / four fills.\n")

    for threshold in THRESHOLDS:
        summarize(f"BTCUSDT/ETHUSDT threshold={threshold * 100:.2f}%", simulate(btc, eth, threshold))


if __name__ == "__main__":
    main()