#!/usr/bin/env python3
"""HR System — Lattice agent demo (LLM-driven Search-then-Execute).

An OpenAI-backed agent that sees exactly two tools:
  search_capabilities  — discovers what capabilities exist by intent
  execute_capability   — runs a capability by name with extracted inputs

The LLM drives every tool call.  Lattice handles all orchestration.
The agent only reasons over projections — it never sees raw API calls,
credentials, or intermediate state.

Usage (Docker):
    cd demo/hr && docker compose up --build    # reads api.env automatically

Usage (local — HR API must be running on :8000):
    cd demo/hr && python run_demo.py            # reads api.env from the same folder
    python -m demo.hr.run_demo                  # also supported from repo root

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


def _load_env_file(path: Path) -> None:
    """Load KEY=VALUE pairs from a .env file into os.environ (no-op if absent)."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file(Path(__file__).parent / "api.env")

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from hr_lattice.capabilities.employee_onboarding import employee_onboarding
from hr_lattice.capabilities.payroll_processing import payroll_processing
from hr_lattice.capabilities.performance_review import performance_review
from hr_lattice.stubs import HR_API_URL, client_factory
from lattice.auth.scopes import CredentialStore
from lattice.runtime.engine import Engine
from lattice.runtime.registry import CapabilityRegistry, LazyRegistry

console = Console()

MANIFEST_PATH = Path(__file__).parent / "registry.json"

HR_SCOPES = {
    "hr.read",
    "hr.write",
    "payroll.read",
    "payroll.write",
    "benefits.write",
}

SYSTEM_PROMPT = """\
You are an HR assistant powered by Lattice.

You have exactly TWO tools:
1. search_capabilities — search for available HR capabilities by describing
   what you want to accomplish. ALWAYS call this first for any new request.
2. execute_capability — execute a capability by its exact name with the
   required inputs. Only call this after you know the capability name and
   required inputs from a search result.

Workflow for every user request:
- Call search_capabilities with a short description of the goal.
- Review the results: find the best match and understand required inputs.
- Extract business-level input values from the user's message.
- Do not translate names to internal system IDs yourself unless the user
  explicitly provides an ID. The Lattice capability will resolve names,
  titles, departments, and emails internally.
- Call execute_capability with the correct name and an `inputs` object.
- If a tool returns an error saying inputs are missing or invalid, fix the
  payload and call execute_capability again.
- After receiving the projection, respond to the user in clear natural language.
  Include specific values (IDs, statuses, amounts). Do not invent information
  beyond what the projection contains.
"""


# ── Registry ───────────────────────────────────────────────────────────────

def build_registry() -> LazyRegistry:
    eager = CapabilityRegistry()
    eager.register(employee_onboarding)
    eager.register(payroll_processing)
    eager.register(performance_review)
    eager.save(MANIFEST_PATH)
    return LazyRegistry.from_manifest(MANIFEST_PATH)


# ── Agent ──────────────────────────────────────────────────────────────────

class HRAgent:
    """OpenAI function-calling agent backed by Lattice HR capabilities."""

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
        """Process one user message through the search-then-execute loop."""
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

                self._messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str),
                })

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
            creds = CredentialStore(granted_scopes=HR_SCOPES)
            try:
                return await self.engine.execute(
                    fn,
                    inputs,
                    credentials=creds,
                    client_factory=client_factory,
                    requester="hr-agent",
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
        console.print(f"\n  [dim yellow]→ {tool}[/dim yellow]")
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


async def run_interactive(agent: HRAgent) -> None:
    console.print("[dim]Interactive mode. Type your HR request. 'quit' to exit.[/dim]\n")
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


# ── Infrastructure ─────────────────────────────────────────────────────────

def wait_for_api(url: str, timeout: int = 30) -> None:
    console.print(f"[dim]Waiting for HR API at {url} ...[/dim]")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            httpx.get(f"{url}/health", timeout=2).raise_for_status()
            console.print("[dim]HR API is ready.[/dim]\n")
            return
        except Exception:
            time.sleep(1)
    console.print(f"[red]HR API did not become ready within {timeout}s.[/red]")
    sys.exit(1)


# ── Entry point ────────────────────────────────────────────────────────────

async def main() -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        console.print("[red]OPENAI_API_KEY is not set.[/red]")
        console.print("[dim]Set it before running:[/dim]")
        console.print("  [cyan]Copy api.env.example to api.env and set OPENAI_API_KEY[/cyan]")
        console.print("  [cyan]Then run: cd demo/hr && docker compose up --build[/cyan]")
        sys.exit(1)

    wait_for_api(HR_API_URL)

    lazy = build_registry()
    n = len(lazy._manifest)
    engine = Engine()
    model = os.environ.get("OPENAI_MODEL", "gpt-4o")
    agent = HRAgent(lazy, engine, model=model)

    console.print(
        Panel(
            "[bold]Lattice HR Agent[/bold]\n\n"
            "The agent sees exactly [cyan]two tools[/cyan]:\n"
            "  [cyan]search_capabilities[/cyan]  — find what's available by intent\n"
            "  [cyan]execute_capability[/cyan]   — run by name with extracted inputs\n\n"
            f"[dim]Registry: {n} capabilities loaded into manifest, 0 modules imported.\n"
            f"Model:    {model}\n"
            f"HR API:   {HR_API_URL}[/dim]",
            border_style="blue",
        )
    )

    await run_interactive(agent)

    console.rule("[bold green]Done[/bold green]")
    total = len(engine.audit_trail.records)
    loaded = len(lazy._loaded)
    console.print(
        f"[dim]{total} capability execution(s). "
        f"{loaded}/{n} module(s) loaded on demand.[/dim]"
    )


if __name__ == "__main__":
    asyncio.run(main())
