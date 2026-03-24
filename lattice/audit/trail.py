"""Structured audit trail for capability executions."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from lattice.log import get_logger

if TYPE_CHECKING:
    from lattice.audit.sinks import AuditSink

logger = get_logger(__name__)


@dataclass
class StepRecord:
    """Audit record for a single step execution."""

    step_name: str
    scope: str | None = None
    status: str = "pending"  # pending | running | completed | failed | skipped
    started_at: float | None = None
    finished_at: float | None = None
    duration_ms: float | None = None
    attempts: int = 0
    result: Any = None
    error: str | None = None

    def mark_running(self) -> None:
        self.status = "running"
        self.started_at = time.time()

    def mark_completed(self, result: Any) -> None:
        self.status = "completed"
        self.finished_at = time.time()
        self.result = result
        if self.started_at:
            self.duration_ms = (self.finished_at - self.started_at) * 1000

    def mark_failed(self, error: BaseException) -> None:
        self.status = "failed"
        self.finished_at = time.time()
        self.error = str(error)
        if self.started_at:
            self.duration_ms = (self.finished_at - self.started_at) * 1000

    def mark_skipped(self, reason: str) -> None:
        self.status = "skipped"
        self.error = reason


@dataclass
class AuditRecord:
    """Audit record for an entire capability execution."""

    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    capability_name: str = ""
    capability_version: str = ""
    requester: str = ""
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    duration_ms: float | None = None
    status: str = "running"  # running | completed | failed | aborted
    steps: list[StepRecord] = field(default_factory=list)
    projection: Any = None
    error: str | None = None
    intent: dict[str, Any] = field(default_factory=dict)
    granted_scopes: list[str] = field(default_factory=list)

    def add_step(self, step_name: str, scope: str | None = None) -> StepRecord:
        rec = StepRecord(step_name=step_name, scope=scope)
        self.steps.append(rec)
        return rec

    def complete(self, projection: Any) -> None:
        self.status = "completed"
        self.finished_at = time.time()
        self.projection = projection
        self.duration_ms = (self.finished_at - self.started_at) * 1000

    def fail(self, error: BaseException) -> None:
        self.status = "failed"
        self.finished_at = time.time()
        self.error = str(error)
        self.duration_ms = (self.finished_at - self.started_at) * 1000

    def abort(self, error: BaseException) -> None:
        self.status = "aborted"
        self.finished_at = time.time()
        self.error = str(error)
        self.duration_ms = (self.finished_at - self.started_at) * 1000

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "capability": self.capability_name,
            "version": self.capability_version,
            "requester": self.requester,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "intent": self.intent,
            "granted_scopes": self.granted_scopes,
            "steps": [
                {
                    "step": s.step_name,
                    "scope": s.scope,
                    "status": s.status,
                    "attempts": s.attempts,
                    "duration_ms": s.duration_ms,
                    "error": s.error,
                }
                for s in self.steps
            ],
            "projection": self.projection,
            "error": self.error,
        }


class AuditTrail:
    """Routes AuditRecords to a pluggable sink.

    Pass any ``AuditSink`` implementation to customise storage.
    Defaults to ``InMemoryAuditSink`` when no sink is provided.
    """

    def __init__(self, sink: AuditSink | None = None) -> None:
        from lattice.audit.sinks import InMemoryAuditSink

        self._sink: AuditSink = sink or InMemoryAuditSink()

    def record(self, audit: AuditRecord) -> None:
        self._sink.emit(audit)
        logger.debug(
            "Audit recorded: %s [%s] %s (%.1fms)",
            audit.capability_name,
            audit.execution_id[:8],
            audit.status,
            audit.duration_ms or 0,
        )

    @property
    def records(self) -> list[AuditRecord]:
        return self._sink.records

    def query(
        self,
        capability: str | None = None,
        requester: str | None = None,
        status: str | None = None,
    ) -> list[AuditRecord]:
        return self._sink.query(
            capability=capability, requester=requester, status=status
        )

    @property
    def sink(self) -> AuditSink:
        """The underlying sink instance."""
        return self._sink
