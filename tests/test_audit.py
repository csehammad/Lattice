"""Tests for lattice.audit."""

import pytest

from lattice.audit.sinks import (
    AuditSink,
    InMemoryAuditSink,
    JsonFileAuditSink,
)
from lattice.audit.trail import AuditRecord, AuditTrail, StepRecord


# ---------------------------------------------------------------------------
# StepRecord / AuditRecord (unchanged)
# ---------------------------------------------------------------------------


def test_step_record_lifecycle():
    rec = StepRecord(step_name="s1", scope="read")
    assert rec.status == "pending"

    rec.mark_running()
    assert rec.status == "running"
    assert rec.started_at is not None

    rec.mark_completed({"val": 1})
    assert rec.status == "completed"
    assert rec.result == {"val": 1}
    assert rec.duration_ms is not None


def test_step_record_failure():
    rec = StepRecord(step_name="s1")
    rec.mark_running()
    rec.mark_failed(ValueError("boom"))
    assert rec.status == "failed"
    assert "boom" in rec.error


def test_audit_record_complete():
    audit = AuditRecord(capability_name="Test", requester="user1")
    step_rec = audit.add_step("s1", "read")
    step_rec.mark_running()
    step_rec.mark_completed({"ok": True})

    audit.complete({"result": "done"})
    assert audit.status == "completed"
    assert audit.projection == {"result": "done"}
    assert len(audit.steps) == 1


def test_audit_record_to_dict():
    audit = AuditRecord(capability_name="Test", requester="u")
    audit.complete({"r": 1})
    d = audit.to_dict()
    assert d["capability"] == "Test"
    assert d["status"] == "completed"
    assert "execution_id" in d


def test_audit_trail_query():
    trail = AuditTrail()

    a1 = AuditRecord(capability_name="Cap1", requester="alice")
    a1.complete({})
    trail.record(a1)

    a2 = AuditRecord(capability_name="Cap2", requester="bob")
    a2.fail(RuntimeError("err"))
    trail.record(a2)

    assert len(trail.query(capability="Cap1")) == 1
    assert len(trail.query(requester="bob")) == 1
    assert len(trail.query(status="failed")) == 1
    assert len(trail.records) == 2


# ---------------------------------------------------------------------------
# AuditSink ABC
# ---------------------------------------------------------------------------


def test_audit_sink_cannot_be_instantiated():
    with pytest.raises(TypeError):
        AuditSink()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# InMemoryAuditSink
# ---------------------------------------------------------------------------


def test_in_memory_sink_emit_and_records():
    sink = InMemoryAuditSink()
    assert sink.records == []

    a = AuditRecord(capability_name="Cap1", requester="alice")
    a.complete({})
    sink.emit(a)

    assert len(sink.records) == 1
    assert sink.records[0].capability_name == "Cap1"


def test_in_memory_sink_query():
    sink = InMemoryAuditSink()

    a1 = AuditRecord(capability_name="Cap1", requester="alice")
    a1.complete({})
    sink.emit(a1)

    a2 = AuditRecord(capability_name="Cap2", requester="bob")
    a2.fail(RuntimeError("err"))
    sink.emit(a2)

    assert len(sink.query(capability="Cap1")) == 1
    assert len(sink.query(requester="bob")) == 1
    assert len(sink.query(status="failed")) == 1
    assert len(sink.query(status="completed")) == 1


def test_in_memory_sink_records_returns_copy():
    sink = InMemoryAuditSink()
    a = AuditRecord(capability_name="X")
    a.complete({})
    sink.emit(a)

    r1 = sink.records
    r2 = sink.records
    assert r1 is not r2


# ---------------------------------------------------------------------------
# JsonFileAuditSink
# ---------------------------------------------------------------------------


def test_json_file_sink_emit_and_records(tmp_path):
    path = tmp_path / "audit.jsonl"
    sink = JsonFileAuditSink(path)

    a = AuditRecord(capability_name="Cap1", requester="alice")
    step = a.add_step("s1", "read")
    step.mark_running()
    step.mark_completed({"ok": True})
    a.complete({"result": "done"})
    sink.emit(a)

    records = sink.records
    assert len(records) == 1
    rec = records[0]
    assert rec.capability_name == "Cap1"
    assert rec.requester == "alice"
    assert rec.status == "completed"
    assert len(rec.steps) == 1
    assert rec.steps[0].step_name == "s1"
    assert rec.steps[0].scope == "read"
    assert rec.execution_id == a.execution_id


def test_json_file_sink_query(tmp_path):
    path = tmp_path / "audit.jsonl"
    sink = JsonFileAuditSink(path)

    a1 = AuditRecord(capability_name="Cap1", requester="alice")
    a1.complete({})
    sink.emit(a1)

    a2 = AuditRecord(capability_name="Cap2", requester="bob")
    a2.fail(RuntimeError("err"))
    sink.emit(a2)

    assert len(sink.query(capability="Cap1")) == 1
    assert len(sink.query(requester="bob")) == 1
    assert len(sink.query(status="failed")) == 1
    assert len(sink.records) == 2


def test_json_file_sink_empty_file(tmp_path):
    path = tmp_path / "audit.jsonl"
    sink = JsonFileAuditSink(path)
    assert sink.records == []


def test_json_file_sink_creates_parent_dirs(tmp_path):
    path = tmp_path / "nested" / "dir" / "audit.jsonl"
    sink = JsonFileAuditSink(path)

    a = AuditRecord(capability_name="X")
    a.complete({})
    sink.emit(a)

    assert path.exists()
    assert len(sink.records) == 1


# ---------------------------------------------------------------------------
# AuditTrail with injected sink
# ---------------------------------------------------------------------------


def test_audit_trail_default_sink_is_in_memory():
    trail = AuditTrail()
    assert isinstance(trail.sink, InMemoryAuditSink)


def test_audit_trail_accepts_custom_sink():
    sink = InMemoryAuditSink()
    trail = AuditTrail(sink=sink)
    assert trail.sink is sink


def test_audit_trail_with_json_file_sink(tmp_path):
    path = tmp_path / "audit.jsonl"
    sink = JsonFileAuditSink(path)
    trail = AuditTrail(sink=sink)

    a = AuditRecord(capability_name="Cap1", requester="alice")
    a.complete({"done": True})
    trail.record(a)

    assert len(trail.records) == 1
    assert trail.records[0].capability_name == "Cap1"
    assert len(trail.query(requester="alice")) == 1
    assert path.exists()
