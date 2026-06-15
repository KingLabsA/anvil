"""CLI interface for BenchAgent benchmark runner."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from bench_agent.evaluator import evaluate_with_retry
from bench_agent.models import ScoreReport
from bench_agent.leaderboard import (
    export_leaderboard,
    export_markdown,
    load_leaderboard,
    save_leaderboard,
    update_leaderboard,
)
from bench_agent.models import TaskCategory
from bench_agent.runner import TaskRunner
from bench_agent.tasks import ALL_TASKS, get_task_count


console = Console()


@click.group()
@click.version_option(version="0.1.0")
def main() -> None:
    """BenchAgent — HumanEval for tool use."""


@main.command("list-tasks")
@click.option("--category", "-c", type=click.Choice([c.value for c in TaskCategory]), default=None)
@click.option("--difficulty", "-d", type=click.Choice(["easy", "medium", "hard"]), default=None)
def list_tasks(category: str | None, difficulty: str | None) -> None:
    """List available benchmark tasks."""
    table = Table(title="BenchAgent Tasks")
    table.add_column("ID", style="cyan")
    table.add_column("Category", style="green")
    table.add_column("Difficulty", style="yellow")
    table.add_column("Description", style="white")
    table.add_column("Max Turns", style="magenta")

    tasks = ALL_TASKS
    if category:
        tasks = [t for t in tasks if t.category.value == category]
    if difficulty:
        tasks = [t for t in tasks if t.difficulty.value == difficulty]

    for task in tasks:
        table.add_row(
            task.task_id,
            task.category.value,
            task.difficulty.value,
            task.description[:60] + ("..." if len(task.description) > 60 else ""),
            str(task.max_turns),
        )

    console.print(table)
    console.print(f"\nTotal: {len(tasks)} tasks (of {get_task_count()} total)")


@main.command("run")
@click.option("--model", "-m", required=True, help="Model name to evaluate")
@click.option("--category", "-c", type=click.Choice([c.value for c in TaskCategory]), default=None, help="Task category")
@click.option("--all", "run_all", is_flag=True, help="Run all categories")
@click.option("--num-tasks", "-n", type=int, default=None, help="Number of tasks to run")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file for results")
@click.option("--provider", "-p", type=click.Choice(["openai", "anthropic", "local", "huggingface"]), default="openai")
@click.option("--timeout", type=float, default=300.0, help="Total timeout per task in seconds")
@click.option("--retries", type=int, default=3, help="Max retries on API errors")
def run(
    model: str,
    category: str | None,
    run_all: bool,
    num_tasks: int | None,
    output: str | None,
    provider: str,
    timeout: float,
    retries: int,
) -> None:
    """Run benchmark tasks against a model."""
    categories = None
    if run_all:
        categories = list(TaskCategory)
    elif category:
        categories = [TaskCategory(category)]

    console.print(f"[bold blue]Running BenchAgent for model: {model}[/bold blue]")
    console.print(f"Provider: {provider}")

    runner = TaskRunner(total_timeout=timeout)

    if categories:
        cat_names = [c.value for c in categories]
        console.print(f"Categories: {', '.join(cat_names)}")
    else:
        console.print("Categories: all")

    try:
        report = evaluate_with_retry(
            model_name=model,
            provider=provider,
            categories=categories,
            num_tasks=num_tasks,
            max_retries=retries,
            runner=runner,
        )
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)

    console.print(f"\n[bold green]Results for {model}[/bold green]")
    console.print(f"Total Score: {report.total_score}")
    console.print(f"Error Recovery Rate: {report.error_recovery_rate}")

    if report.category_scores:
        table = Table(title="Category Scores")
        table.add_column("Category", style="cyan")
        table.add_column("Score", style="green")
        for cat, score in report.category_scores.items():
            table.add_row(cat, f"{score:.1f}")
        console.print(table)

    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report.model_dump_json(indent=2))
        console.print(f"\nResults saved to: {output}")


@main.command("leaderboard")
@click.option("--update", is_flag=True, help="Update leaderboard with new results")
@click.option("--results", type=click.Path(exists=True), help="Results file to add")
@click.option("--path", type=click.Path(), default="leaderboard.json", help="Leaderboard file path")
@click.option("--format", "-f", type=click.Choice(["json", "markdown"]), default="json", help="Export format")
def leaderboard(update: bool, results: str | None, path: str, format: str) -> None:
    """Show or update the leaderboard."""
    lb = load_leaderboard(path)

    if update and results:
        results_path = Path(results)
        data = json.loads(results_path.read_text())

        if isinstance(data, list):
            for entry in data:
                lb = update_leaderboard(lb, entry.get("model", "unknown"), [])
        elif isinstance(data, dict) and "task_id" in data:
            entries = [data]
        else:
            report = ScoreReport(**data) if isinstance(data, dict) else data
            lb.entries.append(report)

        lb = update_leaderboard(lb, data.get("model", "unknown") if isinstance(data, dict) else "unknown", [])
        save_leaderboard(lb, path)
        console.print(f"[green]Leaderboard updated and saved to {path}[/green]")

    if format == "markdown":
        console.print(export_markdown(lb))
    else:
        table = Table(title="BenchAgent Leaderboard")
        table.add_column("Rank", style="bold")
        table.add_column("Model", style="cyan")
        table.add_column("Score", style="green")
        table.add_column("Recovery Rate", style="yellow")

        for entry in lb.entries:
            table.add_row(
                str(entry.leaderboard_rank),
                entry.model,
                f"{entry.total_score:.1f}",
                f"{entry.error_recovery_rate:.3f}",
            )

        console.print(table)
        console.print(f"\nLast updated: {lb.last_updated}")


@main.command("export")
@click.option("--path", type=click.Path(), default="leaderboard.json", help="Leaderboard file path")
@click.option("--format", "-f", type=click.Choice(["json", "markdown"]), default="json")
@click.option("--output", "-o", type=click.Path(), default=None)
def export(path: str, format: str, output: str | None) -> None:
    """Export leaderboard in the specified format."""
    lb = load_leaderboard(path)
    content = export_leaderboard(lb, format=format)

    if output:
        Path(output).write_text(content)
        console.print(f"Exported to: {output}")
    else:
        console.print(content)


if __name__ == "__main__":
    main()
