from urllib.parse import urlencode

# Untracked hotel search URL
EXPEDIA_BASE_URL = "https://www.expedia.com/Hotel-Search"


def get_hotel_recommendations(
    venue_name: str, check_in: str, check_out: str, adults: int = 2
) -> dict:
    """Generates untracked search links for Game Time venues."""
    params = {
        "destination": f"Hotels near {venue_name}",
        "startDate": check_in,
        "endDate": check_out,
        "adults": str(adults),
    }

    booking_url = f"{EXPEDIA_BASE_URL}?{urlencode(params)}"

    return {
        "status": "success",
        "hotels": [{
            "name": f"Recommended Hotels near {venue_name}",
            "booking_url": booking_url,
            "source": "provider_search",
        }],
    }