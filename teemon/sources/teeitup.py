"""TeeItUp / Kenna booking system (Richter Park)."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from ..http import TIMEOUT, new_session
from ..models import CourseError, TeeTime

API = "https://phx-api-be-east-1b.kenna.io/v2/tee-times"


def fetch(course: dict, days: list[dt.date], credentials: dict | None = None) -> list[TeeTime]:
    session = new_session()
    session.headers["x-be-alias"] = course["alias"]
    results: list[TeeTime] = []

    for day in days:
        resp = session.get(
            API,
            params={"date": day.isoformat(), "facilityIds": course["facility_id"]},
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            raise CourseError(f"HTTP {resp.status_code} for {day}")
        for block in resp.json():
            for slot in block.get("teetimes", []):
                allowed: set[int] = set()
                holes = 18
                for rate in slot.get("rates", []):
                    allowed.update(int(p) for p in rate.get("allowedPlayers", []))
                    holes = int(rate.get("holes") or holes)
                if not allowed:
                    continue
                start = _to_local(slot["teetime"])
                results.append(
                    TeeTime(
                        course=course["name"],
                        start=start,
                        open_spots=max(allowed),
                        holes=holes,
                        booking_url=course["booking_url"],
                        allowed_players=frozenset(allowed),
                    )
                )
    return results


def _to_local(raw: str) -> dt.datetime:
    """TeeItUp reports UTC; the courses are all America/New_York."""
    utc = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return utc.astimezone(ZoneInfo("America/New_York")).replace(tzinfo=None)
