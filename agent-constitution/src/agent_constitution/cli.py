"""CLI for Agent Constitution."""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from agent_constitution.extractor import ExtractSafetyPatterns
from agent_constitution.rules import ConstitutionalRules, RuleLevel
from agent_constitution.guardrails import GuardrailEngine

console = Console()


@click.group()
def cli() -> None:
    """Agent Constitution - Extract safety patterns and enforce guardrails."""
    pass


@cli.command()
@click.argument("trace_file", type=click.Path(exists=True))
@click.option("--category", type=click.Choice(["refusals", "self_corrections", "flagged_content", "all"]), default="all", help="Category to extract")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path")
def extract(trace_file: str, category: str, output: str | None) -> None:
    """Extract safety patterns from a trace file (JSONL format)."""
    extractor = ExtractSafetyPatterns()

    with console.status("[bold green]Extracting patterns..."):
        if category == "all":
            results = extractor.extract_all(trace_file)
        elif category == "refusals":
            results = {"refusals": extractor.extract_refusals(trace_file)}
        elif category == "self_corrections":
            results = {"self_corrections": extractor.extract_self_corrections(trace_file)}
        else:
            results = {"flagged_content": extractor.extract_flagged_content(trace_file)}

    total_found = sum(len(v) for v in results.values())

    if total_found == 0:
        console.print("[yellow]No safety patterns found in the trace file.[/yellow]")
        return

    for cat_name, patterns in results.items():
        if not patterns:
            continue
        table = Table(title=f"Extracted {cat_name.replace('_', ' ').title()}", show_lines=True)
        table.add_column("Pattern", style="cyan", max_width=40)
        table.add_column("Severity", style="bold")
        table.add_column("Count", justify="right")
        table.add_column("Context", max_width=60)

        for p in patterns[:20]:
            severity_style = {"critical": "bold red", "high": "red", "medium": "yellow", "low": "green"}[p.severity]
            table.add_row(p.pattern[:40], f"[{severity_style}]{p.severity}[/{severity_style}]", str(p.count), p.context[:60])

        console.print(table)

    if output:
        serializable = {}
        for cat_name, patterns in results.items():
            serializable[cat_name] = [
                {"pattern": p.pattern, "context": p.context, "severity": p.severity, "count": p.count}
                for p in patterns
            ]
        Path(output).write_text(json.dumps(serializable, indent=2))
        console.print(f"\n[green]Results saved to {output}[/green]")


@cli.command()
@click.argument("text", type=str)
@click.option("--level", type=click.Choice(["must", "should", "may_not", "all"]), default="all", help="Rule level to check against")
def check(text: str, level: str) -> None:
    """Check output text against constitutional rules."""
    engine = GuardrailEngine()
    rules = ConstitutionalRules()

    if level != "all":
        level_map = {"must": RuleLevel.MUST, "should": RuleLevel.SHOULD, "may_not": RuleLevel.MAY_NOT}
        filtered = rules.get_rules(level=level_map[level])
        filtered_rules = ConstitutionalRules()
        filtered_rules._rules = {r.id: r for r in filtered}
        result = engine.check_output(text, rules=filtered_rules)
    else:
        result = engine.check_output(text)

    if result.passed:
        console.print(Panel("[bold green]✓ PASSED[/bold green]\nOutput complies with all constitutional rules.", title="Guardrail Check"))
    else:
        console.print(Panel("[bold red]✗ FAILED[/bold red]\nOutput violates constitutional rules.", title="Guardrail Check"))
        for v in result.violations:
            severity_style = {"MUST": "bold red", "SHOULD": "yellow", "MAY_NOT": "red"}[v.rule.level.value.upper()]
            console.print(f"\n  [{severity_style}]{v.rule.id}[/{severity_style}] {v.rule.description}")
            console.print(f"  [dim]Matched: {v.matched_text[:80]}[/dim]")
            console.print(f"  [blue]Suggestion: {v.suggestion}[/blue]")

    if result.suggestions:
        console.print("\n[bold]Suggestions:[/bold]")
        for i, s in enumerate(result.suggestions, 1):
            console.print(f"  {i}. {s}")


@cli.command()
@click.option("--level", type=click.Choice(["must", "should", "may_not", "all"]), default="all", help="Filter by rule level")
@click.option("--category", default=None, help="Filter by category (safety, privacy, integrity, security, quality, transparency, robustness, destruction, deception, excess, conscience)")
def list_rules(level: str, category: str | None) -> None:
    """List all constitutional rules."""
    rules = ConstitutionalRules()

    if level != "all":
        level_map = {"must": RuleLevel.MUST, "should": RuleLevel.SHOULD, "may_not": RuleLevel.MAY_NOT}
        filtered = rules.get_rules(level=level_map[level])
    else:
        filtered = rules.get_rules()

    if category:
        filtered = [r for r in filtered if r.category == category]

    table = Table(title=f"Constitutional Rules ({len(filtered)} rules)", show_lines=True)
    table.add_column("ID", style="bold", width=12)
    table.add_column("Level", width=8)
    table.add_column("Category", style="cyan", width=12)
    table.add_column("Description", max_width=60)
    table.add_column("Enforcement", width=10)

    for r in filtered:
        level_style = {"MUST": "bold red", "SHOULD": "yellow", "MAY_NOT": "red"}[r.level.value.upper()]
        enforce_style = {"block": "bold red", "warn": "yellow", "log": "green"}[r.enforcement]
        table.add_row(
            r.id,
            f"[{level_style}]{r.level.value.upper()}[/{level_style}]",
            r.category,
            r.description,
            f"[{enforce_style}]{r.enforcement}[/{enforce_style}]",
        )

    console.print(table)
    console.print(f"\nTotal rules: [bold]{rules.count()}[/bold]")


if __name__ == "__main__":
    cli()
