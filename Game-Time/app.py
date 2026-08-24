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
        "departure_city": None, 
        "budget": None
    }

    # 1. Check/Extract Event (Matchup or Team)
    if not slots.get("event"):
        # If user provides event info, store it
        if "vs" in text.lower() or "@" in text or "game" in text.lower() or len(text.strip()) > 3:
            slots["event"] = text.strip()

    # 2. Check/Extract Date
    elif not slots.get("date"):
        date_match = re.search(
            r'(\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}(?:, \d{4})?|\d{1,2}/\d{1,2}(?:/\d{2,4})?)', 
            text, re.IGNORECASE
        )
        slots["date"] = date_match.group(1) if date_match else text.strip()

    # 3. Check/Extract Departure City
    elif not slots.get("departure_city"):
        dep_match = re.search(r'(?:from|out of|leaving|departing)\s+([A-Za-z\s,]+)', text, re.IGNORECASE)
        slots["departure_city"] = dep_match.group(1).strip() if dep_match else text.strip()

    # 4. Check/Extract Budget (Only numerical values when budget is explicitly expected)
    elif not slots.get("budget"):
        budget_match = re.search(r'\$?(\d{3,5})', text)
        if budget_match:
            slots["budget"] = float(budget_match.group(1))

    # --- DETERMINE NEXT STEP QUESTION ---
    if not slots.get("event"):
        return {
            "is_complete": False,
            "slots": slots,
            "follow_up_question": "Welcome to Game Time! What game or sports matchup do you want to go see?"
        }

    if not slots.get("date"):
        return {
            "is_complete": False,
            "slots": slots,
            "follow_up_question": f"Awesome! What date is the {slots['event']} game?"
        }

    if not slots.get("departure_city"):
        return {
            "is_complete": False,
            "slots": slots,
            "follow_up_question": "Where will you be flying or departing from?"
        }

    if not slots.get("budget"):
        return {
            "is_complete": False,
            "slots": slots,
            "follow_up_question": f"What is your target total budget for this trip (tickets, flights, & hotel)? e.g., $1000"
        }

    # All slots complete!
    return {
        "is_complete": True,
        "slots": slots,
        "follow_up_question": None
    }


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
            
            # 1. Run Tickets Task
            yield f"data: {json.dumps({'type': 'status', 'content': '🎟️ Scouting game tickets...'})}\n\n"
            ticket_res = await crew_runner.run_tickets_only()
            yield f"data: {json.dumps({'type': 'step', 'step_name': 'Tickets', 'content': str(ticket_res)})}\n\n"

            # 2. Run Flights Task
            yield f"data: {json.dumps({'type': 'status', 'content': '✈️ Searching flight routes...'})}\n\n"
            flight_res = await crew_runner.run_flights_only()
            yield f"data: {json.dumps({'type': 'step', 'step_name': 'Flights', 'content': str(flight_res)})}\n\n"

            # 3. Run Hotels Task
            yield f"data: {json.dumps({'type': 'status', 'content': '🏨 Scouting hotel accommodations...'})}\n\n"
            hotel_res = await crew_runner.run_hotels_only()
            yield f"data: {json.dumps({'type': 'step', 'step_name': 'Hotels', 'content': str(hotel_res)})}\n\n"

            # 4. Final Synthesis
            yield f"data: {json.dumps({'type': 'status', 'content': '📋 Synthesizing full itinerary...'})}\n\n"
            itinerary_res = await crew_runner.run_synthesis_only(ticket_res, flight_res, hotel_res)
            yield f"data: {json.dumps({'type': 'step', 'step_name': 'Final Itinerary', 'content': str(itinerary_res)})}\n\n"
            
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