"""Email delivery: Resend if an API key is configured, otherwise SMTP."""

from __future__ import annotations

import datetime as dt
import logging
import os
import smtplib
from email.message import EmailMessage
from html import escape

from .http import TIMEOUT, new_session
from .models import TeeTime

log = logging.getLogger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"

# Resend only accepts a From address on a verified domain; this shared sandbox
# sender works with no domain setup, delivering to the account owner.
RESEND_DEFAULT_FROM = "Tee Time Monitor <onboarding@resend.dev>"


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


def send(matches: list[tuple[TeeTime, dict]], limit: int | None = None) -> None:
    omitted = 0
    if limit is not None and len(matches) > limit:
        omitted = len(matches) - limit
        matches = matches[:limit]

    to_address = os.environ["ALERT_EMAIL_TO"]
    subject = subject_for(matches)
    text, html = render(matches, omitted)

    api_key = os.environ.get("RESEND_API_KEY")
    if api_key:
        from_address = os.environ.get("ALERT_EMAIL_FROM", RESEND_DEFAULT_FROM)
        _send_resend(api_key, from_address, to_address, subject, text, html)
    else:
        from_address = os.environ.get("ALERT_EMAIL_FROM", to_address)
        _send_smtp(from_address, to_address, subject, text, html)
    log.info("emailed %d matching slot(s) to %s", len(matches), to_address)


def _send_resend(api_key, from_address, to_address, subject, text, html) -> None:
    session = new_session()
    resp = session.post(
        RESEND_ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "from": from_address,
            "to": [to_address],
            "subject": subject,
            "text": text,
            "html": html,
        },
        timeout=TIMEOUT,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"Resend rejected the email: {resp.status_code} {resp.text}")


def _send_smtp(from_address, to_address, subject, text, html) -> None:
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))
    username = os.environ["SMTP_USERNAME"]
    password = os.environ["SMTP_PASSWORD"]

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_address
    message["To"] = to_address
    message.set_content(text)
    message.add_alternative(html, subtype="html")

    with smtplib.SMTP(host, port, timeout=TIMEOUT) as server:
        server.starttls()
        server.login(username, password)
        server.send_message(message)
