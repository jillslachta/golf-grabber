"""Chelsea Reservations booking system (Sterling Farms).

Chelsea is a classic ASP.NET WebForms app: every interaction is a postback that
carries __VIEWSTATE forward, so reading a tee sheet means replaying the same
click sequence a person would perform -- pick filters, click the day in the
calendar, then ask for times.
"""

from __future__ import annotations

import datetime as dt
import re

from ..http import TIMEOUT, new_session
from ..models import CourseError, TeeTime

HIDDEN = re.compile(r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"')
SLOT = re.compile(r">(\d{2}:\d{2} [ap]m)\s+Hole-(\d+)<")


def _hidden_fields(html: str) -> dict[str, str]:
    return dict(HIDDEN.findall(html))


def fetch(course: dict, days: list[dt.date], credentials: dict | None = None) -> list[TeeTime]:
    """Read the tee sheet, as a guest and -- when configured -- as the member.

    The two views do not nest: the member view carries early-release dates the
    guest view has not published yet, while the guest view can list dates the
    member's own booking limits hide. Reading both and merging keeps either
    from masking the other.
    """
    results = _fetch_as(course, days, None)
    if credentials:
        results += _fetch_as(course, days, credentials)
    return _dedupe(results)


def _fetch_as(course: dict, days: list[dt.date], credentials: dict | None) -> list[TeeTime]:
    url = course["url"]
    session = new_session()
    html = session.get(url, timeout=TIMEOUT).text

    if credentials:
        html = _login(session, url, html, credentials)

    results: list[TeeTime] = []
    for day in days:
        for players in course.get("player_counts", [2, 4]):
            results.extend(_fetch_day(session, url, course, html, day, players))
    return results


def _login(session, url: str, html: str, credentials: dict) -> str:
    form = _hidden_fields(html)
    form["btnLoginNow"] = "Login"
    html = session.post(url, data=form, timeout=TIMEOUT).text
    form = _hidden_fields(html)
    form.update(
        {
            "txtLogin": credentials["username"],
            "txtPassword": credentials["password"],
            "btnSubmitNow": "Login",
        }
    )
    html = session.post(url, data=form, timeout=TIMEOUT).text
    if "txtPassword" in html:
        raise CourseError("Chelsea login rejected")

    if 'name="btnAccept"' in html:
        # Members land on a booking-policy interstitial before the tee sheet.
        form = _hidden_fields(html) | {"btnAccept": "I Agree"}
        html = session.post(url, data=form, timeout=TIMEOUT).text

    if 'name="btnDisplay"' not in html:
        raise CourseError("Chelsea did not return the booking form after login")
    return html


def _fetch_day(session, url, course, html, day: dt.date, players: int) -> list[TeeTime]:
    filters = {
        "ddlCourse1": course["course_value"],
        "ddlTime": "05:00",
        "ddlQuantity": str(players),
        "ddlHoleSelection": "18",
        "ddlMonth": f"{day.month:02d}",
        "ddlYear": str(day.year),
    }

    form = _hidden_fields(html) | filters | {"btnDisplay": "Display"}
    page = session.post(url, data=form, timeout=TIMEOUT).text

    if f"__doPostBack('Day{day.day}'" not in page:
        # The course has not opened this date for booking yet.
        return []

    form = _hidden_fields(page) | filters | {"__EVENTTARGET": f"Day{day.day}"}
    page = session.post(url, data=form, timeout=TIMEOUT).text

    form = _hidden_fields(page) | filters | {"btnDisplayTimes": "Display Times"}
    page = session.post(url, data=form, timeout=TIMEOUT).text

    if "Tee Times for" not in page:
        return []
    if day.strftime("%B %d, %Y") not in page:
        raise CourseError(f"Chelsea returned a tee sheet for the wrong date ({day})")

    slots = []
    for raw_time, hole in SLOT.findall(page):
        start = dt.datetime.combine(day, dt.datetime.strptime(raw_time, "%I:%M %p").time())
        slots.append(
            TeeTime(
                course=course["name"],
                start=start,
                open_spots=players,
                holes=18,
                booking_url=url,
                note=f"starts on hole {int(hole)}" if int(hole) != 1 else "",
                allowed_players=frozenset({players}),
            )
        )
    return slots


def _dedupe(slots: list[TeeTime]) -> list[TeeTime]:
    """Collapse the per-player-count queries into one slot per start time."""
    merged: dict[dt.datetime, TeeTime] = {}
    for slot in slots:
        existing = merged.get(slot.start)
        if existing is None:
            merged[slot.start] = slot
            continue
        merged[slot.start] = TeeTime(
            course=slot.course,
            start=slot.start,
            open_spots=max(existing.open_spots, slot.open_spots),
            holes=slot.holes,
            booking_url=slot.booking_url,
            note=existing.note or slot.note,
            allowed_players=existing.allowed_players | slot.allowed_players,
        )
    return sorted(merged.values(), key=lambda s: s.start)
