#!/usr/bin/env python3
"""agy_nexus.project_stats — Project-Scoped Stats Filtering, Session Roster & Code Health."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any

from agy_nexus.hygiene import is_sensitive_filename, resolve_source_repo_root
from agy_nexus.media_discovery import format_relative_age, parse_iso_epoch
from agy_nexus.stats_series import _sum_slots, _sum_slots_usd, resolve_canonical_project, resolve_root_conversation
from agy_nexus.telemetry_scanner import normalize_workspace_name, to_1h_slot

ROLLOVER_SEAM_STEPS = 700
CODE_EXTS = frozenset({".py", ".js", ".ts", ".tsx", ".jsx", ".css", ".html", ".go", ".rs", ".vue", ".sh", ".sql"})
SKIP_CODE_DIRS = frozenset({
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", "vendor", ".next", ".cache", "target",
})


def resolve_session_project_identity(
    cid: str,
    db_convs: dict[str, dict[str, Any]],
    live_sess_map: dict[str, dict[str, Any]],
    projects_map: dict[str, dict[str, Any]],
) -> tuple[str, str, str, str]:
    """Return (root_cid, project_id, project_name, workspace_path) for any conversation or subagent."""
    meta = db_convs.get(cid, {})
    is_sub = bool(meta.get("is_subagent"))
    root_cid = resolve_root_conversation(cid, db_convs) if is_sub else cid
    live_s = live_sess_map.get(root_cid) or live_sess_map.get(cid) or {}
    if live_s.get("project_id"):
        return (
            root_cid,
            str(live_s["project_id"]),
            str(live_s.get("project_name") or "Workspace"),
            str(live_s.get("workspace_path") or meta.get("workspace") or ""),
        )
    root_meta = db_convs.get(root_cid, meta)
    pid, pname, wpath = resolve_canonical_project(root_meta, projects_map)
    return root_cid, pid, pname, wpath


def build_fleet_project_index(
    conv_cache: dict[str, dict[str, Any]],
    db_convs: dict[str, dict[str, Any]],
    live_sess_map: dict[str, dict[str, Any]],
    projects_map: dict[str, dict[str, Any]],
    tree_bundle: dict[str, Any],
    s_iso: str,
    e_iso: str,
) -> dict[str, Any]:
    """Compute workstation-wide window steps, project color_slots, session count, and latest session ID."""
    proj_steps: dict[str, int] = {}
    proj_meta: dict[str, dict[str, Any]] = {}
    for tp in tree_bundle.get("projects") or []:
        pid = str(tp.get("project_id") or "")
        if not pid:
            continue
        ws_list = tp.get("workspaces") or []
        proj_meta[pid] = {
            "project_id": pid,
            "project_name": str(tp.get("project_name") or pid),
            "workspace_path": str(ws_list[0] if ws_list else ""),
            "staged_count": int(tp.get("staged_count") or 0),
            "in_work_handoff_count": int(tp.get("in_work_handoff_count") or 0),
            "completed_count": int(tp.get("completed_count") or 0),
            "staged_handoffs": list(tp.get("staged_handoffs") or []),
            "running_count": int(tp.get("running_count") or 0),
        }

    for cid, cdata in conv_cache.items():
        _, pid, pname, wpath = resolve_session_project_identity(cid, db_convs, live_sess_map, projects_map)
        w_st = sum(cnt for ds, cnt in (cdata.get("day_steps") or {}).items() if s_iso <= ds <= e_iso)
        proj_steps[pid] = proj_steps.get(pid, 0) + w_st
        cur = proj_meta.setdefault(pid, {"project_id": pid, "project_name": pname, "workspace_path": wpath, "staged_count": 0, "in_work_handoff_count": 0, "completed_count": 0, "staged_handoffs": [], "running_count": 0})
        if wpath and not cur.get("workspace_path"):
            cur["workspace_path"] = wpath

    for cid, meta in db_convs.items():
        if meta.get("is_subagent") and cid not in conv_cache and int(meta.get("step_count") or 0) > 0:
            d_str, _, _ = to_1h_slot(str(meta.get("last_modified") or ""), time.time())
            if len(d_str) == 10 and s_iso <= d_str <= e_iso:
                _, pid, pname, wpath = resolve_session_project_identity(cid, db_convs, live_sess_map, projects_map)
                proj_steps[pid] = proj_steps.get(pid, 0) + int(meta["step_count"])
                proj_meta.setdefault(pid, {"project_id": pid, "project_name": pname, "workspace_path": wpath, "staged_count": 0, "in_work_handoff_count": 0, "completed_count": 0, "staged_handoffs": [], "running_count": 0})

    ranked = sorted((pid for pid, st in proj_steps.items() if st > 0), key=lambda pid: (-proj_steps[pid], -proj_meta[pid]["running_count"], -proj_meta[pid]["staged_count"], pid))
    color_slots = {pid: idx for idx, pid in enumerate(ranked[:10])}
    seen_cids: set[str] = set()
    latest_cid, latest_ts = "", -1.0
    for tp in tree_bundle.get("projects") or []:
        for s in tp.get("sessions") or []:
            scid = str(s.get("conversation_id") or "")
            if scid:
                seen_cids.add(scid)
                ts = float(s.get("last_updated_ts") or 0.0)
                if ts > latest_ts:
                    latest_ts, latest_cid = ts, scid
    return {
        "fleet_window_steps": sum(proj_steps.values()),
        "color_slots": color_slots,
        "proj_meta": proj_meta,
        "total_sessions_count": len(seen_cids),
        "latest_session_id": latest_cid,
    }


def resolve_target_project_id(
    raw_pid: str,
    proj_meta: dict[str, dict[str, Any]],
    projects_map: dict[str, dict[str, Any]],
) -> str:
    """Resolve user-supplied project_id cleanly against known project IDs, slugs, or workspace paths."""
    q = (raw_pid or "").strip()
    if not q:
        return ""
    if q in proj_meta:
        return q
    q_low = q.lower()
    for pid, meta in proj_meta.items():
        if pid.lower() == q_low or str(meta.get("project_name") or "").lower() == q_low:
            return pid
        wp = str(meta.get("workspace_path") or "").rstrip("/")
        if wp and (wp.lower() == q_low or normalize_workspace_name(wp).lower() == q_low or f"ws:{normalize_workspace_name(wp).lower()}" == q_low):
            return pid
    for pid, pinfo in projects_map.items():
        if pid.lower() == q_low or str(pinfo.get("name") or "").lower() == q_low:
            return pid
    return q


def filter_project_conversations(
    conv_cache: dict[str, dict[str, Any]],
    db_convs: dict[str, dict[str, Any]],
    live_sess_map: dict[str, dict[str, Any]],
    projects_map: dict[str, dict[str, Any]],
    target_pid: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Filter conv_cache and db_convs strictly to main chats and subagents belonging to target_pid."""
    f_cache: dict[str, dict[str, Any]] = {}
    f_db: dict[str, dict[str, Any]] = {}
    for cid, cdata in conv_cache.items():
        _, pid, _, _ = resolve_session_project_identity(cid, db_convs, live_sess_map, projects_map)
        if pid == target_pid:
            f_cache[cid] = cdata
    for cid, meta in db_convs.items():
        _, pid, _, _ = resolve_session_project_identity(cid, db_convs, live_sess_map, projects_map)
        if pid == target_pid:
            f_db[cid] = meta
    return f_cache, f_db


