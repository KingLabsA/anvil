"""Scoring system for BenchAgent benchmark results."""

from __future__ import annotations

from bench_agent.models import Difficulty, Task, TaskCategory, TaskResult


def exact_match(result: TaskResult, expected_files: dict[str, str] | None = None) -> float:
    if expected_files is None:
        return 0.0

    if not result.success:
        return 0.0

    total = len(expected_files)
    if total == 0:
        return 1.0

    matched = 0
    for filename, expected_content in expected_files.items():
        actual = result.actual_output.get("files", {}).get(filename, "")
        if actual.strip() == expected_content.strip():
            matched += 1

    return matched / total


def functional_match(result: TaskResult, task: Task) -> float:
    if not result.success:
        return 0.0

    if task.verification_script:
        return 1.0

    expected = task.expected_outcome
    score = 0.0
    total_checks = 0

    if "file_exists" in expected:
        total_checks += len(expected["file_exists"])
        for f in expected["file_exists"]:
            if f in result.actual_output.get("files", {}):
                score += 1

    if "files" in expected:
        total_checks += len(expected["files"])
        for fname, content in expected["files"].items():
            actual = result.actual_output.get("files", {}).get(fname, "")
            if actual.strip() == content.strip():
                score += 1
            elif actual and content.split("\n")[0] in actual:
                score += 0.5

    if "stdout_contains" in expected:
        total_checks += len(expected["stdout_contains"])
        for pattern in expected["stdout_contains"]:
            if result.actual_output.get("stdout", "").find(pattern) >= 0:
                score += 1

    if "exit_code" in expected:
        total_checks += 1
        if result.actual_output.get("exit_code") == expected["exit_code"]:
            score += 1

    if total_checks == 0:
        return 1.0 if result.success else 0.0

    return score / total_checks


def partial_credit(result: TaskResult, task: Task) -> float:
    if result.success:
        return 1.0

    credit = 0.0

    if result.errors:
        credit += 0.1

    if result.turns_used > 0:
        credit += min(result.turns_used / task.max_turns, 0.3)

    if result.actual_output:
        credit += 0.1

    expected_files = task.expected_outcome.get("file_exists", [])
    if expected_files:
        created = len(result.actual_output.get("files", {}))
        credit += 0.3 * (created / len(expected_files)) if expected_files else 0

    return min(credit, 0.99)


def error_recovery_score(result: TaskResult) -> float:
    if not result.errors:
        return 1.0

    num_errors = len(result.errors)

    if result.success:
        recovery_rate = min(result.recovery_attempts / max(num_errors, 1), 1.0)
        return 0.5 + 0.5 * recovery_rate

    if result.recovery_attempts > 0:
        recovery_rate = result.recovery_attempts / max(num_errors, 1)
        return 0.3 * recovery_rate

    return 0.0


def efficiency_score(result: TaskResult, task: Task) -> float:
    if not result.success:
        return 0.0

    turn_efficiency = 1.0 - (result.turns_used / max(task.max_turns, 1))
    token_efficiency = max(0.0, 1.0 - (result.tokens_used / 10000))

    return 0.6 * turn_efficiency + 0.4 * token_efficiency


def calculate_overall_score(
    results: list[TaskResult], tasks: list[Task] | None = None
) -> float:
    if not results:
        return 0.0

    from bench_agent.tasks import TASKS_BY_ID

    scores: list[float] = []
    for result in results:
        task = TASKS_BY_ID.get(result.task_id)
        if task is None and tasks:
            task = next((t for t in tasks if t.task_id == result.task_id), None)
        if task is None:
            task = Task(
                task_id=result.task_id,
                category=TaskCategory.BASH,
                difficulty=Difficulty.MEDIUM,
                description="",
                max_turns=10,
            )

        func_score = functional_match(result, task)
        part_score = partial_credit(result, task)
        recovery_score = error_recovery_score(result)
        eff_score = efficiency_score(result, task)

        if result.success:
            score = 0.6 * func_score + 0.15 * recovery_score + 0.25 * eff_score
        else:
            score = 0.5 * part_score + 0.3 * recovery_score + 0.2 * eff_score

        scores.append(score)

    if not scores:
        return 0.0

    return round(sum(scores) / len(scores) * 100, 1)


def calculate_category_scores(
    results: list[TaskResult],
) -> dict[str, float]:
    from bench_agent.tasks import TASKS_BY_ID

    cat_results: dict[str, list[float]] = {}

    for result in results:
        task = TASKS_BY_ID.get(result.task_id)
        if task is None:
            continue

        score = functional_match(result, task)
        cat_results.setdefault(task.category.value, []).append(score)

    return {
        cat: round(sum(scores) / len(scores) * 100, 1)
        for cat, scores in cat_results.items()
        if scores
    }
