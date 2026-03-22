#!/usr/bin/env python3
"""Lattice demo — full engine execution with rich console output.

Runs all reference capabilities (VendorOnboarding, EquipmentProcurement,
TripPlanning) through the Lattice runtime with stub clients, then prints
the projection results and audit trail.

Usage:
    python -m demo.run_demo          (from the project root)
    python demo/run_demo.py          (from the project root)
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from demo.procurement.capabilities.vendor_onboarding import vendor_onboarding
from demo.procurement.capabilities.equipment_procurement import equipment_procurement
from demo.travel.capabilities.trip_planning import trip_planning
from demo.stubs import client_factory
from lattice.auth.scopes import CredentialStore
from lattice.runtime.engine import Engine

console = Console()


def print_projection(name: str, result: dict) -> None:
    console.print(
        Panel(
            json.dumps(result, indent=2, default=str),
            title=f"[bold green]{name} — Projection[/bold green]",
            border_style="green",
        )
    )


def print_audit(engine: Engine) -> None:
    record = engine.audit_trail.records[-1]

    table = Table(
        title=f"Audit Trail — {record.capability_name} v{record.capability_version}",
        show_lines=True,
    )
    table.add_column("Field", style="bold")
    table.add_column("Value")

    table.add_row("Execution ID", record.execution_id)
    table.add_row("Requester", record.requester)
    table.add_row(
        "Status",
        f"[green]{record.status}[/green]" if record.status == "completed" else record.status,
    )
    table.add_row("Duration", f"{record.duration_ms:.0f} ms")
    table.add_row("Scopes", ", ".join(record.granted_scopes))
    console.print(table)

    steps_table = Table(title="Steps", show_lines=True)
    steps_table.add_column("Step")
    steps_table.add_column("Status")
    steps_table.add_column("Attempts")
    steps_table.add_column("Scope")
    steps_table.add_column("Duration (ms)")

    for s in record.steps:
        status_str = f"[green]{s.status}[/green]" if s.status == "completed" else s.status
        steps_table.add_row(
            s.step_name,
            status_str,
            str(s.attempts),
            s.scope or "",
            f"{s.duration_ms:.1f}" if s.duration_ms else "-",
        )
    console.print(steps_table)


async def run_vendor_onboarding(engine: Engine) -> None:
    console.rule("[bold blue]VendorOnboarding (Procurement)[/bold blue]")

    creds = CredentialStore(
        granted_scopes={"compliance.read", "vendor.write"},
    )

    result = await engine.execute(
        vendor_onboarding,
        inputs={
            "vendor_name": "Acme Corp",
            "vendor_type": "supplier",
            "region": "US",
        },
        credentials=creds,
        client_factory=client_factory,
        requester="demo-runner",
    )

    print_projection("VendorOnboarding", result)
    print_audit(engine)


async def run_equipment_procurement(engine: Engine) -> None:
    console.rule("[bold blue]EquipmentProcurement (Procurement)[/bold blue]")

    creds = CredentialStore(
        granted_scopes={
            "budget.read",
            "budget.write",
            "vendor.read",
            "approval.read",
            "approval.write",
        },
    )

    result = await engine.execute(
        equipment_procurement,
        inputs={
            "item": "Standing Desk",
            "quantity": 10,
            "budget_department": "engineering",
            "preferred_vendor_id": "V-10001",
            "requested_by": "alex.johnson@company.com",
        },
        credentials=creds,
        client_factory=client_factory,
        requester="demo-runner",
    )

    print_projection("EquipmentProcurement", result)
    print_audit(engine)


async def run_trip_planning(engine: Engine) -> None:
    console.rule("[bold blue]TripPlanning (Travel)[/bold blue]")

    creds = CredentialStore(
        granted_scopes={
            "travel.read",
            "travel.approve",
            "travel.book",
            "budget.write",
        },
    )

    result = await engine.execute(
        trip_planning,
        inputs={
            "traveler_email": "jane.doe@company.com",
            "origin": "SFO",
            "destination": "NYC",
            "departure_date": "2026-04-15",
            "return_date": "2026-04-17",
            "department": "engineering",
        },
        credentials=creds,
        client_factory=client_factory,
        requester="demo-runner",
    )

    print_projection("TripPlanning", result)
    print_audit(engine)


async def main() -> None:
    console.print(
        Panel(
            "[bold]Lattice Demo[/bold] — End-to-end runtime execution\n"
            "Running all reference capabilities with stub API clients.\n\n"
            "[dim]Domains: Procurement, Travel[/dim]",
            border_style="blue",
        )
    )

    engine = Engine()

    await run_vendor_onboarding(engine)
    console.print()
    await run_equipment_procurement(engine)
    console.print()
    await run_trip_planning(engine)

    console.print()
    console.rule("[bold green]Demo complete[/bold green]")
    console.print(
        f"[dim]Total executions: {len(engine.audit_trail.records)}, "
        f"all completed successfully.[/dim]"
    )


if __name__ == "__main__":
    asyncio.run(main())
