import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI()

# Enable CORS for Next.js frontend
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


class ChatPayload(BaseModel):
    messages: list = []
    currentItinerary: str | None = None


@app.post("/api/chat")
async def chat_endpoint(payload: ChatPayload):
    # Extract the user's prompt from messages
    user_message = ""
    if payload.messages:
        last_msg = payload.messages[-1]
        user_message = last_msg.get("content", "")

    async def generate_response():
        # Replace this example logic with your actual LLM / CrewAI streaming output
        response_text = (
            f"I can help with that! Here is the update regarding: '{user_message}'"
        )

        # Formats text chunks for AI SDK protocol: 0:"<text_chunk>"\n
        for word in response_text.split():
            chunk = f"{word} "
            yield f"0:{json.dumps(chunk)}\n"

    return StreamingResponse(
        generate_response(),
        media_type="text/plain",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.get("/")
def read_root():
    return {"status": "Game Time API is running"}