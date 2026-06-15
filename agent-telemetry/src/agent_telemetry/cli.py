"""CLI for AgentTelemetry — analyze traces, view costs, start dashboard."""

from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.table import Table

from agent_telemetry.collector import (
    auto_detect_format,
    calculate_metrics,
    ingest_trace,
)
from agent_telemetry.error_tracker import generate_error_report
from agent_telemetry.models import Span
from agent_telemetry.storage import TelemetryStorage
from agent_telemetry.token_tracker import estimate_cost, format_cost_table

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
    """AgentTelemetry — Datadog for AI agents."""


@cli.command()
@click.argument("trace_file", type=click.Path(exists=True))
@click.option("--format", "fmt", type=click.Choice(["glint", "armand0e", "vfable", "auto"]), default="auto", help="Trace format")
@click.option("--store/--no-store", default=True, help="Store results in database")
def analyze(trace_file: str, fmt: str, store: bool) -> None:
    """Analyze a trace file and display metrics."""
    if fmt == "auto":
        fmt = auto_detect_format(trace_file)
        console.print(f"[dim]Detected format: {fmt}[/dim]")

    spans = ingest_trace(trace_file, fmt=fmt)
    if not spans:
        console.print("[red]No spans found in trace file.[/red]")
        sys.exit(1)

    console.print(f"[green]Loaded {len(spans)} spans[/green]")

    metrics_result = calculate_metrics(spans)
    session = metrics_result["session"]
    tools = metrics_result["tools"]

    console.print(f"\n[bold]Session:[/bold] {session.session_id}")
    console.print(f"[bold]Model:[/bold]    {session.model}")
    console.print(f"[bold]Duration:[/bold]  {session.duration_seconds:.1f}s")

    metrics_table = Table(title="Session Metrics", show_header=True)
    metrics_table.add_column("Metric", style="cyan")
    metrics_table.add_column("Value", justify="right")

    metrics_table.add_row("Total Tokens", f"{session.total_tokens:,}")
    metrics_table.add_row("Total Cost", f"${session.total_cost:.6f}")
    metrics_table.add_row("Tool Calls", str(session.tool_calls))
    metrics_table.add_row("Errors", str(session.error_count))
    metrics_table.add_row("Avg Duration", f"{session.avg_tool_duration_ms:.0f}ms")
    metrics_table.add_row("P50 Duration", f"{session.p50_duration_ms:.0f}ms")
    metrics_table.add_row("P95 Duration", f"{session.p95_duration_ms:.0f}ms")
    metrics_table.add_row("P99 Duration", f"{session.p99_duration_ms:.0f}ms")
    metrics_table.add_row("Cache Hit Rate", f"{session.cache_hit_rate:.1%}")
    console.print(metrics_table)

    tool_table = Table(title="Tool Metrics", show_header=True)
    tool_table.add_column("Tool", style="cyan")
    tool_table.add_column("Calls", justify="right")
    tool_table.add_column("Avg ms", justify="right")
    tool_table.add_column("P95 ms", justify="right")
    tool_table.add_column("Error Rate", justify="right")
    tool_table.add_column("Cost", justify="right", style="green")

    for name, tm in sorted(tools.items()):
        tool_table.add_row(
            name,
            str(tm.call_count),
            f"{tm.avg_duration_ms:.0f}",
            f"{tm.p95_duration_ms:.0f}",
            f"{tm.error_rate:.1%}",
            f"${tm.total_cost_usd:.6f}",
        )
    console.print(tool_table)

    if store:
        storage = TelemetryStorage()
        storage.store_spans(spans)
        storage.store_session_metrics(session)
        console.print(f"\n[dim]Stored {len(spans)} spans in database[/dim]")


@cli.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option("--port", default=8088, type=int, help="Port to bind to")
def dashboard(host: str, port: int) -> None:
    """Start the interactive dashboard server."""
    import uvicorn
    from agent_telemetry.dashboard import app

    console.print(f"[green]Starting AgentTelemetry dashboard on http://{host}:{port}[/green]")
    console.print("[dim]Press Ctrl+C to stop[/dim]")
    uvicorn.run(app, host=host, port=port)


