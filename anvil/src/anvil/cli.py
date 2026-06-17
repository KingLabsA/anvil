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
@click.option(
    "--flow", "-f",
    type=click.Choice(["brainstorm", "plan", "work", "lfg"]),
    default=None,
    help="Wrap the task in a compound-engineering flow",
)
@click.pass_context
def run(ctx, task, max_iterations, no_verify, no_recover, flow):
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

    # Optionally wrap the task in a compound-engineering flow template.
    if flow:
        from anvil.commands.command_manager import CommandManager

        cmd_mgr = CommandManager(project_root=cfg.project_root)
        rendered = cmd_mgr.execute(f"/{flow}", task_str)
        task_str = rendered.get("prompt") or rendered.get("output") or task_str

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
@click.argument("service", required=True)
@click.option("--base-url", "-u", default="", help="API base URL")
@click.option("--spec-url", "-s", default="", help="OpenAPI/Swagger spec URL")
@click.option("--spec-file", default="", help="Local OpenAPI/Swagger JSON file")
@click.option("--output-dir", "-o", default=None, help="Skills output directory")
@click.pass_context
def press(ctx, service, base_url, spec_url, spec_file, output_dir):
    """Printing Press: generate a CLI + skill wrapper for an API service."""
    import json as _json
    import urllib.request

    from anvil.printing_press import press as _press

    cfg: AnvilConfig = ctx.obj["config"]
    spec = None
    if spec_file:
        try:
            spec = _json.loads(Path(spec_file).read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]Failed to read spec file: {e}[/]")
            sys.exit(1)
    elif spec_url:
        try:
            with urllib.request.urlopen(spec_url, timeout=30) as resp:
                spec = _json.loads(resp.read().decode())
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]Failed to fetch spec URL: {e}[/]")
            sys.exit(1)

    out_dir = output_dir or (Path(cfg.project_root or ".") / ".anvil" / "skills")
    try:
        result = _press(service, base_url=base_url, spec=spec, output_dir=out_dir)
    except ValueError as e:
        console.print(f"[red]{e}[/]")
        sys.exit(1)

    console.print(f"[green]Pressed[/] [bold]{service}[/] -> {len(result.endpoints)} endpoint(s)")
    console.print(f"  Base URL: {result.base_url}")
    console.print(f"  CLI:   {result.cli_path}")
    console.print(f"  Skill: {result.skill_path}")
    console.print(f"  Load with: [cyan]skill name={result.cli_path.parent.name}[/]")
    console.print(f"  Try: [cyan]python {result.cli_path} --list[/]")
    sys.exit(0)


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
@click.option("--host", "-h", default="127.0.0.1", help="Host to bind")
@click.option("--port", "-p", default=8000, help="Port to bind")
@click.pass_context
def serve(ctx, host, port):
    """Start the web UI server (browser-based interface)."""
    cfg: AnvilConfig = ctx.obj["config"]
    console.print(f"[bold green]Starting Anvil web UI at http://{host}:{port}[/]")
    console.print("[dim]Press Ctrl+C to stop[/]\n")
    from anvil.web.server import create_app
    import uvicorn
    app = create_app(config=cfg)
    uvicorn.run(app, host=host, port=port)


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


@main.command()
@click.argument("session_id")
@click.option("--output", "-o", type=click.Path(), help="Save to file instead of printing")
@click.option("--link", "-l", is_flag=True, help="Generate shareable link")
def share(session_id, output, link):
    """Share a session — export as JSON or generate shareable link."""
    from anvil.core.session import Session
    
    session = Session.load(session_id)
    if not session:
        console.print(f"[red]Session {session_id} not found.[/]")
        sys.exit(1)
    
    # Load full session data from step files
    session_dir = Path.home() / ".anvil" / "sessions" / session_id
    if session_dir.exists():
        for step_file in sorted(session_dir.glob("step_*.json")):
            try:
                step_data = json.loads(step_file.read_text())
                from anvil.core.session import Step, StepKind, StepStatus, ToolCall
                tool_calls = [ToolCall(**tc) for tc in step_data.get("tool_calls", [])]
                step = Step(
                    kind=StepKind(step_data["kind"]),
                    content=step_data["content"],
                    tool_calls=tool_calls,
                    status=StepStatus(step_data["status"]),
                    verify_result=step_data.get("verify_result"),
                    recovery_attempts=step_data.get("recovery_attempts", 0),
                    duration_ms=step_data.get("duration_ms", 0.0),
                    timestamp=step_data.get("timestamp", 0.0),
                )
                session.steps.append(step)
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
    
    if link:
        shareable = session.to_shareable_link()
        if output:
            Path(output).write_text(shareable)
            console.print(f"[green]Shareable link saved to {output}[/]")
        else:
            console.print(f"\n[bold]Shareable link:[/bold]")
            console.print(f"[cyan]{shareable}[/]")
            console.print(f"\n[dim]Share this link to let others import this session.[/]")
    else:
        json_data = session.to_json()
        if output:
            Path(output).write_text(json_data)
            console.print(f"[green]Session exported to {output}[/]")
        else:
            console.print(json_data)


