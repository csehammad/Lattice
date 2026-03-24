"""Name-to-ID resolution helpers for the staffing domain.

Capability steps accept human-friendly names from the agent intent
and resolve them to internal identifiers via the API.
"""

from __future__ import annotations


def _normalize(value: str) -> str:
    return " ".join(value.strip().casefold().split())


async def resolve_project(client, project_name: str) -> dict:
    """Search projects by name and return the first matching project dict."""
    result = await client.search(name=project_name)
    wanted = _normalize(project_name)
    for entry in result.get("projects", []):
        if (
            _normalize(entry["id"]) == wanted
            or _normalize(entry["name"]) == wanted
            or wanted in _normalize(entry["name"])
            or _normalize(entry["name"]) in wanted
        ):
            return entry
    raise ValueError(f"Project '{project_name}' not found")


async def resolve_employee(client, employee: str) -> dict:
    """Find an employee by ID, name, or email."""
    result = await client.list()
    wanted = _normalize(employee)
    for entry in result.get("employees", []):
        full_name = f"{entry['first_name']} {entry['last_name']}"
        if (
            _normalize(entry["id"]) == wanted
            or _normalize(entry.get("email", "")) == wanted
            or _normalize(full_name) == wanted
        ):
            return entry
    raise ValueError(f"Employee '{employee}' not found")
