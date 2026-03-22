# Lattice Demo

End-to-end demonstration of the Lattice capability runtime across two domains: **Procurement** and **Travel**.

---

## Case studies

### Procurement

| Capability | Steps | What it does |
|---|---|---|
| VendorOnboarding | 5 | Sanctions check, insurance verification, ERP record creation, payment terms, document collection |
| EquipmentProcurement | 5 | Budget check, vendor lookup, approval, budget allocation, approval tracking |

### Travel

| Capability | Steps | What it does |
|---|---|---|
| TripPlanning | 8 | Flight search, hotel search, loyalty lookup, policy check, approval, budget allocation, flight booking, hotel booking |

---

## Folder structure

```
demo/
  procurement/
    apis/
      procurement-platform.yaml     OpenAPI 3.0 spec — 20 endpoints
    capabilities/
      vendor_onboarding.py          VendorOnboarding capability
      equipment_procurement.py      EquipmentProcurement capability
    generated/
      vendor_onboarding.py          LLM-generated capability
    stubs.py                        Procurement domain stub clients
  travel/
    capabilities/
      trip_planning.py              TripPlanning capability
    stubs.py                        Travel domain stub clients
  agent/
    agent.py                        LatticeAgent (search-then-execute)
    run_agent.py                    Interactive agent CLI
    registry.json                   Auto-generated capability manifest
  stubs.py                          Unified stub factory (all domains)
  run_demo.py                       Python runner (all capabilities)
  run_demo.sh                       Shell script (full CLI pipeline)
```

---

## Quick start

### Runtime execution (no LLM needed)

```bash
python -m demo.run_demo
```

Runs all 3 capabilities through the Lattice engine with stub clients. Shows projections and audit trails.

### Interactive agent (requires OpenAI API key)

```bash
export OPENAI_API_KEY="sk-..."
python -m demo.agent.run_agent
```

The agent uses the **search-then-execute** pattern — two meta-tools instead of N capability tools. Try:

- "Onboard Acme Corp as a supplier in the US"
- "Procure 10 monitors for marketing from vendor V-10001"
- "Book a trip from SFO to NYC on April 15, returning April 17, for jane.doe@company.com in engineering"

### Full CLI pipeline (requires LLM API key)

```bash
bash demo/run_demo.sh
```

Runs discover, match, generate, visualize, validate, register, run, and the Python runner.

---

## Prerequisites

```bash
# From the project root
pip install -e ".[llm]"
```

Set one of the following environment variables for LLM-powered steps:

```bash
export OPENAI_API_KEY="sk-..."
# or
export ANTHROPIC_API_KEY="sk-ant-..."
```

All other commands work without an API key.

---

## Reference capabilities

### VendorOnboarding (Procurement)

```
sanctions_check  ──┐
                   ├── create_vendor_record ──┬── set_payment_terms
insurance_verification ┘                      └── request_documents
```

**Inputs:** `vendor_name`, `vendor_type`, `region`
**Projection:** `vendor_id`, `status`, `compliance`, `risk_score`, `documents_pending`

### EquipmentProcurement (Procurement)

```
check_budget ──┐
               ├── submit_for_approval ──┬── allocate_budget
find_vendor ───┘                         └── track_approval
```

**Inputs:** `item`, `quantity`, `budget_department`, `preferred_vendor_id`, `requested_by`
**Projection:** `order_status`, `total_cost`, `vendor_name`, `approval_status`, `budget_remaining`

### TripPlanning (Travel)

```
search_flights ──┐
                 ├── check_policy ── request_approval ── allocate_budget ──┬── book_flight
search_hotels  ──┘                                                        └── book_hotel
lookup_loyalty (parallel, independent)
```

**Inputs:** `traveler_email`, `origin`, `destination`, `departure_date`, `return_date`, `department`
**Projection:** `status`, `flight_confirmation`, `hotel_confirmation`, `total_cost`, `policy_status`, `budget_remaining`, `loyalty_tier`
