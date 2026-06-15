"""Semantic pattern matching with FAISS for fast nearest-neighbor search."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

from error_recovery.models import ErrorCategory, ErrorPattern

logger = logging.getLogger(__name__)

PATTERNS_DIR = Path(__file__).parent / "patterns"


class PatternMatcher:
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        similarity_threshold: float = 0.8,
        pattern_data_dir: str | Path | None = None,
        top_k: int = 5,
    ) -> None:
        self.model_name = model_name
        self.similarity_threshold = similarity_threshold
        self.top_k = top_k
        self._patterns: list[ErrorPattern] = []
        self._index: Any = None
        self._embeddings: np.ndarray | None = None
        self._model: Any = None
        self._pattern_data_dir = Path(pattern_data_dir) if pattern_data_dir else PATTERNS_DIR

    def _load_model(self) -> None:
        if self._model is not None:
            return
        # Allow disabling embeddings entirely (offline/CI/tests).
        import os

        if os.environ.get("ERROR_RECOVERY_NO_EMBEDDINGS"):
            logger.info("ERROR_RECOVERY_NO_EMBEDDINGS set; using keyword matching")
            self._model = None
            return
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
            logger.info("Loaded sentence-transformers model: %s", self.model_name)
        except Exception as exc:  # noqa: BLE001 — network/download/import all fall back
            logger.warning(
                "Could not load sentence-transformers model (%s); falling back to keyword matching",
                exc,
            )
            self._model = None

    def load_patterns(self, data_dir: str | Path | None = None) -> int:
        data_dir = Path(data_dir) if data_dir else self._pattern_data_dir
        patterns: list[ErrorPattern] = []

        if data_dir.is_dir():
            for json_file in sorted(data_dir.glob("*.json")):
                try:
                    raw = json.loads(json_file.read_text(encoding="utf-8"))
                    if isinstance(raw, list):
                        for entry in raw:
                            entry.setdefault("error_type", ErrorCategory.UNKNOWN.value)
                            if isinstance(entry.get("error_type"), str):
                                try:
                                    entry["error_type"] = ErrorCategory(entry["error_type"])
                                except ValueError:
                                    entry["error_type"] = ErrorCategory.UNKNOWN
                            patterns.append(ErrorPattern(**entry))
                    logger.info("Loaded %d patterns from %s", len(raw), json_file.name)
                except Exception as exc:
                    logger.warning("Failed to load %s: %s", json_file, exc)

        self._patterns.extend(patterns)
        logger.info("Total patterns loaded: %d", len(self._patterns))
        return len(patterns)

    def build_index(self) -> None:
        self._load_model()
        if not self._patterns:
            logger.warning("No patterns loaded; cannot build index")
            return

        texts = [f"{p.error_message} {p.recovery_prompt}" for p in self._patterns]

        if self._model is not None:
            self._embeddings = self._model.encode(texts, show_progress_bar=False)
            self._embeddings = np.array(self._embeddings, dtype=np.float32)

            import faiss

            dim = self._embeddings.shape[1]
            self._index = faiss.IndexFlatIP(dim)
            faiss.normalize_L2(self._embeddings)
            self._index.add(self._embeddings)
            logger.info("Built FAISS index with %d vectors (dim=%d)", len(self._patterns), dim)
        else:
            self._index = None
            self._embeddings = None
            logger.info("No model available; using keyword matching only")

    def match(
        self,
        error_message: str,
        tool_name: str = "",
        top_k: int | None = None,
        category: ErrorCategory | None = None,
    ) -> list[tuple[ErrorPattern, float]]:
        if not self._patterns:
            self.load_patterns()
            self.build_index()

        k = top_k or self.top_k
        candidates = self._patterns

        if category and category != ErrorCategory.UNKNOWN:
            candidates = [p for p in self._patterns if p.error_type == category]

        regex_matches = self._regex_match(error_message, candidates)
        if regex_matches:
            regex_matches.sort(key=lambda x: x[1], reverse=True)
            return regex_matches[:k]

        if self._model is not None and self._index is not None and self._embeddings is not None:
            semantic_matches = self._semantic_match(error_message, candidates, k)
            if semantic_matches:
                return semantic_matches

        return self._keyword_match(error_message, candidates, k)

    def _regex_match(
        self, error_message: str, candidates: list[ErrorPattern]
    ) -> list[tuple[ErrorPattern, float]]:
        results: list[tuple[ErrorPattern, float]] = []
        for pattern in candidates:
            if pattern.matches(error_message):
                results.append((pattern, 1.0))
        return results

    def _semantic_match(
        self, error_message: str, candidates: list[ErrorPattern], k: int
    ) -> list[tuple[ErrorPattern, float]]:
        import faiss

        query_embedding = self._model.encode([error_message], show_progress_bar=False)
        query_embedding = np.array(query_embedding, dtype=np.float32)
        faiss.normalize_L2(query_embedding)

        scores, indices = self._index.search(query_embedding, min(k * 3, len(self._patterns)))

        results: list[tuple[ErrorPattern, float]] = []
        candidate_ids = {id(p): p for p in candidates}

        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            pattern = self._patterns[idx]
            if id(pattern) in candidate_ids or pattern in candidates:
                if score >= self.similarity_threshold:
                    results.append((pattern, float(score)))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:k]

    def _keyword_match(
        self, error_message: str, candidates: list[ErrorPattern], k: int
    ) -> list[tuple[ErrorPattern, float]]:
        error_lower = error_message.lower()
        error_words = set(error_lower.split())

        scored: list[tuple[ErrorPattern, float]] = []
        for pattern in candidates:
            pattern_words = set(f"{pattern.error_message} {pattern.recovery_prompt}".lower().split())
            overlap = len(error_words & pattern_words)
            total = max(len(error_words | pattern_words), 1)
            score = overlap / total if total > 0 else 0.0

            pattern_match_bonus = 0.1 if pattern.matches(error_message) else 0.0
            score += pattern_match_bonus

            if score > 0.1:
                scored.append((pattern, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

    def get_pattern_by_id(self, pattern_id: str) -> ErrorPattern | None:
        for p in self._patterns:
            if p.id == pattern_id:
                return p
        return None

    @property
    def pattern_count(self) -> int:
        return len(self._patterns)

    @property
    def categories_covered(self) -> set[ErrorCategory]:
        return {p.error_type for p in self._patterns}

    def save_index(self, path: str | Path) -> None:
        import faiss

        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        if self._index is not None:
            faiss.write_index(self._index, str(path / "patterns.faiss"))

        if self._embeddings is not None:
            np.save(str(path / "embeddings.npy"), self._embeddings)

        meta = [
            {
                "id": p.id,
                "error_type": p.error_type.value,
                "error_message": p.error_message,
                "recovery_prompt": p.recovery_prompt,
                "success_rate": p.success_rate,
                "pattern": p.pattern,
            }
            for p in self._patterns
        ]
        (path / "patterns_meta.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("Saved index to %s", path)

    def load_index(self, path: str | Path) -> None:
        import faiss

        path = Path(path)
        index_file = path / "patterns.faiss"
        meta_file = path / "patterns_meta.json"

        if not index_file.exists() or not meta_file.exists():
            raise FileNotFoundError(f"Index files not found in {path}")

        self._index = faiss.read_index(str(index_file))
        self._embeddings = np.load(str(path / "embeddings.npy"))

        raw = json.loads(meta_file.read_text(encoding="utf-8"))
        self._patterns = []
        for entry in raw:
            entry["error_type"] = ErrorCategory(entry["error_type"])
            self._patterns.append(ErrorPattern(**entry))

        self._load_model()
        logger.info("Loaded index from %s (%d patterns)", path, len(self._patterns))
