#!/usr/bin/env python3
"""
agy_nexus.stats_metrics — Per-Run Subagent Range, Active-Day Project Range & Trailing-24h Helpers.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any


def compute_trailing_24h_slots(
    start_d: date,
    end_d: date,
    today: date,
    now_hour: int,
) -> tuple[bool, set[str]]:
    """Return (has_last_24h, slot_1h_keys) for the trailing 24 hours inside [start_d, end_d]."""
    if not (start_d <= today <= end_d):
        return False, set()
    s_iso, e_iso = start_d.strftime("%Y-%m-%d"), end_d.strftime("%Y-%m-%d")
    today_iso = today.strftime("%Y-%m-%d")
    yest_iso = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    slots: set[str] = set()
    for h in range(24):
        sl = f"{today_iso}T{h:02d}" if h <= now_hour else f"{yest_iso}T{h:02d}"
        if s_iso <= sl[:10] <= e_iso:
            slots.add(sl)
    return True, slots


def sum_slots_in_set(slot_map: dict[str, int] | None, slots: set[str]) -> int:
    """Sum integer slot counters for keys present in slots."""
    if not slot_map or not slots:
        return 0
    return sum(int(slot_map.get(sl, 0)) for sl in slots)


def slot_key_epoch(slot_map: dict[str, Any] | None, tz: Any) -> float:
    """Parse latest YYYY-MM-DDTHH slot key into epoch seconds as a chronological fallback."""
    if not slot_map:
        return 0.0
    valid = [str(k)[:13] for k in slot_map if len(str(k)) >= 13 and str(k)[10] == "T"]
    if not valid:
        return 0.0
    try:
        dt = datetime.strptime(max(valid), "%Y-%m-%dT%H").replace(tzinfo=tz)
        return dt.timestamp()
    except Exception:
        return 0.0


def init_subagent_role_record() -> dict[str, Any]:
    """Return a clean zero-initialized subagent role accumulator with per-run range tracking."""
    return {
        "runs": 0, "steps": 0, "tokens": 0, "cost_usd_micros": 0,
        "min_steps_per_run": 0, "max_steps_per_run": 0, "last_run_steps": 0,
        "min_tokens_per_run": 0, "max_tokens_per_run": 0, "last_run_tokens": 0,
        "min_cost_micros_per_run": 0, "max_cost_micros_per_run": 0, "last_run_cost_micros": 0,
        "over_120_runs": 0, "_latest_ts": -1.0,
    }


def fold_subagent_run_sample(
    rec: dict[str, Any],
    steps: int,
    tokens: int,
    cost_micros: int,
    *,
    run_ts: float = 0.0,
    over_120: bool = False,
) -> None:
    """Fold one subagent run into role totals, min/max per-run bounds, >120-step flag, and latest run."""
    st_i, tk_i, cm_i = max(0, int(steps)), max(0, int(tokens)), max(0, int(cost_micros))
    prev_runs = int(rec.get("runs") or 0)
    rec["runs"] = prev_runs + 1
    rec["steps"] = int(rec.get("steps") or 0) + st_i
    rec["tokens"] = int(rec.get("tokens") or 0) + tk_i
    rec["cost_usd_micros"] = int(rec.get("cost_usd_micros") or 0) + cm_i
    if over_120 or st_i > 120:
        rec["over_120_runs"] = int(rec.get("over_120_runs") or 0) + 1
    for k_min, k_max, val in (
        ("min_steps_per_run", "max_steps_per_run", st_i),
        ("min_tokens_per_run", "max_tokens_per_run", tk_i),
        ("min_cost_micros_per_run", "max_cost_micros_per_run", cm_i),
    ):
        if prev_runs == 0:
            rec[k_min], rec[k_max] = val, val
        else:
            p_min, p_max = rec.get(k_min), rec.get(k_max)
            rec[k_min] = val if p_min is None else min(int(p_min), val)
            rec[k_max] = val if p_max is None else max(int(p_max), val)
    ts_val = float(run_ts or 0.0)
    if prev_runs == 0 or ts_val >= float(rec.get("_latest_ts", -1.0)):
        rec["_latest_ts"] = ts_val
        rec["last_run_steps"], rec["last_run_tokens"], rec["last_run_cost_micros"] = st_i, tk_i, cm_i


def merge_subagent_role_stats(dst: dict[str, Any], src: dict[str, Any]) -> None:
    """Merge an archived/secondary subagent role accumulator into dst preserving min/max/latest."""
    src_runs = int(src.get("runs") or 0)
    if src_runs <= 0:
        return
    dst_runs = int(dst.get("runs") or 0)
    dst["runs"] = dst_runs + src_runs
    dst["steps"] = int(dst.get("steps") or 0) + int(src.get("steps") or 0)
    dst["tokens"] = int(dst.get("tokens") or 0) + int(src.get("tokens") or 0)
    dst["cost_usd_micros"] = int(dst.get("cost_usd_micros") or 0) + int(src.get("cost_usd_micros") or 0)
    dst["over_120_runs"] = int(dst.get("over_120_runs") or 0) + int(src.get("over_120_runs") or 0)
    for k_min, k_max in (
        ("min_steps_per_run", "max_steps_per_run"),
        ("min_tokens_per_run", "max_tokens_per_run"),
        ("min_cost_micros_per_run", "max_cost_micros_per_run"),
    ):
        s_min_raw, s_max_raw = src.get(k_min), src.get(k_max)
        if s_min_raw is not None:
            s_min, d_min_raw = int(s_min_raw), dst.get(k_min)
            dst[k_min] = s_min if (dst_runs == 0 or d_min_raw is None) else min(int(d_min_raw), s_min)
        if s_max_raw is not None:
            dst[k_max] = max(int(dst.get(k_max) or 0), int(s_max_raw))
    src_ts = float(src.get("_latest_ts", -1.0))
    if dst_runs == 0 or src_ts >= float(dst.get("_latest_ts", -1.0)):
        dst["_latest_ts"] = src_ts
        for lk in ("last_run_steps", "last_run_tokens", "last_run_cost_micros"):
            dst[lk] = int(src.get(lk) or 0)


def compute_daily_range_metrics(
    s1_steps: dict[str, int],
    s1_toks: dict[str, int],
    s1_cost: dict[str, int],
    l24_slots: set[str],
    has_l24: bool,
    *,
    fallback_steps: int = 0,
    fallback_tokens: int = 0,
    fallback_cost_micros: int = 0,
) -> dict[str, Any]:
    """Compute active-day min/avg/max and trailing-24h metrics across steps, tokens, and USD."""
    d_st: dict[str, int] = {}
    d_tk: dict[str, int] = {}
    d_cm: dict[str, int] = {}
    for sl_k, v in (s1_steps or {}).items():
        d_st[sl_k[:10]] = d_st.get(sl_k[:10], 0) + int(v or 0)
    for sl_k, v in (s1_toks or {}).items():
        d_tk[sl_k[:10]] = d_tk.get(sl_k[:10], 0) + int(v or 0)
    for sl_k, v in (s1_cost or {}).items():
        d_cm[sl_k[:10]] = d_cm.get(sl_k[:10], 0) + int(v or 0)
    days = [d for d in (set(d_st) | set(d_tk) | set(d_cm)) if d_st.get(d, 0) > 0 or d_tk.get(d, 0) > 0 or d_cm.get(d, 0) > 0]
    if not days and (fallback_steps > 0 or fallback_tokens > 0 or fallback_cost_micros > 0):
        st_v, tk_v, cm_v = int(fallback_steps), int(fallback_tokens), int(fallback_cost_micros)
        usd_v = round(cm_v / 1_000_000.0, 4)
        return {
            "active_days": 1,
            "min_daily_steps": st_v, "avg_daily_steps": float(st_v), "max_daily_steps": st_v,
            "min_daily_tokens": tk_v, "avg_daily_tokens": tk_v, "max_daily_tokens": tk_v,
            "min_daily_cost_usd": usd_v, "avg_daily_cost_usd": usd_v, "max_daily_cost_usd": usd_v,
            "has_last_24h": has_l24,
            "last_24h_steps": 0 if has_l24 else None,
            "last_24h_tokens": 0 if has_l24 else None,
            "last_24h_cost_usd": 0.0 if has_l24 else None,
        }
    n_days = len(days)
    st_vals = [d_st.get(d, 0) for d in days] or [0]
    tk_vals = [d_tk.get(d, 0) for d in days] or [0]
    cm_vals = [d_cm.get(d, 0) for d in days] or [0]
    denom = max(1, n_days)
    l24_st = sum_slots_in_set(s1_steps, l24_slots) if has_l24 else None
    l24_tk = sum_slots_in_set(s1_toks, l24_slots) if has_l24 else None
    l24_cm = sum_slots_in_set(s1_cost, l24_slots) if has_l24 else None
    return {
        "active_days": n_days,
        "min_daily_steps": min(st_vals),
        "avg_daily_steps": round(sum(st_vals) / denom, 1) if n_days else 0.0,
        "max_daily_steps": max(st_vals),
        "min_daily_tokens": min(tk_vals),
        "avg_daily_tokens": round(sum(tk_vals) / denom) if n_days else 0,
        "max_daily_tokens": max(tk_vals),
        "min_daily_cost_usd": round(min(cm_vals) / 1_000_000.0, 4),
        "avg_daily_cost_usd": round((sum(cm_vals) / denom) / 1_000_000.0, 4) if n_days else 0.0,
        "max_daily_cost_usd": round(max(cm_vals) / 1_000_000.0, 4),
        "has_last_24h": has_l24,
        "last_24h_steps": l24_st,
        "last_24h_tokens": l24_tk,
        "last_24h_cost_usd": round(l24_cm / 1_000_000.0, 4) if l24_cm is not None else None,
    }


def build_subagent_list_rows(
    agg: dict[str, Any],
    act_d: int,
    act_w: float,
    l24_slots: set[str],
    has_l24: bool,
    *,
    resolve_model_fn: Any,
    short_labels: dict[str, str],
    e_iso: str,
    parent_model_map: dict[str, str],
    main_mk: str,
    main_switch_date: str,
    agent_target_map: dict[str, str],
    agent_role_specs: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Format subagent role accumulators with per-run min/avg/max/latest, >120 flags, trailing 24h & intended-vs-actual adjudication."""
    from agy_nexus.catalog_report import build_subagent_adjudication

    sa_sum = max(1, sum(int(v.get("steps", 0)) for v in agg["subagent_roles"].values()))
    out: list[dict[str, Any]] = []
    for rk, rv in sorted(agg["subagent_roles"].items(), key=lambda kv: kv[1]["steps"], reverse=True):
        rv.pop("_latest_ts", None)
        tk, st_s = int(rv.get("tokens", 0)), int(rv.get("steps", 0))
        runs, cm_s = int(rv.get("runs", 0)), int(rv.get("cost_usd_micros", 0))
        votes = agg["role_model_votes"].get(rk) or {}
        dom_mk = max(votes.items(), key=lambda kv: kv[1])[0] if votes else resolve_model_fn(
            rk, "", parent_model_map, main_mk, main_switch_date, e_iso, agent_target_map
        )[0]
        r_spec = (agent_role_specs or {}).get(rk.lower())
        adj = build_subagent_adjudication(rk, votes, dom_mk, bool(agg["role_inherited"].get(rk)), r_spec, short_labels)
        dom_lbl = short_labels.get(dom_mk, dom_mk) + (" (inherit)" if adj["is_inherited"] else "")
        denom = max(1, runs)
        l24_st = sum_slots_in_set(agg["s1_sub_steps"].get(rk), l24_slots) if has_l24 else None
        l24_tk = sum_slots_in_set(agg["s1_sub_toks"].get(rk), l24_slots) if has_l24 else None
        l24_cm = sum_slots_in_set(agg["s1_sub_cost"].get(rk), l24_slots) if has_l24 else None
        rv.update({
            "tok_per_day": round(tk / act_d), "tok_per_week": round(tk / act_w),
            "avg_steps_per_run": round(st_s / denom, 1),
            "avg_tokens_per_run": round(tk / denom),
            "avg_cost_usd_per_run": round((cm_s / denom) / 1_000_000.0, 4),
            "min_cost_usd_per_run": round(int(rv.get("min_cost_micros_per_run", 0)) / 1_000_000.0, 4),
            "max_cost_usd_per_run": round(int(rv.get("max_cost_micros_per_run", 0)) / 1_000_000.0, 4),
            "last_run_cost_usd": round(int(rv.get("last_run_cost_micros", 0)) / 1_000_000.0, 4),
            "cost_usd_micros": cm_s, "est_cost_usd": round(cm_s / 1_000_000.0, 2),
            "share_pct": round((st_s / sa_sum) * 100.0, 1),
            "dominant_model_key": dom_mk, "dominant_model_label": dom_lbl,
            **adj,
            "has_last_24h": has_l24, "last_24h_steps": l24_st, "last_24h_tokens": l24_tk,
            "last_24h_cost_usd": round(l24_cm / 1_000_000.0, 4) if l24_cm is not None else None,
        })
        out.append({"role": rk, **rv})
    return out


