"""Team schedules from ESPN's public feed. No search snippets or booking links."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import re
from typing import Literal
from zoneinfo import ZoneInfo

import requests
from event_records import EventRecord, EventSchedule

League = Literal["nfl", "nba", "wnba", "mlb", "nhl", "college-football"]
LEAGUES = {"nfl": "football", "nba": "basketball", "wnba": "basketball",
           "mlb": "baseball", "nhl": "hockey", "college-football": "football"}
PHASES = {"preseason": 1, "regular": 2, "postseason": 3}
CENTRAL = ZoneInfo("America/Chicago")


class TeamSelectionError(ValueError):
    """The supplied name does not identify exactly one directory entry."""


def normalize(value):
    return re.sub(r"[^a-z0-9]", "", value.lower())


def resolve_team(data, name):
    entries = data["sports"][0]["leagues"][0]["teams"]
    needle = normalize(name)
    matches = {}
    for entry in entries:
        team = entry["team"]
        aliases = [team.get(k, "") for k in
                   ("displayName", "shortDisplayName", "name", "nickname", "abbreviation", "location")]
        if needle and needle in [normalize(a) for a in aliases if a]:
            matches[str(team["id"])] = team
    if len(matches) == 1:
        return next(iter(matches.values()))
    if matches:
        options = ", ".join(t["displayName"] for t in matches.values())
        raise TeamSelectionError(f"Which team did you mean: {options}?")
    raise TeamSelectionError(f"I couldn't match '{name}' to this league's team directory. Please provide the full team name and league.")


def parse_schedule(data, *, league, team, year, phase):
    """Validate each fixture's identity/season; preserve doubleheaders by event ID."""
    if str(data["team"]["id"]) != str(team["id"]):
        raise ValueError("Wrong team returned")
    records = {}
    for event in data["events"]:
        if int(event["season"]["year"]) != year or int(event["seasonType"]["type"]) != phase:
            raise ValueError("Wrong season returned")
        competitions = event["competitions"]
        if len(competitions) != 1:
            raise ValueError("Unexpected competition format")
        game = competitions[0]
        competitors = game["competitors"]
        ours = [c for c in competitors if str(c["team"]["id"]) == str(team["id"])]
        others = [c for c in competitors if str(c["team"]["id"]) != str(team["id"])]
        if len(ours) != 1 or len(others) != 1:
            raise ValueError("Unexpected participants")
        instant = datetime.fromisoformat(game["date"].replace("Z", "+00:00"))
        if instant.tzinfo is None:
            raise ValueError("Missing source timezone")
        timed = game.get("timeValid", event.get("timeValid", False)) is True
        local = instant.astimezone(CENTRAL)
        venue = game.get("venue") or {}
        address = venue.get("address") or {}
        location = ", ".join(address[k] for k in ("city", "state", "country") if address.get(k))
        state = game.get("status", {}).get("type", {})
        status = state.get("description")
        if status in ("Scheduled", "Final", "In Progress"):
            status = None
        record = EventRecord(
            # Untimed source dates are calendar placeholders, not instants to shift.
            date=local.date() if timed else instant.date(), team=team["displayName"],
            opponent=others[0]["team"]["displayName"], location=location or "Location TBD",
            venue=venue.get("fullName"),
            home_away="Neutral" if game.get("neutralSite") else
                {"home": "Home", "away": "Away"}.get(ours[0].get("homeAway"), "Unconfirmed"),
            kickoff=local.strftime("%I:%M %p %Z").lstrip("0") if timed else None,
            status=status)
        identity = str(event["id"])
        if identity in records and records[identity] != record:
            raise ValueError("Conflicting duplicate event")
        records[identity] = record
    return records


def team_event_records(league: League, name: str, year: int, phase: str = "all"):
    if league not in LEAGUES or phase not in {"all", *PHASES} or not 1900 <= year <= 2100:
        raise ValueError("Unsupported schedule request")
    base = f"https://site.api.espn.com/apis/site/v2/sports/{LEAGUES[league]}/{league}"
    def get(path, params):
        response = requests.get(base + path, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    team = resolve_team(get("/teams", {"limit": 1000}), name)
    phases = list(PHASES.values()) if phase == "all" else [PHASES[phase]]
    def fetch(number):
        data = get(f"/teams/{team['id']}/schedule", {"season": year, "seasontype": number})
        return parse_schedule(data, league=league, team=team, year=year, phase=number)
    records = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        for part in pool.map(fetch, phases):
            if records.keys() & part.keys():
                raise ValueError("Event appears in multiple season phases")
            records.update(part)
    if not records:
        return None
    label = f"{year-1}–{str(year)[-2:]}" if league in {"nba", "nhl"} else str(year)
    label += " (all published phases)" if phase == "all" else f" ({phase} season)"
    return EventSchedule(season=year, season_label=label, team=team["displayName"],
        sport=LEAGUES[league], source_name="ESPN",
        source_url=base + f"/teams/{team['id']}/schedule?season={year}",
        time_note="Confirmed dates and times use America/Chicago (CST/CDT). Untimed dates remain as published.",
        events=list(records.values()))
