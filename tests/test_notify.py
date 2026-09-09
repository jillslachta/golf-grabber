import datetime as dt

from teemon.models import TeeTime
from teemon.notify import render, subject_for


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


def test_body_reports_omitted_slots():
    text, html = render([match()], omitted=7)
    assert "7 further matching slot(s) not listed" in text
    assert "7 further matching slot(s) not listed" in html
