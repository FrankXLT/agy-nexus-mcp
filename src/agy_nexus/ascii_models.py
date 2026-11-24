#!/usr/bin/env python3
"""
agy_nexus.ascii_models — Deadbolt-Safe 76-Col Live Model, Subagent, Subscription & Drift Matrix.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Any
import urllib.request

from agy_nexus.config import AGY_BG_DIR, AGY_CONFIG_DIR, AGY_DATA_DIR
from agy_nexus.cost_ledger import read_model_drift_status
from agy_nexus.inventory import parse_markdown_frontmatter
from agy_nexus.model_pricing import (
    classify_model_key,
    get_model_specs_map,
    load_model_catalog,
    resolve_rate_epoch,
)
from agy_nexus.telemetry_scanner import get_live_quota_and_pool_status


def _box_full(inner_72: str) -> str:
    return f"║ {inner_72[:72].ljust(72)} ║"


def _box_split(left_35: str, right_35: str) -> str:
    return f"║ {left_35[:35].ljust(35)}│ {right_35[:35].ljust(35)} ║"


def _fmt_ctx(tokens: int) -> str:
    if tokens >= 1_000_000:
        return f"{tokens / 1_000_000:.0f}M" if tokens % 1_000_000 < 100_000 else f"{tokens / 1_000_000:.1f}M"
    if tokens >= 1_000:
        return f"{tokens // 1_000}k"
    return str(tokens)


def _fetch_ls_live_configs() -> list[dict[str, Any]]:
    """Best-effort loopback query to local Language Server GetUserStatus without blocking (> 1.5s)."""
    try:
        import re
        import subprocess
        out = subprocess.run(
            ["ps", "-u", str(os.getuid()), "-o", "args"], capture_output=True, text=True, timeout=1.5, check=False
        ).stdout
        csrf = ""
        for line in out.splitlines():
            if "language_server" in line and "--csrf_token" in line:
                m = re.search(r"--csrf_token[=\s]+([^\s]+)", line)
                if m:
                    csrf = m.group(1).strip()
                    break
        if not csrf:
            return []
        ss_out = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True, timeout=1.5, check=False).stdout
        ports: list[int] = []
        for ln in ss_out.splitlines():
            if "language_server" in ln:
                pm = re.search(r"127\.0\.0\.1:(\d+)", ln)
                if pm:
                    ports.append(int(pm.group(1)))
        no_proxy_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for port in ports[:4]:
            try:
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/exa.language_server_pb.LanguageServerService/GetUserStatus",
                    data=b"{}",
                    headers={"Content-Type": "application/json", "Connect-Protocol-Version": "1", "X-Codeium-Csrf-Token": csrf},
                    method="POST",
                )
                with no_proxy_opener.open(req, timeout=1.5) as resp:
                    payload = json.loads(resp.read().decode("utf-8", errors="replace"))
                    cfgs = ((payload.get("userStatus") or {}).get("cascadeModelConfigData") or {}).get("clientModelConfigs") or []
                    if cfgs:
                        return list(cfgs)
            except Exception:
                continue
    except Exception:
        pass
    return []


def _ls_remaining_by_model_key(ls_configs: list[dict[str, Any]]) -> dict[str, int]:
    rem_map: dict[str, int] = {}
    for cfg in ls_configs:
        if not isinstance(cfg, dict):
            continue
        raw_id = str((cfg.get("modelOrAlias") or {}).get("model") or cfg.get("label") or "")
        mk = classify_model_key(raw_id, str(cfg.get("label") or ""))
        qinfo = cfg.get("quotaInfo") or {}
        if not isinstance(qinfo, dict):
            continue
        rf = qinfo.get("remainingFraction")
        if rf is not None and not isinstance(rf, bool):
            try:
                pct = max(0, min(100, int(round(float(rf) * 100.0))))
                rem_map[mk] = min(rem_map[mk], pct) if mk in rem_map else pct
            except (TypeError, ValueError):
                pass
    return rem_map


from agy_nexus.hygiene import resolve_package_resource_dir


def _check_agent_roster_and_sync(agy_config_dir: Path) -> list[dict[str, str]]:
    """Build tracked subagent summary with zero filesystem path disclosure."""
    repo_agents = resolve_package_resource_dir("agents", __file__)
    user_agents = agy_config_dir / "agents"
    rows: list[dict[str, str]] = []
    if not repo_agents.is_dir():
        return rows
    for src in sorted(repo_agents.glob("*.md")):
        if src.name.lower() == "readme.md":
            continue
        raw = src.read_text(encoding="utf-8", errors="replace")
        fm, _ = parse_markdown_frontmatter(raw)
        dst = user_agents / src.name
        if not dst.is_file():
            sync_state = "MISSING"
        else:
            sh1 = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            sh2 = hashlib.sha256(dst.read_bytes()).hexdigest()
            sync_state = "SYNCED" if sh1 == sh2 else "PENDING"
        tools = fm.get("tools") or []
        if isinstance(tools, str):
            tools = [t.strip() for t in tools.split(",") if t.strip()]
        t_set = {str(t).strip() for t in tools}
        has_w = bool(t_set & {"replace_file_content", "write_to_file", "multi_replace_file_content"})
        has_ex = "run_command" in t_set
        perms = ("RW+Ex" if (has_w and has_ex) else ("RW" if has_w else ("RO+Ex" if has_ex else "RO")))
        rows.append({
            "role": str(fm.get("name") or src.stem),
            "model": str(fm.get("model") or "inherit"),
            "target": str(fm.get("targetModel") or "-"),
            "effort": str(fm.get("difficultyLevel") or "Medium"),
            "perms": perms,
            "cap": "<=120",
            "sync": sync_state,
        })
    return rows


def render_ascii_models_status(
    *,
    data_dir: Path | None = None,
    agy_config_dir: Path | None = None,
    bg_dir: Path | None = None,
    ls_configs: list[dict[str, Any]] | None = None,
) -> str:
    """Render deadbolt-safe <=76-col monospace 8-model, subagent, pricing, subscription & drift status."""
    d_dir = data_dir or AGY_DATA_DIR
    c_dir = agy_config_dir or AGY_CONFIG_DIR
    b_dir = bg_dir or AGY_BG_DIR
    cat = load_model_catalog()
    specs = get_model_specs_map()
    quota = get_live_quota_and_pool_status(d_dir, c_dir)
    main_info = quota.get("active_mainchat_model") or {}
    main_mk = str(main_info.get("model_key") or "carbon")
    main_lbl = str((specs.get(main_mk) or {}).get("short_label") or main_mk)
    prof = str(quota.get("active_tier_profile") or "ultra-20x")
    pools = quota.get("pools") or {}
    g_p, c_p = pools.get("google") or {}, pools.get("claude") or {}

    live_cfgs = ls_configs if ls_configs is not None else _fetch_ls_live_configs()
    ls_rem = _ls_remaining_by_model_key(live_cfgs)
    drift = read_model_drift_status(b_dir)
    roster = _check_agent_roster_and_sync(c_dir)

    lines = [
        "╔══════════════════════════════════════════════════════════════════════════╗",
        _box_full("AGY-NEXUS LIVE MODELS, SUBAGENTS & PRICING MATRIX  (76-COL SAFE REPORT)"),
        "╠════════════════════════════════════╦═════════════════════════════════════╣",
        _box_split(f"Profile: {prof} | Main: {main_lbl}", f"Pools: G {g_p.get('status', 'OK')[:7]} | C {c_p.get('status', 'OK')[:7]}"),
        _box_split(f"Google 429s: {int(g_p.get('total_429_count', 0))} | LS Live: {'YES' if ls_rem else 'NO'}", f"Drift Cron: {str(drift.get('status') or 'NOT_RUN')[:14]}"),
        "╠════════════════════════════════════╩═════════════════════════════════════╣",
        _box_full("MODEL       TIER / IDS     CTX/OUT  CUR $/1M     NEXT $/1M    POOL LS%"),
    ]
    today_iso = datetime.now().strftime("%Y-%m-%d")
    for m in cat.get("models") or []:
        mk = str(m.get("key") or "")
        ml = str(m.get("short_11") or mk)[:11].ljust(11)
        ph_list = [str(p).replace("MODEL_PLACEHOLDER_", "").replace("MODEL_OPENAI_", "") for p in (m.get("placeholders") or [])]
        ids_col = "/".join(ph_list[:3])[:14].ljust(14)
        ctx_out = f"{_fmt_ctx(int(m.get('context_window', 0)))}/{_fmt_ctx(int(m.get('max_output_tokens', 0)))}".ljust(8)
        cur_ep = resolve_rate_epoch(mk, today_iso, bg_dir=b_dir)
        nxt_ep = resolve_rate_epoch(mk, today_iso, forecast=True, bg_dir=b_dir)
        cur_s = f"${cur_ep.get('input_micros', 0) / 1_000_000:.2f}/${cur_ep.get('output_micros', 0) / 1_000_000:.2f}"
        if (
            int(nxt_ep.get("input_micros") or 0) != int(cur_ep.get("input_micros") or 0)
            or int(nxt_ep.get("output_micros") or 0) != int(cur_ep.get("output_micros") or 0)
        ) and nxt_ep.get("effective_from"):
            ef = str(nxt_ep.get("effective_from") or "")[2:7]
            nxt_s = f"{ef}:${nxt_ep.get('input_micros', 0) / 1_000_000:.0f}/${nxt_ep.get('output_micros', 0) / 1_000_000:.0f}"
        else:
            nxt_s = "Stable"
        p_tag = "G20x" if str(m.get("pool_key") or "") == "google" else ("GPT0" if "gpt" in mk else "Prtn")
        rem_s = f"{ls_rem[mk]:>3}%" if mk in ls_rem else " -- "
        lines.append(_box_full(f"{ml} {ids_col} {ctx_out} {cur_s:<12} {nxt_s:<12} {p_tag:<4}{rem_s}"))

    lines.extend([
        _box_full("Tiers: Low/Med/High (Gemini+Claude) | Cache Read: $0.075-$0.20 / 1M tok"),
        "╠══════════════════════════════════════════════════════════════════════════╣",
        _box_full(f"SUBAGENT ROSTER ({len(roster)})   MODEL   TARGET MODEL      EFFORT PERMS CAP   SYNC"),
    ])
    for r in roster:
        lines.append(_box_full(
            f"{r['role'][:19]:<19} {r['model'][:7]:<7} {r['target'][:17]:<17} {r['effort'][:6]:<6} {r['perms'][:5]:<5} {r['cap'][:5]:<5} {r['sync'][:4]:<4}"
        ))

    synced_cnt = sum(1 for r in roster if r["sync"] == "SYNCED")
    lines.extend([
        _box_full(f"Agent Parity: {synced_cnt}/{len(roster)} SYNCED (run sync_agents.py for host update)"),
        "╠══════════════════════════════════════════════════════════════════════════╣",
        _box_full(_format_subscription_tiers_line(cat.get("subscription_tiers") or [])),
        _box_full(
            f"DRIFT 01:45: {str(drift.get('status') or 'NOT_RUN'):<12} Checked: {str(drift.get('checked_at') or 'never')[:16]:<16} Findings: {int(drift.get('drift_count') or 0)}"
        ),
        _box_full(f"Drift Note : {str(drift.get('summary') or 'Drift check not yet run')[:59]}"),
        "╚══════════════════════════════════════════════════════════════════════════╝",
    ])
    return "\n".join(line[:76] for line in lines)


def _short_tier_label(tier: dict[str, Any]) -> str:
    tid = str(tier.get("id") or "").lower()
    lbl = str(tier.get("label") or tid)
    if "20x" in tid or "20x" in lbl.lower():
        return "20x"
    if "5x" in tid or "5x" in lbl.lower():
        return "5x"
    if lbl.lower().startswith("google ai "):
        return lbl[10:].strip()
    return lbl.split()[-1] if lbl else tid


def _format_subscription_tiers_line(tiers: list[dict[str, Any]]) -> str:
    """Format subscription tiers dynamically within the 72-char inner box limit."""
    parts = [f"{_short_tier_label(t)} ${int(t.get('monthly_usd_micros') or 0) / 1_000_000.0:.2f}" for t in tiers]
    joined = " | ".join(parts)
    full = f"SUBSCRIPTION TIERS: {joined}"
    if len(full) <= 72:
        return full
    compact = f"TIERS: {joined}"
    return compact[:72]