@cli.command()
@click.argument("trace_file", type=click.Path(exists=True))
@click.option("--format", "fmt", type=click.Choice(["glint", "armand0e", "vfable", "auto"]), default="auto", help="Trace format")
def cost(trace_file: str, fmt: str) -> None:
    """Show cost breakdown for a trace file."""
    if fmt == "auto":
        fmt = auto_detect_format(trace_file)
        console.print(f"[dim]Detected format: {fmt}[/dim]")

    spans = ingest_trace(trace_file, fmt=fmt)
    if not spans:
        console.print("[red]No spans found in trace file.[/red]")
        sys.exit(1)

    models: dict[str, list[Span]] = {}
    for s in spans:
        models.setdefault(s.model, []).append(s)

    breakdowns = []
    for model, model_spans in sorted(models.items()):
        bd = estimate_cost(
            sum(s.input_tokens for s in model_spans),
            sum(s.output_tokens for s in model_spans),
            model,
            sum(s.cache_read for s in model_spans),
            sum(s.cache_creation for s in model_spans),
        )
        breakdowns.append(bd)

    console.print(format_cost_table(breakdowns))

    total = sum(b.total_cost for b in breakdowns)
    console.print(f"\n[bold green]Grand Total: ${total:.6f}[/bold green]")


@cli.command()
@click.argument("trace_file", type=click.Path(exists=True))
@click.option("--format", "fmt", type=click.Choice(["glint", "armand0e", "vfable", "auto"]), default="auto", help="Trace format")
def errors(trace_file: str, fmt: str) -> None:
    """Show error report for a trace file."""
    if fmt == "auto":
        fmt = auto_detect_format(trace_file)
        console.print(f"[dim]Detected format: {fmt}[/dim]")

    spans = ingest_trace(trace_file, fmt=fmt)
    if not spans:
        console.print("[red]No spans found in trace file.[/red]")
        sys.exit(1)

    session_id = spans[0].session_id
    report = generate_error_report(session_id, spans=spans)

    console.print(f"\n[bold]Error Report: {session_id}[/bold]")
    console.print(f"Total Errors:  {report.total_errors}")
    console.print(f"Recovered:      {report.recovered_errors}")
    console.print(f"Recovery Rate:  {report.recovery_rate:.0%}")

    if report.errors_by_type:
        type_table = Table(title="Errors by Type", show_header=True)
        type_table.add_column("Error Type", style="red")
        type_table.add_column("Count", justify="right")

        for etype, count in sorted(report.errors_by_type.items(), key=lambda x: -x[1]):
            type_table.add_row(etype, str(count))
        console.print(type_table)

    if report.errors:
        error_table = Table(title="Error Details", show_header=True)
        error_table.add_column("Span ID", style="dim")
        error_table.add_column("Type", style="red")
        error_table.add_column("Tool", style="cyan")
        error_table.add_column("Message", max_width=60)
        error_table.add_column("Recovered")

        for e in report.errors[:50]:
            recovered = "[green]✓[/green]" if e.recovered else "[red]✗[/red]"
            error_table.add_row(
                e.span_id[:12] + "...",
                e.error_type,
                e.tool_name,
                e.error_message[:60],
                recovered,
            )
        console.print(error_table)


@cli.command()
@click.argument("text")
@click.option("--model", default="gpt-4", help="Model name for token counting")
def tokens(text: str, model: str) -> None:
    """Count tokens in a text string."""
    from agent_telemetry.token_tracker import count_tokens

    n = count_tokens(text, model)
    console.print(f"[bold]{n:,}[/bold] tokens ({model})")

    bd = estimate_cost(n, 0, model)
    console.print(f"Input cost (no output): ${bd.input_cost:.6f}")


if __name__ == "__main__":
    cli()
