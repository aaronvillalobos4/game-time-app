import unittest
from unittest.mock import AsyncMock, patch
from budget_gate import BUDGET_QUESTION, budget_from_message, needs_budget
from conversation import ChatParseRequest, ChatMessage, AssistantTurn
from app import parse_intent, ItineraryRequest
from pydantic import ValidationError


class BudgetGateTests(unittest.IsolatedAsyncioTestCase):
    def test_information_is_not_booking_research(self):
        for message in ("Are tickets digital?", "What time is hotel checkout?",
                        "What does a refundable flight mean?", "When is their next game?"):
            self.assertFalse(needs_budget(message))
        for message in ("Find hotels", "Compare flights", "How much do tickets cost?",
                        "Build my itinerary", "Show ticket prices"):
            self.assertTrue(needs_budget(message))

    async def test_booking_research_waits_without_calling_agent(self):
        for message in ("Find hotels in Dallas", "Find flights to Dallas", "Show ticket prices", "Build my itinerary"):
            with patch('app.answer_trip_message', new_callable=AsyncMock) as agent:
                result = await parse_intent(ChatParseRequest(message=message))
            agent.assert_not_awaited()
            self.assertEqual(result['follow_up_question'], BUDGET_QUESTION)
            self.assertIsNone(result['slots']['budget'])

    async def test_sample_consent_is_saved_and_disclosed(self):
        request = ChatParseRequest(message='Yes please', history=[ChatMessage(role='assistant', content=BUDGET_QUESTION)])
        with patch('app.answer_trip_message', new_callable=AsyncMock, return_value=AssistantTurn(reply='Which game?')) as agent:
            result = await parse_intent(request)
        self.assertEqual(agent.call_args.args[0].current_slots.budget, 1500)
        self.assertEqual(result['slots']['budget'], 1500)
        self.assertIn('suggested **$1,500', result['follow_up_question'])

    def test_no_implicit_sample_or_quoted_price_as_budget(self):
        for message in ('yes', 'Hotel costs $200', 'Can you suggest a sample budget?', 'budget 0'):
            self.assertEqual(budget_from_message(ChatParseRequest(message=message)), (None, False))
        self.assertEqual(budget_from_message(ChatParseRequest(message='Find hotels, my budget is $900')), (900, False))

    def test_itinerary_endpoint_requires_budget(self):
        with self.assertRaises(ValidationError):
            ItineraryRequest(event='Game', date='2026-10-10', departure_city='Dallas')