@main.command()
@click.argument("source")
@click.option("--id", "session_id", help="Override session ID")
def import_session(source, session_id):
    """Import a session from JSON file or shareable link."""
    from anvil.core.session import Session
    
    # Determine if source is a link or file
    if source.startswith("anvil://"):
        try:
            session = Session.from_shareable_link(source)
            console.print("[green]Session imported from shareable link.[/]")
        except (ValueError, json.JSONDecodeError) as e:
            console.print(f"[red]Invalid shareable link: {e}[/]")
            sys.exit(1)
    else:
        # Treat as file path
        path = Path(source)
        if not path.exists():
            console.print(f"[red]File not found: {source}[/]")
            sys.exit(1)
        try:
            json_data = path.read_text()
            session = Session.from_json(json_data)
            console.print(f"[green]Session imported from {source}[/]")
        except (json.JSONDecodeError, KeyError) as e:
            console.print(f"[red]Invalid session file: {e}[/]")
            sys.exit(1)
    
    # Override ID if provided
    if session_id:
        session.id = session_id
    
    # Save the imported session
    session.persist = True
    session_dir = Path.home() / ".anvil" / "sessions" / session.id
    session_dir.mkdir(parents=True, exist_ok=True)
    
    # Save summary
    summary = session.summary()
    (session_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    
    # Save steps
    for i, step in enumerate(session.steps):
        from dataclasses import asdict
        step_file = session_dir / f"step_{i:04d}.json"
        step_file.write_text(json.dumps(asdict(step), indent=2, default=str))
    
    console.print(f"[green]Session {session.id} saved.[/]")
    console.print(f"[dim]Task: {session.task}[/]")
    console.print(f"[dim]Steps: {len(session.steps)}[/]")


# ── Skill management commands ───────────────────────────────────────────

@main.group()
def skills():
    """Manage skills — search, install, list, remove."""
    pass


@skills.command("search")
@click.argument("query")
@click.option("--limit", "-n", default=20, help="Maximum results")
def skills_search(query, limit):
    """Search for available skills."""
    from anvil.skills.registry import SkillRegistry
    registry = SkillRegistry()
    results = registry.search(query, limit)
    if not results:
        console.print(f"[dim]No skills found matching '{query}'[/]")
        return
    table = Table(show_header=True)
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Tags")
    for skill in results:
        table.add_row(skill.name, skill.description[:60], ", ".join(skill.tags[:3]))
    console.print(table)


@skills.command("list")
def skills_list():
    """List installed skills."""
    from anvil.skills.registry import SkillRegistry
    registry = SkillRegistry()
    skills = registry.list_installed()
    if not skills:
        console.print("[dim]No skills installed.[/]")
        return
    table = Table(show_header=True)
    table.add_column("Name", style="cyan")
    table.add_column("Version")
    table.add_column("Description")
    table.add_column("Tags")
    for skill in skills:
        table.add_row(
            skill.name,
            skill.version,
            skill.description[:50],
            ", ".join(skill.tags[:3])
        )
    console.print(table)


@skills.command("install")
@click.argument("source")
@click.option("--name", help="Custom name for the skill")
def skills_install(source, name):
    """Install a skill from GitHub URL or local path."""
    from anvil.skills.registry import SkillRegistry
    registry = SkillRegistry()
    try:
        if source.startswith("https://github.com/"):
            skill = registry.install_from_github(source, name)
        else:
            skill = registry.install_from_path(source, name)
        console.print(f"[green]✓ Installed skill: {skill.name}[/]")
        console.print(f"[dim]Location: {skill.path}[/]")
    except Exception as e:
        console.print(f"[red]Failed to install: {e}[/]")
        sys.exit(1)


@skills.command("remove")
@click.argument("name")
def skills_remove(name):
    """Remove an installed skill."""
    from anvil.skills.registry import SkillRegistry
    registry = SkillRegistry()
    if registry.uninstall(name):
        console.print(f"[green]✓ Removed skill: {name}[/]")
    else:
        console.print(f"[red]Skill '{name}' not found.[/]")
        sys.exit(1)


@skills.command("info")
@click.argument("name")
def skills_info(name):
    """Show detailed info about an installed skill."""
    from anvil.skills.registry import SkillRegistry
    registry = SkillRegistry()
    skill = registry.get_skill(name)
    if not skill:
        console.print(f"[red]Skill '{name}' not found.[/]")
        sys.exit(1)
    console.print(f"[bold cyan]{skill.name}[/] v{skill.version}")
    console.print(f"[dim]Author: {skill.author or 'Unknown'}[/]")
    console.print(f"[dim]Source: {skill.source}[/]")
    console.print(f"[dim]Path: {skill.path}[/]")
    if skill.tags:
        console.print(f"[dim]Tags: {', '.join(skill.tags)}[/]")
    console.print(f"\n{skill.description}")


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


# ── Memory management commands ─────────────────────────────────────────

@main.group()
def memory():
    """Manage agent memory — persistent cross-session learning."""
    pass


@memory.command("list")
@click.option("--category", "-c", type=click.Choice(["preference", "project", "pattern", "mistake", "fact"]), help="Filter by category")
@click.option("--limit", "-n", default=50, help="Maximum memories to show")
def memory_list(category, limit):
    """List stored memories."""
    from anvil.memory.manager import MemoryManager, MemoryCategory
    
    mgr = MemoryManager()
    cat = MemoryCategory(category) if category else None
    memories = mgr.list(category=cat, limit=limit)
    
    if not memories:
        console.print("[dim]No memories found.[/]")
        return
    
    table = Table(show_header=True, title="Agent Memories")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Category", style="green")
    table.add_column("Content")
    table.add_column("Importance", justify="right")
    table.add_column("Uses", justify="right")
    
    for mem in memories:
        table.add_row(
            mem.id,
            mem.category.value,
            mem.content[:60],
            f"{mem.importance:.2f}",
            str(mem.use_count),
        )
    
    console.print(table)


@memory.command("add")
@click.option("--category", "-c", type=click.Choice(["preference", "project", "pattern", "mistake", "fact"]), required=True, help="Memory category")
@click.option("--content", "-m", required=True, help="Memory content")
@click.option("--context", "-x", default="", help="Context in which this was learned")
@click.option("--importance", "-i", type=float, default=0.5, help="Importance (0.0 to 1.0)")
def memory_add(category, content, context, importance):
    """Add a new memory."""
    from anvil.memory.manager import MemoryManager, MemoryCategory
    
    mgr = MemoryManager()
    mem = mgr.add(
        category=MemoryCategory(category),
        content=content,
        context=context,
        importance=importance,
    )
    console.print(f"[green]✓ Memory added: {mem.id}[/]")
    console.print(f"  Category: {mem.category.value}")
    console.print(f"  Content: {mem.content}")
    console.print(f"  Importance: {mem.importance:.2f}")


@memory.command("recall")
@click.argument("query")
@click.option("--limit", "-n", default=5, help="Maximum memories to recall")
def memory_recall(query, limit):
    """Recall relevant memories for a query."""
    from anvil.memory.manager import MemoryManager
    
    mgr = MemoryManager()
    memories = mgr.recall(query, limit=limit)
    
    if not memories:
        console.print(f"[dim]No memories found for: {query}[/]")
        return
    
    console.print(f"\n[bold]Recalled memories for:[/] [cyan]{query}[/]\n")
    for mem in memories:
        console.print(f"[green][{mem.category.value}][/] {mem.content}")
        if mem.context:
            console.print(f"  [dim]Context: {mem.context}[/]")
        console.print()


@memory.command("delete")
@click.argument("memory_id")
def memory_delete(memory_id):
    """Delete a memory by ID."""
    from anvil.memory.manager import MemoryManager
    
    mgr = MemoryManager()
    if mgr.delete(memory_id):
        console.print(f"[green]✓ Memory deleted: {memory_id}[/]")
    else:
        console.print(f"[red]Memory not found: {memory_id}[/]")


@memory.command("clear")
@click.option("--category", "-c", type=click.Choice(["preference", "project", "pattern", "mistake", "fact"]), help="Clear only this category")
@click.confirmation_option(prompt="Are you sure you want to clear memories?")
def memory_clear(category):
    """Clear memories (optionally by category)."""
    from anvil.memory.manager import MemoryManager, MemoryCategory
    
    mgr = MemoryManager()
    cat = MemoryCategory(category) if category else None
    count = mgr.clear(category=cat)
    console.print(f"[green]✓ Cleared {count} memories[/]")


# ── Extensions management commands ─────────────────────────────────────

@main.group()
def extensions():
    """Manage extensions — install, list, enable, disable, remove."""
    pass


@extensions.command("list")
def extensions_list():
    """List installed extensions."""
    from anvil.extensions.manager import ExtensionManager
    
    mgr = ExtensionManager()
    exts = mgr.list_extensions()
    
    if not exts:
        console.print("[dim]No extensions installed.[/]")
        return
    
    table = Table(show_header=True, title="Installed Extensions")
    table.add_column("Name", style="cyan")
    table.add_column("Version")
    table.add_column("Description")
    table.add_column("Author")
    table.add_column("Tools")
    
    for ext in exts:
        status = mgr.get_extension(ext.name)
        enabled = "✓" if status and status.enabled else "✗"
        table.add_row(
            f"{enabled} {ext.name}",
            ext.version,
            ext.description[:50],
            ext.author,
            ", ".join(ext.tools) if ext.tools else "none",
        )
    
    console.print(table)


@extensions.command("install")
@click.argument("source")
def extensions_install(source):
    """Install an extension from a local path or git URL."""
    from anvil.extensions.manager import ExtensionManager
    
    mgr = ExtensionManager()
    
    try:
        metadata = mgr.install(source)
        console.print(f"[green]✓ Installed extension: {metadata.name} v{metadata.version}[/]")
        console.print(f"  Description: {metadata.description}")
        console.print(f"  Author: {metadata.author}")
        if metadata.tools:
            console.print(f"  Tools: {', '.join(metadata.tools)}")
        if metadata.hooks:
            console.print(f"  Hooks: {', '.join(metadata.hooks)}")
    except Exception as e:
        console.print(f"[red]Failed to install extension: {e}[/]")
        sys.exit(1)


@extensions.command("uninstall")
@click.argument("name")
def extensions_uninstall(name):
    """Uninstall an extension."""
    from anvil.extensions.manager import ExtensionManager
    
    mgr = ExtensionManager()
    
    if mgr.uninstall(name):
        console.print(f"[green]✓ Uninstalled extension: {name}[/]")
    else:
        console.print(f"[red]Extension not found: {name}[/]")
        sys.exit(1)


@extensions.command("enable")
@click.argument("name")
def extensions_enable(name):
    """Enable an extension."""
    from anvil.extensions.manager import ExtensionManager
    
    mgr = ExtensionManager()
    
    if mgr.enable(name):
        console.print(f"[green]✓ Enabled extension: {name}[/]")
    else:
        console.print(f"[red]Extension not found: {name}[/]")
        sys.exit(1)


@extensions.command("disable")
@click.argument("name")
def extensions_disable(name):
    """Disable an extension."""
    from anvil.extensions.manager import ExtensionManager
    
    mgr = ExtensionManager()
    
    if mgr.disable(name):
        console.print(f"[green]✓ Disabled extension: {name}[/]")
    else:
        console.print(f"[red]Extension not found: {name}[/]")
        sys.exit(1)


@extensions.command("info")
@click.argument("name")
def extensions_info(name):
    """Show detailed info about an extension."""
    from anvil.extensions.manager import ExtensionManager
    
    mgr = ExtensionManager()
    ext = mgr.get_extension(name)
    
    if not ext:
        console.print(f"[red]Extension not found: {name}[/]")
        sys.exit(1)
    
    console.print(f"\n[bold cyan]{ext.metadata.name}[/] v{ext.metadata.version}")
    console.print(f"[dim]Author: {ext.metadata.author}[/]")
    console.print(f"[dim]Path: {ext.path}[/]")
    console.print(f"[dim]Enabled: {'Yes' if ext.enabled else 'No'}[/]")
    
    if ext.metadata.description:
        console.print(f"\n{ext.metadata.description}")
    
    if ext.metadata.tools:
        console.print(f"\n[bold]Tools:[/]")
        for tool in ext.metadata.tools:
            console.print(f"  • {tool}")
    
    if ext.metadata.hooks:
        console.print(f"\n[bold]Hooks:[/]")
        for hook in ext.metadata.hooks:
            console.print(f"  • {hook}")


# ── MCP server command ─────────────────────────────────────────────────

@main.command()
def mcp():
    """Start Anvil as an MCP (Model Context Protocol) server.
    
    The MCP server exposes Anvil's capabilities to other AI agents and tools
    via the Model Context Protocol. It runs on stdin/stdout.
    
    Example:
        anvil mcp
    """
    from anvil.mcp.server import run_mcp_server
    console.print("[dim]Starting Anvil MCP server on stdin/stdout...[/]")
    run_mcp_server()


# ── Authentication commands ────────────────────────────────────────────

@main.group()
def auth():
    """Authentication commands — login, register, logout."""
    pass


@auth.command("login")
@click.option("--email", prompt=True, help="Email address")
@click.option("--password", prompt=True, hide_input=True, help="Password")
def auth_login(email, password):
    """Login to Anvil API (OPTIONAL - only needed for cloud features).
    
    Note: Anvil works fully offline without login. Login is only needed if you
    want to use cloud API features or sync across devices.
    """
    import requests
    from pathlib import Path
    
    console.print("[yellow]Note: Login is OPTIONAL. Anvil works fully offline without login.[/]")
    console.print("[dim]Login is only needed for cloud API features or device sync.[/]\n")
    
    try:
        response = requests.post(
            "http://localhost:8000/api/auth/login",
            json={"email": email, "password": password},
            timeout=10,
        )
        
        if response.status_code == 200:
            data = response.json()
            # Save tokens
            token_file = Path.home() / ".anvil" / "auth.json"
            token_file.parent.mkdir(parents=True, exist_ok=True)
            token_file.write_text(json.dumps({
                "access_token": data["access_token"],
                "refresh_token": data["refresh_token"],
                "email": email,
            }))
            token_file.chmod(0o600)  # Secure permissions
            
            console.print(f"[green]✓ Logged in as {email}[/]")
        else:
            console.print(f"[red]✗ Login failed: {response.json().get('detail', 'Unknown error')}[/]")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        console.print("[red]✗ Cannot connect to Anvil server. Is it running? (anvil serve)[/]")
        console.print("[yellow]Note: You can still use Anvil offline without login.[/]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗ Login failed: {e}[/]")
        sys.exit(1)


@auth.command("register")
@click.option("--email", prompt=True, help="Email address")
@click.option("--username", prompt=True, help="Username")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True, help="Password")
def auth_register(email, username, password):
    """Register a new Anvil account."""
    import requests
    from pathlib import Path
    
    try:
        response = requests.post(
            "http://localhost:8000/api/auth/register",
            json={"email": email, "username": username, "password": password},
            timeout=10,
        )
        
        if response.status_code == 200:
            data = response.json()
            # Save tokens
            token_file = Path.home() / ".anvil" / "auth.json"
            token_file.parent.mkdir(parents=True, exist_ok=True)
            token_file.write_text(json.dumps({
                "access_token": data["access_token"],
                "refresh_token": data["refresh_token"],
                "email": email,
            }))
            token_file.chmod(0o600)  # Secure permissions
            
            console.print(f"[green]✓ Registered and logged in as {email}[/]")
        else:
            console.print(f"[red]✗ Registration failed: {response.json().get('detail', 'Unknown error')}[/]")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        console.print("[red]✗ Cannot connect to Anvil server. Is it running? (anvil serve)[/]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗ Registration failed: {e}[/]")
        sys.exit(1)


