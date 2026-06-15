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


