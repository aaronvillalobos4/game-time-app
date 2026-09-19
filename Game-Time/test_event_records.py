import unittest
from datetime import date
from event_records import render_schedule
from schedule_source import parse_aggies_schedule


def fixture(day="Oct 3", clock="Flex", opponent="Arkansas", location="College Station / Kyle Field", away=""):
    return f'''<tr class="schedule-table-item"><td>
      <time class="schedule-event-time__day">{day}</time>
      <time class="schedule-event-time__label">{clock}</time>
      <strong class="schedule-event-default__name schedule-event-default__name--current">Texas A&amp;M</strong>
      {away}<strong class="schedule-event-default__name">{opponent}</strong>
      <span class="schedule-table-item__location">{location}</span></td></tr>'''


class EventRecordTests(unittest.TestCase):
    def parse(self, rows):
        return parse_aggies_schedule('<title>2026 Football Schedule</title><table>' + rows + '</table>', 2026)

    def test_windows_are_not_midnight_and_source_is_retained(self):
        schedule = self.parse(fixture())
        self.assertIsNone(schedule.events[0].kickoff)
        self.assertEqual(schedule.events[0].time_window, 'Flex')
        self.assertIn('/season/2026', schedule.source_url)
        self.assertIn('TBD (Flex window)', render_schedule(schedule))

    def test_filtered_next_game_uses_dates_and_home_away(self):
        schedule = self.parse(fixture() + fixture('Sep 26', '6:30 p.m.', 'LSU', 'Baton Rouge / Tiger Stadium', 'at at '))
        display = render_schedule(schedule, start=date(2026, 9, 18), scope='away', limit=1)
        self.assertIn('LSU', display)
        self.assertNotIn('Arkansas', display)
        self.assertIn('2026-09-26', display)

    def test_no_matching_games_does_not_invent_records(self):
        self.assertIn('No published games', render_schedule(self.parse(fixture()), start=date(2027, 1, 1)))

    def test_incomplete_duplicate_and_wrong_season_fail_closed(self):
        for html in ('<title>2026 Football Schedule</title>',
                     '<title>2025 Football Schedule</title>' + fixture(),
                     '<title>2026 Football Schedule</title><table>' + fixture() * 2 + '</table>',
                     '<title>2026 Football Schedule</title><table>' + fixture(opponent='') + '</table>'):
            with self.assertRaises(ValueError):
                parse_aggies_schedule(html, 2026)