@auth.command("logout")
def auth_logout():
    """Logout from Anvil API."""
    from pathlib import Path
    
    token_file = Path.home() / ".anvil" / "auth.json"
    if token_file.exists():
        token_file.unlink()
        console.print("[green]✓ Logged out[/]")
    else:
        console.print("[yellow]Not logged in[/]")


@auth.command("whoami")
def auth_whoami():
    """Show current logged in user."""
    import requests
    from pathlib import Path
    
    token_file = Path.home() / ".anvil" / "auth.json"
    if not token_file.exists():
        console.print("[yellow]Not logged in. Run 'anvil auth login'[/]")
        return
    
    auth_data = json.loads(token_file.read_text())
    
    try:
        response = requests.get(
            "http://localhost:8000/api/auth/me",
            headers={"Authorization": f"Bearer {auth_data['access_token']}"},
            timeout=10,
        )
        
        if response.status_code == 200:
            user = response.json()
            console.print(f"[cyan]Email:[/] {user['email']}")
            console.print(f"[cyan]Username:[/] {user['username']}")
            console.print(f"[cyan]User ID:[/] {user['id']}")
            console.print(f"[cyan]Active:[/] {'Yes' if user['is_active'] else 'No'}")
            console.print(f"[cyan]Admin:[/] {'Yes' if user['is_admin'] else 'No'}")
        else:
            console.print(f"[red]✗ Failed to get user info: {response.json().get('detail', 'Unknown error')}[/]")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        console.print("[red]✗ Cannot connect to Anvil server. Is it running? (anvil serve)[/]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗ Failed: {e}[/]")
        sys.exit(1)


