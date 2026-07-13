import json

import numpy as np
import pandas as pd
import pytest

from scanner.conditions import TemplateResult
from scanner.patterns import CupResult
from scanner.report import build_report


def make_eval(symbol, failed=(), rs=90, cup=None):
    conditions = {f"c{i}": f"c{i}" not in failed for i in range(1, 10)}
    result = TemplateResult(
        conditions=conditions,
        metrics={
            "price": np.float64(42.5), "ma50": 40.0, "ma150": 38.0, "ma200": 36.0,
            "low_52w": 30.0, "high_52w": 45.0,
            "pct_above_low": 0.42, "pct_from_high": -0.05,
            "volume": 1_000_000.0, "vol_ema": 900_000.0, "avg_volume": 950_000.0,
            "ma200_trend_preferred": True, "rs_rating": rs,
        },
        all_pass=not failed,
        failed=list(failed),
    )
    return {
        "symbol": symbol,
        "name": f"{symbol} Inc",
        "result": result,
        "cup": cup,
        "spark": [np.float64(40.0), 41.0, 42.5],
    }


def sample_cup():
    return CupResult(
        state="forming", zone="mid_cheat", pivot=np.float64(43.9),
        confidence=0.85, depth=0.28, lip_price=45.0, low_price=32.4,
        lip_date=pd.Timestamp("2026-03-02"), low_date=pd.Timestamp("2026-05-04"),
        plateau_start=pd.Timestamp("2026-07-01"), plateau_end=pd.Timestamp("2026-07-10"),
    )


def test_matches_and_near_misses_split():
    evals = [
        make_eval("PASS"),
        make_eval("NEAR", failed=("c8",)),
        make_eval("FAR", failed=("c1", "c2", "c5")),
    ]
    report = build_report("2026-07-10", evals, previous=None)
    assert [m["symbol"] for m in report["matches"]] == ["PASS"]
    assert [m["symbol"] for m in report["near_misses"]] == ["NEAR"]
    assert report["near_misses"][0]["failed"] == ["c8"]
    assert all(m["symbol"] != "FAR" for m in report["near_misses"])


def test_new_and_dropped_vs_previous():
    previous = {"matches": [{"symbol": "OLD", "days_on_list": 3},
                            {"symbol": "STAY", "days_on_list": 2}]}
    evals = [make_eval("STAY"), make_eval("FRESH")]
    report = build_report("2026-07-10", evals, previous=previous)
    assert report["new"] == ["FRESH"]
    assert report["dropped"] == ["OLD"]


def test_days_on_list_increments():
    previous = {"matches": [{"symbol": "STAY", "days_on_list": 4}]}
    report = build_report("2026-07-10", [make_eval("STAY"), make_eval("FRESH")],
                          previous=previous)
    days = {m["symbol"]: m["days_on_list"] for m in report["matches"]}
    assert days["STAY"] == 5
    assert days["FRESH"] == 1


def test_matches_sorted_by_rs_desc():
    evals = [make_eval("LOWRS", rs=71), make_eval("HIGHRS", rs=98)]
    report = build_report("2026-07-10", evals, previous=None)
    assert [m["symbol"] for m in report["matches"]] == ["HIGHRS", "LOWRS"]


def test_cups_listed_even_when_template_fails():
    # A stock deep in a cup base legitimately fails c7 (far from 52w high):
    # it must still surface in the cups list, with its failure count visible.
    evals = [
        make_eval("BASE", failed=("c1", "c7"), cup=sample_cup()),
        make_eval("PASS", cup=sample_cup()),
        make_eval("NOCUP"),
    ]
    report = build_report("2026-07-10", evals, previous=None)
    cups = {c["symbol"] for c in report["cups"]}
    assert cups == {"BASE", "PASS"}
    base = next(c for c in report["cups"] if c["symbol"] == "BASE")
    assert base["failed"] == ["c1", "c7"]


def test_new_cups_flagged_vs_previous():
    previous = {"matches": [], "cups": [{"symbol": "KNOWN"}]}
    evals = [make_eval("KNOWN", failed=("c7",), cup=sample_cup()),
             make_eval("FRESH", failed=("c7",), cup=sample_cup())]
    report = build_report("2026-07-10", evals, previous=previous)
    flags = {c["symbol"]: c["cup_new"] for c in report["cups"]}
    assert flags == {"KNOWN": False, "FRESH": True}


def test_report_json_serializable_with_cup():
    evals = [make_eval("CUP", cup=sample_cup())]
    report = build_report("2026-07-10", evals, previous=None)
    dumped = json.dumps(report)  # raises on numpy/Timestamp leakage
    parsed = json.loads(dumped)
    cup = parsed["matches"][0]["cup"]
    assert cup["zone"] == "mid_cheat"
    assert cup["pivot"] == pytest.approx(43.9)
    assert cup["plateau_end"] == "2026-07-10"
