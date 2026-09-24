from __future__ import annotations

import json
import os
import sqlite3
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar


T = TypeVar("T")


class AuditStore:
    """Persist bounded MCP call metadata without storing document contents."""

    def __init__(self, environ: dict[str, str] | None = None):
        env = dict(os.environ if environ is None else environ)
        self.enabled = env.get("MARKDOWN_MCP_AUDIT_ENABLED", "true").casefold() not in {"0", "false", "no"}
        self.max_entries = max(100, min(100_000, int(env.get("MARKDOWN_MCP_AUDIT_MAX_ENTRIES", "2000"))))
        state_dir = Path(env.get("MARKDOWN_MCP_STATE_DIR", ".markdown-mcp-state"))
        self.path = state_dir / "audit.sqlite3"
        if self.enabled:
            self._initialize()

    def call(self, tool: str, params: dict[str, Any], operation: Callable[[], T]) -> T:
        started = time.perf_counter()
        try:
            result = operation()
        except Exception as exc:
            self.record(tool, params, "error", time.perf_counter() - started, None, str(exc))
            raise
        self.record(tool, params, "success", time.perf_counter() - started, self._result_meta(result), None)
        return result

    def record(
        self,
        tool: str,
        params: dict[str, Any],
        status: str,
        duration_seconds: float,
        result_meta: dict[str, Any] | None,
        error: str | None,
    ) -> None:
        if not self.enabled:
            return
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO calls(called_at,tool,params_json,status,duration_ms,result_json,error) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    tool,
                    json.dumps(params, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                    status,
                    round(duration_seconds * 1000, 2),
                    json.dumps(result_meta or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                    error,
                ),
            )
            conn.execute(
                "DELETE FROM calls WHERE id NOT IN (SELECT id FROM calls ORDER BY id DESC LIMIT ?)",
                (self.max_entries,),
            )
            conn.commit()

    def dashboard_data(
        self,
        page: int = 1,
        page_size: int = 20,
        tool: str | None = None,
        query: str | None = None,
    ) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "calls": [], "summary": {"total_calls": 0}, "pagination": {}}
        page = max(1, page)
        page_size = max(5, min(100, page_size))
        clauses: list[str] = []
        values: list[Any] = []
        if tool:
            clauses.append("tool=?")
            values.append(tool)
        if query:
            clauses.append("(tool LIKE ? OR params_json LIKE ? OR result_json LIKE ? OR error LIKE ?)")
            term = f"%{query}%"
            values.extend([term, term, term, term])
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connect() as conn:
            total = int(conn.execute(f"SELECT count(*) FROM calls{where}", values).fetchone()[0])
            page = min(page, max(1, (total + page_size - 1) // page_size))
            offset = (page - 1) * page_size
            rows = conn.execute(
                f"SELECT id,called_at,tool,params_json,status,duration_ms,result_json,error "
                f"FROM calls{where} ORDER BY id DESC LIMIT ? OFFSET ?",
                (*values, page_size, offset),
            ).fetchall()
            summary = conn.execute(
                "SELECT count(*) AS total_calls, "
                "sum(CASE WHEN status='error' THEN 1 ELSE 0 END) AS error_calls, "
                "round(avg(duration_ms),2) AS average_duration_ms, max(called_at) AS last_called_at FROM calls"
            ).fetchone()
            tools = [row[0] for row in conn.execute("SELECT DISTINCT tool FROM calls ORDER BY tool")]
        return {
            "enabled": True,
            "max_entries": self.max_entries,
            "summary": dict(summary),
            "calls": [self._decode_row(row) for row in rows],
            "tools": tools,
            "pagination": self._pagination(page, page_size, total),
        }

    def patterns_data(self, page: int = 1, page_size: int = 12, query: str | None = None) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "patterns": [], "pagination": {}}
        page = max(1, page)
        page_size = max(4, min(100, page_size))
        where = " WHERE tool LIKE ? OR params_json LIKE ?" if query else ""
        values: tuple[Any, ...] = (f"%{query}%", f"%{query}%") if query else ()
        grouped = f"SELECT tool,params_json FROM calls{where} GROUP BY tool,params_json"
        with self._connect() as conn:
            total = int(conn.execute(f"SELECT count(*) FROM ({grouped})", values).fetchone()[0])
            page = min(page, max(1, (total + page_size - 1) // page_size))
            offset = (page - 1) * page_size
            rows = conn.execute(
                f"SELECT tool,params_json,count(*) AS uses,round(avg(duration_ms),2) AS average_duration_ms,"
                f"max(called_at) AS last_used_at FROM calls{where} GROUP BY tool,params_json "
                "ORDER BY uses DESC,last_used_at DESC LIMIT ? OFFSET ?",
                (*values, page_size, offset),
            ).fetchall()
        return {
            "enabled": True,
            "patterns": [
                {
                    "tool": row["tool"],
                    "params": json.loads(row["params_json"]),
                    "uses": row["uses"],
                    "average_duration_ms": row["average_duration_ms"],
                    "last_used_at": row["last_used_at"],
                }
                for row in rows
            ],
            "pagination": self._pagination(page, page_size, total),
        }

    def _initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS calls("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,called_at TEXT NOT NULL,tool TEXT NOT NULL,"
                "params_json TEXT NOT NULL,status TEXT NOT NULL,duration_ms REAL NOT NULL,"
                "result_json TEXT NOT NULL,error TEXT)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS calls_called_at ON calls(called_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS calls_tool ON calls(tool)")
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _decode_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "called_at": row["called_at"],
            "tool": row["tool"],
            "params": json.loads(row["params_json"]),
            "status": row["status"],
            "duration_ms": row["duration_ms"],
            "result": json.loads(row["result_json"]),
            "error": row["error"],
        }

    @staticmethod
    def _result_meta(result: Any) -> dict[str, Any]:
        if isinstance(result, list):
            return {"item_count": len(result)}
        if not isinstance(result, dict):
            return {}
        metadata: dict[str, Any] = {}
        for key in (
            "root_id",
            "query",
            "result_count",
            "roots_searched",
            "indexed_documents",
            "total_lines",
            "start_line",
            "end_line",
        ):
            if key in result:
                metadata[key] = result[key]
        if "results" in result and "result_count" not in metadata:
            metadata["result_count"] = len(result["results"])
        if "candidates" in result:
            metadata["candidate_count"] = len(result["candidates"])
        return metadata

    @staticmethod
    def _pagination(page: int, page_size: int, total: int) -> dict[str, int]:
        pages = max(1, (total + page_size - 1) // page_size)
        return {"page": min(page, pages), "page_size": page_size, "total": total, "pages": pages}
