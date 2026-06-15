"""Model evaluation orchestrator for BenchAgent benchmark."""

from __future__ import annotations

import time
from typing import Any

from bench_agent.models import ScoreReport, Task, TaskCategory, TaskResult
from bench_agent.runner import TaskRunner
from bench_agent.scorer import (
    calculate_category_scores,
    calculate_overall_score,
    error_recovery_score,
)
from bench_agent.tasks import ALL_TASKS, TASKS_BY_CATEGORY

PROMPT_TEMPLATE = """You are an AI assistant being evaluated on your tool-use capabilities.

You have access to the following tools: {tools}

Your task: {description}

Working directory: {workdir}

{initial_files}

You must complete this task using the tools available. You have {max_turns} turns maximum.
Be precise and thorough. After completing the task, verify your work.
"""


class ModelProvider:
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"
    HUGGINGFACE = "huggingface"


def _build_prompt(task: Task, workdir: str) -> str:
    files_section = ""
    if task.initial_state:
        files_section = "Initial files:\n"
        for fname, content in task.initial_state.items():
            files_section += f"\n--- {fname} ---\n{content}\n"

    return PROMPT_TEMPLATE.format(
        tools=", ".join(task.tools_required),
        description=task.description,
        workdir=workdir,
        initial_files=files_section,
        max_turns=task.max_turns,
    )


def evaluate_model(
    model_name: str,
    provider: str = ModelProvider.OPENAI,
    categories: list[TaskCategory] | None = None,
    num_tasks: int | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    runner: TaskRunner | None = None,
) -> ScoreReport:
    runner = runner or TaskRunner()

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
    provider: str = ModelProvider.OPENAI,
    categories: list[TaskCategory] | None = None,
    num_tasks: int | None = None,
    max_retries: int = 3,
    retry_delay: float = 5.0,
    **kwargs: Any,
) -> ScoreReport:
    for attempt in range(max_retries):
        try:
            return evaluate_model(
                model_name=model_name,
                provider=provider,
                categories=categories,
                num_tasks=num_tasks,
                **kwargs,
            )
        except Exception:
            if attempt == max_retries - 1:
                raise
            time.sleep(retry_delay * (2**attempt))

    raise RuntimeError("Unreachable")
