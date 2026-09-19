import unittest
from unittest.mock import Mock
from research_policy import run_research, BOOKING_PURPOSES
from budget_gate import BUDGET_QUESTION
from conversation import AssistantTurn, TripSlots


class ResearchPolicyTests(unittest.TestCase):
    def test_booking_permissions_are_independent_of_query_words(self):
        for purpose in BOOKING_PURPOSES:
            for budget in (None, 0, -1, True, float('nan')):
                search = Mock()
                self.assertEqual(run_research('that cheaper one', purpose, budget, search), BUDGET_QUESTION)
                search.assert_not_called()

    def test_information_does_not_need_budget_or_affiliate_conversion(self):
        search = Mock(return_value='facts')
        self.assertEqual(run_research('Are tickets digital?', 'travel_information', None, search), 'facts')
        search.assert_called_once_with('Are tickets digital?', monetize=False)

    def test_confirmed_budget_allows_booking_research(self):
        search = Mock(return_value='options')
        run_research('hotels', 'hotels', 1500, search)
        search.assert_called_once_with('hotels', monetize=True)

    def test_information_cannot_select_a_trip_or_build(self):
        turn = AssistantTurn(intent='information', reply='The game starts at 3.',
                             slot_updates=TripSlots(event='Unchosen game'), build_itinerary=True)
        self.assertIsNone(turn.slot_updates.event)
        self.assertFalse(turn.build_itinerary)

    def test_explicit_trip_update_is_preserved(self):
        turn = AssistantTurn(intent='trip_update', reply='Budget updated.',
                             slot_updates=TripSlots(budget=900), build_itinerary=True)
        self.assertEqual(turn.slot_updates.budget, 900)
        self.assertFalse(turn.build_itinerary)
