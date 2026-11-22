#!/usr/bin/env python3
"""
agy-nexus-mcp — Rich (76-Col) Box-Drawn Monospace TUI Telemetry Renderer
"""

from __future__ import annotations

from typing import Any

from . import __version__

from agy_nexus.ascii_default import (
    build_quota_bar_with_pin,
    build_reversed_8h_stack_canvas,
    build_reversed_weeks,
    fmt_k,
    fmt_rate,
    fmt_short_date,
    fmt_tok,
    get_model_short_labels,
    is_google_pool_model,
)
from agy_nexus.model_pricing import format_usd


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


def _build_rich_model_and_tables(
    models: list[dict[str, Any]],
    billing: dict[str, Any],
    workspaces: list[dict[str, Any]],
    subagents: list[dict[str, Any]],
) -> list[str]:
    """Build 76-col boxed 8-model quota+cost rows, billing summary, workspaces, and subagents."""
    s11, _ = get_model_short_labels()
    lines = [
        "╠══════════════════════════════════════════════════════════════════════════╣",
        _box_full("MODEL       [QUOTA ┼ TARGET] SHARE    CALLS     TOK    EST.$  DLT  STAT"),
    ]
    for m in models:
        mk = str(m.get("model_key", ""))
        ml = s11.get(mk, str(m.get("short_label") or m.get("label") or mk)[:11].ljust(11))
        ap, tp, dp = float(m.get("actual_pct", 0.0)), float(m.get("target_pct", 0.0)), float(m.get("delta_pct", 0.0))
        b14 = build_quota_bar_with_pin(ap, tp, width=14)
        usd_s = format_usd(float(m.get("est_cost_usd", 0.0) or 0.0))
        tks = fmt_tok(int(m.get("est_tokens", 0)), False)
        stat = "OK  " if abs(dp) <= 12.0 else "WRN "
        lines.append(_box_full(f"{ml} [{b14}] {ap:>4.1f}% {int(m.get('actual_calls', 0)):>7,} {tks:>7} {usd_s:>7} {dp:>+4.0f}% {stat}"))

    if billing:
        h_u, f_u = float(billing.get("historical_usd", 0.0) or 0.0), float(billing.get("forecast_usd", 0.0) or 0.0)
        d_pct = float(billing.get("forecast_delta_pct", 0.0) or 0.0)
        tiers = billing.get("tiers") or []
        u20 = next((t for t in tiers if "20x" in str(t.get("id") or "")), tiers[-1] if tiers else {})
        mult = float(u20.get("value_multiplier", 0.0) or 0.0)
        lines.append(_box_full(
            f"BILLING CMP: Hist {format_usd(h_u)} | NextRate {format_usd(f_u)} ({d_pct:+.0f}%) | 20x {mult:.1f}x"
        ))

    lines.extend([
        "╠══════════════════════════════════════════════════════════════════════════╣",
        _box_full(f"{f'WORKSPACES ({len(workspaces)})':<16} CHATS   STEPS     TOK   TOK/D   EST.$ SHARE GAUGE"),
    ])
    for idx, w in enumerate(workspaces, start=1):
        wn = f"{idx}. {str(w.get('workspace', 'root'))}"[:16].ljust(16)
        gg = _share_gauge(float(w.get("share_pct", 0.0)), width=6)
        usd_w = format_usd(float(w.get("est_cost_usd", 0.0) or 0.0))
        lines.append(_box_full(f"{wn} {int(w.get('sessions', 0)):>3}c {int(w.get('steps', 0)):>7,} {fmt_tok(w.get('tokens', 0), False):>7} {fmt_rate(w.get('tok_per_day', 0)):>6} {usd_w:>7} {gg}"))

    if subagents:
        lines.extend([
            "╟──────────────────────────────────────────────────────────────────────────╢",
            _box_full(f"{f'SUBAGENTS ({len(subagents)})':<16}  RUNS   STEPS     TOK   TOK/D   EST.$ SHARE GAUGE"),
        ])
        for idx, sa in enumerate(subagents, start=1):
            sn = f"{idx}. {str(sa.get('role', 'subagent'))}"[:16].ljust(16)
            gg = _share_gauge(float(sa.get("share_pct", 0.0)), width=6)
            usd_s = format_usd(float(sa.get("est_cost_usd", 0.0) or 0.0))
            lines.append(_box_full(f"{sn} {int(sa.get('runs', 0)):>3}r {int(sa.get('steps', 0)):>7,} {fmt_tok(sa.get('tokens', 0), False):>7} {fmt_rate(sa.get('tok_per_day', 0)):>6} {usd_s:>7} {gg}"))
    lines.append("╚══════════════════════════════════════════════════════════════════════════╝")
    return lines


