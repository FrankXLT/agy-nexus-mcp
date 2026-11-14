#!/usr/bin/env python3
"""
agy_nexus.session_tree — Project -> Chat -> Session ID Hierarchy, Parallel Context Slots & 76-Column ASCII Tree Renderer.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from typing import Any

from agy_nexus import __version__
import agy_nexus.config as cfg
from agy_nexus.config import AGY_GITLAB_DIR, AGY_PROJECTS_DIR, SESSION_STATE
from agy_nexus.handoff_queue import list_handoff_tickets, slugify_token
from agy_nexus.hygiene import TTL_SECONDS
from agy_nexus.sessions import _list_saved_sessions_internal, _load_projects_map
from agy_nexus.telemetry_scanner import normalize_workspace_name


def _format_relative_age(iso_str: str) -> str:
    """Convert ISO-8601 timestamp string into compact relative age (e.g. '4m ago', '2h ago', '3d ago')."""
    if not iso_str:
        return "recent"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        diff_s = max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))
        if diff_s < 60:
            return f"{diff_s}s ago"
        if diff_s < 3600:
            return f"{diff_s // 60}m ago"
        if diff_s < 86400:
            return f"{diff_s // 3600}h ago"
        return f"{diff_s // 86400}d ago"
    except Exception:
        return iso_str[:10]


def read_backup_321_manifest(bg_dir: Path | None = None) -> dict[str, Any]:
    """Read 3-2-1 Git backup manifest from ~/.local/share/ag-bridge-mcp/backups or AGY_BG_DIR."""
    eff_bg = bg_dir or cfg.AGY_BG_DIR
    candidates = [
        Path(os.getenv("AGY_BACKUP_DIR", str(Path.home() / ".local/share/ag-bridge-mcp/backups"))).expanduser() / "backup_manifest.json",
        eff_bg / "backup_manifest.json",
    ]
    for cand in candidates:
        try:
            if cand.is_file():
                data = json.loads(cand.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    head_sha = str(data.get("head_sha") or "")
                    shas_match = bool(data.get("shas_match", True))
                    size_b = int(data.get("bundle_size_bytes") or 0)
                    ts_utc = str(data.get("timestamp_utc") or "")
                    return {
                        "ok": bool(data.get("ok", True)), "short_sha": head_sha[:7] if head_sha else "unknown",
                        "head_sha": head_sha, "origin_sha": str(data.get("origin_sha") or ""), "gitlab_sha": str(data.get("gitlab_sha") or ""),
                        "shas_match": shas_match, "bundle_size_bytes": size_b, "bundle_size_kb": round(size_b / 1024.0, 1) if size_b else 0.0,
                        "timestamp_utc": ts_utc, "age": _format_relative_age(ts_utc),
                        "status_label": "SYNCED ✓" if shas_match and head_sha else "DRIFT !",
                    }
        except Exception:
            continue
    return {
        "ok": False, "short_sha": "none", "head_sha": "", "origin_sha": "", "gitlab_sha": "",
        "shas_match": False, "bundle_size_bytes": 0, "bundle_size_kb": 0.0, "timestamp_utc": "", "age": "never", "status_label": "UNVERIFIED",
    }


def get_routing_telemetry() -> dict[str, Any]:
    """Return parallel context slot counts, routing counters, and Deadbolt TTL telemetry."""
    now = time.time()
    unlocked_at = float(SESSION_STATE.get("unlocked_at") or 0.0)
    ttl_rem = max(0, int(TTL_SECONDS - (now - unlocked_at))) if unlocked_at > 0 else 0
    raw_contexts = SESSION_STATE.get("active_contexts") or {}
    slots_list = sorted(
        (v for v in raw_contexts.values() if isinstance(v, dict) and v.get("conversation_id")),
        key=lambda x: float(x.get("last_used_at") or 0.0),
        reverse=True,
    )
    return {
        "active_slots": len(slots_list),
        "pinned_calls": int(SESSION_STATE.get("pinned_calls") or 0),
        "auto_resolved_calls": int(SESSION_STATE.get("auto_resolved_calls") or 0),
        "selected_session": str(SESSION_STATE.get("selected_session") or ""),
        "selected_workspace": str(SESSION_STATE.get("selected_workspace") or ""),
        "ttl_remaining_seconds": ttl_rem,
        "ttl_remaining_min": round(ttl_rem / 60.0, 1),
        "slots": slots_list[:15],
    }


def _attach_handoffs_to_groups(
    grouped: dict[str, dict[str, Any]],
    projects_map: dict[str, dict[str, Any]],
    eff_bg: Path,
    active_only: bool,
    pf_clean: str,
) -> None:
    """Attach STAGED, IN_WORK, and recent SUPERSEDED handoffs onto matching project groups (creating groups for new repos)."""
    inbox = list_handoff_tickets(eff_bg, include_superseded=True, limit=120)
    for t in inbox.get("tickets") or []:
        st = str(t.get("status") or "STAGED").upper()
        if st not in ("STAGED", "IN_WORK", "SUPERSEDED"):
            continue
        if active_only and st not in ("STAGED", "IN_WORK"):
            continue
        t_pid = str(t.get("project_id") or "").strip()
        t_ws = str(t.get("workspace_path") or "").rstrip("/")
        t_slug = str(t.get("repo_slug") or "").strip()
        t_pname = str(t.get("project_name") or t_slug or "Workspace")

        matched_pid = t_pid if t_pid in grouped else ""
        if not matched_pid:
            for cand_pid, pg in grouped.items():
                ws_list = pg.get("workspaces") or []
                if (t_ws and t_ws in ws_list) or cand_pid == f"ws:{t_slug}" or slugify_token(str(pg.get("project_name") or "")) == t_slug:
                    matched_pid = cand_pid
                    break
                if t_slug and any(slugify_token(Path(w).name) == t_slug for w in ws_list if w):
                    matched_pid = cand_pid
                    break
        if not matched_pid and (t_ws or t_slug):
            for cand_id, p_info in projects_map.items():
                p_paths = p_info.get("workspace_paths") or []
                if (t_ws and t_ws in p_paths) or any(slugify_token(Path(w).name) == t_slug for w in p_paths if w):
                    matched_pid = cand_id
                    t_pname = str(p_info.get("name") or t_pname)
                    break
        eff_pid = matched_pid or t_pid or f"ws:{t_slug or 'general'}"
        if pf_clean and pf_clean not in t_pname.lower() and pf_clean not in eff_pid.lower() and pf_clean not in t_slug.lower() and pf_clean not in str(t.get("title") or "").lower():
            continue

        pg = grouped.setdefault(
            eff_pid,
            {
                "project_id": eff_pid, "project_name": t_pname,
                "workspaces": list(projects_map.get(eff_pid, {}).get("workspace_paths") or ([t_ws] if t_ws else [])),
                "shared_repo": False, "running_count": 0, "pinned_count": 0,
                "staged_count": 0, "in_work_handoff_count": 0, "superseded_count": 0,
                "staged_handoffs": [], "sessions": [],
            },
        )
        if st == "SUPERSEDED" and int(pg.get("superseded_count") or 0) >= 4:
            continue
        if st == "STAGED":
            pg["staged_count"] = int(pg.get("staged_count") or 0) + 1
        elif st == "IN_WORK":
            pg["in_work_handoff_count"] = int(pg.get("in_work_handoff_count") or 0) + 1
        else:
            pg["superseded_count"] = int(pg.get("superseded_count") or 0) + 1
        pg.setdefault("staged_handoffs", []).append({
            "handoff_id": str(t.get("handoff_id") or ""), "sequence": int(t.get("sequence") or 0),
            "repo_slug": t_slug, "title": str(t.get("title") or "Gemini Research Handoff"),
            "status": st, "status_label": str(t.get("status_label") or st), "is_unclaimed": bool(st == "STAGED"),
            "workspace_path": t_ws, "target_conversation_id": str(t.get("target_conversation_id") or ""),
            "claimed_by_conversation_id": str(t.get("claimed_by_conversation_id") or ""),
            "rollover_from": str(t.get("rollover_from") or ""),
            "execution_mode": str(t.get("execution_mode") or "plan"), "handoff_mode": str(t.get("handoff_mode") or "intent"),
            "chars_written": int(t.get("chars_written") or 0), "superseded_by": str(t.get("superseded_by") or ""),
            "relative_age": str(t.get("relative_age") or ""), "updated_at": str(t.get("updated_at") or ""),
        })


def build_project_session_tree(
    active_only: bool = False,
    project_filter: str = "",
    limit: int = 25,
    bg_dir: Path | None = None,
) -> dict[str, Any]:
    """Build grouped Project -> Chat -> Session ID (+ Staged Handoff) hierarchy with 76-col ASCII tree."""
    eff_bg = bg_dir or cfg.AGY_BG_DIR
    sessions = _list_saved_sessions_internal(limit=max(10, min(limit, 200)), status_filter="ALL", include_subagents=False)
    projects_map = _load_projects_map()
    active_contexts = SESSION_STATE.get("active_contexts") or {}
    sel_conv = str(SESSION_STATE.get("selected_session") or "")

    ws_session_counts: dict[str, int] = {}
    ws_running_convs: dict[str, list[str]] = {}
    for s in sessions:
        wpath, cid, st = str(s.get("workspace_path") or "").rstrip("/"), str(s.get("conversation_id") or ""), str(s.get("status") or "IDLE")
        if wpath:
            ws_session_counts[wpath] = ws_session_counts.get(wpath, 0) + 1
            if st in ("RUNNING", "STALLED_WAITING_APPROVAL"):
                ws_running_convs.setdefault(wpath, []).append(cid)

    pf_clean = (project_filter or "").strip().lower()
    grouped: dict[str, dict[str, Any]] = {}
    for s in sessions:
        cid, title = str(s.get("conversation_id") or ""), str(s.get("title") or "Untitled Conversation")
        pid = str(s.get("project_id") or "")
        wpath = str(s.get("workspace_path") or str(AGY_PROJECTS_DIR if AGY_PROJECTS_DIR.is_dir() else AGY_GITLAB_DIR)).rstrip("/")
        norm_repo = normalize_workspace_name(wpath) if wpath else "unassigned"
        pname = str(s.get("project_name") or projects_map.get(pid, {}).get("name") or norm_repo or "Unassigned Workspace")
        pid = pid or f"ws:{norm_repo}"
        st = str(s.get("status") or "IDLE")
        is_running = st in ("RUNNING", "STALLED_WAITING_APPROVAL")
        is_pinned = (cid in active_contexts) or (cid == sel_conv)
        if active_only and not (is_running or is_pinned):
            continue
        if pf_clean and pf_clean not in pname.lower() and pf_clean not in pid.lower() and pf_clean not in wpath.lower() and pf_clean not in title.lower():
            continue

        other_writers = [rc for rc in ws_running_convs.get(wpath, []) if rc != cid]
        slot_info = active_contexts.get(cid, {}) if isinstance(active_contexts, dict) else {}
        mode = "WORKTREE" if "/worktrees/" in wpath else ("MAIN WRITER" if is_running else ("SHARED (READ-ONLY)" if other_writers else (str(slot_info.get("mode") or "PINNED") if is_pinned else "MAIN TREE")))
        status_badge = "[● RUNNING]" if is_running else ("[◉ PINNED · IDLE]" if is_pinned else f"[○ {st}]")

        p_group = grouped.setdefault(
            pid,
            {
                "project_id": pid, "project_name": pname,
                "workspaces": list(projects_map.get(pid, {}).get("workspace_paths") or ([wpath] if wpath else [])),
                "shared_repo": False, "running_count": 0, "pinned_count": 0,
                "staged_count": 0, "in_work_handoff_count": 0, "superseded_count": 0,
                "staged_handoffs": [], "sessions": [],
            },
        )
        if wpath and wpath not in p_group["workspaces"]:
            p_group["workspaces"].append(wpath)
        if ws_session_counts.get(wpath, 0) >= 2:
            p_group["shared_repo"] = True
        p_group["running_count"] += int(is_running)
        p_group["pinned_count"] += int(is_pinned)
        p_group["sessions"].append({
            "index": str(s.get("index") or ""), "conversation_id": cid, "title": title, "project_id": pid, "project_name": pname,
            "workspace_path": wpath, "workspace_short": Path(wpath).name if wpath else "unassigned",
            "status": st, "is_running": is_running, "is_pinned": is_pinned, "status_badge": status_badge, "mode": mode,
            "shared_repo": ws_session_counts.get(wpath, 0) >= 2, "step_count": int(s.get("step_count") or 0),
            "last_updated": str(s.get("last_updated") or ""), "relative_age": _format_relative_age(str(s.get("last_updated") or "")),
            "task_preview": str(s.get("task_preview") or ""),
        })

    _attach_handoffs_to_groups(grouped, projects_map, eff_bg, active_only, pf_clean)

    projects_list = list(grouped.values())
    for pg in projects_list:
        pg["sessions"].sort(key=lambda s: (not s.get("is_running"), not s.get("is_pinned"), int(s.get("index") or 999)))
    projects_list.sort(
        key=lambda p: (
            -(int(p.get("running_count") or 0) * 10 + int(p.get("staged_count") or 0) * 6 + int(p.get("in_work_handoff_count") or 0) * 4 + int(p.get("pinned_count") or 0)),
            -sum(int(s.get("step_count") or 0) for s in p.get("sessions", [])),
        )
    )
    for idx_p, pg in enumerate(projects_list, 1):
        pg["project_index"] = idx_p

    routing = get_routing_telemetry()
    backup_info = read_backup_321_manifest(eff_bg)
    ascii_tree = render_ascii_session_tree(projects_list, routing, backup_info)
    return {
        "projects_count": len(projects_list),
        "sessions_count": sum(len(p["sessions"]) for p in projects_list),
        "staged_handoffs_count": sum(int(p.get("staged_count") or 0) for p in projects_list),
        "in_work_handoffs_count": sum(int(p.get("in_work_handoff_count") or 0) for p in projects_list),
        "active_only": active_only, "project_filter": project_filter,
        "projects": projects_list, "routing_telemetry": routing, "backup_321": backup_info, "ascii_tree": ascii_tree,
    }


def render_ascii_session_tree(
    projects_list: list[dict[str, Any]],
    routing: dict[str, Any],
    backup_info: dict[str, Any],
) -> str:
    """Render a copy-ready 76-column ASCII Project -> Chat -> Session ID (+ Handoff) tree without UUID truncation."""
    w_box = 76
    top_border, mid_border, bot_border = "╔" + ("═" * (w_box - 2)) + "╗", "╠" + ("═" * (w_box - 2)) + "╣", "╚" + ("═" * (w_box - 2)) + "╝"

    def _box_line(txt: str) -> str:
        clipped = txt[: w_box - 4]
        return f"║ {clipped:<{w_box - 4}} ║"

    ttl_m, slots_n = routing.get("ttl_remaining_min", 0.0), routing.get("active_slots", 0)
    tot_stg = sum(int(p.get("staged_count") or 0) for p in projects_list)
    tot_inw = sum(int(p.get("in_work_handoff_count") or 0) for p in projects_list)
    lines = [
        top_border,
        _box_line(f"AGY-NEXUS v{__version__} // PROJECT -> CHAT -> SESSION ID HIERARCHY (COPY-READY)"),
        mid_border,
        _box_line(f"SLOTS: {slots_n} | STAGED: {tot_stg} | IN-WORK: {tot_inw} | PINNED: {routing.get('pinned_calls', 0)} | TTL: {ttl_m}m"),
        _box_line(f"3-2-1 BACKUP: {backup_info.get('short_sha', 'none')} ({backup_info.get('status_label', 'UNVERIFIED')} · {backup_info.get('bundle_size_kb', 0)} KB · {backup_info.get('age', '')})"),
        bot_border,
    ]
    if not projects_list:
        lines.append("  (No matching sessions found for current filter)")
        return "\n".join(lines)

    for pg in projects_list:
        shared_tag = " [SHARED REPO]" if pg.get("shared_repo") else ""
        stg_tag = f" [◈ {pg['staged_count']} STAGED]" if pg.get("staged_count") else ""
        inw_tag = f" [▶ {pg['in_work_handoff_count']} IN-WORK]" if pg.get("in_work_handoff_count") else ""
        ws_joined = ", ".join(pg.get("workspaces") or [])
        lines.extend(["", f"[PROJECT {pg.get('project_index', 1)}] {pg.get('project_name', 'Workspace')}{shared_tag}{stg_tag}{inw_tag}", f"  project_id : {pg.get('project_id', '')}"])
        if ws_joined:
            lines.append(f"  workspaces : {ws_joined}")
        handoffs = pg.get("staged_handoffs") or []
        sess_arr = pg.get("sessions") or []
        for h_i, h in enumerate(handoffs):
            is_last_h = (h_i == len(handoffs) - 1) and not sess_arr
            branch, pipe = ("└─", "   ") if is_last_h else ("├─", "│  ")
            hst = h.get("status", "STAGED")
            st_str = "[◈ STAGED · UNCLAIMED]" if hst == "STAGED" else (f"[▶ IN-WORK]" if hst == "IN_WORK" else f"[⊘ SUPERSEDED -> {h.get('superseded_by') or 'newer'}]")
            owner = h.get("claimed_by_conversation_id") or h.get("target_conversation_id") or "(unclaimed · new chat)"
            lines.append(f"  {branch} [HANDOFF {h.get('handoff_id', '?')}] {h.get('title', 'Handoff')}")
            lines.append(f"  {pipe} pass_off   : {st_str} · {h.get('execution_mode', 'plan')}/{h.get('handoff_mode', 'intent')} · {h.get('relative_age', '')}")
            lines.append(f"  {pipe} session_id : {owner}")
        for s_i, s in enumerate(sess_arr):
            is_last = s_i == len(sess_arr) - 1
            branch, pipe = ("└─", "   ") if is_last else ("├─", "│  ")
            lines.append(f"  {branch} [#{s.get('index', '?')}] {s.get('title', 'Untitled')}")
            lines.append(f"  {pipe} session_id : {s.get('conversation_id', '')}")
            lines.append(f"  {pipe} workspace  : {s.get('workspace_path', '')}")
            lines.append(f"  {pipe} status     : {s.get('status_badge', '[○ IDLE]')} · {s.get('mode', 'MAIN TREE')} · {int(s.get('step_count') or 0):,} steps · {s.get('relative_age', '')}")
    return "\n".join(lines)
