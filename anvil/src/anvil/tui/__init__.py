"""Anvil TUI package."""
from anvil.tui.app import HAS_TEXTUAL, ChatMessage, FileChange, MessageRole, RichTUI, run_tui
from anvil.tui.dashboard import AnvilTUI

__all__ = [
    "AnvilTUI",
    "RichTUI",
    "run_tui",
    "ChatMessage",
    "MessageRole",
    "FileChange",
    "HAS_TEXTUAL",
]

if HAS_TEXTUAL:
    from anvil.tui.app import AgentBar, AnvilTUIApp, InputBar, MessageArea, StatusBar, TUIHeader
    __all__.extend(["AnvilTUIApp", "TUIHeader", "StatusBar", "AgentBar", "MessageArea", "InputBar"])
