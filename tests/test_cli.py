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

    def fake_send(matches, limit=None, channel=None):
        sent.append(len(matches))
        return min(len(matches), limit or len(matches))

    monkeypatch.setenv("ALERT_EMAIL_TO", "golfer@example.com")
    monkeypatch.setattr(cli, "STATE_PATH", tmp_path / "alerted.json")
    monkeypatch.setattr(cli.notify, "send", fake_send)
    monkeypatch.setattr(
        config,
        "COURSES",
        [{"key": "oak_hills", "name": "Oak Hills Park (Norwalk)", "fetch": lambda *_: slots}],
    )
    monkeypatch.setattr(cli.dt, "datetime", _FixedDatetime)

    cli.main([])
    cli.main([])

    assert sent == [total, 5]


def test_a_failed_text_is_retried_without_re_emailing(tmp_path, monkeypatch):
    """Each channel remembers what it delivered, so one failure cannot spill onto the other."""
    slots = [_slot(0)]
    sent: list[str] = []
    gateway_works = False

    def fake_send(matches, limit=None, channel=None):
        if channel == cli.notify.SMS and not gateway_works:
            raise RuntimeError("gateway rejected the message")
        sent.append(channel)
        return len(matches)

    monkeypatch.setenv("ALERT_EMAIL_TO", "golfer@example.com, 6175550123@mms.att.net")
    monkeypatch.setattr(cli, "STATE_PATH", tmp_path / "alerted.json")
    monkeypatch.setattr(cli.notify, "send", fake_send)
    monkeypatch.setattr(
        config,
        "COURSES",
        [{"key": "oak_hills", "name": "Oak Hills Park (Norwalk)", "fetch": lambda *_: slots}],
    )
    monkeypatch.setattr(cli.dt, "datetime", _FixedDatetime)

    assert cli.main([]) == 1
    assert sent == [cli.notify.EMAIL]

    gateway_works = True
    assert cli.main([]) == 0
    assert sent == [cli.notify.EMAIL, cli.notify.SMS]

    assert cli.main([]) == 0
    assert sent == [cli.notify.EMAIL, cli.notify.SMS]


def test_texts_only_record_the_slots_the_text_listed(tmp_path, monkeypatch):
    """A text lists three slots, so the rest must still be new next run."""
    slots = [_slot(i) for i in range(cli.notify.SMS_MAX_SLOTS + 2)]
    texted: list[int] = []

    def fake_send(matches, limit=None, channel=None):
        texted.append(len(matches))
        return min(len(matches), cli.notify.SMS_MAX_SLOTS)

    monkeypatch.setenv("ALERT_EMAIL_TO", "6175550123@mms.att.net")
    monkeypatch.setattr(cli, "STATE_PATH", tmp_path / "alerted.json")
    monkeypatch.setattr(cli.notify, "send", fake_send)
    monkeypatch.setattr(
        config,
        "COURSES",
        [{"key": "oak_hills", "name": "Oak Hills Park (Norwalk)", "fetch": lambda *_: slots}],
    )
    monkeypatch.setattr(cli.dt, "datetime", _FixedDatetime)

    cli.main([])
    cli.main([])

    assert texted == [cli.notify.SMS_MAX_SLOTS + 2, 2]


class _FixedDatetime(dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return dt.datetime(2026, 9, 9, 7, 0, tzinfo=tz)
