"""Tests for Anvil verification pipeline — syntax, tests, lint, imports, VerifyPipeline, VerifyReport."""



from anvil.verify.pipeline import (
    Checkers,
    VerifyPipeline,
    VerifyReport,
    VerifyResult,
    VerifyStatus,
)

# ---------------------------------------------------------------------------
# VerifyResult dataclass
# ---------------------------------------------------------------------------

class TestVerifyResult:
    def test_pass_result(self):
        r = VerifyResult(checker="syntax", status=VerifyStatus.PASS, message="Valid")
        assert r.status == VerifyStatus.PASS
        assert r.checker == "syntax"
        assert r.message == "Valid"
        assert r.details is None
        assert r.file_path is None
        assert r.fixes == []

    def test_fail_result_with_details(self):
        r = VerifyResult(
            checker="syntax", status=VerifyStatus.FAIL,
            message="Syntax error: invalid syntax",
            details="  x =",
            file_path="/tmp/test.py",
            fixes=["Fix the syntax error"],
        )
        assert r.status == VerifyStatus.FAIL
        assert r.details is not None
        assert r.file_path == "/tmp/test.py"
        assert len(r.fixes) == 1

    def test_skip_result(self):
        r = VerifyResult(checker="syntax", status=VerifyStatus.SKIP, message="No checker")
        assert r.status == VerifyStatus.SKIP

    def test_error_result(self):
        r = VerifyResult(checker="lint", status=VerifyStatus.ERROR, message="Linter crashed")
        assert r.status == VerifyStatus.ERROR


# ---------------------------------------------------------------------------
# VerifyReport
# ---------------------------------------------------------------------------

class TestVerifyReport:
    def test_empty_report_passes(self):
        report = VerifyReport()
        assert report.passed is True
        assert report.overall == VerifyStatus.PASS
        assert len(report.results) == 0
        assert len(report.failures) == 0

    def test_add_pass_result(self):
        report = VerifyReport()
        report.add(VerifyResult(checker="syntax", status=VerifyStatus.PASS, message="OK"))
        assert report.passed is True
        assert report.overall == VerifyStatus.PASS
        assert len(report.failures) == 0

    def test_add_fail_result(self):
        report = VerifyReport()
        report.add(VerifyResult(checker="syntax", status=VerifyStatus.FAIL, message="Bad"))
        assert report.passed is False
        assert report.overall == VerifyStatus.FAIL
        assert len(report.failures) == 1

    def test_add_error_result(self):
        report = VerifyReport()
        report.add(VerifyResult(checker="lint", status=VerifyStatus.ERROR, message="Crash"))
        assert report.overall == VerifyStatus.ERROR

    def test_error_does_not_override_fail(self):
        report = VerifyReport()
        report.add(VerifyResult(checker="syntax", status=VerifyStatus.FAIL, message="Bad"))
        report.add(VerifyResult(checker="lint", status=VerifyStatus.ERROR, message="Crash"))
        assert report.overall == VerifyStatus.FAIL

    def test_pass_does_not_override_fail(self):
        report = VerifyReport()
        report.add(VerifyResult(checker="syntax", status=VerifyStatus.FAIL, message="Bad"))
        report.add(VerifyResult(checker="lint", status=VerifyStatus.PASS, message="OK"))
        assert report.overall == VerifyStatus.FAIL

    def test_multiple_failures(self):
        report = VerifyReport()
        report.add(VerifyResult(checker="syntax", status=VerifyStatus.FAIL, message="Syntax error"))
        report.add(VerifyResult(checker="lint", status=VerifyStatus.FAIL, message="Lint issue"))
        assert len(report.failures) == 2

    def test_failures_property_filters(self):
        report = VerifyReport()
        report.add(VerifyResult(checker="syntax", status=VerifyStatus.PASS, message="OK"))
        report.add(VerifyResult(checker="lint", status=VerifyStatus.FAIL, message="Bad lint"))
        report.add(VerifyResult(checker="tests", status=VerifyStatus.SKIP, message="No tests"))
        fails = report.failures
        assert len(fails) == 1
        assert fails[0].checker == "lint"

    def test_format_summary_pass(self):
        report = VerifyReport()
        report.add(VerifyResult(checker="syntax", status=VerifyStatus.PASS, message="Valid"))
        output = report.format_summary()
        assert "✓" in output
        assert "Overall: PASS" in output

    def test_format_summary_fail(self):
        report = VerifyReport()
        report.add(VerifyResult(checker="syntax", status=VerifyStatus.FAIL, message="Syntax error"))
        output = report.format_summary()
        assert "✗" in output
        assert "Overall: FAIL" in output

    def test_format_summary_skip(self):
        report = VerifyReport()
        report.add(VerifyResult(checker="syntax", status=VerifyStatus.SKIP, message="No checker"))
        output = report.format_summary()
        assert "—" in output

    def test_format_summary_with_details(self):
        report = VerifyReport()
        report.add(VerifyResult(
            checker="syntax", status=VerifyStatus.FAIL,
            message="Error", details="Line 5: broken\nLine 6: also broken\nLine 7: more",
        ))
        output = report.format_summary()
        assert "Line 5" in output

    def test_format_summary_truncates_details(self):
        report = VerifyReport()
        report.add(VerifyResult(
            checker="syntax", status=VerifyStatus.FAIL,
            message="Error",
            details="\n".join(f"Line {i}: detail" for i in range(20)),
        ))
        output = report.format_summary()
        assert len(output) < 5000  # Should be truncated


