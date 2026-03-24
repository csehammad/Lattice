from lattice import capability, step, state, projection
from lattice.failure import retry, soft_failure, hard_failure, abort


@capability(
    name="UpdateAssignment",
    version="1.0",
    inputs={
        "assignment_id": str,
        "role": str,
        "allocation_pct": int,
        "start_date": str,
    },
    projection={
        "assignment_id": {"type": str, "example": "ASGN-48292",
                          "description": "Unique assignment identifier"},
        "status": {"type": str, "example": "updated",
                   "description": "Status of the assignment after update"},
        "updated_fields": {"type": dict,
                           "example": {"role": "Senior Backend Engineer", "allocation_pct": 80},
                           "description": "Fields that were changed"},
        "notification_sent": {"type": bool, "example": True,
                              "description": "Whether stakeholders were notified of the change"},
    },
)
async def update_assignment(ctx):

    @step(depends_on=[], scope="assignments.read")
    @retry(max=3, backoff="exponential", on=[TimeoutError])
    @hard_failure(on_exhausted=abort)
    async def fetch_current():
        client = ctx.client("assignment_api")
        data = await client.get(assignment_id=ctx.intent.assignment_id)
        return {
            "employee_id": data.get("employee_id", ""),
            "project_id": data.get("project_id", ""),
            "current_role": data.get("role", ""),
            "current_alloc": data.get("allocation_pct", 0),
        }

    @step(depends_on=[fetch_current], scope="assignments.write")
    @retry(max=3, backoff="exponential", on=[TimeoutError])
    @hard_failure(on_exhausted=abort)
    async def apply_update():
        client = ctx.client("assignment_api")
        data = await client.update(
            assignment_id=ctx.intent.assignment_id,
            role=ctx.intent.role,
            allocation_pct=ctx.intent.allocation_pct,
            start_date=ctx.intent.start_date,
        )
        return {"status": data.get("status", "updated")}

    @step(depends_on=[apply_update], scope="notifications.write")
    @retry(max=2, on=[TimeoutError])
    @soft_failure(fallback={"sent": False})
    async def notify_stakeholders():
        client = ctx.client("notification_api")
        await client.send(
            recipients=["employee", "project_lead", "manager"],
            message_type="assignment_updated",
            details={
                "assignment_id": ctx.intent.assignment_id,
                "changes": {
                    "role": ctx.intent.role,
                    "allocation_pct": ctx.intent.allocation_pct,
                    "start_date": ctx.intent.start_date,
                },
            },
        )
        return {"sent": True}

    return projection(
        assignment_id=ctx.intent.assignment_id,
        status=state.apply_update.status,
        updated_fields={
            "role": ctx.intent.role,
            "allocation_pct": ctx.intent.allocation_pct,
            "start_date": ctx.intent.start_date,
        },
        notification_sent=state.notify_stakeholders.sent,
    )
