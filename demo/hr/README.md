# HR Demo

This folder contains the self-contained HR demo for Lattice.

Unlike the stubbed Procurement and Travel examples, this demo includes a real in-memory FastAPI service, real HTTP calls, Docker orchestration, and an LLM-driven search-then-execute runner.

## What's Inside

- `hr_api/`
  - FastAPI service with in-memory HR endpoints
- `hr_lattice/`
  - HR capabilities, HTTP clients, and runtime-side resolution helpers
- `run_demo.py`
  - OpenAI function-calling demo runner
- `Dockerfile`
- `docker-compose.yml`
- `requirements.txt`
- `api.env.example`
  - template for local secrets and model selection
- `visualizations/`
  - HTML capability diagrams for this domain only

## Capabilities

- `EmployeeOnboarding`
  - inputs: `full_name`, `email`, `department`, `position_title`, `salary`
- `PayrollProcessing`
  - inputs: `department`, `pay_period`
- `PerformanceReview`
  - inputs: `employee`, `reviewer`, `rating`, `notes`

## Setup

Create a local env file:

```bash
cd demo/hr
cp api.env.example api.env
```

Then set your real `OPENAI_API_KEY` in `api.env`.

## How To Run

### Docker

```bash
cd demo/hr
docker compose up --build
```

This is a live interactive session. Type your request directly into the attached terminal.

### Local

First run the HR API yourself, then run:

```bash
cd demo/hr
python run_demo.py
```

You can also run from the repository root:

```bash
python -m demo.hr.run_demo
```

This is also live interactive input only. There is no scripted fallback.

## HTML Visualizations

The HR visualizations live here:

- `demo/hr/visualizations/index.html`
- `demo/hr/visualizations/employee_onboarding.html`
- `demo/hr/visualizations/payroll_processing.html`
- `demo/hr/visualizations/performance_review.html`

To regenerate them from the repository root:

```bash
mkdir -p demo/hr/visualizations
PYTHONPATH=demo/hr lattice visualize --module hr_lattice.capabilities.employee_onboarding --capability EmployeeOnboarding --html demo/hr/visualizations/employee_onboarding.html
PYTHONPATH=demo/hr lattice visualize --module hr_lattice.capabilities.payroll_processing --capability PayrollProcessing --html demo/hr/visualizations/payroll_processing.html
PYTHONPATH=demo/hr lattice visualize --module hr_lattice.capabilities.performance_review --capability PerformanceReview --html demo/hr/visualizations/performance_review.html
```
