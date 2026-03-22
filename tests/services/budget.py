"""Budget service with real allocation tracking."""

from __future__ import annotations

from tests.services.common import Result


class BudgetService:
    def __init__(self) -> None:
        self._budgets: dict[str, float] = {
            "engineering": 100_000.0,
            "procurement": 50_000.0,
            "compliance": 25_000.0,
        }
        self._allocations: list[dict] = []

    def set_budget(self, department: str, amount: float) -> None:
        self._budgets[department] = amount

    def get_remaining(self, department: str) -> float:
        return self._budgets.get(department, 0.0)

    async def check_limit(
        self, *, department: str, amount: float, category: str
    ) -> Result:
        remaining = self._budgets.get(department, 0.0)
        return Result(
            approved=amount <= remaining,
            remaining=remaining,
            limit=remaining,
        )

    async def allocate(
        self,
        *,
        department: str,
        amount: float,
        purpose: str,
        reference_id: str,
    ) -> Result:
        remaining = self._budgets.get(department, 0.0)
        if amount > remaining:
            raise ValueError(
                f"Insufficient budget: {department} has ${remaining:.2f}, "
                f"requested ${amount:.2f}"
            )
        self._budgets[department] = remaining - amount
        alloc = {
            "department": department,
            "amount": amount,
            "purpose": purpose,
            "reference_id": reference_id,
        }
        self._allocations.append(alloc)
        alloc_id = f"ALLOC-{len(self._allocations):03d}"
        return Result(
            allocation_id=alloc_id,
            department=department,
            amount=amount,
            remaining_after=self._budgets[department],
        )
