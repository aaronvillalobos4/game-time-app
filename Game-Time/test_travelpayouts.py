import os
import unittest
from unittest.mock import Mock, patch

import requests
import travelpayouts as tp
from affiliate_links import with_hotel_booking_link, hotel_booking_policy, EXPEDIA_AFFILIATE_URL


class TravelpayoutsTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"TRAVELPAYOUTS_API_TOKEN": "test-token",
            "TRAVELPAYOUTS_MARKER": "123", "TRAVELPAYOUTS_PROJECT_ID": "456"})
        self.env.start()
        self.addCleanup(self.env.stop)
        tp._cache.clear()

    def response(self, rows):
        response = Mock()
        response.json.return_value = {"result": {"links": rows}}
        return response

    def test_batching_auth_and_caching(self):
        urls = [f"https://www.booking.com/hotel/us/example-{i}.html?checkin=2026-10-10" for i in range(11)]
        def convert(*args, **kwargs):
            return self.response([{"url": item["url"], "code": "success", "partner_url": f"https://booking.tp.st/{urls.index(item['url'])}"} for item in kwargs["json"]["links"]])
        with patch("travelpayouts.requests.post", side_effect=convert) as post:
            result = tp.convert_hotel_links(urls + urls)
            self.assertEqual(len(result), 11)
            self.assertEqual(post.call_count, 2)
            self.assertEqual(post.call_args.kwargs["headers"], {"X-Access-Token": "test-token"})
            self.assertEqual(post.call_args.kwargs["json"]["trs"], 456)
            self.assertEqual(tp.convert_hotel_links(urls), result)
            self.assertEqual(post.call_count, 2)

    def test_partial_failures_preserve_original_destinations(self):
        a, b = "https://booking.com/hotel/a.html", "https://hotels.com/ho123/example"
        rows = [{"url": a, "code": "success", "partner_url": "https://booking.tp.st/abc"},
                {"url": b, "code": "failed", "partner_url": ""}]
        with patch("travelpayouts.requests.post", return_value=self.response(rows)), self.assertLogs("travelpayouts", level="WARNING"):
            result = tp.monetize_hotel_markdown(f"[A]({a}) [B]({b})")
        self.assertIn("[A](https://booking.tp.st/abc)", result)
        self.assertIn(f"[B]({b})", result)
        self.assertIn("may earn a commission", result)

    def test_timeout_does_not_break_answer_or_inject_old_expedia_link(self):
        reply = "Hotel [Book](https://booking.com/hotel/a.html)"
        with patch("travelpayouts.requests.post", side_effect=requests.Timeout), self.assertLogs("travelpayouts", level="WARNING"):
            self.assertEqual(with_hotel_booking_link(reply, True), reply)
        self.assertNotIn(EXPEDIA_AFFILIATE_URL, hotel_booking_policy())

    def test_wrong_or_unsafe_response_not_used(self):
        url = "https://booking.com/hotel/a.html"
        for row in ({"url": url, "code": "success", "partner_url": "javascript:alert(1)"},
                    {"url": "https://booking.com/hotel/other.html", "code": "success", "partner_url": "https://booking.tp.st/abc"}):
            tp._cache.clear()
            with patch("travelpayouts.requests.post", return_value=self.response([row])), self.assertLogs("travelpayouts", level="WARNING"):
                self.assertEqual(tp.convert_hotel_links([url]), {})

    def test_non_hotel_and_existing_affiliate_links_skipped(self):
        urls = ["https://booking.com.evil.test/hotel", "https://user@booking.com/hotel", "http://booking.com/hotel",
                "https://ticketmaster.com/event/123", "https://booking.tp.st/abc", EXPEDIA_AFFILIATE_URL,
                "https://www.expedia.co.uk/Hotel-Search", "https://www.expedia.com/Flights-Search"]
        with patch("travelpayouts.requests.post") as post:
            self.assertEqual(tp.convert_hotel_links(urls), {})
            post.assert_not_called()

    def test_missing_configuration_skips_api(self):
        with patch.dict(os.environ, {"TRAVELPAYOUTS_API_TOKEN": ""}), patch("travelpayouts.requests.post") as post:
            self.assertEqual(tp.convert_hotel_links(["https://booking.com/hotel/a.html"]), {})
            post.assert_not_called()
