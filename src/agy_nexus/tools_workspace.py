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
    AGY_PROJECTS_DIR,
    AGY_WORKSPACE_DIR,
    LOCKED_RESPONSE,
    READONLY_ANNOTATIONS,
    REPLY_PROMPT_GUIDANCE,
    SESSION_STATE,
    _compact_json,
    _save_session_state,
    get_antigravity_config_repo,
    get_umbrella_roots,
    get_workspace_pillar_roots,
    is_unlocked,
    mcp,
    pin_session_context,
)
from agy_nexus.hygiene import MAX_DIFF_CHARS, MAX_FILE_CHARS, MAX_TOTAL_FILE_CHARS, compact_payload_to_wire_budget, resolve_source_repo_root, slice_git_diff
from agy_nexus.routing import _resolve_session_identifier, _session_matches_workspace
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
        ws_str = SESSION_STATE.get("selected_workspace") or str(AGY_PROJECTS_DIR if AGY_PROJECTS_DIR.is_dir() else AGY_GITLAB_DIR)
    ws = Path(ws_str)
    if not ws.is_dir() and not (AGY_DATA_DIR / "worktrees" / ws.name).is_dir():
        ws = AGY_PROJECTS_DIR if AGY_PROJECTS_DIR.is_dir() else AGY_GITLAB_DIR
    if workspace.strip() and not session_identifier.strip() and conv_id:
        if not _session_matches_workspace(conv_id, ws):
            conv_id = ""
            extra_uris = []
    if is_pinned_call:
        SESSION_STATE["pinned_calls"] = int(SESSION_STATE.get("pinned_calls") or 0) + 1
        if conv_id:
            pin_session_context(conv_id, workspace=str(ws), workspace_uris=extra_uris, mode="PINNED (READ-ONLY)", last_tool=tool_name, set_default=not bool(SESSION_STATE.get("selected_session")))
        else:
            _save_session_state()
    elif conv_id:
        pin_session_context(conv_id, workspace=str(ws), workspace_uris=extra_uris, last_tool=tool_name, set_default=False)
    return conv_id, ws, extra_uris

def _derive_auto_subpath(raw_sub: str, search_bundle: dict[str, Any]) -> str:
    if raw_sub:
        return raw_sub
    if search_bundle.get("code_search_matches"):
        auto_specs: list[str] = []
        seen_files: set[str] = set()
        for m_str in search_bundle["code_search_matches"]:
            m_hit = re.match(r"^(\[[^\]]+\]\s*([^:]+)):(\d+):", str(m_str))
            if m_hit and m_hit.group(1).strip() not in seen_files:
                file_key = m_hit.group(1).strip()
                seen_files.add(file_key)
                auto_specs.append(f"{file_key}:{m_hit.group(3)}")
                if len(auto_specs) >= 4:
                    break
        if auto_specs:
            return ",".join(auto_specs)
    if search_bundle.get("polyglot_symbol_matches"):
        return ",".join(m["slice_hint"] for m in search_bundle["polyglot_symbol_matches"][:3] if m.get("slice_hint"))
    return raw_sub


@mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
def ask_workspace_readonly(
    question: str, search_query: str = "", file_subpath: str = "", start_line: int = 0,
    end_line: int = 0, session_identifier: str = "", workspace: str = "", spoken_passphrase: str = "",
) -> Any:
    """Read 1..12 CSV files/URIs (file:10-90, outline:file, polyglot:map|search:<q>, workflow:baseline, transcript:latest, brain:*, telemetry:stats, image:#01@top, skill|agent|rule:<name>), git grep & FTS5."""
    if not is_unlocked(spoken_passphrase):
        return LOCKED_RESPONSE
    raw_sub = file_subpath.strip()
    if re.match(r"^(?:image|visual):", raw_sub, flags=re.IGNORECASE):
        from agy_nexus.tools_media import inspect_visual_artifacts
        spec = re.sub(r"^(?:image|visual):", "", raw_sub, flags=re.IGNORECASE).strip()
        spec, reg = [p.strip() for p in spec.rsplit("@", 1)] if "@" in spec else (spec, "full")
        return inspect_visual_artifacts(targets=spec, session_identifier=session_identifier, region=reg or "full", workspace=workspace, spoken_passphrase=spoken_passphrase)
    conv_id, ws, extra_uris = _resolve_pinned_context(session_identifier, workspace, tool_name="ask_workspace_readonly")
    effective_query = search_query.strip()
    if not effective_query and not raw_sub and question.strip():
        words = [w for w in re.findall(r"[A-Za-z0-9_-]{4,}", question) if w.lower() not in {"find", "existing", "project", "current", "what", "where", "with", "from", "that", "this", "read", "check", "audit"}]
        effective_query = words[0] if words else ""
    search_bundle = _search_workspaces_and_history(effective_query, primary_ws=ws if ws.is_dir() else None, conv_id=conv_id, workspace_pinned=bool(workspace.strip())) if effective_query else {
        "configured_mcp_servers": [] if raw_sub else _get_configured_mcp_servers(),
        "available_repositories": [], "pinned_session_matches": [], "polyglot_symbol_matches": [], "code_search_matches": [], "historical_session_matches": [],
    }
    file_result = _resolve_and_read_files(
        _derive_auto_subpath(raw_sub, search_bundle), ws=ws, session_dir=(AGY_BRAIN_DIR / conv_id) if conv_id else None,
        max_chars_per_file=MAX_FILE_CHARS, max_total_chars=MAX_TOTAL_FILE_CHARS,
        start_line=start_line, end_line=end_line, extra_workspace_uris=extra_uris,
    )
    auto_ws = str(file_result.get("auto_resolved_workspace") or "") if isinstance(file_result, dict) else ""
    out_ws: dict[str, Any] = {
        "ok": True, "question": question, "conversation_id": conv_id, "workspace": auto_ws or str(ws),
        "assistant_guidance": (
            "Inspection complete. All requested file details, code search matches, and session status are included below. "
            "You may synthesize your analysis directly, or issue a sequential read-only follow-up call (e.g. paging lines or inspecting git diff, one call at a time, up to 4 sequential hops/turn—never in parallel). "
            "If a tool call fails with permission_denied or an immediate error, you MAY automatically invoke load_session_into_gemini once as a same-turn fallback. "
            + REPLY_PROMPT_GUIDANCE
        ),
        "selected_session_status": _get_selected_session_quick_status(conv_id),
        "file_details": file_result, "code_search_matches": search_bundle["code_search_matches"],
        "historical_session_matches": search_bundle["historical_session_matches"],
    }
    for k in ("pinned_session_matches", "polyglot_symbol_matches"):
        if search_bundle.get(k):
            out_ws[k] = search_bundle[k]
    if auto_ws:
        out_ws["auto_resolved_workspace"] = auto_ws
    if not raw_sub:
        out_ws["configured_mcp_servers"] = search_bundle["configured_mcp_servers"]
        out_ws["available_repositories"] = search_bundle["available_repositories"]
    return compact_payload_to_wire_budget(out_ws, serializer=_compact_json)


