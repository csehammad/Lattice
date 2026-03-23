# Travel Demo

This folder contains the Travel domain example for Lattice.

## What's Inside

- `capabilities/`
  - `trip_planning.py`
- `stubs.py`
  - stub travel backend clients
- `visualizations/`
  - HTML capability diagrams for this domain only

## Capability

- `TripPlanning`
  - inputs: `traveler_email`, `origin`, `destination`, `departure_date`, `return_date`, `department`

## How To Run

From the repository root:

```bash
python -m demo.run_demo
```

That launches the real interactive Procurement + Travel demo. Type a natural language request and the LLM will use Lattice's search-then-execute flow.

If you want the full CLI pipeline:

```bash
bash demo/run_demo.sh
```

## HTML Visualizations

The Travel visualization lives here:

- `demo/travel/visualizations/index.html`
- `demo/travel/visualizations/trip_planning.html`

To regenerate it from the repository root:

```bash
mkdir -p demo/travel/visualizations
lattice visualize --module demo.travel.capabilities.trip_planning --capability TripPlanning --html demo/travel/visualizations/trip_planning.html
```
