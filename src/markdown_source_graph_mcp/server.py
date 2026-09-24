from __future__ import annotations

import argparse
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from .audit import AuditStore
from .dashboard import dashboard_html
from .hub import create_service
from .prompt_library import list_prompts
from .tool_catalog import tool_catalog


READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)


def service_health(service: Any) -> tuple[dict[str, Any], int]:
    if hasattr(service, "health"):
        return service.health()
    status = service.source_graph_status(service.root.root_id)
    healthy = bool(status["mps_index_present"] and status["supported"] and not status["source_error"])
    payload = {"status": "ok" if healthy else "error", "mode": "single", "root": status}
    if not healthy:
        payload["error"] = (
            status["source_error"]
            or "A supported .mps/source-graph.sqlite was not found in the mounted workspace."
        )
        payload["action"] = "Check MARKDOWN_MOUNT_SOURCE, then initialize Source Graph with Agent Docs."
    return payload, 200 if healthy else 503


def create_server(
    service: Any | None = None,
    host: str = "0.0.0.0",
    port: int = 8811,
) -> FastMCP:
    service = service or create_service()
    audit = AuditStore()
    mcp = FastMCP(
        "markdown-source-graph",
        instructions=(
            "Search and read the local Markdown workspace indexed by Agent Docs for Markdown. "
            "Call list_markdown_roots first when multiple roots are available. Select a root from "
            "its id, description, and public path when the question clearly matches one workspace; "
            "use search_all_markdown when it is ambiguous or spans workspaces. Use search_markdown "
            "before read_markdown and get_markdown_links when link context matters. The server is "
            "read-only and never edits Markdown files."
        ),
        host=host,
        port=port,
        json_response=True,
    )

    @mcp.tool(annotations=READ_ONLY)
    def search_markdown(
        query: str,
        root_id: str | None = None,
        limit: int = 10,
        excerpt_chars: int = 1200,
        modified_from: str | None = None,
        modified_to: str | None = None,
        sort_by: Literal["recent", "relevance"] = "relevance",
    ) -> dict[str, Any]:
        """Search the MPS index; date filters use YYYY-MM-DD."""
        params = {
            "query": query,
            "root_id": root_id,
            "limit": limit,
            "excerpt_chars": excerpt_chars,
            "modified_from": modified_from,
            "modified_to": modified_to,
            "sort_by": sort_by,
        }
        return audit.call(
            "search_markdown",
            params,
            lambda: service.search_markdown(
                query, root_id, limit, excerpt_chars, modified_from, modified_to, sort_by
            ),
        )

    @mcp.tool(annotations=READ_ONLY)
    def search_all_markdown(
        query: str,
        root_ids: list[str] | None = None,
        limit_per_root: int = 5,
        excerpt_chars: int = 800,
        sort_by: Literal["recent", "relevance"] = "relevance",
    ) -> dict[str, Any]:
        """Search every root, or a selected set, when a question may span workspaces."""
        def operation() -> dict[str, Any]:
            available = [item["root_id"] for item in service.root_statuses() if item.get("supported")]
            selected = root_ids or available
            results: list[dict[str, Any]] = []
            errors: list[dict[str, str]] = []
            for root_id in selected:
                try:
                    response = service.search_markdown(
                        query, root_id, limit_per_root, excerpt_chars, None, None, sort_by
                    )
                    results.extend(response["results"])
                except (OSError, ValueError) as exc:
                    errors.append({"root_id": root_id, "error": str(exc)})
            return {
                "query": query,
                "roots_searched": selected,
                "result_count": len(results),
                "results": results,
                "errors": errors,
            }

        return audit.call(
            "search_all_markdown",
            {
                "query": query,
                "root_ids": root_ids,
                "limit_per_root": limit_per_root,
                "excerpt_chars": excerpt_chars,
                "sort_by": sort_by,
            },
            operation,
        )

    @mcp.tool(annotations=READ_ONLY)
    def find_relevant_markdown_roots(
        query: str,
        sample_results_per_root: int = 3,
    ) -> dict[str, Any]:
        """Probe every root and return evidence for choosing the best workspace."""
        def operation() -> dict[str, Any]:
            candidates: list[dict[str, Any]] = []
            errors: list[dict[str, str]] = []
            for status in service.root_statuses():
                root_id = status["root_id"]
                if not status.get("supported"):
                    errors.append({"root_id": root_id, "error": status.get("error") or "Unsupported root."})
                    continue
                try:
                    response = service.search_markdown(
                        query, root_id, sample_results_per_root, 500, None, None, "relevance"
                    )
                    matches = response["results"]
                    candidates.append(
                        {
                            "root_id": root_id,
                            "description": status.get("description"),
                            "public_path": status.get("public_path"),
                            "source_documents": status.get("source_documents"),
                            "sample_match_count": len(matches),
                            "sample_matches": [
                                {
                                    "relative_path": item["relative_path"],
                                    "title": item["title"],
                                    "excerpt": item["excerpt"],
                                    "rank": item["rank"],
                                }
                                for item in matches
                            ],
                        }
                    )
                except (OSError, ValueError) as exc:
                    errors.append({"root_id": root_id, "error": str(exc)})
            candidates.sort(key=lambda item: item["sample_match_count"], reverse=True)
            return {"query": query, "candidates": candidates, "errors": errors}

        return audit.call(
            "find_relevant_markdown_roots",
            {"query": query, "sample_results_per_root": sample_results_per_root},
            operation,
        )

    @mcp.tool(annotations=READ_ONLY)
    def read_markdown(
        root_id: str,
        relative_path: str,
        start_line: int = 1,
        max_lines: int = 120,
    ) -> dict[str, Any]:
        """Read a bounded line range from a Markdown search result."""
        return audit.call(
            "read_markdown",
            {
                "root_id": root_id,
                "relative_path": relative_path,
                "start_line": start_line,
                "max_lines": max_lines,
            },
            lambda: service.read_markdown(root_id, relative_path, start_line, max_lines),
        )

    @mcp.tool(annotations=READ_ONLY)
    def get_markdown_links(
        root_id: str,
        relative_path: str,
        direction: Literal["outgoing", "incoming", "both"] = "both",
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return outgoing links and backlinks recorded in the Source Graph."""
        return audit.call(
            "get_markdown_links",
            {"root_id": root_id, "relative_path": relative_path, "direction": direction, "limit": limit},
            lambda: service.get_markdown_links(root_id, relative_path, direction, limit),
        )

    @mcp.tool(annotations=READ_ONLY)
    def list_markdown_roots() -> list[dict[str, Any]]:
        """List mounted roots, descriptions, document counts, and Source Graph freshness."""
        return audit.call("list_markdown_roots", {}, service.root_statuses)

    @mcp.tool(annotations=READ_ONLY)
    def get_source_graph_status(root_id: str = "workspace") -> dict[str, Any]:
        """Show Source Graph compatibility, document count, and cache freshness."""
        return audit.call(
            "get_source_graph_status", {"root_id": root_id}, lambda: service.source_graph_status(root_id)
        )

    @mcp.tool(annotations=READ_ONLY)
    def refresh_markdown_root(root_id: str = "workspace") -> dict[str, Any]:
        """Re-import the current MPS index into the MCP search cache."""
        return audit.call("refresh_markdown_root", {"root_id": root_id}, lambda: service.refresh_root(root_id))

    @mcp.custom_route("/healthz", methods=["GET"], include_in_schema=False)
    async def healthz(_: Request) -> JSONResponse:
        payload, status_code = service_health(service)
        return JSONResponse(payload, status_code=status_code, headers={"Cache-Control": "no-store"})

    @mcp.custom_route("/", methods=["GET"], include_in_schema=False)
    @mcp.custom_route("/dashboard", methods=["GET"], include_in_schema=False)
    async def dashboard(_: Request) -> HTMLResponse:
        return HTMLResponse(
            dashboard_html(),
            headers={
                "Cache-Control": "no-store",
                "Content-Security-Policy": (
                    "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
                    "connect-src 'self'; img-src 'self' data:"
                ),
            },
        )

    @mcp.custom_route("/api/activity", methods=["GET"], include_in_schema=False)
    async def activity(request: Request) -> JSONResponse:
        try:
            page = int(request.query_params.get("page", "1"))
            page_size = int(request.query_params.get("page_size", request.query_params.get("limit", "20")))
        except ValueError:
            page, page_size = 1, 20
        tool = request.query_params.get("tool") or None
        query = request.query_params.get("q") or None
        return JSONResponse(
            audit.dashboard_data(page, page_size, tool, query), headers={"Cache-Control": "no-store"}
        )

    @mcp.custom_route("/api/patterns", methods=["GET"], include_in_schema=False)
    async def patterns(request: Request) -> JSONResponse:
        try:
            page = int(request.query_params.get("page", "1"))
            page_size = int(request.query_params.get("page_size", "12"))
        except ValueError:
            page, page_size = 1, 12
        return JSONResponse(
            audit.patterns_data(page, page_size, request.query_params.get("q") or None),
            headers={"Cache-Control": "no-store"},
        )

    @mcp.custom_route("/api/prompts", methods=["GET"], include_in_schema=False)
    async def prompts(_: Request) -> JSONResponse:
        return JSONResponse({"prompts": list_prompts()}, headers={"Cache-Control": "no-store"})

    @mcp.custom_route("/api/tools", methods=["GET"], include_in_schema=False)
    async def tools(_: Request) -> JSONResponse:
        return JSONResponse({"tools": tool_catalog()}, headers={"Cache-Control": "no-store"})

    @mcp.custom_route("/api/search", methods=["GET"], include_in_schema=False)
    async def dashboard_search(request: Request) -> JSONResponse:
        query = (request.query_params.get("q") or "").strip()
        root_id = request.query_params.get("root_id") or None
        try:
            page = max(1, int(request.query_params.get("page", "1")))
            page_size = max(5, min(20, int(request.query_params.get("page_size", "10"))))
        except ValueError:
            page, page_size = 1, 10
        if not query:
            return JSONResponse({"error": "검색어를 입력하세요."}, status_code=400)

        def operation() -> dict[str, Any]:
            roots = [root_id] if root_id else [
                item["root_id"] for item in service.root_statuses() if item.get("supported")
            ]
            buckets: list[list[dict[str, Any]]] = []
            errors: list[dict[str, str]] = []
            for selected in roots:
                try:
                    buckets.append(service.search_markdown(query, selected, 50, 700)["results"])
                except (OSError, ValueError) as exc:
                    errors.append({"root_id": selected, "error": str(exc)})
            found = [
                item
                for index in range(max((len(bucket) for bucket in buckets), default=0))
                for bucket in buckets
                for item in bucket[index : index + 1]
            ]
            start = (page - 1) * page_size
            return {
                "query": query,
                "root_id": root_id,
                "results": found[start : start + page_size],
                "errors": errors,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": len(found),
                    "pages": max(1, (len(found) + page_size - 1) // page_size),
                },
            }

        payload = audit.call(
            "dashboard_search",
            {"query": query, "root_id": root_id, "page": page, "page_size": page_size},
            operation,
        )
        return JSONResponse(payload, headers={"Cache-Control": "no-store"})

    return mcp


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Agent Docs Source Graph MCP server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8811)
    args = parser.parse_args(argv)
    create_server(host=args.host, port=args.port).run(transport="streamable-http")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
