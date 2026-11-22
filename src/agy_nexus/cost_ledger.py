#!/usr/bin/env python3
"""agy_nexus.cost_ledger — Effective-Dated cost_ledger.json Persistence, Drift Status & Hourly Whiskers."""
from __future__ import annotations

from datetime import date, timedelta
import fcntl
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from agy_nexus.model_pricing import (
    classify_model_key,
    compute_step_cost_micros,
    get_canonical_model_keys,
    split_estimated_tokens,
)

LEDGER_VERSION = 1
_LEDGER_LOCK = threading.Lock()


def _atomic_write_json_600(target: Path, payload: dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fd = -1
            json.dump(payload, fh, separators=(",", ":"), ensure_ascii=False)
        os.replace(tmp_name, target)
    except Exception:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def load_cost_ledger(bg_dir: Path) -> dict[str, Any]:
    """Read persistent sidecar cost_ledger.json (or return an empty v1 ledger)."""
    lpath = bg_dir / "cost_ledger.json"
    if lpath.is_file():
        try:
            data = json.loads(lpath.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("ledger_version") == LEDGER_VERSION:
                data.setdefault("conversations", {})
                return data
        except Exception:
            pass
    return {"ledger_version": LEDGER_VERSION, "conversations": {}}


def read_model_drift_status(bg_dir: Path) -> dict[str, Any]:
    """Read latest 01:45 AM model drift status JSON without failing if absent."""
    dpath = bg_dir / "model_drift_status.json"
    if dpath.is_file():
        try:
            data = json.loads(dpath.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {
        "status": "NOT_RUN",
        "checked_at": "",
        "drift_count": 0,
        "summary": "Drift check not yet run",
        "findings": [],
    }


def build_conv_ledger_entry(
    cid: str,
    cdata: dict[str, Any],
    *,
    title: str = "",
    project_id: str = "",
    project_name: str = "",
    workspace: str = "",
    is_subagent: bool = False,
    parent_id: str = "",
    agent_name: str = "",
    resolved_model: str = "",
    bg_dir: Path | None = None,
) -> dict[str, Any]:
    """Build deterministic date x model ledger summary for one scanned conversation."""
    by_date_model: dict[str, dict[str, dict[str, int]]] = {}
    day_models = cdata.get("day_models") or {}
    day_mtoks = cdata.get("day_model_tokens") or {}
    day_mcost = cdata.get("day_model_cost_micros") or {}
    day_mfore = cdata.get("day_model_forecast_micros") or {}
    day_msplits = cdata.get("day_model_token_splits") or {}
    all_days = set(day_models.keys()) | set(day_mtoks.keys()) | set(day_mcost.keys())
    for ds in sorted(all_days):
        dm = day_models.get(ds) or {}
        dtk = day_mtoks.get(ds) or {}
        dc = day_mcost.get(ds) or {}
        df = day_mfore.get(ds) or {}
        dsp = day_msplits.get(ds) or {}
        m_set = set(dm.keys()) | set(dtk.keys()) | set(dc.keys())
        if not m_set:
            continue
        day_out: dict[str, dict[str, int]] = {}
        for mk_raw in sorted(m_set):
            mk_orig = classify_model_key(mk_raw)
            mk = resolved_model or mk_orig
            sp = dsp.get(mk_raw) or [0, 0, 0]
            tok = int(dtk.get(mk_raw, 0))
            u_in, c_in, out_t = int(sp[0]), int(sp[1]), int(sp[2])
            if (u_in + c_in + out_t) == 0 and tok > 0:
                u_in, c_in, out_t = split_estimated_tokens(tok)
            same_mk = mk == mk_orig
            cm = int(dc.get(mk_raw, 0)) if (same_mk and mk_raw in dc) else compute_step_cost_micros(mk, ds, u_in, c_in, out_t, bg_dir=bg_dir)
            fm = int(df.get(mk_raw, 0)) if (same_mk and mk_raw in df) else compute_step_cost_micros(mk, ds, u_in, c_in, out_t, forecast=True, bg_dir=bg_dir)
            prev = day_out.setdefault(mk, {
                "steps": 0, "tokens": 0, "uncached_input_tokens": 0,
                "cached_input_tokens": 0, "output_tokens": 0,
                "cost_usd_micros": 0, "forecast_cost_usd_micros": 0,
            })
            prev["steps"] += int(dm.get(mk_raw, 0))
            prev["tokens"] += tok
            prev["uncached_input_tokens"] += u_in
            prev["cached_input_tokens"] += c_in
            prev["output_tokens"] += out_t
            prev["cost_usd_micros"] += cm
            prev["forecast_cost_usd_micros"] += fm
        by_date_model[ds] = day_out
    return {
        "conversation_id": cid, "title": title or cid[:8], "project_id": project_id,
        "project_name": project_name, "workspace": workspace, "is_subagent": bool(is_subagent),
        "parent_id": parent_id, "agent_name": agent_name,
        "mtime": cdata.get("mtime", 0), "size": cdata.get("size", 0), "by_date_model": by_date_model,
    }


def merge_and_persist_cost_ledger(
    bg_dir: Path,
    conv_cache: dict[str, dict[str, Any]],
    db_convs: dict[str, dict[str, Any]] | None = None,
    *,
    projects_map: dict[str, dict[str, Any]] | None = None,
    parent_model_map: dict[str, str] | None = None,
    main_mk: str = "argon",
    main_switch_date: str = "",
    agent_target_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Atomically merge live conv_cache into persistent cost_ledger.json with canonical metadata."""
    from agy_nexus.stats_series import (
        normalize_workspace_name,
        resolve_canonical_project,
        resolve_root_conversation,
        resolve_subagent_model,
    )

    db_map, pmap = db_convs or {}, projects_map or {}
    pmod, atmap = parent_model_map or {}, agent_target_map or {}
    bg_dir.mkdir(parents=True, exist_ok=True)
    lock_path = bg_dir / ".cost_ledger.lock"
    with _LEDGER_LOCK, open(lock_path, "a+", encoding="utf-8") as lf:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        try:
            os.fchmod(lf.fileno(), 0o600)
        except OSError:
            pass
        try:
            ledger = load_cost_ledger(bg_dir)
            convs, dirty = ledger.setdefault("conversations", {}), False
            for cid, cdata in conv_cache.items():
                meta = db_map.get(cid, {})
                is_sub = bool(meta.get("is_subagent"))
                root_cid = resolve_root_conversation(cid, db_map) if is_sub else cid
                root_meta = db_map.get(root_cid, meta)
                merged_meta = root_meta if (root_meta.get("project_id") or root_meta.get("workspace")) else meta
                can_pid, can_pname, can_ws = resolve_canonical_project(merged_meta, pmap)
                ws_short = normalize_workspace_name(can_ws) or "unassigned"
                if can_pid == "ws:unassigned" and not can_ws:
                    can_pid = str((convs.get(cid) or {}).get("project_id") or can_pid)
                existing = convs.get(cid)
                mtime, fsize = cdata.get("mtime", 0), cdata.get("size", 0)
                if (
                    existing and existing.get("mtime") == mtime and existing.get("size") == fsize
                    and existing.get("project_id") == can_pid and existing.get("workspace_short") == ws_short
                ):
                    continue
                role = str(meta.get("agent_name") or "subagent")
                res_mk = ""
                if is_sub:
                    last_day = max((cdata.get("day_steps") or {"": 0}).keys(), default="")
                    res_mk = resolve_subagent_model(role, root_cid, pmod, main_mk, main_switch_date, last_day, atmap)[0]
                entry = build_conv_ledger_entry(
                    cid, cdata,
                    title=str(meta.get("title") or (existing or {}).get("title") or cid[:8]),
                    project_id=can_pid, project_name=can_pname,
                    workspace=can_ws or str((existing or {}).get("workspace") or ""),
                    is_subagent=is_sub, parent_id=str(meta.get("parent_id") or ""),
                    agent_name=role if is_sub else "", resolved_model=res_mk, bg_dir=bg_dir,
                )
                entry["workspace_short"] = ws_short
                convs[cid] = entry
                dirty = True
            if dirty or not (bg_dir / "cost_ledger.json").is_file():
                _atomic_write_json_600(bg_dir / "cost_ledger.json", ledger)
            return ledger
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


def collect_archived_ledger_totals(
    ledger: dict[str, Any],
    live_cids: set[str],
    s_iso: str,
    e_iso: str,
    *,
    allowed_project_id: str = "",
) -> dict[str, Any]:
    """Aggregate historical spend from ledger entries whose brain directories were pruned."""
    convs = ledger.get("conversations") or {}
    m_keys = get_canonical_model_keys()
    model_steps, model_tokens = {k: 0 for k in m_keys}, {k: 0 for k in m_keys}
    model_cost, model_fore = {k: 0 for k in m_keys}, {k: 0 for k in m_keys}
    day_steps, day_tokens, day_cost, out_day_cost = {}, {}, {}, {}
    ws_map: dict[str, dict[str, Any]] = {}
    subagent_roles: dict[str, dict[str, Any]] = {}
    split_tot, archived_convs = [0, 0, 0], 0
    for cid, entry in convs.items():
        if cid in live_cids or not isinstance(entry, dict):
            continue
        if allowed_project_id and str(entry.get("project_id") or "") != allowed_project_id:
            continue
        ws_n = str(entry.get("workspace_short") or "").strip() or (
            Path(str(entry.get("workspace") or "")).name if entry.get("workspace") else "unassigned"
        )
        is_sub, role = bool(entry.get("is_subagent")), str(entry.get("agent_name") or "subagent")
        used, conv_st, conv_tk, conv_cm = False, 0, 0, 0
        for ds, dmap in (entry.get("by_date_model") or {}).items():
            if not isinstance(dmap, dict):
                continue
            in_win = s_iso <= ds <= e_iso
            for mk_raw, mv in dmap.items():
                if not isinstance(mv, dict):
                    continue
                cm = int(mv.get("cost_usd_micros") or 0)
                if not in_win:
                    out_day_cost[ds] = out_day_cost.get(ds, 0) + cm
                    continue
                mk = classify_model_key(mk_raw)
                st, tk, fm = int(mv.get("steps") or 0), int(mv.get("tokens") or 0), int(mv.get("forecast_cost_usd_micros") or 0)
                model_steps[mk] = model_steps.get(mk, 0) + st
                model_tokens[mk] = model_tokens.get(mk, 0) + tk
                model_cost[mk] = model_cost.get(mk, 0) + cm
                model_fore[mk] = model_fore.get(mk, 0) + fm
                day_steps[ds] = day_steps.get(ds, 0) + st
                day_tokens[ds] = day_tokens.get(ds, 0) + tk
                day_cost[ds] = day_cost.get(ds, 0) + cm
                split_tot[0] += int(mv.get("uncached_input_tokens") or 0)
                split_tot[1] += int(mv.get("cached_input_tokens") or 0)
                split_tot[2] += int(mv.get("output_tokens") or 0)
                conv_st, conv_tk, conv_cm, used = conv_st + st, conv_tk + tk, conv_cm + cm, True
        if used:
            we = ws_map.setdefault(ws_n, {"workspace": ws_n, "sessions": 0, "steps": 0, "tokens": 0, "cost_usd_micros": 0})
            if not is_sub:
                archived_convs += 1
                we["sessions"] += 1
            else:
                sr = subagent_roles.setdefault(role, {"runs": 0, "steps": 0, "tokens": 0, "cost_usd_micros": 0})
                sr["runs"], sr["steps"], sr["tokens"], sr["cost_usd_micros"] = sr["runs"] + 1, sr["steps"] + conv_st, sr["tokens"] + conv_tk, sr["cost_usd_micros"] + conv_cm
            we["steps"], we["tokens"], we["cost_usd_micros"] = we["steps"] + conv_st, we["tokens"] + conv_tk, we["cost_usd_micros"] + conv_cm
    return {
        "archived_convs": archived_convs, "model_steps": model_steps, "model_tokens": model_tokens,
        "model_cost_micros": model_cost, "model_forecast_micros": model_fore,
        "day_steps": day_steps, "day_tokens": day_tokens, "day_cost_micros": day_cost,
        "out_of_window_daily_cost": out_day_cost, "ws_map": ws_map, "subagent_roles": subagent_roles,
        "token_split": split_tot,
    }


def compute_hourly_whiskers(
    s1_steps: dict[str, int],
    s1_toks: dict[str, int],
    s1_cost_micros: dict[str, int],
    start_d: date,
    end_d: date,
    today_d: date,
    now_hour: int,
) -> dict[str, Any]:
    """Compute active-day 00h-23h Min/Avg/Max whiskers plus trailing 24h dot across steps, tokens, and USD."""
    s_iso, e_iso = start_d.strftime("%Y-%m-%d"), end_d.strftime("%Y-%m-%d")
    today_iso = today_d.strftime("%Y-%m-%d")
    yest_iso = (today_d - timedelta(days=1)).strftime("%Y-%m-%d")
    has_l24 = start_d <= today_d <= end_d

    active_day_hours: dict[str, dict[int, tuple[int, int, int]]] = {}
    for sl_k in set(s1_steps.keys()) | set(s1_toks.keys()) | set(s1_cost_micros.keys()):
        if len(sl_k) < 13 or sl_k[10] != "T":
            continue
        ds = sl_k[:10]
        if not (s_iso <= ds <= e_iso):
            continue
        try:
            hr = int(sl_k[11:13])
        except ValueError:
            continue
        if not (0 <= hr <= 23):
            continue
        st = int(s1_steps.get(sl_k, 0))
        tk = int(s1_toks.get(sl_k, 0))
        cm = int(s1_cost_micros.get(sl_k, 0))
        if st > 0 or tk > 0 or cm > 0:
            active_day_hours.setdefault(ds, {})[hr] = (st, tk, cm)

    def _summarize(metric_idx: int, as_usd: bool = False) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for h in range(24):
            obs = [day_map[h][metric_idx] for day_map in active_day_hours.values() if h in day_map]
            slot_24 = f"{today_iso}T{h:02d}" if h <= now_hour else f"{yest_iso}T{h:02d}"
            in_win_l24 = has_l24 and (s_iso <= slot_24[:10] <= e_iso)
            l24_raw = (
                int(s1_steps.get(slot_24, 0))
                if metric_idx == 0
                else (int(s1_toks.get(slot_24, 0)) if metric_idx == 1 else int(s1_cost_micros.get(slot_24, 0)))
            ) if in_win_l24 else None
            if not obs:
                mn, av, mx = 0, 0, 0
            else:
                mn, av, mx = min(obs), sum(obs) / len(obs), max(obs)
            if as_usd:
                rows.append({
                    "min": round(mn / 1_000_000.0, 4),
                    "avg": round(av / 1_000_000.0, 4),
                    "max": round(mx / 1_000_000.0, 4),
                    "last_24h": round(l24_raw / 1_000_000.0, 4) if l24_raw is not None else None,
                    "active_days": len(obs),
                })
            else:
                rows.append({
                    "min": int(mn),
                    "avg": round(av, 1),
                    "max": int(mx),
                    "last_24h": int(l24_raw) if l24_raw is not None else None,
                    "active_days": len(obs),
                })
        return rows

    return {
        "hours": [f"{h:02d}h" for h in range(24)],
        "active_days_count": len(active_day_hours),
        "has_last_24h": has_l24,
        "steps": _summarize(0, as_usd=False),
        "tokens": _summarize(1, as_usd=False),
        "cost": _summarize(2, as_usd=True),
    }
