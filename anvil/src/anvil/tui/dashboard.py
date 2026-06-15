"""TUI dashboard for Anvil — Rich terminal UI with live progress."""

from __future__ import annotations

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel

from anvil.core.session import Session, StepKind, StepStatus
from anvil.verify.pipeline import VerifyReport

STATUS_ICONS = {
    StepStatus.SUCCESS: "[green]✓[/]",
    StepStatus.FAILED: "[red]✗[/]",
    StepStatus.RECOVERED: "[yellow]↻[/]",
    StepStatus.RUNNING: "[cyan]…[/]",
    StepStatus.RECOVERING: "[yellow]↻[/]",
    StepStatus.PLANNED: "[dim]○[/]",
    StepStatus.SKIPPED: "[dim]—[/]",
}

KIND_COLORS = {
    StepKind.PLAN: "blue",
    StepKind.EXECUTE: "cyan",
    StepKind.VERIFY: "green",
    StepKind.RECOVER: "yellow",
    StepKind.THINK: "magenta",
}


class AnvilTUI:
    def __init__(self, console: Console | None = None):
        self.console = console or Console()

    def render_session(self, session: Session) -> Panel:
        rows = []
        for step in session.steps:
            icon = STATUS_ICONS.get(step.status, "?")
            color = KIND_COLORS.get(step.kind, "white")
            duration = f"{step.duration_ms:.0f}ms" if step.duration_ms else ""
            rows.append(f"{icon} [{color}]{step.kind.value}[/{color}] {step.content[:70]} {duration}")

        stats = session.stats
        status_line = (
            f"Steps: {stats.total_steps} | "
            f"✓ {stats.successful_steps} ✗ {stats.failed_steps} ↻ {stats.recovered_steps} | "
            f"Error rate: {stats.error_rate:.0%} | "
            f"Recovery: {stats.recovery_rate:.0%} | "
            f"Tokens: {stats.total_tokens} | "
            f"${stats.total_cost_usd:.4f}"
        )
        return Panel("\n".join(rows), title=f"[bold]Session {session.id}[/]", subtitle=status_line, border_style="cyan")

    def render_verify(self, report: VerifyReport) -> Panel:
        rows = []
        for r in report.results:
            icon = {"pass": "[green]✓[/]", "fail": "[red]✗[/]", "error": "[yellow]![/]", "skip": "[dim]—[/]"}.get(r.status.value, "?")
            rows.append(f"{icon} {r.checker}: {r.message}")
            if r.details:
                for line in r.details.split("\n")[:2]:
                    rows.append(f"  [dim]{line}[/]")
        overall_color = "green" if report.passed else "red"
        rows.append(f"\n[bold {overall_color}]Overall: {report.overall.value.upper()}[/]")
        return Panel("\n".join(rows), title="[bold]Verification[/]", border_style="cyan")

    def render_progress(self, step_num: int, total: int, step: str, kind: StepKind) -> Panel:
        color = KIND_COLORS.get(kind, "white")
        bar_pct = int((step_num / max(total, 1)) * 30)
        bar = "█" * bar_pct + "░" * (30 - bar_pct)
        return Panel(
            f"[{color}]{kind.value.upper()}[/{color}] Step {step_num}/{total}\n"
            f"{bar} {step_num/total:.0%}\n\n"
            f"[bold]{step[:80]}[/]",
            title="[bold]Progress[/]", border_style="cyan",
        )

    def render_dashboard(self, session: Session, verify_report: VerifyReport | None = None) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", size=10),
            Layout(name="footer", size=3),
        )
        layout["header"].update(Panel(
            "[bold cyan]Anvil[/] — Self-Verified Coding Agent",
            border_style="cyan",
        ))
        layout["main"].update(self.render_session(session))
        if verify_report:
            layout["main"].update(self.render_verify(verify_report))
        layout["footer"].update(Panel(
            f"Session: {session.id} | State: {'running' if session.ended_at is None else 'completed'}",
            border_style="dim",
        ))
        return layout
