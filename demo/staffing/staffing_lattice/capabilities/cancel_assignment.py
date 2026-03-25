from lattice import capability, projection, state, step
from lattice.failure import abort, hard_failure, retry, soft_failure


@capability(
    name="CancelAssignment",
    version="1.0",
    inputs={"assignment_id": str, "notify": bool},
    projection={
        "assignment_id": {"type": str, "example": "ASGN-48292",
                          "description": "Unique identifier for the cancelled assignment"},
        "status": {"type": str, "example": "cancelled",
                   "description": "Assignment status after cancellation"},
        "notification_sent": {"type": bool, "example": True,
                              "description": "Whether stakeholders were notified"},
    },
)
async def cancel_assignment(ctx):

    @step(depends_on=[], scope="assignments.read")
    @retry(max=3, backoff="exponential", on=[TimeoutError])
    @hard_failure(on_exhausted=abort)
    async def fetch_assignment():
        client = ctx.client("assignment_api")
        data = await client.get(assignment_id=ctx.intent.assignment_id)
        return {
            "employee_id": data.get("employee_id", ""),
            "project_id": data.get("project_id", ""),
        }

    @step(depends_on=[fetch_assignment], scope="assignments.write")
    @retry(max=3, backoff="exponential", on=[TimeoutError])
    @hard_failure(on_exhausted=abort)
    async def do_cancel():
        client = ctx.client("assignment_api")
        data = await client.cancel(assignment_id=ctx.intent.assignment_id)
        return {"status": data.get("status", "cancelled")}

    @step(depends_on=[do_cancel], scope="notifications.write")
    @retry(max=2, on=[TimeoutError])
    @soft_failure(fallback={"sent": False})
    async def send_notification():
        if not ctx.intent.notify:
            return {"sent": False}
        client = ctx.client("notification_api")
        await client.send(
            recipients=["employee", "project_lead", "manager"],
            message_type="assignment_cancelled",
            details={"assignment_id": ctx.intent.assignment_id},
        )
        return {"sent": True}

    return projection(
        assignment_id=ctx.intent.assignment_id,
        status=state.do_cancel.status,
        notification_sent=state.send_notification.sent,
    )
