"""HR System API — in-memory FastAPI implementation.

22 REST endpoints covering employees, departments, positions,
onboarding, payroll, performance reviews, leave, and benefits.
All data lives in module-level dicts so the service is fully
self-contained with no database dependency.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="HR System API",
    version="1.0.0",
    description="In-memory HR system used by the Lattice capability demo.",
)

# ── Seed data ─────────────────────────────────────────────────────────────

EMPLOYEES: dict[str, dict] = {
    "E001": {
        "id": "E001",
        "first_name": "Alice",
        "last_name": "Chen",
        "email": "alice.chen@company.com",
        "department_id": "D001",
        "position_id": "P001",
        "status": "active",
        "start_date": "2023-01-15",
        "manager_id": None,
    },
    "E002": {
        "id": "E002",
        "first_name": "Bob",
        "last_name": "Martinez",
        "email": "bob.martinez@company.com",
        "department_id": "D002",
        "position_id": "P003",
        "status": "active",
        "start_date": "2022-06-01",
        "manager_id": "E001",
    },
    "E003": {
        "id": "E003",
        "first_name": "Carol",
        "last_name": "Singh",
        "email": "carol.singh@company.com",
        "department_id": "D001",
        "position_id": "P002",
        "status": "active",
        "start_date": "2023-08-01",
        "manager_id": "E001",
    },
}

DEPARTMENTS: dict[str, dict] = {
    "D001": {
        "id": "D001",
        "name": "Engineering",
        "head_id": "E001",
        "budget": 500000,
        "location": "San Francisco",
    },
    "D002": {
        "id": "D002",
        "name": "Human Resources",
        "head_id": "E002",
        "budget": 200000,
        "location": "New York",
    },
    "D003": {
        "id": "D003",
        "name": "Finance",
        "head_id": None,
        "budget": 300000,
        "location": "Chicago",
    },
}

POSITIONS: dict[str, dict] = {
    "P001": {
        "id": "P001",
        "title": "Senior Engineer",
        "level": "L5",
        "min_salary": 120000,
        "max_salary": 180000,
    },
    "P002": {
        "id": "P002",
        "title": "Junior Engineer",
        "level": "L3",
        "min_salary": 80000,
        "max_salary": 110000,
    },
    "P003": {
        "id": "P003",
        "title": "HR Manager",
        "level": "M2",
        "min_salary": 90000,
        "max_salary": 130000,
    },
    "P004": {
        "id": "P004",
        "title": "Financial Analyst",
        "level": "L2",
        "min_salary": 70000,
        "max_salary": 100000,
    },
}

PAYROLL: dict[str, dict] = {
    "E001": {
        "employee_id": "E001",
        "salary": 150000,
        "currency": "USD",
        "pay_frequency": "biweekly",
        "bank_account": "****1234",
    },
    "E002": {
        "employee_id": "E002",
        "salary": 110000,
        "currency": "USD",
        "pay_frequency": "biweekly",
        "bank_account": "****5678",
    },
    "E003": {
        "employee_id": "E003",
        "salary": 90000,
        "currency": "USD",
        "pay_frequency": "biweekly",
        "bank_account": "****9012",
    },
}

PAYROLL_RUNS: dict[str, dict] = {}
PERFORMANCE_REVIEWS: dict[str, list] = {}
LEAVE_REQUESTS: dict[str, dict] = {}
BENEFITS: dict[str, list] = {}
ONBOARDING: dict[str, dict] = {}

_counters: dict[str, int] = {
    "employee": 100,
    "run": 1000,
    "review": 1,
    "leave": 1,
    "benefit": 1,
    "onboarding": 1,
}


def _next_id(prefix: str, key: str) -> str:
    _counters[key] += 1
    return f"{prefix}{_counters[key]}"


# ── Request / response models ──────────────────────────────────────────────

class CreateEmployeeRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    department_id: str
    position_id: str
    manager_id: Optional[str] = None


class UpdateEmployeeRequest(BaseModel):
    department_id: Optional[str] = None
    position_id: Optional[str] = None
    status: Optional[str] = None
    manager_id: Optional[str] = None


class UpdatePayrollRequest(BaseModel):
    salary: float
    currency: str = "USD"
    pay_frequency: str = "biweekly"
    bank_account: Optional[str] = None


class PayrollRunRequest(BaseModel):
    department_id: str
    pay_period: str


class CreateReviewRequest(BaseModel):
    employee_id: str
    reviewer_id: str
    rating: int
    notes: str


class LeaveRequestBody(BaseModel):
    employee_id: str
    leave_type: str
    start_date: str
    end_date: str
    reason: str


class LeaveDecision(BaseModel):
    decision: str
    decided_by: str
    notes: Optional[str] = None


class BenefitEnrollment(BaseModel):
    employee_id: str
    plan_ids: list[str]


class OnboardingRequest(BaseModel):
    employee_id: str


# ── Endpoints ──────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


# ── Employees (5) ──────────────────────────────────────────────────────────

@app.get("/employees")
def list_employees(department_id: Optional[str] = None, status: Optional[str] = None):
    result = list(EMPLOYEES.values())
    if department_id:
        result = [e for e in result if e["department_id"] == department_id]
    if status:
        result = [e for e in result if e["status"] == status]
    return {"employees": result, "count": len(result)}


@app.get("/employees/{employee_id}")
def get_employee(employee_id: str):
    if employee_id not in EMPLOYEES:
        raise HTTPException(404, f"Employee {employee_id} not found")
    return EMPLOYEES[employee_id]


@app.post("/employees", status_code=201)
def create_employee(body: CreateEmployeeRequest):
    if body.department_id not in DEPARTMENTS:
        raise HTTPException(400, f"Department {body.department_id} not found")
    if body.position_id not in POSITIONS:
        raise HTTPException(400, f"Position {body.position_id} not found")
    emp_id = _next_id("E", "employee")
    emp = {
        "id": emp_id,
        "first_name": body.first_name,
        "last_name": body.last_name,
        "email": body.email,
        "department_id": body.department_id,
        "position_id": body.position_id,
        "status": "pending_onboarding",
        "start_date": date.today().isoformat(),
        "manager_id": body.manager_id,
    }
    EMPLOYEES[emp_id] = emp
    return emp


@app.put("/employees/{employee_id}")
def update_employee(employee_id: str, body: UpdateEmployeeRequest):
    if employee_id not in EMPLOYEES:
        raise HTTPException(404, f"Employee {employee_id} not found")
    emp = EMPLOYEES[employee_id]
    if body.department_id is not None:
        emp["department_id"] = body.department_id
    if body.position_id is not None:
        emp["position_id"] = body.position_id
    if body.status is not None:
        emp["status"] = body.status
    if body.manager_id is not None:
        emp["manager_id"] = body.manager_id
    return emp


@app.get("/employees/{employee_id}/profile")
def get_employee_profile(employee_id: str):
    if employee_id not in EMPLOYEES:
        raise HTTPException(404, f"Employee {employee_id} not found")
    emp = dict(EMPLOYEES[employee_id])
    emp["department"] = DEPARTMENTS.get(emp["department_id"], {})
    emp["position"] = POSITIONS.get(emp["position_id"], {})
    emp["payroll"] = PAYROLL.get(employee_id, {})
    emp["benefits"] = BENEFITS.get(employee_id, [])
    return emp


# ── Departments (3) ────────────────────────────────────────────────────────

@app.get("/departments")
def list_departments():
    return {"departments": list(DEPARTMENTS.values())}


@app.get("/departments/{dept_id}")
def get_department(dept_id: str):
    if dept_id not in DEPARTMENTS:
        raise HTTPException(404, f"Department {dept_id} not found")
    return DEPARTMENTS[dept_id]


@app.get("/departments/{dept_id}/headcount")
def get_headcount(dept_id: str):
    if dept_id not in DEPARTMENTS:
        raise HTTPException(404, f"Department {dept_id} not found")
    employees = [
        e for e in EMPLOYEES.values()
        if e["department_id"] == dept_id and e["status"] == "active"
    ]
    return {
        "department_id": dept_id,
        "headcount": len(employees),
        "employee_ids": [e["id"] for e in employees],
    }


# ── Positions (2) ──────────────────────────────────────────────────────────

@app.get("/positions")
def list_positions():
    return {"positions": list(POSITIONS.values())}


@app.get("/positions/{position_id}")
def get_position(position_id: str):
    if position_id not in POSITIONS:
        raise HTTPException(404, f"Position {position_id} not found")
    return POSITIONS[position_id]


# ── Onboarding (2) ─────────────────────────────────────────────────────────

@app.post("/onboarding", status_code=201)
def start_onboarding(body: OnboardingRequest):
    if body.employee_id not in EMPLOYEES:
        raise HTTPException(404, f"Employee {body.employee_id} not found")
    ob_id = _next_id("OB", "onboarding")
    record = {
        "id": ob_id,
        "employee_id": body.employee_id,
        "status": "in_progress",
        "tasks": [
            {"task": "IT equipment setup", "status": "pending"},
            {"task": "Access provisioning", "status": "pending"},
            {"task": "Benefits enrollment", "status": "completed"},
            {"task": "Policy acknowledgment", "status": "pending"},
            {"task": "Team introduction", "status": "pending"},
        ],
        "started_at": datetime.utcnow().isoformat(),
    }
    ONBOARDING[body.employee_id] = record
    return record


@app.get("/onboarding/{employee_id}/status")
def get_onboarding_status(employee_id: str):
    if employee_id not in ONBOARDING:
        raise HTTPException(404, f"No onboarding record for {employee_id}")
    return ONBOARDING[employee_id]


# ── Payroll (4) ────────────────────────────────────────────────────────────

@app.get("/payroll/{employee_id}")
def get_payroll(employee_id: str):
    if employee_id not in EMPLOYEES:
        raise HTTPException(404, f"Employee {employee_id} not found")
    return PAYROLL.get(
        employee_id,
        {"employee_id": employee_id, "salary": 0, "currency": "USD"},
    )


@app.put("/payroll/{employee_id}")
def update_payroll(employee_id: str, body: UpdatePayrollRequest):
    if employee_id not in EMPLOYEES:
        raise HTTPException(404, f"Employee {employee_id} not found")
    record = {
        "employee_id": employee_id,
        "salary": body.salary,
        "currency": body.currency,
        "pay_frequency": body.pay_frequency,
        "bank_account": body.bank_account or "****0000",
    }
    PAYROLL[employee_id] = record
    return record


@app.post("/payroll/runs", status_code=201)
def run_payroll(body: PayrollRunRequest):
    if body.department_id not in DEPARTMENTS:
        raise HTTPException(400, f"Department {body.department_id} not found")
    active = [
        e for e in EMPLOYEES.values()
        if e["department_id"] == body.department_id and e["status"] == "active"
    ]
    total = sum(
        PAYROLL.get(e["id"], {}).get("salary", 0) / 26
        for e in active
    )
    run_id = _next_id("PR", "run")
    run = {
        "run_id": run_id,
        "department_id": body.department_id,
        "pay_period": body.pay_period,
        "employee_count": len(active),
        "total_amount": round(total, 2),
        "currency": "USD",
        "status": "completed",
        "processed_at": datetime.utcnow().isoformat(),
        "breakdown": [
            {
                "employee_id": e["id"],
                "name": f"{e['first_name']} {e['last_name']}",
                "amount": round(PAYROLL.get(e["id"], {}).get("salary", 0) / 26, 2),
            }
            for e in active
        ],
    }
    PAYROLL_RUNS[run_id] = run
    return run


@app.get("/payroll/runs/{run_id}")
def get_payroll_run(run_id: str):
    if run_id not in PAYROLL_RUNS:
        raise HTTPException(404, f"Payroll run {run_id} not found")
    return PAYROLL_RUNS[run_id]


# ── Performance reviews (2) ────────────────────────────────────────────────

@app.post("/performance/reviews", status_code=201)
def create_review(body: CreateReviewRequest):
    if body.employee_id not in EMPLOYEES:
        raise HTTPException(404, f"Employee {body.employee_id} not found")
    if not 1 <= body.rating <= 5:
        raise HTTPException(400, "Rating must be between 1 and 5")
    review_id = _next_id("RV", "review")
    review = {
        "review_id": review_id,
        "employee_id": body.employee_id,
        "reviewer_id": body.reviewer_id,
        "rating": body.rating,
        "notes": body.notes,
        "status": "submitted",
        "created_at": datetime.utcnow().isoformat(),
    }
    PERFORMANCE_REVIEWS.setdefault(body.employee_id, []).append(review)
    return review


@app.get("/performance/reviews/{employee_id}")
def get_reviews(employee_id: str):
    if employee_id not in EMPLOYEES:
        raise HTTPException(404, f"Employee {employee_id} not found")
    return {
        "employee_id": employee_id,
        "reviews": PERFORMANCE_REVIEWS.get(employee_id, []),
    }


# ── Leave requests (2) ─────────────────────────────────────────────────────

@app.post("/leave/requests", status_code=201)
def create_leave_request(body: LeaveRequestBody):
    if body.employee_id not in EMPLOYEES:
        raise HTTPException(404, f"Employee {body.employee_id} not found")
    req_id = _next_id("LV", "leave")
    req = {
        "request_id": req_id,
        "employee_id": body.employee_id,
        "leave_type": body.leave_type,
        "start_date": body.start_date,
        "end_date": body.end_date,
        "reason": body.reason,
        "status": "pending",
        "submitted_at": datetime.utcnow().isoformat(),
    }
    LEAVE_REQUESTS[req_id] = req
    return req


@app.put("/leave/requests/{request_id}/decision")
def decide_leave(request_id: str, body: LeaveDecision):
    if request_id not in LEAVE_REQUESTS:
        raise HTTPException(404, f"Leave request {request_id} not found")
    req = LEAVE_REQUESTS[request_id]
    req["status"] = body.decision
    req["decided_by"] = body.decided_by
    req["decision_notes"] = body.notes
    req["decided_at"] = datetime.utcnow().isoformat()
    return req


# ── Benefits (2) ───────────────────────────────────────────────────────────

_PLAN_NAMES = {
    "HEALTH_BASIC": "Basic Health",
    "HEALTH_PREMIUM": "Premium Health",
    "DENTAL": "Dental Coverage",
    "VISION": "Vision Coverage",
    "401K": "401(k) Retirement Plan",
    "LIFE": "Life Insurance",
}


@app.post("/benefits/enroll", status_code=201)
def enroll_benefits(body: BenefitEnrollment):
    if body.employee_id not in EMPLOYEES:
        raise HTTPException(404, f"Employee {body.employee_id} not found")
    enrollments = [
        {
            "id": _next_id("BE", "benefit"),
            "employee_id": body.employee_id,
            "plan_id": plan_id,
            "plan_name": _PLAN_NAMES.get(plan_id, plan_id),
            "status": "active",
            "enrolled_at": datetime.utcnow().isoformat(),
        }
        for plan_id in body.plan_ids
    ]
    BENEFITS.setdefault(body.employee_id, []).extend(enrollments)
    return {"employee_id": body.employee_id, "enrollments": enrollments}


@app.get("/benefits/{employee_id}")
def get_benefits(employee_id: str):
    if employee_id not in EMPLOYEES:
        raise HTTPException(404, f"Employee {employee_id} not found")
    return {"employee_id": employee_id, "benefits": BENEFITS.get(employee_id, [])}
