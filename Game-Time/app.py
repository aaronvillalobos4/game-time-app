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
    """
    Extracts event, date, departure city, and budget slots from natural text.
    Returns follow-up questions for any missing slot.
    """
    text = req.message
    slots = req.current_slots or {
        "event": None, 
        "date": None, 
        "departure_city": None, 
        "budget": None
    }

    # Extract Budget (e.g., "$1200", "1200 budget", "under 800", "700 bucks")
    budget_match = re.search(r'\$?(\d{3,5})', text)
    if budget_match and not slots.get("budget"):
        try:
            slots["budget"] = float(budget_match.group(1))
        except ValueError:
            pass

    # Extract Date (e.g., "Sept 5", "09/05/2026", "September 5", "March 14")
    date_match = re.search(
        r'(\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}(?:, \d{4})?|\d{1,2}/\d{1,2}(?:/\d{2,4})?)', 
        text, 
        re.IGNORECASE
    )
    if date_match and not slots.get("date"):
        slots["date"] = date_match.group(1)

    # Extract Departure City (e.g., "from Austin, TX", "flying out of Houston", "leaving College Station")
    dep_match = re.search(
        r'(?:from|out of|leaving|departing)\s+([A-Za-z\s]+(?:,\s*[A-Za-z]{2})?)', 
        text, 
        re.IGNORECASE
    )
    if dep_match and not slots.get("departure_city"):
        slots["departure_city"] = dep_match.group(1).strip()

    # Extract Event/Matchup fallback if not yet set
    if not slots.get("event") and ("vs" in text.lower() or "@" in text or "game" in text.lower() or "bears" in text.lower() or "aggies" in text.lower()):
        # Remove budget, date, and location patterns to leave the game title
        clean_text = re.sub(
            r'(\$?(\d{3,5})|from\s+.*|out of\s+.*|on\s+.*|\d{1,2}/\d{1,2}(?:/\d{2,4})?)', 
            '', 
            text, 
            flags=re.IGNORECASE
        ).strip()
        slots["event"] = clean_text if clean_text else text

    # Check for missing slots in priority order
    missing = [k for k, v in slots.items() if v is None]

    if not missing:
        return {
            "is_complete": True, 
            "slots": slots, 
            "follow_up_question": None
        }

    # Dynamic follow-up questions
    questions = {
        "event": "Which game or sports matchup are you planning to see?",
        "date": f"What date is the {slots.get('event') or 'event'}?",
        "departure_city": "Where will you be flying or departing from?",
        "budget": "What is your target total budget for this trip?"
    }

    return {
        "is_complete": False,
        "slots": slots,
        "follow_up_question": questions[missing[0]]
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