import numpy as np
import pytest

from scanner.config import Config
from scanner.rs_rating import weighted_return, rs_ratings
from tests.fixtures import make_bars


def test_weighted_return_known_values():
    closes = np.full(260, 100.0)
    closes[-253] = 40.0   # r252 = 120/40  - 1 = 2.0
    closes[-190] = 60.0   # r189 = 120/60  - 1 = 1.0
    closes[-127] = 80.0   # r126 = 120/80  - 1 = 0.5
    closes[-64] = 100.0   # r63  = 120/100 - 1 = 0.2
    closes[-1] = 120.0
    bars = make_bars(closes)
    # 0.4*0.2 + 0.2*0.5 + 0.2*1.0 + 0.2*2.0 = 0.78
    assert weighted_return(bars, Config().rs_weights) == pytest.approx(0.78)


def test_weighted_return_insufficient_history():
    bars = make_bars(np.full(100, 50.0))
    assert weighted_return(bars, Config().rs_weights) is None


def test_rs_ratings_percentiles():
    returns = {f"S{i}": float(i) for i in range(100)}  # S0 worst .. S99 best
    ratings = rs_ratings(returns)
    assert ratings["S99"] == 99
    assert ratings["S0"] == 1
    assert ratings["S50"] == 50
    assert all(1 <= r <= 99 for r in ratings.values())


def test_rs_ratings_excludes_none():
    ratings = rs_ratings({"A": 0.5, "B": None, "C": 1.0})
    assert "B" not in ratings
    assert ratings["C"] > ratings["A"]
