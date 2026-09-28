#!/usr/bin/env python3
"""Tiny synthetic unit test for the adaptive scalp regime gate."""

from __future__ import annotations

import pandas as pd

from strategy import range_allowed, trend_allowed


def test_regime_gate() -> None:
    rows = pd.DataFrame([
        {"adx14": 25.0, "ema9": 102.0, "ema21": 100.0},
        {"adx14": 25.0, "ema9": 98.0, "ema21": 100.0},
        {"adx14": 17.0, "ema9": 101.0, "ema21": 100.0},
        {"adx14": 20.0, "ema9": 101.0, "ema21": 100.0},
    ])
    assert trend_allowed(rows.iloc[0], 1)
    assert not trend_allowed(rows.iloc[0], -1)
    assert trend_allowed(rows.iloc[1], -1)
    assert range_allowed(rows.iloc[2])
    assert not range_allowed(rows.iloc[3])
    assert not trend_allowed(rows.iloc[3], 1)


if __name__ == "__main__":
    test_regime_gate()
    print("regime gate test passed")
