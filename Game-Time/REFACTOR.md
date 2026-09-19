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
This adapter covers Texas A&M football only. Other teams still use general research;
they are not silently marked as structured/verified. Additional source adapters,
cross-source conflict checks and structured itinerary storage remain future work.
