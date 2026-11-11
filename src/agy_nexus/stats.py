#!/usr/bin/env python3
"""
agy-nexus-mcp — Usage, Quota, 1h Adaptive Stacked Series, Token Metering & Three-Tier ASCII Engine (v2.6.0)
"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from agy_nexus.ascii_default import render_ascii_default, render_ascii_quick
from agy_nexus.ascii_rich import render_ascii_rich
from . import __version__
from .code_health import get_code_health_summary
from agy_nexus.stats_series import (
    MODEL_SHORT_LABELS,
    build_series_and_project_hierarchy,
    load_projects_meta,
    resolve_root_conversation,
    resolve_subagent_model,
)
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
    to_1h_slot,
    to_4h_slot,
)

__all__ = [
    "CACHE_VERSION", "MAX_WIRE_RING", "MODEL_TARGET_ALLOCATION", "WIRE_TELEMETRY_RING",
    "build_nexus_stats_bundle", "classify_model_key", "detect_product_name",
    "extract_pending_approval", "get_live_quota_and_pool_status", "get_wire_telemetry_summary",
    "record_wire_telemetry", "render_ascii_default", "render_ascii_quick",
    "render_ascii_rich", "render_ascii_stats", "to_4h_slot",
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
    brain_dir: Path | None = None, db_file: Path | None = None, agy_config_dir: Path | None = None,
    bg_dir: Path | None = None, period: str = "last_90d", *, style: str = "default",
    data_dir: Path | None = None, config_dir: Path | None = None,
) -> dict[str, Any]:
    """Build complete multi-window telemetry, heatmap, adaptive stacked series, canonical project hierarchy & ASCII reports."""
    base_data = data_dir or Path.home() / ".gemini/antigravity"
    brain_dir = brain_dir or (base_data / "brain")
    db_file = db_file or (base_data / "conversation_summaries.db")
    agy_config_dir = agy_config_dir or config_dir or (Path.home() / ".gemini/config")
    bg_dir = bg_dir or (base_data / "sidecar_data/ag-bridge-bg")
    now_loc = datetime.now(DISPLAY_TZ)
    today = now_loc.date()
    pk = (period or "last_90d").strip().lower()
    if pk in ("current_month", "this_month", "mtd"):
        pk, start_d, end_d, p_label = "current_month", today.replace(day=1), today, f"This Month — MTD ({today.strftime('%b %Y')})"
    elif pk == "last_month":
        end_d = today.replace(day=1) - timedelta(days=1)
        start_d, p_label = end_d.replace(day=1), f"Last Month ({end_d.strftime('%b %Y')})"
    elif pk in ("last_year", "rolling_52w", "52w"):
        pk, start_d, end_d, p_label = "last_year", today - timedelta(days=363), today, "Rolling 52 Weeks"
    elif pk == "ytd":
        start_d, end_d, p_label = today.replace(month=1, day=1), today, f"Year to Date ({today.year})"
    else:
        pk, start_d, end_d, p_label = "last_90d", today - timedelta(days=89), today, "Rolling 90 Days"

    s_iso, e_iso = start_d.strftime("%Y-%m-%d"), end_d.strftime("%Y-%m-%d")
    quota_info = get_live_quota_and_pool_status(base_data, agy_config_dir)
    main_info = quota_info.get("active_mainchat_model") or {}
    main_mk, main_switch_date = str(main_info.get("model_key") or "argon_pro"), str(main_info.get("state_updated_date") or "")

    conv_cache = scan_transcript_stats(brain_dir, bg_dir)
    projects_map = load_projects_meta(agy_config_dir)
    parent_model_map = {cid: str(cd.get("last_conv_model") or "") for cid, cd in conv_cache.items() if cd.get("last_conv_model")}
    db_convs: dict[str, dict[str, Any]] = {}
    if db_file.exists():
        try:
            conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True, timeout=3.0)
            conn.row_factory = sqlite3.Row
            cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(conversation_summaries)").fetchall()}
            proj_col = ", project_id" if "project_id" in cols else ""
            rows = conn.execute(f"SELECT conversation_id, title, step_count, last_modified_time, workspace_uris, status, parent_conversation_id, agent_name{proj_col} FROM conversation_summaries").fetchall()
            conn.close()
            for r in rows:
                cid, parent_id, agent_name = str(r["conversation_id"]), str(r["parent_conversation_id"] or ""), str(r["agent_name"] or "").strip()
                uris = json.loads(r["workspace_uris"] or "[]") if isinstance(r["workspace_uris"], str) and r["workspace_uris"].startswith("[") else []
                title_str = str(r["title"] or cid[:8])
                pid_val = str(r["project_id"] or "") if "project_id" in cols else ""
                db_convs[cid] = {"title": title_str, "step_count": int(r["step_count"] or 0), "last_modified": str(r["last_modified_time"] or ""), "workspace": _pick_primary_workspace(uris, title_str), "status": str(r["status"] or "IDLE"), "is_subagent": bool(parent_id), "parent_id": parent_id, "agent_name": agent_name or "subagent", "project_id": pid_val}
            for cid, info in db_convs.items():
                if info["parent_id"] and info["parent_id"] in db_convs:
                    p_obj = db_convs[info["parent_id"]]
                    if p_obj.get("workspace"): info["workspace"] = p_obj["workspace"]
                    if p_obj.get("project_id") and not info.get("project_id"): info["project_id"] = p_obj["project_id"]
        except Exception:
            pass

    subagent_roles: dict[str, dict[str, Any]] = {}
    role_model_votes: dict[str, dict[str, int]] = {}
    role_inherited: dict[str, bool] = {}
    model_totals = {"carbon": 0, "argon_pro": 0, "flash": 0, "claude_partner": 0, "gpt_oss": 0}
    model_tokens = {"carbon": 0, "argon_pro": 0, "flash": 0, "claude_partner": 0, "gpt_oss": 0}
    daily_steps, daily_tools, daily_tokens, daily_sessions = {}, {}, {}, {}
    s1_tot_steps, s1_tot_toks, ws_map = {}, {}, {}
    s1_mod_steps: dict[str, dict[str, int]] = {mk: {} for mk in model_totals}
    s1_mod_toks: dict[str, dict[str, int]] = {mk: {} for mk in model_totals}
    s1_sub_steps: dict[str, dict[str, int]] = {}
    s1_sub_toks: dict[str, dict[str, int]] = {}
    s1_ws_steps: dict[str, dict[str, int]] = {}
    root_sess_stats: dict[str, dict[str, Any]] = {}
    active_parent_convs = 0

    for cid, cdata in conv_cache.items():
        meta = db_convs.get(cid, {})
        is_sub, agent_role = bool(meta.get("is_subagent")), str(meta.get("agent_name") or "subagent")
        root_cid = resolve_root_conversation(cid, db_convs) if is_sub else cid
        root_meta = db_convs.get(root_cid, meta)
        ws_name = normalize_workspace_name(root_meta.get("workspace") or meta.get("workspace") or "") or "unassigned"
        win_steps, win_toks = 0, 0
        for ds, cnt in (cdata.get("day_steps") or {}).items():
            daily_steps[ds] = daily_steps.get(ds, 0) + cnt
            daily_sessions.setdefault(ds, set()).add(root_cid)
            if s_iso <= ds <= e_iso: win_steps += cnt
        for ds, tok_c in (cdata.get("day_tokens") or {}).items():
            daily_tokens[ds] = daily_tokens.get(ds, 0) + tok_c
            if s_iso <= ds <= e_iso: win_toks += tok_c
        for ds, tcnt in (cdata.get("day_tools") or {}).items():
            daily_tools[ds] = daily_tools.get(ds, 0) + tcnt

        r_stat = root_sess_stats.setdefault(root_cid, {"win_steps": 0, "win_tokens": 0, "sub_runs": 0, "s1_steps": {}, "s1_toks": {}})
        r_stat["win_steps"], r_stat["win_tokens"] = r_stat["win_steps"] + win_steps, r_stat["win_tokens"] + win_toks
        if is_sub and win_steps > 0: r_stat["sub_runs"] += 1

        s1_st_src = cdata.get("slot_1h_steps") or cdata.get("slot_steps") or {}
        s1_tk_src = cdata.get("slot_1h_tokens") or {}
        for sl_k, sl_cnt in s1_st_src.items():
            if s_iso <= sl_k[:10] <= e_iso:
                s1_tot_steps[sl_k] = s1_tot_steps.get(sl_k, 0) + sl_cnt
                s1_ws_steps.setdefault(ws_name, {})[sl_k] = s1_ws_steps.get(ws_name, {}).get(sl_k, 0) + sl_cnt
                r_stat["s1_steps"][sl_k] = r_stat["s1_steps"].get(sl_k, 0) + sl_cnt
                if is_sub:
                    s1_sub_steps.setdefault(agent_role, {})[sl_k] = s1_sub_steps.get(agent_role, {}).get(sl_k, 0) + sl_cnt
                    smk, _ = resolve_subagent_model(agent_role, root_cid, parent_model_map, main_mk, main_switch_date, sl_k)
                    s1_mod_steps[smk][sl_k] = s1_mod_steps[smk].get(sl_k, 0) + sl_cnt
        for sl_k, sl_tk in s1_tk_src.items():
            if s_iso <= sl_k[:10] <= e_iso:
                s1_tot_toks[sl_k] = s1_tot_toks.get(sl_k, 0) + sl_tk
                r_stat["s1_toks"][sl_k] = r_stat["s1_toks"].get(sl_k, 0) + sl_tk
                if is_sub:
                    s1_sub_toks.setdefault(agent_role, {})[sl_k] = s1_sub_toks.get(agent_role, {}).get(sl_k, 0) + sl_tk
                    smk, _ = resolve_subagent_model(agent_role, root_cid, parent_model_map, main_mk, main_switch_date, sl_k)
                    s1_mod_toks[smk][sl_k] = s1_mod_toks[smk].get(sl_k, 0) + sl_tk
        if not is_sub:
            for sl_k, m_dict in (cdata.get("slot_1h_models") or {}).items():
                if s_iso <= sl_k[:10] <= e_iso and isinstance(m_dict, dict):
                    for mk, mv in m_dict.items(): s1_mod_steps.setdefault(mk, {})[sl_k] = s1_mod_steps.get(mk, {}).get(sl_k, 0) + int(mv)
            for sl_k, mt_dict in (cdata.get("slot_1h_model_tokens") or {}).items():
                if s_iso <= sl_k[:10] <= e_iso and isinstance(mt_dict, dict):
                    for mk, mtv in mt_dict.items(): s1_mod_toks.setdefault(mk, {})[sl_k] = s1_mod_toks.get(mk, {}).get(sl_k, 0) + int(mtv)

        for ds, dm_map in (cdata.get("day_models") or {}).items():
            if s_iso <= ds <= e_iso and isinstance(dm_map, dict):
                if is_sub:
                    smk, is_inh = resolve_subagent_model(agent_role, root_cid, parent_model_map, main_mk, main_switch_date, ds)
                    c_sum = sum(int(v) for v in dm_map.values())
                    model_totals[smk] = model_totals.get(smk, 0) + c_sum
                    role_model_votes.setdefault(agent_role, {})[smk] = role_model_votes.get(agent_role, {}).get(smk, 0) + c_sum
                    if is_inh: role_inherited[agent_role] = True
                else:
                    for mk, mval in dm_map.items(): model_totals[mk] = model_totals.get(mk, 0) + int(mval)
        for ds, dtk_map in (cdata.get("day_model_tokens") or {}).items():
            if s_iso <= ds <= e_iso and isinstance(dtk_map, dict):
                if is_sub:
                    smk, _ = resolve_subagent_model(agent_role, root_cid, parent_model_map, main_mk, main_switch_date, ds)
                    model_tokens[smk] = model_tokens.get(smk, 0) + sum(int(v) for v in dtk_map.values())
                else:
                    for mk, mtok in dtk_map.items(): model_tokens[mk] = model_tokens.get(mk, 0) + int(mtok)

        if win_steps > 0:
            we = ws_map.setdefault(ws_name, {"workspace": ws_name, "sessions": 0, "steps": 0, "tokens": 0})
            if not is_sub:
                we["sessions"], active_parent_convs = we["sessions"] + 1, active_parent_convs + 1
            else:
                rec = subagent_roles.setdefault(agent_role, {"runs": 0, "steps": 0, "tokens": 0})
                rec["runs"], rec["steps"], rec["tokens"] = rec["runs"] + 1, rec["steps"] + win_steps, rec["tokens"] + win_toks
            we["steps"], we["tokens"] = we["steps"] + win_steps, we["tokens"] + win_toks

    for cid, meta in db_convs.items():
        if meta.get("is_subagent") and cid not in conv_cache and int(meta.get("step_count") or 0) > 0:
            d_str, s1_str, _ = to_1h_slot(str(meta.get("last_modified") or ""), time.time())
            if len(d_str) == 10 and s_iso <= d_str <= e_iso:
                role, st_c = str(meta.get("agent_name") or "subagent"), int(meta["step_count"])
                tok_est = st_c * 380
                root_cid = resolve_root_conversation(cid, db_convs)
                ws_n = normalize_workspace_name((db_convs.get(root_cid) or meta).get("workspace") or "") or "unassigned"
                smk, is_inh = resolve_subagent_model(role, root_cid, parent_model_map, main_mk, main_switch_date, d_str)
                daily_steps[d_str], daily_tokens[d_str] = daily_steps.get(d_str, 0) + st_c, daily_tokens.get(d_str, 0) + tok_est
                s1_tot_steps[s1_str], s1_tot_toks[s1_str] = s1_tot_steps.get(s1_str, 0) + st_c, s1_tot_toks.get(s1_str, 0) + tok_est
                s1_sub_steps.setdefault(role, {})[s1_str] = s1_sub_steps.get(role, {}).get(s1_str, 0) + st_c
                s1_sub_toks.setdefault(role, {})[s1_str] = s1_sub_toks.get(role, {}).get(s1_str, 0) + tok_est
                s1_ws_steps.setdefault(ws_n, {})[s1_str] = s1_ws_steps.get(ws_n, {}).get(s1_str, 0) + st_c
                s1_mod_steps[smk][s1_str] = s1_mod_steps[smk].get(s1_str, 0) + st_c
                s1_mod_toks[smk][s1_str] = s1_mod_toks[smk].get(s1_str, 0) + tok_est
                r_stat = root_sess_stats.setdefault(root_cid, {"win_steps": 0, "win_tokens": 0, "sub_runs": 0, "s1_steps": {}, "s1_toks": {}})
                r_stat["win_steps"], r_stat["win_tokens"], r_stat["sub_runs"] = r_stat["win_steps"] + st_c, r_stat["win_tokens"] + tok_est, r_stat["sub_runs"] + 1
                r_stat["s1_steps"][s1_str], r_stat["s1_toks"][s1_str] = r_stat["s1_steps"].get(s1_str, 0) + st_c, r_stat["s1_toks"].get(s1_str, 0) + tok_est
                rec = subagent_roles.setdefault(role, {"runs": 0, "steps": 0, "tokens": 0})
                rec["runs"], rec["steps"], rec["tokens"] = rec["runs"] + 1, rec["steps"] + st_c, rec["tokens"] + tok_est
                we = ws_map.setdefault(ws_n, {"workspace": ws_n, "sessions": 0, "steps": 0, "tokens": 0})
                we["steps"], we["tokens"] = we["steps"] + st_c, we["tokens"] + tok_est
                model_totals[smk], model_tokens[smk] = model_totals.get(smk, 0) + st_c, model_tokens.get(smk, 0) + tok_est
                role_model_votes.setdefault(role, {})[smk] = role_model_votes.get(role, {}).get(smk, 0) + st_c
                if is_inh: role_inherited[role] = True

    cur, win_steps_sum, win_tools_sum, win_tokens_sum, active_days, peak = start_d, 0, 0, 0, 0, {"date": "", "steps": 0}
    while cur <= end_d:
        ds = cur.strftime("%Y-%m-%d")
        st_c, tl_c, tk_c = daily_steps.get(ds, 0), daily_tools.get(ds, 0), daily_tokens.get(ds, 0)
        win_steps_sum, win_tools_sum, win_tokens_sum = win_steps_sum + st_c, win_tools_sum + tl_c, win_tokens_sum + tk_c
        if st_c > 0: active_days += 1
        if st_c >= peak["steps"]: peak = {"date": ds, "steps": st_c}
        cur += timedelta(days=1)

    heat_start_d, heat_end_d = (start_d, ((today.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1))) if pk == "current_month" else (start_d, end_d)
    heat_start_d -= timedelta(days=heat_start_d.weekday())
    global_nz = sorted(v for v in daily_steps.values() if v > 0)
    q1, q2, q3 = (global_nz[max(0, int(len(global_nz) * 0.25) - 1)], global_nz[max(0, int(len(global_nz) * 0.50) - 1)], global_nz[max(0, int(len(global_nz) * 0.75) - 1)]) if global_nz else (25, 100, 300)
    heatmap_series, h_cur = [], heat_start_d
    while h_cur <= heat_end_d:
        ds, is_fut = h_cur.strftime("%Y-%m-%d"), h_cur > today
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
        votes = role_model_votes.get(rk) or {}
        dom_mk = max(votes.items(), key=lambda kv: kv[1])[0] if votes else resolve_subagent_model(rk, "", parent_model_map, main_mk, main_switch_date, e_iso)[0]
        dom_lbl = MODEL_SHORT_LABELS.get(dom_mk, dom_mk) + (" (inherit)" if role_inherited.get(rk) else "")
        rv["tok_per_day"], rv["tok_per_week"], rv["share_pct"] = round(tk / act_d), round(tk / act_w), round((st_s / sa_step_sum) * 100.0, 1)
        rv["dominant_model_key"], rv["dominant_model_label"] = dom_mk, dom_lbl
        subagent_list.append({"role": rk, **rv})

    chart_days = [x for x in heatmap_series if not x.get("future") and s_iso <= x["date"] <= e_iso]
    first_act_idx = next((idx for idx, x in enumerate(chart_days) if x["steps"] > 0), 0)
    trimmed_days = [x["date"] for x in (chart_days[max(0, first_act_idx - 1) :] if len(chart_days) > 7 else chart_days)]

    from agy_nexus.session_tree import build_project_session_tree
    tree_bundle = build_project_session_tree(active_only=False, limit=180, bg_dir=bg_dir)
    series_pkg = build_series_and_project_hierarchy(
        period_key=pk, trimmed_days=trimmed_days, today_iso=today.strftime("%Y-%m-%d"), now_hour=now_loc.hour,
        s1_tot_steps=s1_tot_steps, s1_tot_toks=s1_tot_toks, s1_mod_steps=s1_mod_steps, s1_mod_toks=s1_mod_toks,
        s1_sub_steps=s1_sub_steps, s1_sub_toks=s1_sub_toks, s1_ws_steps=s1_ws_steps,
        all_ws_list=all_ws_list, subagent_list=subagent_list, root_sess_stats=root_sess_stats,
        db_convs=db_convs, projects_map=projects_map, tree_bundle=tree_bundle,
    )

    targets, tot_calls = quota_info["target_model_allocation"], max(1, sum(model_totals.values()))
    model_comp = []
    for mk in ("carbon", "argon_pro", "flash", "claude_partner", "gpt_oss"):
        tm, ac = targets.get(mk, {"label": mk, "pool": "Unknown", "target_pct": 0.0}), model_totals.get(mk, 0)
        ap, tp = round((ac / tot_calls) * 100.0, 1), float(tm["target_pct"])
        dp = round(ap - tp, 1)
        model_comp.append({"model_key": mk, "label": tm["label"], "pool": tm["pool"], "actual_calls": ac, "est_tokens": model_tokens.get(mk, 0), "actual_pct": ap, "target_pct": tp, "delta_pct": dp, "status": "ON_TARGET" if abs(dp) <= 12.0 else ("OVER_TARGET" if dp > 12.0 else "UNDER_TARGET")})

    parent_cnt = active_parent_convs or sum(1 for v in db_convs.values() if not v.get("is_subagent"))
    kpis_obj = {"total_conversations": parent_cnt, "total_subagents_spawned": sum(v["runs"] for v in subagent_roles.values()), "window_steps": win_steps_sum, "period_steps": win_steps_sum, "window_tool_calls": win_tools_sum, "period_tool_calls": win_tools_sum, "window_tokens": win_tokens_sum, "active_days": active_days, "avg_daily_steps": round(win_steps_sum / act_d, 1), "tok_per_day": round(win_tokens_sum / act_d), "tok_per_week": round(win_tokens_sum / act_w), "peak_day": peak}
    res_label = series_pkg["resolution"]
    bundle = {
        "server": "agy-nexus-mcp", "version": __version__, "generated_at": now_loc.isoformat(), "style": (style or "default").strip().lower(),
        "period": {"key": pk, "label": p_label, "start_date": s_iso, "end_date": e_iso, "total_days": len([x for x in heatmap_series if x.get("in_window")]), "active_days": active_days, "resolution": res_label},
        "kpis": kpis_obj, "summary": kpis_obj, "quota_and_pools": quota_info, "model_usage_vs_target": model_comp, "subagent_role_breakdown": subagent_roles,
        "subagent_list": subagent_list, "all_workspaces": all_ws_list, "top_workspaces": all_ws_list[:10],
        "velocity_series": series_pkg["velocity_series"], "model_series": series_pkg["model_series"],
        "workspace_series": series_pkg["workspace_series"], "subagent_series": series_pkg["subagent_series"],
        "project_hierarchy": series_pkg["project_hierarchy"],
        "heatmap_series": heatmap_series, "wire_telemetry": get_wire_telemetry_summary(bg_dir, limit=15),
        "project_session_tree": tree_bundle, "routing_telemetry": tree_bundle.get("routing_telemetry", {}), "backup_321": tree_bundle.get("backup_321", {}),
        "code_health": get_code_health_summary(),
    }
    bundle["ascii_report_default"], bundle["ascii_report_quick"], bundle["ascii_report_rich"] = render_ascii_default(bundle), render_ascii_quick(bundle), render_ascii_rich(bundle)
    bundle["ascii_mobile_dashboard"] = bundle["ascii_mobile_report"] = render_ascii_stats(bundle, style=style)
    return bundle


get_quota_and_stats_bundle = build_nexus_stats_bundle
