from staffing_lattice.resolution import resolve_employee

from lattice import capability, projection, state, step
from lattice.failure import abort, hard_failure, retry, soft_failure


@capability(
    name="ViewEmployeeWorkload",
    version="1.0",
    inputs={"employee_name": str},
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
    async def resolve():
        client = ctx.client("employee_api")
        emp = await resolve_employee(client, ctx.intent.employee_name)
        first = emp.get("first_name", "")
        last = emp.get("last_name", "")
        return {
            "employee_id": emp["id"],
            "name": f"{first} {last}".strip() or emp.get("name", ""),
            "role": emp.get("current_role", emp.get("role", "")),
        }

    @step(depends_on=[resolve], scope="employees.read")
    @retry(max=3, backoff="exponential", on=[TimeoutError])
    @soft_failure(fallback={"skills": []})
    async def get_skills():
        client = ctx.client("employee_api")
        data = await client.skills(employee_id=state.resolve.employee_id)
        return {"skills": data.get("skills", [])}

    @step(depends_on=[resolve], scope="availability.read")
    @retry(max=3, backoff="exponential", on=[TimeoutError])
    @soft_failure(fallback={"pct": 0})
    async def get_availability():
        client = ctx.client("availability_api")
        data = await client.get(employee_id=state.resolve.employee_id)
        allocated = data.get("allocation_pct", 0)
        return {"pct": 100 - allocated}

    @step(depends_on=[resolve], scope="availability.read")
    @retry(max=3, backoff="exponential", on=[TimeoutError])
    @soft_failure(fallback={"schedule": {}})
    async def get_schedule():
        client = ctx.client("availability_api")
        data = await client.schedule(employee_id=state.resolve.employee_id)
        return {"schedule": data}

    return projection(
        employee_name=state.resolve.name,
        current_role=state.resolve.role,
        skills=state.get_skills.skills,
        availability_pct=state.get_availability.pct,
        schedule=state.get_schedule.schedule,
    )
