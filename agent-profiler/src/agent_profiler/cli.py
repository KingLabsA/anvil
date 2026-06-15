"""CLI for Agent Profiler."""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from agent_profiler.profiler import AgentProfiler
from agent_profiler.classifier import BehaviorClassifier
from agent_profiler.visualizer import ProfileVisualizer

console = Console()


@click.group()
def cli() -> None:
    """Agent Profiler - Profile and classify agent behavior patterns."""
    pass


@cli.command()
@click.argument("trace_file", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path (JSON)")
def profile(trace_file: str, output: str | None) -> None:
    """Profile an agent session from a trace file."""
    profiler = AgentProfiler()

    with console.status("[bold green]Profiling session..."):
        result = profiler.profile(trace_file)

    category_colors = {
        "debugging": "red", "building": "green", "exploring": "blue",
        "lost": "yellow", "verifying": "magenta",
    }
    color = category_colors.get(result.category, "white")

    console.print(Panel(
        f"[bold {color}]{result.category.upper()}[/bold {color}]\n"
        f"Confidence: {result.confidence:.1%}\n"
        f"Turns: {result.num_turns}\n"
        f"Duration: {result.session_duration:.0f}s\n"
        f"Error Rate: {result.error_rate:.1%}\n"
        f"Edit Ratio: {result.edit_ratio:.1%}\n"
        f"Read Ratio: {result.read_ratio:.1%}\n"
        f"Write Ratio: {result.write_ratio:.1%}\n"
        f"Bash Ratio: {result.bash_ratio:.1%}\n"
        f"Grep Ratio: {result.grep_ratio:.1%}",
        title="Profile Result",
    ))

    if result.profile_scores:
        score_table = Table(title="Profile Scores", show_lines=True)
        score_table.add_column("Category", style="bold")
        score_table.add_column("Score", justify="right")
        score_table.add_column("Bar")

        for cat, score in sorted(result.profile_scores.items(), key=lambda x: -x[1]):
            bar_len = int(score * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            cat_color = category_colors.get(cat, "white")
            is_best = cat == result.category
            score_table.add_row(
                f"[{cat_color}]{cat}[/{cat_color}]{' ←' if is_best else ''}",
                f"{score:.1%}",
                f"[{cat_color}]{bar}[/{cat_color}]",
            )
        console.print(score_table)

    if result.tool_distribution.tool_counts:
        tool_table = Table(title="Tool Distribution", show_lines=True)
        tool_table.add_column("Tool", style="cyan")
        tool_table.add_column("Count", justify="right")
        tool_table.add_column("Frequency", justify="right")

        for tool, count in sorted(result.tool_distribution.tool_counts.items(), key=lambda x: -x[1]):
            freq = result.tool_distribution.frequencies.get(tool, 0.0)
            tool_table.add_row(tool.title(), str(count), f"{freq:.1%}")
        console.print(tool_table)

    if output:
        result_dict = {
            "category": result.category,
            "confidence": result.confidence,
            "num_turns": result.num_turns,
            "session_duration": result.session_duration,
            "error_rate": result.error_rate,
            "edit_ratio": result.edit_ratio,
            "read_ratio": result.read_ratio,
            "bash_ratio": result.bash_ratio,
            "write_ratio": result.write_ratio,
            "grep_ratio": result.grep_ratio,
            "error_recovery_rate": result.error_recovery_rate,
            "profile_scores": result.profile_scores,
            "tool_distribution": {
                "counts": result.tool_distribution.tool_counts,
                "total_calls": result.tool_distribution.total_calls,
                "entropy": result.tool_distribution.entropy,
            },
        }
        Path(output).write_text(json.dumps(result_dict, indent=2))
        console.print(f"\n[green]Results saved to {output}[/green]")


@cli.command()
@click.argument("trace_file", type=click.Path(exists=True))
def classify(trace_file: str) -> None:
    """Classify agent behavior from a trace file."""
    profiler = AgentProfiler()

    with console.status("[bold green]Classifying behavior..."):
        result = profiler.profile(trace_file)

    classifier = BehaviorClassifier()
    profiles = classifier.list_profiles()

    console.print(Panel(
        f"[bold]Category: {result.category}[/bold]\n"
        f"Confidence: {result.confidence:.1%}",
        title="Classification Result",
    ))

    category_descriptions = {
        "debugging": "Active debugging with edits and error recovery loops",
        "building": "Active feature development with writes and executions",
        "exploring": "Code exploration with reads and searches, minimal edits",
        "lost": "Confused or circular behavior, reading without progress",
        "verifying": "Verifying changes with reads after edits and test execution",
    }

    desc_table = Table(title="Profile Descriptions", show_lines=True)
    desc_table.add_column("Profile", style="bold")
    desc_table.add_column("Description")
    desc_table.add_column("Your Score", justify="right")

    for name, desc in profiles.items():
        score = result.profile_scores.get(name, 0.0)
        is_match = name == result.category
        desc_table.add_row(
            f"{'→ ' if is_match else '  '}{name}",
            desc,
            f"[bold]{score:.1%}[/bold]" if is_match else f"{score:.1%}",
        )
    console.print(desc_table)


@cli.command()
@click.argument("trace_file", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), default="profile_chart.png", help="Output image path")
def visualize(trace_file: str, output: str) -> None:
    """Generate visualization charts for an agent session."""
    profiler = AgentProfiler()
    visualizer = ProfileVisualizer()

    with console.status("[bold green]Profiling and generating charts..."):
        result = profiler.profile(trace_file)

    console.print("[bold]Generating profile radar chart...[/bold]")
    fig1 = visualizer.generate_profile_chart(result, output=output)
    console.print(f"  [green]Saved: {output}[/green]")

    heatmap_path = str(Path(output).with_name(Path(output).stem + "_heatmap.png"))
    console.print("[bold]Generating transition heatmap...[/bold]")
    fig2 = visualizer.generate_transition_heatmap(trace_file, output=heatmap_path)
    console.print(f"  [green]Saved: {heatmap_path}[/green]")

    pie_path = str(Path(output).with_name(Path(output).stem + "_tools.png"))
    console.print("[bold]Generating tool distribution pie chart...[/bold]")
    fig3 = visualizer.generate_tool_distribution_pie(trace_file, output=pie_path)
    console.print(f"  [green]Saved: {pie_path}[/green]")


if __name__ == "__main__":
    cli()