# ── Debug commands ─────────────────────────────────────────────────────

@main.group()
def debug():
    """Debugging commands — breakpoints, step, continue."""
    pass


@debug.command("start")
@click.argument("file_path")
def debug_start(file_path):
    """Start debugging a file."""
    console.print(f"[cyan]Starting debug session for {file_path}...[/]")
    console.print("[yellow]Debug adapter not yet implemented in CLI[/]")
    console.print("[dim]Use the Web UI for debugging: anvil serve[/]")


@debug.command("breakpoint")
@click.argument("file_path")
@click.argument("line", type=int)
def debug_breakpoint(file_path, line):
    """Set a breakpoint."""
    console.print(f"[cyan]Setting breakpoint at {file_path}:{line}[/]")
    console.print("[yellow]Debug adapter not yet implemented in CLI[/]")


@debug.command("continue")
def debug_continue():
    """Continue execution."""
    console.print("[cyan]Continuing execution...[/]")
    console.print("[yellow]Debug adapter not yet implemented in CLI[/]")


@debug.command("step-over")
def debug_step_over():
    """Step over to next line."""
    console.print("[cyan]Stepping over...[/]")
    console.print("[yellow]Debug adapter not yet implemented in CLI[/]")


@debug.command("step-into")
def debug_step_into():
    """Step into function."""
    console.print("[cyan]Stepping into...[/]")
    console.print("[yellow]Debug adapter not yet implemented in CLI[/]")


