"""Shared helpers for in-memory services."""

from __future__ import annotations


class Result:
    """Attribute-access wrapper for service return values."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __repr__(self) -> str:
        fields = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items())
        return f"Result({fields})"
