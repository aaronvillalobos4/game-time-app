import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from pydantic import ValidationError
from itinerary import CostItem, ItineraryPlan, PlanStep, render_itinerary, parse_plan_output, itinerary_guardrail
from agents import TravelCrew

INPUTS = dict(game="Test game", date="2026-10-03", origin="Local", budget=1000)


def item(category, price, **kwargs):
    return CostItem(category=category, name=category.title(), basis="One traveler; fees included",
                    unit_low=price, unit_high=price, evidence="Test source", **kwargs)


def plan(costs=None):
    return ItineraryPlan(steps=[PlanStep(time="1 hour before start", activity="Arrive", details="Suggested buffer")],
        costs=costs if costs is not None else [item("tickets", 100), item("hotel", 200),
        item("transport", 20), item("food", 30), item("fees", 0)])


class BudgetTests(unittest.TestCase):
    def test_price_schema_uses_nullable_numbers_without_decimal_regex(self):
        properties = ItineraryPlan.model_json_schema()['$defs']['CostItem']['properties']
        for field in ('unit_low', 'unit_high'):
            choices = properties[field]['anyOf']
            self.assertEqual({c['type'] for c in choices}, {'number', 'null'})
            self.assertTrue(all('pattern' not in c for c in choices))
        priced = item('tickets', '10.10', quantity=3)
        self.assertIsInstance(priced.unit_low, Decimal)
        self.assertEqual(priced.unit_low * priced.quantity, Decimal('30.30'))

    def test_fenced_and_json_dict_output_are_validated(self):
        data = plan()
        for output in (SimpleNamespace(raw='```json\n' + data.model_dump_json() + '\n```'),
                       SimpleNamespace(json_dict=data.model_dump(mode='json'))):
            self.assertEqual(parse_plan_output(output), data)
            self.assertTrue(itinerary_guardrail(output)[0])

    def test_invalid_selection_requests_repair_not_unchecked_rendering(self):
        data = plan().model_dump(mode='json')
        data['costs'].append(data['costs'][1].copy())
        valid, feedback = itinerary_guardrail(SimpleNamespace(json_dict=data))
        self.assertFalse(valid)
        self.assertIn('Select only one hotel', feedback)
        self.assertIn('Never invent prices', feedback)
        data['costs'][-1]['selected'] = False
        self.assertTrue(itinerary_guardrail(SimpleNamespace(json_dict=data))[0])

    def test_decimal_quantity_ranges_and_alternatives(self):
        data = plan()
        data.costs[0] = item("tickets", "10.10", quantity=3)
        data.costs[1] = item("hotel", 100, quantity=2)
        data.costs[1].unit_high = Decimal("125")
        data.costs.append(item("hotel", 900, selected=False))
        text = render_itinerary(data, INPUTS)
        self.assertIn("**Estimated total:** $280.30–$330.30", text)
        self.assertIn("**Remaining budget:** $669.70", text)
        self.assertIn("Alternative", text)

    def test_unknown_and_missing_essentials_do_not_claim_budget_fit(self):
        for data in (plan([item("tickets", 100)]), plan()):
            if len(data.costs) > 1:
                data.costs[1] = item("hotel", None)
            text = render_itinerary(data, INPUTS)
            self.assertIn("Known-cost subtotal", text)
            self.assertNotIn("**Remaining budget:**", text)
            self.assertIn("Budget fit cannot be confirmed", text)

    def test_foreign_currency_is_displayed_but_not_summed_as_dollars(self):
        data = plan(); data.costs[1] = item("hotel", 200, currency="EUR")
        text = render_itinerary(data, INPUTS)
        self.assertIn("EUR 200.00", text)
        self.assertIn("subtotal (USD only):** $150.00", text)

    def test_extras_use_combined_upper_bound_and_leave_buffer(self):
        data = plan()
        data.costs += [item("activity", 400, selected=False, optional=True),
                       item("food", 300, selected=False, optional=True)]
        text = render_itinerary(data, INPUTS)
        self.assertNotIn("Make It a Weekend", text)
        data.costs.pop()
        text = render_itinerary(data, INPUTS)
        self.assertIn("**Estimated total with extras:** $750.00", text)
        self.assertIn("**Budget left with extras:** $250.00", text)
        self.assertIn("**Estimated total:** $350.00", text)

    def test_paid_extras_hidden_when_essential_unknown(self):
        data = plan([item("tickets", None), item("activity", 10, selected=False, optional=True)])
        self.assertNotIn("Make It a Weekend", render_itinerary(data, INPUTS))

    def test_flight_requirement_and_local_omission(self):
        data = plan(); data.costs.append(item("flights", 250))
        self.assertIn("**Estimated total:** $350.00", render_itinerary(data, INPUTS))
        self.assertIn("**Estimated total:** $600.00", render_itinerary(data, dict(INPUTS, origin="Austin")))
        self.assertIn("Budget fit cannot be confirmed", render_itinerary(plan(), dict(INPUTS, origin="Austin")))

    def test_over_budget_uses_upper_bound(self):
        text = render_itinerary(plan(), dict(INPUTS, budget=300))
        self.assertIn("**Over budget:** $50.00", text)

    def test_invalid_prices_and_duplicate_selected_options_rejected(self):
        for price in (-1, "NaN", "Infinity", "1.234"):
            with self.assertRaises(ValidationError): item("hotel", price)
        with self.assertRaises(ValidationError):
            CostItem(category="hotel", name="Hotel", basis="night", evidence="source", unit_low=200, unit_high=100)
        with self.assertRaises(ValidationError): item("hotel", 10, optional=True)
        with self.assertRaises(ValidationError): plan([item("hotel", 100), item("hotel", 200)])
        with self.assertRaises(ValidationError): item("hotel", 10, booking_url="javascript:alert(1)")

    def test_booking_query_preserved(self):
        data = plan(); data.costs[1].booking_url = "https://www.klook.com/hotels/detail/123/?a=1&b=2"
        data.costs[1].provider = "Klook"
        self.assertIn("[Klook](<https://www.klook.com/hotels/detail/123/?a=1&b=2>)", render_itinerary(data, INPUTS))


class CrewTests(unittest.IsolatedAsyncioTestCase):
    async def test_build_and_revision_use_same_schema_and_renderer(self):
        for extra in ({}, {"current_itinerary": "Old itinerary", "revision_request": "Change budget"}):
            with patch("agents.Crew") as crew, patch("agents.with_hotel_booking_link", side_effect=lambda s: s):
                crew.return_value.kickoff_async = AsyncMock(return_value=SimpleNamespace(pydantic=plan()))
                result = await TravelCrew(dict(INPUTS, **extra)).run()
                task = crew.call_args.kwargs["tasks"][-1]
                self.assertIs(task.output_pydantic, ItineraryPlan)
                self.assertIs(task.guardrail, itinerary_guardrail)
                self.assertEqual(task.guardrail_max_retries, 2)
                self.assertIn("**Estimated total:** $350.00", result)

    async def test_invalid_raw_output_fails_instead_of_rendering_unverified_total(self):
        with patch("agents.Crew") as crew:
            crew.return_value.kickoff_async = AsyncMock(return_value=SimpleNamespace(pydantic=None, raw="Total: $1"))
            with self.assertRaises(ValidationError): await TravelCrew(INPUTS).run()

    async def test_nonfinite_budget_rejected_before_research(self):
        for budget in (float("nan"), float("inf")):
            with patch("agents.Crew") as crew:
                with self.assertRaises(ValueError): await TravelCrew(dict(INPUTS, budget=budget)).run()
                crew.assert_not_called()