@debug.command("step-out")
def debug_step_out():
    """Step out of function."""
    console.print("[cyan]Stepping out...[/]")
    console.print("[yellow]Debug adapter not yet implemented in CLI[/]")


# ── Metrics commands ───────────────────────────────────────────────────

@main.command()
@click.option("--format", "-f", type=click.Choice(["text", "json", "prometheus"]), default="text")
def metrics(format):
    """Show Anvil metrics and statistics."""
    import requests
    
    try:
        if format == "prometheus":
            response = requests.get("http://localhost:8000/api/metrics", timeout=10)
            if response.status_code == 200:
                print(response.text)
            else:
                console.print(f"[red]✗ Failed to get metrics[/]")
                sys.exit(1)
        else:
            # Get basic stats
            response = requests.get("http://localhost:8000/api/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                if format == "json":
                    print(json.dumps(data, indent=2))
                else:
                    console.print("[bold cyan]Anvil Metrics[/]")
                    console.print(f"[cyan]Status:[/] {data['status']}")
                    console.print(f"[cyan]Version:[/] {data['version']}")
                    console.print(f"[cyan]Uptime:[/] {data['uptime_seconds']:.1f}s")
                    console.print(f"[cyan]Timestamp:[/] {data['timestamp']}")
            else:
                console.print(f"[red]✗ Failed to get metrics[/]")
                sys.exit(1)
    except requests.exceptions.ConnectionError:
        console.print("[red]✗ Cannot connect to Anvil server. Is it running? (anvil serve)[/]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗ Failed: {e}[/]")
        sys.exit(1)


# ── Git commands ───────────────────────────────────────────────────────

@main.group()
def git():
    """Git integration commands — auto-commit, diff, undo."""
    pass


@git.command("status")
def git_status():
    """Show git status."""
    import subprocess
    
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            check=True,
        )
        if result.stdout:
            console.print(result.stdout)
        else:
            console.print("[green]Working tree clean[/]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]✗ Git error: {e}[/]")
        sys.exit(1)
    except FileNotFoundError:
        console.print("[red]✗ Git not found. Please install git.[/]")
        sys.exit(1)


