import pytest
from click.testing import CliRunner
from fableforge_cli.main import cli, list_projects, status


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "FableForge" in result.output


def test_list_projects():
    runner = CliRunner()
    result = runner.invoke(list_projects)
    assert result.exit_code == 0
    assert "anvil" in result.output


def test_status():
    runner = CliRunner()
    result = runner.invoke(status)
    assert result.exit_code == 0
    assert "ShellWhisperer" in result.output
