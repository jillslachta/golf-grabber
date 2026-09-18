"""Email delivery: Resend if an API key is configured, otherwise SMTP.

Recipients on a carrier email-to-SMS gateway get their own cut-down plain-text
message, since a phone renders the entire body as one text.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
import smtplib
from email.message import EmailMessage
from email.utils import formataddr, getaddresses
from html import escape

from .http import TIMEOUT, new_session
from .models import TeeTime

log = logging.getLogger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"

# Resend only accepts a From address on a verified domain; this shared sandbox
# sender works with no domain setup, delivering to the account owner.
RESEND_DEFAULT_FROM = "Tee Time Monitor <onboarding@resend.dev>"

# Carrier email-to-SMS/MMS gateways: mail sent here is delivered as a text.
SMS_GATEWAYS = frozenset(
    {
        "txt.att.net",
        "mms.att.net",
        "vtext.com",
        "vzwpix.com",
        "tmomail.net",
        "messaging.sprintpcs.com",
        "msg.fi.google.com",
        "sms.myboostmobile.com",
        "mymetropcs.com",
        "email.uscc.net",
        "vmobl.com",
    }
)

# A text is a poor place for a long list; keep the message short enough that
# carriers do not split or truncate it mid-link.
SMS_MAX_SLOTS = 3


def setting(name: str, default: str | None = None) -> str | None:
    """Read a configuration env var, treating blank as unset and trimming it.

    GitHub Actions passes an unset secret through as an empty string, so a
    plain lookup would see configuration that is not really there.
    """
    return os.environ.get(name, "").strip() or default


def password(name: str) -> str | None:
    """Read an env var whose value may legitimately end in whitespace."""
    value = os.environ.get(name, "")
    return value if value.strip() else None


def subject_for(matches: list[tuple[TeeTime, dict]]) -> str:
    slot, hit = matches[0]
    lead = f"{slot.course} {slot.start:%a %-m/%-d %-I:%M %p} ({max(hit['players'])}p)"
    if len(matches) == 1:
        return f"Tee time open: {lead}"
    return f"Tee time open: {lead} +{len(matches) - 1} more"


def render(matches: list[tuple[TeeTime, dict]], omitted: int = 0) -> tuple[str, str]:
    lines = []
    rows = []
    for slot, hit in matches:
        players = " or ".join(f"{p}" for p in hit["players"])
        detail = f"{slot.holes} holes, {players} players"
        if slot.note:
            detail += f" - {slot.note}"
        lines.append(
            f"{slot.course}\n"
            f"  {slot.start:%A %B %-d} at {slot.start:%-I:%M %p} ({hit['window']})\n"
            f"  {detail}\n"
            f"  Book: {slot.booking_url}\n"
        )
        rows.append(
            "<tr>"
            f"<td><strong>{escape(slot.course)}</strong></td>"
            f"<td>{slot.start:%a %b %-d}</td>"
            f"<td>{slot.start:%-I:%M %p}</td>"
            f"<td>{escape(detail)}</td>"
            f'<td><a href="{escape(slot.booking_url)}">Book</a></td>'
            "</tr>"
        )

    footer = f"Checked at {dt.datetime.now():%-I:%M %p on %A %B %-d}."
    if omitted:
        footer = f"{omitted} further matching slot(s) not listed. {footer}"

    text = "\n".join(lines) + f"\n{footer}\n"
    html = (
        "<h2>Tee times just opened up</h2>"
        '<table cellpadding="6" cellspacing="0" border="1" '
        'style="border-collapse:collapse;font-family:sans-serif">'
        "<tr><th>Course</th><th>Date</th><th>Time</th><th>Details</th><th></th></tr>"
        + "".join(rows)
        + "</table>"
        f"<p style='color:#666;font-size:12px'>{escape(footer)}</p>"
    )
    return text, html


def render_sms(matches: list[tuple[TeeTime, dict]], omitted: int = 0) -> str:
    """One line and one link per slot, trimmed to what fits comfortably in a text."""
    shown = matches[:SMS_MAX_SLOTS]
    omitted += len(matches) - len(shown)

    lines = []
    for slot, hit in shown:
        players = "-".join(str(p) for p in hit["players"])
        lines.append(
            f"{slot.course.split(' (')[0]} {slot.start:%a %-m/%-d %-I:%M%p} "
            f"{slot.holes}h {players}p\n{slot.booking_url}"
        )
    if omitted:
        lines.append(f"+{omitted} more")
    return "\n".join(lines)


def send(matches: list[tuple[TeeTime, dict]], limit: int | None = None) -> None:
    omitted = 0
    if limit is not None and len(matches) > limit:
        omitted = len(matches) - limit
        matches = matches[:limit]

    recipients = _recipients()
    if not recipients:
        raise RuntimeError("ALERT_EMAIL_TO is not set, so there is nowhere to send alerts")
    subject = subject_for(matches)
    text, html = render(matches, omitted)

    inboxes = [r for r in recipients if not is_sms(r)]
    phones = [r for r in recipients if is_sms(r)]

    # Both groups are attempted, and one delivery counts as sent: the caller
    # records the slots only when send() returns, so raising after a partial
    # success would re-alert the group that already received the message.
    delivered, failures = [], []
    for group, group_subject, group_text, group_html in (
        (inboxes, subject, text, html),
        (phones, "Tee time open", render_sms(matches, omitted), None),
    ):
        if not group:
            continue
        try:
            _deliver(group, group_subject, group_text, group_html)
        except Exception as exc:
            failures.append(f"{', '.join(group)}: {exc}")
        else:
            delivered.extend(group)

    for failure in failures:
        log.error("alert delivery failed for %s", failure)
    if not delivered:
        raise RuntimeError("; ".join(failures))
    log.info("alerted %d matching slot(s) to %s", len(matches), ", ".join(delivered))


def _deliver(recipients: list[str], subject: str, text: str, html: str | None) -> None:
    api_key = setting("RESEND_API_KEY")
    if api_key:
        _send_resend(
            api_key,
            setting("ALERT_EMAIL_FROM", RESEND_DEFAULT_FROM),
            recipients,
            subject,
            text,
            html,
        )
    else:
        _send_smtp(setting("ALERT_EMAIL_FROM"), recipients, subject, text, html)


def is_sms(recipient: str) -> bool:
    _, address = getaddresses([recipient])[0]
    return address.rpartition("@")[2].lower() in SMS_GATEWAYS


def _recipients() -> list[str]:
    """Parse ALERT_EMAIL_TO, which may list several comma-separated addresses.

    Parsed as an RFC 5322 address list so a display name may itself contain a
    comma, as in '"Slachta, Jill" <jill@example.com>'.
    """
    parsed = getaddresses([setting("ALERT_EMAIL_TO", "")])
    return [formataddr((name, address)) for name, address in parsed if address]


def _send_resend(api_key, from_address, to_addresses, subject, text, html) -> None:
    session = new_session()
    payload = {
        "from": from_address,
        "to": to_addresses,
        "subject": subject,
        "text": text,
    }
    if html:
        payload["html"] = html
    resp = session.post(
        RESEND_ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
        timeout=TIMEOUT,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"Resend rejected the email: {resp.status_code} {resp.text}")


def _send_smtp(from_address, to_addresses, subject, text, html) -> None:
    username = setting("SMTP_USERNAME")
    secret = password("SMTP_PASSWORD")
    if not username or not secret:
        raise RuntimeError("Neither RESEND_API_KEY nor SMTP_USERNAME/SMTP_PASSWORD is configured")
    host = setting("SMTP_HOST", "smtp.gmail.com")
    port = int(setting("SMTP_PORT", "587"))

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_address or username
    message["To"] = ", ".join(to_addresses)
    message.set_content(text)
    if html:
        message.add_alternative(html, subtype="html")

    with smtplib.SMTP(host, port, timeout=TIMEOUT) as server:
        server.starttls()
        server.login(username, secret)
        server.send_message(message)
