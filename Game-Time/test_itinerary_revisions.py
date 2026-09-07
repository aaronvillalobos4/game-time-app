"""Ensure edits reach the revision workflow with the existing plan intact."""

import json
import unittest
from unittest.mock import AsyncMock, patch

from agents import TravelCrew
from app import ItineraryRequest, generate_itinerary_stream, parse_intent
from conversation import AssistantTurn, ChatParseRequest, TripSlots


class RevisionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.slots = TripSlots(event="Team A vs Team B", date="October 10, 2026",
                               budget=1000, needs_flight=False, departure_city="Local")

    async def test_hotel_edit_can_build_without_changing_slots(self):
        with patch("app.answer_trip_message", new_callable=AsyncMock,
                   return_value=AssistantTurn(reply="I'll replace the hotel", build_itinerary=True)):
            result = await parse_intent(ChatParseRequest(message="Replace the hotel",
                current_slots=self.slots, current_itinerary="Existing plan"))
        self.assertTrue(result["is_complete"])
        self.assertEqual(result["slots"], self.slots.model_dump())

    async def test_budget_edit_uses_new_budget(self):
        with patch("app.answer_trip_message", new_callable=AsyncMock,
                   return_value=AssistantTurn(reply="I'll revise it", build_itinerary=True,
                                              slot_updates=TripSlots(budget=800))):
            result = await parse_intent(ChatParseRequest(message="Lower my budget to $800",
                current_slots=self.slots, current_itinerary="Existing plan"))
        self.assertTrue(result["is_complete"])
        self.assertEqual(result["slots"]["budget"], 800)

    async def test_hotel_question_does_not_rebuild(self):
        with patch("app.answer_trip_message", new_callable=AsyncMock,
                   return_value=AssistantTurn(reply="The hotel costs $200")):
            result = await parse_intent(ChatParseRequest(message="How much is the hotel?",
                current_slots=self.slots, current_itinerary="Existing plan"))
        self.assertFalse(result["is_complete"])

    async def test_stream_passes_original_and_requested_changes(self):
        request = ItineraryRequest(event=self.slots.event, date=self.slots.date,
            departure_city="Local", budget=800, current_itinerary="Original hotel and tickets",
            revision_request="Find a cheaper hotel", revision_context="Keep my ticket seats")
        with patch("app.TravelCrew") as crew:
            crew.return_value.run = AsyncMock(return_value="Revised full itinerary")
            response = await generate_itinerary_stream(request)
            chunks = [chunk async for chunk in response.body_iterator]
        inputs = crew.call_args.args[0]
        self.assertEqual(inputs["budget"], 800)
        self.assertEqual(inputs["current_itinerary"], request.current_itinerary)
        self.assertEqual(inputs["revision_request"], request.revision_request)
        self.assertEqual(inputs["revision_context"], request.revision_context)
        self.assertEqual(chunks[-1], "data: [DONE]\n\n")
        self.assertEqual(json.loads(chunks[-2][6:])["content"], "Revised full itinerary")

    async def test_existing_plan_uses_editor_instead_of_new_trip_research(self):
        inputs = {"game": "Game", "date": "October 10, 2026", "origin": "Local", "budget": 800,
                  "current_itinerary": "Original plan", "revision_request": "Cheaper hotel"}
        crew = TravelCrew(inputs)
        with patch.object(crew, "_revise", new_callable=AsyncMock, return_value="Updated") as revise, \
             patch.object(crew, "ticket_agent") as tickets:
            self.assertEqual(await crew.run(), "Updated")
        revise.assert_awaited_once()
        tickets.assert_not_called()

    async def test_stream_failure_does_not_emit_success_marker(self):
        request = ItineraryRequest(event="Game", date="October 10, 2026", departure_city="Local", budget=800)
        with patch("app.TravelCrew") as crew, self.assertLogs("app", level="ERROR"):
            crew.return_value.run = AsyncMock(side_effect=RuntimeError("Unavailable"))
            response = await generate_itinerary_stream(request)
            chunks = [chunk async for chunk in response.body_iterator]
        self.assertNotIn("data: [DONE]\n\n", chunks)
        self.assertEqual(json.loads(chunks[-1][6:])["type"], "error")


if __name__ == "__main__":
    unittest.main()
