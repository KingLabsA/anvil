"""Model evaluation orchestrator for BenchAgent benchmark."""

from __future__ import annotations

import time
from typing import Any, Callable

from bench_agent.models import ScoreReport, Task, TaskCategory, TaskResult
from bench_agent.runner import TaskRunner
from bench_agent.scorer import (
    calculate_category_scores,
    calculate_overall_score,
    error_recovery_score,
)
from bench_agent.tasks import ALL_TASKS, TASKS_BY_CATEGORY

ModelFn = Callable[[str], str]


def evaluate_model(
    model_name: str,
    provider: str = "openai",
    categories: list[TaskCategory] | None = None,
    num_tasks: int | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    runner: TaskRunner | None = None,
    model_fn: ModelFn | None = None,
) -> ScoreReport:
    runner = runner or TaskRunner(model_fn=model_fn)

    tasks: list[Task] = []
    if categories:
        for cat in categories:
            tasks.extend(TASKS_BY_CATEGORY.get(cat, []))
    else:
        tasks = list(ALL_TASKS)

    if num_tasks:
        tasks = tasks[:num_tasks]

    results: list[TaskResult] = []
    for task in tasks:
        try:
            result = runner.run_task(task, model_name)
            results.append(result)
        except Exception as e:
            results.append(
                TaskResult(
                    task_id=task.task_id,
                    model=model_name,
                    success=False,
                    errors=[str(e)],
                )
            )

    total_score = calculate_overall_score(results)
    category_scores = calculate_category_scores(results)

    recovery_scores = [error_recovery_score(r) for r in results]
    avg_recovery = sum(recovery_scores) / len(recovery_scores) if recovery_scores else 0.0

    return ScoreReport(
        model=model_name,
        total_score=total_score,
        category_scores=category_scores,
        error_recovery_rate=round(avg_recovery, 3),
    )


def evaluate_with_retry(
    model_name: str,
    provider: str = "openai",
    categories: list[TaskCategory] | None = None,
    num_tasks: int | None = None,
    max_retries: int = 3,
    retry_delay: float = 5.0,
    model_fn: ModelFn | None = None,
    **kwargs: Any,
) -> ScoreReport:
    for attempt in range(max_retries):
        try:
            return evaluate_model(
                model_name=model_name,
                provider=provider,
                categories=categories,
                num_tasks=num_tasks,
                model_fn=model_fn,
                **kwargs,
            )
        except Exception:
            if attempt == max_retries - 1:
                raise
            time.sleep(retry_delay * (2**attempt))

    raise RuntimeError("Unreachable")
