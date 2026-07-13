import numpy as np
import pytest

from scanner.config import Config
from scanner.conditions import moving_average, evaluate_template
from tests.fixtures import make_bars, uptrend_bars, downtrend_bars


CFG = Config()


def test_sma_basic():
    bars = make_bars([1, 2, 3, 4, 5])
    assert moving_average(bars["close"], 5, "sma").iloc[-1] == pytest.approx(3.0)


def test_ema_differs_from_sma_on_trending_series():
    bars = make_bars(np.linspace(10, 20, 50))
    sma = moving_average(bars["close"], 20, "sma").iloc[-1]
    ema = moving_average(bars["close"], 20, "ema").iloc[-1]
    assert ema > sma  # EMA weights recent (higher) closes more


def test_uptrend_passes_all_price_conditions():
    res = evaluate_template(uptrend_bars(), rs_rating=85, cfg=CFG)
    for key in ("c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8", "c9"):
        assert res.conditions[key], f"{key} should pass for steady uptrend"
    assert res.all_pass
    assert res.failed == []


def test_downtrend_fails_ma_stack():
    res = evaluate_template(downtrend_bars(), rs_rating=85, cfg=CFG)
    for key in ("c1", "c2", "c3", "c4", "c5", "c6", "c7"):
        assert not res.conditions[key], f"{key} should fail for steady downtrend"
    assert not res.all_pass


def test_condition6_threshold_exact():
    # Flat long history at 10 establishes MAs, low of 10 * 0.99 (make_bars lows).
    # Price ends 28% above the 52w low -> fail; 35% above -> pass.
    lowish = np.full(300, 10.0)
    just_below = np.concatenate([lowish, [10.0 * 0.99 * 1.28]])
    res = evaluate_template(make_bars(just_below), rs_rating=85, cfg=CFG)
    assert not res.conditions["c6"]

    above = np.concatenate([lowish, [10.0 * 0.99 * 1.35]])
    res = evaluate_template(make_bars(above), rs_rating=85, cfg=CFG)
    assert res.conditions["c6"]


def test_condition7_within_25pct_of_high():
    # Ran up to 100 then faded: high 101 (make_bars highs = close*1.01).
    run_up = np.linspace(50, 100, 260)
    faded_far = np.concatenate([run_up, np.full(30, 70.0)])   # 70 < 101*0.75
    res = evaluate_template(make_bars(faded_far), rs_rating=85, cfg=CFG)
    assert not res.conditions["c7"]

    faded_near = np.concatenate([run_up, np.full(30, 90.0)])  # 90 > 101*0.75
    res = evaluate_template(make_bars(faded_near), rs_rating=85, cfg=CFG)
    assert res.conditions["c7"]


def test_condition8_rs_threshold():
    bars = uptrend_bars()
    assert evaluate_template(bars, rs_rating=70, cfg=CFG).conditions["c8"]
    assert not evaluate_template(bars, rs_rating=69, cfg=CFG).conditions["c8"]
    assert not evaluate_template(bars, rs_rating=None, cfg=CFG).conditions["c8"]


def test_condition9_volume_vs_ema():
    n = 300
    closes = uptrend_bars(n)["close"].to_numpy()
    heavy = np.full(n, 500_000.0); heavy[-1] = 1_200_000.0
    res = evaluate_template(make_bars(closes, volumes=heavy), rs_rating=85, cfg=CFG)
    assert res.conditions["c9"]

    light = np.full(n, 500_000.0); light[-1] = 200_000.0
    res = evaluate_template(make_bars(closes, volumes=light), rs_rating=85, cfg=CFG)
    assert not res.conditions["c9"]


def test_condition9_disabled_always_passes():
    cfg = Config(volume_condition_enabled=False)
    n = 300
    closes = uptrend_bars(n)["close"].to_numpy()
    light = np.full(n, 500_000.0); light[-1] = 200_000.0
    res = evaluate_template(make_bars(closes, volumes=light), rs_rating=85, cfg=cfg)
    assert res.conditions["c9"]


def test_ma200_preferred_trend_flag():
    res = evaluate_template(uptrend_bars(), rs_rating=85, cfg=CFG)
    assert res.metrics["ma200_trend_preferred"] is True
    # 300 flat days then a 40-day pop: MA200 only recently started rising
    closes = np.concatenate([np.full(300, 20.0), np.linspace(20, 30, 40)])
    res = evaluate_template(make_bars(closes), rs_rating=85, cfg=CFG)
    assert res.metrics["ma200_trend_preferred"] is False


def test_insufficient_history_returns_none():
    assert evaluate_template(uptrend_bars(n=100), rs_rating=85, cfg=CFG) is None


def test_nan_rows_are_ignored():
    bars = uptrend_bars(300)
    bars.iloc[50, bars.columns.get_loc("close")] = np.nan
    res = evaluate_template(bars, rs_rating=85, cfg=CFG)
    assert res is not None and res.all_pass


def test_metrics_reported():
    res = evaluate_template(uptrend_bars(), rs_rating=85, cfg=CFG)
    m = res.metrics
    for key in ("price", "ma50", "ma150", "ma200", "low_52w", "high_52w",
                "pct_above_low", "pct_from_high", "volume", "avg_volume"):
        assert key in m, f"missing metric {key}"
    assert m["price"] > m["ma50"] > m["ma150"] > m["ma200"]
