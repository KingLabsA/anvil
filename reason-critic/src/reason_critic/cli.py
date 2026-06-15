"""CLI for ReasonCritic — verify code, train the critic, or start the server.

Usage:
    critic verify --code "def foo(): pass"
    critic verify --file app.py
    critic verify --trace trace.jsonl
    critic train --data pairs.jsonl
    critic serve --port 8000
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """ReasonCritic — a self-verification model that critiques agent output."""
    pass


@cli.command()
@click.option("--code", "-c", help="Code string to verify")
@click.option("--file", "-f", type=click.Path(exists=True), help="File to verify")
@click.option("--trace", "-t", type=click.Path(exists=True), help="Agent trace JSONL to verify")
@click.option("--model", "-m", default="Qwen/Qwen3-7B", help="Model name or path")
@click.option("--backend", "-b", default="local", type=click.Choice(["local", "api", "hybrid"]), help="Backend type")
@click.option("--api-endpoint", default="", help="API endpoint for api/hybrid backend")
@click.option("--language", "-l", default="python", help="Programming language")
@click.option("--context", default="", help="Additional context for verification")
@click.option("--output", "-o", type=click.Path(), help="Output file path (JSON)")
def verify(code, file, trace, model, backend, api_endpoint, language, context, output):
    """Verify code, a file, or an agent trace."""
    from reason_critic.critic import ReasonCritic

    critic = ReasonCritic(backend=backend, model_name=model, api_endpoint=api_endpoint)

    if code:
        result = critic.verify(code=code, context=context, language=language)
        _print_result(result)
        _maybe_save(result, output)

    elif file:
        code_content = Path(file).read_text()
        lang = _language_from_ext(file, language)
        result = critic.verify(code=code_content, context=context, language=lang)
        _print_result(result)
        _maybe_save(result, output)

    elif trace:
        traces = _load_trace(trace)
        run_result = critic.verify_run(run=traces, context=context)
        _print_run_result(run_result)
        if output:
            Path(output).write_text(run_result.to_json())
            console.print(f"[green]Results saved to {output}[/green]")

    else:
        console.print("[red]Provide --code, --file, or --trace[/red]")
        sys.exit(1)


@cli.command()
@click.option("--data", "-d", type=click.Path(exists=True), required=True, help="Training data file (JSONL)")
@click.option("--output", "-o", default="./reason-critic-output", help="Output directory")
@click.option("--model", "-m", default="Qwen/Qwen3-7B", help="Base model name")
@click.option("--stage", "-s", default="all", type=click.Choice(["all", "contrastive", "lora", "dpo"]), help="Training stage")
@click.option("--epochs", "-e", default=None, type=int, help="Override epochs per stage")
@click.option("--batch-size", default=None, type=int, help="Override batch size")
@click.option("--learning-rate", default=None, type=float, help="Override learning rate")
def train(data, output, model, stage, epochs, batch_size, learning_rate):
    """Train the ReasonCritic model."""
    from reason_critic.data_prep import (
        ContrastivePair,
        VerificationExample,
        create_contrastive_pairs,
    )
    from reason_critic.trainer import (
        TrainingConfig,
        run_three_stage_pipeline,
        train_contrastive,
        train_dpo,
        train_lora,
    )

    config = TrainingConfig(model_name=model, output_dir=output)

    if epochs:
        config.contrastive_epochs = epochs
        config.lora_epochs = epochs
        config.dpo_epochs = epochs
    if batch_size:
        config.contrastive_batch_size = batch_size
        config.lora_batch_size = batch_size
        config.dpo_batch_size = batch_size
    if learning_rate:
        config.contrastive_learning_rate = learning_rate
        config.lora_learning_rate = learning_rate
        config.dpo_learning_rate = learning_rate

    pairs = []
    examples = []

    with open(data) as f:
        for line in f:
            if not line.strip():
                continue
            entry = json.loads(line)

            if "correct_code" in entry and "incorrect_code" in entry:
                pairs.append(
                    ContrastivePair(
                        correct_code=entry["correct_code"],
                        incorrect_code=entry["incorrect_code"],
                        explanation=entry.get("explanation", ""),
                        bug_type=entry.get("bug_type", ""),
                        language=entry.get("language", "python"),
                    )
                )
            elif "code" in entry and "label" in entry:
                examples.append(
                    VerificationExample(
                        prompt=entry.get("prompt", "Verify this code:"),
                        code=entry["code"],
                        label=entry["label"],
                        explanation=entry.get("explanation", ""),
                        language=entry.get("language", "python"),
                        source=entry.get("source", ""),
                    )
                )

    if not pairs and examples:
        for ex in examples:
            if ex.label == "PASS":
                pair = create_contrastive_pairs(ex.code)
                pairs.append(pair)

    console.print(f"[bold]Training data:[/bold] {len(pairs)} pairs, {len(examples)} examples")

    if stage == "all":
        results = run_three_stage_pipeline(examples, pairs, output, config)
        for stage_name, path in results.items():
            console.print(f"[green]  {stage_name}: {path}[/green]")
    elif stage == "contrastive":
        path = train_contrastive(pairs, output, config)
        console.print(f"[green]Contrastive model saved to: {path}[/green]")
    elif stage == "lora":
        path = train_lora(pairs, output, config)
        console.print(f"[green]LoRA model saved to: {path}[/green]")
    elif stage == "dpo":
        preferred = [f"PASS: {p.correct_code}" for p in pairs]
        dispreferred = [f"PASS: {p.incorrect_code}" for p in pairs]
        path = train_dpo(preferred, dispreferred, output, config)
        console.print(f"[green]DPO model saved to: {path}[/green]")


@cli.command()
@click.option("--port", "-p", default=8000, help="Server port")
@click.option("--host", "-h", default="0.0.0.0", help="Server host")
@click.option("--model", "-m", default="Qwen/Qwen3-7B", help="Model name")
@click.option("--backend", "-b", default="local", type=click.Choice(["local", "api", "hybrid"]), help="Backend type")
@click.option("--api-endpoint", default="", help="API endpoint for api/hybrid backend")
def serve(port, host, model, backend, api_endpoint):
    """Start the ReasonCritic FastAPI server."""
    import uvicorn

    import reason_critic.server as server_module

    console.print(Panel.fit(
        f"[bold]ReasonCritic Server[/bold]\n"
        f"Host: {host}\n"
        f"Port: {port}\n"
        f"Model: {model}\n"
        f"Backend: {backend}",
        title="Starting Server",
    ))

    # Use the setup endpoint pattern via direct module assignment
    from reason_critic.critic import ReasonCritic

    server_module._critic = ReasonCritic(
        backend=backend,
        model_name=model,
        api_endpoint=api_endpoint,
    )

    if backend != "api":
        from reason_critic.pipeline import GenerateVerifyPipeline, GeneratorWrapper

        server_module._pipeline = GenerateVerifyPipeline(
            generator=GeneratorWrapper(model_name=model),
            critic=server_module._critic,
        )

    uvicorn.run(server_module.app, host=host, port=port)


def _print_result(result):
    """Pretty-print a single verification result."""
    verdict_color = "green" if result.is_pass else "red"
    verdict_icon = "PASS" if result.is_pass else "FAIL"

    console.print(Panel.fit(
        f"[bold {verdict_color}]{verdict_icon} {result.pass_fail}[/bold {verdict_color}]  "
        f"Confidence: {result.confidence:.2f}\n\n"
        f"[bold]Issues:[/bold] {', '.join(result.issues) if result.issues else 'none'}\n"
        f"[bold]Suggestions:[/bold] {', '.join(result.suggestions) if result.suggestions else 'none'}\n\n"
        f"[dim]{result.explanation}[/dim]",
        title="Verification Result",
    ))


def _print_run_result(run_result):
    """Pretty-print a run verification result."""
    verdict_color = "green" if run_result.overall_verdict == "PASS" else "red"

    table = Table(title=f"Run Verification: {run_result.run_id}")
    table.add_column("Step", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Verdict", style=verdict_color)
    table.add_column("Confidence", style="yellow")
    table.add_column("Issues", style="red")

    for sv in run_result.step_verifications:
        verdict_str = sv.result.pass_fail
        v_style = "green" if sv.result.is_pass else "red"
        table.add_row(
            str(sv.step_index),
            sv.step_type,
            f"[{v_style}]{verdict_str}[/{v_style}]",
            f"{sv.result.confidence:.2f}",
            ", ".join(sv.result.issues[:2]) if sv.result.issues else "none",
        )

    console.print(table)
    console.print(f"\n[bold]Overall: [bold {verdict_color}]{run_result.overall_verdict}[/bold {verdict_color}][/bold] "
                  f"({run_result.num_passed}/{run_result.num_passed + run_result.num_failed} steps passed)")
    console.print(f"[dim]{run_result.summary}[/dim]")


def _language_from_ext(filepath: str, default: str = "python") -> str:
    """Detect language from file extension."""
    ext_to_lang = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".rs": "rust",
        ".go": "go",
        ".java": "java",
        ".cpp": "cpp",
        ".c": "c",
        ".rb": "ruby",
    }
    ext = Path(filepath).suffix
    return ext_to_lang.get(ext, default)


def _load_trace(path: str) -> dict:
    """Load a trace from a JSONL file."""
    path = Path(path)

    if path.suffix == ".jsonl":
        steps = []
        with open(path) as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    steps.append(entry)
        return {"id": path.stem, "steps": steps}
    else:
        data = json.loads(path.read_text())
        if "steps" not in data:
            data["steps"] = [data] if "code" in data else []
        return data


def _maybe_save(result, output_path):
    """Optionally save result to file."""
    if output_path:
        Path(output_path).write_text(result.to_json())
        console.print(f"[green]Result saved to {output_path}[/green]")


if __name__ == "__main__":
    cli()
