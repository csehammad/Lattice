"""Insurance verification service with policy tracking."""

from __future__ import annotations

from tests.services.common import Result


class InsuranceService:
    def __init__(self) -> None:
        self._policies: dict[str, dict] = {
            "Acme Corp": {
                "valid": True,
                "expiry_date": "2027-06-01",
                "provider": "AIG",
            },
            "Global Logistics": {
                "valid": True,
                "expiry_date": "2026-12-15",
                "provider": "Zurich",
            },
        }
        self.fail_next = False

    async def verify(self, *, entity_name: str) -> Result:
        if self.fail_next:
            self.fail_next = False
            raise ConnectionError(f"Insurance service unavailable for {entity_name}")

        policy = self._policies.get(entity_name)
        if policy is None:
            return Result(valid=False, expiry_date=None, provider=None)
        return Result(**policy)
