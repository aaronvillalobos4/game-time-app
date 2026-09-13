import unittest

from booking_links import booking_links_only, is_booking_url


class BookingLinkTests(unittest.TestCase):
    def test_booking_and_affiliate_urls_are_preserved_exactly(self):
        for url in ["https://www.booking.com/hotel/us/example.html?checkin=2026-10-01",
                    "https://ticketmaster.evyy.net/c/7499899/264167/4272?u=https%3A%2F%2Fwww.ticketmaster.com%2Fevent%2F123",
                    "https://klook.tp.st/AbC123", "https://expedia.com/affiliate/Zc2O7FL"]:
            with self.subTest(url=url):
                text = f"[Book this option]({url})"
                self.assertEqual(booking_links_only(text), text)

    def test_schedule_label_and_game_details_survive(self):
        text = "[Team schedule](https://www.espn.com/team/schedule)\nTeam A vs Team B — October 10, 2026"
        self.assertEqual(booking_links_only(text), "Team schedule\nTeam A vs Team B — October 10, 2026")

    def test_bare_autolinks_and_reference_sources_removed(self):
        result = booking_links_only("https://espn.com/scores <https://nfl.com/schedules>\n[source]: https://nba.com/schedule")
        self.assertNotIn("https://", result)

    def test_information_and_spoofed_destinations_rejected(self):
        for url in ["https://espn.com", "https://booking.com.evil.test/hotel",
                    "https://booking.com@evil.test", "http://booking.com/hotel",
                    "javascript:alert(1)", "https://www.klook.com/blog/stadium-guide",
                    "https://ticketmaster.com/schedule", "https://booking.com/%62log/test"]:
            with self.subTest(url=url):
                self.assertFalse(is_booking_url(url))

    def test_information_cannot_hide_behind_affiliate_wrapper(self):
        self.assertFalse(is_booking_url("https://help.ticketmaster.com/question"))
        self.assertFalse(is_booking_url("https://ticketmaster.evyy.net/c/123?u=https%3A%2F%2Fwww.espn.com%2Fschedule"))

    def test_mixed_reply_keeps_only_booking_action(self):
        result = booking_links_only("[Game](https://nfl.com/game/123) [Tickets](https://www.ticketmaster.com/event/123)")
        self.assertEqual(result, "Game [Tickets](https://www.ticketmaster.com/event/123)")


if __name__ == "__main__":
    unittest.main()
