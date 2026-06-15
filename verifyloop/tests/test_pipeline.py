"""Tests for the VerifyLoop pipeline."""


import pytest

from verifyloop.executor import Executor
from verifyloop.memory import ConversationContext, FileStore, InMemoryStore
from verifyloop.models import (
    AgentRun,
    ExecuteStep,
    PipelineConfig,
    RecoverStep,
    Step,
    StepType,
    TokenUsage,
)
from verifyloop.planner import PlanGenerator
from verifyloop.recoverer import Recoverer
from verifyloop.verifier import Verifier, VerifierConfig


class TestModels:
    def test_step_creation(self):
        step = Step(step_type=StepType.PLAN, content="test", confidence=0.9)
        assert step.step_type == StepType.PLAN
        assert step.content == "test"
        assert step.confidence == 0.9

    def test_execute_step_failed_property(self):
        step = ExecuteStep(tool="bash", arguments={}, result="", success=False)
        assert step.failed is True

    def test_execute_step_not_failed(self):
        step = ExecuteStep(tool="bash", arguments={}, result="ok", success=True)
        assert step.failed is False

    def test_recover_step_exhausted(self):
        step = RecoverStep(
            original_error="test",
            recovery_attempt="retry",
            attempt_number=3,
            max_attempts=3,
            success=False,
        )
        assert step.exhausted is True

    def test_recover_step_not_exhausted(self):
        step = RecoverStep(
            original_error="test",
            recovery_attempt="retry",
            attempt_number=1,
            max_attempts=3,
            success=False,
        )
        assert step.exhausted is False

    def test_recover_step_success_not_exhausted(self):
        step = RecoverStep(
            original_error="test",
            recovery_attempt="fixed",
            attempt_number=3,
            max_attempts=3,
            success=True,
        )
        assert step.exhausted is False

    def test_agent_run_elapsed(self):
        run = AgentRun(task="test task")
        elapsed = run.elapsed()
        assert elapsed >= 0

    def test_agent_run_add_step(self):
        run = AgentRun(task="test")
        step = Step(step_type=StepType.EXECUTE, content="ran bash", confidence=1.0)
        run.add_step(step)
        assert len(run.steps) == 1
        assert run.steps[0].step_type == StepType.EXECUTE

    def test_token_usage_merge(self):
        a = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        b = TokenUsage(prompt_tokens=20, completion_tokens=10, total_tokens=30)
        merged = a.merge(b)
        assert merged.prompt_tokens == 30
        assert merged.completion_tokens == 15
        assert merged.total_tokens == 45


class TestPlanGenerator:
    def test_decompose_task_edit(self):
        planner = PlanGenerator(model="gpt-4o")
        substeps = planner.decompose_task("add auth to app.py")
        assert len(substeps) == 1
        assert substeps[0].tool == "edit"
        assert "app.py" in substeps[0].arguments.get("file_path", "")

    def test_decompose_task_read(self):
        planner = PlanGenerator(model="gpt-4o")
        substeps = planner.decompose_task("read config.yaml")
        assert len(substeps) == 1
        assert substeps[0].tool == "read"

    def test_decompose_task_create(self):
        planner = PlanGenerator(model="gpt-4o")
        substeps = planner.decompose_task("create a main.py")
        assert len(substeps) >= 1

    def test_estimate_tools(self):
        planner = PlanGenerator(model="gpt-4o")
        tools = planner.estimate_tools("fix the bug in app.py and run tests")
        assert "edit" in tools
        assert "bash" in tools

    def test_fallback_plan(self):
        planner = PlanGenerator(model="gpt-4o")
        plan = planner._fallback_plan("do something")
        assert plan.description == "do something"
        assert len(plan.substeps) >= 1


