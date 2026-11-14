#!/usr/bin/env python3
"""
agy_nexus.routing — Deterministic Session Identifier & Cross-Project Handoff Routing.
"""

from __future__ import annotations

from pathlib import Path
import re

from agy_nexus.config import (
    AGY_BRAIN_DIR,
    AGY_DATA_DIR,
    AGY_GITLAB_DIR,
    AGY_WORKSPACE_DIR,
    SESSION_STATE,
    _save_session_state,
    get_antigravity_config_repo,
    get_workspace_pillar_roots,
)
import agy_nexus.config as cfg
from agy_nexus.handoff_queue import resolve_session_from_handoff_id
from agy_nexus.sessions import (
    NEXUS_TITLE_KEYWORDS,
    _list_saved_sessions_internal,
    _load_projects_map,
)
from agy_nexus.workspace import _resolve_workspace_str

def _resolve_session_identifier(ident_raw: str) -> str:
    """Resolve index ('1', '#1', 'latest'), handoff ID ('<repo>-01'), conversation UUID/prefix, title keyword, project name, or workspace URI to a conversation_id."""
    ident = (ident_raw or "").strip()
    if not ident or ident.lower() in ("latest", "current", "active", "recent", "top", "last"):
        ident = "1"
    handoff_conv = resolve_session_from_handoff_id(cfg.AGY_BG_DIR, ident)
    if handoff_conv and (cfg.AGY_BRAIN_DIR / handoff_conv).is_dir():
        return handoff_conv
    ident_num = re.sub(r"^(?:session|index|item|#)\s*", "", ident, flags=re.I).strip()
    conv_id = SESSION_STATE["session_index_map"].get(ident_num) or SESSION_STATE["session_index_map"].get(ident, "")
    if conv_id and (cfg.AGY_BRAIN_DIR / conv_id).is_dir():
        return conv_id

    candidate_id = re.sub(r"[^a-zA-Z0-9_-]", "", ident)
    if candidate_id and len(candidate_id) >= 32 and (cfg.AGY_BRAIN_DIR / candidate_id).is_dir():
        return candidate_id

    sessions = _list_saved_sessions_internal(limit=25, status_filter="ALL", include_subagents=False)
    conv_id = SESSION_STATE["session_index_map"].get(ident_num) or SESSION_STATE["session_index_map"].get(ident, "")
    if conv_id and (cfg.AGY_BRAIN_DIR / conv_id).is_dir():
        return conv_id

    ident_lower = ident.lower()
    for s in sessions:
        sid = str(s.get("conversation_id", ""))
        all_uris = " ".join(str(u) for u in (s.get("workspace_uris") or [])).lower()
        if (
            ident_lower == sid.lower()
            or (len(ident_lower) >= 6 and sid.lower().startswith(ident_lower))
            or ident_lower in str(s.get("title", "")).lower()
            or ident_lower in str(s.get("project_name", "")).lower()
            or ident_lower in str(s.get("workspace_path", "")).lower()
            or ident_lower in all_uris
        ):
            return sid
    return candidate_id if (candidate_id and (cfg.AGY_BRAIN_DIR / candidate_id).is_dir()) else ""

def _session_matches_repo_hint(conv_id: str, repo_hint: str) -> bool:
    """Return True if conv_id's workspace_uris, workspace_path, project mapping, or title matches repo_hint."""
    if not conv_id or not repo_hint:
        return False
    rh = repo_hint.lower().strip("/")
    uris = SESSION_STATE.get("session_workspace_uris_map", {}).get(conv_id) or []
    ws = str(SESSION_STATE.get("session_workspace_map", {}).get(conv_id) or "")
    title = str(SESSION_STATE.get("session_title_map", {}).get(conv_id) or "").lower()
    all_paths = [ws.lower()] + [str(u).lower() for u in uris if u]
    for p in all_paths:
        if p.endswith("/" + rh) or f"/{rh}/" in p:
            return True
    if rh in ("antigravity-config", "agy-nexus-mcp", "ag-bridge-mcp"):
        if any(k in title for k in NEXUS_TITLE_KEYWORDS):
            return True
        if rh in ("agy-nexus-mcp", "ag-bridge-mcp") and any(
            p.endswith("/antigravity-config") or "/antigravity-config/" in p for p in all_paths
        ) and any(k in title for k in NEXUS_TITLE_KEYWORDS):
            return True
    for pinfo in _load_projects_map().values():
        pname = str(pinfo.get("name") or "").lower()
        p_paths = [str(x).lower() for x in (pinfo.get("workspace_paths") or [])]
        if any(pp.endswith("/" + rh) or f"/{rh}/" in pp for pp in p_paths) and pname and pname in title:
            return True
    return len(rh) >= 4 and bool(re.search(rf"\b{re.escape(rh)}\b", title))

