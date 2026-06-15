"""Anvil CLI — the command line agent that actually verifies its work."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from anvil import __version__
from anvil.agents.agent_manager import AgentManager
from anvil.agents.builtin_agents import BUILTIN_AGENTS
from anvil.core.config import AnvilConfig
from anvil.core.engine import AnvilEngine, EngineResult
from anvil.core.init_project import ProjectInitializer
from anvil.daemon.server import AgentDaemon

console = Console()


def print_banner():
    banner = """
[bold cyan]  ___                      _____           _     [/]
[bold cyan] / _ \\ _ __   ___ _ __    / ___| ___  ___| |__  [/]
[bold cyan]| | | | '_ \\ / _ \\ '_ \\  | |  _ / _ \\/ __| '_ \\ [/]
[bold cyan]| |_| | |_) |  __/ | | | | |_| |  __/\\__ \\ | | |[/]
[bold cyan] \\___/| .__/ \\___|_| |_|  \\____|\\___|___/_| |_|[/]
[bold cyan]      |_|  [dim]v0.2.0 — self-verified coding agent[/]
"""
    console.print(banner)
    console.print("[dim]Generate → Execute → Verify → Recover[/]")
    console.print("[dim]Trained on 210K examples of real agents doing exactly this.[/]")
    console.print("[dim]Press [bold]Tab[/] to switch agents. Use [bold]@agent[/] to invoke subagents.[/]")
    console.print()


def format_result(result: EngineResult) -> None:
    if result.success:
        console.print(f"\n[bold green]✓ Task completed and verified[/] [dim](agent: {result.agent_name})[/]")
    else:
        console.print(f"\n[bold red]✗ Task failed[/] [dim](agent: {result.agent_name})[/]")
        if result.error:
            console.print(f"[red]Error: {result.error}[/]")

    if result.output:
        console.print(Panel(result.output[:2000], title="Output", border_style="cyan"))

    if result.verify_report:
        console.print("\n[bold]Verification Report:[/]")
        for vr in result.verify_report.results:
            icon = {"pass": "✓", "fail": "✗", "error": "!", "skip": "—"}.get(vr.status.value, "?")
            color = {"pass": "green", "fail": "red", "error": "yellow", "skip": "dim"}.get(vr.status.value, "white")
            console.print(f"  [{color}]{icon}[/{color}] {vr.checker}: {vr.message}")
            if vr.details:
                for line in vr.details.split("\n")[:3]:
                    console.print(f"      [dim]{line}[/]")

    if result.session:
        console.print(
            f"\n[dim]Session: {result.session.id} | Steps: {result.session.stats.total_steps} | "
            f"Errors: {result.session.stats.error_rate:.0%} | "
            f"Recovery: {result.session.stats.recovery_rate:.0%}[/]"
        )


@click.group(invoke_without_command=True)
@click.option("--model", "-m", default="shellwhisperer", help="Model to use (shellwhisperer, local, gpt-4o, claude-3.5-sonnet)")
@click.option("--agent", "-a", default=None, help="Agent to use (build, plan, explore, general, scout)")
@click.option("--config", "-c", type=click.Path(), help="Config file path")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--quiet", "-q", is_flag=True, help="Minimal output")
@click.version_option(version=__version__, prog_name="anvil")
@click.pass_context
def main(ctx, model, agent, config, verbose, quiet):
    """Anvil — the self-verified coding agent.

    Every other open agent generates and hopes. This one generates,
    runs, checks, and fixes — because it was trained on 210K examples
    of real agents doing exactly that.

    Use --agent to pick a persona, or @mention subagents mid-conversation.
    """
    ctx.ensure_object(dict)
    if config:
        cfg = AnvilConfig.from_file(Path(config))
    else:
        cfg = AnvilConfig()
    cfg.model.model = model
    cfg.verbose = verbose
    cfg.quiet = quiet
    if agent:
        cfg.default_agent = agent
    ctx.obj["config"] = cfg
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
@click.argument("task", nargs=-1, required=True)
@click.option("--max-iterations", "-i", default=20, help="Max verify-recover cycles")
@click.option("--no-verify", is_flag=True, help="Disable verification")
@click.option("--no-recover", is_flag=True, help="Disable auto-recovery")
@click.pass_context
def run(ctx, task, max_iterations, no_verify, no_recover):
    """Run a task with self-verification."""
    if not ctx.obj.get("quiet"):
        print_banner()

    cfg: AnvilConfig = ctx.obj["config"]
    cfg.verify.enabled = not no_verify
    cfg.verify.auto_recover = not no_recover

    # Resolve the agent from config or CLI flag.
    agent_name = cfg.default_agent
    agent_obj = BUILTIN_AGENTS.get(agent_name)
    if agent_obj is None:
        mgr = AgentManager()
        agent_obj = mgr.get(agent_name)
        if agent_obj is None:
            console.print(f"[red]Unknown agent: {agent_name}[/]")
            console.print(f"[dim]Available: {', '.join(BUILTIN_AGENTS.keys())}[/]")
            sys.exit(1)

    task_str = " ".join(task)

    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        console=console, transient=True,
    ) as progress:
        progress.add_task(description=f"[{agent_obj.color}]Agent: {agent_obj.name} — [/{agent_obj.color}] Generating plan...", total=None)
        engine = AnvilEngine(cfg, agent=agent_obj)
        result = engine.run(task_str, max_iterations=max_iterations)

    format_result(result)
    sys.exit(0 if result.success else 1)


@main.command()
@click.argument("task", nargs=-1, required=False)
@click.option("--max-iterations", "-i", default=20)
@click.pass_context
def chat(ctx, task, max_iterations):
    """Interactive chat mode with verification and agent switching."""
    if not ctx.obj.get("quiet"):
        print_banner()

    cfg: AnvilConfig = ctx.obj["config"]
    agent_name = cfg.default_agent
    agent_obj = BUILTIN_AGENTS.get(agent_name) or AgentManager().get(agent_name) or BUILTIN_AGENTS["build"]
    engine = AnvilEngine(cfg, agent=agent_obj)

    console.print(f"[bold]Active agent:[/] [{agent_obj.color}]{agent_obj.name}[/{agent_obj.color}] — {agent_obj.description}")
    console.print("[dim]Type 'exit' to quit, 'verify' to force a check, 'status' to see progress, '@agent task' to invoke subagent, Tab to switch agent[/]\n")

    while True:
        if task:
            user_input = " ".join(task)
            task = ()
        else:
            try:
                user_input = console.input(f"[bold {agent_obj.color}]❯[/] ").strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]Goodbye![/]")
                break

        if not user_input or user_input.lower() in ("exit", "quit"):
            break

        # Agent switch (Tab emulation — user types "switch <name>" or Tab).
        if user_input.lower().startswith("switch ") or user_input == "\t":
            new_name = user_input[7:].strip() if user_input.lower().startswith("switch ") else ""
            if new_name:
                try:
                    switched = engine.switch_agent(new_name)
                    agent_obj = switched
                    console.print(f"[green]Switched to agent: [{switched.color}]{switched.name}[/{switched.color}][/]")
                except (KeyError, ValueError) as exc:
                    console.print(f"[red]{exc}[/]")
            continue

        # Show available agents.
        if user_input.lower() == "agents":
            _print_agents(engine.agent_manager)
            continue

        # Status.
        if user_input.lower() == "status":
            if engine.session:
                console.print(engine.session.format_progress())
            continue

        # Force verify.
        if user_input.lower() == "verify":
            if engine.session:
                files = list(set(
                    str(tc.file_path) for step in engine.session.steps
                    for tc in step.tool_calls if tc.file_path
                ))
                report = engine.verify.verify(files=files, working_dir=cfg.tools.working_dir)
                console.print(report.format_summary())
            continue

        # Check for @mention subagent dispatch.
        mention = engine.agent_manager.parse_mention(user_input)
        if mention:
            sub_name, sub_task = mention
            sub_agent = engine.agent_manager.get(sub_name)
            if sub_agent and sub_agent.is_subagent:
                console.print(f"[dim]Invoking subagent [{sub_agent.color}]{sub_agent.name}[/{sub_agent.color}]...[/]")
                invocation = engine.invoke_subagent(sub_name, sub_task)
                console.print(Panel(invocation.response[:3000], title=f"@{sub_name}", border_style=sub_agent.color))
                continue
            else:
                console.print(f"[yellow]No subagent named '{sub_name}'. Available: {', '.join(engine.agent_manager.agent_names())}[/]")
                continue

        result = engine.run(user_input, max_iterations=max_iterations)
        format_result(result)
        if result.error:
            console.print("[yellow]Recovery: auto-fixing...[/]")


@main.command()
@click.option("--port", "-p", default=8765, help="Port to listen on")
@click.pass_context
def daemon(ctx, port):
    """Start Anvil as a persistent daemon server."""
    cfg: AnvilConfig = ctx.obj["config"]
    cfg.daemon.enabled = True
    cfg.daemon.port = port
    daemon_server = AgentDaemon(cfg, port=port)
    console.print(Panel(
        f"[bold cyan]Anvil Daemon[/]\n"
        f"Running on [bold]http://localhost:{port}[/]\n\n"
        f"Endpoints:\n"
        f"  POST /run       — Execute a task\n"
        f"  GET  /status     — Check daemon\n"
        f"  GET  /sessions  — List sessions",
        title="Daemon Mode", border_style="cyan",
    ))
    daemon_server.start()




@main.command()
@click.pass_context
def tui(ctx):
    """Launch the interactive TUI (default when no subcommand)."""
    from anvil.tui.app import run_tui
    cfg: AnvilConfig = ctx.obj["config"]
    run_tui(cfg)


@main.command()
def models():
    """List available models."""
    console.print("[bold]Available Models:[/]\n")
    table = Table(show_header=True)
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Input $/1M tokens")
    table.add_column("Output $/1M tokens")

    models_info = [
        ("shellwhisperer (fableforge-ai/ShellWhisperer-1.5B)", "Local (Transformers)", "Free", "Free"),
        ("local (fableforge-14b)", "Local (Ollama/llama.cpp)", "Free", "Free"),
        ("gpt-4o", "API (OpenAI)", "$2.50", "$10.00"),
        ("gpt-4o-mini", "API (OpenAI)", "$0.15", "$0.60"),
        ("o3-mini", "API (OpenAI)", "$1.10", "$4.40"),
        ("claude-3.5-sonnet", "API (Anthropic)", "$3.00", "$15.00"),
        ("claude-3.5-haiku", "API (Anthropic)", "$0.80", "$4.00"),
    ]
    for name, typ, in_price, out_price in models_info:
        table.add_row(name, typ, in_price, out_price)
    console.print(table)




@main.command("init")
@click.option("--project-dir", "-d", default=".", type=click.Path(), help="Project directory to initialize")
@click.option("--non-interactive", "-y", is_flag=True, help="Skip confirmation prompts")
@click.pass_context
def init_cmd(ctx, project_dir, non_interactive):
    """Initialize an Anvil project with auto-detected configuration."""
    initializer = ProjectInitializer(
        project_dir=project_dir,
        interactive=not non_interactive,
    )
    result = initializer.init()
    if result.get("status") == "cancelled":
        import sys
        sys.exit(1)


@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--checks", "-c", multiple=True, help="Checks to run: syntax, lint, tests, imports")
@click.pass_context
def verify(ctx, path, checks):
    """Verify files or directories."""
    from anvil.verify.pipeline import VerifyPipeline
    cfg: AnvilConfig = ctx.obj["config"]
    pipeline = VerifyPipeline(cfg.verify)

    path_obj = Path(path)
    if path_obj.is_dir():
        files = [
            str(f) for f in path_obj.rglob("*")
            if f.suffix in (".py", ".js", ".ts", ".rs", ".go") and "node_modules" not in str(f)
        ]
    else:
        files = [str(path_obj)]

    test_cmd = None
    if "tests" in (checks or ["syntax", "lint"]):
        root = Path(cfg.project_root)
        if (root / "pytest.ini").exists() or (root / "pyproject.toml").exists():
            test_cmd = "pytest -x"
        elif (root / "package.json").exists():
            test_cmd = "npm test"

    report = pipeline.verify(
        files=files,
        test_command=test_cmd,
        working_dir=cfg.project_root,
        checks=list(checks) if checks else None,
    )
    console.print(report.format_summary())
    sys.exit(0 if report.passed else 1)


@main.command()
@click.pass_context
def sessions(ctx):
    """List past sessions."""
    sessions_dir = Path.home() / ".anvil" / "sessions"
    if not sessions_dir.exists():
        console.print("[dim]No sessions found.[/]")
        return
    table = Table(show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Task", style="white")
    table.add_column("Steps")
    table.add_column("Status")
    for sid in sorted(sessions_dir.iterdir()):
        summary_file = sid / "summary.json"
        if summary_file.exists():
            data = json.loads(summary_file.read_text())
            table.add_row(
                data.get("session_id", sid.name),
                data.get("task", "")[:50],
                str(data.get("stats", {}).get("total_steps", 0)),
                data.get("status", "unknown"),
            )
    console.print(table)


# ── Agent management commands ───────────────────────────────────────────

@main.group()
def agents():
    """Manage agents — list, create, and inspect."""
    pass


@agents.command("list")
def agents_list():
    """Show available agents (builtins + custom)."""
    mgr = AgentManager()
    _print_agents(mgr)


@agents.command("create")
@click.argument("name")
@click.option("--description", "-d", default="", help="Agent description")
@click.option("--mode", "-m", type=click.Choice(["primary", "subagent"]), default="subagent", help="Agent mode")
@click.option("--model", "-M", default="local", help="Model to use")
@click.option("--temperature", "-t", type=float, default=0.2, help="Sampling temperature")
@click.option("--max-steps", type=int, default=20, help="Maximum steps per task")
def agents_create(name, description, mode, model, temperature, max_steps):
    """Interactively create a new custom agent."""
    console.print(f"\n[bold]Creating agent:[/] [cyan]{name}[/]")
    console.print(f"  Description: {description or '(empty)'}")
    console.print(f"  Mode: {mode}")
    console.print(f"  Model: {model}")
    console.print(f"  Temperature: {temperature}")
    console.print(f"  Max steps: {max_steps}")

    if not description:
        description = click.prompt("  Description", default=f"Custom agent: {name}")

    # Ask for permissions.
    console.print("\n[bold]Tool permissions[/] (allow/ask/deny):")
    perm_rules: dict[str, str] = {}
    for tool in ["bash", "read", "write", "edit", "grep", "glob", "ls"]:
        default = "allow" if tool in ("read", "grep", "glob", "ls") else "ask"
        action = click.prompt(f"  {tool}", default=default, type=click.Choice(["allow", "ask", "deny"]))
        perm_rules[tool] = action

    # Ask for tools whitelist/blacklist.
    console.print("\n[bold]Tools[/] — press Enter for defaults")
    whitelist_str = click.prompt("  Whitelist (comma-separated, empty = all)", default="")
    blacklist_str = click.prompt("  Blacklist (comma-separated, empty = none)", default="")
    tools_whitelist = [t.strip() for t in whitelist_str.split(",") if t.strip()] or []
    tools_blacklist = [t.strip() for t in blacklist_str.split(",") if t.strip()] or []

    # Ask for prompt template.
    console.print("\n[bold]System prompt[/] — press Enter to use default")
    prompt = click.prompt("  Prompt template (or Enter for default)", default="")

    # Build spec dict.
    spec = {
        "description": description,
        "mode": mode,
        "model": model,
        "temperature": temperature,
        "max_steps": max_steps,
        "tools_whitelist": tools_whitelist,
        "tools_blacklist": tools_blacklist,
        "permission": perm_rules,
        "prompt_template": prompt,
    }

    # Save to file.
    agents_dir = Path.cwd() / ".anvil" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    spec_file = agents_dir / f"{name}.json"

    # Write as a named-key JSON (compatible with AgentManager loading).
    agent_json = {name: spec}
    spec_file.write_text(json.dumps(agent_json, indent=2))
    console.print(f"\n[green]✓ Agent '{name}' saved to {spec_file}[/]")
    console.print(f"[dim]Use with: anvil chat --agent {name}[/]")


# ── helpers ─────────────────────────────────────────────────────────────

def _print_agents(mgr: AgentManager) -> None:
    """Render the agent list as a Rich table."""
    table = Table(show_header=True, title="Available Agents")
    table.add_column("Name", style="cyan")
    table.add_column("Mode", style="green")
    table.add_column("Model")
    table.add_column("Description")
    table.add_column("Max Steps", justify="right")
    table.add_column("Tools")

    for agent in mgr.list_agents(include_hidden=False):
        mode_style = "bold green" if agent.is_primary else "dim"
        all_tools = ["bash", "read", "write", "edit", "grep", "glob", "ls"]
        available = agent.available_tools(all_tools)
        tools_str = ", ".join(available) if available else "none"
        table.add_row(
            agent.name,
            f"[{mode_style}]{agent.mode.value}[/{mode_style}]",
            agent.model,
            agent.description[:60],
            str(agent.max_steps),
            tools_str,
        )

    console.print(table)
    console.print("[dim]Primary agents own the main loop. Subagents are invoked with @mention.[/]")
    console.print("[dim]Switch primary agent with: anvil chat --agent <name>[/]")