def build_model_comparison_rows(
    agg: dict[str, Any],
    quota_info: dict[str, Any],
    e_iso: str,
    l24_slots: set[str],
    has_l24: bool,
    *,
    canonical_keys: list[str],
    specs: dict[str, dict[str, Any]],
    short_labels: dict[str, str],
    resolve_rate_epoch_fn: Any,
    bg_dir: Any,
) -> list[dict[str, Any]]:
    """Build 8-model workload comparison rows including token/cost shares and trailing-24h metrics."""
    targets = quota_info["target_model_allocation"]
    tot_calls = max(1, sum(int(v) for v in agg["model_totals"].values()))
    tot_tokens = max(1, sum(int(v) for v in agg["model_tokens"].values()))
    tot_cost = max(1, sum(int(v) for v in agg["model_cost"].values()))
    out: list[dict[str, Any]] = []
    for mk in canonical_keys:
        sp = specs.get(mk, {})
        tm = targets.get(mk, {
            "label": sp.get("label", mk), "pool": sp.get("pool_label", "Unknown"),
            "pool_key": sp.get("pool_key", "google"), "quota_group": sp.get("quota_group", "Gemini Models"), "target_pct": 0.0,
        })
        ac = int(agg["model_totals"].get(mk, 0))
        tk_m = int(agg["model_tokens"].get(mk, 0))
        cm_m = int(agg["model_cost"].get(mk, 0))
        fm_m = int(agg["model_fore"].get(mk, 0))
        ap, tp = round((ac / tot_calls) * 100.0, 1), float(tm.get("target_pct", 0.0))
        dp = round(ap - tp, 1)
        epoch = resolve_rate_epoch_fn(mk, e_iso, bg_dir=bg_dir)
        l24_st = sum_slots_in_set(agg["s1_mod_steps"].get(mk), l24_slots) if has_l24 else None
        l24_tk = sum_slots_in_set(agg["s1_mod_toks"].get(mk), l24_slots) if has_l24 else None
        l24_cm = sum_slots_in_set(agg["s1_mod_cost"].get(mk), l24_slots) if has_l24 else None
        out.append({
            "model_key": mk, "label": str(tm.get("label") or sp.get("label") or mk),
            "short_label": str(sp.get("short_label") or short_labels.get(mk, mk)),
            "pool": str(tm.get("pool") or sp.get("pool_label") or "Unknown"),
            "pool_key": str(tm.get("pool_key") or sp.get("pool_key") or "google"),
            "quota_group": str(tm.get("quota_group") or sp.get("quota_group") or "Gemini Models"),
            "rate_label": f"${epoch['input_micros'] / 1_000_000:.2f}/${epoch['output_micros'] / 1_000_000:.2f}",
            "actual_calls": ac, "est_tokens": tk_m, "cost_usd_micros": cm_m,
            "est_cost_usd": round(cm_m / 1_000_000.0, 2),
            "forecast_cost_micros": fm_m, "forecast_cost_usd": round(fm_m / 1_000_000.0, 2),
            "actual_pct": ap, "token_share_pct": round((tk_m / tot_tokens) * 100.0, 1),
            "cost_share_pct": round((cm_m / tot_cost) * 100.0, 1),
            "target_pct": tp, "delta_pct": dp,
            "has_last_24h": has_l24, "last_24h_steps": l24_st, "last_24h_tokens": l24_tk,
            "last_24h_cost_usd": round(l24_cm / 1_000_000.0, 4) if l24_cm is not None else None,
            "status": "ON_TARGET" if abs(dp) <= 12.0 else ("OVER_TARGET" if dp > 12.0 else "UNDER_TARGET"),
        })
    return out