@git.command("diff")
@click.option("--staged", is_flag=True, help="Show staged changes")
def git_diff(staged):
    """Show git diff."""
    import subprocess
    
    cmd = ["git", "diff"]
    if staged:
        cmd.append("--staged")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if result.stdout:
            console.print(result.stdout)
        else:
            console.print("[green]No changes[/]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]✗ Git error: {e}[/]")
        sys.exit(1)


@git.command("commit")
@click.option("--message", "-m", help="Commit message")
@click.option("--auto", is_flag=True, help="Auto-generate commit message with AI")
def git_commit(message, auto):
    """Commit changes."""
    import subprocess
    
    if auto:
        console.print("[cyan]Generating commit message with AI...[/]")
        # TODO: Implement AI commit message generation
        message = "Update code with AI assistance"
    
    if not message:
        message = click.prompt("Commit message")
    
    try:
        subprocess.run(["git", "add", "-A"], check=True)
        subprocess.run(["git", "commit", "-m", message], check=True)
        console.print(f"[green]✓ Committed: {message}[/]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]✗ Git error: {e}[/]")
        sys.exit(1)


@git.command("undo")
@click.option("--steps", "-n", default=1, help="Number of commits to undo")
def git_undo(steps):
    """Undo last commit(s)."""
    import subprocess
    
    try:
        subprocess.run(["git", "reset", f"HEAD~{steps}"], check=True)
        console.print(f"[green]✓ Undid {steps} commit(s)[/]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]✗ Git error: {e}[/]")
        sys.exit(1)


# ── Rules commands ─────────────────────────────────────────────────────

@main.group()
def rules():
    """Custom rules and instructions for AI behavior."""
    pass


@rules.command("list")
def rules_list():
    """List all custom rules."""
    from pathlib import Path
    
    rules_dir = Path.home() / ".anvil" / "rules"
    if not rules_dir.exists():
        console.print("[yellow]No custom rules. Use 'anvil rules add' to create one.[/]")
        return
    
    rules_files = list(rules_dir.glob("*.md"))
    if not rules_files:
        console.print("[yellow]No custom rules. Use 'anvil rules add' to create one.[/]")
        return
    
    console.print("[bold cyan]Custom Rules:[/]")
    for rule_file in rules_files:
        console.print(f"  • {rule_file.stem}")


@rules.command("add")
@click.argument("name")
def rules_add(name):
    """Add a new custom rule."""
    from pathlib import Path
    
    rules_dir = Path.home() / ".anvil" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    
    rule_file = rules_dir / f"{name}.md"
    if rule_file.exists():
        console.print(f"[red]✗ Rule '{name}' already exists[/]")
        sys.exit(1)
    
    # Open editor
    content = click.edit(
        f"# {name}\n\n"
        "Write your custom rule/instruction here.\n\n"
        "This will be included in the AI's system prompt.\n"
    )
    
    if content:
        rule_file.write_text(content)
        console.print(f"[green]✓ Added rule: {name}[/]")
    else:
        console.print("[yellow]Cancelled[/]")


@rules.command("show")
@click.argument("name")
def rules_show(name):
    """Show a custom rule."""
    from pathlib import Path
    
    rule_file = Path.home() / ".anvil" / "rules" / f"{name}.md"
    if not rule_file.exists():
        console.print(f"[red]✗ Rule '{name}' not found[/]")
        sys.exit(1)
    
    console.print(rule_file.read_text())


@rules.command("edit")
@click.argument("name")
def rules_edit(name):
    """Edit a custom rule."""
    from pathlib import Path
    
    rule_file = Path.home() / ".anvil" / "rules" / f"{name}.md"
    if not rule_file.exists():
        console.print(f"[red]✗ Rule '{name}' not found[/]")
        sys.exit(1)
    
    content = click.edit(rule_file.read_text())
    if content:
        rule_file.write_text(content)
        console.print(f"[green]✓ Updated rule: {name}[/]")
    else:
        console.print("[yellow]Cancelled[/]")


