"""FableForge CLI — umbrella command for the entire agent ecosystem."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

__version__ = "0.2.0"

ECOSYSTEM_PROJECTS = [
    ("anvil", "Self-verified coding agent (flagship)", "anvil"),
    ("agent-runtime", "Production agent runtime", "fableforge_agent_runtime"),
    ("agent-skills", "Reusable skill library", "fableforge_agent_skills"),
    ("agent-swarm", "Multi-agent orchestration", "fableforge_agent_swarm"),
    ("agent-telemetry", "Telemetry and observability", "fableforge_agent_telemetry"),
    ("agent-profiler", "Agent performance profiler", "fableforge_agent_profiler"),
    ("agent-constitution", "Constitutional AI constraints", "fableforge_agent_constitution"),
    ("agent-curriculum", "Curriculum learning for agents", "fableforge_agent_curriculum"),
    ("agent-fuzzer", "Agent fuzz testing", "fableforge_agent_fuzzer"),
    ("agent-dev", "VS Code extension for agent dev", None),
    ("bench-agent", "Agent benchmarking harness", "fableforge_bench_agent"),
    ("cost-optimizer", "LLM cost optimization", "fableforge_cost_optimizer"),
    ("error-recovery", "Agent error recovery loops", "fableforge_error_recovery"),
    ("fable5-dataset", "Training dataset curation", "fableforge_fable5_dataset"),
    ("fableforge-14b", "14B flagship model trainer", "fableforge_14b"),
    ("reason-critic", "Reasoning critic model", "reason_critic"),
    ("shell-whisperer", "Shell command model", "shell_whisperer"),
    ("trace-compiler", "Trace compilation and replay", "fableforge_trace_compiler"),
    ("trace-viz", "Trace visualization UI", None),
    ("trajectory-distiller", "Trajectory distillation", "fableforge_trajectory_distiller"),
    ("verifyloop", "Verification loops", "verifyloop"),
]

HF_MODELS = [
    ("ShellWhisperer-1.5B", "fableforge-ai/ShellWhisperer-1.5B", "Shell command generation"),
    ("ReasonCritic-7B", "fableforge-ai/ReasonCritic-7B", "Reasoning critique (training)"),
    ("FableForge-14B", "fableforge-ai/FableForge-14B", "Flagship agent model (training)"),
]


def _project_dir(name: str) -> Path:
    return Path(__file__).parent.parent.parent.parent / name


def _is_installed(pkg: str) -> bool:
    try:
        __import__(pkg)
        return True
    except ImportError:
        return False


@click.group(invoke_without_command=True)
@click.option("--version", is_flag=True, help="Show version and exit")
@click.pass_context
def cli(ctx, version):
    """FableForge — umbrella CLI for the 21-project agent ecosystem."""
    if version:
        console.print(f"FableForge CLI v{__version__}")
        return
    if ctx.invoked_subcommand is None:
        console.print(Panel.fit(
            "[bold cyan]FableForge[/] — 21 open-source projects for building, training, "
            "and deploying self-verified AI agents.\n\n"
            "Run [bold]fableforge list[/] to see all projects.\n"
            "Run [bold]fableforge status[/] for ecosystem health.",
            title="Welcome", border_style="cyan"
        ))


@cli.command("list")
def list_projects():
    """List all 21 FableForge ecosystem projects."""
    table = Table(title="FableForge Ecosystem", show_header=True)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Project", style="cyan")
    table.add_column("Description")
    table.add_column("Package / CLI", style="green")
    table.add_column("Status", style="bold")

    for i, (name, desc, pkg) in enumerate(ECOSYSTEM_PROJECTS, 1):
        status = "✓ installed" if pkg and _is_installed(pkg) else "—"
        table.add_row(str(i), name, desc, pkg or "N/A", status)

    console.print(table)


@cli.command("status")
def status():
    """Show ecosystem health status."""
    table = Table(title="FableForge Status", show_header=True)
    table.add_column("Metric")
    table.add_column("Value")

    installed = sum(1 for _, _, pkg in ECOSYSTEM_PROJECTS if pkg and _is_installed(pkg))
    table.add_row("Total projects", str(len(ECOSYSTEM_PROJECTS)))
    table.add_row("Python packages installed", f"{installed}/{sum(1 for _, _, pkg in ECOSYSTEM_PROJECTS if pkg)}")
    table.add_row("CLI", "anvil, fableforge")
    table.add_row("Flagship model", "fableforge-ai/ShellWhisperer-1.5B")
    table.add_row("Website", "https://kinglabsa.github.io/fableforge/")

    console.print(table)


@cli.command("run")
@click.argument("project")
@click.argument("args", nargs=-1)
def run_project(project: str, args: tuple):
    """Run a sub-project's CLI (e.g., anvil)."""
    mapping = {
        "anvil": ("anvil", ["anvil"] + list(args)),
        "shell-whisperer": ("shell-whisperer", ["python", "-m", "shell_whisperer.cli"] + list(args)),
        "reason-critic": ("reason-critic", ["python", "-m", "reason_critic.cli"] + list(args)),
        "verifyloop": ("verifyloop", ["python", "-m", "verifyloop.cli"] + list(args)),
        "bench-agent": ("bench-agent", ["python", "-m", "fableforge_bench_agent.cli"] + list(args)),
    }
    if project not in mapping:
        console.print(f"[red]Unknown project: {project}[/]")
        console.print(f"[dim]Runnable projects: {', '.join(mapping.keys())}[/]")
        sys.exit(1)

    _, cmd = mapping[project]
    console.print(f"[dim]Running: {' '.join(cmd)}[/]")
    subprocess.run(cmd)