def scan_project_code_health(workspace_path: str) -> dict[str, Any]:
    """Inspect <=500L / 650L modular line budget for a project's workspace_path on disk."""
    wp = (workspace_path or "").strip()
    if not wp:
        return {"available": False, "workspace_path": "", "reason": "No workspace path linked"}
    root = Path(wp).expanduser()
    if not root.is_dir():
        return {"available": False, "workspace_path": wp, "reason": "Workspace directory not present on local disk"}
    try:
        resolved = root.resolve()
        repo_root = resolve_source_repo_root(__file__)
        if repo_root is not None and resolved == repo_root.resolve():
            from agy_nexus.code_health import get_modular_hygiene_summary
            hyg = get_modular_hygiene_summary()
            return {"available": True, "workspace_path": str(resolved), **hyg, "modules": (hyg.get("modules") or [])[:15]}
    except Exception:
        return {"available": False, "workspace_path": wp, "reason": "Workspace path unreadable"}

    modules: list[dict[str, Any]] = []
    compliant = warning = violations = total_lines = 0
    stack: list[Path] = [resolved]
    while stack and len(modules) < 300:
        cur = stack.pop()
        try:
            entries = sorted(cur.iterdir(), key=lambda p: p.name)
        except OSError:
            continue
        for entry in entries:
            if entry.is_symlink():
                continue
            if entry.is_dir():
                if entry.name not in SKIP_CODE_DIRS and not entry.name.startswith("."):
                    stack.append(entry)
                continue
            if entry.suffix.lower() not in CODE_EXTS or is_sensitive_filename(entry.name):
                continue
            try:
                if entry.stat().st_size > 1_000_000:
                    continue
                lcnt = len(entry.read_text(encoding="utf-8", errors="replace").splitlines())
            except OSError:
                continue
            status = "compliant" if lcnt <= 500 else ("warning" if lcnt <= 650 else "violation")
            compliant += int(status == "compliant")
            warning += int(status == "warning")
            violations += int(status == "violation")
            total_lines += lcnt
            modules.append({"name": entry.relative_to(resolved).as_posix(), "lines": lcnt, "status": status})
            if len(modules) >= 300:
                break

    modules.sort(key=lambda m: (-m["lines"], m["name"]))
    return {
        "available": True, "workspace_path": str(resolved), "target_lines": 500, "ceiling_lines": 650,
        "total_modules": len(modules), "compliant_500": compliant, "warning_501_650": warning,
        "violations_over_650": violations, "ceiling_pass": violations == 0, "total_lines": total_lines,
        "modules": modules[:15],
    }


