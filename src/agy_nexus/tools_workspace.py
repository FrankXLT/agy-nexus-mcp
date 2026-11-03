#!/usr/bin/env python3
"""agy_nexus.tools_workspace — Read-Only Workspace Explorer & Git Diff/Drift Tools."""
from __future__ import annotations
import os
from pathlib import Path
import re
import subprocess
from typing import Any
from agy_nexus.config import (
    AGY_BRAIN_DIR,
    AGY_DATA_DIR,
    AGY_GITLAB_DIR,
    LOCKED_RESPONSE,
    READONLY_ANNOTATIONS,
    SESSION_STATE,
    _compact_json,
    is_unlocked,
    mcp,
)
from agy_nexus.hygiene import MAX_DIFF_CHARS, MAX_FILE_CHARS, MAX_TOTAL_FILE_CHARS, slice_git_diff
from agy_nexus.search import _get_configured_mcp_servers, _search_workspaces_and_history
from agy_nexus.sessions import _get_selected_session_quick_status
from agy_nexus.workflows import inspect_multi_repo_drift
from agy_nexus.workspace import _host_git_inspect, _resolve_and_read_files, _resolve_workspace_str

@mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)

def ask_workspace_readonly(
    question: str,
    search_query: str = "",
    file_subpath: str = "",
    start_line: int = 0,
    end_line: int = 0,
    spoken_passphrase: str = "",
) -> str:
    """Read-only codebase explorer querying one or up to 12 comma-separated files in full (up to 48 KB per file / 120 KB total per call; also supports line ranges via start_line/end_line or inline 'path/file.py:100-350' / 'path/file.py:420' syntax, plus 'skill:<name>' / 'agent:<name>' / 'rule:<name>'), git grep across local repositories, and SQLite FTS5 conversation history."""
    if not is_unlocked(spoken_passphrase):
        return LOCKED_RESPONSE
    ws_str = SESSION_STATE.get("selected_workspace") or str(AGY_GITLAB_DIR)
    ws = Path(ws_str)
    if not ws.is_dir() and not (AGY_DATA_DIR / "worktrees" / ws.name).is_dir():
        ws = AGY_GITLAB_DIR
    conv_id = SESSION_STATE.get("selected_session", "")
    session_dir = (AGY_BRAIN_DIR / conv_id) if conv_id else None
    file_result = _resolve_and_read_files(
        file_subpath,
        ws=ws,
        session_dir=session_dir,
        max_chars_per_file=MAX_FILE_CHARS,
        max_total_chars=MAX_TOTAL_FILE_CHARS,
        start_line=start_line,
        end_line=end_line,
    )
    effective_query = search_query.strip()
    if not effective_query and not file_subpath.strip() and question.strip():
        # Extract meaningful keywords only when no explicit file_subpath was requested
        words = [w for w in re.findall(r"[A-Za-z0-9_-]{4,}", question) if w.lower() not in {"find", "existing", "project", "current", "what", "where", "with", "from", "that", "this", "read", "check", "audit"}]
        if words:
            effective_query = words[0]
    search_bundle = (
        _search_workspaces_and_history(effective_query, primary_ws=ws if ws.is_dir() else None)
        if effective_query
        else {
            "configured_mcp_servers": _get_configured_mcp_servers(),
            "available_repositories": [],
            "code_search_matches": [],
            "historical_session_matches": [],
        }
    )
    out_ws: dict[str, Any] = {
        "ok": True,
        "question": question,
        "workspace": str(ws),
        "assistant_guidance": (
            "Workspace query complete. If you identified additional files to inspect (or if a >1,000-line file has truncated=True and you need its remaining lines), "
            "call ask_workspace_readonly again immediately in this turn (batching comma-separated file_subpath='f1,f2,f3')—NEVER stop mid-task to ask the user whether you should read another file or section."
        ),
        "selected_session_status": _get_selected_session_quick_status(),
        "file_details": file_result,
        "code_search_matches": search_bundle["code_search_matches"],
        "historical_session_matches": search_bundle["historical_session_matches"],
    }
    if not file_subpath.strip():
        out_ws["configured_mcp_servers"] = search_bundle["configured_mcp_servers"]
        out_ws["available_repositories"] = search_bundle["available_repositories"]
    return _compact_json(out_ws)

@mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)