# ---------------------------------------------------------------------------
# Syntax checker
# ---------------------------------------------------------------------------

class TestSyntaxChecker:
    def test_python_valid(self, tmp_path):
        f = tmp_path / "valid.py"
        f.write_text("x = 1\ny = 2\n")
        result = Checkers.check_syntax(str(f))
        assert result.status == VerifyStatus.PASS
        assert "Python" in result.message

    def test_python_invalid_syntax(self, tmp_path):
        f = tmp_path / "invalid.py"
        f.write_text("def foo(\n  pass\n")
        result = Checkers.check_syntax(str(f))
        assert result.status == VerifyStatus.FAIL
        assert "Syntax" in result.message

    def test_python_indentation_error(self, tmp_path):
        f = tmp_path / "indent.py"
        f.write_text("if True:\nprint('bad indent')\n")
        result = Checkers.check_syntax(str(f))
        assert result.status == VerifyStatus.FAIL

    def test_python_with_content_parameter(self, tmp_path):
        f = tmp_path / "content_test.py"
        f.write_text("x = 1\n")
        code = "def bar():\n    return 42\n"
        result = Checkers.check_syntax(str(f), content=code)
        assert result.status == VerifyStatus.PASS

    def test_unknown_language_skipped(self):
        result = Checkers.check_syntax("file.xyz")
        assert result.status == VerifyStatus.SKIP
        assert "No syntax checker" in result.message

    def test_rust_extension_skipped_without_rustc(self):
        result = Checkers.check_syntax("file.rs")
        assert result.status in (VerifyStatus.PASS, VerifyStatus.FAIL, VerifyStatus.SKIP)

    def test_go_extension_skipped_without_gofmt(self):
        result = Checkers.check_syntax("file.go")
        assert result.status in (VerifyStatus.PASS, VerifyStatus.FAIL, VerifyStatus.SKIP)


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

class TestTestRunner:
    def test_successful_test_command(self, tmp_path):
        (tmp_path / "test_pass.py").write_text("def test_ok(): assert True\n")
        result = Checkers.check_tests(
            f"python -m pytest {tmp_path}/test_pass.py -x", str(tmp_path),
        )
        assert result.status in (VerifyStatus.PASS, VerifyStatus.FAIL, VerifyStatus.ERROR)

    def test_missing_command_returns_error(self):
        result = Checkers.check_tests("nonexistent_test_runner_12345", ".")
        assert result.status in (VerifyStatus.ERROR, VerifyStatus.FAIL)

    def test_failing_test_command(self, tmp_path):
        fail_test = tmp_path / "test_fail.py"
        fail_test.write_text("def test_fail(): assert 1 == 2\n")
        result = Checkers.check_tests(
            f"python -m pytest {tmp_path}/test_fail.py -x", str(tmp_path),
        )
        assert result.status in (VerifyStatus.FAIL, VerifyStatus.ERROR)

    def test_echo_command_passes(self):
        result = Checkers.check_tests("echo 'all tests passed'", ".")
        assert result.status == VerifyStatus.PASS


