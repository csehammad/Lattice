"""HTTP clients that wrap the Staffing Platform API.

Each class maps one-to-one with an API resource group and makes real
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
        department: str | None = None,
        status: str | None = None,
    ) -> dict:
        params: dict = {}
        if department:
            params["department"] = department
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

    async def search(
        self,
        skills: list[str] | None = None,
        department: str | None = None,
        seniority: str | None = None,
        role: str | None = None,
    ) -> dict:
        body: dict = {}
        if skills:
            body["skills"] = skills
        if department:
            body["department"] = department
        if seniority:
            body["seniority"] = seniority
        if role:
            body["role"] = role
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{self._base}/employees/search", json=body)
            r.raise_for_status()
            return r.json()

    async def skills(self, employee_id: str) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self._base}/employees/{employee_id}/skills")
            r.raise_for_status()
            return r.json()


class AvailabilityClient:
    def __init__(self, base_url: str) -> None:
        self._base = base_url

    async def get(self, employee_id: str) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self._base}/employees/{employee_id}/availability")
            r.raise_for_status()
            return r.json()

    async def batch_check(self, employee_ids: list[str]) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.post(
                f"{self._base}/availability/batch-check",
                json={"employee_ids": employee_ids},
            )
            r.raise_for_status()
            return r.json()

    async def schedule(self, employee_id: str) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self._base}/employees/{employee_id}/schedule")
            r.raise_for_status()
            return r.json()


class AssignmentClient:
    def __init__(self, base_url: str) -> None:
        self._base = base_url

    async def validate(
        self,
        employee_id: str,
        allocation_pct: int,
        start_date: str,
        role: str | None = None,
    ) -> dict:
        body: dict = {
            "employee_id": employee_id,
            "allocation_pct": allocation_pct,
            "start_date": start_date,
        }
        if role:
            body["role"] = role
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{self._base}/assignments/validate", json=body)
            r.raise_for_status()
            return r.json()

    async def create(
        self,
        employee_id: str,
        allocation_pct: int,
        start_date: str,
        role: str,
        requested_by: str,
    ) -> dict:
        body = {
            "employee_id": employee_id,
            "allocation_pct": allocation_pct,
            "start_date": start_date,
            "role": role,
            "requested_by": requested_by,
        }
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{self._base}/assignments", json=body)
            r.raise_for_status()
            return r.json()

    async def get(self, assignment_id: str) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self._base}/assignments/{assignment_id}")
            r.raise_for_status()
            return r.json()

    async def update(self, assignment_id: str, **kwargs) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.put(
                f"{self._base}/assignments/{assignment_id}",
                json=kwargs,
            )
            r.raise_for_status()
            return r.json()

    async def cancel(self, assignment_id: str) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.delete(f"{self._base}/assignments/{assignment_id}")
            r.raise_for_status()
            return r.json()


class NotificationClient:
    def __init__(self, base_url: str) -> None:
        self._base = base_url

    async def send(
        self,
        recipients: list[str],
        message_type: str,
        details: dict,
    ) -> dict:
        body = {
            "recipients": recipients,
            "message_type": message_type,
            "details": details,
        }
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{self._base}/notifications/send", json=body)
            r.raise_for_status()
            return r.json()

    async def get(self, notification_id: str) -> dict:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self._base}/notifications/{notification_id}")
            r.raise_for_status()
            return r.json()
