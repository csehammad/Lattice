"""Approval service with stateful workflow transitions."""

from __future__ import annotations

from tests.services.common import Result


class ApprovalService:
    def __init__(self) -> None:
        self._requests: dict[str, dict] = {}
        self._counter = 0
        self.auto_approve = True

    async def submit(
        self,
        *,
        request_type: str,
        requester: str,
        details: dict,
        amount: float,
    ) -> Result:
        self._counter += 1
        request_id = f"APR-{self._counter:03d}"
        status = "approved" if self.auto_approve else "pending"
        record = {
            "request_id": request_id,
            "request_type": request_type,
            "requester": requester,
            "details": details,
            "amount": amount,
            "status": status,
            "approver": "Sarah Chen" if status == "approved" else None,
        }
        self._requests[request_id] = record
        return Result(
            request_id=request_id,
            status=status,
            approver=record["approver"],
        )

    async def get_status(self, *, request_id: str) -> Result:
        record = self._requests.get(request_id)
        if record is None:
            raise KeyError(f"Approval request {request_id} not found")
        return Result(
            request_id=request_id,
            status=record["status"],
            approver=record["approver"],
        )

    def approve(self, request_id: str) -> None:
        if request_id not in self._requests:
            raise KeyError(f"Approval request {request_id} not found")
        self._requests[request_id]["status"] = "approved"
        self._requests[request_id]["approver"] = "Sarah Chen"

    def reject(self, request_id: str) -> None:
        if request_id not in self._requests:
            raise KeyError(f"Approval request {request_id} not found")
        self._requests[request_id]["status"] = "rejected"
