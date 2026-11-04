#!/usr/bin/env python3
"""
agy-nexus-mcp — Rich (76-Col) Box-Drawn Monospace TUI Telemetry Renderer
"""

from __future__ import annotations

from typing import Any

from agy_nexus.ascii_default import (
    build_quota_bar_with_pin,
    build_reversed_8h_stack_canvas,
    build_reversed_weeks,
    fmt_k,
    fmt_rate,
    fmt_short_date,
    fmt_tok,
)

def _share_gauge(pct: float, width: int = 6) -> str:
    val = max(0.0, min(100.0, float(pct or 0.0)))
    exact = (val / 100.0) * width
    full = int(exact)
    rem = exact - full
    cells = ["█" if i < full else "░" for i in range(width)]
    if full < width and rem >= 0.25:
        cells[full] = "▍"
    return f"{''.join(cells)} {val:>4.1f}%"

def _box_split(left_36: str, right_37: str) -> str:
    return f"║ {left_36[:35].ljust(35)}│ {right_37[:35].ljust(35)} ║"

def _box_full(inner_72: str) -> str:
    return f"║ {inner_72[:72].ljust(72)} ║"

def _fmt_wk_3c(steps: int) -> str:
    if steps <= 0:
        return " · "
    if steps >= 950:
        return f"{int(round(steps / 1000.0)):>2}k"
    return f"{steps:>3}"

