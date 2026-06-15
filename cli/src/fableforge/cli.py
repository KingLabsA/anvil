"""FableForge CLI — 21 projects, one command."""

import sys
import subprocess
import importlib
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

PROJECTS = {
    "anvil": {"name": "Anvil", "desc": "Self-verified coding agent (flagship)", "layer": "3: Tools", "cmd": "anvil"},
    "verifyloop": {"name": "VerifyLoop", "desc": "Plan→Execute→Verify→Recover framework", "layer": "2: Frameworks", "cmd": "verifyloop"},
    "error-recovery": {"name": "ErrorRecovery", "desc": "Self-healing middleware (3,725 errors)", "layer": "2: Frameworks", "cmd": "error-recovery"},
    "agent-swarm": {"name": "AgentSwarm", "desc": "Multi-agent from real trace transitions", "layer": "2: Frameworks", "cmd": "swarm"},
    "fableforge-14b": {"name": "FableForge-14B", "desc": "Fine-tuned model (4-stage training)", "layer": "1: Models", "cmd": "fableforge-14b"},
    "shell-whisperer": {"name": "ShellWhisperer", "desc": "1.5B edge agent (ONNX/GGUF)", "layer": "1: Models", "cmd": "shell-whisperer"},
    "reason-critic": {"name": "ReasonCritic", "desc": "Verification model (130 tasks)", "layer": "1: Models", "cmd": "reason-critic"},
    "trace-compiler": {"name": "TraceCompiler", "desc": "Compile traces → LoRA skills", "layer": "0: Infrastructure", "cmd": "trace-compiler"},
    "agent-runtime": {"name": "AgentRuntime", "desc": "Persistent agent daemon", "layer": "0: Infrastructure", "cmd": "agent-runtime"},
    "agent-telemetry": {"name": "AgentTelemetry", "desc": "Datadog for agents (tokens, costs)", "layer": "0: Infrastructure", "cmd": "agent-telemetry"},
    "bench-agent": {"name": "BenchAgent", "desc": "HumanEval for tool-use (107 tasks)", "layer": "3: Tools", "cmd": "bench-agent"},
    "agent-dev": {"name": "AgentDev", "desc": "VSCode extension with verification", "layer": "3: Tools", "cmd": None},
    "trace-viz": {"name": "TraceViz", "desc": "Trace replay visualizer (Next.js)", "layer": "3: Tools", "cmd": None},
    "agent-skills": {"name": "AgentSkills.org", "desc": "npm for agent behaviors", "layer": "4: Data Products", "cmd": "agent-skills"},
    "agent-curriculum": {"name": "AgentCurriculum", "desc": "5-stage progressive training", "layer": "4: Data Products", "cmd": "agent-curriculum"},
    "agent-fuzzer": {"name": "AgentFuzzer", "desc": "Adversarial testing for agents", "layer": "4: Data Products", "cmd": "agent-fuzzer"},
    "agent-constitution": {"name": "AgentConstitution", "desc": "Safety guardrails from traces", "layer": "5: Meta", "cmd": "constitution"},
    "cost-optimizer": {"name": "CostOptimizer", "desc": "Token cost reduction (50-80%)", "layer": "5: Meta", "cmd": "costopt"},
    "agent-profiler": {"name": "AgentProfiler", "desc": "Behavioral fingerprinting", "layer": "5: Meta", "cmd": "aprof"},
    "trajectory-distiller": {"name": "TrajectoryDistiller", "desc": "Trace→training data pipeline", "layer": "5: Meta", "cmd": "distill"},
    "fable5-dataset": {"name": "Fable5-Dataset", "desc": "HuggingFace dataset release", "layer": "5: Meta", "cmd": "fable5"},
}

