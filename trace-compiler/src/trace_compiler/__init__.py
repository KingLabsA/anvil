"""TraceCompiler — Compile agent traces into distilled LoRA weights."""

__version__ = "0.1.0"

from trace_compiler.distiller import Distiller
from trace_compiler.evaluator import Evaluator
from trace_compiler.parser import ToolCall, TraceParser, TraceRecord
from trace_compiler.skill_extractor import SkillExample, SkillExtractor, SkillType

__all__ = [
    "TraceParser",
    "TraceRecord",
    "ToolCall",
    "SkillExtractor",
    "SkillExample",
    "SkillType",
    "Distiller",
    "Evaluator",
]
