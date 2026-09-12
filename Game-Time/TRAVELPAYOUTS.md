# Hotel affiliate links

Klook and KKday are preferred accommodation research providers. The chat, hotel
research task, coordinator and revision prompts share this policy: search both
first, verify overnight stays and trip fit, then fall back to other providers if
necessary. Existing user hotel choices take precedence. Accommodation URL paths
on klook.com and kkday.com are eligible for conversion; ambiguous product URLs
without hotel/accommodation/staycation markers remain unchanged. Conversion is
not proof of overnight availability or commission eligibility under brand terms.
Live checks on September 11, 2026 created links for Klook's hotel landing page
and KKday's www Japan hotel promotion page. The tested m.kkday.com hotel URL
returned "not brand link"; it remains a source link. Agents are instructed to
research verified www.kkday.com alternatives rather than inventing URL rewrites.

Configure `TRAVELPAYOUTS_API_TOKEN`, `TRAVELPAYOUTS_MARKER` (partner ID), and
`TRAVELPAYOUTS_PROJECT_ID` (`trs`) in the backend environment. Run locally with
`uvicorn app:app --env-file .env`; set the same variables on the hosted backend.
The API token stays on the server and is never sent to the model or browser.

The project must be connected/approved for each hotel brand. Creating an account
and obtaining a token alone is insufficient. The live setup check returned
"not subscribed to brand" for both Booking.com and Expedia on September 9, 2026.
Connect an eligible hotel program to this exact project, then retest a full URL
from that program. No test bookings are created by link conversion.

Search results retain source links and gain a separate Travelpayouts booking URL
on successful conversion. The backend also converts hotel URLs in final chat and
itinerary Markdown, including revisions. There is no Expedia affiliate fallback, even without Travelpayouts credentials. Ticketmaster retains its existing tracking handler.

The converter sends up to 10 links per request, deduplicates originals, limits
processing to 50 unique hotel links per response, and caches successes for one
hour and failures for one minute in each server process (bounded cache). Eight-second
timeouts and per-link failure handling keep source links usable during outages or
missing brand access. An unchanged source URL is not claimed to earn commission.
Recognized Expedia affiliate URLs are removed from new replies and revisions.
Previously displayed messages are not retroactively changed. Expedia is excluded
from Travelpayouts conversion; ordinary untracked Expedia research links may remain.

Hotel URL detection currently covers booking.com, hotels.com, agoda.com, trip.com hotel paths, and hostelworld.com. This allowlist does
not imply account eligibility. Expedia UK and Ticketmaster are excluded from
Travelpayouts conversion. Add other provider domains after confirming API support.

The API documents a limit of 100 requests/minute per partner ID. Batching and
caching reduce traffic but do not impose an account-wide limit across workers;
larger deployments should add a shared cache/rate limiter. A successful conversion
validates link creation, not price/availability or a future commission payment.

Reference: https://support.travelpayouts.com/hc/en-us/articles/25289759198226-API-for-Travelpayouts-partner-links