@rules.command("remove")
@click.argument("name")
def rules_remove(name):
    """Remove a custom rule."""
    from pathlib import Path
    
    rule_file = Path.home() / ".anvil" / "rules" / f"{name}.md"
    if not rule_file.exists():
        console.print(f"[red]✗ Rule '{name}' not found[/]")
        sys.exit(1)
    
    rule_file.unlink()
    console.print(f"[green]✓ Removed rule: {name}[/]")


# ── Codebase commands ─────────────────────────────────────────────────

@main.group()
def codebase():
    """Codebase search and indexing commands."""
    pass


@codebase.command("index")
@click.option("--path", "-p", default=".", help="Path to index")
def codebase_index(path):
    """Index the codebase for semantic search."""
    from anvil.codebase.indexer import CodebaseIndex
    
    indexer = CodebaseIndex(path)
    console.print(f"[cyan]Indexing codebase at {path}...[/]")
    
    count = indexer.index()
    stats = indexer.get_stats()
    
    console.print(f"[green]✓ Indexed {stats['total_chunks']} chunks across {stats['total_files']} files[/]")
    console.print(f"[dim]Languages: {', '.join(f'{k}: {v}' for k, v in stats['languages'].items())}[/]")


@codebase.command("search")
@click.argument("query")
@click.option("--limit", "-n", default=10, help="Maximum results")
def codebase_search(query, limit):
    """Search the codebase semantically."""
    from anvil.codebase.indexer import CodebaseIndex
    
    indexer = CodebaseIndex(".")
    indexer.index()
    
    results = indexer.search(query, limit)
    
    if not results:
        console.print(f"[yellow]No results found for '{query}'[/]")
        return
    
    table = Table(title=f"Search Results for '{query}'")
    table.add_column("File", style="cyan")
    table.add_column("Lines", style="dim")
    table.add_column("Score", style="green")
    table.add_column("Match")
    
    for r in results:
        table.add_row(
            r.chunk.file_path,
            f"{r.chunk.line_start}-{r.chunk.line_end}",
            f"{r.score:.1f}",
            r.match_reason[:50],
        )
    
    console.print(table)


@codebase.command("docs")
@click.argument("query")
@click.option("--limit", "-n", default=5, help="Maximum results")
def codebase_docs(query, limit):
    """Search documentation."""
    from anvil.codebase.docs_rag import DocumentationRAG
    
    rag = DocumentationRAG(".")
    rag.index()
    
    results = rag.search(query, limit)
    
    if not results:
        console.print(f"[yellow]No docs found for '{query}'[/]")
        return
    
    table = Table(title=f"Documentation Results for '{query}'")
    table.add_column("Doc", style="cyan")
    table.add_column("Section")
    table.add_column("Score", style="green")
    
    for r in results:
        table.add_row(
            r.chunk.doc_path,
            r.chunk.section,
            f"{r.score:.1f}",
        )
    
    console.print(table)





# ── MCP commands ──────────────────────────────────────────────────────

@main.group()
def mcp():
    """MCP (Model Context Protocol) commands."""
    pass


@mcp.command("list")
def mcp_list():
    """List available MCP tools."""
    from anvil.mcp.registry import MCPToolRegistry
    
    registry = MCPToolRegistry()
    tools = registry.get_available_tools()
    
    if not tools:
        console.print("[yellow]No MCP tools configured[/]")
        console.print("[dim]Configure MCP servers in ~/.anvil/mcp_servers.json[/]")
        return
    
    table = Table(title="MCP Tools")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Server", style="dim")
    
    for tool in tools:
        table.add_row(
            tool.get("name", "unknown"),
            tool.get("description", "")[:50],
            tool.get("server", "built-in"),
        )
    
    console.print(table)


@mcp.command("call")
@click.argument("tool_name")
@click.argument("args", nargs=-1)
def mcp_call(tool_name, args):
    """Call an MCP tool."""
    from anvil.mcp import MCPToolRegistry
    
    registry = MCPToolRegistry()
    
    # Parse args as key=value pairs
    kwargs = {}
    for arg in args:
        if "=" in arg:
            key, value = arg.split("=", 1)
            kwargs[key] = value
    
    try:
        result = registry.call_tool(tool_name, **kwargs)
        console.print(f"[green]✓ Tool '{tool_name}' executed successfully[/]")
        console.print(Panel(str(result), title="Result", border_style="cyan"))
    except Exception as e:
        console.print(f"[red]✗ Error calling tool: {e}[/]")
        sys.exit(1)


@mcp.command("servers")
def mcp_servers():
    """List configured MCP servers."""
    from anvil.mcp import MCPToolRegistry
    
    registry = MCPToolRegistry()
    servers = registry.list_servers()
    
    if not servers:
        console.print("[yellow]No MCP servers configured[/]")
        return
    
    table = Table(title="MCP Servers")
    table.add_column("Name", style="cyan")
    table.add_column("Type")
    table.add_column("Status", style="green")
    
    for server in servers:
        table.add_row(
            server.name,
            server.type,
            "connected" if server.connected else "disconnected",
        )
    
    console.print(table)


# ── Model commands ────────────────────────────────────────────────────

@main.group()
def models():
    """Model provider commands."""
    pass


