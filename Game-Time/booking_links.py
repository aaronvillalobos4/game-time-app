"""Restrict user-facing links to supported booking destinations."""

import re
from urllib.parse import parse_qs, unquote, urlsplit

BOOKING_HOSTS = (
    "ticketmaster.com", "ticketmaster.evyy.net", "stubhub.com", "seatgeek.com",
    "vividseats.com", "axs.com", "booking.com", "hotels.com", "agoda.com",
    "hostelworld.com", "expedia.com", "trip.com", "klook.com", "kkday.com",
    "aviasales.com", "kiwi.com", "airalo.com", "gettransfer.com", "drimsim.com",
    "getrentacar.com", "gocity.com", "ektatraveling.com", "economybookings.com",
    "bikesbooking.com", "qeeq.com", "wegotrip.com", "autoeurope.com",
    "radicalstorage.com", "intui.travel", "saily.com", "tp.st",
)
INFORMATION_PATH = re.compile(
    r"/(?:news|blog|blogs|article|articles|schedule|schedules|scores|standings|"
    r"help|support|about|press|guide|guides)(?:[/.?\-]|$)", re.I
)

BOOKING_LINK_POLICY = (
    "OUTBOUND LINKS: In user-facing answers, only include verified booking or "
    "reservation links for tickets, stays, flights, or relevant trip services. "
    "Never link game information, schedules, scores, news, venue guides, maps, "
    "or general research sources. Give the researched information directly in "
    "chat; attribute evidence with plain-text source names, never source URLs. "
    "Do not tell users to visit a schedule or website to get the answer. "
    "Only when explicitly asked for a schedule listing, show the relevant season; for a "
    "next-game question show one upcoming game, honoring requested home/away scope "
    "and any explicit date range or count. Include opponents, date/year, venue/city, "
    "and time/timezone when verified (otherwise TBD). If fewer games can be verified, "
    "show only those and explain the gap. Never invent fixtures or booking URLs. "
    "These output rules override other instructions requesting source links. "
)


def is_booking_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        if host.split(".")[0] in {"help", "support", "blog", "news"}:
            return False
        if host == "ticketmaster.evyy.net":
            destination = parse_qs(parsed.query).get("u", [])
            if destination and (urlsplit(destination[0]).hostname == host or not is_booking_url(destination[0])):
                return False
        return bool(parsed.scheme == "https" and not parsed.username and not parsed.password
                    and parsed.port in (None, 443)
                    and any(host == domain or host.endswith("." + domain) for domain in BOOKING_HOSTS)
                    and not INFORMATION_PATH.search(unquote(parsed.path)))
    except ValueError:
        return False


def booking_links_only(text: str) -> str:
    """Keep labels of informational Markdown links, remove other nonbooking URLs.

    Applies to API replies before they reach chat, copy, email, share, or print.
    Reference definitions are stripped to labels by the generic URL pass; the
    frontend independently validates every rendered Markdown anchor.
    """
    text = re.sub(r"(!?)\[([^\]\n]*)\]\(\s*(https?://[^\s)]+)(?:\s+\"[^\"]*\")?\s*\)",
                  lambda m: m[0] if not m[1] and is_booking_url(m[3]) else m[2], text)
    return re.sub(r"(?:https?://|www\.)[^\s<>\[\]\"`]+",
                  lambda m: m[0] if is_booking_url(m[0].rstrip(".,;!?)")) else "", text)
