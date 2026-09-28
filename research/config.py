#!/usr/bin/env python3
"""Configuration for the adaptive BTCUSDT 5m scalp research harness."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


SYMBOL = "BTCUSDT"
BASE_URL = "https://fapi.binance.com"
START_DATE = date(2024, 1, 1)
END_DATE_EXCLUSIVE = date(2026, 9, 7)
INTERVAL_5M = "5m"
INTERVAL_15M = "15m"
DATA_DIR = "data/adaptive_scalper"
RESULTS_DIR = "results"

TRAIN_START = date(2024, 1, 1)
TRAIN_END = date(2025, 6, 30)
VALIDATE_START = date(2025, 7, 1)
VALIDATE_END = date(2026, 2, 28)
HOLDOUT_START = date(2026, 3, 1)

START_EQUITY = 10_000.0
RISK_FRACTION = 0.0035
MAX_LEVERAGE = 5.0
DAILY_STOP_FRACTION = 0.02
LOSS_COOLDOWN_COUNT = 3
COOLDOWN_BARS = 9

ADX_TREND = 22.0
ADX_RANGE = 18.0
PULLBACK_TOLERANCE = 0.0005
TREND_STOP_ATR_MULT = 1.2
TREND_STOP_CAP = 0.0028
TREND_TP_ATR_MULT = 1.6
VWAP_SIGMA_MULT = 1.0
RANGE_RSI_LONG = 32.0
RANGE_RSI_SHORT = 68.0
RANGE_STOP_BUFFER = 0.0004
LIMIT_CANCEL_BARS = 2
MAX_HOLD_BARS = 12


@dataclass(frozen=True)
class CostModel:
    name: str
    open_fee: float
    open_slippage: float
    limit_fee: float
    limit_slippage: float
    exit_fee: float
    exit_slippage: float
    stop_fee: float
    stop_slippage: float


COST_A = CostModel(
    name="A_maker_maker",
    open_fee=0.0002,
    open_slippage=0.00005,
    limit_fee=0.0002,
    limit_slippage=0.0,
    exit_fee=0.0002,
    exit_slippage=0.00005,
    stop_fee=0.0002,
    stop_slippage=0.00005,
)

COST_B = CostModel(
    name="B_realistic_mix",
    open_fee=0.0005,
    open_slippage=0.0001,
    limit_fee=0.0002,
    limit_slippage=0.000025,
    exit_fee=0.0005,
    exit_slippage=0.0001,
    stop_fee=0.0005,
    stop_slippage=0.0001,
)

FUNDING_PLACEHOLDER = 0.0001
