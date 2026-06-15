"""AgentSwarm CLI — Command-line interface for agent swarm orchestration."""

from __future__ import annotations

import json
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from agent_swarm.orchestrator import SwarmOrchestrator
from agent_swarm.transition_matrix import TransitionMatrix

console = Console()


@click.group()
@click.version_option("0.1.0")
def cli() -> None:
    """AgentSwarm — Orchestrate micro-agent swarms using Markov transition matrices.

    Derived from Fable5 trace data. Key transitions:
      Bash→Bash=0.59, Bash→Edit=0.18, Read→Bash=0.37, Read→Edit=0.22
    """


@cli.command()
@click.argument("task")
@click.option("--max-handoffs", default=20, help="Maximum handoffs before forcing completion")
@click.option("--trace-file", type=click.Path(), help="Path to JSONL trace file for custom transition matrix")
@click.option("--output", "-o", type=click.Path(), help="Save state to file after execution")
@click.option("--json-output", "json_output", is_flag=True, help="Output result as JSON")
def run(task: str, max_handoffs: int, trace_file: str | None, output: str | None, json_output: bool) -> None:
    """Run a task through the agent swarm.

    The swarm starts with the Planner agent, which analyzes the task and
    coordinates handoffs to specialized agents based on the transition matrix.

    The default flow: Planner → Reader → Editor → Verifier
    """
    tm = TransitionMatrix()
    if trace_file:
        tm = TransitionMatrix.from_traces(trace_file)
        console.print(f"[green]Loaded custom transition matrix from {trace_file}[/green]")

    orchestrator = SwarmOrchestrator(transition_matrix=tm, max_handoffs=max_handoffs)
    result = orchestrator.run(task)

    if json_output:
        click.echo(result.model_dump_json(indent=2))
        return

    console.print()
    console.print(Panel(f"[bold blue]{task}[/bold blue]", title="Task", border_style="blue"))

    # Show handoff chain
    tree = Tree("[bold]Handoff Chain[/bold]")
    prev_agent = "planner"
    branch = tree.add("[cyan]planner[/cyan] → analyze task")
    for handoff in result.handoffs:
        prob_str = f" ({handoff.probability:.0%})" if handoff.probability > 0 else ""
        branch = branch.add(f"[cyan]{handoff.from_role.value}[/cyan] → [green]{handoff.to_role.value}[/green]{prob_str}")
        prev_agent = handoff.to_role.value

    console.print(tree)

    # Show transition probabilities used
    table = Table(title="Key Transitions Used", show_header=True)
    table.add_column("From", style="cyan")
    table.add_column("To", style="green")
    table.add_column("Probability", justify="right")
    table.add_column("Visual", justify="left")

    seen = set()
    for handoff in result.handoffs:
        key = (handoff.from_role.value, handoff.to_role.value)
        if key not in seen:
            seen.add(key)
            prob = handoff.probability
            bar = "█" * int(prob * 20)
            table.add_row(key[0], key[1], f"{prob:.2f}", bar)

    console.print(table)

    # Result
    status_color = "green" if result.success else "red"
    console.print()
    console.print(Panel(
        f"[bold {status_color}]{result.status}[/bold {status_color}]\n"
        f"Final agent: [cyan]{result.final_agent}[/cyan]\n"
        f"Total handoffs: [bold]{result.total_handoffs}[/bold]\n"
        f"[dim]{result.final_output}[/dim]",
        title="Result",
        border_style=status_color,
    ))

    if output:
        orchestrator.save_state(output)
        console.print(f"[green]State saved to {output}[/green]")


@cli.command()
@click.option("--task-id", help="Show status for a specific task")
def status(task_id: str | None) -> None:
    """Show the current swarm status.

    Displays information about active agents, tasks, and handoff history.
    """
    orchestrator = SwarmOrchestrator()
    state = orchestrator.get_status(task_id)

    table = Table(title="AgentSwarm Status")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="white")

    if task_id and "task" in state:
        task = state["task"]
        for key, value in task.items():
            if isinstance(value, (list, dict)):
                table.add_row(key, json.dumps(value, indent=2)[:200])
            else:
                table.add_row(key, str(value))
    else:
        for key, value in state.items():
            if isinstance(value, dict):
                for k, v in value.items():
                    if isinstance(v, dict):
                        table.add_row(f"{key}.{k}", json.dumps(v)[:100])
                    else:
                        table.add_row(f"{key}.{k}", str(v))
            else:
                table.add_row(key, str(value))

    console.print(table)


