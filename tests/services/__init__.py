"""Stateful in-memory services for integration testing.

These are real Python classes with actual business logic -- not mocks,
not stubs returning hardcoded data.  Each service maintains state and
performs validation, making integration tests meaningful.
"""

from __future__ import annotations

from tests.services.factory import ServiceCluster, create_service_cluster

__all__ = ["ServiceCluster", "create_service_cluster"]
