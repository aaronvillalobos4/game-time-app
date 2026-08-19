import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agents import TravelCrew

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