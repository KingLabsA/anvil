"""AgentSkills CLI — Command-line interface for skill management."""

from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.table import Table

from agent_skills.registry import SkillRegistry
from agent_skills.decomposition import SkillDecomposer
from agent_skills.lora_builder import build_lora, LoRABuildConfig

console = Console()


@click.group()
@click.version_option("0.1.0")
def cli() -> None:
    """AgentSkills — Skill registry, decomposition, and LoRA building for coding agents."""


@cli.command()
@click.argument("skill_name")
@click.option("--source", "-s", help="Local path or URL to install from")
def install(skill_name: str, source: str | None) -> None:
    """Install a skill from the registry or a local path."""
    registry = SkillRegistry()
    try:
        meta = registry.install(skill_name, source=source)
        console.print(f"[green]✓[/green] Installed skill: {meta.name} v{meta.version}")
        console.print(f"  Description: {meta.description}")
        console.print(f"  Tools: {', '.join(meta.tools)}")
        console.print(f"  Category: {meta.category}")
    except ValueError as e:
        console.print(f"[red]✗[/red] {e}")
        sys.exit(1)


@cli.command("list")
@click.option("--category", "-c", help="Filter by category")
def list_skills(category: str | None) -> None:
    """List all available skills."""
    registry = SkillRegistry()
    skills = registry.list_skills(category=category)

    if not skills:
        console.print("[yellow]No skills found[/yellow]")
        return

    table = Table(title="AgentSkills Registry")
    table.add_column("Name", style="cyan")
    table.add_column("Version", style="green")
    table.add_column("Category", style="yellow")
    table.add_column("Tools", style="white")
    table.add_column("Description", style="white", max_width=40)

    for skill in skills:
        table.add_row(
            skill.name,
            skill.version,
            skill.category,
            ", ".join(skill.tools),
            skill.description[:40] + "..." if len(skill.description) > 40 else skill.description,
        )

    console.print(table)


@cli.command()
@click.argument("skill_path", type=click.Path(exists=True))
def publish(skill_path: str) -> None:
    """Publish a skill to the local registry."""
    registry = SkillRegistry()
    meta = registry.publish(skill_path)
    console.print(f"[green]✓[/green] Published skill: {meta.name} v{meta.version}")
    console.print(f"  Path: {meta.install_path}")


@cli.command()
@click.argument("skill_name")
def download(skill_name: str) -> None:
    """Download a skill from the remote registry."""
    registry = SkillRegistry()
    try:
        meta = registry.download(skill_name)
        console.print(f"[green]✓[/green] Downloaded skill: {meta.name} v{meta.version}")
    except ValueError as e:
        console.print(f"[red]✗[/red] {e}")
        sys.exit(1)


@cli.command()
@click.argument("trace_path", type=click.Path(exists=True))
@click.option("--min-occurrences", default=3, help="Minimum occurrences to include a skill")
@click.option("--min-success-rate", default=0.5, help="Minimum success rate to include a skill")
def decompose(trace_path: str, min_occurrences: int, min_success_rate: float) -> None:
    """Extract skills from a trace file and cluster them."""
    decomposer = SkillDecomposer(
        min_occurrences=min_occurrences,
        min_success_rate=min_success_rate,
    )
    skills = decomposer.extract_skills_from_trace(trace_path)

    if not skills:
        console.print("[yellow]No skills extracted from trace[/yellow]")
        return

    console.print(f"\n[bold]Extracted {len(skills)} skills:[/bold]")
    for skill in skills:
        console.print(f"  [cyan]{skill.name}[/cyan]: {skill.description}")
        console.print(f"    Tools: {', '.join(skill.tools)}")
        console.print(f"    Occurrences: {skill.occurrence_count}, Success: {skill.success_rate:.1%}")

    clusters = decomposer.cluster_skills()
    console.print(f"\n[bold]Clustered into {len(clusters)} groups:[/bold]")
    for cluster in clusters:
        console.print(f"  [yellow]{cluster.name}[/yellow]: {', '.join(s.name for s in cluster.skills)}")
        console.print(f"    Tools: {', '.join(cluster.representative_tools)}")
        console.print(f"    Avg success: {cluster.avg_success_rate:.1%}")


@cli.command()
@click.argument("trace_path", type=click.Path(exists=True))
@click.option("--base-model", default="Qwen/Qwen2.5-14B", help="Base model for LoRA")
@click.option("--output-dir", default="output/lora", help="Output directory")
@click.option("--lora-r", default=16, help="LoRA rank")
@click.option("--lora-alpha", default=32, help="LoRA alpha")
def build(trace_path: str, base_model: str, output_dir: str, lora_r: int, lora_alpha: int) -> None:
    """Build a LoRA adapter from a trace file."""
    decomposer = SkillDecomposer()
    skills = decomposer.extract_skills_from_trace(trace_path)
    if not skills:
        console.print("[red]✗ No skills extracted from trace[/red]")
        sys.exit(1)

    clusters = decomposer.cluster_skills()
    if not clusters:
        console.print("[red]✗ Could not cluster skills[/red]")
        sys.exit(1)

    config = LoRABuildConfig(
        base_model=base_model,
        output_dir=output_dir,
        LoRA_r=lora_r,
        LoRA_alpha=lora_alpha,
    )

    # Build a LoRA for each cluster
    adapters = []
    for cluster in clusters:
        adapter = build_lora(cluster, base_model=base_model, output_dir=output_dir, config=config)
        adapters.append(adapter)
        console.print(f"[green]✓[/green] Built LoRA: {adapter.name}")
        console.print(f"  Output: {adapter.output_path}")
        console.print(f"  Examples: {adapter.num_examples}")
        console.print(f"  Quality: {adapter.quality_score:.1%}")

    console.print(f"\n[bold]Built {len(adapters)} LoRA adapters[/bold]")


if __name__ == "__main__":
    cli()
