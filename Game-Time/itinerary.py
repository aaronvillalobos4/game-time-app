"""Structured planning output with server-calculated USD trip totals."""
from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit
from pydantic import BaseModel, ConfigDict, Field, model_validator


class CostItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Literal["tickets", "hotel", "flights", "transport", "food", "activity", "fees"]
    name: str = Field(min_length=1, max_length=200)
    basis: str = Field(min_length=1, max_length=600, description="Counts, dates, per-unit basis, taxes and fee assumptions")
    quantity: int = Field(default=1, ge=1, le=10000)
    unit_low: Decimal | None = Field(default=None, ge=0, le=1000000, decimal_places=2, allow_inf_nan=False)
    unit_high: Decimal | None = Field(default=None, ge=0, le=1000000, decimal_places=2, allow_inf_nan=False)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    selected: bool = True
    optional: bool = False
    provider: str = Field(default="Provider", max_length=100)
    booking_url: str | None = Field(default=None, max_length=3000)
    evidence: str = Field(min_length=1, max_length=700, description="Source name and quote/estimate basis, or why price is unavailable")

    @model_validator(mode="after")
    def validate_cost(self):
        if (self.unit_low is None) != (self.unit_high is None):
            raise ValueError("Supply both price bounds or neither")
        if self.unit_low is not None and self.unit_high < self.unit_low:
            raise ValueError("Price bounds reversed")
        if self.optional and self.selected:
            raise ValueError("Optional suggestions cannot also be selected costs")
        if self.booking_url:
            url = urlsplit(self.booking_url)
            if url.scheme != "https" or not url.hostname or url.username or any(c.isspace() for c in self.booking_url):
                raise ValueError("Booking URLs must be valid HTTPS links")
        return self


class PlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    time: str = Field(min_length=1, max_length=150)
    activity: str = Field(min_length=1, max_length=200)
    details: str = Field(min_length=1, max_length=700)


class ItineraryPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    venue: str = Field(default="TBD", max_length=300)
    timezone: str = Field(default="TBD", max_length=100)
    game_start: str = Field(default="TBD", max_length=150)
    assumptions: list[str] = Field(default_factory=list, max_length=15)
    changes: list[str] = Field(default_factory=list, max_length=10)
    steps: list[PlanStep] = Field(min_length=1, max_length=48)
    costs: list[CostItem] = Field(min_length=1, max_length=40)
    checklist: list[str] = Field(default_factory=list, max_length=15)

    @model_validator(mode="after")
    def one_recommended_combination(self):
        for category in ("tickets", "hotel", "flights"):
            if sum(c.selected and c.category == category for c in self.costs) > 1:
                raise ValueError(f"Select only one {category} option; combine units using quantity")
        return self


STRUCTURED_ITINERARY = """
OUTPUT CONTRACT: Return ItineraryPlan structured data, not Markdown. The server
renders the itinerary and calculates all totals. Never put totals or budget-fit
claims in text fields. Supply costs for tickets, lodging, transport, fees, food
and flights when required, including unknown essential costs with null bounds.
Prices are per unit; quantity is the multiplier (e.g. rooms times nights).
Exact prices have equal low/high bounds. Never invent estimates. Keep original
currency; do not invent currency conversions. Explain source and fees in evidence
and basis. Select exactly one recommended ticket/hotel/flight combination; mark
alternatives selected=false. Optional extras are selected=false, optional=true;
their combined costs form one suggested combination. Chosen extras instead belong
in selected costs, once only. Include unknown taxes/fees as an unpriced fee item
unless research establishes they are included. Preserve exact supplied URLs and
use provider names for link labels. Include hour-by-hour steps, verified timezone
and start or TBD; use relative hours if start is unknown. Label planning times
Suggested and game duration estimated. Do not put optional paid ideas into steps
as confirmed activities. Record one-traveler/one-night assumptions when unspecified.
Offer up to three optional dinner/local attraction ideas from research. Include
tax, tip and transport allowances in their bounds; never claim an unsupported
price is free. Explicitly use a sourced zero-cost item for lodging/transport/fees
that are not needed or already included, with the reason in basis. No double
counting included fees. Verify the actual host city instead of assuming home turf.
For revisions return the entire updated plan with a short changes list. Do not
include calculated totals copied from the previous itinerary. Text fields are
plain descriptions, not independently formatted tables or budget calculations.
"""


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def money(value):
    return f"${value:,.2f}"


def bounds(item):
    if item.unit_low is None or item.currency != "USD":
        return None
    return item.unit_low * item.quantity, item.unit_high * item.quantity


def cost_text(item):
    if item.unit_low is None:
        return "Estimate unavailable"
    low, high = item.unit_low * item.quantity, item.unit_high * item.quantity
    return f"{item.currency} {low:,.2f}" + (f"–{high:,.2f}" if low != high else "")


def booking(item):
    # Angle brackets preserve query strings/parentheses without changing URLs.
    label = item.provider.replace("[", "").replace("]", "")
    if not item.booking_url or any(c in item.booking_url for c in "<>"):
        return "Booking link unavailable"
    return f"[{cell(label)}](<{item.booking_url}>)"


