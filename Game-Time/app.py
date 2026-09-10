"""FastAPI application for the Game Time conversational trip planner."""

import json
import asyncio
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from agents import TravelCrew, answer_trip_message, evaluate_user_intent
from conversation import ChatParseRequest, TripSlots, merge_slots, next_question
from affiliate_links import with_hotel_booking_link


logger = logging.getLogger(__name__)

ALLOWED_ORIGINS = [
    "https://game-time-bot.com",
    "https://www.game-time-bot.com",
    "http://localhost:3000",
]


class ItineraryRequest(BaseModel):
    event: str = Field(min_length=1, max_length=300)
    date: str = Field(min_length=1, max_length=100)
    departure_city: str = Field(min_length=1, max_length=200)
    budget: float = Field(gt=0, le=1_000_000)
    current_itinerary: str | None = Field(default=None, max_length=20_000)
    revision_request: str | None = Field(default=None, max_length=1_000)
    revision_context: str | None = Field(default=None, max_length=40_000)


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


@app.post("/api/parse-intent")
async def parse_intent(request: ChatParseRequest) -> dict[str, object]:
    """Answer a trip question or apply confirmed details from the conversation."""
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

    try:
        turn = await asyncio.wait_for(answer_trip_message(request), timeout=90)
        slots = merge_slots(request.current_slots, turn.slot_updates)
    except Exception:
        logger.exception("Sports trip assistant failed")
        return {
            "is_reset": False,
            "is_complete": False,
            "slots": request.current_slots.model_dump(),
            "follow_up_question": (
                "I couldn't answer that right now. Your trip details are saved; "
                "please try your question again."
            ),
        }

    missing_question = next_question(slots)
    complete = turn.build_itinerary and missing_question is None
    reply = await asyncio.to_thread(with_hotel_booking_link, turn.reply, turn.suggests_hotels)
    if turn.build_itinerary and missing_question:
        reply = f"{reply}\n\nBefore I can build your itinerary: {missing_question}"
    elif missing_question is None and not complete and slots != request.current_slots:
        reply += "\n\nWould you like me to build your itinerary with these details?"
    return {
        "is_reset": False,
        "is_complete": complete,
        "slots": slots.model_dump(),
        "follow_up_question": reply,
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
        "current_itinerary": request.current_itinerary,
        "revision_request": request.revision_request,
        "revision_context": request.revision_context,
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
