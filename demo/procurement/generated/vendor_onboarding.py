from lattice import capability, projection, state, step
from lattice.failure import abort, hard_failure, retry, soft_failure


@capability(
    name="VendorOnboarding",
    version="1.0",
    inputs={"vendor_name": str, "vendor_type": str, "region": str},
    projection={
        "vendor_id": {
            "type": str,
            "example": "V-10001",
            "description": "Unique vendor identifier from ERP",
        },
        "status": {
            "type": str,
            "example": "active",
            "description": "Current vendor lifecycle status",
        },
        "compliance": {
            "type": str,
            "example": "passed",
            "description": "Overall compliance screening result",
        },
        "risk_score": {
            "type": int,
            "example": 15,
            "description": "Risk score from sanctions screening (0-100)",
        },
        "documents_pending": {
            "type": list,
            "example": ["W-9", "insurance_certificate"],
            "description": "Documents still pending from the vendor",
        },
    },
)
async def vendor_onboarding(ctx):

    @step(depends_on=[], scope="compliance.read")
    @retry(max=3, backoff="exponential", on=[TimeoutError])
    @hard_failure(on_exhausted=abort)
    async def sanctions_check():
        client = ctx.client("compliance_api")
        result = await client.checkSanctions(
            {"entity_name": ctx.intent.vendor_name, "country": ctx.intent.region}
        )
        return {"passed": result.clear, "risk_score": result.score}

    @step(depends_on=[sanctions_check], scope="insurance.read")
    @retry(max=3, backoff="exponential", on=[TimeoutError])
    @soft_failure(fallback={"verified": False, "warning": "unavailable"})
    async def insurance_verification():
        client = ctx.client("insurance_api")
        result = await client.verifyInsurance({"entity_name": ctx.intent.vendor_name})
        return {"verified": result.valid, "expiry": result.expiry_date}

    @step(depends_on=[sanctions_check, insurance_verification], scope="vendor.write")
    @retry(max=2, on=[TimeoutError])
    @hard_failure(on_exhausted=abort)
    async def create_vendor_record():
        client = ctx.client("erp_api")
        vendor = await client.createVendor(
            {
                "name": ctx.intent.vendor_name,
                "type": ctx.intent.vendor_type,
                "region": ctx.intent.region,
                "risk_score": state.sanctions_check.risk_score,
                "insurance_status": state.insurance_verification,
            }
        )
        return {"vendor_id": vendor.id, "payment_terms": vendor.default_terms}

    @step(depends_on=[create_vendor_record], scope="documents.write")
    async def request_onboarding_documents():
        client = ctx.client("documents_api")
        await client.requestDocuments(
            {
                "vendor_id": state.create_vendor_record.vendor_id,
                "documents": ["W-9", "insurance_certificate", "bank_details"],
            }
        )
        return {
            "documents_pending": ["W-9", "insurance_certificate", "bank_details"],
            "portal_link": f"https://vendors.company.com/onboard/{state.create_vendor_record.vendor_id}",
        }

    return projection(
        vendor_id=state.create_vendor_record.vendor_id,
        status="active",
        compliance="passed" if state.sanctions_check.passed else "failed",
        risk_score=state.sanctions_check.risk_score,
        documents_pending=state.request_onboarding_documents.documents_pending,
    )
