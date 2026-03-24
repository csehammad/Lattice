#!/usr/bin/env python3
"""End-to-end agent test for the Staffing demo.

Runs the full two-phase flow automatically:
  1. User asks to staff Project Phoenix with a Python backend engineer
  2. Agent calls FindCandidates -> presents ranked candidates
  3. User picks Alice Chen
  4. Agent calls AssignResource -> confirms assignment

The test starts the FastAPI server in-process, feeds scripted messages
through the LLM agent, and validates every projection.

Usage:
    cd demo/staffing
    OPENAI_API_KEY=sk-... python test_e2e.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

os.environ.setdefault("STAFFING_API_URL", "http://localhost:8001")

from staffing_lattice.capabilities.find_candidates import find_candidates
from staffing_lattice.capabilities.assign_resource import assign_resource
from staffing_lattice.stubs import client_factory

from lattice.auth.scopes import CredentialStore
from lattice.runtime.engine import Engine
from lattice.runtime.registry import CapabilityRegistry, LazyRegistry

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich import print_json

console = Console()


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file(Path(__file__).parent / "api.env")
_load_env_file(Path(__file__).parent.parent / "hr" / "api.env")

STAFFING_SCOPES = {
    "project.read", "project.write",
    "hr.read", "hr.write",
    "notification.write",
}

MANIFEST_PATH = Path(__file__).parent / "registry.json"


SYSTEM_PROMPT = """\
You are a staffing and resource allocation assistant powered by Lattice.

You have exactly TWO tools:
1. search_capabilities — search for available staffing capabilities by describing
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
  titles, and departments internally.
- Call execute_capability with the correct name and an `inputs` JSON object
  containing ALL required fields from the search results. Example:
  execute_capability(capability_name="X", inputs={"field1": "value1", ...})
- CRITICAL: You MUST include the `inputs` object with all required fields.
  Never call execute_capability without inputs.
- If a tool returns an error saying inputs are missing or invalid, fix the
  payload and call execute_capability again.

IMPORTANT — Two-phase staffing flow:
- When a projection contains `decision_required: true` and a `candidates` list,
  you MUST present the candidates as a comparison table to the user and ask
  which candidate they want to assign. Include role_fit_score, availability_pct,
  hourly_rate, avg_rating, and any conflict_flags for each candidate.
- Also mention the system recommendation.
- WAIT for the user's choice before calling AssignResource.
- When the user picks a candidate, call AssignResource with the candidate_id
  and project_id from the FindCandidates projection. The user may override
  allocation_pct or start_date — respect their values.

