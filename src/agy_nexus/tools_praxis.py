#!/usr/bin/env python3
"""agy_nexus.tools_praxis — Deadbolt-Free Local Antigravity Praxis MCP Server (`agy-praxis-mcp`).

AGY-Praxis is the internal workstation doorway pairing with AGY-Nexus (external Gemini doorway):
1. Incremental SHA-256 Polyglot semantic indexing (`polyglot_map`, `polyglot_search`, `polyglot_outline`).
2. Repo-prefixed staged handoff pass-off inbox & claiming (`praxis_handoff_inbox`, `praxis_claim_handoff`, `praxis_update_handoff`).
"""
from __future__ import annotations

import sys

from fastmcp import FastMCP

import agy_nexus.config as cfg
from agy_nexus.config import HANDOFF_ANNOTATIONS, READONLY_ANNOTATIONS, _compact_json
from agy_nexus.handoff import _unwrap_staged_handoff_markdown
from agy_nexus.handoff_queue import (
    claim_handoff_for_ide,
    list_handoff_tickets,
    mark_ticket_status,
)
from agy_nexus.polyglot_index import (
    polyglot_file_outline,
    polyglot_repo_map,
    polyglot_symbol_search,
)

praxis_mcp = FastMCP(
    name="agy-praxis-mcp",
    instructions=(
        "AGY-PRAXIS-MCP — Local Antigravity IDE Execution Doorway (Semantic Codebase Index + Gemini Handoff Inbox).\n"
        "- Codebase Navigation: Call `polyglot_map`, `polyglot_search`, and `polyglot_outline` first to read incremental SHA-256 cached Lstart-Lend symbol spans before viewing full files.\n"
        "- Staged Gemini Handoffs: When the user says 'Run staged handoff', 'Run <repo>-01', or asks what handoffs are queued from Gemini, call `praxis_handoff_inbox(workspace=...)` or `praxis_claim_handoff(handoff_id=..., workspace=..., conversation_id=...)`.\n"
        "  - If `praxis_claim_handoff` returns `AMBIGUOUS_MULTIPLE_STAGED`, present the returned candidates to the user so they can pick which `<repo>-NN` ticket to execute.\n"
        "  - Once execution finishes, call `praxis_update_handoff(handoff_id=..., status='COMPLETED')`."
    ),
)


@praxis_mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
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


@praxis_mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
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


@praxis_mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
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


@praxis_mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
def praxis_handoff_inbox(
    workspace: str = "",
    status_filter: str = "ALL",
    include_superseded: bool = True,
    limit: int = 25,
) -> str:
    """List repo-prefixed Gemini handoffs (`<repo-slug>-01`, `<repo-slug>-02`, ...) across `STAGED` (unclaimed), `IN_WORK`, and `SUPERSEDED` states, prioritizing the active workspace."""
    res = list_handoff_tickets(
        cfg.AGY_BG_DIR,
        workspace=workspace,
        status_filter=status_filter,
        include_superseded=include_superseded,
        limit=limit,
    )
    return _compact_json(res)


@praxis_mcp.tool(annotations=HANDOFF_ANNOTATIONS, output_schema=None)
def praxis_claim_handoff(
    handoff_id: str = "",
    workspace: str = "",
    conversation_id: str = "",
    force: bool = False,
) -> str:
    """Claim a staged Gemini handoff (`<repo-slug>-NN`) for execution in Antigravity IDE, transitioning it from `STAGED` (unclaimed) to `IN_WORK` and binding `conversation_id`.

    - Pass `handoff_id` (e.g., `'quiet-ui-skills-01'`) to claim a specific ticket directly.
    - Omit `handoff_id` and pass `workspace` (your Active Workspace path) to auto-claim when only 1 unclaimed `STAGED` ticket exists for that repository; if 2+ unclaimed tickets exist, returns `AMBIGUOUS_MULTIPLE_STAGED` with candidates so you can ask the user which one to run.
    """
    res = claim_handoff_for_ide(
        cfg.AGY_BG_DIR,
        cfg.AGY_BRAIN_DIR,
        handoff_id=handoff_id,
        workspace=workspace,
        conversation_id=conversation_id,
        force=force,
    )
    if res.get("ok") and "markdown" in res:
        clean_md = _unwrap_staged_handoff_markdown(str(res.get("markdown") or ""))
        res["clean_specification"] = clean_md
        res["specification_markdown"] = clean_md
    return _compact_json(res)


@praxis_mcp.tool(annotations=HANDOFF_ANNOTATIONS, output_schema=None)
def praxis_update_handoff(
    handoff_id: str,
    status: str = "COMPLETED",
    conversation_id: str = "",
    notes: str = "",
) -> str:
    """Update a handoff ticket's lifecycle state (`COMPLETED`, `IN_WORK`, `STAGED` to release back to unclaimed, or `SUPERSEDED`)."""
    updated = mark_ticket_status(
        cfg.AGY_BG_DIR,
        handoff_id=handoff_id,
        new_status=status,
        conversation_id=conversation_id,
        claim_method="praxis_ide",
        notes=notes,
    )
    if not updated:
        return _compact_json({"ok": False, "error": f"Could not update handoff '{handoff_id}' to '{status}'."})
    return _compact_json({"ok": True, "ticket": updated})


def main() -> None:
    if "--self-test" in sys.argv:
        m = polyglot_repo_map(limit=10)
        assert m.get("ok") is True and m.get("matched_files", 0) > 0, f"polyglot_map failed: {m}"
        print("[✓] agy-praxis-mcp self-test passed.")
        return
    praxis_mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
