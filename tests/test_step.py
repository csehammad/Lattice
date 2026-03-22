"""Tests for lattice.step."""

from lattice.step import get_step_meta, step


def test_step_decorator_basic():
    @step(depends_on=[], scope="read")
    async def my_step():
        return {"x": 1}

    meta = get_step_meta(my_step)
    assert meta is not None
    assert meta.name == "my_step"
    assert meta.depends_on == []
    assert meta.scope == "read"


def test_step_decorator_with_deps():
    @step(depends_on=[], scope="a")
    async def first():
        return {}

    @step(depends_on=[first], scope="b")
    async def second():
        return {}

    meta = get_step_meta(second)
    assert meta is not None
    assert meta.depends_on == ["first"]


def test_step_no_scope():
    @step(depends_on=[])
    async def plain():
        return {}

    meta = get_step_meta(plain)
    assert meta is not None
    assert meta.scope is None
