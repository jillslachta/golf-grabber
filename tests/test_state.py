import datetime as dt

from teemon.models import TeeTime
from teemon.state import AlertState, slot_key


def make_slot(when="2026-09-12T08:00", spots=4):
    return TeeTime(
        course="Oak Hills Park (Norwalk)",
        start=dt.datetime.fromisoformat(when),
        open_spots=spots,
        holes=18,
        booking_url="https://example.com",
    )


def test_slot_key_distinguishes_party_size():
    slot = make_slot()
    assert slot_key("oak_hills", slot, [2]) != slot_key("oak_hills", slot, [2, 4])


def test_new_slot_alerts_once(tmp_path):
    path = tmp_path / "alerted.json"
    key = slot_key("oak_hills", make_slot(), [2, 4])

    state = AlertState(path)
    assert state.is_new(key)
    state.record(key, dt.datetime(2026, 9, 9, 7, 0))
    state.save()

    assert not AlertState(path).is_new(key)


def test_slot_that_disappears_alerts_again(tmp_path):
    path = tmp_path / "alerted.json"
    key = slot_key("oak_hills", make_slot(), [2, 4])
    state = AlertState(path)
    state.record(key, dt.datetime(2026, 9, 9, 7, 0))

    state.prune(live_keys=set(), checked_courses={"oak_hills"}, today=dt.date(2026, 9, 9))

    assert state.is_new(key)


def test_unchecked_course_keeps_its_history(tmp_path):
    """A course that errored out must not have its slots re-alerted next run."""
    path = tmp_path / "alerted.json"
    key = slot_key("sterling_farms", make_slot(), [2, 4])
    state = AlertState(path)
    state.record(key, dt.datetime(2026, 9, 9, 7, 0))

    state.prune(live_keys=set(), checked_courses={"oak_hills"}, today=dt.date(2026, 9, 9))

    assert not state.is_new(key)


def test_past_slots_are_forgotten(tmp_path):
    path = tmp_path / "alerted.json"
    key = slot_key("oak_hills", make_slot("2026-09-05T08:00"), [4])
    state = AlertState(path)
    state.record(key, dt.datetime(2026, 9, 4, 7, 0))

    state.prune(live_keys={key}, checked_courses={"oak_hills"}, today=dt.date(2026, 9, 9))

    assert state.seen == {}
