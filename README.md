# golf-grabber

Watches the public tee sheets of eight Fairfield County, CT golf courses and emails
you when a slot you'd actually want opens up. It only ever reads — it never books,
changes, or cancels anything.

## What it watches

| Course | Booking system | Coverage |
| --- | --- | --- |
| Oak Hills Park (Norwalk) | foreUP | Full, member class when logged in |
| Longshore (Westport) | foreUP | Full |
| Tashua Knolls (Trumbull) | foreUP | Full |
| Tashua Glen (Trumbull, 9 holes) | foreUP | Full |
| H. Smith Richardson (Fairfield) | foreUP | Full, resident class when logged in |
| Sterling Farms (Stamford) | Chelsea Reservations | Full, guest + member views merged |
| Richter Park (Danbury) | TeeItUp | Full |
| Ridgefield | GolfNow | **Partial** — the course's own EZLinks site blocks automated reads, so only the times Ridgefield lists on GolfNow are visible |
| Griffith E. Harris (Greenwich) | WebTrac | **Not watched** — the booking host is behind Cloudflare bot protection and returns HTTP 403 to any script |

## What counts as a match

- Saturday/Sunday 6:00–10:00am (top priority)
- Monday–Friday 4:00–7:00pm (secondary)
- Room for 2 or 4 players

On top of the windows, `CUTOFFS` drops anything starting too late: 18 holes never
after 3:00pm on any day, and on Sunday 18 holes stop at 8:00am and 9 holes at
10:00am. The 3:00pm ceiling means the weekday twilight window only ever yields
9-hole times.

Edit `WINDOWS` and `CUTOFFS` in `teemon/config.py` to change any of that.

## Alerts

New matches are emailed with course, date, time, group sizes and a direct booking
link. Each slot is alerted once: `state/alerted.json` is committed back to the repo
after every run. If a slot disappears and later reopens, it alerts again.

## Schedule

`.github/workflows/tee-times.yml` runs on GitHub Actions:

- every 15 minutes through the golfing day, to catch cancellations
- every 5 minutes across the morning release window (Sterling 5:00, Tashua 5:30,
  Oak Hills 6:00, Longshore 6:30 Eastern), to catch new days as they drop

GitHub's scheduler can run a few minutes late when it is busy, so treat the burst
window as a good chance rather than a guarantee of being first.

## Configuration

Set these as repository secrets (Settings → Secrets and variables → Actions):

| Secret | Purpose |
| --- | --- |
| `ALERT_EMAIL_TO` | where alerts go (required); comma-separate for several recipients |
| `RESEND_API_KEY` | Resend API key (required unless using SMTP) |
| `ALERT_EMAIL_FROM` | optional; defaults to Resend's `onboarding@resend.dev` |
| `OAK_HILLS_USERNAME` / `OAK_HILLS_PASSWORD` | optional; unlocks the member booking class |
| `HSR_USERNAME` / `HSR_PASSWORD` | optional; unlocks the H. Smith Richardson resident class |
| `STERLING_USERNAME` / `STERLING_PASSWORD` | optional; unlocks the early-access tee sheet |
| `LONGSHORE_USERNAME` / `LONGSHORE_PASSWORD` | optional; pass-holder class |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USERNAME` / `SMTP_PASSWORD` | only if sending via SMTP instead of Resend |

Without credentials a course is still checked, just through its public view.

## Running it yourself

```bash
pip install -r requirements.txt
python -m teemon.cli --dry-run             # print matches, send nothing
python -m teemon.cli --courses oak_hills   # one course
pytest
```
