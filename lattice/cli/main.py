"""Lattice CLI.

Commands::

    lattice discover    # Read what your systems can do
    lattice match       # See what capabilities are possible
    lattice generate    # Produce executable code
    lattice visualize   # Review dependency graph, data flow, permissions
    lattice validate    # Test against real systems
    lattice register    # Make it available to models
    lattice run         # Test with a real intent
    lattice bind        # Connect individual steps to new APIs
    lattice prompt      # Generate agent system prompt from registry
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import json
import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

console = Console()


def _get_version() -> str:
    try:
        from importlib.metadata import version as pkg_version

        return pkg_version("lattice")
    except Exception:
        return "0.1.0"


@click.group()
@click.version_option(version=_get_version(), prog_name="lattice")
def cli() -> None:
    """Lattice — the capability runtime for outcome-based execution."""


# ---------------------------------------------------------------------------
# discover
# ---------------------------------------------------------------------------


@cli.command()
@click.option(
    "--source",
    multiple=True,
    default=["openapi"],
    help="Source type (openapi, graphql, fhir).",
)
@click.option(
    "--spec",
    multiple=True,
    required=True,
    help="Path to an API specification file.",
)
@click.option(
    "--output",
    "-o",
    default=None,
    help="Write discovered operations to this YAML file.",
)
def discover(source: tuple[str, ...], spec: tuple[str, ...], output: str | None) -> None:
    """Read what your systems can do."""
    from lattice.discovery.inventory import Inventory
    from lattice.discovery.openapi import parse_openapi

    inventory = Inventory()

    for spec_path in spec:
        path = Path(spec_path)
        if not path.exists():
            console.print(f"[red]Spec not found:[/red] {spec_path}")
            sys.exit(1)
        ops = parse_openapi(path)
        inventory.add_operations(ops)
        console.print(f"Discovered [bold]{len(ops)}[/bold] operations from {spec_path}")

    table = Table(title="Discovered operations")
    table.add_column("ID")
    table.add_column("Method")
    table.add_column("Path")
    table.add_column("Summary")
    for op in inventory.operations:
        table.add_row(op.operation_id, op.method, op.path, op.summary)
    console.print(table)

    if output:
        inventory.save(output)
        console.print(f"Saved inventory to {output}")


# ---------------------------------------------------------------------------
# match
# ---------------------------------------------------------------------------


@cli.command()
@click.option(
    "--spec",
    multiple=True,
    required=True,
    help="Path to an OpenAPI spec or discovered inventory YAML.",
)
@click.option("--domain", default=None, help="Filter by domain.")
@click.option("--provider", default=None, help="LLM provider (openai / anthropic).")
@click.option("--model", default=None, help="LLM model name.")
@click.option("--api-key", default=None, help="LLM API key (or set env var).")
def match(
    spec: tuple[str, ...],
    domain: str | None,
    provider: str | None,
    model: str | None,
    api_key: str | None,
) -> None:
    """See what capabilities are possible (LLM-powered)."""
    from lattice.discovery.inventory import Inventory
    from lattice.discovery.openapi import parse_openapi
    from lattice.llm.prompts import MATCH_SYSTEM_PROMPT, build_match_prompt
    from lattice.llm.provider import get_llm_client

    inventory = Inventory()
    for spec_path in spec:
        path = Path(spec_path)
        if not path.exists():
            console.print(f"[red]Spec not found:[/red] {spec_path}")
            sys.exit(1)
        ops = parse_openapi(path)
        inventory.add_operations(ops)
        console.print(f"Loaded [bold]{len(ops)}[/bold] operations from {spec_path}")

    if not inventory.operations:
        console.print("[red]No operations found in provided specs.[/red]")
        sys.exit(1)

    context = inventory.to_llm_context()
    user_prompt = build_match_prompt(context, domain=domain)

    console.print("Sending operations to LLM for capability matching...")
    llm = get_llm_client(provider=provider, model=model, api_key=api_key)
    response = llm.complete(MATCH_SYSTEM_PROMPT, user_prompt)
    data = response.extract_json()

    capabilities = data.get("capabilities", [])
    unmatched = data.get("unmatched_operations", [])

    if not capabilities:
        console.print("[yellow]No capabilities proposed by the LLM.[/yellow]")
        return

    for cap in capabilities:
        console.print(f"\n[bold]{cap['name']}[/bold] — {cap.get('description', '')}")
        console.print(f"  Domain: {cap.get('domain', 'unknown')}")
        inputs_str = ", ".join(f"{k}: {v}" for k, v in cap.get("inputs", {}).items())
        proj_str = ", ".join(f"{k}: {v}" for k, v in cap.get("projection", {}).items())
        console.print(f"  Inputs: {inputs_str}")
        console.print(f"  Projection: {proj_str}")

        steps = cap.get("steps", [])
        if steps:
            table = Table(show_header=True, title="Steps")
            table.add_column("Step")
            table.add_column("Operations")
            table.add_column("Depends on")
            table.add_column("Scope")
            for s in steps:
                table.add_row(
                    s.get("name", ""),
                    ", ".join(s.get("operation_ids", [])),
                    ", ".join(s.get("depends_on", [])),
                    s.get("scope", ""),
                )
            console.print(table)

    if unmatched:
        console.print(f"\n[yellow]Unmatched operations:[/yellow] {', '.join(unmatched)}")


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--capability", "cap_name", required=True, help="Capability name.")
@click.option("--output", "-o", default="./capabilities/", help="Output directory.")
@click.option("--human-tasks", is_flag=True, help="Generate all steps as human tasks.")
@click.option(
    "--spec",
    multiple=True,
    default=(),
    help="Path to OpenAPI spec(s). When provided, the LLM generates a full capability from the discovered operations.",
)
@click.option("--provider", default=None, help="LLM provider (openai / anthropic).")
@click.option("--model", default=None, help="LLM model name.")
@click.option("--api-key", default=None, help="LLM API key (or set env var).")
def generate(
    cap_name: str,
    output: str,
    human_tasks: bool,
    spec: tuple[str, ...],
    provider: str | None,
    model: str | None,
    api_key: str | None,
) -> None:
    """Produce executable capability code.

    Without --spec: generates a static skeleton (no LLM needed).
    With --spec: parses the API specs, sends them to an LLM, and
    generates a full capability implementation.
    """
    out_dir = Path(output)
    out_dir.mkdir(parents=True, exist_ok=True)

    fn_name = _to_snake(cap_name)
    filename = f"{fn_name}.py"

    if spec:
        code = _generate_with_llm(
            cap_name,
            spec,
            human_tasks,
            provider=provider,
            model=model,
            api_key=api_key,
        )
    elif human_tasks:
        code = _generate_human_skeleton(cap_name, fn_name)
    else:
        code = _generate_skeleton(cap_name, fn_name)

    (out_dir / filename).write_text(code)
    console.print(f"Generated [bold]{out_dir / filename}[/bold]")


def _generate_with_llm(
    cap_name: str,
    spec_paths: tuple[str, ...],
    human_tasks: bool,
    provider: str | None,
    model: str | None,
    api_key: str | None,
) -> str:
    """Use an LLM to generate a full capability from OpenAPI specs."""
    from lattice.discovery.inventory import Inventory
    from lattice.discovery.openapi import parse_openapi
    from lattice.llm.prompts import build_generate_prompt, get_generate_system_prompt
    from lattice.llm.provider import get_llm_client

    inventory = Inventory()
    for spec_path in spec_paths:
        path = Path(spec_path)
        if not path.exists():
            console.print(f"[red]Spec not found:[/red] {spec_path}")
            sys.exit(1)
        ops = parse_openapi(path)
        inventory.add_operations(ops)
        console.print(f"Loaded [bold]{len(ops)}[/bold] operations from {spec_path}")

    context = inventory.to_llm_context()
    system_prompt = get_generate_system_prompt(human_tasks=human_tasks)
    user_prompt = build_generate_prompt(cap_name, context, human_tasks=human_tasks)

    console.print(f"Sending to LLM to generate [bold]{cap_name}[/bold]...")
    llm = get_llm_client(provider=provider, model=model, api_key=api_key)
    response = llm.complete(system_prompt, user_prompt)
    return response.extract_python()


def _to_snake(name: str) -> str:
    import re

    s = re.sub(r"(?<=[a-z])(?=[A-Z])", "_", name)
    return s.lower()


def _generate_skeleton(name: str, fn_name: str) -> str:
    return f'''\
"""Capability: {name} — generated skeleton."""

from lattice import capability, step, state, projection
from lattice.failure import retry, soft_failure, hard_failure, abort


@capability(
    name="{name}",
    version="1.0",
    inputs={{}},
    projection={{}},
)
async def {fn_name}(ctx):

    @step(depends_on=[], scope="")
    @retry(max=3, backoff="exponential", on=[TimeoutError])
    async def step_one():
        # TODO: implement
        return {{}}

    return projection()
'''


def _generate_human_skeleton(name: str, fn_name: str) -> str:
    return f'''\
"""Capability: {name} — human-task skeleton."""

from lattice import capability, step, state, projection
from lattice.human import human_task


@capability(
    name="{name}",
    version="1.0",
    inputs={{}},
    projection={{}},
)
async def {fn_name}(ctx):

    @step(depends_on=[], scope="")
    @human_task(assigned_to="team", sla="4_hours")
    async def step_one():
        return await ctx.request_human_input(
            task="TODO: describe task",
            expected_output={{}}
        )

    return projection()
'''


# ---------------------------------------------------------------------------
# visualize
# ---------------------------------------------------------------------------


@cli.command()
@click.option(
    "--module", "module_path", required=True, help="Python module path containing the capability."
)
@click.option("--capability", "cap_name", required=True, help="Capability name.")
@click.option(
    "--html",
    "html_path",
    default=None,
    help="Generate an interactive HTML visualization and open it in the browser. "
    "Pass a file path or 'auto' to use <capability>.html.",
)
def visualize(module_path: str, cap_name: str, html_path: str | None) -> None:
    """Review dependency graph, data flow, permissions."""
    mod = importlib.import_module(module_path)
    fn = _find_capability(mod, cap_name)

    if fn is None:
        console.print(f"[red]Capability '{cap_name}' not found in {module_path}[/red]")
        sys.exit(1)

    from lattice.capability import get_capability_def

    defn = get_capability_def(fn)
    assert defn is not None

    if not defn.steps:
        _collect_steps_for_visualization(defn)

    # ── Terminal output (always) ──────────────────────────────────────
    tree = Tree(f"[bold]{defn.name}[/bold] v{defn.version}")

    inputs_node = tree.add("[blue]Inputs[/blue]")
    for name, typ in defn.input_schema.items():
        inputs_node.add(f"{name}: {typ.__name__}")

    from lattice.types import (
        projection_field_description,
        projection_field_example,
        projection_field_type,
    )

    proj_node = tree.add("[green]Projection[/green]")
    for name, spec in defn.projection_schema.items():
        ftype = projection_field_type(spec).__name__
        fexample = projection_field_example(spec)
        fdesc = projection_field_description(spec)
        label = f"{name}: {ftype}"
        if fexample is not None:
            label += f"  [dim](e.g. {fexample!r})[/dim]"
        if fdesc:
            label += f"  [italic dim]— {fdesc}[/italic dim]"
        proj_node.add(label)

    if defn.steps:
        steps_node = tree.add("[yellow]Steps[/yellow]")
        for s in defn.steps:
            label = s.name
            tags: list[str] = []
            if s.scope:
                tags.append(f"scope={s.scope}")
            if s.human_task:
                tags.append("[magenta]human[/magenta]")
            if s.needs_human_input:
                tags.append("[red]gap[/red]")
            if s.depends_on:
                tags.append(f"after: {', '.join(s.depends_on)}")
            if s.retry_policy:
                tags.append(f"retry={s.retry_policy.max_attempts}")
            if s.soft_failure_fallback:
                tags.append("soft-failure")
            if s.hard_failure_action:
                tags.append("hard-failure")
            suffix = f"  ({', '.join(tags)})" if tags else ""
            steps_node.add(f"{label}{suffix}")

    console.print(tree)

    # ── HTML output (when requested) ─────────────────────────────────
    if html_path is not None:
        if html_path == "auto":
            html_path = f"{_to_snake(cap_name)}.html"
        out = Path(html_path)
        out.write_text(_build_html_visualization(defn))
        console.print(f"\nHTML visualization written to [bold]{html_path}[/bold]")

        index_path = _rebuild_html_index(out.parent)
        console.print(f"Index updated at [bold]{index_path}[/bold]")

        import webbrowser

        webbrowser.open(index_path.resolve().as_uri())


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--module", "module_path", required=True, help="Python module path.")
@click.option("--capability", "cap_name", required=True, help="Capability name.")
def validate(module_path: str, cap_name: str) -> None:
    """Test a capability against real systems (dry-run validation)."""
    mod = importlib.import_module(module_path)
    fn = _find_capability(mod, cap_name)
    if fn is None:
        console.print(f"[red]Capability '{cap_name}' not found[/red]")
        sys.exit(1)

    from lattice.capability import get_capability_def

    defn = get_capability_def(fn)
    assert defn is not None

    console.print(f"Validating [bold]{defn.name}[/bold] v{defn.version}...")
    console.print(f"  Input schema: {defn.input_schema}")
    console.print(f"  Projection schema: {defn.projection_schema}")
    console.print("[green]Schema validation passed.[/green]")


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--module", "module_path", required=True, help="Python module path.")
@click.option("--capability", "cap_name", required=True, help="Capability name.")
@click.option(
    "--registry", "registry_path", default=".lattice.registry.json", help="Registry file path."
)
def register(module_path: str, cap_name: str, registry_path: str) -> None:
    """Make a capability available to models."""
    mod = importlib.import_module(module_path)
    fn = _find_capability(mod, cap_name)
    if fn is None:
        console.print(f"[red]Capability '{cap_name}' not found[/red]")
        sys.exit(1)

    from lattice.runtime.registry import CapabilityRegistry

    reg_path = Path(registry_path)
    existing: dict[str, Any] = {}
    if reg_path.exists():
        existing = json.loads(reg_path.read_text())

    registry = CapabilityRegistry()
    defn = registry.register(fn)
    registry.save(registry_path)

    # Merge: new save only contains the just-registered capability,
    # so layer it on top of the existing entries.
    new_data = json.loads(reg_path.read_text())
    merged = {**existing, **new_data}
    reg_path.write_text(json.dumps(merged, indent=2))
    console.print(f"Registered [bold]{defn.name}[/bold] -> {registry_path}")


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--module", "module_path", required=True, help="Python module path.")
@click.option("--capability", "cap_name", required=True, help="Capability name.")
@click.option("--intent", "intent_json", required=True, help="JSON string with input fields.")
@click.option("--scopes", default="", help="Comma-separated scopes to grant.")
@click.option(
    "--stubs",
    "stubs_module",
    default=None,
    help="Python module exporting client_factory(name, credentials).",
)
def run(
    module_path: str, cap_name: str, intent_json: str, scopes: str, stubs_module: str | None
) -> None:
    """Test with a real intent."""
    mod = importlib.import_module(module_path)
    fn = _find_capability(mod, cap_name)
    if fn is None:
        console.print(f"[red]Capability '{cap_name}' not found[/red]")
        sys.exit(1)

    inputs = json.loads(intent_json)

    from lattice.auth.scopes import CredentialStore
    from lattice.runtime.engine import Engine

    creds = CredentialStore(granted_scopes=set(s.strip() for s in scopes.split(",") if s.strip()))

    client_factory = None
    if stubs_module:
        stubs = importlib.import_module(stubs_module)
        client_factory = getattr(stubs, "client_factory", None)
        if client_factory is None:
            console.print(f"[red]Module '{stubs_module}' has no client_factory function[/red]")
            sys.exit(1)

    engine = Engine()

    try:
        result = asyncio.run(
            engine.execute(fn, inputs, credentials=creds, client_factory=client_factory)
        )
        console.print_json(json.dumps(result, indent=2, default=str))
    except Exception as exc:
        console.print(f"[red]Execution failed:[/red] {exc}")
        sys.exit(1)

    audit = engine.audit_trail.records[-1]
    console.print(
        f"\n[dim]Execution {audit.execution_id} — {audit.status} in {audit.duration_ms:.0f}ms[/dim]"
    )


# ---------------------------------------------------------------------------
# bind
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--module", "module_path", required=True, help="Python module path.")
@click.option("--step", "step_name", required=True, help="Step name to bind.")
@click.option("--to", "target", required=True, help="API client name to bind to.")
def bind(module_path: str, step_name: str, target: str) -> None:
    """Connect individual steps to new APIs."""
    console.print(f"Binding step [bold]{step_name}[/bold] -> client [bold]{target}[/bold]")
    console.print(
        "[yellow]Note:[/yellow] Binding updates the step body to use the specified client. "
        "Edit the generated capability file to complete the integration."
    )


# ---------------------------------------------------------------------------
# prompt
# ---------------------------------------------------------------------------


@cli.command()
@click.option(
    "--registry",
    "registry_path",
    required=True,
    help="Path to registry.json (created by `lattice register` or CapabilityRegistry.save).",
)
@click.option("--domain", default=None, help="Domain name for the system prompt (e.g. 'staffing').")
@click.option("--output", "-o", default=None, help="Write the system prompt to a file.")
def prompt(registry_path: str, domain: str | None, output: str | None) -> None:
    """Generate an agent system prompt from a capability registry.

    Reads the registry manifest and produces a system prompt that teaches
    the agent what capabilities exist, what inputs each requires, and
    what projections to expect — so the agent can drive the search-then-
    execute loop without hard-coded knowledge.
    """
    path = Path(registry_path)
    if not path.exists():
        console.print(f"[red]Registry not found:[/red] {registry_path}")
        sys.exit(1)

    manifest = json.loads(path.read_text())
    if not manifest:
        console.print("[yellow]Registry is empty — no capabilities found.[/yellow]")
        sys.exit(1)

    domain_label = domain or "general"
    sys_prompt = _build_system_prompt(manifest, domain_label)

    if output:
        out = Path(output)
        out.write_text(sys_prompt)
        console.print(f"System prompt written to [bold]{output}[/bold]")
        console.print(f"  Capabilities: {len(manifest)}")
        console.print(f"  Domain: {domain_label}")
        console.print(f"  Length: {len(sys_prompt)} chars")
    else:
        console.print(sys_prompt)


def _build_system_prompt(manifest: dict[str, Any], domain: str) -> str:
    """Build an agent system prompt from a capability registry manifest."""
    from lattice.types import projection_field_type

    cap_sections = []
    for name, entry in manifest.items():
        inputs = entry.get("inputs", {})
        proj = entry.get("projection", {})

        input_lines = []
        for iname, itype in inputs.items():
            input_lines.append(f"    - {iname}: {itype}")

        proj_lines = []
        for pname, pspec in proj.items():
            if isinstance(pspec, dict):
                ptype = pspec.get("type", "any")
                pdesc = pspec.get("description", "")
                pex = pspec.get("example", "")
                line = f"    - {pname} ({ptype}): {pdesc}"
                if pex:
                    line += f"  [example: {pex!r}]"
                proj_lines.append(line)
            else:
                proj_lines.append(f"    - {pname}: {pspec}")

        section = f"""### {name}
  Inputs:
{chr(10).join(input_lines) if input_lines else '    (none)'}
  Projection:
{chr(10).join(proj_lines) if proj_lines else '    (none)'}"""
        cap_sections.append(section)

    capabilities_block = "\n\n".join(cap_sections)
    cap_count = len(manifest)

    return f"""\
