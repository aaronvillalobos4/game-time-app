import os
import re
import requests
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool
import openai
from crewai import LLM

# =====================================================================
# 1. SYSTEM PROMPT & ROUTING TOOL
# =====================================================================

GAME_TIME_SYSTEM_PROMPT = """
You are Game Time, a highly skilled travel and event planning assistant.

CRITICAL ROUTING RULES:
1. Before extracting event details, check if the user wants to cancel, restart, 
   or search for a different game (e.g., "start over", "never mind", "cancel").
2. If a reset intent is detected, call the `reset_search` tool immediately.
"""

RESET_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "reset_search",
        "description": "Clears current context and restarts the search flow.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Reason for reset"}
            },
            "required": []
        }
    }
}

# =====================================================================
# 2. ENTRYPOINT ROUTER FUNCTION
# =====================================================================

def extract_slots(user_input: str, current_slots: dict | None = None) -> dict:
    """Extract common trip fields and preserve slots collected previously."""
    slots = dict(current_slots or {})
    text = user_input.strip()

    patterns = {
        "date": r"\b(?:on|for)\s+([A-Za-z]+\s+\d{1,2}(?:,\s*\d{4})?|\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)",
        "budget": r"\$\s*([\d,]+(?:\.\d{1,2})?)",
        "origin": r"\bfrom\s+([A-Za-z][A-Za-z .'-]*?)(?=\s+(?:on|for|under)\b|[,.;]|$)",
    }
    for slot, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            slots[slot] = float(value.replace(",", "")) if slot == "budget" else value

    game_match = re.search(
        r"\b(?:game|match|event)\s*[:\-]?\s*(.+?)(?=\s+(?:on|for|from|under)\b|$)",
        text,
        re.IGNORECASE,
    )
    if game_match:
        slots["game"] = game_match.group(1).strip(" ,.;")
    return slots

def get_missing_slots(slots: dict) -> list[str]:
    """Return required trip fields that have not been collected yet."""
    required_slots = ("game", "origin", "budget")
    return [slot for slot in required_slots if not slots.get(slot)]

def evaluate_user_intent(user_input: str, session_history: list | dict):
    # Extract slots safely regardless of type
    current_slots = session_history.get("slots", {}) if isinstance(session_history, dict) else {}
    updated_slots = extract_slots(user_input, current_slots)
    
    # Avoid dict key assignment if session_history is a list
    if isinstance(session_history, dict):
        session_history["slots"] = updated_slots
    """
    Acts as the entry guardrail. Checks if the user wants to reset 
    BEFORE triggering the heavy CrewAI execution pipeline.
    """
    #1 Check for Reset Guardrail
    reset_pattern = r"\b(?:cancel|restart|reset|start over|never mind)\b"
    intent_result = {
        "status": "RESET" if re.search(reset_pattern, user_input, re.IGNORECASE) else "PROCEED"
    }
    if intent_result.get("status") == "RESET":
        session_history.clear()  # Clear session context
        return "Search cancelled. What new game are you looking for?"

    # Safely get current slots if session_history happens to be a dict, otherwise fallback to empty dict
    current_slots = session_history.get("slots", {}) if isinstance(session_history, dict) else {}
    
    # Extract updated slots
    updated_slots = extract_slots(user_input, current_slots)

    # 3. GATEKEEPER: Check if mandatory inputs are present
    missing_slots = get_missing_slots(updated_slots) # e.g. checks if 'origin' or 'game' is missing
    
    if missing_slots:
        # DO NOT call TravelCrew here. Ask the clarifying question instead.
        if "origin" in missing_slots:
            return "Got it! Will you be flying in for the game, or are you local?"
        elif "budget" in missing_slots:
            return "What is your budget for this trip?"

    # 4. ALL SLOTS READY: Trigger CrewAI Agents now
    crew = TravelCrew(inputs=updated_slots)
    return crew.run()

    messages = [
        {"role": "system", "content": GAME_TIME_SYSTEM_PROMPT},
        *session_history,
        {"role": "user", "content": user_input}
    ]

    response = openai.chat.completions.create(
        model="gpt-5.6-sol",
        messages=messages,
        tools=[RESET_TOOL_DEFINITION],
        tool_choice="auto"
    )

    # Check if LLM requested reset_search tool call
    message = response.choices[0].message
    if message.tool_calls:
        for tool_call in message.tool_calls:
            if tool_call.function.name == "reset_search":
                return {"status": "RESET", "message": "Search reset requested."}

    return {"status": "PROCEED", "content": message.content}


# ==========================================
# 3. HELPER FUNCTIONS & CUSTOM TOOLS
# ==========================================

def format_origin_location(raw_origin: str) -> str:
    if not raw_origin:
        return ""
    cleaned = raw_origin.strip()
    parts = [p.strip() for p in re.split(r'[, ]+', cleaned) if p.strip()]
    if len(parts) >= 2 and len(parts[-1]) == 2:
        return f"{' '.join(parts[:-1]).title()}, {parts[-1].upper()}"
    return cleaned.title()

