#!/usr/bin/env python3
"""
agy_nexus.target_resolver — Fail-Closed Workspace/Project Resolution & Greenfield Guardrails.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any
import urllib.request

import agy_nexus.config as cfg
from agy_nexus.config import get_antigravity_config_repo
from agy_nexus.handoff_queue import normalize_repo_slug, slugify_token
from agy_nexus.inventory import evaluate_session_customization_scope
from agy_nexus.routing import _extract_handoff_repo_hint, _resolve_target_session_for_handoff, _session_matches_repo_hint
from agy_nexus.session_status import _get_selected_session_quick_status
from agy_nexus.sessions import _load_projects_map, resolve_canonical_project_for_workspace
from agy_nexus.workspace import _resolve_workspace_str, normalize_pillar_target_path

_DISALLOWED_BRANCH_TOKENS = {"", "head", "none", "null", "true", "false", "auto", "plan", "fast"}


_FILE_EXT_RE = re.compile(r"\.(?:md|py|js|ts|tsx|jsx|json|ya?ml|toml|sql|sh|html|css|txt|env|lock|ini|cfg|xml|csv)$", re.I)


def humanize_repo_slug(slug: str) -> str:
    """Convert a kebab/snake repository slug into a clean Antigravity Project display title."""
    words = [w for w in re.split(r"[-_.\s]+", (slug or "").strip()) if w]
    if not words:
        return "New Project"
    return " ".join(w.upper() if w.lower() in {"ai", "ui", "ux", "mcp", "api", "cli", "db", "os"} else w.capitalize() for w in words)


def _sanitize_branch_name(raw_branch: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_./-]", "", (raw_branch or "").strip()).strip("./-")
    if not cleaned or ".." in cleaned or cleaned.endswith(".lock") or cleaned.lower() in _DISALLOWED_BRANCH_TOKENS:
        return ""
    return cleaned[:64]


def extract_default_branch(default_branch: str, body_clean: str) -> str:
    """Resolve explicit default_branch or detect greenfield branch directive (e.g. 'on branch develop'), defaulting to 'main'."""
    explicit = _sanitize_branch_name(default_branch)
    if explicit:
        return explicit
    head_excerpt = (body_clean or "")[:1500]
    patterns = (
        r"\bon\s+branch\s+[`'\"]?([a-zA-Z0-9_./-]+)[`'\"]?",
        r"\b(?:default|initial|primary)\s+branch\s*(?:is|[:=])?\s*[`'\"]?([a-zA-Z0-9_./-]+)[`'\"]?",
        r"\bgit\s+(?:init\s+-b|checkout\s+-b|switch\s+-c)\s+[`'\"]?([a-zA-Z0-9_./-]+)[`'\"]?",
    )
    for pat in patterns:
        m = re.search(pat, head_excerpt, re.I)
        if m:
            cand = _sanitize_branch_name(m.group(1))
            if cand:
                return cand
    return "main"


def extract_markdown_target_path(body_clean: str) -> str:
    """Extract an explicit 3-pillar workspace target path from handoff markdown without matching ordinary prose filenames or file subpaths."""
    txt = body_clean or ""
    if not txt:
        return ""
    end_bound = r"/?(?=$|[\s`'\"\),;:>\]])"
    for p_root in cfg.get_workspace_pillar_roots():
        p_re = re.escape(str(p_root))
        m_p = re.search(rf"({p_re}/[a-zA-Z0-9._-]+){end_bound}", txt)
        if m_p and not _FILE_EXT_RE.search(m_p.group(1)):
            return m_p.group(1).rstrip("/")
    for base_dir in {cfg.AGY_WORKSPACE_DIR, Path.home(), cfg.AGY_WORKSPACE_DIR.parent}:
        b_str = str(base_dir).rstrip("/")
        if b_str and b_str != "/":
            m_b = re.search(rf"({re.escape(b_str)}/(?:projects|workbooks|configuration)/[a-zA-Z0-9._-]+){end_bound}", txt)
            if m_b and not _FILE_EXT_RE.search(m_b.group(1)):
                return m_b.group(1).rstrip("/")
    m_tilde = re.search(rf"(~/(?:projects|workbooks|configuration)/[a-zA-Z0-9._-]+){end_bound}", txt)
    if m_tilde and not _FILE_EXT_RE.search(m_tilde.group(1)):
        return m_tilde.group(1).rstrip("/")
    m_rel = re.search(
        rf"(?:(?:Target\s+(?:Workspace|Repo|Project)|Workspace|Repository|Directory)\s*[:=-]\s*[`'\"\s]*|(?:init|initialize|create|bootstrap)\s+(?:repo(?:sitory)?\s+|project\s+|workspace\s+)?[`'\"\s]*)((?:projects|workbooks|configuration)/[a-zA-Z0-9_-]+){end_bound}",
        txt[:1500],
        re.I,
    )
    if m_rel:
        return m_rel.group(1).rstrip("/")
    return ""


def infer_workspace_and_project(
    workspace_path: str,
    project_name: str,
    session_title: str,
    activate_skills: str,
    body_clean: str,
    conv_id: str = "",
) -> tuple[str, str, str, str]:
    """Resolve (eff_workspace_path, eff_project_id, eff_project_name, repo_slug) without cross-project fallback on explicit/inferred targets."""
    raw_ws = (workspace_path or "").strip()
    eff_pname = (project_name or "").strip()
    eff_ws = _resolve_workspace_str(raw_ws) if raw_ws else ""
    eff_pid = ""
    if conv_id:
        quick_st = _get_selected_session_quick_status(conv_id)
        if not eff_ws and not raw_ws and not eff_pname:
            eff_ws = str(quick_st.get("workspace_path") or cfg.SESSION_STATE.get("session_workspace_map", {}).get(conv_id) or "")
        if not raw_ws and not eff_pname:
            eff_pid = str(cfg.SESSION_STATE.get("session_project_map", {}).get(conv_id) or "")

    md_path = extract_markdown_target_path(body_clean) if (not eff_ws and not raw_ws and not conv_id) else ""
    if md_path:
        eff_ws = _resolve_workspace_str(md_path)
        if not eff_pname and eff_ws:
            eff_pname = Path(eff_ws).name

    inferred_hint = _extract_handoff_repo_hint(eff_ws or raw_ws, eff_pname, session_title, activate_skills, body_clean)
    if not eff_ws and inferred_hint:
        cand_ws = _resolve_workspace_str(inferred_hint)
        if cand_ws and Path(cand_ws).is_dir():
            eff_ws = cand_ws

    has_explicit_or_inferred = bool(raw_ws or eff_pname or md_path or inferred_hint)
    if not eff_ws and not has_explicit_or_inferred:
        eff_ws = cfg.SESSION_STATE.get("selected_workspace", "")

    ws_for_lookup = eff_ws if (eff_ws and Path(eff_ws).is_dir()) else ""
    resolved_pid, resolved_pname = resolve_canonical_project_for_workspace(ws_for_lookup, eff_pname or inferred_hint)
    if not eff_pid and resolved_pid:
        eff_pid = resolved_pid
    if resolved_pname and not eff_pname:
        eff_pname = resolved_pname
    repo_slug = normalize_repo_slug(eff_ws, eff_pname, inferred_hint, umbrella_roots=cfg.get_umbrella_roots())
    return eff_ws, eff_pid, eff_pname, repo_slug


def _build_project_not_found_error(
    *,
    repo_slug: str,
    requested_ws: str,
    requested_pname: str,
    suggested_ws: str,
    default_branch: str,
) -> dict[str, Any]:
    proj_map = _load_projects_map()
    available = sorted(
        [
            {"project_id": pid, "name": str(info.get("name") or pid), "workspace_paths": list(info.get("workspace_paths") or [])}
            for pid, info in proj_map.items()
        ],
        key=lambda x: x["name"].lower(),
    )[:25]
    disp_name = requested_pname or humanize_repo_slug(repo_slug)
    return {
        "ok": False,
        "status": "PROJECT_NOT_FOUND",
        "repo_slug": repo_slug,
        "requested_workspace_path": requested_ws,
        "requested_project_name": requested_pname,
        "suggested_workspace_path": suggested_ws,
        "suggested_project_name": disp_name,
        "suggested_default_branch": default_branch,
        "available_projects": available,
        "error": (
            f"Target project/repository '{requested_pname or requested_ws or repo_slug}' does not exist on disk or in Antigravity projects, "
            "and create_new_project=False (fail-closed guardrail prevented silent fallback to another project)."
        ),
        "assistant_guidance": (
            f"Target project `{disp_name}` (`{suggested_ws}`) does not exist yet. "
            f"If this is intentionally a brand-new greenfield repository/project, re-call `send_handoff_and_resume` with "
            f"`create_new_project=True`, `project_name=\"{disp_name}\"`, `workspace_path=\"{suggested_ws}\"`, and `default_branch=\"{default_branch}\"`. "
            "If you meant an existing project, pass one of `available_projects`."
        ),
    }


def resolve_handoff_target(
    *,
    workspace_path: str,
    project_name: str,
    repo_hint: str,
    session_title: str,
    activate_skills: str,
    body_clean: str,
    conv_id: str,
    create_new_project: bool = False,
    default_branch: str = "",
    resume_headless: bool = False,
    customization_edit_scope: str = "none",
    explicit_caller_ws: bool = True,
) -> dict[str, Any]:
    """Resolve and validate handoff workspace/project target with Option 1A fail-closed greenfield guardrail."""
    raw_ws = (workspace_path or "").strip()
    raw_pname = (project_name or "").strip()
    raw_rhint = (repo_hint or "").strip()
    eff_project_arg = raw_pname or raw_rhint
    edit_scope = (customization_edit_scope or "none").strip().lower()
    eff_branch = extract_default_branch(default_branch, body_clean)

    if raw_ws:
        norm_ws, _, _ = normalize_pillar_target_path(raw_ws)
        exp_ws = Path(os.path.expanduser(re.sub(r"^file://", "", raw_ws)))
        is_exact_cfg = edit_scope == "global" and exp_ws.is_absolute() and exp_ws.resolve() == cfg.AGY_CONFIG_DIR.resolve()
        if not norm_ws and not is_exact_cfg and (exp_ws.is_absolute() or any(pt in (".", "..") for pt in raw_ws.split("/")) or "/" in raw_ws):
            return {
                "guard_error": {
                    "ok": False,
                    "status": "OUTSIDE_ALLOWED_ROOTS",
                    "requested_workspace_path": raw_ws,
                    "error": f"Workspace path '{raw_ws}' is outside allowed Antigravity 3-pillar workspace roots.",
                    "assistant_guidance": "Pass a canonical 3-pillar workspace path such as 'projects/<repo-slug>', 'workbooks/<slug>', or 'configuration/<slug>'.",
                }
            }

    md_path = extract_markdown_target_path(body_clean) if (not raw_ws and (create_new_project or not conv_id)) else ""
    eff_ws, eff_pid, eff_pname, repo_slug = infer_workspace_and_project(
        raw_ws, eff_project_arg, session_title, activate_skills, body_clean, conv_id
    )
    inferred_hint = _extract_handoff_repo_hint(raw_ws, eff_project_arg, session_title, activate_skills, body_clean)
    has_target_spec = bool(raw_ws or raw_pname or raw_rhint or md_path or inferred_hint)
    caller_override = bool((raw_ws and explicit_caller_ws) or raw_pname or md_path)
    conv_exists = bool(conv_id and (cfg.AGY_BRAIN_DIR / conv_id).is_dir() and not caller_override)
    target_exists = bool((eff_ws and Path(eff_ws).is_dir()) or eff_pid or conv_exists)

    cand_norm_ws, _, _ = normalize_pillar_target_path(raw_ws or md_path or slugify_token(repo_slug, "new-project", 36))
    suggested_ws = cand_norm_ws or str(cfg.AGY_PROJECTS_DIR / slugify_token(repo_slug, "new-project", 36))

    strict_gate = (
        not target_exists
        and has_target_spec
        and not create_new_project
        and edit_scope != "global"
        and (resume_headless or caller_override)
    )
    if strict_gate:
        return {
            "guard_error": _build_project_not_found_error(
                repo_slug=repo_slug,
                requested_ws=raw_ws or md_path,
                requested_pname=raw_pname or raw_rhint,
                suggested_ws=suggested_ws,
                default_branch=eff_branch,
            )
        }

    force_new_session = False
    if not target_exists and create_new_project:
        eff_ws = suggested_ws
        eff_pid = ""
        eff_pname = raw_pname or (humanize_repo_slug(repo_slug) if repo_slug and repo_slug != "general" else raw_rhint or "New Project")
        repo_slug = normalize_repo_slug(eff_ws, eff_pname, raw_rhint or inferred_hint, umbrella_roots=cfg.get_umbrella_roots())
        force_new_session = True

    return {
        "guard_error": None,
        "eff_ws": eff_ws,
        "eff_pid": eff_pid,
        "eff_pname": eff_pname,
        "repo_slug": repo_slug,
        "target_exists": target_exists,
        "has_target_spec": has_target_spec,
        "default_branch": eff_branch,
        "force_new_session": force_new_session,
    }


def apply_global_scope_isolation(
    *, edit_scope_clean: str, active_ws: str, conv_id: str, create_new_session: bool, create_new_project: bool,
    routing_reason: str, eff_ws: str, eff_pid: str, eff_pname: str, repo_slug: str,
    session_title: str, activate_skills: str, body_clean: str,
) -> tuple[str, bool, bool, str, str, str, str, str, str]:
    """Isolate global config edits to antigravity-config repository session."""
    if edit_scope_clean != "global":
        return conv_id, create_new_session, create_new_project, routing_reason, eff_ws, active_ws, eff_pid, eff_pname, repo_slug
    scope_check = evaluate_session_customization_scope(active_ws, cfg.AGY_CONFIG_DIR, cfg.AGY_GITLAB_DIR)
    if scope_check["is_global_config_session"] or _session_matches_repo_hint(conv_id, "antigravity-config"):
        cfg_repo_str = str(get_antigravity_config_repo())
        cfg_pid, cfg_pname = resolve_canonical_project_for_workspace(cfg_repo_str, "antigravity-config")
        eff_ws = eff_ws or active_ws or cfg_repo_str
        if cfg_pid and (not eff_pid or repo_slug != "antigravity-config"):
            eff_pid = cfg_pid
            eff_pname = cfg_pname or eff_pname or "antigravity-config"
            if Path(eff_ws).resolve() != Path(cfg_repo_str).resolve():
                eff_ws = cfg_repo_str
        return (
            conv_id,
            create_new_session,
            create_new_project,
            routing_reason,
            eff_ws,
            eff_ws,
            eff_pid,
            eff_pname or cfg_pname or "antigravity-config",
            "antigravity-config",
        )
    cfg_repo_str = str(get_antigravity_config_repo())
    cfg_pid, cfg_pname = resolve_canonical_project_for_workspace(cfg_repo_str, "antigravity-config")
    if not create_new_session:
        cfg_conv, cfg_reason = _resolve_target_session_for_handoff("", cfg_repo_str, "antigravity-config", session_title, activate_skills, body_clean)
        if cfg_conv and _session_matches_repo_hint(cfg_conv, "antigravity-config"):
            return cfg_conv, False, False, f"scope_isolation_routed_to_existing_config_session ({cfg_reason})", cfg_repo_str, cfg_repo_str, cfg_pid, (cfg_pname or "antigravity-config"), "antigravity-config"
    return "", True, False, "scope_isolation_new_config_session", cfg_repo_str, cfg_repo_str, cfg_pid, (cfg_pname or "antigravity-config"), "antigravity-config"


_USER_BODY_START = "<!-- BEGIN_USER_HANDOFF_BODY -->"
_USER_BODY_END = "<!-- END_USER_HANDOFF_BODY -->"


def extract_markdown_heading(md_text: str) -> str:
    """Extract the first top-level Markdown heading for default session_title."""
    for ln in (md_text or "").splitlines():
        s = ln.strip()
        if not s or s.startswith("<!--"):
            continue
        m = re.match(r"^#{1,2}\s+(.+)$", s)
        if m:
            cleaned = re.sub(r"[`*_~]+", "", m.group(1)).strip()
            if cleaned:
                return cleaned[:90]
    return ""


def unwrap_staged_handoff_markdown(staged_text: str) -> str:
    """Extract pure user handoff markdown from an already-staged handoff file."""
    txt = (staged_text or "").strip()
    if not txt:
        return ""
    if _USER_BODY_START in txt and _USER_BODY_END in txt:
        i0 = txt.index(_USER_BODY_START) + len(_USER_BODY_START)
        i1 = txt.rindex(_USER_BODY_END)
        if i1 >= i0:
            return txt[i0:i1].strip()
    txt = re.sub(r"^(?:<!--[^\n]*-->\s*\n)+", "", txt).lstrip()
    txt = re.sub(r"^>\s*\[!IMPORTANT\]\s*\n(?:>[^\n]*\n)+\s*", "", txt).lstrip()
    txt = re.sub(r"^## Prior Session Baton[\s\S]*?\n---\s*\n+", "", txt).lstrip()
    txt = re.sub(r"\n---\s*\n+## Mandatory 4-Step Execution Lifecycle[\s\S]*$", "", txt).rstrip()
    txt = re.sub(r"\n### Mandatory Modular Architecture[\s\S]*$", "", txt).rstrip()
    txt = re.sub(r"\n---\s*\n+## Antigravity Skill, Agent Role & Customization Scope Directive[\s\S]*$", "", txt).rstrip()
    return txt.strip()


def post_host_bridge(payload: dict[str, Any]) -> dict[str, Any]:
    """Execute authenticated POST to agy-host-bridge (:8098)."""
    try:
        req = urllib.request.Request(cfg.AGY_HOST_BRIDGE_URL, data=json.dumps(payload).encode("utf-8"), headers=cfg.get_host_bridge_headers(), method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as e:
        return {"ok": False, "error": f"Failed reaching agy-host-bridge at {cfg.AGY_HOST_BRIDGE_URL}: {e}"}