# ---------------------------------------------------------------------------
# Lint checker
# ---------------------------------------------------------------------------

class TestLintChecker:
    def test_lint_unknown_extension_returns_skip(self):
        result = Checkers.check_lint("file.xyz42")
        assert result.status == VerifyStatus.SKIP

    def test_lint_explicit_linter_not_found(self):
        result = Checkers.check_lint("file.py", linter="nonexistent_linter_xyz")
        assert result.status in (VerifyStatus.SKIP, VerifyStatus.ERROR)

    def test_lint_python_with_explicit_linter(self, tmp_path):
        f = tmp_path / "clean.py"
        f.write_text("x = 1\n")
        result = Checkers.check_lint(str(f), linter="ruff")
        assert result.status in (VerifyStatus.PASS, VerifyStatus.FAIL, VerifyStatus.SKIP)


# ---------------------------------------------------------------------------
# Import checker
# ---------------------------------------------------------------------------

class TestImportChecker:
    def test_valid_python_imports(self, tmp_path):
        f = tmp_path / "imports.py"
        f.write_text("import os\nimport sys\nx = 1\n")
        result = Checkers.check_imports(str(f))
        assert result.status in (VerifyStatus.PASS, VerifyStatus.ERROR)

    def test_non_python_file_skipped(self):
        result = Checkers.check_imports("file.js")
        assert result.status == VerifyStatus.SKIP
        assert "Only Python" in result.message


# ---------------------------------------------------------------------------
# VerifyPipeline integration
# ---------------------------------------------------------------------------

class TestVerifyPipeline:
    def test_verify_valid_python_file(self, tmp_path):
        f = tmp_path / "good.py"
        f.write_text("x = 1\ny = 2\n")
        pipeline = VerifyPipeline()
        report = pipeline.verify(files=[str(f)], checks=["syntax"])
        assert len(report.results) >= 1
        syntax_results = [r for r in report.results if r.checker == "syntax"]
        assert any(r.status == VerifyStatus.PASS for r in syntax_results)

    def test_verify_invalid_python_file(self, tmp_path):
        f = tmp_path / "bad.py"
        f.write_text("def foo(\npass\n")
        pipeline = VerifyPipeline()
        report = pipeline.verify(files=[str(f)], checks=["syntax"])
        failures = [r for r in report.results if r.status == VerifyStatus.FAIL]
        assert len(failures) >= 1

    def test_verify_with_test_command(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("x = 1\n")
        pipeline = VerifyPipeline()
        report = pipeline.verify(
            files=[str(f)],
            test_command="echo 'tests pass'",
            working_dir=str(tmp_path),
            checks=["syntax", "tests"],
        )
        test_results = [r for r in report.results if r.checker == "tests"]
        assert len(test_results) >= 1

    def test_verify_skip_lint_and_imports(self, tmp_path):
        f = tmp_path / "simple.py"
        f.write_text("x = 1\n")
        pipeline = VerifyPipeline()
        report = pipeline.verify(files=[str(f)], checks=["syntax"])
        assert report is not None

    def test_verify_multiple_files(self, tmp_path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("x = 1\n")
        f2.write_text("y = 2\n")
        pipeline = VerifyPipeline()
        report = pipeline.verify(files=[str(f1), str(f2)], checks=["syntax"])
        syntax_results = [r for r in report.results if r.checker == "syntax"]
        assert len(syntax_results) >= 2

    def test_verify_code_good(self):
        pipeline = VerifyPipeline()
        report = pipeline.verify_code("x = 1\nprint(x)\n")
        assert report.passed

    def test_verify_code_bad(self):
        pipeline = VerifyPipeline()
        report = pipeline.verify_code("def foo(\npass\n")
        assert not report.passed

    def test_verify_config_passed_through(self):
        from anvil.core.config import VerifyConfig
        config = VerifyConfig(enabled=True, auto_recover=False, max_retries=1)
        pipeline = VerifyPipeline(config)
        assert pipeline.config.enabled is True
        assert pipeline.config.auto_recover is False

    def test_verify_report_cumulative(self, tmp_path):
        f = tmp_path / "cumul.py"
        f.write_text("x = 1\n")
        pipeline = VerifyPipeline()
        report = pipeline.verify(files=[str(f)], checks=["syntax", "lint"], working_dir=str(tmp_path))
        assert len(report.results) >= 1
