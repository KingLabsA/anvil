"""Run E2E pipeline test on each FableForge model.

Usage:
    python3 tests/test_all_models.py
"""

import subprocess
import sys
import json
import time
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"

MODELS = [
    "shellwhisperer-1.5b:latest",
    "mythos-9b:latest",
    "mythos-9b-enhanced:latest",
    "mythos-9b-unhinged:latest",
    "fableforge-ai/shellwhisperer:latest",
    "fableforge-ai/mythos-9b:latest",
    "fableforge-ai/mythos-9b-enhanced:latest",
    "fableforge-ai/mythos-9b-unhinged:latest",
]

# Also test the aliases
ALIASES = {
    "shellwhisperer:latest": "shellwhisperer-1.5b:latest",
    "fableforge/shellwhisperer:latest": "shellwhisperer-1.5b:latest",
    "fableforge/mythos-9b:latest": "mythos-9b:latest",
    "fableforge/mythos-9b-enhanced:latest": "mythos-9b-enhanced:latest",
    "fableforge/mythos-9b-unhinged:latest": "mythos-9b-unhinged:latest",
}


def check_ollama_model(name: str) -> bool:
    """Check if a model exists in Ollama."""
    try:
        result = subprocess.run(
            ["curl", "-s", "http://localhost:11434/api/tags"],
            capture_output=True, text=True, timeout=5,
        )
        data = json.loads(result.stdout)
        available = [m["name"] for m in data.get("models", [])]
        # Check exact match or match without tag
        base = name.split(":")[0]
        for avail in available:
            if avail == name or avail.startswith(base + ":"):
                return True
        return False
    except Exception:
        return False


def run_single_model_test(model: str) -> dict:
    """Run the E2E test for a single model and return results."""
    print(f"\n{'─'*60}")
    print(f"  MODEL: {model}")
    print(f"{'─'*60}")

    if not check_ollama_model(model):
        print(f"  ⚠ Not found in Ollama, skipping")
        return {"model": model, "status": "skipped", "reason": "not in ollama"}

    start = time.time()
    result = subprocess.run(
        [sys.executable, "-m", "tests.test_e2e_pipeline", "--model", model],
        capture_output=True, text=True, timeout=600,
        cwd=str(Path(__file__).resolve().parent.parent),
    )
    elapsed = time.time() - start

    passed = result.returncode == 0
    status = "PASS ✓" if passed else "FAIL ✗"

    # Extract key info from output
    output = result.stdout + result.stderr
    lines = output.strip().split("\n")

    print(f"  Status: {status} ({elapsed:.1f}s)")

    # Show relevant lines
    for line in lines:
        line = line.strip()
        if any(kw in line for kw in ["Pre-fix", "Post-fix", "Engine result:", "Output:", "Verify report:", "Error:", "calculator.py"]):
            print(f"  {line}")

    if not passed:
        # Show last 15 lines of output for debugging
        print(f"\n  --- Last lines of output ---")
        for line in lines[-15:]:
            print(f"  {line}")

    return {
        "model": model,
        "status": "pass" if passed else "fail",
        "elapsed": elapsed,
        "output_lines": len(lines),
    }


def main():
    print("=" * 60)
    print("FABLEFORGE ANVIL — ALL-MODEL E2E TEST")
    print("=" * 60)

    # Check Ollama is running
    if not check_ollama_model("shellwhisperer-1.5b:latest"):
        print("ERROR: Ollama not running or no models available")
        sys.exit(1)

    results = []

    # Test all models (including aliases)
    all_models = list(MODELS)
    for alias, target in ALIASES.items():
        if alias not in all_models and check_ollama_model(alias):
            all_models.append(alias)

    for model in all_models:
        try:
            r = run_single_model_test(model)
            results.append(r)
        except subprocess.TimeoutExpired:
            print(f"  ✗ TIMEOUT after 600s")
            results.append({"model": model, "status": "timeout", "elapsed": 600})
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            results.append({"model": model, "status": "error", "error": str(e)})

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    pass_count = sum(1 for r in results if r["status"] == "pass")
    fail_count = sum(1 for r in results if r["status"] == "fail")
    skip_count = sum(1 for r in results if r["status"] in ("skipped", "timeout", "error"))

    for r in results:
        icon = {"pass": "✓", "fail": "✗", "skipped": "⚠", "timeout": "⏱", "error": "!"}.get(r["status"], "?")
        elapsed = f" ({r['elapsed']:.1f}s)" if "elapsed" in r else ""
        print(f"  {icon} {r['model']:50s} {r['status']}{elapsed}")

    print(f"\n  Total: {len(results)} | Pass: {pass_count} | Fail: {fail_count} | Skip: {skip_count}")
    print("=" * 60)

    sys.exit(1 if fail_count > 0 else 0)


if __name__ == "__main__":
    main()
