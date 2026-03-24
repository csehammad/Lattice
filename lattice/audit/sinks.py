"""Pluggable audit sinks for AuditRecord persistence."""

from __future__ import annotations

import json
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from lattice.audit.trail import AuditRecord, StepRecord


class AuditSink(ABC):
    """Abstract interface for audit record persistence.

    Implement ``emit`` to store records and ``query`` / ``records``
    to retrieve them.  Pass an instance to ``AuditTrail(sink=...)``
    to wire it in.
    """

    @abstractmethod
    def emit(self, record: AuditRecord) -> None:
        """Persist or forward a single audit record."""
        ...

    @abstractmethod
    def query(
        self,
        capability: str | None = None,
        requester: str | None = None,
        status: str | None = None,
    ) -> list[AuditRecord]:
        """Return records matching the given filters."""
        ...

    @property
    @abstractmethod
    def records(self) -> list[AuditRecord]:
        """Return all stored records (newest last)."""
        ...


class InMemoryAuditSink(AuditSink):
    """Stores audit records in an in-memory list.  No persistence."""

    def __init__(self) -> None:
        self._records: list[AuditRecord] = []

    def emit(self, record: AuditRecord) -> None:
        self._records.append(record)

    def query(
        self,
        capability: str | None = None,
        requester: str | None = None,
        status: str | None = None,
    ) -> list[AuditRecord]:
        results = self._records
        if capability:
            results = [r for r in results if r.capability_name == capability]
        if requester:
            results = [r for r in results if r.requester == requester]
        if status:
            results = [r for r in results if r.status == status]
        return results

    @property
    def records(self) -> list[AuditRecord]:
        return list(self._records)


def _record_to_json(record: AuditRecord) -> str:
    return json.dumps(record.to_dict(), default=str)


def _record_from_dict(d: dict[str, Any]) -> AuditRecord:
    steps = [
        StepRecord(
            step_name=s["step"],
            scope=s.get("scope"),
            status=s.get("status", "pending"),
            attempts=s.get("attempts", 0),
            duration_ms=s.get("duration_ms"),
            error=s.get("error"),
        )
        for s in d.get("steps", [])
    ]
    return AuditRecord(
        execution_id=d["execution_id"],
        capability_name=d.get("capability", ""),
        capability_version=d.get("version", ""),
        requester=d.get("requester", ""),
        started_at=d.get("started_at", 0.0),
        finished_at=d.get("finished_at"),
        duration_ms=d.get("duration_ms"),
        status=d.get("status", "running"),
        steps=steps,
        projection=d.get("projection"),
        error=d.get("error"),
        intent=d.get("intent", {}),
        granted_scopes=d.get("granted_scopes", []),
    )


class JsonFileAuditSink(AuditSink):
    """Appends audit records as JSON lines to a file for durable storage.

    Each call to ``emit`` appends one JSON line.  ``records`` and ``query``
    read back from the file so they reflect the full persisted history.
    Thread-safe via a lock around file writes.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()

    def emit(self, record: AuditRecord) -> None:
        line = _record_to_json(record) + "\n"
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as f:
                f.write(line)

    def _load(self) -> list[AuditRecord]:
        if not self._path.exists():
            return []
        records: list[AuditRecord] = []
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                records.append(_record_from_dict(json.loads(line)))
        return records

    def query(
        self,
        capability: str | None = None,
        requester: str | None = None,
        status: str | None = None,
    ) -> list[AuditRecord]:
        results = self._load()
        if capability:
            results = [r for r in results if r.capability_name == capability]
        if requester:
            results = [r for r in results if r.requester == requester]
        if status:
            results = [r for r in results if r.status == status]
        return results

    @property
    def records(self) -> list[AuditRecord]:
        return self._load()
