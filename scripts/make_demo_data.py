"""Generate a realistic fixture docs/data/latest.json so the dashboard can be
built and reviewed while the market is closed / before Alpaca keys exist.

Run: python -m scripts.make_demo_data
"""
import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from scanner.config import DEFAULT
from scanner.conditions import evaluate_template
from scanner.patterns import detect_cup
from scanner.report import build_report
from tests.fixtures import make_bars

rng = np.random.default_rng(7)


def noisy(closes, pct=0.012):
    closes = np.asarray(closes, dtype=float)
    return closes * (1 + rng.normal(0, pct, len(closes)))


def trending_stock(start, daily, n=340, vol=2_000_000):
    closes = noisy(start * (1 + daily) ** np.arange(n))
    volumes = np.abs(rng.normal(vol, vol * 0.3, n))
    volumes[-1] = vol * 1.6  # active today -> passes the volume condition
    return make_bars(closes, volumes=volumes)


def cup_stock(base=60.0, zone_frac=0.55, triggered=False, vol=1_500_000):
    low = base * 0.78  # ~22% correction: deep enough to detect, shallow enough to stay near the template
    plateau_price = low + zone_frac * (base - low)
    closes = np.concatenate([
        noisy(np.linspace(base * 0.55, base, 170), 0.008),   # long prior uptrend
        noisy(np.linspace(base, low, 45), 0.008),            # correction
        noisy(low * (1 + 0.02 * np.abs(np.sin(np.linspace(0, 3, 25)))), 0.006),
        noisy(np.linspace(low, plateau_price, 30), 0.008),   # right side
        plateau_price * (1 + rng.normal(0, 0.004, 7)),       # tight pause
    ])
    volumes = np.abs(rng.normal(vol, vol * 0.25, len(closes)))
    volumes[-7:] *= 0.55
    if triggered:
        closes = np.append(closes, plateau_price * 1.06)
        volumes = np.append(volumes, vol * 2.2)
    return make_bars(closes, volumes=volumes)


STOCKS = {
    # strong clean trenders (template matches)
    "NVAX": ("Novavax Inc", trending_stock(22, 0.0045), 96),
    "AXON": ("Axon Enterprise Inc", trending_stock(180, 0.0035), 93),
    "CELH": ("Celsius Holdings Inc", trending_stock(45, 0.0040), 91),
    "APP":  ("AppLovin Corp", trending_stock(70, 0.0030), 88),
    "DUOL": ("Duolingo Inc", trending_stock(150, 0.0026), 84),
    "SMCI": ("Super Micro Computer Inc", trending_stock(300, 0.0024), 82),
    # cup setups
    "PLTR": ("Palantir Technologies", cup_stock(85, 0.58), 90),
    "HIMS": ("Hims & Hers Health", cup_stock(28, 0.22), 86),
    "RKLB": ("Rocket Lab USA", cup_stock(32, 0.86), 83),
    "CRDO": ("Credo Technology Group", cup_stock(55, 0.60, triggered=True), 89),
    # near misses
    "ONON": ("On Holding AG", trending_stock(38, 0.0035), 64),      # fails RS only
    "TMDX": ("TransMedics Group", trending_stock(95, 0.0028), 75),  # light volume today
    # clear fails (won't appear anywhere)
    "DECL": ("Declining Industries", trending_stock(90, -0.0035), 12),
    "FLAT": ("Flatline Corp", trending_stock(40, 0.0001), 35),
}

# Make TMDX fail only the volume condition
tmdx = STOCKS["TMDX"][1]
tmdx.iloc[-1, tmdx.columns.get_loc("volume")] = 150_000.0


def spark(bars):
    tail = bars.tail(260).iloc[::2]
    return [[ts.isoformat()[:10], round(float(c), 2)] for ts, c in tail["close"].items()]


evaluations = []
for symbol, (name, bars, rs) in STOCKS.items():
    result = evaluate_template(bars, rs, DEFAULT)
    if result is None:
        continue
    cup = detect_cup(bars, DEFAULT)
    evaluations.append({"symbol": symbol, "name": name, "result": result,
                        "cup": cup, "spark": spark(bars)})

previous = {"matches": [{"symbol": s, "days_on_list": d} for s, d in
            [("AXON", 11), ("CELH", 7), ("APP", 4), ("DUOL", 2), ("SMCI", 21),
             ("PLTR", 3), ("CRDO", 5), ("GONE", 9)]]}

report = build_report("2026-07-10", evaluations, previous, DEFAULT)
report["demo"] = True

out = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "latest.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=1), encoding="utf-8")

print(f"wrote {out}")
print(f"matches: {[m['symbol'] for m in report['matches']]}")
print(f"near misses: {[m['symbol'] for m in report['near_misses']]}")
print(f"cups: {[(c['symbol'], c['cup']['zone'], c['cup']['state']) for c in report['cups']]}")
print(f"new: {report['new']}  dropped: {report['dropped']}")
