"""Markdown presentation contract consumed by the conversational and itinerary agents."""

CHAT_FORMAT = """
PRESENTATION: Write the reply in GitHub-flavored Markdown, not HTML or a code
fence. Use short paragraphs, **bold** key details, and bullets for parallel tips.
Use a compact table for comparing dates, games, or costs when useful (at most
four columns); use numbered lists for options the user can choose. Use meaningful
Unicode emojis sparingly in headings, such as 📅, 🎟️, 🏨, ✈️, and 💰, with text
labels alongside them. Simple answers do not need a heading or table. Separate
headings, paragraphs, lists, and tables with blank lines. Tables require a header
and separator row, one item per row, and no multiline cells. Use descriptive
Markdown link labels instead of bare URLs. Never wrap the entire reply in quotes.
"""

ITINERARY_FORMAT = """
PRESENTATION CONTRACT: Return a readable GitHub-flavored Markdown itinerary,
not JSON, HTML, or a fenced code block. Follow this section order:

## 🏟️ Your Game Time Trip
A short overview, then bullets with **Matchup**, **Date**, **Venue / city**,
**Travel origin**, and **Target budget**. Use only supplied facts; mark unknowns TBD.

## 📅 Game-Day Plan
A table with columns Time | Activity | Details. Include the timezone for verified
times. Mark suggested travel/arrival times as suggestions and unknown kickoff as
TBD. Do not invent an event time to fill the table.

## 🎟️ Ticket Options
Numbered options with bold labels, short seat/price details, and exact booking links.

## 🏨 Where to Stay
Bulleted hotel options with location, nightly rate, and exact booking links.

## ✈️ Getting There
For flights, use short bullets with researched routes, prices, and exact links.
For local/driving trips use the heading '## 🚗 Getting There' and omit flights.

## 💰 Budget Breakdown
A table with columns Item | Quantity / basis | Estimated cost | Notes. Total only
one recommended combination, not all alternative options added together. Show
**Estimated total** and **Remaining budget** or **Over budget** below the table.
Identify per-person vs per-trip amounts, nights, fees, assumptions, and unpriced
items. If any costs are unknown, call the sum a known-cost subtotal, not a complete
trip total. Never invent prices or treat missing prices as zero to complete a table.

## 🍽️ Make It a Weekend
Offer up to three OPTIONAL ideas: a casual dinner or local food experience and
one or two nearby activities, such as a campus walk, public art, a local museum,
or a scenic neighborhood. Keep each idea to one or two friendly sentences about
why it could make the trip fun. Tailor ideas to the researched destination, not
an assumed home stadium. Prefer broad experiences over detailed reservations.

First calculate estimated room in the budget AFTER the recommended tickets,
lodging, transport, and known fees. If essential costs are missing, do not claim
there is money left for paid extras. If the plan is at/over budget or costs are
incomplete, offer only no-admission-cost ideas supported by research (or clearly
conditional general ideas), noting that transport/parking may still cost money.
Do not add paid activities in these cases. If the user declines extras, omit them.

When the core plan has room, suggest an affordable dinner and/or attraction.
Use sourced prices or a clearly labeled suggested spending cap, never a made-up
venue quote. Show per-person/per-group basis; if party size is unknown, explicitly
state a one-traveler planning assumption rather than treating a per-person amount
as the whole group's cost. Keep the COMBINED upper cost/caps of suggested extras,
including applicable taxes, tips and transport allowances, within the estimated
remaining budget and leave a buffer. If these costs cannot be bounded, do not
claim the extras fit. Never present a paid idea as free or promise opening hours.

Show **Optional extras allowance**, **Estimated total with extras**, and
**Budget left with extras** only when that calculation is supported; keep this
scenario separate from the core trip total. Ideas are not selected purchases.
Do not count alternative dinners or activities as if the user will do all of
them; say which combination the example total covers. Fit suggestions around the
game with flexible 'before the game'/'next morning' timing when times are unknown.
Cite sources for named places, admission prices and specific local claims. If
research is missing, use conditional general ideas without invented businesses,
prices, hours or links. End with a short invitation to pick an idea in chat.

## ✅ Before You Go
Short checklist bullets for useful next steps, plus a blockquote for material
unknowns, estimates, or items the user should confirm. Include source links beside
the relevant option/fact; do not invent any. Never claim a booking was made.

Use blank lines around headings, lists and tables; each table must include its
Markdown header separator row. Keep tables to at most four columns and one line
per row. Use real Unicode emojis only as section accents, paired with readable
text. Do not pad missing research: say when options could not be verified.
"""
