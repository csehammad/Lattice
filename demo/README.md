# Lattice Demos

This folder is the entrypoint for all runnable demos in the repository.

Each domain folder is self-contained:
- it has its own `README.md`
- it keeps its own visualizations under `visualizations/`
- it explains how to run that demo without guessing

## What's Here

| Folder | What it contains | Start here |
|---|---|---|
| `demo/procurement/` | Procurement capabilities, stubs, generated example, OpenAPI spec, HTML visualizations | [`demo/procurement/README.md`](demo/procurement/README.md) |
| `demo/travel/` | Travel capability, stubs, HTML visualizations | [`demo/travel/README.md`](demo/travel/README.md) |
| `demo/hr/` | HR API, HR capabilities, Docker demo, HTML visualizations | [`demo/hr/README.md`](demo/hr/README.md) |
| `demo/agent/` | Shared search-then-execute agent infrastructure for the Procurement/Travel demo | [`demo/agent/run_agent.py`](demo/agent/run_agent.py) |

## Suggested Path

### 1. Browse a domain

Open one of:
- [`demo/procurement/README.md`](demo/procurement/README.md)
- [`demo/travel/README.md`](demo/travel/README.md)
- [`demo/hr/README.md`](demo/hr/README.md)

Each one explains:
- what is inside
- how to run it
- where the HTML visualizations live

### 2. Run the real interactive Procurement + Travel demo

```bash
python -m demo.run_demo
```

This is the main typed-input demo entrypoint. You type a real request, the LLM searches the capability registry, executes the right capability, and shows the execution summary.

Try:
- `Onboard Acme Corp as a supplier in the US`
- `Procure 10 monitors for marketing from Acme Industrial Supply`
- `Book a trip from SFO to NYC on April 15, returning April 17, for jane.doe@company.com in engineering`

### 3. Run the shared agent demo

```bash
export OPENAI_API_KEY="sk-..."
python -m demo.agent.run_agent
```

Try:
- `Onboard Acme Corp as a supplier in the US`
- `Procure 10 monitors for marketing from Acme Industrial Supply`
- `Book a trip from SFO to NYC on April 15, returning April 17, for jane.doe@company.com in engineering`

### 4. Run the full Procurement + Travel CLI pipeline

```bash
bash demo/run_demo.sh
```

This regenerates the Procurement and Travel visualizations into:
- `demo/procurement/visualizations/`
- `demo/travel/visualizations/`

It does not launch the live demo automatically. Run `python -m demo.run_demo` yourself afterward.

## Folder Layout

```text
demo/
  README.md
  agent/                 Shared search-then-execute agent layer
  procurement/           Procurement domain demo
  travel/                Travel domain demo
  hr/                    HR domain demo
  stubs.py               Unified stub factory for Procurement + Travel
  run_demo.py            Real interactive Procurement + Travel demo
  run_demo.sh            Combined Procurement + Travel CLI pipeline
```

## Notes

- `demo/agent/` is shared infrastructure, not a separate business domain.
- `demo/hr/` is intentionally self-contained because it includes a real FastAPI service plus Docker orchestration.
- Old shared HTML output is no longer the recommended entrypoint. Use each domain's own `visualizations/` folder instead.
