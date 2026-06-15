"""Dataset loader for Fable5 datasets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fable5_dataset.preprocessor import Preprocessor


_DATASET_CONFIGS = {
    "glint": {
        "description": "Glint agent traces - session-based format with turns",
        "url": "https://huggingface.co/datasets/fable5/glint",
        "format": "jsonl",
        "fields": ["session_id", "turns", "metadata"],
    },
    "armand0e": {
        "description": "armand0e agent traces - conversation format with tool calls",
        "url": "https://huggingface.co/datasets/fable5/armand0e",
        "format": "jsonl",
        "fields": ["id", "conversation", "metadata"],
    },
    "vfable": {
        "description": "vfable agent traces - trajectory format with tool use",
        "url": "https://huggingface.co/datasets/fable5/vfable",
        "format": "jsonl",
        "fields": ["id", "trajectory", "metadata"],
    },
    "coding_excellence": {
        "description": "Coding Excellence traces - high-quality coding agent sessions",
        "url": "https://huggingface.co/datasets/fable5/coding_excellence",
        "format": "jsonl",
        "fields": ["session_id", "turns", "quality_score", "metadata"],
    },
    "opencoven": {
        "description": "OpenCoven traces - source/target pair format",
        "url": "https://huggingface.co/datasets/fable5/opencoven",
        "format": "jsonl",
        "fields": ["id", "source", "target", "metadata"],
    },
    "victor": {
        "description": "Victor traces - prompt/response pairs",
        "url": "https://huggingface.co/datasets/fable5/victor",
        "format": "jsonl",
        "fields": ["id", "prompt", "response", "metadata"],
    },
}


class DatasetLoader:
    """Load and manage Fable5 agent trace datasets."""

    def __init__(self, cache_dir: str | Path | None = None) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".cache" / "fable5"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.preprocessor = Preprocessor()
        self._cache: dict[str, list[dict[str, Any]]] = {}

    def load_dataset(
        self,
        source: str = "all",
        split: str | None = None,
        normalize: bool = True,
        remove_pii: bool = False,
        min_quality: float = 0.0,
    ) -> list[dict[str, Any]] | dict[str, list[dict[str, Any]]]:
        """Load a Fable5 dataset.

        Args:
            source: Dataset name. One of: glint, armand0e, vfable, coding_excellence,
                   opencoven, victor, or "all".
            split: Optional data split ('train', 'validation', 'test').
            normalize: Whether to normalize format to unified schema.
            remove_pii: Whether to remove PII from records.
            min_quality: Minimum quality score filter (0.0-1.0).

        Returns:
            If source is "all": dict mapping dataset names to lists of records.
            Otherwise: list of records.
        """
        if source == "all":
            results: dict[str, list[dict[str, Any]]] = {}
            for name in _DATASET_CONFIGS:
                try:
                    records = self._load_single(name, split=split)
                    if normalize:
                        records = self.preprocessor.normalize_format(records, source_format=name)
                    if remove_pii:
                        records = self.preprocessor.remove_pii(records)
                    if min_quality > 0:
                        records = self.preprocessor.filter_quality(records, min_quality=min_quality)
                    results[name] = records
                except Exception:
                    results[name] = []
            return results

        records = self._load_single(source, split=split)

        if normalize:
            records = self.preprocessor.normalize_format(records, source_format=source)
        if remove_pii:
            records = self.preprocessor.remove_pii(records)
        if min_quality > 0:
            records = self.preprocessor.filter_quality(records, min_quality=min_quality)

        return records

    def _load_single(self, source: str, split: str | None = None) -> list[dict[str, Any]]:
        """Load a single dataset."""
        if source not in _DATASET_CONFIGS:
            raise ValueError(f"Unknown dataset: {source}. Available: {list(_DATASET_CONFIGS.keys())}")

        config = _DATASET_CONFIGS[source]

        if source in self._cache:
            return self._cache[source]

        cache_path = self.cache_dir / f"{source}.jsonl"

        if not cache_path.exists():
            records = self._load_from_hf(source, split)
            self._save_cache(source, records)
        else:
            records = self._load_from_cache(source)

        self._cache[source] = records
        return records

    def _load_from_hf(self, source: str, split: str | None = None) -> list[dict[str, Any]]:
        """Load dataset from HuggingFace Hub."""
        config = _DATASET_CONFIGS[source]
        try:
            from datasets import load_dataset
            dataset = load_dataset(config["url"].split("/")[-1], split=split)
            records = []
            for item in dataset:
                record = dict(item)
                records.append(record)
            return records
        except (ImportError, Exception):
            return self._load_synthetic(source)

    def _load_synthetic(self, source: str) -> list[dict[str, Any]]:
        """Generate synthetic sample data for development and testing."""
        samples = []
        if source == "glint":
            for i in range(10):
                samples.append({
                    "session_id": f"session_{i:04d}",
                    "turns": [
                        {"role": "user", "content": f"Help me with task {i}"},
                        {"role": "assistant", "content": f"I'll help you with task {i}. Let me check the code.", "tool_use": [{"name": "read", "input": {"file_path": f"src/module_{i}.py"}}]},
                        {"role": "assistant", "content": f"Here's what I found. The issue is in line {i * 10}."},
                        {"role": "user", "content": "Can you fix it?"},
                        {"role": "assistant", "content": "I'll fix it now.", "tool_use": [{"name": "edit", "input": {"file_path": f"src/module_{i}.py", "old": "buggy", "new": "fixed"}}]},
                    ],
                    "metadata": {"source": "glint", "quality_score": 0.7 + (i * 0.02)},
                })
        elif source == "armand0e":
            for i in range(8):
                samples.append({
                    "id": f"conv_{i:04d}",
                    "conversation": [
                        {"role": "user", "content": f"Create a function for task {i}"},
                        {"role": "assistant", "content": f"Here's the function for task {i}.", "tool_calls": [{"type": "function", "function": {"name": "write", "arguments": f'{{"path": "task_{i}.py", "content": "def task_{i}(): pass"}}'}}]},
                    ],
                    "metadata": {"source": "armand0e", "quality_score": 0.75 + (i * 0.02)},
                })
        elif source == "vfable":
            for i in range(6):
                samples.append({
                    "id": f"traj_{i:04d}",
                    "trajectory": [
                        {"role": "user", "content": f"Debug issue {i}"},
                        {"role": "assistant", "content": f"Let me investigate issue {i}.", "tool_use": {"name": "bash", "input": {"command": f"grep -r 'error_{i}' src/"}}},
                        {"role": "assistant", "content": "Found the error. Fixing now."},
                    ],
                    "metadata": {"source": "vfable", "quality_score": 0.8},
                })
        elif source == "coding_excellence":
            for i in range(12):
                samples.append({
                    "session_id": f"excellent_{i:04d}",
                    "turns": [
                        {"role": "user", "content": f"Implement feature {i} with tests"},
                        {"role": "assistant", "content": f"I'll implement feature {i} following TDD."},
                        {"role": "assistant", "content": "First, let me write the test.", "tool_use": [{"name": "write", "input": {"path": f"tests/test_feature_{i}.py"}}]},
                        {"role": "assistant", "content": "Now the implementation.", "tool_use": [{"name": "write", "input": {"path": f"src/feature_{i}.py"}}]},
                        {"role": "assistant", "content": "Running tests.", "tool_use": [{"name": "bash", "input": {"command": "pytest"}}]},
                    ],
                    "quality_score": 0.9 + (i * 0.005),
                    "metadata": {"source": "coding_excellence"},
                })
        elif source == "opencoven":
            for i in range(8):
                samples.append({
                    "id": f"coven_{i:04d}",
                    "source": f"Write a function that handles task {i} with proper error handling",
                    "target": f"def handle_task_{i}():\n    try:\n        pass\n    except Exception as e:\n        logger.error(f'Task {i} failed: {{e}}')\n        raise",
                    "metadata": {"source": "opencoven", "quality_score": 0.85},
                })
        elif source == "victor":
            for i in range(10):
                samples.append({
                    "id": f"victor_{i:04d}",
                    "prompt": f"Explain how to implement caching for operation {i}",
                    "response": f"Caching operation {i} involves: 1) Check the cache first 2) If miss, compute and store 3) Return cached value. Use a decorator or memoization pattern.",
                    "metadata": {"source": "victor", "quality_score": 0.8},
                })
        return samples

    def _save_cache(self, source: str, records: list[dict[str, Any]]) -> None:
        """Save records to local cache."""
        cache_path = self.cache_dir / f"{source}.jsonl"
        with open(cache_path, "w") as f:
            for record in records:
                f.write(json.dumps(record) + "\n")

    def _load_from_cache(self, source: str) -> list[dict[str, Any]]:
        """Load records from local cache."""
        cache_path = self.cache_dir / f"{source}.jsonl"
        records = []
        with open(cache_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def list_datasets(self) -> dict[str, dict[str, str]]:
        """List available datasets with metadata."""
        return {name: dict(config) for name, config in _DATASET_CONFIGS.items()}

    def get_dataset_info(self, source: str) -> dict[str, str]:
        """Get info about a specific dataset."""
        if source not in _DATASET_CONFIGS:
            raise ValueError(f"Unknown dataset: {source}. Available: {list(_DATASET_CONFIGS.keys())}")
        return dict(_DATASET_CONFIGS[source])

    def load_from_file(self, path: str | Path, source_format: str | None = None) -> list[dict[str, Any]]:
        """Load dataset from a local JSONL file.

        Args:
            path: Path to JSONL file.
            source_format: Optional format hint. Auto-detected if None.

        Returns:
            List of records.
        """
        path = Path(path)
        records = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))

        if source_format and source_format in _DATASET_CONFIGS:
            records = self.preprocessor.normalize_format(records, source_format=source_format)

        return records