def _extract_handoff_repo_hint(
    workspace_path: str,
    project_name: str,
    session_title: str,
    activate_skills: str,
    research_markdown: str,
) -> str:
    """Extract target repository name from handoff parameters, local git directories, or markdown."""
    for explicit in (workspace_path, project_name):
        clean_exp = (explicit or "").strip().rstrip("/")
        if clean_exp:
            resolved = _resolve_workspace_str(clean_exp)
            if resolved:
                return Path(resolved).name.lower()
    md = f"{session_title or ''}\n{activate_skills or ''}\n{research_markdown or ''}"
    for host_dir in get_workspace_pillar_roots():
        host_re = re.escape(str(host_dir))
        m_repo = re.search(rf"{host_re}/([a-zA-Z0-9._-]+)", md)
        if m_repo:
            return m_repo.group(1).lower()
    ws_re = re.escape(str(AGY_WORKSPACE_DIR))
    m_ws_repo = re.search(rf"{ws_re}/(?:projects|workbooks|configuration)/([a-zA-Z0-9._-]+)", md)
    if m_ws_repo:
        return m_ws_repo.group(1).lower()
    if any(k in md.lower() for k in ("quiet-ui-skills", "quiet ui", "quiet-ui", "quiet-ui-diagrams", "visual-architecture-system")):
        return "quiet-ui-skills"
    if any(k in md.lower() for k in ("sidecars/ag-bridge-mcp", "ag_bridge.py", "ag_bridge_stats.py", "agy-nexus-stats", "agy-nexus-mcp", "agy-polyglot-mcp")):
        sidecar_dir = get_antigravity_config_repo() / "sidecars" / "ag-bridge-mcp"
        if sidecar_dir.is_symlink():
            return "agy-nexus-mcp"
        return "antigravity-config"
    known_repos: list[str] = ["agy-nexus-mcp", "antigravity-config"]
    for host_dir in get_workspace_pillar_roots():
        if host_dir.is_dir():
            known_repos.extend(d.name.lower() for d in host_dir.iterdir() if d.is_dir() and not d.name.startswith("."))
    wt_root = AGY_DATA_DIR / "worktrees"
    if wt_root.is_dir():
        known_repos.extend(d.name.lower() for d in wt_root.iterdir() if d.is_dir() and not d.name.startswith("."))
    for known_repo in dict.fromkeys(known_repos):
        if len(known_repo) >= 3 and re.search(rf"\b{re.escape(known_repo)}\b", md, re.I):
            return known_repo
    return ""

def _resolve_target_session_for_handoff(
    session_identifier: str,
    workspace_path: str,
    project_name: str,
    session_title: str,
    activate_skills: str,
    research_markdown: str,
) -> tuple[str, str]:
    """Deterministically resolve the target conversation_id for send_handoff_and_resume and guard against stale cross-project misrouting."""
    ident_clean = (session_identifier or "").strip()
    if ident_clean:
        ident_num = re.sub(r"^(?:session|index|item|#)\s*", "", ident_clean, flags=re.I).strip()
        cached_conv = SESSION_STATE["session_index_map"].get(ident_num) or SESSION_STATE["session_index_map"].get(ident_clean, "")
        if cached_conv and (cfg.AGY_BRAIN_DIR / cached_conv).is_dir():
            SESSION_STATE["selected_session"] = cached_conv
            SESSION_STATE["selected_workspace"] = SESSION_STATE["session_workspace_map"].get(cached_conv, "")
            SESSION_STATE["selected_workspace_uris"] = SESSION_STATE["session_workspace_uris_map"].get(cached_conv, [])
            SESSION_STATE["selected_project"] = SESSION_STATE["session_project_map"].get(cached_conv, "")
            _save_session_state()
            return cached_conv, f"explicit_session_identifier ({ident_clean})"

    sessions = _list_saved_sessions_internal(limit=20, status_filter="ALL", include_subagents=False)

    # 1. Explicit session_identifier always wins
    if ident_clean:
        resolved = _resolve_session_identifier(ident_clean)
        if resolved:
            SESSION_STATE["selected_session"] = resolved
            SESSION_STATE["selected_workspace"] = SESSION_STATE["session_workspace_map"].get(resolved, "")
            SESSION_STATE["selected_workspace_uris"] = SESSION_STATE["session_workspace_uris_map"].get(resolved, [])
            SESSION_STATE["selected_project"] = SESSION_STATE["session_project_map"].get(resolved, "")
            _save_session_state()
            return resolved, f"explicit_session_identifier ({ident_clean})"

    # 2. Check repo/project hint from handoff markdown & arguments against selected_session
    repo_hint = _extract_handoff_repo_hint(workspace_path, project_name, session_title, activate_skills, research_markdown)
    current_conv = SESSION_STATE.get("selected_session", "")

    if repo_hint:
        if current_conv and _session_matches_repo_hint(current_conv, repo_hint):
            return current_conv, f"selected_session_matched_repo ({repo_hint})"
        # Current selected_session is missing or belongs to a DIFFERENT repo (e.g., stale session from another project)!
        for s in sessions:
            sid = str(s.get("conversation_id") or "")
            if _session_matches_repo_hint(sid, repo_hint):
                prev_note = f"overrode mismatched session {current_conv[:8]}" if current_conv else "auto-selected"
                SESSION_STATE["selected_session"] = sid
                SESSION_STATE["selected_workspace"] = SESSION_STATE["session_workspace_map"].get(sid, "")
                SESSION_STATE["selected_workspace_uris"] = SESSION_STATE["session_workspace_uris_map"].get(sid, [])
                SESSION_STATE["selected_project"] = SESSION_STATE["session_project_map"].get(sid, "")
                _save_session_state()
                return sid, f"auto_matched_repo:{repo_hint} ({prev_note})"
        # Brand-new repo with zero matching sessions: do NOT hijack an unrelated session!
        return "", f"new_repo_unclaimed:{repo_hint}"

    # 3. Fallback to current_conv or #1 most recently modified session (only when no repo_hint was specified)
    if current_conv and (cfg.AGY_BRAIN_DIR / current_conv).is_dir():
        return current_conv, "selected_session"
    if sessions:
        top_id = str(sessions[0].get("conversation_id") or "")
        if top_id:
            SESSION_STATE["selected_session"] = top_id
            SESSION_STATE["selected_workspace"] = SESSION_STATE["session_workspace_map"].get(top_id, "")
            SESSION_STATE["selected_workspace_uris"] = SESSION_STATE["session_workspace_uris_map"].get(top_id, [])
            SESSION_STATE["selected_project"] = SESSION_STATE["session_project_map"].get(top_id, "")
            _save_session_state()
            return top_id, "most_recent_session_fallback"
    return "", "none"
