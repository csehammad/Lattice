"""Execution engine — runs a capability to completion.

The engine:
1. Validates inputs against the capability's input schema.
2. Calls the capability function with a step-collector active, which
   collects @step closures as they are defined.
3. Validates that all required scopes are available before any step runs.
4. Executes steps sequentially in dependency order, applying retry /
   soft-failure / hard-failure policies.
5. Populates the state store so later steps (and the projection builder)
   can read earlier step results.
6. Calls the capability function a second time (with state populated)
   to evaluate the projection.
7. Produces a structured audit record.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Callable
from typing import Any, cast

from lattice.audit.trail import AuditRecord, AuditTrail, StepRecord
from lattice.auth.scopes import (
    CredentialStore,
    bind_credentials,
    unbind_credentials,
)
from lattice.capability import CapabilityDefinition, get_capability_def
from lattice.context import ExecutionContext
from lattice.errors import (
    AbortExecution,
    LatticeError,
    StepFailure,
    ValidationError,
)
from lattice.failure.policies import HardFailurePolicy, SoftFailurePolicy, _Abort
from lattice.failure.retry import RetryPolicy
from lattice.intent import Intent
from lattice.log import clear_log_context, get_logger, set_log_context
from lattice.state import StateStore, bind_store, unbind_store
from lattice.step import StepMetadata, _begin_collecting, _end_collecting
from lattice.types import ProjectionData

logger = get_logger(__name__)


def _validate_inputs(defn: CapabilityDefinition, raw: dict[str, Any]) -> None:
    for field_name, field_type in defn.input_schema.items():
        if field_name not in raw:
            logger.error("Missing required input '%s' for %s", field_name, defn.name)
            raise ValidationError(
                f"Missing required input '{field_name}' for capability '{defn.name}'"
            )
        value = raw[field_name]
        if not isinstance(value, field_type):
            logger.error(
                "Input '%s' type mismatch: expected %s, got %s",
                field_name,
                field_type.__name__,
                type(value).__name__,
            )
            raise ValidationError(
                f"Input '{field_name}' must be {field_type.__name__}, got {type(value).__name__}"
            )
    logger.debug("Input validation passed for %s (%d fields)", defn.name, len(defn.input_schema))


def _validate_projection(defn: CapabilityDefinition, proj: ProjectionData) -> None:
    for field_name in defn.projection_schema:
        if field_name not in proj:
            logger.error("Projection missing field '%s' for %s", field_name, defn.name)
            raise ValidationError(
                f"Projection missing field '{field_name}' for capability '{defn.name}'"
            )
    logger.debug("Projection validation passed (%d fields)", len(defn.projection_schema))


def _pre_check_permissions(
    steps: list[StepMetadata],
    credentials: CredentialStore,
) -> None:
    for step_meta in steps:
        if step_meta.scope:
            credentials.check_scope(step_meta.name, step_meta.scope)
        fn = step_meta.fn
        if fn is not None:
            for extra_scope in getattr(fn, "_lattice_required_scopes", []):
                credentials.check_scope(step_meta.name, extra_scope)
            for role in getattr(fn, "_lattice_required_roles", []):
                credentials.check_role(step_meta.name, role)


def _resolve_order(steps: list[StepMetadata]) -> list[StepMetadata]:
    """Return steps in an order that respects depends_on declarations."""
    by_name: dict[str, StepMetadata] = {s.name: s for s in steps}
    in_degree: dict[str, int] = {s.name: 0 for s in steps}
    dependents: dict[str, list[str]] = {s.name: [] for s in steps}

    for s in steps:
        for dep in s.depends_on:
            if dep in by_name:
                in_degree[s.name] += 1
                dependents[dep].append(s.name)

    queue: list[str] = [name for name, deg in in_degree.items() if deg == 0]
    ordered: list[StepMetadata] = []

    while queue:
        name = queue.pop(0)
        ordered.append(by_name[name])
        for dependent in dependents[name]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if len(ordered) != len(steps):
        executed = {s.name for s in ordered}
        stuck = [s.name for s in steps if s.name not in executed]
        raise ValidationError(f"Circular or unresolvable dependencies among steps: {stuck}")

    return ordered


async def _run_step_with_retry(
    step_meta: StepMetadata,
    audit_step: StepRecord,
) -> dict[str, Any]:
    fn = step_meta.fn
    if fn is None:
        raise StepFailure(step_meta.name, RuntimeError("Step has no function"))

    policy: RetryPolicy | None = step_meta.retry_policy
    max_attempts = policy.max_attempts if policy else 1
    last_error: BaseException | None = None

    for attempt in range(max_attempts):
        audit_step.attempts = attempt + 1
        try:
            if asyncio.iscoroutinefunction(fn):
                result = await fn()
            else:
                result = fn()
            if attempt > 0:
                logger.info(
                    "Step '%s' succeeded on attempt %d/%d",
                    step_meta.name,
                    attempt + 1,
                    max_attempts,
                )
            return result if isinstance(result, dict) else {"_value": result}
        except Exception as exc:
            last_error = exc
            if policy and not isinstance(exc, tuple(policy.on)):
                logger.error(
                    "Step '%s' raised non-retryable %s: %s",
                    step_meta.name,
                    type(exc).__name__,
                    exc,
                )
                raise
            if attempt < max_attempts - 1 and policy:
                delay = policy.delay_for(attempt)
                logger.warning(
                    "Step '%s' attempt %d/%d failed (%s: %s), retrying in %.1fs",
                    step_meta.name,
                    attempt + 1,
                    max_attempts,
                    type(exc).__name__,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "Step '%s' exhausted %d attempts, last error: %s: %s",
                    step_meta.name,
                    max_attempts,
                    type(exc).__name__,
                    exc,
                )

    raise last_error  # type: ignore[misc]


async def _execute_step(
    step_meta: StepMetadata,
    store: StateStore,
    audit_step: StepRecord,
) -> None:
    step_token = set_log_context(step=step_meta.name)
    audit_step.mark_running()
    logger.debug("Step '%s' starting (scope=%s)", step_meta.name, step_meta.scope or "none")

    soft: SoftFailurePolicy | None = step_meta.soft_failure_fallback
    hard: HardFailurePolicy | None = step_meta.hard_failure_action

    try:
        result = await _run_step_with_retry(step_meta, audit_step)
        store.set(step_meta.name, result)
        audit_step.mark_completed(result)
        logger.debug(
            "Step '%s' completed (keys=%s)",
            step_meta.name,
            list(result.keys()) if isinstance(result, dict) else "scalar",
        )
    except Exception as exc:
        audit_step.mark_failed(exc)

        if soft is not None:
            fallback = soft.fallback
            if callable(fallback):
                fallback = fallback()
            store.set(
                step_meta.name,
                fallback if isinstance(fallback, dict) else {"_value": fallback},
            )
            audit_step.status = "completed"
            audit_step.error = f"soft-failure fallback applied: {exc}"
            logger.warning(
                "Step '%s' soft-failure fallback applied (%s: %s)",
                step_meta.name,
                type(exc).__name__,
                exc,
            )
            return

        if hard is not None and isinstance(hard.on_exhausted, _Abort):
            logger.error(
                "Step '%s' hard-failure abort (%s: %s)",
                step_meta.name,
                type(exc).__name__,
                exc,
            )
            raise AbortExecution(step_meta.name, exc) from exc

        logger.error("Step '%s' failed: %s: %s", step_meta.name, type(exc).__name__, exc)
        raise StepFailure(step_meta.name, exc) from exc
    finally:
        clear_log_context(step_token)


class Engine:
    """Executes capabilities."""

    def __init__(self, audit_trail: AuditTrail | None = None) -> None:
        self.audit_trail = audit_trail or AuditTrail()

    async def execute(
        self,
        capability_fn: Callable[..., Any],
        inputs: dict[str, Any],
        credentials: CredentialStore | None = None,
        client_factory: Any | None = None,
        human_input_handler: Any | None = None,
        requester: str = "unknown",
    ) -> ProjectionData:
        defn = get_capability_def(capability_fn)
        if defn is None:
            raise LatticeError(f"{capability_fn.__name__} is not decorated with @capability")

        _validate_inputs(defn, inputs)

        creds = credentials or CredentialStore()
        intent = Intent(inputs)

        audit = AuditRecord(
            capability_name=defn.name,
            capability_version=defn.version,
            requester=requester,
            intent=inputs,
            granted_scopes=sorted(creds.granted_scopes),
        )

        log_token = set_log_context(
            execution_id=audit.execution_id,
            capability=defn.name,
            requester=requester,
        )
        logger.info(
            "Executing %s v%s (requester=%s, scopes=%d)",
            defn.name,
            defn.version,
            requester,
            len(creds.granted_scopes),
        )

        ctx = ExecutionContext(
            intent=intent,
            credentials=creds,
            client_factory=client_factory,
            human_input_handler=human_input_handler,
            requester=requester,
        )

        store = StateStore()
        state_token = bind_store(store)
        cred_token = bind_credentials(creds)

        try:
            projection_result = await self._run_capability(defn, ctx, store, creds, audit)
            _validate_projection(defn, projection_result)
            audit.complete(projection_result)
            logger.info(
                "Completed %s in %.1fms (%d steps)",
                defn.name,
                audit.duration_ms or 0,
                len(audit.steps),
            )
            return projection_result

        except AbortExecution as exc:
            audit.abort(exc)
            logger.error("Aborted %s at step '%s': %s", defn.name, exc.step_name, exc.cause)
            raise
        except LatticeError as exc:
            audit.fail(exc)
            logger.error("Failed %s: %s", defn.name, exc)
            raise
        except Exception as exc:
            audit.fail(exc)
            logger.error("Unexpected error in %s: %s: %s", defn.name, type(exc).__name__, exc)
            raise LatticeError(f"Unexpected error: {exc}") from exc
        finally:
            self.audit_trail.record(audit)
            unbind_store(state_token)
            unbind_credentials(cred_token)
            clear_log_context(log_token)

    async def _run_capability(
        self,
        defn: CapabilityDefinition,
        ctx: ExecutionContext,
        store: StateStore,
        creds: CredentialStore,
        audit: AuditRecord,
    ) -> ProjectionData:
        """Phase 1: collect step definitions.
        Phase 2: execute steps in dependency order.
        Phase 3: evaluate the projection.
        """
        collector, collect_token = _begin_collecting()
        try:
            with contextlib.suppress(AttributeError, KeyError, TypeError):
                await defn.fn(ctx)
        finally:
            _end_collecting(collect_token)

        collected_steps = list(collector)
        defn.steps = collected_steps
        logger.debug("Collected %d steps for %s", len(collected_steps), defn.name)

        _pre_check_permissions(collected_steps, creds)
        logger.debug("Permission pre-check passed for all %d steps", len(collected_steps))

        ordered = _resolve_order(collected_steps)
        logger.debug(
            "Execution order: %s",
            " -> ".join(s.name for s in ordered),
        )
        for step_meta in ordered:
            audit_step = audit.add_step(step_meta.name, step_meta.scope)
            await _execute_step(step_meta, store, audit_step)

        result = await defn.fn(ctx)
        return cast(ProjectionData, result)
