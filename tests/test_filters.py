import datetime as dt

from teemon.config import WINDOWS
from teemon.filters import match, matching_slots
from teemon.models import TeeTime


def slot(when: str, spots: int = 4, allowed=None, holes: int = 18) -> TeeTime:
    return TeeTime(
        course="Test",
        start=dt.datetime.fromisoformat(when),
        open_spots=spots,
        holes=holes,
        booking_url="https://example.com",
        allowed_players=frozenset(allowed or ()),
    )


def test_sunday_morning_matches():
    hit = match(slot("2026-09-13T07:00"), WINDOWS)
    assert hit["window"] == "fri/sun morning"
    assert hit["players"] == [2, 3]


def test_friday_afternoon_is_ignored():
    assert match(slot("2026-09-11T14:00"), WINDOWS) is None


def test_monday_to_thursday_is_ignored():
    assert match(slot("2026-09-10T08:00"), WINDOWS) is None  # Thursday morning
    assert match(slot("2026-09-10T17:00", holes=9), WINDOWS) is None  # Thursday twilight


def test_friday_morning_matches():
    hit = match(slot("2026-09-11T08:00"), WINDOWS)
    assert hit["window"] == "fri/sun morning"


def test_friday_twilight_matches_at_lower_priority():
    hit = match(slot("2026-09-11T17:00", holes=9), WINDOWS)
    assert hit["window"] == "friday twilight"
    assert hit["priority"] == 2


def test_eighteen_holes_after_three_is_cut():
    # Friday twilight, inside the window but past the 18-hole ceiling.
    assert match(slot("2026-09-11T17:00"), WINDOWS) is None


def test_sunday_eighteen_holes_after_eight_is_cut():
    assert match(slot("2026-09-13T08:00"), WINDOWS)
    assert match(slot("2026-09-13T08:01"), WINDOWS) is None


def test_sunday_nine_holes_run_until_ten():
    assert match(slot("2026-09-13T09:30", holes=9), WINDOWS)
    assert match(slot("2026-09-13T10:01", holes=9), WINDOWS) is None


def test_saturday_runs_from_ten_to_three():
    assert match(slot("2026-09-12T09:59"), WINDOWS) is None
    assert match(slot("2026-09-12T10:00"), WINDOWS)["window"] == "saturday midday"
    assert match(slot("2026-09-12T14:30"), WINDOWS)
    assert match(slot("2026-09-12T15:01"), WINDOWS) is None


def test_single_open_spot_does_not_match():
    assert match(slot("2026-09-12T11:00", spots=1), WINDOWS) is None


def test_two_open_spots_only_offers_a_twosome():
    assert match(slot("2026-09-12T11:00", spots=2), WINDOWS)["players"] == [2]


def test_foursome_only_slot_does_not_match():
    assert match(slot("2026-09-12T11:00", spots=4, allowed=[4]), WINDOWS) is None


def test_explicit_allowed_players_beats_spot_count():
    hit = match(slot("2026-09-12T11:00", spots=4, allowed=[1, 2]), WINDOWS)
    assert hit["players"] == [2]


def test_prime_windows_sort_ahead_of_twilight():
    twilight = slot("2026-09-11T17:00", holes=9)
    saturday = slot("2026-09-12T11:00")
    ordered = matching_slots([twilight, saturday], WINDOWS)
    assert [s.start for s, _ in ordered] == [saturday.start, twilight.start]
