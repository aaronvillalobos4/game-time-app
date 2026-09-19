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
