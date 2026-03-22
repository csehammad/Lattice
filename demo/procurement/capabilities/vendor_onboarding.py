"""Capability: VendorOnboarding

Composes sanctions screening, insurance verification, vendor creation,
payment-term negotiation, and document collection into a single
outcome-shaped contract.

Endpoints used:
  - checkSanctions      POST /compliance/sanctions/check
  - verifyInsurance     POST /insurance/verify
  - createVendor        POST /vendors
  - setPaymentTerms     PUT  /vendors/{vendorId}/payment-terms
  - requestDocuments    POST /documents/request
"""

from lattice import capability, projection, state, step
from lattice.failure import abort, hard_failure, retry, soft_failure


class ServerError(Exception):
    pass


@capability(
    name="VendorOnboarding",
    version="1.0",
    inputs={"vendor_name": str, "vendor_type": str, "region": str},
    projection={
        "vendor_id": {
            "type": str,
            "example": "V-10001",
            "description": "Unique vendor identifier assigned by the ERP system",
        },
        "status": {
            "type": str,
            "example": "active",
            "description": "Current vendor lifecycle status (active, pending, blocked)",
        },
        "compliance": {
            "type": str,
            "example": "passed",
            "description": "Overall compliance screening result",
        },
        "risk_score": {
            "type": int,
            "example": 15,
            "description": "Numeric risk score from sanctions screening (0-100, lower is better)",
        },
        "documents_pending": {
            "type": list,
            "example": ["W-9", "insurance_certificate", "bank_details"],
            "description": "Documents the vendor still needs to submit before activation",
        },
    },
)
async def vendor_onboarding(ctx):

    @step(depends_on=[], scope="compliance.read")
    @retry(max=3, backoff="exponential", on=[TimeoutError, ServerError])
    @hard_failure(on_exhausted=abort)
    async def sanctions_check():
        client = ctx.client("sanctions_screening_api")
        result = await client.check(
            entity_name=ctx.intent.vendor_name,
            country=ctx.intent.region,
        )
        return {"passed": result.clear, "risk_score": result.score}

    @step(depends_on=[sanctions_check], scope="compliance.read")
    @retry(max=3, backoff="exponential", on=[TimeoutError, ServerError])
    @soft_failure(fallback={"verified": False, "warning": "insurance check unavailable"})
    async def insurance_verification():
        client = ctx.client("insurance_verification_api")
        result = await client.verify(entity_name=ctx.intent.vendor_name)
        return {"verified": result.valid, "expiry": result.expiry_date}

    @step(depends_on=[sanctions_check, insurance_verification], scope="vendor.write")
    @retry(max=2, on=[TimeoutError, ServerError])
    @hard_failure(on_exhausted=abort)
    async def create_vendor_record():
        erp = ctx.client("erp")
        vendor = await erp.create_vendor(
            name=ctx.intent.vendor_name,
            type=ctx.intent.vendor_type,
            region=ctx.intent.region,
            risk_score=state.sanctions_check.risk_score,
            insurance_status=state.insurance_verification,
        )
        return {"vendor_id": vendor.id, "payment_terms": vendor.default_terms}

    @step(depends_on=[create_vendor_record], scope="vendor.write")
    @retry(max=2, on=[TimeoutError, ServerError])
    async def set_payment_terms():
        client = ctx.client("payments_api")
        terms = await client.set_terms(
            vendor_id=state.create_vendor_record.vendor_id,
            terms="net-30",
            currency="USD",
        )
        return {"terms": terms.terms, "currency": terms.currency}

    @step(depends_on=[create_vendor_record])
    async def request_documents():
        client = ctx.client("documents_api")
        result = await client.request(
            vendor_id=state.create_vendor_record.vendor_id,
            document_types=["W-9", "insurance_certificate", "bank_details"],
        )
        return {
            "documents_pending": result.documents_pending,
            "portal_link": result.portal_link,
        }

    return projection(
        vendor_id=state.create_vendor_record.vendor_id,
        status="active",
        compliance="passed" if state.sanctions_check.passed else "failed",
        risk_score=state.sanctions_check.risk_score,
        documents_pending=state.request_documents.documents_pending,
    )
