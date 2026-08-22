import json
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Import TravelCrew from agents.py
from agents import TravelCrew

app = FastAPI(redirect_slashes=True)

# ------------------------------------------------------------------
# CORS Setup
# ------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://www.game-time-bot.com",
        "https://game-time-bot.com",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------
# Request & Response Data Models
# ------------------------------------------------------------------
class ItineraryRequest(BaseModel):
    event: str
    date: str
    departure_city: str
    budget: float | int | str


class ChatPayload(BaseModel):
    messages: list = []
    currentItinerary: str | None = None


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------
@app.get("/")
@app.head("/")
def read_root():
    """Health check endpoint for Render service deployment verification."""
    return {"status": "Game Time API is running"}


@app.post("/api/itinerary-stream")
@app.post("/generate-itinerary")
async def generate_itinerary_stream(req: ItineraryRequest):
    """Executes TravelCrew agents and streams live status updates & final results."""
    async def event_generator():
        # 1. Send initial status updates to UI
        yield f"data: {json.dumps({'type': 'status', 'content': 'Scouting ticket prices & stadium sections...'})}\n\n"
        await asyncio.sleep(0.5)

        yield f"data: {json.dumps({'type': 'status', 'content': 'Searching flight routes & travel schedules...'})}\n\n"
        await asyncio.sleep(0.5)

        yield f"data: {json.dumps({'type': 'status', 'content': 'Locating highly-rated hotels near the venue...'})}\n\n"
        await asyncio.sleep(0.5)

        # 2. Map frontend inputs to TravelCrew dictionary keys
        inputs = {
            "game": req.event,
            "date": req.date,
            "origin": req.departure_city,
            "budget": str(req.budget),
        }

        # 3. Final status frame before running CrewAI pipeline
        yield f"data: {json.dumps({'type': 'status', 'content': 'Synthesizing custom itinerary with agents...'})}\n\n"
        await asyncio.sleep(0.5)

        try:
            # Instantiate TravelCrew and run crew.kickoff_async()
            crew_instance = TravelCrew(inputs=inputs)
            result = await crew_instance.run()
            result_text = str(result)
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'Agent execution failed: {str(e)}'})}\n\n"
            return

        # 4. Stream final synthesized itinerary output to UI
        for word in result_text.split(" "):
            yield f"data: {json.dumps({'type': 'token', 'content': word + ' '})}\n\n"
            await asyncio.sleep(0.01)

        # 5. Signal streaming completion
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.post("/api/chat")
async def chat_endpoint(payload: ChatPayload):
    """Refinement chat endpoint for AI SDK streaming responses."""
    user_message = ""
    if payload.messages:
        user_message = payload.messages[-1].get("content", "")

    async def generate_response():
        response_text = f"Updating itinerary based on request: '{user_message}'"
        for word in response_text.split():
            chunk = f"{word} "
            yield f"0:{json.dumps(chunk)}\n"

    return StreamingResponse(
        generate_response(),
        media_type="text/plain",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )