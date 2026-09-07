"""Validated conversation state shared by the API and sports-trip assistant."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TripSlots(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    event: str | None = Field(default=None, min_length=1, max_length=300)
    date: str | None = Field(default=None, min_length=1, max_length=100)
    needs_flight: bool | None = None
    departure_city: str | None = Field(default=None, min_length=1, max_length=200)
    budget: float | None = Field(default=None, gt=0, le=1_000_000, allow_inf_nan=False)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8_000)


class ChatParseRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1_000)
    current_slots: TripSlots = Field(default_factory=TripSlots)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)
    current_itinerary: str | None = Field(default=None, max_length=20_000)

    @model_validator(mode="after")
    def limit_history(self):
        if not self.message.strip():
            raise ValueError("Message cannot be blank")
        if sum(len(message.content) for message in self.history) > 40_000:
            raise ValueError("Conversation history is too long")
        return self


class AssistantTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reply: str = Field(min_length=1, max_length=8_000)
    slot_updates: TripSlots = Field(default_factory=TripSlots)
    build_itinerary: bool = False


def merge_slots(current: TripSlots, updates: TripSlots) -> TripSlots:
    """Apply confirmed changes without retaining a date for a different event."""
    values = current.model_dump()
    patch = updates.model_dump(exclude_none=True)
    if "event" in patch and patch["event"] != current.event:
        values["date"] = None
    if patch.get("needs_flight") is True and current.needs_flight is False:
        values["departure_city"] = None
    values.update(patch)
    if values["needs_flight"] is False:
        values["departure_city"] = "Local"
    elif values["departure_city"] == "Local":
        values["departure_city"] = None
    return TripSlots.model_validate(values)


def next_question(slots: TripSlots) -> str | None:
    """Server-side completeness check; normal conversational replies come from AI."""
    if not slots.event:
        return "Which game would you like to plan around?"
    if not slots.date:
        return "Which date would you like to attend?"
    if slots.needs_flight is None:
        return "Will you need flights for this trip?"
    if slots.needs_flight and not slots.departure_city:
        return "Where will you be flying from?"
    if slots.budget is None:
        return "What is your target total budget for this trip?"
    return None
