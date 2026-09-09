import datetime as dt

from teemon.config import WINDOWS
from teemon.filters import match, matching_slots
from teemon.models import TeeTime


def slot(when: str, spots: int = 4, allowed=None) -> TeeTime:
    return TeeTime(
        course="Test",
        start=dt.datetime.fromisoformat(when),
        open_spots=spots,
        holes=18,
        booking_url="https://example.com",
        allowed_players=frozenset(allowed or ()),
    )


def test_weekend_morning_matches():
    hit = match(slot("2026-09-12T08:00"), WINDOWS)
    assert hit["window"] == "weekend morning"
    assert hit["players"] == [2, 4]


def test_weekend_afternoon_is_ignored():
    assert match(slot("2026-09-12T14:00"), WINDOWS) is None


def test_weekday_morning_is_ignored():
    assert match(slot("2026-09-10T08:00"), WINDOWS) is None


def test_weekday_twilight_matches_at_lower_priority():
    hit = match(slot("2026-09-10T17:00"), WINDOWS)
    assert hit["window"] == "weekday twilight"
    assert hit["priority"] == 2


def test_single_open_spot_does_not_match():
    assert match(slot("2026-09-12T08:00", spots=1), WINDOWS) is None


def test_three_open_spots_only_offers_a_twosome():
    assert match(slot("2026-09-12T08:00", spots=3), WINDOWS)["players"] == [2]


def test_explicit_allowed_players_beats_spot_count():
    hit = match(slot("2026-09-12T08:00", spots=4, allowed=[1, 2]), WINDOWS)
    assert hit["players"] == [2]


def test_weekend_mornings_sort_ahead_of_twilight():
    twilight = slot("2026-09-10T17:00")
    weekend = slot("2026-09-13T09:00")
    ordered = matching_slots([twilight, weekend], WINDOWS)
    assert [s.start for s, _ in ordered] == [weekend.start, twilight.start]
