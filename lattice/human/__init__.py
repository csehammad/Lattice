"""lattice.human — human task and gap decorators."""

from lattice.human.gaps import needs_human_input
from lattice.human.task import human_task

__all__ = ["human_task", "needs_human_input"]
