"""FastAPI application for the Game Time conversational trip planner."""

import json
import logging
import re
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from agents import TravelCrew, evaluate_user_intent


logger = logging.getLogger(__name__)

ALLOWED_ORIGINS = [
    "https://game-time-bot.com",
    "https://www.game-time-bot.com",
    "http://localhost:3000",
]

DATE_PATTERN = re.compile(
    r"\b(?:"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"
    r"\s+\d{1,2}(?:,?\s+\d{4})?"
    r"|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?"
    r")\b",
    re.IGNORECASE,
)
MONEY_PATTERN = re.compile(
    r"(?:\$\s*|\bbudget(?:\s+(?:is|of))?\s*)"
    r"(?P<amount>\d[\d,]*(?:\.\d{1,2})?)\b",
    re.IGNORECASE,
)
BARE_MONEY_PATTERN = re.compile(r"^\s*(?P<amount>\d[\d,]*(?:\.\d{1,2})?)\s*$")
ORIGIN_PATTERN = re.compile(
    r"\b(?:flying\s+out\s+of|departing\s+from|flying\s+from|from)\s+"
    r"(?P<origin>[A-Za-z][A-Za-z .'-]*?)"
    r"(?=\s+(?:on|for|with|under|budget)\b|[,;]|$)",
    re.IGNORECASE,
)
NO_FLIGHT_PATTERN = re.compile(
    r"\b(?:no|local|driving|drive|already\s+there|do(?:n't|\s+not)\s+need\s+flights?)\b",
    re.IGNORECASE,
)
YES_FLIGHT_PATTERN = re.compile(
    r"\b(?:yes|yep|yeah|flying|fly|need\s+flights?)\b",
    re.IGNORECASE,
)


class TripSlots(BaseModel):
    """Conversation fields collected before itinerary generation."""

    event: str | None = None
    date: str | None = None
    needs_flight: bool | None = None
    departure_city: str | None = None
    budget: float | None = Field(default=None, gt=0)


class ChatParseRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1_000)
    current_slots: TripSlots = Field(default_factory=TripSlots)


class ItineraryRequest(BaseModel):
    event: str = Field(min_length=1, max_length=300)
    date: str = Field(min_length=1, max_length=100)
    departure_city: str = Field(min_length=1, max_length=200)
    budget: float = Field(gt=0, le=1_000_000)


