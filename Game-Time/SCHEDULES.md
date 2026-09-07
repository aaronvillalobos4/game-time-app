# Conversational sports-trip assistant

The main chat's `/api/parse-intent` endpoint sends every non-reset message to a
CrewAI assistant. It answers questions, researches current information, and
extracts selected trip details in a validated structured response. It replaces
the keyword schedule router and fixed regular-expression questionnaire.

Examples:

- "Show me the Texas A&M Aggies football schedule."
- "What are the top college football games in Texas this month?"
- "Which of those would be easiest to reach from Austin?"
- "Let's choose the second one."
- "Which airport should I use?"
- "I'll fly from Denver and my total budget is $1,200."
- "Build my itinerary."

The frontend sends up to 20 recent messages (40,000 characters total) and the
current itinerary. This lets the assistant resolve follow-ups and selection of
previously suggested games. Missing or ambiguous context should prompt a
clarification. State lives in the current browser page, not a persistent account;
refreshing clears it. Reset clears the chat, selected trip, and itinerary.

The assistant is instructed to answer questions before collecting more details,
search for current facts, cite sources, distinguish subjective rankings from
facts, and label incomplete results and unknown times. Search snippets are not
a complete structured league feed. Without search access it can still provide
general advice but must disclose that current facts could not be verified.

Only selected/provided facts should update trip fields; recommendations alone
must not select a game or change a budget. Changing events clears the old date
unless the new date is supplied. Switching from driving to flying clears the
local origin. The server validates fields and preserves them if AI output fails
validation or the 90-second request deadline expires.

The assistant offers to build an itinerary when details are complete. Generation
requires the model to recognize an explicit build request/confirmation and the
server to verify all required trip fields. Asking another question with a
complete trip does not automatically regenerate the itinerary.

## Configuration and checks

The server process needs the credentials for `CREWAI_MODEL` (default `gpt-4o`)
and `SERPER_API_KEY` for live research. From `Game-Time`, start locally with
`uvicorn app:app --env-file .env`. For the frontend, set `NEXT_PUBLIC_API_URL` to
the local backend URL when testing locally. Every conversational turn uses the
configured model; research turns may make multiple search requests.

Run `python -m unittest discover -s . -p "test_*.py"` from `Game-Time`. Unit tests
mock model/search responses and cover state preservation, history, selections,
build gating, invalid model output, reset handling, and field validation. Live
model/search quality requires separate smoke testing with configured credentials.
