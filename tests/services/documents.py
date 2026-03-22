"""Document request service with tracking."""

from __future__ import annotations

from tests.services.common import Result


class DocumentService:
    def __init__(self) -> None:
        self._requests: dict[str, list[str]] = {}
        self._counter = 0

    def get_pending(self, vendor_id: str) -> list[str]:
        return list(self._requests.get(vendor_id, []))

    async def request(self, *, vendor_id: str, document_types: list) -> Result:
        self._counter += 1
        self._requests[vendor_id] = list(document_types)
        return Result(
            request_id=f"DOC-{self._counter:03d}",
            vendor_id=vendor_id,
            documents_pending=list(document_types),
            portal_link=f"https://vendors.company.com/onboard/{vendor_id}",
        )
