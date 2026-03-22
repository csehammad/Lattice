"""Tests for lattice.cli."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml
from click.testing import CliRunner

from lattice.cli.main import cli
from lattice.llm.provider import LLMResponse


def _make_spec(tmp_path: Path) -> Path:
    """Create a minimal OpenAPI spec file for tests."""
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Test", "version": "1.0"},
        "paths": {
            "/users": {
                "get": {
                    "operationId": "listUsers",
                    "summary": "List users",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/users/{id}": {
                "get": {
                    "operationId": "getUser",
                    "summary": "Get user",
                    "parameters": [{"name": "id", "in": "path"}],
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
    }
    spec_file = tmp_path / "api.yaml"
    spec_file.write_text(yaml.dump(spec))
    return spec_file


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_generate_skeleton(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "generate",
            "--capability",
            "VendorOnboarding",
            "--output",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0
    generated = tmp_path / "vendor_onboarding.py"
    assert generated.exists()
    content = generated.read_text()
    assert "VendorOnboarding" in content
    assert "@capability" in content


def test_generate_human_tasks(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "generate",
            "--capability",
            "MyCapability",
            "--output",
            str(tmp_path),
            "--human-tasks",
        ],
    )
    assert result.exit_code == 0
    generated = tmp_path / "my_capability.py"
    assert generated.exists()
    content = generated.read_text()
    assert "human_task" in content


def test_discover_with_openapi(tmp_path: Path):
    spec_file = _make_spec(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "discover",
            "--spec",
            str(spec_file),
        ],
    )
    assert result.exit_code == 0
    assert "listUsers" in result.output
    assert "getUser" in result.output
    assert "2" in result.output


def test_match_with_llm(tmp_path: Path):
    """Test that `lattice match` sends operations to LLM and displays results."""
    spec_file = _make_spec(tmp_path)

    llm_json = json.dumps(
        {
            "capabilities": [
                {
                    "name": "UserManagement",
                    "description": "Manage user accounts",
                    "domain": "identity",
                    "inputs": {"user_id": "str"},
                    "projection": {"status": "str"},
                    "steps": [
                        {
                            "name": "fetch_user",
                            "operation_ids": ["getUser"],
                            "depends_on": [],
                            "scope": "users.read",
                        }
                    ],
                }
            ],
            "unmatched_operations": ["listUsers"],
        }
    )

    mock_backend = MagicMock()
    mock_backend.complete.return_value = LLMResponse(text=llm_json)

    with patch("lattice.llm.provider.get_llm_client", return_value=mock_backend):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "match",
                "--spec",
                str(spec_file),
                "--domain",
                "identity",
                "--provider",
                "openai",
                "--api-key",
                "sk-test",
            ],
        )

    assert result.exit_code == 0, result.output
    assert "UserManagement" in result.output
    assert "Manage user accounts" in result.output
    assert "listUsers" in result.output
    mock_backend.complete.assert_called_once()


def test_generate_with_llm(tmp_path: Path):
    """Test that `lattice generate --spec` invokes the LLM and writes code."""
    spec_file = _make_spec(tmp_path)

    llm_code = (
        "```python\nfrom lattice import capability\n\n"
        '@capability(name="UserManagement")\nasync def user_management(ctx):\n'
        "    pass\n```"
    )

    mock_backend = MagicMock()
    mock_backend.complete.return_value = LLMResponse(text=llm_code)

    out_dir = tmp_path / "out"

    with patch("lattice.llm.provider.get_llm_client", return_value=mock_backend):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "generate",
                "--capability",
                "UserManagement",
                "--spec",
                str(spec_file),
                "--output",
                str(out_dir),
                "--provider",
                "openai",
                "--api-key",
                "sk-test",
            ],
        )

    assert result.exit_code == 0, result.output
    generated = out_dir / "user_management.py"
    assert generated.exists()
    content = generated.read_text()
    assert "@capability" in content
    assert "UserManagement" in content
    mock_backend.complete.assert_called_once()


def test_generate_with_llm_human_tasks(tmp_path: Path):
    """Test --human-tasks flag is passed to LLM system prompt."""
    spec_file = _make_spec(tmp_path)

    llm_code = "```python\nfrom lattice import capability\n\nasync def cap(ctx):\n    pass\n```"

    mock_backend = MagicMock()
    mock_backend.complete.return_value = LLMResponse(text=llm_code)

    out_dir = tmp_path / "out"

    with patch("lattice.llm.provider.get_llm_client", return_value=mock_backend):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "generate",
                "--capability",
                "HumanCap",
                "--spec",
                str(spec_file),
                "--output",
                str(out_dir),
                "--human-tasks",
                "--provider",
                "openai",
                "--api-key",
                "sk-test",
            ],
        )

    assert result.exit_code == 0, result.output
    # Verify the system prompt used was the human-tasks variant
    call_args = mock_backend.complete.call_args
    system_prompt = call_args[0][0]
    assert "human_task" in system_prompt