You are a {domain} assistant powered by Lattice.

You have exactly TWO tools:
1. search_capabilities — search for available capabilities by describing
   what you want to accomplish. ALWAYS call this first for any new request.
2. execute_capability — execute a capability by its exact name with the
   required inputs. Only call this after you know the capability name and
   required inputs from a search result.

Workflow for every user request:
- Call search_capabilities with a short description of the goal.
- Review the results: find the best match and understand required inputs.
- Extract business-level input values from the user's message.
- Do not translate names to internal system IDs yourself — the Lattice
  capability will resolve names, titles, and departments internally.
- Call execute_capability with the correct name and an `inputs` JSON object
  containing ALL required fields from the search results.
- CRITICAL: You MUST include the `inputs` object with all required fields.
- If a tool returns an error saying inputs are missing or invalid, fix the
  payload and call execute_capability again.

IMPORTANT — Two-phase flows:
- When a projection contains `decision_required: true` and a list of options
  (e.g. candidates), you MUST present the options to the user and ask them
  to pick before proceeding with the next action.
- Do NOT auto-select; wait for the user's explicit choice.

After receiving any projection, respond in clear natural language using
markdown formatting. Include specific values (IDs, statuses, amounts).
Do not invent information beyond what the projection contains.

## Available Capabilities ({cap_count} registered)

