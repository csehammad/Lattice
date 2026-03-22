"""Intent — typed representation of what the model requested."""

from __future__ import annotations

from typing import Any


class Intent:
    """Wraps the raw input dict so fields are accessible as attributes.

    >>> intent = Intent({"vendor_name": "Acme", "region": "US"})
    >>> intent.vendor_name
    'Acme'
    """

    def __init__(self, fields: dict[str, Any]) -> None:
        self._fields = dict(fields)

    def __getattr__(self, name: str) -> Any:
        try:
            return self._fields[name]
        except KeyError:
            raise AttributeError(
                f"Intent has no field '{name}'. Available: {list(self._fields)}"
            ) from None

    def __repr__(self) -> str:
        pairs = ", ".join(f"{k}={v!r}" for k, v in self._fields.items())
        return f"Intent({pairs})"

    def to_dict(self) -> dict[str, Any]:
        return dict(self._fields)
