import datetime as dt

from teemon import config
from teemon.sources import chelsea
from teemon.sources.chelsea import SLOT
from teemon.sources.golfnow import _players_from_rule
from teemon.sources.teeitup import _to_local

CHELSEA_FRAGMENT = (
    "<a id=\"Compare11164001\" href=\"javascript:__doPostBack('Compare11164001','')\">"
    "06:40 am  Hole-01</a>"
    "<a id=\"Compare11165001\" href=\"javascript:__doPostBack('Compare11165001','')\">"
    "07:50 am  Hole-10</a>"
)


def test_chelsea_slot_parsing():
    assert SLOT.findall(CHELSEA_FRAGMENT) == [("06:40 am", "01"), ("07:50 am", "10")]


def test_chelsea_requests_every_configured_party_size(monkeypatch):
    asked: list[int] = []
    monkeypatch.setattr(chelsea, "new_session", lambda: _StubSession())
    monkeypatch.setattr(
        chelsea,
        "_fetch_day",
        lambda session, url, course, html, day, players: asked.append(players) or [],
    )

    course = next(c for c in config.COURSES if c["key"] == "sterling_farms")
    chelsea.fetch(course, [dt.date(2026, 9, 12)])

    assert asked == course["player_counts"]


class _StubSession:
    def get(self, *_, **__):
        return _StubResponse()


class _StubResponse:
    text = ""


def test_golfnow_player_rules():
    assert _players_from_rule("OneTwo") == {1, 2}
    assert _players_from_rule("TwoThreeFour") == {2, 3, 4}
    assert _players_from_rule("Four") == {4}
    assert _players_from_rule("") == set()


def test_teeitup_times_convert_to_eastern():
    assert _to_local("2026-09-13T11:10:00.000Z") == dt.datetime(2026, 9, 13, 7, 10)
