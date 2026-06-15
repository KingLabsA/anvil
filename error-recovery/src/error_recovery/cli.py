"""CLI for error recovery: recover, analyze, build-index, serve."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from error_recovery.error_classifier import ErrorClassifier
from error_recovery.models import ErrorRecoveryConfig
from error_recovery.pattern_matcher import PatternMatcher
from error_recovery.recovery_engine import ErrorRecoveryEngine

console = Console()


def _cmd_recover(args: argparse.Namespace) -> None:
    config = ErrorRecoveryConfig(
        max_attempts=args.max_attempts,
        similarity_threshold=args.threshold,
        fallback_to_llm=not args.no_llm_fallback,
    )
    engine = ErrorRecoveryEngine(config=config)

    with Progress(SpinnerColumn(), TextColumn("[bold]Recovering..."), console=console) as progress:
        progress.add_task("recover", total=None)
        result = engine.recover_sync(
            error_message=args.error,
            context=args.context or "",
            tool_name=args.tool or "",
        )

    status = "[green]SUCCESS[/green]" if result.success else "[red]FAILED[/red]"
    console.print(Panel(
        f"[bold]{status}[/bold]\n\n"
        f"[cyan]Error:[/cyan] {result.original_error}\n"
        f"[cyan]Category:[/cyan] {result.error_category.value}\n"
        f"[cyan]Recovery:[/cyan] {result.recovery_prompt[:200]}...\n"
        f"[cyan]Pattern:[/cyan] {result.pattern_matched or 'none'}\n"
        f"[cyan]Similarity:[/cyan] {result.pattern_similarity:.2f}\n"
        f"[cyan]Attempts:[/cyan] {result.attempts}\n"
        f"[cyan]Time:[/cyan] {result.elapsed_seconds:.2f}s",
        title="Recovery Result",
        border_style="green" if result.success else "red",
    ))

    if args.json:
        console.print_json(result.model_dump_json(indent=2))


def _cmd_analyze(args: argparse.Namespace) -> None:
    trace_file = Path(args.trace)
    if not trace_file.exists():
        console.print(f"[red]Error:[/red] File not found: {trace_file}")
        sys.exit(1)

    records = []
    with open(trace_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if not records:
        console.print("[red]No valid records found in trace file[/red]")
        sys.exit(1)


    classifier = ErrorClassifier()
    engine = ErrorRecoveryEngine(ErrorRecoveryConfig())
    total = len(records)
    by_category: dict[str, int] = {}
    errors_with_recovery: int = 0
    example_prompts: dict[str, list[str]] = {}

    for rec in records:
        error_msg = rec.get("error", rec.get("error_message", ""))
        tool = rec.get("tool", rec.get("tool_name", ""))
        cat = classifier.classify(error_msg, tool)

        cat_key = cat.value
        by_category[cat_key] = by_category.get(cat_key, 0) + 1

        if cat_key not in example_prompts:
            example_prompts[cat_key] = []

        matches = engine.pattern_matcher.match(error_msg, tool_name=tool, top_k=1)
        if matches:
            pattern, score = matches[0]
            example_prompts[cat_key].append(
                f"  • {pattern.recovery_prompt[:80]}... (score: {score:.2f})"
            )

    table = Table(title=f"Error Trace Analysis: {trace_file.name}")
    table.add_column("Category", style="cyan")
    table.add_column("Count", style="white", justify="right")
    table.add_column("Percentage", style="yellow", justify="right")
    table.add_column("Top Recovery Hint", style="green", max_width=60)

    for cat, count in sorted(by_category.items(), key=lambda x: -x[1]):
        pct = f"{count / total * 100:.1f}%"
        examples = example_prompts.get(cat, [])
        hint = examples[0] if examples else "  (no pattern match)"
        table.add_row(cat, str(count), pct, hint.strip())

    table.add_row("[bold]TOTAL[/bold]", f"[bold]{total}[/bold]", "[bold]100%[/bold]", "")
    console.print(table)

    if args.json:
        summary = {
            "total_records": total,
            "by_category": by_category,
            "example_prompts": {k: v[:3] for k, v in example_prompts.items()},
        }
        console.print_json(json.dumps(summary, indent=2))


def _cmd_build_index(args: argparse.Namespace) -> None:
    config = ErrorRecoveryConfig(
        model_name=args.model,
        similarity_threshold=args.threshold,
    )

    matcher = PatternMatcher(
        model_name=config.model_name,
        similarity_threshold=config.similarity_threshold,
        pattern_data_dir=args.data,
        top_k=args.top_k,
    )

    count = matcher.load_patterns(args.data)
    console.print(f"[green]Loaded {count} patterns[/green]")

    with Progress(SpinnerColumn(), TextColumn("[bold]Building FAISS index..."), console=console) as progress:
        progress.add_task("build", total=None)
        matcher.build_index()

    output = args.output or "./error_recovery_index"
    matcher.save_index(output)
    console.print(f"[green]Index saved to {output}[/green]")
    console.print(f"  Patterns: {matcher.pattern_count}")
    console.print(f"  Categories: {[c.value for c in matcher.categories_covered]}")


def _cmd_serve(args: argparse.Namespace) -> None:
    try:
        import uvicorn
        from fastapi import FastAPI
        from pydantic import BaseModel as APImodel
    except ImportError:
        console.print("[red]Error:[/red] Install server dependencies: pip install error-recovery[server]")
        sys.exit(1)

    config = ErrorRecoveryConfig(
        max_attempts=args.max_attempts,
        similarity_threshold=args.threshold,
    )
    engine = ErrorRecoveryEngine(config=config)

    app = FastAPI(title="ErrorRecovery API", version="0.1.0")

    class RecoverRequest(APImodel):
        error_message: str
        context: str = ""
        tool_name: str = ""
        max_attempts: int = 3

    class RecoverResponse(APImodel):
        success: bool
        error_category: str
        recovery_prompt: str
        pattern_matched: str | None = None
        pattern_similarity: float = 0.0
        attempts: int = 1

    @app.post("/recover", response_model=RecoverResponse)
    async def recover(req: RecoverRequest) -> RecoverResponse:
        result = await engine.recover(
            error_message=req.error_message,
            context=req.context,
            tool_name=req.tool_name,
        )
        return RecoverResponse(
            success=result.success,
            error_category=result.error_category.value,
            recovery_prompt=result.recovery_prompt,
            pattern_matched=result.pattern_matched,
            pattern_similarity=result.pattern_similarity,
            attempts=result.attempts,
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "patterns": str(engine.pattern_matcher.pattern_count)}

    @app.get("/stats")
    async def stats() -> dict:
        return engine.get_stats()

    console.print(f"[green]Starting ErrorRecovery server on port {args.port}[/green]")
    uvicorn.run(app, host=args.host, port=args.port)


def app() -> None:
    parser = argparse.ArgumentParser(
        prog="error-recovery",
        description="Self-healing agent middleware — intercept errors, inject recovery prompts",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # recover
    p_recover = subparsers.add_parser("recover", help="Test error recovery on an error message")
    p_recover.add_argument("--error", required=True, help="Error message to recover from")
    p_recover.add_argument("--context", default="", help="Execution context")
    p_recover.add_argument("--tool", default="", help="Tool name that produced the error")
    p_recover.add_argument("--max-attempts", type=int, default=3, help="Max recovery attempts")
    p_recover.add_argument("--threshold", type=float, default=0.8, help="Similarity threshold")
    p_recover.add_argument("--no-llm-fallback", action="store_true", help="Disable LLM fallback")
    p_recover.add_argument("--json", action="store_true", help="Output as JSON")

    # analyze
    p_analyze = subparsers.add_parser("analyze", help="Analyze error patterns in a trace file")
    p_analyze.add_argument("trace", help="Path to JSONL trace file")
    p_analyze.add_argument("--json", action="store_true", help="Output as JSON")

    # build-index
    p_build = subparsers.add_parser("build-index", help="Build FAISS index from pattern data")
    p_build.add_argument("--data", default=str(Path(__file__).parent / "patterns"), help="Pattern data directory")
    p_build.add_argument("--output", default="./error_recovery_index", help="Output directory for index")
    p_build.add_argument("--model", default="all-MiniLM-L6-v2", help="Sentence transformer model")
    p_build.add_argument("--threshold", type=float, default=0.8, help="Similarity threshold")
    p_build.add_argument("--top-k", type=int, default=5, help="Top-K matches")

    # serve
    p_serve = subparsers.add_parser("serve", help="Start recovery API server")
    p_serve.add_argument("--port", type=int, default=8000, help="Server port")
    p_serve.add_argument("--host", default="0.0.0.0", help="Server host")
    p_serve.add_argument("--max-attempts", type=int, default=3, help="Max recovery attempts")
    p_serve.add_argument("--threshold", type=float, default=0.8, help="Similarity threshold")

    args = parser.parse_args()

    if args.command == "recover":
        _cmd_recover(args)
    elif args.command == "analyze":
        _cmd_analyze(args)
    elif args.command == "build-index":
        _cmd_build_index(args)
    elif args.command == "serve":
        _cmd_serve(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    app()
