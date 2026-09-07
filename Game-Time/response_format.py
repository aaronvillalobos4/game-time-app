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

## ✅ Before You Go
Short checklist bullets for useful next steps, plus a blockquote for material
unknowns, estimates, or items the user should confirm. Include source links beside
the relevant option/fact; do not invent any. Never claim a booking was made.

Use blank lines around headings, lists and tables; each table must include its
Markdown header separator row. Keep tables to at most four columns and one line
per row. Use real Unicode emojis only as section accents, paired with readable
text. Do not pad missing research: say when options could not be verified.
"""
