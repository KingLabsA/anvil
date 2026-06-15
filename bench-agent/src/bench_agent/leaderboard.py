"""Leaderboard management for BenchAgent benchmark results."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from bench_agent.models import Leaderboard, ScoreReport, TaskResult
from bench_agent.scorer import calculate_overall_score, calculate_category_scores, error_recovery_score


def load_leaderboard(path: str | Path) -> Leaderboard:
    path = Path(path)
    if not path.exists():
        return Leaderboard(last_updated=datetime.now(timezone.utc).isoformat())

    data = json.loads(path.read_text())
    return Leaderboard(**data)


def update_leaderboard(
    leaderboard: Leaderboard, model_name: str, results: list[TaskResult]
) -> Leaderboard:
    total_score = calculate_overall_score(results)
    category_scores = calculate_category_scores(results)

    recovery_scores = [error_recovery_score(r) for r in results]
    avg_recovery = sum(recovery_scores) / len(recovery_scores) if recovery_scores else 0.0

    existing = None
    for entry in leaderboard.entries:
        if entry.model == model_name:
            existing = entry
            break

    report = ScoreReport(
        model=model_name,
        total_score=total_score,
        category_scores=category_scores,
        error_recovery_rate=round(avg_recovery, 3),
    )

    if existing:
        idx = leaderboard.entries.index(existing)
        leaderboard.entries[idx] = report
    else:
        leaderboard.entries.append(report)

    leaderboard = sort_leaderboard(leaderboard)
    leaderboard.last_updated = datetime.now(timezone.utc).isoformat()
    return leaderboard


def sort_leaderboard(leaderboard: Leaderboard) -> Leaderboard:
    sorted_entries = sorted(leaderboard.entries, key=lambda e: e.total_score, reverse=True)
    for idx, entry in enumerate(sorted_entries):
        entry.leaderboard_rank = idx + 1
    leaderboard.entries = sorted_entries
    return leaderboard


def export_leaderboard(leaderboard: Leaderboard, format: str = "json") -> str:
    if format == "json":
        return leaderboard.model_dump_json(indent=2)
    elif format == "markdown":
        return export_markdown(leaderboard)
    else:
        raise ValueError(f"Unknown format: {format}")


def export_markdown(leaderboard: Leaderboard) -> str:
    lines = [
        "# BenchAgent Leaderboard",
        "",
        f"Last updated: {leaderboard.last_updated}",
        "",
        "| Rank | Model | Total Score | Error Recovery | Bash | Edit | Read | Write | Multi-Tool | Error Recovery Cat |",
        "|------|-------|-------------|-----------------|------|------|------|-------|------------|-------------------|",
    ]

    for entry in leaderboard.entries:
        cat = entry.category_scores
        lines.append(
            f"| {entry.leaderboard_rank} | {entry.model} | {entry.total_score:.1f} | "
            f"{entry.error_recovery_rate:.3f} | "
            f"{cat.get('bash', 0):.1f} | {cat.get('edit', 0):.1f} | "
            f"{cat.get('read', 0):.1f} | {cat.get('write', 0):.1f} | "
            f"{cat.get('multi_tool', 0):.1f} | {cat.get('error_recovery', 0):.1f} |"
        )

    lines.append("")
    return "\n".join(lines)


def save_leaderboard(leaderboard: Leaderboard, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(export_leaderboard(leaderboard, format="json"))
