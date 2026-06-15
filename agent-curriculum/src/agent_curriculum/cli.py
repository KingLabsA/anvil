"""CLI for AgentCurriculum — curriculum learning with difficulty-scored stages."""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from agent_curriculum.difficulty_scorer import DifficultyScorer
from agent_curriculum.stage_builder import StageBuilder
from agent_curriculum.scheduler import DEFAULT_SCHEDULE

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """AgentCurriculum — Curriculum learning for agent training with difficulty-scored stages."""
    pass


@cli.command()
@click.argument("trace_file", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="Output JSONL file for scores")
def score(trace_file, output):
    """Score traces by difficulty level."""
    scorer = DifficultyScorer()
    scores = scorer.score_file(trace_file)

    table = Table(title="Difficulty Scores")
    table.add_column("Trace ID", style="cyan")
    table.add_column("Difficulty", style="bold")
    table.add_column("Level", style="magenta")
    table.add_column("Tools", justify="right")
    table.add_column("Errors", justify="right")

    for s in scores:
        level_color = {"basic": "green", "intermediate": "yellow", "advanced": "orange3", "expert": "red", "master": "bold red"}.get(s.difficulty_level, "white")
        table.add_row(
            s.trace_id,
            f"{s.overall_difficulty:.3f}",
            f"[{level_color}]{s.difficulty_level}[/{level_color}]",
            str(s.tool_count),
            str(s.error_count),
        )

    console.print(table)

    if output:
        out_data = [s.to_dict() for s in scores]
        Path(output).write_text("\n".join(json.dumps(d) for d in out_data))
        console.print(f"[green]Scores saved to {output}[/green]")


@cli.command()
@click.argument("trace_file", type=click.Path(exists=True))
@click.option("--stages", "-s", default=5, type=int, help="Number of curriculum stages")
@click.option("--output", "-o", type=click.Path(), help="Output directory for stage files")
def build(trace_file, stages, output):
    """Build curriculum stages from a trace file."""
    stager = StageBuilder(num_stages=stages)
    result = stager.build_from_file(trace_file)

    table = Table(title=f"Curriculum Stages ({len(result)} stages)")
    table.add_column("Stage", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Difficulty", style="magenta")
    table.add_column("Traces", justify="right")

    for stage in result:
        table.add_row(
            str(stage.stage_id),
            stage.name,
            f"[{stage.difficulty_range[0]:.1f} - {stage.difficulty_range[1]:.1f}]",
            str(len(stage.traces)),
        )

    console.print(table)

    if output:
        out_path = Path(output)
        out_path.mkdir(parents=True, exist_ok=True)
        for stage in result:
            stage_file = out_path / f"stage_{stage.stage_id}_{stage.name}.json"
            stage_file.write_text(json.dumps(stage.to_dict(), indent=2))
        console.print(f"[green]Stages saved to {output}[/green]")


@cli.command()
def schedule():
    """Show the default learning rate / batch size schedule."""
    table = Table(title="Default Curriculum Schedule")
    table.add_column("Stage", style="cyan")
    table.add_column("LR", style="green")
    table.add_column("Batch", justify="right")
    table.add_column("LoRA r", justify="right")
    table.add_column("LoRA alpha", justify="right")
    table.add_column("Epochs", justify="right")

    for s in DEFAULT_SCHEDULE:
        table.add_row(
            str(s.stage_id),
            f"{s.learning_rate:.1e}",
            str(s.batch_size),
            str(s.lora_r),
            str(s.lora_alpha),
            str(s.num_epochs),
        )

    console.print(table)


if __name__ == "__main__":
    cli()
