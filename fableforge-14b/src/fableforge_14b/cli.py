"""CLI for FableForge-14B training, merging, quantization, inference, and evaluation."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from fableforge_14b.training.stage1_behavior_shaping import Stage1Config, run_stage1
from fableforge_14b.training.stage2_skill_distillation import Stage2Config, run_stage2
from fableforge_14b.training.stage3_error_recovery import Stage3Config, run_stage3
from fableforge_14b.training.stage4_dpo_alignment import Stage4Config, run_stage4
from fableforge_14b.model.merge_lora import MergeConfig, merge_lora_adapters
from fableforge_14b.model.quantize import QuantizeConfig, quantize
from fableforge_14b.inference.server import InferenceServer, ServerConfig
from fableforge_14b.evaluation.bench_agent import BenchAgent

console = Console()


@click.group()
def cli() -> None:
    """FableForge-14B - 4-stage training, merge, quantize, serve, evaluate."""
    pass


@cli.command()
@click.option("--dataset", type=click.Path(exists=True), help="Path to behavior-shaping dataset")
@click.option("--output", "-o", type=click.Path(), default="stage1_output.jsonl", help="Output file")
@click.option("--model", default="Qwen/Qwen2.5-Coder-14B-Instruct", help="Base model")
@click.option("--max-samples", type=int, default=None, help="Max samples to use")
def stage1(dataset: str | None, output: str, model: str, max_samples: int | None) -> None:
    """Run Stage 1: behavior shaping SFT."""
    config = Stage1Config(base_model=model, output_path=output)
    with console.status("[bold green]Running Stage 1 behavior shaping..."):
        result = run_stage1(config=config, dataset_path=dataset, max_samples=max_samples)
    _print_result(result, "Stage 1 Complete")


@cli.command()
@click.option("--dataset", type=click.Path(exists=True), help="Path to skill distillation dataset")
@click.option("--output", "-o", type=click.Path(), default="stage2_output.jsonl", help="Output file")
@click.option("--model", default="Qwen/Qwen2.5-Coder-14B-Instruct", help="Base model")
@click.option("--min-quality", type=float, default=0.85, help="Minimum quality score")
def stage2(dataset: str | None, output: str, model: str, min_quality: float) -> None:
    """Run Stage 2: skill distillation SFT."""
    config = Stage2Config(base_model=model, output_path=output, min_quality=min_quality)
    with console.status("[bold green]Running Stage 2 skill distillation..."):
        result = run_stage2(config=config, dataset_path=dataset)
    _print_result(result, "Stage 2 Complete")


@cli.command()
@click.option("--dataset", type=click.Path(exists=True), help="Path to error recovery dataset")
@click.option("--output", "-o", type=click.Path(), default="stage3_output.jsonl", help="Output file")
@click.option("--model", default="Qwen/Qwen2.5-Coder-14B-Instruct", help="Base model")
@click.option("--target-per-type", type=int, default=200, help="Target examples per error type")
def stage3(dataset: str | None, output: str, model: str, target_per_type: int) -> None:
    """Run Stage 3: error recovery SFT."""
    config = Stage3Config(base_model=model, output_path=output, target_per_type=target_per_type)
    with console.status("[bold green]Running Stage 3 error recovery..."):
        result = run_stage3(config=config, dataset_path=dataset)
    _print_result(result, "Stage 3 Complete")


@cli.command()
@click.option("--dataset", type=click.Path(exists=True), help="Path to DPO preference dataset")
@click.option("--output", "-o", type=click.Path(), default="stage4_output.jsonl", help="Output file")
@click.option("--model", default="Qwen/Qwen2.5-Coder-14B-Instruct", help="Base model")
def stage4(dataset: str | None, output: str, model: str) -> None:
    """Run Stage 4: DPO alignment."""
    config = Stage4Config(base_model=model, output_path=output)
    with console.status("[bold green]Running Stage 4 DPO alignment..."):
        result = run_stage4(config=config, dataset_path=dataset)
    _print_result(result, "Stage 4 Complete")


@cli.command()
@click.option("--adapters", "-a", multiple=True, required=True, help="LoRA adapter paths")
@click.option("--output", "-o", type=click.Path(), default="merged_model", help="Output directory")
@click.option("--base-model", default="Qwen/Qwen2.5-Coder-14B-Instruct", help="Base model")
def merge(adapters: tuple[str, ...], output: str, base_model: str) -> None:
    """Merge LoRA adapters into a base model."""
    config = MergeConfig(base_model=base_model, adapters=list(adapters), output_dir=output)
    with console.status("[bold green]Merging adapters..."):
        result = merge_lora_adapters(config=config)
    _print_result(result, "Merge Complete")


@cli.command()
@click.option("--model", "-m", type=click.Path(exists=True), required=True, help="Model path")
@click.option("--output", "-o", type=click.Path(), default="quantized", help="Output directory")
@click.option("--method", type=click.Choice(["gguf", "awq", "gptq"]), default="gguf", help="Quantization method")
def quantize_model(model: str, output: str, method: str) -> None:
    """Quantize a merged model (GGUF/AWQ/GPTQ)."""
    config = QuantizeConfig(model_path=model, output_dir=output, method=method)
    with console.status(f"[bold green]Quantizing with {method}..."):
        result = quantize(config=config)
    _print_result(result, "Quantization Complete")


@cli.command()
@click.option("--model", "-m", type=click.Path(exists=True), required=True, help="Model path")
@click.option("--host", default="0.0.0.0", help="Host to bind")
@click.option("--port", type=int, default=8000, help="Port to bind")
def serve(model: str, host: str, port: int) -> None:
    """Start the FableForge-14B inference server."""
    config = ServerConfig(model_path=model, host=host, port=port)
    server = InferenceServer(config)
    console.print(Panel(f"[bold]Starting server at {host}:{port}[/bold]\nModel: {model}"))
    server.run()


@cli.command()
@click.option("--model", "-m", required=True, help="Model identifier or path")
@click.option("--tasks", type=click.Path(exists=True), help="Path to task JSONL")
@click.option("--category", type=click.Choice(["coding", "reasoning", "planning", "verification", "safety"]), help="Task category")
@click.option("--output", "-o", type=click.Path(), default="bench_report.json", help="Report path")
def benchmark(model: str, tasks: str | None, category: str | None, output: str) -> None:
    """Run the FableForge agent benchmark."""
    agent = BenchAgent(model_path=model)
    with console.status("[bold green]Running benchmark..."):
        report = agent.run(tasks_path=tasks, category=category)
    console.print(Panel(
        f"[bold]Benchmark Complete[/bold]\n"
        f"Total: {report.total}\nPassed: {report.passed}\nFailed: {report.failed}\n"
        f"Pass rate: {report.pass_rate:.1%}",
        title="FableForge-14B Benchmark",
    ))
    Path(output).write_text(report.to_json())
    console.print(f"Report saved to {output}")


def _print_result(result: dict, title: str) -> None:
    table = Table(title=title, show_lines=True)
    table.add_column("Key")
    table.add_column("Value")
    for key, value in result.items():
        table.add_row(str(key), str(value)[:200])
    console.print(table)


if __name__ == "__main__":
    cli()