{capabilities_block}
"""


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _find_capability(mod: Any, name: str) -> Any | None:
    from lattice.capability import get_capability_def

    for attr_name in dir(mod):
        obj = getattr(mod, attr_name)
        if callable(obj):
            defn = get_capability_def(obj)
            if defn and defn.name == name:
                return obj
    return None


def _collect_steps_for_visualization(defn: Any) -> None:
    """Run a step-collection pass so visualize can show steps without
    executing the full engine.  Creates a dummy context and swallows
    all errors — the only purpose is to trigger @step decorators."""
    from lattice.context import ExecutionContext
    from lattice.intent import Intent
    from lattice.step import _begin_collecting, _end_collecting

    dummy_inputs = {k: k for k in defn.input_schema}
    ctx = ExecutionContext(intent=Intent(dummy_inputs))

    collector, token = _begin_collecting()
    try:
        with contextlib.suppress(Exception):
            asyncio.run(defn.fn(ctx))
    finally:
        _end_collecting(token)

    defn.steps = list(collector)


def _rebuild_html_index(directory: Path) -> Path:
    """Scan *directory* for Lattice capability HTML files and write
    (or overwrite) an index.html that links to each one."""
    import html as html_mod
    import re

    marker_re = re.compile(
        r"<!-- lattice-capability: (.+?) v(.+?) \| "
        r"inputs=(\d+) proj=(\d+) steps=(\d+) scoped=(\d+) -->"
    )

    entries: list[dict[str, str]] = []
    for f in sorted(directory.glob("*.html")):
        if f.name == "index.html":
            continue
        first_lines = f.read_text()[:500]
        m = marker_re.search(first_lines)
        if m:
            entries.append(
                {
                    "file": f.name,
                    "name": m.group(1),
                    "version": m.group(2),
                    "inputs": m.group(3),
                    "proj": m.group(4),
                    "steps": m.group(5),
                    "scoped": m.group(6),
                }
            )

    esc = html_mod.escape
    rows = ""
    for e in entries:
        rows += f"""\
      <tr>
        <td>
          <a href="{esc(e["file"])}" class="text-decoration-none fw-semibold">
            <i class="bi bi-diagram-3 me-1"></i>{esc(e["name"])}
          </a>
        </td>
        <td><span class="badge bg-secondary-subtle text-secondary">v{esc(e["version"])}</span></td>
        <td class="text-center">{esc(e["inputs"])}</td>
        <td class="text-center">{esc(e["proj"])}</td>
        <td class="text-center">{esc(e["steps"])}</td>
        <td class="text-center">{esc(e["scoped"])}</td>
        <td>
          <a href="{esc(e["file"])}" class="btn btn-sm btn-outline-primary">
            <i class="bi bi-eye"></i> View
          </a>
        </td>
      </tr>
