"""Lattice — the capability runtime for outcome-based execution.

Public API::

    from lattice import capability, step, state, projection
    from lattice.log import configure_logging
"""

from lattice.capability import capability
from lattice.log import configure_logging
from lattice.projection import projection
from lattice.state import state
from lattice.step import step

__all__ = ["capability", "configure_logging", "projection", "state", "step"]
__version__ = "0.1.0"
