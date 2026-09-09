import datetime as dt

import pytest

from teemon.models import TeeTime
from teemon.notify import render, send, setting, subject_for


def match(course="Oak Hills Park (Norwalk)", when="2026-09-12T08:10", players=(2, 4)):
    slot = TeeTime(
        course=course,
        start=dt.datetime.fromisoformat(when),
        open_spots=max(players),
        holes=18,
        booking_url="https://example.com/book",
    )
    return slot, {"window": "weekend morning", "priority": 1, "players": list(players)}


def test_subject_names_the_first_slot():
    assert subject_for([match()]) == "Tee time open: Oak Hills Park (Norwalk) Sat 9/12 8:10 AM (4p)"


def test_subject_counts_the_rest():
    assert subject_for([match(), match(when="2026-09-12T08:20")]).endswith("+1 more")


def test_body_carries_course_time_and_link():
    text, html = render([match()])
    for body in (text, html):
        assert "Oak Hills Park (Norwalk)" in body
        assert "8:10 AM" in body
        assert "https://example.com/book" in body


def test_blank_secret_counts_as_unset(monkeypatch):
    """GitHub Actions supplies unset secrets as empty strings."""
    monkeypatch.setenv("SMTP_PORT", "")
    assert setting("SMTP_PORT", "587") == "587"


def test_blank_credentials_do_not_fall_through_to_smtp(monkeypatch):
    monkeypatch.setenv("ALERT_EMAIL_TO", "golfer@example.com")
    for name in ("RESEND_API_KEY", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD"):
        monkeypatch.setenv(name, "")

    with pytest.raises(RuntimeError, match="RESEND_API_KEY"):
        send([match()])


def test_body_reports_omitted_slots():
    text, html = render([match()], omitted=7)
    assert "7 further matching slot(s) not listed" in text
    assert "7 further matching slot(s) not listed" in html
