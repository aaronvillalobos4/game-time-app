"""Unit tests for outbound affiliate-link generation."""

import os
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from affiliate_links import affiliate_url_for, ticketmaster_affiliate_url, with_hotel_booking_link

class AffiliateLinkTests(unittest.TestCase):
    def test_expedia_tracking_removed_from_replies(self):
        with patch.dict(os.environ, {"TRAVELPAYOUTS_API_TOKEN": ""}):
            for url in ("https://expedia.com/affiliate/legacy",
                        "https://www.expedia.com/Hotel-Search?camref=legacy",
                        "https://expedia.tp.st/old"):
                result = with_hotel_booking_link(f"[Book]({url})")
                self.assertNotIn(url, result)
                self.assertIn("booking link removed", result)

    def test_no_expedia_fallback_without_configuration(self):
        with patch.dict(os.environ, {"TRAVELPAYOUTS_API_TOKEN": ""}):
            self.assertEqual(with_hotel_booking_link("Try this hotel", True), "Try this hotel")

    def test_wraps_ticketmaster_event_url(self) -> None:
        destination = "https://www.ticketmaster.com/event/123?qty=2"

        tracked = ticketmaster_affiliate_url(destination)
        parsed = urlsplit(tracked)
        query = parse_qs(parsed.query)

        self.assertEqual(parsed.hostname, "ticketmaster.evyy.net")
        self.assertEqual(query["u"], [destination])
        self.assertEqual(query["subId1"], ["game-time-itinerary"])

    def test_accepts_ticketmaster_subdomains(self) -> None:
        destination = "https://help.ticketmaster.com/event/example"
        self.assertNotEqual(affiliate_url_for(destination), destination)

    def test_does_not_wrap_lookalike_domain(self) -> None:
        destination = "https://ticketmaster.com.example.org/event/123"
        self.assertEqual(affiliate_url_for(destination), destination)

    def test_does_not_wrap_insecure_url(self) -> None:
        destination = "http://www.ticketmaster.com/event/123"
        self.assertEqual(affiliate_url_for(destination), destination)

    def test_leaves_other_providers_unchanged(self) -> None:
        destination = "https://seatgeek.com/example"
        self.assertEqual(affiliate_url_for(destination), destination)

    def test_invalid_config_fails_closed(self) -> None:
        destination = "https://www.ticketmaster.com/event/123"
        with patch.dict(
            os.environ,
            {"TICKETMASTER_AFFILIATE_BASE_URL": "https://example.com/redirect"},
        ):
            self.assertEqual(ticketmaster_affiliate_url(destination), destination)


if __name__ == "__main__":
    unittest.main()
