import os
import re
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any

# Import your CrewAI pipeline from agents.py
from agents import TravelCrew

app = FastAPI(title="Game Time API", version="1.0.0")

# Enable CORS for Next.js frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust to specific domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# PYDANTIC SCHEMAS
# ==========================================
class ChatParseRequest(BaseModel):
    message: str
    current_slots: Optional[Dict[str, Any]] = None

class ItineraryRequest(BaseModel):
    event: str
    date: str
    departure_city: str
    budget: float


# ==========================================
# 1. CONVERSATIONAL INTENT PARSER ENDPOINT
# ==========================================
@app.post("/api/parse-intent")
async def parse_intent(req: ChatParseRequest):
    text = req.message
    slots = req.current_slots or {
        "event": None, 
        "date": None, 
        "needs_flight": None,
        "departure_city": None, 
        "budget": None
    }

    # 1. Capture Event
    if not slots.get("event"):
        if len(text.strip()) > 2:
            slots["event"] = text.strip()

    # 2. Capture Date
    elif not slots.get("date"):
        date_match = re.search(
            r'(\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}(?:, \d{4})?|\d{1,2}/\d{1,2}(?:/\d{2,4})?)', 
            text, re.IGNORECASE
        )
        slots["date"] = date_match.group(1) if date_match else text.strip()

    # 3. Handle Flight Check (Yes/No or direct answer)
    elif slots.get("needs_flight") is None:
        lower_text = text.lower().strip()
        if any(neg in lower_text for neg in ["no", "local", "already there", "driving", "don't need"]):
            slots["needs_flight"] = False
            slots["departure_city"] = "Local"  # Set fallback for local trips
        elif any(pos in lower_text for pos in ["yes", "yep", "flying", "fly"]):
            slots["needs_flight"] = True
        else:
            # If user directly answered with a city like "Austin, TX"
            slots["needs_flight"] = True
            slots["departure_city"] = text.strip()

    # 4. If user said YES to flying, capture Departure City
    elif slots.get("needs_flight") and not slots.get("departure_city"):
        # Clean conversational prefixes like "flying from" or "I am in"
        clean_city = re.sub(r'^(i am in|flying out of|departing from|from)\s*', '', text, flags=re.IGNORECASE).strip()
        slots["departure_city"] = clean_city

    # 5. Capture Budget
    elif not slots.get("budget"):
        budget_match = re.search(r'\$?(\d{3,5})', text)
        if budget_match:
            slots["budget"] = float(budget_match.group(1))

    # --- CONDITIONAL QUESTION QUEUE ---
    if not slots.get("event"):
        return {
            "is_complete": False, "slots": slots,
            "follow_up_question": "Welcome to Game Time! What game or sports matchup do you want to go see?"
        }

    if not slots.get("date"):
        return {
            "is_complete": False, "slots": slots,
            "follow_up_question": f"Awesome! What date is the {slots['event']} game?"
        }

    if slots.get("needs_flight") is None:
        return {
            "is_complete": False, "slots": slots,
            "follow_up_question": "Will you be needing flights for this trip?"
        }

    if slots.get("needs_flight") and not slots.get("departure_city"):
        return {
            "is_complete": False, "slots": slots,
            "follow_up_question": "Where will you be flying out from?"
        }

    if not slots.get("budget"):
        return {
            "is_complete": False, "slots": slots,
            "follow_up_question": f"What is your target total budget for this trip? e.g., $600"
        }

    # All slots complete!
    return {"is_complete": True, "slots": slots, "follow_up_question": None}


# ==========================================
# 2. CREWAI STREAMING ITINERARY ENDPOINT
# ==========================================
@app.post("/api/itinerary-stream")
async def generate_itinerary_stream(req: ItineraryRequest):
    inputs = {
        "game": req.event,
        "date": req.date,
        "origin": req.departure_city,
        "budget": req.budget
    }

    async def event_generator():
        try:
            crew_runner = TravelCrew(inputs)
            
            # Status Update 1
            yield f"data: {json.dumps({'type': 'status', 'content': '🎟️ Scouting available tickets on StubHub & SeatGeek...'})}\n\n"
            
            # Status Update 2
            yield f"data: {json.dumps({'type': 'status', 'content': '✈️ Searching flight options & airline schedules...'})}\n\n"
            
            # Status Update 3
            yield f"data: {json.dumps({'type': 'status', 'content': '🏨 Finding top-rated hotels near the venue...'})}\n\n"
            
            # Status Update 4
            yield f"data: {json.dumps({'type': 'status', 'content': '📋 Synthesizing full itinerary & cost breakdown...'})}\n\n"
            
            result = await crew_runner.run()
            yield f"data: {json.dumps({'type': 'token', 'content': str(result)})}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ==========================================
# HEALTH CHECK
# ==========================================
@app.get("/")
def read_root():
    return {"status": "Game Time Backend API Running"}