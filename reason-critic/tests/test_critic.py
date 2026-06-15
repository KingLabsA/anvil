"""Unit tests for ReasonCritic."""

import json
from unittest.mock import patch

import pytest

from reason_critic.critic import (
    LocalBackend,
    ReasonCritic,
    RunVerification,
    StepVerification,
    Verdict,
    VerificationResult,
    _build_prompt,
    _detect_language,
    _parse_output,
)
from reason_critic.data_prep import (
    ContrastivePair,
    VerificationExample,
    _apply_bug,
    create_contrastive_pairs,
    examples_to_dataset,
    extract_verification_pairs,
    format_contrastive_prompt,
    format_training_prompt,
    generate_incorrect_versions,
    pairs_to_dataset,
)
from reason_critic.pipeline import (
    GenerationAttempt,
    VerifiedResult,
    _extract_code,
)

# ===== VerificationResult =====

class TestVerificationResult:
    def test_pass_result(self):
        result = VerificationResult(
            pass_fail="PASS",
            confidence=0.95,
            issues=[],
            suggestions=[],
            explanation="Code is correct",
        )
        assert result.is_pass is True
        assert result.pass_fail == "PASS"

    def test_fail_result(self):
        result = VerificationResult(
            pass_fail="FAIL",
            confidence=0.8,
            issues=["Off-by-one error"],
            suggestions=["Fix the loop bound"],
        )
        assert result.is_pass is False
        assert result.pass_fail == "FAIL"

    def test_to_dict(self):
        result = VerificationResult(
            pass_fail="PASS",
            confidence=0.9,
            issues=[],
            suggestions=[],
            explanation="Looks good",
            language="python",
        )
        d = result.to_dict()
        assert d["pass_fail"] == "PASS"
        assert d["confidence"] == 0.9
        assert d["language"] == "python"

    def test_to_json(self):
        result = VerificationResult(
            pass_fail="FAIL",
            confidence=0.7,
            issues=["bug1"],
            suggestions=["fix1"],
        )
        j = result.to_json()
        parsed = json.loads(j)
        assert parsed["pass_fail"] == "FAIL"


class TestStepVerification:
    def test_step_verification(self):
        result = VerificationResult(pass_fail="PASS", confidence=0.9, issues=[], suggestions=[])
        sv = StepVerification(
            step_index=0,
            step_type="generation",
            step_name="write_code",
            result=result,
        )
        d = sv.to_dict()
        assert d["step_index"] == 0
        assert d["step_type"] == "generation"

    def test_step_verification_fail(self):
        result = VerificationResult(
            pass_fail="FAIL",
            confidence=0.8,
            issues=["null dereference"],
            suggestions=["add None check"],
        )
        sv = StepVerification(step_index=3, step_type="test", result=result)
        d = sv.to_dict()
        assert d["result"]["pass_fail"] == "FAIL"


class TestRunVerification:
    def test_run_verification_pass(self):
        results = [
            StepVerification(step_index=0, step_type="gen", result=VerificationResult(pass_fail="PASS", confidence=0.9, issues=[], suggestions=[])),
            StepVerification(step_index=1, step_type="gen", result=VerificationResult(pass_fail="PASS", confidence=0.85, issues=[], suggestions=[])),
        ]
        rv = RunVerification(
            run_id="test-1",
            step_verifications=results,
            overall_verdict="PASS",
            overall_confidence=0.875,
            summary="2/2 steps passed",
        )
        assert rv.num_passed == 2
        assert rv.num_failed == 0

    def test_run_verification_mixed(self):
        results = [
            StepVerification(step_index=0, step_type="gen", result=VerificationResult(pass_fail="PASS", confidence=0.9, issues=[], suggestions=[])),
            StepVerification(step_index=1, step_type="gen", result=VerificationResult(pass_fail="FAIL", confidence=0.7, issues=["bug"], suggestions=["fix"])),
        ]
        rv = RunVerification(
            run_id="test-2",
            step_verifications=results,
            overall_verdict="FAIL",
            overall_confidence=0.8,
        )
        assert rv.num_passed == 1
        assert rv.num_failed == 1

    def test_run_empty(self):
        rv = RunVerification(
            run_id="empty",
            step_verifications=[],
            overall_verdict="FAIL",
            overall_confidence=1.0,
            summary="No steps found",
        )
        assert rv.num_passed == 0
        assert rv.num_failed == 0

    def test_run_to_json(self):
        results = [
            StepVerification(step_index=0, step_type="gen", result=VerificationResult(pass_fail="PASS", confidence=0.95, issues=[], suggestions=[])),
        ]
        rv = RunVerification(
            run_id="json-test",
            step_verifications=results,
            overall_verdict="PASS",
            overall_confidence=0.95,
            summary="All passed",
        )
        j = rv.to_json()
        parsed = json.loads(j)
        assert parsed["run_id"] == "json-test"