@cli.command()
@click.option("--trace-file", type=click.Path(exists=True), help="Custom trace file for transition matrix")
@click.option("--output", "-o", type=click.Path(), default=None, help="Save visualization to file")
def visualize(trace_file: str | None, output: str | None) -> None:
    """Visualize the swarm transition matrix and agent graph.

    Shows:
    - All agent roles and their available tools
    - Tool-to-tool transition probabilities (from Fable5 data)
    - Role-to-role handoff probabilities
    - Key transitions highlighted
    """
    tm = TransitionMatrix()
    if trace_file:
        tm = TransitionMatrix.from_traces(trace_file)

    orchestrator = SwarmOrchestrator(transition_matrix=tm)
    orchestrator._ensure_agents()

    # Agent roles table
    agent_table = Table(title="Agent Roles", show_header=True)
    agent_table.add_column("Role", style="cyan")
    agent_table.add_column("Tools", style="green")
    agent_table.add_column("Can Hand Off To", style="yellow")

    for role, agent in orchestrator.agents.items():
        tools = ", ".join(agent.tool_names())
        handoffs = ", ".join(r.value for r in agent.can_handoff_to)
        agent_table.add_row(role, tools, handoffs)

    console.print(agent_table)
    console.print()

    # Transition matrix
    trans_table = Table(title="Tool Transition Matrix (Fable5 Data)", show_header=True)
    trans_table.add_column("From", style="cyan")
    trans_table.add_column("Top Predictions", style="white")

    for tool in tm.tools:
        preds = tm.next_tool(tool, top_k=3)
        pred_str = " → ".join(f"{p.name}({p.confidence:.0%})" for p in preds)
        trans_table.add_row(tool, pred_str)

    console.print(trans_table)
    console.print()

    # Key Fable5 transitions
    key_table = Table(title="Key Fable5 Transitions", show_header=True)
    key_table.add_column("Transition", style="cyan")
    key_table.add_column("Probability", justify="right", style="green")
    key_table.add_column("Bar", style="yellow")

    key_transitions = [
        ("bash", "bash"), ("bash", "edit"), ("read", "bash"),
        ("read", "edit"), ("edit", "bash"), ("edit", "read"),
    ]
    for from_t, to_t in key_transitions:
        prob = tm.get_transition_prob(from_t, to_t)
        bar = "█" * int(prob * 40)
        key_table.add_row(f"{from_t} → {to_t}", f"{prob:.2f}", bar)

    console.print(key_table)
    console.print()

    # Handoff probabilities
    handoff_table = Table(title="Role Handoff Probabilities", show_header=True)
    handoff_table.add_column("From", style="cyan")
    handoff_table.add_column("To", style="green")
    handoff_table.add_column("Probability", justify="right")
    handoff_table.add_column("Bar", style="yellow")

    for from_role in ["planner", "reader", "editor", "bash", "verifier"]:
        probs = tm.get_all_handoff_probabilities(from_role)
        for to_role, prob in sorted(probs.items(), key=lambda x: x[1], reverse=True):
            if prob > 0.05:
                bar = "█" * int(prob * 30)
                handoff_table.add_row(from_role, to_role, f"{prob:.2f}", bar)

    console.print(handoff_table)

    if output:
        viz_text = orchestrator.visualize()
        Path(output).write_text(viz_text)
        console.print(f"\n[green]Visualization saved to {output}[/green]")


@cli.command()
@click.argument("trace_file", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), required=True, help="Output JSON path")
def build_matrix(trace_file: str, output: str) -> None:
    """Build a transition matrix from a JSONL trace file.

    Each line of the trace file should be a JSON object with a 'tool_calls'
    list containing objects with a 'name' field.

    Example trace line:
    {"tool_calls": [{"name": "read"}, {"name": "edit"}, {"name": "bash"}]}
    """
    tm = TransitionMatrix.from_traces(trace_file)
    tm.to_json(output)
    console.print(f"[green]Transition matrix saved to {output}[/green]")
    console.print(f"  Tools: {len(tm.tools)}")
    console.print(f"  Matrix shape: {tm.matrix.shape}")

    # Show top transitions for each tool
    console.print()
    console.print("[bold]Top transitions per tool:[/bold]")
    for tool in tm.tools:
        preds = tm.next_tool(tool, top_k=3)
        pred_str = ", ".join(f"{p.name} ({p.confidence:.1%})" for p in preds)
        console.print(f"  {tool}: {pred_str}")


if __name__ == "__main__":
    cli()
