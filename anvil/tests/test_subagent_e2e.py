"""E2E test of subagent dispatch (task tool).

Tests that the engine can dispatch a subagent to handle a subtask,
and the subagent returns a result.

Usage:
    python -m tests.test_subagent_e2e
    python -m tests.test_subagent_e2e --model qwen3.5:9b
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from anvil.core.config import AnvilConfig, ModelConfig, VerifyConfig, ToolConfig
from anvil.core.engine import AnvilEngine


# ---------------------------------------------------------------------------
# Workspace with a task that requires reading + writing
# ---------------------------------------------------------------------------

PROJECT_PY = '''\
def greet(name):
    return f"Hello, {name}!"

def add(a, b):
    return a + b
'''

TEST_PY = '''\
from project import greet, add

def test_greet():
    assert greet("World") == "Hello, World!"

def test_add():
    assert add(2, 3) == 5
'''


def make_workspace(root: Path) -> Path:
    ws = root / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "project.py").write_text(PROJECT_PY)
    (ws / "test_project.py").write_text(TEST_PY)
    return ws


# ---------------------------------------------------------------------------
# Test: subagent dispatch via task tool
# ---------------------------------------------------------------------------

def test_subagent_dispatch(model_name: str, api_base: str):
    """E2E: parent model dispatches a subagent to explore + report."""
    with tempfile.TemporaryDirectory() as tmp:
        ws = make_workspace(Path(tmp))

        config = AnvilConfig(
            model=ModelConfig(
                model=model_name,
                api_base=api_base,
                max_tokens=2048,
                temperature=0.1,
            ),
            verify=VerifyConfig(
                enabled=True,
                auto_recover=False,
                max_retries=1,
                check_syntax=True,
                check_lint=False,
                check_types=False,
                check_tests=False,
                timeout_seconds=60,
            ),
            tools=ToolConfig(
                working_dir=str(ws),
                allow_shell=True,
                allow_file_write=True,
                allow_file_read=True,
            ),
            project_root=str(ws),
        )

        engine = AnvilEngine(config)

        # Directly call _run_task to test subagent dispatch
        result = engine._run_task({
            "subagent_type": "explore",
            "prompt": "Read project.py and list all functions defined in it. Return the function names.",
            "description": "Explore project structure",
        })

        print(f"\n  Subagent result: {'SUCCESS' if result.success else 'FAILED'}")
        print(f"  Output: {result.output[:500]}")

        assert result.success, f"Subagent dispatch failed: {result.error}"
        assert "task_result" in result.output, \
            f"Subagent didn't return task_result: {result.output[:200]}"

        print("  ✓ Subagent dispatch E2E: PASS")


# ---------------------------------------------------------------------------
# Test: skill tool loads skill content
# ---------------------------------------------------------------------------

def test_skill_load():
    """E2E: skill tool loads SKILL.md content."""
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "workspace"
        ws.mkdir()
        skill_dir = ws / ".anvil" / "skills" / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "# Test Skill\n\nThis skill tests loading.\n\nSteps:\n1. Do something\n2. Verify\n"
        )

        config = AnvilConfig(
            model=ModelConfig(model="local"),
            tools=ToolConfig(working_dir=str(ws)),
            project_root=str(ws),
        )
        engine = AnvilEngine(config)
        result = engine._run_skill({"name": "test-skill"})

        assert result.success, f"Skill load failed: {result.error}"
        assert "Test Skill" in result.output
        assert "Do something" in result.output

        print("  ✓ Skill load E2E: PASS")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Subagent E2E Test")
    parser.add_argument("--model", default="shellwhisperer-1.5b:latest",
                        help="Model to use for testing")
    parser.add_argument("--api-base", default="http://localhost:11434",
                        help="Ollama API base URL")
    args = parser.parse_args()

    print("=" * 60)
    print("SUBAGENT & SKILL E2E TEST")
    print("=" * 60)

    # Test 1: skill load (no model needed)
    print("\n[1/2] Skill tool E2E...")
    test_skill_load()

    # Test 2: subagent dispatch (needs model)
    print(f"\n[2/2] Subagent dispatch E2E (model: {args.model})...")
    test_subagent_dispatch(args.model, args.api_base)

    print("\n" + "=" * 60)
    print("ALL SUBAGENT E2E TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
