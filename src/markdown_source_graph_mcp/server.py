from __future__ import annotations

import argparse
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import JSONResponse

from .hub import create_service


READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)


def create_server(
    service: Any | None = None,
    host: str = "0.0.0.0",
    port: int = 8811,
) -> FastMCP:
    service = service or create_service()
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
        return service.search_markdown(
            query,
            root_id,
            limit,
            excerpt_chars,
            modified_from,
            modified_to,
            sort_by,
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
        available = [item["root_id"] for item in service.root_statuses() if item.get("supported")]
        selected = root_ids or available
        results: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for root_id in selected:
            try:
                response = service.search_markdown(
                    query,
                    root_id,
                    limit_per_root,
                    excerpt_chars,
                    None,
                    None,
                    sort_by,
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

    @mcp.tool(annotations=READ_ONLY)
    def find_relevant_markdown_roots(
        query: str,
        sample_results_per_root: int = 3,
    ) -> dict[str, Any]:
        """Probe every root and return evidence for choosing the best workspace."""
        candidates: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for status in service.root_statuses():
            root_id = status["root_id"]
            if not status.get("supported"):
                errors.append({"root_id": root_id, "error": status.get("error") or "Unsupported root."})
                continue
            try:
                response = service.search_markdown(
                    query,
                    root_id,
                    sample_results_per_root,
                    500,
                    None,
                    None,
                    "relevance",
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

    @mcp.tool(annotations=READ_ONLY)
    def read_markdown(
        root_id: str,
        relative_path: str,
        start_line: int = 1,
        max_lines: int = 120,
    ) -> dict[str, Any]:
        """Read a bounded line range from a Markdown search result."""
        return service.read_markdown(root_id, relative_path, start_line, max_lines)

    @mcp.tool(annotations=READ_ONLY)
    def get_markdown_links(
        root_id: str,
        relative_path: str,
        direction: Literal["outgoing", "incoming", "both"] = "both",
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return outgoing links and backlinks recorded in the Source Graph."""
        return service.get_markdown_links(root_id, relative_path, direction, limit)

    @mcp.tool(annotations=READ_ONLY)
    def list_markdown_roots() -> list[dict[str, Any]]:
        """List mounted roots, descriptions, document counts, and Source Graph freshness."""
        return service.root_statuses()

    @mcp.tool(annotations=READ_ONLY)
    def get_source_graph_status(root_id: str = "workspace") -> dict[str, Any]:
        """Show Source Graph compatibility, document count, and cache freshness."""
        return service.source_graph_status(root_id)

    @mcp.tool(annotations=READ_ONLY)
    def refresh_markdown_root(root_id: str = "workspace") -> dict[str, Any]:
        """Re-import the current MPS index into the MCP search cache."""
        return service.refresh_root(root_id)

    @mcp.custom_route("/healthz", methods=["GET"], include_in_schema=False)
    async def healthz(_: Request) -> JSONResponse:
        if hasattr(service, "health"):
            payload, status_code = service.health()
            return JSONResponse(payload, status_code=status_code)
        status = service.source_graph_status(service.root.root_id)
        healthy = bool(status["mps_index_present"] and status["supported"] and not status["source_error"])
        payload = {"status": "ok" if healthy else "error", "mode": "single", "root": status}
        if not healthy:
            payload["error"] = (
                status["source_error"]
                or "A supported .mps/source-graph.sqlite was not found in the mounted workspace."
            )
            payload["action"] = (
                "Check MARKDOWN_MOUNT_SOURCE, then initialize Source Graph with Agent Docs for Markdown."
            )
        return JSONResponse(payload, status_code=200 if healthy else 503)

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