def render_ascii_rich(bundle: dict[str, Any]) -> str:
    """Render Rich 76-Column Box-Drawn TUI Telemetry Rig."""
    kpis, period = bundle.get("kpis") or {}, bundle.get("period") or {}
    quota, wire = bundle.get("quota_and_pools") or {}, bundle.get("wire_telemetry") or {}
    models = bundle.get("model_usage_vs_target") or []
    workspaces = bundle.get("all_workspaces") or bundle.get("top_workspaces") or []
    subagents, series = bundle.get("subagent_list") or [], bundle.get("heatmap_series") or []
    billing = bundle.get("billing_comparison") or {}

    s_dt, e_dt = fmt_short_date(str(period.get("start_date") or "")), fmt_short_date(str(period.get("end_date") or ""))
    act_days = max(1, int(kpis.get("active_days", period.get("active_days", 1)) or 1))
    cal_days = max(1, int(period.get("total_days", 90) or 90))
    tot_steps, tot_tools = int(kpis.get("window_steps", 0)), int(kpis.get("window_tool_calls", 0))
    tot_chats, tot_subs = int(kpis.get("total_conversations", 0)), int(kpis.get("total_subagents_spawned", 0))
    tot_tok = int(kpis.get("window_tokens", 0))
    tot_cost = float(kpis.get("window_cost_usd", 0.0) or 0.0)
    fore_cost = float(kpis.get("forecast_cost_usd", tot_cost) or tot_cost)
    cost_d = float(kpis.get("cost_per_day_usd", tot_cost / act_days) or 0.0)

    g_pct = sum(float(m.get("actual_pct", 0.0)) for m in models if is_google_pool_model(m))
    p_used = max(0.0, 100.0 - g_pct)
    p_rem = max(0.0, 100.0 - p_used)
    g_bar, p_bar = build_quota_bar_with_pin(g_pct, 90.0, 10), build_quota_bar_with_pin(p_used, 10.0, 10)
    g_429 = int(((quota.get("pools") or {}).get("google") or {}).get("total_429_count", 0))
    wk_left = round(max(0.0, 100.0 - float((quota.get("partner_weekly_pacing") or {}).get("recommended_cumulative_ceiling_pct", 14.3))), 1)
    w_calls, w_avg, w_max = int(wire.get("total_recorded_calls", 0)), float(wire.get("avg_kb", 0.0)), float(wire.get("max_kb", 0.0))
    w_tok, w_pct = fmt_tok(int(wire.get("total_mcp_tokens", 0)), False), int(round(float(wire.get("budget_compliance_pct", 100.0))))
    by_prod = wire.get("by_product") or {}
    p_tot = max(1, sum(int((v or {}).get("calls", 0)) for v in by_prod.values()))
    web_c = sum(int((v or {}).get("calls", 0)) for k, v in by_prod.items() if "Web" in k or "Client" in k)
    prx_c = sum(int((v or {}).get("calls", 0)) for k, v in by_prod.items() if "Praxis" in k or "IDE" in k)
    mob_c = sum(int((v or {}).get("calls", 0)) for k, v in by_prod.items() if "Mobile" in k)
    client_line = f"Client: Web {round(web_c * 100 / p_tot)}% · Prx {round(prx_c * 100 / p_tot)}% · Mob {round(mob_c * 100 / p_tot)}%" if by_prod else "Client: Gemini Web (100% / 0 Mob)"

    code_health = bundle.get("code_health") or {}
    v_info, m_info = code_health.get("version") or {}, code_health.get("modular_hygiene") or {}
    poly_info = code_health.get("polyglot_health") or code_health.get("ast_integrity") or {}

    lines = [
        "╔══════════════════════════════════════════════════════════════════════════╗",
        _box_full(f"▄▀█ █▀▀ █▄█ ▄▄ █▄░█ █▀▀ ▀▄▀ █░█ █▀   v{__version__} // RICH TELEMETRY RIG"),
        _box_full(f"█▀█ █▄█ ░█░ ░░ █░▀█ ██▄ █░█ █▄█ ▄█   WINDOW: {cal_days}d ({e_dt} ◄── {s_dt})"),
        "╠════════════════════════════════════╦═════════════════════════════════════╣",
        _box_split("QUOTA POOLS & 429 COOLDOWNS", "STEP & TOOL VELOCITY"),
        _box_split(f"G-20x: {g_pct:>5.1f}% [{g_bar}] OK", f"Total : {tot_steps:,} steps | {tot_tools:,} tools"),
        _box_split(f"P-1x : {p_rem:>5.1f}% [{p_bar}] OK", f"Active: {tot_steps // act_days:,} s/act-d ({act_days}d active)"),
        _box_split(f"429s : {g_429} events | {wk_left:.1f}% Wk Left", f"Calend: {tot_steps // cal_days:,} s/cal-d ({tot_chats}c, {tot_subs}r)"),
        "╠════════════════════════════════════╬═════════════════════════════════════╣",
        _box_split("TOKEN BURN & API COST LEDGER", "MCP WIRE & CLIENT SURFACES"),
        _box_split(f"Total : {fmt_tok(tot_tok)} | ${tot_cost:,.2f}", f"Wire  : {w_pct}% <20KB (avg {w_avg:.1f}/{w_max:.1f}KB)"),
        _box_split(f"Daily : {fmt_rate(tot_tok / act_days)}/d (${cost_d:,.2f}/d)", f"Calls : {w_calls} MCP reqs ({w_tok} tok)"),
        _box_split(f"NextRt: ${fore_cost:,.2f} API Forecast", client_line),
        "╠════════════════════════════════════╦═════════════════════════════════════╣",
        _box_split("VERSION & RELEASE STATUS", "POLYGLOT & MODULAR CODE HEALTH"),
        _box_split(
            f"Installed: v{__version__} ({v_info.get('status', 'OK')})",
            f"Poly: {int(poly_info.get('total_symbols', 0))}s | {m_info.get('compliant_500', m_info.get('compliant_300', 0))}/{m_info.get('total_modules', 0)} <=500L {m_info.get('violations_over_650', 0)}>650L",
        ),
        _box_split(f"Remote   : {v_info.get('remote', 'unknown')}", "IDE MCP  : agy-praxis-mcp + Serena"),
        "╠════════════════════════════════════╩═════════════════════════════════════╣",
        _box_full("DAILY ACTIVITY MATRIX (NOW: W01 ──► W13)     [·· 0  ░░ <1k  ▒▒ <4k  ██]"),
    ]

    weeks_13 = build_reversed_weeks(series, num_weeks=13)
    lines.append(_box_full("Wk   " + " ".join(f"W{i + 1:02d}" for i in range(13)) + "  ┌─ PEAK DAY ─┐"))
    pk = kpis.get("peak_day") or {"date": "", "steps": 0}
    box_side = [
        f"│ {fmt_short_date(str(pk.get('date') or '')):<10} │",
        f"│ {int(pk.get('steps') or 0):>6,} stp │",
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
        _box_full(f"{fmt_k(pk_8h):>4} ╷{c_rows[0]}"), _box_full(f"{fmt_k(pk_8h * 0.78):>4} ┤{c_rows[1]}"),
        _box_full(f"{fmt_k(pk_8h * 0.55):>4} ┤{c_rows[2]}"), _box_full(f"{fmt_k(avg_8h):>4} ┼{c_rows[3]}"),
        _box_full(f"{fmt_k(pk_8h * 0.18):>4} ┤{c_rows[4]}"), _box_full(f"   0 ╵{c_rows[5]}"),
        _box_full("     └─▲───────────▲───────────▲───────────▲───────────▲───────────▲───"),
    ])
    tl = [fmt_short_date(c_dates[min(len(c_dates) - 1, idx)]) for idx in (0, 13, 26, 39, 52, 63)]
    lines.append(_box_full(f"      {tl[0]:<11} {tl[1]:<11} {tl[2]:<11} {tl[3]:<11} {tl[4]:<11} {tl[5]:<6}"))
    leg = [f"[{s}]{str(w.get('workspace', ''))[:12]}({float(w.get('share_pct', 0.0)):.0f}%)" for s, w in zip(["█", "▓", "▒"], workspaces[:3])]
    if leg:
        lines.append(_box_full("      Stack: " + "  ".join(leg)))

    lines.extend(_build_rich_model_and_tables(models, billing, workspaces, subagents))
    return "\n".join(lines)
