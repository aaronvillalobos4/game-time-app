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
        flight_agent_inst = self.flight_agent()
        hotel_agent_inst = self.hotel_agent()
        coordinator_agent_inst = self.coordinator_agent()

        task_tickets = Task(
            description=f"Find 2 tickets for {self.inputs.get('game')} on {self.inputs.get('date')}. Find realistic price ranges, sections, and source links.",
            expected_output="A list of 2-3 ticket options with seat details, exact prices, and URLs.",
            agent=ticket_agent_inst
        )

        task_flights = Task(
            description=f"Search for flights from {self.inputs.get('origin')} to the match city for {self.inputs.get('date')}. Standalone Flights: Search options and output referral links (e.g. Skyscanner/WayAway). Bundled Packages: If combining with hotels, prioritize Expedia package deals and highlight total savings. Focus on arrival times, estimated costs, and airline options.",
            expected_output="Flight options with flight numbers, times, and booking source names.",
            agent=flight_agent_inst
        )

        task_hotels = Task(
            description=f"Search for top-rated hotels close to the venue of {self.inputs.get('game')}.",
            expected_output="A curated list of 3 hotels including distance to arena, nightly rate, and ratings.",
            agent=hotel_agent_inst
        )

        task_itinerary = Task(
            description=f"Verify all data. Build a cohesive weekend plan that keeps total costs under {self.inputs.get('budget')}. Format with a cost summary table and an hour-by-hour itinerary.",
            expected_output="A beautifully styled markdown itinerary including a budget breakdown table, transit directions, and an hour-by-hour timeline.",
            agent=coordinator_agent_inst
        )

        crew = Crew(
            agents=[ticket_agent_inst, flight_agent_inst, hotel_agent_inst, coordinator_agent_inst],
            tasks=[task_tickets, task_flights, task_hotels, task_itinerary],
            process=Process.sequential,
            verbose=True
        )

        return await crew.kickoff_async()