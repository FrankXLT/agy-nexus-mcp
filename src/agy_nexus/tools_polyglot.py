#!/usr/bin/env python3
"""agy_nexus.tools_polyglot — Deadbolt-Free Local Antigravity Polyglot MCP Server (agy-polyglot-mcp).

Exposes a dedicated local MCP surface (`polyglot_map`, `polyglot_search`, `polyglot_outline`)
backed by the shared incremental SHA-256 Polyglot index (`polyglot_index.py`) without mixing
remote Gemini Web/Mobile bridge handoff/deadbolt tools into Antigravity IDE sessions.
"""
from __future__ import annotations

import sys

from fastmcp import FastMCP

from agy_nexus.config import READONLY_ANNOTATIONS, _compact_json
from agy_nexus.polyglot_index import (
    polyglot_file_outline,
    polyglot_repo_map,
    polyglot_symbol_search,
)

polyglot_mcp = FastMCP(
    name="agy-polyglot-mcp",
    instructions=(
        "AGY-POLYGLOT-MCP — Local Semantic Outliner & Incremental SHA-256 Codebase Index for Antigravity IDE.\n"
        "- Call `polyglot_map(workspace=..., path_prefix=...)` first when exploring an unfamiliar repository or directory.\n"
        "- Call `polyglot_search(query=..., workspace=..., kind=...)` to locate functions, classes, markdown sections, JSON/YAML keys, and 1-liner docstrings with exact Lstart-Lend spans.\n"
        "- Call `polyglot_outline(file_subpath=..., workspace=..., include_callers=...)` to inspect all symbol spans and 1-liner summaries of a file before reading targeted line slices via view_file."
    ),
)


@polyglot_mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
def polyglot_map(
    workspace: str = "",
    path_prefix: str = "",
    limit: int = 120,
    force_refresh: bool = False,
) -> str:
    """Build or incrementally refresh the SHA-256 Polyglot index for a workspace and return its semantic file map with top symbol spans and 1-liner summaries."""
    res = polyglot_repo_map(
        workspace=workspace,
        path_prefix=path_prefix,
        limit=limit,
        force_refresh=force_refresh,
    )
    return _compact_json(res)


@polyglot_mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
def polyglot_search(
    query: str,
    workspace: str = "",
    kind: str = "",
    limit: int = 25,
    force_refresh: bool = False,
) -> str:
    """Search indexed functions, classes, methods, Markdown headings, JSON/YAML keys, CSS rules, and 1-liner docstrings across a workspace, returning exact Lstart-Lend slice hints."""
    res = polyglot_symbol_search(
        query=query,
        workspace=workspace,
        kind=kind,
        limit=limit,
        force_refresh=force_refresh,
    )
    return _compact_json(res)


@polyglot_mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
def polyglot_outline(
    file_subpath: str,
    workspace: str = "",
    include_callers: bool = False,
) -> str:
    """Return a rich Polyglot structural outline (Lstart-Lend spans, line counts, signatures, long-function flags, and 1-liner docstrings/comments) for a single file."""
    res = polyglot_file_outline(
        file_subpath=file_subpath,
        workspace=workspace,
        include_callers=include_callers,
    )
    return _compact_json(res)


def main() -> None:
    if "--self-test" in sys.argv:
        m = polyglot_repo_map(limit=10)
        assert m.get("ok") is True and m.get("matched_files", 0) > 0, f"polyglot_map failed: {m}"
        print("[✓] agy-polyglot-mcp self-test passed.")
        return
    polyglot_mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