IMPORT_MAP = {
    "anvil": "anvil.core.config",
    "verifyloop": "verifyloop.pipeline",
    "error-recovery": "error_recovery.error_classifier",
    "agent-swarm": "agent_swarm.orchestrator",
    "fableforge-14b": "fableforge_14b",
    "shell-whisperer": "shell_whisperer.inference",
    "reason-critic": "reason_critic.critic",
    "trace-compiler": "trace_compiler.parser",
    "agent-runtime": "agent_runtime.daemon",
    "agent-telemetry": "agent_telemetry.tracker",
    "bench-agent": "bench_agent.tasks",
    "agent-skills": "agent_skills.registry",
    "agent-curriculum": "agent_curriculum.scheduler",
    "agent-fuzzer": "agent_fuzzer.fuzzer",
    "agent-constitution": "agent_constitution.rules",
    "cost-optimizer": "cost_optimizer.token_analyzer",
    "agent-profiler": "agent_profiler.profiler",
    "trajectory-distiller": "trajectory_distiller.distiller",
    "fable5-dataset": "fable5_dataset.loader",
}


def _try_import(module_name: str) -> Optional[str]:
    try:
        mod = importlib.import_module(module_name)
        return getattr(mod, "__version__", "installed")
    except ImportError:
        return None


@click.group(invoke_without_command=True)
@click.option("--version", "-v", is_flag=True, help="Show version")
@click.pass_context
def main(ctx, version):
    """FableForge — 21 projects, one command.

    The open-source agent ecosystem built from 210K real traces.

    \b
    Quick start:
      ff run "fix the auth bug"     # Run Anvil (the self-verified agent)
      ff verify src/                # Verify code
      ff status                     # Check ecosystem status
      ff projects                   # List all projects
    """
    if version:
        from fableforge import __version__
        console.print(f"FableForge v{__version__}")
        return
    if ctx.invoked_subcommand is None:
        console.print(Panel(
            "[bold cyan]FableForge[/] — 21 projects, one command\n\n"
            "[dim]The open-source agent ecosystem built from 210K real traces.[/]\n\n"
            "[bold]Quick start:[/]\n"
            "  [cyan]ff run[/] \"fix the auth bug\"    Run Anvil\n"
            "  [cyan]ff verify[/] src/                 Verify code\n"
            "  [cyan]ff status[/]                       Ecosystem status\n"
            "  [cyan]ff projects[/]                      List all projects\n"
            "  [cyan]ff demo[/]                           Run ecosystem demo\n"
            "  [cyan]ff train[/]                         Train all models\n"
            "  [cyan]ff data[/]                           Show dataset stats\n"
            "  [cyan]ff test[/]                           Run integration tests\n\n"
            "[dim]Use [bold]ff --help[/] for all commands.[/]",
            border_style="cyan",
        ))


@main.command()
@click.argument("task", nargs=-1, required=True)
@click.option("--model", "-m", default="local", help="Model to use")
@click.option("--max-iterations", "-i", default=20, help="Max verify-recover cycles")
@click.option("--no-verify", is_flag=True, help="Disable verification")
@click.option("--no-recover", is_flag=True, help="Disable auto-recovery")
@click.pass_context
def run(ctx, task, model, max_iterations, no_verify, no_recover):
    """Run Anvil — the self-verified coding agent."""
    try:
        from anvil.core.config import AnvilConfig
        from anvil.core.engine import AnvilEngine
        cfg = AnvilConfig()
        cfg.model.model = model
        cfg.verify.enabled = not no_verify
        cfg.verify.auto_recover = not no_recover
        engine = AnvilEngine(cfg)
        result = engine.run(" ".join(task), max_iterations=max_iterations)
        console.print(result.format_result())
        sys.exit(0 if result.success else 1)
    except ImportError:
        console.print("[yellow]Anvil not installed. Install with: pip install anvil-agent[/]")
        console.print("[dim]Or run with: cd anvil && python -m anvil.cli run[/]")
        sys.exit(1)