app = FastAPI(title="Game Time API", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "HEAD", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log unexpected failures without exposing server internals to clients."""
    logger.exception("Unhandled error for %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred."},
    )


def _parse_amount(match: re.Match[str]) -> float:
    return float(match.group("amount").replace(",", ""))


def _looks_like_standalone_answer(text: str) -> bool:
    """Return True when text is clearly a non-event answer."""
    return bool(
        DATE_PATTERN.fullmatch(text)
        or MONEY_PATTERN.fullmatch(text)
        or BARE_MONEY_PATTERN.fullmatch(text)
        or NO_FLIGHT_PATTERN.fullmatch(text)
        or YES_FLIGHT_PATTERN.fullmatch(text)
    )


def _event_candidate(text: str) -> str:
    """Remove recognizable travel/budget clauses from an initial event request."""
    candidate = MONEY_PATTERN.sub("", text)
    candidate = re.sub(
        r"\b(?:with|under)\s*(?:a\s+)?(?:total\s+)?(?:budget)?\s*$",
        "",
        candidate,
        flags=re.IGNORECASE,
    )
    candidate = DATE_PATTERN.sub("", candidate)
    candidate = re.sub(r"\b(?:on|for)\s*$", "", candidate, flags=re.IGNORECASE)
    candidate = ORIGIN_PATTERN.sub("", candidate)
    candidate = re.sub(
        r"\b(?:and\s+)?(?:i(?:'m|\s+am)\s+)?"
        r"(?:flying|need\s+flights?|(?:yes|no),?\s*(?:i\s+)?(?:need\s+)?flights?|"
        r"do(?:n't|\s+not)\s+need\s+flights?)\s*$",
        "",
        candidate,
        flags=re.IGNORECASE,
    )
    candidate = re.sub(r"\b(?:on|for)\s*$", "", candidate, flags=re.IGNORECASE)
    return candidate.strip(" ,.;-")


def update_slots(message: str, current: TripSlots) -> TripSlots:
    """Extract every recognizable field without discarding prior values."""
    text = message.strip()
    slots = current.model_copy(deep=True)

    date_match = DATE_PATTERN.search(text)
    if date_match:
        slots.date = date_match.group(0).strip()

    money_match = MONEY_PATTERN.search(text)
    awaiting_budget = all(
        (
            slots.event,
            slots.date,
            slots.needs_flight is not None,
            slots.departure_city,
        )
    )
    if not money_match and awaiting_budget:
        money_match = BARE_MONEY_PATTERN.fullmatch(text)
    if money_match:
        slots.budget = _parse_amount(money_match)

    origin_match = ORIGIN_PATTERN.search(text)
    if origin_match:
        slots.departure_city = origin_match.group("origin").strip(" ,.;")
        slots.needs_flight = True

    if slots.needs_flight is None:
        if NO_FLIGHT_PATTERN.search(text):
            slots.needs_flight = False
            slots.departure_city = "Local"
        elif YES_FLIGHT_PATTERN.search(text):
            slots.needs_flight = True
        elif slots.event and slots.date and not date_match and not money_match:
            # A city is also a valid direct response to the flight question.
            city = re.sub(
                r"^(?:i\s+am\s+in|flying\s+out\s+of|departing\s+from|from)\s+",
                "",
                text,
                flags=re.IGNORECASE,
            ).strip(" ,.;")
            if city:
                slots.needs_flight = True
                slots.departure_city = city

    if slots.needs_flight and not slots.departure_city:
        # Capture a plain city after the user has already answered "yes".
        if current.needs_flight is True and not date_match and not money_match:
            city = re.sub(
                r"^(?:i\s+am\s+in|flying\s+out\s+of|departing\s+from|from)\s+",
                "",
                text,
                flags=re.IGNORECASE,
            ).strip(" ,.;")
            if city and not YES_FLIGHT_PATTERN.fullmatch(city):
                slots.departure_city = city

    if not slots.event and not _looks_like_standalone_answer(text):
        candidate = _event_candidate(text)
        if len(candidate) >= 3:
            slots.event = candidate

    if slots.needs_flight is False:
        slots.departure_city = "Local"

    return slots


def next_question(slots: TripSlots) -> str | None:
    """Return the next required question, or None when the trip is complete."""
    if not slots.event:
        return "Welcome to Game Time! What game or sports matchup do you want to see?"
    if not slots.date:
        return f"Awesome! What date is the {slots.event} game?"
    if slots.needs_flight is None:
        return "Will you need flights for this trip?"
    if slots.needs_flight and not slots.departure_city:
        return "Where will you be flying from?"
    if slots.budget is None:
        return "What is your target total budget for this trip? For example, $600."
    return None


@app.post("/api/parse-intent")
async def parse_intent(request: ChatParseRequest) -> dict[str, object]:
    """Update conversation slots and return either a question or completion."""
    text = request.message.strip()
    intent = evaluate_user_intent(text)
    if intent["is_reset"]:
        return {
            "is_reset": True,
            "is_complete": False,
            "slots": TripSlots().model_dump(),
            "follow_up_question": (
                "No problem! Let's start fresh. What game do you want to see?"
            ),
        }

    slots = update_slots(text, request.current_slots)
    question = next_question(slots)
    return {
        "is_reset": False,
        "is_complete": question is None,
        "slots": slots.model_dump(),
        "follow_up_question": question,
    }


def _sse_event(event_type: str, content: str) -> str:
    payload = json.dumps({"type": event_type, "content": content})
    return f"data: {payload}\n\n"


@app.post("/api/itinerary-stream")
async def generate_itinerary_stream(request: ItineraryRequest) -> StreamingResponse:
    """Run the planning crew and deliver status/result messages over SSE."""
    inputs = {
        "game": request.event.strip(),
        "date": request.date.strip(),
        "origin": request.departure_city.strip(),
        "budget": request.budget,
    }

    async def event_generator() -> AsyncIterator[str]:
        yield _sse_event(
            "status",
            "🎟️ Scouting tickets, hotels, and flight itineraries...",
        )
        try:
            result = await TravelCrew(inputs).run()
        except Exception:
            logger.exception("Itinerary crew failed")
            yield _sse_event(
                "error",
                "We couldn't build the itinerary right now. Please try again.",
            )
            return

        yield _sse_event("token", result)
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@app.api_route("/", methods=["GET", "HEAD"])
async def health_check() -> dict[str, str]:
    return {"status": "Game Time Backend API Running"}
