"""Tests for lazy registry behavior and manifest correctness."""

from __future__ import annotations

from lattice import capability, projection
from lattice.runtime.registry import CapabilityRegistry, LazyRegistry


@capability(
    name="DummyCapability",
    version="1.0",
    inputs={"name": str},
    projection={"greeting": {"type": str, "example": "hello"}},
)
async def dummy_capability(ctx):
    return projection(greeting=f"hello {ctx.intent.name}")


def test_lazy_registry_from_registry_builds_manifest_without_filesystem_io():
    registry = CapabilityRegistry()
    registry.register(dummy_capability)

    lazy = LazyRegistry.from_registry(registry)

    assert "DummyCapability" in lazy.manifest
    entry = lazy.manifest["DummyCapability"]
    assert entry["module_path"] == dummy_capability.__module__
    assert entry["function_name"] == dummy_capability.__name__
    assert entry["inputs"]["name"] == "str"


def test_lazy_registry_from_registry_marks_capabilities_loaded():
    registry = CapabilityRegistry()
    registry.register(dummy_capability)

    lazy = LazyRegistry.from_registry(registry)

    assert lazy.is_loaded("DummyCapability")
    fn = lazy.get_function("DummyCapability")
    assert fn is dummy_capability
