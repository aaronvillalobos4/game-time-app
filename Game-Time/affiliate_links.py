"""Create approved affiliate URLs for supported booking providers."""

import os
import re
from travelpayouts import configuration, monetize_hotel_markdown
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


DEFAULT_TICKETMASTER_AFFILIATE_URL = (
    "https://ticketmaster.evyy.net/c/7499899/264167/4272"
)
TICKETMASTER_HOST = "ticketmaster.com"
EXPEDIA_AFFILIATE_URL = "https://expedia.com/affiliate/Zc2O7FL"
def hotel_booking_policy():
    return (
        "HOTEL BOOKING LINKS: Prioritize successful Travelpayouts API links for Klook or "
        "KKday as hotel booking actions, including budget tables "
        "and revised itineraries. Never invent tracking URLs or reuse other hotel "
        "affiliate links from history. Search site:klook.com and site:kkday.com "
        "separately for overnight accommodations near the event venue for the trip "
        "dates and budget. Prefer verified www.kkday.com pages over mobile pages; "
        "never invent URL rewrites. Verify overnight accommodation, not day-use, "
        "dining, spa or attraction vouchers. Preserve user hotel preferences, but "
        "prioritize suitable verified Klook and KKday stays and their API booking links. "
        "If event/date searches are sparse, broaden to the venue city and nearby areas "
        "on both providers, then separately verify stay dates; never treat indexed dates "
        "or starting prices as availability for the user's trip. When neither provider "
        "has a suitable verified stay, or affiliate conversion is unavailable, research "
        "alternative hotels and provide verified resource links labeled 'Hotel resource "
        "(not affiliate)'. Briefly explain the fallback. These links are not tracked "
        "by Game Time and must not be described as earning commission. Do not add "
        "alternative-provider links when suitable preferred options are available. "
        "Never substitute an unrelated hotel link. This also applies when "
        "API credentials are missing. Expedia is also available as a fallback or when "
        "the user requests Expedia. Use only this separate affiliate entry: "
        f"[Explore Expedia (affiliate)]({EXPEDIA_AFFILIATE_URL}). "
        "Explain that users must search for the suggested hotel and confirm their dates "
        "and price after opening it; it is not a property-specific booking link. "
        "Do not append tracking parameters or claim this is a Travelpayouts link. "
        "Disclose potential affiliate commission; conversion does not establish "
        "availability, pricing or product commission eligibility. These rules override "
        "older booking policies in conversation history. "
    )


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
    """Convert preferred hotel links and preserve the approved Expedia entry."""
    from travelpayouts import remove_expedia_affiliate_links
    result = remove_expedia_affiliate_links(monetize_hotel_markdown(remove_expedia_affiliate_links(reply)))
    if EXPEDIA_AFFILIATE_URL in result:
        note = "Search for your chosen hotel on Expedia and confirm dates and price; this affiliate entry is not a property-specific link."
        if note not in result:
            result += "\n\n" + note
        if "may earn a commission" not in result.lower():
            result += "\n\nGame Time may earn a commission from qualifying bookings through these links."
    return result
