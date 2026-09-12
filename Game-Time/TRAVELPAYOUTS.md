# Hotel affiliate links

Klook and KKday remain the only hotel providers enabled for Travelpayouts
conversion. Agents search both first and broaden sparse event/date queries to the
venue city before falling back. If suitable accommodations or affiliate conversion
are unavailable, verified hotel resource links from other providers are allowed.
Inline raw hotel URLs are labeled "Hotel resource (not affiliate)"; bare and
reference URLs are preserved. Agents must explain the fallback and must not claim
these resources earn commission. The decision to use fallback recommendations is
prompt-based. The user-approved Expedia affiliate entry is available as a fallback or on request.
It is a separate creator link, not a Travelpayouts hotel deep link; users must
search for the selected hotel and verify dates and price.
Accommodation URL paths on klook.com and kkday.com are eligible for conversion;
ambiguous product URLs can remain untracked resources. Conversion is not proof of
availability, pricing or commission eligibility.
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
itinerary Markdown, including revisions. The approved Expedia entry also works without Travelpayouts credentials. Ticketmaster retains its existing tracking handler.

The converter sends up to 10 links per request, deduplicates originals, limits
processing to 50 unique hotel links per response, and caches successes for one
hour and failures for one minute in each server process (bounded cache). Eight-second
timeouts and per-link failure handling keep source links usable during outages or
missing brand access. An unchanged source URL is not claimed to earn commission.
Recognized obsolete Expedia affiliate URLs are removed; the exact approved entry is preserved with a disclosure and explanation.
Previously displayed messages are not retroactively changed. Expedia is excluded
from Travelpayouts conversion; ordinary Expedia hotel resource URLs may remain untracked.

The conversion allowlist is limited to klook.com and kkday.com accommodation
paths, including subdomains. Other hotel providers are never sent to this API.
Flight and Ticketmaster link handling are unchanged.

The API documents a limit of 100 requests/minute per partner ID. Batching and
caching reduce traffic but do not impose an account-wide limit across workers;
larger deployments should add a shared cache/rate limiter. A successful conversion
validates link creation, not price/availability or a future commission payment.

Reference: https://support.travelpayouts.com/hc/en-us/articles/25289759198226-API-for-Travelpayouts-partner-links
