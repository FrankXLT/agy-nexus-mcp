#!/usr/bin/env python3
"""
agy-nexus-mcp — Default (72-Col) & Quick (40-Col) Monospace ASCII Telemetry Renderers
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from agy_nexus.model_pricing import format_usd, get_model_specs_map
from . import __version__


def is_google_pool_model(m: dict[str, Any]) -> bool:
    """Classify a model breakdown entry into Google vs Partner pool dynamically without hardcoded keys."""
    pk = str(m.get("pool_key") or "").strip().lower()
    if pk:
        return pk == "google"
    pool = str(m.get("pool") or "").lower()
    if "google" in pool or "20x" in pool:
        return True
    return "gemini" in str(m.get("quota_group") or "").lower()


def get_model_short_labels() -> tuple[dict[str, str], dict[str, str]]:
    """Return (short_11_map, short_7_map) dynamically from model_catalog.json."""
    specs = get_model_specs_map()
    s11: dict[str, str] = {}
    s7: dict[str, str] = {}
    for mk, sp in specs.items():
        lbl = str(sp.get("short_label") or sp.get("label") or mk)
        s11[mk] = str(sp.get("short_11") or lbl[:11]).ljust(11)[:11]
        s7[mk] = str(sp.get("short_7") or lbl[:7]).ljust(7)[:7]
    return s11, s7

def fmt_tok(val: int | float, tilde: bool = True) -> str:
    v, p = float(val or 0), ("~" if tilde else "")
    if v <= 0:
        return "0"
    if v >= 1_000_000_000:
        return f"{p}{v / 1_000_000_000.0:.1f}B"
    if v >= 1_000_000:
        return f"{p}{v / 1_000_000.0:.1f}M"
    if v >= 100_000:
        return f"{p}{v / 1_000.0:.0f}k"
    if v >= 1_000:
        return f"{p}{v / 1_000.0:.1f}k"
    return f"{int(v)}"

def fmt_rate(val: int | float) -> str:
    v = float(val or 0)
    if v <= 0:
        return "0"
    if v >= 1_000_000_000:
        return f"{v / 1_000_000_000.0:.2f}B"
    if v >= 10_000_000:
        return f"{v / 1_000_000.0:.1f}M"
    if v >= 1_000_000:
        return f"{v / 1_000_000.0:.2f}M"
    if v >= 10_000:
        return f"{v / 1_000.0:.0f}k"
    if v >= 1_000:
        return f"{v / 1_000.0:.1f}k"
    return f"{int(v)}"

def fmt_k(val: int | float) -> str:
    v = float(val or 0)
    return f"{v / 1_000.0:.1f}k" if v >= 1_000 else f"{int(v)}"

def fmt_short_date(iso_str: str) -> str:
    try:
        return datetime.strptime(iso_str[:10], "%Y-%m-%d").strftime("%b %d")
    except Exception:
        return iso_str[:10]

def build_quota_bar_with_pin(actual_pct: float, target_pct: float, width: int = 20) -> str:
    filled = max(0, min(width, round((max(0.0, actual_pct) / 100.0) * width)))
    cells = ["█" if i < filled else "░" for i in range(width)]
    if 0 < filled < width and (actual_pct / 100.0) * width - filled > -0.35:
        cells[min(width - 1, filled)] = "▓"
    pin_idx = max(0, min(width - 1, round((max(0.0, target_pct) / 100.0) * (width - 1))))
    cells[pin_idx] = "▏" if pin_idx == 0 else "┼"
    return "".join(cells)

def build_reversed_weeks(heatmap_series: list[dict[str, Any]], num_weeks: int = 22) -> list[dict[str, Any]]:
    """Group daily heatmap_series into Monday..Sunday weeks ordered NEWEST (W01) on LEFT to OLDEST on RIGHT."""
    weeks_chron: list[dict[str, Any]] = []
    cur_week: dict[int, dict[str, Any]] = {}
    for item in heatmap_series:
        wd = int(item.get("weekday", 0))
        if wd == 0 and cur_week:
            weeks_chron.append({"days": cur_week, "steps": sum(d.get("steps", 0) for d in cur_week.values())})
            cur_week = {}
        cur_week[wd] = item
    if cur_week:
        weeks_chron.append({"days": cur_week, "steps": sum(d.get("steps", 0) for d in cur_week.values())})
    rev = list(reversed(weeks_chron))[:num_weeks]
    while len(rev) < num_weeks:
        rev.append({"days": {}, "steps": 0})
    return rev

def build_reversed_8h_stack_canvas(
    bundle: dict[str, Any], width: int = 65, height: int = 4
) -> tuple[list[str], list[str], int, int]:
    """Render reversed (NOW on LEFT -> OLDER on RIGHT) 2x half-block curve + dithered project stack."""
    vel_obj = bundle.get("velocity_series") or {}
    ws_obj = bundle.get("workspace_series") or {}
    vals_rev = list(reversed(list(vel_obj.get("values") or [0]))) or [0]
    dates_rev = list(reversed(list(vel_obj.get("dates") or [""]))) or [""]
    ws_keys = list(ws_obj.get("keys") or [])[:3]
    ws_layers = ws_obj.get("layers") or {}
    n_src = len(vals_rev)

    col_vals, col_dates, col_ws_dom = [], [], []
    shades_rank = ["█", "▓", "▒"]
    for c in range(width):
        idx = min(n_src - 1, int((c / max(1, width - 1)) * (n_src - 1)))
        col_vals.append(int(vals_rev[idx]))
        col_dates.append(str(dates_rev[idx])[:10])
        rev_idx = n_src - 1 - idx
        best_sh, best_v = "░", 0
        for r_i, wk in enumerate(ws_keys):
            arr = ws_layers.get(wk) or []
            wv = int(arr[rev_idx]) if 0 <= rev_idx < len(arr) else 0
            if wv > best_v:
                best_v, best_sh = wv, shades_rank[r_i]
        col_ws_dom.append(best_sh if best_v > 0 else "░")

    peak_v = max(max(col_vals, default=1), 100)
    nz_vals = [v for v in col_vals if v > 0]
    avg_v = int(round(sum(nz_vals) / max(1, len(nz_vals)))) if nz_vals else int(peak_v * 0.33)
    sub_h = height * 2
    avg_row = max(1, min(height - 2, height - 1 - int(round((avg_v / max(1, peak_v)) * (height - 1)))))

    grid = [[" " for _ in range(width)] for _ in range(height)]
    for c in range(width):
        v, dom_ch = col_vals[c], col_ws_dom[c]
        level_2x = max(0, min(sub_h, int(round((v / float(peak_v)) * sub_h))))
        for r in range(height):
            low_sub = (height - 1 - r) * 2
            if level_2x > low_sub + 1:
                grid[r][c] = "█" if r < height - 1 else dom_ch
            elif level_2x > low_sub:
                grid[r][c] = "▄"
            elif r == avg_row:
                grid[r][c] = "─"
    return ["".join(r) for r in grid], col_dates, peak_v, avg_v

def _build_default_tables_72(
    models: list[dict[str, Any]],
    billing: dict[str, Any],
    workspaces: list[dict[str, Any]],
    subagents: list[dict[str, Any]],
) -> list[str]:
    """Render dynamic 8-model quota/cost table, billing comparison, workspaces, and subagents (<= 72 cols)."""
    s11, _ = get_model_short_labels()
    lines = [
        "────────────────────────────────────────────────────────────────────────",
        "MODEL       [QUOTA ┼ TARGET] SHARE    CALLS     TOK    EST.$  DLT  STAT",
    ]
    for m in models:
        mk = str(m.get("model_key", ""))
        ml = s11.get(mk, str(m.get("short_label") or m.get("label") or mk)[:11].ljust(11))
        ap, tp, dp = float(m.get("actual_pct", 0.0)), float(m.get("target_pct", 0.0)), float(m.get("delta_pct", 0.0))
        b14 = build_quota_bar_with_pin(ap, tp, width=14)
        calls = int(m.get("actual_calls", 0))
        tks = fmt_tok(int(m.get("est_tokens", 0)), False)
        usd_s = format_usd(float(m.get("est_cost_usd", 0.0) or 0.0))
        stat = "OK  " if abs(dp) <= 12.0 else "WARN"
        lines.append(f"{ml} [{b14}] {ap:>4.1f}% {calls:>7,} {tks:>7} {usd_s:>7} {dp:>+4.0f}% {stat}"[:72])

    if billing:
        h_u, f_u = float(billing.get("historical_usd", 0.0) or 0.0), float(billing.get("forecast_usd", 0.0) or 0.0)
        d_pct = float(billing.get("forecast_delta_pct", 0.0) or 0.0)
        tiers = billing.get("tiers") or []
        u20 = next((t for t in tiers if "20x" in str(t.get("id") or "")), tiers[-1] if tiers else {})
        mult = float(u20.get("value_multiplier", 0.0) or 0.0)
        lines.append(
            f"BILLING    Hist:{format_usd(h_u)} API | NextRate:{format_usd(f_u)} ({d_pct:+.0f}%) | 20x:{mult:.1f}x"[:72]
        )

    lines.extend(["────────────────────────────────────────────────────────────────────────", f"{f'WORKSPACES ({len(workspaces)})':<17}CHATS  STEPS    TOK   TOK/D   TOK/WK   EST.$  SHARE"[:72]])
    for idx, w in enumerate(workspaces, start=1):
        wn = f"{idx}. {str(w.get('workspace', 'root'))}"[:16].ljust(16)
        usd_w = format_usd(float(w.get("est_cost_usd", 0.0) or 0.0))
        lines.append(
            f"{wn} {int(w.get('sessions', 0)):>3}c {int(w.get('steps', 0)):>6,} {fmt_tok(w.get('tokens', 0), False):>7} "
            f"{fmt_rate(w.get('tok_per_day', 0)):>6} {fmt_rate(w.get('tok_per_week', 0)):>7} {usd_w:>7} {float(w.get('share_pct', 0.0)):>5.1f}%"[:72]
        )

    if subagents:
        lines.extend(["────────────────────────────────────────────────────────────────────────", f"{f'SUBAGENTS ({len(subagents)})':<17} RUNS  STEPS    TOK   TOK/D   TOK/WK   EST.$  SHARE"[:72]])
        for idx, sa in enumerate(subagents, start=1):
            sn = f"{idx}. {str(sa.get('role', 'subagent'))}"[:16].ljust(16)
            usd_s = format_usd(float(sa.get("est_cost_usd", 0.0) or 0.0))
            lines.append(
                f"{sn} {int(sa.get('runs', 0)):>3}r {int(sa.get('steps', 0)):>6,} {fmt_tok(sa.get('tokens', 0), False):>7} "
                f"{fmt_rate(sa.get('tok_per_day', 0)):>6} {fmt_rate(sa.get('tok_per_week', 0)):>7} {usd_s:>7} {float(sa.get('share_pct', 0.0)):>5.1f}%"[:72]
            )
    lines.append("════════════════════════════════════════════════════════════════════════")
    return lines


def render_ascii_default(bundle: dict[str, Any]) -> str:
    """Render Default 72-Column Stats: 2-col split header (40┆31), then full-width 72-col sections."""
    kpis, period = bundle.get("kpis") or {}, bundle.get("period") or {}
    quota, wire = bundle.get("quota_and_pools") or {}, bundle.get("wire_telemetry") or {}
    models = bundle.get("model_usage_vs_target") or []
    workspaces = bundle.get("all_workspaces") or bundle.get("top_workspaces") or []
    subagents = bundle.get("subagent_list") or []
    series = bundle.get("heatmap_series") or []
    billing = bundle.get("billing_comparison") or {}

    s_dt, e_dt = fmt_short_date(str(period.get("start_date") or "")), fmt_short_date(str(period.get("end_date") or ""))
    act_days = max(1, int(kpis.get("active_days", period.get("active_days", 1)) or 1))
    cal_days = max(1, int(period.get("total_days", 90) or 90))
    tot_steps, tot_tools = int(kpis.get("window_steps", 0)), int(kpis.get("window_tool_calls", 0))
    tot_chats, tot_subs = int(kpis.get("total_conversations", 0)), int(kpis.get("total_subagents_spawned", 0))
    tot_tok = int(kpis.get("window_tokens", 0))
    tot_cost = float(kpis.get("window_cost_usd", 0.0) or 0.0)
    cost_d = float(kpis.get("cost_per_day_usd", tot_cost / act_days) or 0.0)

    g_pct = sum(float(m.get("actual_pct", 0.0)) for m in models if is_google_pool_model(m))
    p_used = max(0.0, 100.0 - g_pct)
    p_rem = max(0.0, 100.0 - p_used)
    g_bar, p_bar = build_quota_bar_with_pin(g_pct, 90.0, 10), build_quota_bar_with_pin(p_used, 10.0, 10)
    g_pool = (quota.get("pools") or {}).get("google") or {}
    g_429, g_stat = int(g_pool.get("total_429_count", 0)), ("HEALTHY" if g_pool.get("status", "HEALTHY") == "HEALTHY" else "COOLDWN")
    wk_left = round(max(0.0, 100.0 - float((quota.get("partner_weekly_pacing") or {}).get("recommended_cumulative_ceiling_pct", 14.3))), 1)
    w_calls, w_avg, w_max = int(wire.get("total_recorded_calls", 0)), float(wire.get("avg_kb", 0.0)), float(wire.get("max_kb", 0.0))
    w_tok, w_pct = fmt_tok(int(wire.get("total_mcp_tokens", 0)), False), int(round(float(wire.get("budget_compliance_pct", 100.0))))
    by_prod = wire.get("by_product") or {}
    has_web = any("Web" in k or "Mobile" in k for k in by_prod)
    has_prx = any("Praxis" in k or "IDE" in k for k in by_prod)
    w_client = "Web+Praxis" if (has_web and has_prx) else ("Praxis IDE" if has_prx else "Gemini Web")

    code_health = bundle.get("code_health") or {}
    v_info, m_info, ast_info = code_health.get("version") or {}, code_health.get("modular_hygiene") or {}, code_health.get("ast_integrity") or {}
    rel_label = v_info.get("status_label", f"v{__version__}")

    def _sr(l40: str, r31: str) -> str:
        return f"{l40[:40].ljust(40)}┆{r31[:31].ljust(31)}"

    lines = [
        "════════════════════════════════════════╤═══════════════════════════════",
        _sr(f"AGY-NEXUS v{__version__} // {cal_days}d ({e_dt} ◄── {s_dt})", f" {rel_label[:30]}"),
        "════════════════════════════════════════╪═══════════════════════════════",
        _sr(f"GOOGLE 20x : {g_pct:>5.1f}% [{g_bar}] {g_stat}", f" {g_429}x 429s | Ultra-20x (T:>=90%)"),
        _sr(f"PARTNER 1x : {p_rem:>5.1f}% [{p_bar}] ON PACE", f" {wk_left:>4.1f}% Wk Left | Lim <=14.3%/d"),
        _sr(f"STEPS/TOOLS: {tot_steps:,}s | {tot_tools:,}t | {tot_chats}c", f" {tot_steps // act_days:,} s/act-d | {tot_steps // cal_days:,} s/cal-d"),
        _sr(f"TOKEN BURN : {fmt_tok(tot_tok)} | ${tot_cost:,.2f}", f" {fmt_rate(tot_tok / act_days)}/d | ${cost_d:,.2f}/d ({tot_subs}r)"),
        _sr(f"MCP WIRE   : {w_pct}% <20KB (avg {w_avg:.1f}/{w_max:.1f}KB)", f" {w_calls} req ({w_tok} tok) | {w_client}"),
        _sr(
            f"CODE HEALTH: Poly {int((code_health.get('polyglot_health') or ast_info).get('total_symbols', 0))} syms | {m_info.get('compliant_500', m_info.get('compliant_300', 0))}/{m_info.get('total_modules', 0)} <=500L",
            f" {m_info.get('violations_over_650', 0)} >650L | Praxis+Serena",
        ),
        "────────────────────────────────────────┴───────────────────────────────",
    ]

    pk = kpis.get("peak_day") or {"date": "", "steps": 0}
    pk_dt, pk_st = str(pk.get("date") or "")[-5:].replace("-", "/") or "--/--", int(pk.get("steps") or 0)
    lines.append(f"DAILY HEATMAP (NOW: W01 ──► 22w AGO)   Peak: {pk_dt} ({pk_st:,}s) | Act: {act_days}d"[:72])
    weeks_22 = build_reversed_weeks(series, num_weeks=22)
    lines.append("Wk    " + " ".join(f"{i + 1:02d}" for i in range(22)))
    cmap = {0: "··", 1: "░░", 2: "▒▒", 3: "▓▓", 4: "██"}
    for wd_idx, d_name in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
        cells = [cmap.get(int((wk["days"].get(wd_idx) or {}).get("level", 0)), "··") for wk in weeks_22]
        lines.append(f"{d_name}   " + " ".join(cells))

    max_wk = max(max((w["steps"] for w in weeks_22), default=1), 1)
    sparks = ["──", "▁▁", "▂▂", "▃▃", "▄▄", "▅▅", "▆▆", "██"]
    vol = ["──" if w["steps"] <= 0 else sparks[min(7, max(1, int(round((w["steps"] / float(max_wk)) * 7))))] for w in weeks_22]
    lines.extend(["Vol   " + " ".join(vol), "────────────────────────────────────────────────────────────────────────"])

    c_rows, c_dates, pk_8h, avg_8h = build_reversed_8h_stack_canvas(bundle, width=65, height=4)
    old_lbl = fmt_short_date(c_dates[-1]).upper() if c_dates else "OLDER"
    lines.extend([
        f"8H SUB-DAILY PACE (NOW ──► {old_lbl})   [Avg: {fmt_k(avg_8h)}/8h | Peak: {fmt_k(pk_8h)} | ░▒▓█]"[:72],
        f"{fmt_k(pk_8h):>4} ╷{c_rows[0]}",
        f"{fmt_k(pk_8h * 0.52):>4} ┤{c_rows[1]}",
        f"{fmt_k(avg_8h):>4} ┼{c_rows[2]}",
        f"   0 ╵{c_rows[3]}",
        "     └─▲────────────▲────────────▲────────────▲────────────▲──────────▲─",
    ])
    tl = [fmt_short_date(c_dates[min(len(c_dates) - 1, idx)]) for idx in (0, 13, 26, 39, 52, 64)]
    lines.append(f"      {tl[0]:<12} {tl[1]:<12} {tl[2]:<12} {tl[3]:<12} {tl[4]:<10} {tl[5]:<6}"[:72])
    leg = [f"[{s}] {str(w.get('workspace', ''))[:13]} ({float(w.get('share_pct', 0.0)):.0f}%)" for s, w in zip(["█", "▓", "▒"], workspaces[:3])]
    if leg:
        lines.append(("      Stack: " + "  ".join(leg))[:72])
    lines.extend(_build_default_tables_72(models, billing, workspaces, subagents))
    return "\n".join(line[:72] for line in lines)


def render_ascii_quick(bundle: dict[str, Any]) -> str:
    """Render Quick 40-Column Mobile Stats (strictly <= 40 chars per line)."""
    kpis, period = bundle.get("kpis") or {}, bundle.get("period") or {}
    quota, models = bundle.get("quota_and_pools") or {}, bundle.get("model_usage_vs_target") or []
    workspaces = bundle.get("all_workspaces") or bundle.get("top_workspaces") or []
    subagents, series = bundle.get("subagent_list") or [], bundle.get("heatmap_series") or []
    _, s7 = get_model_short_labels()

    s_dt, e_dt = fmt_short_date(str(period.get("start_date") or "")), fmt_short_date(str(period.get("end_date") or ""))
    act_days, cal_days = max(1, int(kpis.get("active_days", period.get("active_days", 1)) or 1)), max(1, int(period.get("total_days", 90) or 90))
    tot_steps, tot_tools, tot_tok = int(kpis.get("window_steps", 0)), int(kpis.get("window_tool_calls", 0)), int(kpis.get("window_tokens", 0))
    tot_cost = float(kpis.get("window_cost_usd", 0.0) or 0.0)
    g_pct = sum(float(m.get("actual_pct", 0.0)) for m in models if is_google_pool_model(m))
    p_rem = max(0.0, 100.0 - max(0.0, 100.0 - g_pct))
    g_bar, p_bar = build_quota_bar_with_pin(g_pct, 90.0, 10), build_quota_bar_with_pin(100.0 - g_pct, 10.0, 10)
    g_429 = int(((quota.get("pools") or {}).get("google") or {}).get("total_429_count", 0))
    wk_left = int(round(max(0.0, 100.0 - float((quota.get("partner_weekly_pacing") or {}).get("recommended_cumulative_ceiling_pct", 14.3)))))
    code_health = bundle.get("code_health") or {}
    v_info, m_info = code_health.get("version") or {}, code_health.get("modular_hygiene") or {}
    poly_info = code_health.get("polyglot_health") or code_health.get("ast_integrity") or {}

    lines = [
        "════════════════════════════════════════",
        f"AGY-NEXUS v{__version__} // {cal_days}d ({e_dt} ◄── {s_dt})"[:40],
        "════════════════════════════════════════",
        f"G-20x:{g_pct:>4.0f}% [{g_bar}] OK | {g_429}x 429s"[:40],
        f"P-1x :{p_rem:>4.0f}% [{p_bar}] OK | {wk_left}% WkLft"[:40],
        f"Steps:{fmt_k(tot_steps):>6} | Tools:{fmt_k(tot_tools):>5} | Act:{act_days}d"[:40],
        f"Burn:{fmt_tok(tot_tok, False):>5} | {format_usd(tot_cost)} | {fmt_rate(tot_tok / act_days)}/d"[:40],
        f"Health: Poly {int(poly_info.get('total_symbols', 0))}s | {m_info.get('compliant_500', m_info.get('compliant_300', 0))}/{m_info.get('total_modules', 0)} <=500L | {v_info.get('status', 'OK')[:6]}"[:40],
        "────────────────────────────────────────",
        "HEATMAP (NOW ──► 13w Ago)  │ PEAK & VOL",
    ]
    weeks_13, cmap1 = build_reversed_weeks(series, num_weeks=13), {0: "·", 1: "░", 2: "▒", 3: "▓", 4: "█"}
    pk = kpis.get("peak_day") or {"date": "", "steps": 0}
    callouts = [
        f"Pk: {str(pk.get('date') or '')[-5:].replace('-', '/')}",
        f"{int(pk.get('steps') or 0):,} stp",
        f"Avg:{tot_steps // act_days:,}/d",
        f"Cost: {format_usd(tot_cost)}",
        f"Subs : {int(kpis.get('total_subagents_spawned', 0))}r",
        f"Tok/d:{fmt_rate(tot_tok / act_days)}",
        f"Tok/w:{fmt_rate(tot_tok / max(1.0, act_days / 7.0))}",
    ]
    for wd_idx, d_lbl in enumerate(["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]):
        cells_13 = "".join(cmap1.get(int((w["days"].get(wd_idx) or {}).get("level", 0)), "·") for w in weeks_13)
        lines.append(f"{d_lbl} {cells_13}           │ {callouts[wd_idx]}"[:40])

    c_rows, _, pk_8h, avg_8h = build_reversed_8h_stack_canvas(bundle, width=32, height=4)
    lines.extend([
        "────────────────────────────────────────",
        f"8H PACE & STACK (NOW──►OLD) Pk:{fmt_k(pk_8h)}"[:40],
        f"{fmt_k(pk_8h):>4}╷{c_rows[0]}"[:40],
        f"{fmt_k(pk_8h * 0.5):>4}┤{c_rows[1]}"[:40],
        f"{fmt_k(avg_8h):>4}┼{c_rows[2]}"[:40],
        f"   0╵{c_rows[3]}"[:40],
        "────────────────────────────────────────",
        "MODEL   [PIN]    PCT   TOK  EST.$   DLT",
    ])
    for m in models:
        mk = str(m.get("model_key", ""))
        b8 = build_quota_bar_with_pin(float(m.get("actual_pct", 0.0)), float(m.get("target_pct", 0.0)), 8)
        tk_q = fmt_tok(m.get("est_tokens", 0), False)
        usd_q = format_usd(float(m.get("est_cost_usd", 0.0) or 0.0))
        lines.append(f"{s7.get(mk, mk[:7]):<7} [{b8}]{float(m.get('actual_pct', 0.0)):>3.0f}% {tk_q:>5} {usd_q:>6} {float(m.get('delta_pct', 0.0)):>+3.0f}"[:40])

    lines.extend(["────────────────────────────────────────", "WORKSPACES & SUBS  TOK   EST.$  TOK/WK"])
    for w in workspaces[:6]:
        usd_w = format_usd(float(w.get("est_cost_usd", 0.0) or 0.0))
        lines.append(f"{str(w.get('workspace', 'root'))[:15]:<15} {fmt_tok(w.get('tokens', 0), False):>5} {usd_w:>7} {fmt_rate(w.get('tok_per_week', 0)):>7}"[:40])
    for sa in subagents[:3]:
        usd_s = format_usd(float(sa.get("est_cost_usd", 0.0) or 0.0))
        lines.append(f"{('*' + str(sa.get('role', 'sub')))[:15]:<15} {fmt_tok(sa.get('tokens', 0), False):>5} {usd_s:>7} {fmt_rate(sa.get('tok_per_week', 0)):>7}"[:40])
    lines.append("════════════════════════════════════════")
    return "\n".join(line[:40] for line in lines)
