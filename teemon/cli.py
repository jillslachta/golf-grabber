from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config, filters, notify
from .models import CourseError, TeeTime
from .state import AlertState, slot_key

log = logging.getLogger("teemon")

STATE_PATH = Path(__file__).resolve().parent.parent / "state" / "alerted.json"


def credentials_for(course: dict) -> dict | None:
    prefix = course.get("credentials_env")
    if not prefix:
        return None
    username = notify.setting(f"{prefix}_USERNAME")
    password = notify.password(f"{prefix}_PASSWORD")
    if username and password:
        return {"username": username, "password": password}
    return None


def upcoming_days(today: dt.date, count: int) -> list[dt.date]:
    return [today + dt.timedelta(days=offset) for offset in range(count)]


def check_courses(
    courses: list[dict], days: list[dt.date]
) -> tuple[list[tuple[dict, TeeTime]], set[str], list[str]]:
    found: list[tuple[dict, TeeTime]] = []
    checked: set[str] = set()
    problems: list[str] = []

    for course in courses:
        try:
            slots = course["fetch"](course, days, credentials_for(course))
        except CourseError as exc:
            problems.append(f"{course['name']}: {exc}")
            log.warning("skipping %s: %s", course["name"], exc)
            continue
        except Exception as exc:  # noqa: BLE001 - one broken course must not stop the rest
            problems.append(f"{course['name']}: {exc}")
            log.warning("skipping %s: %s", course["name"], exc, exc_info=True)
            continue
        checked.add(course["key"])
        found.extend((course, slot) for slot in slots)
        log.info("%s: %d open slot(s)", course["name"], len(slots))

    return found, checked, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Monitor Fairfield County tee times")
    parser.add_argument("--courses", nargs="*", help="only check these course keys")
    parser.add_argument("--days", type=int, default=config.LOOKAHEAD_DAYS)
    parser.add_argument("--dry-run", action="store_true", help="print matches, send no email")
    parser.add_argument(
        "--no-state",
        action="store_true",
        help="ignore and do not write the already-alerted list",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    courses = config.COURSES
    if args.courses:
        courses = [c for c in courses if c["key"] in args.courses]
        if not courses:
            parser.error("no courses matched --courses")

    today = dt.datetime.now(ZoneInfo(config.TIMEZONE)).date()
    days = upcoming_days(today, args.days)

    found, checked, problems = check_courses(courses, days)

    live_keys: set[str] = set()
    candidates: list[tuple[str, TeeTime, dict]] = []
    for course, slot in found:
        hit = filters.match(slot, config.WINDOWS)
        if not hit:
            continue
        key = slot_key(course["key"], slot, hit["players"])
        live_keys.add(key)
        candidates.append((key, slot, hit))

    state = AlertState(STATE_PATH)
    candidates.sort(key=lambda c: (c[2]["priority"], c[1].start))

    channels = [notify.EMAIL]
    if candidates and not args.dry_run:
        channels = list(notify.channels())
    unseen_by_channel = {
        channel: [c for c in candidates if args.no_state or state.is_new(c[0], channel)]
        for channel in channels
    }
    # A slot counts as new while any configured channel still owes it.
    new_keys = {key for unseen in unseen_by_channel.values() for key, _, _ in unseen}
    new_matches = [c for c in candidates if c[0] in new_keys]

    for _, slot, hit in new_matches:
        log.info(
            "MATCH %s %s (%s players, %s)",
            slot.course,
            slot.start,
            "/".join(str(p) for p in hit["players"]),
            hit["window"],
        )

    undelivered: list[str] = []
    if not args.dry_run:
        # Each channel keeps its own alerted list, so a channel that fails is
        # retried on the next run without re-alerting the channels that worked.
        for channel, unseen in unseen_by_channel.items():
            if not unseen:
                continue
            try:
                listed = notify.send(
                    [(slot, hit) for _, slot, hit in unseen],
                    limit=config.MAX_SLOTS_PER_EMAIL,
                    channel=channel,
                )
            except Exception as exc:  # noqa: BLE001 - one channel must not stop the rest
                undelivered.append(f"{channel}: {exc}")
                log.error("could not alert over %s: %s", channel, exc)
                continue
            now = dt.datetime.now()
            # Only the slots the message actually listed count as alerted; the
            # rest stay unseen so the next run can send them.
            for key, _, _ in unseen[:listed]:
                state.record(key, now, channel)

    if not args.no_state and not args.dry_run:
        state.prune(live_keys, checked, today)
        state.save()

    if problems:
        log.warning("courses skipped this run: %s", "; ".join(problems))
    print(
        f"{len(found)} open slots, {len(candidates)} matching preferences, "
        f"{len(new_matches)} new, {len(problems)} course(s) skipped"
    )
    if undelivered:
        log.error("alerts not delivered: %s", "; ".join(undelivered))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
