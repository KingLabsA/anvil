"""Persistent memory store with short-term and long-term memory."""

from __future__ import annotations

import json
import logging
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    LargeBinary,
    String,
    Text,
    create_engine,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .models import MemoryEntry, MemorySearchResult

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path.home() / ".agent_runtime" / "memory.db"

SHORT_TERM_WINDOW = 50


class MemBase(DeclarativeBase):
    pass


class LongTermMemoryRow(MemBase):
    __tablename__ = "long_term_memory"

    key = Column(String(512), primary_key=True)
    value_json = Column(Text, nullable=False)
    embedding_blob = Column(LargeBinary, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    access_count = Column(Integer, default=1)


class ShortTermMemoryRow(MemBase):
    __tablename__ = "short_term_memory"

    id = Column(String(64), primary_key=True)
    session_id = Column(String(64), nullable=False, index=True)
    role = Column(String(32), nullable=False)
    content = Column(Text, default="")
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class MemoryConsolidationRow(MemBase):
    __tablename__ = "memory_consolidations"

    id = Column(String(64), primary_key=True)
    session_id = Column(String(64), nullable=False, index=True)
    summary = Column(Text, default="")
    from_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class MemoryStore:
    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is None:
            db_path = DEFAULT_DB_PATH
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        MemBase.metadata.create_all(self.engine)
        self._session_factory = sessionmaker(bind=self.engine)

    def _get_session(self) -> Session:
        return self._session_factory()

    def store(self, key: str, value: Any, embedding: list[float] | None = None) -> None:
        with self._get_session() as db:
            row = db.get(LongTermMemoryRow, key)
            if row is None:
                row = LongTermMemoryRow(key=key)
                db.add(row)
            row.value_json = json.dumps(value, default=str)
            row.embedding_blob = self._encode_embedding(embedding)
            row.timestamp = datetime.now(timezone.utc)
            row.access_count = (row.access_count or 0) + 1
            db.commit()
        logger.info("Stored memory key=%s", key)

    def retrieve(self, key: str) -> MemoryEntry | None:
        with self._get_session() as db:
            row = db.get(LongTermMemoryRow, key)
            if row is None:
                return None
            row.access_count = (row.access_count or 0) + 1
            db.commit()
        return MemoryEntry(
            key=row.key,
            value=json.loads(row.value_json),
            embedding=self._decode_embedding(row.embedding_blob),
            timestamp=row.timestamp,
        )

    def search(self, query_embedding: list[float], limit: int = 10) -> list[MemorySearchResult]:
        results: list[MemorySearchResult] = []
        with self._get_session() as db:
            rows = db.query(LongTermMemoryRow).all()
        for row in rows:
            emb = self._decode_embedding(row.embedding_blob)
            if emb is None:
                continue
            score = self._cosine_similarity(query_embedding, emb)
            results.append(
                MemorySearchResult(
                    key=row.key,
                    value=json.loads(row.value_json),
                    score=score,
                    timestamp=row.timestamp,
                )
            )
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def store_short_term(self, session_id: str, role: str, content: str) -> None:
        with self._get_session() as db:
            row = ShortTermMemoryRow(
                id=uuid.uuid4().hex[:16],
                session_id=session_id,
                role=role,
                content=content,
            )
            db.add(row)
            db.commit()
        self._prune_short_term(session_id)

    def get_short_term(self, session_id: str, last_n: int = SHORT_TERM_WINDOW) -> list[dict[str, Any]]:
        with self._get_session() as db:
            rows = (
                db.query(ShortTermMemoryRow)
                .filter(ShortTermMemoryRow.session_id == session_id)
                .order_by(ShortTermMemoryRow.timestamp.desc())
                .limit(last_n)
                .all()
            )
        rows.reverse()
        return [{"role": r.role, "content": r.content, "timestamp": r.timestamp.isoformat()} for r in rows]

    def consolidate(self, session_id: str) -> str | None:
        messages = self.get_short_term(session_id, last_n=SHORT_TERM_WINDOW)
        if len(messages) < 5:
            logger.info("Not enough short-term memory to consolidate for %s", session_id)
            return None
        summary_parts = []
        for msg in messages:
            summary_parts.append(f"[{msg['role']}] {msg['content'][:200]}")
        summary = "\n".join(summary_parts)
        consolidation_id = uuid.uuid4().hex[:16]
        with self._get_session() as db:
            row = MemoryConsolidationRow(
                id=consolidation_id,
                session_id=session_id,
                summary=summary,
                from_count=len(messages),
            )
            db.add(row)
            db.commit()
        self.store(
            key=f"consolidation:{session_id}:{consolidation_id}",
            value={"summary": summary, "message_count": len(messages)},
        )
        logger.info("Consolidated %d messages for session %s", len(messages), session_id)
        return consolidation_id

    def list_keys(self, prefix: str = "") -> list[str]:
        with self._get_session() as db:
            if prefix:
                rows = db.query(LongTermMemoryRow.key).filter(
                    LongTermMemoryRow.key.like(f"{prefix}%")
                ).all()
            else:
                rows = db.query(LongTermMemoryRow.key).all()
        return [r[0] for r in rows]

    def delete(self, key: str) -> bool:
        with self._get_session() as db:
            row = db.get(LongTermMemoryRow, key)
            if row is None:
                return False
            db.delete(row)
            db.commit()
        return True

    def _prune_short_term(self, session_id: str) -> None:
        with self._get_session() as db:
            count = db.query(ShortTermMemoryRow).filter(
                ShortTermMemoryRow.session_id == session_id
            ).count()
            if count > SHORT_TERM_WINDOW * 2:
                subq = (
                    db.query(ShortTermMemoryRow.id)
                    .filter(ShortTermMemoryRow.session_id == session_id)
                    .order_by(ShortTermMemoryRow.timestamp.desc())
                    .limit(SHORT_TERM_WINDOW)
                    .subquery()
                )
                db.execute(
                    text(
                        "DELETE FROM short_term_memory "
                        "WHERE session_id = :sid "
                        "AND id NOT IN (SELECT id FROM subq)"
                    ).bindparams(sid=session_id)
                )
                db.commit()

    @staticmethod
    def _encode_embedding(embedding: list[float] | None) -> bytes | None:
        if embedding is None:
            return None
        import struct
        return struct.pack(f"{len(embedding)}d", *embedding)

    @staticmethod
    def _decode_embedding(blob: bytes | None) -> list[float] | None:
        if blob is None:
            return None
        import struct
        count = len(blob) // 8
        return list(struct.unpack(f"{count}d", blob))

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(x * x for x in b))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)
