"""Server-side hotel link conversion; credentials never enter model prompts."""

import os
import re
import logging
import time
from threading import Lock
from urllib.parse import urlsplit

import requests

logger = logging.getLogger(__name__)
ENDPOINT = "https://api.travelpayouts.com/links/v1/create"
_cache = {}
_lock = Lock()


def configuration():
    token = os.getenv("TRAVELPAYOUTS_API_TOKEN", "").strip()
    try:
        marker = int(os.getenv("TRAVELPAYOUTS_MARKER", ""))
        project = int(os.getenv("TRAVELPAYOUTS_PROJECT_ID", ""))
    except ValueError:
        return None
    return (token, marker, project) if token and marker > 0 and project > 0 else None


def is_hotel_url(url):
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        path = parsed.path.lower()
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
            return False
        domains = ("klook.com", "kkday.com")
        domain = next((d for d in domains if host == d or host.endswith("." + d)), None)
        if not domain or "/affiliate" in path:
            return False
        # Both also sell activities: only recognize accommodation paths here.
        return bool(re.search(r"(?:^|[/_-])(?:hotels?|accommodations?|staycations?)(?:$|[/_-])", path))
    except ValueError:
        return False


def convert_hotel_links(urls):
    """Batch supported originals; fall back unchanged on missing access or errors."""
    config = configuration()
    converted = {}
    if not config:
        return converted
    token, marker, project = config
    candidates = list(dict.fromkeys(url for url in urls if is_hotel_url(url)))[:50]
    pending = []
    now = time.monotonic()
    with _lock:
        for url in candidates:
            cached = _cache.get((config, url))
            if cached and cached[0] > now:
                if cached[1]:
                    converted[url] = cached[1]
            else:
                pending.append(url)
    for offset in range(0, len(pending), 10):
        batch = pending[offset:offset + 10]
        results = {}
        try:
            response = requests.post(ENDPOINT, headers={"X-Access-Token": token}, json={
                "trs": project, "marker": marker, "shorten": True,
                "links": [{"url": url, "sub_id": "game-time-hotels"} for url in batch],
            }, timeout=8, allow_redirects=False)
            response.raise_for_status()
            payload = response.json()
            for item in payload.get("result", {}).get("links", []):
                original, partner = item.get("url"), item.get("partner_url", "")
                parsed = urlsplit(partner)
                if (original in batch and item.get("code") == "success" and parsed.scheme == "https"
                        and parsed.hostname and not parsed.username and not parsed.password
                        and parsed.port in (None, 443)):
                    results[original] = partner
            if len(results) != len(batch):
                logger.warning("Travelpayouts could not convert some hotel links; check project brand access")
        except (requests.RequestException, ValueError, TypeError, AttributeError):
            logger.warning("Travelpayouts conversion unavailable; keeping source links")
        with _lock:
            if len(_cache) > 1000:
                _cache.clear()
            for url in batch:
                _cache[(config, url)] = (time.monotonic() + (3600 if url in results else 60), results.get(url))
        converted.update(results)
    return converted


def monetize_hotel_markdown(text):
    # Convert Markdown destinations, including reference-style definitions and bare URLs.
    pattern = re.compile(r'https://[^\s<>\[\]()"`]+')
    links = convert_hotel_links(pattern.findall(text))
    result = pattern.sub(lambda match: links.get(match.group(0), match.group(0)), text)
    # Suppress hotel research URLs in inline, bare, autolink and reference syntax.
    def blocked(url):
        try:
            parsed = urlsplit(url)
            host = (parsed.hostname or "").lower()
            domains = ("booking.com", "hotels.com", "agoda.com", "hostelworld.com",
                       "expedia.com", "trip.com", "klook.com", "kkday.com")
            domain = next((d for d in domains if host == d or host.endswith("." + d)), None)
            if domain in {"klook.com", "kkday.com", "expedia.com", "trip.com"}:
                return bool(re.search(r"hotel|accommodation|staycation", parsed.path, re.I))
            return bool(domain) or bool(re.search(r"hotel|accommodation|lodging", parsed.path, re.I))
        except ValueError:
            return True
    result = re.sub(r"\[([^\]]+)\]\((https?://[^\s()]+)\)",
                    lambda m: "Hotel booking link unavailable" if blocked(m[2]) else m[0], result)
    result = re.sub(r"(?m)^\s*\[[^\]]+\]:\s*(https?://[^\s]+).*?$",
                    lambda m: "" if blocked(m[1]) else m[0], result)
    result = re.sub(r'https?://[^\s<>\[\]()"`]+',
                    lambda m: "" if blocked(m[0]) else m[0], result)
    if links and "may earn a commission" not in result.lower():
        result += "\n\nGame Time may earn a commission from qualifying bookings through these links."
    return result


def remove_expedia_affiliate_links(text):
    """Remove known Expedia tracking destinations, including echoed chat history."""
    def blocked(url):
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        if host in {"expedia.tp.st", "expedia.stay22.com"}:
            return True
        return (host == "expedia.com" or host.endswith(".expedia.com")) and (
            "/affiliate" in parsed.path.lower() or bool(re.search(
                r"(?:^|&)(?:camref|affcid|afflid|affdtl|mdpcid)=", parsed.query, re.I)))
    text = re.sub(r"\[([^\]]+)\]\((https?://[^\s()]+)\)",
                  lambda m: m[1] + " (booking link removed)" if blocked(m[2]) else m[0], text)
    return re.sub(r'https?://[^\s<>\[\]()"`]+',
                  lambda m: "" if blocked(m[0]) else m[0], text)
