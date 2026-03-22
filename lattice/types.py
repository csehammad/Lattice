"""Shared type aliases used across Lattice."""

from __future__ import annotations

from typing import Any

# A projection field can be declared as a plain type (backwards-compat)
# or a rich dict with type/example/description.
ProjectionFieldSpec = dict[str, Any]  # {"type": type, "example": ..., "description": ...}
ProjectionSchema = dict[str, Any]  # field_name -> type | ProjectionFieldSpec
ProjectionData = dict[str, Any]
InputSchema = dict[str, type]
StepResult = dict[str, Any]
Scope = str


def normalize_projection_schema(raw: ProjectionSchema | None) -> dict[str, ProjectionFieldSpec]:
    """Convert a projection schema into the canonical rich format.

    Accepts both::

        {"vendor_id": str}                            # plain type
        {"vendor_id": {"type": str, "example": "V-12345"}}  # rich dict

    Returns every field as ``{"type": <type>, ...}``.
    """
    if not raw:
        return {}
    out: dict[str, ProjectionFieldSpec] = {}
    for name, spec in raw.items():
        if isinstance(spec, type):
            out[name] = {"type": spec}
        elif isinstance(spec, dict) and "type" in spec:
            out[name] = spec
        else:
            out[name] = {"type": type(spec) if spec is not None else str}
    return out


def projection_field_type(spec: Any) -> type:
    """Extract the Python type from a projection field spec."""
    if isinstance(spec, type):
        return spec
    if isinstance(spec, dict):
        maybe_type = spec.get("type", str)
        if isinstance(maybe_type, type):
            return maybe_type
        return str
    return type(spec)


def projection_field_example(spec: Any) -> Any | None:
    """Extract the example value from a projection field spec, or None."""
    if isinstance(spec, dict):
        return spec.get("example")
    return None


def projection_field_description(spec: Any) -> str | None:
    """Extract the description from a projection field spec, or None."""
    if isinstance(spec, dict):
        return spec.get("description")
    return None
