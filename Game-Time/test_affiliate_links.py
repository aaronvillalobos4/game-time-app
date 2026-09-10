"""Unit tests for outbound affiliate-link generation."""

import os
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from affiliate_links import (affiliate_url_for, ticketmaster_affiliate_url,
                             expedia_booking_entry_for, with_expedia_booking_link,
                             EXPEDIA_AFFILIATE_URL)
from affiliate_links import with_hotel_booking_link


class AffiliateLinkTests(unittest.TestCase):
    def setUp(self):
        config = patch.dict(os.environ, {"TRAVELPAYOUTS_API_TOKEN": ""})
        config.start()
        self.addCleanup(config.stop)

    def test_chat_hotel_recommendation_has_canonical_booking_action(self):
        reply = "Try the Example Inn. [View hotel details](https://example.com/property)"
        result = with_hotel_booking_link(reply, suggests_hotels=True)
        self.assertIn(reply, result)
        self.assertIn(f"[Book through Expedia]({EXPEDIA_AFFILIATE_URL})", result)

    def test_non_hotel_reply_does_not_add_booking_action(self):
        self.assertEqual(with_hotel_booking_link("Will you need flights?"), "Will you need flights?")

    def test_explicit_hotel_booking_action_uses_our_link(self):
        reply = "[Book through Expedia](https://expedia.com/affiliate/another)"
        result = with_expedia_booking_link(reply)
        self.assertEqual(result, f"[Book through Expedia]({EXPEDIA_AFFILIATE_URL})")

    def test_expedia_source_preserved_with_separate_affiliate_entry(self):
        source = "https://www.expedia.com/Hotel-Search?destination=Austin"
        self.assertEqual(affiliate_url_for(source), source)
        self.assertEqual(expedia_booking_entry_for(source), EXPEDIA_AFFILIATE_URL)

    def test_expedia_rejects_unrelated_or_unsafe_urls(self):
        for source in ("https://expedia.com.evil.test/hotel", "http://expedia.com", "https://user@expedia.com", "https://example.com"):
            self.assertIsNone(expedia_booking_entry_for(source))

    def test_itinerary_affiliate_entry_added_once(self):
        original = "Hotel: [Details](https://www.expedia.com/hotel-example)"
        result = with_expedia_booking_link(original)
        self.assertIn(original, result)
        self.assertIn(EXPEDIA_AFFILIATE_URL, result)
        self.assertEqual(with_expedia_booking_link(result), result)

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