# ===== Parse Output =====

class TestParseOutput:
    def test_parse_pass(self):
        output = "VERDICT: PASS\nCONFIDENCE: 0.95\nISSUES: none\nSUGGESTIONS: none\nEXPLANATION: Code looks correct."
        result = _parse_output(output, "python")
        assert result.pass_fail == "PASS"
        assert result.confidence == 0.95
        assert result.issues == []

    def test_parse_fail(self):
        output = "VERDICT: FAIL\nCONFIDENCE: 0.8\nISSUES: off-by-one error, missing None check\nSUGGESTIONS: fix loop bound, add None check\nEXPLANATION: Two issues found."
        result = _parse_output(output, "python")
        assert result.pass_fail == "FAIL"
        assert result.confidence == 0.8
        assert len(result.issues) == 2
        assert len(result.suggestions) == 2

    def test_parse_case_insensitive(self):
        output = "verdict: pass\nconfidence: 0.9\nissues: none\nsuggestions: none\nexplanation: OK"
        result = _parse_output(output)
        assert result.pass_fail == "PASS"

    def test_parse_clamped_confidence(self):
        output = "VERDICT: PASS\nCONFIDENCE: 1.5\nISSUES: none"
        result = _parse_output(output)
        assert result.confidence == 1.0

    def test_parse_no_issues_text(self):
        output = "VERDICT: PASS\nCONFIDENCE: 0.9\nISSUES: N/A\nSUGGESTIONS: N/A\nEXPLANATION: Fine"
        result = _parse_output(output)
        assert result.issues == []
        assert result.suggestions == []


# ===== Build Prompt =====

class TestBuildPrompt:
    def test_basic_prompt(self):
        prompt = _build_prompt("def add(a, b): return a + b", "", "python")
        assert "def add(a, b): return a + b" in prompt
        assert "python" in prompt
        assert "VERDICT" in prompt

    def test_prompt_with_context(self):
        prompt = _build_prompt("x = 1", "This is a test function", "python")
        assert "Context: This is a test function" in prompt


# ===== Detect Language =====

class TestDetectLanguage:
    def test_python(self):
        assert _detect_language("def foo(): pass") == "python"
        assert _detect_language("import os") == "python"

    def test_javascript(self):
        assert _detect_language("function foo() { return 1; }") == "javascript"
        assert _detect_language("const x = 1;") == "javascript"

    def test_rust(self):
        assert _detect_language("fn main() { let x = 1; }") == "rust"

    def test_go(self):
        assert _detect_language("package main\nfunc main() {}") == "go"

    def test_default(self):
        assert _detect_language("x = 1") == "python"


# ===== Data Prep =====

