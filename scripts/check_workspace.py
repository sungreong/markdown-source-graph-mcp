from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path


SUPPORTED = {"markdown-agent-docs.source-graph", "markdown-pattern-studio.source-graph"}


def inspect_index(workspace: Path) -> tuple[bool, str]:
    index = workspace / ".mps" / "source-graph.sqlite"
    if not index.is_file():
        return False, f"missing: {index}"
    try:
        conn = sqlite3.connect(f"file:{index.as_posix()}?mode=ro", uri=True)
        meta = dict(conn.execute("SELECT key,value FROM meta"))
        count = int(conn.execute("SELECT count(*) FROM documents").fetchone()[0])
        conn.close()
    except sqlite3.Error as exc:
        return False, f"invalid SQLite index: {index} ({exc})"
    if meta.get("schemaVersion") != "1" or meta.get("kind") not in SUPPORTED:
        return False, f"unsupported index: schema={meta.get('schemaVersion')!r}, kind={meta.get('kind')!r}"
    return True, f"ok: {workspace} ({count} documents, {meta.get('kind')})"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Agent Docs Source Graph workspaces before Docker Compose.")
    parser.add_argument("path", type=Path, help="Workspace path in single mode, or parent path in hub mode")
    parser.add_argument("--hub", action="store_true", help="Discover workspaces recursively below the path")
    parser.add_argument("--max-depth", type=int, default=4)
    args = parser.parse_args()
    root = args.path.expanduser().resolve()
    if not root.is_dir():
        print(f"ERROR: mounted path does not exist or is not a directory: {root}", file=sys.stderr)
        return 2
    if not args.hub:
        valid, message = inspect_index(root)
        print(("OK: " if valid else "ERROR: ") + message, file=sys.stdout if valid else sys.stderr)
        return 0 if valid else 2
    matches: list[Path] = []
    for base, dirs, _ in os.walk(root):
        base_path = Path(base)
        depth = len(base_path.relative_to(root).parts)
        index = base_path / ".mps" / "source-graph.sqlite"
        if index.is_file():
            matches.append(base_path)
            dirs[:] = []
            continue
        if depth >= max(1, args.max_depth):
            dirs[:] = []
            continue
        dirs[:] = [
            name
            for name in dirs
            if name not in {".git", ".mps", "node_modules", ".venv", "dist", "build"}
            and not name.startswith(".")
        ]
    valid_count = 0
    for workspace in sorted(set(matches)):
        valid, message = inspect_index(workspace)
        print(("OK: " if valid else "WARN: ") + message)
        valid_count += int(valid)
    if not valid_count:
        print("ERROR: no supported Source Graph workspace found in hub path.", file=sys.stderr)
        return 2
    print(f"OK: {valid_count} workspace(s) ready for Hub mode.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
