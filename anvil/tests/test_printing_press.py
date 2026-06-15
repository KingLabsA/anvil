"""Tests for the Printing Press API-to-CLI generator."""

import ast
import json
import subprocess
import sys

import pytest

from anvil.printing_press import (
    Endpoint,
    generate_cli_source,
    generate_skill_md,
    parse_openapi,
    press,
)

SAMPLE_SPEC = {
    "openapi": "3.0.0",
    "servers": [{"url": "https://api.example.com/v1"}],
    "paths": {
        "/users": {
            "get": {
                "operationId": "listUsers",
                "summary": "List all users",
                "parameters": [{"name": "limit", "in": "query"}],
            },
            "post": {"operationId": "createUser", "summary": "Create a user"},
        },
        "/users/{id}": {
            "get": {
                "operationId": "getUser",
                "summary": "Get one user",
                "parameters": [{"name": "id", "in": "path"}],
            },
        },
    },
}


class TestParseOpenAPI:
    def test_extracts_base_url(self):
        base, _ = parse_openapi(SAMPLE_SPEC)
        assert base == "https://api.example.com/v1"

    def test_extracts_endpoints(self):
        _, endpoints = parse_openapi(SAMPLE_SPEC)
        ops = {e.operation_id for e in endpoints}
        assert ops == {"listUsers", "createUser", "getUser"}

    def test_path_and_query_params(self):
        _, endpoints = parse_openapi(SAMPLE_SPEC)
        get_user = next(e for e in endpoints if e.operation_id == "getUser")
        assert "id" in get_user.path_params
        list_users = next(e for e in endpoints if e.operation_id == "listUsers")
        assert "limit" in list_users.query_params

    def test_swagger2_host_basepath(self):
        spec = {
            "swagger": "2.0",
            "host": "api.test.io",
            "basePath": "/api",
            "schemes": ["https"],
            "paths": {"/ping": {"get": {"operationId": "ping"}}},
        }
        base, endpoints = parse_openapi(spec)
        assert base == "https://api.test.io/api"
        assert endpoints[0].command_name == "ping"


class TestCommandName:
    def test_camel_to_kebab(self):
        ep = Endpoint(method="GET", path="/x", operation_id="listAllUsers")
        assert ep.command_name == "listallusers" or ep.command_name == "list-all-users"

    def test_fallback_from_path(self):
        ep = Endpoint(method="GET", path="/health/check", operation_id="")
        assert ep.command_name  # non-empty


class TestGeneration:
    def test_cli_source_is_valid_python(self):
        _, endpoints = parse_openapi(SAMPLE_SPEC)
        src = generate_cli_source("Example", "https://api.example.com/v1", endpoints, "example_cli.py")
        ast.parse(src)  # raises SyntaxError if invalid

    def test_cli_source_embeds_endpoints(self):
        _, endpoints = parse_openapi(SAMPLE_SPEC)
        src = generate_cli_source("Example", "https://api.example.com/v1", endpoints, "example_cli.py")
        assert "listUsers" in src or "listusers" in src
        assert "https://api.example.com/v1" in src
        assert "EXAMPLE_TOKEN" in src

    def test_skill_md_lists_commands(self):
        _, endpoints = parse_openapi(SAMPLE_SPEC)
        md = generate_skill_md("Example", "https://api.example.com/v1", endpoints, "example_cli.py")
        assert "# Skill: Example API" in md
        assert "getuser" in md.lower()
        assert "--list" in md


class TestPress:
    def test_press_writes_artifacts(self, tmp_path):
        result = press("Example", spec=SAMPLE_SPEC, output_dir=tmp_path)
        assert result.cli_path.exists()
        assert result.skill_path.exists()
        assert result.base_url == "https://api.example.com/v1"
        assert len(result.endpoints) == 3
        # skill folder uses kebab slug
        assert result.cli_path.parent.name == "example"

    def test_press_requires_base_url_without_servers(self, tmp_path):
        spec = {"openapi": "3.0.0", "paths": {"/p": {"get": {"operationId": "p"}}}}
        with pytest.raises(ValueError):
            press("NoServers", spec=spec, output_dir=tmp_path)

    def test_press_base_url_only(self, tmp_path):
        result = press("Raw", base_url="https://raw.example.com", output_dir=tmp_path)
        assert result.cli_path.exists()
        assert result.endpoints == []

    def test_generated_cli_runs_list(self, tmp_path):
        result = press("Example", spec=SAMPLE_SPEC, output_dir=tmp_path)
        proc = subprocess.run(
            [sys.executable, str(result.cli_path), "--list"],
            capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == 0
        assert "Available commands" in proc.stdout

    def test_generated_cli_unknown_command(self, tmp_path):
        result = press("Example", spec=SAMPLE_SPEC, output_dir=tmp_path)
        proc = subprocess.run(
            [sys.executable, str(result.cli_path), "nope"],
            capture_output=True, text=True, timeout=30,
        )
        assert proc.returncode == 2
        assert "Unknown command" in proc.stderr
