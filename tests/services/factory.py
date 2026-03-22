"""Service cluster -- wires all in-memory services together."""

from __future__ import annotations

from typing import Any

from tests.services.approval import ApprovalService
from tests.services.budget import BudgetService
from tests.services.documents import DocumentService
from tests.services.erp import ERPService
from tests.services.insurance import InsuranceService
from tests.services.payments import PaymentsService
from tests.services.sanctions import SanctionsService
from tests.services.vendors import VendorService


class ServiceCluster:
    """All in-memory services sharing state where appropriate."""

    def __init__(self) -> None:
        self.sanctions = SanctionsService()
        self.insurance = InsuranceService()
        self.erp = ERPService()
        self.budget = BudgetService()
        self.approval = ApprovalService()
        self.documents = DocumentService()
        self.payments = PaymentsService()
        self.vendors = VendorService(self.erp)

        self._client_map: dict[str, Any] = {
            "sanctions_screening_api": self.sanctions,
            "insurance_verification_api": self.insurance,
            "erp": self.erp,
            "sap": self.erp,
            "payments_api": self.payments,
            "documents_api": self.documents,
            "budget_api": self.budget,
            "vendor_api": self.vendors,
            "approval_api": self.approval,
        }

    def client_factory(self, name: str, credentials: Any = None) -> Any:
        if name not in self._client_map:
            raise KeyError(
                f"No service registered for '{name}'. Available: {sorted(self._client_map)}"
            )
        return self._client_map[name]


def create_service_cluster() -> ServiceCluster:
    """Create a fresh service cluster with default state."""
    return ServiceCluster()
