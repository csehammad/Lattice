"""Client factory for the Lattice engine.

Maps client names used in @capability steps to the httpx-based
client instances that call the live HR System API.
"""

from __future__ import annotations

import os

from hr_lattice.clients import (
    BenefitsClient,
    DepartmentClient,
    EmployeeClient,
    OnboardingClient,
    PayrollClient,
    PerformanceClient,
    PositionClient,
)

HR_API_URL = os.environ.get("HR_API_URL", "http://localhost:8000")

_CLIENTS: dict = {
    "employees": EmployeeClient(HR_API_URL),
    "departments": DepartmentClient(HR_API_URL),
    "positions": PositionClient(HR_API_URL),
    "payroll": PayrollClient(HR_API_URL),
    "performance": PerformanceClient(HR_API_URL),
    "onboarding": OnboardingClient(HR_API_URL),
    "benefits": BenefitsClient(HR_API_URL),
}


def client_factory(name: str, credentials=None):
    if name not in _CLIENTS:
        raise KeyError(f"No client registered for '{name}'. Available: {sorted(_CLIENTS)}")
    return _CLIENTS[name]