class TestExecutor:
    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        executor = Executor()
        result = await executor.execute("unknown_tool", {})
        assert result.success is False
        assert "Unknown tool" in result.error

    @pytest.mark.asyncio
    async def test_bash_simple_command(self, tmp_path):
        executor = Executor(working_dir=str(tmp_path))
        result = await executor.bash("echo 'hello world'")
        assert result.success is True
        assert "hello world" in result.result

    @pytest.mark.asyncio
    async def test_bash_failing_command(self, tmp_path):
        executor = Executor(working_dir=str(tmp_path))
        result = await executor.bash("exit 1")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_write_and_read_file(self, tmp_path):
        executor = Executor(working_dir=str(tmp_path))
        write_result = await executor.write("test_file.txt", "Hello, VerifyLoop!")
        assert write_result.success is True

        read_result = await executor.read("test_file.txt")
        assert read_result.success is True
        assert "Hello, VerifyLoop!" in read_result.result

    @pytest.mark.asyncio
    async def test_edit_file(self, tmp_path):
        executor = Executor(working_dir=str(tmp_path))

        await executor.write("edit_test.py", "def hello():\n    return 'hello'\n")

        result = await executor.edit(
            "edit_test.py",
            old_content="'hello'",
            new_content="'goodbye'",
        )
        assert result.success is True

        read_back = await executor.read("edit_test.py")
        assert "goodbye" in read_back.result

    @pytest.mark.asyncio
    async def test_edit_missing_old_content(self, tmp_path):
        executor = Executor(working_dir=str(tmp_path))
        await executor.write("edit_missing.py", "original content")

        result = await executor.edit(
            "edit_missing.py",
            old_content="not found in file",
            new_content="replacement",
        )
        assert result.success is False

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, tmp_path):
        executor = Executor(working_dir=str(tmp_path))
        result = await executor.read("nonexistent_file.txt")
        assert result.success is False
        assert "not found" in result.error.lower() or "No such file" in result.error

    @pytest.mark.asyncio
    async def test_file_history(self, tmp_path):
        executor = Executor(working_dir=str(tmp_path))
        await executor.write("history_test.txt", "version 1")
        await executor.edit("history_test.txt", "version 1", "version 2")

        history = executor.get_file_history(str(tmp_path / "history_test.txt"))
        assert len(history) == 1
        assert "version 1" in history[0]

    @pytest.mark.asyncio
    async def test_rollback_file(self, tmp_path):
        executor = Executor(working_dir=str(tmp_path))
        await executor.write("rollback_test.txt", "original")

        # Make an edit (which stores history)
        await executor.edit("rollback_test.txt", "original", "modified")

        # Rollback
        result = executor.rollback_file(str(tmp_path / "rollback_test.txt"))
        assert result is True

        # Verify rollback
        read_result = await executor.read("rollback_test.txt")
        assert "original" in read_result.result


class TestRecoverer:
    def test_should_retry_syntax_error(self):
        recoverer = Recoverer(max_recovery_attempts=3)
        assert recoverer.should_retry("SyntaxError: invalid syntax", attempt=1) is True

    def test_should_retry_exhausted(self):
        recoverer = Recoverer(max_recovery_attempts=3)
        assert recoverer.should_retry("some error", attempt=3) is False

    def test_pattern_matching_syntax_error(self):
        recoverer = Recoverer()
        result = recoverer._match_pattern_recovery("SyntaxError: invalid syntax at line 5")
        assert result is not None
        assert result.recovery_type == "edit"

    def test_pattern_matching_file_not_found(self):
        recoverer = Recoverer()
        result = recoverer._match_pattern_recovery("FileNotFoundError: [Errno 2] No such file")
        assert result is not None
        assert result.recovery_type == "create"

    def test_pattern_matching_timeout(self):
        recoverer = Recoverer()
        result = recoverer._match_pattern_recovery("TimeoutError: command timed out after 30s")
        assert result is not None
        assert result.recovery_type == "simplify"

    def test_no_pattern_match(self):
        recoverer = Recoverer()
        result = recoverer._match_pattern_recovery("Some unknown error occurred")
        assert result is None

    @pytest.mark.asyncio
    async def test_recover_max_attempts(self):
        recoverer = Recoverer(max_recovery_attempts=2)
        result = await recoverer.recover("some error", attempt=3)
        assert result.exhausted or "Max recovery" in result.recovery_attempt


