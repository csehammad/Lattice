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
    ProjectClient,
    ProjectPlanClient,
)

STAFFING_API_URL = os.environ.get("STAFFING_API_URL", "http://localhost:8001")

_CLIENTS: dict = {
    "project_api": ProjectClient(STAFFING_API_URL),
    "employee_api": EmployeeClient(STAFFING_API_URL),
    "availability_api": AvailabilityClient(STAFFING_API_URL),
    "assignment_api": AssignmentClient(STAFFING_API_URL),
    "notification_api": NotificationClient(STAFFING_API_URL),
    "project_plan_api": ProjectPlanClient(STAFFING_API_URL),
}


def client_factory(name: str, credentials=None):
    if name not in _CLIENTS:
        raise KeyError(f"No client registered for '{name}'. Available: {sorted(_CLIENTS)}")
    return _CLIENTS[name]
