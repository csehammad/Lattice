"""Capability inventory — stores discovered operations and matches them
to capability templates."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from lattice.discovery.openapi import OperationInfo


@dataclass
class CapabilityTemplate:
    """A template describing a capability that can be generated from
    matched operations."""

    name: str
    domain: str
    required_operations: list[str] = field(default_factory=list)
    optional_operations: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class MatchResult:
    """Result of matching operations against a template."""

    template: CapabilityTemplate
    matched_operations: list[OperationInfo] = field(default_factory=list)
    missing_operations: list[str] = field(default_factory=list)
    coverage: float = 0.0


class Inventory:
    """Collects discovered operations and matches them to templates."""

    def __init__(self) -> None:
        self.operations: list[OperationInfo] = []
        self.templates: list[CapabilityTemplate] = []

    def add_operations(self, ops: list[OperationInfo]) -> None:
        self.operations.extend(ops)

    def load_templates(self, path: str | Path) -> None:
        """Load capability templates from a YAML inventory file."""
        path = Path(path)
        text = path.read_text()
        doc = yaml.safe_load(text)
        for entry in doc.get("capabilities", []):
            self.templates.append(
                CapabilityTemplate(
                    name=entry["name"],
                    domain=entry.get("domain", ""),
                    required_operations=entry.get("required_operations", []),
                    optional_operations=entry.get("optional_operations", []),
                    description=entry.get("description", ""),
                )
            )

    def match(self, domain: str | None = None) -> list[MatchResult]:
        """Match discovered operations against templates, optionally
        filtered by domain."""
        op_ids = {op.operation_id for op in self.operations}
        results: list[MatchResult] = []

        for tmpl in self.templates:
            if domain and tmpl.domain != domain:
                continue

            matched = [
                op
                for op in self.operations
                if op.operation_id in (tmpl.required_operations + tmpl.optional_operations)
            ]
            missing = [op_id for op_id in tmpl.required_operations if op_id not in op_ids]

            total_required = len(tmpl.required_operations) or 1
            coverage = (total_required - len(missing)) / total_required

            results.append(
                MatchResult(
                    template=tmpl,
                    matched_operations=matched,
                    missing_operations=missing,
                    coverage=coverage,
                )
            )

        return results

    def to_llm_context(self) -> str:
        """Serialize operations into a compact text block for LLM prompts."""
        lines: list[str] = []
        for op in self.operations:
            line = f"- {op.operation_id}  {op.method} {op.path}"
            if op.summary:
                line += f"  — {op.summary}"
            lines.append(line)

            if op.parameters:
                param_names = [p.get("name", "?") for p in op.parameters]
                lines.append(f"    Parameters: {', '.join(param_names)}")

            if op.request_body_schema:
                lines.append(f"    Request body: {json.dumps(op.request_body_schema, default=str)}")

            if op.response_schema:
                lines.append(f"    Response: {json.dumps(op.response_schema, default=str)}")

            if op.tags:
                lines.append(f"    Tags: {', '.join(op.tags)}")

            if op.security:
                lines.append(f"    Security: {json.dumps(op.security, default=str)}")

        return "\n".join(lines)

    def save(self, path: str | Path) -> None:
        """Save the current inventory to YAML."""
        path = Path(path)
        data = {
            "operations": [
                {
                    "operation_id": op.operation_id,
                    "path": op.path,
                    "method": op.method,
                    "summary": op.summary,
                    "tags": op.tags,
                }
                for op in self.operations
            ]
        }
        path.write_text(yaml.dump(data, default_flow_style=False))
