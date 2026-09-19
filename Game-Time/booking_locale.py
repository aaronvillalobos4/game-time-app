"""English destinations for known storefront routes, before affiliate conversion."""
import re
from urllib.parse import urlsplit, urlunsplit


def english_booking_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
            return url
        host = (parsed.hostname or "").lower()
        if host in {"klook.com", "www.klook.com"}:
            locale, routes = "en-US", {"hotels", "hotel", "activity", "city", "search"}
        elif host in {"kkday.com", "www.kkday.com", "m.kkday.com"}:
            locale, routes = "en", {"hotel", "hotels", "product", "productlist", "city"}
        else:
            return url
        parts = parsed.path.lstrip('/').split('/')
        if re.fullmatch(r"[a-z]{2}(?:-[a-z]{2})?", parts[0], re.I):
            parts = parts[1:]
        if not parts or parts[0] not in routes:
            return url
        path = '/' + locale + '/' + '/'.join(parts)
        # Preserve dates, currency and tracking query bytes; never edit short links.
        return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))
    except (ValueError, TypeError):
        return url
