from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .service import MarkdownSourceGraphService


@dataclass(frozen=True)
class ConfiguredRoot:
    root_id: str
    path: Path
    public_path: str | None
    description: str | None


class WorkspaceHubService:
    """Route MCP calls to workspaces below one pre-mounted, read-only parent."""

    def __init__(self, environ: dict[str, str] | None = None):
        self.environ = dict(os.environ if environ is None else environ)
        self.hub_path = Path(self.environ.get("MARKDOWN_MCP_HUB_PATH", "/markdown"))
        self.public_path = self.environ.get("MARKDOWN_MCP_HUB_PUBLIC_PATH") or None
        self.state_dir = Path(self.environ.get("MARKDOWN_MCP_STATE_DIR", ".markdown-mcp-state"))
        self.max_depth = max(1, min(10, int(self.environ.get("MARKDOWN_MCP_DISCOVERY_MAX_DEPTH", "4"))))
        self.discovery_ttl = max(1, int(self.environ.get("MARKDOWN_MCP_DISCOVERY_TTL_SECONDS", "15")))
        self._discovery_cache: tuple[float, list[str]] | None = None
        self._discovery_lock = threading.Lock()

    def root_statuses(self) -> list[dict[str, Any]]:
        statuses: list[dict[str, Any]] = []
        for root_id in self.discover_root_ids():
            try:
                statuses.append(self._service(root_id).source_graph_status(root_id))
            except (OSError, ValueError) as exc:
                statuses.append({"root_id": root_id, "supported": False, "error": str(exc)})
        return statuses

    def discover_root_ids(self, force: bool = False) -> list[str]:
        if not self.hub_path.is_dir():
            return []
        now = time.monotonic()
        with self._discovery_lock:
            if not force and self._discovery_cache and now - self._discovery_cache[0] < self.discovery_ttl:
                return list(self._discovery_cache[1])
            roots: list[str] = []
            base_depth = len(self.hub_path.resolve().parts)
            for base, dirs, _ in os.walk(self.hub_path):
                base_path = Path(base)
                depth = len(base_path.resolve().parts) - base_depth
                index = base_path / ".mps" / "source-graph.sqlite"
                if index.is_file():
                    relative = base_path.relative_to(self.hub_path).as_posix()
                    roots.append(relative if relative != "." else "workspace")
                    dirs[:] = []
                    continue
                if depth >= self.max_depth:
                    dirs[:] = []
                    continue
                dirs[:] = [
                    name
                    for name in dirs
                    if name not in {".git", ".mps", "node_modules", ".venv", "dist", "build"}
                    and not name.startswith(".")
                ]
            found = sorted(set(roots))
            self._discovery_cache = (now, found)
            return list(found)

    def source_graph_status(self, root_id: str) -> dict[str, Any]:
        return self._service(root_id).source_graph_status(root_id)

    def refresh_root(self, root_id: str) -> dict[str, Any]:
        return self._service(root_id).refresh_root(root_id)

    def search_markdown(self, query: str, root_id: str | None = None, *args: Any, **kwargs: Any) -> dict[str, Any]:
        selected = self._require_selected_root(root_id)
        return self._service(selected).search_markdown(query, selected, *args, **kwargs)

    def read_markdown(self, root_id: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._service(root_id).read_markdown(root_id, *args, **kwargs)

    def get_markdown_links(self, root_id: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._service(root_id).get_markdown_links(root_id, *args, **kwargs)

    def health(self) -> tuple[dict[str, Any], int]:
        if not self.hub_path.is_dir():
            return (
                {
                    "status": "error",
                    "mode": "hub",
                    "error": f"Mounted hub directory does not exist: {self.hub_path}",
                    "action": "Check MARKDOWN_MOUNT_SOURCE and Docker file sharing.",
                },
                503,
            )
        roots = self.root_statuses()
        valid = [item for item in roots if item.get("mps_index_present") and item.get("supported")]
        if not valid:
            return (
                {
                    "status": "error",
                    "mode": "hub",
                    "error": "No supported .mps/source-graph.sqlite was found below the mounted hub.",
                    "action": "Initialize Source Graph in Agent Docs or increase MARKDOWN_MCP_DISCOVERY_MAX_DEPTH.",
                    "discovered_roots": roots,
                },
                503,
            )
        return ({"status": "ok", "mode": "hub", "root_count": len(valid), "roots": valid}, 200)

    def _require_selected_root(self, root_id: str | None) -> str:
        if root_id:
            return root_id
        roots = self.discover_root_ids()
        if len(roots) == 1:
            return roots[0]
        raise ValueError("Hub mode requires root_id. Call list_markdown_roots and choose one workspace.")

    def _service(self, root_id: str) -> MarkdownSourceGraphService:
        relative = self._safe_root_id(root_id)
        path = self.hub_path if relative == "workspace" else self.hub_path.joinpath(*PurePosixPath(relative).parts)
        resolved_hub = self.hub_path.resolve()
        resolved_path = path.resolve()
        if not resolved_path.is_relative_to(resolved_hub):
            raise ValueError("root_id escapes the mounted workspace hub.")
        public = self._public_root(relative)
        cache_key = hashlib.sha256(relative.encode("utf-8")).hexdigest()[:16]
        env = {
            "MARKDOWN_MCP_ROOT_ID": root_id,
            "MARKDOWN_MCP_ROOT_PATH": str(resolved_path),
            "MARKDOWN_MCP_STATE_DIR": str(self.state_dir / cache_key),
        }
        if public:
            env["MARKDOWN_MCP_PUBLIC_PATH"] = public
        return MarkdownSourceGraphService(env)

    @staticmethod
    def _safe_root_id(root_id: str) -> str:
        normalized = root_id.replace("\\", "/").strip("/")
        if root_id == "workspace":
            return root_id
        pure = PurePosixPath(normalized)
        if not normalized or pure.is_absolute() or ".." in pure.parts or ":" in normalized:
            raise ValueError("root_id must be a relative workspace path below the mounted hub.")
        return pure.as_posix()

    def _public_root(self, relative: str) -> str | None:
        if not self.public_path:
            return None
        if relative == "workspace":
            return self.public_path
        if "\\" in self.public_path:
            return self.public_path.rstrip("\\/") + "\\" + relative.replace("/", "\\")
        return self.public_path.rstrip("/") + "/" + relative


class ConfiguredRootsService:
    """Route MCP calls to an explicit allowlist of read-only workspace mounts."""

    def __init__(self, environ: dict[str, str] | None = None):
        self.environ = dict(os.environ if environ is None else environ)
        self.state_dir = Path(self.environ.get("MARKDOWN_MCP_STATE_DIR", ".markdown-mcp-state"))
        self.roots = self._parse_roots(self.environ.get("MARKDOWN_MCP_ROOTS_JSON", ""))

    def discover_root_ids(self, force: bool = False) -> list[str]:
        del force
        return sorted(self.roots)

    def root_statuses(self) -> list[dict[str, Any]]:
        statuses: list[dict[str, Any]] = []
        for root_id in self.discover_root_ids():
            try:
                statuses.append(self.source_graph_status(root_id))
            except (OSError, ValueError) as exc:
                statuses.append({"root_id": root_id, "supported": False, "error": str(exc)})
        return statuses

    def source_graph_status(self, root_id: str) -> dict[str, Any]:
        root = self._root(root_id)
        status = self._service(root_id).source_graph_status(root_id)
        status["description"] = root.description
        return status

    def refresh_root(self, root_id: str) -> dict[str, Any]:
        return self._service(root_id).refresh_root(root_id)

    def search_markdown(self, query: str, root_id: str | None = None, *args: Any, **kwargs: Any) -> dict[str, Any]:
        selected = self._require_selected_root(root_id)
        return self._service(selected).search_markdown(query, selected, *args, **kwargs)

    def read_markdown(self, root_id: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._service(root_id).read_markdown(root_id, *args, **kwargs)

    def get_markdown_links(self, root_id: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self._service(root_id).get_markdown_links(root_id, *args, **kwargs)

    def health(self) -> tuple[dict[str, Any], int]:
        if not self.roots:
            return (
                {
                    "status": "error",
                    "mode": "multi",
                    "error": "No named Markdown roots are configured.",
                    "action": "Set MARKDOWN_MCP_ROOTS_JSON and mount every configured path read-only.",
                },
                503,
            )
        statuses = self.root_statuses()
        valid = [item for item in statuses if item.get("mps_index_present") and item.get("supported")]
        invalid = [item for item in statuses if item not in valid]
        if not valid:
            return (
                {
                    "status": "error",
                    "mode": "multi",
                    "error": "No configured root has a supported .mps/source-graph.sqlite.",
                    "action": "Check every bind mount and initialize Source Graph with Agent Docs.",
                    "roots": statuses,
                },
                503,
            )
        payload: dict[str, Any] = {
            "status": "degraded" if invalid else "ok",
            "mode": "multi",
            "root_count": len(valid),
            "roots": statuses,
        }
        if invalid:
            payload["action"] = "Some roots are unavailable; inspect their status and bind mounts."
        return payload, 200

    def _require_selected_root(self, root_id: str | None) -> str:
        if root_id:
            self._root(root_id)
            return root_id
        if len(self.roots) == 1:
            return next(iter(self.roots))
        raise ValueError("Multi mode requires root_id. Call list_markdown_roots or use search_all_markdown.")

    def _root(self, root_id: str) -> ConfiguredRoot:
        try:
            return self.roots[root_id]
        except KeyError as exc:
            raise ValueError(f"Unknown Markdown root: {root_id!r}.") from exc

    def _service(self, root_id: str) -> MarkdownSourceGraphService:
        root = self._root(root_id)
        cache_key = hashlib.sha256(root_id.encode("utf-8")).hexdigest()[:16]
        env = {
            "MARKDOWN_MCP_ROOT_ID": root.root_id,
            "MARKDOWN_MCP_ROOT_PATH": str(root.path),
            "MARKDOWN_MCP_STATE_DIR": str(self.state_dir / cache_key),
        }
        if root.public_path:
            env["MARKDOWN_MCP_PUBLIC_PATH"] = root.public_path
        return MarkdownSourceGraphService(env)

    @staticmethod
    def _parse_roots(raw: str) -> dict[str, ConfiguredRoot]:
        if not raw.strip():
            return {}
        try:
            items = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"MARKDOWN_MCP_ROOTS_JSON is invalid JSON: {exc}") from exc
        if not isinstance(items, list):
            raise ValueError("MARKDOWN_MCP_ROOTS_JSON must be a JSON array.")
        roots: dict[str, ConfiguredRoot] = {}
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("Every configured root must be a JSON object.")
            root_id = str(item.get("id", "")).strip()
            path_text = str(item.get("path", "")).strip()
            if not root_id or WorkspaceHubService._safe_root_id(root_id) != root_id:
                raise ValueError("Each configured root id must be a safe relative identifier.")
            if root_id in roots:
                raise ValueError(f"Duplicate configured root id: {root_id!r}.")
            if not path_text:
                raise ValueError(f"Configured root {root_id!r} requires path.")
            roots[root_id] = ConfiguredRoot(
                root_id=root_id,
                path=Path(path_text),
                public_path=str(item.get("public_path") or "") or None,
                description=str(item.get("description") or "") or None,
            )
        return roots


def create_service(
    environ: dict[str, str] | None = None,
) -> MarkdownSourceGraphService | WorkspaceHubService | ConfiguredRootsService:
    env = dict(os.environ if environ is None else environ)
    mode = env.get("MARKDOWN_MCP_MODE", "single").casefold()
    if mode == "hub":
        return WorkspaceHubService(env)
    if mode == "multi":
        return ConfiguredRootsService(env)
    return MarkdownSourceGraphService(env)
