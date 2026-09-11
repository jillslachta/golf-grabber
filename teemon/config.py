"""Course definitions and alert preferences."""

from __future__ import annotations

from .sources import chelsea, foreup, golfnow, teeitup

TIMEZONE = "America/New_York"

# How many days ahead to look. Booking systems only publish times inside each
# course's own reservation window, so anything further out simply comes back
# empty.
LOOKAHEAD_DAYS = 10

# Ceiling on how many slots a single email lists, so the first run (or a mass
# cancellation) cannot produce an unreadable wall of tee times.
MAX_SLOTS_PER_EMAIL = 20

COURSES = [
    {
        "key": "oak_hills",
        "name": "Oak Hills Park (Norwalk)",
        "fetch": foreup.fetch,
        "course_id": 22739,
        "schedule_id": 11739,
        "booking_class": 50728,  # Public
        "member_booking_class": 50727,  # Membership pass holders
        "credentials_env": "OAK_HILLS",
    },
    {
        "key": "longshore",
        "name": "Longshore (Westport)",
        "fetch": foreup.fetch,
        "course_id": 23148,
        "schedule_id": 12897,
        "booking_class": 52697,  # Guests (Public)
        "member_booking_class": 52696,  # Adult pass holders
        "credentials_env": "LONGSHORE",
    },
    {
        "key": "tashua_knolls",
        "name": "Tashua Knolls (Trumbull)",
        "fetch": foreup.fetch,
        "course_id": 21017,
        "schedule_id": 6654,
        "booking_class": 14911,
    },
    {
        "key": "tashua_glen",
        "name": "Tashua Glen (Trumbull, 9 holes)",
        "fetch": foreup.fetch,
        "course_id": 21017,
        "schedule_id": 6463,
        "booking_class": 14910,
    },
    {
        "key": "h_smith_richardson",
        "name": "H. Smith Richardson (Fairfield)",
        "fetch": foreup.fetch,
        "course_id": 21120,
        "schedule_id": 6992,
        "booking_class": 8436,  # Non-Resident
        "member_booking_class": 8437,  # Resident ID & pass holders
        "credentials_env": "HSR",
    },
    {
        "key": "sterling_farms",
        "name": "Sterling Farms (Stamford)",
        "fetch": chelsea.fetch,
        "url": "https://sterling.chelseareservations.com/golf/bookingadmin.aspx",
        "course_value": "1",
        "player_counts": [2, 4],
        "credentials_env": "STERLING",
    },
    {
        "key": "richter_park",
        "name": "Richter Park (Danbury)",
        "fetch": teeitup.fetch,
        "alias": "richter-park-golf-course",
        "facility_id": 5789,
        "booking_url": "https://richter-park-golf-course.book.teeitup.com/",
    },
    {
        "key": "ridgefield",
        "name": "Ridgefield",
        "fetch": golfnow.fetch,
        "facility_id": 8922,
        "latitude": 41.3082,
        "longitude": -73.4954,
        "booking_url": "https://www.golfnow.com/tee-times/facility/8922-ridgefield-golf-course/search",
    },
]

# Priority 1: weekend mornings. Priority 2: weekday twilight.
WINDOWS = [
    {
        "name": "weekend morning",
        "weekdays": {5, 6},  # Saturday, Sunday
        "start": "06:00",
        "end": "10:00",
        "players": [2, 4],
        "priority": 1,
    },
    {
        "name": "weekday twilight",
        "weekdays": {0, 1, 2, 3, 4},
        "start": "16:00",
        "end": "19:00",
        "players": [2, 4],
        "priority": 2,
    },
]

# Latest start time a slot may have, by hole count. "any" applies every day; a
# weekday key (Sunday is 6) overrides it for that day.
CUTOFFS = {
    "any": {18: "15:00"},
    6: {18: "08:00", 9: "10:00"},
}
