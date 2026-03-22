"""Tests for lattice.state."""

import pytest

from lattice.state import StateStore, _StateProxy, bind_store, unbind_store


def test_state_store_set_get():
    store = StateStore()
    store.set("step_a", {"value": 42})
    assert store.get("step_a") == {"value": 42}


def test_state_store_has():
    store = StateStore()
    assert not store.has("missing")
    store.set("found", {"x": 1})
    assert store.has("found")


def test_step_view_attribute_access():
    store = StateStore()
    store.set("my_step", {"risk_score": 85, "passed": True})
    view = store.view("my_step")
    assert view.risk_score == 85
    assert view.passed is True


def test_step_view_missing_field():
    store = StateStore()
    store.set("my_step", {"a": 1})
    view = store.view("my_step")
    with pytest.raises(AttributeError, match="no field 'missing'"):
        _ = view.missing


def test_state_proxy_outside_execution():
    proxy = _StateProxy()
    with pytest.raises(RuntimeError, match="outside of a capability"):
        _ = proxy.anything


def test_state_proxy_with_bound_store():
    store = StateStore()
    store.set("s1", {"val": "hello"})
    token = bind_store(store)
    try:
        proxy = _StateProxy()
        assert proxy.s1.val == "hello"
    finally:
        unbind_store(token)


def test_state_proxy_step_not_run():
    store = StateStore()
    token = bind_store(store)
    try:
        proxy = _StateProxy()
        with pytest.raises(AttributeError, match="hasn't run yet"):
            _ = proxy.nonexistent
    finally:
        unbind_store(token)
