"""Nightly scan entrypoint.

Usage:
    python -m scanner.main [--limit N] [--out docs/data]

Needs ALPACA_KEY / ALPACA_SECRET in the environment. Writes
docs/data/latest.json (dashboard input) and docs/data/scan-<date>.json.
"""
import argparse
import datetime as dt
import json
import pathlib

from .config import DEFAULT
from .conditions import evaluate_template
from .data import fetch_daily_bars, quality_filter
from .emailer import notify
from .patterns import detect_cup
from .report import build_report
from .rs_rating import rs_ratings, weighted_return
from .universe import fetch_assets

SPARK_SESSIONS = 260
SPARK_STEP = 5  # ~weekly points keep latest.json small


def make_spark(bars):
    tail = bars.tail(SPARK_SESSIONS).iloc[::SPARK_STEP]
    return [[ts.isoformat()[:10], round(float(c), 2)]
            for ts, c in tail["close"].items()]


def run_scan(out_dir="docs/data", limit=None, cfg=DEFAULT):
    today = dt.date.today()
    start = (today - dt.timedelta(days=500)).isoformat()

    assets = fetch_assets()
    names = {a["symbol"]: a.get("name") or a["symbol"] for a in assets}
    symbols = sorted(names)
    if limit:
        symbols = symbols[:limit]
    print(f"universe: {len(symbols)} assets after filtering")

    bars = fetch_daily_bars(symbols, start=start, end=today.isoformat())
    kept = quality_filter(bars, cfg)
    print(f"quality filter: {len(kept)} symbols (price/volume floor)")

    ratings = rs_ratings({s: weighted_return(bars[s], cfg.rs_weights) for s in kept})

    evaluations = []
    for symbol in kept:
        result = evaluate_template(bars[symbol], ratings.get(symbol), cfg)
        if result is None:
            continue
        cup = detect_cup(bars[symbol], cfg)
        evaluations.append({
            "symbol": symbol,
            "name": names.get(symbol, symbol),
            "result": result,
            "cup": cup,
            "spark": make_spark(bars[symbol]),
        })

    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    latest_path = out / "latest.json"
    previous = None
    if latest_path.exists():
        previous = json.loads(latest_path.read_text(encoding="utf-8"))

    report = build_report(today.isoformat(), evaluations, previous, cfg)
    payload = json.dumps(report, separators=(",", ":"))
    latest_path.write_text(payload, encoding="utf-8")
    (out / f"scan-{today.isoformat()}.json").write_text(payload, encoding="utf-8")
    print(f"matches: {len(report['matches'])}  near misses: {len(report['near_misses'])}  "
          f"new: {report['new']}  dropped: {report['dropped']}")
    notify(report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None,
                        help="debug: scan only the first N symbols")
    parser.add_argument("--out", default="docs/data")
    args = parser.parse_args()
    run_scan(out_dir=args.out, limit=args.limit)