class TestExtractVerificationPairs:
    def test_extract_pass_fail(self):
        traces = [
            {
                "steps": [
                    {"type": "verification", "code": "x = 1", "result": "pass", "explanation": "Variable assignment is correct"},
                    {"type": "generation", "code": "y = 2", "result": "success"},
                    {"type": "verification", "code": "def bad(): return", "result": "fail", "explanation": "Missing return value"},
                ]
            }
        ]
        examples = extract_verification_pairs(traces)
        assert len(examples) == 2
        assert examples[0].label == "PASS"
        assert examples[1].label == "FAIL"

    def test_extract_with_outcome_field(self):
        traces = [
            {
                "steps": [
                    {"type": "verification", "content": "x += 1", "outcome": "success", "explanation": "Increment is fine"},
                ]
            }
        ]
        examples = extract_verification_pairs(traces)
        assert len(examples) == 1
        assert examples[0].label == "PASS"

    def test_extract_unknown_filtered(self):
        traces = [
            {
                "steps": [
                    {"type": "verification", "code": "x = 1", "result": "inconclusive"},
                ]
            }
        ]
        examples = extract_verification_pairs(traces)
        assert len(examples) == 0

    def test_extract_boolean_result(self):
        traces = [
            {
                "steps": [
                    {"type": "verification", "code": "def ok(): pass", "result": True},
                    {"type": "verification", "code": "def bad(): 1/0", "result": False},
                ]
            }
        ]
        examples = extract_verification_pairs(traces)
        assert len(examples) == 2
        assert examples[0].label == "PASS"
        assert examples[1].label == "FAIL"

    def test_extract_with_issues_and_suggestions(self):
        traces = [
            {
                "steps": [
                    {"type": "verification", "code": "x = 1 / 0", "result": "fail",
                     "issues": ["division by zero"], "suggestions": ["add zero check"],
                     "explanation": "Will crash"},
                ]
            }
        ]
        examples = extract_verification_pairs(traces)
        assert len(examples) == 1
        assert examples[0].issues == ["division by zero"]
        assert examples[0].suggestions == ["add zero check"]


class TestGenerateIncorrectVersions:
    def test_off_by_one(self):
        code = "for i in range(10):\n    print(i)"
        versions = generate_incorrect_versions(code, num_versions=1, bug_types=["off_by_one"])
        assert len(versions) >= 1
        assert versions[0]["bug_type"] == "off_by_one"

    def test_wrong_operator(self):
        code = "if x == y:\n    return True"
        versions = generate_incorrect_versions(code, num_versions=1, bug_types=["wrong_operator"])
        assert len(versions) >= 1

    def test_forgotten_await(self):
        code = "result = await fetch_data()"
        versions = generate_incorrect_versions(code, num_versions=1, bug_types=["forgotten_await"])
        assert len(versions) >= 1
        assert "await" not in versions[0]["code"]

    def test_mutable_default(self):
        code = "def append(item, dest=[]):\n    dest.append(item)\n    return dest"
        versions = generate_incorrect_versions(code, num_versions=1, bug_types=["mutable_default"])
        assert len(versions) >= 1

    def test_num_versions_cap(self):
        code = "x = 1\ny = 2\nz = 3"
        versions = generate_incorrect_versions(code, num_versions=10)
        assert len(versions) <= 10


class TestCreateContrastivePairs:
    def test_with_incorrect_provided(self):
        pair = create_contrastive_pairs("def add(a, b): return a + b", "def add(a, b): return a - b")
        assert pair.correct_code == "def add(a, b): return a + b"
        assert pair.incorrect_code == "def add(a, b): return a - b"
        assert pair.bug_type == "provided"

    def test_with_incorrect_generated(self):
        code = "for i in range(10):\n    print(i)"
        pair = create_contrastive_pairs(code)
        assert pair.correct_code == code
        assert pair.incorrect_code != code


class TestFormatFunctions:
    def test_format_training_prompt(self):
        example = VerificationExample(
            prompt="Verify this code:",
            code="x = 1",
            label="PASS",
            explanation="Simple assignment",
        )
        prompt = format_training_prompt(example)
        assert "Verify this code:" in prompt
        assert "x = 1" in prompt
        assert "PASS" in prompt

    def test_format_contrastive_prompt(self):
        pair = ContrastivePair(
            correct_code="x = 1",
            incorrect_code="x = 2",
            explanation="Wrong value",
            bug_type="wrong_value",
            language="python",
        )
        prompts = format_contrastive_prompt(pair)
        assert "preferred" in prompts
        assert "dispreferred" in prompts
        assert "x = 1" in prompts["preferred"]
        assert "x = 2" in prompts["dispreferred"]


class TestDatasetConversion:
    def test_examples_to_dataset(self):
        examples = [
            VerificationExample(prompt="Verify:", code="x=1", label="PASS", explanation="OK"),
            VerificationExample(prompt="Verify:", code="x=1/0", label="FAIL", explanation="div by zero", issues=["division by zero"]),
        ]
        ds = examples_to_dataset(examples)
        assert len(ds) == 2
        assert ds[0]["label"] == "PASS"

    def test_pairs_to_dataset(self):
        pairs = [
            ContrastivePair(correct_code="x=1", incorrect_code="x=2", explanation="typo", bug_type="typo", language="python"),
        ]
        ds = pairs_to_dataset(pairs)
        assert len(ds) == 1
        assert ds[0]["preferred"] == "x=1"
        assert ds[0]["dispreferred"] == "x=2"


