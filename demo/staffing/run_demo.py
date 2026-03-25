#!/usr/bin/env python3
"""Staffing Platform — Lattice agent demo (LLM-driven Search-then-Execute).

An OpenAI-backed agent that sees exactly two tools:
  search_capabilities  — discovers what capabilities exist by intent
  execute_capability   — runs a capability by name with extracted inputs

Two-phase flow: FindCandidates returns a ranked list with
decision_required=true, the agent presents options, the user picks,
then the agent invokes AssignResource.

Usage (Docker):
    cd demo/staffing && docker compose up --build

Usage (local — Staffing API must be running on :8001):
    cd demo/staffing && python run_demo.py

Interactive mode:
    Type requests naturally. The agent figures out which capability to call.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def _merge_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key and value:
            os.environ[key] = value


_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_merge_env_file(_REPO_ROOT / "api.env")
_merge_env_file(Path(__file__).parent / "api.env")
_merge_env_file(Path(__file__).parent.parent / "hr" / "api.env")

import httpx  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.table import Table  # noqa: E402
from staffing_lattice.capabilities.assign_resource import assign_resource  # noqa: E402
from staffing_lattice.capabilities.cancel_assignment import cancel_assignment  # noqa: E402
from staffing_lattice.capabilities.find_candidates import find_candidates  # noqa: E402
from staffing_lattice.capabilities.update_assignment import update_assignment  # noqa: E402
from staffing_lattice.capabilities.view_employee_workload import (  # noqa: E402
    view_employee_workload,
)
from staffing_lattice.capabilities.view_project_staffing import view_project_staffing  # noqa: E402
from staffing_lattice.stubs import STAFFING_API_URL, client_factory  # noqa: E402

from lattice.auth.scopes import CredentialStore  # noqa: E402
from lattice.runtime.engine import Engine  # noqa: E402
from lattice.runtime.registry import CapabilityRegistry, LazyRegistry  # noqa: E402

console = Console()

MANIFEST_PATH = Path(__file__).parent / "registry.json"

STAFFING_SCOPES = {
    "project.read", "project.write",
    "hr.read", "hr.write",
    "notification.write",
    "assignments.read", "assignments.write",
    "availability.read",
    "employees.read",
    "notifications.read", "notifications.write",
    "projects.read", "projects.write",
    "resource_plans.read",
}

_PROMPT_PATH = Path(__file__).parent / "SYSTEM_PROMPT.txt"
SYSTEM_PROMPT = (
    _PROMPT_PATH.read_text() if _PROMPT_PATH.exists()
    else "You are a staffing assistant."
)


_ALL_CAPABILITIES = [
    find_candidates,
    assign_resource,
    view_project_staffing,
    view_employee_workload,
    update_assignment,
    cancel_assignment,
]


def build_registry() -> LazyRegistry:
    eager = CapabilityRegistry()
    for cap_fn in _ALL_CAPABILITIES:
        eager.register(cap_fn)
    eager.save(MANIFEST_PATH)
    return LazyRegistry.from_manifest(MANIFEST_PATH)


class StaffingAgent:
    """OpenAI function-calling agent backed by Lattice staffing capabilities."""

    def __init__(self, lazy: LazyRegistry, engine: Engine, model: str = "gpt-4o") -> None:
        self.lazy = lazy
        self.engine = engine
        self.model = model
        self._tools = LazyRegistry.openai_meta_tools()
        self._messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    def _client(self):
        import openai
        return openai.OpenAI()

    async def send(self, user_message: str) -> str:
        self._messages.append({"role": "user", "content": user_message})
        client = self._client()

        for _ in range(6):
            response = client.chat.completions.create(
                model=self.model,
                messages=self._messages,
                tools=self._tools,
                tool_choice="auto",
            )
            msg = response.choices[0].message

            if not msg.tool_calls:
                reply = msg.content or ""
                self._messages.append({"role": "assistant", "content": reply})
                return reply

            self._messages.append(msg.model_dump())

            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                result = await self._dispatch(tc.function.name, args)
                self._print_tool_turn(tc.function.name, args, result)

                self._messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, default=str),
                    }
                )

        return "(agent reached max tool-call rounds without a text reply)"

    async def _dispatch(self, tool: str, args: dict):
        if tool == "search_capabilities":
            return self.lazy.search(args.get("query", ""))
        if tool == "execute_capability":
            name = args.get("capability_name", "")
            manifest_entry = self.lazy._manifest.get(name, {})
            inputs = args.get("inputs") or {k: v for k, v in args.items() if k != "capability_name"}
            if not isinstance(inputs, dict) or not inputs:
                return {
                    "error": f"Missing inputs for capability '{name}'",
                    "required_inputs": manifest_entry.get("inputs", {}),
                    "instruction": (
                        "Call execute_capability again with the same capability_name "
                        "and a complete inputs object."
                    ),
                }
            self.lazy.ensure_loaded(name)
            fn = self.lazy.get_function(name)
            creds = CredentialStore(granted_scopes=STAFFING_SCOPES)
            try:
                return await self.engine.execute(
                    fn,
                    inputs,
                    credentials=creds,
                    client_factory=client_factory,
                    requester="staffing-agent",
                )
            except Exception as exc:
                return {
                    "error": str(exc),
                    "required_inputs": manifest_entry.get("inputs", {}),
                    "instruction": (
                        "Fix the execute_capability payload and try again with "
                        "business-level inputs only."
                    ),
                }
        return {"error": f"unknown tool: {tool}"}

    def _print_tool_turn(self, tool: str, args: dict, result) -> None:
        console.print(f"\n  [dim yellow]-> {tool}[/dim yellow]")
        if tool == "search_capabilities":
            query = args.get("query", "")
            names = [r.get("name") for r in result] if isinstance(result, list) else []
            console.print(f'  [dim]  query: "{query}"[/dim]')
            console.print(f"  [dim]  found: {', '.join(names)}[/dim]")
        elif tool == "execute_capability":
            name = args.get("capability_name", "")
            console.print(f"  [dim]  capability: {name}[/dim]")
            if isinstance(result, dict) and "error" in result:
                console.print(f"  [red]  error: {result['error']}[/red]")
            elif isinstance(result, dict):
                console.print(
                    Panel(
                        json.dumps(result, indent=2, default=str),
                        title=f"[dim]{name} — projection[/dim]",
                        border_style="dim",
                        padding=(0, 2),
                    )
                )
                self._print_audit()

    def _print_audit(self) -> None:
        if not self.engine.audit_trail.records:
            return
        r = self.engine.audit_trail.records[-1]
        t = Table(show_header=False, box=None, padding=(0, 1))
        t.add_column(style="dim cyan")
        t.add_column()
        t.add_row("Capability", f"{r.capability_name} v{r.capability_version}")
        t.add_row("Status", f"[green]{r.status}[/green]")
        t.add_row("Steps", str(len(r.steps)))
        t.add_row("Duration", f"{r.duration_ms:.0f} ms" if r.duration_ms is not None else "—")
        t.add_row("Execution ID", f"[dim]{r.execution_id}[/dim]")
        console.print(Panel(t, title="[dim]Lattice execution[/dim]", border_style="dim"))


async def run_interactive(agent: StaffingAgent) -> None:
    console.print("[dim]Interactive mode. Type your staffing request. 'quit' to exit.[/dim]\n")
    while True:
        try:
            user_input = console.input("[bold green]You:[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye.[/dim]")
            break
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            console.print("[dim]Goodbye.[/dim]")
            break
        with console.status("[dim]Thinking...[/dim]"):
            reply = await agent.send(user_input)
        console.print(f"\n[bold blue]Agent:[/bold blue] {reply}\n")


def wait_for_api(url: str, timeout: int = 30) -> None:
    console.print(f"[dim]Waiting for Staffing API at {url} ...[/dim]")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            httpx.get(f"{url}/health", timeout=2).raise_for_status()
            console.print("[dim]Staffing API is ready.[/dim]\n")
            return
        except Exception:
            time.sleep(1)
    console.print(f"[red]Staffing API did not become ready within {timeout}s.[/red]")
    sys.exit(1)


async def main() -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        console.print("[red]OPENAI_API_KEY is not set.[/red]")
        console.print("[dim]Set it before running:[/dim]")
        console.print("  [cyan]Copy api.env.example to api.env and set OPENAI_API_KEY[/cyan]")
        console.print("  [cyan]Then run: cd demo/staffing && docker compose up --build[/cyan]")
        sys.exit(1)

    wait_for_api(STAFFING_API_URL)

    lazy = build_registry()
    n = len(lazy._manifest)
    engine = Engine()
    model = os.environ.get("OPENAI_MODEL", "gpt-4o")
    agent = StaffingAgent(lazy, engine, model=model)

    console.print(
        Panel(
            "[bold]Lattice Staffing Agent[/bold]\n\n"
            "The agent sees exactly [cyan]two tools[/cyan]:\n"
            "  [cyan]search_capabilities[/cyan]  — find what's available by intent\n"
            "  [cyan]execute_capability[/cyan]   — run by name with extracted inputs\n\n"
            "Two-phase flow: FindCandidates -> user picks -> AssignResource\n\n"
            f"[dim]Registry: {n} capabilities loaded into manifest, 0 modules imported.\n"
            f"Model:    {model}\n"
            f"API:      {STAFFING_API_URL}[/dim]",
            border_style="blue",
        )
    )

    await run_interactive(agent)

    console.rule("[bold green]Done[/bold green]")
    total = len(engine.audit_trail.records)
    loaded = len(lazy._loaded)
    console.print(
        f"[dim]{total} capability execution(s). {loaded}/{n} module(s) loaded on demand.[/dim]"
    )


if __name__ == "__main__":
    asyncio.run(main())
