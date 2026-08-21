import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agents import TravelCrew
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any

load_dotenv()

app = FastAPI(title="Game Time API", version="1.0.0")

# Enable CORS for Vercel front-end and local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to your Vercel URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Updated Request Schema to match Next.js payload
class TripRequest(BaseModel):
    event: str
    date: str
    departure_city: str
    budget: str

#Chat Request Data Model capturing message history and active itinerary
class RefinementRequest(BaseModel):
    session_id: str
    messages: List[Dict[str, str]]  # [{'role': 'user', 'content': 'Change hotel to...'}, ...]
    current_itinerary: Dict[str, Any]  # The existing generated JSON/data state

async def stream_itinerary_updates(messages: List[Dict[str, str]], current_itinerary: Dict[str, Any]):
    user_instruction = messages[-1]["content"]
    
    # 1. Pass 'user_instruction' + 'current_itinerary' to your Refinement Agent
    # 2. Yield text tokens or updated JSON state as the agent processes
    yield f"data: Updating your itinerary based on: '{user_instruction}'...\n\n"
    
    # Example token yield...
    yield "data: [DONE]\n\n"

@app.post("/api/chat")
async def chat_endpoint(request: RefinementRequest):
    return StreamingResponse(
        stream_itinerary_updates(request.messages, request.current_itinerary),
        media_type="text/event-stream"
    )

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "Game Time API"}


# Updated Route Path to match fetch URL
@app.post("/api/itinerary")
async def plan_trip(request: TripRequest):
    try:
        session_data = {
            "game": request.event,
            "date": request.date,
            "origin": request.departure_city,
            "budget": request.budget,
        }

        # Run CrewAI agents
        planner = TravelCrew(inputs=session_data)
        
        # Check if TravelCrew.run() is async; if not, call: planner.run() directly
        final_itinerary = await planner.run()

        return {"success": True, "itinerary": str(final_itinerary)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))