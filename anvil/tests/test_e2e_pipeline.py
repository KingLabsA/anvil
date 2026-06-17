"""End-to-end test of the Anvil pipeline.

Creates a workspace with a buggy Python file + test, runs the full
Plan → Execute → Verify → Recover loop, and confirms the fix was applied.

Usage:
    python -m tests.test_e2e_pipeline                    # uses shellwhisperer-1.5b
    python -m tests.test_e2e_pipeline --model mythos-9b  # uses mythos-9b
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

# Ensure the src directory is on the path
SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from anvil.core.config import AnvilConfig, ModelConfig, VerifyConfig, ToolConfig
from anvil.core.engine import AnvilEngine


# ---------------------------------------------------------------------------
# Fixtures — a tiny project with a known bug
# ---------------------------------------------------------------------------

CALCULATOR_PY = '''\
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b

def divide(a, b):
    return a / b
'''

TEST_CALCULATOR_PY = '''\
import pytest
from calculator import add, subtract, multiply, divide


def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0, 0) == 0


def test_subtract():
    assert subtract(5, 3) == 2
    assert subtract(0, 5) == -5


def test_multiply():
    assert multiply(3, 4) == 12
    assert multiply(-2, 3) == -6
    assert multiply(0, 10) == 0


def test_divide():
    assert divide(10, 2) == 5.0
    assert divide(7, 2) == 3.5
    with pytest.raises(ZeroDivisionError):
        divide(1, 0)
'''

BUGGY_CALCULATOR_PY = '''\
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b

def divide(a, b):
    return a / b
'''

# Inject the bug: divide should return int division, and subtract has an off-by-one
BUGGY_CALCULATOR_PY = '''\
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b - 1

def multiply(a, b):
    return a * b

def divide(a, b):
    return a // b
'''


def make_workspace(tmp_dir: Path) -> Path:
    """Create a workspace with buggy code + tests."""
    ws = tmp_dir / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "calculator.py").write_text(BUGGY_CALCULATOR_PY)
    (ws / "test_calculator.py").write_text(TEST_CALCULATOR_PY)
    return ws


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_verify_pipeline_standalone():
    """Verify the verify pipeline catches syntax errors and runs tests."""
    from anvil.verify.pipeline import VerifyPipeline, VerifyStatus

    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        # Good file
        good = ws / "good.py"
        good.write_text("x = 1\n")
        cfg = VerifyConfig(enabled=True, check_syntax=True, check_lint=False, check_types=False)
        pipeline = VerifyPipeline(cfg)
        report = pipeline.verify([str(good)])
        assert report.passed, f"Expected pass for good file, got: {report.format_summary()}"

        # Bad file
        bad = ws / "bad.py"
        bad.write_text("def foo(\n  pass\n")
        report = pipeline.verify([str(bad)])
        assert not report.passed, f"Expected failure for bad file"

        print("  ✓ Verify pipeline standalone: PASS")


def test_error_recovery_standalone():
    """Verify error recovery classifies errors correctly."""
    from anvil.integrations.error_recovery import ErrorCategory, ErrorRecoveryIntegration

    er = ErrorRecoveryIntegration()

    # Syntax error
    result = er.recover("SyntaxError: invalid syntax at line 5")
    assert result.category == ErrorCategory.SYNTAX, f"Expected SYNTAX, got {result.category}"
    assert result.strategy == "fix_syntax_error"

    # Import error
    result = er.recover("ModuleNotFoundError: No module named 'requests'")
    assert result.category == ErrorCategory.IMPORT, f"Expected IMPORT, got {result.category}"

    # Runtime error
    result = er.recover("KeyError: 'name'")
    assert result.category == ErrorCategory.RUNTIME, f"Expected RUNTIME, got {result.category}"

    print("  ✓ Error recovery standalone: PASS")


def test_tool_executor_standalone():
    """Verify tool executor runs real commands."""
    from anvil.tools.executor import ToolExecutor

    with tempfile.TemporaryDirectory() as tmp:
        executor = ToolExecutor(working_dir=tmp, timeout=10)

        # bash
        result = executor.execute("bash", {"command": "echo hello"})
        assert result.success, f"bash failed: {result.error}"
        assert "hello" in result.output

        # write + read
        result = executor.execute("write", {"path": "test.txt", "content": "hi there"})
        assert result.success, f"write failed: {result.error}"
        result = executor.execute("read", {"path": "test.txt"})
        assert result.success, f"read failed: {result.error}"
        assert "hi there" in result.output

        # edit
        result = executor.execute("edit", {"path": "test.txt", "old_string": "hi there", "new_string": "hello world"})
        assert result.success, f"edit failed: {result.error}"
        result = executor.execute("read", {"path": "test.txt"})
        assert "hello world" in result.output

        # grep
        result = executor.execute("grep", {"pattern": "hello", "path": tmp})
        assert result.success and "hello" in result.output

        # glob
        result = executor.execute("glob", {"pattern": "*.txt", "path": tmp})
        assert result.success and "test.txt" in result.output

        # ls
        result = executor.execute("ls", {"path": tmp})
        assert result.success and "test.txt" in result.output

        print("  ✓ Tool executor standalone: PASS")


def test_full_pipeline_with_model(model_name: str, api_base: str):
    """Full E2E: model generates → tools execute → verify checks → recovery.

    This is the real test — the full Anvil loop with an actual model.
    """
    with tempfile.TemporaryDirectory() as tmp:
        ws = make_workspace(Path(tmp))

        # First, confirm the tests FAIL with the buggy code
        import subprocess
        pre_result = subprocess.run(
            [sys.executable, "-m", "pytest", "test_calculator.py", "-x", "--tb=short"],
            capture_output=True, text=True, cwd=str(ws),
        )
        assert pre_result.returncode != 0, "Tests should fail before fix"
        print(f"  ✓ Pre-fix tests correctly fail (exit {pre_result.returncode})")

        # Configure the engine to use the local model
        config = AnvilConfig(
            model=ModelConfig(
                model=model_name,
                api_base=api_base,
                max_tokens=2048,
                temperature=0.1,
            ),
            verify=VerifyConfig(
                enabled=True,
                auto_recover=True,
                max_retries=3,
                check_syntax=True,
                check_lint=False,
                check_types=False,
                check_tests=True,
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

        print(f"\n  Running full pipeline with model: {model_name}")
        print(f"  Workspace: {ws}")

        engine = AnvilEngine(config)
        result = engine.run(
            "Fix the bugs in calculator.py so that all tests in test_calculator.py pass. "
            "The subtract function has an off-by-one error (-1) and the divide function "
            "uses integer division instead of float division.",
            max_iterations=10,
        )

        print(f"\n  Engine result: {'SUCCESS' if result.success else 'FAILED'}")
        print(f"  Output: {result.output[:300]}")
        if result.verify_report:
            print(f"  Verify report:\n{result.verify_report.format_summary()}")
        if result.error:
            print(f"  Error: {result.error[:300]}")

        # Print session progress
        if result.session:
            print(f"\n  Session progress:\n{result.session.format_progress()}")

        # Check that tests pass now
        post_result = subprocess.run(
            [sys.executable, "-m", "pytest", "test_calculator.py", "-v", "--tb=short"],
            capture_output=True, text=True, cwd=str(ws),
        )
        print(f"\n  Post-fix test result: exit {post_result.returncode}")
        if post_result.returncode != 0:
            print(f"  stdout: {post_result.stdout[-500:]}")
            print(f"  stderr: {post_result.stderr[-500:]}")

        # Verify the actual file content was changed
        fixed_code = (ws / "calculator.py").read_text()
        print(f"\n  Fixed calculator.py:\n{fixed_code}")

        # Assertions
        assert post_result.returncode == 0, (
            f"Tests should pass after engine fix. Engine success={result.success}.\n"
            f"Engine output: {result.output[:500]}\n"
            f"Test output: {post_result.stdout[-500:]}"
        )
        assert "a - b - 1" not in fixed_code, "subtract off-by-one should be fixed"
        assert "a // b" not in fixed_code, "integer division should be float division"

        print("  ✓ Full pipeline E2E: PASS")
        return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Anvil E2E Pipeline Test")
    parser.add_argument("--model", default="shellwhisperer-1.5b:latest",
                        help="Ollama model to use (default: shellwhisperer-1.5b:latest)")
    parser.add_argument("--api-base", default="http://localhost:11434",
                        help="Ollama API base URL")
    parser.add_argument("--skip-model", action="store_true",
                        help="Skip the model-dependent E2E test")
    args = parser.parse_args()

    print("=" * 60)
    print("ANVIL END-TO-END PIPELINE TEST")
    print("=" * 60)

    passed = 0
    failed = 0

    # 1. Standalone unit tests (no model needed)
    print("\n[1/4] Verify pipeline standalone...")
    try:
        test_verify_pipeline_standalone()
        passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        failed += 1

    print("\n[2/4] Error recovery standalone...")
    try:
        test_error_recovery_standalone()
        passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        failed += 1

    print("\n[3/4] Tool executor standalone...")
    try:
        test_tool_executor_standalone()
        passed += 1
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        failed += 1

    # 4. Full pipeline with model
    if not args.skip_model:
        print(f"\n[4/4] Full pipeline E2E (model: {args.model})...")
        try:
            test_full_pipeline_with_model(args.model, args.api_base)
            passed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    else:
        print("\n[4/4] Skipped (--skip-model)")

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
