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
from agy_nexus.handoff_queue import resolve_session_from_handoff_id, slugify_token
from agy_nexus.sessions import (
    NEXUS_TITLE_KEYWORDS,
    _list_saved_sessions_internal,
    _load_projects_map,
)
from agy_nexus.workspace import _resolve_workspace_str, normalize_pillar_target_path

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
    all_paths = [p for p in ([ws.lower().rstrip("/")] + [str(u).lower().rstrip("/") for u in uris if u]) if p]
    for p in all_paths:
        if p.endswith("/" + rh) or f"/{rh}/" in p:
            return True
    if rh in ("agy-nexus-mcp", "ag-bridge-mcp") and any(
        p.endswith("/antigravity-config") or "/antigravity-config/" in p for p in all_paths
    ) and any(k in title for k in NEXUS_TITLE_KEYWORDS):
        return True
    umb_lower = {str(u).lower().rstrip("/") for u in cfg.get_umbrella_roots()}
    if any(p not in umb_lower for p in all_paths):
        return False
    if rh in ("antigravity-config", "agy-nexus-mcp", "ag-bridge-mcp") and any(k in title for k in NEXUS_TITLE_KEYWORDS):
        return True
    for pinfo in _load_projects_map().values():
        pname = str(pinfo.get("name") or "").lower()
        p_paths = [str(x).lower().rstrip("/") for x in (pinfo.get("workspace_paths") or [])]
        if any(pp.endswith("/" + rh) or f"/{rh}/" in pp for pp in p_paths) and pname and (pname == title or f"[{pname}]" in title):
            return True
    return bool(re.search(rf"\[{re.escape(rh)}\]", title, re.I)) or title.startswith(f"{rh}:") or slugify_token(title, "", 36) == rh

def _extract_handoff_repo_hint(
    workspace_path: str,
    project_name: str,
    session_title: str,
    activate_skills: str,
    research_markdown: str,
) -> str:
    """Extract target repository slug from explicit arguments, pillar paths, or title/target headers without skill-keyword hijacking."""
    del activate_skills  # Never infer target repo from activated global skill names
    umb_abs = {Path(u).resolve() for u in cfg.get_umbrella_roots()}
    for explicit in (workspace_path, project_name):
        clean_exp = re.sub(r"^file://", "", (explicit or "").strip()).rstrip("/")
        if not clean_exp:
            continue
        resolved = _resolve_workspace_str(clean_exp)
        if resolved and Path(resolved).is_dir() and Path(resolved).resolve() not in umb_abs:
            return Path(resolved).name.lower()
        _, norm_slug, _ = normalize_pillar_target_path(clean_exp)
        if norm_slug:
            return slugify_token(norm_slug, "", 36)
        leaf = Path(clean_exp).name if "/" in clean_exp else clean_exp
        tok = slugify_token(leaf, "", 36)
        if tok:
            return tok

    md = f"{session_title or ''}\n{research_markdown or ''}"
    file_ext_re = re.compile(r"\.(?:md|py|js|ts|tsx|jsx|json|ya?ml|toml|sql|sh|html|css|txt|env|lock|ini|cfg|xml|csv)$", re.I)
    for host_dir in cfg.get_workspace_pillar_roots():
        m_repo = re.search(rf"{re.escape(str(host_dir))}/([a-zA-Z0-9._-]+)", md)
        if m_repo and not file_ext_re.search(m_repo.group(1)):
            return m_repo.group(1).lower()
    for base_dir in {cfg.AGY_WORKSPACE_DIR, Path.home(), cfg.AGY_WORKSPACE_DIR.parent}:
        b_str = str(base_dir).rstrip("/")
        if b_str and b_str != "/":
            m_ws = re.search(rf"{re.escape(b_str)}/(?:projects|workbooks|configuration)/([a-zA-Z0-9._-]+)", md)
            if m_ws and not file_ext_re.search(m_ws.group(1)):
                return m_ws.group(1).lower()
    m_rel = re.search(
        r"(?:(?:Target\s+(?:Workspace|Repo|Project)|Workspace|Repository|Directory)\s*[:=-]\s*[`'\"\s]*|(?:init|initialize|create|bootstrap)\s+(?:repo(?:sitory)?\s+|project\s+|workspace\s+)?[`'\"\s]*)(?:projects|workbooks|configuration)/([a-zA-Z0-9_-]+)(?![a-zA-Z0-9_./-])",
        md[:1500],
        re.I,
    )
    if m_rel:
        return m_rel.group(1).lower()
    for m_cand in re.finditer(r"(?:^|[\s`'\"(])(projects|workbooks|configuration)/([a-zA-Z0-9_-]+)(?=$|[\s`'\")/])", md, re.M):
        p_dir = getattr(cfg, f"AGY_{m_cand.group(1).upper()}_DIR", None)
        if isinstance(p_dir, Path) and (p_dir / m_cand.group(2)).is_dir():
            return m_cand.group(2).lower()

    target_hdrs = "\n".join(
        m.group(1)
        for m in re.finditer(r"(?:Target\s+(?:Workspace|Repo|Project)|Repository|Workspace)\s*[:=-]\s*([^\n]+)", md, re.I)
    )
    first_heading = ""
    for ln in (research_markdown or "").splitlines():
        if ln.strip().startswith("#"):
            first_heading = ln.strip()
            break
    header_zone = f"{session_title or ''}\n{first_heading}\n{target_hdrs}"
    if "sidecars/ag-bridge-mcp" in header_zone.lower():
        sidecar_dir = get_antigravity_config_repo() / "sidecars" / "ag-bridge-mcp"
        return "agy-nexus-mcp" if sidecar_dir.is_symlink() else "antigravity-config"

    known_repos: list[str] = ["agy-nexus-mcp", "antigravity-config"]
    for host_dir in cfg.get_workspace_pillar_roots():
        if host_dir.is_dir():
            known_repos.extend(d.name.lower() for d in host_dir.iterdir() if d.is_dir() and not d.name.startswith("."))
    wt_root = cfg.AGY_DATA_DIR / "worktrees"
    if wt_root.is_dir():
        known_repos.extend(d.name.lower() for d in wt_root.iterdir() if d.is_dir() and not d.name.startswith("."))
    for known_repo in dict.fromkeys(known_repos):
        if len(known_repo) >= 3 and re.search(rf"\b{re.escape(known_repo)}\b", header_zone, re.I):
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
