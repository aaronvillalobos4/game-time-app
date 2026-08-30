"""Conversation guardrails and CrewAI itinerary agents for Game Time."""

import os
import re
from typing import Any
import requests
from crewai import Agent, Crew, LLM, Process, Task
from crewai.tools import tool

from affiliate_links import affiliate_url_for


RESET_PATTERN = re.compile(
    r"\b(?:cancel|restart|reset|start over|never mind)\b",
    re.IGNORECASE,
)

crew_llm = LLM(
    model=os.getenv("CREWAI_MODEL", "gpt-4o"),
    temperature=0.7,
)


def evaluate_user_intent(
    user_input: str,
    session_history: list[Any] | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Detect reset requests before the API performs its normal slot parsing.

    The ``status`` field maintains the contract expected by ``app.py``. The
    boolean fields give callers a consistent response shape if this function is
    reused elsewhere.
    """
    if RESET_PATTERN.search(user_input):
        if isinstance(session_history, dict):
            session_history.clear()

        return {
            "status": "RESET",
            "is_reset": True,
            "is_complete": False,
            "slots": {},
            "follow_up_question": (
                "Search cancelled! What new game do you want to see?"
            ),
        }

    return {
        "status": "PROCEED",
        "is_reset": False,
        "is_complete": False,
    }


def format_origin_location(raw_origin: str) -> str:
    """Normalize a city/state string while preserving the local-trip marker."""
    cleaned = raw_origin.strip()
    if not cleaned:
        return ""
    if cleaned.casefold() == "local":
        return "Local"

    parts = [part for part in re.split(r"[,\s]+", cleaned) if part]
    if len(parts) >= 2 and len(parts[-1]) == 2:
        return f"{' '.join(parts[:-1]).title()}, {parts[-1].upper()}"
    return cleaned.title()


@tool("Google Search")
def google_search(query: str) -> str:
    """Search the web for current booking options through the Serper API."""
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return "Search unavailable: SERPER_API_KEY is not configured."

    try:
        response = requests.post(
            "https://google.serper.dev/search",
            headers={
                "X-API-KEY": api_key,
                "Content-Type": "application/json",
            },
            json={"q": query, "num": 3},
            timeout=12,
        )
        response.raise_for_status()
        results = response.json()
    except requests.RequestException as exc:
        return f"Search request failed: {exc}"
    except ValueError:
        return "Search request failed: Serper returned invalid JSON."

    options = []
    for item in results.get("organic", []):
        title = item.get("title", "Untitled result")
        original_link = item.get("link", "")
        link = affiliate_url_for(original_link) if original_link else "No link provided"
        snippet = item.get("snippet", "No description provided")
        options.append(f"Title: {title}\nLink: {link}\nInfo: {snippet}")

    return "\n---\n".join(options) if options else "No search results found."


class TravelCrew:
    """Build and execute the ticket, hotel, flight, and coordinator crew."""

    def __init__(self, inputs: dict[str, Any]):
        self.inputs = dict(inputs)
        self.inputs["origin"] = format_origin_location(
            str(self.inputs.get("origin", ""))
        )

    def ticket_agent(self) -> Agent:
        return Agent(
            role="Sports Ticket Specialist",
            goal="Find available stadium seating and current ticket pricing",
            backstory=(
                "An expert sports ticket broker who finds strong seat value and "
                "provides direct booking links."
            ),
            tools=[google_search],
            llm=crew_llm,
            verbose=False,
        )

    def flight_agent(self) -> Agent:
        return Agent(
            role="Flight Booking Expert",
            goal="Find practical flight routes and pricing for sports travel",
            backstory=(
                "A travel agent who compares flight schedules, total prices, "
                "and booking options for event trips."
            ),
            tools=[google_search],
            llm=crew_llm,
            verbose=False,
        )

    def hotel_agent(self) -> Agent:
        return Agent(
            role="Hotel and Lodging Specialist",
            goal="Find well-rated lodging close to the game venue",
            backstory=(
                "A lodging specialist who balances location, guest ratings, "
                "price, and convenient booking options."
            ),
            tools=[google_search],
            llm=crew_llm,
            verbose=False,
        )

    def coordinator_agent(self) -> Agent:
        return Agent(
            role="Sports Trip Coordinator",
            goal=(
                "Turn ticket, lodging, and flight research into a useful "
                "itinerary that respects the user's total budget"
            ),
            backstory=(
                "An experienced itinerary planner who clearly identifies "
                "estimated prices, assumptions, and booking links."
            ),
            llm=crew_llm,
            verbose=False,
        )

    def _validate_inputs(self) -> None:
        missing = [
            field
            for field in ("game", "date", "budget")
            if self.inputs.get(field) in (None, "")
        ]
        if missing:
            raise ValueError(f"Missing required trip inputs: {', '.join(missing)}")

        budget = self.inputs["budget"]
        if isinstance(budget, bool) or not isinstance(budget, (int, float)):
            raise ValueError("Trip budget must be a number.")
        if budget <= 0:
            raise ValueError("Trip budget must be greater than zero.")

    async def run(self) -> str:
        """Run research tasks concurrently, then synthesize their results."""
        self._validate_inputs()

        ticket_agent = self.ticket_agent()
        hotel_agent = self.hotel_agent()
        coordinator_agent = self.coordinator_agent()

        ticket_task = Task(
            description=(
                f"Find two bookable ticket options for {self.inputs['game']} "
                f"on {self.inputs['date']}. Include current listed price, seat "
                "details, and the provided source link. Do not invent availability "
                "or alter any URL."
            ),
            expected_output=(
                "Two ticket options with seat details, listed prices, source "
                "names, and booking links."
            ),
            agent=ticket_agent,
            async_execution=True,
        )

        hotel_task = Task(
            description=(
                f"Find two well-rated hotels near the venue for "
                f"{self.inputs['game']} around {self.inputs['date']}. Include "
                "nightly rate, rating, location information, and source link."
            ),
            expected_output=(
                "Two hotel options with nightly rates, ratings, locations, "
                "source names, and booking links."
            ),
            agent=hotel_agent,
            async_execution=True,
        )

        research_tasks = [ticket_task, hotel_task]
        agents = [ticket_agent, hotel_agent]

        if self.inputs["origin"].casefold() not in {"", "local", "none"}:
            flight_agent = self.flight_agent()
            flight_task = Task(
                description=(
                    f"Find practical flight options from {self.inputs['origin']} "
                    f"for attending {self.inputs['game']} on "
                    f"{self.inputs['date']}. Include times, total listed price, "
                    "airline, and source link. Clearly state date assumptions."
                ),
                expected_output=(
                    "Flight options with airlines, schedules, listed prices, "
                    "date assumptions, source names, and booking links."
                ),
                agent=flight_agent,
                async_execution=True,
            )
            research_tasks.append(flight_task)
            agents.append(flight_agent)

        coordinator_task = Task(
            description=(
                f"Using only the supplied research, create a concise itinerary "
                f"for {self.inputs['game']} on {self.inputs['date']} with a total "
                f"target budget of ${self.inputs['budget']:,.2f}. Provide a "
                "budget table, estimated total, useful schedule, assumptions, "
                "and booking links. Copy every booking URL exactly as supplied: "
                "never shorten, decode, rewrite, or remove its query parameters. "
                "Never claim that a booking was made. If the options exceed the "
                "budget, say so and identify the shortfall."
            ),
            expected_output=(
                "A polished Markdown itinerary with a schedule, budget breakdown, "
                "estimated total, assumptions, and source booking links."
            ),
            agent=coordinator_agent,
            context=research_tasks,
        )

        crew = Crew(
            agents=[*agents, coordinator_agent],
            tasks=[*research_tasks, coordinator_task],
            process=Process.sequential,
            verbose=False,
        )
        result = await crew.kickoff_async()
        return str(result.raw) if hasattr(result, "raw") else str(result)
