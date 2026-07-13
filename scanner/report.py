"""Turn per-symbol evaluations into the JSON report the dashboard reads.

Matches pass all 9 conditions; near-misses fail at most
near_miss_max_failures. Diffing against the previous report yields the
new/dropped lists the email alert is built from.
"""
from .config import Config, DEFAULT


def _clean(value):
    """Coerce numpy scalars / pandas Timestamps into plain JSON types."""
    if hasattr(value, "item"):
        return value.item()
    if hasattr(value, "isoformat"):
        return value.isoformat()[:10]
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    return value


def _entry(evaluation):
    result = evaluation["result"]
    cup = evaluation["cup"]
    entry = {
        "symbol": evaluation["symbol"],
        "name": evaluation.get("name", evaluation["symbol"]),
        "conditions": result.conditions,
        "failed": result.failed,
        "metrics": _clean(result.metrics),
        "spark": _clean(list(evaluation.get("spark") or [])),
        "cup": _clean(vars(cup)) if cup is not None else None,
    }
    entry["rs"] = entry["metrics"].get("rs_rating")
    entry["price"] = entry["metrics"].get("price")
    return entry


def build_report(scan_date, evaluations, previous, cfg: Config = DEFAULT):
    matches, near_misses, cups = [], [], []
    for ev in evaluations:
        result = ev["result"]
        if result.all_pass:
            matches.append(_entry(ev))
        elif len(result.failed) <= cfg.near_miss_max_failures:
            near_misses.append(_entry(ev))
        # Cups get their own list regardless of template status: a stock deep
        # in a base legitimately fails c7 until the right side completes.
        if ev.get("cup") is not None:
            cups.append(_entry(ev))

    by_rs = lambda e: -(e["rs"] or 0)
    matches.sort(key=by_rs)
    near_misses.sort(key=by_rs)
    cups.sort(key=lambda e: -(e["cup"]["confidence"] or 0))

    prev_days = {}
    prev_cups = set()
    if previous:
        prev_days = {m["symbol"]: m.get("days_on_list", 1)
                     for m in previous.get("matches", [])}
        prev_cups = {c["symbol"] for c in previous.get("cups", [])}
    for m in matches:
        m["days_on_list"] = prev_days.get(m["symbol"], 0) + 1
        m["is_new"] = m["symbol"] not in prev_days
    for c in cups:
        c["cup_new"] = c["symbol"] not in prev_cups

    current_syms = {m["symbol"] for m in matches}
    return {
        "scan_date": scan_date,
        "matches": matches,
        "near_misses": near_misses,
        "cups": cups,
        "new": sorted(s for s in current_syms if s not in prev_days),
        "dropped": sorted(s for s in prev_days if s not in current_syms),
        "universe_size": len(evaluations),
    }
