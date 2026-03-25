#!/usr/bin/env python3
"""Staffing Agent HTTP server — exposes the LLM agent over REST.

Endpoints:
    POST /chat          — send a user message, get agent reply + projections + audit
    POST /chat/reset    — clear conversation history
    GET  /chat/history  — return full conversation history
    GET  /health        — liveness check

The Staffing Platform API should be reachable at STAFFING_API_URL (default
http://localhost:8001). On application startup, if the URL points at localhost and nothing answers
/health, an embedded in-memory staffing API is started on that port (works
with both `python agent_server.py` and `uvicorn agent_server:app`).

This server runs on port 8003.

Usage:
    cd demo/staffing
    python agent_server.py

Open the chat UI at http://127.0.0.1:8003/ (do not use file:// — browsers block
fetch to localhost from file pages).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def _merge_env_file(path: Path) -> None:
    """Set os.environ for non-empty values only; later files override earlier ones.

    Empty assignments (e.g. OPENAI_API_KEY=) are skipped so a key from repo
    root api.env is not overwritten by a blank line in demo/staffing/api.env.
    """
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and value:
            os.environ[key] = value


_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_merge_env_file(_REPO_ROOT / "api.env")
_merge_env_file(Path(__file__).parent / "api.env")
_merge_env_file(Path(__file__).parent.parent / "hr" / "api.env")

import httpx  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.encoders import jsonable_encoder  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse, Response  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from staffing_lattice.capabilities.assign_resource import assign_resource  # noqa: E402
from staffing_lattice.capabilities.cancel_assignment import cancel_assignment  # noqa: E402
from staffing_lattice.capabilities.find_candidates import find_candidates  # noqa: E402
from staffing_lattice.capabilities.update_assignment import update_assignment  # noqa: E402
from staffing_lattice.capabilities.view_employee_workload import (  # noqa: E402
    view_employee_workload,
)
from staffing_lattice.stubs import STAFFING_API_URL, client_factory  # noqa: E402
from starlette.requests import Request  # noqa: E402

from lattice.auth.scopes import CredentialStore  # noqa: E402
from lattice.runtime.engine import Engine  # noqa: E402
from lattice.runtime.registry import CapabilityRegistry, LazyRegistry  # noqa: E402

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

MANIFEST_PATH = Path(__file__).parent / "registry.json"
PROMPT_PATH = Path(__file__).parent / "SYSTEM_PROMPT.txt"

def _build_system_prompt() -> str:
    import datetime
    base = PROMPT_PATH.read_text() if PROMPT_PATH.exists() else "You are a staffing assistant."
    today = datetime.date.today()
    date_line = f"TODAY'S DATE: {today.strftime('%A, %B %d, %Y')} (ISO: {today.isoformat()})\n\n"
    return date_line + base

SYSTEM_PROMPT = _build_system_prompt()


def _staffing_health_url() -> str:
    return f"{STAFFING_API_URL.rstrip('/')}/health"


def staffing_api_reachable() -> bool:
    try:
        r = httpx.get(_staffing_health_url(), timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


def _staffing_url_is_local(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in ("127.0.0.1", "localhost", "::1")


def _staffing_bind_port(url: str) -> int:
    parsed = urlparse(url)
    if parsed.port is not None:
        return parsed.port
    return 443 if parsed.scheme == "https" else 80


def _start_embedded_staffing_api(host: str, port: int) -> None:
    """Run the in-memory staffing FastAPI in a daemon thread (local demo only)."""

    def _run() -> None:
        import uvicorn as _uv
        from staffing_api.app import app as staffing_app

        _uv.run(staffing_app, host=host, port=port, log_level="warning")

    threading.Thread(target=_run, daemon=True, name="embedded-staffing-api").start()
    deadline = time.time() + 20.0
    while time.time() < deadline:
        if staffing_api_reachable():
            return
        time.sleep(0.15)
    raise RuntimeError(
        f"Embedded staffing API did not become ready on port {port} "
        "(port may be in use by another process)."
    )


def ensure_local_staffing_api() -> None:
    """If STAFFING_API_URL points at localhost and nothing answers /health, start the demo API."""
    if staffing_api_reachable():
        return
    if not _staffing_url_is_local(STAFFING_API_URL):
        print(
            f"WARNING: Staffing API not reachable at {STAFFING_API_URL!r}. "
            "Start the staffing API or fix STAFFING_API_URL.",
            file=sys.stderr,
        )
        return
    port = _staffing_bind_port(STAFFING_API_URL)
    print(
        f"Staffing API not reachable; starting embedded server on 0.0.0.0:{port} …",
        file=sys.stderr,
    )
    _start_embedded_staffing_api("0.0.0.0", port)


@asynccontextmanager
async def _agent_lifespan(_app: FastAPI):
    try:
        await asyncio.to_thread(ensure_local_staffing_api)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
    yield


app = FastAPI(
    title="Lattice Staffing Agent API",
    version="1.0.0",
    lifespan=_agent_lifespan,
)

# allow_credentials=False so allow_origins=["*"] is valid (browser rejects * with credentials).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _chat_errors_as_json(request: Request, call_next):
    """Never return a plain-text 500 for POST /chat (UI expects JSON)."""
    if request.url.path != "/chat" or request.method != "POST":
        return await call_next(request)
    try:
        return await call_next(request)
    except Exception as exc:
        return Response(
            status_code=200,
            media_type="application/json",
            content=json.dumps(
                {
                    "reply": (
                        f"**Server error** ({type(exc).__name__}): {exc}\n\n"
                        "Set OPENAI_API_KEY in Lattice/api.env or demo/staffing/api.env "
                        "and restart agent_server.py."
                    ),
                    "tool_calls": [],
                    "projections": [],
                    "audit": [],
                    "conversation_length": 0,
                }
            ),
        )


_DEMO_DIR = Path(__file__).resolve().parent


@app.get("/")
async def serve_staffing_demo():
    """Serve the interactive demo over HTTP (avoids file:// + fetch failures)."""
    return FileResponse(_DEMO_DIR / "staffing_demo.html")


_ALL_CAPABILITIES = [
    find_candidates,
    assign_resource,
    view_employee_workload,
    update_assignment,
    cancel_assignment,
]


def _build_registry() -> LazyRegistry:
    eager = CapabilityRegistry()
    for cap_fn in _ALL_CAPABILITIES:
        eager.register(cap_fn)
    eager.save(MANIFEST_PATH)
    return LazyRegistry.from_manifest(MANIFEST_PATH)


_lazy = _build_registry()
_engine = Engine()
_model = os.environ.get("OPENAI_MODEL", "gpt-4o")


class AgentState:
    def __init__(self) -> None:
        self.messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.tool_calls: list[dict] = []
        self.projections: list[dict] = []
        self.audit_records: list[dict] = []

    def reset(self) -> None:
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.tool_calls = []
        self.projections = []
        self.audit_records = []


_state = AgentState()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    tool_calls: list[dict]
    projections: list[dict]
    audit: list[dict]
    conversation_length: int


async def _dispatch(tool: str, args: dict) -> dict:
    if tool == "search_capabilities":
        return {"type": "search", "result": _lazy.search(args.get("query", ""))}

    if tool == "execute_capability":
        name = args.get("capability_name", "")
        manifest_entry = _lazy._manifest.get(name, {})
        inputs = args.get("inputs")
        if not inputs:
            inputs = {k: v for k, v in args.items() if k != "capability_name"}
        if not isinstance(inputs, dict) or not inputs:
            return {
                "type": "error",
                "result": {
                    "error": f"Missing inputs for capability '{name}'",
                    "required_inputs": manifest_entry.get("inputs", {}),
                    "instruction": (
                        "Call execute_capability again with a complete 'inputs' object."
                    ),
                },
            }
        _lazy.ensure_loaded(name)
        fn = _lazy.get_function(name)
        creds = CredentialStore(granted_scopes=STAFFING_SCOPES)
        try:
            result = await _engine.execute(
                fn, inputs,
                credentials=creds,
                client_factory=client_factory,
                requester="staffing-web-agent",
            )
            _state.projections.append({"capability": name, "projection": result})

            audit_rec = None
            if _engine.audit_trail.records:
                r = _engine.audit_trail.records[-1]
                audit_rec = {
                    "capability": f"{r.capability_name} v{r.capability_version}",
                    "status": r.status,
                    "steps": len(r.steps),
                    "duration_ms": round(r.duration_ms) if r.duration_ms else None,
                    "execution_id": r.execution_id,
                }
                _state.audit_records.append(audit_rec)

            return {"type": "projection", "capability": name, "result": result, "audit": audit_rec}
        except Exception as exc:
            return {
                "type": "error",
                "result": {
                    "error": str(exc),
                    "required_inputs": manifest_entry.get("inputs", {}),
                },
            }
    return {"type": "error", "result": {"error": f"unknown tool: {tool}"}}


def _visible_message_count() -> int:
    return len([m for m in _state.messages if m.get("role") != "system"])


def _assistant_message_for_api(msg: Any) -> dict[str, Any]:
    """OpenAI rejects full msg.model_dump() (extra keys like audio, annotations)."""
    d: dict[str, Any] = {"role": "assistant", "content": msg.content}
    tcalls = getattr(msg, "tool_calls", None)
    if tcalls:
        d["tool_calls"] = [
            {
                "id": tc.id,
                "type": getattr(tc, "type", None) or "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in tcalls
        ]
    return d


def _json_chat_response(body: ChatResponse) -> Response:
    """Always emit valid JSON (avoids FastAPI 500 on non-encodable projection fields)."""
    try:
        payload = json.dumps(jsonable_encoder(body.model_dump()))
    except Exception as enc_exc:
        payload = json.dumps(
            {
                "reply": f"**Response encoding failed** ({type(enc_exc).__name__}): {enc_exc}",
                "tool_calls": [],
                "projections": [],
                "audit": [],
                "conversation_length": 0,
            }
        )
    return Response(media_type="application/json", content=payload)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> Response:
    """Keep /chat responses JSON-shaped even on unexpected crashes."""
    print(
        f"ERROR: unhandled exception for {request.method} {request.url.path}: "
        f"{type(exc).__name__}: {exc}",
        file=sys.stderr,
    )
    if request.url.path == "/chat":
        return _json_chat_response(
            ChatResponse(
                reply=(
                    f"**Unexpected server error** ({type(exc).__name__}): {exc}\n\n"
                    "Please retry. If it persists, check server logs and OPENAI_API_KEY."
                ),
                tool_calls=[],
                projections=[],
                audit=[],
                conversation_length=_visible_message_count(),
            )
        )
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {exc}"},
    )


@app.post("/chat")
async def chat(req: ChatRequest):
    import openai

    messages_snapshot = list(_state.messages)
    _state.messages.append({"role": "user", "content": req.message})
    turn_tool_calls: list[dict] = []
    turn_projections: list[dict] = []
    turn_audit: list[dict] = []

    try:
        client = openai.OpenAI()
        tools = LazyRegistry.openai_meta_tools()

        for _ in range(10):
            response = client.chat.completions.create(
                model=_model,
                messages=_state.messages,
                tools=tools,
                tool_choice="auto",
            )
            msg = response.choices[0].message

            if not msg.tool_calls:
                reply = msg.content or ""
                _state.messages.append({"role": "assistant", "content": reply})
                return _json_chat_response(
                    ChatResponse(
                        reply=reply,
                        tool_calls=turn_tool_calls,
                        projections=turn_projections,
                        audit=turn_audit,
                        conversation_length=_visible_message_count(),
                    )
                )

            _state.messages.append(_assistant_message_for_api(msg))

            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                result = await _dispatch(tc.function.name, args)

                tool_entry = {
                    "tool": tc.function.name,
                    "args": args,
                    "result_type": result["type"],
                }
                if result["type"] == "search":
                    tool_entry["capabilities_found"] = [
                        r.get("name") for r in result["result"] if isinstance(r, dict)
                    ]
                elif result["type"] == "projection":
                    tool_entry["capability"] = result["capability"]
                    turn_projections.append({
                        "capability": result["capability"],
                        "projection": result["result"],
                    })
                    if result.get("audit"):
                        turn_audit.append(result["audit"])
                elif result["type"] == "error":
                    tool_entry["error"] = result["result"].get("error", "")

                turn_tool_calls.append(tool_entry)
                _state.tool_calls.append(tool_entry)

                content = result["result"]
                _state.messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(content, default=str),
                })

        return _json_chat_response(
            ChatResponse(
                reply="(agent reached max tool-call rounds)",
                tool_calls=turn_tool_calls,
                projections=turn_projections,
                audit=turn_audit,
                conversation_length=_visible_message_count(),
            )
        )
    except Exception as exc:
        _state.messages = messages_snapshot
        hint = (
            "Check OPENAI_API_KEY and OPENAI_MODEL in Lattice/api.env or "
            "demo/staffing/api.env (non-empty values only). "
            "Examples: gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo."
        )
        return _json_chat_response(
            ChatResponse(
                reply=(
                    f"**Model request failed** ({type(exc).__name__}): {exc}\n\n{hint}"
                ),
                tool_calls=[],
                projections=[],
                audit=[],
                conversation_length=_visible_message_count(),
            )
        )


@app.post("/chat/reset")
async def reset_chat():
    _state.reset()
    return {"status": "ok", "message": "Conversation reset"}


@app.get("/chat/history")
async def get_history():
    visible = [m for m in _state.messages if m.get("role") != "system"]
    return {
        "messages": visible,
        "projections": _state.projections,
        "audit": _state.audit_records,
    }


@app.get("/health")
async def health():
    api_ok = await asyncio.to_thread(staffing_api_reachable)
    return {
        "status": "ok",
        "model": _model,
        "capabilities": list(_lazy._manifest.keys()),
        "staffing_api": STAFFING_API_URL,
        "staffing_api_reachable": api_ok,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8003)
