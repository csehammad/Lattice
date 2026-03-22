"""Stub API clients for the travel domain demo.

Simulates flight search, hotel search, loyalty lookup, policy checking,
booking, and approval services.
"""

from __future__ import annotations

import random


class _Obj:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FlightSearchClient:
    _counter = 0

    async def search(self, *, origin: str, destination: str, date: str, passengers: int):
        FlightSearchClient._counter += 1
        return _Obj(
            flights=[
                _Obj(
                    flight_id=f"FL-{7000 + FlightSearchClient._counter}",
                    airline="United Airlines",
                    departure="08:30",
                    arrival="11:45",
                    price=450.0 * passengers,
                    cabin="economy",
                ),
                _Obj(
                    flight_id=f"FL-{7100 + FlightSearchClient._counter}",
                    airline="Delta Air Lines",
                    departure="14:15",
                    arrival="17:30",
                    price=520.0 * passengers,
                    cabin="economy",
                ),
            ],
            currency="USD",
        )

    async def book(self, *, flight_id: str, passenger_name: str):
        return _Obj(
            confirmation="BK-" + str(random.randint(100000, 999999)),
            flight_id=flight_id,
            status="confirmed",
        )


class HotelSearchClient:
    _counter = 0

    async def search(self, *, city: str, check_in: str, check_out: str, guests: int):
        HotelSearchClient._counter += 1
        return _Obj(
            hotels=[
                _Obj(
                    hotel_id=f"HTL-{3000 + HotelSearchClient._counter}",
                    name="Marriott Downtown",
                    rate_per_night=189.0,
                    rating=4.3,
                ),
                _Obj(
                    hotel_id=f"HTL-{3100 + HotelSearchClient._counter}",
                    name="Hilton Airport",
                    rate_per_night=159.0,
                    rating=4.1,
                ),
            ],
            currency="USD",
        )

    async def book(self, *, hotel_id: str, guest_name: str, check_in: str, check_out: str):
        return _Obj(
            confirmation="HBK-" + str(random.randint(100000, 999999)),
            hotel_id=hotel_id,
            status="confirmed",
        )


class LoyaltyClient:
    async def lookup(self, *, employee_email: str):
        return _Obj(
            tier="gold",
            points=45200,
            airline_programs=["United MileagePlus", "Delta SkyMiles"],
            hotel_programs=["Marriott Bonvoy"],
        )


class TravelPolicyClient:
    async def check(
        self,
        *,
        employee_email: str,
        department: str,
        total_amount: float,
        trip_type: str,
    ):
        if total_amount > 3000:
            return _Obj(
                compliant=False,
                violations=[
                    {
                        "policy": "Department Travel Limit",
                        "threshold": 3000,
                        "current": total_amount,
                    },
                ],
                requires_approval=True,
                approval_threshold=2000,
            )
        return _Obj(
            compliant=True,
            violations=[],
            requires_approval=total_amount > 2000,
            approval_threshold=2000,
        )


class TravelApprovalClient:
    async def submit(self, *, requester: str, manager: str, amount: float, details: dict):
        return _Obj(
            request_id="TAPR-" + str(random.randint(1000, 9999)),
            status="approved",
            approver=manager,
        )


class TravelBudgetClient:
    _remaining = 8000.0

    async def check(self, *, department: str):
        return _Obj(
            department=department,
            annual_limit=15000.0,
            spent=15000.0 - TravelBudgetClient._remaining,
            remaining=TravelBudgetClient._remaining,
        )

    async def allocate(self, *, department: str, amount: float, reference: str):
        TravelBudgetClient._remaining -= amount
        return _Obj(
            allocated=amount,
            remaining_after=TravelBudgetClient._remaining,
        )


_CLIENT_MAP = {
    "flight_search_api": FlightSearchClient(),
    "hotel_search_api": HotelSearchClient(),
    "loyalty_api": LoyaltyClient(),
    "travel_policy_api": TravelPolicyClient(),
    "travel_approval_api": TravelApprovalClient(),
    "travel_budget_api": TravelBudgetClient(),
}


def client_factory(name: str, credentials=None):
    if name not in _CLIENT_MAP:
        raise KeyError(f"No stub client registered for '{name}'. Available: {sorted(_CLIENT_MAP)}")
    return _CLIENT_MAP[name]