@models.command("list")
def models_list():
    """List available model providers."""
    from anvil.models.registry import ModelRegistry
    
    providers = ModelRegistry.list_providers()
    
    table = Table(title="Model Providers")
    table.add_column("Provider", style="cyan")
    table.add_column("Prefix", style="dim")
    table.add_column("Models", style="green")
    table.add_column("Status")
    
    for provider in providers:
        status = "[green]✓ Configured[/]" if provider["configured"] else "[dim]Not configured[/]"
        table.add_row(
            provider["name"],
            provider["prefix"],
            ", ".join(provider["models"][:3]),
            status,
        )
    
    console.print(table)
    console.print(f"\n[dim]Total: {len(providers)} providers, {sum(len(p['models']) for p in providers)} models[/]")


@models.command("test")
@click.argument("provider")
@click.option("--model", "-m", default=None, help="Specific model to test")
def models_test(provider, model):
    """Test a model provider."""
    from anvil.models.registry import ModelRegistry
    
    registry = ModelRegistry()
    
    console.print(f"[cyan]Testing provider: {provider}...[/]")
    
    try:
        result = registry.test_provider(provider, model)
        if result.success:
            console.print(f"[green]✓ Provider '{provider}' is working[/]")
            console.print(f"[dim]Response: {result.response[:100]}...[/]")
        else:
            console.print(f"[red]✗ Provider '{provider}' failed: {result.error}[/]")
            sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗ Error testing provider: {e}[/]")
        sys.exit(1)


# ── Remote commands ───────────────────────────────────────────────────

@main.group()
def remote():
    """Remote access and session sharing commands."""
    pass


@remote.command("share")
@click.argument("session_id")
@click.option("--expires", "-e", default=24, help="Hours until link expires")
def remote_share(session_id, expires):
    """Create a shareable link for a session."""
    from anvil.remote import RemoteControl
    
    control = RemoteControl()
    link = control.create_share_link(session_id, expires_hours=expires)
    
    console.print(f"[green]✓ Share link created[/]")
    console.print(f"[cyan]{link}[/]")
    console.print(f"[dim]Expires in {expires} hours[/]")


@remote.command("list")
def remote_list():
    """List active remote sessions."""
    from anvil.remote import RemoteControl
    
    control = RemoteControl()
    sessions = control.list_sessions()
    
    if not sessions:
        console.print("[yellow]No active remote sessions[/]")
        return
    
    table = Table(title="Active Remote Sessions")
    table.add_column("Session ID", style="cyan")
    table.add_column("Share Link")
    table.add_column("Expires", style="dim")
    table.add_column("Devices", style="green")
    
    for session in sessions:
        table.add_row(
            session.session_id[:8] + "...",
            session.share_link[:30] + "...",
            session.expires_at.strftime("%Y-%m-%d %H:%M"),
            str(len(session.devices)),
        )
    
    console.print(table)


@remote.command("revoke")
@click.argument("share_token")
def remote_revoke(share_token):
    """Revoke a share link."""
    from anvil.remote import RemoteControl
    
    control = RemoteControl()
    control.revoke_share_link(share_token)
    
    console.print(f"[green]✓ Share link revoked[/]")


# ── Instructions commands ─────────────────────────────────────────────

@main.group()
def instructions():
    """Persistent instructions (ANVIL.md) commands."""
    pass


@instructions.command("init")
@click.option("--type", "-t", "project_type", default="general", 
              type=click.Choice(["general", "python", "typescript"]),
              help="Project type for template")
def instructions_init(project_type):
    """Initialize ANVIL.md with template."""
    from anvil.core.instructions import InstructionsTemplate
    
    template = InstructionsTemplate.generate_template(project_type)
    
    anvil_md = Path("ANVIL.md")
    if anvil_md.exists():
        console.print("[yellow]ANVIL.md already exists[/]")
        if not click.confirm("Overwrite?"):
            return
    
    anvil_md.write_text(template)
    console.print(f"[green]✓ Created ANVIL.md with {project_type} template[/]")


@instructions.command("show")
def instructions_show():
    """Show loaded instructions."""
    from anvil.core.instructions import InstructionsLoader
    
    loader = InstructionsLoader(Path("."))
    instructions = loader.load_all()
    
    if not instructions:
        console.print("[yellow]No instructions found[/]")
        console.print("[dim]Create ANVIL.md or .anvil/rules/*.md[/]")
        return
    
    console.print(Panel(instructions, title="Loaded Instructions", border_style="cyan"))


@instructions.command("validate")
def instructions_validate():
    """Validate instructions syntax."""
    from anvil.core.instructions import InstructionsLoader
    
    loader = InstructionsLoader(Path("."))
    instructions = loader.load_all()
    
    if not instructions:
        console.print("[yellow]No instructions to validate[/]")
        return
    
    # Basic validation
    errors = []
    if len(instructions) > 10000:
        errors.append("Instructions too long (>10KB)")
    
    if errors:
        console.print("[red]✗ Validation errors:[/]")
        for error in errors:
            console.print(f"  [red]• {error}[/]")
        sys.exit(1)
    else:
        console.print("[green]✓ Instructions are valid[/]")
