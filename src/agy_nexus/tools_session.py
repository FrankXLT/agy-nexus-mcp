#!/usr/bin/env python3
"""agy_nexus.tools_session — Deadbolt, Session Discovery & Session Context Loader Tools."""
from __future__ import annotations
import json
from pathlib import Path
import re
import sqlite3
import time
from typing import Any
from agy_nexus.config import (
    AGY_BG_DIR,
    AGY_BRAIN_DIR,
    AGY_CONFIG_DIR,
    AGY_DATA_DIR,
    AGY_DB_FILE,
    AGY_GITLAB_DIR,
    LOCKED_RESPONSE,
    READONLY_ANNOTATIONS,
    SESSION_STATE,
    TTL_SECONDS,
    _clear_selected_session_state,
    _compact_json,
    _save_session_state,
    is_unlocked,
    mcp,
    verify_passphrase,
)
from agy_nexus.hygiene import (
    MAX_FILE_CHARS,
    MAX_TASK_DOC_CHARS,
    MAX_TOTAL_FILE_CHARS,
    MAX_TRANSCRIPT_TURNS,
    MODULAR_HYGIENE_STANDARDS,
    _compact_markdown,
)
from agy_nexus.media import discover_visual_artifacts
from agy_nexus.routing import _resolve_session_identifier
from agy_nexus.search import _search_workspaces_and_history
from agy_nexus.sessions import _list_saved_sessions_internal, _load_projects_map
from agy_nexus.stats import build_nexus_stats_bundle, extract_pending_approval
from agy_nexus.workspace import _collect_git_summary, _resolve_and_read_files
@mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
def unlock_sessions(spoken_passphrase: str, search_query: str = "", style: str = "default") -> str:
    """Verify user spoken passphrase against the deadbolt hash, unlock sessions, return active conversations and projects, and optionally search workspaces/history in a single step."""
    if not verify_passphrase(spoken_passphrase):
        return _compact_json({
            "ok": False, "locked": True,
            "error": "Passphrase verification failed. Deadbolt remains locked."
        })
    now = time.time()
    was_expired = (now - float(SESSION_STATE.get("unlocked_at") or 0.0)) >= TTL_SECONDS
    if was_expired:
        _clear_selected_session_state()
    SESSION_STATE["unlocked_at"] = now
    sessions = _list_saved_sessions_internal(limit=12, status_filter="ALL")
    if sessions and not SESSION_STATE.get("selected_session"):
        top = sessions[0]
        top_id = str(top.get("conversation_id") or "")
        SESSION_STATE["selected_session"] = top_id
        SESSION_STATE["selected_workspace"] = str(top.get("workspace_path") or "")
        SESSION_STATE["selected_workspace_uris"] = SESSION_STATE["session_workspace_uris_map"].get(top_id, [])
        SESSION_STATE["selected_project"] = str(top.get("project_id") or "")
    _save_session_state()
    projects_map = _load_projects_map()
    stats_bundle = build_nexus_stats_bundle(
        data_dir=AGY_DATA_DIR,
        brain_dir=AGY_BRAIN_DIR,
        db_file=AGY_DB_FILE,
        config_dir=AGY_CONFIG_DIR,
        bg_dir=AGY_BG_DIR,
        period="last_90d",
        style=style,
    )
    sel_id = SESSION_STATE.get("selected_session", "")
    payload: dict[str, Any] = {
        "ok": True, "locked": False,
        "message": "Deadbolt unlocked. Session list and live telemetry stats retrieved successfully.",
        "assistant_guidance": (
            "Deadbolt unlocked. If the user asked for stats, display ascii_mobile_report inside a ```text block now. "
            "If the user asked to inspect a session or codebase, proceed directly to load_session_into_gemini or ask_workspace_readonly "
            "(batching needed files via comma-separated file_subpath) without asking for confirmation."
        ),
        "ttl_seconds": TTL_SECONDS, "selected_session": sel_id,
        "selected_session_title": SESSION_STATE["session_title_map"].get(sel_id, ""),
        "ascii_mobile_report": stats_bundle.get("ascii_mobile_report", ""),
        "quota_and_pools": stats_bundle.get("quota_and_pools", {}),
        "available_projects": list(projects_map.values()), "active_sessions_count": len(sessions),
        "sessions": sessions,
    }
    if search_query.strip():
        payload["search_results"] = _search_workspaces_and_history(search_query.strip())
    return _compact_json(payload)
@mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
def lock_bridge() -> str:
    """Manually engage the security deadbolt immediately, clearing active session selections."""
    SESSION_STATE["unlocked_at"] = 0.0
    SESSION_STATE["selected_session"] = ""
    SESSION_STATE["selected_workspace"] = ""
    SESSION_STATE["selected_workspace_uris"] = []
    SESSION_STATE["selected_project"] = ""
    _save_session_state()
    return _compact_json({
        "ok": True, "locked": True,
        "message": "Security Deadbolt engaged. Bridge locked. Passphrase required to re-authenticate."
    })
@mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
def list_saved_sessions(
    limit: int = 15,
    status_filter: str = "ALL",
    include_subagents: bool = False,
    spoken_passphrase: str = "",
) -> str:
    """List recent Antigravity conversations with execution status, project, workspace, step count, and task previews."""
    if not is_unlocked(spoken_passphrase):
        return LOCKED_RESPONSE
    sessions = _list_saved_sessions_internal(
        limit=max(1, min(limit, 30)),
        status_filter=status_filter,
        include_subagents=include_subagents,
    )
    projects_map = _load_projects_map()
    return _compact_json({
        "ok": True,
        "assistant_guidance": (
            "Sessions listed. If the user asked to inspect a specific session or codebase, call load_session_into_gemini "
            "or ask_workspace_readonly directly to gather all needed files before replying."
        ),
        "count": len(sessions), "available_projects": list(projects_map.values()),
        "sessions": sessions,
    })
@mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
def load_session_into_gemini(
    session_identifier: str,
    spoken_passphrase: str = "",
    include_files: str = "",
) -> str:
    """Load complete conversation context in a single call (live execution_status, git_summary, visual_artifacts with 30-min signed /web/media/ links, task.md, implementation_plan.md, walkthrough.md, and recent transcript turns).
    IMPORTANT: Because execution_status and git_summary are already included in this response, DO NOT chain manage_background_run or inspect_git_diff after calling this tool—reply directly to the user!
    """
    if not is_unlocked(spoken_passphrase):
        return LOCKED_RESPONSE
    ident = session_identifier.strip()
    conv_id = _resolve_session_identifier(ident)
    session_dir = AGY_BRAIN_DIR / conv_id if conv_id else AGY_BRAIN_DIR / "__missing__"
    if not conv_id or not session_dir.is_dir():
        return json.dumps({"ok": False, "error": f"Session directory not found for session_identifier '{ident}'."}, indent=2)
    SESSION_STATE["selected_session"] = conv_id
    workspace = SESSION_STATE["session_workspace_map"].get(conv_id, "")
    workspace_uris: list[str] = []
    project_id = SESSION_STATE["session_project_map"].get(conv_id, "")
    db_status_info: dict[str, Any] = {}
    if AGY_DB_FILE.is_file():
        try:
            con = sqlite3.connect(f"file:{AGY_DB_FILE}?mode=ro", uri=True)
            row = con.execute(
                "SELECT workspace_uris, project_id, status, step_count, last_modified_time, not_fully_idle, killed FROM conversation_summaries WHERE conversation_id = ?",
                (conv_id,),
            ).fetchone()
            con.close()
            if row:
                if row[0]:
                    uris = json.loads(row[0])
                    if uris and isinstance(uris, list):
                        workspace_uris = [re.sub(r"^file://", "", str(u)).rstrip("/") for u in uris if u]
                        if not workspace and workspace_uris:
                            workspace = workspace_uris[0]
                if not project_id and row[1]:
                    project_id = str(row[1])
                db_status_info = {
                    "db_status": str(row[2] or "CASCADE_RUN_STATUS_IDLE"),
                    "step_count": int(row[3] or 0),
                    "last_modified": str(row[4] or ""),
                    "is_running": bool(row[5]) or str(row[2] or "") == "CASCADE_RUN_STATUS_RUNNING",
                    "not_fully_idle": bool(row[5]), "killed": bool(row[6]),
                    "summary": (
                        "RUNNING" if (bool(row[5]) or str(row[2] or "") == "CASCADE_RUN_STATUS_RUNNING")
                        else "COMPLETED_AND_IDLE (Antigravity finished; do NOT call manage_background_run)"
                    ),
                }
        except Exception:
            pass
    projects_map = _load_projects_map()
    project_name = projects_map.get(project_id, {}).get("name", project_id)
    if not workspace and project_id in projects_map:
        p_paths = projects_map[project_id].get("workspace_paths", [])
        if p_paths:
            workspace = p_paths[0]
            if not workspace_uris:
                workspace_uris = list(p_paths)
    if not workspace:
        workspace = str(AGY_GITLAB_DIR)
    SESSION_STATE["selected_workspace"] = workspace
    SESSION_STATE["selected_workspace_uris"] = workspace_uris
    SESSION_STATE["selected_project"] = project_id
    _save_session_state()
    has_inc = bool(include_files.strip())
    task_cap, plan_cap, walk_cap, resp_cap, turns_cap = (1800, 1200, 1400, 1000, 3) if has_inc else (3200, 2400, 2800, 2000, 5)
    task_file = session_dir / "task.md"
    task_raw = task_file.read_text(encoding="utf-8", errors="replace") if task_file.is_file() else ""
    task_content = _compact_markdown(task_raw, max_chars=task_cap) if task_raw else ""
    plan_file = session_dir / "implementation_plan.md"
    plan_raw = plan_file.read_text(encoding="utf-8", errors="replace") if plan_file.is_file() else ""
    plan_content = _compact_markdown(plan_raw, max_chars=plan_cap) if plan_raw else ""
    walk_file = session_dir / "walkthrough.md"
    walk_raw = walk_file.read_text(encoding="utf-8", errors="replace") if walk_file.is_file() else ""
    walk_content = _compact_markdown(walk_raw, max_chars=walk_cap) if walk_raw else ""
    scratch_dir = session_dir / "scratch"
    scratch_files = [f.name for f in scratch_dir.iterdir() if f.is_file()][:20] if scratch_dir.is_dir() else []
    transcript_file = session_dir / ".system_generated" / "logs" / "transcript.jsonl"
    recent_turns: list[dict[str, Any]] = []
    latest_assistant_response = ""
    if transcript_file.is_file():
        try:
            lines = transcript_file.read_text(encoding="utf-8", errors="replace").splitlines()
            for line in lines:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    etype = entry.get("type") or entry.get("role") or ""
                    if etype in ("USER_INPUT", "user"):
                        content = str(entry.get("content") or entry.get("text") or "")
                        recent_turns.append({"type": "USER_INPUT", "created_at": entry.get("created_at", ""), "content": content[:500]})
                    elif etype in ("PLANNER_RESPONSE", "assistant", "model"):
                        content = str(entry.get("content") or entry.get("text") or "").strip()
                        thinking = str(entry.get("thinking") or "").strip()
                        tool_calls_raw = entry.get("tool_calls", [])
                        tool_summary: list[str] = []
                        if isinstance(tool_calls_raw, list):
                            for tc in tool_calls_raw[:6]:
                                if isinstance(tc, dict):
                                    tool_summary.append(tc.get("name") or tc.get("toolAction") or "call")
                        if content:
                            latest_assistant_response = content[:resp_cap]
                        if content or thinking or tool_summary:
                            turn_obj: dict[str, Any] = {"type": "PLANNER_RESPONSE", "created_at": entry.get("created_at", "")}
                            if content:
                                turn_obj["content"] = content[:650]
                            elif thinking:
                                turn_obj["thinking_preview"] = thinking[:250]
                            if tool_summary:
                                turn_obj["tool_calls"] = tool_summary
                            recent_turns.append(turn_obj)
                except Exception:
                    continue
            recent_turns = recent_turns[-turns_cap:]
        except Exception as e:
            recent_turns.append({"error": f"Failed reading transcript: {e}"})
    ws_path = Path(workspace) if workspace else AGY_GITLAB_DIR
    git_summary = _collect_git_summary(ws_path)
    pending_app = extract_pending_approval(transcript_file)
    if pending_app:
        db_status_info["pending_approval"] = pending_app
    included_files = (
        _resolve_and_read_files(
            include_files,
            ws=ws_path,
            session_dir=session_dir,
            max_chars_per_file=5500,
            max_total_chars=8000,
        )
        if has_inc
        else {}
    )
    visual_artifacts = discover_visual_artifacts(conv_id, workspace, limit=6)
    payload: dict[str, Any] = {
        "ok": True, "status": "LOADED",
        "conversation_id": conv_id, "project_id": project_id,
        "project_name": project_name, "workspace_path": workspace,
        "assistant_guidance": (
            "Session context loaded in full (execution_status, git_summary, visual_artifacts, task_content, implementation_plan, walkthrough, and recent turns). "
            "If this answers the user's question (or if include_files was already loaded), STOP AND REPLY TO THE USER NOW so Google Gemini's UI does not stall on chained calls."
        ),
        "project_hygiene_standards": MODULAR_HYGIENE_STANDARDS, "execution_status": db_status_info,
        "git_summary": git_summary, "visual_artifacts": visual_artifacts,
        "latest_assistant_response": latest_assistant_response,
        "task_content": task_content, "implementation_plan": plan_content,
        "walkthrough": walk_content, "scratch_files": scratch_files,
        "recent_transcript_turns": recent_turns,
    }
    if included_files:
        payload["included_files"] = included_files
    out_str = _compact_json(payload)
    if len(out_str.encode("utf-8")) > 19000:
        for k_trim, cap_trim in (("walkthrough", 900), ("implementation_plan", 900), ("latest_assistant_response", 900), ("task_content", 1200)):
            if payload.get(k_trim):
                payload[k_trim] = _compact_markdown(str(payload[k_trim]), max_chars=cap_trim)
        payload["recent_transcript_turns"] = recent_turns[-2:]
        out_str = _compact_json(payload)
        if len(out_str.encode("utf-8")) > 19500 and isinstance(payload.get("included_files"), dict):
            inc_files = payload["included_files"].get("files")
            if isinstance(inc_files, dict):
                for fk, fv in inc_files.items():
                    if isinstance(fv, dict) and isinstance(fv.get("content"), str) and len(fv["content"]) > 2500:
                        fv["content"] = fv["content"][:2500]
                        fv["truncated"] = True
            out_str = _compact_json(payload)
    return out_str
