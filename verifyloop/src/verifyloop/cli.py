"""CLI interface for VerifyLoop."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from verifyloop.models import AgentRun, PipelineConfig, RunStatus
from verifyloop.pipeline import AgentPipeline

console = Console()


def format_step_table(run: AgentRun) -> Table:
    table = Table(title="VerifyLoop Execution", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Phase", style="bold")
    table.add_column("Content", max_width=60)
    table.add_column("Confidence", justify="right")

    phase_colors = {
        "plan": "cyan",
        "execute": "green",
        "verify": "yellow",
        "recover": "red",
    }

    for i, step in enumerate(run.steps, 1):
        color = phase_colors.get(step.step_type.value, "white")
        table.add_row(
            str(i),
            f"[{color}]{step.step_type.value}[/{color}]",
            step.content[:120] + ("..." if len(step.content) > 120 else ""),
            f"{step.confidence:.0%}",
        )
    return table


async def run_pipeline(
    task: str,
    context: str = "",
    model: str = "gpt-4o",
    verify_model: str = "reason-critic-7b",
    max_iterations: int = 5,
    working_dir: str = ".",
    dry_run: bool = False,
    interactive: bool = False,
    sandbox: bool = False,
) -> AgentRun:
    config = PipelineConfig(
        model=model,
        verify_model=verify_model,
        max_iterations=max_iterations,
        working_dir=working_dir,
        dry_run=dry_run,
        interactive=interactive,
        sandbox=sandbox,
    )
    pipeline = AgentPipeline(config)

    events_log: list[dict[str, Any]] = []

    async def on_event(event: str, data: dict[str, Any]) -> None:
        events_log.append({"event": event, **data})
        if event == "phase_start":
            phase = data.get("phase", "")
            color_map = {"plan": "cyan", "execute": "green", "verify": "yellow", "recover": "red"}
            color = color_map.get(phase, "white")
            console.print(f"\n[bold {color}]═══ {phase.upper()} ═══[/]")
        elif event == "step_complete":
            status = "✓" if data.get("success") else "✗"
            console.print(f"  {status} {data.get('tool', '')} (iteration {data.get('iteration', '')})")
        elif event == "phase_complete":
            phase = data.get("phase", "")
            if phase == "verify":
                passed = data.get("passed", False)
                confidence = data.get("confidence", 0)
                icon = "✓" if passed else "✗"
                console.print(f"  {icon} Verification: confidence={confidence:.0%}")
        elif event == "recovery_attempt":
            console.print(
                f"  ⟳ Recovery #{data.get('attempt', '')}: {data.get('description', '')}"
            )

    pipeline.on_event(on_event)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task_display = progress.add_task("Running VerifyLoop...", total=None)
        result = await pipeline.run(task, context, max_iterations)
        progress.update(task_display, completed=1)

    console.print()
    console.print(format_step_table(result))

    status_style = "bold green" if result.status == RunStatus.COMPLETED else "bold red"
    console.print(f"\n[{status_style}]Status: {result.status.value}[/{status_style}]")
    console.print(f"Duration: {result.duration_seconds:.2f}s")
    console.print(f"Iterations: {result.iteration}")
    console.print(
        f"Tokens: {result.token_usage.prompt_tokens} prompt + "
        f"{result.token_usage.completion_tokens} completion = "
        f"{result.token_usage.total_tokens} total"
    )

    return result


@click.group()
def cli() -> None:
    """VerifyLoop — Plan → Execute → Verify → Recover agent framework."""
    pass


@cli.command()
@click.argument("task", required=False)
@click.option("--task-file", type=click.Path(exists=True), help="Path to JSON task file")
@click.option("--context", default="", help="Additional context for the task")
@click.option("--model", default="gpt-4o", help="LLM model for planning")
@click.option("--verify-model", default="reason-critic-7b", help="Verification model")
@click.option("--max-iterations", default=5, type=int, help="Maximum plan-execute-verify loops")
@click.option("--working-dir", default=".", help="Working directory")
@click.option("--dry-run", is_flag=True, help="Plan only, don't execute")
@click.option("--interactive", is_flag=True, help="Confirm each step before execution")
@click.option("--sandbox", is_flag=True, help="Run bash commands in Docker sandbox")
@click.option("--output", type=click.Path(), help="Save results to JSON file")
def run(
    task: str | None,
    task_file: str | None,
    context: str,
    model: str,
    verify_model: str,
    max_iterations: int,
    working_dir: str,
    dry_run: bool,
    interactive: bool,
    sandbox: bool,
    output: str | None,
) -> None:
    """Run a task through the Plan → Execute → Verify → Recover pipeline."""
    if task_file:
        path = Path(task_file)
        data = json.loads(path.read_text())
        task = data.get("task", "")
        context = data.get("context", context)
        model = data.get("model", model)
        verify_model = data.get("verify_model", verify_model)
        max_iterations = data.get("max_iterations", max_iterations)
    elif not task:
        console.print("[bold red]Error:[/] Provide a task string or --task-file")
        sys.exit(1)

    result = asyncio.run(run_pipeline(
        task=task,
        context=context,
        model=model,
        verify_model=verify_model,
        max_iterations=max_iterations,
        working_dir=working_dir,
        dry_run=dry_run,
        interactive=interactive,
        sandbox=sandbox,
    ))

    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result.model_dump_json(indent=2))
        console.print(f"\n[dim]Results saved to {output}[/]")


if __name__ == "__main__":
    cli()
