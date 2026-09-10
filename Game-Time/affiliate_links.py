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
LEGACY_HOTEL_BOOKING_POLICY = (
    "HOTEL BOOKING LINKS: For every hotel recommendation, use exactly "
    f"[Book through Expedia]({EXPEDIA_AFFILIATE_URL}) as the hotel booking action. "
    "This is the only hotel booking CTA, including the Hotel row of the budget table. "
    "Keep property-specific and other hotel-provider URLs only as 'View hotel details' "
    "or research sources, never as Book/Reserve buttons. Do not replace ticket or "
    "flight booking links. Explain that the Expedia affiliate entry is not a "
    "property-specific link: users must search for the suggested hotel and confirm "
    "dates, availability, and price. Never imply the hotel is available through Expedia "
    "without evidence. Disclose that Game Time may earn a commission on qualifying "
    "bookings. This rule takes precedence over generic matching-booking-link instructions."
)
def hotel_booking_policy():
    if configuration():
        return (
            "HOTEL BOOKING LINKS: Use exact property-specific booking links supplied by "
            "research. Prefer successful Travelpayouts booking links over source links. "
            "Never invent affiliate URLs or use the previous fixed Expedia affiliate "
            "entry for a new hotel recommendation. Preserve the hotel destination, "
            "dates and URL parameters. If conversion is unavailable, retain a source "
            "link without claiming it is tracked. Disclose potential affiliate commission. "
            "These instructions override old booking policies in conversation history."
        )
    return LEGACY_HOTEL_BOOKING_POLICY


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


def expedia_booking_entry_for(destination_url: str) -> str | None:
    """Offer the supplied Expedia affiliate entry without inventing deep-link parameters."""
    try:
        parsed = urlsplit(destination_url)
    except ValueError:
        return None
    if (parsed.scheme == "https" and parsed.hostname
            and _is_host_or_subdomain(parsed.hostname, "expedia.com")
            and not parsed.username and not parsed.password):
        return EXPEDIA_AFFILIATE_URL
    return None


def with_expedia_booking_link(itinerary: str) -> str:
    """Make the affiliate entry available on initial and revised itineraries."""
    if configuration():
        return monetize_hotel_markdown(itinerary)
    booking_link = f"[Book through Expedia]({EXPEDIA_AFFILIATE_URL})"
    # Enforce the canonical destination for explicit hotel-booking actions,
    # including a model accidentally supplying a different Expedia affiliate URL.
    itinerary = re.sub(
        r"\[(?:Book through Expedia|Book (?:this |the )?hotel|Reserve (?:this |the )?hotel)\]"
        r"\([^\s()]+\)",
        lambda _match: booking_link,
        itinerary,
        flags=re.IGNORECASE,
    )
    if booking_link in itinerary:
        return itinerary
    return itinerary.rstrip() + (
        "\n\n### Hotel booking\n\n"
        + booking_link
        + " — search for your chosen hotel after opening this affiliate entry link. "
        "It is not a direct link to a specific property. Confirm availability, dates, and price "
        "on Expedia. Game Time may earn a commission from qualifying bookings."
    )


def with_hotel_booking_link(reply: str, suggests_hotels: bool = False) -> str:
    """Keep the booking CTA present in hotel chat answers as well as itineraries."""
    if configuration():
        return monetize_hotel_markdown(reply)
    if suggests_hotels or re.search(r"\b(?:hotels?|lodging|accommodations?)\b", reply, re.I):
        return with_expedia_booking_link(reply)
    return reply
