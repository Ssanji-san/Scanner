"""Best-effort cup-base detection with Minervini-style early-entry zones.

Heuristic, not gospel: every detection carries a confidence score and the
dashboard draws the detected cup so a human can eyeball it. A cup is a
significant high (lip), a 12-50% correction with a rounded (not V) bottom,
a recovering right side, and a tight low-volume pause (plateau) whose high
is the pivot. The pause's position within the cup depth names the entry:
lower third = low cheat, middle third = mid cheat, upper third = cheat.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import Config, DEFAULT

PLATEAU_SEARCH_CAP = 15  # longest pause we look for, in sessions


@dataclass
class CupResult:
    state: str        # "forming" | "triggered"
    zone: str         # "low_cheat" | "mid_cheat" | "cheat"
    pivot: float
    confidence: float
    depth: float
    lip_price: float
    low_price: float
    lip_date: pd.Timestamp
    low_date: pd.Timestamp
    plateau_start: pd.Timestamp
    plateau_end: pd.Timestamp


def _find_plateau(bars: pd.DataFrame, cfg: Config):
    """Longest suffix (capped) whose high/low span stays within the max range."""
    n = len(bars)
    for length in range(min(PLATEAU_SEARCH_CAP, n), cfg.plateau_min_days - 1, -1):
        window = bars.iloc[n - length:]
        lo = float(window["low"].min())
        hi = float(window["high"].max())
        if lo > 0 and (hi - lo) / lo <= cfg.plateau_max_range:
            return window
    return None


def detect_cup(bars: pd.DataFrame, cfg: Config = DEFAULT):
    bars = bars.dropna(subset=["close", "volume"]).tail(cfg.cup_max_length)
    if len(bars) < cfg.cup_min_length:
        return None
    closes = bars["close"].to_numpy()

    # Anchor on the most recent major high (leaders rise into their bases, so
    # the window minimum is usually the start of the prior uptrend, not the
    # cup). Exclude the trailing pause/breakout region so it can't be the lip.
    search = closes[:-(PLATEAU_SEARCH_CAP + 5)]
    if len(search) < 2:
        return None
    lip_idx = int(len(search) - 1 - np.argmax(search[::-1]))  # last occurrence of max
    lip = closes[lip_idx]
    after = closes[lip_idx + 1:]
    if len(after) == 0:
        return None
    low_idx = lip_idx + 1 + int(np.argmin(after))
    low = closes[low_idx]
    if lip <= 0 or lip <= low:
        return None

    depth = (lip - low) / lip
    if not (cfg.cup_min_depth <= depth <= cfg.cup_max_depth):
        return None
    if len(bars) - lip_idx < cfg.cup_min_length:
        return None

    # Rounded bottom: enough sessions near the low, else it's a V
    # (counted within the cup only — the prior uptrend also has low closes)
    bottom_span = int((closes[lip_idx:] <= low * 1.05).sum())
    if bottom_span < cfg.cup_min_bottom_span:
        return None

    # Plateau: prefer a breakout reading (pause ended yesterday, price broke
    # its pivot today), else a still-forming pause including today.
    state, plateau = None, None
    prev_plateau = _find_plateau(bars.iloc[:-1], cfg)
    if prev_plateau is not None and closes[-1] > float(prev_plateau["high"].max()):
        state, plateau = "triggered", prev_plateau
    else:
        current = _find_plateau(bars, cfg)
        if current is not None:
            state, plateau = "forming", current
    if plateau is None:
        return None

    pivot = float(plateau["high"].max())
    plateau_mean = float(plateau["close"].mean())
    frac = np.clip((plateau_mean - low) / (lip - low), 0.0, 1.0)
    zone = "low_cheat" if frac < 1 / 3 else ("mid_cheat" if frac < 2 / 3 else "cheat")

    # Confidence: depth sanity, bottom roundness, cup symmetry, volume dry-up
    depth_score = float(np.clip(1 - abs(depth - 0.25) / 0.25, 0, 1))
    cup_len = len(bars) - lip_idx
    roundness = float(min(1.0, bottom_span / (0.15 * cup_len)))
    decline_len = max(low_idx - lip_idx, 1)
    recovery_len = max(len(bars) - 1 - low_idx, 1)
    ratio = decline_len / recovery_len
    symmetry = float(min(1.0, 2 * min(ratio, 1 / ratio)))
    cup_vol = float(bars["volume"].iloc[lip_idx:].mean())
    plateau_vol = float(plateau["volume"].mean())
    vol_ratio = plateau_vol / cup_vol if cup_vol > 0 else 1.0
    vol_score = 1.0 if vol_ratio <= cfg.plateau_volume_contraction else \
        float(max(0.0, 1 - (vol_ratio - cfg.plateau_volume_contraction)))
    confidence = round((depth_score + roundness + symmetry + vol_score) / 4, 3)

    return CupResult(
        state=state,
        zone=zone,
        pivot=pivot,
        confidence=confidence,
        depth=round(float(depth), 4),
        lip_price=float(lip),
        low_price=float(low),
        lip_date=bars.index[lip_idx],
        low_date=bars.index[low_idx],
        plateau_start=plateau.index[0],
        plateau_end=plateau.index[-1],
    )
