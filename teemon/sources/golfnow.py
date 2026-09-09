"""GolfNow marketplace (Ridgefield).

Ridgefield's own booking site (EZLinks) sits behind bot protection, so the only
machine-readable view of its tee sheet is the subset the course lists on
GolfNow. Coverage is therefore partial.
"""

from __future__ import annotations

import datetime as dt

from ..http import TIMEOUT, new_session
from ..models import CourseError, TeeTime

API = "https://www.golfnow.com/api/tee-times/tee-time-results"
DETAIL = "https://www.golfnow.com{path}"

_PLAYER_WORDS = {"One": 1, "Two": 2, "Three": 3, "Four": 4}


def _players_from_rule(rule: str) -> set[int]:
    players: set[int] = set()
    word = ""
    for char in rule or "":
        if char.isupper() and word:
            players.add(_PLAYER_WORDS.get(word, 0))
            word = ""
        word += char
    if word:
        players.add(_PLAYER_WORDS.get(word, 0))
    return {p for p in players if p}


def fetch(course: dict, days: list[dt.date], credentials: dict | None = None) -> list[TeeTime]:
    session = new_session()
    facility_id = course["facility_id"]
    session.headers["Referer"] = course["booking_url"]
    results: list[TeeTime] = []

    for day in days:
        payload = {
            "Radius": 25,
            "Latitude": course["latitude"],
            "Longitude": course["longitude"],
            "PageSize": 500,
            "PageNumber": 0,
            "SearchType": 1,
            "SortBy": "Date",
            "SortDirection": 0,
            "FacilityId": facility_id,
            "Date": day.strftime("%b %d %Y"),
            "View": "Grouping",
        }
        resp = session.post(API, json=payload, timeout=TIMEOUT)
        if resp.status_code != 200:
            raise CourseError(f"HTTP {resp.status_code} for {day}")
        body = resp.json().get("ttResults", {})
        for slot in body.get("teeTimes", []):
            allowed = _players_from_rule(slot.get("playerRule", ""))
            if not allowed:
                continue
            start = dt.datetime.fromisoformat(slot["time"]["date"]).replace(tzinfo=None)
            detail = slot.get("detailUrl") or ""
            results.append(
                TeeTime(
                    course=course["name"],
                    start=start,
                    open_spots=max(allowed),
                    holes=int(slot.get("multipleHolesRate") or 18),
                    booking_url=DETAIL.format(path=detail) if detail else course["booking_url"],
                    note="GolfNow listing (partial view of tee sheet)",
                    allowed_players=frozenset(allowed),
                )
            )
    return results
