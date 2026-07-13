import numpy as np
import pytest

from scanner.config import Config
from scanner.patterns import detect_cup
from tests.fixtures import make_bars

CFG = Config()
BASE = 50.0
LOW = BASE * 0.70  # 30% deep cup


def cup_bars(zone_frac=0.55, plateau_vol_factor=0.6, triggered=False):
    """Flat base -> 30% decline -> rounded bottom -> recovery -> tight plateau.

    zone_frac places the plateau within the cup depth (0 = at the low,
    1 = back at the lip), so it lands in low cheat / mid cheat / cheat zones.
    """
    plateau_price = LOW + zone_frac * (BASE - LOW)
    pre = np.full(60, BASE)
    decline = np.linspace(BASE, LOW, 40)
    bottom = LOW * (1 + 0.02 * np.abs(np.sin(np.linspace(0, 3, 20))))
    recovery = np.linspace(LOW, plateau_price, 25)
    plateau = np.full(6, plateau_price)
    closes = np.concatenate([pre, decline, bottom, recovery, plateau])

    volumes = np.full(len(closes), 1_000_000.0)
    volumes[-6:] = 1_000_000.0 * plateau_vol_factor

    if triggered:
        closes = np.append(closes, plateau_price * 1.05)
        volumes = np.append(volumes, 2_000_000.0)

    return make_bars(closes, volumes=volumes)


def test_detects_clean_cup_forming_mid_cheat():
    res = detect_cup(cup_bars(zone_frac=0.55), cfg=CFG)
    assert res is not None
    assert res.state == "forming"
    assert res.zone == "mid_cheat"
    # pivot = plateau high (make_bars highs = close * 1.01)
    expected_pivot = (LOW + 0.55 * (BASE - LOW)) * 1.01
    assert res.pivot == pytest.approx(expected_pivot, rel=1e-3)
    assert 0 < res.confidence <= 1
    assert res.depth == pytest.approx(0.30, abs=0.02)


def test_low_cheat_zone():
    res = detect_cup(cup_bars(zone_frac=0.20), cfg=CFG)
    assert res is not None
    assert res.zone == "low_cheat"


def test_upper_zone_is_cheat():
    res = detect_cup(cup_bars(zone_frac=0.85), cfg=CFG)
    assert res is not None
    assert res.zone == "cheat"


def test_breakout_marks_triggered():
    res = detect_cup(cup_bars(zone_frac=0.55, triggered=True), cfg=CFG)
    assert res is not None
    assert res.state == "triggered"


def test_rejects_v_bottom():
    closes = np.concatenate([
        np.full(100, BASE),
        np.linspace(BASE, LOW, 3),      # crash in 3 sessions
        np.linspace(LOW, 44.0, 3),      # instant recovery
        np.full(6, 44.0),
    ])
    assert detect_cup(make_bars(closes), cfg=CFG) is None


def test_rejects_flat_drift():
    closes = BASE + np.sin(np.linspace(0, 12, 200)) * 0.5  # +-1% wiggle
    assert detect_cup(make_bars(closes), cfg=CFG) is None


def test_rejects_too_shallow():
    shallow_low = BASE * 0.92  # only an 8% correction
    closes = np.concatenate([
        np.full(60, BASE),
        np.linspace(BASE, shallow_low, 40),
        shallow_low * (1 + 0.02 * np.abs(np.sin(np.linspace(0, 3, 20)))),
        np.linspace(shallow_low, 48.0, 25),
        np.full(6, 48.0),
    ])
    assert detect_cup(make_bars(closes), cfg=CFG) is None


def test_detects_cup_after_long_prior_uptrend():
    # Real leaders rise into their bases: the window's lowest close is the
    # start of the uptrend, NOT the cup bottom. Detection must anchor on the
    # most recent major high, then the low after it.
    plateau_price = LOW + 0.55 * (BASE - LOW)
    closes = np.concatenate([
        np.linspace(BASE * 0.4, BASE, 150),      # long uptrend into the base
        np.linspace(BASE, LOW, 40),              # 30% correction
        LOW * (1 + 0.02 * np.abs(np.sin(np.linspace(0, 3, 20)))),
        np.linspace(LOW, plateau_price, 25),
        np.full(6, plateau_price),
    ])
    volumes = np.full(len(closes), 1_000_000.0)
    volumes[-6:] = 600_000.0
    res = detect_cup(make_bars(closes, volumes=volumes), cfg=CFG)
    assert res is not None
    assert res.zone == "mid_cheat"
    assert res.low_price == pytest.approx(LOW, rel=0.01)
    assert res.lip_price == pytest.approx(BASE, rel=0.01)


def test_volume_contraction_raises_confidence():
    contracted = detect_cup(cup_bars(plateau_vol_factor=0.6), cfg=CFG)
    expanded = detect_cup(cup_bars(plateau_vol_factor=1.3), cfg=CFG)
    assert contracted is not None and expanded is not None
    assert contracted.confidence > expanded.confidence
