from __future__ import annotations


def normalize(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def split_full_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split(maxsplit=1)
    if len(parts) != 2:
        raise ValueError("full_name must include first and last name")
    return parts[0], parts[1]


async def resolve_department(client, department: str) -> dict:
    result = await client.list()
    wanted = normalize(department)
    for entry in result["departments"]:
        if normalize(entry["id"]) == wanted or normalize(entry["name"]) == wanted:
            return entry
    raise ValueError(f"Department '{department}' not found")


async def resolve_position(client, position_title: str) -> dict:
    result = await client.list()
    wanted = normalize(position_title)
    for entry in result["positions"]:
        if normalize(entry["id"]) == wanted or normalize(entry["title"]) == wanted:
            return entry
    raise ValueError(f"Position '{position_title}' not found")


async def resolve_employee(client, employee: str) -> dict:
    result = await client.list()
    wanted = normalize(employee)
    for entry in result["employees"]:
        full_name = f"{entry['first_name']} {entry['last_name']}"
        if (
            normalize(entry["id"]) == wanted
            or normalize(entry["email"]) == wanted
            or normalize(full_name) == wanted
        ):
            return entry
    raise ValueError(f"Employee '{employee}' not found")
