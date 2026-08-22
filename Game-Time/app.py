import os
import json
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import AsyncOpenAI

# Import TravelCrew from agents.py
from agents import TravelCrew

app = FastAPI(redirect_slashes=True)

# ------------------------------------------------------------------
# CORS Setup
# ------------------------------------------------------------------
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

# Initialize OpenAI Client
client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


# ------------------------------------------------------------------
# Request Data Models
# ------------------------------------------------------------------
class ItineraryRequest(BaseModel):
    event: str
    date: str
    departure_city: str
    budget: float | int | str


class ChatPayload(BaseModel):
    messages: list[dict] = []
    currentItinerary: str | None = None

    class Config:
        extra = "allow"


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------
@app.get("/")
@app.head("/")
def read_root():
    """Health check endpoint for Render service deployment verification."""
    return {"status": "Game Time API is running"}


@app.post("/api/itinerary-stream")
@app.post("/generate-itinerary")
async def generate_itinerary_stream(req: ItineraryRequest):
    """Executes TravelCrew agents and streams live status updates & final results."""
    async def event_generator():
        yield f"data: {json.dumps({'type': 'status', 'content': 'Scouting ticket prices & stadium sections...'})}\n\n"
        await asyncio.sleep(0.5)

        yield f"data: {json.dumps({'type': 'status', 'content': 'Searching flight routes & travel schedules...'})}\n\n"
        await asyncio.sleep(0.5)

        yield f"data: {json.dumps({'type': 'status', 'content': 'Locating highly-rated hotels near the venue...'})}\n\n"
        await asyncio.sleep(0.5)

        inputs = {
            "game": req.event,
            "date": req.date,
            "origin": req.departure_city,
            "budget": str(req.budget),
        }

        yield f"data: {json.dumps({'type': 'status', 'content': 'Synthesizing custom itinerary with agents...'})}\n\n"
        await asyncio.sleep(0.5)

        try:
            crew_instance = TravelCrew(inputs=inputs)
            result = await crew_instance.run()
            result_text = str(result)
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'Agent execution failed: {str(e)}'})}\n\n"
            return

        for word in result_text.split(" "):
            yield f"data: {json.dumps({'type': 'token', 'content': word + ' '})}\n\n"
            await asyncio.sleep(0.01)

        yield "data: [DONE]\n\n"

    from fastapi.responses import StreamingResponse
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
    """Refinement chat endpoint using standard non-streaming JSON."""
    
    system_prompt = (
        "You are an expert sports travel assistant for Game Time. "
        "Your task is to refine and modify the user's existing trip itinerary based on their questions or requested changes "
        "(e.g., swapping flight times, changing hotel tiers, adjusting budgets, or adding local spot recommendations). "
        "Keep responses clear, concise, and formatted in clean Markdown."
    )

    if payload.currentItinerary:
        system_prompt += f"\n\nCURRENT ITINERARY CONTEXT:\n{payload.currentItinerary}"

    formatted_messages = [{"role": "system", "content": system_prompt}]
    for msg in payload.messages:
        role = msg.get("role", "user") if isinstance(msg, dict) else getattr(msg, "role", "user")
        content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
        formatted_messages.append({"role": role, "content": content})

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=formatted_messages,
            stream=False,
        )
        reply = response.choices[0].message.content
        return {"role": "assistant", "content": reply}
    except Exception as e:
        return {"role": "assistant", "content": f"Error refining itinerary: {str(e)}"}