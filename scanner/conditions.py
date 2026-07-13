"""Minervini Trend Template conditions (1-8) plus the Chartink volume clause (9).

evaluate_template() is pure: daily bars + a precomputed RS rating in, a
TemplateResult out. RS is computed universe-wide in rs_rating.py.
"""
from dataclasses import dataclass

import pandas as pd

from .config import Config, DEFAULT

# 200-day MA plus a year of range data
MIN_HISTORY = 252


@dataclass
class TemplateResult:
    conditions: dict
    metrics: dict
    all_pass: bool
    failed: list


def moving_average(series: pd.Series, window: int, ma_type: str = "sma") -> pd.Series:
    if ma_type == "ema":
        return series.ewm(span=window, adjust=False).mean()
    return series.rolling(window).mean()


def _rising_throughout(ma: pd.Series, sessions: int) -> bool:
    diffs = ma.diff().tail(sessions)
    if len(diffs) < sessions or diffs.isna().any():
        return False
    return bool((diffs > 0).all())


def evaluate_template(bars: pd.DataFrame, rs_rating, cfg: Config = DEFAULT):
    bars = bars.dropna(subset=["close", "volume"])
    if len(bars) < MIN_HISTORY:
        return None

    close = bars["close"]
    price = float(close.iloc[-1])

    ma50 = moving_average(close, 50, cfg.ma_type)
    ma150 = moving_average(close, 150, cfg.ma_type)
    ma200 = moving_average(close, 200, cfg.ma_type)

    year = bars.tail(252)
    low_52w = float(year["low"].min())
    high_52w = float(year["high"].max())

    vol = bars["volume"]
    vol_ema = float(vol.ewm(span=cfg.volume_ema_days, adjust=False).mean().iloc[-1])
    volume_today = float(vol.iloc[-1])

    conditions = {
        "c1": price > ma150.iloc[-1] and price > ma200.iloc[-1],
        "c2": ma150.iloc[-1] > ma200.iloc[-1],
        "c3": _rising_throughout(ma200, cfg.ma200_trend_days),
        "c4": ma50.iloc[-1] > ma150.iloc[-1] and ma50.iloc[-1] > ma200.iloc[-1],
        "c5": price > ma50.iloc[-1],
        "c6": price >= low_52w * (1 + cfg.pct_above_52w_low),
        "c7": price >= high_52w * (1 - cfg.pct_from_52w_high),
        "c8": rs_rating is not None and rs_rating >= cfg.rs_min,
        "c9": (not cfg.volume_condition_enabled) or volume_today >= vol_ema,
    }
    conditions = {k: bool(v) for k, v in conditions.items()}
    failed = [k for k, v in conditions.items() if not v]

    metrics = {
        "price": price,
        "ma50": float(ma50.iloc[-1]),
        "ma150": float(ma150.iloc[-1]),
        "ma200": float(ma200.iloc[-1]),
        "low_52w": low_52w,
        "high_52w": high_52w,
        "pct_above_low": price / low_52w - 1,
        "pct_from_high": price / high_52w - 1,
        "volume": volume_today,
        "vol_ema": vol_ema,
        "avg_volume": float(vol.tail(cfg.avg_volume_days).mean()),
        "ma200_trend_preferred": _rising_throughout(ma200, cfg.ma200_trend_pref_days),
        "rs_rating": rs_rating,
    }

    return TemplateResult(
        conditions=conditions,
        metrics=metrics,
        all_pass=not failed,
        failed=failed,
    )
