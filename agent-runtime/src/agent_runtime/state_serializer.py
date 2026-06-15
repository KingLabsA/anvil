"""Serialize and deserialize agent state to/from SQLite."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    String,
    Text,
    create_engine,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .models import (
    CheckpointInfo,
    Message,
    SessionState,
    SessionStatus,
    ToolCall,
)

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path.home() / ".agent_runtime" / "state.db"


class Base(DeclarativeBase):
    pass


class SessionRow(Base):
    __tablename__ = "sessions"

    session_id = Column(String(64), primary_key=True)
    name = Column(String(256), default="")
    model = Column(String(128), default="")
    system_prompt = Column(Text, default="")
    tools = Column(Text, default="[]")
    status = Column(String(32), default=SessionStatus.CREATED.value)
    memory_json = Column(Text, default="{}")
    messages_json = Column(Text, default="[]")
    tool_history_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class CheckpointRow(Base):
    __tablename__ = "checkpoints"

    checkpoint_id = Column(String(64), primary_key=True)
    session_id = Column(String(64), nullable=False, index=True)
    label = Column(String(256), nullable=True)
    state_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (Index("ix_checkpoints_session_created", "session_id", "created_at"),)


class StateSerializer:
    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is None:
            db_path = DEFAULT_DB_PATH
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self._session_factory = sessionmaker(bind=self.engine)

    def _get_session(self) -> Session:
        return self._session_factory()

    def save_session(self, state: SessionState) -> None:
        with self._get_session() as db:
            row = db.get(SessionRow, state.session_id)
            if row is None:
                row = SessionRow(session_id=state.session_id)
                db.add(row)
            row.name = state.name
            row.model = state.model
            row.system_prompt = state.system_prompt
            row.tools = json.dumps(state.tools)
            row.status = state.status.value
            row.memory_json = json.dumps(state.memory, default=str)
            row.messages_json = json.dumps(
                [m.model_dump(mode="json") for m in state.messages],
                default=str,
            )
            row.tool_history_json = json.dumps(
                [t.model_dump(mode="json") for t in state.tool_history],
                default=str,
            )
            row.created_at = state.created_at
            row.updated_at = datetime.now(timezone.utc)
            db.commit()
        logger.info("Saved session %s", state.session_id)

    def load_session(self, session_id: str) -> SessionState | None:
        with self._get_session() as db:
            row = db.get(SessionRow, session_id)
            if row is None:
                return None
        return self._row_to_state(row)

    def delete_session(self, session_id: str) -> bool:
        with self._get_session() as db:
            row = db.get(SessionRow, session_id)
            if row is None:
                return False
            db.delete(row)
            db.execute(
                text("DELETE FROM checkpoints WHERE session_id = :sid"),
                {"sid": session_id},
            )
            db.commit()
        return True

    def list_sessions(self) -> list[SessionState]:
        with self._get_session() as db:
            rows = db.query(SessionRow).order_by(SessionRow.created_at).all()
        return [self._row_to_state(r) for r in rows]

    def create_checkpoint(self, session_id: str, label: str | None = None) -> CheckpointInfo:
        state = self.load_session(session_id)
        if state is None:
            raise ValueError(f"Session {session_id} not found")
        checkpoint_id = uuid.uuid4().hex[:16]
        state_json = json.dumps(state.model_dump(mode="json"), default=str)
        with self._get_session() as db:
            row = CheckpointRow(
                checkpoint_id=checkpoint_id,
                session_id=session_id,
                label=label,
                state_json=state_json,
            )
            db.add(row)
            db.commit()
            created_at = row.created_at
        logger.info("Created checkpoint %s for session %s", checkpoint_id, session_id)
        return CheckpointInfo(
            checkpoint_id=checkpoint_id,
            session_id=session_id,
            created_at=created_at,
            label=label,
        )

    def list_checkpoints(self, session_id: str) -> list[CheckpointInfo]:
        with self._get_session() as db:
            rows = (
                db.query(CheckpointRow)
                .filter(CheckpointRow.session_id == session_id)
                .order_by(CheckpointRow.created_at)
                .all()
            )
        return [
            CheckpointInfo(
                checkpoint_id=r.checkpoint_id,
                session_id=r.session_id,
                created_at=r.created_at,
                label=r.label,
            )
            for r in rows
        ]

    def resume_from_checkpoint(self, session_id: str, checkpoint_id: str) -> SessionState:
        with self._get_session() as db:
            row = db.get(CheckpointRow, checkpoint_id)
            if row is None or row.session_id != session_id:
                raise ValueError(f"Checkpoint {checkpoint_id} not found for session {session_id}")
            state_data = json.loads(row.state_json)
        state = SessionState.model_validate(state_data)
        state.status = SessionStatus.PAUSED
        self.save_session(state)
        logger.info("Resumed session %s from checkpoint %s", session_id, checkpoint_id)
        return state

    def prune_checkpoints(
        self, session_id: str, keep_last: int = 10
    ) -> int:
        with self._get_session() as db:
            rows = (
                db.query(CheckpointRow)
                .filter(CheckpointRow.session_id == session_id)
                .order_by(CheckpointRow.created_at.desc())
                .all()
            )
            to_delete = rows[keep_last:]
            count = 0
            for row in to_delete:
                db.delete(row)
                count += 1
            db.commit()
        if count:
            logger.info("Pruned %d old checkpoints for session %s", count, session_id)
        return count

    @staticmethod
    def _row_to_state(row: SessionRow) -> SessionState:
        messages = [Message.model_validate(m) for m in json.loads(row.messages_json)]
        tool_history = [ToolCall.model_validate(t) for t in json.loads(row.tool_history_json)]
        return SessionState(
            session_id=row.session_id,
            name=row.name,
            model=row.model,
            system_prompt=row.system_prompt,
            tools=json.loads(row.tools),
            status=SessionStatus(row.status),
            memory=json.loads(row.memory_json),
            messages=messages,
            tool_history=tool_history,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
