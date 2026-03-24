#!/usr/bin/env python3
"""Staffing Agent HTTP server — exposes the LLM agent over REST.

Endpoints:
    POST /chat          — send a user message, get agent reply + projections + audit
    POST /chat/reset    — clear conversation history
    GET  /chat/history  — return full conversation history
    GET  /health        — liveness check

The Staffing Platform API must be running (default http://localhost:8001).
This server runs on port 8003.

Usage:
    cd demo/staffing
    python agent_server.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from staffing_lattice.capabilities.find_candidates import find_candidates
from staffing_lattice.capabilities.assign_resource import assign_resource
from staffing_lattice.capabilities.view_project_staffing import view_project_staffing
from staffing_lattice.capabilities.view_employee_workload import view_employee_workload
from staffing_lattice.capabilities.update_assignment import update_assignment
from staffing_lattice.capabilities.cancel_assignment import cancel_assignment
from staffing_lattice.stubs import STAFFING_API_URL, client_factory

from lattice.auth.scopes import CredentialStore
from lattice.runtime.engine import Engine
from lattice.runtime.registry import CapabilityRegistry, LazyRegistry


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
    "assignments.read", "assignments.write",
    "availability.read",
    "employees.read",
    "notifications.read", "notifications.write",
    "projects.read", "projects.write",
    "resource_plans.read",
}

MANIFEST_PATH = Path(__file__).parent / "registry.json"
PROMPT_PATH = Path(__file__).parent / "SYSTEM_PROMPT.txt"

SYSTEM_PROMPT = PROMPT_PATH.read_text() if PROMPT_PATH.exists() else "You are a staffing assistant."


app = FastAPI(title="Lattice Staffing Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


_ALL_CAPABILITIES = [
    find_candidates,
    assign_resource,
    view_project_staffing,
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


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    import openai

    _state.messages.append({"role": "user", "content": req.message})
    turn_tool_calls: list[dict] = []
    turn_projections: list[dict] = []
    turn_audit: list[dict] = []

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
            return ChatResponse(
                reply=reply,
                tool_calls=turn_tool_calls,
                projections=turn_projections,
                audit=turn_audit,
                conversation_length=len([m for m in _state.messages if m.get("role") != "system"]),
            )

        _state.messages.append(msg.model_dump())

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

            content = result["result"] if result["type"] != "projection" else result["result"]
            _state.messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(content, default=str),
            })

    return ChatResponse(
        reply="(agent reached max tool-call rounds)",
        tool_calls=turn_tool_calls,
        projections=turn_projections,
        audit=turn_audit,
        conversation_length=len([m for m in _state.messages if m.get("role") != "system"]),
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
    return {
        "status": "ok",
        "model": _model,
        "capabilities": list(_lazy._manifest.keys()),
        "staffing_api": STAFFING_API_URL,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
