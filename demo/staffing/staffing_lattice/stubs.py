"""Client factory for the Lattice engine.

Maps client names used in @capability steps to the httpx-based
client instances that call the live Staffing Platform API.
"""

from __future__ import annotations

import os

from staffing_lattice.clients import (
    AssignmentClient,
    AvailabilityClient,
    EmployeeClient,
    NotificationClient,
)

# Default to IPv4 loopback so httpx matches an embedded API bound to 0.0.0.0:8001
# (some systems resolve "localhost" to ::1 first, which would miss a v4-only listener).
STAFFING_API_URL = os.environ.get("STAFFING_API_URL", "http://127.0.0.1:8001")

_CLIENTS: dict = {
    "employee_api": EmployeeClient(STAFFING_API_URL),
    "availability_api": AvailabilityClient(STAFFING_API_URL),
    "assignment_api": AssignmentClient(STAFFING_API_URL),
    "notification_api": NotificationClient(STAFFING_API_URL),
}


def client_factory(name: str, credentials=None):
    if name not in _CLIENTS:
        raise KeyError(f"No client registered for '{name}'. Available: {sorted(_CLIENTS)}")
    return _CLIENTS[name]