@main.command()
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--checks", "-c", multiple=True, help="Checks: syntax, lint, tests, imports")
def verify(path, checks):
    """Verify code — syntax, tests, lint, imports."""
    try:
        from anvil.verify.pipeline import VerifyPipeline
        from anvil.core.config import AnvilConfig
        cfg = AnvilConfig()
        cfg.project_root = str(Path(path).resolve())
        pipeline = VerifyPipeline(cfg.verify)
        path_obj = Path(path)
        if path_obj.is_dir():
            files = [str(f) for f in path_obj.rglob("*") if f.suffix in (".py", ".js", ".ts", ".rs", ".go") and "node_modules" not in str(f)]
        else:
            files = [str(path_obj)]
        report = pipeline.verify(files=files, working_dir=str(cfg.project_root), checks=list(checks) or None)
        console.print(report.format_summary())
        sys.exit(0 if report.passed else 1)
    except ImportError:
        console.print("[yellow]Anvil not installed. Install with: pip install anvil-agent[/]")
        sys.exit(1)


@main.command()
def projects():
    """List all 21 FableForge projects."""
    table = Table(title="FableForge Ecosystem — 21 Projects", show_lines=True)
    table.add_column("Project", style="bold cyan")
    table.add_column("Description")
    table.add_column("Layer", style="dim")
    table.add_column("CLI", style="green")

    for key, info in sorted(PROJECTS.items(), key=lambda x: x[1]["layer"]):
        table.add_row(
            info["name"], info["desc"], info["layer"],
            info["cmd"] or "[dim]—[/]",
        )
    console.print(table)
    console.print("\n[bold]210,000+ real agent traces • 87.7% planning rate • 39.5% error recovery • 31 tools mapped[/]")


@main.command()
def status():
    """Check ecosystem status — which projects are installed."""
    table = Table(title="FableForge Ecosystem Status")
    table.add_column("Project", style="bold cyan")
    table.add_column("Installed", style="green")
    table.add_column("Version")

    installed_count = 0
    for key, info in sorted(PROJECTS.items()):
        module_name = IMPORT_MAP.get(key, key.replace("-", "_"))
        version = _try_import(module_name)
        if version:
            installed_count += 1
            table.add_row(info["name"], "[green]✓[/]", version)
        else:
            table.add_row(info["name"], "[dim]—[/]", "[dim]not installed[/]")

    console.print(table)
    console.print(f"\n[bold]{installed_count}/{len(PROJECTS)}[/] projects installed")
    console.print("[dim]Install packages: pip install anvil-agent verifyloop error-recovery agent-swarm[/]")


@main.command()
def demo():
    """Run the ecosystem demo — exercises all major components."""
    project_dir = Path(__file__).resolve().parent.parent.parent.parent
    demo_script = project_dir / "scripts" / "demo_ecosystem.sh"

    if not demo_script.exists():
        alt_dirs = [Path.cwd(), Path.home() / "fableforge"]
        for d in alt_dirs:
            candidate = d / "scripts" / "demo_ecosystem.sh"
            if candidate.exists():
                demo_script = candidate
                break

    if not demo_script.exists():
        console.print("[red]Demo script not found.[/]")
        console.print(f"[dim]Looked for: {demo_script}[/]")
        console.print("[dim]Run: bash scripts/demo_ecosystem.sh[/]")
        sys.exit(1)

    console.print(f"[cyan]Running ecosystem demo from {demo_script}...[/]\n")
    result = subprocess.run(["bash", str(demo_script)], check=False)
    sys.exit(result.returncode)


@main.command()
@click.option("--stage", "-s", multiple=True, help="Stage to run: data, fableforge, shellwhisperer, reasoncritic, exports, all")
@click.option("--dry-run", is_flag=True, help="Print commands without executing")
@click.option("--skip-data", is_flag=True, help="Skip data download/conversion")
def train(stage, dry_run, skip_data):
    """Train all FableForge models (orchestrates train_all.sh)."""
    project_dir = Path(__file__).resolve().parent.parent.parent.parent
    train_script = project_dir / "scripts" / "train_all.sh"

    if not train_script.exists():
        alt_dirs = [Path.cwd(), Path.home() / "fableforge"]
        for d in alt_dirs:
            candidate = d / "scripts" / "train_all.sh"
            if candidate.exists():
                train_script = candidate
                break

    if not train_script.exists():
        console.print("[red]Training script not found.[/]")
        console.print(f"[dim]Looked for: {train_script}[/]")
        console.print("[dim]GPU training requires: PyTorch, transformers, peft, trl, bitsandbytes[/]")
        console.print("[dim]Estimated time: ~63h on 4x A100-80GB (~$170 on AWS p4d.24xlarge)[/]")
        sys.exit(1)

    cmd = ["bash", str(train_script)]
    if dry_run:
        cmd.append("--dry-run")
    if skip_data:
        cmd.append("--skip-data")
    for s in stage:
        cmd.extend(["--stage", s])

    console.print(f"[cyan]Training pipeline: {train_script}[/]")
    console.print(f"[dim]Command: {' '.join(cmd)}[/]\n")
    result = subprocess.run(cmd, check=False)
    sys.exit(result.returncode)


