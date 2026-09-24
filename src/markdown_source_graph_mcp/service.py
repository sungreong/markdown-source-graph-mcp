from __future__ import annotations

import os
import re
import shutil
import sqlite3
import threading
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Literal


MARKDOWN_EXTENSIONS = {".md", ".mdx", ".markdown", ".mdown", ".mkd", ".mkdn"}
SUPPORTED_INDEX_KINDS = {
    "markdown-agent-docs.source-graph",
    "markdown-pattern-studio.source-graph",
}


@dataclass(frozen=True)
class MarkdownRoot:
    root_id: str
    path: Path
    public_path: str | None


class MarkdownSourceGraphService:
    """Read one Agent Docs Source Graph and expose safe Markdown operations."""

    def __init__(self, environ: dict[str, str] | None = None):
        env = dict(os.environ if environ is None else environ)
        self.root = MarkdownRoot(
            root_id=env.get("MARKDOWN_MCP_ROOT_ID", "workspace").strip() or "workspace",
            path=Path(env.get("MARKDOWN_MCP_ROOT_PATH", "/workspace")),
            public_path=env.get("MARKDOWN_MCP_PUBLIC_PATH") or None,
        )
        self.state_dir = Path(env.get("MARKDOWN_MCP_STATE_DIR", ".markdown-mcp-state"))
        self.cache_path = self.state_dir / "source-graph-cache.sqlite"
        self._refresh_lock = threading.Lock()

    @property
    def source_path(self) -> Path:
        return self.root.path / ".mps" / "source-graph.sqlite"

    def root_statuses(self) -> list[dict[str, Any]]:
        return [self.source_graph_status(self.root.root_id)]

    def source_graph_status(self, root_id: str) -> dict[str, Any]:
        self._require_root(root_id)
        source_meta: dict[str, str] = {}
        document_count = 0
        source_error: str | None = None
        if self.source_path.is_file():
            try:
                with closing(self._source_connection()) as conn:
                    source_meta = self._read_meta(conn)
                    document_count = int(conn.execute("SELECT count(*) FROM documents").fetchone()[0])
            except sqlite3.Error as exc:
                source_error = str(exc)
        cached = self._cached_root()
        source_mtime = self.source_path.stat().st_mtime if self.source_path.is_file() else None
        stale = bool(cached and source_mtime and source_mtime > float(cached["source_mtime"]))
        return {
            "root_id": self.root.root_id,
            "public_path": self.root.public_path or f"md://{self.root.root_id}",
            "mounted": self.root.path.is_dir(),
            "mps_index_present": self.source_path.is_file(),
            "source_kind": source_meta.get("kind"),
            "source_updated_at": source_meta.get("updatedAt"),
            "source_documents": document_count,
            "source_error": source_error,
            "supported": source_meta.get("kind") in SUPPORTED_INDEX_KINDS if source_meta else False,
            "cached": cached is not None,
            "cached_documents": int(cached["document_count"]) if cached else 0,
            "refreshed_at": cached["refreshed_at"] if cached else None,
            "stale": stale,
        }

    def ensure_fresh(self) -> None:
        status = self.source_graph_status(self.root.root_id)
        if not status["mps_index_present"]:
            raise ValueError(
                "Missing .mps/source-graph.sqlite. Initialize Source Graph with the "
                "Agent Docs for Markdown VS Code extension first."
            )
        if not status["supported"]:
            raise ValueError(f"Unsupported Source Graph kind: {status['source_kind']!r}.")
        if not status["cached"] or status["stale"]:
            self.refresh_root(self.root.root_id)

    def refresh_root(self, root_id: str) -> dict[str, Any]:
        self._require_root(root_id)
        if not self.source_path.is_file():
            raise ValueError("Missing .mps/source-graph.sqlite in the mounted workspace.")
        with self._refresh_lock:
            return self._refresh_locked()

    def _refresh_locked(self) -> dict[str, Any]:
        temp_path = self.cache_path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
        source: sqlite3.Connection | None = None
        cache: sqlite3.Connection | None = None
        replaced = False
        try:
            source = self._source_connection()
            source.row_factory = sqlite3.Row
            meta = self._read_meta(source)
            if meta.get("schemaVersion") != "1" or meta.get("kind") not in SUPPORTED_INDEX_KINDS:
                raise ValueError(
                    "Unsupported MPS Source Graph schema. Expected schemaVersion=1 and an "
                    "Agent Docs/Markdown Pattern Studio source graph."
                )
            documents = source.execute(
                """
                SELECT d.path, d.title, d.snippet, d.mtime_ms,
                       COALESCE(NULLIF(sb.text, ''), NULLIF(si.text, ''), d.snippet, '') AS text
                FROM documents d
                LEFT JOIN search_index si ON si.document_id = d.id
                LEFT JOIN search_blobs sb ON sb.id = si.blob_id
                """
            )
            headings = source.execute(
                """
                SELECT d.path, h.title, h.depth, h.line, h.slug
                FROM headings h JOIN documents d ON d.id = h.document_id
                """
            )
            document_count = int(source.execute("SELECT count(*) FROM documents").fetchone()[0])
            self.state_dir.mkdir(parents=True, exist_ok=True)
            temp_path.unlink(missing_ok=True)
            cache = sqlite3.connect(temp_path)
            self._create_cache(cache)
            while rows := documents.fetchmany(250):
                metadata = [
                    (self.root.root_id, row["path"], row["title"], row["snippet"], row["mtime_ms"])
                    for row in rows
                ]
                cache.executemany(
                    "INSERT INTO documents(root_id,path,title,snippet,source_mtime) VALUES (?,?,?,?,?)",
                    metadata,
                )
                cache.executemany(
                    "INSERT INTO documents_fts(root_id,path,title,text) VALUES (?,?,?,?)",
                    [(self.root.root_id, row["path"], row["title"], row["text"]) for row in rows],
                )
            while rows := headings.fetchmany(500):
                cache.executemany(
                    "INSERT INTO headings(root_id,path,title,depth,line,slug) VALUES (?,?,?,?,?,?)",
                    [
                        (self.root.root_id, row["path"], row["title"], row["depth"], row["line"], row["slug"])
                        for row in rows
                    ],
                )
            refreshed_at = self._now()
            cache.execute(
                "INSERT INTO roots VALUES (?,?,?,?,?)",
                (
                    self.root.root_id,
                    self.source_path.stat().st_mtime,
                    meta.get("updatedAt"),
                    refreshed_at,
                    document_count,
                ),
            )
            cache.commit()
            cache.close()
            cache = None
            os.replace(temp_path, self.cache_path)
            replaced = True
            return {
                "root_id": self.root.root_id,
                "status": "refreshed",
                "source_kind": meta.get("kind"),
                "source_updated_at": meta.get("updatedAt"),
                "refreshed_at": refreshed_at,
                "indexed_documents": document_count,
            }
        except sqlite3.Error as exc:
            raise ValueError(f"MPS Source Graph could not be imported: {exc}") from exc
        finally:
            if source is not None:
                source.close()
            if cache is not None:
                cache.close()
            if not replaced:
                temp_path.unlink(missing_ok=True)

    def search_markdown(
        self,
        query: str,
        root_id: str | None = None,
        limit: int = 10,
        excerpt_chars: int = 1200,
        modified_from: str | None = None,
        modified_to: str | None = None,
        sort_by: Literal["recent", "relevance"] = "relevance",
    ) -> dict[str, Any]:
        self._require_root(root_id or self.root.root_id)
        self.ensure_fresh()
        query = query.strip()
        if not query:
            raise ValueError("query is required.")
        if sort_by not in {"recent", "relevance"}:
            raise ValueError("sort_by must be 'recent' or 'relevance'.")
        limit = self._bounded(limit, 10, 1, 50)
        excerpt_chars = self._bounded(excerpt_chars, 1200, 100, 3000)
        start = self._parse_date(modified_from, end=False)
        end = self._parse_date(modified_to, end=True)
        if start and end and start > end:
            raise ValueError("modified_from must not be later than modified_to.")
        terms = self._terms(query)
        if not terms:
            return {"query": query, "sort_by": sort_by, "results": []}
        fts_query = " OR ".join(f'"{term.replace(chr(34), "")}"' for term in terms)
        sql = """
            SELECT d.path,d.title,d.snippet,d.source_mtime,bm25(documents_fts) AS rank
            FROM documents_fts
            JOIN documents d ON d.root_id=documents_fts.root_id AND d.path=documents_fts.path
            WHERE documents_fts.root_id=? AND documents_fts MATCH ?
        """
        values: list[Any] = [self.root.root_id, fts_query]
        if start:
            sql += " AND d.source_mtime >= ?"
            values.append(start.timestamp() * 1000)
        if end:
            sql += " AND d.source_mtime <= ?"
            values.append(end.timestamp() * 1000)
        sql += " ORDER BY rank LIMIT 500"
        with closing(self._cache_connection()) as cache:
            rows = cache.execute(sql, values).fetchall()
            results = [
                {
                    "root_id": self.root.root_id,
                    "relative_path": row["path"],
                    "path": self._public_path(row["path"]),
                    "title": row["title"],
                    "snippet": row["snippet"],
                    "rank": round(float(row["rank"]), 4),
                    "modified_at": self._mtime_iso(row["source_mtime"]),
                }
                for row in rows
            ]
            if sort_by == "recent":
                results.sort(key=lambda item: item["modified_at"] or "", reverse=True)
            else:
                results.sort(key=lambda item: item["rank"])
            selected = results[:limit]
            for item in selected:
                target = self._safe_document_path(item["relative_path"])
                try:
                    text = target.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    text = item["snippet"]
                item["excerpt"] = self._excerpt(text, query, excerpt_chars)
                item["headings"] = [
                    dict(row)
                    for row in cache.execute(
                        "SELECT title,depth,line,slug FROM headings WHERE root_id=? AND path=? ORDER BY line LIMIT 12",
                        (self.root.root_id, item["relative_path"]),
                    )
                ]
                item["readable"] = target.is_file()
                del item["snippet"]
        return {
            "query": query,
            "modified_from": modified_from,
            "modified_to": modified_to,
            "sort_by": sort_by,
            "results": selected,
        }

    def read_markdown(
        self, root_id: str, relative_path: str, start_line: int = 1, max_lines: int = 120
    ) -> dict[str, Any]:
        self._require_root(root_id)
        target = self._safe_document_path(relative_path)
        if not target.is_file():
            raise ValueError("Markdown document was not found.")
        start_line = self._bounded(start_line, 1, 1, 1_000_000)
        max_lines = self._bounded(max_lines, 120, 1, 500)
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        selected = lines[start_line - 1 : start_line - 1 + max_lines]
        return {
            "root_id": self.root.root_id,
            "relative_path": relative_path.replace("\\", "/"),
            "path": self._public_path(relative_path),
            "start_line": start_line,
            "end_line": start_line + len(selected) - 1,
            "total_lines": len(lines),
            "content": "\n".join(selected),
        }

    def get_markdown_links(
        self,
        root_id: str,
        relative_path: str,
        direction: Literal["outgoing", "incoming", "both"] = "both",
        limit: int = 50,
    ) -> dict[str, Any]:
        self._require_root(root_id)
        if direction not in {"outgoing", "incoming", "both"}:
            raise ValueError("direction must be 'outgoing', 'incoming', or 'both'.")
        normalized = self._validate_relative_markdown_path(relative_path)
        limit = self._bounded(limit, 50, 1, 200)
        with closing(self._source_connection()) as conn:
            conn.row_factory = sqlite3.Row
            document = conn.execute(
                "SELECT id,path,title FROM documents WHERE lower(path)=lower(?)", (normalized,)
            ).fetchone()
            if document is None:
                raise ValueError("Document is not present in the Source Graph index.")
            outgoing: list[dict[str, Any]] = []
            incoming: list[dict[str, Any]] = []
            if direction in {"outgoing", "both"}:
                outgoing = [
                    dict(row)
                    for row in conn.execute(
                        """
                        SELECT l.target_path AS relative_path,COALESCE(d.title,l.label,l.href) AS title,
                               l.href,l.label,l.type,l.status,l.line
                        FROM links l LEFT JOIN documents d ON d.id=l.target_document_id
                        WHERE l.source_document_id=? ORDER BY l.line LIMIT ?
                        """,
                        (document["id"], limit),
                    )
                ]
            if direction in {"incoming", "both"}:
                incoming = [
                    dict(row)
                    for row in conn.execute(
                        """
                        SELECT s.path AS relative_path,s.title,l.href,l.label,l.type,l.status,l.line
                        FROM links l JOIN documents s ON s.id=l.source_document_id
                        WHERE l.target_document_id=? ORDER BY s.path,l.line LIMIT ?
                        """,
                        (document["id"], limit),
                    )
                ]
        for item in outgoing + incoming:
            path = item.get("relative_path")
            item["path"] = self._public_path(path) if path else None
        return {
            "root_id": self.root.root_id,
            "relative_path": document["path"],
            "title": document["title"],
            "direction": direction,
            "outgoing": outgoing,
            "incoming": incoming,
        }

    def _source_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(f"file:{self.source_path.as_posix()}?immutable=1", uri=True)

    def _cache_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.cache_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _cached_root(self) -> sqlite3.Row | None:
        if not self.cache_path.is_file():
            return None
        try:
            with closing(self._cache_connection()) as conn:
                return conn.execute("SELECT * FROM roots WHERE root_id=?", (self.root.root_id,)).fetchone()
        except sqlite3.Error:
            return None

    @staticmethod
    def _create_cache(conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            PRAGMA journal_mode=DELETE;
            PRAGMA synchronous=NORMAL;
            CREATE TABLE roots (
              root_id TEXT PRIMARY KEY, source_mtime REAL NOT NULL, source_updated_at TEXT,
              refreshed_at TEXT NOT NULL, document_count INTEGER NOT NULL
            );
            CREATE TABLE documents (
              root_id TEXT NOT NULL,path TEXT NOT NULL,title TEXT NOT NULL,snippet TEXT NOT NULL,
              source_mtime REAL NOT NULL,PRIMARY KEY(root_id,path)
            );
            CREATE TABLE headings (
              root_id TEXT NOT NULL,path TEXT NOT NULL,title TEXT NOT NULL,depth INTEGER NOT NULL,
              line INTEGER NOT NULL,slug TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE documents_fts USING fts5(
              root_id UNINDEXED,path UNINDEXED,title,text,tokenize='unicode61'
            );
            """
        )

    @staticmethod
    def _read_meta(conn: sqlite3.Connection) -> dict[str, str]:
        return {str(key): str(value) for key, value in conn.execute("SELECT key,value FROM meta")}

    def _require_root(self, root_id: str) -> None:
        if root_id != self.root.root_id:
            raise ValueError(f"Unknown Markdown root: {root_id!r}.")

    def _safe_document_path(self, relative_path: str) -> Path:
        normalized = self._validate_relative_markdown_path(relative_path)
        resolved_root = self.root.path.resolve()
        target = (resolved_root / Path(*PurePosixPath(normalized).parts)).resolve()
        if not target.is_relative_to(resolved_root):
            raise ValueError("Path escapes the configured Markdown root.")
        return target

    @staticmethod
    def _validate_relative_markdown_path(relative_path: str) -> str:
        normalized = relative_path.replace("\\", "/")
        pure = PurePosixPath(normalized)
        if (
            not normalized
            or pure.is_absolute()
            or re.match(r"^[A-Za-z]:[\\/]", normalized)
            or ".." in pure.parts
            or Path(normalized).suffix.lower() not in MARKDOWN_EXTENSIONS
        ):
            raise ValueError("Path must be a relative Markdown path inside the configured root.")
        return pure.as_posix()

    def _public_path(self, relative_path: str) -> str:
        relative = relative_path.replace("\\", "/").lstrip("/")
        if not self.root.public_path:
            return f"md://{self.root.root_id}/{relative}"
        if "\\" in self.root.public_path:
            return self.root.public_path.rstrip("\\/") + "\\" + relative.replace("/", "\\")
        return self.root.public_path.rstrip("/") + "/" + relative

    @staticmethod
    def _terms(value: str) -> list[str]:
        return [term for term in re.findall(r"[\w가-힣]{2,}", value.casefold()) if term]

    @staticmethod
    def _excerpt(text: str, query: str, limit: int) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        if len(compact) <= limit:
            return compact
        positions = [compact.casefold().find(term) for term in MarkdownSourceGraphService._terms(query)]
        start = max(0, min((position for position in positions if position >= 0), default=0) - limit // 4)
        end = min(len(compact), start + limit)
        return ("…" if start else "") + compact[start:end] + ("…" if end < len(compact) else "")

    @staticmethod
    def _parse_date(value: str | None, *, end: bool) -> datetime | None:
        if value is None:
            return None
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise ValueError("Dates must use YYYY-MM-DD.") from exc
        return parsed + timedelta(days=1, microseconds=-1) if end else parsed

    @staticmethod
    def _bounded(value: int, default: int, minimum: int, maximum: int) -> int:
        try:
            return max(minimum, min(maximum, int(value)))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _mtime_iso(value: float | int | None) -> str | None:
        if value is None:
            return None
        return (
            datetime.fromtimestamp(float(value) / 1000, timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
