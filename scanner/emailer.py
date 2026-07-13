"""Alert email: sent when the scan finds something new, silent otherwise.

Something new = a stock newly passing all 9 conditions, a newly detected
cup setup, or a cup pivot breaking out today. Plain-text body, Gmail SMTP.
"""
import os
import smtplib
from email.message import EmailMessage

from .config import DEFAULT

ZONE_LABELS = {"low_cheat": "Low Cheat", "mid_cheat": "Mid Cheat", "cheat": "Cheat"}


def _confident(report):
    floor = DEFAULT.email_cup_min_confidence
    return [c for c in report.get("cups", []) if c["cup"]["confidence"] >= floor]


def _new_cups(report):
    return [c for c in _confident(report) if c.get("cup_new")]


def _breakouts(report):
    return [c for c in _confident(report) if c["cup"]["state"] == "triggered"]


def should_send(report) -> bool:
    return bool(report.get("new") or _new_cups(report) or _breakouts(report))


def build_email(report, dashboard_url):
    n_new = len(report["new"])
    parts = []
    if n_new:
        parts.append(f"{n_new} new match{'es' if n_new != 1 else ''}")
    breakouts = _breakouts(report)
    if breakouts:
        parts.append(f"{len(breakouts)} cup breakout{'s' if len(breakouts) != 1 else ''}")
    new_cups = [c for c in _new_cups(report) if c["cup"]["state"] != "triggered"]
    if new_cups:
        parts.append(f"{len(new_cups)} new cup setup{'s' if len(new_cups) != 1 else ''}")
    subject = f"Minervini scan {report['scan_date']}: " + (", ".join(parts) or "no changes")

    lines = [f"Scan of {report['universe_size']:,} stocks on {report['scan_date']}", ""]

    cap = DEFAULT.email_max_rows_per_section

    def capped(items):
        overflow = len(items) - cap
        return items[:cap], (f"  ... and {overflow} more on the dashboard"
                             if overflow > 0 else None)

    by_symbol = {m["symbol"]: m for m in report["matches"]}
    if report["new"]:
        shown, more = capped(report["new"])
        lines.append("NEW MATCHES (pass all 9 conditions):")
        for sym in shown:
            m = by_symbol.get(sym, {})
            pct_high = (m.get("metrics", {}).get("pct_from_high") or 0) * 100
            lines.append(f"  {sym:<6} {m.get('name', ''):<30} ${m.get('price', 0):<8.2f} "
                         f"RS {m.get('rs', '?'):<3} {pct_high:+.1f}% vs 52w high")
        if more:
            lines.append(more)
        lines.append("")

    if breakouts:
        shown, more = capped(breakouts)
        lines.append("CUP BREAKOUTS (pivot broken today):")
        for c in shown:
            lines.append(f"  {c['symbol']:<6} {ZONE_LABELS[c['cup']['zone']]:<10} "
                         f"pivot ${c['cup']['pivot']:.2f} "
                         f"confidence {round(c['cup']['confidence'] * 100)}%")
        if more:
            lines.append(more)
        lines.append("")

    if new_cups:
        shown, more = capped(new_cups)
        lines.append("NEW CUP SETUPS (forming, watch the pivot):")
        for c in shown:
            lines.append(f"  {c['symbol']:<6} {ZONE_LABELS[c['cup']['zone']]:<10} "
                         f"pivot ${c['cup']['pivot']:.2f} "
                         f"depth {round(c['cup']['depth'] * 100)}% "
                         f"confidence {round(c['cup']['confidence'] * 100)}%")
        if more:
            lines.append(more)
        lines.append("")

    if report["dropped"]:
        lines.append(f"Dropped from the list: {', '.join(report['dropped'])}")
        lines.append("")

    lines += [
        f"Full dashboard: {dashboard_url}",
        "",
        "Candidates, not buy signals. Cup detection is heuristic - always check "
        "the chart. Not financial advice.",
    ]
    return subject, "\n".join(lines)


def notify(report, dry_run=None):
    """Send the alert (or print it when creds are missing / dry_run)."""
    user = os.environ.get("GMAIL_USER", "")
    password = os.environ.get("GMAIL_APP_PASSWORD", "")
    to_addr = os.environ.get("ALERT_TO", user)
    dashboard = os.environ.get("DASHBOARD_URL", "(dashboard URL not configured)")

    if not should_send(report):
        print("email: nothing new, not sending")
        return False

    subject, body = build_email(report, dashboard)
    if dry_run or not (user and password):
        print(f"email (dry run) -> {to_addr or '?'}\nSubject: {subject}\n\n{body}")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(user, password)
        smtp.send_message(msg)
    print(f"email: sent to {to_addr}")
    return True
