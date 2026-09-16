import unittest
from unittest.mock import Mock, patch
from schedule_source import aggies_schedule_source


class ScheduleSourceTests(unittest.TestCase):
    def test_extracts_requested_season_without_scripts_or_duplicate_table(self):
        response = Mock(text='<title>2026 Football Schedule</title><script>wrong fixture</script>'
                        '<main>Schedule Events Sat Oct 17 The Citadel Date Teams Location duplicate</main>')
        with patch('schedule_source.requests.get', return_value=response) as get:
            text = aggies_schedule_source(2026)
        self.assertIn('The Citadel', text)
        self.assertNotIn('wrong fixture', text)
        self.assertNotIn('duplicate', text)
        self.assertIn('/season/2026', get.call_args.args[0])

    def test_wrong_season_is_rejected(self):
        with patch('schedule_source.requests.get', return_value=Mock(text='2025 Football Schedule Schedule Events')):
            with self.assertRaises(ValueError):
                aggies_schedule_source(2026)
