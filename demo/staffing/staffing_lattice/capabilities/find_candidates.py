from lattice import capability, projection, state, step
from lattice.failure import retry, soft_failure


@capability(
    name="FindCandidates",
    version="1.0",
    inputs={
        "role": str,
        "required_skills": list,
        "department": str,
        "start_date": str,
        "duration_weeks": int,
    },
    projection={
        "candidates": {
            "type": list,
            "example": [
                {"candidate_id": "EMP-1024", "name": "Alice Chen",
                 "role_fit_score": 92, "availability_pct": 80},
            ],
            "description": (
                "Ranked list of candidates with fit scores, "
                "availability, rates, and conflict flags"
            ),
        },
        "total_found": {"type": int, "example": 4,
                        "description": "Total candidates matching base criteria"},
        "recommendation": {
            "type": dict,
            "example": {"candidate_id": "EMP-1024", "rationale": "Highest fit score, no conflicts"},
            "description": "Top recommendation with reasoning",
        },
        "decision_required": {
            "type": bool,
            "example": True,
            "description": "Whether a human decision is needed before proceeding to assignment",
        },
    },
)
async def find_candidates(ctx):

    @step(depends_on=[], scope="hr.read")
    @retry(max=3, backoff="exponential", on=[TimeoutError])
    @soft_failure(fallback={"employees": [], "skill_profiles": {}})
    async def search_resource_pool():
        emp_client = ctx.client("employee_api")
        result = await emp_client.search(
            skills=ctx.intent.required_skills,
            department=ctx.intent.department,
        )
        employees = result.get("employees", [])
        skill_profiles = {}
        for emp in employees:
            skills_result = await emp_client.skills(emp["id"])
            skill_profiles[emp["id"]] = skills_result.get("skills", [])
        return {"employees": employees, "skill_profiles": skill_profiles}

    @step(depends_on=[search_resource_pool], scope="hr.read")
    @retry(max=2, on=[TimeoutError])
    @soft_failure(fallback={"availability": {}})
    async def check_availability():
        avail_client = ctx.client("availability_api")
        employee_ids = [e["id"] for e in state.search_resource_pool.employees]
        if not employee_ids:
            return {"availability": {}}
        result = await avail_client.batch_check(employee_ids)
        avail_map = {}
        for rec in result.get("records", []):
            avail_map[rec["employee_id"]] = rec
        return {"availability": avail_map}

    @step(depends_on=[search_resource_pool, check_availability])
    async def score_and_rank():
        required_skills = set(s.casefold() for s in ctx.intent.required_skills)
        employees = state.search_resource_pool.employees
        skill_profiles = state.search_resource_pool.skill_profiles
        avail_map = state.check_availability.availability

        # Role match: keywords from the requested role (ignore short words)
        requested_role_words = {
            w.casefold() for w in ctx.intent.role.split() if len(w) > 2
        }

        scored = []
        for emp in employees:
            emp_skills = skill_profiles.get(emp["id"], [])
            emp_skill_names = {s["name"].casefold() for s in emp_skills}
            matched = required_skills & emp_skill_names
            requirements_met = (
                int(100 * len(matched) / len(required_skills))
                if required_skills else 0
            )

            avg_prof = 0
            if emp_skills:
                matching_profs = [
                    s["proficiency"] for s in emp_skills
                    if s["name"].casefold() in required_skills
                ]
                avg_prof = sum(matching_profs) / len(matching_profs) if matching_profs else 0

            ratings = emp.get("past_project_ratings", [])
            avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0.0

            avail = avail_map.get(emp["id"], {})
            allocation = avail.get("allocation_pct", 0)
            availability_pct = 100 - allocation

            # Role alignment: fraction of requested role keywords in candidate's role
            candidate_role_words = {
                w.casefold() for w in emp.get("current_role", "").split() if len(w) > 2
            }
            role_match = (
                len(requested_role_words & candidate_role_words) / len(requested_role_words)
                if requested_role_words else 0.5
            )

            fit_score = int(
                requirements_met * 0.35
                + avg_prof * 10
                + avg_rating * 5
                + availability_pct * 0.1
                + role_match * 25
            )

            scored.append({
                "candidate_id": emp["id"],
                "name": f"{emp['first_name']} {emp['last_name']}",
                "current_role": emp.get("current_role", ""),
                "role_fit_score": min(fit_score, 100),
                "availability_pct": availability_pct,
                "max_safe_allocation_pct": int(availability_pct),
                "hourly_rate": emp.get("hourly_rate", 0.0),
                "past_project_ratings": ratings,
                "avg_rating": avg_rating,
                "skills_matched": list(matched),
                "project_requirements_met_pct": requirements_met,
                "conflict_flags": [],
            })

        scored.sort(key=lambda c: c["role_fit_score"], reverse=True)
        return {"scored_candidates": scored}

    @step(depends_on=[score_and_rank], scope="hr.read")
    @retry(max=2, on=[TimeoutError])
    @soft_failure(fallback={"candidates_with_conflicts": []})
    async def check_conflicts():
        avail_client = ctx.client("availability_api")
        candidates = list(state.score_and_rank.scored_candidates)
        for candidate in candidates:
            schedule = await avail_client.schedule(candidate["candidate_id"])
            flags = []
            for entry in schedule.get("entries", []):
                if entry.get("type") == "pto":
                    flags.append(f"pto:{entry.get('start_date', '?')}-{entry.get('end_date', '?')}")
                elif entry.get("type") == "project" and entry.get("allocation_pct", 0) > 0:
                    desc = entry.get("description", "other work")
                    flags.append(f"committed:{desc}")
            candidate["conflict_flags"] = flags
        return {"candidates_with_conflicts": candidates}

    candidates = state.check_conflicts.candidates_with_conflicts
    top = candidates[0] if candidates else None
    rationale_parts = []
    if top:
        rationale_parts.append(f"Highest fit score ({top['role_fit_score']})")
        if top["availability_pct"] >= 80:
            rationale_parts.append(f"strong availability ({top['availability_pct']}%)")
        if not top["conflict_flags"]:
            rationale_parts.append("no conflicts")
        if top["avg_rating"] >= 4.5:
            rationale_parts.append(f"top-tier ratings ({top['avg_rating']})")

    return projection(
        candidates=candidates,
        total_found=len(candidates),
        recommendation={
            "candidate_id": top["candidate_id"] if top else None,
            "rationale": ", ".join(rationale_parts) if rationale_parts else "no candidates found",
        },
        decision_required=True,
    )