# ===== Bug Application =====

class TestApplyBug:
    def test_off_by_one(self):
        code = "for i in range(10):\n    print(i)"
        result = _apply_bug(code, "off_by_one")
        assert result is not None
        assert "range(9)" in result

    def test_wrong_operator(self):
        code = "if x == y:\n    return True"
        result = _apply_bug(code, "wrong_operator")
        assert result is not None
        assert "!=" in result or " <= " in result

    def test_forgotten_await(self):
        code = "result = await fetch()"
        result = _apply_bug(code, "forgotten_await")
        assert result is not None
        assert "await" not in result

    def test_mutable_default(self):
        code = "def f(x=[]):\n    return x"
        result = _apply_bug(code, "mutable_default")
        assert result is not None
        assert "= None" in result

    def test_apply_bug_none_when_no_match(self):
        code = "pass"
        result = _apply_bug(code, "off_by_one")
        # No range() to modify
        # Should return None


# ===== ReasonCritic =====

class TestReasonCritic:
    def test_init_local(self):
        critic = ReasonCritic(backend="local", model_name="test-model")
        assert critic.backend_name == "local"
        assert critic.model_name == "test-model"

    def test_init_api(self):
        critic = ReasonCritic(backend="api", model_name="test", api_endpoint="http://localhost:8000")
        assert critic.backend_name == "api"

    def test_init_api_no_endpoint(self):
        with pytest.raises(ValueError, match="api_endpoint required"):
            ReasonCritic(backend="api", model_name="test")

    def test_init_invalid_backend(self):
        with pytest.raises(ValueError, match="Unknown backend"):
            ReasonCritic(backend="invalid")

    def test_verify_empty_code(self):
        critic = ReasonCritic(backend="local", model_name="test")
        result = critic.verify(code="")
        assert result.pass_fail == "FAIL"
        assert "Empty code" in result.issues[0]

    def test_verify_whitespace_code(self):
        critic = ReasonCritic(backend="local", model_name="test")
        result = critic.verify(code="   \n  ")
        assert result.pass_fail == "FAIL"

    @patch.object(LocalBackend, 'verify')
    def test_verify_with_mock(self, mock_verify):
        mock_verify.return_value = VerificationResult(
            pass_fail="PASS", confidence=0.95, issues=[], suggestions=[], explanation="OK",
        )
        critic = ReasonCritic(backend="local", model_name="test")
        result = critic.verify("def add(a, b): return a + b")
        assert result.pass_fail == "PASS"
        mock_verify.assert_called_once()

    @patch.object(LocalBackend, 'verify')
    def test_verify_step(self, mock_verify):
        mock_verify.return_value = VerificationResult(
            pass_fail="PASS", confidence=0.9, issues=[], suggestions=[],
        )
        critic = ReasonCritic(backend="local", model_name="test")
        step = {"index": 2, "type": "generation", "code": "x = 1", "name": "assign"}
        sv = critic.verify_step(step, context="test context")
        assert sv.step_index == 2
        assert sv.step_type == "generation"
        assert sv.result.pass_fail == "PASS"

    @patch.object(LocalBackend, 'verify')
    def test_verify_run(self, mock_verify):
        mock_verify.return_value = VerificationResult(
            pass_fail="PASS", confidence=0.9, issues=[], suggestions=[],
        )
        critic = ReasonCritic(backend="local", model_name="test")
        run = {"id": "run-1", "steps": [
            {"index": 0, "type": "generation", "code": "x = 1"},
            {"index": 1, "type": "test", "code": "assert x == 1"},
        ]}
        rv = critic.verify_run(run)
        assert rv.run_id == "run-1"
        assert rv.num_passed == 2
        assert rv.num_failed == 0
        assert rv.overall_verdict == "PASS"

    @patch.object(LocalBackend, 'verify')
    def test_verify_run_empty(self, mock_verify):
        critic = ReasonCritic(backend="local", model_name="test")
        rv = critic.verify_run({"id": "empty", "steps": []})
        assert rv.overall_verdict == "FAIL"
        assert "No steps" in rv.summary

    @patch.object(LocalBackend, 'batch_verify')
    def test_batch_verify(self, mock_batch):
        mock_batch.return_value = [
            VerificationResult(pass_fail="PASS", confidence=0.9, issues=[], suggestions=[]),
            VerificationResult(pass_fail="FAIL", confidence=0.8, issues=["bug"], suggestions=["fix"]),
        ]
        critic = ReasonCritic(backend="local", model_name="test")
        items = [{"code": "x=1"}, {"code": "x=1/0"}]
        results = critic.batch_verify(items)
        assert len(results) == 2


