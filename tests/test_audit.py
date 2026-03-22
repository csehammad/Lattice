"""Tests for lattice.audit."""

from lattice.audit.trail import AuditRecord, AuditTrail, StepRecord


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
