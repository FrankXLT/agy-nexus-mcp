#!/usr/bin/env python3
"""
agy_nexus.stats_aggregator — Live Conversation, Orphaned Subagent & Archived Cost Ledger Aggregation Helpers.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from agy_nexus.cost_ledger import collect_archived_ledger_totals
from agy_nexus.inventory import parse_markdown_frontmatter
from agy_nexus.media_discovery import parse_iso_epoch
from agy_nexus.model_pricing import (
    classify_model_key,
    compute_step_cost_micros,
    get_canonical_model_keys,
    split_estimated_tokens,
)
from agy_nexus.stats_metrics import (
    fold_subagent_run_sample,
    init_subagent_role_record,
    merge_subagent_role_stats,
    slot_key_epoch,
)
from agy_nexus.stats_series import resolve_root_conversation, resolve_subagent_model
from agy_nexus.telemetry_scanner import DISPLAY_TZ, normalize_workspace_name, to_1h_slot


def load_db_conversations(db_file: Path) -> dict[str, dict[str, Any]]:
    """Read conversation_summaries SQLite table safely and propagate parent workspaces."""
    from agy_nexus.sessions import pick_primary_workspace_uri

    db_convs: dict[str, dict[str, Any]] = {}
    if not db_file.exists():
        return db_convs
    try:
        conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True, timeout=3.0)
        try:
            conn.row_factory = sqlite3.Row
            cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(conversation_summaries)").fetchall()}
            proj_col = ", project_id" if "project_id" in cols else ""
            rows = conn.execute(
                f"SELECT conversation_id, title, step_count, last_modified_time, workspace_uris, "
                f"status, parent_conversation_id, agent_name{proj_col} FROM conversation_summaries"
            ).fetchall()
        finally:
            conn.close()
        for r in rows:
            cid, pid = str(r["conversation_id"]), str(r["parent_conversation_id"] or "")
            agent_name = str(r["agent_name"] or "").strip()
            uris = json.loads(r["workspace_uris"] or "[]") if isinstance(r["workspace_uris"], str) and r["workspace_uris"].startswith("[") else []
            title_str = str(r["title"] or cid[:8])
            db_convs[cid] = {
                "title": title_str, "step_count": int(r["step_count"] or 0),
                "last_modified": str(r["last_modified_time"] or ""),
                "workspace": pick_primary_workspace_uri(uris, title_str),
                "status": str(r["status"] or "IDLE"), "is_subagent": bool(pid),
                "parent_id": pid, "agent_name": agent_name or "subagent",
                "project_id": str(r["project_id"] or "") if "project_id" in cols else "",
            }
        for info in db_convs.values():
            p_obj = db_convs.get(info["parent_id"])
            if p_obj:
                if p_obj.get("workspace"):
                    info["workspace"] = p_obj["workspace"]
                if p_obj.get("project_id") and not info.get("project_id"):
                    info["project_id"] = p_obj["project_id"]
    except Exception:
        pass
    return db_convs


from agy_nexus.hygiene import resolve_package_resource_dir


def load_agent_target_map(agy_config_dir: Path) -> dict[str, str]:
    """Map subagent names from tracked agents/*.md and user AGY_CONFIG_DIR/agents/*.md to model keys."""
    out: dict[str, str] = {}
    repo_agents = resolve_package_resource_dir("agents", __file__)
    for root in (repo_agents, agy_config_dir / "agents"):
        if not root.is_dir():
            continue
        for md_path in sorted(root.glob("*.md")):
            if md_path.name.lower() == "readme.md":
                continue
            try:
                fm, _ = parse_markdown_frontmatter(md_path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            raw_m = str(fm.get("model") or "").strip().lower()
            tgt = str(fm.get("targetModel") or "").strip()
            stem = str(fm.get("name") or md_path.stem).strip().lower()
            val = "inherit" if raw_m == "inherit" else classify_model_key(tgt if (tgt and "/" not in tgt) else (raw_m or stem), stem)
            out[stem] = val
            out[md_path.stem.lower()] = val
    return out


def init_agg_state() -> dict[str, Any]:
    """Initialize 8-model aggregation accumulators for live, orphaned, and archived usage."""
    m_keys = get_canonical_model_keys()
    return {
        "subagent_roles": {},
        "role_model_votes": {},
        "role_inherited": {},
        "model_totals": {mk: 0 for mk in m_keys},
        "model_tokens": {mk: 0 for mk in m_keys},
        "model_cost": {mk: 0 for mk in m_keys},
        "model_fore": {mk: 0 for mk in m_keys},
        "tok_split": [0, 0, 0],
        "daily_steps": {},
        "daily_tools": {},
        "daily_tokens": {},
        "daily_cost": {},
        "daily_sessions": {},
        "s1_tot_steps": {},
        "s1_tot_toks": {},
        "s1_tot_cost": {},
        "ws_map": {},
        "s1_mod_steps": {mk: {} for mk in m_keys},
        "s1_mod_toks": {mk: {} for mk in m_keys},
        "s1_mod_cost": {mk: {} for mk in m_keys},
        "s1_sub_steps": {},
        "s1_sub_toks": {},
        "s1_sub_cost": {},
        "s1_ws_steps": {},
        "root_sess_stats": {},
        "active_parent_convs": 0,
    }


def _fold_slot_metrics(
    agg: dict[str, Any], cdata: dict[str, Any], r_stat: dict[str, Any], *,
    s_iso: str, e_iso: str, is_sub: bool, agent_role: str, root_cid: str, ws_name: str,
    parent_model_map: dict[str, str], main_mk: str, main_switch_date: str,
    agent_target_map: dict[str, str], bg_dir: Path,
) -> None:
    s1_st_src = cdata.get("slot_1h_steps") or cdata.get("slot_steps") or {}
    s1_tk_src = cdata.get("slot_1h_tokens") or {}
    s1_cs_src = cdata.get("slot_1h_cost_micros") or {}
    s1_ps_src = cdata.get("slot_1h_planner_splits") or {}
    has_cost_slots = "slot_1h_cost_micros" in cdata
    est_base_mk = classify_model_key(str(cdata.get("last_conv_model") or main_mk or "argon"))

    for sl_k, sl_cnt in s1_st_src.items():
        if s_iso <= sl_k[:10] <= e_iso:
            agg["s1_tot_steps"][sl_k] = agg["s1_tot_steps"].get(sl_k, 0) + sl_cnt
            agg["s1_ws_steps"].setdefault(ws_name, {})[sl_k] = agg["s1_ws_steps"].get(ws_name, {}).get(sl_k, 0) + sl_cnt
            r_stat["s1_steps"][sl_k] = r_stat["s1_steps"].get(sl_k, 0) + sl_cnt
            if is_sub:
                agg["s1_sub_steps"].setdefault(agent_role, {})[sl_k] = agg["s1_sub_steps"].get(agent_role, {}).get(sl_k, 0) + sl_cnt
                smk, _ = resolve_subagent_model(agent_role, root_cid, parent_model_map, main_mk, main_switch_date, sl_k, agent_target_map)
                agg["s1_mod_steps"].setdefault(smk, {})[sl_k] = agg["s1_mod_steps"].get(smk, {}).get(sl_k, 0) + sl_cnt

    for sl_k, sl_tk in s1_tk_src.items():
        if not (s_iso <= sl_k[:10] <= e_iso):
            continue
        sl_tk_i = int(sl_tk)
        agg["s1_tot_toks"][sl_k] = agg["s1_tot_toks"].get(sl_k, 0) + sl_tk_i
        r_stat["s1_toks"][sl_k] = r_stat["s1_toks"].get(sl_k, 0) + sl_tk_i
        if is_sub:
            smk, _ = resolve_subagent_model(agent_role, root_cid, parent_model_map, main_mk, main_switch_date, sl_k, agent_target_map)
            agg["s1_sub_toks"].setdefault(agent_role, {})[sl_k] = agg["s1_sub_toks"].get(agent_role, {}).get(sl_k, 0) + sl_tk_i
            agg["s1_mod_toks"].setdefault(smk, {})[sl_k] = agg["s1_mod_toks"].get(smk, {}).get(sl_k, 0) + sl_tk_i
            if has_cost_slots and smk == est_base_mk:
                sl_cs = int(s1_cs_src.get(sl_k, 0))
            elif sl_k in s1_ps_src and isinstance(s1_ps_src[sl_k], list) and len(s1_ps_src[sl_k]) == 3:
                sp_u, sp_c, sp_o = int(s1_ps_src[sl_k][0]), int(s1_ps_src[sl_k][1]), int(s1_ps_src[sl_k][2])
                sl_cs = compute_step_cost_micros(smk, sl_k[:10], sp_u, sp_c, sp_o, bg_dir=bg_dir)
            elif has_cost_slots:
                sl_cs = 0
            else:
                sl_cs = compute_step_cost_micros(smk, sl_k[:10], *split_estimated_tokens(sl_tk_i), bg_dir=bg_dir)
            agg["s1_sub_cost"].setdefault(agent_role, {})[sl_k] = agg["s1_sub_cost"].get(agent_role, {}).get(sl_k, 0) + sl_cs
            agg["s1_mod_cost"].setdefault(smk, {})[sl_k] = agg["s1_mod_cost"].get(smk, {}).get(sl_k, 0) + sl_cs
        else:
            sl_cs = int(s1_cs_src[sl_k]) if has_cost_slots else compute_step_cost_micros(
                est_base_mk, sl_k[:10], *split_estimated_tokens(sl_tk_i), bg_dir=bg_dir
            )
        agg["s1_tot_cost"][sl_k] = agg["s1_tot_cost"].get(sl_k, 0) + sl_cs
        r_stat["s1_cost"][sl_k] = r_stat["s1_cost"].get(sl_k, 0) + sl_cs

    if not is_sub:
        for sl_k, m_dict in (cdata.get("slot_1h_models") or {}).items():
            if s_iso <= sl_k[:10] <= e_iso and isinstance(m_dict, dict):
                for mk_r, mv in m_dict.items():
                    mk = classify_model_key(mk_r)
                    agg["s1_mod_steps"].setdefault(mk, {})[sl_k] = agg["s1_mod_steps"].get(mk, {}).get(sl_k, 0) + int(mv)
        mc_src = cdata.get("slot_1h_model_cost_micros") or {}
        for sl_k, mt_dict in (cdata.get("slot_1h_model_tokens") or {}).items():
            if s_iso <= sl_k[:10] <= e_iso and isinstance(mt_dict, dict):
                slot_c = mc_src.get(sl_k) if isinstance(mc_src, dict) else None
                for mk_r, mtv in mt_dict.items():
                    mk = classify_model_key(mk_r)
                    mtv_i = int(mtv)
                    agg["s1_mod_toks"].setdefault(mk, {})[sl_k] = agg["s1_mod_toks"].get(mk, {}).get(sl_k, 0) + mtv_i
                    c_add = int(slot_c[mk_r]) if (isinstance(slot_c, dict) and mk_r in slot_c) else compute_step_cost_micros(
                        mk, sl_k[:10], *split_estimated_tokens(mtv_i), bg_dir=bg_dir
                    )
                    agg["s1_mod_cost"].setdefault(mk, {})[sl_k] = agg["s1_mod_cost"].get(mk, {}).get(sl_k, 0) + c_add


def _fold_day_models_and_cost(
    agg: dict[str, Any], cdata: dict[str, Any], *,
    s_iso: str, e_iso: str, is_sub: bool, agent_role: str, root_cid: str,
    parent_model_map: dict[str, str], main_mk: str, main_switch_date: str,
    agent_target_map: dict[str, str], bg_dir: Path,
) -> int:
    has_day_cost = "day_cost_micros" in cdata
    dc_days, df_days = cdata.get("day_model_cost_micros") or {}, cdata.get("day_model_forecast_micros") or {}
    dsp_days = cdata.get("day_model_token_splits") or {}
    if has_day_cost and not is_sub:
        for ds, dc in (cdata.get("day_cost_micros") or {}).items():
            agg["daily_cost"][ds] = agg["daily_cost"].get(ds, 0) + int(dc)
    elif is_sub:
        for ds, dtk_map in (cdata.get("day_model_tokens") or {}).items():
            if not (s_iso <= ds <= e_iso) and isinstance(dtk_map, dict):
                smk_o = resolve_subagent_model(agent_role, root_cid, parent_model_map, main_mk, main_switch_date, ds, agent_target_map)[0]
                dc_o, dsp_o = dc_days.get(ds) or {}, dsp_days.get(ds) or {}
                for mk_r, mtok in dtk_map.items():
                    sp = dsp_o.get(mk_r)
                    u_in, c_in, out_t = (int(sp[0]), int(sp[1]), int(sp[2])) if (isinstance(sp, list) and len(sp) == 3) else split_estimated_tokens(int(mtok))
                    mc_o = int(dc_o[mk_r]) if (classify_model_key(mk_r) == smk_o and mk_r in dc_o) else compute_step_cost_micros(smk_o, ds, u_in, c_in, out_t, bg_dir=bg_dir)
                    agg["daily_cost"][ds] = agg["daily_cost"].get(ds, 0) + mc_o

    for ds, dm_map in (cdata.get("day_models") or {}).items():
        if s_iso <= ds <= e_iso and isinstance(dm_map, dict):
            if is_sub:
                smk, is_inh = resolve_subagent_model(agent_role, root_cid, parent_model_map, main_mk, main_switch_date, ds, agent_target_map)
                c_sum = sum(int(v) for v in dm_map.values())
                agg["model_totals"][smk] = agg["model_totals"].get(smk, 0) + c_sum
                agg["role_model_votes"].setdefault(agent_role, {})[smk] = agg["role_model_votes"].get(agent_role, {}).get(smk, 0) + c_sum
                if is_inh:
                    agg["role_inherited"][agent_role] = True
            else:
                for mk_r, mv in dm_map.items():
                    mk = classify_model_key(mk_r)
                    agg["model_totals"][mk] = agg["model_totals"].get(mk, 0) + int(mv)

    win_cost = 0
    for ds, dtk_map in (cdata.get("day_model_tokens") or {}).items():
        if not (s_iso <= ds <= e_iso and isinstance(dtk_map, dict)):
            continue
        smk = resolve_subagent_model(agent_role, root_cid, parent_model_map, main_mk, main_switch_date, ds, agent_target_map)[0] if is_sub else ""
        dc_map, df_map, dsp_map = dc_days.get(ds) or {}, df_days.get(ds) or {}, dsp_days.get(ds) or {}
        for mk_r, mtok in dtk_map.items():
            mk_raw_c = classify_model_key(mk_r)
            mk_c = smk if is_sub else mk_raw_c
            mtok_i = int(mtok)
            agg["model_tokens"][mk_c] = agg["model_tokens"].get(mk_c, 0) + mtok_i
            sp = dsp_map.get(mk_r)
            u_in, c_in, out_t = (int(sp[0]), int(sp[1]), int(sp[2])) if (isinstance(sp, list) and len(sp) == 3) else split_estimated_tokens(mtok_i)
            agg["tok_split"][0] += u_in
            agg["tok_split"][1] += c_in
            agg["tok_split"][2] += out_t
            same_mk = (not is_sub) or (mk_raw_c == mk_c)
            mc_v = int(dc_map[mk_r]) if (same_mk and mk_r in dc_map) else compute_step_cost_micros(mk_c, ds, u_in, c_in, out_t, bg_dir=bg_dir)
            mf_v = int(df_map[mk_r]) if (same_mk and mk_r in df_map) else compute_step_cost_micros(mk_c, ds, u_in, c_in, out_t, forecast=True, bg_dir=bg_dir)
            agg["model_cost"][mk_c] = agg["model_cost"].get(mk_c, 0) + mc_v
            agg["model_fore"][mk_c] = agg["model_fore"].get(mk_c, 0) + mf_v
            win_cost += mc_v
            if not has_day_cost or is_sub:
                agg["daily_cost"][ds] = agg["daily_cost"].get(ds, 0) + mc_v
    return win_cost


def fold_live_conversations(
    agg: dict[str, Any], conv_cache: dict[str, dict[str, Any]], db_convs: dict[str, dict[str, Any]], *,
    s_iso: str, e_iso: str, parent_model_map: dict[str, str], main_mk: str, main_switch_date: str,
    agent_target_map: dict[str, str], bg_dir: Path,
) -> None:
    """Fold cached/scanned live conversations into daily, 1h slot, model, and workspace accumulators."""
    for cid, cdata in conv_cache.items():
        meta = db_convs.get(cid, {})
        is_sub, agent_role = bool(meta.get("is_subagent")), str(meta.get("agent_name") or "subagent")
        root_cid = resolve_root_conversation(cid, db_convs) if is_sub else cid
        root_meta = db_convs.get(root_cid, meta)
        ws_name = normalize_workspace_name(root_meta.get("workspace") or meta.get("workspace") or "") or "unassigned"
        win_steps, win_toks = 0, 0
        for ds, cnt in (cdata.get("day_steps") or {}).items():
            agg["daily_steps"][ds] = agg["daily_steps"].get(ds, 0) + cnt
            agg["daily_sessions"].setdefault(ds, set()).add(root_cid)
            if s_iso <= ds <= e_iso:
                win_steps += cnt
        for ds, tok_c in (cdata.get("day_tokens") or {}).items():
            agg["daily_tokens"][ds] = agg["daily_tokens"].get(ds, 0) + tok_c
            if s_iso <= ds <= e_iso:
                win_toks += tok_c
        for ds, tcnt in (cdata.get("day_tools") or {}).items():
            agg["daily_tools"][ds] = agg["daily_tools"].get(ds, 0) + tcnt

        r_stat = agg["root_sess_stats"].setdefault(root_cid, {"win_steps": 0, "win_tokens": 0, "win_cost_micros": 0, "sub_runs": 0, "s1_steps": {}, "s1_toks": {}, "s1_cost": {}})
        r_stat["win_steps"] += win_steps
        r_stat["win_tokens"] += win_toks
        if is_sub and win_steps > 0:
            r_stat["sub_runs"] += 1

        _fold_slot_metrics(
            agg, cdata, r_stat, s_iso=s_iso, e_iso=e_iso, is_sub=is_sub, agent_role=agent_role,
            root_cid=root_cid, ws_name=ws_name, parent_model_map=parent_model_map, main_mk=main_mk,
            main_switch_date=main_switch_date, agent_target_map=agent_target_map, bg_dir=bg_dir,
        )
        win_cost = _fold_day_models_and_cost(
            agg, cdata, s_iso=s_iso, e_iso=e_iso, is_sub=is_sub, agent_role=agent_role,
            root_cid=root_cid, parent_model_map=parent_model_map, main_mk=main_mk,
            main_switch_date=main_switch_date, agent_target_map=agent_target_map, bg_dir=bg_dir,
        )
        r_stat["win_cost_micros"] += win_cost
        if win_steps > 0:
            we = agg["ws_map"].setdefault(ws_name, {"workspace": ws_name, "sessions": 0, "steps": 0, "tokens": 0, "cost_usd_micros": 0})
            if not is_sub:
                we["sessions"] += 1
                agg["active_parent_convs"] += 1
            else:
                rec = agg["subagent_roles"].setdefault(agent_role, init_subagent_role_record())
                run_ts = (
                    float(meta.get("last_updated_ts") or 0.0)
                    or parse_iso_epoch(str(meta.get("last_modified") or ""))
                    or float(cdata.get("mtime") or 0.0)
                    or slot_key_epoch(cdata.get("slot_1h_steps"), DISPLAY_TZ)
                )
                over_120 = int(meta.get("step_count") or win_steps) > 120 or win_steps > 120
                fold_subagent_run_sample(rec, win_steps, win_toks, win_cost, run_ts=run_ts, over_120=over_120)
            we["steps"] += win_steps
            we["tokens"] += win_toks
            we["cost_usd_micros"] += win_cost


def fold_orphaned_and_archived(
    agg: dict[str, Any], db_convs: dict[str, dict[str, Any]], conv_cache: dict[str, dict[str, Any]],
    ledger: dict[str, Any], full_live_cids: set[str], *,
    s_iso: str, e_iso: str, target_pid: str, parent_model_map: dict[str, str],
    main_mk: str, main_switch_date: str, agent_target_map: dict[str, str], bg_dir: Path,
) -> int:
    """Fold SQLite-only subagents plus pruned conversations persisted in cost_ledger.json."""
    for cid, meta in db_convs.items():
        if not (meta.get("is_subagent") and cid not in conv_cache and int(meta.get("step_count") or 0) > 0):
            continue
        d_str, s1_str, _ = to_1h_slot(str(meta.get("last_modified") or ""), time.time())
        if not (len(d_str) == 10 and s_iso <= d_str <= e_iso):
            continue
        role, st_c = str(meta.get("agent_name") or "subagent"), int(meta["step_count"])
        tok_est = st_c * 380
        u_in, c_in, out_t = split_estimated_tokens(tok_est)
        root_cid = resolve_root_conversation(cid, db_convs)
        ws_n = normalize_workspace_name((db_convs.get(root_cid) or meta).get("workspace") or "") or "unassigned"
        smk, is_inh = resolve_subagent_model(role, root_cid, parent_model_map, main_mk, main_switch_date, d_str, agent_target_map)
        cm = compute_step_cost_micros(smk, d_str, u_in, c_in, out_t, bg_dir=bg_dir)
        fm = compute_step_cost_micros(smk, d_str, u_in, c_in, out_t, forecast=True, bg_dir=bg_dir)
        agg["daily_steps"][d_str] = agg["daily_steps"].get(d_str, 0) + st_c
        agg["daily_tokens"][d_str] = agg["daily_tokens"].get(d_str, 0) + tok_est
        agg["daily_cost"][d_str] = agg["daily_cost"].get(d_str, 0) + cm
        agg["s1_tot_steps"][s1_str], agg["s1_tot_toks"][s1_str], agg["s1_tot_cost"][s1_str] = agg["s1_tot_steps"].get(s1_str, 0) + st_c, agg["s1_tot_toks"].get(s1_str, 0) + tok_est, agg["s1_tot_cost"].get(s1_str, 0) + cm
        agg["s1_sub_steps"].setdefault(role, {})[s1_str] = agg["s1_sub_steps"].get(role, {}).get(s1_str, 0) + st_c
        agg["s1_sub_toks"].setdefault(role, {})[s1_str] = agg["s1_sub_toks"].get(role, {}).get(s1_str, 0) + tok_est
        agg["s1_sub_cost"].setdefault(role, {})[s1_str] = agg["s1_sub_cost"].get(role, {}).get(s1_str, 0) + cm
        agg["s1_ws_steps"].setdefault(ws_n, {})[s1_str] = agg["s1_ws_steps"].get(ws_n, {}).get(s1_str, 0) + st_c
        agg["s1_mod_steps"].setdefault(smk, {})[s1_str] = agg["s1_mod_steps"].get(smk, {}).get(s1_str, 0) + st_c
        agg["s1_mod_toks"].setdefault(smk, {})[s1_str] = agg["s1_mod_toks"].get(smk, {}).get(s1_str, 0) + tok_est
        agg["s1_mod_cost"].setdefault(smk, {})[s1_str] = agg["s1_mod_cost"].get(smk, {}).get(s1_str, 0) + cm
        r_stat = agg["root_sess_stats"].setdefault(root_cid, {"win_steps": 0, "win_tokens": 0, "win_cost_micros": 0, "sub_runs": 0, "s1_steps": {}, "s1_toks": {}, "s1_cost": {}})
        r_stat["win_steps"] += st_c
        r_stat["win_tokens"] += tok_est
        r_stat["win_cost_micros"] += cm
        r_stat["sub_runs"] += 1
        r_stat["s1_steps"][s1_str] = r_stat["s1_steps"].get(s1_str, 0) + st_c
        r_stat["s1_toks"][s1_str] = r_stat["s1_toks"].get(s1_str, 0) + tok_est
        r_stat["s1_cost"][s1_str] = r_stat["s1_cost"].get(s1_str, 0) + cm
        rec = agg["subagent_roles"].setdefault(role, init_subagent_role_record())
        run_ts = float(meta.get("last_updated_ts") or 0.0) or parse_iso_epoch(str(meta.get("last_modified") or ""))
        fold_subagent_run_sample(rec, st_c, tok_est, cm, run_ts=run_ts, over_120=(st_c > 120))
        we = agg["ws_map"].setdefault(ws_n, {"workspace": ws_n, "sessions": 0, "steps": 0, "tokens": 0, "cost_usd_micros": 0})
        we["steps"] += st_c
        we["tokens"] += tok_est
        we["cost_usd_micros"] += cm
        agg["model_totals"][smk], agg["model_tokens"][smk] = agg["model_totals"].get(smk, 0) + st_c, agg["model_tokens"].get(smk, 0) + tok_est
        agg["model_cost"][smk], agg["model_fore"][smk] = agg["model_cost"].get(smk, 0) + cm, agg["model_fore"].get(smk, 0) + fm
        agg["tok_split"][0] += u_in
        agg["tok_split"][1] += c_in
        agg["tok_split"][2] += out_t
        agg["role_model_votes"].setdefault(role, {})[smk] = agg["role_model_votes"].get(role, {}).get(smk, 0) + st_c
        if is_inh:
            agg["role_inherited"][role] = True

    arch = collect_archived_ledger_totals(ledger, full_live_cids, s_iso, e_iso, allowed_project_id=target_pid)
    for k_src, k_dst in (
        ("model_steps", "model_totals"), ("model_tokens", "model_tokens"),
        ("model_cost_micros", "model_cost"), ("model_forecast_micros", "model_fore"),
        ("day_steps", "daily_steps"), ("day_tokens", "daily_tokens"),
        ("day_cost_micros", "daily_cost"), ("out_of_window_daily_cost", "daily_cost"),
    ):
        for mk, mv in arch[k_src].items():
            agg[k_dst][mk] = agg[k_dst].get(mk, 0) + int(mv)
    for ws_n, aw in (arch.get("ws_map") or {}).items():
        we = agg["ws_map"].setdefault(ws_n, {"workspace": ws_n, "sessions": 0, "steps": 0, "tokens": 0, "cost_usd_micros": 0})
        we["sessions"] += int(aw.get("sessions") or 0)
        we["steps"] += int(aw.get("steps") or 0)
        we["tokens"] += int(aw.get("tokens") or 0)
        we["cost_usd_micros"] += int(aw.get("cost_usd_micros") or 0)
    for role_k, asr in (arch.get("subagent_roles") or {}).items():
        sr = agg["subagent_roles"].setdefault(role_k, init_subagent_role_record())
        merge_subagent_role_stats(sr, asr)
    for idx in range(3):
        agg["tok_split"][idx] += int(arch["token_split"][idx])
    return int(arch["archived_convs"])