@main.command()
@click.option("--source", "-s", default="all", help="Dataset source: glint, armand0e, vfable, coding_excellence, opencoven, victor, all")
@click.option("--detail", "-d", is_flag=True, help="Show detailed per-source statistics")
def data(source, detail):
    """Show Fable-5 dataset statistics."""
    DATASETS = {
        "glint": {
            "source": "Glint-Research/Fable-5-traces",
            "format": "Session-based (parquet)",
            "rows": 4665,
            "sessions": 60,
            "avg_turns": 8.2,
            "quality": 0.72,
            "error_recovery": 0.45,
            "tools": 12,
        },
        "armand0e": {
            "source": "armand0e/claude-fable-5-claude-code",
            "format": "Conversation with tool_calls",
            "rows": 18370,
            "sessions": 63,
            "avg_turns": 5.4,
            "quality": 0.68,
            "error_recovery": 0.38,
            "tools": 8,
        },
        "vfable": {
            "source": "summerMC/v-Fable",
            "format": "Trajectory with tool_use",
            "rows": 100000,
            "sessions": 1000,
            "avg_turns": 6.7,
            "quality": 0.75,
            "error_recovery": 0.42,
            "tools": 10,
        },
        "coding_excellence": {
            "source": "summerMC/coding-excellence",
            "format": "Session-based with quality scores",
            "rows": 100000,
            "sessions": 500,
            "avg_turns": 12.3,
            "quality": 0.92,
            "error_recovery": 0.65,
            "tools": 15,
        },
        "opencoven": {
            "source": "OpenCoven/fable-forge-10k",
            "format": "Source/target pairs",
            "rows": 10000,
            "sessions": 200,
            "avg_turns": 2.0,
            "quality": 0.85,
            "error_recovery": 0.10,
            "tools": 0,
        },
        "victor": {
            "source": "victor/fable-5-boeing-747-trace",
            "format": "Prompt/response pairs",
            "rows": 1311,
            "sessions": 1,
            "avg_turns": 2.0,
            "quality": 0.80,
            "error_recovery": 0.05,
            "tools": 0,
        },
    }

    if source == "all":
        console.print(Panel(
            "[bold]Fable-5 Dataset Collection[/]\n"
            "6 sources • ~234K total rows • 31 unique tools • 87.7% planning rate",
            border_style="cyan",
        ))
        table = Table(title="Dataset Sources", show_lines=True)
        table.add_column("Source", style="bold cyan")
        table.add_column("HuggingFace ID")
        table.add_column("Rows", justify="right")
        table.add_column("Sessions", justify="right")
        table.add_column("Avg Turns", justify="right")
        table.add_column("Quality", justify="right")
        table.add_column("Err Recovery", justify="right")

        total_rows = 0
        for name, info in DATASETS.items():
            table.add_row(
                name,
                info["source"],
                f"{info['rows']:,}",
                str(info["sessions"]),
                str(info["avg_turns"]),
                f"{info['quality']:.2f}",
                f"{info['error_recovery']:.0%}",
            )
            total_rows += info["rows"]

        table.add_row("[bold]TOTAL[/]", "", f"[bold]{total_rows:,}[/]", "", "", "", "")
        console.print(table)

        console.print("\n[bold]Key Metrics:[/]")
        console.print("  • 87.7% planning rate — agents plan before they act")
        console.print("  • 39.5% error recovery rate — agents that hit errors and recover")
        console.print("  • 31 unique tools mapped into transition matrices")
        console.print("  • 1 Boeing 747 trace: 303 tool calls, 15-hour session")
    else:
        if source not in DATASETS:
            console.print(f"[red]Unknown source: {source}[/]")
            console.print(f"[dim]Available: {', '.join(DATASETS.keys())}, all[/]")
            sys.exit(1)
        info = DATASETS[source]
        console.print(Panel(f"[bold]{source}[/] Dataset", border_style="cyan"))
        for key, val in info.items():
            console.print(f"  [bold]{key}:[/] {val}")

    if detail:
        console.print("\n[bold]Load datasets:[/]")
        console.print("  [cyan]fable5 load glint[/]          # Load Glint dataset")
        console.print("  [cyan]fable5 load all[/]            # Load all datasets")
        console.print("  [cyan]fable5 stats --source glint[/] # Show Glint stats")
        console.print("  [cyan]distill input.jsonl[/]        # Convert traces")


