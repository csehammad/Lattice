"""Tests for lattice.capability."""

from lattice.capability import capability, get_capability_def


def test_capability_decorator():
    @capability(
        name="TestCap",
        version="2.0",
        inputs={"name": str},
        projection={"result": str},
    )
    async def test_cap(ctx):
        pass

    defn = get_capability_def(test_cap)
    assert defn is not None
    assert defn.name == "TestCap"
    assert defn.version == "2.0"
    assert defn.input_schema == {"name": str}
    assert defn.projection_schema == {"result": {"type": str}}


def test_capability_signature():
    @capability(
        name="VendorOnboarding",
        inputs={"vendor_name": str, "region": str},
        projection={"vendor_id": str, "status": str},
    )
    async def cap(ctx):
        pass

    defn = get_capability_def(cap)
    assert defn is not None
    sig = defn.signature
    assert "VendorOnboarding" in sig
    assert "vendor_name" in sig
    assert "vendor_id" in sig
