"""Create approved affiliate URLs for supported booking providers."""

import os
import re
from travelpayouts import configuration, monetize_hotel_markdown
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


DEFAULT_TICKETMASTER_AFFILIATE_URL = (
    "https://ticketmaster.evyy.net/c/7499899/264167/4272"
)
TICKETMASTER_HOST = "ticketmaster.com"
def hotel_booking_policy():
    if configuration():
        return (
            "HOTEL BOOKING LINKS: Never include Expedia affiliate links, including from history. Use exact property-specific booking links supplied by "
            "research. HOTEL SEARCH PRIORITY: Before broader hotel searches, search "
            "both site:klook.com and site:kkday.com separately for overnight accommodation "
            "(prefer www.kkday.com pages; the tested m.kkday.com URL was rejected by "
            "the affiliate API). Retrieve a verified main-site alternative rather than "
            "rewriting mobile URLs or inventing destinations. Search "
            "in the event city near the venue, using the trip dates when known. Prefer "
            "suitable Klook and KKday accommodation offers and their matching booking "
            "links when they meet the user's location, dates, budget and preferences. "
            "Verify the offer includes an overnight stay; hotel dining, spa, day-use "
            "and attraction vouchers are not overnight accommodation. Do not assume "
            "these providers cover every destination. If neither has a suitable verified "
            "option, explain briefly and research other providers. Respect an explicit "
            "user provider choice and preserve existing hotel choices unless asked to change. "
            "Never substitute an unrelated preferred-provider link for the selected hotel. "
            "A successful affiliate conversion does not establish product commission eligibility. "
            "Use exact URLs from "
            "research. Prefer successful Travelpayouts booking links over source links. "
            "Never invent affiliate URLs or use the previous fixed Expedia affiliate "
            "entry for a new hotel recommendation. Preserve the hotel destination, "
            "dates and URL parameters. If conversion is unavailable, retain a source "
            "link without claiming it is tracked. Disclose potential affiliate commission. "
            "These instructions override old booking policies in conversation history."
        )
    return "HOTEL BOOKING LINKS: Use verified source links. Never include Expedia affiliate links."


SUB_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


def _is_host_or_subdomain(hostname: str, allowed_host: str) -> bool:
    hostname = hostname.rstrip(".").casefold()
    allowed_host = allowed_host.casefold()
    return hostname == allowed_host or hostname.endswith(f".{allowed_host}")


def is_ticketmaster_url(url: str) -> bool:
    """Return whether a URL is an HTTPS Ticketmaster destination."""
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False

    return bool(
        parsed.scheme.casefold() == "https"
        and parsed.hostname
        and _is_host_or_subdomain(parsed.hostname, TICKETMASTER_HOST)
    )


def ticketmaster_affiliate_url(destination_url: str) -> str:
    """Wrap an approved Ticketmaster destination in the Impact tracking URL.

    Impact's ``u`` parameter receives the destination through normal query-string
    encoding. Unsupported or unsafe destinations are returned unchanged.
    """
    if not is_ticketmaster_url(destination_url):
        return destination_url

    base_url = os.getenv(
        "TICKETMASTER_AFFILIATE_BASE_URL",
        DEFAULT_TICKETMASTER_AFFILIATE_URL,
    ).strip()
    try:
        parsed_base = urlsplit(base_url)
    except ValueError:
        return destination_url

    if (
        parsed_base.scheme.casefold() != "https"
        or parsed_base.hostname != "ticketmaster.evyy.net"
    ):
        return destination_url

    query = dict(parse_qsl(parsed_base.query, keep_blank_values=True))
    query["u"] = destination_url

    sub_id = os.getenv("TICKETMASTER_SUB_ID", "game-time-itinerary").strip()
    if SUB_ID_PATTERN.fullmatch(sub_id):
        query["subId1"] = sub_id

    return urlunsplit(
        (
            parsed_base.scheme,
            parsed_base.netloc,
            parsed_base.path,
            urlencode(query),
            "",
        )
    )


def affiliate_url_for(destination_url: str) -> str:
    """Return a tracked URL when a supported provider matches."""
    if is_ticketmaster_url(destination_url):
        return ticketmaster_affiliate_url(destination_url)
    return destination_url


def with_hotel_booking_link(reply: str, suggests_hotels: bool = False) -> str:
    """Convert supported hotel links and remove obsolete Expedia affiliate URLs."""
    from travelpayouts import remove_expedia_affiliate_links
    return remove_expedia_affiliate_links(monetize_hotel_markdown(remove_expedia_affiliate_links(reply)))
