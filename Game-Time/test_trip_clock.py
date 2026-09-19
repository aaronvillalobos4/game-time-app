import unittest
from datetime import datetime, timezone
from trip_clock import planning_now, calendar_context


class TripClockTests(unittest.TestCase):
    def test_utc_rollover_keeps_texas_previous_day(self):
        instant = datetime(2026, 9, 19, 1, 30, tzinfo=timezone.utc)
        self.assertEqual(planning_now(instant).date().isoformat(), "2026-09-18")
        self.assertIn("2026-09-18", calendar_context(instant))
        self.assertIn("CDT", calendar_context(instant))

    def test_winter_offset(self):
        instant = datetime(2026, 1, 19, 5, 30, tzinfo=timezone.utc)
        self.assertEqual(planning_now(instant).date().isoformat(), "2026-01-18")
        self.assertEqual(planning_now(instant).tzname(), "CST")

    def test_local_midnight_advances_day(self):
        instant = datetime(2026, 9, 19, 5, 0, tzinfo=timezone.utc)
        self.assertEqual(planning_now(instant).date().isoformat(), "2026-09-19")