# ===== Pipeline =====

class TestExtractCode:
    def test_extract_from_fences(self):
        text = "Here's the code:\n```python\nx = 1\n```\nDone."
        assert _extract_code(text) == "x = 1"

    def test_extract_no_fences(self):
        text = "x = 1"
        assert _extract_code(text) == "x = 1"

    def test_extract_language_fences(self):
        text = "```js\nconst x = 1;\n```"
        assert _extract_code(text) == "const x = 1;"


class TestVerifiedResult:
    def test_to_dict(self):
        attempt = GenerationAttempt(
            attempt_number=1,
            code="x = 1",
            verification=VerificationResult(pass_fail="PASS", confidence=0.95, issues=[], suggestions=[]),
            timestamp="2024-01-01T00:00:00",
        )
        result = VerifiedResult(
            task="test",
            attempts=[attempt],
            final_code="x = 1",
            final_verification=VerificationResult(pass_fail="PASS", confidence=0.95, issues=[], suggestions=[]),
            passed=True,
            total_attempts=1,
        )
        d = result.to_dict()
        assert d["task"] == "test"
        assert d["passed"] is True
        assert d["total_attempts"] == 1

    def test_to_json(self):
        result = VerifiedResult(
            task="test",
            attempts=[],
            final_code="x=1",
            final_verification=VerificationResult(pass_fail="FAIL", confidence=0.5, issues=["bug"], suggestions=[]),
            passed=False,
            total_attempts=3,
        )
        j = result.to_json()
        parsed = json.loads(j)
        assert parsed["passed"] is False


# ===== Verdict Enum =====

class TestVerdict:
    def test_verdict_values(self):
        assert Verdict.PASS == "PASS"
        assert Verdict.FAIL == "FAIL"

    def test_verdict_comparison(self):
        assert Verdict.PASS == "PASS"
        assert Verdict.FAIL == "FAIL"


# ===== Benchmarks =====

class TestBenchmarks:
    def _load_benchmark(self, path):
        import pathlib
        p = pathlib.Path(path)
        if p.exists():
            return json.loads(p.read_text())
        return []

    def test_code_correctness_tasks_exist(self):
        tasks = self._load_benchmark(
            "/tmp/fableforge/reason-critic/src/reason_critic/benchmarks/code_correctness/tasks.json"
        )
        assert len(tasks) == 50
        for t in tasks:
            assert "correct_code" in t
            assert "buggy_code" in t
            assert "bug_type" in t

    def test_security_issues_tasks_exist(self):
        tasks = self._load_benchmark(
            "/tmp/fableforge/reason-critic/src/reason_critic/benchmarks/security_issues/tasks.json"
        )
        assert len(tasks) == 30
        for t in tasks:
            assert "vulnerable" in t
            assert "secure" in t
            assert "bug_type" in t

    def test_logic_errors_tasks_exist(self):
        tasks = self._load_benchmark(
            "/tmp/fableforge/reason-critic/src/reason_critic/benchmarks/logic_errors/tasks.json"
        )
        assert len(tasks) == 30
        for t in tasks:
            assert "buggy" in t
            assert "correct" in t
            assert "bug_type" in t

    def test_style_issues_tasks_exist(self):
        tasks = self._load_benchmark(
            "/tmp/fableforge/reason-critic/src/reason_critic/benchmarks/style_issues/tasks.json"
        )
        assert len(tasks) == 20
        for t in tasks:
            assert "code" in t
            assert "expected_issues" in t


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
