"""ERP service with in-memory vendor store."""

from __future__ import annotations

from tests.services.common import Result


class ERPService:
    def __init__(self) -> None:
        self._vendors: dict[str, dict] = {}
        self._counter = 10000

    @property
    def vendors(self) -> dict[str, dict]:
        return dict(self._vendors)

    async def create_vendor(self, **kwargs) -> Result:
        self._counter += 1
        vendor_id = f"V-{self._counter}"
        record = {
            "id": vendor_id,
            "name": kwargs.get("name", "Unknown"),
            "type": kwargs.get("type", "supplier"),
            "region": kwargs.get("region", "US"),
            "risk_score": kwargs.get("risk_score", 0),
            "insurance_status": kwargs.get("insurance_status"),
            "default_terms": "net-30",
            "status": "active",
        }
        self._vendors[vendor_id] = record
        return Result(id=vendor_id, default_terms="net-30")

    async def get_vendor(self, *, vendor_id: str) -> Result:
        record = self._vendors.get(vendor_id)
        if record is None:
            raise KeyError(f"Vendor {vendor_id} not found")
        return Result(**record)
