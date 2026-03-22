"""Tests for lattice.runtime.engine — the execution engine."""

import pytest

from lattice import capability, projection, state, step
from lattice.auth.scopes import CredentialStore
from lattice.errors import AbortExecution, PermissionDenied, ValidationError
from lattice.failure import abort, hard_failure, retry, soft_failure
from lattice.runtime.engine import Engine


@pytest.mark.asyncio
async def test_simple_capability():
    @capability(
        name="Simple",
        version="1.0",
        inputs={"name": str},
        projection={"greeting": str},
    )
    async def simple(ctx):
        @step(depends_on=[])
        async def greet():
            return {"message": f"Hello, {ctx.intent.name}!"}

        return projection(
            greeting=state.greet.message,
        )

    engine = Engine()
    result = await engine.execute(
        simple,
        {"name": "World"},
    )
    assert result == {"greeting": "Hello, World!"}


@pytest.mark.asyncio
async def test_multi_step_with_dependencies():
    @capability(
        name="MultiStep",
        version="1.0",
        inputs={"x": int},
        projection={"final": int},
    )
    async def multi(ctx):
        @step(depends_on=[])
        async def step_a():
            return {"val": ctx.intent.x * 2}

        @step(depends_on=[step_a])
        async def step_b():
            return {"val": state.step_a.val + 10}

        return projection(final=state.step_b.val)

    engine = Engine()
    result = await engine.execute(multi, {"x": 5})
    assert result == {"final": 20}


@pytest.mark.asyncio
async def test_soft_failure_fallback():
    @capability(
        name="SoftFail",
        version="1.0",
        inputs={"x": int},
        projection={"result": str},
    )
    async def soft_cap(ctx):
        @step(depends_on=[])
        @soft_failure(fallback={"status": "fallback"})
        async def failing_step():
            raise RuntimeError("boom")

        return projection(result=state.failing_step.status)

    engine = Engine()
    result = await engine.execute(soft_cap, {"x": 1})
    assert result == {"result": "fallback"}


@pytest.mark.asyncio
async def test_hard_failure_abort():
    @capability(
        name="HardFail",
        version="1.0",
        inputs={"x": int},
        projection={"result": str},
    )
    async def hard_cap(ctx):
        @step(depends_on=[])
        @hard_failure(on_exhausted=abort)
        async def failing_step():
            raise RuntimeError("critical failure")

        return projection(result="unreachable")

    engine = Engine()
    with pytest.raises(AbortExecution, match="failing_step"):
        await engine.execute(hard_cap, {"x": 1})


@pytest.mark.asyncio
async def test_retry_then_succeed():
    call_count = 0

    @capability(
        name="RetrySuccess",
        version="1.0",
        inputs={"x": int},
        projection={"val": int},
    )
    async def retry_cap(ctx):
        @step(depends_on=[])
        @retry(max=3, backoff="fixed", on=[RuntimeError], base_delay=0.01)
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("not yet")
            return {"val": 42}

        return projection(val=state.flaky.val)

    engine = Engine()
    result = await engine.execute(retry_cap, {"x": 0})
    assert result == {"val": 42}
    assert call_count == 3


@pytest.mark.asyncio
async def test_permission_denied():
    @capability(
        name="Secured",
        version="1.0",
        inputs={"x": int},
        projection={"val": int},
    )
    async def secured(ctx):
        @step(depends_on=[], scope="admin.write")
        async def protected_step():
            return {"val": 1}

        return projection(val=state.protected_step.val)

    engine = Engine()
    creds = CredentialStore(granted_scopes={"read.only"})
    with pytest.raises(PermissionDenied, match=r"admin\.write"):
        await engine.execute(secured, {"x": 1}, credentials=creds)


@pytest.mark.asyncio
async def test_scoped_execution_passes():
    @capability(
        name="Scoped",
        version="1.0",
        inputs={"x": int},
        projection={"val": int},
    )
    async def scoped(ctx):
        @step(depends_on=[], scope="data.read")
        async def read_step():
            return {"val": 100}

        return projection(val=state.read_step.val)

    engine = Engine()
    creds = CredentialStore(granted_scopes={"data.read"})
    result = await engine.execute(scoped, {"x": 1}, credentials=creds)
    assert result == {"val": 100}


@pytest.mark.asyncio
async def test_input_validation_missing():
    @capability(
        name="NeedsInput",
        version="1.0",
        inputs={"required_field": str},
        projection={"out": str},
    )
    async def needs_input(ctx):
        @step(depends_on=[])
        async def s():
            return {"out": "x"}

        return projection(out=state.s.out)

    engine = Engine()
    with pytest.raises(ValidationError, match="required_field"):
        await engine.execute(needs_input, {})


@pytest.mark.asyncio
async def test_input_validation_wrong_type():
    @capability(
        name="TypeCheck",
        version="1.0",
        inputs={"count": int},
        projection={"out": int},
    )
    async def type_check(ctx):
        @step(depends_on=[])
        async def s():
            return {"out": 1}

        return projection(out=state.s.out)

    engine = Engine()
    with pytest.raises(ValidationError, match="must be int"):
        await engine.execute(type_check, {"count": "not_an_int"})


@pytest.mark.asyncio
async def test_audit_trail_recorded():
    @capability(
        name="Audited",
        version="1.0",
        inputs={"x": int},
        projection={"val": int},
    )
    async def audited(ctx):
        @step(depends_on=[], scope="read")
        async def s():
            return {"val": ctx.intent.x}

        return projection(val=state.s.val)

    engine = Engine()
    creds = CredentialStore(granted_scopes={"read"})
    await engine.execute(audited, {"x": 7}, credentials=creds, requester="alice")

    assert len(engine.audit_trail.records) == 1
    record = engine.audit_trail.records[0]
    assert record.capability_name == "Audited"
    assert record.requester == "alice"
    assert record.status == "completed"
    assert record.projection == {"val": 7}
    assert len(record.steps) == 1
    assert record.steps[0].step_name == "s"
    assert record.steps[0].status == "completed"


@pytest.mark.asyncio
async def test_three_step_chain():
    @capability(
        name="Chain",
        version="1.0",
        inputs={"base": int},
        projection={"result": int},
    )
    async def chain(ctx):
        @step(depends_on=[])
        async def first():
            return {"val": ctx.intent.base}

        @step(depends_on=[first])
        async def second():
            return {"val": state.first.val * 2}

        @step(depends_on=[second])
        async def third():
            return {"val": state.second.val + 1}

        return projection(result=state.third.val)

    engine = Engine()
    result = await engine.execute(chain, {"base": 10})
    assert result == {"result": 21}


@pytest.mark.asyncio
async def test_keyboard_interrupt_is_not_swallowed():
    @capability(
        name="Interruptible",
        version="1.0",
        inputs={"x": int},
        projection={"ok": bool},
    )
    async def interruptible(ctx):
        @step(depends_on=[])
        async def explode():
            raise KeyboardInterrupt("stop")

        return projection(ok=state.explode.ok)

    engine = Engine()
    with pytest.raises(KeyboardInterrupt):
        await engine.execute(interruptible, {"x": 1})
