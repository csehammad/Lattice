"""Staffing Platform API — in-memory FastAPI implementation.

REST endpoints covering employees, availability, assignments, and notifications.
All data lives in module-level dicts so the service is fully self-contained
with no database dependency.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="Staffing Platform API",
    version="2.0.0",
    description="In-memory staffing platform used by the Lattice capability demo.",
)

# ── Seed data ──────────────────────────────────────────────────────────────

EMPLOYEES: dict[str, dict] = {
    "EMP-1024": {
        "id": "EMP-1024",
        "first_name": "Alice",
        "last_name": "Chen",
        "email": "alice.chen@company.com",
        "department": "Engineering",
        "current_role": "Senior Backend Engineer",
        "seniority": "senior",
        "hourly_rate": 95.00,
        "status": "active",
        "past_project_ratings": [4.8, 4.6, 4.9],
    },
    "EMP-2187": {
        "id": "EMP-2187",
        "first_name": "Marcus",
        "last_name": "Rivera",
        "email": "marcus.rivera@company.com",
        "department": "Engineering",
        "current_role": "Backend Engineer II",
        "seniority": "mid",
        "hourly_rate": 75.00,
        "status": "active",
        "past_project_ratings": [4.2, 4.5],
    },
    "EMP-3042": {
        "id": "EMP-3042",
        "first_name": "Priya",
        "last_name": "Sharma",
        "email": "priya.sharma@company.com",
        "department": "Engineering",
        "current_role": "Senior Full-Stack Engineer",
        "seniority": "senior",
        "hourly_rate": 90.00,
        "status": "active",
        "past_project_ratings": [4.5, 4.7, 4.6],
    },
    "EMP-4511": {
        "id": "EMP-4511",
        "first_name": "James",
        "last_name": "Park",
        "email": "james.park@company.com",
        "department": "Engineering",
        "current_role": "Junior Backend Engineer",
        "seniority": "junior",
        "hourly_rate": 65.00,
        "status": "active",
        "past_project_ratings": [4.1, 4.0],
    },
    "EMP-5290": {
        "id": "EMP-5290",
        "first_name": "Dana",
        "last_name": "Kim",
        "email": "dana.kim@company.com",
        "department": "Data Science",
        "current_role": "ML Engineer",
        "seniority": "senior",
        "hourly_rate": 105.00,
        "status": "active",
        "past_project_ratings": [4.9, 4.8],
    },
    "EMP-6100": {
        "id": "EMP-6100",
        "first_name": "Raj",
        "last_name": "Patel",
        "email": "raj.patel@company.com",
        "department": "Engineering",
        "current_role": "DevOps Engineer",
        "seniority": "mid",
        "hourly_rate": 85.00,
        "status": "active",
        "past_project_ratings": [4.3, 4.4, 4.2],
    },
}

SKILLS: dict[str, list[dict]] = {
    "EMP-1024": [
        {"name": "Python", "proficiency": 5, "years_experience": 8},
        {"name": "PostgreSQL", "proficiency": 4, "years_experience": 6},
        {"name": "Kubernetes", "proficiency": 4, "years_experience": 3},
        {"name": "Redis", "proficiency": 3, "years_experience": 4},
        {"name": "Go", "proficiency": 2, "years_experience": 1},
    ],
    "EMP-2187": [
        {"name": "Python", "proficiency": 4, "years_experience": 4},
        {"name": "PostgreSQL", "proficiency": 3, "years_experience": 3},
        {"name": "Django", "proficiency": 4, "years_experience": 3},
        {"name": "Redis", "proficiency": 2, "years_experience": 1},
    ],
    "EMP-3042": [
        {"name": "Python", "proficiency": 4, "years_experience": 6},
        {"name": "React", "proficiency": 4, "years_experience": 5},
        {"name": "TypeScript", "proficiency": 4, "years_experience": 4},
        {"name": "AWS", "proficiency": 3, "years_experience": 3},
        {"name": "PostgreSQL", "proficiency": 3, "years_experience": 3},
    ],
    "EMP-4511": [
        {"name": "Python", "proficiency": 3, "years_experience": 2},
        {"name": "Go", "proficiency": 3, "years_experience": 1},
        {"name": "PostgreSQL", "proficiency": 2, "years_experience": 1},
        {"name": "Docker", "proficiency": 2, "years_experience": 1},
    ],
    "EMP-5290": [
        {"name": "Python", "proficiency": 5, "years_experience": 7},
        {"name": "PyTorch", "proficiency": 5, "years_experience": 4},
        {"name": "Spark", "proficiency": 4, "years_experience": 3},
        {"name": "TensorFlow", "proficiency": 4, "years_experience": 3},
        {"name": "Airflow", "proficiency": 3, "years_experience": 2},
    ],
    "EMP-6100": [
        {"name": "Kubernetes", "proficiency": 5, "years_experience": 5},
        {"name": "Terraform", "proficiency": 4, "years_experience": 4},
        {"name": "AWS", "proficiency": 4, "years_experience": 5},
        {"name": "Python", "proficiency": 3, "years_experience": 3},
        {"name": "Docker", "proficiency": 5, "years_experience": 5},
    ],
}

AVAILABILITY: dict[str, dict] = {
    "EMP-1024": {
        "employee_id": "EMP-1024",
        "allocation_pct": 20,
        "available_from": "2026-03-01",
    },
    "EMP-2187": {
        "employee_id": "EMP-2187",
        "allocation_pct": 0,
        "available_from": "2026-03-01",
    },
    "EMP-3042": {
        "employee_id": "EMP-3042",
        "allocation_pct": 40,
        "available_from": "2026-04-15",
    },
    "EMP-4511": {
        "employee_id": "EMP-4511",
        "allocation_pct": 0,
        "available_from": "2026-03-01",
    },
    "EMP-5290": {
        "employee_id": "EMP-5290",
        "allocation_pct": 80,
        "available_from": "2026-06-01",
    },
    "EMP-6100": {
        "employee_id": "EMP-6100",
        "allocation_pct": 50,
        "available_from": "2026-03-01",
    },
}

SCHEDULES: dict[str, list[dict]] = {
    "EMP-1024": [
        {
            "type": "project",
            "description": "data pipeline support",
            "start_date": "2026-01-15",
            "end_date": "2026-05-30",
            "allocation_pct": 20,
        },
    ],
    "EMP-2187": [],
    "EMP-3042": [
        {
            "type": "project",
            "description": "frontend dashboard work",
            "start_date": "2026-02-01",
            "end_date": "2026-04-15",
            "allocation_pct": 40,
        },
        {
            "type": "pto",
            "description": "Vacation",
            "start_date": "2026-05-01",
            "end_date": "2026-05-09",
            "allocation_pct": 100,
        },
    ],
    "EMP-4511": [],
    "EMP-5290": [
        {
            "type": "project",
            "description": "ML model training",
            "start_date": "2026-02-01",
            "end_date": "2026-08-31",
            "allocation_pct": 80,
        },
    ],
    "EMP-6100": [
        {
            "type": "project",
            "description": "infrastructure work",
            "start_date": "2026-01-15",
            "end_date": "2026-06-30",
            "allocation_pct": 50,
        },
    ],
}

ASSIGNMENTS: dict[str, dict] = {}
NOTIFICATIONS: dict[str, dict] = {}

_counters: dict[str, int] = {
    "assignment": 48290,
    "notification": 7000,
}


def _next_id(prefix: str, key: str) -> str:
    _counters[key] += 1
    return f"{prefix}{_counters[key]}"


def _normalize(value: str) -> str:
    return " ".join(value.strip().casefold().split())


# ── Request / response models ──────────────────────────────────────────────


class EmployeeSearchRequest(BaseModel):
    skills: list[str] | None = None
    department: str | None = None
    seniority: str | None = None
    role: str | None = None


class BatchAvailabilityRequest(BaseModel):
    employee_ids: list[str]


class AssignmentValidateRequest(BaseModel):
    employee_id: str
    allocation_pct: int
    start_date: str
    role: str | None = None


class AssignmentCreateRequest(BaseModel):
    employee_id: str
    allocation_pct: int
    start_date: str
    role: str
    requested_by: str


class AssignmentUpdateRequest(BaseModel):
    allocation_pct: int | None = None
    start_date: str | None = None
    status: str | None = None


class NotificationSendRequest(BaseModel):
    recipients: list[str]
    message_type: str
    details: dict


# ── Endpoints ──────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return {"status": "ok"}


# ── Employees (4) ──────────────────────────────────────────────────────────


@app.get("/employees")
def list_employees(department: str | None = None, status: str | None = None):
    result = list(EMPLOYEES.values())
    if department:
        wanted = _normalize(department)
        result = [e for e in result if _normalize(e["department"]) == wanted]
    if status:
        result = [e for e in result if e["status"] == status]
    return {"employees": result, "total": len(result)}


@app.get("/employees/{employee_id}")
def get_employee(employee_id: str):
    if employee_id not in EMPLOYEES:
        raise HTTPException(404, f"Employee {employee_id} not found")
    return EMPLOYEES[employee_id]


@app.post("/employees/search")
def search_employees(body: EmployeeSearchRequest):
    result = list(EMPLOYEES.values())
    if body.department:
        wanted = _normalize(body.department)
        result = [e for e in result if _normalize(e["department"]) == wanted]
    if body.seniority:
        result = [e for e in result if e["seniority"] == body.seniority]
    if body.role:
        wanted = _normalize(body.role)
        result = [e for e in result if wanted in _normalize(e["current_role"])]
    if body.skills:
        wanted_skills = {_normalize(s) for s in body.skills}
        filtered = []
        for emp in result:
            emp_skills = {_normalize(s["name"]) for s in SKILLS.get(emp["id"], [])}
            if wanted_skills & emp_skills:
                filtered.append(emp)
        result = filtered
    return {"employees": result, "total": len(result)}


@app.get("/employees/{employee_id}/skills")
def get_employee_skills(employee_id: str):
    if employee_id not in EMPLOYEES:
        raise HTTPException(404, f"Employee {employee_id} not found")
    return {"employee_id": employee_id, "skills": SKILLS.get(employee_id, [])}


# ── Availability (3) ───────────────────────────────────────────────────────


@app.get("/employees/{employee_id}/availability")
def get_employee_availability(employee_id: str):
    if employee_id not in EMPLOYEES:
        raise HTTPException(404, f"Employee {employee_id} not found")
    return AVAILABILITY.get(
        employee_id,
        {
            "employee_id": employee_id,
            "allocation_pct": 0,
            "available_from": "2026-03-01",
        },
    )


@app.post("/availability/batch-check")
def batch_check_availability(body: BatchAvailabilityRequest):
    records = []
    for eid in body.employee_ids:
        records.append(
            AVAILABILITY.get(
                eid,
                {
                    "employee_id": eid,
                    "allocation_pct": 0,
                    "available_from": "2026-03-01",
                },
            )
        )
    return {"records": records}


@app.get("/employees/{employee_id}/schedule")
def get_employee_schedule(employee_id: str):
    if employee_id not in EMPLOYEES:
        raise HTTPException(404, f"Employee {employee_id} not found")
    return {"employee_id": employee_id, "entries": SCHEDULES.get(employee_id, [])}


# ── Assignments (5) ────────────────────────────────────────────────────────


@app.post("/assignments/validate")
def validate_assignment(body: AssignmentValidateRequest):
    conflicts: list[str] = []
    warnings: list[str] = []
    if body.employee_id not in EMPLOYEES:
        conflicts.append(f"Employee {body.employee_id} not found")
    avail = AVAILABILITY.get(body.employee_id)
    if avail:
        total = avail["allocation_pct"] + body.allocation_pct
        if total > 100:
            conflicts.append(
                f"Over-allocation: current {avail['allocation_pct']}% + "
                f"requested {body.allocation_pct}% = {total}%"
            )
        elif total > 80:
            warnings.append(f"High allocation: total would be {total}%")
    return {"valid": len(conflicts) == 0, "conflicts": conflicts, "warnings": warnings}


@app.post("/assignments", status_code=201)
def create_assignment(body: AssignmentCreateRequest):
    if body.employee_id not in EMPLOYEES:
        raise HTTPException(404, f"Employee {body.employee_id} not found")
    emp = EMPLOYEES[body.employee_id]
    asgn_id = _next_id("ASGN-", "assignment")
    assignment = {
        "assignment_id": asgn_id,
        "employee_id": body.employee_id,
        "employee_name": f"{emp['first_name']} {emp['last_name']}",
        "role": body.role,
        "allocation_pct": body.allocation_pct,
        "start_date": body.start_date,
        "status": "confirmed",
        "created_at": datetime.utcnow().isoformat(),
    }
    ASSIGNMENTS[asgn_id] = assignment
    avail = AVAILABILITY.get(body.employee_id)
    if avail:
        avail["allocation_pct"] += body.allocation_pct
    return assignment


@app.get("/assignments/{assignment_id}")
def get_assignment(assignment_id: str):
    if assignment_id not in ASSIGNMENTS:
        raise HTTPException(404, f"Assignment {assignment_id} not found")
    return ASSIGNMENTS[assignment_id]


@app.put("/assignments/{assignment_id}")
def update_assignment(assignment_id: str, body: AssignmentUpdateRequest):
    if assignment_id not in ASSIGNMENTS:
        raise HTTPException(404, f"Assignment {assignment_id} not found")
    asgn = ASSIGNMENTS[assignment_id]
    if body.allocation_pct is not None:
        asgn["allocation_pct"] = body.allocation_pct
    if body.start_date is not None:
        asgn["start_date"] = body.start_date
    if body.status is not None:
        asgn["status"] = body.status
    return asgn


@app.delete("/assignments/{assignment_id}")
def cancel_assignment(assignment_id: str):
    if assignment_id not in ASSIGNMENTS:
        raise HTTPException(404, f"Assignment {assignment_id} not found")
    asgn = ASSIGNMENTS[assignment_id]
    asgn["status"] = "cancelled"
    return asgn


# ── Notifications (2) ──────────────────────────────────────────────────────


@app.post("/notifications/send", status_code=201)
def send_notification(body: NotificationSendRequest):
    notif_id = _next_id("NOTIF-", "notification")
    notification = {
        "notification_id": notif_id,
        "recipients": body.recipients,
        "message_type": body.message_type,
        "status": "sent",
        "sent_at": datetime.utcnow().isoformat(),
    }
    NOTIFICATIONS[notif_id] = notification
    return notification


@app.get("/notifications/{notification_id}")
def get_notification(notification_id: str):
    if notification_id not in NOTIFICATIONS:
        raise HTTPException(404, f"Notification {notification_id} not found")
    return NOTIFICATIONS[notification_id]
