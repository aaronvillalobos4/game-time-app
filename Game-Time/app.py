import json
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Import your CrewAI setup/crew module here
# Import your actual Crew class:
from crew import GameTimeCrew

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

@app.post("/api/itinerary-stream")
@app.post("/generate-itinerary")
async def generate_itinerary_stream(req: ItineraryRequest):
    """Executes CrewAI agents and streams live status updates & token results."""
    async def event_generator():
        # 1. Send initial status message
        yield f"data: {json.dumps({'type': 'status', 'content': 'Scouting ticket prices & stadium sections...'})}\n\n"
        await asyncio.sleep(2) # Give UI time to render status

        # 2. Update status for flight/hotel search
        yield f"data: {json.dumps({'type': 'status', 'content': 'Searching flight routes & accommodation...'})}\n\n"
        
        # 3. Kick off your CrewAI Kickoff task
        inputs = {
            'event': req.event,
            'date': req.date,
            'departure_city': req.departure_city,
            'budget': str(req.budget)
        }
        
        # Run synchronous CrewAI kickoff in an async thread pool
        # result = await asyncio.to_thread(GameTimeCrew().crew().kickoff, inputs=inputs)
        # result_text = str(result)

        # 4. Final status update before streaming output
        yield f"data: {json.dumps({'type': 'status', 'content': 'Synthesizing your custom itinerary...'})}\n\n"
        await asyncio.sleep(1)

        # 5. Stream the CrewAI output tokens to frontend
        # (Replace `result_text` with your actual crew result)
        result_text = f"# Custom Itinerary for {req.event}\n\nDetailed breakdown..."
        for chunk in result_text.split(" "):
            yield f"data: {json.dumps({'type': 'token', 'content': chunk + ' '})}\n\n"
            await asyncio.sleep(0.02)
            
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