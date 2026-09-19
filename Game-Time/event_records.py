"""Validated source records and deterministic schedule presentation."""
from datetime import date, datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class EventRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: date
    team: str = Field(min_length=1)
    opponent: str = Field(min_length=1)
    location: str = Field(min_length=1)
    venue: str | None = None
    home_away: Literal["Home", "Away", "Neutral", "Unconfirmed"]
    kickoff: str | None = None
    time_window: str | None = None
    status: str | None = None


class EventSchedule(BaseModel):
    season: int
    team: str
    sport: str = "football"
    season_label: str | None = None
    time_note: str = "Times are shown as published; timezone is not inferred."
    source_url: str
    source_name: str
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    events: list[EventRecord] = Field(min_length=1)


def render_schedule(schedule, *, start=None, end=None, scope="all", limit=None):
    events = sorted(schedule.events, key=lambda e: e.date)
    events = [e for e in events if (start is None or e.date >= start)
              and (end is None or e.date <= end)
              and (scope == "all" or e.home_away.lower() == scope)]
    if limit is not None:
        events = events[:limit]
    heading = f"{schedule.team} — {schedule.season_label or schedule.season} {schedule.sport} schedule"
    filters = []
    if scope != "all": filters.append(f"{scope} games")
    if start: filters.append(f"from {start.isoformat()}")
    if end: filters.append(f"through {end.isoformat()}")
    if limit: filters.append(f"up to {limit} games")
    if filters: heading += " (" + ", ".join(filters) + ")"
    if not events:
        return heading + "\n\nNo published games match these filters."
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ")
    rows = [heading, "", "| Date | Opponent | Home/Away | Location / venue | Time |",
            "|---|---|---|---|---|"]
    for event in events:
        time = event.kickoff or (f"TBD ({event.time_window} window)" if event.time_window else "TBD")
        if event.status:
            time += f" ({event.status})"
        place = event.location + (f" / {event.venue}" if event.venue else "")
        rows.append("| " + " | ".join(map(cell, [event.date.isoformat(), event.opponent,
                    event.home_away, place, time])) + " |")
    rows += ["", f"Source: {schedule.source_name}. {schedule.time_note} "
             "TBD means the exact start time is unconfirmed. Only published fixtures are included; schedules may change."]
    return "\n".join(rows)