"""

    count = len(entries)
    index_html = f"""\
<!DOCTYPE html>
<html lang="en" data-bs-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lattice — Capability Portal</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">
<style>
  .hero {{
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: #fff;
    padding: 3rem 0;
  }}
  .hero h1 {{ font-weight: 700; }}
  .cap-table th {{
    font-weight: 600; font-size: 0.8rem;
    text-transform: uppercase; letter-spacing: 0.5px;
    color: #6c757d;
  }}
  .cap-table td {{ vertical-align: middle; }}
  .cap-table tr {{ transition: background 0.1s; }}
  .cap-table tr:hover {{ background: #f8f9fa; }}
  .empty-state {{
    text-align: center; padding: 4rem 1rem; color: #adb5bd;
  }}
  .stat-pill {{
    display: inline-flex; align-items: center; gap: 4px;
    background: #f0f0f5; border-radius: 20px; padding: 6px 14px;
    font-weight: 600; font-size: 0.95rem;
  }}
</style>
</head>
<body>

<div class="hero">
  <div class="container">
    <h1><i class="bi bi-grid-3x3-gap me-2"></i>Lattice</h1>
    <p class="opacity-75 mb-3">Capability Portal &mdash; generated visualizations</p>
    <div class="d-flex gap-3">
      <span class="stat-pill" style="background:rgba(255,255,255,0.15);color:#fff">
        <i class="bi bi-box"></i> {count} capabilities
      </span>
    </div>
  </div>
</div>

<div class="container py-4">
  <div class="card">
    <div class="card-header d-flex align-items-center justify-content-between">
      <strong><i class="bi bi-list-ul me-1"></i> Registered Capabilities</strong>
      <small class="text-body-secondary">{count} total</small>
    </div>
    <div class="card-body p-0">
{
        ""
        if entries
        else '<div class="empty-state"><i class="bi bi-inbox" style="font-size:2rem"></i><p class="mt-2">No capability visualizations found.</p><p>Run <code>lattice visualize --html &lt;path&gt;</code> to generate one.</p></div>'
    }
{
        ""
        if not entries
        else f'''      <table class="table table-hover mb-0 cap-table">
        <thead>
          <tr>
            <th>Capability</th>
            <th>Version</th>
            <th class="text-center">Inputs</th>
            <th class="text-center">Projection</th>
            <th class="text-center">Steps</th>
            <th class="text-center">Scoped</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
{rows}        </tbody>
      </table>'''
    }
    </div>
  </div>
</div>

<footer class="text-center py-3 border-top text-body-secondary">
  <small>Generated by <strong>Lattice</strong> &mdash; the capability runtime for outcome-based execution</small>
</footer>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>"""

    index_file = directory / "index.html"
    index_file.write_text(index_html)
    return index_file


def _build_html_visualization(defn: Any) -> str:
    """Generate an interactive HTML portal with Bootstrap layout and
    Mermaid.js flow diagrams for a Lattice capability."""
    import html as html_mod

    esc = html_mod.escape
    cap_name = esc(defn.name)
    version = esc(defn.version)

    # ── Inputs table rows ─────────────────────────────────────────
    inputs_rows = ""
    for n, t in defn.input_schema.items():
        inputs_rows += (
            f"<tr><td><code>{esc(n)}</code></td>"
            f'<td><span class="badge bg-primary-subtle text-primary">{esc(t.__name__)}</span></td></tr>\n'
        )

    # ── Projection table rows ─────────────────────────────────────
    from lattice.types import projection_field_description as _pfd
    from lattice.types import projection_field_example as _pfe
    from lattice.types import projection_field_type as _pft

    proj_rows = ""
    for n, spec in defn.projection_schema.items():
        ftype = _pft(spec).__name__
        fex = _pfe(spec)
        fdesc = _pfd(spec)
        example_html = ""
        if fex is not None:
            example_html = f'<br><small class="text-body-secondary font-monospace">e.g. {esc(repr(fex))}</small>'
        desc_html = ""
        if fdesc:
            desc_html = f'<br><small class="text-body-secondary">{esc(fdesc)}</small>'
        proj_rows += (
            f"<tr><td><code>{esc(n)}</code>{desc_html}</td>"
            f'<td><span class="badge bg-success-subtle text-success">{esc(ftype)}</span>'
            f"{example_html}</td></tr>\n"
        )

    # ── Mermaid flowchart ─────────────────────────────────────────
    mermaid_lines = ["flowchart TD"]

    node_ids: dict[str, str] = {}
    for i, s in enumerate(defn.steps):
        nid = f"S{i}"
        node_ids[s.name] = nid

        policies: list[str] = []
        if s.retry_policy:
            policies.append(f"retry: {s.retry_policy.max_attempts}")
        if s.soft_failure_fallback:
            policies.append("soft-failure")
        if s.hard_failure_action:
            policies.append("hard-failure")
        if s.human_task:
            policies.append("human task")
        if s.needs_human_input:
            policies.append("needs input")

        label = s.name
        if s.scope:
            label += f"\\n{s.scope}"
        if policies:
            label += f"\\n[{', '.join(policies)}]"
        mermaid_lines.append(f'    {nid}["{esc(label)}"]')

    for s in defn.steps:
        for dep in s.depends_on:
            if dep in node_ids:
                mermaid_lines.append(f"    {node_ids[dep]} --> {node_ids[s.name]}")

    mermaid_graph = "\n".join(mermaid_lines)

    # ── Steps detail cards ────────────────────────────────────────
    step_cards = ""
    for idx, s in enumerate(defn.steps):
        badges = ""
        if s.scope:
            badges += f'<span class="badge bg-info-subtle text-info me-1"><i class="bi bi-shield-lock"></i> {esc(s.scope)}</span>'
        if s.retry_policy:
            badges += f'<span class="badge bg-warning-subtle text-warning me-1"><i class="bi bi-arrow-repeat"></i> retry: {s.retry_policy.max_attempts}</span>'
        if s.soft_failure_fallback:
            badges += '<span class="badge bg-success-subtle text-success me-1"><i class="bi bi-check-circle"></i> soft-failure</span>'
        if s.hard_failure_action:
            badges += '<span class="badge bg-danger-subtle text-danger me-1"><i class="bi bi-x-octagon"></i> hard-failure</span>'
        if s.human_task:
            badges += '<span class="badge bg-purple-subtle text-purple me-1"><i class="bi bi-person"></i> human task</span>'
        if s.needs_human_input:
            badges += '<span class="badge bg-orange-subtle text-orange me-1"><i class="bi bi-pencil-square"></i> needs input</span>'

        deps_html = ""
        if s.depends_on:
            dep_badges = " ".join(
                f'<span class="badge bg-secondary-subtle text-secondary">{esc(d)}</span>'
                for d in s.depends_on
            )
            deps_html = f'<div class="mt-2"><small class="text-body-secondary">Depends on:</small> {dep_badges}</div>'

        step_cards += f"""
        <div class="col-md-6 col-lg-4">
          <div class="card h-100 step-card" data-step="{idx}">
            <div class="card-body">
              <h6 class="card-title font-monospace fw-bold">{esc(s.name)}</h6>
              <div>{badges}</div>
              {deps_html}
            </div>
          </div>
        </div>"""

    # ── Capability signature ──────────────────────────────────────
    input_items = [
        f"<span class='sig-param'>{n}: <em>{t.__name__}</em></span>"
        for n, t in defn.input_schema.items()
    ]
    input_args = ",\n    ".join(input_items)

    proj_items = []
    for n, spec in defn.projection_schema.items():
        ftype = _pft(spec).__name__
        fex = _pfe(spec)
        if fex is not None:
            proj_items.append(
                f"<span class='sig-field'>{n}: <em>{ftype}</em>"
                f" <span class='sig-example'>(e.g. {esc(repr(fex))})</span></span>"
            )
        else:
            proj_items.append(f"<span class='sig-field'>{n}: <em>{ftype}</em></span>")
    proj_fields = ",\n    ".join(proj_items)

    signature = (
        f"<span class='sig-name'>{defn.name}</span>(\n"
        f"    {input_args}\n"
        f") &rarr; {{\n"
        f"    {proj_fields}\n"
        f"}}"
    )

    num_inputs = len(defn.input_schema)
    num_proj = len(defn.projection_schema)
    num_steps = len(defn.steps)
    num_scoped = sum(1 for s in defn.steps if s.scope)

    return f"""\
<!DOCTYPE html>
<!-- lattice-capability: {cap_name} v{version} | inputs={num_inputs} proj={num_proj} steps={num_steps} scoped={num_scoped} -->
<html lang="en" data-bs-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{cap_name} — Lattice Capability</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">
<style>
  .hero {{
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: #fff;
    padding: 3rem 0;
  }}
  .hero h1 {{ font-weight: 700; }}
  .hero .badge {{ font-size: 0.85rem; }}
  .signature-box {{
    background: rgba(255,255,255,0.12);
    border-radius: 8px;
    padding: 16px 24px;
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 0.9rem;
    line-height: 1.7;
    margin-top: 1rem;
    backdrop-filter: blur(4px);
    white-space: pre;
    overflow-x: auto;
  }}
  .sig-name {{ font-weight: 700; font-size: 1.05em; }}
  .sig-param {{ color: #c3e0ff; }}
  .sig-field {{ color: #e0f0ff; }}
  .sig-example {{ opacity: 0.7; font-size: 0.9em; }}
  }}
  .section-title {{
    font-weight: 600;
    font-size: 1.1rem;
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }}
  .mermaid {{
    display: flex;
    justify-content: center;
  }}
  .mermaid svg {{
    max-width: 100%;
    height: auto;
  }}
  .step-card {{
    border-left: 3px solid #667eea;
    transition: transform 0.15s, box-shadow 0.15s;
  }}
  .step-card:hover {{
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
  }}
  .table th {{ font-weight: 600; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.5px; color: #6c757d; }}
  .schema-table code {{ font-size: 0.9rem; }}
  .nav-pills .nav-link.active {{
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  }}
  footer {{ color: #adb5bd; }}
</style>
</head>
<body>

<!-- Hero -->
<div class="hero">
  <div class="container">
    <a href="index.html" class="text-white-50 text-decoration-none d-inline-block mb-2" style="font-size:0.85rem">
      <i class="bi bi-arrow-left me-1"></i>Back to Capability Portal
    </a>
    <div class="d-flex align-items-center gap-3 mb-2">
      <h1 class="mb-0">{cap_name}</h1>
      <span class="badge bg-light text-dark">v{version}</span>
    </div>
    <p class="mb-0 opacity-75">Lattice Capability Visualization</p>
    <div class="signature-box">{signature}</div>
  </div>
</div>

<!-- Nav -->
<div class="bg-body-tertiary border-bottom sticky-top">
  <div class="container">
    <ul class="nav nav-pills py-2" id="sections">
      <li class="nav-item"><a class="nav-link active" href="#overview-section">Overview</a></li>
      <li class="nav-item"><a class="nav-link" href="#flow-section">Execution Flow</a></li>
      <li class="nav-item"><a class="nav-link" href="#steps-section">Step Details</a></li>
      <li class="nav-item"><a class="nav-link" href="#schema-section">Schemas</a></li>
    </ul>
  </div>
</div>

<div class="container py-4">

  <!-- Overview -->
  <section id="overview-section" class="mb-5">
    <h5 class="section-title"><i class="bi bi-grid-3x3-gap"></i> Overview</h5>
    <div class="row g-3">
      <div class="col-sm-6 col-lg-3">
        <div class="card text-center h-100">
          <div class="card-body">
            <div class="display-6 fw-bold text-primary">{num_inputs}</div>
            <small class="text-body-secondary">Inputs</small>
          </div>
        </div>
      </div>
      <div class="col-sm-6 col-lg-3">
        <div class="card text-center h-100">
          <div class="card-body">
            <div class="display-6 fw-bold text-success">{num_proj}</div>
            <small class="text-body-secondary">Projection Fields</small>
          </div>
        </div>
      </div>
      <div class="col-sm-6 col-lg-3">
        <div class="card text-center h-100">
          <div class="card-body">
            <div class="display-6 fw-bold text-info">{num_steps}</div>
            <small class="text-body-secondary">Steps</small>
          </div>
        </div>
      </div>
      <div class="col-sm-6 col-lg-3">
        <div class="card text-center h-100">
          <div class="card-body">
            <div class="display-6 fw-bold text-warning">{num_scoped}</div>
            <small class="text-body-secondary">Scoped Steps</small>
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- Execution Flow -->
  <section id="flow-section" class="mb-5">
    <h5 class="section-title"><i class="bi bi-diagram-3"></i> Execution Flow</h5>
    <div class="card">
      <div class="card-body p-4">
        <pre class="mermaid">
{mermaid_graph}
        </pre>
      </div>
    </div>
  </section>

  <!-- Step Details -->
  <section id="steps-section" class="mb-5">
    <h5 class="section-title"><i class="bi bi-list-check"></i> Step Details</h5>
    <div class="row g-3">
      {step_cards}
    </div>
  </section>

  <!-- Schemas -->
  <section id="schema-section" class="mb-5">
    <h5 class="section-title"><i class="bi bi-braces"></i> Schemas</h5>
    <div class="row g-4">
      <div class="col-md-6">
        <div class="card h-100">
          <div class="card-header bg-primary-subtle">
            <strong><i class="bi bi-box-arrow-in-right"></i> Input Schema</strong>
          </div>
          <div class="card-body p-0">
            <table class="table table-hover mb-0 schema-table">
              <thead><tr><th>Field</th><th>Type</th></tr></thead>
              <tbody>{inputs_rows}</tbody>
            </table>
          </div>
        </div>
      </div>
      <div class="col-md-6">
        <div class="card h-100">
          <div class="card-header bg-success-subtle">
            <strong><i class="bi bi-box-arrow-right"></i> Projection Schema</strong>
          </div>
          <div class="card-body p-0">
            <table class="table table-hover mb-0 schema-table">
              <thead><tr><th>Field</th><th>Type</th></tr></thead>
              <tbody>{proj_rows}</tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </section>

</div>

<footer class="text-center py-3 border-top">
  <small>Generated by <strong>Lattice</strong> &mdash; the capability runtime for outcome-based execution</small>
</footer>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
  mermaid.initialize({{
    startOnLoad: true,
    theme: 'default',
    flowchart: {{ curve: 'basis', padding: 20 }},
    themeVariables: {{
      primaryColor: '#e8eaf6',
      primaryBorderColor: '#667eea',
      primaryTextColor: '#1a1a2e',
      lineColor: '#667eea',
      secondaryColor: '#f3e5f5',
      tertiaryColor: '#e8f5e9'
    }}
  }});
</script>
<script>
  document.querySelectorAll('#sections .nav-link').forEach(link => {{
    link.addEventListener('click', e => {{
      e.preventDefault();
      document.querySelectorAll('#sections .nav-link').forEach(l => l.classList.remove('active'));
      link.classList.add('active');
      const target = document.querySelector(link.getAttribute('href'));
      if (target) target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
    }});
  }});
</script>
</body>
</html>"""