class TestMemory:
    @pytest.mark.asyncio
    async def test_in_memory_store(self):
        store = InMemoryStore()
        await store.store("key1", "value1", namespace="test")
        result = await store.retrieve("key1", namespace="test")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_in_memory_store_missing(self):
        store = InMemoryStore()
        result = await store.retrieve("nonexistent", namespace="test")
        assert result is None

    @pytest.mark.asyncio
    async def test_in_memory_search(self):
        store = InMemoryStore()
        await store.store("hello world", "data1")
        await store.store("goodbye world", "data2")
        results = await store.search("world")
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_in_memory_delete(self):
        store = InMemoryStore()
        await store.store("key1", "value1")
        assert await store.delete("key1") is True
        assert await store.retrieve("key1") is None

    @pytest.mark.asyncio
    async def test_in_memory_list_keys(self):
        store = InMemoryStore()
        await store.store("a", 1)
        await store.store("b", 2)
        keys = await store.list_keys()
        assert len(keys) == 2
        assert "a" in keys

    @pytest.mark.asyncio
    async def test_file_store(self, tmp_path):
        store = FileStore(base_dir=str(tmp_path / "mem"))
        await store.store("key1", {"nested": "data"})
        result = await store.retrieve("key1")
        assert result == {"nested": "data"}

    @pytest.mark.asyncio
    async def test_conversation_context(self):
        ctx = ConversationContext()
        ctx.add_message("user", "Fix the bug")
        ctx.add_message("assistant", "I'll fix it")

        messages = ctx.get_messages()
        assert len(messages) == 2

    @pytest.mark.asyncio
    async def test_conversation_file_context(self):
        ctx = ConversationContext()
        ctx.add_file_context("app.py", "def hello(): pass")
        assert ctx.get_file_context("app.py") == "def hello(): pass"
        assert "app.py" in ctx.get_all_file_paths()

    def test_conversation_context_string(self):
        ctx = ConversationContext()
        ctx.add_message("user", "Fix the bug in main.py")
        ctx.add_file_context("main.py", "def broken():\n  return 1/0")

        context_str = ctx.build_context_string()
        assert "Fix the bug" in context_str
        assert "broken" in context_str


class TestVerifierLocal:
    @pytest.mark.asyncio
    async def test_verify_file_exists(self, tmp_path):
        verifier = Verifier(VerifierConfig(prefer_trained_model=False))
        (tmp_path / "exists.txt").write_text("hello")

        result = await verifier.verify_file_state(str(tmp_path / "exists.txt"), should_exist=True)
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_verify_file_missing(self, tmp_path):
        verifier = Verifier(VerifierConfig(prefer_trained_model=False))
        result = await verifier.verify_file_state(
            str(tmp_path / "missing.txt"), should_exist=True
        )
        assert result.passed is False
        assert len(result.failures) > 0

    @pytest.mark.asyncio
    async def test_verify_file_content(self, tmp_path):
        verifier = Verifier(VerifierConfig(prefer_trained_model=False))
        (tmp_path / "content.txt").write_text("Hello VerifyLoop!")

        result = await verifier.verify_file_state(
            str(tmp_path / "content.txt"), expected_content="VerifyLoop"
        )
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_verify_file_content_mismatch(self, tmp_path):
        verifier = Verifier(VerifierConfig(prefer_trained_model=False))
        (tmp_path / "wrong.txt").write_text("Wrong content")

        result = await verifier.verify_file_state(
            str(tmp_path / "wrong.txt"), expected_content="Expected content"
        )
        assert result.passed is False


class TestPipelineConfig:
    def test_default_config(self):
        config = PipelineConfig()
        assert config.model == "gpt-4o"
        assert config.verify_model == "reason-critic-7b"
        assert config.max_iterations == 5
        assert config.confidence_threshold == 0.8

    def test_custom_config(self):
        config = PipelineConfig(
            model="claude-3-opus",
            verify_model="reason-critic-7b",
            max_iterations=3,
            confidence_threshold=0.9,
        )
        assert config.model == "claude-3-opus"
        assert config.max_iterations == 3
