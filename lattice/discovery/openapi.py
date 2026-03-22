"""Parse OpenAPI specs into a structured inventory of available operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from lattice.log import get_logger

logger = get_logger(__name__)


@dataclass
class OperationInfo:
    """One API operation extracted from an OpenAPI spec."""

    operation_id: str
    path: str
    method: str
    summary: str = ""
    parameters: list[dict[str, Any]] = field(default_factory=list)
    request_body_schema: dict[str, Any] | None = None
    response_schema: dict[str, Any] | None = None
    tags: list[str] = field(default_factory=list)
    security: list[dict[str, Any]] = field(default_factory=list)


def parse_openapi(spec_path: str | Path) -> list[OperationInfo]:
    """Parse an OpenAPI YAML/JSON spec and return operation descriptors."""
    path = Path(spec_path)
    logger.info("Parsing OpenAPI spec: %s", path)
    text = path.read_text()
    if path.suffix in (".yaml", ".yml"):
        doc = yaml.safe_load(text)
    else:
        import json

        doc = json.loads(text)

    operations: list[OperationInfo] = []
    paths = doc.get("paths", {})

    for url_path, methods in paths.items():
        for method, details in methods.items():
            if method.startswith("x-") or method == "parameters":
                continue
            op_id = details.get("operationId", f"{method}_{url_path}")
            params = details.get("parameters", [])
            req_body = None
            rb = details.get("requestBody", {})
            if rb:
                content = rb.get("content", {})
                json_ct = content.get("application/json", {})
                req_body = json_ct.get("schema")

            resp_schema = None
            responses = details.get("responses", {})
            for code, resp in responses.items():
                if code.startswith("2"):
                    content = resp.get("content", {})
                    json_ct = content.get("application/json", {})
                    resp_schema = json_ct.get("schema")
                    break

            operations.append(
                OperationInfo(
                    operation_id=op_id,
                    path=url_path,
                    method=method.upper(),
                    summary=details.get("summary", ""),
                    parameters=params,
                    request_body_schema=req_body,
                    response_schema=resp_schema,
                    tags=details.get("tags", []),
                    security=details.get("security", []),
                )
            )

    logger.info("Discovered %d operations from %s", len(operations), path.name)
    return operations
