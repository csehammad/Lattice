"""HTTP clients that wrap the HR System API.

Each class maps one-to-one with an API resource and makes real
httpx async calls.  The Lattice capabilities use these via
ctx.client("resource_name").
"""

from __future__ import annotations

import httpx


class EmployeeClient:
    def __init__(self, base_url: str) -> None:
        self._base = base_url

    async def list(
        self,
        department_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        params: dict = {}
        if department_id:
            params["department_id"] = department_id
        if status:
            params["status"] = status
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self._base}/employees", params=params)
            r.raise_for_status()
            return r.json()

    async def get(self, employee_id: str) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self._base}/employees/{employee_id}")
            r.raise_for_status()
            return r.json()

    async def create(self, **kwargs) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{self._base}/employees", json=kwargs)
            r.raise_for_status()
            return r.json()

    async def update(self, employee_id: str, **kwargs) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.put(f"{self._base}/employees/{employee_id}", json=kwargs)
            r.raise_for_status()
            return r.json()

    async def profile(self, employee_id: str) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self._base}/employees/{employee_id}/profile")
            r.raise_for_status()
            return r.json()


class DepartmentClient:
    def __init__(self, base_url: str) -> None:
        self._base = base_url

    async def list(self) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self._base}/departments")
            r.raise_for_status()
            return r.json()

    async def get(self, dept_id: str) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self._base}/departments/{dept_id}")
            r.raise_for_status()
            return r.json()

    async def headcount(self, dept_id: str) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self._base}/departments/{dept_id}/headcount")
            r.raise_for_status()
            return r.json()


class PositionClient:
    def __init__(self, base_url: str) -> None:
        self._base = base_url

    async def list(self) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self._base}/positions")
            r.raise_for_status()
            return r.json()

    async def get(self, position_id: str) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self._base}/positions/{position_id}")
            r.raise_for_status()
            return r.json()


class PayrollClient:
    def __init__(self, base_url: str) -> None:
        self._base = base_url

    async def get(self, employee_id: str) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self._base}/payroll/{employee_id}")
            r.raise_for_status()
            return r.json()

    async def update(self, employee_id: str, **kwargs) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.put(f"{self._base}/payroll/{employee_id}", json=kwargs)
            r.raise_for_status()
            return r.json()

    async def run(self, department_id: str, pay_period: str) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.post(
                f"{self._base}/payroll/runs",
                json={"department_id": department_id, "pay_period": pay_period},
            )
            r.raise_for_status()
            return r.json()

    async def get_run(self, run_id: str) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self._base}/payroll/runs/{run_id}")
            r.raise_for_status()
            return r.json()


class PerformanceClient:
    def __init__(self, base_url: str) -> None:
        self._base = base_url

    async def create_review(self, **kwargs) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{self._base}/performance/reviews", json=kwargs)
            r.raise_for_status()
            return r.json()

    async def get_reviews(self, employee_id: str) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self._base}/performance/reviews/{employee_id}")
            r.raise_for_status()
            return r.json()


class OnboardingClient:
    def __init__(self, base_url: str) -> None:
        self._base = base_url

    async def start(self, employee_id: str) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.post(
                f"{self._base}/onboarding",
                json={"employee_id": employee_id},
            )
            r.raise_for_status()
            return r.json()

    async def status(self, employee_id: str) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self._base}/onboarding/{employee_id}/status")
            r.raise_for_status()
            return r.json()


class BenefitsClient:
    def __init__(self, base_url: str) -> None:
        self._base = base_url

    async def enroll(self, employee_id: str, plan_ids: list[str]) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.post(
                f"{self._base}/benefits/enroll",
                json={"employee_id": employee_id, "plan_ids": plan_ids},
            )
            r.raise_for_status()
            return r.json()

    async def get(self, employee_id: str) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self._base}/benefits/{employee_id}")
            r.raise_for_status()
            return r.json()
