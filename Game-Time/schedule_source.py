"""Read the official Aggies football season page, without search-snippet truncation."""
from html.parser import HTMLParser
import requests
import re
from datetime import datetime
from bs4 import BeautifulSoup
from event_records import EventRecord, EventSchedule


def parse_aggies_schedule(html: str, year: int) -> EventSchedule:
    soup = BeautifulSoup(html, "html.parser")
    if f"{year} Football Schedule" not in soup.get_text(" ", strip=True):
        raise ValueError("Requested season does not match source")
    rows = soup.select("tr.schedule-table-item")
    events = []
    for row in rows:
        def value(selector):
            node = row.select_one(selector)
            return node.get_text(" ", strip=True) if node else ""
        day = value(".schedule-event-time__day")
        opponent = value(".schedule-event-default__name:not(.schedule-event-default__name--current)")
        location = value(".schedule-table-item__location")
        if not day or not opponent or not location:
            raise ValueError("Incomplete official event row")
        event_date = datetime.strptime(f"{day} {year}", "%b %d %Y").date()
        clock = value(".schedule-event-time__label")
        exact = bool(re.fullmatch(r"\d{1,2}:\d{2}\s*(?:[AP]M|[ap]\.m\.)", clock))
        text = row.get_text(" ", strip=True)
        away = "Away" if re.search(r"Texas A&M\s+at\b", text) else (
            "Home" if "Kyle Field" in location else "Unconfirmed")
        city, _, venue = location.partition(" / ")
        events.append(EventRecord(date=event_date, team="Texas A&M Aggies", opponent=opponent,
            location=city, venue=venue or None, home_away=away, kickoff=clock if exact else None,
            time_window=clock if clock and not exact and clock.upper() != "TBD" else None))
    if len({(e.date, e.opponent) for e in events}) != len(events):
        raise ValueError("Duplicate official event rows")
    return EventSchedule(season=year, team="Texas A&M Aggies",
        source_url=f"https://12thman.com/sports/football/schedule/season/{year}",
        source_name="Texas A&M Athletics (12thman.com)", events=events)


def aggies_event_records(year: int) -> EventSchedule:
    response = requests.get(f"https://12thman.com/sports/football/schedule/season/{year}",
                            timeout=15, allow_redirects=False)
    response.raise_for_status()
    return parse_aggies_schedule(response.text, year)


class PageText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def aggies_schedule_source(year: int) -> str:
    response = requests.get(f"https://12thman.com/sports/football/schedule/season/{year}",
                            timeout=15, allow_redirects=False)
    response.raise_for_status()
    parser = PageText()
    parser.feed(response.text)
    text = " ".join(parser.parts)
    if f"{year} Football Schedule" not in text or "Schedule Events" not in text:
        raise ValueError("Official season schedule could not be verified")
    events = text.split("Schedule Events", 1)[1].split("Date Teams Location", 1)[0]
    return f"Official Texas A&M Athletics / 12thman.com, {year} season:\n{events[:24000]}"