def inspect_git_diff(
    target_branch: str = "HEAD",
    include_untracked: bool = True,
    workspace_override: str = "",
    file_path: str = "",
    offset_chars: int = 0,
    start_line: int = 0,
    end_line: int = 0,
    spoken_passphrase: str = "",
) -> str:
    """Inspect active git status, untracked files, and branch diffs across the target repository (or pass workspace_override='ALL' / comma-separated repo names for a 1-turn multi-repo drift audit). Supports filtering to a specific file_path (e.g. 'src/worker.ts') and paging through large diffs via offset_chars or start_line/end_line."""
    if not is_unlocked(spoken_passphrase):
        return LOCKED_RESPONSE
    raw_override = workspace_override.strip()
    if raw_override.upper() in ("ALL", "*", "ALL_REPOS") or "," in raw_override or ";" in raw_override:
        drift_bundle = inspect_multi_repo_drift(
            gitlab_dir=AGY_GITLAB_DIR,
            data_dir=AGY_DATA_DIR,
            workspace_override=raw_override,
            include_untracked=include_untracked,
        )
        return _compact_json({
            "assistant_guidance": (
                "STOP AND REPLY TO USER NOW: Multi-repository drift audit completed in a single turn. "
                "Do NOT chain a second tool call in this turn."
            ),
            "selected_session_status": _get_selected_session_quick_status(),
            **drift_bundle,
        })
    ws_str = _resolve_workspace_str(raw_override)
    ws = Path(ws_str)
    if ws == AGY_GITLAB_DIR or ws_str == str(AGY_GITLAB_DIR):
        ws = (AGY_GITLAB_DIR / "antigravity-config").resolve()
        ws_str = str(ws)
    safe_branch = re.sub(r"[^a-zA-Z0-9_./~^-]", "", target_branch.strip()).lstrip("-") or "HEAD"
    safe_file_path = ""
    if file_path.strip():
        norm_fp = os.path.normpath(file_path.strip()).lstrip("/")
        if not norm_fp.startswith(".."):
            safe_file_path = norm_fp
    configured_mcps = _get_configured_mcp_servers()
    allowed_local_roots = (AGY_GITLAB_DIR.resolve(), (AGY_DATA_DIR / "worktrees").resolve())
    if ws.is_dir():
        ws_res = ws.resolve()
        if any(ws_res.is_relative_to(r) for r in allowed_local_roots):
            try:
                branch_proc = subprocess.run(
                    ["git", "-c", "safe.directory=*", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=str(ws_res), capture_output=True, text=True, timeout=5, check=False
                )
                if branch_proc.returncode == 0:
                    current_branch = branch_proc.stdout.strip()
                    status_proc = subprocess.run(
                        ["git", "-c", "safe.directory=*", "status", "--short"],
                        cwd=str(ws_res), capture_output=True, text=True, timeout=5, check=False
                    )
                    stat_proc = subprocess.run(
                        ["git", "-c", "safe.directory=*", "diff", "--stat", safe_branch, "--"],
                        cwd=str(ws_res), capture_output=True, text=True, timeout=5, check=False
                    )
                    if stat_proc.returncode != 0 and safe_branch != "HEAD":
                        safe_branch = "HEAD"
                        stat_proc = subprocess.run(
                            ["git", "-c", "safe.directory=*", "diff", "--stat", "HEAD", "--"],
                            cwd=str(ws_res), capture_output=True, text=True, timeout=5, check=False
                        )
                    untracked_files: list[str] = []
                    if include_untracked:
                        untracked_proc = subprocess.run(
                            ["git", "-c", "safe.directory=*", "ls-files", "--others", "--exclude-standard"],
                            cwd=str(ws_res), capture_output=True, text=True, timeout=5, check=False
                        )
                        untracked_files = [l.strip() for l in untracked_proc.stdout.splitlines() if l.strip()][:120]
                    diff_cmd = ["git", "-c", "safe.directory=*", "diff", safe_branch, "--"]
                    if safe_file_path:
                        diff_cmd.append(safe_file_path)
                    diff_proc = subprocess.run(
                        diff_cmd,
                        cwd=str(ws_res), capture_output=True, text=True, timeout=10, check=False
                    )
                    diff_meta = slice_git_diff(
                        diff_out=diff_proc.stdout,
                        offset_chars=offset_chars,
                        max_diff_chars=MAX_DIFF_CHARS,
                        file_path=safe_file_path,
                        start_line=start_line,
                        end_line=end_line,
                    )
                    return _compact_json({
                        "ok": True,
                        "workspace": str(ws_res),
                        "assistant_guidance": (
                            "Git diff inspection complete. If you need to inspect any modified or untracked files in full, "
                            "call ask_workspace_readonly immediately (batching comma-separated file_subpath) before replying."
                        ),
                        "selected_session_status": _get_selected_session_quick_status(),
                        "configured_mcp_servers": configured_mcps,
                        "branch": current_branch,
                        "current_branch": current_branch,
                        "status_short": status_proc.stdout.strip(),
                        "diff_stat": stat_proc.stdout.strip(),
                        "untracked_files": untracked_files,
                        "target_branch": safe_branch,
                        **diff_meta,
                    })
            except Exception:
                pass
    # Fallback to host git-inspect for host-backed repositories/worktrees
    host_res = _host_git_inspect(
        ws_str,
        target_branch=safe_branch,
        include_untracked=include_untracked,
        summary_only=False,
        file_path=safe_file_path,
    )
    if host_res:
        br = host_res.get("branch") or host_res.get("current_branch", "")
        diff_meta = slice_git_diff(
            diff_out=str(host_res.get("diff", "")),
            offset_chars=offset_chars,
            max_diff_chars=MAX_DIFF_CHARS,
            file_path=safe_file_path,
            start_line=start_line,
            end_line=end_line,
        )
        return _compact_json({
            "ok": True,
            "workspace": host_res.get("workspace", ws_str),
            "assistant_guidance": (
                "Git diff inspection complete. If you need to inspect any modified or untracked files in full, "
                "call ask_workspace_readonly immediately (batching comma-separated file_subpath) before replying."
            ),
            "selected_session_status": _get_selected_session_quick_status(),
            "configured_mcp_servers": configured_mcps,
            "branch": br,
            "current_branch": br,
            "status_short": host_res.get("status_short", ""),
            "diff_stat": host_res.get("diff_stat", ""),
            "untracked_files": host_res.get("untracked_files", []),
            "target_branch": safe_branch,
            **diff_meta,
        })
    return _compact_json({"ok": False, "error": f"Unable to inspect git repository for workspace '{ws_str}'."})
