"""IBD-style Relative Strength rating, approximated within our universe.

weighted_return: 40% x 3-month + 20% x 6/9/12-month price return.
rs_ratings: percentile rank (1-99) of those returns across all scanned symbols.
"""
import pandas as pd


def weighted_return(bars: pd.DataFrame, weights: dict):
    close = bars["close"].dropna()
    max_lookback = max(weights)
    if len(close) < max_lookback + 1:
        return None
    last = close.iloc[-1]
    return float(sum(
        w * (last / close.iloc[-1 - lb] - 1) for lb, w in weights.items()
    ))


def rs_ratings(returns: dict) -> dict:
    valid = {sym: r for sym, r in returns.items() if r is not None}
    if not valid:
        return {}
    if len(valid) == 1:
        return {sym: 99 for sym in valid}
    ranked = sorted(valid, key=valid.get)
    n = len(ranked)
    return {sym: int(round(1 + (i / (n - 1)) * 98)) for i, sym in enumerate(ranked)}
