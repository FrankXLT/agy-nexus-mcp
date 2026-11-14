#!/usr/bin/env python3
"""
agy_nexus.stats_series — 1h Adaptive Slot Grids, Stacked Model/Subagent Series & Canonical Top-10 Project->Session Hierarchy.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agy_nexus.telemetry_scanner import normalize_workspace_name

MODEL_KEYS = ("carbon", "argon_pro", "flash", "claude_partner", "gpt_oss")
MODEL_SHORT_LABELS = {"carbon": "Carbon 4", "argon_pro": "Argon 4 Pro", "flash": "Flash 3.8", "claude_partner": "Claude 5.5", "gpt_oss": "GPT-OSS 120B"}


def load_projects_meta(agy_config_dir: Path) -> dict[str, dict[str, Any]]:
    """Read Antigravity project definitions from AGY_CONFIG_DIR/projects/*.json."""
    proj_map: dict[str, dict[str, Any]] = {}
    proj_dir = agy_config_dir / "projects"
    if not proj_dir.is_dir():
        return proj_map
    for pfile in sorted(proj_dir.glob("*.json")):
        try:
            data = json.loads(pfile.read_text(encoding="utf-8"))
            pid, name = str(data.get("id") or pfile.stem), str(data.get("name") or pfile.stem)
            paths: list[str] = []
            for res in (data.get("projectResources") or {}).get("resources") or []:
                uri = (res.get("gitFolder") or {}).get("folderUri") or res.get("folderUri") or ""
                if uri:
                    paths.append(str(uri).replace("file://", "").rstrip("/"))
            proj_map[pid] = {"project_id": pid, "name": name, "workspace_paths": paths}
        except Exception:
            continue
    return proj_map


def resolve_subagent_model(agent_role: str, parent_id: str, parent_model_map: dict[str, str], main_mk: str, main_switch_date: str, day_or_slot: str) -> tuple[str, bool]:
    """Return (model_key, is_inherited) for a subagent conversation."""
    r_low = (agent_role or "").lower()
    if any(k in r_low for k in ("claude", "sonnet", "opus")): return "claude_partner", False
    if "gpt" in r_low or "120b" in r_low: return "gpt_oss", False
    if "flash" in r_low: return "flash", False
    if "argon" in r_low: return "argon_pro", False
    if "carbon" in r_low: return "carbon", False
    if parent_id and parent_model_map.get(parent_id): return parent_model_map[parent_id], True
    if main_mk == "carbon" and main_switch_date and (day_or_slot or "")[:10] >= main_switch_date: return "carbon", True
    return "argon_pro", True


def resolve_root_conversation(cid: str, db_convs: dict[str, dict[str, Any]]) -> str:
    """Walk parent_id pointers (up to 6 hops) to locate the root main-chat session ID."""
    cur, seen = cid, {cid}
    for _ in range(6):
        p_id = str((db_convs.get(cur) or {}).get("parent_id") or "")
        if not p_id or p_id in seen or p_id not in db_convs:
            break
        seen.add(p_id)
        cur = p_id
    return cur


def resolve_canonical_project(meta: dict[str, Any], projects_map: dict[str, dict[str, Any]]) -> tuple[str, str, str]:
    """Resolve canonical (project_id, project_name, workspace_path) matching session_tree.py."""
    pid, wpath = str(meta.get("project_id") or "").strip(), str(meta.get("workspace") or "").rstrip("/")
    if not wpath and pid in projects_map:
        p_paths = projects_map[pid].get("workspace_paths") or []
        if p_paths: wpath = str(p_paths[0])
    norm_repo = normalize_workspace_name(wpath) if wpath else "unassigned"
    if not pid and wpath:
        for cand_id, p_info in projects_map.items():
            if any(wpath == p_ws or normalize_workspace_name(p_ws) == norm_repo for p_ws in (p_info.get("workspace_paths") or [])):
                pid = cand_id
                break
    pname = str((projects_map.get(pid) or {}).get("name") or norm_repo or "Unassigned Workspace")
    return (pid or f"ws:{norm_repo}"), pname, wpath


def build_base_slot_grid(period_key: str, trimmed_days: list[str], today_iso: str, now_hour: int) -> tuple[list[str], list[list[str]], int, str]:
    """Generate calendar-aligned base slot groups (1h / 2h / 6h / 24h) for adaptive client binning."""
    step_h, res_lbl = (1, "1h sub-daily") if period_key == "current_month" else ((2, "2h sub-daily") if period_key == "last_month" else ((6, "6h sub-daily") if period_key == "last_90d" else (24, "daily")))
    labels, groups = [], []
    for d_iso in trimmed_days:
        if step_h == 24:
            s_list = [f"{d_iso}T{h:02d}" for h in range(24) if d_iso < today_iso or h <= now_hour]
            if s_list:
                labels.append(d_iso)
                groups.append(s_list)
        else:
            for h0 in range(0, 24, step_h):
                if d_iso == today_iso and h0 > now_hour: continue
                s_list = [f"{d_iso}T{h:02d}" for h in range(h0, min(24, h0 + step_h)) if d_iso < today_iso or h <= now_hour]
                if s_list:
                    labels.append(f"{d_iso} {h0:02d}:00")
                    groups.append(s_list)
    return labels, groups, step_h, res_lbl


def _sum_slots(slot_map: dict[str, int], groups: list[list[str]]) -> list[int]:
    return [sum(slot_map.get(s, 0) for s in g) for g in groups] if slot_map else [0] * len(groups)


def _build_project_buckets(
    root_sess_stats: dict[str, dict[str, Any]],
    db_convs: dict[str, dict[str, Any]],
    projects_map: dict[str, dict[str, Any]],
    tree_bundle: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Merge window telemetry, live session states, and repo-prefixed handoff tickets into per-project buckets."""
    live_sess_map, live_proj_meta = {}, {}
    for tp in tree_bundle.get("projects") or []:
        if tp.get("project_id"):
            live_proj_meta[str(tp["project_id"])] = tp
        for ts in tp.get("sessions") or []:
            if ts.get("conversation_id"):
                live_sess_map[str(ts["conversation_id"])] = ts

    def _init_bucket(pid: str, pname: str) -> dict[str, Any]:
        tp_meta = live_proj_meta.get(pid) or {}
        return {
            "project_id": pid, "project_name": pname, "shared_repo": bool(tp_meta.get("shared_repo")),
            "running_count": 0, "pinned_count": 0,
            "staged_count": int(tp_meta.get("staged_count") or 0),
            "in_work_handoff_count": int(tp_meta.get("in_work_handoff_count") or 0),
            "superseded_count": int(tp_meta.get("superseded_count") or 0),
            "staged_handoffs": list(tp_meta.get("staged_handoffs") or []),
            "window_steps": 0, "window_tokens": 0, "total_steps": 0,
            "sessions": [], "_s1_steps": {}, "_s1_toks": {},
        }

    proj_buckets: dict[str, dict[str, Any]] = {}
    for rcid in (set(root_sess_stats.keys()) | set(live_sess_map.keys())):
        st_info, live_s, meta = root_sess_stats.get(rcid, {}), live_sess_map.get(rcid, {}), db_convs.get(rcid, {})
        if live_s:
            pid, pname, wpath = str(live_s.get("project_id") or ""), str(live_s.get("project_name") or "Workspace"), str(live_s.get("workspace_path") or meta.get("workspace") or "")
        else:
            pid, pname, wpath = resolve_canonical_project(meta, projects_map)
        w_steps, w_toks = int(st_info.get("win_steps") or 0), int(st_info.get("win_tokens") or 0)
        tot_steps = max(w_steps, int(live_s.get("step_count") or meta.get("step_count") or 0))
        if w_steps == 0 and not live_s:
            continue
        status_s = str(live_s.get("status") or meta.get("status") or "IDLE")
        is_run = bool(live_s.get("is_running") or status_s in ("RUNNING", "STALLED_WAITING_APPROVAL"))
        is_pin = bool(live_s.get("is_pinned"))
        pb = proj_buckets.setdefault(pid, _init_bucket(pid, pname))
        pb["running_count"] += int(is_run)
        pb["pinned_count"] += int(is_pin)
        pb["window_steps"], pb["window_tokens"], pb["total_steps"] = pb["window_steps"] + w_steps, pb["window_tokens"] + w_toks, pb["total_steps"] + tot_steps
        for sk, sv in (st_info.get("s1_steps") or {}).items():
            pb["_s1_steps"][sk] = pb["_s1_steps"].get(sk, 0) + sv
        for sk, sv in (st_info.get("s1_toks") or {}).items():
            pb["_s1_toks"][sk] = pb["_s1_toks"].get(sk, 0) + sv
        pb["sessions"].append({
            "index": str(live_s.get("index") or ""), "conversation_id": rcid, "title": str(live_s.get("title") or meta.get("title") or rcid[:8]),
            "project_id": pid, "project_name": pname, "workspace_path": wpath, "workspace_short": str(live_s.get("workspace_short") or (Path(wpath).name if wpath else "unassigned")),
            "status": status_s, "is_running": is_run, "is_pinned": is_pin, "mode": str(live_s.get("mode") or ("WORKTREE" if "/worktrees/" in wpath else "MAIN TREE")),
            "window_steps": w_steps, "window_tokens": w_toks, "step_count": tot_steps, "subagent_runs": int(st_info.get("sub_runs") or 0),
            "last_updated": str(live_s.get("last_updated") or meta.get("last_modified") or ""), "relative_age": str(live_s.get("relative_age") or ""),
            "_s1_steps": st_info.get("s1_steps") or {}, "_s1_toks": st_info.get("s1_toks") or {},
        })

    # Ensure zero-session projects that already have staged/in-work handoffs appear in the hierarchy
    for pid, tp_meta in live_proj_meta.items():
        if pid not in proj_buckets and (tp_meta.get("staged_handoffs") or []):
            proj_buckets[pid] = _init_bucket(pid, str(tp_meta.get("project_name") or pid))
    return proj_buckets


def build_series_and_project_hierarchy(
    *, period_key: str, trimmed_days: list[str], today_iso: str, now_hour: int,
    s1_tot_steps: dict[str, int], s1_tot_toks: dict[str, int],
    s1_mod_steps: dict[str, dict[str, int]], s1_mod_toks: dict[str, dict[str, int]],
    s1_sub_steps: dict[str, dict[str, int]], s1_sub_toks: dict[str, dict[str, int]],
    s1_ws_steps: dict[str, dict[str, int]], all_ws_list: list[dict[str, Any]],
    subagent_list: list[dict[str, Any]], root_sess_stats: dict[str, dict[str, Any]],
    db_convs: dict[str, dict[str, Any]], projects_map: dict[str, dict[str, Any]], tree_bundle: dict[str, Any],
) -> dict[str, Any]:
    """Assemble velocity_series, model_series, subagent_series, workspace_series, and canonical Top-10 project_hierarchy."""
    labels, groups, step_h, res_lbl = build_base_slot_grid(period_key, trimmed_days, today_iso, now_hour)
    n_bins = len(groups)
    vel_steps, vel_toks = _sum_slots(s1_tot_steps, groups), _sum_slots(s1_tot_toks, groups)
    mod_layers = {mk: _sum_slots(s1_mod_steps.get(mk, {}), groups) for mk in MODEL_KEYS}
    mod_tok_layers = {mk: _sum_slots(s1_mod_toks.get(mk, {}), groups) for mk in MODEL_KEYS}

    sub_keys = [s["role"] for s in subagent_list[:8]] + (["other-subagents"] if len(subagent_list) > 8 else [])
    other_sub = [s["role"] for s in subagent_list[8:]]
    sub_layers = {k: ([sum(sum(s1_sub_steps.get(ok, {}).get(s, 0) for ok in other_sub) for s in g) for g in groups] if k == "other-subagents" else _sum_slots(s1_sub_steps.get(k, {}), groups)) for k in sub_keys}
    sub_tok_layers = {k: ([sum(sum(s1_sub_toks.get(ok, {}).get(s, 0) for ok in other_sub) for s in g) for g in groups] if k == "other-subagents" else _sum_slots(s1_sub_toks.get(k, {}), groups)) for k in sub_keys}

    ws_keys = [w["workspace"] for w in all_ws_list[:5]] + (["other-projects"] if len(all_ws_list) > 5 else [])
    other_ws = [w["workspace"] for w in all_ws_list[5:]]
    ws_layers = {k: ([sum(sum(s1_ws_steps.get(ok, {}).get(s, 0) for ok in other_ws) for s in g) for g in groups] if k == "other-projects" else _sum_slots(s1_ws_steps.get(k, {}), groups)) for k in ws_keys}

    proj_buckets = _build_project_buckets(root_sess_stats, db_convs, projects_map, tree_bundle)
    tot_win_steps = max(1, sum(p["window_steps"] for p in proj_buckets.values()))
    active_projs = sorted((p for p in proj_buckets.values() if p["window_steps"] > 0), key=lambda p: (-p["window_steps"], -p["running_count"], -p["staged_count"], -p["total_steps"]))
    idle_projs = sorted((p for p in proj_buckets.values() if p["window_steps"] == 0), key=lambda p: (-p["staged_count"], -p["in_work_handoff_count"], -p["running_count"], -p["pinned_count"], -p["total_steps"]))

    top_projects: list[dict[str, Any]] = []
    for p_idx, pb in enumerate(active_projs[:10]):
        pb["color_slot"], pb["share_pct"] = p_idx, round((pb["window_steps"] / tot_win_steps) * 100.0, 1)
        pb["steps_series"], pb["tokens_series"] = _sum_slots(pb.pop("_s1_steps"), groups), _sum_slots(pb.pop("_s1_toks"), groups)
        pb["sessions"].sort(key=lambda s: (-s["window_steps"], not s["is_running"], not s["is_pinned"], -s["step_count"]))
        act_cnt = sum(1 for s in pb["sessions"] if s["window_steps"] > 0)
        shade_cap, ovf_steps, ovf_toks, has_ovf, act_rank = min(12, max(1, act_cnt)), [0] * n_bins, [0] * n_bins, False, 0
        for s in pb["sessions"]:
            s_st_map, s_tk_map = s.pop("_s1_steps"), s.pop("_s1_toks")
            s["share_pct"] = round((s["window_steps"] / tot_win_steps) * 100.0, 1)
            if s["window_steps"] > 0:
                if act_rank < 11 or act_cnt <= 12:
                    s["shade_idx"], s["shade_count"] = act_rank, shade_cap
                    s["steps_series"], s["tokens_series"] = _sum_slots(s_st_map, groups), _sum_slots(s_tk_map, groups)
                else:
                    s["shade_idx"], s["shade_count"] = 11, shade_cap
                    st_arr, tk_arr = _sum_slots(s_st_map, groups), _sum_slots(s_tk_map, groups)
                    ovf_steps, ovf_toks, has_ovf = [a + b for a, b in zip(ovf_steps, st_arr)], [a + b for a, b in zip(ovf_toks, tk_arr)], True
                act_rank += 1
            else:
                s["shade_idx"], s["shade_count"] = -1, shade_cap
        if has_ovf:
            pb["overflow_sessions_series"] = {"steps_series": ovf_steps, "tokens_series": ovf_toks, "shade_idx": 11, "shade_count": shade_cap}
        pb["active_sessions_count"] = act_cnt
        top_projects.append(pb)

    other_projects: dict[str, Any] | None = None
    if len(active_projs) > 10:
        ovf_projs = active_projs[10:]
        o_s1_st, o_s1_tk, o_sessions, o_handoffs = {}, {}, [], []
        o_win_st = o_win_tk = o_run = o_pin = o_stg = o_inw = o_sup = 0
        for op in ovf_projs:
            o_win_st, o_win_tk, o_run, o_pin = o_win_st + op["window_steps"], o_win_tk + op["window_tokens"], o_run + op["running_count"], o_pin + op["pinned_count"]
            o_stg, o_inw, o_sup = o_stg + op["staged_count"], o_inw + op["in_work_handoff_count"], o_sup + op["superseded_count"]
            o_handoffs.extend(op.get("staged_handoffs") or [])
            for sk, sv in op.pop("_s1_steps").items():
                o_s1_st[sk] = o_s1_st.get(sk, 0) + sv
            for sk, sv in op.pop("_s1_toks").items():
                o_s1_tk[sk] = o_s1_tk.get(sk, 0) + sv
            for s in op["sessions"]:
                s.pop("_s1_steps", None)
                s.pop("_s1_toks", None)
                s["share_pct"] = round((s["window_steps"] / tot_win_steps) * 100.0, 1)
                o_sessions.append(s)
        o_sessions.sort(key=lambda s: (-s["window_steps"], not s["is_running"], -s["step_count"]))
        other_projects = {
            "project_id": "__other_projects__", "project_name": "Other Projects", "is_rollup": True, "color_slot": 10,
            "projects_count": len(ovf_projs), "running_count": o_run, "pinned_count": o_pin,
            "staged_count": o_stg, "in_work_handoff_count": o_inw, "superseded_count": o_sup, "staged_handoffs": o_handoffs,
            "window_steps": o_win_st, "window_tokens": o_win_tk,
            "share_pct": round((o_win_st / tot_win_steps) * 100.0, 1), "steps_series": _sum_slots(o_s1_st, groups), "tokens_series": _sum_slots(o_s1_tk, groups), "sessions": o_sessions,
        }

    for ip in idle_projs:
        ip.pop("_s1_steps", None)
        ip.pop("_s1_toks", None)
        ip["share_pct"] = 0.0
        for s in ip["sessions"]:
            s.pop("_s1_steps", None)
            s.pop("_s1_toks", None)
            s["share_pct"] = 0.0

    return {
        "resolution": res_lbl, "step_hours": step_h,
        "velocity_series": {"dates": labels, "step_hours": step_h, "values": vel_steps, "token_values": vel_toks, "resolution": res_lbl},
        "model_series": {"keys": list(MODEL_KEYS), "dates": labels, "step_hours": step_h, "layers": mod_layers, "token_layers": mod_tok_layers, "resolution": res_lbl},
        "subagent_series": {"keys": sub_keys, "dates": labels, "step_hours": step_h, "layers": sub_layers, "token_layers": sub_tok_layers, "resolution": res_lbl},
        "workspace_series": {"keys": ws_keys, "dates": labels, "step_hours": step_h, "layers": ws_layers, "resolution": res_lbl},
        "project_hierarchy": {"dates": labels, "step_hours": step_h, "resolution": res_lbl, "active_projects_count": len(active_projs), "idle_projects_count": len(idle_projs), "top_projects": top_projects, "other_projects": other_projects, "idle_projects": idle_projs},
    }
