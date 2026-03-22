"""Unified stub client factory for the Lattice demo.

Merges procurement and travel domain stubs into a single factory
so the agent and runner can execute any capability.
"""

from __future__ import annotations

from demo.procurement.stubs import client_factory as _procurement_factory
from demo.procurement.stubs import _CLIENT_MAP as _PROCUREMENT_MAP
from demo.travel.stubs import client_factory as _travel_factory
from demo.travel.stubs import _CLIENT_MAP as _TRAVEL_MAP

_UNIFIED_MAP = {**_PROCUREMENT_MAP, **_TRAVEL_MAP}


def client_factory(name: str, credentials=None):
    """Return a stub client by name from any domain."""
    if name not in _UNIFIED_MAP:
        raise KeyError(
            f"No stub client registered for '{name}'. "
            f"Available: {sorted(_UNIFIED_MAP)}"
        )
    return _UNIFIED_MAP[name]
