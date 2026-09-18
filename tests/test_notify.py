import datetime as dt

import pytest

from teemon import notify
from teemon.models import TeeTime
from teemon.notify import password, render, send, setting, subject_for


def match(course="Oak Hills Park (Norwalk)", when="2026-09-12T08:10", players=(2, 4)):
    slot = TeeTime(
        course=course,
        start=dt.datetime.fromisoformat(when),
        open_spots=max(players),
        holes=18,
        booking_url="https://example.com/book",
    )
    return slot, {"window": "weekend morning", "priority": 1, "players": list(players)}


def test_subject_names_the_first_slot():
    assert subject_for([match()]) == "Tee time open: Oak Hills Park (Norwalk) Sat 9/12 8:10 AM (4p)"


def test_subject_counts_the_rest():
    assert subject_for([match(), match(when="2026-09-12T08:20")]).endswith("+1 more")


def test_body_carries_course_time_and_link():
    text, html = render([match()])
    for body in (text, html):
        assert "Oak Hills Park (Norwalk)" in body
        assert "8:10 AM" in body
        assert "https://example.com/book" in body


def test_blank_secret_counts_as_unset(monkeypatch):
    """GitHub Actions supplies unset secrets as empty strings."""
    monkeypatch.setenv("SMTP_PORT", "")
    assert setting("SMTP_PORT", "587") == "587"


def test_password_keeps_its_whitespace(monkeypatch):
    monkeypatch.setenv("STERLING_PASSWORD", " hunter2 ")
    assert password("STERLING_PASSWORD") == " hunter2 "


def test_padded_setting_is_trimmed(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", " smtp.example.com ")
    assert setting("SMTP_HOST") == "smtp.example.com"


def test_alerts_go_to_every_listed_recipient(monkeypatch):
    monkeypatch.setenv("ALERT_EMAIL_TO", "golfer@example.com, caddie@example.com")
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    captured = {}
    monkeypatch.setattr(notify, "_send_resend", lambda *args, **kw: captured.update(to=args[2]))

    send([match()])

    assert captured["to"] == ["golfer@example.com", "caddie@example.com"]


def test_display_name_commas_do_not_split_a_recipient(monkeypatch):
    monkeypatch.setenv("ALERT_EMAIL_TO", '"Slachta, Jill" <golfer@example.com>, caddie@example.com')
    assert notify._recipients() == [
        '"Slachta, Jill" <golfer@example.com>',
        "caddie@example.com",
    ]


def test_blank_credentials_do_not_fall_through_to_smtp(monkeypatch):
    monkeypatch.setenv("ALERT_EMAIL_TO", "golfer@example.com")
    for name in ("RESEND_API_KEY", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD"):
        monkeypatch.setenv(name, "")

    with pytest.raises(RuntimeError, match="RESEND_API_KEY"):
        send([match()])


def test_carrier_gateway_recipients_get_their_own_short_text(monkeypatch):
    monkeypatch.setenv("ALERT_EMAIL_TO", "golfer@example.com, 6175550123@mms.att.net")
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    calls = []
    monkeypatch.setattr(
        notify,
        "_send_resend",
        lambda key, sender, to, subject, text, html: calls.append((to, text, html)),
    )

    send([match()])

    (inbox_to, inbox_text, inbox_html), (phone_to, phone_text, phone_html) = calls
    assert inbox_to == ["golfer@example.com"] and inbox_html
    assert phone_to == ["6175550123@mms.att.net"]
    assert phone_html is None
    assert len(phone_text) < len(inbox_text)
    assert "https://example.com/book" in phone_text


def test_channels_split_inboxes_from_gateways(monkeypatch):
    monkeypatch.setenv("ALERT_EMAIL_TO", "golfer@example.com, 6175550123@mms.att.net")
    assert notify.channels() == {
        notify.EMAIL: ["golfer@example.com"],
        notify.SMS: ["6175550123@mms.att.net"],
    }


def test_send_can_target_one_channel(monkeypatch):
    monkeypatch.setenv("ALERT_EMAIL_TO", "golfer@example.com, 6175550123@mms.att.net")
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    calls = []
    monkeypatch.setattr(
        notify,
        "_send_resend",
        lambda key, sender, to, subject, text, html: calls.append(to),
    )

    send([match()], channel=notify.SMS)

    assert calls == [["6175550123@mms.att.net"]]


def test_sms_body_lists_at_most_three_slots():
    matches = [match(when=f"2026-09-12T08:{minute:02d}") for minute in range(0, 50, 10)]
    text = notify.render_sms(matches)
    assert text.count("https://example.com/book") == notify.SMS_MAX_SLOTS
    assert text.endswith("+2 more")


def test_body_reports_omitted_slots():
    text, html = render([match()], omitted=7)
    assert "7 further matching slot(s) not listed" in text
    assert "7 further matching slot(s) not listed" in html
