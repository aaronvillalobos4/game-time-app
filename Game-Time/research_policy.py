"""Request-scoped research permissions, independent of conversation wording."""
import math
from typing import Literal
from budget_gate import BUDGET_QUESTION

ResearchPurpose = Literal["event_schedule", "event_details", "travel_information",
                          "tickets", "flights", "hotels", "trip_extras"]
BOOKING_PURPOSES = {"tickets", "flights", "hotels", "trip_extras"}
PURPOSES = BOOKING_PURPOSES | {"event_schedule", "event_details", "travel_information"}


def run_research(query, purpose, budget, search):
    if purpose not in PURPOSES:
        raise ValueError("Unsupported research purpose")
    if purpose in BOOKING_PURPOSES and (
            isinstance(budget, bool) or not isinstance(budget, (int, float))
            or not math.isfinite(budget) or budget <= 0):
        return BUDGET_QUESTION
    return search(query, monetize=purpose in BOOKING_PURPOSES)
