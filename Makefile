.DEFAULT_GOAL := help

.PHONY: help install test test-cov lint format typecheck build ci clean

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install package with all extras in editable mode
	pip install -e ".[llm,dev]"

test: ## Run all tests
	pytest tests/

test-unit: ## Run unit tests only
	pytest tests/ -m unit

test-integration: ## Run integration tests only
	pytest tests/ -m integration

test-cov: ## Run tests with coverage report
	pytest tests/ --cov=lattice --cov-report=term-missing --cov-report=html --cov-report=xml

lint: ## Check code with ruff linter
	ruff check .

format: ## Auto-format code with ruff
	ruff format .
	ruff check --fix .

typecheck: ## Run mypy type checker
	mypy lattice/

build: ## Build standalone binary with PyInstaller
	./release/build.sh

ci: lint typecheck test-cov ## Run everything CI runs (lint + typecheck + test-cov)

clean: ## Remove build artifacts
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov coverage.xml .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
