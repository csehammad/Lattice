"""Projection builder.

``projection(**kwargs)`` constructs the dict that the engine returns
to the model.  The @capability decorator validates it against the
declared schema after the capability function returns.
"""

from __future__ import annotations

from typing import Any

from lattice.types import ProjectionData


def projection(**kwargs: Any) -> ProjectionData:
    """Build a projection dict from keyword arguments."""
    return dict(kwargs)
