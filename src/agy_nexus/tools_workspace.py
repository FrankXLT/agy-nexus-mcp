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
    _save_session_state,
    is_unlocked,
    mcp,
    pin_session_context,
)
from agy_nexus.ast_outline import build_file_outline
from agy_nexus.hygiene import MAX_DIFF_CHARS, MAX_FILE_CHARS, MAX_TOTAL_FILE_CHARS, slice_git_diff
from agy_nexus.routing import _resolve_session_identifier
from agy_nexus.search import _get_configured_mcp_servers, _search_workspaces_and_history
from agy_nexus.sessions import _get_selected_session_quick_status
from agy_nexus.workflows import inspect_multi_repo_drift
from agy_nexus.workspace import _host_git_inspect, _resolve_and_read_files, _resolve_workspace_str

def _resolve_pinned_context(session_identifier: str = "", workspace: str = "", tool_name: str = "ask_workspace_readonly") -> tuple[str, Path, list[str]]:
    """Resolve isolated (conv_id, ws_path, extra_uris) for a tool call without clobbering global default pointers."""
    conv_id = SESSION_STATE.get("selected_session", "")
    extra_uris = list(SESSION_STATE.get("selected_workspace_uris") or [])
    ws_str = ""
    is_pinned_call = bool(session_identifier.strip() or workspace.strip())
    if session_identifier.strip():
        resolved_cid = _resolve_session_identifier(session_identifier.strip())
        if resolved_cid:
            conv_id = resolved_cid
            slot = (SESSION_STATE.get("active_contexts") or {}).get(conv_id, {})
            ws_str = str(slot.get("workspace") or SESSION_STATE["session_workspace_map"].get(conv_id) or "")
            extra_uris = list(slot.get("workspace_uris") or SESSION_STATE["session_workspace_uris_map"].get(conv_id) or [])
    if workspace.strip():
        ws_str = _resolve_workspace_str(workspace.strip())
    if not ws_str:
        ws_str = SESSION_STATE.get("selected_workspace") or str(AGY_GITLAB_DIR)
    ws = Path(ws_str)
    if not ws.is_dir() and not (AGY_DATA_DIR / "worktrees" / ws.name).is_dir():
        ws = AGY_GITLAB_DIR
    if is_pinned_call:
        SESSION_STATE["pinned_calls"] = int(SESSION_STATE.get("pinned_calls") or 0) + 1
        if conv_id:
            pin_session_context(conv_id, workspace=str(ws), workspace_uris=extra_uris, mode="PINNED (READ-ONLY)", last_tool=tool_name, set_default=not bool(SESSION_STATE.get("selected_session")))
        else:
            _save_session_state()
    elif conv_id:
        pin_session_context(conv_id, workspace=str(ws), workspace_uris=extra_uris, last_tool=tool_name, set_default=False)
    return conv_id, ws, extra_uris

@mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
def ask_workspace_readonly(
    question: str,
    search_query: str = "",
    file_subpath: str = "",
    start_line: int = 0,
    end_line: int = 0,
    session_identifier: str = "",
    workspace: str = "",
    spoken_passphrase: str = "",
) -> str:
    """Read-only codebase explorer and secondary 'Check-in' status reader querying 1..12 comma-separated files (supports line ranges via start_line/end_line or inline 'path/file.py:100-350' syntax, plus 'outline:path/to/file' for 1-call Universal Polyglot structural line-span outlines across Python (.py), Markdown (.md), JSON/JSONC (.json), YAML (.yaml/.yml), and JS/TS/CSS/HTML (.js/.ts/.css/.html) with automatic outlines on truncated file reads, 'skill:<name>' / 'agent:<name>' / 'rule:<name>'), git grep across local repositories, and SQLite FTS5 conversation history. Pass session_identifier or workspace to pin this call in parallel chats without mutating other chats' context.
    NOTE: This tool returns selected_session_status automatically alongside file details, making it safe for live check-ins and fallback queries."""
    if not is_unlocked(spoken_passphrase):
        return LOCKED_RESPONSE
    conv_id, ws, extra_uris = _resolve_pinned_context(session_identifier, workspace, tool_name="ask_workspace_readonly")
    session_dir = (AGY_BRAIN_DIR / conv_id) if conv_id else None
    effective_query = search_query.strip()
    if not effective_query and not file_subpath.strip() and question.strip():
        words = [w for w in re.findall(r"[A-Za-z0-9_-]{4,}", question) if w.lower() not in {"find", "existing", "project", "current", "what", "where", "with", "from", "that", "this", "read", "check", "audit"}]
        if words:
            effective_query = words[0]
    search_bundle = (
        _search_workspaces_and_history(effective_query, primary_ws=ws if ws.is_dir() else None)
        if effective_query
        else {"configured_mcp_servers": _get_configured_mcp_servers(), "available_repositories": [], "code_search_matches": [], "historical_session_matches": []}
    )
    effective_subpath = file_subpath.strip()
    if not effective_subpath and search_bundle["code_search_matches"]:
        auto_specs: list[str] = []
        seen_files: set[str] = set()
        for m_str in search_bundle["code_search_matches"]:
            m_hit = re.match(r"^(\[[^\]]+\]\s*([^:]+)):(\d+):", str(m_str))
            if m_hit:
                file_key = m_hit.group(1).strip()
                if file_key not in seen_files:
                    seen_files.add(file_key)
                    auto_specs.append(f"{file_key}:{m_hit.group(3)}")
                    if len(auto_specs) >= 4:
                        break
        if auto_specs:
            effective_subpath = ",".join(auto_specs)
    file_result = _resolve_and_read_files(
        effective_subpath,
        ws=ws,
        session_dir=session_dir,
        max_chars_per_file=MAX_FILE_CHARS,
        max_total_chars=MAX_TOTAL_FILE_CHARS,
        start_line=start_line,
        end_line=end_line,
        extra_workspace_uris=extra_uris,
    )
    auto_ws = ""
    if isinstance(file_result, dict):
        auto_ws = str(file_result.get("auto_resolved_workspace") or "")
    out_ws: dict[str, Any] = {
        "ok": True,
        "question": question,
        "conversation_id": conv_id,
        "workspace": auto_ws or str(ws),
        "assistant_guidance": (
            "STOP AND REPLY TO USER NOW: Inspection complete. "
            "Do NOT chain a second MCP tool after a successful response (selected_session_status, file_details, and code_search_matches are ALL included below). "
            "However, if a tool call fails with permission_denied or an immediate error, you MAY automatically invoke load_session_into_gemini once as a same-turn fallback without asking the user to reply 'Go'. "
            "Synthesize your analysis or answer the user's question directly."
        ),
        "selected_session_status": _get_selected_session_quick_status(conv_id),
        "file_details": file_result,
        "code_search_matches": search_bundle["code_search_matches"],
        "historical_session_matches": search_bundle["historical_session_matches"],
    }
    if auto_ws:
        out_ws["auto_resolved_workspace"] = auto_ws
    if not file_subpath.strip():
        out_ws["configured_mcp_servers"] = search_bundle["configured_mcp_servers"]
        out_ws["available_repositories"] = search_bundle["available_repositories"]
    out_json = _compact_json(out_ws)
    if len(out_json.encode("utf-8")) > 19200:
        out_ws["historical_session_matches"] = out_ws.get("historical_session_matches", [])[:2]
        out_ws["code_search_matches"] = out_ws.get("code_search_matches", [])[:5]
        out_json = _compact_json(out_ws)
    if len(out_json.encode("utf-8")) > 19200 and isinstance(out_ws.get("file_details"), dict):
        files_arr = out_ws["file_details"].get("files") or ([out_ws["file_details"]] if "path" in out_ws["file_details"] else [])
        while len(out_json.encode("utf-8")) > 19200 and files_arr:
            largest = max(files_arr, key=lambda f: len(str(f.get("content", ""))))
            content_str = str(largest.get("content", ""))
            if len(content_str) <= 800:
                break
            excess = len(out_json.encode("utf-8")) - 18800
            new_len = max(800, len(content_str) - max(excess, 1500))
            largest["content"] = content_str[:new_len] + "\n... [compacted for <20KB wire ceiling — use start_line/end_line for remaining lines]"
            largest["truncated"] = True
            if "ast_outline" not in largest and largest.get("path"):
                try:
                    largest["ast_outline"] = build_file_outline(Path(largest["path"]), max_chars=1200, include_callers=False)
                except Exception:
                    pass
            out_json = _compact_json(out_ws)
    return out_json

@mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
def inspect_git_diff(
    target_branch: str = "HEAD",
    include_untracked: bool = True,
    workspace_override: str = "",
    file_path: str = "",
    offset_chars: int = 0,
    start_line: int = 0,
    end_line: int = 0,
    session_identifier: str = "",
    spoken_passphrase: str = "",
) -> str:
    """Inspect active git status, untracked files, and branch diffs across the target repository (or pass workspace_override='ALL' / comma-separated repo names for a 1-turn multi-repo drift audit, or session_identifier to pin a specific session's repo). Supports filtering to a specific file_path and paging through large diffs."""
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
                "Do NOT chain a second MCP tool after a successful response (all data is already included below). "
                "However, if a tool call fails with permission_denied or an immediate error, you MAY automatically invoke ask_workspace_readonly or load_session_into_gemini once as a same-turn fallback without asking the user to reply 'Go'."
            ),
            "selected_session_status": _get_selected_session_quick_status(),
            **drift_bundle,
        })
    pinned_cid, pinned_ws, _ = _resolve_pinned_context(session_identifier, raw_override, tool_name="inspect_git_diff")
    ws_str = str(pinned_ws) if (session_identifier.strip() or raw_override) else _resolve_workspace_str(raw_override)
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
                    diff_proc = subprocess.run(diff_cmd, cwd=str(ws_res), capture_output=True, text=True, timeout=10, check=False)
                    diff_meta = slice_git_diff(
                        diff_out=diff_proc.stdout, offset_chars=offset_chars, max_diff_chars=MAX_DIFF_CHARS,
                        file_path=safe_file_path, start_line=start_line, end_line=end_line,
                    )
                    return _compact_json({
                        "ok": True, "workspace": str(ws_res),
                        "assistant_guidance": "STOP AND REPLY TO USER NOW: Git diff retrieved. Do NOT chain a second MCP tool after a successful response.",
                        "selected_session_status": _get_selected_session_quick_status(),
                        "configured_mcp_servers": configured_mcps, "branch": current_branch,
                        "current_branch": current_branch, "status_short": status_proc.stdout.strip(),
                        "diff_stat": stat_proc.stdout.strip(), "untracked_files": untracked_files,
                        "target_branch": safe_branch, **diff_meta,
                    })
            except Exception:
                pass
    host_res = _host_git_inspect(ws_str, target_branch=safe_branch, include_untracked=include_untracked, summary_only=False, file_path=safe_file_path)
    if host_res:
        br = host_res.get("branch") or host_res.get("current_branch", "")
        diff_meta = slice_git_diff(
            diff_out=str(host_res.get("diff", "")), offset_chars=offset_chars, max_diff_chars=MAX_DIFF_CHARS,
            file_path=safe_file_path, start_line=start_line, end_line=end_line,
        )
        return _compact_json({
            "ok": True, "workspace": host_res.get("workspace", ws_str),
            "assistant_guidance": "STOP AND REPLY TO USER NOW: Host git inspection complete. Do NOT chain a second MCP tool after a successful response.",
            "selected_session_status": _get_selected_session_quick_status(),
            "configured_mcp_servers": configured_mcps, "branch": br, "current_branch": br,
            "status_short": host_res.get("status_short", ""), "diff_stat": host_res.get("diff_stat", ""),
            "untracked_files": host_res.get("untracked_files", []), "target_branch": safe_branch, **diff_meta,
        })
    return _compact_json({"ok": False, "error": f"Unable to inspect git repository for workspace '{ws_str}'."})
