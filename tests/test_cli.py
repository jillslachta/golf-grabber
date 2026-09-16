import datetime as dt

from teemon import cli, config
from teemon.models import TeeTime


def _slot(minute: int) -> TeeTime:
    return TeeTime(
        course="Oak Hills Park (Norwalk)",
        start=dt.datetime(2026, 9, 12, 11, minute),
        open_spots=4,
        holes=18,
        booking_url="https://example.com",
    )


def test_overflowing_matches_are_emailed_across_runs(tmp_path, monkeypatch):
    """Slots trimmed from an oversized email must still alert on a later run."""
    total = config.MAX_SLOTS_PER_EMAIL + 5
    slots = [_slot(i) for i in range(total)]
    sent: list[int] = []

    monkeypatch.setattr(cli, "STATE_PATH", tmp_path / "alerted.json")
    monkeypatch.setattr(cli.notify, "send", lambda matches, limit=None: sent.append(len(matches)))
    monkeypatch.setattr(
        config,
        "COURSES",
        [{"key": "oak_hills", "name": "Oak Hills Park (Norwalk)", "fetch": lambda *_: slots}],
    )
    monkeypatch.setattr(cli.dt, "datetime", _FixedDatetime)

    cli.main([])
    cli.main([])

    assert sent == [total, 5]


class _FixedDatetime(dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return dt.datetime(2026, 9, 9, 7, 0, tzinfo=tz)
