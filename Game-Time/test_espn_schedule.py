import copy
import unittest
from datetime import date
from unittest.mock import Mock, patch

from espn_schedule import parse_schedule, resolve_team, team_event_records, TeamSelectionError
from event_records import render_schedule
from conversation import AssistantTurn


TEAM = {"id": "6", "displayName": "Dallas Cowboys", "name": "Cowboys", "abbreviation": "DAL"}


def fixture():
    return {"team": TEAM, "events": [{"id": "1", "season": {"year": 2026},
        "seasonType": {"type": 2}, "competitions": [{"date": "2026-09-21T00:20Z",
        "timeValid": True, "neutralSite": False,
        "competitors": [{"team": TEAM, "homeAway": "home"},
                        {"team": {"id": "2", "displayName": "Opponent"}, "homeAway": "away"}],
        "venue": {"fullName": "AT&T Stadium", "address": {"city": "Arlington", "state": "TX"}}}]}]}


def parse(data):
    return parse_schedule(data, league="nfl", team=TEAM, year=2026, phase=2)


class ESPNScheduleTests(unittest.TestCase):
    def test_name_resolution_and_ambiguity(self):
        other = {"id": "2", "displayName": "Other Cowboys", "name": "Cowboys"}
        data = {"sports": [{"leagues": [{"teams": [{"team": TEAM}, {"team": other}]}]}]}
        self.assertEqual(resolve_team(data, "DAL"), TEAM)
        self.assertEqual(resolve_team(data, "Dallas Cowboys"), TEAM)
        with self.assertRaises(TeamSelectionError): resolve_team(data, "Cowboys")
        with self.assertRaises(TeamSelectionError): resolve_team(data, "Unknown")

    def test_central_date_rollover_and_dst(self):
        record = parse(fixture())["1"]
        self.assertEqual(record.date, date(2026, 9, 20))
        self.assertEqual(record.kickoff, "7:20 PM CDT")
        data = fixture()
        data["events"][0]["competitions"][0]["date"] = "2026-12-21T01:20Z"
        self.assertEqual(parse(data)["1"].kickoff, "7:20 PM CST")

    def test_tbd_date_does_not_shift_and_neutral_site(self):
        data = fixture()
        game = data["events"][0]["competitions"][0]
        game.update(timeValid=False, neutralSite=True, date="2026-09-20T00:00Z")
        game["status"] = {"type": {"description": "Postponed"}}
        record = parse(data)["1"]
        self.assertEqual(record.date, date(2026, 9, 20))
        self.assertIsNone(record.kickoff)
        self.assertEqual(record.home_away, "Neutral")
        self.assertEqual(record.status, "Postponed")

    def test_wrong_season_team_and_participants_rejected(self):
        for mutate in (
            lambda d: d["events"][0]["season"].update(year=2025),
            lambda d: d["events"][0]["seasonType"].update(type=3),
            lambda d: d.update(team={"id": "9"}),
            lambda d: d["events"][0]["competitions"][0].update(competitors=[]),
        ):
            data = fixture(); mutate(data)
            with self.assertRaises(ValueError): parse(data)

    def test_doubleheaders_and_duplicate_ids(self):
        data = fixture(); second = copy.deepcopy(data["events"][0]); second["id"] = "2"
        data["events"].append(second)
        self.assertEqual(len(parse(data)), 2)
        second["id"] = "1"
        self.assertEqual(len(parse(data)), 1)
        second["competitions"][0]["date"] = "2026-09-22T00:20Z"
        with self.assertRaises(ValueError): parse(data)

    def test_full_schedule_and_filters_without_truncation(self):
        directory = {"sports": [{"leagues": [{"teams": [{"team": TEAM}]}]}]}
        data = fixture()
        data["events"] = [dict(copy.deepcopy(data["events"][0]), id=str(i)) for i in range(162)]
        def get(url, params, **kwargs):
            payload = directory if url.endswith('/teams') else data
            return Mock(json=lambda: payload, raise_for_status=lambda: None)
        with patch("espn_schedule.requests.get", side_effect=get):
            schedule = team_event_records("mlb", "DAL", 2026, "regular")
        self.assertEqual(len(schedule.events), 162)
        display = render_schedule(schedule)
        self.assertEqual(display.count("| Opponent |"), 163)  # header plus all fixtures
        self.assertEqual(AssistantTurn(reply=display).reply, display)
        self.assertIn("baseball schedule", display)
        self.assertEqual(render_schedule(schedule, limit=1).count("| Opponent |"), 2)
        self.assertIn("No published", render_schedule(schedule, scope="away"))


if __name__ == "__main__":
    unittest.main()