def _slot_set_for_epoch_span(start_epoch: float, end_epoch: float, tz: Any) -> set[str]:
    s_dt = datetime.fromtimestamp(start_epoch, tz=tz).replace(minute=0, second=0, microsecond=0)
    e_dt = datetime.fromtimestamp(end_epoch, tz=tz).replace(minute=0, second=0, microsecond=0)
    out: set[str] = set()
    cur = s_dt
    while cur <= e_dt:
        out.add(cur.strftime("%Y-%m-%dT%H"))
        cur += timedelta(hours=1)
    return out


def _add_pool_burn(acc: dict[str, list[int]], slots_5: set[str], slots_7: set[str], sl_k: str, pk: str, st: int, tk: int, cm: int) -> None:
    if sl_k in slots_5:
        b5 = acc[pk]["5h"]
        b5[0], b5[1], b5[2] = b5[0] + st, b5[1] + tk, b5[2] + cm
    if sl_k in slots_7:
        b7 = acc[pk]["7d"]
        b7[0], b7[1], b7[2] = b7[0] + st, b7[1] + tk, b7[2] + cm


def compute_pool_window_burn(
    full_conv_cache: dict[str, dict[str, Any]],
    db_convs: dict[str, dict[str, Any]],
    quota_info: dict[str, Any],
    now_loc: datetime,
    *,
    specs: dict[str, dict[str, Any]],
    classify_fn: Any,
    compute_cost_fn: Any,
    split_fn: Any,
    resolve_root_fn: Any,
    resolve_subagent_fn: Any,
    parent_model_map: dict[str, str],
    main_mk: str,
    main_switch_date: str,
    agent_target_map: dict[str, str],
    display_tz: Any,
    bg_dir: Any,
) -> dict[str, dict[str, Any]]:
    """Compute steps, tokens, and API-equivalent USD burned inside each pool's active 5h and 7d windows."""
    now_ep = now_loc.timestamp()
    pools = quota_info.get("pools") or {}
    is_fresh = bool((quota_info.get("live_quota") or {}).get("is_fresh"))
    slots_5: dict[str, set[str]] = {}
    slots_7: dict[str, set[str]] = {}
    win_src: dict[str, tuple[str, str]] = {}
    for pk in ("google", "claude"):
        po = pools.get(pk) or {}
        b5, bw = po.get("bucket_5h") or {}, po.get("bucket_weekly") or {}
        use_r5 = is_fresh and bool(b5.get("has_active_reset") and b5.get("window_start_epoch"))
        use_rw = is_fresh and bool(bw.get("has_active_reset") and bw.get("window_start_epoch"))
        s5 = float(b5["window_start_epoch"]) if use_r5 else (now_ep - 5 * 3600)
        sw = float(bw["window_start_epoch"]) if use_rw else (now_ep - 7 * 86400)
        slots_5[pk] = _slot_set_for_epoch_span(min(s5, now_ep), now_ep, display_tz)
        slots_7[pk] = _slot_set_for_epoch_span(min(sw, now_ep), now_ep, display_tz)
        win_src[pk] = ("reset_window" if use_r5 else "trailing_5h", "reset_window" if use_rw else "trailing_7d")
    all_slots = slots_5["google"] | slots_7["google"] | slots_5["claude"] | slots_7["claude"]
    acc = {pk: {"5h": [0, 0, 0], "7d": [0, 0, 0]} for pk in ("google", "claude")}
    for cid, cdata in full_conv_cache.items():
        meta = db_convs.get(cid, {})
        is_sub, role = bool(meta.get("is_subagent")), str(meta.get("agent_name") or "subagent")
        root_cid = resolve_root_fn(cid, db_convs) if is_sub else cid
        s1_mods, s1_mtoks, s1_mc = cdata.get("slot_1h_models") or {}, cdata.get("slot_1h_model_tokens") or {}, cdata.get("slot_1h_model_cost_micros") or {}
        s1_st, s1_tk, s1_cs = cdata.get("slot_1h_steps") or {}, cdata.get("slot_1h_tokens") or {}, cdata.get("slot_1h_cost_micros") or {}
        exp_days = cdata.get("explicit_day_models") or {}
        for sl_k in (set(s1_mods) | set(s1_mtoks) | set(s1_st)) & all_slots:
            md_s, md_t, md_c = s1_mods.get(sl_k), s1_mtoks.get(sl_k), s1_mc.get(sl_k)
            if isinstance(md_s, dict) or isinstance(md_t, dict):
                ek = {classify_fn(k) for k, v in (exp_days.get(sl_k[:10]) or {}).items() if int(v) > 0} if is_sub else set()
                smk = resolve_subagent_fn(role, root_cid, parent_model_map, main_mk, main_switch_date, sl_k, agent_target_map)[0] if is_sub else ""
                for mk_r in set(md_s or {}) | set(md_t or {}):
                    mk_raw = classify_fn(mk_r)
                    dst_mk = mk_raw if (not is_sub or mk_raw in ek) else smk
                    pk = "google" if str((specs.get(dst_mk) or {}).get("pool_key") or "google") == "google" else "claude"
                    tk_v = int((md_t or {}).get(mk_r) or 0)
                    cm_v = int(md_c[mk_r]) if (isinstance(md_c, dict) and mk_r in md_c and dst_mk == mk_raw) else compute_cost_fn(dst_mk, sl_k[:10], *split_fn(tk_v), bg_dir=bg_dir)
                    _add_pool_burn(acc, slots_5[pk], slots_7[pk], sl_k, pk, int((md_s or {}).get(mk_r) or 0), tk_v, cm_v)
            else:
                dst_mk = resolve_subagent_fn(role, root_cid, parent_model_map, main_mk, main_switch_date, sl_k, agent_target_map)[0] if is_sub else classify_fn(str(cdata.get("last_conv_model") or main_mk or "argon"))
                pk = "google" if str((specs.get(dst_mk) or {}).get("pool_key") or "google") == "google" else "claude"
                _add_pool_burn(acc, slots_5[pk], slots_7[pk], sl_k, pk, int(s1_st.get(sl_k) or 0), int(s1_tk.get(sl_k) or 0), int(s1_cs.get(sl_k) or 0))
    return {
        pk: {
            "burn_5h": {"steps": acc[pk]["5h"][0], "tokens": acc[pk]["5h"][1], "cost_usd": round(acc[pk]["5h"][2] / 1_000_000.0, 2), "window_source": win_src[pk][0]},
            "burn_7d": {"steps": acc[pk]["7d"][0], "tokens": acc[pk]["7d"][1], "cost_usd": round(acc[pk]["7d"][2] / 1_000_000.0, 2), "window_source": win_src[pk][1]},
        }
        for pk in ("google", "claude")
    }
