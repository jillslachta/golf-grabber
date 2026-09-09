from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass, field


@dataclass(frozen=True)
class TeeTime:
    """A single bookable slot at a course, as advertised by its booking system."""

    course: str
    start: dt.datetime
    open_spots: int
    holes: int
    booking_url: str
    note: str = ""
    allowed_players: frozenset[int] = field(default_factory=frozenset)

    @property
    def slot_id(self) -> str:
        raw = f"{self.course}|{self.start.isoformat()}|{self.holes}|{self.open_spots}"
        return hashlib.sha1(raw.encode()).hexdigest()[:16]

    def fits(self, players: int) -> bool:
        if self.allowed_players:
            return players in self.allowed_players
        return self.open_spots >= players


class CourseError(Exception):
    """Raised when a course's booking system cannot be read."""
