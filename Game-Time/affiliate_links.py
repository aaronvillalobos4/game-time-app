"""Create approved affiliate URLs for supported booking providers."""

import os
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


DEFAULT_TICKETMASTER_AFFILIATE_URL = (
    "https://ticketmaster.evyy.net/c/7499899/264167/4272"
)
TICKETMASTER_HOST = "ticketmaster.com"
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
