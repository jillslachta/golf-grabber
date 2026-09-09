from __future__ import annotations

import datetime as dt

from .models import TeeTime


def _parse(hhmm: str) -> dt.time:
    hour, minute = hhmm.split(":")
    return dt.time(int(hour), int(minute))


def match(slot: TeeTime, windows: list[dict]) -> dict | None:
    """Return the highest-priority window a slot satisfies, if any."""
    hits = []
    for window in windows:
        if slot.start.weekday() not in window["weekdays"]:
            continue
        if not _parse(window["start"]) <= slot.start.time() <= _parse(window["end"]):
            continue
        players = sorted(p for p in window["players"] if slot.fits(p))
        if not players:
            continue
        hits.append((window["priority"], window, players))
    if not hits:
        return None
    priority, window, players = min(hits, key=lambda h: h[0])
    return {"window": window["name"], "priority": priority, "players": players}


def matching_slots(slots: list[TeeTime], windows: list[dict]) -> list[tuple[TeeTime, dict]]:
    matches = [(slot, hit) for slot in slots if (hit := match(slot, windows))]
    return sorted(matches, key=lambda m: (m[1]["priority"], m[0].start))
