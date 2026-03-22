"""Tests for lattice.auth."""

import pytest

from lattice.auth.scopes import CredentialStore, require_role, require_scope
from lattice.errors import PermissionDenied


def test_has_scope_exact():
    store = CredentialStore(granted_scopes={"compliance.read", "vendor.write"})
    assert store.has_scope("compliance.read")
    assert store.has_scope("vendor.write")
    assert not store.has_scope("admin")


def test_has_scope_wildcard():
    store = CredentialStore(granted_scopes={"*"})
    assert store.has_scope("anything.at.all")


def test_has_scope_empty():
    store = CredentialStore()
    assert store.has_scope("")  # empty scope always passes


def test_check_scope_raises():
    store = CredentialStore(granted_scopes={"read"})
    with pytest.raises(PermissionDenied, match=r"vendor\.write"):
        store.check_scope("my_step", "vendor.write")


def test_has_role():
    store = CredentialStore(granted_roles={"admin", "viewer"})
    assert store.has_role("admin")
    assert not store.has_role("editor")


def test_require_scope_decorator():
    @require_scope("special.access")
    async def my_fn():
        pass

    assert hasattr(my_fn, "_lattice_required_scopes")
    assert "special.access" in my_fn._lattice_required_scopes


def test_require_role_decorator():
    @require_role("admin")
    async def my_fn():
        pass

    assert hasattr(my_fn, "_lattice_required_roles")
    assert "admin" in my_fn._lattice_required_roles


def test_credential_store_get_credential():
    store = CredentialStore(credentials={"api_key": "secret123"})
    assert store.get_credential("api_key") == "secret123"
    assert store.get_credential("missing") is None
