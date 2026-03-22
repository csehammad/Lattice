"""End-to-end test: the VendorOnboarding example from the README.

This test substitutes real API clients with stubs to verify the full
capability lifecycle — step execution, state flow, retry, soft-failure
fallback, scoped auth, audit trail, and projection building.
"""

import pytest

from lattice import capability, projection, state, step
from lattice.auth import CredentialStore
from lattice.failure import abort, hard_failure, retry, soft_failure
from lattice.runtime.engine import Engine


class FakeSanctionsClient:
    async def check(self, entity_name: str, country: str):
        return type("R", (), {"clear": True, "score": 15})()


class FakeInsuranceClient:
    async def verify(self, entity_name: str):
        return type("R", (), {"valid": True, "expiry_date": "2027-01-01"})()


class FakeERPClient:
    async def create_vendor(self, **kwargs):
        return type("V", (), {"id": "V-12345", "default_terms": "net-30"})()


def make_client_factory():
    clients = {
        "sanctions_screening_api": FakeSanctionsClient(),
        "insurance_verification_api": FakeInsuranceClient(),
        "sap": FakeERPClient(),
    }

    def factory(name, credentials):
        return clients[name]

    return factory


class ServerError(Exception):
    pass


@capability(
    name="VendorOnboarding",
    version="1.0",
    inputs={"vendor_name": str, "vendor_type": str, "region": str},
    projection={
        "vendor_id": str,
        "status": str,
        "compliance": str,
        "risk_score": int,
        "documents_pending": list,
    },
)
async def vendor_onboarding(ctx):

    @step(depends_on=[], scope="compliance.read")
    @retry(max=3, backoff="exponential", on=[TimeoutError, ServerError], base_delay=0.01)
    @hard_failure(on_exhausted=abort)
    async def sanctions_check():
        client = ctx.client("sanctions_screening_api")
        result = await client.check(entity_name=ctx.intent.vendor_name, country=ctx.intent.region)
        return {"passed": result.clear, "risk_score": result.score}

    @step(depends_on=[sanctions_check], scope="compliance.read")
    @retry(max=3, backoff="exponential", on=[TimeoutError, ServerError], base_delay=0.01)
    @soft_failure(fallback={"verified": False, "warning": "insurance check unavailable"})
    async def insurance_verification():
        client = ctx.client("insurance_verification_api")
        result = await client.verify(entity_name=ctx.intent.vendor_name)
        return {"verified": result.valid, "expiry": result.expiry_date}

    @step(depends_on=[sanctions_check, insurance_verification], scope="vendor.write")
    @retry(max=2, on=[TimeoutError, ServerError], base_delay=0.01)
    @hard_failure(on_exhausted=abort)
    async def create_vendor_record():
        erp = ctx.client("sap")
        vendor = await erp.create_vendor(
            name=ctx.intent.vendor_name,
            type=ctx.intent.vendor_type,
            region=ctx.intent.region,
            risk_score=state.sanctions_check.risk_score,
            insurance_status=state.insurance_verification,
        )
        return {"vendor_id": vendor.id, "payment_terms": vendor.default_terms}

    @step(depends_on=[create_vendor_record])
    async def generate_onboarding_package():
        return {
            "documents_pending": ["W-9", "insurance_certificate", "bank_details"],
            "portal_link": f"https://vendors.company.com/onboard/{state.create_vendor_record.vendor_id}",
        }

    return projection(
        vendor_id=state.create_vendor_record.vendor_id,
        status="active",
        compliance="passed" if state.sanctions_check.passed else "failed",
        risk_score=state.sanctions_check.risk_score,
        documents_pending=state.generate_onboarding_package.documents_pending,
    )


@pytest.mark.asyncio
async def test_vendor_onboarding_end_to_end():
    engine = Engine()
    creds = CredentialStore(
        granted_scopes={"compliance.read", "vendor.write"},
    )

    result = await engine.execute(
        vendor_onboarding,
        inputs={
            "vendor_name": "Acme Corp",
            "vendor_type": "supplier",
            "region": "US",
        },
        credentials=creds,
        client_factory=make_client_factory(),
        requester="test-harness",
    )

    assert result["vendor_id"] == "V-12345"
    assert result["status"] == "active"
    assert result["compliance"] == "passed"
    assert result["risk_score"] == 15
    assert result["documents_pending"] == ["W-9", "insurance_certificate", "bank_details"]

    audit = engine.audit_trail.records[0]
    assert audit.capability_name == "VendorOnboarding"
    assert audit.requester == "test-harness"
    assert audit.status == "completed"
    assert len(audit.steps) == 4

    step_names = [s.step_name for s in audit.steps]
    assert "sanctions_check" in step_names
    assert "insurance_verification" in step_names
    assert "create_vendor_record" in step_names
    assert "generate_onboarding_package" in step_names

    for s in audit.steps:
        assert s.status == "completed"


@pytest.mark.asyncio
async def test_vendor_onboarding_missing_scope():
    engine = Engine()
    creds = CredentialStore(granted_scopes={"compliance.read"})

    with pytest.raises(Exception, match=r"vendor\.write"):
        await engine.execute(
            vendor_onboarding,
            inputs={
                "vendor_name": "Acme Corp",
                "vendor_type": "supplier",
                "region": "US",
            },
            credentials=creds,
            client_factory=make_client_factory(),
        )


@pytest.mark.asyncio
async def test_vendor_onboarding_insurance_fallback():
    """When insurance verification fails, soft-failure kicks in."""

    class FailingInsurance:
        async def verify(self, entity_name: str):
            raise TimeoutError("insurance service down")

    def factory(name, credentials):
        clients = {
            "sanctions_screening_api": FakeSanctionsClient(),
            "insurance_verification_api": FailingInsurance(),
            "sap": FakeERPClient(),
        }
        return clients[name]

    engine = Engine()
    creds = CredentialStore(
        granted_scopes={"compliance.read", "vendor.write"},
    )

    result = await engine.execute(
        vendor_onboarding,
        inputs={
            "vendor_name": "Acme Corp",
            "vendor_type": "supplier",
            "region": "US",
        },
        credentials=creds,
        client_factory=factory,
        requester="test-harness",
    )

    assert result["vendor_id"] == "V-12345"
    assert result["status"] == "active"
