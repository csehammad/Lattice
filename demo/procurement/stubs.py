"""Stub API clients for the Lattice demo.

Each stub returns realistic-looking data so capabilities can run
end-to-end without real backend services.  The ``client_factory``
function at the bottom maps client names used in capabilities to
the corresponding stub instances.
"""

from __future__ import annotations

from typing import ClassVar


class _Obj:
    """Tiny helper to build objects with attribute access from kwargs."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class SanctionsClient:
    async def check(self, *, entity_name: str, country: str):
        return _Obj(clear=True, score=15, matched_lists=[])


class InsuranceClient:
    async def verify(self, *, entity_name: str):
        return _Obj(valid=True, expiry_date="2027-06-01", provider="AIG")


class ERPClient:
    _counter = 0

    async def create_vendor(self, **kwargs):
        ERPClient._counter += 1
        return _Obj(
            id=f"V-{10000 + ERPClient._counter}",
            default_terms="net-30",
        )


class PaymentsClient:
    async def set_terms(self, *, vendor_id: str, terms: str, currency: str):
        return _Obj(
            vendor_id=vendor_id,
            terms=terms,
            currency=currency,
            discount_percent=2.0,
        )


class DocumentsClient:
    async def request(self, *, vendor_id: str, document_types: list):
        return _Obj(
            request_id="DOC-001",
            vendor_id=vendor_id,
            documents_pending=document_types,
            portal_link=f"https://vendors.company.com/onboard/{vendor_id}",
        )


class BudgetClient:
    async def check_limit(self, *, department: str, amount: float, category: str):
        return _Obj(approved=True, remaining=50000.0, limit=100000.0)

    async def allocate(self, *, department: str, amount: float, purpose: str, reference_id: str):
        return _Obj(
            allocation_id="ALLOC-001",
            department=department,
            amount=amount,
            remaining_after=50000.0 - amount,
        )


class VendorClient:
    _vendors: ClassVar[list[dict[str, str]]] = [
        {
            "id": "V-10001",
            "name": "Acme Industrial Supply",
            "type": "supplier",
            "region": "US",
            "status": "active",
            "default_terms": "net-30",
        },
        {
            "id": "V-10002",
            "name": "Northwind Office",
            "type": "supplier",
            "region": "US",
            "status": "active",
            "default_terms": "net-45",
        },
    ]

    async def list_vendors(self):
        return [_Obj(**vendor) for vendor in self._vendors]

    async def get_vendor(self, *, vendor_id: str):
        for vendor in self._vendors:
            if vendor["id"] == vendor_id:
                return _Obj(**vendor)
        raise KeyError(f"Vendor '{vendor_id}' not found")


class ApprovalClient:
    async def submit(self, *, request_type: str, requester: str, details: dict, amount: float):
        return _Obj(
            request_id="APR-001",
            status="approved",
            approver="Sarah Chen",
        )

    async def get_status(self, *, request_id: str):
        return _Obj(
            request_id=request_id,
            status="approved",
            approver="Sarah Chen",
        )


_CLIENT_MAP = {
    "sanctions_screening_api": SanctionsClient(),
    "insurance_verification_api": InsuranceClient(),
    "erp": ERPClient(),
    "payments_api": PaymentsClient(),
    "documents_api": DocumentsClient(),
    "budget_api": BudgetClient(),
    "vendor_api": VendorClient(),
    "approval_api": ApprovalClient(),
}


def client_factory(name: str, credentials=None):
    """Return a stub client by name.  Used by ``lattice run --stubs demo.stubs``."""
    if name not in _CLIENT_MAP:
        raise KeyError(f"No stub client registered for '{name}'.  Available: {sorted(_CLIENT_MAP)}")
    return _CLIENT_MAP[name]
