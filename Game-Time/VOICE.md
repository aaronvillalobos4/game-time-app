# Game Time voice conversations

The existing Talk to Game Time button starts a WebRTC session. Spoken messages
are automatically transcribed and sent through the same research and itinerary
flow as typed messages. Realtime audio reads the planner answer; it does not
independently research or invent game details. Full answers and booking links
remain in chat. Users can speak over playback, mute their microphone, interrupt
with a button, or end the session. Leaving the tab ends voice capture. Requests
already submitted to the planner can still finish in text after voice ends.

## Server configuration

The FastAPI backend needs `OPENAI_API_KEY` in its runtime environment, with
access to the configured realtime and transcription models. No key is sent to
the browser. The browser only receives the SDP connection answer.

Optional environment variables:

- `OPENAI_REALTIME_MODEL`: defaults to `gpt-realtime-2.1`.
- `OPENAI_REALTIME_VOICE`: defaults to `marin`.

This uses an OpenAI stock voice with warm, natural delivery instructions, not
Grok's Ara voice. Realtime audio and transcription incur API usage charges.
Deploy both the frontend and backend changes together. Local backend launches
can use `uvicorn app:app --env-file .env --port 8000`; point the frontend's
`NEXT_PUBLIC_API_URL` at that backend when testing locally. Use HTTPS in production.

## Verification

- Backend mocked integration/regression checks:
  `python -m unittest test_voice test_booking_links test_affiliate_links test_itinerary_revisions test_conversation`
- Frontend mocked microphone/connection lifecycle checks (from game-time-web):
  `node --test lib/voice-session.test.cjs`
- Frontend build: `npm run build`

Before release, test with an actual microphone on desktop and mobile:

1. Start voice, allow microphone access, ask for a team's next games, and verify
   the transcript and researched answer appear in chat and the answer is spoken.
2. Answer a follow-up without pressing Send; confirm chosen trip details persist.
3. Speak over a reply and use Interrupt; verify playback stops and a correction
   is handled. Planner requests run in order; research latency still applies.
4. Mute while speaking, unmute, and verify discarded audio is not submitted.
5. End during connection, research, and playback; verify microphone capture and
   audio stop, typed chat is available, and no late voice playback occurs.
6. Deny microphone permission, disconnect the network, and switch tabs. Verify
   helpful recovery messages and microphone release.

Automated tests mock provider calls and browser media. They do not establish
live account access, acoustic echo handling, perceived voice quality, or mobile
audio autoplay behavior. Sessions end after 15 minutes in this client.

Implementation reference: https://developers.openai.com/api/docs/guides/voice-webrtc
