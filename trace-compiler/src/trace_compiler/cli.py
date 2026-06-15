"""CLI entry point for TraceCompiler.

Commands:
    trace-compiler parse <input.jsonl>                  — Parse traces
    trace-compiler extract --skill debug <input.jsonl>   — Extract skill examples
    trace-compiler compile --skill debug --model qwen3-1.5b <input.jsonl> — Compile into LoRA
    trace-compiler evaluate --skill debug --adapter ./output <input.jsonl> — Evaluate
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from trace_compiler.distiller import Distiller, TrainingConfig
from trace_compiler.evaluator import Evaluator
from trace_compiler.parser import TraceParser
from trace_compiler.skill_extractor import SkillExtractor, SkillType

console = Console()

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)],
)
logger = logging.getLogger("trace_compiler")


def _resolve_skill(skill_name: str) -> SkillType:
    mapping = {st.value: st for st in SkillType}
    if skill_name.lower() in mapping:
        return mapping[skill_name.lower()]
    valid = ", ".join(st.value for st in SkillType)
    raise click.BadParameter(f"Unknown skill '{skill_name}'. Valid skills: {valid}")


def _resolve_model(model_name: str) -> str:
    from trace_compiler.distiller import MODEL_ALIASES
    return MODEL_ALIASES.get(model_name.lower(), model_name)


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
    """TraceCompiler — Compile agent traces into distilled LoRA weights."""


@cli.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option("--format", "trace_format", type=click.Choice(["auto", "glint", "armand0e", "vfable"]), default="auto", help="Trace format")
@click.option("--output", "-o", type=click.Path(path_type=Path), default=None, help="Output file (JSON)")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
def parse(input_file: Path, trace_format: str, output: Path | None, verbose: bool) -> None:
    """Parse JSONL traces into unified TraceRecord format."""
    console.print(f"[bold blue]Parsing:[/bold blue] {input_file}")

    parser = TraceParser()
    records = parser.parse_file(input_file)

    console.print(f"[green]Parsed {len(records)} records[/green]")

    if verbose:
        for rec in records[:10]:
            console.print(f"  {rec.role}: {rec.content[:80]}..." if len(rec.content) > 80 else f"  {rec.role}: {rec.content}")
        if len(records) > 10:
            console.print(f"  ... and {len(records) - 10} more")

    if output:
        data = [
            {
                "role": r.role,
                "content": r.content,
                "thinking": r.thinking,
                "tool_calls": [tc.to_dict() for tc in r.tool_calls],
                "source_format": r.source_format.value,
                "source_uid": r.source_uid,
                "session": r.session,
                "model": r.model,
            }
            for r in records
        ]
        output.write_text(json.dumps(data, indent=2), encoding="utf-8")
        console.print(f"[green]Saved to[/green] {output}")


@cli.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option("--skill", required=True, type=click.Choice([st.value for st in SkillType]), help="Skill type to extract")
@click.option("--min-confidence", type=float, default=0.5, help="Minimum confidence threshold")
@click.option("--output", "-o", type=click.Path(path_type=Path), default=None, help="Output file (JSON)")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
def extract(input_file: Path, skill: str, min_confidence: float, output: Path | None, verbose: bool) -> None:
    """Extract skill examples from parsed traces."""
    skill_type = _resolve_skill(skill)
    console.print(f"[bold blue]Extracting[/bold blue] {skill_type.value} examples from {input_file}")

    parser = TraceParser()
    records = parser.parse_file(input_file)
    console.print(f"  Parsed {len(records)} records")

    extractor = SkillExtractor(min_confidence=min_confidence)
    examples = extractor.extract(records, skill_type=skill_type)
    console.print(f"[green]Found {len(examples)} {skill_type.value} examples[/green]")

    if verbose:
        for i, ex in enumerate(examples[:5]):
            console.print(f"\n  [bold]Example {i + 1}[/bold] (confidence: {ex.confidence:.2f})")
            console.print(f"    Source: {ex.source_uid}")
            console.print(f"    Messages: {len(ex.messages)}")
            if ex.metadata:
                for k, v in ex.metadata.items():
                    console.print(f"    {k}: {v}")
        if len(examples) > 5:
            console.print(f"  ... and {len(examples) - 5} more")

    if output:
        data = [ex.to_training_sample() for ex in examples]
        output.write_text(json.dumps(data, indent=2), encoding="utf-8")
        console.print(f"[green]Saved to[/green] {output}")


@cli.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option("--skill", required=True, type=click.Choice([st.value for st in SkillType]), help="Skill type to train")
@click.option("--model", default="qwen3-1.5b", help="Base model name or alias")
@click.option("--config", type=click.Path(exists=True, path_type=Path), default=None, help="Training config YAML")
@click.option("--output", "-o", type=click.Path(path_type=Path), default="./output", help="Output directory")
@click.option("--min-confidence", type=float, default=0.5, help="Minimum confidence threshold")
def compile(
    input_file: Path,
    skill: str,
    model: str,
    config: Path | None,
    output: Path,
    min_confidence: float,
) -> None:
    """Compile traces into LoRA adapter weights."""
    skill_type = _resolve_skill(skill)
    resolved_model = _resolve_model(model)

    console.print(f"[bold blue]Compiling[/bold blue] {skill_type.value} skill")
    console.print(f"  Input: {input_file}")
    console.print(f"  Model: {resolved_model}")
    console.print(f"  Output: {output}")

    parser = TraceParser()
    records = parser.parse_file(input_file)
    console.print(f"  Parsed {len(records)} records")

    extractor = SkillExtractor(min_confidence=min_confidence)
    examples = extractor.extract(records, skill_type=skill_type)
    console.print(f"  Extracted {len(examples)} examples")

    if len(examples) < 3:
        console.print("[yellow]Warning: Fewer than 3 training examples. Training may not converge well.[/yellow]")

    if config:
        training_config = TrainingConfig.from_yaml(config)
        training_config.model_name = resolved_model
        training_config.output_dir = str(output)
    else:
        training_config = TrainingConfig(
            model_name=resolved_model,
            output_dir=str(output),
        )

    distiller = Distiller(config=training_config)

    console.print("[bold]Starting LoRA training...[/bold]")
    adapter_path = distiller.train(examples, skill_type)
    console.print("[bold green]Training complete![/bold green]")
    console.print(f"  Adapter saved to: {adapter_path}")


@cli.command()
@click.option("--skill", required=True, type=click.Choice([st.value for st in SkillType]), help="Skill type to evaluate")
@click.option("--adapter", required=True, type=click.Path(exists=True, path_type=Path), help="Path to LoRA adapter")
@click.option("--model", default="qwen3-1.5b", help="Base model name or alias")
@click.option("--output", "-o", type=click.Path(path_type=Path), default=None, help="Output report path")
def evaluate(
    skill: str,
    adapter: Path,
    model: str,
    output: Path | None,
) -> None:
    """Evaluate distilled skill adapter against base model."""
    skill_type = _resolve_skill(skill)
    resolved_model = _resolve_model(model)

    console.print(f"[bold blue]Evaluating[/bold blue] {skill_type.value} skill")
    console.print(f"  Base model: {resolved_model}")
    console.print(f"  Adapter: {adapter}")

    evaluator = Evaluator(
        model_name=resolved_model,
        adapter_path=str(adapter),
    )

    report = evaluator.evaluate(
        skill_types=[skill_type],
        output_path=str(output) if output else None,
    )

    table = Table(title=f"Evaluation Results: {skill_type.value}")
    table.add_column("Task", style="cyan")
    table.add_column("Base Score", style="red")
    table.add_column("Adapted Score", style="green")
    table.add_column("Improvement", style="bold")
    table.add_column("Base Latency (ms)", style="dim")
    table.add_column("Adapted Latency (ms)", style="dim")

    for result in report.results:
        imp_color = "green" if result.improvement > 0 else "red"
        table.add_row(
            result.task_name,
            f"{result.base_score:.3f}",
            f"{result.adapted_score:.3f}",
            f"[{imp_color}]{result.improvement:+.3f}[/{imp_color}]",
            f"{result.base_latency_ms:.0f}",
            f"{result.adapted_latency_ms:.0f}",
        )

    console.print(table)

    console.print("\n[bold]Overall:[/bold]")
    console.print(f"  Base score:     {report.overall_base_score:.3f}")
    console.print(f"  Adapted score:  {report.overall_adapted_score:.3f}")
    console.print(f"  Improvement:    {report.overall_improvement:+.3f}")

    if output:
        console.print(f"\n[green]Report saved to[/green] {output}")


@cli.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option("--verbose", "-v", is_flag=True, help="Show format details")
def inspect(input_file: Path, verbose: bool) -> None:
    """Inspect a trace file to determine its format and content summary."""
    from trace_compiler.parser import _detect_format

    console.print(f"[bold blue]Inspecting:[/bold blue] {input_file}")

    text = input_file.read_text(encoding="utf-8")
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    format_counts: dict[str, int] = {}
    total_records = 0

    for line in lines:
        try:
            obj = json.loads(line)
            fmt = _detect_format(obj)
            format_counts[fmt.value] = format_counts.get(fmt.value, 0) + 1
            total_records += 1
        except json.JSONDecodeError:
            pass

    console.print(f"  Total lines: {len(lines)}")
    console.print(f"  Valid JSON: {total_records}")
    console.print("  Format distribution:")
    for fmt_name, count in format_counts.items():
        pct = (count / total_records * 100) if total_records > 0 else 0
        console.print(f"    {fmt_name}: {count} ({pct:.1f}%)")

    if verbose:
        parser = TraceParser()
        records = parser.parse_file(input_file)

        role_counts: dict[str, int] = {}
        tool_call_count = 0
        thinking_count = 0

        for r in records:
            role_counts[r.role] = role_counts.get(r.role, 0) + 1
            if r.tool_calls:
                tool_call_count += 1
            if r.thinking:
                thinking_count += 1

        console.print(f"\n  [bold]Parsed records:[/bold] {len(records)}")
        console.print("  Role distribution:")
        for role, count in role_counts.items():
            console.print(f"    {role}: {count}")
        console.print(f"  Records with tool calls: {tool_call_count}")
        console.print(f"  Records with thinking: {thinking_count}")


if __name__ == "__main__":
    cli()
