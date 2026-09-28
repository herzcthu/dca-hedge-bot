#!/usr/bin/env python3
"""Donchian indicators for Experiment D1."""

from __future__ import annotations

import pandas as pd


def add_donchian(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["high_20"] = out.high.shift(1).rolling(20, min_periods=20).max()
    out["low_10"] = out.low.shift(1).rolling(10, min_periods=10).min()
    out["channel_sane"] = out.high_20.ne(out.high)
    return out
