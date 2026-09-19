"""Calendar context for Game Time, independent of the server's timezone."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

PLANNING_TIMEZONE = "America/Chicago"


def planning_now(instant: datetime | None = None) -> datetime:
    instant = instant or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("Clock inputs must be timezone-aware")
    return instant.astimezone(ZoneInfo(PLANNING_TIMEZONE))


def calendar_context(instant: datetime | None = None) -> str:
    local = planning_now(instant)
    return (f"Today is {local.date().isoformat()} in {PLANNING_TIMEZONE} "
            f"({local.tzname()}); local time is {local.strftime('%H:%M')}. "
            "Resolve today, tomorrow, this month and upcoming games using this local "
            "calendar date, not UTC or dates mentioned earlier in the conversation. "
            "Display event kickoff times in their verified venue timezone; do not "
            "assume every venue uses Central Time. ")
