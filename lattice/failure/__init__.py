"""lattice.failure — retry and failure-mode decorators."""

from lattice.failure.policies import abort, hard_failure, soft_failure
from lattice.failure.retry import RetryPolicy, retry

__all__ = [
    "RetryPolicy",
    "abort",
    "hard_failure",
    "retry",
    "soft_failure",
]