@tool("Google Search Scraper")
def google_search_scraper(query: str) -> str:
    """Scrapes Google Search results for real-time ticket, flight, and hotel info."""
    api_key = os.environ.get("SERPER_API_KEY", "")
    if not api_key:
        return "Error: SERPER_API_KEY environment variable is not set."

    url = "https://google.serper.dev/search"
    payload = {"q": query, "num": 3}
    headers = {'X-API-KEY': api_key, 'Content-Type': 'application/json'}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=12)
        if response.status_code == 200:
            results = response.json()
            output = []
            for item in results.get("organic", []):
                output.append(f"Title: {item.get('title')}\nLink: {item.get('link')}\nInfo: {item.get('snippet')}\n---")
            return "\n".join(output) if output else "No results found."
        return f"Search scraper failed. Status code: {response.status_code}"
    except Exception as e:
        return f"Error executing search scrape: {str(e)}"


# ==========================================
# 4. CREWAI AGENTS & PIPELINE
# ==========================================
crew_llm = LLM(model="gpt-5.6-terra", temperature=0.7)

class TravelCrew:
    def __init__(self, inputs: dict):
        self.inputs = inputs
        if "origin" in self.inputs:
            self.inputs["origin"] = format_origin_location(str(self.inputs["origin"]))

    # ==========================================
    # AGENT DEFINITIONS
    # ==========================================
    def ticket_agent(self) -> Agent:
        return Agent(
            role="Sports Ticket Specialist",
            goal="Find available stadium seating and current ticket pricing",
            backstory="An expert sports ticket broker who finds best seat value and links.",
            tools=[google_search_scraper],
            llm=crew_llm,
            verbose=False
        )

    def flight_agent(self) -> Agent:
        return Agent(
            role="Flight Booking Expert",
            goal="Find optimal flight routes and pricing for fan travel",
            backstory="A seasoned travel agent who specializes in roundtrip event flights.",
            tools=[google_search_scraper],
            llm=crew_llm,
            verbose=False
        )

    def hotel_agent(self) -> Agent:
        return Agent(
            role="Hotel & Lodging Specialist",
            goal="Find top-rated hotels close to the game venue",
            backstory="A travel scout who specializes in conveniently located accommodations.",
            tools=[google_search_scraper],
            llm=crew_llm,
            verbose=False
        )

    def coordinator_agent(self) -> Agent:
        return Agent(
            role="Sports Trip Coordinator",
            goal="Synthesize tickets, flights, and hotels into a budget-friendly itinerary",
            backstory="A master itinerary planner who structures trips under budget with markdown formatting.",
            llm=crew_llm,
            verbose=False
        )

    # ==========================================
    # EXECUTION PIPELINE
    # ==========================================
    async def run(self):
        ticket_agent_inst = self.ticket_agent()
        hotel_agent_inst = self.hotel_agent()
        coordinator_agent_inst = self.coordinator_agent()
        # ... rest of your run code stays the same ...

    async def run(self):
        ticket_agent_inst = self.ticket_agent()
        hotel_agent_inst = self.hotel_agent()
        coordinator_agent_inst = self.coordinator_agent()

        is_local = self.inputs.get('origin', '').lower() in ['local', 'none', '']

        # 1. MARK SCRAPING TASKS AS ASYNCHRONOUS (Run in Parallel)
        ticket_task = Task(
            description=f"Find 2 ticket options for {self.inputs.get('game')} on {self.inputs.get('date')}.",
            expected_output="2 ticket options with seat details, prices, and booking links.",
            agent=ticket_agent_inst,
            async_execution=True  # <-- Enables parallel execution
        )

        hotel_task = Task(
            description=f"Search 2 top-rated hotels close to the venue for {self.inputs.get('game')}.",
            expected_output="2 hotel options with nightly rates, ratings, and booking links.",
            agent=hotel_agent_inst,
            async_execution=True  # <-- Enables parallel execution
        )

        tasks = [ticket_task, hotel_task]

        if not is_local:
            flight_agent_inst = self.flight_agent()
            flight_task = Task(
                description=f"Search flights from {self.inputs.get('origin')} for {self.inputs.get('date')}.",
                expected_output="Flight options with numbers, times, prices, and booking links.",
                agent=flight_agent_inst,
                async_execution=True  # <-- Enables parallel execution
            )
            tasks.append(flight_task)

        # 2. FINAL SYNTHESIS TASK (Runs sequentially AFTER parallel tasks finish)
        coordinator_task = Task(
            description=f"Synthesize ticket, hotel, and flight choices into a plan under ${self.inputs.get('budget')}.",
            expected_output="A styled markdown itinerary with budget breakdown table and booking links.",
            agent=coordinator_agent_inst,
            async_execution=False  # Must wait for previous tasks to complete
        )
        tasks.append(coordinator_task)

        # 3. INITIALIZE CREW
        crew = Crew(
            agents=[t.agent for t in tasks],
            tasks=tasks,
            process=Process.sequential, # Keep sequential so coordinator waits for parallel tasks
            verbose=False # Set to False for faster execution overhead
        )

        result = await crew.kickoff_async()
        return str(result.raw)  # or str(result)