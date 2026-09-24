from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from markdown_source_graph_mcp.audit import AuditStore
from markdown_source_graph_mcp.service import MarkdownSourceGraphService
from markdown_source_graph_mcp.hub import ConfiguredRootsService, WorkspaceHubService
from markdown_source_graph_mcp.dashboard import dashboard_html
from markdown_source_graph_mcp.prompt_library import list_prompts
from markdown_source_graph_mcp.tool_catalog import tool_catalog


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


def test_dashboard_contains_health_monitoring_ui():
    html = dashboard_html()
    assert "Markdown Knowledge Hub" in html
    assert "./healthz" in html
    assert "검색 가능한 문서" in html
    assert "지식 검색" in html
    assert "질문 패턴" in html
    assert "바로 쓰는 프롬프트" in html
    assert "MCP 도구 안내" in html


def test_audit_store_records_parameters_without_document_content(tmp_path: Path):
    audit = AuditStore(
        {
            "MARKDOWN_MCP_AUDIT_ENABLED": "true",
            "MARKDOWN_MCP_AUDIT_MAX_ENTRIES": "100",
            "MARKDOWN_MCP_STATE_DIR": str(tmp_path),
        }
    )
    result = audit.call(
        "search_markdown",
        {"query": "career", "root_id": "career-signal", "limit": 2},
        lambda: {"results": [{"content": "must not be stored"}], "query": "career"},
    )
    assert result["results"][0]["content"] == "must not be stored"
    data = audit.dashboard_data()
    assert data["summary"]["total_calls"] == 1
    assert data["calls"][0]["params"]["root_id"] == "career-signal"
    assert data["calls"][0]["result"] == {"query": "career", "result_count": 1}
    assert data["pagination"] == {"page": 1, "page_size": 20, "total": 1, "pages": 1}
    assert data["tools"] == ["search_markdown"]
    assert audit.patterns_data()["patterns"][0]["uses"] == 1
    assert "must not be stored" not in audit.path.read_text(encoding="utf-8", errors="ignore")


def test_audit_store_paginates_and_filters(tmp_path: Path):
    audit = AuditStore(
        {
            "MARKDOWN_MCP_AUDIT_ENABLED": "true",
            "MARKDOWN_MCP_STATE_DIR": str(tmp_path),
        }
    )
    for index in range(7):
        audit.record("search_markdown", {"query": f"query-{index}"}, "success", 0.01, {}, None)
    second = audit.dashboard_data(page=2, page_size=5)
    assert second["pagination"] == {"page": 2, "page_size": 5, "total": 7, "pages": 2}
    assert len(second["calls"]) == 2
    assert audit.dashboard_data(query="query-6")["pagination"]["total"] == 1


def test_prompt_library_groups_markdown_files(tmp_path: Path):
    prompt = tmp_path / "codex" / "install.md"
    prompt.parent.mkdir()
    prompt.write_text("# Codex Install\n\nDo the setup.\n", encoding="utf-8")
    items = list_prompts({"MARKDOWN_MCP_PROMPT_DIR": str(tmp_path)})
    assert items == [
        {
            "id": "codex/install.md",
            "category": "codex",
            "title": "Codex Install",
            "content": "# Codex Install\n\nDo the setup.\n",
        }
    ]


def test_tool_catalog_documents_every_mcp_tool():
    tools = tool_catalog()
    assert len(tools) == 8
    assert {item["name"] for item in tools} >= {
        "list_markdown_roots",
        "search_markdown",
        "search_all_markdown",
        "read_markdown",
    }
