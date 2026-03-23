"""Capability: PayrollProcessing

Runs the payroll cycle for an entire department:
  1. Validates the department exists and is active
  2. Fetches the active employee roster
  3. Triggers a payroll run for the pay period
  4. Retrieves and returns the finalised run summary

API endpoints exercised:
  GET  /departments/{id}
  GET  /departments/{id}/headcount
  GET  /employees?department_id=X&status=active
  POST /payroll/runs
  GET  /payroll/runs/{run_id}
"""

from lattice import capability, projection, state, step
from lattice.failure import abort, hard_failure, retry

from hr_lattice.resolution import resolve_department


@capability(
    name="PayrollProcessing",
    version="1.0",
    inputs={
        "department": str,
        "pay_period": str,
    },
    projection={
        "run_id": {
            "type": str,
            "example": "PR1001",
            "description": "Unique payroll run identifier",
        },
        "department": {
            "type": str,
            "example": "Engineering",
            "description": "Department name the run was executed for",
        },
        "employee_count": {
            "type": int,
            "example": 3,
            "description": "Number of employees included in the run",
        },
        "total_amount": {
            "type": float,
            "example": 13461.54,
            "description": "Total gross payroll amount disbursed (USD)",
        },
        "status": {
            "type": str,
            "example": "completed",
            "description": "Final status of the payroll run",
        },
        "pay_period": {
            "type": str,
            "example": "2026-03",
            "description": "The pay period this run covers",
        },
    },
)
async def payroll_processing(ctx):

    @step(depends_on=[], scope="hr.read")
    @retry(max=2, on=[Exception])
    @hard_failure(on_exhausted=abort)
    async def validate_department():
        client = ctx.client("departments")
        dept = await resolve_department(client, ctx.intent.department)
        return {
            "department_id": dept["id"],
            "department_name": dept["name"],
            "budget": dept["budget"],
        }

    @step(depends_on=[validate_department], scope="hr.read")
    @retry(max=2, on=[Exception])
    async def fetch_active_roster():
        client = ctx.client("employees")
        result = await client.list(
            department_id=state.validate_department.department_id,
            status="active",
        )
        return {
            "employee_ids": [e["id"] for e in result["employees"]],
            "headcount": result["count"],
        }

    @step(depends_on=[fetch_active_roster], scope="payroll.write")
    @retry(max=2, on=[Exception])
    @hard_failure(on_exhausted=abort)
    async def run_payroll():
        client = ctx.client("payroll")
        run = await client.run(
            department_id=state.validate_department.department_id,
            pay_period=ctx.intent.pay_period,
        )
        return {
            "run_id": run["run_id"],
            "total_amount": run["total_amount"],
            "employee_count": run["employee_count"],
            "status": run["status"],
        }

    return projection(
        run_id=state.run_payroll.run_id,
        department=state.validate_department.department_name,
        employee_count=state.run_payroll.employee_count,
        total_amount=state.run_payroll.total_amount,
        status=state.run_payroll.status,
        pay_period=ctx.intent.pay_period,
    )
