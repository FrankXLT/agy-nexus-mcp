#!/usr/bin/env python3
"""
agy-nexus-mcp — Usage, Quota, Sub-Daily Stacked Series, Token Metering & Three-Tier ASCII Engine (v3.8)
"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from agy_nexus.ascii_default import render_ascii_default, render_ascii_quick
from agy_nexus.ascii_rich import render_ascii_rich
from agy_nexus.telemetry_scanner import (
    CACHE_VERSION,
    DISPLAY_TZ,
    MAX_WIRE_RING,
    MODEL_TARGET_ALLOCATION,
    WIRE_TELEMETRY_RING,
    classify_model_key,
    detect_product_name,
    extract_pending_approval,
    get_live_quota_and_pool_status,
    get_wire_telemetry_summary,
    normalize_workspace_name,
    record_wire_telemetry,
    scan_transcript_stats,
    to_4h_slot,
)

__all__ = [
    "CACHE_VERSION",
    "MAX_WIRE_RING",
    "MODEL_TARGET_ALLOCATION",
    "WIRE_TELEMETRY_RING",
    "build_nexus_stats_bundle",
    "extract_pending_approval",
    "get_live_quota_and_pool_status",
    "get_wire_telemetry_summary",
    "record_wire_telemetry",
    "render_ascii_default",
    "render_ascii_quick",
    "render_ascii_rich",
    "render_ascii_stats",
]

def _pick_primary_workspace(uris: list[str], title: str) -> str:
    if not uris:
        return ""
    cleaned = [str(u).replace("file://", "").rstrip("/") for u in uris if u]
    if len(cleaned) <= 1:
        return cleaned[0] if cleaned else ""
    t_low = (title or "").lower()
    if any(k in t_low for k in ("mcp", "antigravity", "nexus", "bridge")):
        for u in cleaned:
            if "antigravity-config" in u:
                return u
    for u in cleaned:
        bname = u.rsplit("/", 1)[-1].lower()
        if bname and bname in t_low:
            return u
    return cleaned[0]

def render_ascii_stats(bundle: dict[str, Any], style: str = "default") -> str:
    """Dispatch telemetry bundle to the requested ASCII style: 'default' (72c), 'quick' (40c), or 'rich' (76c)."""
    sk = (style or "default").strip().lower()
    if sk in ("quick", "mobile", "40", "compact"):
        return render_ascii_quick(bundle)
    if sk in ("rich", "tui", "76", "full"):
        return render_ascii_rich(bundle)
    return render_ascii_default(bundle)

def build_nexus_stats_bundle(
    brain_dir: Path | None = None,
    db_file: Path | None = None,
    agy_config_dir: Path | None = None,
    bg_dir: Path | None = None,
    period: str = "last_90d",
    *,
    style: str = "default",
    data_dir: Path | None = None,
    config_dir: Path | None = None,
) -> dict[str, Any]:
    """Build complete multi-window telemetry, heatmap, sub-daily stacked series, rolling rates & 3-tier ASCII reports."""
    base_data = data_dir or Path.home() / ".gemini/antigravity"
    brain_dir = brain_dir or (base_data / "brain")
    db_file = db_file or (base_data / "conversation_summaries.db")
    agy_config_dir = agy_config_dir or config_dir or (Path.home() / ".gemini/config")
    bg_dir = bg_dir or (base_data / "sidecar_data/ag-bridge-bg")
    now_loc = datetime.now(DISPLAY_TZ)
    today = now_loc.date()
    pk = (period or "last_90d").strip().lower()
    if pk in ("current_month", "this_month", "mtd"):
        pk = "current_month"
        start_d, end_d = today.replace(day=1), today
        p_label = f"This Month — MTD ({today.strftime('%b %Y')})"
    elif pk == "last_month":
        end_d = today.replace(day=1) - timedelta(days=1)
        start_d, p_label = end_d.replace(day=1), f"Last Month ({end_d.strftime('%b %Y')})"
    elif pk in ("last_year", "rolling_52w", "52w"):
        pk = "last_year"
        start_d, end_d, p_label = today - timedelta(days=363), today, "Rolling 52 Weeks"
    elif pk == "ytd":
        start_d, end_d, p_label = today.replace(month=1, day=1), today, f"Year to Date ({today.year})"
    else:
        pk, start_d, end_d, p_label = "last_90d", today - timedelta(days=89), today, "Rolling 90 Days"

    s_iso, e_iso = start_d.strftime("%Y-%m-%d"), end_d.strftime("%Y-%m-%d")
    conv_cache = scan_transcript_stats(brain_dir, bg_dir)
    db_convs: dict[str, dict[str, Any]] = {}
    subagent_roles: dict[str, dict[str, Any]] = {}
    model_totals = {"argon_pro": 0, "flash": 0, "claude_partner": 0, "gpt_oss": 0}
    model_tokens = {"argon_pro": 0, "flash": 0, "claude_partner": 0, "gpt_oss": 0}
    if db_file.exists():
        try:
            conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True, timeout=3.0)
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT conversation_id, title, step_count, last_modified_time, workspace_uris, status, parent_conversation_id, agent_name FROM conversation_summaries").fetchall()
            conn.close()
            for r in rows:
                cid, parent_id, agent_name = str(r["conversation_id"]), str(r["parent_conversation_id"] or ""), str(r["agent_name"] or "").strip()
                uris = json.loads(r["workspace_uris"] or "[]") if isinstance(r["workspace_uris"], str) and r["workspace_uris"].startswith("[") else []
                title_str = str(r["title"] or cid[:8])
                db_convs[cid] = {
                    "title": title_str, "step_count": int(r["step_count"] or 0), "last_modified": str(r["last_modified_time"] or ""),
                    "workspace": _pick_primary_workspace(uris, title_str), "status": str(r["status"] or "IDLE"),
                    "is_subagent": bool(parent_id), "parent_id": parent_id, "agent_name": agent_name or "subagent",
                }
            for cid, info in db_convs.items():
                if info["parent_id"] and info["parent_id"] in db_convs:
                    parent_ws = db_convs[info["parent_id"]].get("workspace", "")
                    if parent_ws:
                        info["workspace"] = parent_ws
        except Exception:
            pass

    chart_s_iso = s_iso
    daily_steps, daily_tools, daily_tokens, daily_sessions, slot_totals, ws_map, ws_slots, sub_slots = {}, {}, {}, {}, {}, {}, {}, {}
    active_parent_convs = 0
    for cid, cdata in conv_cache.items():
        meta = db_convs.get(cid, {})
        ws_name = normalize_workspace_name(meta.get("workspace") or "") or "unassigned"
        is_sub, agent_role = bool(meta.get("is_subagent")), str(meta.get("agent_name") or "subagent")
        win_steps, win_toks = 0, 0
        for ds, cnt in (cdata.get("day_steps") or {}).items():
            daily_steps[ds] = daily_steps.get(ds, 0) + cnt
            daily_sessions.setdefault(ds, set()).add(cid)
            if s_iso <= ds <= e_iso:
                win_steps += cnt
        for ds, tok_c in (cdata.get("day_tokens") or {}).items():
            daily_tokens[ds] = daily_tokens.get(ds, 0) + tok_c
            if s_iso <= ds <= e_iso:
                win_toks += tok_c
        for sl_k, sl_cnt in (cdata.get("slot_steps") or {}).items():
            if chart_s_iso <= sl_k[:10] <= e_iso:
                slot_totals[sl_k] = slot_totals.get(sl_k, 0) + sl_cnt
                ws_slots.setdefault(ws_name, {})[sl_k] = ws_slots.get(ws_name, {}).get(sl_k, 0) + sl_cnt
                if is_sub:
                    sub_slots.setdefault(agent_role, {})[sl_k] = sub_slots.get(agent_role, {}).get(sl_k, 0) + sl_cnt
        for ds, tcnt in (cdata.get("day_tools") or {}).items():
            daily_tools[ds] = daily_tools.get(ds, 0) + tcnt
        for ds, dm_map in (cdata.get("day_models") or {}).items():
            if s_iso <= ds <= e_iso and isinstance(dm_map, dict):
                for mk, mval in dm_map.items():
                    model_totals[mk] = model_totals.get(mk, 0) + int(mval)
        for ds, dtk_map in (cdata.get("day_model_tokens") or {}).items():
            if s_iso <= ds <= e_iso and isinstance(dtk_map, dict):
                for mk, mtok in dtk_map.items():
                    model_tokens[mk] = model_tokens.get(mk, 0) + int(mtok)
        if win_steps > 0:
            we = ws_map.setdefault(ws_name, {"workspace": ws_name, "sessions": 0, "steps": 0, "tokens": 0})
            if not is_sub:
                we["sessions"] += 1
                active_parent_convs += 1
            else:
                rec = subagent_roles.setdefault(agent_role, {"runs": 0, "steps": 0, "tokens": 0})
                rec["runs"] += 1
                rec["steps"] += win_steps
                rec["tokens"] += win_toks
            we["steps"] += win_steps
            we["tokens"] += win_toks

    for cid, meta in db_convs.items():
        if meta.get("is_subagent") and cid not in conv_cache and int(meta.get("step_count") or 0) > 0:
            d_str, sl_str = to_4h_slot(str(meta.get("last_modified") or ""), time.time())
            if len(d_str) == 10 and s_iso <= d_str <= e_iso:
                role, st_c = str(meta.get("agent_name") or "subagent"), int(meta["step_count"])
                tok_est = st_c * 380
                daily_steps[d_str] = daily_steps.get(d_str, 0) + st_c
                daily_tokens[d_str] = daily_tokens.get(d_str, 0) + tok_est
                slot_totals[sl_str] = slot_totals.get(sl_str, 0) + st_c
                rec = subagent_roles.setdefault(role, {"runs": 0, "steps": 0, "tokens": 0})
                rec["runs"] += 1
                rec["steps"] += st_c
                rec["tokens"] += tok_est
                sub_slots.setdefault(role, {})[sl_str] = sub_slots.get(role, {}).get(sl_str, 0) + st_c
                ws_n = normalize_workspace_name(meta.get("workspace") or "") or "unassigned"
                ws_slots.setdefault(ws_n, {})[sl_str] = ws_slots.get(ws_n, {}).get(sl_str, 0) + st_c
                we = ws_map.setdefault(ws_n, {"workspace": ws_n, "sessions": 0, "steps": 0, "tokens": 0})
                we["steps"] += st_c
                we["tokens"] += tok_est
                mk = classify_model_key("", role)
                model_totals[mk] = model_totals.get(mk, 0) + st_c
                model_tokens[mk] = model_tokens.get(mk, 0) + tok_est

    cur, win_steps_sum, win_tools_sum, win_tokens_sum, active_days, peak = start_d, 0, 0, 0, 0, {"date": "", "steps": 0}
    while cur <= end_d:
        ds = cur.strftime("%Y-%m-%d")
        st_c, tl_c, tk_c = daily_steps.get(ds, 0), daily_tools.get(ds, 0), daily_tokens.get(ds, 0)
        win_steps_sum, win_tools_sum, win_tokens_sum = win_steps_sum + st_c, win_tools_sum + tl_c, win_tokens_sum + tk_c
        if st_c > 0:
            active_days += 1
        if st_c >= peak["steps"]:
            peak = {"date": ds, "steps": st_c}
        cur += timedelta(days=1)

    if pk == "current_month":
        nxt_m = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
        heat_start_d, heat_end_d = start_d, nxt_m - timedelta(days=1)
    else:
        heat_start_d, heat_end_d = start_d, end_d
    heat_start_d -= timedelta(days=heat_start_d.weekday())

    global_nz = sorted(v for v in daily_steps.values() if v > 0)
    q1, q2, q3 = (global_nz[max(0, int(len(global_nz) * 0.25) - 1)], global_nz[max(0, int(len(global_nz) * 0.50) - 1)], global_nz[max(0, int(len(global_nz) * 0.75) - 1)]) if global_nz else (25, 100, 300)
    heatmap_series, h_cur = [], heat_start_d
    while h_cur <= heat_end_d:
        ds = h_cur.strftime("%Y-%m-%d")
        is_fut = h_cur > today
        st_c = 0 if is_fut else daily_steps.get(ds, 0)
        lvl = -1 if is_fut else (0 if st_c == 0 else (1 if st_c <= q1 else (2 if st_c <= q2 else (3 if st_c <= q3 else 4))))
        heatmap_series.append({"date": ds, "weekday": h_cur.weekday(), "steps": st_c, "tools": 0 if is_fut else daily_tools.get(ds, 0), "tokens": 0 if is_fut else daily_tokens.get(ds, 0), "sessions": 0 if is_fut else len(daily_sessions.get(ds, set())), "level": lvl, "future": is_fut, "in_window": start_d <= h_cur <= end_d})
        h_cur += timedelta(days=1)

    act_d, act_w = max(1, active_days), max(1.0, max(1, active_days) / 7.0)
    ws_step_sum = max(1, sum(int(w.get("steps", 0)) for w in ws_map.values()))
    all_ws_list = sorted(ws_map.values(), key=lambda x: x["steps"], reverse=True)
    for w in all_ws_list:
        tk, st_w = int(w.get("tokens", 0)), int(w.get("steps", 0))
        w["tok_per_day"], w["tok_per_week"], w["share_pct"] = round(tk / act_d), round(tk / act_w), round((st_w / ws_step_sum) * 100.0, 1)

    sa_step_sum = max(1, sum(int(v.get("steps", 0)) for v in subagent_roles.values()))
    subagent_list = []
    for rk, rv in sorted(subagent_roles.items(), key=lambda kv: kv[1]["steps"], reverse=True):
        tk, st_s = int(rv.get("tokens", 0)), int(rv.get("steps", 0))
        rv["tok_per_day"], rv["tok_per_week"], rv["share_pct"] = round(tk / act_d), round(tk / act_w), round((st_s / sa_step_sum) * 100.0, 1)
        subagent_list.append({"role": rk, **rv})

    ws_keys = [w["workspace"] for w in all_ws_list[:5]]
    other_ws_keys = [w["workspace"] for w in all_ws_list[5:]]
    if other_ws_keys:
        ws_keys.append("other-projects")
    sub_keys = [s["role"] for s in subagent_list[:5]]
    other_sub_keys = [s["role"] for s in subagent_list[5:]]
    if other_sub_keys:
        sub_keys.append("other-subagents")

    chart_days = [x for x in heatmap_series if not x.get("future") and s_iso <= x["date"] <= e_iso]
    first_act_idx = next((idx for idx, x in enumerate(chart_days) if x["steps"] > 0), 0)
    trimmed_days = [x["date"] for x in (chart_days[max(0, first_act_idx - 1) :] if len(chart_days) > 7 else chart_days)]
    today_iso, cur_slot_hr = today.strftime("%Y-%m-%d"), (now_loc.hour // 4) * 4
    all_4h_slots = [f"{d_iso}T{hr:02d}" for d_iso in trimmed_days for hr in (0, 4, 8, 12, 16, 20) if d_iso < today_iso or (d_iso == today_iso and hr <= cur_slot_hr)]
    slot_group = 1 if len(all_4h_slots) <= 150 else (2 if len(all_4h_slots) <= 320 else (3 if len(all_4h_slots) <= 560 else 6))
    resolution_label = f"{slot_group * 4}h sub-daily" if slot_group < 6 else "daily"
    chart_labels = [f"{all_4h_slots[i : i + slot_group][-1][:10]} {all_4h_slots[i : i + slot_group][-1][11:13]}:00" if slot_group < 6 else all_4h_slots[i : i + slot_group][-1][:10] for i in range(0, len(all_4h_slots), slot_group)]
    vel_points = [sum(slot_totals.get(s, 0) for s in all_4h_slots[i : i + slot_group]) for i in range(0, len(all_4h_slots), slot_group)]
    ws_layers: dict[str, list[int]] = {}
    for k in ws_keys:
        ws_layers[k] = [sum(sum(ws_slots.get(ok, {}).get(s, 0) for ok in other_ws_keys) for s in all_4h_slots[i : i + slot_group]) for i in range(0, len(all_4h_slots), slot_group)] if k == "other-projects" else [sum(ws_slots.get(k, {}).get(s, 0) for s in all_4h_slots[i : i + slot_group]) for i in range(0, len(all_4h_slots), slot_group)]
    sub_layers: dict[str, list[int]] = {}
    for k in sub_keys:
        sub_layers[k] = [sum(sum(sub_slots.get(ok, {}).get(s, 0) for ok in other_sub_keys) for s in all_4h_slots[i : i + slot_group]) for i in range(0, len(all_4h_slots), slot_group)] if k == "other-subagents" else [sum(sub_slots.get(k, {}).get(s, 0) for s in all_4h_slots[i : i + slot_group]) for i in range(0, len(all_4h_slots), slot_group)]

    quota_info = get_live_quota_and_pool_status(agy_config_dir)
    targets, tot_calls = quota_info["target_model_allocation"], max(1, sum(model_totals.values()))
    model_comp = []
    for mk in ("argon_pro", "flash", "claude_partner", "gpt_oss"):
        tm, ac = targets.get(mk, {"label": mk, "pool": "Unknown", "target_pct": 0.0}), model_totals.get(mk, 0)
        ap, tp = round((ac / tot_calls) * 100.0, 1), float(tm["target_pct"])
        dp = round(ap - tp, 1)
        model_comp.append({"model_key": mk, "label": tm["label"], "pool": tm["pool"], "actual_calls": ac, "est_tokens": model_tokens.get(mk, 0), "actual_pct": ap, "target_pct": tp, "delta_pct": dp, "status": "ON_TARGET" if abs(dp) <= 12.0 else ("OVER_TARGET" if dp > 12.0 else "UNDER_TARGET")})

    from agy_nexus.session_tree import build_project_session_tree
    tree_bundle = build_project_session_tree(active_only=False, limit=30, bg_dir=bg_dir)
    parent_cnt = active_parent_convs or sum(1 for v in db_convs.values() if not v.get("is_subagent"))
    kpis_obj = {"total_conversations": parent_cnt, "total_subagents_spawned": sum(v["runs"] for v in subagent_roles.values()), "window_steps": win_steps_sum, "period_steps": win_steps_sum, "window_tool_calls": win_tools_sum, "period_tool_calls": win_tools_sum, "window_tokens": win_tokens_sum, "active_days": active_days, "avg_daily_steps": round(win_steps_sum / act_d, 1), "tok_per_day": round(win_tokens_sum / act_d), "tok_per_week": round(win_tokens_sum / act_w), "peak_day": peak}
    bundle = {
        "server": "agy-nexus-mcp", "version": "3.8.0", "generated_at": now_loc.isoformat(), "style": (style or "default").strip().lower(),
        "period": {"key": pk, "label": p_label, "start_date": s_iso, "end_date": e_iso, "total_days": len([x for x in heatmap_series if x.get("in_window")]), "active_days": active_days, "resolution": resolution_label},
        "kpis": kpis_obj, "summary": kpis_obj, "quota_and_pools": quota_info, "model_usage_vs_target": model_comp, "subagent_role_breakdown": subagent_roles,
        "subagent_list": subagent_list, "all_workspaces": all_ws_list, "top_workspaces": all_ws_list[:10],
        "velocity_series": {"dates": chart_labels, "values": vel_points, "resolution": resolution_label},
        "workspace_series": {"keys": ws_keys, "dates": chart_labels, "layers": ws_layers, "resolution": resolution_label},
        "subagent_series": {"keys": sub_keys, "dates": chart_labels, "layers": sub_layers, "resolution": resolution_label},
        "heatmap_series": heatmap_series, "wire_telemetry": get_wire_telemetry_summary(bg_dir, limit=15),
        "project_session_tree": tree_bundle, "routing_telemetry": tree_bundle.get("routing_telemetry", {}), "backup_321": tree_bundle.get("backup_321", {}),
    }
    bundle["ascii_report_default"], bundle["ascii_report_quick"], bundle["ascii_report_rich"] = render_ascii_default(bundle), render_ascii_quick(bundle), render_ascii_rich(bundle)
    selected_ascii = render_ascii_stats(bundle, style=style)
    bundle["ascii_mobile_dashboard"] = selected_ascii
    bundle["ascii_mobile_report"] = selected_ascii
    return bundle

get_quota_and_stats_bundle = build_nexus_stats_bundle
