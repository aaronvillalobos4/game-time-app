# Conversation refactor

The first phase keeps the frontend/API response contract and itinerary crew intact.
Chat uses one contextual assistant instead of separate short/full answer prompts.
AssistantTurn declares intent; information, schedule and clarification turns cannot
mutate trip slots or start itinerary generation. Existing clients do not need to
send intent. The nullable default preserves compatibility with existing callers.

The assistant calls Trip Research with a typed purpose. Booking categories require
a finite positive saved budget at execution time; informational searches skip
affiliate conversion. Query wording no longer blocks requests at the API entrance.
The model still selects the purpose, so semantic misclassification remains possible;
this is not a guarantee that arbitrary search queries can never concern prices.
Explicit budget parsing and sample consent remain in the existing budget module.
Newly inferred budgets may require another turn before booking tools can run.

Next phases: structured general-purpose event records and source verification;
structured itinerary items and deterministic budget totals; broader multi-turn live
evaluations and latency measurements. The existing Aggies page reader, affiliate
postprocessing and itinerary crew have not been replaced in this first phase.

## Structured events: first source adapter

EventRecord and EventSchedule now hold dates, opponents, venue/location, home/away,
published kickoff text, unconfirmed time windows, source URL and retrieval timestamp.
The Texas A&M football adapter parses the official HTML schedule table. Missing
fields, duplicate rows, empty schedules and wrong seasons fail validation instead
of producing invented fixtures. A dedicated tool supports date ranges, home/away
filters and counts. Schedule-intent answers use deterministic Markdown rendering
of the tool's records, not the LLM's rewritten table. Exact timezones are not guessed.

Live full-season and next-game tests should accompany changes to this adapter.
The official adapter remains preferred for Texas A&M football.

## Expanded team schedules

`espn_schedule.py` adds ESPN team-directory resolution and structured schedules for
NFL, NBA, WNBA, MLB, NHL and college football. Team names and abbreviations must
match a unique directory entry; ambiguous names request clarification. The tool
accepts a season, home/away filter, date bounds, optional count and season phase.
By default it fetches all three published phases concurrently and renders every
returned fixture. Future playoff opponents and unpublished games are not invented.
NBA/NHL season numbers use the ending year (2026-27 = 2027).

Every populated response validates the requested team, each fixture's season and
phase, participants and timestamp. Event IDs preserve doubleheaders and identify
conflicting duplicates. Missing venues and start times remain TBD. Confirmed dates
and times use America/Chicago with DST; untimed placeholder dates are not shifted.
This is a display timezone, not an inferred venue timezone. Schedules carry source
provenance and retrieval time; no schedule database or new credentials are needed.

ESPN's public feed is an external dependency, not a guaranteed service contract.
Unavailable/malformed responses fail with a verification message; empty feeds say
no published fixtures. Other leagues still use general research. This validates
provider records, not agreement between multiple independent sources. Team tools
are intended for game lists/next-game questions, while other details remain
conversational. Model routing and season/filter selection still need ongoing live
conversation evaluation.

Assistant replies allow 64,000 characters so long baseball schedules are not cut
off. Existing browser history limits are unchanged; tools can refetch for follow-up
questions. No affiliate or budget-gate behavior changes.

Validation: backend regression suite plus live adapter smoke checks for Cowboys,
Mavericks, Wings, Rangers, Stars and Longhorns. Cross-source conflict checks and
structured itinerary storage remain future work.

## Structured itineraries and calculated budgets

Both initial planning and revisions now request `ItineraryPlan` from CrewAI. The
backend validates the result and renders Markdown through `itinerary.py`, then
applies the existing affiliate and outbound-link processing. The streaming API
and frontend chat contract are unchanged. Invalid structured output fails through
the existing stream error path instead of displaying unchecked raw model text.

Costs have category, selection/optional flags, quantity, per-unit low/high prices,
currency, basis, evidence and provider booking URL. Decimal arithmetic computes
selected totals and uses upper estimates for budget comparisons. Alternative
hotels/tickets/flights are displayed but excluded from totals; multiple selected
options in these categories fail validation. Local trips omit flights. Missing
essential categories, missing prices and non-USD costs produce a known-cost USD
subtotal, not a claim of budget fit. The current budget currency is USD; no
automatic exchange-rate conversion is performed.

Optional paid extras are rendered only when their combined upper estimates fit
after all selected essentials with some budget remaining. Otherwise only supplied
zero-cost ideas are eligible. Selected extras count once in the core plan. Budget
math is deterministic; research accuracy, correct quantities/selection, timeline
quality and whether fees are actually included still depend on supplied evidence
and model extraction. This is not real-time booking inventory or price verification.

Structured plans are transient during generation; no new database is introduced.
Revisions still receive the existing Markdown/history and extract a fresh complete
plan. Persisting versioned structured plans is a separate future phase. Tests cover
build/revision wiring, ranges, quantities, unknown costs, currency, alternatives,
extras, malformed output and nonfinite budgets. No paid live-model evaluation was
run for this phase.

## Guided attendance intake

Personal attendance/ticket requests start a saved `trip_requested` intake. The
assistant resolves the chosen event/date from context or asks, then gathers flight
need (and origin if flying), explicit `needs_hotel`, and total budget. It asks only
for missing details. On an intake update with complete details, the API starts
generation automatically; schedule/information detours do not trigger generation.
Intent recognition and extraction remain model-driven; completeness is enforced
server-side. Sample budgets still require consent. Booking research tools also
check intake completeness before searching.

Hotel preference is carried through the browser and required by the itinerary
endpoint. Deploy frontend and backend together: older browser builds must refresh
before generating itineraries. No-hotel plans omit hotel research, options and
costs, including on revisions. Research cannot guarantee inventory or matching
booking links; missing verified links remain explicitly unavailable.

## Intake and generation reliability

Unambiguous yes/no answers to the immediately preceding flight/hotel question are
saved directly, bypassing model intent classification that can discard choices
when labeled clarification. Ambiguous replies, combined questions and itinerary
revisions still use the conversational assistant. The next question is computed
from saved slots.

Both itinerary composition and revision have a validation guardrail with at most
two retries of the final task. Validation feedback identifies schema errors without
relaxing cost or selection rules. Typed output, JSON dictionaries and fenced JSON
are validated before rendering. Local regression tests cover these paths; the
production error's exact cause still requires a live trace or server logs.

The subsequent authorized live test reproduced LengthFinishReasonError with zero
completion tokens. Both model clients previously left output limits unspecified;
they now explicitly request max_completion_tokens=8192. Local request preparation
confirms that parameter is sent. The stream distinguishes this failure from other
errors. This mitigation has not yet had a second live run; zero-token termination
may also reflect upstream service behavior rather than a normal truncated answer.

A second authorized live test with the explicit 8192-token allowance also failed
with zero completion tokens and LengthFinishReasonError. The allowance change did
not resolve the live failure. Do not treat local regression success as evidence
that live generation is restored; endpoint/provider diagnostics remain necessary.

Follow-up diagnostics isolated the failure to the itinerary schema: a plain model
request and a simple structured schema succeeded, while a minimal ItineraryPlan
request failed with zero output tokens. Decimal price fields emitted a string
regex containing negative lookahead. Advertising those fields as nullable JSON
numbers with WithJsonSchema removed the failure, while preserving Decimal runtime
validation and arithmetic. The same minimal request then succeeded, followed by a
successful full synthetic itinerary run (2,905 characters, no hotel). That run
recovered from an intermediate missing-price-bound validation error. Console
printing of emoji failed under Windows cp1252 after generation completed; the
itinerary itself returned successfully. No deployment was performed.
