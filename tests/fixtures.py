"""Builders for synthetic daily-bar series used across tests.

Bars are pandas DataFrames with columns: open, high, low, close, volume,
one row per trading day, oldest first — the same shape scanner.data returns.
"""
import numpy as np
import pandas as pd


def make_bars(closes, volumes=None, opens=None, highs=None, lows=None):
    closes = np.asarray(closes, dtype=float)
    n = len(closes)
    if volumes is None:
        volumes = np.full(n, 1_000_000.0)
    if opens is None:
        opens = closes.copy()
    if highs is None:
        highs = closes * 1.01
    if lows is None:
        lows = closes * 0.99
    idx = pd.bdate_range(end="2026-07-10", periods=n)
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows,
         "close": closes, "volume": np.asarray(volumes, dtype=float)},
        index=idx,
    )


def uptrend_bars(n=340, start=10.0, daily=0.004):
    """Steady riser: passes every trend-template price/MA condition."""
    closes = start * (1 + daily) ** np.arange(n)
    return make_bars(closes)


def downtrend_bars(n=340, start=100.0, daily=0.004):
    """Steady faller: fails the MA stack conditions."""
    closes = start * (1 - daily) ** np.arange(n)
    return make_bars(closes)


def flat_bars(n=340, price=50.0):
    return make_bars(np.full(n, price))
