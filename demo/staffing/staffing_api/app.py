"""Staffing Platform API — in-memory FastAPI implementation.

20 REST endpoints covering projects, employees, availability,
assignments, notifications, and resource plans.  All data lives
in module-level dicts so the service is fully self-contained
with no database dependency.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="Staffing Platform API",
    version="1.0.0",
    description="In-memory staffing platform used by the Lattice capability demo.",
)

# ── Seed data ──────────────────────────────────────────────────────────────

PROJECTS: dict[str, dict] = {
    "PROJ-4501": {
        "id": "PROJ-4501",
        "name": "Phoenix",
        "department": "Engineering",
        "status": "active",
        "tech_stack": ["Python", "PostgreSQL", "Kubernetes", "Redis"],
        "team_size": 6,
        "start_date": "2026-01-15",
        "end_date": "2026-09-30",
    },
    "PROJ-4502": {
        "id": "PROJ-4502",
        "name": "Atlas",
        "department": "Data Science",
        "status": "active",
        "tech_stack": ["Python", "PyTorch", "Spark", "Airflow"],
        "team_size": 4,
        "start_date": "2026-02-01",
        "end_date": "2026-08-31",
    },
    "PROJ-4503": {
        "id": "PROJ-4503",
        "name": "Horizon",
        "department": "Engineering",
        "status": "planning",
        "tech_stack": ["React", "TypeScript", "GraphQL", "Node.js"],
        "team_size": 5,
        "start_date": "2026-04-01",
        "end_date": "2026-12-31",
    },
}

STAFFING_GAPS: dict[str, list[dict]] = {
    "PROJ-4501": [
        {
            "role": "Senior Backend Engineer",
            "required_skills": ["Python", "PostgreSQL", "Kubernetes"],
            "priority": "high",
            "open_since": "2026-02-15",
        },
        {
            "role": "DevOps Engineer",
            "required_skills": ["Kubernetes", "Terraform", "AWS"],
            "priority": "medium",
            "open_since": "2026-03-01",
        },
    ],
    "PROJ-4502": [
        {
            "role": "ML Engineer",
            "required_skills": ["Python", "PyTorch", "Spark"],
            "priority": "critical",
            "open_since": "2026-02-10",
        },
    ],
    "PROJ-4503": [
        {
            "role": "Senior Frontend Engineer",
            "required_skills": ["React", "TypeScript", "GraphQL"],
            "priority": "high",
            "open_since": "2026-03-15",
        },
    ],
}

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

# Existing assignments that affect availability.
AVAILABILITY: dict[str, dict] = {
    "EMP-1024": {
        "employee_id": "EMP-1024",
        "allocation_pct": 20,
        "current_projects": ["PROJ-4502"],
        "available_from": "2026-03-01",
    },
    "EMP-2187": {
        "employee_id": "EMP-2187",
        "allocation_pct": 0,
        "current_projects": [],
        "available_from": "2026-03-01",
    },
    "EMP-3042": {
        "employee_id": "EMP-3042",
        "allocation_pct": 40,
        "current_projects": ["PROJ-4502"],
        "available_from": "2026-04-15",
    },
    "EMP-4511": {
        "employee_id": "EMP-4511",
        "allocation_pct": 0,
        "current_projects": [],
        "available_from": "2026-03-01",
    },
    "EMP-5290": {
        "employee_id": "EMP-5290",
        "allocation_pct": 80,
        "current_projects": ["PROJ-4502"],
        "available_from": "2026-06-01",
    },
    "EMP-6100": {
        "employee_id": "EMP-6100",
        "allocation_pct": 50,
        "current_projects": ["PROJ-4501"],
        "available_from": "2026-03-01",
    },
}

SCHEDULES: dict[str, list[dict]] = {
    "EMP-1024": [
        {
            "type": "project",
            "description": "Atlas — data pipeline support",
            "start_date": "2026-01-15",
            "end_date": "2026-05-30",
            "allocation_pct": 20,
        },
    ],
    "EMP-2187": [],
    "EMP-3042": [
        {
            "type": "project",
            "description": "Atlas — frontend dashboard",
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
            "description": "Atlas — model training",
            "start_date": "2026-02-01",
            "end_date": "2026-08-31",
            "allocation_pct": 80,
        },
    ],
    "EMP-6100": [
        {
            "type": "project",
            "description": "Phoenix — infrastructure",
            "start_date": "2026-01-15",
            "end_date": "2026-06-30",
            "allocation_pct": 50,
        },
    ],
}

ASSIGNMENTS: dict[str, dict] = {}
NOTIFICATIONS: dict[str, dict] = {}
RESOURCE_PLANS: dict[str, list[dict]] = {
    "PROJ-4501": [
        {
            "employee_id": "EMP-6100",
            "employee_name": "Raj Patel",
            "role": "DevOps Engineer",
            "allocation_pct": 50,
            "start_date": "2026-01-15",
        },
    ],
    "PROJ-4502": [
        {
            "employee_id": "EMP-1024",
            "employee_name": "Alice Chen",
            "role": "Backend Support",
            "allocation_pct": 20,
            "start_date": "2026-01-15",
        },
        {
            "employee_id": "EMP-3042",
            "employee_name": "Priya Sharma",
            "role": "Frontend Developer",
            "allocation_pct": 40,
            "start_date": "2026-02-01",
        },
        {
            "employee_id": "EMP-5290",
            "employee_name": "Dana Kim",
            "role": "ML Engineer",
            "allocation_pct": 80,
            "start_date": "2026-02-01",
        },
    ],
    "PROJ-4503": [],
}

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


class ProjectSearchRequest(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    status: Optional[str] = None


class EmployeeSearchRequest(BaseModel):
    skills: Optional[List[str]] = None
    department: Optional[str] = None
    seniority: Optional[str] = None
    role: Optional[str] = None


class BatchAvailabilityRequest(BaseModel):
    employee_ids: list[str]


class AssignmentValidateRequest(BaseModel):
    employee_id: str
    project_id: str
    allocation_pct: int
    start_date: str
    role: Optional[str] = None


class AssignmentCreateRequest(BaseModel):
    employee_id: str
    project_id: str
    allocation_pct: int
    start_date: str
    role: str
    requested_by: str


class AssignmentUpdateRequest(BaseModel):
    allocation_pct: Optional[int] = None
    start_date: Optional[str] = None
    status: Optional[str] = None


class NotificationSendRequest(BaseModel):
    recipients: list[str]
    message_type: str
    details: dict


class ResourcePlanUpdateRequest(BaseModel):
    employee_id: str
    employee_name: Optional[str] = None
    role: str
    allocation_pct: int
    start_date: str


# ── Endpoints ──────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return {"status": "ok"}


# ── Projects (4) ───────────────────────────────────────────────────────────


@app.get("/projects")
def list_projects(department: Optional[str] = None, status: Optional[str] = None):
    result = list(PROJECTS.values())
    if department:
        result = [p for p in result if _normalize(p["department"]) == _normalize(department)]
    if status:
        result = [p for p in result if p["status"] == status]
    return {"projects": result, "total": len(result)}


@app.get("/projects/{project_id}")
def get_project(project_id: str):
    if project_id not in PROJECTS:
        raise HTTPException(404, f"Project {project_id} not found")
    return PROJECTS[project_id]


@app.post("/projects/search")
def search_projects(body: ProjectSearchRequest):
    result = list(PROJECTS.values())
    if body.name:
        wanted = _normalize(body.name)
        result = [
            p for p in result
            if wanted in _normalize(p["name"])
            or _normalize(p["name"]) in wanted
            or wanted in _normalize(p["id"])
        ]
    if body.department:
        wanted = _normalize(body.department)
        result = [p for p in result if _normalize(p["department"]) == wanted]
    if body.status:
        result = [p for p in result if p["status"] == body.status]
    return {"projects": result, "total": len(result)}


@app.get("/projects/{project_id}/staffing-gaps")
def get_staffing_gaps(project_id: str):
    if project_id not in PROJECTS:
        raise HTTPException(404, f"Project {project_id} not found")
    return {"project_id": project_id, "gaps": STAFFING_GAPS.get(project_id, [])}


# ── Employees (4) ──────────────────────────────────────────────────────────


@app.get("/employees")
def list_employees(department: Optional[str] = None, status: Optional[str] = None):
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
            "current_projects": [],
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
                    "current_projects": [],
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
    avail = AVAILABILITY.get(body.employee_id)
    if avail:
        total = avail["allocation_pct"] + body.allocation_pct
        if total > 100:
            conflicts.append(
                f"Over-allocation: current {avail['allocation_pct']}% + "
                f"requested {body.allocation_pct}% = {total}%"
            )
        elif total > 80:
            warnings.append(
                f"High allocation: total would be {total}%"
            )
    if body.project_id not in PROJECTS:
        conflicts.append(f"Project {body.project_id} not found")
    if body.employee_id not in EMPLOYEES:
        conflicts.append(f"Employee {body.employee_id} not found")
    return {"valid": len(conflicts) == 0, "conflicts": conflicts, "warnings": warnings}


@app.post("/assignments", status_code=201)
def create_assignment(body: AssignmentCreateRequest):
    if body.employee_id not in EMPLOYEES:
        raise HTTPException(404, f"Employee {body.employee_id} not found")
    if body.project_id not in PROJECTS:
        raise HTTPException(404, f"Project {body.project_id} not found")
    emp = EMPLOYEES[body.employee_id]
    asgn_id = _next_id("ASGN-", "assignment")
    assignment = {
        "assignment_id": asgn_id,
        "employee_id": body.employee_id,
        "employee_name": f"{emp['first_name']} {emp['last_name']}",
        "project_id": body.project_id,
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
        if body.project_id not in avail["current_projects"]:
            avail["current_projects"].append(body.project_id)
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


# ── Resource Plans (2) ─────────────────────────────────────────────────────


@app.get("/projects/{project_id}/resource-plan")
def get_resource_plan(project_id: str):
    if project_id not in PROJECTS:
        raise HTTPException(404, f"Project {project_id} not found")
    return {
        "project_id": project_id,
        "resources": RESOURCE_PLANS.get(project_id, []),
    }


@app.put("/projects/{project_id}/resource-plan")
def update_resource_plan(project_id: str, body: ResourcePlanUpdateRequest):
    if project_id not in PROJECTS:
        raise HTTPException(404, f"Project {project_id} not found")
    entry = {
        "employee_id": body.employee_id,
        "employee_name": body.employee_name or body.employee_id,
        "role": body.role,
        "allocation_pct": body.allocation_pct,
        "start_date": body.start_date,
    }
    RESOURCE_PLANS.setdefault(project_id, []).append(entry)
    return {
        "project_id": project_id,
        "resources": RESOURCE_PLANS[project_id],
    }
