"""Payment terms service with storage."""

from __future__ import annotations

from tests.services.common import Result


class PaymentsService:
    def __init__(self) -> None:
        self._terms: dict[str, dict] = {}

    def get_terms(self, vendor_id: str) -> dict | None:
        return self._terms.get(vendor_id)

    async def set_terms(self, *, vendor_id: str, terms: str, currency: str) -> Result:
        record = {
            "vendor_id": vendor_id,
            "terms": terms,
            "currency": currency,
            "discount_percent": 2.0,
        }
        self._terms[vendor_id] = record
        return Result(**record)
