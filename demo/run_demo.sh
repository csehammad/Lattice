#!/usr/bin/env bash
#
# Lattice Demo — Full CLI Pipeline
#
# Prerequisites:
#   1. Install the lattice package:  pip install -e ".[llm]"
#   2. Set your LLM API key:
#        export OPENAI_API_KEY="sk-..."       (for OpenAI)
#        export ANTHROPIC_API_KEY="sk-ant-..."  (for Anthropic)
#
# Usage:
#   cd <project-root>
#   bash demo/run_demo.sh
#
# The script runs from the project root so that Python module paths
# like "demo.procurement.capabilities.vendor_onboarding" resolve correctly.

set -euo pipefail

SPEC="demo/procurement/apis/procurement-platform.yaml"

echo "============================================================"
echo " LATTICE DEMO — End-to-End CLI Pipeline"
echo " Domains: Procurement, Travel"
echo "============================================================"
echo

# ── Step 1: Discover ─────────────────────────────────────────────

echo "──────────────────────────────────────────────────────────────"
echo " Step 1: lattice discover"
echo "   Parse the OpenAPI spec and list all available operations."
echo "──────────────────────────────────────────────────────────────"
echo

lattice discover --spec "$SPEC"

echo
echo

# ── Step 2: Match (LLM) ─────────────────────────────────────────

echo "──────────────────────────────────────────────────────────────"
echo " Step 2: lattice match"
echo "   Send discovered operations to the LLM to propose"
echo "   capabilities that can be composed from them."
echo "──────────────────────────────────────────────────────────────"
echo

lattice match --spec "$SPEC"

echo
echo

# ── Step 3: Generate (LLM) ──────────────────────────────────────

echo "──────────────────────────────────────────────────────────────"
echo " Step 3: lattice generate"
echo "   Ask the LLM to generate a full VendorOnboarding capability"
echo "   from the discovered API operations."
echo "──────────────────────────────────────────────────────────────"
echo

mkdir -p demo/procurement/generated
lattice generate \
  --capability VendorOnboarding \
  --spec "$SPEC" \
  -o demo/procurement/generated/

echo
echo "   Generated file:"
ls -la demo/procurement/generated/vendor_onboarding.py
echo
echo

# ── Step 4: Visualize ───────────────────────────────────────────

echo "──────────────────────────────────────────────────────────────"
echo " Step 4: lattice visualize"
echo "   Show the step tree, inputs, projection, and policies."
echo "──────────────────────────────────────────────────────────────"
echo

echo "--- VendorOnboarding (Procurement) ---"
lattice visualize \
  --module demo.procurement.capabilities.vendor_onboarding \
  --capability VendorOnboarding

echo
echo "--- EquipmentProcurement (Procurement) ---"
lattice visualize \
  --module demo.procurement.capabilities.equipment_procurement \
  --capability EquipmentProcurement

echo
echo "--- TripPlanning (Travel) ---"
lattice visualize \
  --module demo.travel.capabilities.trip_planning \
  --capability TripPlanning

echo
echo

# ── Step 5: Validate ────────────────────────────────────────────

echo "──────────────────────────────────────────────────────────────"
echo " Step 5: lattice validate"
echo "   Validate input and projection schemas."
echo "──────────────────────────────────────────────────────────────"
echo

lattice validate \
  --module demo.procurement.capabilities.vendor_onboarding \
  --capability VendorOnboarding

lattice validate \
  --module demo.procurement.capabilities.equipment_procurement \
  --capability EquipmentProcurement

lattice validate \
  --module demo.travel.capabilities.trip_planning \
  --capability TripPlanning

echo
echo

# ── Step 6: Register ────────────────────────────────────────────

echo "──────────────────────────────────────────────────────────────"
echo " Step 6: lattice register"
echo "   Register capabilities in the local registry."
echo "──────────────────────────────────────────────────────────────"
echo

lattice register \
  --module demo.procurement.capabilities.vendor_onboarding \
  --capability VendorOnboarding

lattice register \
  --module demo.procurement.capabilities.equipment_procurement \
  --capability EquipmentProcurement

lattice register \
  --module demo.travel.capabilities.trip_planning \
  --capability TripPlanning

echo
echo

# ── Step 7: Run (with stubs) ────────────────────────────────────

echo "──────────────────────────────────────────────────────────────"
echo " Step 7: lattice run"
echo "   Execute capabilities through the Lattice runtime with"
echo "   stub API clients."
echo "──────────────────────────────────────────────────────────────"
echo

echo "--- VendorOnboarding ---"
lattice run \
  --module demo.procurement.capabilities.vendor_onboarding \
  --capability VendorOnboarding \
  --intent '{"vendor_name":"Acme Corp","vendor_type":"supplier","region":"US"}' \
  --scopes "compliance.read,vendor.write" \
  --stubs demo.stubs

echo
echo "--- EquipmentProcurement ---"
lattice run \
  --module demo.procurement.capabilities.equipment_procurement \
  --capability EquipmentProcurement \
  --intent '{"item":"Standing Desk","quantity":10,"budget_department":"engineering","preferred_vendor_id":"V-10001","requested_by":"alex@company.com"}' \
  --scopes "budget.read,budget.write,vendor.read,approval.read,approval.write" \
  --stubs demo.stubs

echo
echo "--- TripPlanning ---"
lattice run \
  --module demo.travel.capabilities.trip_planning \
  --capability TripPlanning \
  --intent '{"traveler_email":"jane.doe@company.com","origin":"SFO","destination":"NYC","departure_date":"2026-04-15","return_date":"2026-04-17","department":"engineering"}' \
  --scopes "travel.read,travel.approve,travel.book,budget.write" \
  --stubs demo.stubs

echo
echo

# ── Step 8: Python runner ───────────────────────────────────────

echo "──────────────────────────────────────────────────────────────"
echo " Step 8: Python demo runner"
echo "   Run all capabilities via the Engine API directly,"
echo "   with rich formatted output and full audit trails."
echo "──────────────────────────────────────────────────────────────"
echo

python -m demo.run_demo

echo
echo "============================================================"
echo " DEMO COMPLETE"
echo "============================================================"
