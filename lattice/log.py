"""Structured logging for the Lattice runtime.

Provides a configurable logging layer that is:

- **Async-safe**: uses contextvars to carry execution context (execution_id,
  capability name, step name) through async call chains without threading issues.
- **Structured**: ships a JSON formatter for machine-readable log output
  alongside the default human-readable text formatter.
- **Configurable**: ``configure_logging()`` sets up the ``lattice`` logger tree
  with level, format, and optional JSON mode. Libraries that embed Lattice can
  ignore this and configure the ``lattice`` logger however they want.
- **Zero-config by default**: without calling ``configure_logging()``, all
  Lattice loggers use the stdlib NullHandler (silent), following the library
  best-practice from the Python logging HOWTO.

Usage::

    from lattice.log import configure_logging

    configure_logging(level="DEBUG", json_output=True)
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
from typing import Any

# ---------------------------------------------------------------------------
# Execution context carried across async boundaries
# ---------------------------------------------------------------------------

_exec_ctx: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "lattice_log_context", default=None
)


def set_log_context(**kwargs: Any) -> contextvars.Token[dict[str, Any] | None]:
    """Set key-value pairs on the async-safe log context."""
    current = _exec_ctx.get() or {}
    merged = {**current, **kwargs}
    return _exec_ctx.set(merged)


def clear_log_context(token: contextvars.Token[dict[str, Any] | None]) -> None:
    """Restore log context to the state before the matching ``set_log_context``."""
    _exec_ctx.reset(token)


def get_log_context() -> dict[str, Any]:
    """Return the current log context (read-only copy)."""
    return dict(_exec_ctx.get() or {})


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

class LatticeTextFormatter(logging.Formatter):
    """Human-readable formatter that includes execution context fields."""

    def format(self, record: logging.LogRecord) -> str:
        ctx = _exec_ctx.get() or {}
        parts = [self.formatTime(record), record.levelname.ljust(8), record.name]

        if ctx.get("execution_id"):
            parts.append(f"[{ctx['execution_id'][:8]}]")
        if ctx.get("capability"):
            parts.append(ctx["capability"])
        if ctx.get("step"):
            parts.append(f"step={ctx['step']}")

        parts.append(record.getMessage())

        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            parts.append(record.exc_text)

        return " | ".join(parts)


class LatticeJSONFormatter(logging.Formatter):
    """Machine-readable JSON-lines formatter with full context."""

    def format(self, record: logging.LogRecord) -> str:
        ctx = _exec_ctx.get() or {}
        payload: dict[str, Any] = {
            "ts": record.created,
            "time": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(ctx)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        extra_keys = {
            k: v for k, v in record.__dict__.items()
            if k.startswith("lattice_") or k.startswith("lx_")
        }
        if extra_keys:
            payload.update(extra_keys)

        return json.dumps(payload, default=str)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_configured = False


def configure_logging(
    level: str | int = "INFO",
    json_output: bool = False,
    stream: Any = None,
) -> None:
    """Configure the ``lattice`` logger tree.

    Parameters
    ----------
    level:
        Log level (e.g. ``"DEBUG"``, ``"INFO"``, ``logging.WARNING``).
    json_output:
        If ``True``, use JSON-lines format. Otherwise human-readable text.
    stream:
        Output stream. Defaults to ``sys.stderr``.
    """
    global _configured

    root_logger = logging.getLogger("lattice")

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(stream or sys.stderr)
    formatter: logging.Formatter
    if json_output:
        formatter = LatticeJSONFormatter()
    else:
        formatter = LatticeTextFormatter(datefmt="%Y-%m-%d %H:%M:%S")

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(level)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger under the ``lattice`` namespace.

    All Lattice modules should use this instead of ``logging.getLogger``
    directly, so the entire framework is controlled by one logger tree::

        logger = get_logger(__name__)   # e.g. "lattice.runtime.engine"
    """
    if name.startswith("lattice"):
        return logging.getLogger(name)
    return logging.getLogger(f"lattice.{name}")


# Install the NullHandler on the root lattice logger so that
# importing lattice without configuring logging produces no warnings.
logging.getLogger("lattice").addHandler(logging.NullHandler())
