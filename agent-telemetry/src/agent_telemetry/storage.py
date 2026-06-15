"""Storage layer: ClickHouse primary with SQLite fallback."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from agent_telemetry.models import SessionMetrics, Span, ToolMetrics


DEFAULT_DB_PATH = Path.home() / ".agent_telemetry" / "telemetry.db"
DEFAULT_CLICKHOUSE_CONFIG = {
    "host": "localhost",
    "port": 9000,
    "database": "agent_telemetry",
}


class TelemetryStorage:
    """Dual-mode storage for agent telemetry data.

    Tries ClickHouse first; falls back to SQLite if ClickHouse is unavailable.
    """

    def __init__(
        self,
        clickhouse_host: str | None = None,
        clickhouse_port: int | None = None,
        clickhouse_database: str | None = None,
        sqlite_path: str | Path | None = None,
    ):
        self._clickhouse_available = False
        self._ch_client = None

        ch_host = clickhouse_host or DEFAULT_CLICKHOUSE_CONFIG["host"]
        ch_port = clickhouse_port or DEFAULT_CLICKHOUSE_CONFIG["port"]
        ch_db = clickhouse_database or DEFAULT_CLICKHOUSE_CONFIG["database"]

        try:
            import clickhouse_driver
            self._ch_client = clickhouse_driver.Client(
                host=ch_host, port=ch_port, database=ch_db
            )
            self._ch_client.execute("SELECT 1")
            self._clickhouse_available = True
            self._init_clickhouse()
        except Exception:
            self._clickhouse_available = False

        db_path = Path(sqlite_path) if sqlite_path else DEFAULT_DB_PATH
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._sqlite_path = db_path
        self._init_sqlite()

    def _init_clickhouse(self) -> None:
        if not self._clickhouse_available or self._ch_client is None:
            return

        self._ch_client.execute("""
            CREATE TABLE IF NOT EXISTS spans (
                span_id String,
                session_id String,
                tool_name String,
                input_tokens UInt64,
                output_tokens UInt64,
                cache_read UInt64,
                cache_creation UInt64,
                duration_ms Float64,
                cost_usd Float64,
                status String,
                error Nullable(String),
                model String,
                timestamp Nullable(DateTime),
                metadata String
            ) ENGINE = MergeTree()
            ORDER BY (session_id, timestamp)
        """)

        self._ch_client.execute("""
            CREATE TABLE IF NOT EXISTS session_metrics (
                session_id String,
                total_tokens UInt64,
                total_cost Float64,
                tool_calls UInt64,
                error_count UInt64,
                recovery_count UInt64,
                duration_seconds Float64,
                avg_tool_duration_ms Float64,
                p50_duration_ms Float64,
                p95_duration_ms Float64,
                p99_duration_ms Float64,
                cache_hit_rate Float64,
                model String,
                started_at Nullable(DateTime),
                ended_at Nullable(DateTime)
            ) ENGINE = ReplacingMergeTree()
            ORDER BY session_id
        """)

    def _init_sqlite(self) -> None:
        conn = sqlite3.connect(str(self._sqlite_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS spans (
                span_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cache_read INTEGER DEFAULT 0,
                cache_creation INTEGER DEFAULT 0,
                duration_ms REAL DEFAULT 0.0,
                cost_usd REAL DEFAULT 0.0,
                status TEXT DEFAULT 'ok',
                error TEXT,
                model TEXT DEFAULT 'unknown',
                timestamp TEXT,
                metadata TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS session_metrics (
                session_id TEXT PRIMARY KEY,
                total_tokens INTEGER DEFAULT 0,
                total_cost REAL DEFAULT 0.0,
                tool_calls INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                recovery_count INTEGER DEFAULT 0,
                duration_seconds REAL DEFAULT 0.0,
                avg_tool_duration_ms REAL DEFAULT 0.0,
                p50_duration_ms REAL DEFAULT 0.0,
                p95_duration_ms REAL DEFAULT 0.0,
                p99_duration_ms REAL DEFAULT 0.0,
                cache_hit_rate REAL DEFAULT 0.0,
                model TEXT DEFAULT 'unknown',
                started_at TEXT,
                ended_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_spans_session ON spans(session_id);
            CREATE INDEX IF NOT EXISTS idx_spans_tool ON spans(tool_name);
            CREATE INDEX IF NOT EXISTS idx_spans_timestamp ON spans(timestamp);
        """)
        conn.commit()
        conn.close()

    def store_span(self, span: Span) -> None:
        if self._clickhouse_available and self._ch_client is not None:
            self._store_span_clickhouse(span)
        self._store_span_sqlite(span)

    def store_spans(self, spans: list[Span]) -> None:
        for span in spans:
            self.store_span(span)

    def _store_span_clickhouse(self, span: Span) -> None:
        if self._ch_client is None:
            return
        self._ch_client.execute(
            """INSERT INTO spans VALUES""",
            [{
                "span_id": span.span_id,
                "session_id": span.session_id,
                "tool_name": span.tool_name,
                "input_tokens": span.input_tokens,
                "output_tokens": span.output_tokens,
                "cache_read": span.cache_read,
                "cache_creation": span.cache_creation,
                "duration_ms": span.duration_ms,
                "cost_usd": span.cost_usd,
                "status": span.status.value,
                "error": span.error,
                "model": span.model,
                "timestamp": span.timestamp,
                "metadata": json.dumps(span.metadata),
            }],
        )

    def _store_span_sqlite(self, span: Span) -> None:
        conn = sqlite3.connect(str(self._sqlite_path))
        conn.execute(
            """INSERT OR REPLACE INTO spans
            (span_id, session_id, tool_name, input_tokens, output_tokens,
             cache_read, cache_creation, duration_ms, cost_usd, status,
             error, model, timestamp, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                span.span_id,
                span.session_id,
                span.tool_name,
                span.input_tokens,
                span.output_tokens,
                span.cache_read,
                span.cache_creation,
                span.duration_ms,
                span.cost_usd,
                span.status.value,
                span.error,
                span.model,
                span.timestamp.isoformat() if span.timestamp else None,
                json.dumps(span.metadata),
            ),
        )
        conn.commit()
        conn.close()

    def store_session_metrics(self, metrics: SessionMetrics) -> None:
        if self._clickhouse_available and self._ch_client is not None:
            self._ch_client.execute(
                """INSERT INTO session_metrics VALUES""",
                [{
                    "session_id": metrics.session_id,
                    "total_tokens": metrics.total_tokens,
                    "total_cost": metrics.total_cost,
                    "tool_calls": metrics.tool_calls,
                    "error_count": metrics.error_count,
                    "recovery_count": metrics.recovery_count,
                    "duration_seconds": metrics.duration_seconds,
                    "avg_tool_duration_ms": metrics.avg_tool_duration_ms,
                    "p50_duration_ms": metrics.p50_duration_ms,
                    "p95_duration_ms": metrics.p95_duration_ms,
                    "p99_duration_ms": metrics.p99_duration_ms,
                    "cache_hit_rate": metrics.cache_hit_rate,
                    "model": metrics.model,
                    "started_at": metrics.started_at,
                    "ended_at": metrics.ended_at,
                }],
            )

        conn = sqlite3.connect(str(self._sqlite_path))
        conn.execute(
            """INSERT OR REPLACE INTO session_metrics
            (session_id, total_tokens, total_cost, tool_calls, error_count,
             recovery_count, duration_seconds, avg_tool_duration_ms,
             p50_duration_ms, p95_duration_ms, p99_duration_ms,
             cache_hit_rate, model, started_at, ended_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                metrics.session_id,
                metrics.total_tokens,
                metrics.total_cost,
                metrics.tool_calls,
                metrics.error_count,
                metrics.recovery_count,
                metrics.duration_seconds,
                metrics.avg_tool_duration_ms,
                metrics.p50_duration_ms,
                metrics.p95_duration_ms,
                metrics.p99_duration_ms,
                metrics.cache_hit_rate,
                metrics.model,
                metrics.started_at.isoformat() if metrics.started_at else None,
                metrics.ended_at.isoformat() if metrics.ended_at else None,
            ),
        )
        conn.commit()
        conn.close()

    def query_spans(
        self,
        session_id: str | None = None,
        tool_name: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> list[Span]:
        if self._clickhouse_available and self._ch_client is not None:
            return self._query_spans_clickhouse(session_id, tool_name, start_time, end_time, limit)
        return self._query_spans_sqlite(session_id, tool_name, start_time, end_time, limit)

    def _query_spans_clickhouse(
        self,
        session_id: str | None,
        tool_name: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
        limit: int,
    ) -> list[Span]:
        if self._ch_client is None:
            return []

        conditions = []
        params: dict[str, Any] = {}
        if session_id:
            conditions.append("session_id = %(sid)s")
            params["sid"] = session_id
        if tool_name:
            conditions.append("tool_name = %(tn)s")
            params["tn"] = tool_name
        if start_time:
            conditions.append("timestamp >= %(st)s")
            params["st"] = start_time
        if end_time:
            conditions.append("timestamp <= %(et)s")
            params["et"] = end_time

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = self._ch_client.execute(
            f"SELECT * FROM spans {where} ORDER BY timestamp LIMIT %(lim)s",
            {**params, "lim": limit},
        )

        from agent_telemetry.models import SpanStatus
        result = []
        for r in rows:
            result.append(Span(
                span_id=r[0], session_id=r[1], tool_name=r[2],
                input_tokens=r[3], output_tokens=r[4],
                cache_read=r[5], cache_creation=r[6],
                duration_ms=r[7], cost_usd=r[8],
                status=SpanStatus(r[9]), error=r[10], model=r[11],
                timestamp=r[12], metadata=json.loads(r[13]) if r[13] else {},
            ))
        return result

    def _query_spans_sqlite(
        self,
        session_id: str | None,
        tool_name: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
        limit: int,
    ) -> list[Span]:
        conn = sqlite3.connect(str(self._sqlite_path))
        conn.row_factory = sqlite3.Row

        conditions = []
        params_list: list[Any] = []
        if session_id:
            conditions.append("session_id = ?")
            params_list.append(session_id)
        if tool_name:
            conditions.append("tool_name = ?")
            params_list.append(tool_name)
        if start_time:
            conditions.append("timestamp >= ?")
            params_list.append(start_time.isoformat())
        if end_time:
            conditions.append("timestamp <= ?")
            params_list.append(end_time.isoformat())

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = conn.execute(
            f"SELECT * FROM spans {where} ORDER BY timestamp LIMIT ?",
            params_list + [limit],
        ).fetchall()

        from agent_telemetry.models import SpanStatus

        result = []
        for r in rows:
            result.append(Span(
                span_id=r["span_id"],
                session_id=r["session_id"],
                tool_name=r["tool_name"],
                input_tokens=r["input_tokens"],
                output_tokens=r["output_tokens"],
                cache_read=r["cache_read"],
                cache_creation=r["cache_creation"],
                duration_ms=r["duration_ms"],
                cost_usd=r["cost_usd"],
                status=SpanStatus(r["status"]),
                error=r["error"],
                model=r["model"],
                timestamp=datetime.fromisoformat(r["timestamp"]) if r["timestamp"] else None,
                metadata=json.loads(r["metadata"]) if r["metadata"] else {},
            ))
        conn.close()
        return result

    def get_session_metrics(self, session_id: str) -> Optional[SessionMetrics]:
        if self._clickhouse_available and self._ch_client is not None:
            rows = self._ch_client.execute(
                "SELECT * FROM session_metrics WHERE session_id = %(sid)s",
                {"sid": session_id},
            )
            if rows:
                r = rows[0]
                return SessionMetrics(
                    session_id=r[0], total_tokens=r[1], total_cost=r[2],
                    tool_calls=r[3], error_count=r[4], recovery_count=r[5],
                    duration_seconds=r[6], avg_tool_duration_ms=r[7],
                    p50_duration_ms=r[8], p95_duration_ms=r[9], p99_duration_ms=r[10],
                    cache_hit_rate=r[11], model=r[12], started_at=r[13], ended_at=r[14],
                )

        conn = sqlite3.connect(str(self._sqlite_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM session_metrics WHERE session_id = ?", (session_id,)
        ).fetchone()
        conn.close()

        if not row:
            return None

        return SessionMetrics(
            session_id=row["session_id"],
            total_tokens=row["total_tokens"],
            total_cost=row["total_cost"],
            tool_calls=row["tool_calls"],
            error_count=row["error_count"],
            recovery_count=row["recovery_count"],
            duration_seconds=row["duration_seconds"],
            avg_tool_duration_ms=row["avg_tool_duration_ms"],
            p50_duration_ms=row["p50_duration_ms"],
            p95_duration_ms=row["p95_duration_ms"],
            p99_duration_ms=row["p99_duration_ms"],
            cache_hit_rate=row["cache_hit_rate"],
            model=row["model"],
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            ended_at=datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
        )

    def list_sessions(self, limit: int = 50) -> list[str]:
        if self._clickhouse_available and self._ch_client is not None:
            rows = self._ch_client.execute(
                "SELECT DISTINCT session_id FROM spans ORDER BY session_id LIMIT %(lim)s",
                {"lim": limit},
            )
            return [r[0] for r in rows]

        conn = sqlite3.connect(str(self._sqlite_path))
        rows = conn.execute(
            "SELECT DISTINCT session_id FROM spans ORDER BY session_id LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [r[0] for r in rows]

    def aggregate_tool_metrics(self) -> list[ToolMetrics]:
        if self._clickhouse_available and self._ch_client is not None:
            rows = self._ch_client.execute("""
                SELECT tool_name,
                       count(),
                       avg(duration_ms),
                       quantile(0.5)(duration_ms),
                       quantile(0.95)(duration_ms),
                       countIf(status = 'error') / count(),
                       sum(input_tokens),
                       sum(output_tokens),
                       sum(cache_read),
                       sum(cache_creation),
                       sum(cost_usd)
                FROM spans
                GROUP BY tool_name
                ORDER BY tool_name
            """)
            return [
                ToolMetrics(
                    tool_name=r[0],
                    call_count=r[1],
                    avg_duration_ms=r[2],
                    p50_duration_ms=r[3],
                    p95_duration_ms=r[4],
                    error_rate=r[5],
                    total_input_tokens=r[6],
                    total_output_tokens=r[7],
                    total_cache_read=r[8],
                    total_cache_creation=r[9],
                    total_cost_usd=r[10],
                )
                for r in rows
            ]

        conn = sqlite3.connect(str(self._sqlite_path))
        rows = conn.execute("""
            SELECT tool_name,
                   COUNT(*) as call_count,
                   AVG(duration_ms) as avg_duration,
                   0 as p50_duration,
                   0 as p95_duration,
                   SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as error_rate,
                   SUM(input_tokens),
                   SUM(output_tokens),
                   SUM(cache_read),
                   SUM(cache_creation),
                   SUM(cost_usd)
            FROM spans
            GROUP BY tool_name
            ORDER BY tool_name
        """).fetchall()
        conn.close()

        return [
            ToolMetrics(
                tool_name=r[0],
                call_count=r[1],
                avg_duration_ms=r[2] or 0.0,
                p50_duration_ms=r[3] or 0.0,
                p95_duration_ms=r[4] or 0.0,
                error_rate=r[5] or 0.0,
                total_input_tokens=r[6] or 0,
                total_output_tokens=r[7] or 0,
                total_cache_read=r[8] or 0,
                total_cache_creation=r[9] or 0,
                total_cost_usd=r[10] or 0.0,
            )
            for r in rows
        ]
