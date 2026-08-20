import os
from urllib.parse import urlencode

# Base affiliate search URL
EXPEDIA_BASE_URL = "https://www.expedia.com/Hotel-Search"
EXPEDIA_CAMREF = os.getenv("EXPEDIA_CAMREF", "game_time")


def get_hotel_recommendations(
    venue_name: str, check_in: str, check_out: str, adults: int = 2
) -> dict:
    """Generates direct affiliate tracking search links for Game Time venues."""
    params = {
        "destination": f"Hotels near {venue_name}",
        "startDate": check_in,
        "endDate": check_out,
        "adults": str(adults),
        "camref": EXPEDIA_CAMREF,
    }

    booking_url = f"{EXPEDIA_BASE_URL}?{urlencode(params)}"

    return {
        "status": "success",
        "hotels": [{
            "name": f"Recommended Hotels near {venue_name}",
            "booking_url": booking_url,
            "source": "affiliate_deep_link",
        }],
    }