def _run_local_git_diff(
    ws: Path, safe_branch: str, safe_file_path: str, include_untracked: bool,
    offset_chars: int, start_line: int, end_line: int, conv_id: str, configured_mcps: Any,
) -> str | None:
    src_repo = resolve_source_repo_root(__file__)
    allowed_roots = [AGY_WORKSPACE_DIR.resolve(), *get_workspace_pillar_roots(), (AGY_DATA_DIR / "worktrees").resolve()]
    if src_repo is not None:
        allowed_roots.append(src_repo)
    if not ws.is_dir():
        return None
    ws_res = ws.resolve()
    if not any(ws_res.is_relative_to(r) for r in allowed_roots):
        return None
    try:
        br_p = subprocess.run(["git", "-c", "safe.directory=*", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(ws_res), capture_output=True, text=True, timeout=5, check=False)
        if br_p.returncode != 0:
            return None
        current_branch = br_p.stdout.strip()
        st_p = subprocess.run(["git", "-c", "safe.directory=*", "status", "--short"], cwd=str(ws_res), capture_output=True, text=True, timeout=5, check=False)
        stat_p = subprocess.run(["git", "-c", "safe.directory=*", "diff", "--stat", safe_branch, "--"], cwd=str(ws_res), capture_output=True, text=True, timeout=5, check=False)
        if stat_p.returncode != 0 and safe_branch != "HEAD":
            safe_branch = "HEAD"
            stat_p = subprocess.run(["git", "-c", "safe.directory=*", "diff", "--stat", "HEAD", "--"], cwd=str(ws_res), capture_output=True, text=True, timeout=5, check=False)
        untracked: list[str] = []
        if include_untracked:
            ut_p = subprocess.run(["git", "-c", "safe.directory=*", "ls-files", "--others", "--exclude-standard"], cwd=str(ws_res), capture_output=True, text=True, timeout=5, check=False)
            untracked = [ln.strip() for ln in ut_p.stdout.splitlines() if ln.strip()][:120]
        diff_cmd = ["git", "-c", "safe.directory=*", "diff", safe_branch, "--"] + ([safe_file_path] if safe_file_path else [])
        diff_p = subprocess.run(diff_cmd, cwd=str(ws_res), capture_output=True, text=True, timeout=10, check=False)
        diff_meta = slice_git_diff(diff_out=diff_p.stdout, offset_chars=offset_chars, max_diff_chars=MAX_DIFF_CHARS, file_path=safe_file_path, start_line=start_line, end_line=end_line)
        return compact_payload_to_wire_budget({
            "ok": True, "workspace": str(ws_res),
            "assistant_guidance": f"Git diff retrieved. Synthesize your report directly, or issue a sequential read-only follow-up call (one call at a time, never in parallel). {REPLY_PROMPT_GUIDANCE}",
            "selected_session_status": _get_selected_session_quick_status(conv_id), "configured_mcp_servers": configured_mcps,
            "branch": current_branch, "current_branch": current_branch, "status_short": st_p.stdout.strip(),
            "diff_stat": stat_p.stdout.strip(), "untracked_files": untracked, "target_branch": safe_branch, **diff_meta,
        }, serializer=_compact_json)
    except Exception:
        return None


@mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
def inspect_git_diff(
    target_branch: str = "HEAD", include_untracked: bool = True, workspace_override: str = "", file_path: str = "",
    offset_chars: int = 0, start_line: int = 0, end_line: int = 0, session_identifier: str = "", spoken_passphrase: str = "",
) -> str:
    """Inspect repo git status, untracked files & diffs (workspace_override='ALL'|CSV repos for drift, or session_identifier); pages file_path/lines."""
    if not is_unlocked(spoken_passphrase):
        return LOCKED_RESPONSE
    raw_override = workspace_override.strip()
    conv_id = _resolve_session_identifier(session_identifier.strip()) if session_identifier.strip() else str(SESSION_STATE.get("selected_session") or "")
    if raw_override.upper() in ("ALL", "*", "ALL_REPOS") or "," in raw_override or ";" in raw_override:
        drift_bundle = inspect_multi_repo_drift(gitlab_dir=AGY_GITLAB_DIR, data_dir=AGY_DATA_DIR, workspace_override=raw_override, include_untracked=include_untracked)
        return compact_payload_to_wire_budget({
            "assistant_guidance": f"Multi-repository drift audit completed in a single turn (all branch, status, and drift details included below). Synthesize your report directly, or issue a sequential read-only follow-up call (one call at a time, never in parallel). {REPLY_PROMPT_GUIDANCE}",
            "selected_session_status": _get_selected_session_quick_status(conv_id), **drift_bundle,
        }, serializer=_compact_json)
    conv_id, pinned_ws, _ = _resolve_pinned_context(session_identifier, raw_override, tool_name="inspect_git_diff")
    ws_str = str(pinned_ws) if (session_identifier.strip() or raw_override) else _resolve_workspace_str(raw_override)
    ws = Path(ws_str)
    umbrella_roots = get_umbrella_roots()
    if (ws.exists() and ws.resolve() in umbrella_roots) or ws_str in {str(u) for u in umbrella_roots}:
        ws = get_antigravity_config_repo().resolve()
        ws_str = str(ws)
    safe_branch = re.sub(r"[^a-zA-Z0-9_./~^-]", "", target_branch.strip()).lstrip("-") or "HEAD"
    norm_fp = os.path.normpath(file_path.strip()).lstrip("/") if file_path.strip() else ""
    safe_file_path = norm_fp if norm_fp and not norm_fp.startswith("..") else ""
    configured_mcps = _get_configured_mcp_servers()
    local_out = _run_local_git_diff(ws, safe_branch, safe_file_path, include_untracked, offset_chars, start_line, end_line, conv_id, configured_mcps)
    if local_out is not None:
        return local_out
    host_res = _host_git_inspect(ws_str, target_branch=safe_branch, include_untracked=include_untracked, summary_only=False, file_path=safe_file_path)
    if host_res:
        br = host_res.get("branch") or host_res.get("current_branch", "")
        diff_meta = slice_git_diff(diff_out=str(host_res.get("diff", "")), offset_chars=offset_chars, max_diff_chars=MAX_DIFF_CHARS, file_path=safe_file_path, start_line=start_line, end_line=end_line)
        return compact_payload_to_wire_budget({
            "ok": True, "workspace": host_res.get("workspace", ws_str),
            "assistant_guidance": f"Host git inspection complete. Synthesize your report directly, or issue a sequential read-only follow-up call (one call at a time, never in parallel). {REPLY_PROMPT_GUIDANCE}",
            "selected_session_status": _get_selected_session_quick_status(conv_id), "configured_mcp_servers": configured_mcps,
            "branch": br, "current_branch": br, "status_short": host_res.get("status_short", ""), "diff_stat": host_res.get("diff_stat", ""),
            "untracked_files": host_res.get("untracked_files", []), "target_branch": safe_branch, **diff_meta,
        }, serializer=_compact_json)
    return _compact_json({"ok": False, "error": f"Unable to inspect git repository for workspace '{ws_str}'."})
