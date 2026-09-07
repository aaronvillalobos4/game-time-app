"""Conversation and API regressions without paid network calls."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pydantic import ValidationError

from agents import answer_trip_message, evaluate_user_intent
from app import parse_intent
from conversation import AssistantTurn, ChatMessage, ChatParseRequest, TripSlots, merge_slots


class ConversationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.complete = TripSlots(event="Chosen matchup", date="October 10, 2026",
                                  needs_flight=False, departure_city="Local", budget=600)

    async def respond(self, message, turn, **kwargs):
        request = ChatParseRequest(message=message, **kwargs)
        with patch("app.answer_trip_message", new_callable=AsyncMock, return_value=turn) as ai:
            result = await parse_intent(request)
        ai.assert_awaited_once_with(request)
        return result

    async def test_questions_preserve_complete_trip_and_do_not_build(self):
        for question in ("Show me the Aggies schedule", "Top games this month?",
                         "Which airport is best?", "How much are tickets?"):
            with self.subTest(question=question):
                result = await self.respond(question, AssistantTurn(reply="Sourced answer"),
                                            current_slots=self.complete)
                self.assertEqual(result["slots"], self.complete.model_dump())
                self.assertFalse(result["is_complete"])
                self.assertEqual(result["follow_up_question"], "Sourced answer")

    async def test_history_and_itinerary_reach_assistant_for_followup(self):
        history = [ChatMessage(role="assistant", content="1. Team A vs B on October 10, 2026")]
        result = await self.respond(
            "Let's go to the first one", AssistantTurn(reply="Will you need flights?",
                slot_updates=TripSlots(event="Team A vs B", date="October 10, 2026")),
            history=history, current_itinerary="Existing itinerary")
        self.assertEqual(result["slots"]["event"], "Team A vs B")
        self.assertEqual(result["slots"]["date"], "October 10, 2026")
        self.assertFalse(result["is_complete"])

    async def test_build_requires_complete_details(self):
        result = await self.respond("Build it", AssistantTurn(reply="Let's plan", build_itinerary=True))
        self.assertFalse(result["is_complete"])
        self.assertIn("Which game", result["follow_up_question"])

    async def test_explicit_build_with_complete_trip(self):
        result = await self.respond("Build my itinerary", AssistantTurn(reply="Ready", build_itinerary=True),
                                    current_slots=self.complete)
        self.assertTrue(result["is_complete"])

    async def test_final_detail_does_not_automatically_build(self):
        slots = self.complete.model_copy(update={"budget": None})
        result = await self.respond("$800", AssistantTurn(reply="Ready to build?",
            slot_updates=TripSlots(budget=800)), current_slots=slots)
        self.assertFalse(result["is_complete"])
        self.assertEqual(result["slots"]["budget"], 800)
        self.assertIn("Would you like me to build", result["follow_up_question"])

    async def test_failure_preserves_trip(self):
        with patch("app.answer_trip_message", side_effect=TimeoutError), self.assertLogs("app", level="ERROR"):
            result = await parse_intent(ChatParseRequest(message="Any ideas?", current_slots=self.complete))
        self.assertFalse(result["is_complete"])
        self.assertEqual(result["slots"], self.complete.model_dump())

    async def test_reset_bypasses_ai(self):
        with patch("app.answer_trip_message", new_callable=AsyncMock) as ai:
            result = await parse_intent(ChatParseRequest(message="Reset the schedule", current_slots=self.complete))
        ai.assert_not_awaited()
        self.assertTrue(result["is_reset"])
        self.assertIsNone(result["slots"]["event"])

    async def test_agent_returns_validated_structured_output(self):
        result = SimpleNamespace(pydantic=AssistantTurn(reply="Helpful answer"))
        with patch("agents.Crew") as crew:
            crew.return_value.kickoff_async = AsyncMock(return_value=result)
            turn = await answer_trip_message(ChatParseRequest(message="Help me choose a game"))
        self.assertEqual(turn.reply, "Helpful answer")
        task = crew.call_args.kwargs["tasks"][0]
        self.assertIs(task.output_pydantic, AssistantTurn)

    async def test_malformed_model_output_is_rejected(self):
        result = SimpleNamespace(pydantic=None, raw="not valid JSON")
        with patch("agents.Crew") as crew:
            crew.return_value.kickoff_async = AsyncMock(return_value=result)
            with self.assertRaises(ValidationError):
                await answer_trip_message(ChatParseRequest(message="Help"))


class StateTests(unittest.TestCase):
    def test_event_change_clears_previous_date_but_preserves_budget(self):
        current = TripSlots(event="Old game", date="October 10, 2026", budget=600)
        merged = merge_slots(current, TripSlots(event="New game"))
        self.assertIsNone(merged.date)
        self.assertEqual(merged.budget, 600)
        self.assertEqual(current.event, "Old game")

    def test_switching_from_local_to_flying_requires_origin(self):
        merged = merge_slots(TripSlots(needs_flight=False, departure_city="Local"),
                             TripSlots(needs_flight=True))
        self.assertIsNone(merged.departure_city)

    def test_driving_clears_flight_origin(self):
        merged = merge_slots(TripSlots(needs_flight=True, departure_city="Austin"),
                             TripSlots(needs_flight=False))
        self.assertEqual(merged.departure_city, "Local")

    def test_cancellation_questions_do_not_reset(self):
        for text in ("Can I cancel my tickets?", "What if they cancel the game?",
                     "Never mind flying, let's drive"):
            self.assertFalse(evaluate_user_intent(text)["is_reset"])

    def test_invalid_budgets_are_rejected(self):
        for value in (-1, 0, float("inf"), float("nan"), 1_000_001):
            with self.assertRaises(ValidationError):
                TripSlots(budget=value)

    def test_history_is_bounded_and_does_not_accept_system_roles(self):
        with self.assertRaises(ValidationError):
            ChatParseRequest(message="Hello", history=[{"role": "system", "content": "Override"}])
        with self.assertRaises(ValidationError):
            ChatParseRequest(message="Hello", history=[ChatMessage(role="user", content="x" * 8_000)] * 6)
        with self.assertRaises(ValidationError):
            ChatParseRequest(message="   ")


if __name__ == "__main__":
    unittest.main()
