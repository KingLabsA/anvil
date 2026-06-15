"""CLI for Fable5 Dataset."""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from fable5_dataset.loader import DatasetLoader
from fable5_dataset.benchmark import BenchmarkGenerator
from fable5_dataset.stats import DatasetStats

console = Console()


@click.group()
def cli() -> None:
    """Fable5 Dataset - Load and manage agent trace datasets."""
    pass


@cli.command()
@click.argument("source", type=click.Choice(["glint", "armand0e", "vfable", "coding_excellence", "opencoven", "victor", "all"]))
@click.option("--normalize", is_flag=True, default=True, help="Normalize format")
@click.option("--remove-pii", is_flag=True, help="Remove PII from records")
@click.option("--min-quality", type=float, default=0.0, help="Minimum quality score filter")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path")
def load(source: str, normalize: bool, remove_pii: bool, min_quality: float, output: str | None) -> None:
    """Load a Fable5 dataset."""
    loader = DatasetLoader()

    with console.status(f"[bold green]Loading {source} dataset..."):
        result = loader.load_dataset(
            source=source,
            normalize=normalize,
            remove_pii=remove_pii,
            min_quality=min_quality,
        )

    if source == "all":
        total = sum(len(v) for v in result.values())
        console.print(Panel(
            f"[bold]Loaded all datasets[/bold]\n"
            f"Total records: {total}",
            title="Load Results",
        ))
        for name, records in result.items():
            console.print(f"  {name}: {len(records)} records")

        if output:
            all_records = []
            for records in result.values():
                all_records.extend(records)
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            with open(output, "w") as f:
                for record in all_records:
                    clean = {k: v for k, v in record.items() if not k.startswith("_")}
                    f.write(json.dumps(clean) + "\n")
            console.print(f"\n[green]Results saved to {output}[/green]")
    else:
        records = result
        console.print(Panel(
            f"[bold]Dataset:[/bold] {source}\n"
            f"[bold]Records:[/bold] {len(records)}",
            title="Load Results",
        ))

        if output and isinstance(records, list):
            Path(output).parent.mkdir(parents=True, exist_ok=True)
            with open(output, "w") as f:
                for record in records:
                    clean = {k: v for k, v in record.items() if not k.startswith("_")}
                    f.write(json.dumps(clean) + "\n")
            console.print(f"\n[green]Results saved to {output}[/green]")


@cli.command()
@click.argument("input_file", type=click.Path(exists=True), required=False)
@click.option("--source", type=click.Choice(["glint", "armand0e", "vfable", "coding_excellence", "opencoven", "victor", "all"]), default=None, help="Dataset source to analyze")
def stats(input_file: str | None, source: str | None) -> None:
    """Compute and display dataset statistics."""
    stat_calc = DatasetStats()

    if input_file:
        result = stat_calc.compute_stats_from_file(input_file)
        console.print(result.summary())
    elif source:
        loader = DatasetLoader()
        records = loader.load_dataset(source=source)
        result = stat_calc.compute_stats(records)
        console.print(result.summary())
    else:
        loader = DatasetLoader()
        all_datasets = loader.load_dataset(source="all")
        comparisons = stat_calc.compare_datasets(all_datasets)

        table = Table(title="Dataset Comparison", show_lines=True)
        table.add_column("Dataset", style="bold")
        table.add_column("Records", justify="right")
        table.add_column("Avg Turns", justify="right")
        table.add_column("Tools", justify="right")
        table.add_column("Quality", justify="right")

        for name, ds_stats in comparisons.items():
            top_tool = max(ds_stats.tool_distribution, key=ds_stats.tool_distribution.get) if ds_stats.tool_distribution else "none"
            table.add_row(
                name,
                f"{ds_stats.total_rows:,}",
                f"{ds_stats.avg_turns_per_session:.1f}",
                top_tool,
                f"{ds_stats.quality_score_avg:.3f}",
            )
        console.print(table)


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--format", "-f", "output_format", type=click.Choice(["openai_chat", "alpaca", "sharegpt", "conversation"]), default="openai_chat", help="Output format")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path")
def convert(input_file: str, output_format: str, output: str | None) -> None:
    """Convert dataset to a different format."""
    from trajectory_distiller.distiller import Distiller

    distiller = Distiller()

    with console.status(f"[bold green]Converting to {output_format}..."):
        result = distiller.distill(
            input_path=input_file,
            output_format=output_format,
            output_path=output,
        )

    console.print(Panel(
        f"[bold]Converted:[/bold] {input_file}\n"
        f"[bold]Format:[/bold] {output_format}\n"
        f"[bold]Records:[/bold] {len(result)}",
        title="Conversion Complete",
    ))


@cli.command()
@click.option("--source", type=click.Choice(["glint", "armand0e", "vfable", "coding_excellence", "opencoven", "victor"]), default="glint", help="Dataset source")
@click.option("--num-tasks", type=int, default=50, help="Number of tasks to generate")
@click.option("--categories", multiple=True, help="Categories to include")
@click.option("--output", "-o", type=click.Path(), default="benchmark.jsonl", help="Output file path")
def benchmark(source: str, num_tasks: int, categories: tuple, output: str) -> None:
    """Generate benchmark tasks from a dataset."""
    loader = DatasetLoader()
    gen = BenchmarkGenerator()

    with console.status(f"[bold green]Loading {source} dataset..."):
        records = loader.load_dataset(source=source)

    cat_list = list(categories) if categories else None

    with console.status("[bold green]Generating benchmark tasks..."):
        tasks = gen.generate_benchmark(records, num_tasks=num_tasks, categories=cat_list)

    table = Table(title=f"Benchmark Tasks ({len(tasks)} total)", show_lines=True)
    table.add_column("ID", style="dim", width=20)
    table.add_column("Category", style="cyan")
    table.add_column("Difficulty", style="bold")
    table.add_column("Tools", width=25)
    table.add_column("Prompt Preview", max_width=40)

    for task in tasks[:20]:
        diff_style = {"easy": "green", "medium": "yellow", "hard": "red"}[task.difficulty]
        table.add_row(
            task.id[:20],
            task.category,
            f"[{diff_style}]{task.difficulty}[/{diff_style}]",
            ", ".join(task.expected_tools[:3]),
            task.prompt[:40] + "...",
        )

    console.print(table)

    gen.save_benchmark(tasks, output)
    console.print(f"\n[green]Saved {len(tasks)} tasks to {output}[/green]")


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--train-ratio", type=float, default=0.95, help="Training set ratio")
@click.option("--val-ratio", type=float, default=0.05, help="Validation set ratio")
@click.option("--stratify-by", type=click.Choice(["tool", "length", "quality", "none"]), default="none", help="Stratify by")
@click.option("--output-dir", "-o", type=click.Path(), default="splits", help="Output directory")
def split(input_file: str, train_ratio: float, val_ratio: float, stratify_by: str, output_dir: str) -> None:
    """Split a dataset into train/validation/test sets."""
    from trajectory_distiller.distiller import Distiller
    from trajectory_distiller.splitter import DataSplitter

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

    result.save(output_dir)
    console.print(f"\n[green]Splits saved to {output_dir}/[/green]")


if __name__ == "__main__":
    cli()
