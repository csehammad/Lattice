"""Vendor lookup service backed by the ERP store."""

from __future__ import annotations

from tests.services.common import Result
from tests.services.erp import ERPService


class VendorService:
    """Wraps ERP for vendor queries (separate from create operations)."""

    def __init__(self, erp: ERPService) -> None:
        self._erp = erp

    async def get_vendor(self, *, vendor_id: str) -> Result:
        return await self._erp.get_vendor(vendor_id=vendor_id)
