"""Remembers which slots have already been alerted on, per delivery channel.

A slot key includes how many players fit, so a twosome that grows into a
foursome counts as new. Keys are dropped once the slot is no longer open, which
means a cancelled-then-reopened slot alerts again -- that is the point.

A channel other than email stores its keys under a prefix, so a text that never
arrived can be retried without re-emailing the inbox that already got it.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from .models import TeeTime

CHANNEL_SEPARATOR = "#"
DEFAULT_CHANNEL = "email"


def slot_key(course_key: str, slot: TeeTime, players: list[int]) -> str:
    sizes = ",".join(str(p) for p in sorted(players))
    return f"{course_key}|{slot.start:%Y-%m-%dT%H:%M}|{slot.holes}|{sizes}"


def _stored(key: str, channel: str) -> str:
    """Email keeps the bare key so state written before channels still counts."""
    return key if channel == DEFAULT_CHANNEL else f"{channel}{CHANNEL_SEPARATOR}{key}"


def _slot_part(stored_key: str) -> str:
    return stored_key.rpartition(CHANNEL_SEPARATOR)[2]


class AlertState:
    def __init__(self, path: Path):
        self.path = path
        raw = json.loads(path.read_text()) if path.exists() else {}
        self.seen: dict[str, str] = raw.get("seen", {})

    def is_new(self, key: str, channel: str = DEFAULT_CHANNEL) -> bool:
        return _stored(key, channel) not in self.seen

    def record(self, key: str, when: dt.datetime, channel: str = DEFAULT_CHANNEL) -> None:
        self.seen[_stored(key, channel)] = when.isoformat(timespec="seconds")

    def prune(self, live_keys: set[str], checked_courses: set[str], today: dt.date) -> None:
        """Forget slots that are gone, and anything in the past."""
        kept = {}
        for key, when in self.seen.items():
            slot = _slot_part(key)
            course_key, start = slot.split("|")[:2]
            if dt.datetime.fromisoformat(start).date() < today:
                continue
            if course_key in checked_courses and slot not in live_keys:
                continue
            kept[key] = when
        self.seen = kept

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"updated_at": dt.datetime.now().isoformat(timespec="seconds"), "seen": self.seen}
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
