import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Enable redirect_slashes so /api/chat and /api/chat/ both work
app = FastAPI(redirect_slashes=True)

# Enable CORS for Next.js frontend and custom domain
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
# Request Models
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


@app.post("/generate-itinerary")
async def generate_itinerary(req: ItineraryRequest):
    """Primary endpoint for generating the initial itinerary."""
    # Insert your actual CrewAI / LLM itinerary generation execution here
    sample_itinerary = (
        f"Itinerary for {req.event} on {req.date}\n"
        f"Departing from: {req.departure_city}\n"
        f"Budget: ${req.budget}"
    )
    return {"itinerary": sample_itinerary}


@app.post("/api/chat")
async def chat_endpoint(payload: ChatPayload):
    """Streaming chat endpoint for refining existing itineraries via AI SDK v5."""
    user_message = ""
    if payload.messages:
        last_msg = payload.messages[-1]
        user_message = last_msg.get("content", "")

    async def generate_response():
        # Insert your actual CrewAI / LLM chat refinement execution here
        response_text = f"Updating itinerary based on request: '{user_message}'"

        # Format chunks matching AI SDK Stream Protocol (0:"<chunk>"\n)
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