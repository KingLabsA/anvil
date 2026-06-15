"""AgentFuzzer CLI."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from agent_fuzzer.generator import ScenarioGenerator
from agent_fuzzer.runner import FuzzRunner
from agent_fuzzer.reporter import FuzzReporter

console = Console()


@click.group()
@click.version_option("0.1.0")
def cli() -> None:
    """AgentFuzzer — Adversarial scenario testing for coding agents."""


@cli.command()
@click.option("--model", default="gpt-4", help="Model to test")
@click.option("--category", "-c", type=click.Choice(["broken_code", "failing_tests", "missing_deps", "network_errors"]), help="Scenario category")
@click.option("--count", "-n", default=10, help="Number of scenarios to generate")
@click.option("--difficulty", "-d", type=click.Choice(["easy", "medium", "hard"]), help="Difficulty filter")
@click.option("--output", "-o", type=click.Path(), help="Save scenarios to directory")
def fuzz(model: str, category: str | None, count: int, difficulty: str | None, output: str | None) -> None:
    """Run fuzzing scenarios against an agent."""
    generator = ScenarioGenerator()
    scenarios = generator.generate(category=category, count=count, difficulty=difficulty)

    console.print(f"\n[bold]Running {len(scenarios)} scenarios against {model}[/bold]\n")

    runner = FuzzRunner(model=model)
    results = runner.run_suite(scenarios)

    reporter = FuzzReporter(results)
    report = reporter.generate_report()

    table = Table(title="Fuzzing Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    for key, value in report.items():
        if key not in ("by_category", "by_difficulty"):
            table.add_row(key, str(value))
    console.print(table)

    if output:
        reporter.save_report(output)
        console.print(f"\n[green]Report saved to {output}[/green]")


@cli.command()
@click.option("--report", "-r", type=click.Path(exists=True), help="Report JSON file")
def report(report: str | None) -> None:
    """Display a saved fuzzing report."""
    import json
    from pathlib import Path

    if report:
        path = Path(report)
        with open(path) as f:
            data = json.load(f)
    else:
        console.print("[yellow]No report file specified. Run 'agentfuzzer fuzz' first.[/yellow]")
        return

    table = Table(title="Fuzzing Report")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    for key, value in data.items():
        if isinstance(value, dict):
            continue
        table.add_row(key, str(value))
    console.print(table)

    if "by_category" in data:
        cat_table = Table(title="Results by Category")
        cat_table.add_column("Category", style="cyan")
        cat_table.add_column("Total")
        cat_table.add_column("Passed")
        cat_table.add_column("Pass Rate", style="green")
        for cat, val in data["by_category"].items():
            cat_table.add_row(cat, str(val["total"]), str(val["passed"]), str(val["pass_rate"]))
        console.print(cat_table)


if __name__ == "__main__":
    cli()
