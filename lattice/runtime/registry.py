"""Capability registry — stores and retrieves registered capabilities.

Provides two registry types:

* ``CapabilityRegistry`` — eager, in-memory registry where all capabilities
  are imported and registered at startup.
* ``LazyRegistry`` — manifest-backed registry that loads only metadata at
  startup and dynamically imports capability modules on first execution.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from lattice.capability import CapabilityDefinition, get_capability_def
from lattice.errors import LatticeError
from lattice.log import get_logger

logger = get_logger(__name__)


class CapabilityRegistry:
    """In-memory registry of capability definitions.

    Also supports persistence to a JSON file via ``save`` / ``load``.
    """

    def __init__(self) -> None:
        self._capabilities: dict[str, CapabilityDefinition] = {}
        self._functions: dict[str, Callable[..., Any]] = {}

    def register(self, fn: Callable[..., Any]) -> CapabilityDefinition:
        defn = get_capability_def(fn)
        if defn is None:
            raise LatticeError(f"{fn.__name__} is not decorated with @capability")
        self._capabilities[defn.name] = defn
        self._functions[defn.name] = fn
        logger.info("Registered capability: %s v%s", defn.name, defn.version)
        return defn

    def get(self, name: str) -> CapabilityDefinition:
        if name not in self._capabilities:
            raise LatticeError(f"Capability '{name}' not registered")
        return self._capabilities[name]

    def get_function(self, name: str) -> Callable[..., Any]:
        if name not in self._functions:
            raise LatticeError(f"Capability '{name}' not registered")
        return self._functions[name]

    def list_capabilities(self) -> list[CapabilityDefinition]:
        return list(self._capabilities.values())

    def signatures(self) -> list[str]:
        return [defn.signature for defn in self._capabilities.values()]

    def save(self, path: Path | str) -> None:
        from lattice.types import (
            projection_field_description,
            projection_field_example,
            projection_field_type,
        )

        path = Path(path)
        data = {}
        for name, defn in self._capabilities.items():
            fn = self._functions.get(name)
            proj_out: dict[str, Any] = {}
            for fname, spec in defn.projection_schema.items():
                entry: dict[str, Any] = {"type": projection_field_type(spec).__name__}
                ex = projection_field_example(spec)
                if ex is not None:
                    entry["example"] = ex
                desc = projection_field_description(spec)
                if desc is not None:
                    entry["description"] = desc
                proj_out[fname] = entry
            entry_data: dict[str, Any] = {
                "name": defn.name,
                "version": defn.version,
                "inputs": {k: v.__name__ for k, v in defn.input_schema.items()},
                "projection": proj_out,
                "signature": defn.signature,
            }
            if fn is not None:
                entry_data["module_path"] = fn.__module__
                entry_data["function_name"] = fn.__name__
            data[name] = entry_data
        path.write_text(json.dumps(data, indent=2))

    def load(self, path: Path | str) -> dict[str, Any]:
        """Load registry metadata from JSON.  Returns the raw dict.

        Note: this loads *metadata* only — not the executable functions.
        Use ``register()`` to add executable capabilities.
        """
        path = Path(path)
        data = json.loads(path.read_text())
        return cast(dict[str, Any], data)

    # -- LLM tool exports --------------------------------------------------

    def to_openai_tools(self) -> list[dict[str, Any]]:
        """Export capabilities as OpenAI function-calling tool definitions."""
        from lattice.types import (
            projection_field_description,
            projection_field_example,
            projection_field_type,
        )

        _TYPE_MAP = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }
        tools: list[dict[str, Any]] = []
        for defn in self._capabilities.values():
            properties: dict[str, Any] = {}
            required: list[str] = []
            for param_name, param_type in defn.input_schema.items():
                properties[param_name] = {
                    "type": _TYPE_MAP.get(param_type, "string"),
                }
                required.append(param_name)

            proj_lines = []
            for fname, spec in defn.projection_schema.items():
                ftype = projection_field_type(spec).__name__
                fex = projection_field_example(spec)
                fdesc = projection_field_description(spec)
                part = f"- {fname} ({ftype})"
                if fdesc:
                    part += f": {fdesc}"
                if fex is not None:
                    part += f" [example: {fex!r}]"
                proj_lines.append(part)
            proj_description = "\n".join(proj_lines)

            description = (
                f"Lattice capability: {defn.name} v{defn.version}.\n"
                f"Returns a projection with:\n{proj_description}"
            )

            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": defn.name,
                        "description": description,
                        "parameters": {
                            "type": "object",
                            "properties": properties,
                            "required": required,
                        },
                    },
                }
            )
        return tools

    # Backward-compat alias: historically exposed as `.list()`.
    def list(self) -> list[CapabilityDefinition]:
        return self.list_capabilities()


# ---------------------------------------------------------------------------
# LazyRegistry — manifest-backed progressive loading
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# agrep-inspired capability search
#   Term expansion, intent detection, domain-aware scoring, score breakdown.
#   Deterministic — no LLM, no embeddings.
#   See: https://github.com/csehammad/agrep
# ---------------------------------------------------------------------------

_TERM_EXPANSIONS: dict[str, list[str]] = {
    "assign": ["assignment", "allocate", "allocation", "resource"],
    "assignment": ["assign", "allocate", "allocation", "resource"],
    "cancel": ["remove", "revoke", "terminate", "cancellation"],
    "remove": ["cancel", "revoke", "cancellation"],
    "view": ["show", "get", "display", "list", "check", "status", "inspect"],
    "show": ["view", "get", "display", "list", "check", "status"],
    "status": ["view", "show", "check", "get"],
    "update": ["change", "modify", "edit", "adjust"],
    "change": ["update", "modify", "edit", "adjust"],
    "find": ["search", "discover", "locate", "lookup", "candidates"],
    "search": ["find", "discover", "locate", "lookup"],
    "employee": ["staff", "engineer", "resource", "worker", "member", "person"],
    "staff": ["employee", "engineer", "resource", "worker", "staffing"],
    "engineer": ["employee", "staff", "resource", "developer"],
    "project": ["staffing", "team", "initiative"],
    "workload": ["schedule", "availability", "capacity", "utilization"],
    "schedule": ["workload", "availability", "calendar", "commitments"],
    "availability": ["schedule", "workload", "capacity", "free"],
    "candidate": ["applicant", "resource", "employee", "match"],
    "gap": ["unfilled", "vacancy", "opening", "missing", "need"],
    "notify": ["notification", "alert", "inform", "message"],
    "notification": ["notify", "alert", "inform", "message"],
    "skill": ["skills", "competency", "expertise", "proficiency"],
    "role": ["position", "title", "job"],
}

_INTENT_MAP: dict[str, str] = {
    "show": "view",
    "view": "view",
    "display": "view",
    "list": "view",
    "check": "view",
    "status": "view",
    "inspect": "view",
    "who": "view",
    "what": "view",
    "find": "search",
    "search": "search",
    "discover": "search",
    "locate": "search",
    "lookup": "search",
    "assign": "create",
    "create": "create",
    "allocate": "create",
    "add": "create",
    "update": "update",
    "change": "update",
    "modify": "update",
    "edit": "update",
    "adjust": "update",
    "cancel": "cancel",
    "remove": "cancel",
    "revoke": "cancel",
    "terminate": "cancel",
    "delete": "cancel",
}

_INTENT_CAPABILITY_BOOST: dict[str, list[str]] = {
    "view": ["View", "Get", "Check", "List", "Status"],
    "search": ["Find", "Search", "Discover"],
    "create": ["Assign", "Create", "Submit"],
    "update": ["Update", "Modify", "Change"],
    "cancel": ["Cancel", "Remove", "Revoke"],
}


def _expand_terms(keywords: list[str]) -> list[str]:
    """Expand keywords with domain synonyms (agrep-style term expansion)."""
    expanded = set(keywords)
    for kw in keywords:
        if kw in _TERM_EXPANSIONS:
            expanded.update(_TERM_EXPANSIONS[kw])
    return list(expanded)


def _detect_intent(keywords: list[str]) -> str | None:
    """Detect user intent from query keywords (agrep-style intent detection)."""
    for kw in keywords:
        if kw in _INTENT_MAP:
            return _INTENT_MAP[kw]
    return None


def _score_entry(entry: dict[str, Any], keywords: list[str]) -> dict[str, Any]:
    """Score a manifest entry with agrep-style multi-signal scoring.

    Returns a dict with total score and breakdown for transparency.
    """
    name = entry.get("name", "")
    name_lower = name.lower()

    searchable = " ".join(
        [
            name,
            entry.get("signature", ""),
            " ".join(entry.get("inputs", {}).keys()),
            " ".join(entry.get("projection", {}).keys()),
            " ".join(
                spec.get("description", "")
                for spec in entry.get("projection", {}).values()
                if isinstance(spec, dict)
            ),
        ]
    ).lower()

    expanded = _expand_terms(keywords)
    intent = _detect_intent(keywords)

    # 1. Direct term hits (original keywords)
    direct_hits = sum(1 for kw in keywords if kw in searchable)
    direct_score = direct_hits / max(len(keywords), 1)

    # 2. Expanded term hits (synonyms)
    extra_terms = [t for t in expanded if t not in keywords]
    expanded_hits = sum(1 for kw in extra_terms if kw in searchable)
    expansion_score = (expanded_hits / max(len(extra_terms), 1)) * 0.5 if extra_terms else 0.0

    # 3. Intent alignment bonus
    intent_score = 0.0
    if intent and intent in _INTENT_CAPABILITY_BOOST:
        prefixes = _INTENT_CAPABILITY_BOOST[intent]
        for prefix in prefixes:
            if prefix.lower() in name_lower:
                intent_score = 0.4
                break

    # 4. Name relevance bonus (keyword directly in capability name)
    name_score = 0.0
    for kw in keywords:
        if kw in name_lower:
            name_score += 0.2
    name_score = min(name_score, 0.4)

    total = direct_score + expansion_score + intent_score + name_score

    return {
        "total": round(total, 3),
        "direct": round(direct_score, 3),
        "expansion": round(expansion_score, 3),
        "intent": round(intent_score, 3),
        "name": round(name_score, 3),
        "detected_intent": intent,
        "expanded_terms": len(expanded),
    }


class LazyRegistry:
    """Manifest-backed registry with progressive capability loading.

    At init, only the JSON manifest (metadata) is loaded — no Python
    imports.  Capabilities are imported on-demand when ``ensure_loaded``
    is called.

    Typical flow (used by the agent's two meta-tools)::

        reg = LazyRegistry.from_manifest("registry.json")
        results = reg.search("vendor onboarding")   # fast, metadata only
        reg.ensure_loaded("VendorOnboarding")        # imports module now
        fn = reg.get_function("VendorOnboarding")    # ready to execute
    """

    def __init__(self, manifest: dict[str, dict[str, Any]]) -> None:
        self._manifest = manifest
        self._registry = CapabilityRegistry()
        self._loaded: set[str] = set()

    @classmethod
    def from_manifest(cls, path: Path | str) -> LazyRegistry:
        path = Path(path)
        manifest = json.loads(path.read_text())
        logger.info("Loaded manifest from %s (%d capabilities)", path, len(manifest))
        return cls(manifest)

    @classmethod
    def from_registry(cls, registry: CapabilityRegistry) -> LazyRegistry:
        """Build a LazyRegistry from an already-populated CapabilityRegistry.

        The manifest is derived from the live definitions so the registry
        can be used without a JSON file (useful for demos/tests).
        """
        manifest: dict[str, dict[str, Any]] = {}
        from lattice.types import (
            projection_field_description,
            projection_field_example,
            projection_field_type,
        )

        for defn in registry.list_capabilities():
            fn = registry.get_function(defn.name)
            proj_out: dict[str, Any] = {}
            for fname, spec in defn.projection_schema.items():
                entry: dict[str, Any] = {"type": projection_field_type(spec).__name__}
                ex = projection_field_example(spec)
                if ex is not None:
                    entry["example"] = ex
                desc = projection_field_description(spec)
                if desc is not None:
                    entry["description"] = desc
                proj_out[fname] = entry
            manifest[defn.name] = {
                "name": defn.name,
                "version": defn.version,
                "inputs": {k: v.__name__ for k, v in defn.input_schema.items()},
                "projection": proj_out,
                "signature": defn.signature,
                "module_path": fn.__module__,
                "function_name": fn.__name__,
            }

        instance = cls(manifest)
        logger.info(
            "Built lazy registry from in-memory registry (%d capabilities)",
            len(manifest),
        )
        # Pre-populate the inner registry with already-loaded functions
        for defn in registry.list_capabilities():
            fn = registry.get_function(defn.name)
            instance._registry.register(fn)
            instance._loaded.add(defn.name)
        return instance

    @property
    def manifest(self) -> dict[str, dict[str, Any]]:
        return dict(self._manifest)

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """agrep-style search over the manifest with term expansion,
        intent detection, and multi-signal scoring."""
        keywords = [w.lower() for w in query.split() if len(w) >= 2]
        if not keywords:
            return list(self._manifest.values())[:limit]

        scored = []
        for entry in self._manifest.values():
            breakdown = _score_entry(entry, keywords)
            if breakdown["total"] > 0:
                result = dict(entry)
                result["_search_score"] = breakdown
                scored.append((breakdown["total"], result))
        scored.sort(key=lambda x: x[0], reverse=True)
        results = [entry for _, entry in scored[:limit]]
        logger.debug(
            "Search '%s' matched %d/%d capabilities (intent=%s, expanded=%d terms)",
            query,
            len(results),
            len(self._manifest),
            _detect_intent(keywords),
            len(_expand_terms(keywords)),
        )
        return results

    def ensure_loaded(self, name: str) -> None:
        """Dynamically import and register a capability by name."""
        if name in self._loaded:
            return
        if name not in self._manifest:
            logger.error("Capability '%s' not found in manifest", name)
            raise LatticeError(f"Capability '{name}' not in manifest")

        entry = self._manifest[name]
        module_path = entry.get("module_path")
        function_name = entry.get("function_name")
        if not module_path or not function_name:
            raise LatticeError(f"Capability '{name}' manifest missing module_path/function_name")

        logger.info("Lazy-loading capability '%s' from %s.%s", name, module_path, function_name)
        mod = importlib.import_module(module_path)
        fn = getattr(mod, function_name)
        self._registry.register(fn)
        self._loaded.add(name)
        logger.debug("Capability '%s' loaded and registered", name)

    def get_function(self, name: str) -> Callable[..., Any]:
        self.ensure_loaded(name)
        return self._registry.get_function(name)

    def get(self, name: str) -> CapabilityDefinition:
        self.ensure_loaded(name)
        return self._registry.get(name)

    def is_loaded(self, name: str) -> bool:
        return name in self._loaded

    # -- Meta-tool definitions for OpenAI function-calling -----------------

    @staticmethod
    def openai_meta_tools() -> list[dict[str, Any]]:
        """Return the two meta-tool definitions for OpenAI function-calling."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_capabilities",
                    "description": (
                        "Search the Lattice capability registry. Returns matching "
                        "capabilities with their name, required inputs, and "
                        "projected outputs. Use this FIRST to discover which "
                        "capability can fulfill the user's request."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": (
                                    "Natural language search query describing what "
                                    "the user wants to accomplish."
                                ),
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "execute_capability",
                    "description": (
                        "Execute a Lattice capability by name. You MUST call "
                        "search_capabilities first to find the right capability "
                        "and learn its required inputs. Pass the exact capability "
                        "name and all required inputs as a JSON object."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "capability_name": {
                                "type": "string",
                                "description": "Exact name of the capability from search results.",
                            },
                            "inputs": {
                                "type": "object",
                                "description": (
                                    "Input parameters for the capability. Keys and "
                                    "types must match what search_capabilities returned."
                                ),
                            },
                        },
                        "required": ["capability_name", "inputs"],
                    },
                },
            },
        ]


# Module-level default registry
_default_registry = CapabilityRegistry()


def get_default_registry() -> CapabilityRegistry:
    return _default_registry
