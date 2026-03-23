"""Capability: EmployeeOnboarding

Hires a new employee end-to-end:
  1. Validates the target department and position exist
  2. Creates the employee record
  3. Sets up payroll (in parallel with benefits)
  4. Enrolls default benefits (in parallel with payroll)
  5. Kicks off the onboarding checklist

API endpoints exercised:
  GET  /departments/{id}
  GET  /positions/{id}
  POST /employees
  PUT  /payroll/{id}
  POST /benefits/enroll
  POST /onboarding
"""

from lattice import capability, projection, state, step
from lattice.failure import abort, hard_failure, retry

from hr_lattice.resolution import resolve_department, resolve_position, split_full_name


@capability(
    name="EmployeeOnboarding",
    version="1.0",
    inputs={
        "full_name": str,
        "email": str,
        "department": str,
        "position_title": str,
        "salary": float,
    },
    projection={
        "employee_id": {
            "type": str,
            "example": "E101",
            "description": "Newly created employee ID",
        },
        "status": {
            "type": str,
            "example": "pending_onboarding",
            "description": "Employee lifecycle status after creation",
        },
        "department": {
            "type": str,
            "example": "Engineering",
            "description": "Name of the assigned department",
        },
        "position": {
            "type": str,
            "example": "Senior Engineer",
            "description": "Job title assigned to the employee",
        },
        "start_date": {
            "type": str,
            "example": "2026-03-23",
            "description": "Employment start date (ISO 8601)",
        },
        "onboarding_id": {
            "type": str,
            "example": "OB101",
            "description": "Onboarding checklist ID for tracking",
        },
    },
)
async def employee_onboarding(ctx):

    @step(depends_on=[], scope="hr.read")
    @retry(max=2, on=[Exception])
    @hard_failure(on_exhausted=abort)
    async def validate_department():
        client = ctx.client("departments")
        dept = await resolve_department(client, ctx.intent.department)
        return {"department_id": dept["id"], "department_name": dept["name"]}

    @step(depends_on=[], scope="hr.read")
    @retry(max=2, on=[Exception])
    @hard_failure(on_exhausted=abort)
    async def validate_position():
        client = ctx.client("positions")
        pos = await resolve_position(client, ctx.intent.position_title)
        return {
            "position_id": pos["id"],
            "title": pos["title"],
            "min_salary": pos["min_salary"],
            "max_salary": pos["max_salary"],
        }

    @step(depends_on=[validate_department, validate_position], scope="hr.write")
    @retry(max=2, on=[Exception])
    @hard_failure(on_exhausted=abort)
    async def create_employee_record():
        client = ctx.client("employees")
        first_name, last_name = split_full_name(ctx.intent.full_name)
        emp = await client.create(
            first_name=first_name,
            last_name=last_name,
            email=ctx.intent.email,
            department_id=state.validate_department.department_id,
            position_id=state.validate_position.position_id,
        )
        return {
            "employee_id": emp["id"],
            "status": emp["status"],
            "start_date": emp["start_date"],
        }

    @step(depends_on=[create_employee_record], scope="payroll.write")
    @retry(max=2, on=[Exception])
    async def setup_payroll():
        client = ctx.client("payroll")
        record = await client.update(
            state.create_employee_record.employee_id,
            salary=ctx.intent.salary,
            currency="USD",
            pay_frequency="biweekly",
        )
        return {"salary": record["salary"], "currency": record["currency"]}

    @step(depends_on=[create_employee_record], scope="benefits.write")
    @retry(max=2, on=[Exception])
    async def enroll_default_benefits():
        client = ctx.client("benefits")
        result = await client.enroll(
            employee_id=state.create_employee_record.employee_id,
            plan_ids=["HEALTH_BASIC", "DENTAL", "401K"],
        )
        return {
            "enrolled_plans": [e["plan_name"] for e in result["enrollments"]],
        }

    @step(
        depends_on=[create_employee_record, setup_payroll, enroll_default_benefits],
        scope="hr.write",
    )
    @retry(max=2, on=[Exception])
    async def start_onboarding_checklist():
        client = ctx.client("onboarding")
        record = await client.start(
            employee_id=state.create_employee_record.employee_id,
        )
        return {"onboarding_id": record["id"], "task_count": len(record["tasks"])}

    return projection(
        employee_id=state.create_employee_record.employee_id,
        status=state.create_employee_record.status,
        department=state.validate_department.department_name,
        position=state.validate_position.title,
        start_date=state.create_employee_record.start_date,
        onboarding_id=state.start_onboarding_checklist.onboarding_id,
    )
