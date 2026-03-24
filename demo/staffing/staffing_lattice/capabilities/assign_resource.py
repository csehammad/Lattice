from lattice import capability, step, state, projection
from lattice.failure import retry, soft_failure, hard_failure, abort


@capability(
    name="AssignResource",
    version="1.0",
    inputs={
        "candidate_id": str,
        "project_id": str,
        "role": str,
        "start_date": str,
        "allocation_pct": int,
        "requested_by": str,
    },
    projection={
        "assignment_id": {"type": str, "example": "ASGN-48291",
                          "description": "Unique assignment identifier"},
        "status": {"type": str, "example": "confirmed",
                   "description": "Assignment status (confirmed, pending_manager_approval, conflict_detected)"},
        "candidate_name": {"type": str, "example": "Alice Chen",
                           "description": "Name of the assigned resource"},
        "effective_start_date": {"type": str, "example": "2026-04-01",
                                 "description": "Confirmed start date"},
        "allocation_confirmed_pct": {"type": int, "example": 80,
                                     "description": "Confirmed allocation percentage"},
        "notifications_sent": {"type": list, "example": ["candidate", "current_manager", "project_lead"],
                               "description": "Stakeholders who were notified"},
        "follow_up_actions": {"type": list, "example": ["schedule_onboarding_sync", "transfer_current_tasks"],
                              "description": "Actions to take after assignment is confirmed"},
    },
)
async def assign_resource(ctx):

    @step(depends_on=[], scope="hr.read")
    @retry(max=3, backoff="exponential", on=[TimeoutError])
    @hard_failure(on_exhausted=abort)
    async def validate_assignment():
        client = ctx.client("assignment_api")
        result = await client.validate(
            employee_id=ctx.intent.candidate_id,
            project_id=ctx.intent.project_id,
            allocation_pct=ctx.intent.allocation_pct,
            start_date=ctx.intent.start_date,
            role=ctx.intent.role,
        )
        return {
            "valid": result["valid"],
            "conflicts": result.get("conflicts", []),
            "warnings": result.get("warnings", []),
        }

    @step(depends_on=[validate_assignment], scope="hr.write")
    @retry(max=2, on=[TimeoutError])
    @hard_failure(on_exhausted=abort)
    async def reserve_allocation():
        if not state.validate_assignment.valid:
            return {
                "assignment_id": None,
                "employee_name": "",
                "status": "conflict_detected",
                "start_date": ctx.intent.start_date,
                "allocation_pct": 0,
            }
        client = ctx.client("assignment_api")
        result = await client.create(
            employee_id=ctx.intent.candidate_id,
            project_id=ctx.intent.project_id,
            allocation_pct=ctx.intent.allocation_pct,
            start_date=ctx.intent.start_date,
            role=ctx.intent.role,
            requested_by=ctx.intent.requested_by,
        )
        return {
            "assignment_id": result["assignment_id"],
            "employee_name": result.get("employee_name", ""),
            "status": result["status"],
            "start_date": result["start_date"],
            "allocation_pct": result["allocation_pct"],
        }

    @step(depends_on=[reserve_allocation], scope="notification.write")
    @retry(max=2, on=[TimeoutError])
    @soft_failure(fallback={"recipients_notified": []})
    async def notify_stakeholders():
        if state.reserve_allocation.assignment_id is None:
            return {"recipients_notified": []}
        client = ctx.client("notification_api")
        recipients = ["candidate", "current_manager", "project_lead"]
        result = await client.send(
            recipients=recipients,
            message_type="assignment_created",
            details={
                "assignment_id": state.reserve_allocation.assignment_id,
                "project_id": ctx.intent.project_id,
                "employee_id": ctx.intent.candidate_id,
                "role": ctx.intent.role,
            },
        )
        return {"recipients_notified": result.get("recipients", recipients)}

    @step(depends_on=[reserve_allocation], scope="project.write")
    @retry(max=2, on=[TimeoutError])
    @soft_failure(fallback={"plan_updated": False})
    async def update_project_plan():
        if state.reserve_allocation.assignment_id is None:
            return {"plan_updated": False}
        client = ctx.client("project_plan_api")
        await client.update(
            project_id=ctx.intent.project_id,
            employee_id=ctx.intent.candidate_id,
            employee_name=state.reserve_allocation.employee_name,
            role=ctx.intent.role,
            allocation_pct=ctx.intent.allocation_pct,
            start_date=ctx.intent.start_date,
        )
        return {"plan_updated": True}

    follow_ups = []
    if state.reserve_allocation.status == "confirmed":
        follow_ups = ["schedule_onboarding_sync", "transfer_current_tasks"]

    return projection(
        assignment_id=state.reserve_allocation.assignment_id or "NONE",
        status=state.reserve_allocation.status,
        candidate_name=state.reserve_allocation.employee_name,
        effective_start_date=state.reserve_allocation.start_date,
        allocation_confirmed_pct=state.reserve_allocation.allocation_pct,
        notifications_sent=state.notify_stakeholders.recipients_notified,
        follow_up_actions=follow_ups,
    )
