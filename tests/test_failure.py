"""Tests for lattice.failure decorators."""

from lattice.failure import abort, hard_failure, retry, soft_failure
from lattice.failure.policies import _Abort
from lattice.failure.retry import RetryPolicy
from lattice.step import get_step_meta, step


def test_retry_attaches_policy():
    @step(depends_on=[], scope="r")
    @retry(max=5, backoff="linear", on=[TimeoutError])
    async def my_step():
        return {}

    meta = get_step_meta(my_step)
    assert meta is not None
    assert meta.retry_policy is not None
    assert meta.retry_policy.max_attempts == 5
    assert meta.retry_policy.backoff == "linear"
    assert TimeoutError in meta.retry_policy.on


def test_soft_failure_attaches():
    @step(depends_on=[])
    @soft_failure(fallback={"ok": False})
    async def my_step():
        return {}

    meta = get_step_meta(my_step)
    assert meta is not None
    assert meta.soft_failure_fallback is not None
    assert meta.soft_failure_fallback.fallback == {"ok": False}


def test_hard_failure_with_abort():
    @step(depends_on=[])
    @hard_failure(on_exhausted=abort)
    async def my_step():
        return {}

    meta = get_step_meta(my_step)
    assert meta is not None
    assert meta.hard_failure_action is not None
    assert isinstance(meta.hard_failure_action.on_exhausted, _Abort)


def test_abort_repr():
    assert repr(abort) == "abort"


def test_retry_delay_exponential():
    policy = RetryPolicy(max_attempts=3, backoff="exponential", on=(Exception,))
    d0 = policy.delay_for(0)
    d1 = policy.delay_for(1)
    assert d1 > d0


def test_retry_delay_linear():
    policy = RetryPolicy(max_attempts=3, backoff="linear", on=(Exception,), base_delay=2.0)
    assert policy.delay_for(0) == 2.0
    assert policy.delay_for(1) == 4.0


def test_retry_delay_fixed():
    policy = RetryPolicy(max_attempts=3, backoff="fixed", on=(Exception,), base_delay=1.5)
    assert policy.delay_for(0) == 1.5
    assert policy.delay_for(2) == 1.5