@cli.group("model")
def model_group():
    """Manage FableForge models."""
    pass


@model_group.command("list")
def list_models():
    """List FableForge models on HuggingFace."""
    table = Table(title="FableForge Models", show_header=True)
    table.add_column("Name", style="cyan")
    table.add_column("HuggingFace ID", style="green")
    table.add_column("Purpose")

    for name, repo, purpose in HF_MODELS:
        table.add_row(name, repo, purpose)

    console.print(table)


@model_group.command("download")
@click.argument("model_id")
@click.option("--cache-dir", help="Cache directory")
def download_model(model_id: str, cache_dir: Optional[str]):
    """Download a FableForge model from HuggingFace."""
    try:
        from huggingface_hub import snapshot_download
        console.print(f"[dim]Downloading {model_id}...[/]")
        path = snapshot_download(repo_id=model_id, cache_dir=cache_dir)
        console.print(f"[green]Downloaded to {path}[/]")
    except ImportError:
        console.print("[red]huggingface_hub not installed. Run: pip install huggingface_hub[/]")
        sys.exit(1)


@model_group.command("generate")
@click.argument("prompt")
@click.option("--model", default="fableforge-ai/ShellWhisperer-1.5B", help="Model ID or local path")
@click.option("--max-tokens", default=128, help="Max new tokens")
@click.option("--temperature", default=0.2, help="Sampling temperature")
def generate(prompt: str, model: str, max_tokens: int, temperature: float):
    """Generate text using a FableForge model."""
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch
    except ImportError:
        console.print("[red]transformers and torch required. Run: pip install transformers torch[/]")
        sys.exit(1)

    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    console.print(f"[dim]Loading {model} on {device}...[/]")
    tokenizer = AutoTokenizer.from_pretrained(model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    m = AutoModelForCausalLM.from_pretrained(
        model, torch_dtype=torch.float16 if device == "cuda" else torch.float32, trust_remote_code=True
    ).to(device)

    messages = [
        {"role": "system", "content": "You are ShellWhisperer, an expert at shell commands and coding."},
        {"role": "user", "content": prompt},
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = m.generate(**inputs, max_new_tokens=max_tokens, temperature=temperature, do_sample=temperature > 0)
    result = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    console.print(Panel(result.strip(), title="Generated", border_style="green"))


@cli.group("anvil")
def anvil_group():
    """Dispatch to the Anvil self-verified coding agent."""
    pass


@anvil_group.command("run")
@click.argument("task", nargs=-1, required=True)
@click.option("--model", default="shellwhisperer", help="Model to use")
@click.pass_context
def anvil_run(ctx, task, model):
    """Run Anvil on a task."""
    task_str = " ".join(task)
    console.print(f"[dim]Dispatching to anvil run --model {model} {task_str}[/]")
    subprocess.run(["anvil", "--model", model, "run", task_str])


@anvil_group.command("chat")
@click.option("--model", default="shellwhisperer", help="Model to use")
def anvil_chat(model):
    """Start Anvil interactive chat."""
    subprocess.run(["anvil", "--model", model, "chat"])


@cli.command("install-all")
@click.option("--editable", "-e", is_flag=True, help="Install in editable mode")
def install_all(editable: bool):
    """Install all FableForge Python packages."""
    base = Path(__file__).parent.parent.parent.parent
    for project, _, pkg in ECOSYSTEM_PROJECTS:
        if not pkg:
            continue
        pyproject = base / project / "pyproject.toml"
        if not pyproject.exists():
            continue
        cmd = [sys.executable, "-m", "pip", "install"]
        if editable:
            cmd.append("-e")
        cmd.append(str(base / project))
        console.print(f"[dim]Installing {project}...[/]")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            console.print(f"[red]Failed to install {project}[/]")
            console.print(result.stderr[:300])
        else:
            console.print(f"[green]Installed {project}[/]")


if __name__ == "__main__":
    cli()
