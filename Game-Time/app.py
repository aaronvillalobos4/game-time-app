import os
import re
import json
import asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any

# Import CrewAI pipeline and guardrail intent evaluator from agents.py
from agents import TravelCrew, evaluate_user_intent

app = FastAPI(title="Game Time API", version="1.0.0")

# Enable CORS for Next.js frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://www.game-time-bot.com",
        "https://game-time-bot.com",
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Guarantees CORS headers are sent back even when Python encounters a 500 error."""
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
        headers={"Access-Control-Allow-Origin": "*"}
    )

@app.options("/{full_path:path}")
async def options_handler(full_path: str):
    """
    Handles browser preflight OPTIONS requests directly to prevent 
    CORS errors on Render cold starts.
    """
    return {}


# ==========================================
# PYDANTIC SCHEMAS
# ==========================================
class ChatParseRequest(BaseModel):
    message: str
    current_slots: Optional[Dict[str, Any]] = None
    session_history: Optional[list] = []

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
    history = req.session_history or []
    
    # Check for Global Reset/Cancel Intent via Guardrail evaluator safely
    intent_check = evaluate_user_intent(text, history)
    
    # Safely evaluate string or dict output from intent evaluator
    is_reset = False
    if isinstance(intent_check, dict):
        is_reset = (intent_check.get("status") == "RESET")
    elif isinstance(intent_check, str):
        is_reset = ("RESET" in intent_check.upper())

    if is_reset:
        return {
            "is_reset": True,
            "is_complete": False,
            "slots": {
                "event": None, 
                "date": None, 
                "needs_flight": None,
                "departure_city": None, 
                "budget": None
            },
            "follow_up_question": "No problem! Let's start fresh. What game do you want to see?"
        }

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

    if not slots.get("departure_city"):
        slots["departure_city"] = "Local"

    if not slots.get("budget"):
        return {
            "is_complete": False, "slots": slots,
            "follow_up_question": "What is your target total budget for this trip? e.g., $600"
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
            
            # Initial Status Ping
            yield f"data: {json.dumps({'type': 'status', 'content': '🎟️ Scouting tickets, hotels, and flight itineraries...'})}\n\n"
            
            # Await Crew Execution
            result = await crew_runner.run()
            
            # Extract raw string output from CrewOutput object
            final_markdown = str(result.raw) if hasattr(result, 'raw') else str(result)
            
            # Stream payload back to UI
            yield f"data: {json.dumps({'type': 'token', 'content': final_markdown})}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Prevents Nginx/proxy response buffering
        }
    )


# ==========================================
# HEALTH CHECK
# ==========================================
@app.api_route("/", methods=["GET", "HEAD"])
def read_root():
    return {"status": "Game Time Backend API Running"}