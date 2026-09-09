"""foreUP booking system (Oak Hills, Longshore, Tashua Knolls, Tashua Glen)."""

from __future__ import annotations

import datetime as dt
import logging

from ..http import TIMEOUT, new_session
from ..models import CourseError, TeeTime

log = logging.getLogger(__name__)

API = "https://foreupsoftware.com/index.php/api/booking/times"
LOGIN = "https://foreupsoftware.com/index.php/api/booking/users/login"
BOOKING_PAGE = "https://foreupsoftware.com/index.php/booking/{course_id}/{schedule_id}#/teetimes"


def _login(session, course_id: int, booking_class: int, username: str, password: str) -> None:
    resp = session.post(
        LOGIN,
        data={
            "username": username,
            "password": password,
            "booking_class_id": booking_class,
            "course_id": course_id,
        },
        headers={"X-Requested-With": "XMLHttpRequest", "Api-Key": "no_limits"},
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        raise CourseError(f"foreUP login failed with HTTP {resp.status_code}")
    body = resp.json()
    if isinstance(body, dict) and body.get("success") is False:
        raise CourseError(f"foreUP login rejected: {body.get('msg', 'unknown reason')}")
    token = body.get("jwt") if isinstance(body, dict) else None
    if token:
        session.headers["X-Authorization"] = f"Bearer {token}"


def fetch(course: dict, days: list[dt.date], credentials: dict | None = None) -> list[TeeTime]:
    course_id = course["course_id"]
    schedule_id = course["schedule_id"]
    booking_class = course["booking_class"]
    session = new_session()

    if credentials:
        member_class = course.get("member_booking_class")
        if member_class is None:
            raise CourseError("credentials supplied but no member_booking_class configured")
        _login(session, course_id, member_class, credentials["username"], credentials["password"])
        booking_class = member_class

    results: list[TeeTime] = []
    for day in days:
        params = {
            "time": "all",
            "date": day.strftime("%m-%d-%Y"),
            "holes": "all",
            "players": "0",
            "booking_class": booking_class,
            "schedule_id": schedule_id,
            "specials_only": "0",
            "api_key": "no_limits",
        }
        resp = session.get(API, params=params, headers={"Api-Key": "no_limits"}, timeout=TIMEOUT)
        if resp.status_code != 200:
            raise CourseError(f"HTTP {resp.status_code} for {day}")
        payload = resp.json()
        if isinstance(payload, dict):
            # foreUP returns {"success": false, "msg": ...} for permission problems.
            raise CourseError(payload.get("msg", "unexpected response"))
        for slot in payload:
            start = dt.datetime.strptime(slot["time"], "%Y-%m-%d %H:%M")
            spots = int(slot.get("available_spots") or 0)
            if spots <= 0:
                continue
            results.append(
                TeeTime(
                    course=course["name"],
                    start=start,
                    open_spots=spots,
                    holes=int(slot.get("teesheet_holes") or 18),
                    booking_url=BOOKING_PAGE.format(course_id=course_id, schedule_id=schedule_id),
                    note=slot.get("schedule_name", ""),
                )
            )
    return results
