# Procurement Demo

This folder contains the Procurement domain examples for Lattice.

## What's Inside

- `capabilities/`
  - `vendor_onboarding.py`
  - `equipment_procurement.py`
- `generated/`
  - generated `VendorOnboarding` example
- `apis/`
  - `procurement-platform.yaml`
- `stubs.py`
  - stub backend clients used by the capabilities
- `visualizations/`
  - HTML capability diagrams for this domain only

## Capabilities

- `VendorOnboarding`
  - inputs: `vendor_name`, `vendor_type`, `region`
- `EquipmentProcurement`
  - inputs: `item`, `quantity`, `budget_department`, `preferred_vendor`, `requested_by`

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

The Procurement visualizations live here:

- `demo/procurement/visualizations/index.html`
- `demo/procurement/visualizations/vendor_onboarding.html`
- `demo/procurement/visualizations/equipment_procurement.html`

To regenerate them from the repository root:

```bash
mkdir -p demo/procurement/visualizations
lattice visualize --module demo.procurement.capabilities.vendor_onboarding --capability VendorOnboarding --html demo/procurement/visualizations/vendor_onboarding.html
lattice visualize --module demo.procurement.capabilities.equipment_procurement --capability EquipmentProcurement --html demo/procurement/visualizations/equipment_procurement.html
```
