"""Tests for middleware module."""


import pytest

from error_recovery.middleware import ErrorRecovery, ErrorRecoveryMiddleware, ToolCallError
from error_recovery.models import ErrorCategory, ErrorRecoveryConfig, RecoveryResult


class MockAgent:
    def __init__(self, responses=None, should_fail=False):
        self.calls = []
        self.responses = responses or ["ok"]
        self._response_idx = 0
        self.should_fail = should_fail

    def run(self, prompt: str, **kwargs):
        self.calls.append(prompt)
        if self.should_fail:
            raise RuntimeError("Agent execution failed")
        if self._response_idx < len(self.responses):
            resp = self.responses[self._response_idx]
            self._response_idx += 1
            return resp
        return "default response"


class TestErrorRecoveryMiddleware:
    def test_init_default_config(self):
        mw = ErrorRecoveryMiddleware()
        assert mw.config.max_attempts == 3
        assert mw.config.similarity_threshold == 0.8

    def test_init_custom_config(self):
        config = ErrorRecoveryConfig(max_attempts=5, similarity_threshold=0.9)
        mw = ErrorRecoveryMiddleware(config=config)
        assert mw.config.max_attempts == 5
        assert mw.config.similarity_threshold == 0.9

    def test_wrap_tool_call_success(self):
        mw = ErrorRecoveryMiddleware()

        def my_tool(x):
            return x * 2

        wrapped = mw.wrap_tool_call(my_tool, tool_name="doubler")
        result = wrapped(5)
        assert result == 10

    def test_wrap_tool_call_error_recovery(self):
        mw = ErrorRecoveryMiddleware()

        call_count = {"n": 0}

        def failing_tool(x):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise ValueError("command not found: badcmd")
            return x * 2

        wrapped = mw.wrap_tool_call(failing_tool, tool_name="test_tool")
        result = wrapped(5)
        assert result == 10

    def test_wrap_tool_call_persistent_failure(self):
        mw = ErrorRecoveryMiddleware()

        def always_fail(x):
            raise RuntimeError("permanent error permission denied")

        wrapped = mw.wrap_tool_call(always_fail, tool_name="failer")
        with pytest.raises(ToolCallError):
            wrapped(1)

    def test_callback_on_recovery(self):
        recoveries = []
        failures = []
        successes = []

        mw = ErrorRecoveryMiddleware(
            on_recovery=lambda r: recoveries.append(r),
            on_failure=lambda e: failures.append(e),
            on_success=lambda t: successes.append(t),
        )

        def succeed_tool():
            return "ok"

        wrapped = mw.wrap_tool_call(succeed_tool, tool_name="good_tool")
        wrapped()
        assert len(successes) == 1
        assert successes[0] == "good_tool"

    def test_get_trace(self):
        mw = ErrorRecoveryMiddleware()
        trace = mw.get_trace()
        assert trace.total_errors == 0

    def test_stats(self):
        mw = ErrorRecoveryMiddleware()
        stats = mw.stats
        assert "total_recoveries" in stats
        assert "middleware_recoveries" in stats


class TestErrorRecoveryContextManager:
    def test_context_manager_success(self):
        agent = MockAgent(responses=["success"])
        with ErrorRecovery(agent) as mw:
            result = agent.run("do something")
            assert result == "success"

    def test_context_manager_with_error(self):
        agent = MockAgent(should_fail=True)
        try:
            with ErrorRecovery(agent) as mw:
                agent.run("do something")
        except RuntimeError:
            pass

    def test_print_summary_no_error(self):
        agent = MockAgent()
        mw = ErrorRecoveryMiddleware(agent=agent)
        mw.print_summary()


class TestToolCallError:
    def test_creation(self):
        err = ToolCallError("bash", "command not found")
        assert err.tool_name == "bash"
        assert err.error_message == "command not found"
        assert "bash" in str(err)
        assert "command not found" in str(err)


class TestRecoveryResult:
    def test_default_values(self):
        r = RecoveryResult(original_error="test error")
        assert r.original_error == "test error"
        assert r.success is False
        assert r.attempts == 1
        assert r.error_category == ErrorCategory.UNKNOWN

    def test_recovered_property(self):
        r = RecoveryResult(original_error="test", success=True, attempts=2)
        assert r.recovered is True

        r2 = RecoveryResult(original_error="test", success=True, attempts=5)
        assert r2.recovered is False

    def test_failed_recovery(self):
        r = RecoveryResult(original_error="test", success=False, attempts=3)
        assert r.recovered is False


class TestErrorRecoveryConfig:
    def test_default_values(self):
        config = ErrorRecoveryConfig()
        assert config.max_attempts == 3
        assert config.similarity_threshold == 0.8
        assert config.fallback_to_llm is True
        assert config.backoff_base == 2.0
        assert config.top_k == 5

    def test_backoff_calculation(self):
        config = ErrorRecoveryConfig(backoff_base=2.0, backoff_max=30.0)
        b1 = config.backoff_seconds(1)
        b2 = config.backoff_seconds(2)
        b3 = config.backoff_seconds(3)
        assert b1 <= b2 <= b3
        assert b3 <= 30.0

    def test_custom_config(self):
        config = ErrorRecoveryConfig(max_attempts=5, similarity_threshold=0.95, model_name="all-mpnet-base-v2")
        assert config.max_attempts == 5
        assert config.similarity_threshold == 0.95
        assert config.model_name == "all-mpnet-base-v2"


class TestIntegration:
    def test_full_recovery_flow_bash_error(self):
        mw = ErrorRecoveryMiddleware()
        classifier = mw.engine.classifier

        category = classifier.classify("bash: command not found: xyz123", "bash")
        assert category == ErrorCategory.BASH_ERROR

    def test_full_recovery_flow_network_error(self):
        mw = ErrorRecoveryMiddleware()
        classifier = mw.engine.classifier

        category = classifier.classify("Connection refused on port 8080", "fetch")
        assert category == ErrorCategory.NETWORK_ERROR

    def test_pattern_matcher_loaded(self):
        mw = ErrorRecoveryMiddleware()
        assert mw.engine.pattern_matcher.pattern_count > 0

    def test_classify_and_match(self):
        mw = ErrorRecoveryMiddleware()
        result = mw.engine.recover_sync(
            error_message="bash: command not found: nonexistent_cmd",
            tool_name="bash",
        )
        assert result.error_category == ErrorCategory.BASH_ERROR
        assert result.attempts >= 1
        assert len(result.recovery_prompt) > 0

    def test_recover_with_context(self):
        mw = ErrorRecoveryMiddleware()
        result = mw.engine.recover_sync(
            error_message="TypeError: unsupported operand",
            context="Processing user data",
            tool_name="python",
        )
        assert result.error_category == ErrorCategory.TYPE_ERROR

    def test_recovery_multiple_categories(self):
        mw = ErrorRecoveryMiddleware()

        errors = [
            ("command not found: xyz", "bash", ErrorCategory.BASH_ERROR),
            ("assertion failed in test", "pytest", ErrorCategory.TEST_ERROR),
            ("ModuleNotFoundError: no module", "python", ErrorCategory.IMPORT_ERROR),
            ("Connection refused", "fetch", ErrorCategory.NETWORK_ERROR),
        ]

        for error_msg, tool, expected_cat in errors:
            result = mw.engine.recover_sync(error_message=error_msg, tool_name=tool)
            assert result.error_category == expected_cat, f"Expected {expected_cat} for '{error_msg}' got {result.error_category}"
