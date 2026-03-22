# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-03-22

### Added

- Core capability runtime with `@capability`, `@step`, `state`, and `projection` primitives.
- Execution engine with dependency-ordered step execution and topological sorting.
- Concurrent step execution for independent steps via `asyncio.gather()`.
- Failure policies: `@retry`, `@soft_failure`, `@hard_failure`.
- Human task support: `@human_task`, `@needs_human_input`.
- Scoped credential injection and pre-execution permission validation.
- Structured audit trail for every execution.
- Rich projection schema with type, example, and description fields.
- LLM-powered capability matching and code generation (OpenAI and Anthropic).
- OpenAPI discovery and inventory system.
- CLI with commands: `discover`, `match`, `generate`, `visualize`, `validate`, `register`, `run`, `bind`.
- Interactive HTML visualization with Bootstrap and Mermaid.js.
- Registry with `to_openai_tools()` and `to_anthropic_tools()` exports.
- End-to-end agent demo with OpenAI function-calling.
- Standalone binary builds for macOS, Linux, and Windows.
- CI/CD with GitHub Actions (lint, typecheck, test matrix, release).
