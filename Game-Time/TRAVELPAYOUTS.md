# Hotel affiliate links

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
itinerary Markdown, including revisions. When configured, Travelpayouts replaces
the fixed Expedia CTA policy. Ticketmaster retains its existing tracking handler.

The converter sends up to 10 links per request, deduplicates originals, limits
processing to 50 unique hotel links per response, and caches successes for one
hour and failures for one minute in each server process (bounded cache). Eight-second
timeouts and per-link failure handling keep source links usable during outages or
missing brand access. An unchanged source URL is not claimed to earn commission.
Previously generated fixed Expedia links are not automatically converted into
hotel deep links; regenerate/revise using full hotel-provider source URLs.

Hotel URL detection currently covers booking.com, hotels.com, expedia.com hotel
paths, agoda.com, trip.com hotel paths, and hostelworld.com. This allowlist does
not imply account eligibility. Expedia UK and Ticketmaster are excluded from
Travelpayouts conversion. Add other provider domains after confirming API support.

The API documents a limit of 100 requests/minute per partner ID. Batching and
caching reduce traffic but do not impose an account-wide limit across workers;
larger deployments should add a shared cache/rate limiter. A successful conversion
validates link creation, not price/availability or a future commission payment.

Reference: https://support.travelpayouts.com/hc/en-us/articles/25289759198226-API-for-Travelpayouts-partner-links
