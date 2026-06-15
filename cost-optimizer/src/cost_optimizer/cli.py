"""CLI for Cost Optimizer."""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from cost_optimizer.analyzer import TokenAnalyzer
from cost_optimizer.optimizer import CostOptimizer
from cost_optimizer.pricing import PricingData

console = Console()


@click.group()
def cli() -> None:
    """Cost Optimizer - Analyze token waste and optimize LLM routing."""
    pass


@cli.command()
@click.argument("trace_file", type=click.Path(exists=True))
@click.option("--model", default="claude-3-5-sonnet-20241022", help="Model used for cost calculation")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path")
def analyze(trace_file: str, model: str, output: str | None) -> None:
    """Analyze a trace file for token waste."""
    analyzer = TokenAnalyzer(default_model=model)

    with console.status("[bold green]Analyzing traces..."):
        report = analyzer.analyze_trace(trace_file)

    console.print(Panel(
        f"[bold]Total tokens:[/bold] {report.total_tokens:,}\n"
        f"[bold]Total cost:[/bold] ${report.total_cost_usd:.4f}\n"
        f"[bold]Sessions:[/bold] {report.num_sessions}\n"
        f"[bold]Turns:[/bold] {report.num_turns}\n"
        f"[bold]Waste items:[/bold] {len(report.waste_items)}\n"
        f"[bold]Potential savings:[/bold] ${report.potential_savings_usd:.4f} ({report.potential_savings_pct:.1f}%)",
        title="Token Analysis Summary",
    ))

    if report.waste_items:
        table = Table(title="Waste Details", show_lines=True)
        table.add_column("Type", style="cyan")
        table.add_column("Description", max_width=50)
        table.add_column("Tokens", justify="right")
        table.add_column("Cost", justify="right", style="red")
        table.add_column("Suggestion", max_width=40)

        for w in report.waste_items[:20]:
            table.add_row(
                w.waste_type.replace("_", " ").title(),
                w.description[:50],
                f"{w.tokens_wasted:,}",
                f"${w.cost_wasted_usd:.4f}",
                w.suggestion[:40] if w.suggestion else "",
            )
        console.print(table)

    optimizer = CostOptimizer(default_model=model)
    optimizations = optimizer.optimize(report)

    if optimizations:
        opt_table = Table(title="Optimization Recommendations", show_lines=True)
        opt_table.add_column("Priority", style="bold", width=10)
        opt_table.add_column("Strategy", style="cyan", width=25)
        opt_table.add_column("Savings", justify="right", width=12)
        opt_table.add_column("Effort", width=10)
        opt_table.add_column("Description", max_width=50)

        for opt in optimizations:
            priority_style = {"critical": "bold red", "high": "red", "medium": "yellow", "low": "green"}[opt.priority]
            opt_table.add_row(
                f"[{priority_style}]{opt.priority.upper()}[/{priority_style}]",
                opt.strategy,
                f"${opt.estimated_savings_usd:.2f} ({opt.estimated_savings_pct:.1f}%)",
                opt.effort,
                opt.description[:50],
            )
        console.print(opt_table)

    if output:
        result = {
            "total_tokens": report.total_tokens,
            "total_cost_usd": report.total_cost_usd,
            "waste_items": [
                {"type": w.waste_type, "description": w.description,
                 "tokens_wasted": w.tokens_wasted, "cost_wasted_usd": w.cost_wasted_usd}
                for w in report.waste_items
            ],
            "optimizations": [
                {"strategy": o.strategy, "savings_usd": o.estimated_savings_usd,
                 "savings_pct": o.estimated_savings_pct, "priority": o.priority,
                 "implementation": o.implementation}
                for o in optimizations
            ],
        }
        Path(output).write_text(json.dumps(result, indent=2))
        console.print(f"\n[green]Results saved to {output}[/green]")


@cli.command()
@click.option("--model", default="claude-3-5-sonnet-20241022", help="Model to estimate cost for")
@click.option("--tokens", type=int, required=True, help="Number of tokens to estimate")
@click.option("--output-ratio", default=0.4, type=float, help="Ratio of output tokens (default: 0.4)")
@click.option("--compare", is_flag=True, help="Compare costs across all models")
def estimate(model: str, tokens: int, output_ratio: float, compare: bool) -> None:
    """Estimate cost for a given number of tokens."""
    pricing = PricingData()

    if compare:
        comparisons = pricing.compare_models(tokens, output_ratio=output_ratio)
        table = Table(title=f"Cost Comparison for {tokens:,} tokens")
        table.add_column("Model", style="cyan")
        table.add_column("Cost (USD)", justify="right", style="bold")
        table.add_column("Tier", width=12)

        for model_id in sorted(comparisons, key=comparisons.get):
            model_info = pricing.get_model(model_id)
            cost = comparisons[model_id]
            tier = model_info.tier if model_info else "unknown"
            table.add_row(model_id, f"${cost:.4f}", tier)
        console.print(table)
    else:
        cost = pricing.calculate_cost(tokens, model, output_ratio=output_ratio)
        model_info = pricing.get_model(model)
        name = model_info.friendly_name if model_info else model
        console.print(Panel(
            f"[bold]Model:[/bold] {name} ({model})\n"
            f"[bold]Tokens:[/bold] {tokens:,}\n"
            f"[bold]Output ratio:[/bold] {output_ratio:.0%}\n"
            f"[bold]Estimated cost:[/bold] ${cost:.4f}",
            title="Cost Estimate",
        ))


@cli.command()
@click.argument("trace_file", type=click.Path(exists=True))
@click.option("--model", default="claude-3-5-sonnet-20241022", help="Model used for cost calculation")
def optimize(trace_file: str, model: str) -> None:
    """Analyze trace and show optimization recommendations."""
    analyzer = TokenAnalyzer(default_model=model)
    report = analyzer.analyze_trace(trace_file)
    optimizer = CostOptimizer(default_model=model)
    optimizations = optimizer.optimize(report)

    console.print(Panel(
        f"[bold]Current cost:[/bold] ${report.total_cost_usd:.4f}\n"
        f"[bold]Potential savings:[/bold] ${report.potential_savings_usd:.4f} ({report.potential_savings_pct:.1f}%)",
        title="Optimization Summary",
    ))

    if optimizations:
        total_savings = sum(o.estimated_savings_usd for o in optimizations)
        console.print(f"\n[bold green]Total estimated savings: ${total_savings:.4f}[/bold green]\n")

        for i, opt in enumerate(optimizations, 1):
            priority_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}[opt.priority]
            console.print(f"{priority_emoji} [bold]{opt.strategy}[/bold] (saves ${opt.estimated_savings_usd:.2f})")
            console.print(f"   {opt.description}")
            console.print(f"   Effort: {opt.effort} | Priority: {opt.priority}")
            if opt.implementation:
                console.print(f"   [dim]Implementation: {opt.implementation}[/dim]")
            console.print()


if __name__ == "__main__":
    cli()
