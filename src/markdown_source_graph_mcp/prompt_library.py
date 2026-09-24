from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def prompt_root(environ: dict[str, str] | None = None) -> Path:
    env = dict(os.environ if environ is None else environ)
    configured = env.get("MARKDOWN_MCP_PROMPT_DIR")
    return Path(configured) if configured else Path(__file__).resolve().parents[2] / "examples" / "prompts"


def list_prompts(environ: dict[str, str] | None = None) -> list[dict[str, Any]]:
    root = prompt_root(environ).resolve()
    if not root.is_dir():
        return []
    prompts: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.md")):
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            continue
        relative = resolved.relative_to(root).as_posix()
        text = resolved.read_text(encoding="utf-8")
        title = next(
            (line.removeprefix("# ").strip() for line in text.splitlines() if line.startswith("# ")),
            path.stem.replace("-", " ").title(),
        )
        prompts.append(
            {
                "id": relative,
                "category": relative.split("/", 1)[0] if "/" in relative else "shared",
                "title": title,
                "content": text,
            }
        )
    return prompts
