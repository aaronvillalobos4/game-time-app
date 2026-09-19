"""Budget consent before paid-trip research."""
import re

SAMPLE_BUDGET = 1500
BUDGET_QUESTION = (
    "What is your total trip budget in USD? You can give me an amount or say "
    "'use a sample budget' to plan with a suggested $1,500 total. "
    "That is a planning allowance, not a price quote, and you can change it anytime."
)


def budget_from_message(request):
    text = request.message.strip()
    sample = bool(re.fullmatch(r"(?:please )?(?:use|choose|set|suggest)(?: a| the)? "
                              r"(?:sample|suggested) budget[.!]?", text, re.I))
    last = request.history[-1] if request.history else None
    if (last and last.role == "assistant" and BUDGET_QUESTION in last.content
            and re.fullmatch(r"(?:yes|yes please|sure|okay|ok)[.!]?", text, re.I)):
        sample = True
    if sample:
        return float(SAMPLE_BUDGET), True
    # Accept explicit total-budget statements, not quoted hotel/ticket prices.
    match = re.search(r"(?:\bbudget(?: is| of| to)?\s*\$?\s*|^\$)(\d[\d,]*(?:\.\d{1,2})?)", text, re.I)
    if not match and re.fullmatch(r"\d[\d,]*(?:\.\d{1,2})?", text):
        if last and last.role == "assistant" and "budget" in last.content.lower():
            match = re.match(r"(\d[\d,]*(?:\.\d{1,2})?)", text)
    if match:
        amount = float(match[1].replace(",", ""))
        if 0 < amount <= 1_000_000:
            return amount, False
    return None, False


def needs_budget(message):
    # Mentioning a service is not itself a request to shop for it.
    service = r"(?:tickets?|flights?|hotels?|lodging|accommodations?|fares?)"
    return bool(re.search(
        rf"\b(?:find|search|compare|recommend|show|book|reserve|cheaper|replace)\b.*\b{service}\b|"
        rf"\b{service}\b.*\b(?:prices?|cost|rates?|options?|available|availability)\b|"
        rf"\b(?:prices?|cost|rates?)\b.*\b{service}\b|"
        r"\b(?:build|create|make|revise|change|plan)\b.*\b(?:itinerary|trip)\b", message, re.I))
