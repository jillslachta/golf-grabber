"""Remembers which slots have already been alerted on.

A slot key includes how many players fit, so a twosome that grows into a
foursome counts as new. Keys are dropped once the slot is no longer open, which
means a cancelled-then-reopened slot alerts again -- that is the point.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from .models import TeeTime


def slot_key(course_key: str, slot: TeeTime, players: list[int]) -> str:
    return f"{course_key}|{slot.start:%Y-%m-%dT%H:%M}|{slot.holes}|{max(players)}"


class AlertState:
    def __init__(self, path: Path):
        self.path = path
        raw = json.loads(path.read_text()) if path.exists() else {}
        self.seen: dict[str, str] = raw.get("seen", {})

    def is_new(self, key: str) -> bool:
        return key not in self.seen

    def record(self, key: str, when: dt.datetime) -> None:
        self.seen[key] = when.isoformat(timespec="seconds")

    def prune(self, live_keys: set[str], checked_courses: set[str], today: dt.date) -> None:
        """Forget slots that are gone, and anything in the past."""
        kept = {}
        for key, when in self.seen.items():
            course_key, start = key.split("|")[0], key.split("|")[1]
            if dt.datetime.fromisoformat(start).date() < today:
                continue
            if course_key in checked_courses and key not in live_keys:
                continue
            kept[key] = when
        self.seen = kept

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"updated_at": dt.datetime.now().isoformat(timespec="seconds"), "seen": self.seen}
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
