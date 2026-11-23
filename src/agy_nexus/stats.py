#!/usr/bin/env python3
"""
agy-nexus-mcp — Usage, Quota, 1h Adaptive Stacked Series, Token Metering & Three-Tier ASCII Engine (v2.7.0)
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from agy_nexus.ascii_default import render_ascii_default, render_ascii_quick
from agy_nexus.ascii_rich import render_ascii_rich
from . import __version__
from .code_health import get_code_health_summary
from agy_nexus.cost_ledger import (
    compute_hourly_whiskers,
    load_cost_ledger,
    merge_and_persist_cost_ledger,
    read_model_drift_status,
)
from agy_nexus.model_pricing import (
    build_billing_comparison,
    get_canonical_model_keys,
    get_model_specs_map,
    resolve_rate_epoch,
)
from agy_nexus.project_stats import (
    build_fleet_project_index,
    build_project_scope_payload,
    build_project_sessions_series,
    compact_project_hierarchy_sessions,
    filter_project_conversations,
    resolve_target_project_id,
)
from agy_nexus.retirement import is_session_retired
from agy_nexus.stats_aggregator import (
    fold_live_conversations,
    fold_orphaned_and_archived,
    init_agg_state,
    load_agent_target_map,
    load_db_conversations,
)
from agy_nexus.stats_metrics import (
    build_model_comparison_rows,
    build_subagent_list_rows,
    compute_trailing_24h_slots,
)
from agy_nexus.stats_series import (
    MODEL_SHORT_LABELS,
    build_series_and_project_hierarchy,
    load_projects_meta,
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


def _pick_primary_workspace(uris: list[str], title: str, project_id: str = "") -> str:
    from agy_nexus.sessions import pick_primary_workspace_uri
    return pick_primary_workspace_uri(uris, title, project_id=project_id)


def render_ascii_stats(bundle: dict[str, Any], style: str = "default") -> str:
    """Dispatch telemetry bundle to the requested ASCII style: 'default' (72c), 'quick' (40c), or 'rich' (76c)."""
    st = (style or "default").strip().lower()
    if st in ("quick", "compact", "narrow", "40", "mobile"):
        return render_ascii_quick(bundle)
    if st in ("rich", "wide", "desktop", "full", "76"):
        return render_ascii_rich(bundle)
    return render_ascii_default(bundle)


def _resolve_window_bounds(
    period: str, timeframe: str, horizon_mode: str, offset: int, anchor_date: str, today: date,
) -> tuple[date, date, str, str, str, str, date]:
    anchor = today
    if anchor_date:
        try:
            anchor = datetime.strptime(anchor_date.strip()[:10], "%Y-%m-%d").date()
        except Exception:
            anchor = today
    pk_raw = (period or "last_90d").strip().lower()
    if timeframe:
        tf, hm = timeframe.strip().lower(), horizon_mode.strip().lower() if horizon_mode else "to_date"
    elif pk_raw in ("current_month", "this_month", "mtd"):
        tf, hm = "month", "to_date"
    elif pk_raw == "last_month":
        tf, hm, offset = "month", "to_date", -1
    elif pk_raw in ("last_year", "rolling_52w", "52w"):
        tf, hm = "year", "rolling"
    elif pk_raw in ("ytd", "year"):
        tf, hm = "year", "to_date"
    elif pk_raw in ("quarter", "qtr"):
        tf, hm = "quarter", "to_date"
    else:
        tf, hm = "quarter", "rolling"
    hm = hm if hm in ("to_date", "rolling") else "to_date"
    tf = tf if tf in ("month", "quarter", "year") else "quarter"

    if hm == "to_date":
        if tf == "month":
            m_idx = anchor.year * 12 + (anchor.month - 1) + int(offset)
            ty, tm = m_idx // 12, (m_idx % 12) + 1
            start_d = date(ty, tm, 1)
            nm = m_idx + 1
            last_d = date(nm // 12, (nm % 12) + 1, 1) - timedelta(days=1)
            end_d = min(today, last_d) if (ty == today.year and tm == today.month) else last_d
            return start_d, end_d, start_d.strftime("%b %Y"), ("current_month" if (ty == today.year and tm == today.month) else f"month_{ty}_{tm:02d}"), tf, hm, anchor
        if tf == "quarter":
            q_idx = anchor.year * 4 + ((anchor.month - 1) // 3) + int(offset)
            ty, tq = q_idx // 4, (q_idx % 4) + 1
            sm = (tq - 1) * 3 + 1
            start_d = date(ty, sm, 1)
            em = sm + 2
            last_d = (date(ty + 1, 1, 1) if em == 12 else date(ty, em + 1, 1)) - timedelta(days=1)
            end_d = min(today, last_d) if (ty == today.year and ((today.month - 1) // 3 + 1) == tq) else last_d
            return start_d, end_d, f"{ty} Q{tq}", f"quarter_{ty}_q{tq}", tf, hm, anchor
        ty = anchor.year + int(offset)
        start_d, last_d = date(ty, 1, 1), date(ty, 12, 31)
        return start_d, (min(today, last_d) if ty == today.year else last_d), f"{ty}", ("ytd" if ty == today.year else f"year_{ty}"), tf, hm, anchor

    if tf == "month":
        end_d = min(today, anchor + timedelta(days=int(offset) * 30))
        start_d = end_d - timedelta(days=29)
        return start_d, end_d, f"Rolling 30D ({start_d.strftime('%b %d')}–{end_d.strftime('%b %d')})", "month_rolling", tf, hm, anchor
    if tf == "quarter":
        end_d = min(today, anchor + timedelta(days=int(offset) * 91))
        start_d = end_d - timedelta(days=90)
        p_lbl = "Rolling 90 Days" if int(offset) == 0 else f"Rolling 91D ({start_d.strftime('%b %d')}–{end_d.strftime('%b %d')})"
        return start_d, end_d, p_lbl, ("last_90d" if int(offset) == 0 else "quarter_rolling"), tf, hm, anchor
    end_d = min(today, anchor + timedelta(days=int(offset) * 364))
    start_d = end_d - timedelta(days=363)
    p_lbl = "Rolling 52 Weeks" if int(offset) == 0 else f"Rolling 52W ({start_d.strftime('%b %d, %Y')}–{end_d.strftime('%b %d, %Y')})"
    return start_d, end_d, p_lbl, ("last_year" if int(offset) == 0 else "year_rolling"), tf, hm, anchor


def _build_heatmap_and_tables(
    agg: dict[str, Any], *, start_d: date, end_d: date, today: date, now_hour: int, hm: str,
    quota_info: dict[str, Any], parent_model_map: dict[str, str], main_mk: str,
    main_switch_date: str, agent_target_map: dict[str, str], bg_dir: Path,
) -> dict[str, Any]:
    cur, win_st, win_tl, win_tk, win_cs, act_days, peak = start_d, 0, 0, 0, 0, 0, {"date": "", "steps": 0}
    while cur <= end_d:
        ds = cur.strftime("%Y-%m-%d")
        st_c, tl_c = agg["daily_steps"].get(ds, 0), agg["daily_tools"].get(ds, 0)
        tk_c, cs_c = agg["daily_tokens"].get(ds, 0), agg["daily_cost"].get(ds, 0)
        win_st, win_tl, win_tk, win_cs = win_st + st_c, win_tl + tl_c, win_tk + tk_c, win_cs + cs_c
        if st_c > 0:
            act_days += 1
        if st_c >= peak["steps"]:
            peak = {"date": ds, "steps": st_c}
        cur += timedelta(days=1)

    h_cal_s = min(start_d, end_d - timedelta(days=363))
    h_cal_e = end_d
    h_cur, h_end = h_cal_s - timedelta(days=h_cal_s.weekday()), h_cal_e + timedelta(days=(6 - h_cal_e.weekday()))
    s_strip_iso, e_strip_iso = h_cur.strftime("%Y-%m-%d"), min(h_end, today).strftime("%Y-%m-%d")
    s_win_iso, e_win_iso = start_d.strftime("%Y-%m-%d"), min(end_d, today).strftime("%Y-%m-%d")
    in_win_nz = sorted(v for ds, v in agg["daily_steps"].items() if v > 0 and s_win_iso <= ds <= e_win_iso)
    strip_nz = sorted(v for ds, v in agg["daily_steps"].items() if v > 0 and s_strip_iso <= ds <= e_strip_iso)
    nz = in_win_nz if len(in_win_nz) >= 4 else (strip_nz or sorted(v for v in agg["daily_steps"].values() if v > 0))
    q1, q2, q3 = (nz[max(0, int(len(nz) * 0.25) - 1)], nz[max(0, int(len(nz) * 0.50) - 1)], nz[max(0, int(len(nz) * 0.75) - 1)]) if nz else (25, 100, 300)
    heatmap_series: list[dict[str, Any]] = []
    while h_cur <= h_end:
        ds, is_fut = h_cur.strftime("%Y-%m-%d"), h_cur > today
        st_c = 0 if is_fut else agg["daily_steps"].get(ds, 0)
        lvl = -1 if is_fut else (0 if st_c == 0 else (1 if st_c <= q1 else (2 if st_c <= q2 else (3 if st_c <= q3 else 4))))
        heatmap_series.append({
            "date": ds, "weekday": h_cur.weekday(), "steps": st_c,
            "tools": 0 if is_fut else agg["daily_tools"].get(ds, 0),
            "tokens": 0 if is_fut else agg["daily_tokens"].get(ds, 0),
            "cost_usd": 0.0 if is_fut else round(agg["daily_cost"].get(ds, 0) / 1_000_000.0, 4),
            "sessions": 0 if is_fut else len(agg["daily_sessions"].get(ds, set())),
            "level": lvl, "future": is_fut, "in_window": start_d <= h_cur <= end_d,
        })
        h_cur += timedelta(days=1)

    act_d, act_w = max(1, act_days), max(1.0, max(1, act_days) / 7.0)
    ws_sum = max(1, sum(int(w.get("steps", 0)) for w in agg["ws_map"].values()))
    all_ws_list = sorted(agg["ws_map"].values(), key=lambda x: x["steps"], reverse=True)
    for w in all_ws_list:
        tk, st_w, cm_w = int(w.get("tokens", 0)), int(w.get("steps", 0)), int(w.get("cost_usd_micros", 0))
        w.update({"tok_per_day": round(tk / act_d), "tok_per_week": round(tk / act_w), "share_pct": round((st_w / ws_sum) * 100.0, 1), "est_cost_usd": round(cm_w / 1_000_000.0, 2)})

    has_l24, l24_slots = compute_trailing_24h_slots(start_d, end_d, today, now_hour)
    e_iso = end_d.strftime("%Y-%m-%d")
    subagent_list = build_subagent_list_rows(
        agg, act_d, act_w, l24_slots, has_l24,
        resolve_model_fn=resolve_subagent_model, short_labels=MODEL_SHORT_LABELS, e_iso=e_iso,
        parent_model_map=parent_model_map, main_mk=main_mk, main_switch_date=main_switch_date,
        agent_target_map=agent_target_map,
    )
    model_comp = build_model_comparison_rows(
        agg, quota_info, e_iso, l24_slots, has_l24,
        canonical_keys=get_canonical_model_keys(), specs=get_model_specs_map(),
        short_labels=MODEL_SHORT_LABELS, resolve_rate_epoch_fn=resolve_rate_epoch, bg_dir=bg_dir,
    )
    return {
        "win_steps_sum": win_st, "win_tools_sum": win_tl, "win_tokens_sum": win_tk, "win_cost_sum": win_cs,
        "active_days": act_days, "act_d": act_d, "act_w": act_w, "peak": peak,
        "has_last_24h": has_l24, "l24_slots": l24_slots,
        "heatmap_series": heatmap_series, "all_ws_list": all_ws_list, "subagent_list": subagent_list, "model_comp": model_comp,
    }


def build_nexus_stats_bundle(
    brain_dir: Path | None = None, db_file: Path | None = None, agy_config_dir: Path | None = None,
    bg_dir: Path | None = None, period: str = "last_90d", *, style: str = "default",
    data_dir: Path | None = None, config_dir: Path | None = None,
    timeframe: str = "", horizon_mode: str = "", offset: int = 0, anchor_date: str = "",
    project_id: str = "", include_ascii: bool = True, compact_sessions: bool = False,
) -> dict[str, Any]:
    """Build complete multi-window telemetry, 8-model USD ledger, whiskers, canonical hierarchy & ASCII reports."""
    base_data = data_dir or Path.home() / ".gemini/antigravity"
    brain_dir = brain_dir or (base_data / "brain")
    db_file = db_file or (base_data / "conversation_summaries.db")
    agy_config_dir = agy_config_dir or config_dir or (Path.home() / ".gemini/config")
    bg_dir = bg_dir or (base_data / "sidecar_data/ag-bridge-bg")
    now_loc = datetime.now(DISPLAY_TZ)
    today = now_loc.date()

    start_d, end_d, p_label, pk, tf, hm, anchor = _resolve_window_bounds(period, timeframe, horizon_mode, offset, anchor_date, today)
    s_iso, e_iso = start_d.strftime("%Y-%m-%d"), end_d.strftime("%Y-%m-%d")
    quota_info = get_live_quota_and_pool_status(base_data, agy_config_dir)
    main_info = quota_info.get("active_mainchat_model") or {}
    main_mk, main_switch_date = str(main_info.get("model_key") or "argon"), str(main_info.get("state_updated_date") or "")

    full_conv_cache = scan_transcript_stats(brain_dir, bg_dir)
    full_db_convs = load_db_conversations(db_file)
    projects_map = load_projects_meta(agy_config_dir)
    agent_target_map = load_agent_target_map(agy_config_dir)
    default_live_bg = (Path.home() / ".gemini/antigravity/sidecar_data/ag-bridge-bg").resolve()
    can_persist = (bg_dir.resolve() != default_live_bg) or any((brain_dir / cid).is_dir() for cid in full_conv_cache)
    parent_model_map = {cid: str(cd.get("last_conv_model") or "") for cid, cd in full_conv_cache.items() if cd.get("last_conv_model")}
    ledger = (
        merge_and_persist_cost_ledger(bg_dir, full_conv_cache, full_db_convs, projects_map=projects_map, parent_model_map=parent_model_map, main_mk=main_mk, main_switch_date=main_switch_date, agent_target_map=agent_target_map)
        if can_persist else load_cost_ledger(bg_dir)
    )
    full_live_cids = set(full_conv_cache.keys())

    from agy_nexus.session_tree import build_project_session_tree
    tree_bundle = build_project_session_tree(active_only=False, limit=180, bg_dir=bg_dir)
    live_sess_map = {str(s["conversation_id"]): s for tp in (tree_bundle.get("projects") or []) for s in (tp.get("sessions") or []) if s.get("conversation_id")}
    conv_cache, db_convs = full_conv_cache, full_db_convs
    fleet_idx, target_pid = None, ""
    if (project_id or "").strip():
        fleet_idx = build_fleet_project_index(full_conv_cache, full_db_convs, live_sess_map, projects_map, tree_bundle, s_iso, e_iso)
        target_pid = resolve_target_project_id(project_id, fleet_idx["proj_meta"], projects_map)
        conv_cache, db_convs = filter_project_conversations(full_conv_cache, full_db_convs, live_sess_map, projects_map, target_pid)

    agg = init_agg_state()
    fold_live_conversations(
        agg, conv_cache, db_convs, s_iso=s_iso, e_iso=e_iso, parent_model_map=parent_model_map,
        main_mk=main_mk, main_switch_date=main_switch_date, agent_target_map=agent_target_map, bg_dir=bg_dir,
    )
    archived_convs = fold_orphaned_and_archived(
        agg, db_convs, conv_cache, ledger, full_live_cids, s_iso=s_iso, e_iso=e_iso, target_pid=target_pid,
        parent_model_map=parent_model_map, main_mk=main_mk, main_switch_date=main_switch_date,
        agent_target_map=agent_target_map, bg_dir=bg_dir,
    )
    tbl = _build_heatmap_and_tables(
        agg, start_d=start_d, end_d=end_d, today=today, now_hour=now_loc.hour, hm=hm, quota_info=quota_info,
        parent_model_map=parent_model_map, main_mk=main_mk, main_switch_date=main_switch_date,
        agent_target_map=agent_target_map, bg_dir=bg_dir,
    )
    heatmap_series = tbl["heatmap_series"]
    chart_days = [x for x in heatmap_series if not x.get("future") and s_iso <= x["date"] <= e_iso]
    if tf == "year":
        trimmed_days = [x["date"] for x in chart_days]
    else:
        first_idx = next((idx for idx, x in enumerate(chart_days) if x["steps"] > 0), 0)
        trimmed_days = [x["date"] for x in (chart_days[max(0, first_idx - 1) :] if len(chart_days) > 7 else chart_days)]

    tree_for_series = {"projects": [tp for tp in (tree_bundle.get("projects") or []) if str(tp.get("project_id") or "") == target_pid]} if target_pid else tree_bundle
    cand_cids = set(agg["root_sess_stats"]) | {str(s.get("conversation_id") or "") for tp in (tree_for_series.get("projects") or []) for s in (tp.get("sessions") or [])}
    retired_cids = {cid for cid in cand_cids if cid and is_session_retired(cid, brain_dir)}
    sess_s1_steps = {rcid: rs["s1_steps"] for rcid, rs in agg["root_sess_stats"].items()} if target_pid else {}
    sess_s1_toks = {rcid: rs["s1_toks"] for rcid, rs in agg["root_sess_stats"].items()} if target_pid else {}
    sess_s1_cost = {rcid: rs["s1_cost"] for rcid, rs in agg["root_sess_stats"].items()} if target_pid else {}
    series_pkg = build_series_and_project_hierarchy(
        period_key=pk, trimmed_days=trimmed_days, today_iso=today.strftime("%Y-%m-%d"), now_hour=now_loc.hour,
        s1_tot_steps=agg["s1_tot_steps"], s1_tot_toks=agg["s1_tot_toks"], s1_tot_cost=agg["s1_tot_cost"],
        s1_mod_steps=agg["s1_mod_steps"], s1_mod_toks=agg["s1_mod_toks"], s1_mod_cost=agg["s1_mod_cost"],
        s1_sub_steps=agg["s1_sub_steps"], s1_sub_toks=agg["s1_sub_toks"], s1_sub_cost=agg["s1_sub_cost"],
        s1_ws_steps=agg["s1_ws_steps"], all_ws_list=tbl["all_ws_list"], subagent_list=tbl["subagent_list"],
        root_sess_stats=agg["root_sess_stats"], db_convs=db_convs, projects_map=projects_map, tree_bundle=tree_for_series,
        l24_slots=tbl["l24_slots"], has_l24=tbl["has_last_24h"], retired_cids=retired_cids,
    )
    slot_groups, p_hier = series_pkg.pop("groups", []), series_pkg["project_hierarchy"]
    if target_pid and fleet_idx is not None:
        p_hier["total_sessions_count"], p_hier["latest_session_id"] = fleet_idx["total_sessions_count"], fleet_idx["latest_session_id"]
    elif compact_sessions:
        compact_project_hierarchy_sessions(p_hier)
    return _assemble_stats_output(
        agg=agg, tbl=tbl, series_pkg=series_pkg, slot_groups=slot_groups, p_hier=p_hier, heatmap_series=heatmap_series,
        tree_bundle=tree_bundle, quota_info=quota_info, db_convs=db_convs, projects_map=projects_map, fleet_idx=fleet_idx,
        target_pid=target_pid, archived_convs=archived_convs, sess_s1_steps=sess_s1_steps, sess_s1_toks=sess_s1_toks,
        sess_s1_cost=sess_s1_cost, start_d=start_d, end_d=end_d, today=today, now_loc=now_loc, anchor=anchor, pk=pk,
        p_label=p_label, s_iso=s_iso, e_iso=e_iso, tf=tf, hm=hm, offset=offset, style=style, bg_dir=bg_dir, include_ascii=include_ascii,
    )


def _assemble_stats_output(
    *, agg: dict[str, Any], tbl: dict[str, Any], series_pkg: dict[str, Any], slot_groups: list[list[str]],
    p_hier: dict[str, Any], heatmap_series: list[dict[str, Any]], tree_bundle: dict[str, Any],
    quota_info: dict[str, Any], db_convs: dict[str, dict[str, Any]], projects_map: dict[str, dict[str, Any]],
    fleet_idx: dict[str, Any] | None, target_pid: str, archived_convs: int, sess_s1_steps: dict[str, dict[str, int]],
    sess_s1_toks: dict[str, dict[str, int]], sess_s1_cost: dict[str, dict[str, int]],
    start_d: date, end_d: date, today: date, now_loc: datetime, anchor: date,
    pk: str, p_label: str, s_iso: str, e_iso: str, tf: str, hm: str, offset: int,
    style: str, bg_dir: Path, include_ascii: bool,
) -> dict[str, Any]:
    win_cost_micros = max(int(tbl["win_cost_sum"]), sum(int(v) for v in agg["model_cost"].values()))
    win_fore_micros = max(win_cost_micros, sum(int(v) for v in agg["model_fore"].values()))
    parent_cnt = (agg["active_parent_convs"] + archived_convs) or sum(1 for v in db_convs.values() if not v.get("is_subagent"))
    act_d, act_w = tbl["act_d"], tbl["act_w"]
    drift_status = read_model_drift_status(bg_dir)
    hourly_whiskers = compute_hourly_whiskers(agg["s1_tot_steps"], agg["s1_tot_toks"], agg["s1_tot_cost"], start_d, end_d, today, now_loc.hour)
    billing_cmp = build_billing_comparison(
        win_cost_micros, win_fore_micros, window_days=max(1, (end_d - start_d).days + 1),
        active_days=tbl["active_days"], active_profile=str(quota_info.get("active_tier_profile") or quota_info.get("active_profile") or "ultra-20x"), drift_status=drift_status,
    )
    win_cost_usd = round(win_cost_micros / 1_000_000.0, 2)
    kpis_obj = {
        "total_conversations": parent_cnt, "total_subagents_spawned": sum(v["runs"] for v in agg["subagent_roles"].values()),
        "window_steps": tbl["win_steps_sum"], "period_steps": tbl["win_steps_sum"],
        "window_tool_calls": tbl["win_tools_sum"], "period_tool_calls": tbl["win_tools_sum"],
        "window_tokens": tbl["win_tokens_sum"], "active_days": tbl["active_days"],
        "avg_daily_steps": round(tbl["win_steps_sum"] / act_d, 1), "tok_per_day": round(tbl["win_tokens_sum"] / act_d),
        "tok_per_week": round(tbl["win_tokens_sum"] / act_w), "peak_day": tbl["peak"],
        "window_cost_micros": win_cost_micros, "window_cost_usd": win_cost_usd,
        "forecast_cost_micros": win_fore_micros, "forecast_cost_usd": round(win_fore_micros / 1_000_000.0, 2),
        "cost_per_day_usd": round(win_cost_usd / act_d, 2), "cost_per_week_usd": round(win_cost_usd / act_w, 2),
        "uncached_input_tokens": int(agg["tok_split"][0]), "cached_input_tokens": int(agg["tok_split"][1]), "output_tokens": int(agg["tok_split"][2]),
    }
    res_label = series_pkg["resolution"]
    bundle: dict[str, Any] = {
        "server": "agy-nexus-mcp", "version": __version__, "generated_at": now_loc.isoformat(), "style": (style or "default").strip().lower(),
        "period": {
            "key": pk, "label": p_label, "start_date": s_iso, "end_date": e_iso,
            "total_days": len([x for x in heatmap_series if x.get("in_window")]),
            "active_days": tbl["active_days"], "resolution": res_label,
            "timeframe": tf, "horizon_mode": hm, "offset": int(offset), "anchor_date": anchor.strftime("%Y-%m-%d"),
        },
        "kpis": kpis_obj, "summary": kpis_obj, "quota_and_pools": quota_info, "model_usage_vs_target": tbl["model_comp"],
        "subagent_role_breakdown": agg["subagent_roles"], "subagent_list": tbl["subagent_list"],
        "all_workspaces": tbl["all_ws_list"], "top_workspaces": tbl["all_ws_list"][:10],
        "velocity_series": series_pkg["velocity_series"], "model_series": series_pkg["model_series"],
        "workspace_series": series_pkg["workspace_series"], "subagent_series": series_pkg["subagent_series"],
        "project_hierarchy": p_hier, "heatmap_series": heatmap_series, "hourly_whiskers": hourly_whiskers,
        "billing_comparison": billing_cmp, "model_drift_status": drift_status,
        "wire_telemetry": get_wire_telemetry_summary(bg_dir, limit=15),
        "routing_telemetry": tree_bundle.get("routing_telemetry", {}), "backup_321": tree_bundle.get("backup_321", {}),
        "code_health": get_code_health_summary(),
    }
    if target_pid and fleet_idx is not None:
        pb_match = next((p for p in [*(p_hier.get("top_projects") or []), *(p_hier.get("idle_projects") or [])] if p.get("project_id") == target_pid), None)
        proj_meta = (fleet_idx.get("proj_meta") or {}).get(target_pid) or {"project_id": target_pid, "project_name": (projects_map.get(target_pid) or {}).get("name") or target_pid}
        bundle["project_sessions_series"] = build_project_sessions_series(
            pb_match, series_pkg["velocity_series"]["dates"], slot_groups, series_pkg["step_hours"], res_label, sess_s1_steps, sess_s1_toks, sess_s1_cost,
        )
        bundle["project_scope"] = build_project_scope_payload(
            target_pid, proj_meta, fleet_idx, pb_match, tbl["win_steps_sum"], tbl["win_tokens_sum"], tbl["active_days"], win_cost_micros=win_cost_micros,
        )
    if include_ascii:
        bundle["project_session_tree"] = tree_bundle
        bundle["ascii_report_default"], bundle["ascii_report_quick"], bundle["ascii_report_rich"] = render_ascii_default(bundle), render_ascii_quick(bundle), render_ascii_rich(bundle)
        bundle["ascii_mobile_dashboard"] = bundle["ascii_mobile_report"] = render_ascii_stats(bundle, style=style)
    return bundle



get_quota_and_stats_bundle = build_nexus_stats_bundle