def render_itinerary(plan: ItineraryPlan, inputs: dict) -> str:
    budget = Decimal(str(inputs["budget"]))
    if not budget.is_finite() or budget <= 0:
        raise ValueError("A finite positive budget is required")
    flying = inputs.get("origin", "Local").casefold() not in {"", "local", "none"}
    lodging = inputs.get("needs_hotel", True)
    eligible = [c for c in plan.costs if (flying or c.category != "flights") and (lodging or c.category != "hotel")]
    selected = [c for c in eligible if c.selected]
    required = {"tickets", "transport", "food", "fees"} | ({"hotel"} if lodging else set()) | ({"flights"} if flying else set())
    missing = sorted(required - {c.category for c in selected})
    unknown = missing + [c.name for c in selected if bounds(c) is None]
    low = sum((bounds(c)[0] for c in selected if bounds(c)), Decimal(0))
    high = sum((bounds(c)[1] for c in selected if bounds(c)), Decimal(0))
    def span(a, b):
        return money(a) if a == b else f"{money(a)}–{money(b)}"
    rows = []
    if plan.changes:
        rows += ["## What changed", "", *[f"- {cell(x)}" for x in plan.changes], ""]
    rows += ["## 🏟️ Your Game Time Trip", "",
             f"- **Matchup:** {cell(inputs['game'])}", f"- **Date:** {cell(inputs['date'])}",
             f"- **Venue / city:** {cell(plan.venue)}", f"- **Travel origin:** {cell(inputs.get('origin', 'Local'))}",
             f"- **Target budget:** {money(budget)} USD", ""]
    rows += [f"- {cell(a)}" for a in plan.assumptions]
    rows += ["", "## 📅 Game-Day Plan", "",
             f"Date: {cell(inputs['date'])}. Timezone: {cell(plan.timezone)}. Game start: {cell(plan.game_start)}.",
             "Planning times are suggestions; durations are estimates.", "",
             "| Time | Activity | Details |", "|---|---|---|"]
    rows += [f"| {cell(s.time)} | {cell(s.activity)} | {cell(s.details)} |" for s in plan.steps]
    for title, categories in [("🎟️ Ticket Options", {"tickets"}), ("🏨 Where to Stay", {"hotel"}),
                              ("✈️ Getting There" if flying else "🚗 Getting There", {"flights", "transport"})]:
        rows += ["", f"## {title}", ""]
        if not lodging and "hotel" in categories:
            rows += ["Hotel: not needed."]
        for c in eligible:
            if c.category in categories and not c.optional and (flying or c.category != "flights"):
                rows += [f"- **{cell(c.name)}** ({'Selected' if c.selected else 'Alternative'}): {cost_text(c)} — {cell(c.basis)}. {booking(c)}. {cell(c.evidence)}"]
        if not flying and "transport" in categories:
            rows += ["Flights: not needed."]
    rows += ["", "## 💰 Budget Breakdown", "", "| Item | Quantity / basis | Estimated cost | Booking link |", "|---|---|---|---|"]
    for c in selected:
        rows += [f"| {cell(c.name)} | {c.quantity} × {cell(c.basis)} | {cost_text(c)} | {booking(c)} |"]
    for name in missing:
        rows += [f"| {name.title()} | Not supplied | Estimate unavailable | Booking link unavailable |"]
    rows += ["", f"**{'Known-cost subtotal (USD only)' if unknown else 'Estimated total'}:** {span(low, high)}"]
    if unknown:
        rows += ["", "**Unpriced essential costs / conversion needed:** " + ", ".join(map(cell, unknown)) + ". Budget fit cannot be confirmed."]
    if high > budget:
        rows += [f"**Over budget{' on known costs alone' if unknown else ''}:** {money(high-budget)} (using upper estimates)."]
    elif not unknown:
        rows += [f"**Remaining budget:** {money(budget-high)} (using upper estimates)."]
    rows += ["", *[f"- {cell(c.name)}: {cell(c.evidence)}" for c in selected]]
    extras = [c for c in eligible if c.optional]
    extra_high = sum((bounds(c)[1] for c in extras if bounds(c)), Decimal(0))
    fits = bool(extras) and not unknown and all(bounds(c) is not None for c in extras) and high + extra_high < budget
    allowed = extras if fits else [c for c in extras if bounds(c) == (Decimal(0), Decimal(0))]
    if allowed:
        rows += ["", "## 🍽️ Make It a Weekend", ""]
        rows += [f"- **Optional: {cell(c.name)}** — {cost_text(c)}. {cell(c.basis)}. {cell(c.evidence)}. {booking(c)}" for c in allowed]
        if fits:
            extra_low = sum((bounds(c)[0] for c in extras), Decimal(0))
            rows += ["", f"**Optional extras allowance:** {span(extra_low, extra_high)}",
                     f"**Estimated total with extras:** {span(low+extra_low, high+extra_high)}",
                     f"**Budget left with extras:** {money(budget-high-extra_high)}"]
        else:
            rows += ["Admission may be free; transport and other incidental costs still need checking."]
        rows += ["Tell me in chat which ideas you'd like to add."]
    rows += ["", "## ✅ Before You Go", "", *[f"- {cell(x)}" for x in plan.checklist], "",
             "> Estimates and availability may change. Confirm prices, fees and times with providers. No reservations have been made."]
    return "\n".join(rows)
