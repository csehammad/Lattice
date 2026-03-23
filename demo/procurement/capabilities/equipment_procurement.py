"""Capability: EquipmentProcurement

Composes budget verification, vendor lookup, approval submission,
budget allocation, and approval tracking into a single procurement
workflow.

Endpoints used:
  - checkBudgetLimit    POST /budgets/check
  - listVendors         GET  /vendors
  - getVendor           GET  /vendors/{vendorId}
  - submitApproval      POST /approvals
  - allocateBudget      POST /budgets/allocate
  - getApprovalStatus   GET  /approvals/{requestId}
"""

from lattice import capability, projection, state, step
from lattice.failure import abort, hard_failure, retry, soft_failure


class ServerError(Exception):
    pass


def _normalize(value: str) -> str:
    return " ".join(value.strip().casefold().split())


@capability(
    name="EquipmentProcurement",
    version="1.0",
    inputs={
        "item": str,
        "quantity": int,
        "budget_department": str,
        "preferred_vendor": str,
        "requested_by": str,
    },
    projection={
        "order_status": {
            "type": str,
            "example": "approved",
            "description": (
                "Current procurement order status (approved, pending_approval, over_budget)"
            ),
        },
        "total_cost": {
            "type": float,
            "example": 2500.00,
            "description": "Total cost of the procurement order in USD",
        },
        "vendor_name": {
            "type": str,
            "example": "Acme Industrial Supply",
            "description": "Name of the selected vendor fulfilling the order",
        },
        "approval_status": {
            "type": str,
            "example": "approved",
            "description": "Manager approval status (approved, pending, rejected)",
        },
        "budget_remaining": {
            "type": float,
            "example": 47500.00,
            "description": "Department budget remaining after this procurement",
        },
    },
)
async def equipment_procurement(ctx):

    @step(depends_on=[], scope="budget.read")
    @retry(max=3, backoff="exponential", on=[TimeoutError, ServerError])
    @hard_failure(on_exhausted=abort)
    async def check_budget():
        client = ctx.client("budget_api")
        result = await client.check_limit(
            department=ctx.intent.budget_department,
            amount=ctx.intent.quantity * 500.0,
            category="equipment",
        )
        return {
            "approved": result.approved,
            "remaining": result.remaining,
            "limit": result.limit,
        }

    @step(depends_on=[], scope="vendor.read")
    @retry(max=2, on=[TimeoutError, ServerError])
    @soft_failure(
        fallback={"vendor_id": None, "vendor_name": "unknown", "warning": "vendor lookup failed"}
    )
    async def find_vendor():
        client = ctx.client("vendor_api")
        preferred_vendor = _normalize(ctx.intent.preferred_vendor)
        for vendor in await client.list_vendors():
            if (
                _normalize(vendor.id) == preferred_vendor
                or _normalize(vendor.name) == preferred_vendor
            ):
                return {
                    "vendor_id": vendor.id,
                    "vendor_name": vendor.name,
                    "vendor_status": vendor.status,
                }
        raise ValueError(f"Vendor '{ctx.intent.preferred_vendor}' not found")

    @step(depends_on=[check_budget, find_vendor], scope="approval.write")
    @retry(max=2, on=[TimeoutError, ServerError])
    @hard_failure(on_exhausted=abort)
    async def submit_for_approval():
        client = ctx.client("approval_api")
        total = ctx.intent.quantity * 500.0
        approval = await client.submit(
            request_type="equipment_procurement",
            requester=ctx.intent.requested_by,
            details={
                "item": ctx.intent.item,
                "quantity": ctx.intent.quantity,
                "vendor_id": state.find_vendor.vendor_id,
                "total_cost": total,
            },
            amount=total,
        )
        return {
            "request_id": approval.request_id,
            "approval_status": approval.status,
        }

    @step(depends_on=[submit_for_approval], scope="budget.write")
    @retry(max=2, on=[TimeoutError, ServerError])
    @hard_failure(on_exhausted=abort)
    async def allocate_budget():
        client = ctx.client("budget_api")
        total = ctx.intent.quantity * 500.0
        allocation = await client.allocate(
            department=ctx.intent.budget_department,
            amount=total,
            purpose=f"Equipment: {ctx.intent.item}",
            reference_id=state.submit_for_approval.request_id,
        )
        return {
            "allocation_id": allocation.allocation_id,
            "remaining_after": allocation.remaining_after,
        }

    @step(depends_on=[submit_for_approval], scope="approval.read")
    @retry(max=3, backoff="exponential", on=[TimeoutError, ServerError])
    @soft_failure(fallback={"final_status": "pending", "warning": "could not confirm approval"})
    async def track_approval():
        client = ctx.client("approval_api")
        status = await client.get_status(
            request_id=state.submit_for_approval.request_id,
        )
        return {"final_status": status.status, "approver": status.approver}

    total_cost = ctx.intent.quantity * 500.0

    return projection(
        order_status="submitted",
        total_cost=total_cost,
        vendor_name=state.find_vendor.vendor_name,
        approval_status=state.track_approval.final_status,
        budget_remaining=state.allocate_budget.remaining_after,
    )
