from lattice import capability, step, state, projection
from lattice.failure import retry, soft_failure, hard_failure, abort


@capability(
    name="ViewEmployeeWorkload",
    version="1.0",
    inputs={"employee_id": str},
    projection={
        "employee_name": {"type": str, "example": "Alice Chen",
                          "description": "Full name of the employee"},
        "current_role": {"type": str, "example": "Senior Backend Engineer",
                         "description": "Employee current role"},
        "skills": {"type": list, "example": [{"skill": "Python", "proficiency": "expert"}],
                   "description": "Skill profile with proficiency levels"},
        "availability_pct": {"type": int, "example": 60,
                             "description": "Current availability percentage"},
        "schedule": {"type": dict,
                     "example": {"current_projects": ["Phoenix"], "pto": []},
                     "description": "Current schedule including project commitments and PTO"},
    },
)
async def view_employee_workload(ctx):

    @step(depends_on=[], scope="employees.read")
    @retry(max=3, backoff="exponential", on=[TimeoutError])
    @hard_failure(on_exhausted=abort)
    async def get_employee():
        client = ctx.client("employee_api")
        data = await client.get(employee_id=ctx.intent.employee_id)
        first = data.get("first_name", "")
        last = data.get("last_name", "")
        return {
            "name": f"{first} {last}".strip() or data.get("name", ""),
            "role": data.get("current_role", data.get("role", "")),
        }

    @step(depends_on=[get_employee], scope="employees.read")
    @retry(max=3, backoff="exponential", on=[TimeoutError])
    @soft_failure(fallback={"skills": []})
    async def get_skills():
        client = ctx.client("employee_api")
        data = await client.skills(employee_id=ctx.intent.employee_id)
        return {"skills": data.get("skills", [])}

    @step(depends_on=[get_employee], scope="availability.read")
    @retry(max=3, backoff="exponential", on=[TimeoutError])
    @soft_failure(fallback={"pct": 0})
    async def get_availability():
        client = ctx.client("availability_api")
        data = await client.get(employee_id=ctx.intent.employee_id)
        allocated = data.get("allocation_pct", 0)
        return {"pct": 100 - allocated}

    @step(depends_on=[get_employee], scope="availability.read")
    @retry(max=3, backoff="exponential", on=[TimeoutError])
    @soft_failure(fallback={"schedule": {}})
    async def get_schedule():
        client = ctx.client("availability_api")
        data = await client.schedule(employee_id=ctx.intent.employee_id)
        return {"schedule": data}

    return projection(
        employee_name=state.get_employee.name,
        current_role=state.get_employee.role,
        skills=state.get_skills.skills,
        availability_pct=state.get_availability.pct,
        schedule=state.get_schedule.schedule,
    )