def render_ascii_rich(bundle: dict[str, Any]) -> str:
    """Render Rich 76-Column Box-Drawn TUI Telemetry Rig."""
    kpis, period = bundle.get("kpis") or {}, bundle.get("period") or {}
    quota, wire = bundle.get("quota_and_pools") or {}, bundle.get("wire_telemetry") or {}
    models = bundle.get("model_usage_vs_target") or []
    workspaces = bundle.get("all_workspaces") or bundle.get("top_workspaces") or []
    subagents = bundle.get("subagent_list") or []
    series = bundle.get("heatmap_series") or []

    s_dt, e_dt = fmt_short_date(str(period.get("start_date") or "")), fmt_short_date(str(period.get("end_date") or ""))
    act_days = max(1, int(kpis.get("active_days", period.get("active_days", 1)) or 1))
    cal_days = max(1, int(period.get("total_days", 90) or 90))
    tot_steps, tot_tools = int(kpis.get("window_steps", 0)), int(kpis.get("window_tool_calls", 0))
    tot_chats, tot_subs = int(kpis.get("total_conversations", 0)), int(kpis.get("total_subagents_spawned", 0))
    tot_tok = int(kpis.get("window_tokens", 0))

    g_pct = sum(float(m.get("actual_pct", 0.0)) for m in models if m.get("model_key") in ("argon_pro", "flash"))
    p_used = max(0.0, 100.0 - g_pct)
    p_rem = max(0.0, 100.0 - p_used)
    g_bar, p_bar = build_quota_bar_with_pin(g_pct, 90.0, 10), build_quota_bar_with_pin(p_used, 10.0, 10)
    g_429 = int(((quota.get("pools") or {}).get("google") or {}).get("total_429_count", 0))
    wk_left = round(max(0.0, 100.0 - float((quota.get("partner_weekly_pacing") or {}).get("recommended_cumulative_ceiling_pct", 14.3))), 1)
    w_calls, w_avg, w_max = int(wire.get("total_recorded_calls", 0)), float(wire.get("avg_kb", 0.0)), float(wire.get("max_kb", 0.0))
    w_tok, w_pct = fmt_tok(int(wire.get("total_mcp_tokens", 0)), False), int(round(float(wire.get("budget_compliance_pct", 100.0))))

    lines = [
        "╔══════════════════════════════════════════════════════════════════════════╗",
        _box_full("▄▀█ █▀▀ █▄█ ▄▄ █▄░█ █▀▀ ▀▄▀ █░█ █▀   v3.8 // RICH TELEMETRY RIG"),
        _box_full(f"█▀█ █▄█ ░█░ ░░ █░▀█ ██▄ █░█ █▄█ ▄█   WINDOW: 90d ({e_dt} ◄── {s_dt})"),
        "╠════════════════════════════════════╦═════════════════════════════════════╣",
        _box_split("QUOTA POOLS & 429 COOLDOWNS", "STEP & TOOL VELOCITY"),
        _box_split(f"G-20x: {g_pct:>5.1f}% [{g_bar}] OK", f"Total : {tot_steps:,} steps | {tot_tools:,} tools"),
        _box_split(f"P-1x : {p_rem:>5.1f}% [{p_bar}] OK", f"Active: {tot_steps // act_days:,} s/act-d ({act_days}d active)"),
        _box_split(f"429s : {g_429} events | {wk_left:.1f}% Wk Left", f"Calend: {tot_steps // cal_days:,} s/cal-d ({tot_chats}c, {tot_subs}r)"),
        "╠════════════════════════════════════╬═════════════════════════════════════╣",
        _box_split("TOKEN BURN & ROLLING AVERAGES", "MCP WIRE & CLIENT SURFACES"),
        _box_split(f"Total : {fmt_tok(tot_tok)} ({fmt_tok(tot_tok * 0.91)} direct)", f"Wire  : {w_pct}% <20KB (avg {w_avg:.1f}/{w_max:.1f}KB)"),
        _box_split(f"Daily : {fmt_rate(tot_tok / act_days)} tok/act-d", f"Calls : {w_calls} MCP reqs ({w_tok} tok)"),
        _box_split(f"Weekly: {fmt_rate(tot_tok / max(1.0, act_days / 7.0))} tok/wk", "Client: Gemini Web (100% / 0 Mob)"),
        "╠════════════════════════════════════╩═════════════════════════════════════╣",
        _box_full("DAILY ACTIVITY MATRIX (NOW: W01 ──► W13)     [·· 0  ░░ <1k  ▒▒ <4k  ██]"),
    ]

    weeks_13 = build_reversed_weeks(series, num_weeks=13)
    wk_hdr = "Wk   " + " ".join(f"W{i + 1:02d}" for i in range(13)) + "  ┌─ PEAK DAY ─┐"
    lines.append(_box_full(wk_hdr))
    pk = kpis.get("peak_day") or {"date": "", "steps": 0}
    pk_dt = fmt_short_date(str(pk.get("date") or ""))
    pk_st = int(pk.get("steps") or 0)
    box_side = [
        f"│ {pk_dt:<10} │",
        f"│ {pk_st:>6,} stp │",
        "├────────────┤",
        f"│ Act: {act_days:>2}d   │",
        f"│ Avg: {fmt_k(tot_steps / act_days):>5} │",
        f"│ Sub: {tot_subs:>3}r  │",
        "└────────────┘",
    ]
    cmap3 = {0: "···", 1: "░░░", 2: "▒▒▒", 3: "▓▓▓", 4: "███"}
    for wd_idx, d_name in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
        c3 = " ".join(cmap3.get(int((w["days"].get(wd_idx) or {}).get("level", 0)), "···") for w in weeks_13)
        lines.append(_box_full(f"{d_name}  {c3}  {box_side[wd_idx]}"))

    max_wk = max(max((w["steps"] for w in weeks_13), default=1), 1)
    sp3 = ["───", "▁▁▁", "▂▂▂", "▃▃▃", "▄▄▄", "▅▅▅", "▆▆▆", "███"]
    vol3 = " ".join("───" if w["steps"] <= 0 else sp3[min(7, max(1, int(round((w["steps"] / float(max_wk)) * 7))))] for w in weeks_13)
    stp3 = " ".join(_fmt_wk_3c(int(w["steps"])) for w in weeks_13)
    lines.extend([
        _box_full(f"Vol  {vol3}  PeakWk:{fmt_k(max_wk):>5}"),
        _box_full(f"Steps {stp3}"),
        "╠══════════════════════════════════════════════════════════════════════════╣",
    ])

    c_rows, c_dates, pk_8h, avg_8h = build_reversed_8h_stack_canvas(bundle, width=64, height=6)
    old_lbl = fmt_short_date(c_dates[-1]).upper() if c_dates else "OLDER"
    lines.extend([
        _box_full(f"8H SUB-DAILY HORIZON CURVE & PROJECT STACK (NOW ──► {old_lbl})"),
        _box_full(f"{fmt_k(pk_8h):>4} ╷{c_rows[0]}"),
        _box_full(f"{fmt_k(pk_8h * 0.78):>4} ┤{c_rows[1]}"),
        _box_full(f"{fmt_k(pk_8h * 0.55):>4} ┤{c_rows[2]}"),
        _box_full(f"{fmt_k(avg_8h):>4} ┼{c_rows[3]}"),
        _box_full(f"{fmt_k(pk_8h * 0.18):>4} ┤{c_rows[4]}"),
        _box_full(f"   0 ╵{c_rows[5]}"),
        _box_full("     └─▲───────────▲───────────▲───────────▲───────────▲───────────▲───"),
    ])
    tl = [fmt_short_date(c_dates[min(len(c_dates) - 1, idx)]) for idx in (0, 13, 26, 39, 52, 63)]
    lines.append(_box_full(f"      {tl[0]:<11} {tl[1]:<11} {tl[2]:<11} {tl[3]:<11} {tl[4]:<11} {tl[5]:<6}"))
    leg = [f"[{s}]{str(w.get('workspace', ''))[:12]}({float(w.get('share_pct', 0.0)):.0f}%)" for s, w in zip(["█", "▓", "▒"], workspaces[:3])]
    if leg:
        lines.append(_box_full("      Stack: " + "  ".join(leg)))

    lines.extend([
        "╠══════════════════════════════════════════════════════════════════════════╣",
        _box_full("MODEL QUOTA vs TARGET (┼ = Target Pin)       CALLS   EST TOK  DELTA STAT"),
    ])
    sm = {"argon_pro": "Argon 4 Pro", "flash": "Flash 3.8  ", "claude_partner": "Claude 5.5 ", "gpt_oss": "GPT-OSS 120"}
    for m in models:
        mk = str(m.get("model_key", ""))
        ml = sm.get(mk, str(m.get("label", ""))[:11]).ljust(11)
        ap, tp, dp = float(m.get("actual_pct", 0.0)), float(m.get("target_pct", 0.0)), float(m.get("delta_pct", 0.0))
        b21 = build_quota_bar_with_pin(ap, tp, width=21)
        tks = "FastTier" if mk == "flash" and int(m.get("est_tokens", 0)) == 0 else fmt_tok(int(m.get("est_tokens", 0)))
        lines.append(_box_full(f"{ml} [{b21}] {ap:>5.1f}%  {int(m.get('actual_calls', 0)):>6,}  {tks:>8} {dp:>+5.1f}%  {'OK' if abs(dp) <= 12.0 else 'WRN'}"))

    lines.extend([
        "╠══════════════════════════════════════════════════════════════════════════╣",
        _box_full(f"{f'WORKSPACES ({len(workspaces)})':<18} CHATS   STEPS  TOTAL TOK  TOK/DAY  TOK/WK SHARE GAUGE"),
    ])
    for idx, w in enumerate(workspaces, start=1):
        wn = f"{idx}. {str(w.get('workspace', 'root'))}"[:17].ljust(17)
        gg = _share_gauge(float(w.get("share_pct", 0.0)), width=6)
        lines.append(_box_full(f"{wn} {int(w.get('sessions', 0)):>3}c {int(w.get('steps', 0)):>7,}  {fmt_tok(w.get('tokens', 0)):>9}  {fmt_rate(w.get('tok_per_day', 0)):>7}  {fmt_rate(w.get('tok_per_week', 0)):>6} {gg}"))

    if subagents:
        lines.extend([
            "╟──────────────────────────────────────────────────────────────────────────╢",
            _box_full(f"{f'SUBAGENTS ({len(subagents)})':<18}  RUNS   STEPS  TOTAL TOK  TOK/DAY  TOK/WK SHARE GAUGE"),
        ])
        for idx, sa in enumerate(subagents, start=1):
            sn = f"{idx}. {str(sa.get('role', 'subagent'))}"[:17].ljust(17)
            gg = _share_gauge(float(sa.get("share_pct", 0.0)), width=6)
            lines.append(_box_full(f"{sn} {int(sa.get('runs', 0)):>3}r {int(sa.get('steps', 0)):>7,}  {fmt_tok(sa.get('tokens', 0)):>9}  {fmt_rate(sa.get('tok_per_day', 0)):>7}  {fmt_rate(sa.get('tok_per_week', 0)):>6} {gg}"))

    lines.append("╚══════════════════════════════════════════════════════════════════════════╝")
    return "\n".join(lines)
