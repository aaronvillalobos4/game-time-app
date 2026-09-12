import os
import unittest
from unittest.mock import Mock, patch

import requests
import travelpayouts as tp
from affiliate_links import with_hotel_booking_link, hotel_booking_policy


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
        urls = [f"https://www.klook.com/hotels/example-{i}.html?checkin=2026-10-10" for i in range(11)]
        def convert(*args, **kwargs):
            return self.response([{"url": item["url"], "code": "success", "partner_url": f"https://klook.tp.st/{urls.index(item['url'])}"} for item in kwargs["json"]["links"]])
        with patch("travelpayouts.requests.post", side_effect=convert) as post:
            result = tp.convert_hotel_links(urls + urls)
            self.assertEqual(len(result), 11)
            self.assertEqual(post.call_count, 2)
            self.assertEqual(post.call_args.kwargs["headers"], {"X-Access-Token": "test-token"})
            self.assertEqual(post.call_args.kwargs["json"]["trs"], 456)
            self.assertEqual(tp.convert_hotel_links(urls), result)
            self.assertEqual(post.call_count, 2)

    def test_partial_failures_preserve_original_destinations(self):
        a, b = "https://klook.com/hotel/a.html", "https://kkday.com/en/hotel/product/123"
        rows = [{"url": a, "code": "success", "partner_url": "https://klook.tp.st/abc"},
                {"url": b, "code": "failed", "partner_url": ""}]
        with patch("travelpayouts.requests.post", return_value=self.response(rows)), self.assertLogs("travelpayouts", level="WARNING"):
            result = tp.monetize_hotel_markdown(f"[A]({a}) [B]({b})")
        self.assertIn("[A](https://klook.tp.st/abc)", result)
        self.assertIn(f"[Research source]({b})", result)
        self.assertIn("may earn a commission", result)

    def test_timeout_does_not_break_answer_or_inject_old_expedia_link(self):
        reply = "Hotel [Book](https://klook.com/hotel/a.html)"
        with patch("travelpayouts.requests.post", side_effect=requests.Timeout), self.assertLogs("travelpayouts", level="WARNING"):
            self.assertEqual(with_hotel_booking_link(reply, True), reply.replace("[Book]", "[Research source]"))
        self.assertNotIn("https://expedia.com/affiliate/legacy", hotel_booking_policy())

    def test_wrong_or_unsafe_response_not_used(self):
        url = "https://klook.com/hotel/a.html"
        for row in ({"url": url, "code": "success", "partner_url": "javascript:alert(1)"},
                    {"url": "https://klook.com/hotel/other.html", "code": "success", "partner_url": "https://klook.tp.st/abc"}):
            tp._cache.clear()
            with patch("travelpayouts.requests.post", return_value=self.response([row])), self.assertLogs("travelpayouts", level="WARNING"):
                self.assertEqual(tp.convert_hotel_links([url]), {})

    def test_non_hotel_and_existing_affiliate_links_skipped(self):
        urls = ["https://booking.com.evil.test/hotel", "https://user@booking.com/hotel", "http://booking.com/hotel",
                "https://ticketmaster.com/event/123", "https://klook.tp.st/abc",
                "https://www.expedia.co.uk/Hotel-Search", "https://www.expedia.com/Flights-Search"]
        with patch("travelpayouts.requests.post") as post:
            self.assertEqual(tp.convert_hotel_links(urls), {})
            post.assert_not_called()

    def test_missing_configuration_skips_api(self):
        with patch.dict(os.environ, {"TRAVELPAYOUTS_API_TOKEN": ""}), patch("travelpayouts.requests.post") as post:
            self.assertEqual(tp.convert_hotel_links(["https://klook.com/hotel/a.html"]), {})
            post.assert_not_called()

    def test_other_hotel_providers_never_sent_to_api(self):
        urls = ["https://booking.com/hotel/us/example.html", "https://hotels.com/ho123/example",
                "https://agoda.com/example/hotel/city.html", "https://trip.com/hotels/example",
                "https://hostelworld.com/hostels/example", "https://expedia.com/Hotel-Search"]
        with patch("travelpayouts.requests.post") as post:
            result = tp.monetize_hotel_markdown(" ".join(f"[Book hotel]({url})" for url in urls))
            post.assert_not_called()
        self.assertNotIn("[Book hotel]", result)
        self.assertEqual(result.count("[Research source]"), len(urls))

    def test_missing_credentials_never_present_raw_hotel_booking_action(self):
        with patch.dict(os.environ, {"TRAVELPAYOUTS_API_TOKEN": ""}):
            result = with_hotel_booking_link("[Book hotel](https://klook.com/hotels/example)")
        self.assertEqual(result, "[Research source](https://klook.com/hotels/example)")

    def test_preferred_accommodation_links_convert_in_chat(self):
        urls = ["https://www.klook.com/hotels/detail/123-example/",
                "https://m.kkday.com/en-au/hotel/product/299700"]
        rows = [{"url": url, "code": "success", "partner_url": f"https://example.tp.st/{i}"}
                for i, url in enumerate(urls)]
        with patch("travelpayouts.requests.post", return_value=self.response(rows)) as post:
            result = with_hotel_booking_link(" ".join(f"[Hotel]({url})" for url in urls), True)
        self.assertEqual([item["url"] for item in post.call_args.kwargs["json"]["links"]], urls)
        for row in rows:
            self.assertIn(row["partner_url"], result)
        self.assertIn("may earn a commission", result)

    def test_preferred_providers_do_not_match_activities_or_lookalikes(self):
        for url in ("https://www.klook.com/activity/123-stadium-tour/",
                    "https://www.kkday.com/en/product/123-city-tour",
                    "https://klook.com.evil.test/hotels/",
                    "https://user@kkday.com/en/hotel/product/123",
                    "http://klook.com/hotels/"):
            self.assertFalse(tp.is_hotel_url(url), url)