def build_project_sessions_series(
    pb: dict[str, Any] | None,
    labels: list[str],
    groups: list[list[str]],
    step_h: int,
    res_lbl: str,
    s1_sess_steps: dict[str, dict[str, int]],
    s1_sess_toks: dict[str, dict[str, int]],
    s1_sess_cost: dict[str, dict[str, int]] | None = None,
) -> dict[str, Any]:
    """Assemble Project Sessions (Daily) stacked bar layers (steps, tokens, USD) and Session Roster rows."""
    sessions_raw = list((pb or {}).get("sessions") or [])
    proj_win_steps = max(1, sum(int(s.get("window_steps") or 0) for s in sessions_raw))
    sessions_raw.sort(key=lambda s: (-int(s.get("window_steps") or 0), not bool(s.get("is_running")), -float(s.get("last_updated_ts") or 0.0), -int(s.get("step_count") or 0)))

    active_sess = [s for s in sessions_raw if int(s.get("window_steps") or 0) > 0]
    plot_sess = active_sess[:11] if len(active_sess) > 12 else active_sess
    ovf_sess = active_sess[11:] if len(active_sess) > 12 else []

    keys: list[str] = []
    layers: dict[str, list[int]] = {}
    token_layers: dict[str, list[int]] = {}
    cost_layers: dict[str, list[float]] = {}
    labels_map: dict[str, str] = {}
    colors_map: dict[str, int] = {}
    n_bins = len(groups)
    cost_map = s1_sess_cost or {}

    for idx, s in enumerate(plot_sess):
        cid = str(s.get("conversation_id") or "")
        keys.append(cid)
        layers[cid] = _sum_slots(s1_sess_steps.get(cid, {}), groups)
        token_layers[cid] = _sum_slots(s1_sess_toks.get(cid, {}), groups)
        cost_layers[cid] = _sum_slots_usd(cost_map.get(cid, {}), groups)
        labels_map[cid] = str(s.get("title") or cid[:8])
        colors_map[cid] = idx

    if ovf_sess:
        ovf_st, ovf_tk, ovf_cs = [0] * n_bins, [0] * n_bins, [0.0] * n_bins
        for s in ovf_sess:
            cid = str(s.get("conversation_id") or "")
            st_a = _sum_slots(s1_sess_steps.get(cid, {}), groups)
            tk_a = _sum_slots(s1_sess_toks.get(cid, {}), groups)
            cs_a = _sum_slots_usd(cost_map.get(cid, {}), groups)
            ovf_st = [a + b for a, b in zip(ovf_st, st_a)]
            ovf_tk = [a + b for a, b in zip(ovf_tk, tk_a)]
            ovf_cs = [round(a + b, 4) for a, b in zip(ovf_cs, cs_a)]
        keys.append("__other_sessions__")
        layers["__other_sessions__"] = ovf_st
        token_layers["__other_sessions__"] = ovf_tk
        cost_layers["__other_sessions__"] = ovf_cs
        labels_map["__other_sessions__"] = f"Other ({len(ovf_sess)} sessions)"
        colors_map["__other_sessions__"] = 11

    roster: list[dict[str, Any]] = []
    for s in sessions_raw:
        cid = str(s.get("conversation_id") or "")
        w_st = int(s.get("window_steps") or 0)
        w_cm = int(s.get("window_cost_micros") or 0)
        last_iso = str(s.get("last_updated") or "")
        last_ts = float(s.get("last_updated_ts") or 0.0) or parse_iso_epoch(last_iso)
        rel_age = str(s.get("relative_age") or "") or (format_relative_age(last_iso, last_ts) if last_ts > 0 else "recent")
        roster.append({
            "conversation_id": cid, "short_id": cid[:8], "title": str(s.get("title") or cid[:8]),
            "status": str(s.get("status") or "IDLE"), "is_running": bool(s.get("is_running")),
            "is_pinned": bool(s.get("is_pinned")),
            "is_retired": bool(s.get("is_retired") or str(s.get("status") or "").upper() == "RETIRED"),
            "share_pct": round((w_st / proj_win_steps) * 100.0, 1) if w_st > 0 else 0.0,
            "window_steps": w_st, "window_tokens": int(s.get("window_tokens") or 0),
            "window_cost_micros": w_cm, "window_cost_usd": round(w_cm / 1_000_000.0, 4),
            "step_count": int(s.get("step_count") or 0), "subagent_runs": int(s.get("subagent_runs") or 0),
            "has_last_24h": bool(s.get("has_last_24h")),
            "last_24h_steps": s.get("last_24h_steps"),
            "last_24h_tokens": s.get("last_24h_tokens"),
            "last_24h_cost_usd": s.get("last_24h_cost_usd"),
            "last_updated": last_iso, "last_updated_ts": last_ts,
            "relative_age": rel_age,
            "color_slot": colors_map.get(cid, -1),
        })

    return {
        "dates": labels, "step_hours": step_h, "resolution": res_lbl,
        "keys": keys, "layers": layers, "token_layers": token_layers, "cost_layers": cost_layers,
        "labels": labels_map, "colors": colors_map, "sessions": roster,
    }


