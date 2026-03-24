# Staffing Demo

This folder contains the Staffing / Resource Allocation domain example for Lattice.

## What's Inside

- `apis/`
  - `staffing-platform.yaml` — OpenAPI 3.0 spec (20 raw endpoints across 6 tags)
- `staffing_api/`
  - `app.py` — FastAPI server implementing all endpoints with in-memory seed data
- `staffing_lattice/`
  - `capabilities/`
    - `find_candidates.py` — FindCandidates capability (5 steps)
    - `assign_resource.py` — AssignResource capability (4 steps)
  - `clients.py` — httpx HTTP clients for the Staffing Platform API
  - `stubs.py` — client_factory wiring clients to `STAFFING_API_URL`
  - `resolution.py` — name-to-ID resolution helpers
- `run_demo.py` — StaffingAgent + interactive runner
- `Dockerfile` / `docker-compose.yml` — Docker setup

## Capabilities

- `FindCandidates`
  - inputs: `project_name`, `role`, `required_skills`, `department`, `start_date`, `duration_weeks`
  - projection: ranked candidate list with fit scores, availability, conflict flags, recommendation, `decision_required=true`
- `AssignResource`
  - inputs: `candidate_id`, `project_id`, `role`, `start_date`, `allocation_pct`, `requested_by`
  - projection: assignment confirmation with notifications sent and follow-up actions

## Two-Phase Agent Flow

This demo is different from Procurement and Travel — it demonstrates a **two-phase flow**:

1. User describes a staffing need
2. Agent calls `FindCandidates` → gets a ranked candidate list back
3. Agent presents the candidates as a comparison table and asks the user to pick
4. User selects a candidate (and may override allocation or start date)
5. Agent calls `AssignResource` with the selected `candidate_id` and `project_id` from the first projection

The model never fabricates internal IDs — `project_id` is resolved by Lattice from `project_name`, and `candidate_id` comes from the projection data.

## How To Run

### Docker (recommended)

```bash
cp api.env.example api.env
# Edit api.env and set OPENAI_API_KEY

cd demo/staffing && docker compose up --build
```

### Local (Staffing API must be running on :8001)

Terminal 1 — start the API:
```bash
cd demo/staffing
uvicorn staffing_api.app:app --port 8001
```

Terminal 2 — start the agent:
```bash
cd demo/staffing
python run_demo.py
```

## Lattice CLI Workflow

The capabilities were generated using the Lattice CLI from the OpenAPI spec:

```bash
# 1. Discover operations
lattice discover --spec demo/staffing/apis/staffing-platform.yaml

# 2. Generate capabilities
lattice generate --capability FindCandidates --spec demo/staffing/apis/staffing-platform.yaml --output demo/staffing/staffing_lattice/capabilities/
lattice generate --capability AssignResource --spec demo/staffing/apis/staffing-platform.yaml --output demo/staffing/staffing_lattice/capabilities/

# 3. Visualize
mkdir -p demo/staffing/visualizations
lattice visualize --module staffing_lattice.capabilities.find_candidates --capability FindCandidates --html demo/staffing/visualizations/find_candidates.html
lattice visualize --module staffing_lattice.capabilities.assign_resource --capability AssignResource --html demo/staffing/visualizations/assign_resource.html
```
