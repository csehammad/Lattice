#!/usr/bin/env python3
"""Lattice demo — real interactive Search-then-Execute demo.

This is the user-facing Procurement + Travel demo entrypoint.
It uses an OpenAI-backed agent with the two Lattice meta-tools:
  search_capabilities
  execute_capability

Usage:
    python -m demo.run_demo
    python demo/run_demo.py

Optional:
    python -m demo.run_demo --model gpt-5.4-mini
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from demo.agent.agent import LatticeAgent
from demo.procurement.capabilities.equipment_procurement import equipment_procurement
from demo.procurement.capabilities.vendor_onboarding import vendor_onboarding
from demo.stubs import client_factory
from demo.travel.capabilities.trip_planning import trip_planning
from lattice.runtime.engine import Engine
from lattice.runtime.registry import CapabilityRegistry, LazyRegistry

console = Console()
MANIFEST_PATH = Path(__file__).resolve().parent / "agent" / "registry.json"


def _load_api_env() -> None:
    api_env = Path(__file__).resolve().parent.parent / "api.env"
    if not api_env.exists():
        return
    for line in api_env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())
        else:
            os.environ.setdefault("OPENAI_API_KEY", line)


def build_manifest() -> Path:
    eager = CapabilityRegistry()
    eager.register(vendor_onboarding)
    eager.register(equipment_procurement)
    eager.register(trip_planning)
    eager.save(MANIFEST_PATH)
    return MANIFEST_PATH


def build_agent(model: str) -> LatticeAgent:
    manifest_path = build_manifest()
    lazy = LazyRegistry.from_manifest(manifest_path)
    engine = Engine()
    return LatticeAgent(
        lazy_registry=lazy,
        engine=engine,
        client_factory=client_factory,
        openai_model=model,
    )


def print_audit_compact(agent: LatticeAgent) -> None:
    record = agent.last_audit
    if record is None:
        return

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(style="dim")
    table.add_column()

    table.add_row("Capability", f"{record.capability_name} v{record.capability_version}")
    table.add_row("Status", f"[green]{record.status}[/green]")
    table.add_row("Steps", str(len(record.steps)))
    table.add_row("Duration", f"{record.duration_ms:.0f}ms")
    table.add_row("Loaded on demand", "[cyan]yes[/cyan]")
    table.add_row("Execution ID", f"[dim]{record.execution_id}[/dim]")

    console.print(Panel(table, title="[dim]Lattice Execution[/dim]", border_style="dim"))


async def run_interactive(agent: LatticeAgent) -> None:
    prev_audit_count = len(agent.engine.audit_trail.records)
    console.print("[dim]Interactive mode. Type your request. 'quit' to exit.[/dim]\n")
    while True:
        try:
            user_input = console.input("[bold green]You:[/bold green] ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye.[/dim]")
            break
        if user_input.strip().lower() in ("quit", "exit", "q"):
            console.print("[dim]Goodbye.[/dim]")
            break
        if not user_input.strip():
            continue
        try:
            with console.status("[dim]Agent thinking...[/dim]"):
                reply = await agent.handle_message(user_input)
            current_audit_count = len(agent.engine.audit_trail.records)
            if current_audit_count > prev_audit_count:
                print_audit_compact(agent)
                prev_audit_count = current_audit_count
            console.print(f"\n[bold blue]Agent:[/bold blue] {reply}\n")
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]\n")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run the real Lattice demo.")
    parser.add_argument("--model", default="gpt-4o", help="OpenAI model name.")
    args = parser.parse_args()

    _load_api_env()
    if not os.environ.get("OPENAI_API_KEY"):
        console.print("[red]OPENAI_API_KEY not set. Set it or add it to api.env[/red]")
        sys.exit(1)

    agent = build_agent(args.model)
    n_capabilities = len(agent.lazy_registry.manifest)
    console.print(
        Panel(
            "[bold]Lattice Demo[/bold] — Real Search-then-Execute demo\n\n"
            "The agent has TWO tools:\n"
            "  [cyan]search_capabilities[/cyan] — discover what's available\n"
            "  [cyan]execute_capability[/cyan]  — run a capability by name\n\n"
            f"Registry: {n_capabilities} capabilities in manifest "
            f"(0 loaded at startup)\n\n"
            "[dim]Domains: Procurement, Travel[/dim]\n"
            f"[dim]Model: {args.model}[/dim]",
            border_style="blue",
        )
    )
    await run_interactive(agent)


if __name__ == "__main__":
    asyncio.run(main())
