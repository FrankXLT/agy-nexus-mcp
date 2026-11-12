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
from agy_nexus.config import AGY_BG_DIR, AGY_GITLAB_DIR, SESSION_STATE
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
    eff_bg = bg_dir or AGY_BG_DIR
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
                        "ok": bool(data.get("ok", True)),
                        "short_sha": head_sha[:7] if head_sha else "unknown",
                        "head_sha": head_sha,
                        "origin_sha": str(data.get("origin_sha") or ""),
                        "gitlab_sha": str(data.get("gitlab_sha") or ""),
                        "shas_match": shas_match,
                        "bundle_size_bytes": size_b,
                        "bundle_size_kb": round(size_b / 1024.0, 1) if size_b else 0.0,
                        "timestamp_utc": ts_utc,
                        "age": _format_relative_age(ts_utc),
                        "status_label": "SYNCED ✓" if shas_match and head_sha else "DRIFT !",
                    }
        except Exception:
            continue
    return {
        "ok": False,
        "short_sha": "none",
        "head_sha": "",
        "origin_sha": "",
        "gitlab_sha": "",
        "shas_match": False,
        "bundle_size_bytes": 0,
        "bundle_size_kb": 0.0,
        "timestamp_utc": "",
        "age": "never",
        "status_label": "UNVERIFIED",
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


def build_project_session_tree(
    active_only: bool = False,
    project_filter: str = "",
    limit: int = 25,
    bg_dir: Path | None = None,
) -> dict[str, Any]:
    """Build grouped Project -> Chat -> Session ID hierarchy with parallel slot states and 76-col ASCII tree."""
    sessions = _list_saved_sessions_internal(limit=max(10, min(limit, 200)), status_filter="ALL", include_subagents=False)
    projects_map = _load_projects_map()
    active_contexts = SESSION_STATE.get("active_contexts") or {}
    sel_conv = str(SESSION_STATE.get("selected_session") or "")

    # Pre-compute workspace sharing & running writer counts across all fetched sessions
    ws_session_counts: dict[str, int] = {}
    ws_running_convs: dict[str, list[str]] = {}
    for s in sessions:
        wpath = str(s.get("workspace_path") or "").rstrip("/")
        cid = str(s.get("conversation_id") or "")
        st = str(s.get("status") or "IDLE")
        if wpath:
            ws_session_counts[wpath] = ws_session_counts.get(wpath, 0) + 1
            if st in ("RUNNING", "STALLED_WAITING_APPROVAL"):
                ws_running_convs.setdefault(wpath, []).append(cid)

    pf_clean = (project_filter or "").strip().lower()
    grouped: dict[str, dict[str, Any]] = {}
    for s in sessions:
        cid = str(s.get("conversation_id") or "")
        title = str(s.get("title") or "Untitled Conversation")
        pid = str(s.get("project_id") or "")
        wpath = str(s.get("workspace_path") or str(AGY_GITLAB_DIR)).rstrip("/")
        repo_short = Path(wpath).name if wpath else "unassigned"
        norm_repo = normalize_workspace_name(wpath) if wpath else "unassigned"
        pname = str(s.get("project_name") or projects_map.get(pid, {}).get("name") or norm_repo or "Unassigned Workspace")
        if not pid:
            pid = f"ws:{norm_repo}"

        st = str(s.get("status") or "IDLE")
        is_running = st in ("RUNNING", "STALLED_WAITING_APPROVAL")
        is_pinned = (cid in active_contexts) or (cid == sel_conv)
        if active_only and not (is_running or is_pinned):
            continue
        if pf_clean and pf_clean not in pname.lower() and pf_clean not in pid.lower() and pf_clean not in wpath.lower() and pf_clean not in title.lower():
            continue

        other_writers = [rc for rc in ws_running_convs.get(wpath, []) if rc != cid]
        slot_info = active_contexts.get(cid, {}) if isinstance(active_contexts, dict) else {}
        if "/worktrees/" in wpath:
            mode = "WORKTREE"
        elif is_running:
            mode = "MAIN WRITER"
        elif other_writers:
            mode = "SHARED (READ-ONLY)"
        elif is_pinned:
            mode = str(slot_info.get("mode") or "PINNED")
        else:
            mode = "MAIN TREE"

        status_badge = "[● RUNNING]" if is_running else ("[◉ PINNED · IDLE]" if is_pinned else f"[○ {st}]")
        age_str = _format_relative_age(str(s.get("last_updated") or ""))
        step_cnt = int(s.get("step_count") or 0)

        p_group = grouped.setdefault(
            pid,
            {
                "project_id": pid,
                "project_name": pname,
                "workspaces": list(projects_map.get(pid, {}).get("workspace_paths") or ([wpath] if wpath else [])),
                "shared_repo": False,
                "running_count": 0,
                "pinned_count": 0,
                "sessions": [],
            },
        )
        if wpath and wpath not in p_group["workspaces"]:
            p_group["workspaces"].append(wpath)
        if ws_session_counts.get(wpath, 0) >= 2:
            p_group["shared_repo"] = True
        if is_running:
            p_group["running_count"] += 1
        if is_pinned:
            p_group["pinned_count"] += 1

        p_group["sessions"].append({
            "index": str(s.get("index") or ""),
            "conversation_id": cid,
            "title": title,
            "project_id": pid,
            "project_name": pname,
            "workspace_path": wpath,
            "workspace_short": repo_short,
            "status": st,
            "is_running": is_running,
            "is_pinned": is_pinned,
            "status_badge": status_badge,
            "mode": mode,
            "shared_repo": ws_session_counts.get(wpath, 0) >= 2,
            "step_count": step_cnt,
            "last_updated": str(s.get("last_updated") or ""),
            "relative_age": age_str,
            "task_preview": str(s.get("task_preview") or ""),
        })

    projects_list = list(grouped.values())
    for pg in projects_list:
        pg["sessions"].sort(key=lambda s: (not s.get("is_running"), not s.get("is_pinned"), int(s.get("index") or 999)))
    projects_list.sort(
        key=lambda p: (
            -(int(p.get("running_count") or 0) * 10 + int(p.get("pinned_count") or 0)),
            -sum(int(s.get("step_count") or 0) for s in p.get("sessions", [])),
        )
    )
    for idx_p, pg in enumerate(projects_list, 1):
        pg["project_index"] = idx_p

    routing = get_routing_telemetry()
    backup_info = read_backup_321_manifest(bg_dir)
    ascii_tree = render_ascii_session_tree(projects_list, routing, backup_info)

    return {
        "projects_count": len(projects_list),
        "sessions_count": sum(len(p["sessions"]) for p in projects_list),
        "active_only": active_only,
        "project_filter": project_filter,
        "projects": projects_list,
        "routing_telemetry": routing,
        "backup_321": backup_info,
        "ascii_tree": ascii_tree,
    }


def render_ascii_session_tree(
    projects_list: list[dict[str, Any]],
    routing: dict[str, Any],
    backup_info: dict[str, Any],
) -> str:
    """Render a copy-ready 76-column ASCII Project -> Chat -> Session ID tree without UUID/path truncation."""
    w_box = 76
    top_border = "╔" + ("═" * (w_box - 2)) + "╗"
    mid_border = "╠" + ("═" * (w_box - 2)) + "╣"
    bot_border = "╚" + ("═" * (w_box - 2)) + "╝"

    def _box_line(txt: str) -> str:
        clipped = txt[: w_box - 4]
        return f"║ {clipped:<{w_box - 4}} ║"

    ttl_m = routing.get("ttl_remaining_min", 0.0)
    slots_n = routing.get("active_slots", 0)
    pinned_n = routing.get("pinned_calls", 0)
    auto_n = routing.get("auto_resolved_calls", 0)
    b_sha = backup_info.get("short_sha", "none")
    b_lbl = backup_info.get("status_label", "UNVERIFIED")

    lines = [
        top_border,
        _box_line(f"AGY-NEXUS v{__version__} // PROJECT -> CHAT -> SESSION ID HIERARCHY (COPY-READY)"),
        mid_border,
        _box_line(f"ACTIVE SLOTS: {slots_n} | PINNED: {pinned_n} | AUTO-PATH: {auto_n} | TTL: {ttl_m}m"),
        _box_line(f"3-2-1 BACKUP: {b_sha} ({b_lbl} · {backup_info.get('bundle_size_kb', 0)} KB · {backup_info.get('age', '')})"),
        bot_border,
    ]

    if not projects_list:
        lines.append("  (No matching sessions found for current filter)")
        return "\n".join(lines)

    for pg in projects_list:
        p_idx = pg.get("project_index", 1)
        p_name = pg.get("project_name", "Workspace")
        p_id = pg.get("project_id", "")
        shared_tag = " [SHARED REPO]" if pg.get("shared_repo") else ""
        ws_joined = ", ".join(pg.get("workspaces") or [])
        lines.append("")
        lines.append(f"[PROJECT {p_idx}] {p_name}{shared_tag}")
        lines.append(f"  project_id : {p_id}")
        if ws_joined:
            lines.append(f"  workspaces : {ws_joined}")
        sess_arr = pg.get("sessions") or []
        for s_i, s in enumerate(sess_arr):
            is_last = s_i == len(sess_arr) - 1
            branch = "└─" if is_last else "├─"
            pipe = "   " if is_last else "│  "
            lines.append(f"  {branch} [#{s.get('index', '?')}] {s.get('title', 'Untitled')}")
            lines.append(f"  {pipe} session_id : {s.get('conversation_id', '')}")
            lines.append(f"  {pipe} workspace  : {s.get('workspace_path', '')}")
            lines.append(
                f"  {pipe} status     : {s.get('status_badge', '[○ IDLE]')} · {s.get('mode', 'MAIN TREE')} · {int(s.get('step_count') or 0):,} steps · {s.get('relative_age', '')}"
            )
    return "\n".join(lines)