def build_project_scope_payload(
    target_pid: str,
    proj_meta: dict[str, Any],
    fleet_idx: dict[str, Any],
    pb: dict[str, Any] | None,
    win_steps: int,
    win_tokens: int,
    active_days: int,
    *,
    win_cost_micros: int = 0,
) -> dict[str, Any]:
    """Build project_scope metadata (workstation share, 700-step context budget, handoff counts, code health)."""
    sessions = list((pb or {}).get("sessions") or [])
    running_s = [s for s in sessions if s.get("is_running")]
    pool_for_budget = running_s or sessions
    top_sess = max(pool_for_budget, key=lambda s: int(s.get("step_count") or 0)) if pool_for_budget else None
    max_steps = int(top_sess.get("step_count") or 0) if top_sess else 0
    fleet_steps = int(fleet_idx.get("fleet_window_steps") or 0)
    ws_path = str(proj_meta.get("workspace_path") or (sessions[0].get("workspace_path") if sessions else "") or "")
    act_cnt = sum(1 for s in sessions if int(s.get("window_steps") or 0) > 0)
    tot_cnt = len(sessions)
    run_cnt = len(running_s)
    return {
        "project_id": target_pid,
        "project_name": str(proj_meta.get("project_name") or target_pid),
        "workspace_path": ws_path,
        "color_slot": (fleet_idx.get("color_slots") or {}).get(target_pid, 0),
        "fleet_window_steps": fleet_steps,
        "share_of_workstation_pct": round((win_steps / max(1, fleet_steps)) * 100.0, 1) if fleet_steps > 0 else 0.0,
        "total_sessions": tot_cnt,
        "active_sessions_count": act_cnt,
        "running_count": run_cnt,
        "idle_count": max(0, tot_cnt - run_cnt),
        "avg_tokens_per_session": round(win_tokens / max(1, act_cnt or tot_cnt)),
        "window_cost_micros": int(win_cost_micros),
        "window_cost_usd": round(int(win_cost_micros) / 1_000_000.0, 2),
        "staged_count": int(proj_meta.get("staged_count") or 0),
        "in_work_handoff_count": int(proj_meta.get("in_work_handoff_count") or 0),
        "completed_count": int(proj_meta.get("completed_count") or 0),
        "staged_handoffs": list(proj_meta.get("staged_handoffs") or [])[:10],
        "active_days": active_days,
        "context_budget": {
            "max_session_steps": max_steps,
            "rollover_seam_steps": ROLLOVER_SEAM_STEPS,
            "budget_pct": round((max_steps / ROLLOVER_SEAM_STEPS) * 100.0, 1),
            "top_session_id": str(top_sess.get("conversation_id") or "") if top_sess else "",
            "top_session_title": str(top_sess.get("title") or "") if top_sess else "",
            "running_count": run_cnt,
            "idle_count": max(0, tot_cnt - run_cnt),
        },
        "code_health": scan_project_code_health(ws_path),
    }


def compact_project_hierarchy_sessions(project_hierarchy: dict[str, Any]) -> None:
    """Strip per-session steps_series/tokens_series/cost_series arrays from Whole-Fleet project_hierarchy to reduce payload size."""
    if not isinstance(project_hierarchy, dict):
        return
    groups: list[dict[str, Any]] = []
    groups.extend(project_hierarchy.get("top_projects") or [])
    groups.extend(project_hierarchy.get("idle_projects") or [])
    if isinstance(project_hierarchy.get("other_projects"), dict):
        groups.append(project_hierarchy["other_projects"])
    for pg in groups:
        if not isinstance(pg, dict):
            continue
        pg.pop("overflow_sessions_series", None)
        for s in pg.get("sessions") or []:
            if isinstance(s, dict):
                s.pop("steps_series", None)
                s.pop("tokens_series", None)
                s.pop("cost_series", None)
