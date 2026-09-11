from __future__ import annotations

import datetime as dt

from .config import CUTOFFS
from .models import TeeTime


def _parse(hhmm: str) -> dt.time:
    hour, minute = hhmm.split(":")
    return dt.time(int(hour), int(minute))


def _too_late(slot: TeeTime, cutoffs: dict) -> bool:
    """True when the slot starts after the latest time allowed for its length."""
    by_holes = cutoffs.get(slot.start.weekday()) or cutoffs.get("any", {})
    latest = by_holes.get(slot.holes)
    if latest is None:
        latest = cutoffs.get("any", {}).get(slot.holes)
    return latest is not None and slot.start.time() > _parse(latest)


def match(slot: TeeTime, windows: list[dict], cutoffs: dict | None = None) -> dict | None:
    """Return the highest-priority window a slot satisfies, if any."""
    if _too_late(slot, cutoffs if cutoffs is not None else CUTOFFS):
        return None
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


def matching_slots(
    slots: list[TeeTime], windows: list[dict], cutoffs: dict | None = None
) -> list[tuple[TeeTime, dict]]:
    matches = [(slot, hit) for slot in slots if (hit := match(slot, windows, cutoffs))]
    return sorted(matches, key=lambda m: (m[1]["priority"], m[0].start))
