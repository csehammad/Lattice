# Contributing to Lattice

Thank you for your interest in contributing to Lattice. This guide covers the development workflow.

## Development Setup

```bash
git clone https://github.com/csehammad/Lattice.git
cd Lattice
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[llm,dev]"
pre-commit install
```

## Running Tests

```bash
make test           # all tests
make test-cov       # with coverage report
pytest -m unit      # unit tests only
pytest -m integration  # integration tests only
```

## Code Quality

```bash
make lint           # check for lint errors
make format         # auto-format code
make typecheck      # run mypy type checker
make ci             # run everything CI runs
```

## Code Style

- We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting.
- Line length limit is 100 characters.
- Use type hints for all public APIs.
- Follow existing patterns in the codebase.

## Pull Request Guidelines

1. Create a feature branch from `main`.
2. Write tests for new functionality.
3. Ensure `make ci` passes locally before opening a PR.
4. Keep PRs focused -- one feature or fix per PR.
5. Write clear commit messages that explain *why*, not just *what*.

## Reporting Issues

- Use GitHub Issues for bugs and feature requests.
- Include a minimal reproduction case when reporting bugs.
- Check existing issues before opening a new one.

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
