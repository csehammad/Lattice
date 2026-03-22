"""Capability: TripPlanning

Composes flight search, hotel search, loyalty lookup, policy check,
approval, budget allocation, and booking into a single outcome.

This is the travel scenario described in the Lattice README — the model
submits a trip intent and receives a structured projection with booking
confirmations, policy status, budget impact, and actionable options.

Endpoints used:
  - searchFlights         flight_search_api
  - searchHotels          hotel_search_api
  - lookupLoyalty         loyalty_api
  - checkTravelPolicy     travel_policy_api
  - submitApproval        travel_approval_api
  - checkBudget           travel_budget_api
  - allocateBudget        travel_budget_api
  - bookFlight            flight_search_api
  - bookHotel             hotel_search_api
"""

from lattice import capability, projection, state, step
from lattice.failure import abort, hard_failure, retry, soft_failure


class ServerError(Exception):
    pass


@capability(
    name="TripPlanning",
    version="1.0",
    inputs={
        "traveler_email": str,
        "origin": str,
        "destination": str,
        "departure_date": str,
        "return_date": str,
        "department": str,
    },
    projection={
        "status": {
            "type": str,
            "example": "booked",
            "description": "Trip status (booked, approved_pending_booking, blocked)",
        },
        "flight_confirmation": {
            "type": str,
            "example": "BK-482910",
            "description": "Flight booking confirmation code",
        },
        "hotel_confirmation": {
            "type": str,
            "example": "HBK-193847",
            "description": "Hotel booking confirmation code",
        },
        "total_cost": {
            "type": float,
            "example": 1278.0,
            "description": "Total trip cost (flight + hotel) in USD",
        },
        "policy_status": {
            "type": str,
            "example": "compliant",
            "description": "Travel policy compliance status",
        },
        "budget_remaining": {
            "type": float,
            "example": 6722.0,
            "description": "Department travel budget remaining after this trip",
        },
        "loyalty_tier": {
            "type": str,
            "example": "gold",
            "description": "Traveler's loyalty program tier",
        },
    },
)
async def trip_planning(ctx):

    @step(depends_on=[], scope="travel.read")
    @retry(max=3, backoff="exponential", on=[TimeoutError, ServerError])
    @hard_failure(on_exhausted=abort)
    async def search_flights():
        client = ctx.client("flight_search_api")
        result = await client.search(
            origin=ctx.intent.origin,
            destination=ctx.intent.destination,
            date=ctx.intent.departure_date,
            passengers=1,
        )
        best = result.flights[0]
        return {
            "flight_id": best.flight_id,
            "airline": best.airline,
            "price": best.price,
            "departure": best.departure,
            "arrival": best.arrival,
            "alternatives": len(result.flights),
        }

    @step(depends_on=[], scope="travel.read")
    @retry(max=3, backoff="exponential", on=[TimeoutError, ServerError])
    @soft_failure(
        fallback={
            "hotel_id": None,
            "hotel_name": "none",
            "total_hotel_cost": 0.0,
            "warning": "hotel search unavailable",
        }
    )
    async def search_hotels():
        client = ctx.client("hotel_search_api")
        result = await client.search(
            city=ctx.intent.destination,
            check_in=ctx.intent.departure_date,
            check_out=ctx.intent.return_date,
            guests=1,
        )
        best = result.hotels[0]
        nights = 2
        return {
            "hotel_id": best.hotel_id,
            "hotel_name": best.name,
            "rate_per_night": best.rate_per_night,
            "total_hotel_cost": best.rate_per_night * nights,
            "nights": nights,
        }

    @step(depends_on=[])
    @soft_failure(fallback={"tier": "unknown", "points": 0, "programs": []})
    async def lookup_loyalty():
        client = ctx.client("loyalty_api")
        result = await client.lookup(employee_email=ctx.intent.traveler_email)
        return {
            "tier": result.tier,
            "points": result.points,
            "programs": result.airline_programs + result.hotel_programs,
        }

    @step(depends_on=[search_flights, search_hotels], scope="travel.read")
    @retry(max=2, on=[TimeoutError, ServerError])
    @hard_failure(on_exhausted=abort)
    async def check_policy():
        total = state.search_flights.price + state.search_hotels.total_hotel_cost
        client = ctx.client("travel_policy_api")
        result = await client.check(
            employee_email=ctx.intent.traveler_email,
            department=ctx.intent.department,
            total_amount=total,
            trip_type="domestic",
        )
        return {
            "compliant": result.compliant,
            "violations": result.violations,
            "requires_approval": result.requires_approval,
            "total_amount": total,
        }

    @step(depends_on=[check_policy], scope="travel.approve")
    @retry(max=2, on=[TimeoutError, ServerError])
    @soft_failure(
        fallback={
            "approval_id": None,
            "approval_status": "pending",
            "warning": "auto-approval failed",
        }
    )
    async def request_approval():
        if not state.check_policy.requires_approval:
            return {
                "approval_id": "AUTO",
                "approval_status": "auto_approved",
            }
        client = ctx.client("travel_approval_api")
        result = await client.submit(
            requester=ctx.intent.traveler_email,
            manager="manager@company.com",
            amount=state.check_policy.total_amount,
            details={
                "origin": ctx.intent.origin,
                "destination": ctx.intent.destination,
                "departure": ctx.intent.departure_date,
                "return": ctx.intent.return_date,
            },
        )
        return {
            "approval_id": result.request_id,
            "approval_status": result.status,
        }

    @step(depends_on=[request_approval], scope="budget.write")
    @retry(max=2, on=[TimeoutError, ServerError])
    @hard_failure(on_exhausted=abort)
    async def allocate_budget():
        client = ctx.client("travel_budget_api")
        result = await client.allocate(
            department=ctx.intent.department,
            amount=state.check_policy.total_amount,
            reference=state.request_approval.approval_id,
        )
        return {
            "allocated": result.allocated,
            "remaining_after": result.remaining_after,
        }

    @step(depends_on=[allocate_budget], scope="travel.book")
    @retry(max=2, on=[TimeoutError, ServerError])
    @hard_failure(on_exhausted=abort)
    async def book_flight():
        client = ctx.client("flight_search_api")
        result = await client.book(
            flight_id=state.search_flights.flight_id,
            passenger_name=ctx.intent.traveler_email,
        )
        return {
            "confirmation": result.confirmation,
            "status": result.status,
        }

    @step(depends_on=[allocate_budget], scope="travel.book")
    @retry(max=2, on=[TimeoutError, ServerError])
    @soft_failure(fallback={"confirmation": "NONE", "status": "skipped"})
    async def book_hotel():
        if state.search_hotels.hotel_id is None:
            return {"confirmation": "NONE", "status": "no_hotel_found"}
        client = ctx.client("hotel_search_api")
        result = await client.book(
            hotel_id=state.search_hotels.hotel_id,
            guest_name=ctx.intent.traveler_email,
            check_in=ctx.intent.departure_date,
            check_out=ctx.intent.return_date,
        )
        return {
            "confirmation": result.confirmation,
            "status": result.status,
        }

    is_booked = (
        state.book_flight.status == "confirmed"
        and state.request_approval.approval_status in ("approved", "auto_approved")
    )

    return projection(
        status="booked" if is_booked else "blocked",
        flight_confirmation=state.book_flight.confirmation,
        hotel_confirmation=state.book_hotel.confirmation,
        total_cost=state.check_policy.total_amount,
        policy_status="compliant" if state.check_policy.compliant else "violation",
        budget_remaining=state.allocate_budget.remaining_after,
        loyalty_tier=state.lookup_loyalty.tier,
    )
