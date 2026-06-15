"""CLI interface for agentd — start, stop, create, list, resume."""

from __future__ import annotations

import asyncio
import sys

import click

from .daemon import AgentDaemon


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def app(verbose: bool) -> None:
    import logging
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


@app.command()
@click.option("--host", default="0.0.0.0", help="Bind host")
@click.option("--port", default=8721, type=int, help="Bind port")
def start(host: str, port: int) -> None:
    if AgentDaemon.is_running():
        click.echo("agentd is already running")
        sys.exit(1)
    click.echo(f"Starting agentd on {host}:{port}")
    daemon = AgentDaemon(host=host, port=port)
    asyncio.run(daemon.start())


@app.command()
def stop() -> None:
    if not AgentDaemon.is_running():
        click.echo("agentd is not running")
        sys.exit(1)
    if AgentDaemon.stop_running():
        click.echo("Stopped agentd")
    else:
        click.echo("Failed to stop agentd", err=True)
        sys.exit(1)


@app.command()
@click.option("--name", required=True, help="Session name")
@click.option("--model", required=True, help="Model identifier")
@click.option("--system-prompt", default="", help="System prompt")
@click.option("--tools", multiple=True, help="Tool names")
def create(name: str, model: str, system_prompt: str, tools: tuple[str, ...]) -> None:
    from .session_manager import SessionManager
    sm = SessionManager()
    state = sm.create_session(
        name=name,
        model=model,
        config={"system_prompt": system_prompt, "tools": list(tools)},
    )
    click.echo(f"Created session: {state.session_id}")
    click.echo(f"  Name:  {state.name}")
    click.echo(f"  Model: {state.model}")
    click.echo(f"  Status: {state.status.value}")


@app.command("list")
def list_sessions() -> None:
    from .session_manager import SessionManager
    sm = SessionManager()
    sessions = sm.list_sessions()
    if not sessions:
        click.echo("No sessions found")
        return
    click.echo(f"{'ID':<20} {'Name':<20} {'Model':<20} {'Status':<10} {'Created'}")
    click.echo("-" * 90)
    for s in sessions:
        click.echo(
            f"{s.session_id:<20} {s.name:<20} {s.model:<20} {s.status.value:<10} {s.created_at.isoformat()}"
        )


@app.command()
@click.argument("session_id")
@click.option("--checkpoint-id", default=None, help="Resume from specific checkpoint")
def resume(session_id: str, checkpoint_id: str | None) -> None:
    from .session_manager import SessionManager
    sm = SessionManager()
    try:
        state = asyncio.run(sm.resume_session(session_id, checkpoint_id=checkpoint_id))
        click.echo(f"Resumed session: {state.session_id}")
        click.echo(f"  Status: {state.status.value}")
        if checkpoint_id:
            click.echo(f"  From checkpoint: {checkpoint_id}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@app.command()
@click.argument("session_id")
def pause(session_id: str) -> None:
    from .session_manager import SessionManager
    sm = SessionManager()
    try:
        state = asyncio.run(sm.pause_session(session_id))
        click.echo(f"Paused session: {state.session_id}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@app.command()
@click.argument("session_id")
def stop_session(session_id: str) -> None:
    from .session_manager import SessionManager
    sm = SessionManager()
    try:
        state = asyncio.run(sm.stop_session(session_id))
        click.echo(f"Stopped session: {state.session_id}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    app()
