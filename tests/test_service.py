from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from markdown_source_graph_mcp.service import MarkdownSourceGraphService
from markdown_source_graph_mcp.hub import ConfiguredRootsService, WorkspaceHubService


SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE documents (
 id TEXT PRIMARY KEY,path TEXT,title TEXT,source_hash TEXT,mtime_ms REAL,size INTEGER,
 line_count INTEGER,word_count INTEGER,heading_count INTEGER,outgoing_count INTEGER,
 incoming_count INTEGER,snippet TEXT
);
CREATE TABLE headings (id TEXT PRIMARY KEY,document_id TEXT,slug TEXT,title TEXT,depth INTEGER,line INTEGER);
CREATE TABLE links (
 id TEXT PRIMARY KEY,source_document_id TEXT,target_document_id TEXT,source_path TEXT,
 target_path TEXT,href TEXT,label TEXT,type TEXT,line INTEGER,status TEXT,anchor TEXT
);
CREATE TABLE search_index (document_id TEXT PRIMARY KEY,path TEXT,title TEXT,text TEXT,blob_id TEXT);
CREATE TABLE search_blobs (id TEXT PRIMARY KEY,text TEXT);
"""


def make_workspace(root: Path, kind: str = "markdown-agent-docs.source-graph") -> None:
    (root / ".mps").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "docs" / "alpha.md").write_text("# Alpha\nAgent runtime notes.\n[Beta](beta.md)\n", encoding="utf-8")
    (root / "docs" / "beta.md").write_text("# Beta\nMCP search details.\n", encoding="utf-8")
    conn = sqlite3.connect(root / ".mps" / "source-graph.sqlite")
    conn.executescript(SCHEMA)
    conn.executemany(
        "INSERT INTO meta VALUES (?,?)",
        [("schemaVersion", "1"), ("kind", kind), ("updatedAt", "2026-09-24T00:00:00Z")],
    )
    docs = [
        ("a", "docs/alpha.md", "Alpha", "", 1_700_000_000_000, 1, 3, 4, 1, 1, 0, "Agent runtime notes"),
        ("b", "docs/beta.md", "Beta", "", 1_700_000_100_000, 1, 2, 3, 1, 0, 1, "MCP search details"),
    ]
    conn.executemany("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", docs)
    conn.executemany(
        "INSERT INTO headings VALUES (?,?,?,?,?,?)",
        [("ha", "a", "alpha", "Alpha", 1, 1), ("hb", "b", "beta", "Beta", 1, 1)],
    )
    conn.execute(
        "INSERT INTO links VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ("l1", "a", "b", "docs/alpha.md", "docs/beta.md", "beta.md", "Beta", "link", 3, "resolved", ""),
    )
    conn.executemany("INSERT INTO search_blobs VALUES (?,?)", [("ba", "agent runtime notes"), ("bb", "mcp search details")])
    conn.executemany(
        "INSERT INTO search_index VALUES (?,?,?,?,?)",
        [("a", "docs/alpha.md", "Alpha", "", "ba"), ("b", "docs/beta.md", "Beta", "", "bb")],
    )
    conn.commit()
    conn.close()


@pytest.fixture
def service(tmp_path: Path) -> MarkdownSourceGraphService:
    root = tmp_path / "workspace"
    make_workspace(root)
    return MarkdownSourceGraphService(
        {
            "MARKDOWN_MCP_ROOT_ID": "workspace",
            "MARKDOWN_MCP_ROOT_PATH": str(root),
            "MARKDOWN_MCP_PUBLIC_PATH": "C:\\notes",
            "MARKDOWN_MCP_STATE_DIR": str(tmp_path / "state"),
        }
    )


def test_refresh_search_read_and_links(service: MarkdownSourceGraphService):
    refreshed = service.refresh_root("workspace")
    assert refreshed["indexed_documents"] == 2
    result = service.search_markdown("runtime")
    assert result["results"][0]["relative_path"] == "docs/alpha.md"
    assert result["results"][0]["path"] == "C:\\notes\\docs\\alpha.md"
    assert service.read_markdown("workspace", "docs/alpha.md")["content"].startswith("# Alpha")
    links = service.get_markdown_links("workspace", "docs/beta.md")
    assert links["incoming"][0]["relative_path"] == "docs/alpha.md"


def test_legacy_markdown_pattern_studio_kind_is_supported(tmp_path: Path):
    root = tmp_path / "legacy"
    make_workspace(root, "markdown-pattern-studio.source-graph")
    service = MarkdownSourceGraphService(
        {"MARKDOWN_MCP_ROOT_PATH": str(root), "MARKDOWN_MCP_STATE_DIR": str(tmp_path / "state")}
    )
    assert service.refresh_root("workspace")["source_kind"] == "markdown-pattern-studio.source-graph"


def test_path_traversal_is_rejected(service: MarkdownSourceGraphService):
    with pytest.raises(ValueError, match="relative Markdown path"):
        service.read_markdown("workspace", "../secret.md")


def test_hub_discovers_and_switches_workspaces(tmp_path: Path):
    hub = tmp_path / "hub"
    make_workspace(hub / "team" / "wiki")
    service = WorkspaceHubService(
        {
            "MARKDOWN_MCP_HUB_PATH": str(hub),
            "MARKDOWN_MCP_HUB_PUBLIC_PATH": "C:\\knowledge",
            "MARKDOWN_MCP_STATE_DIR": str(tmp_path / "state"),
            "MARKDOWN_MCP_DISCOVERY_MAX_DEPTH": "3",
        }
    )
    assert service.discover_root_ids() == ["team/wiki"]
    assert service.search_markdown("runtime", root_id="team/wiki")["results"][0]["path"].startswith(
        "C:\\knowledge\\team\\wiki"
    )
    payload, status_code = service.health()
    assert status_code == 200
    assert payload["root_count"] == 1
    with pytest.raises(ValueError, match="relative workspace path"):
        service.source_graph_status("../outside")


def test_hub_health_fails_when_no_index_exists(tmp_path: Path):
    hub = tmp_path / "empty"
    hub.mkdir()
    service = WorkspaceHubService({"MARKDOWN_MCP_HUB_PATH": str(hub)})
    payload, status_code = service.health()
    assert status_code == 503
    assert "No supported" in payload["error"]


def test_configured_roots_select_and_describe_separate_mounts(tmp_path: Path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    make_workspace(first)
    make_workspace(second)
    roots_json = (
        f'['
        f'{{"id":"monitoring","path":"{first.as_posix()}","description":"operations"}},'
        f'{{"id":"career","path":"{second.as_posix()}","description":"job research"}}'
        f']'
    )
    service = ConfiguredRootsService(
        {
            "MARKDOWN_MCP_ROOTS_JSON": roots_json,
            "MARKDOWN_MCP_STATE_DIR": str(tmp_path / "state"),
        }
    )
    assert service.discover_root_ids() == ["career", "monitoring"]
    statuses = service.root_statuses()
    assert {item["description"] for item in statuses} == {"operations", "job research"}
    assert service.search_markdown("runtime", root_id="monitoring")["results"][0]["root_id"] == "monitoring"
    assert service.search_markdown("MCP", root_id="career")["results"][0]["root_id"] == "career"
    payload, status_code = service.health()
    assert status_code == 200
    assert payload["root_count"] == 2
    with pytest.raises(ValueError, match="Unknown Markdown root"):
        service.source_graph_status("other")
