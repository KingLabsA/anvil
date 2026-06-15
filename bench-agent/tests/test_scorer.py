"""Unit tests for scoring system."""

import pytest

from bench_agent.models import Difficulty, Task, TaskCategory, TaskResult
from bench_agent.scorer import (
    calculate_category_scores,
    calculate_overall_score,
    efficiency_score,
    error_recovery_score,
    exact_match,
    functional_match,
    partial_credit,
)


@pytest.fixture
def sample_task():
    return Task(
        task_id="test-001",
        category=TaskCategory.BASH,
        difficulty=Difficulty.EASY,
        description="Test task",
        initial_state={"app.py": "print('hello')\n"},
        expected_outcome={"files": {"app.py": "print('hello')\n"}},
        tools_required=["bash"],
        max_turns=5,
    )


@pytest.fixture
def sample_task_file_exists():
    return Task(
        task_id="test-002",
        category=TaskCategory.WRITE,
        difficulty=Difficulty.MEDIUM,
        description="Create a file",
        initial_state={},
        expected_outcome={"file_exists": ["output.txt"]},
        tools_required=["write"],
        max_turns=3,
    )


@pytest.fixture
def successful_result():
    return TaskResult(
        task_id="test-001",
        model="test-model",
        success=True,
        turns_used=2,
        tokens_used=500,
        errors=[],
        recovery_attempts=0,
        duration_seconds=10.5,
        actual_output={"files": {"app.py": "print('hello')\n"}},
    )


@pytest.fixture
def failed_result():
    return TaskResult(
        task_id="test-001",
        model="test-model",
        success=False,
        turns_used=5,
        tokens_used=2000,
        errors=["timeout"],
        recovery_attempts=0,
        duration_seconds=60.0,
        actual_output={},
    )


@pytest.fixture
def partial_result():
    return TaskResult(
        task_id="test-001",
        model="test-model",
        success=True,
        turns_used=4,
        tokens_used=1500,
        errors=["first attempt failed"],
        recovery_attempts=1,
        duration_seconds=30.0,
        actual_output={"files": {"app.py": "print('hello')\n"}},
    )


class TestExactMatch:
    def test_exact_match_success(self, successful_result):
        expected = {"app.py": "print('hello')\n"}
        score = exact_match(successful_result, expected)
        assert score == 1.0

    def test_exact_match_failure(self, failed_result):
        expected = {"app.py": "print('hello')\n"}
        score = exact_match(failed_result, expected)
        assert score == 0.0

    def test_exact_match_no_expected(self, successful_result):
        score = exact_match(successful_result, None)
        assert score == 0.0

    def test_exact_match_empty_expected(self, successful_result):
        score = exact_match(successful_result, {})
        assert score == 1.0

    def test_exact_match_partial_content(self):
        result = TaskResult(
            task_id="test",
            model="m",
            success=True,
            actual_output={"files": {"a.py": "x = 1\ny = 2\n"}},
        )
        score = exact_match(result, {"a.py": "x = 1\ny = 3\n"})
        assert score == 0.0


class TestFunctionalMatch:
    def test_functional_match_success(self, successful_result, sample_task):
        score = functional_match(successful_result, sample_task)
        assert score >= 0.5

    def test_functional_match_failure(self, failed_result, sample_task):
        score = functional_match(failed_result, sample_task)
        assert score == 0.0

    def test_functional_match_verification_script(self, successful_result):
        task_with_verification = Task(
            task_id="test-v",
            category=TaskCategory.BASH,
            difficulty=Difficulty.EASY,
            description="Verified task",
            verification_script="pass",
        )
        assert functional_match(successful_result, task_with_verification) == 1.0

    def test_functional_match_no_expected(self, failed_result):
        task_no_expected = Task(
            task_id="test-ne",
            category=TaskCategory.BASH,
            difficulty=Difficulty.EASY,
            description="No expected",
        )
        assert functional_match(failed_result, task_no_expected) == 0.0


class TestPartialCredit:
    def test_partial_credit_success(self, successful_result, sample_task):
        credit = partial_credit(successful_result, sample_task)
        assert credit == 1.0

    def test_partial_credit_failure(self, failed_result, sample_task):
        credit = partial_credit(failed_result, sample_task)
        assert 0.0 < credit < 1.0

    def test_partial_credit_with_errors(self, partial_result, sample_task):
        credit = partial_credit(partial_result, sample_task)
        assert credit == 1.0

    def test_partial_credit_bounded(self, failed_result, sample_task):
        credit = partial_credit(failed_result, sample_task)
        assert credit <= 1.0


class TestErrorRecoveryScore:
    def test_no_errors(self, successful_result):
        score = error_recovery_score(successful_result)
        assert score == 1.0

    def test_successful_recovery(self, partial_result):
        score = error_recovery_score(partial_result)
        assert score >= 0.5

    def test_failed_recovery(self, failed_result):
        score = error_recovery_score(failed_result)
        assert score >= 0.0

    def test_recovery_rate_calculation(self):
        result = TaskResult(
            task_id="test",
            model="m",
            success=True,
            errors=["error1", "error2"],
            recovery_attempts=2,
        )
        score = error_recovery_score(result)
        assert score >= 0.5


class TestEfficiencyScore:
    def test_efficient_success(self, successful_result, sample_task):
        score = efficiency_score(successful_result, sample_task)
        assert score > 0.0

    def test_failed_task_zero_efficiency(self, failed_result, sample_task):
        score = efficiency_score(failed_result, sample_task)
        assert score == 0.0

    def test_efficiency_in_range(self, partial_result, sample_task):
        score = efficiency_score(partial_result, sample_task)
        assert 0.0 <= score <= 1.0


class TestCalculateOverallScore:
    def test_empty_results(self):
        score = calculate_overall_score([])
        assert score == 0.0

    def test_successful_results_with_tasks(self, successful_result, sample_task):
        score = calculate_overall_score([successful_result], tasks=[sample_task])
        assert score > 0.0

    def test_successful_results_real_task(self):
        from bench_agent.tasks import BASH_TASKS
        result = TaskResult(
            task_id=BASH_TASKS[0].task_id,
            model="test",
            success=True,
            turns_used=1,
            tokens_used=100,
            errors=[],
            actual_output={"files": BASH_TASKS[0].initial_state},
        )
        score = calculate_overall_score([result])
        assert 0.0 <= score <= 100.0

    def test_mixed_results(self, successful_result, failed_result, sample_task):
        score = calculate_overall_score([successful_result, failed_result], tasks=[sample_task, sample_task])
        assert 0.0 < score < 100.0 or score == 0.0

    def test_score_range(self, successful_result):
        score = calculate_overall_score([successful_result])
        assert 0.0 <= score <= 100.0


class TestCalculateCategoryScores:
    def test_category_scores_structure(self, successful_result):
        scores = calculate_category_scores([successful_result])
        assert isinstance(scores, dict)

    def test_category_scores_values(self, successful_result):
        scores = calculate_category_scores([successful_result])
        for cat, score in scores.items():
            assert 0.0 <= score <= 100.0

    def test_empty_results(self):
        scores = calculate_category_scores([])
        assert scores == {}
