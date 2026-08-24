# agents.py
import os
import re
import requests
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def format_origin_location(raw_origin: str) -> str:
    """
    Cleans and standardizes departure locations like 'austin tx', 
    'Austin, TX', or 'austin' into clean 'City, ST' format.
    """
    if not raw_origin:
        return ""
    
    # Trim excess spaces
    cleaned = raw_origin.strip()
    
    # Split by comma or spaces
    parts = [p.strip() for p in re.split(r'[, ]+', cleaned) if p.strip()]
    
    # If a 2-letter state code is present at the end
    if len(parts) >= 2 and len(parts[-1]) == 2:
        city = " ".join(parts[:-1]).title()
        state = parts[-1].upper()
        return f"{city}, {state}"
    
    # Fallback to title casing if state code wasn't specified
    return cleaned.title()
# ==========================================
# CUSTOM SEARCH SCRAPING TOOL
# ==========================================
@tool("Google Search Scraper")
def google_search_scraper(query: str) -> str:
    """
    Scrapes Google Search results to find real-time information.
    Use this to find sports game tickets, flights, hotels, and prices.
    """
    api_key = os.environ.get("SERPER_API_KEY", "")
    if not api_key:
        return "Error: SERPER_API_KEY environment variable is not set."

    url = "https://google.serper.dev/search"
    payload = {
        "q": query,
        "num": 3  # Grabs the top 3 organic results
    }
    headers = {
        'X-API-KEY': api_key,
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=12)
        if response.status_code == 200:
            results = response.json()
            output = []
            
            for item in results.get("organic", []):
                title = item.get('title')
                link = item.get('link')
                snippet = item.get('snippet')
                output.append(f"Title: {title}\nLink: {link}\nInfo: {snippet}\n---")
                
            return "\n".join(output) if output else "No results found."
        else:
            return f"Search scraper failed. Status code: {response.status_code}"
    except Exception as e:
        return f"Error executing search scrape: {str(e)}"


# ==========================================
# CREWAI AGENTS & TASKS PIPELINE
# ==========================================
class TravelCrew:
    def __init__(self, inputs: dict):
        self.inputs = inputs  # Expects: {"game": ..., "date": ..., "origin": ..., "budget": ...}
        
        # Standardize origin city/state right on initialization
        if "origin" in self.inputs:
            self.inputs["origin"] = format_origin_location(str(self.inputs["origin"]))

    def ticket_agent(self) -> Agent:
        return Agent(
            role='Sports Ticket Finder',
            goal=f"Scrape ticket sites to find the best available seats for {self.inputs.get('game')} on {self.inputs.get('date')}.",
            backstory="You are an expert at scanning ticket broker sites (StubHub, SeatGeek, Ticketmaster) via search. You locate exact prices, seat sections, and booking links.",
            tools=[google_search_scraper],
            verbose=True
        )

    def flight_agent(self) -> Agent:
        return Agent(
            role='Flight Searcher',
            goal=f"Find flight itineraries from {self.inputs.get('origin')} to the destination city.",
            backstory="You are a meticulous flight coordinator. You find flight times, airlines, and estimated costs that ensure arrival at least 4 hours before the event.",
            tools=[google_search_scraper],
            verbose=True
        )

    def hotel_agent(self) -> Agent:
        return Agent(
            role='Hotel Scout',
            goal="Locate highly-rated hotels near the venue or convenient transit lines.",
            backstory="You excel at balancing hotel quality, proximity to the stadium, and night-by-night pricing.",
            tools=[google_search_scraper],
            verbose=True
        )

    def coordinator_agent(self) -> Agent:
        return Agent(
            role='Trip Coordinator & Itinerary Planner',
            goal="Synthesize the ticket, flight, and hotel findings into a comprehensive sports weekend itinerary.",
            backstory="You are a detail-oriented logistics manager. You map out transportation timing, double-check budget constraints, and write beautiful Markdown schedules.",
            verbose=True
        )

    async def run(self):
        ticket_agent_inst = self.ticket_agent()
        hotel_agent_inst = self.hotel_agent()
        coordinator_agent_inst = self.coordinator_agent()

        # Determine if flight searching is needed
        is_local = self.inputs.get('origin', '').lower() in ['local', 'none', '']

        tasks = [
            Task(
                description=f"Find 2 ticket options for {self.inputs.get('game')} on {self.inputs.get('date')}. Include booking URLs as [Book Here](URL).",
                expected_output="2 ticket options with seat details, prices, and booking links.",
                agent=ticket_agent_inst
            )
        ]

        # Only include flight task if user is traveling from out of town
        if not is_local:
            flight_agent_inst = self.flight_agent()
            tasks.append(
                Task(
                    description=f"Search flights from {self.inputs.get('origin')} for {self.inputs.get('date')}. Include booking URLs as [Book Here](URL).",
                    expected_output="Flight options with flight numbers, times, prices, and booking links.",
                    agent=flight_agent_inst
                )
            )

        tasks.append(
            Task(
                description=f"Search 2 top-rated hotels close to the venue for {self.inputs.get('game')}. Include booking URLs as [Book Here](URL).",
                expected_output="2 hotel options with nightly rates, ratings, and booking links.",
                agent=hotel_agent_inst
            )
        )

        tasks.append(
            Task(
                description=f"Synthesize ticket, hotel, and flight (if applicable) choices into a weekend plan under ${self.inputs.get('budget')}. Must include clickable markdown links [Name](URL).",
                expected_output="A styled markdown itinerary with budget breakdown table and booking links.",
                agent=coordinator_agent_inst
            )
        )

        crew = Crew(
            agents=[t.agent for t in tasks],
            tasks=tasks,
            process=Process.sequential,
            verbose=True
        )

        return await crew.kickoff_async()