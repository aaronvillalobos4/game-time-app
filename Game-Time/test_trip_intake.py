import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from conversation import AssistantTurn, TripSlots, ChatParseRequest, ChatMessage, next_question
from app import parse_intent, ItineraryRequest
from agents import answer_trip_message, TravelCrew
from pydantic import ValidationError
from test_itinerary import plan, INPUTS


class IntakeTests(unittest.IsolatedAsyncioTestCase):
    async def test_sample_consent_completes_intake(self):
        slots = TripSlots(event='Game', date='2026-10-10', needs_flight=False,
                          needs_hotel=False, trip_requested=True)
        question = next_question(slots)
        with patch('app.answer_trip_message', new_callable=AsyncMock,
                   return_value=AssistantTurn(intent='trip_update', reply='Saved')):
            result = await parse_intent(ChatParseRequest(message='Yes please', current_slots=slots,
                history=[ChatMessage(role='assistant', content=question)]))
        self.assertEqual(result['slots']['budget'], 1500)
        self.assertTrue(result['is_complete'])

    async def test_full_intake_sequence_builds_after_last_answer(self):
        slots = TripSlots()
        steps = [
            ("I want tickets to this game", TripSlots(trip_requested=True), "Which game"),
            ("Cowboys vs Giants on October 10, 2026", TripSlots(event="Cowboys vs Giants", date="2026-10-10"), "flights"),
            ("No flights", TripSlots(needs_flight=False), "hotel"),
            ("No hotel", TripSlots(needs_hotel=False), "budget"),
            ("My budget is $800", TripSlots(budget=800), None),
        ]
        for message, updates, question in steps:
            with patch('app.answer_trip_message', new_callable=AsyncMock,
                       return_value=AssistantTurn(intent='trip_update', reply='Saved', slot_updates=updates)):
                result = await parse_intent(ChatParseRequest(message=message, current_slots=slots))
            slots = TripSlots.model_validate(result['slots'])
            self.assertEqual(result['is_complete'], question is None)
            if question: self.assertIn(question, result['follow_up_question'])
        self.assertFalse(slots.needs_hotel)
        self.assertEqual(slots.budget, 800)

    async def test_schedule_detour_does_not_build_or_force_intake(self):
        slots = TripSlots(event='Game', date='2026-10-10', needs_flight=False,
                          needs_hotel=False, budget=800, trip_requested=True)
        with patch('app.answer_trip_message', new_callable=AsyncMock,
                   return_value=AssistantTurn(intent='schedule', reply='Schedule table')):
            result = await parse_intent(ChatParseRequest(message='Show their schedule', current_slots=slots))
        self.assertFalse(result['is_complete'])
        self.assertEqual(result['follow_up_question'], 'Schedule table')

    def test_flying_requires_origin_and_hotel_is_explicit(self):
        slots = TripSlots(event='Game', date='2026-10-10', needs_flight=True, budget=800)
        self.assertIn('flying from', next_question(slots))
        slots.departure_city = 'Austin'
        self.assertIn('hotel', next_question(slots))

    async def test_booking_tool_waits_for_hotel_choice_even_with_budget(self):
        slots = TripSlots(event='Game', date='2026-10-10', needs_flight=False, budget=800)
        with patch('agents.Crew') as crew, patch('agents._google_search') as search:
            async def kickoff():
                tool = crew.call_args.kwargs['agents'][0].tools[0]
                self.assertIn('hotel', tool.func(query='tickets', purpose='tickets'))
                return SimpleNamespace(pydantic=AssistantTurn(reply='Need hotel?'))
            crew.return_value.kickoff_async = kickoff
            await answer_trip_message(ChatParseRequest(message='Find tickets', current_slots=slots))
        search.assert_not_called()

    async def test_no_hotel_does_not_research_or_budget_lodging(self):
        inputs = dict(INPUTS, needs_hotel=False)
        with patch('agents.Crew') as crew, patch('agents.with_hotel_booking_link', side_effect=lambda s:s):
            crew.return_value.kickoff_async = AsyncMock(return_value=SimpleNamespace(pydantic=plan()))
            text = await TravelCrew(inputs).run()
        tasks = crew.call_args.kwargs['tasks']
        self.assertIn('Do not search for or recommend hotels', tasks[1].description)
        self.assertIn('Hotel: not needed', text)
        self.assertIn('**Estimated total:** $150.00', text)
        self.assertNotIn('**Hotel**', text)

    def test_stream_requires_explicit_hotel_preference(self):
        with self.assertRaises(ValidationError):
            ItineraryRequest(event='Game', date='2026-10-10', departure_city='Local', budget=800)


if __name__ == '__main__':
    unittest.main()
