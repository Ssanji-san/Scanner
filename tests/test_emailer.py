from scanner.emailer import build_email, should_send


def report_fixture(new=("FRESH",), dropped=("GONE",), cups=()):
    return {
        "scan_date": "2026-07-10",
        "matches": [
            {"symbol": "FRESH", "name": "Fresh Co", "price": 12.34, "rs": 95,
             "is_new": True, "days_on_list": 1,
             "metrics": {"pct_from_high": -0.04}},
            {"symbol": "STAY", "name": "Stay Inc", "price": 55.0, "rs": 88,
             "is_new": False, "days_on_list": 7,
             "metrics": {"pct_from_high": -0.10}},
        ],
        "near_misses": [],
        "cups": list(cups),
        "new": list(new),
        "dropped": list(dropped),
        "universe_size": 3120,
    }


def cup_fixture(symbol="CUPY", state="forming", new=True):
    return {"symbol": symbol, "name": f"{symbol} Corp", "price": 18.5, "rs": 90,
            "cup_new": new, "failed": ["c7"],
            "cup": {"zone": "mid_cheat", "state": state, "pivot": 19.25,
                    "confidence": 0.8, "depth": 0.24}}


def test_sends_when_new_matches():
    assert should_send(report_fixture()) is True


def test_sends_when_new_cup_or_breakout():
    quiet = report_fixture(new=(), dropped=())
    assert should_send(quiet) is False
    with_new_cup = report_fixture(new=(), dropped=(), cups=(cup_fixture(),))
    assert should_send(with_new_cup) is True
    with_breakout = report_fixture(new=(), dropped=(),
                                   cups=(cup_fixture(state="triggered", new=False),))
    assert should_send(with_breakout) is True


def test_no_send_when_nothing_happened():
    quiet = report_fixture(new=(), dropped=(),
                           cups=(cup_fixture(new=False),))  # old forming cup only
    assert should_send(quiet) is False


def test_email_content():
    report = report_fixture(cups=(cup_fixture(), cup_fixture("BRKO", "triggered", new=False)))
    subject, body = build_email(report, dashboard_url="https://example.github.io/scan/")
    assert "1 new match" in subject
    assert "FRESH" in body and "Fresh Co" in body
    assert "GONE" in body                      # dropped section
    assert "CUPY" in body and "Mid Cheat" in body and "19.25" in body
    assert "BRKO" in body and "BREAKOUT" in body.upper()
    assert "https://example.github.io/scan/" in body
    assert "not financial advice" in body.lower()


def test_email_subject_counts():
    report = report_fixture(new=("A", "B", "C"))
    subject, _ = build_email(report, dashboard_url="x")
    assert "3 new matches" in subject
