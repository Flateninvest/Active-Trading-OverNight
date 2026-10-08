"""Published XNYS regular schedule, 2026--2028; no network or offset guessing.

Source verified 2026-10-07: https://www.nyse.com/trade/hours-calendars
Unexpected closures are not predicted. Update this calendar before further years.
"""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
LOCAL = ZoneInfo("Europe/Zurich")
UTC = timezone.utc
HOLIDAYS = {
    2026: "01-01 01-19 02-16 04-03 05-25 06-19 07-03 09-07 11-26 12-25",
    2027: "01-01 01-18 02-15 03-26 05-31 06-18 07-05 09-06 11-25 12-24",
    2028: "01-17 02-21 04-14 05-29 06-19 07-04 09-04 11-23 12-25",
}
EARLY_CLOSES = {"2026-11-27", "2026-12-24", "2027-11-26", "2028-07-03", "2028-11-24"}


def aware(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if not isinstance(dt, datetime) or dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("A timezone-aware timestamp is required")
    return dt.astimezone(UTC)


def supported(day):
    if day.year not in HOLIDAYS:
        raise ValueError("Calendar supports published 2026--2028 schedule only")


def is_session(day):
    supported(day)
    return day.weekday() < 5 and day.strftime("%m-%d") not in HOLIDAYS[day.year].split()


def session(day):
    if isinstance(day, str):
        day = date.fromisoformat(day)
    if not is_session(day):
        raise ValueError(f"{day} is not a regular exchange session")
    opening = datetime.combine(day, time(9, 30), NY).astimezone(UTC)
    closing = datetime.combine(day, time(13 if day.isoformat() in EARLY_CLOSES else 16), NY).astimezone(UTC)
    return opening, closing


def next_session(day):
    for offset in range(1, 10):
        candidate = day + timedelta(days=offset)
        if is_session(candidate):
            return candidate
    raise ValueError("No next exchange session in calendar horizon")


def entry_allowed(day):
    """Tue--Thu only, next calendar day must be an actual regular session.

    Thus Thanksgiving Wednesday, Christmas eve, weekend/holiday bridging fail.
    """
    return day.weekday() in (1, 2, 3) and is_session(day) and is_session(day + timedelta(days=1))


def schedule(day, config):
    opening, closing = session(day)
    nxt = next_session(date.fromisoformat(day) if isinstance(day, str) else day)
    next_open, _ = session(nxt)
    return {
        "session_date": (date.fromisoformat(day) if isinstance(day, str) else day).isoformat(),
        "open": opening.isoformat(), "close": closing.isoformat(),
        "decision_at": (closing - timedelta(minutes=config["decision_minutes_before_close"])).isoformat(),
        "entry_at": (closing - timedelta(minutes=config["entry_minutes_before_close"])).isoformat(),
        "regular_exit_at": next_open.isoformat(),
        "preopen_exit_at": (next_open - timedelta(minutes=config["preopen_minutes_before_open"])).isoformat(),
        "entry_allowed": entry_allowed(date.fromisoformat(day) if isinstance(day, str) else day),
        "local_timezone": "Europe/Zurich",
        "local": {"decision": (closing - timedelta(minutes=config["decision_minutes_before_close"])).astimezone(LOCAL).isoformat(),
                  "entry": (closing - timedelta(minutes=config["entry_minutes_before_close"])).astimezone(LOCAL).isoformat(),
                  "regular_exit": next_open.astimezone(LOCAL).isoformat(),
                  "preopen_exit": (next_open - timedelta(minutes=config["preopen_minutes_before_open"])).astimezone(LOCAL).isoformat()},
    }