After receiving any projection, respond in clear natural language.
Include specific values (IDs, statuses, amounts). Do not invent information
beyond what the projection contains.
"""


SCRIPTED_CONVERSATION = [
    {
        "label": "Phase 1 — Find Candidates",
        "user": (
            "I need a Python backend engineer for Project Phoenix. "
            "They should know Python and PostgreSQL, from the Engineering department, "
            "starting April 1st 2026 for about 12 weeks."
        ),
    },
    {
        "label": "Phase 1b — Confirm (if model asked)",
        "user": (
            "Yes, confirmed. Search with: project_name='Phoenix', role='Backend Engineer', "
            "required_skills=['Python', 'PostgreSQL'], department='Engineering', "
            "start_date='2026-04-01', duration_weeks=12. Execute FindCandidates now."
        ),
        "conditional": True,
    },
    {
        "label": "Phase 2 — Assign Resource",
        "user": (
            "I pick Alice Chen (EMP-1024). Assign her to project PROJ-4501 "
            "as Backend Engineer at 80% allocation starting 2026-04-01. "
            "Requested by staffing-e2e-test."
        ),
    },
]


def start_api_server() -> threading.Thread:
    import uvicorn
    from staffing_api.app import app

    def _run():
        uvicorn.run(app, host="127.0.0.1", port=8001, log_level="warning")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t


def wait_for_api(url: str, timeout: int = 15) -> None:
    import httpx
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            httpx.get(f"{url}/health", timeout=2).raise_for_status()
            return
        except Exception:
            time.sleep(0.3)
    raise RuntimeError(f"Staffing API did not become ready within {timeout}s")


def build_registry() -> LazyRegistry:
    eager = CapabilityRegistry()
    eager.register(find_candidates)
    eager.register(assign_resource)
    eager.save(MANIFEST_PATH)
    return LazyRegistry.from_manifest(MANIFEST_PATH)


class StaffingAgent:

    def __init__(self, lazy: LazyRegistry, engine: Engine, model: str = "gpt-4o") -> None:
        self.lazy = lazy
        self.engine = engine
        self.model = model
        self._tools = LazyRegistry.openai_meta_tools()
        self._messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.projections: list[dict] = []

    def _client(self):
        import openai
        return openai.OpenAI()

    async def send(self, user_message: str) -> str:
        self._messages.append({"role": "user", "content": user_message})
        client = self._client()

        for _ in range(10):
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

        return "(agent reached max tool-call rounds)"

    async def _dispatch(self, tool: str, args: dict):
        if tool == "search_capabilities":
            return self.lazy.search(args.get("query", ""))
        if tool == "execute_capability":
            name = args.get("capability_name", "")
            manifest_entry = self.lazy._manifest.get(name, {})
            inputs = args.get("inputs")
            if not inputs:
                inputs = {k: v for k, v in args.items() if k != "capability_name"}
            if not isinstance(inputs, dict) or not inputs:
                return {
                    "error": f"Missing inputs for capability '{name}'",
                    "required_inputs": manifest_entry.get("inputs", {}),
                    "instruction": (
                        "Call execute_capability again with the same capability_name "
                        "and a complete 'inputs' JSON object containing all required fields. "
                        "Example: execute_capability(capability_name='FindCandidates', "
                        "inputs={'project_name': 'Phoenix', 'role': 'Backend Engineer', "
                        "'required_skills': ['Python'], 'department': 'Engineering', "
                        "'start_date': '2026-04-01', 'duration_weeks': 12})"
                    ),
                }
            self.lazy.ensure_loaded(name)
            fn = self.lazy.get_function(name)
            creds = CredentialStore(granted_scopes=STAFFING_SCOPES)
            try:
                result = await self.engine.execute(
                    fn, inputs,
                    credentials=creds,
                    client_factory=client_factory,
                    requester="staffing-e2e-test",
                )
                self.projections.append({"capability": name, "projection": result})
                return result
            except Exception as exc:
                return {
                    "error": str(exc),
                    "required_inputs": manifest_entry.get("inputs", {}),
                    "instruction": (
                        "Fix the execute_capability payload and try again."
                    ),
                }
        return {"error": f"unknown tool: {tool}"}

    def _print_tool_turn(self, tool: str, args: dict, result) -> None:
        console.print(f"\n  [dim yellow]-> {tool}[/dim yellow]")
        console.print(f"  [dim]  args: {json.dumps(args, default=str)}[/dim]")
        if tool == "search_capabilities":
            names = [r.get("name") for r in result] if isinstance(result, list) else []
            console.print(f"  [dim]  found: {', '.join(names)}[/dim]")
        elif tool == "execute_capability":
            name = args.get("capability_name", "")
            if isinstance(result, dict) and "error" in result:
                console.print(f"  [red]  error: {result['error']}[/red]")
            elif isinstance(result, dict):
                console.print(Panel(
                    json.dumps(result, indent=2, default=str),
                    title=f"[bold cyan]{name} — projection[/bold cyan]",
                    border_style="cyan",
                    padding=(0, 2),
                ))
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
        t.add_row("Duration", f"{r.duration_ms:.0f} ms" if r.duration_ms is not None else "-")
        t.add_row("Execution ID", f"[dim]{r.execution_id}[/dim]")
        console.print(Panel(t, title="[dim]Lattice audit[/dim]", border_style="dim"))


def validate_find_candidates(projection: dict) -> list[str]:
    errors = []
    if not projection.get("project_id"):
        errors.append("missing project_id")
    candidates = projection.get("candidates", [])
    if not candidates:
        errors.append("no candidates returned")
    if projection.get("decision_required") is not True:
        errors.append("decision_required should be True")
    for c in candidates:
        for field in ("candidate_id", "name", "role_fit_score", "availability_pct"):
            if field not in c:
                errors.append(f"candidate missing '{field}'")
                break
    if projection.get("recommendation", {}).get("candidate_id") is None:
        errors.append("no recommendation.candidate_id")
    return errors


def validate_assign_resource(projection: dict) -> list[str]:
    errors = []
    if not projection.get("assignment_id"):
        errors.append("missing assignment_id")
    if projection.get("status") != "confirmed":
        errors.append(f"expected status=confirmed, got {projection.get('status')}")
    if not projection.get("candidate_name"):
        errors.append("missing candidate_name")
    if not projection.get("notifications_sent"):
        errors.append("no notifications_sent")
    return errors


async def run_test() -> bool:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        console.print("[red]OPENAI_API_KEY is not set. Set it in api.env or environment.[/red]")
        return False

    console.print(Rule("[bold blue]Staffing Demo — End-to-End Agent Test[/bold blue]"))
    console.print()

    console.print("[dim]Starting Staffing API server...[/dim]")
    start_api_server()
    wait_for_api("http://localhost:8001")
    console.print("[green]Staffing API is ready.[/green]\n")

    lazy = build_registry()
    engine = Engine()
    model = os.environ.get("OPENAI_MODEL", "gpt-4o")
    agent = StaffingAgent(lazy, engine, model=model)

    console.print(Panel(
        f"[bold]Lattice Staffing Agent[/bold]\n"
        f"Model: {model}  |  Capabilities: {len(lazy._manifest)}  |  "
        f"API: http://localhost:8001\n\n"
        f"Scripted conversation: two-phase flow "
        f"(FindCandidates -> pick -> AssignResource)",
        border_style="blue",
    ))
    console.print()

    find_candidates_done = False

    for turn in SCRIPTED_CONVERSATION:
        if turn.get("conditional") and find_candidates_done:
            console.print(f"[dim]  (skipping conditional turn — Phase 1 already succeeded)[/dim]\n")
            continue

        console.print(Rule(f"[bold]{turn['label']}[/bold]"))
        console.print(f"\n[bold green]User:[/bold green] {turn['user']}\n")

        reply = await agent.send(turn["user"])
        console.print(f"\n[bold blue]Agent:[/bold blue] {reply}\n")

        if any(p["capability"] == "FindCandidates" for p in agent.projections):
            find_candidates_done = True

    console.print(Rule("[bold]Validation[/bold]"))
    console.print()

    all_passed = True

    fc_projs = [p for p in agent.projections if p["capability"] == "FindCandidates"]
    ar_projs = [p for p in agent.projections if p["capability"] == "AssignResource"]

    if not fc_projs:
        console.print("[red]FindCandidates was never executed successfully[/red]")
        all_passed = False
    else:
        fc_proj = fc_projs[0]["projection"]
        fc_errors = validate_find_candidates(fc_proj)
        if fc_errors:
            console.print(f"[red]FindCandidates validation FAILED:[/red]")
            for e in fc_errors:
                console.print(f"  [red]- {e}[/red]")
            all_passed = False
        else:
            n = len(fc_proj.get("candidates", []))
            top = fc_proj.get("recommendation", {}).get("candidate_id", "?")
            console.print(
                f"[green]FindCandidates  PASSED[/green]  "
                f"({n} candidates, recommendation={top}, "
                f"urgency={fc_proj.get('project_urgency')})"
            )

    if not ar_projs:
        console.print("[red]AssignResource was never executed successfully[/red]")
        all_passed = False
    else:
        ar_proj = ar_projs[0]["projection"]
        ar_errors = validate_assign_resource(ar_proj)
        if ar_errors:
            console.print(f"[red]AssignResource validation FAILED:[/red]")
            for e in ar_errors:
                console.print(f"  [red]- {e}[/red]")
            all_passed = False
        else:
            console.print(
                f"[green]AssignResource  PASSED[/green]  "
                f"(id={ar_proj.get('assignment_id')}, "
                f"candidate={ar_proj.get('candidate_name')}, "
                f"status={ar_proj.get('status')}, "
                f"notified={ar_proj.get('notifications_sent')})"
            )

    console.print()
    console.print(Rule("[bold]Audit Trail[/bold]"))
    audit_table = Table(show_header=True)
    audit_table.add_column("Capability", style="cyan")
    audit_table.add_column("Status")
    audit_table.add_column("Steps", justify="right")
    audit_table.add_column("Duration", justify="right")
    audit_table.add_column("Execution ID", style="dim")
    for r in engine.audit_trail.records:
        status_style = "[green]" if r.status == "success" else "[red]"
        audit_table.add_row(
            f"{r.capability_name} v{r.capability_version}",
            f"{status_style}{r.status}[/{status_style[1:]}",
            str(len(r.steps)),
            f"{r.duration_ms:.0f} ms" if r.duration_ms is not None else "-",
            r.execution_id,
        )
    console.print(audit_table)

    console.print()
    loaded = len(lazy._loaded)
    total = len(lazy._manifest)
    console.print(f"[dim]Modules loaded on demand: {loaded}/{total}[/dim]")

    console.print()
    if all_passed:
        console.print(Panel(
            "[bold green]ALL CHECKS PASSED[/bold green]\n\n"
            "Two-phase flow completed successfully:\n"
            "  1. FindCandidates returned ranked candidates with decision_required=true\n"
            "  2. Agent presented options and waited for user choice\n"
            "  3. AssignResource confirmed the assignment with notifications",
            border_style="green",
        ))
    else:
        console.print(Panel("[bold red]SOME CHECKS FAILED[/bold red]", border_style="red"))

    return all_passed


if __name__ == "__main__":
    passed = asyncio.run(run_test())
    sys.exit(0 if passed else 1)
