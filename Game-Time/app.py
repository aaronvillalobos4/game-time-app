import json
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Import your agent crew runner/function from agents.py
from agents import TravelCrew  # Adjust to match your function/class name in agents.py (e.g., GameTimeCrew)

app = FastAPI(redirect_slashes=True)

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

class ItineraryRequest(BaseModel):
    event: str
    date: str
    departure_city: str
    budget: float | int | str

class ChatPayload(BaseModel):
    messages: list = []
    currentItinerary: str | None = None

@app.get("/")
@app.head("/")
def read_root():
    return {"status": "Game Time API is running"}

@app.post("/api/itinerary-stream")
@app.post("/generate-itinerary")
async def generate_itinerary_stream(req: ItineraryRequest):
    """Executes CrewAI agents in a background thread while streaming real-time status & results."""
    async def event_generator():
        # 1. Send status updates to frontend while agents prepare
        yield f"data: {json.dumps({'type': 'status', 'content': 'Scouting ticket prices & stadium sections...'})}\n\n"
        await asyncio.sleep(1)

        yield f"data: {json.dumps({'type': 'status', 'content': 'Searching flight routes & travel schedules...'})}\n\n"
        await asyncio.sleep(1)

        yield f"data: {json.dumps({'type': 'status', 'content': 'Synthesizing custom itinerary & budget breakdown...'})}\n\n"

        # 2. Prepare inputs for your agents
        inputs = {
            'event': req.event,
            'date': req.date,
            'departure_city': req.departure_city,
            'budget': str(req.budget)
        }

        # 3. Execute agents asynchronously (prevents blocking the streaming thread)
        # Replace with your exact function or `GameTimeCrew().crew().kickoff(inputs=inputs)`
        result = await asyncio.to_thread(TravelCrew().crew().kickoff, inputs)
        result_text = str(result)

        # 4. Stream final agent token output to UI
        for word in result_text.split(" "):
            yield f"data: {json.dumps({'type': 'token', 'content': word + ' '})}\n\n"
            await asyncio.sleep(0.01)

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
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"}
    )