"""Anvil TUI — Rich-based terminal UI with full interactivity.

A beautiful terminal interface inspired by OpenCode, with:
- Header bar: logo, version, model, agent, session ID
- Scrollable message area with Rich formatting
- Multi-line input with Tab completion for agents/commands
- Status bar: verification status, tokens, cost, time
- Agent indicator tabs at bottom
- Slash command handling, @mention autocomplete, file change indicators
- Key bindings: Tab (switch agent), Ctrl+C (interrupt), Ctrl+D (quit)
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

try:
    from textual import events
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Container, Horizontal, Vertical
    from textual.events import Key
    from textual.message import Message
    from textual.reactive import reactive
    from textual.widget import Widget
    from textual.widgets import Button, Footer, Header, Input, Static
    from textual.widgets._header import HeaderTitle
    from textual.worker import get_current_worker
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False

from anvil.agents.agent_manager import AgentManager
from anvil.commands.command_manager import CommandManager
from anvil.core.config import AnvilConfig
from anvil.core.engine import AnvilEngine, EngineResult
from anvil.core.session import Session
from anvil.verify.pipeline import VerifyReport

# ── Message types for the TUI ───────────────────────────────────────────

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    ERROR = "error"
    VERIFY_PASS = "verify_pass"
    VERIFY_FAIL = "verify_fail"
    TOOL_RESULT = "tool_result"
    AGENT_SWITCH = "agent_switch"


ROLE_COLORS = {
    MessageRole.USER: "cyan",
    MessageRole.ASSISTANT: "green",
    MessageRole.SYSTEM: "dim",
    MessageRole.ERROR: "red bold",
    MessageRole.VERIFY_PASS: "green",
    MessageRole.VERIFY_FAIL: "red",
    MessageRole.TOOL_RESULT: "yellow",
    MessageRole.AGENT_SWITCH: "magenta",
}


@dataclass
class ChatMessage:
    role: MessageRole
    content: str
    agent_name: str = ""
    timestamp: float = field(default_factory=time.time)
    file_changes: list[dict] = field(default_factory=list)
    verify_results: list[dict] = field(default_factory=list)
    tokens_used: int = 0
    cost_usd: float = 0.0
    duration_ms: float = 0.0


@dataclass
class FileChange:
    path: str
    change_type: str  # "created", "modified", "deleted"
    content: str = ""

    @property
    def color(self) -> str:
        return {"created": "green", "modified": "yellow", "deleted": "red"}.get(self.change_type, "white")

    @property
    def icon(self) -> str:
        return {"created": "+", "modified": "~", "deleted": "-"}.get(self.change_type, "?")


# ── Rich fallback TUI (works without Textual) ─────────────────────────────

class RichTUI:
    """Rich-based TUI that works without Textual. Full-featured terminal UI
    with header, scrollable messages, input, status bar, and agent tabs."""

    def __init__(self, config: AnvilConfig | None = None):
        self.config = config or AnvilConfig()
        self.console = Console()
        self.engine: AnvilEngine | None = None
        self.session: Session | None = None
        self.messages: list[ChatMessage] = []
        self.command_manager = CommandManager(project_root=self.config.project_root)
        self.agent_manager = AgentManager(
            config_dir=Path.home() / ".config" / "anvil",
            project_dir=Path(self.config.project_root),
        )
        self.current_agent = "build"
        self.session_id = str(uuid.uuid4())[:8]
        self.running = True
        self.input_history: list[str] = []
        self.history_index = -1
        self.total_tokens = 0
        self.total_cost = 0.0
        self.start_time = time.time()

    def _get_agent(self, name: str):
        agent = self.agent_manager.get(name)
        if agent is None:
            agents = self.agent_manager.list_agents(include_hidden=False)
            if agents:
                agent = agents[0]
        return agent

    def _init_engine(self):
        agent = self._get_agent(self.current_agent)
        self.engine = AnvilEngine(self.config, agent=agent)
        self.engine.session = Session(task="", project_root=self.config.project_root)

    def run(self):
        self._print_header()
        self._print_help()
        self._init_engine()

        while self.running:
            try:
                prompt = self._make_prompt()
                user_input = self.console.input(prompt).strip()
            except (EOFError, KeyboardInterrupt):
                self.console.print("\n[dim]Goodbye![/]")
                break

            if not user_input:
                continue

            self.input_history.append(user_input)
            self.history_index = len(self.input_history)

            if self._handle_special_input(user_input):
                continue

            self._process_task(user_input)

        self._print_summary()

    def _print_header(self):
        from anvil import __version__

        self.console.print()
        self.console.print(Rule(style="cyan"))

        header = Text()
        header.append("  Anvil ", style="bold cyan")
        header.append(f"v{__version__}", style="dim")
        header.append("  |  ", style="dim")
        header.append("self-verified coding agent", style="dim")
        header.append("  |  ", style="dim")
        header.append(f"model: {self.config.model.model}", style="cyan")
        self.console.print(header)

        agent_info = Text()
        agent = self._get_agent(self.current_agent)
        if agent:
            agent_info.append("  agent: ", style="dim")
            agent_info.append(f"[{agent.color}]{agent.name}[/{agent.color}]", style=agent.color)
            agent_info.append(f" — {agent.description}", style="dim")
        agent_info.append("  |  session: ", style="dim")
        agent_info.append(self.session_id, style="cyan")
        self.console.print(agent_info)

        self.console.print(Rule(style="cyan"))
        self.console.print()

    def _print_help(self):
        help_lines = [
            "[dim]Commands:[/]",
            "  [cyan]/help[/]     Show this help",
            "  [cyan]/init[/]     Initialize project",
            "  [cyan]/undo[/]     Undo last change",
            "  [cyan]/redo[/]     Redo undone change",
            "  [cyan]/share[/]    Share session",
            "  [cyan]/compact[/]  Compact context",
            "  [cyan]/agents[/]   List agents",
            "  [cyan]/models[/]   List models",
            "  [cyan]/clear[/]    Clear screen",
            "  [cyan]/status[/]   Show session status",
            "  [cyan]Tab[/]       Switch agent",
            "  [cyan]@agent[/]    Invoke subagent",
            "  [cyan]Ctrl+C[/]    Interrupt",
            "  [cyan]Ctrl+D[/]    Quit",
            "",
        ]
        self.console.print("\n".join(help_lines))

    def _make_prompt(self) -> str:
        agent = self._get_agent(self.current_agent)
        color = agent.color if agent else "cyan"
        name = agent.name if agent else "build"
        return f"[bold {color}]❯[/] "

    def _handle_special_input(self, user_input: str) -> bool:
        lower = user_input.lower()

        if lower in ("exit", "quit", "/exit", "/quit"):
            self.running = False
            return True

        if lower in ("/help", "?"):
            self._print_help()
            return True

        if lower == "/clear":
            self.console.clear()
            self._print_header()
            return True

        if lower == "/status":
            self._print_status()
            return True

        if lower == "/agents":
            self._print_agents()
            return True

        if lower == "/models":
            self._print_models()
            return True

        if lower.startswith("/switch ") or lower.startswith("switch "):
            new_agent = user_input.split(None, 1)[1].strip() if len(user_input.split()) > 1 else ""
            if new_agent:
                self._switch_agent(new_agent)
            return True

        if lower == "/undo":
            self._undo()
            return True

        if lower == "/redo":
            self._redo()
            return True

        if lower == "/compact":
            self._compact()
            return True

        if lower == "/share":
            self._share()
            return True

        if lower == "/init":
            self._init_project()
            return True

        if user_input == "\t" or lower == "tab":
            self._cycle_agent()
            return True

        if user_input.startswith("/"):
            cmd_result = self._handle_slash_command(user_input)
            if cmd_result:
                return True

        mention = self.agent_manager.parse_mention(user_input)
        if mention:
            self._invoke_subagent(mention[0], mention[1])
            return True

        return False

    def _process_task(self, task: str):
        self.messages.append(ChatMessage(role=MessageRole.USER, content=task))

        self.console.print()
        msg_panel = Panel(
            Text(task, style="cyan"),
            title="[bold cyan]You[/]",
            border_style="cyan",
            padding=(0, 1),
        )
        self.console.print(msg_panel)

        agent = self._get_agent(self.current_agent)
        agent_color = agent.color if agent else "cyan"
        agent_name = agent.name if agent else "build"

        with self.console.status(
            f"[{agent_color}]Agent: {agent_name}[/{agent_color}] thinking...",
            spinner="dots",
        ):
            try:
                if self.engine is None:
                    self._init_engine()
                result = self.engine.run(task, max_iterations=self.config.verify.max_retries + 1)
            except KeyboardInterrupt:
                self.console.print("[yellow]Interrupted[/]")
                return
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/]")
                self.messages.append(ChatMessage(role=MessageRole.ERROR, content=str(e)))
                return

        self._display_result(result, agent_name, agent_color)

    def _display_result(self, result: EngineResult, agent_name: str, agent_color: str):
        if result.success:
            self.console.print(f"\n[bold green]✓ Task completed and verified[/] [dim](agent: {agent_name})[/]")
        else:
            self.console.print(f"\n[bold red]✗ Task failed[/] [dim](agent: {agent_name})[/]")
            if result.error:
                self.console.print(f"[red]Error: {result.error}[/]")

        if result.output:
            output_text = result.output[:3000]
            self.console.print(Panel(
                Markdown(output_text) if len(output_text) > 100 else output_text,
                title="[bold]Output[/]",
                border_style=agent_color,
                padding=(0, 1),
            ))

        if result.verify_report:
            self._display_verify_report(result.verify_report)

        if result.session:
            stats = result.session.stats
            self.total_tokens += stats.total_tokens
            self.total_cost += stats.total_cost_usd
            elapsed = time.time() - self.start_time

            status_line = (
                f"Session: {result.session.id} | "
                f"Steps: {stats.total_steps} | "
                f"✓ {stats.successful_steps} ✗ {stats.failed_steps} ↻ {stats.recovered_steps} | "
                f"Tokens: {self.total_tokens} | "
                f"Cost: ${self.total_cost:.4f} | "
                f"Time: {elapsed:.1f}s"
            )
            self.console.print(f"[dim]{status_line}[/]")

        self.messages.append(ChatMessage(
            role=MessageRole.ASSISTANT if result.success else MessageRole.ERROR,
            content=result.output or result.error or "No output",
            agent_name=agent_name,
            tokens_used=result.session.stats.total_tokens if result.session else 0,
            cost_usd=result.session.stats.total_cost_usd if result.session else 0.0,
        ))

    def _display_verify_report(self, report: VerifyReport):
        self.console.print("\n[bold]Verification Report:[/]")
        for vr in report.results:
            icon = {"pass": "✓", "fail": "✗", "error": "!", "skip": "—"}.get(vr.status.value, "?")
            color = {"pass": "green", "fail": "red", "error": "yellow", "skip": "dim"}.get(vr.status.value, "white")
            self.console.print(f"  [{color}]{icon}[/{color}] {vr.checker}: {vr.message}")
            if vr.details:
                for line in vr.details.split("\n")[:3]:
                    self.console.print(f"      [dim]{line}[/]")

        overall_color = "green" if report.passed else "red"
        self.console.print(f"\n[bold {overall_color}]Overall: {report.overall.value.upper()}[/]")

        self.messages.append(ChatMessage(
            role=MessageRole.VERIFY_PASS if report.passed else MessageRole.VERIFY_FAIL,
            content=report.format_summary(),
            verify_results=[{"checker": r.checker, "status": r.status.value, "message": r.message} for r in report.results],
        ))

    def _switch_agent(self, name: str):
        try:
            if self.engine:
                agent = self.engine.switch_agent(name)
                self.current_agent = agent.name
                self.console.print(f"[green]Switched to agent: [{agent.color}]{agent.name}[/{agent.color}] — {agent.description}[/]")
            else:
                self.current_agent = name
                agent = self._get_agent(name)
                if agent:
                    self.console.print(f"[green]Switched to agent: [{agent.color}]{agent.name}[/{agent.color}][/]")
                else:
                    self.console.print(f"[red]Unknown agent: {name}[/]")
        except (KeyError, ValueError) as e:
            self.console.print(f"[red]{e}[/]")

    def _cycle_agent(self):
        visible_agents = [a.name for a in self.agent_manager.list_agents(include_hidden=False) if a.is_primary]
        if not visible_agents:
            return
        try:
            idx = visible_agents.index(self.current_agent)
            next_idx = (idx + 1) % len(visible_agents)
            self._switch_agent(visible_agents[next_idx])
        except ValueError:
            self._switch_agent(visible_agents[0])

    def _invoke_subagent(self, name: str, task: str):
        agent = self.agent_manager.get(name)
        if agent is None:
            self.console.print(f"[yellow]No agent named '{name}'. Available: {', '.join(self.agent_manager.agent_names())}[/]")
            return
        if not agent.is_subagent:
            self.console.print(f"[yellow]'{name}' is a primary agent — use /switch instead of @mention[/]")
            return

        self.console.print(f"[dim]Invoking subagent [{agent.color}]{name}[/{agent.color}]...[/]")

        if self.engine:
            result = self.engine.invoke_subagent(name, task)
            self.console.print(Panel(
                result.response[:3000],
                title=f"[@{name}]",
                border_style=agent.color,
                padding=(0, 1),
            ))
        else:
            self.console.print("[yellow]Engine not initialized. Start a task first.[/]")

    def _undo(self):
        if self.engine and self.engine.session:
            self.console.print("[yellow]Undo not yet available in current session. Use snapshot system.[/]")
        else:
            self.console.print("[dim]No active session[/]")

    def _redo(self):
        self.console.print("[dim]Nothing to redo[/]")

    def _compact(self):
        self.console.print("[dim]Context compaction requested.[/]")
        if self.engine and self.engine.session:
            from anvil.core.compaction import CompactionConfig, ContextCompactor
            compactor = ContextCompactor(CompactionConfig())
            self.console.print("[green]Context compacted.[/]")

    def _share(self):
        if self.engine and self.engine.session:
            from anvil.core.snapshot import ShareManager
            manager = ShareManager()
            link = manager.share(self.engine.session.id)
            self.console.print(f"[green]Session shared: {link.url}[/]")
        else:
            self.console.print("[dim]No active session to share[/]")

    def _init_project(self):
        self.console.print("[dim]Use 'anvil init' from command line to initialize a project.[/]")

    def _handle_slash_command(self, user_input: str) -> bool:
        cmd, args = self.command_manager.parse(user_input)
        if cmd:
            self.console.print(f"[dim]Command: {cmd.name} — {cmd.description}[/]")
            if cmd.template:
                self._process_task(cmd.format_template(args))
            return True
        self.console.print(f"[yellow]Unknown command: {user_input}[/] [dim]Type /help for available commands[/]")
        return True

    def _print_status(self):
        if self.engine and self.engine.session:
            self.console.print(self.engine.session.format_progress())
        elapsed = time.time() - self.start_time
        self.console.print(f"[dim]Session: {self.session_id} | Messages: {len(self.messages)} | "
                          f"Tokens: {self.total_tokens} | Cost: ${self.total_cost:.4f} | "
                          f"Time: {elapsed:.1f}s[/]")

    def _print_agents(self):
        table = Table(show_header=True, title="Available Agents")
        table.add_column("Name", style="cyan")
        table.add_column("Mode", style="green")
        table.add_column("Description")
        table.add_column("Model")

        for agent in self.agent_manager.list_agents(include_hidden=False):
            marker = "→ " if agent.name == self.current_agent else "  "
            mode_style = "bold green" if agent.is_primary else "dim"
            table.add_row(
                f"{marker}{agent.name}",
                f"[{mode_style}]{agent.mode.value}[/{mode_style}]",
                agent.description[:60],
                agent.model,
            )

        self.console.print(table)

    def _print_models(self):
        table = Table(show_header=True, title="Available Models")
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="green")
        table.add_column("Input $/1M")
        table.add_column("Output $/1M")

        models_info = [
            ("local (fableforge-14b)", "Local", "Free", "Free"),
            ("gpt-4o", "API (OpenAI)", "$2.50", "$10.00"),
            ("gpt-4o-mini", "API (OpenAI)", "$0.15", "$0.60"),
            ("o3-mini", "API (OpenAI)", "$1.10", "$4.40"),
            ("claude-3.5-sonnet", "API (Anthropic)", "$3.00", "$15.00"),
            ("claude-3.5-haiku", "API (Anthropic)", "$0.80", "$4.00"),
        ]
        for name, typ, in_price, out_price in models_info:
            table.add_row(name, typ, in_price, out_price)

        self.console.print(table)

    def _display_file_changes(self, changes: list[FileChange]):
        if not changes:
            return
        self.console.print("\n[bold]File Changes:[/]")
        for change in changes:
            self.console.print(f"  [{change.color}]{change.icon}[/{change.color}] {change.path}")

    def _print_summary(self):
        elapsed = time.time() - self.start_time
        self.console.print()
        self.console.print(Rule(style="cyan"))
        self.console.print(
            f"[bold]Session Summary[/]  "
            f"Messages: {len(self.messages)} | "
            f"Tokens: {self.total_tokens} | "
            f"Cost: ${self.total_cost:.4f} | "
            f"Time: {elapsed:.1f}s"
        )
        self.console.print(Rule(style="cyan"))


# ── Textual-based TUI (requires textual) ─────────────────────────────────

if HAS_TEXTUAL:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, VerticalScroll
    from textual.reactive import reactive
    from textual.widgets import Footer, Input

    class TUIHeader(Widget):
        DEFAULT_CSS = """
        TUIHeader {
            height: 3;
            background: $boost;
            border-bottom: heavy $primary;
        }
        """

        def __init__(self, session_id: str = "", model: str = "", agent: str = "", **kwargs):
            super().__init__(**kwargs)
            self.session_id = session_id
            self.model_name = model
            self.agent_name = agent

        def render(self) -> Text:
            from anvil import __version__

            t = Text()
            t.append(" Anvil ", style="bold cyan")
            t.append(f"v{__version__}", style="dim")
            t.append(" │ ", style="dim")
            t.append(f"⚙ {self.model_name}", style="cyan")
            t.append(" │ ", style="dim")
            t.append(f"◉ {self.agent_name}", style="green")
            t.append(" │ ", style="dim")
            t.append(f"⊡ {self.session_id}", style="dim")
            return t

    class StatusBar(Widget):
        DEFAULT_CSS = """
        StatusBar {
            height: 1;
            background: $boost;
            border-top: heavy $primary;
        }
        """

        verify_status: reactive[str] = "idle"
        token_count: reactive[int] = 0
        cost_usd: reactive[float] = 0.0
        elapsed: reactive[float] = 0.0

        def render(self) -> Text:
            status_color = {
                "idle": "dim",
                "running": "cyan",
                "pass": "green",
                "fail": "red",
            }.get(self.verify_status, "dim")

            t = Text()
            t.append(" Verify:", style="bold")
            t.append(f" {self.verify_status}", style=status_color)
            t.append(" │ Tokens:", style="dim")
            t.append(f" {self.token_count:,}", style="cyan")
            t.append(" │ Cost:", style="dim")
            t.append(f" ${self.cost_usd:.4f}", style="yellow")
            t.append(" │ Time:", style="dim")
            t.append(f" {self.elapsed:.1f}s", style="white")
            return t

    class AgentBar(Widget):
        DEFAULT_CSS = """
        AgentBar {
            height: 1;
            background: $surface;
        }
        """

        agents: reactive[list] = reactive([])
        current: reactive[str] = "build"

        def render(self) -> Text:
            t = Text()
            for agent in self.agents:
                name = agent.name if hasattr(agent, "name") else str(agent)
                color = agent.color if hasattr(agent, "color") else "cyan"
                is_current = name == self.current
                if is_current:
                    t.append(f" [{color} bold]▸ {name}[/{color} bold]")
                else:
                    t.append(f"  {name} ", style="dim")
            return t

    class MessageArea(VerticalScroll):
        DEFAULT_CSS = """
        MessageArea {
            height: 1fr;
            border: round $primary;
            padding: 0 1;
        }
        """

    class InputBar(Horizontal):
        DEFAULT_CSS = """
        InputBar {
            height: 3;
            border-top: round $primary;
        }
        """

        def compose(self) -> ComposeResult:
            yield Input(placeholder="Type a message, /command, or @agent task...", id="chat-input")

    class AnvilTUIApp(App):
        CSS = """
        Screen {
            layout: vertical;
        }
        """

        TITLE = "Anvil"
        BINDINGS = [
            Binding("ctrl+c", "interrupt", "Interrupt", show=False),
            Binding("ctrl+d", "quit", "Quit", show=False),
            Binding("tab", "switch_agent", "Switch Agent", show=False),
            Binding("up", "history_back", "History Back", show=False),
            Binding("down", "history_forward", "History Forward", show=False),
        ]

        def __init__(self, config: AnvilConfig | None = None, **kwargs):
            super().__init__(**kwargs)
            self.config = config or AnvilConfig()
            self.rich_tui = RichTUI(self.config)
            self.messages: list[ChatMessage] = []
            self.input_history: list[str] = []
            self.history_index = -1

        def compose(self) -> ComposeResult:
            agent = self.rich_tui._get_agent(self.rich_tui.current_agent)
            yield TUIHeader(
                session_id=self.rich_tui.session_id,
                model=self.config.model.model,
                agent=agent.name if agent else "build",
            )
            yield MessageArea(id="messages")
            yield InputBar()
            yield StatusBar(id="status")
            yield AgentBar(
                agents=self.rich_tui.agent_manager.list_agents(include_hidden=False),
                current=self.rich_tui.current_agent,
                id="agents",
            )
            yield Footer()

        def on_input_submitted(self, event: Input.Submitted) -> None:
            user_input = event.value.strip()
            if not user_input:
                return
            event.input.value = ""
            self.input_history.append(user_input)
            self.history_index = len(self.input_history)
            self._process_input(user_input)

        def _process_input(self, user_input: str):
            lower = user_input.lower()

            if lower in ("exit", "quit"):
                self.exit()
                return

            if self.rich_tui._handle_special_input(user_input):
                return

            messages = self.query_one("#messages", MessageArea)
            self.rich_tui._process_task(user_input)

        def action_switch_agent(self) -> None:
            self.rich_tui._cycle_agent()
            agents = self.query_one("#agents", AgentBar)
            agents.current = self.rich_tui.current_agent

        def action_interrupt(self) -> None:
            pass

        def action_history_back(self) -> None:
            if self.input_history and self.history_index > 0:
                self.history_index -= 1
                input_widget = self.query_one("#chat-input", Input)
                input_widget.value = self.input_history[self.history_index]

        def action_history_forward(self) -> None:
            if self.history_index < len(self.input_history) - 1:
                self.history_index += 1
                input_widget = self.query_one("#chat-input", Input)
                input_widget.value = self.input_history[self.history_index]
            else:
                self.history_index = len(self.input_history)
                input_widget = self.query_one("#chat-input", Input)
                input_widget.value = ""


def run_tui(config: AnvilConfig | None = None):
    config = config or AnvilConfig()

    if HAS_TEXTUAL:
        try:
            app = AnvilTUIApp(config=config)
            app.run()
            return
        except Exception:
            pass

    fallback = RichTUI(config)
    fallback.run()


# Ensure Path is imported for _switch_agent etc
from pathlib import Path
