"""@capability decorator — declares an outcome-shaped contract.

Usage (plain types — backwards compatible)::

    @capability(
        name="VendorOnboarding",
        version="1.0",
        inputs={"vendor_name": str, "vendor_type": str, "region": str},
        projection={"vendor_id": str, "status": str},
    )
    async def vendor_onboarding(ctx): ...

Usage (rich projection with examples and descriptions)::

    @capability(
        name="VendorOnboarding",
        version="1.0",
        inputs={"vendor_name": str, "vendor_type": str, "region": str},
        projection={
            "vendor_id": {"type": str, "example": "V-12345",
                          "description": "Unique vendor identifier"},
            "status":    {"type": str, "example": "active",
                          "description": "Current vendor lifecycle status"},
        },
    )
    async def vendor_onboarding(ctx): ...
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from lattice.step import StepMetadata
from lattice.types import (
    InputSchema,
    ProjectionFieldSpec,
    ProjectionSchema,
    normalize_projection_schema,
    projection_field_example,
    projection_field_type,
)


@dataclass
class CapabilityDefinition:
    """All metadata the runtime needs to execute a capability."""

    name: str
    version: str
    input_schema: InputSchema
    projection_schema: dict[str, ProjectionFieldSpec]
    fn: Callable[..., Any]
    steps: list[StepMetadata] = field(default_factory=list)

    @property
    def signature(self) -> str:
        args = ", ".join(self.input_schema)
        parts = []
        for fname, spec in self.projection_schema.items():
            ftype = projection_field_type(spec).__name__
            fexample = projection_field_example(spec)
            if fexample is not None:
                parts.append(f"{fname}: {ftype} (e.g. {fexample!r})")
            else:
                parts.append(f"{fname}: {ftype}")
        fields = ", ".join(parts)
        return f"{self.name}({args}) -> {{ {fields} }}"


CAPABILITY_META_ATTR = "_lattice_capability"


def capability(
    name: str,
    version: str = "1.0",
    inputs: InputSchema | None = None,
    projection: ProjectionSchema | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that declares an async function as a Lattice capability."""

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        defn = CapabilityDefinition(
            name=name,
            version=version,
            input_schema=inputs or {},
            projection_schema=normalize_projection_schema(projection),
            fn=fn,
        )
        setattr(fn, CAPABILITY_META_ATTR, defn)
        return fn

    return decorator


def get_capability_def(fn: Callable[..., Any]) -> CapabilityDefinition | None:
    return getattr(fn, CAPABILITY_META_ATTR, None)


def collect_steps(fn: Callable[..., Any]) -> list[StepMetadata]:
    """Run the capability function in 'collection mode' to discover
    inner @step definitions.

    This works because the @step decorator is applied when the
    capability body executes (the inner ``async def`` + ``@step``
    assignments happen at definition time inside the outer function).

    We actually inspect the function's code object for nested
    functions decorated with @step that were captured during a
    prior execution.  For the initial implementation, the engine
    calls the capability function once with a real context, and
    the steps are registered as closures in that call frame.
    """
    # Steps are collected by the engine during execution.
    # This function exists for introspection of already-executed capabilities.
    defn = get_capability_def(fn)
    if defn is not None:
        return list(defn.steps)
    return []
