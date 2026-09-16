"""Read the official Aggies football season page, without search-snippet truncation."""
from html.parser import HTMLParser
import requests


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
