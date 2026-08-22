import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(redirect_slashes=True)

# CORS Configuration
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
# Routes
# ------------------------------------------------------------------
@app.get("/")
@app.head("/")
def read_root():
    """Health check for Render service deployment."""
    return {"status": "Game Time API is running"}


@app.post("/api/itinerary-stream")
@app.post("/generate-itinerary")
async def generate_itinerary_stream(req: ItineraryRequest):
    """Handles the form submission with Server-Sent Events (SSE) streaming."""
    async def event_generator():
        # 1. Send status updates
        yield f"data: {json.dumps({'type': 'status', 'content': 'Scouting flights and hotels...'})}\n\n"
        
        # 2. Stream itinerary content tokens
        sample_itinerary = (
            f"# Custom Itinerary for {req.event}\n\n"
            f"- **Date:** {req.date}\n"
            f"- **Departure:** {req.departure_city}\n"
            f"- **Budget:** ${req.budget}\n\n"
            f"### Flight & Hotel Details\n"
            f"Here are the top options scouted for your trip..."
        )
        
        for word in sample_itinerary.split():
            token_payload = json.dumps({'type': 'token', 'content': f"{word} "})
            yield f"data: {token_payload}\n\n"
            
        # 3. Stream completion signal
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
    """Handles refinement chat messages."""
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