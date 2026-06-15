"""ShellWhisperer — 1.5B edge-native shell agent.

Converts natural language to shell commands. Runs on phone/edge
with 50ms latency via ONNX Runtime or llama.cpp GGUF.
"""

__version__ = "0.1.0"

from shell_whisperer.prompts import LINUX_PROMPT, MACOS_PROMPT, WINDOWS_PROMPT

__all__ = [
    "ShellWhisperer",
    "LINUX_PROMPT",
    "MACOS_PROMPT",
    "WINDOWS_PROMPT",
]


def __getattr__(name: str):
    if name == "ShellWhisperer":
        from shell_whisperer.inference import ShellWhisperer
        return ShellWhisperer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
