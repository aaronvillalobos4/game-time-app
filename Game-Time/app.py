import os
import json
import asyncio
from typing import List, Dict, Any
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agents import TravelCrew

load_dotenv()

app = FastAPI(title="Game Time API", version="1.0.0")

# Enable CORS for Vercel front-end and local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to your specific Vercel URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- REQUEST SCHEMAS ---

class TripRequest(BaseModel):
    event: str
    date: str
    departure_city: str
    budget: str


class RefinementRequest(BaseModel):
    session_id: str = "default_session"
    messages: List[Dict[str, str]]  # [{'role': 'user', 'content': 'Change hotel to...'}, ...]
    current_itinerary: Dict[str, Any]  # Active itinerary state


# --- HELPER GENERATORS FOR SSE ---

async def stream_chat_updates(messages: List[Dict[str, str]], current_itinerary: Dict[str, Any]):
    """
    Yields real-time tokens/updates during multi-turn itinerary chat refinement.
    """
    user_instruction = messages[-1]["content"] if messages else ""

    # Initial status broadcast
    yield f"data: {json.dumps({'type': 'status', 'content': f'Updating itinerary based on: {user_instruction}'})}\n\n"
    await asyncio.sleep(0.5)

    # TODO: Connect your specific CrewAI/LangChain refinement agent here
    # Example token stream simulation:
    yield f"data: {json.dumps({'type': 'token', 'content': 'Processing your requested updates...'})}\n\n"
    
    yield "data: [DONE]\n\n"


async def stream_itinerary_generation(request: TripRequest):
    """
    Yields real-time step-by-step updates while TravelCrew executes.
    """
    yield f"data: {json.dumps({'type': 'status', 'content': 'Scouting ticket prices & stadium sections...'})}\n\n"
    await asyncio.sleep(1)

    session_data = {
        "game": request.event,
        "date": request.date,
        "origin": request.departure_city,
        "budget": request.budget,
    }

    try:
        planner = TravelCrew(inputs=session_data)
        
        # Execute crew planning logic
        # Note: If planner.run() is synchronous, run in executor or use loop
        if asyncio.iscoroutinefunction(planner.run):
            final_itinerary = await planner.run()
        else:
            final_itinerary = planner.run()

        yield f"data: {json.dumps({'type': 'token', 'content': str(final_itinerary)})}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"


# --- ROUTE ENDPOINTS ---

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "Game Time API"}


@app.post("/api/itinerary")
async def plan_trip(request: TripRequest):
    """
    Standard blocking JSON endpoint for custom itinerary generation.
    """
    try:
        session_data = {
            "game": request.event,
            "date": request.date,
            "origin": request.departure_city,
            "budget": request.budget,
        }

        planner = TravelCrew(inputs=session_data)

        # Handles both async and sync TravelCrew implementations gracefully
        if asyncio.iscoroutinefunction(planner.run):
            final_itinerary = await planner.run()
        else:
            final_itinerary = planner.run()

        return {"success": True, "itinerary": str(final_itinerary)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/itinerary-stream")
async def plan_trip_stream(request: TripRequest):
    """
    Streaming endpoint using SSE for initial itinerary generation.
    """
    return StreamingResponse(
        stream_itinerary_generation(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disables proxy buffering on Render/Nginx
        },
    )


@app.post("/api/chat")
async def chat_endpoint(request: RefinementRequest):
    """
    Interactive streaming endpoint for follow-up chat refinements.
    """
    return StreamingResponse(
        stream_chat_updates(request.messages, request.current_itinerary),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )