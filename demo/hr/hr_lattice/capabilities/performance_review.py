"""Capability: PerformanceReview

Submits a structured performance review for an employee:
  1. Fetches employee details to validate they exist
  2. Fetches review history (in parallel — informational only)
  3. Submits the new review record

API endpoints exercised:
  GET  /employees/{id}
  GET  /performance/reviews/{employee_id}
  POST /performance/reviews
"""

from hr_lattice.resolution import resolve_employee

from lattice import capability, projection, state, step
from lattice.failure import abort, hard_failure, retry, soft_failure


@capability(
    name="PerformanceReview",
    version="1.0",
    inputs={
        "employee": str,
        "reviewer": str,
        "rating": int,
        "notes": str,
    },
    projection={
        "review_id": {
            "type": str,
            "example": "RV2",
            "description": "Unique ID of the submitted review",
        },
        "employee_name": {
            "type": str,
            "example": "Alice Chen",
            "description": "Full name of the reviewed employee",
        },
        "rating": {
            "type": int,
            "example": 4,
            "description": "Submitted rating (1-5 scale)",
        },
        "status": {
            "type": str,
            "example": "submitted",
            "description": "Review lifecycle status",
        },
        "previous_reviews_count": {
            "type": int,
            "example": 2,
            "description": "Number of prior reviews on record before this one",
        },
    },
)
async def performance_review(ctx):

    @step(depends_on=[], scope="hr.read")
    @retry(max=2, on=[Exception])
    @hard_failure(on_exhausted=abort)
    async def resolve_review_subject():
        client = ctx.client("employees")
        emp = await resolve_employee(client, ctx.intent.employee)
        return {
            "employee_id": emp["id"],
            "name": f"{emp['first_name']} {emp['last_name']}",
        }

    @step(depends_on=[], scope="hr.read")
    @retry(max=2, on=[Exception])
    @hard_failure(on_exhausted=abort)
    async def resolve_reviewer():
        client = ctx.client("employees")
        reviewer = await resolve_employee(client, ctx.intent.reviewer)
        return {
            "reviewer_id": reviewer["id"],
            "reviewer_name": f"{reviewer['first_name']} {reviewer['last_name']}",
        }

    @step(depends_on=[resolve_review_subject], scope="hr.read")
    @retry(max=2, on=[Exception])
    @hard_failure(on_exhausted=abort)
    async def fetch_employee():
        client = ctx.client("employees")
        emp = await client.get(state.resolve_review_subject.employee_id)
        return {
            "name": f"{emp['first_name']} {emp['last_name']}",
            "department_id": emp["department_id"],
            "status": emp["status"],
        }

    @step(depends_on=[fetch_employee], scope="hr.read")
    @retry(max=2, on=[Exception])
    @soft_failure(fallback={"previous_count": 0, "reviews": []})
    async def fetch_review_history():
        client = ctx.client("performance")
        result = await client.get_reviews(state.resolve_review_subject.employee_id)
        return {
            "previous_count": len(result["reviews"]),
            "reviews": result["reviews"],
        }

    @step(depends_on=[fetch_employee, resolve_reviewer], scope="hr.write")
    @retry(max=2, on=[Exception])
    @hard_failure(on_exhausted=abort)
    async def submit_review():
        client = ctx.client("performance")
        review = await client.create_review(
            employee_id=state.resolve_review_subject.employee_id,
            reviewer_id=state.resolve_reviewer.reviewer_id,
            rating=ctx.intent.rating,
            notes=ctx.intent.notes,
        )
        return {"review_id": review["review_id"], "status": review["status"]}

    return projection(
        review_id=state.submit_review.review_id,
        employee_name=state.fetch_employee.name,
        rating=ctx.intent.rating,
        status=state.submit_review.status,
        previous_reviews_count=state.fetch_review_history.previous_count,
    )
