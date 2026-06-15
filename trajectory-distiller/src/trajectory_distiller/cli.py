"""CLI for Trajectory Distiller."""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from trajectory_distiller.distiller import Distiller
from trajectory_distiller.filter import TraceFilter
from trajectory_distiller.splitter import DataSplitter

console = Console()


@click.group()
def cli() -> None:
    """Trajectory Distiller - Convert agent traces to training datasets."""
    pass


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--format", "-f", "output_format", type=click.Choice(["openai_chat", "alpaca", "sharegpt", "conversation"]), default="openai_chat", help="Output format")
@click.option("--input-format", type=click.Choice(["glint", "armand0e", "vfable", "opencoven", "victor", "auto"]), default="auto", help="Input format (auto-detected by default)")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path")
def distill(input_file: str, output_format: str, input_format: str | None, output: str | None) -> None:
    """Distill agent traces into a training dataset."""
    distiller = Distiller()
    fmt = None if input_format == "auto" else input_format

    with console.status("[bold green]Distilling traces..."):
        result = distiller.distill(
            input_path=input_file,
            input_format=fmt,
            output_path=output,
            output_format=output_format,
        )

    console.print(Panel(
        f"[bold]Input:[/bold] {input_file}\n"
        f"[bold]Format:[/bold] {output_format}\n"
        f"[bold]Records:[/bold] {len(result)}",
        title="Distillation Complete",
    ))

    if not output:
        if result:
            console.print("\n[dim]Sample record:[/dim]")
            console.print(json.dumps(result[0], indent=2)[:500] + "...")


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--tool", "-t", multiple=True, help="Filter to records containing this tool")
@click.option("--min-errors", type=float, default=0.0, help="Minimum error rate (0.0-1.0)")
@click.option("--min-turns", type=int, default=2, help="Minimum number of turns")
@click.option("--max-turns", type=int, default=200, help="Maximum number of turns")
@click.option("--min-quality", type=float, default=0.0, help="Minimum quality score (0.0-1.0)")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path")
def filter(input_file: str, tool: tuple, min_errors: float, min_turns: int, max_turns: int, min_quality: float, output: str | None) -> None:
    """Filter traces by various criteria."""
    trace_filter = TraceFilter()

    distiller = Distiller()
    fmt = distiller._detect_format(input_file)
    records = distiller._load_and_normalize(input_file, fmt)

    original_count = len(records)
    console.print(f"Loaded [bold]{original_count}[/bold] records (format: {fmt})")

    if tool:
        records = trace_filter.filter_by_tool(records, list(tool))
        console.print(f"After tool filter: [bold]{len(records)}[/bold] records")

    if min_errors > 0:
        records = trace_filter.filter_by_error_rate(records, min_rate=min_errors)
        console.print(f"After error rate filter: [bold]{len(records)}[/bold] records")

    if min_turns > 2 or max_turns < 200:
        records = trace_filter.filter_by_session_length(records, min_turns=min_turns, max_turns=max_turns)
        console.print(f"After session length filter: [bold]{len(records)}[/bold] records")

    if min_quality > 0:
        records = trace_filter.filter_by_quality(records, min_quality_score=min_quality)
        console.print(f"After quality filter: [bold]{len(records)}[/bold] records")

    console.print(Panel(
        f"[bold]Original:[/bold] {original_count} records\n"
        f"[bold]Remaining:[/bold] {len(records)} records\n"
        f"[bold]Filtered:[/bold] {original_count - len(records)} records",
        title="Filter Results",
    ))

    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w") as f:
            for record in records:
                clean = {k: v for k, v in record.items() if not k.startswith("_")}
                f.write(json.dumps(clean) + "\n")
        console.print(f"\n[green]Results saved to {output}[/green]")


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--train-ratio", type=float, default=0.95, help="Training set ratio")
@click.option("--val-ratio", type=float, default=0.05, help="Validation set ratio")
@click.option("--test-ratio", type=float, default=0.0, help="Test set ratio")
@click.option("--stratify-by", type=click.Choice(["tool", "length", "quality", "none"]), default="none", help="Stratify by")
@click.option("--output-dir", "-o", type=click.Path(), default="splits", help="Output directory")
@click.option("--format", "-f", "output_format", type=click.Choice(["jsonl", "json"]), default="jsonl", help="Output format")
def split(input_file: str, train_ratio: float, val_ratio: float, test_ratio: float, stratify_by: str, output_dir: str, output_format: str) -> None:
    """Split a dataset into train/val/test sets."""
    distiller = Distiller()
    fmt = distiller._detect_format(input_file)
    records = distiller._load_and_normalize(input_file, fmt)

    console.print(f"Loaded [bold]{len(records)}[/bold] records (format: {fmt})")

    splitter = DataSplitter()
    strat_key = None if stratify_by == "none" else stratify_by

    with console.status("[bold green]Splitting dataset..."):
        result = splitter.split(
            records=records,
            train_ratio=train_ratio,
            val_ratio=val_ratio,
            test_ratio=test_ratio,
            stratify_by=strat_key,
        )

    stats = result.stats()
    console.print(Panel(
        f"[bold]Total:[/bold] {stats['total']} records\n"
        f"[bold]Train:[/bold] {stats['train']} ({stats['train_ratio']:.1%})\n"
        f"[bold]Validation:[/bold] {stats['val']} ({stats['val_ratio']:.1%})\n"
        f"[bold]Test:[/bold] {stats['test']} ({stats['test_ratio']:.1%})",
        title="Split Results",
    ))

    result.save(output_dir, format=output_format)
    console.print(f"\n[green]Splits saved to {output_dir}/[/green]")


if __name__ == "__main__":
    cli()
