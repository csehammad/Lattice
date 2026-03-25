from staffing_lattice.resolution import resolve_project

from lattice import capability, projection, state, step
from lattice.failure import abort, hard_failure, retry, soft_failure


@capability(
    name="ViewProjectStaffing",
    version="1.0",
    inputs={"project_name": str},
    projection={
        "project_name": {"type": str, "example": "Project Phoenix",
                         "description": "Name of the project"},
        "status": {"type": str, "example": "active",
                   "description": "Current project status"},
        "staffing_gaps": {"type": list, "example": ["Data Scientist", "UX Designer"],
                          "description": "Unfilled positions and skill needs"},
        "resource_plan": {"type": list,
                          "example": [
                              {"employee_id": "EMP-2187",
                               "role": "Backend Engineer",
                               "allocation_pct": 100},
                          ],
                          "description": "Current resource assignments for the project"},
    },
)
async def view_project_staffing(ctx):

    @step(depends_on=[], scope="projects.read")
    @retry(max=3, backoff="exponential", on=[TimeoutError])
    @hard_failure(on_exhausted=abort)
    async def resolve():
        client = ctx.client("project_api")
        project = await resolve_project(client, ctx.intent.project_name)
        return {
            "project_id": project["id"],
            "name": project.get("name", ""),
            "status": project.get("status", ""),
        }

    @step(depends_on=[resolve], scope="projects.read")
    @retry(max=3, backoff="exponential", on=[TimeoutError])
    @soft_failure(fallback={"gaps": []})
    async def get_gaps():
        client = ctx.client("project_api")
        data = await client.staffing_gaps(project_id=state.resolve.project_id)
        return {"gaps": data.get("gaps", data.get("unfilled_positions", []))}

    @step(depends_on=[resolve], scope="projects.read")
    @retry(max=3, backoff="exponential", on=[TimeoutError])
    @soft_failure(fallback={"plan": []})
    async def get_plan():
        client = ctx.client("project_plan_api")
        data = await client.get(project_id=state.resolve.project_id)
        return {"plan": data.get("resources", data.get("assignments", []))}

    return projection(
        project_name=state.resolve.name,
        status=state.resolve.status,
        staffing_gaps=state.get_gaps.gaps,
        resource_plan=state.get_plan.plan,
    )
