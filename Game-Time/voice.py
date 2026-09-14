"""Server-only SDP exchange for the realtime voice transport."""

import asyncio
import json
import os

import requests
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

router = APIRouter()


class VoiceOffer(BaseModel):
    sdp: str = Field(min_length=10, max_length=64_000)


def session_config() -> dict:
    return {
        "type": "realtime",
        "model": os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime-2.1"),
        "instructions": (
            "You are the AI voice of Game Time. Speak warmly, clearly and naturally, "
            "with relaxed energy and brief pauses. Do not imitate a named person or "
            "character. Only read the supplied planner answer; do not independently "
            "answer sports or travel questions or invent facts. Never read URLs aloud."
        ),
        "audio": {
            "input": {
                "transcription": {"model": "gpt-4o-mini-transcribe", "language": "en"},
                "noise_reduction": {"type": "near_field"},
                "turn_detection": {
                    "type": "semantic_vad", "eagerness": "medium",
                    "create_response": False, "interrupt_response": True,
                },
            },
            "output": {"voice": os.getenv("OPENAI_REALTIME_VOICE", "marin")},
        },
        "max_output_tokens": 1200,
    }


@router.post("/api/voice/session")
async def create_voice_session(offer: VoiceOffer) -> Response:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise HTTPException(503, "Voice chat is not configured yet. Please use text chat.")
    if not offer.sdp.startswith("v=0"):
        raise HTTPException(400, "Invalid voice connection offer.")
    try:
        result = await asyncio.to_thread(
            requests.post, "https://api.openai.com/v1/realtime/calls",
            headers={"Authorization": f"Bearer {key}"},
            files={"sdp": (None, offer.sdp), "session": (None, json.dumps(session_config()))},
            timeout=20,
        )
    except requests.RequestException as exc:
        raise HTTPException(502, "Voice could not connect. Please try again.") from exc
    if not result.ok:
        # Never return provider errors or credentials to the browser.
        raise HTTPException(502, "Voice is temporarily unavailable. Please use text chat.")
    return Response(result.text, media_type="application/sdp", headers={"Cache-Control": "no-store"})