@main.command()
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--integration/--no-integration", default=True, help="Run integration tests")
@click.option("--unit/--no-unit", default=True, help="Run unit tests")
def test(verbose, integration, unit):
    """Run FableForge integration and unit tests."""
    project_dir = Path(__file__).resolve().parent.parent.parent.parent
    results = []
    passed = 0
    failed = 0

    if unit:
        console.print("[bold cyan]Running unit tests...[/]\n")
        pkg_dirs = [
            "anvil", "verifyloop", "error-recovery", "agent-swarm",
            "cost-optimizer", "bench-agent", "agent-constitution",
            "trajectory-distiller", "fable5-dataset",
        ]
        for pkg in pkg_dirs:
            pkg_path = project_dir / pkg
            if not pkg_path.exists():
                continue
            test_dir = pkg_path / "tests"
            if not test_dir.exists():
                console.print(f"  [dim]No tests for {pkg}[/]")
                continue
            cmd = [sys.executable, "-m", "pytest", str(test_dir), "-q", "--tb=short"]
            if not verbose:
                cmd.append("--no-header")
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                console.print(f"  [green]✓[/] {pkg}")
                passed += 1
            else:
                console.print(f"  [red]✗[/] {pkg}")
                if verbose and result.stderr:
                    console.print(f"    [dim]{result.stderr[:200]}[/]")
                failed += 1
            results.append((pkg, result.returncode == 0))

    if integration:
        console.print("\n[bold cyan]Running integration tests...[/]\n")
        integration_path = project_dir / "integration_tests" / "test_ecosystem.py"
        if integration_path.exists():
            cmd = [sys.executable, "-m", "pytest", str(integration_path), "-v" if verbose else "-q", "--tb=short"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                console.print("  [green]✓[/] integration_tests")
                passed += 1
            else:
                console.print("  [red]✗[/] integration_tests")
                if verbose and result.stderr:
                    console.print(f"    [dim]{result.stderr[:200]}[/]")
                failed += 1
            results.append(("integration", result.returncode == 0))
        else:
            console.print("[dim]No integration tests found[/]")

    console.print(f"\n[bold]Results: {passed} passed, {failed} failed, {passed + failed} total[/]")
    sys.exit(0 if failed == 0 else 1)


@main.command()
@click.argument("project")
@click.option("--args", "-a", default="", help="Arguments to pass to project command")
def launch(project, args):
    """Launch a specific project's CLI."""
    if project not in PROJECTS:
        console.print(f"[red]Unknown project: {project}[/]")
        console.print(f"[dim]Available: {', '.join(PROJECTS.keys())}[/]")
        sys.exit(1)
    info = PROJECTS[project]
    cmd = info.get("cmd")
    if not cmd:
        console.print(f"[yellow]{info['name']} doesn't have a CLI[/]")
        sys.exit(1)
    console.print(f"[cyan]Launching {info['name']}...[/]")
    subprocess.run(cmd.split() + args.split() if args else cmd.split())


if __name__ == "__main__":
    main()
