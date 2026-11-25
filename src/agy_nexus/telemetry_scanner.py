#!/usr/bin/env python3
"""
agy-nexus-mcp — Wire Telemetry Ledger, Quota & Resets & Transcript Mtime Scanner
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from agy_nexus.catalog_report import record_unmapped_model_hit
from agy_nexus.model_pricing import (
    classify_model_key, classify_model_key_status, compute_step_cost_micros, get_canonical_model_keys,
    get_placeholder_map, get_pool_target_split, get_target_allocation_map, split_estimated_tokens,
)

CACHE_VERSION = 9
_WIRE_RING_LOCK = threading.Lock()
_CACHE_LOCK = threading.Lock()
WIRE_TELEMETRY_RING: list[dict[str, Any]] = []
MAX_WIRE_RING = 200
MODEL_CHANGE_RE = re.compile(
    r"changed setting `?Model Selection`? from .+? to `?([^\n`]+?)`?\.(?:\s+No need|\s*</USER_SETTINGS_CHANGE>|\s*$)",
    re.MULTILINE,
)

ANTIGRAVITY_MODEL_PLACEHOLDERS: dict[str, dict[str, str]] = get_placeholder_map()


def get_active_mainchat_model(data_dir: Path | None = None) -> dict[str, Any]:
    """Read last_selected_agent_model from antigravity_state.pbtxt and resolve physical model metadata."""
    base = data_dir or Path(os.getenv("AGY_DATA_DIR", str(Path.home() / ".gemini/antigravity"))).expanduser()
    pb_file = base / "antigravity_state.pbtxt"
    raw_ph, switched_iso = "MODEL_PLACEHOLDER_M427", ""
    if pb_file.is_file():
        try:
            txt = pb_file.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"last_selected_agent_model:\s*([A-Za-z0-9_.-]+)", txt)
            if m:
                raw_ph = m.group(1).strip()
            switched_iso = datetime.fromtimestamp(pb_file.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            pass
    ph_map = get_placeholder_map()
    if raw_ph in ph_map:
        info = dict(ph_map[raw_ph])
    else:
        mk = classify_model_key(raw_ph, "")
        tmap = get_target_allocation_map("ultra-20x").get(mk) or {"label": "Gemini 4 Argon", "pool": "Google 20x"}
        info = {"id": raw_ph, "model_key": mk, "label": str(tmap["label"]), "pool": str(tmap["pool"]), "subagent_inherit": str(tmap["label"])}
    info["state_updated_date"] = switched_iso
    return info


def get_display_tz() -> Any:
    tz_env = (os.getenv("AGY_TIMEZONE") or os.getenv("TZ") or "").strip()
    if tz_env:
        try:
            return ZoneInfo(tz_env)
        except Exception:
            pass
    local_tz = datetime.now().astimezone().tzinfo
    if local_tz and str(local_tz) not in ("UTC", "Etc/UTC"):
        return local_tz
    try:
        return ZoneInfo("America/New_York")
    except Exception:
        return timezone.utc


DISPLAY_TZ = get_display_tz()
MODEL_TARGET_ALLOCATION = {
    "ultra-20x": get_target_allocation_map("ultra-20x"),
    "ultra-5x": get_target_allocation_map("ultra-5x"),
}


def detect_product_name(raw_product: str = "", user_agent: str = "", tool_name: str = "", doorway: str = "") -> str:
    raw_low, tool_low, door_low = (raw_product or "").lower(), (tool_name or "").lower(), (doorway or "").lower()
    if door_low == "praxis" or "praxis" in raw_low or "polyglot" in raw_low or tool_low.startswith(("polyglot_", "praxis_")):
        return "Antigravity IDE (Praxis MCP)"
    if "antigravity" in raw_low:
        return "Antigravity IDE"
    s = f"{raw_product or ''} {user_agent or ''}".lower()
    if any(k in s for k in ("mobile", "android", "iphone", "gsa/")):
        return "Gemini Mobile"
    if "web_ui" in tool_low or "web_stats" in tool_low or "mozilla" in s:
        return "Web Dashboard"
    if "antigravity" in s or "agy" in s:
        return "Antigravity IDE"
    if any(k in s for k in ("gemini", "google", "vertex", "http-client")):
        return "Gemini Web / Cloud MCP"
    return raw_product.strip() or "Gemini MCP Client"


def _is_handshake_record(rec: dict[str, Any]) -> bool:
    rpc_val = str(rec.get("rpc") or "").strip().lower()
    tool_val = str(rec.get("tool") or "").strip()
    if rpc_val and rpc_val not in ("tools/call", "-"):
        return True
    return tool_val == "-" or tool_val.startswith("[rpc:")


def _effective_record_product(rec: dict[str, Any]) -> str:
    tool_val = str(rec.get("tool") or "").strip().lower()
    if tool_val.startswith(("polyglot_", "praxis_")) or str(rec.get("doorway") or "").lower() == "praxis":
        return "Antigravity IDE (Praxis MCP)"
    return str(rec.get("product") or "Gemini MCP Client")


def record_wire_telemetry(
    tool_or_event: str | dict[str, Any],
    payload_or_bg_dir: Any = "",
    duration_ms: float = 0.0,
    *,
    bg_dir: Path | None = None,
    product: str = "",
    reported_tokens: int = 0,
) -> dict[str, Any]:
    """Record wire payload size, estimated context tokens, product source, and latency for MCP calls."""
    req_bytes, user_agent, rpc_kind, doorway = 0, "", "", ""
    if isinstance(tool_or_event, dict):
        byte_len, req_bytes = int(tool_or_event.get("bytes", 0) or 0), int(tool_or_event.get("req_bytes", 0) or 0)
        rpc_kind, doorway = str(tool_or_event.get("rpc") or "").strip(), str(tool_or_event.get("doorway") or "").strip()
        raw_t = str(tool_or_event.get("tool") or "").strip()
        tool_name = raw_t if (raw_t and raw_t != "-") else (f"[rpc:{rpc_kind}]" if rpc_kind and rpc_kind not in ("-", "tools/call") else (raw_t or rpc_kind or "mcp"))
        dur, product, user_agent = float(tool_or_event.get("ms", duration_ms) or 0.0), str(tool_or_event.get("product") or product or ""), str(tool_or_event.get("user_agent") or "")
        reported_tokens = int(tool_or_event.get("reported_tokens", reported_tokens) or 0)
        if isinstance(payload_or_bg_dir, Path) and bg_dir is None:
            bg_dir = payload_or_bg_dir
    else:
        byte_len, tool_name, dur = len(str(payload_or_bg_dir or "").encode("utf-8")), str(tool_or_event or "mcp"), float(duration_ms or 0.0)
        rpc_kind = "tools/call" if tool_name not in ("-", "") and not tool_name.startswith("[rpc:") else ""
    est_tokens = reported_tokens if reported_tokens > 0 else max(1, round((byte_len + req_bytes) / 4.0))
    eff_rpc = rpc_kind or ("tools/call" if tool_name != "-" and not tool_name.startswith("[rpc:") else "")
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(), "rpc": eff_rpc, "tool": tool_name,
        "product": detect_product_name(product, user_agent, tool_name, doorway=doorway),
        "bytes": byte_len, "kb": round(byte_len / 1024.0, 2), "est_tokens": est_tokens,
        "under_20kb_budget": byte_len <= 20480, "duration_ms": round(dur, 1),
    }
    with _WIRE_RING_LOCK:
        WIRE_TELEMETRY_RING.append(entry)
        if len(WIRE_TELEMETRY_RING) > MAX_WIRE_RING:
            del WIRE_TELEMETRY_RING[: len(WIRE_TELEMETRY_RING) - MAX_WIRE_RING]
    target_bg = bg_dir or (Path(os.getenv("AGY_DATA_DIR", str(Path.home() / ".gemini/antigravity"))).expanduser() / "sidecar_data/ag-bridge-bg")
    try:
        target_bg.mkdir(parents=True, exist_ok=True)
        with open(target_bg / "mcp_telemetry_ledger.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass
    return entry


def get_wire_telemetry_summary(bg_dir_or_limit: Any = None, limit: int = 25) -> dict[str, Any]:
    """Return summary metrics, product breakdown, handshake totals, and recent entries from wire telemetry."""
    lim = int(bg_dir_or_limit) if isinstance(bg_dir_or_limit, int) else int(limit or 25)
    bg_dir = bg_dir_or_limit if isinstance(bg_dir_or_limit, Path) else (Path(os.getenv("AGY_DATA_DIR", str(Path.home() / ".gemini/antigravity"))).expanduser() / "sidecar_data/ag-bridge-bg")
    with _WIRE_RING_LOCK:
        records = list(WIRE_TELEMETRY_RING)
    ledger_path = bg_dir / "mcp_telemetry_ledger.jsonl"
    if not records and ledger_path.exists():
        try:
            lines = ledger_path.read_text(encoding="utf-8", errors="replace").splitlines()[-MAX_WIRE_RING:]
            records = [json.loads(line) for line in lines if line.strip().startswith("{")]
        except Exception:
            records = []
    empty_hs = {"calls": 0, "bytes": 0, "tokens": 0, "tools_list_kb": 0.0}
    if not records:
        return {"total_recorded_calls": 0, "avg_kb": 0.0, "max_kb": 0.0, "total_mcp_tokens": 0, "budget_compliance_pct": 100.0, "by_product": {}, "protocol_handshakes": empty_hs, "recent_calls": []}
    tool_recs = [x for x in records if not _is_handshake_record(x)]
    hs_recs = [x for x in records if _is_handshake_record(x)]
    recent = [{**r, "product": _effective_record_product(r)} for r in reversed(records[-max(1, min(lim, 100)):])]
    tl_recs = [x for x in hs_recs if str(x.get("rpc") or "").strip().lower() == "tools/list" or str(x.get("tool") or "").strip() == "[rpc:tools/list]"]
    hs_bytes = sum(int(x.get("bytes", 0)) for x in hs_recs)
    hs_tokens = sum(int(x.get("est_tokens", 0) or round(int(x.get("bytes", 0)) / 4.0)) for x in hs_recs)
    protocol_handshakes = {"calls": len(hs_recs), "bytes": hs_bytes, "tokens": hs_tokens, "tools_list_kb": round(float(tl_recs[-1].get("kb", 0.0)), 2) if tl_recs else 0.0}
    if not tool_recs:
        return {"total_recorded_calls": 0, "avg_kb": 0.0, "max_kb": 0.0, "total_mcp_tokens": 0, "budget_compliance_pct": 100.0, "by_product": {}, "protocol_handshakes": protocol_handshakes, "recent_calls": recent}
    kb_vals, compliant = [float(x.get("kb", 0.0)) for x in tool_recs], sum(1 for x in tool_recs if x.get("under_20kb_budget", True))
    tot_tokens = sum(int(x.get("est_tokens", 0) or round(int(x.get("bytes", 0)) / 4.0)) for x in tool_recs)
    by_prod: dict[str, dict[str, int]] = {}
    for x in tool_recs:
        rec = by_prod.setdefault(_effective_record_product(x), {"calls": 0, "tokens": 0, "bytes": 0})
        rec["calls"] += 1
        rec["tokens"] += int(x.get("est_tokens", 0) or round(int(x.get("bytes", 0)) / 4.0))
        rec["bytes"] += int(x.get("bytes", 0))
    return {"total_recorded_calls": len(tool_recs), "avg_kb": round(sum(kb_vals) / len(kb_vals), 2), "max_kb": round(max(kb_vals), 2), "total_mcp_tokens": tot_tokens, "budget_compliance_pct": round((compliant / len(tool_recs)) * 100.0, 1), "by_product": by_prod, "protocol_handshakes": protocol_handshakes, "recent_calls": recent}


def extract_pending_approval(transcript_or_brain_dir: Path, conv_id: str = "") -> dict[str, Any] | None:
    """Inspect transcript.jsonl tail to extract exact tool call details when waiting/running."""
    t_path = transcript_or_brain_dir / conv_id / ".system_generated" / "logs" / "transcript.jsonl" if conv_id else transcript_or_brain_dir
    if not t_path.exists():
        return None
    try:
        fsize = t_path.stat().st_size
        with open(t_path, "rb") as f:
            if fsize > 49152:
                f.seek(fsize - 49152)
            lines = f.read().decode("utf-8", errors="replace").splitlines()
        for raw in reversed(lines[-20:]):
            if not raw.strip().startswith("{"):
                continue
            obj = json.loads(raw)
            tcs = obj.get("tool_calls")
            if isinstance(tcs, list) and tcs and isinstance(tcs[-1], dict):
                tc = tcs[-1]
                args = tc.get("arguments") or tc.get("args") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {"raw": args[:160]}
                detail = str(args.get("CommandLine") or args.get("TargetFile") or args.get("AbsolutePath") or args.get("Url") or args.get("toolSummary") or "")[:180] if isinstance(args, dict) else ""
                return {"step_index": obj.get("step_index"), "step_status": obj.get("status", "UNKNOWN"), "tool_name": str(tc.get("name") or tc.get("tool_name") or "tool_call"), "tool_action": str(args.get("toolAction") or args.get("toolSummary") or "") if isinstance(args, dict) else "", "detail": detail, "created_at": obj.get("created_at", "")}
    except Exception:
        return None
    return None


def _read_json_or_text(path: Path, is_json: bool = False) -> Any:
    try:
        return (json.loads if is_json else str.strip)(path.read_text(encoding="utf-8")) if path.exists() else None
    except Exception:
        return None

def get_live_quota_and_pool_status(data_or_config_dir: Path, config_dir: Path | None = None, *, bg_dir: Path | None = None) -> dict[str, Any]:
    """Read Dual-Pool Quota & Resets, active Main-Chat model, 429 cooldowns, and live LS/snapshot reset buckets."""
    from agy_nexus.ls_quota_probe import enrich_quota_and_pools

    agy_config_dir = config_dir if config_dir is not None else data_or_config_dir
    data_dir = data_or_config_dir if config_dir is not None else None
    q_file = Path(os.getenv("QUOTA_STATE_FILE", str(Path.home() / ".cache/antigravity/quota_state.json"))).expanduser()
    active_profile = _read_json_or_text(agy_config_dir / ".active-tier-profile") or "ultra-20x"
    state_data = _read_json_or_text(q_file, is_json=True) or {"pools": {"google": {}, "claude": {}, "gpt_oss": {}}, "events": []}
    now_epoch, pools_out = int(time.time()), {}
    for pk in ("google", "claude", "gpt_oss"):
        pi = (state_data.get("pools") or {}).get(pk) or {}
        rem = max(0, int(pi.get("cooldown_until", 0) or 0) - now_epoch)
        pools_out[pk] = {"status": "COOLDOWN_429" if rem > 0 else "HEALTHY", "cooldown_remaining_seconds": rem, "total_429_count": int(pi.get("count_429", 0) or 0), "last_reason": str(pi.get("last_reason", ""))}
    env_bg = os.getenv("AGY_BG_DIR", "").strip()
    resolved_bg = bg_dir or (Path(env_bg).expanduser() if env_bg else ((data_dir / "sidecar_data/ag-bridge-bg") if data_dir else None))
    try:
        live_quota = enrich_quota_and_pools(pools_out, bg_dir=resolved_bg)
    except Exception:
        live_quota = {"state": "UNAVAILABLE", "ls_alive": False, "is_fresh": False, "source": "error"}
    day_idx = datetime.now(timezone.utc).weekday() + 1
    return {
        "active_tier_profile": active_profile, "active_mainchat_model": get_active_mainchat_model(data_dir),
        "pools": pools_out, "live_quota": live_quota,
        "partner_weekly_window": {"day_of_week_index": day_idx, "daily_target_pct": 14.28, "recommended_cumulative_ceiling_pct": round(min(100.0, day_idx * 14.28), 1)},
        "tier_target_split": get_pool_target_split(active_profile), "target_model_allocation": MODEL_TARGET_ALLOCATION.get(active_profile, MODEL_TARGET_ALLOCATION["ultra-20x"]),
        "recent_quota_events": (state_data.get("events") or [])[-8:],
    }


def normalize_workspace_name(ws_raw: str) -> str:
    parts = [p for p in (ws_raw or "").rstrip("/").split("/") if p and p != ".git"]
    if "worktrees" in parts:
        idx = parts.index("worktrees")
        ws_name = parts[idx + 1] if (idx > 0 and parts[idx - 1] == "antigravity" and (idx + 1) < len(parts)) else (parts[idx - 1] if idx > 0 else parts[-1])
    else:
        ws_name = parts[-1] if parts else "unassigned"
    return re.sub(r"-wt-\d+$", "", ws_name)


def to_1h_slot(c_str: str, fallback_mtime: float) -> tuple[str, str, str]:
    if c_str:
        try:
            dt = datetime.fromisoformat(c_str.replace("Z", "+00:00"))
            dt_loc = (dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt).astimezone(DISPLAY_TZ)
            day_s = f"{dt_loc.year:04d}-{dt_loc.month:02d}-{dt_loc.day:02d}"
            return day_s, f"{day_s}T{dt_loc.hour:02d}", f"{day_s}T{(dt_loc.hour // 4) * 4:02d}"
        except Exception:
            if len(c_str) >= 10 and c_str[4] == "-":
                return c_str[:10], f"{c_str[:10]}T12", f"{c_str[:10]}T12"
    dt_fb = datetime.fromtimestamp(fallback_mtime, tz=DISPLAY_TZ)
    day_fb = dt_fb.strftime("%Y-%m-%d")
    return day_fb, f"{day_fb}T{dt_fb.hour:02d}", f"{day_fb}T{(dt_fb.hour // 4) * 4:02d}"


def to_4h_slot(c_str: str, fallback_mtime: float) -> tuple[str, str]:
    d, _, s4 = to_1h_slot(c_str, fallback_mtime)
    return d, s4


def _extract_tool_and_subagent_calls(
    obj: dict[str, Any],
    cur_mk: str,
    day_s: str,
    d_tools: dict[str, int],
    d_models: dict[str, dict[str, int]],
    m_counts: dict[str, int],
) -> tuple[int, int]:
    """Compute tool-call character count and count subagent spawns for one transcript row."""
    tcs = obj.get("tool_calls")
    if not isinstance(tcs, list) or not tcs:
        return 0, 0
    extra_chars, subs_added = 0, 0
    d_tools[day_s] = d_tools.get(day_s, 0) + len(tcs)
    for tc in tcs:
        if not isinstance(tc, dict):
            continue
        extra_chars += len(str(tc.get("arguments") or tc.get("args") or ""))
        if tc.get("name") == "invoke_subagent":
            args = tc.get("arguments") or tc.get("args") or {}
            for s in (args.get("Subagents") if isinstance(args, dict) else []) or []:
                if not isinstance(s, dict):
                    continue
                subs_added += 1
                raw_sm, role_s = str(s.get("Model") or ""), str(s.get("TypeName") or s.get("Role") or "")
                is_inh = (raw_sm.lower() == "inherit") or (
                    not raw_sm and not any(
                        k in role_s.lower()
                        for k in ("claude", "sonnet", "opus", "flash", "argon", "hydrogen", "neon", "carbon", "gpt")
                    )
                )
                mk = cur_mk if is_inh else classify_model_key(raw_sm, role_s)
                m_counts[mk] = m_counts.get(mk, 0) + 1
                dm = d_models.setdefault(day_s, {})
                dm[mk] = dm.get(mk, 0) + 1
    return extra_chars, subs_added


def _compute_step_tokens_and_cost(
    obj: dict[str, Any],
    cur_mk: str,
    day_s: str,
    step_chars: int,
    bg_dir: Path,
) -> tuple[bool, int, int, int, int, int, int]:
    """Compute token split (uncached, cached, output) and effective-dated micro-USD step cost."""
    is_planner = obj.get("type") == "PLANNER_RESPONSE"
    u_in = int(obj.get("input_tokens") or 0)
    c_in = int(obj.get("cache_read_tokens") or 0)
    out_t = int(obj.get("output_tokens") or 0)
    if is_planner and (u_in + c_in + out_t) > 0:
        est_tok = u_in + c_in + out_t
    else:
        est_tok = max(12, round(step_chars / 4.0))
        u_in, c_in, out_t = split_estimated_tokens(est_tok) if is_planner else (0, 0, 0)
    if not is_planner:
        return False, est_tok, u_in, c_in, out_t, 0, 0
    step_cost = compute_step_cost_micros(cur_mk, day_s, u_in, c_in, out_t, bg_dir=bg_dir)
    step_fore = compute_step_cost_micros(cur_mk, day_s, u_in, c_in, out_t, forecast=True, bg_dir=bg_dir)
    return True, est_tok, u_in, c_in, out_t, step_cost, step_fore


def _scan_single_transcript(
    t_path: Path,
    mtime: float,
    fsize: int,
    main_mk: str,
    main_switch_date: str,
    bg_dir: Path,
) -> dict[str, Any]:
    """Parse one transcript JSONL into daily/1h counts, 8-model attribution, token splits, cost & unmapped models."""
    m_keys = get_canonical_model_keys()
    d_steps, d_tools, d_tokens, d_cost, slot_steps = {}, {}, {}, {}, {}
    d_models, d_mtoks, d_mcost, d_mfore, d_msplits = {}, {}, {}, {}, {}
    s1_steps, s1_toks, s1_cost, s1_psplits = {}, {}, {}, {}
    s1_models, s1_mtoks, s1_mcost = {}, {}, {}
    exp_models, unmapped = {}, {}
    m_counts = {k: 0 for k in m_keys}
    m_tokens, m_cost, m_fore = {k: 0 for k in m_keys}, {k: 0 for k in m_keys}, {k: 0 for k in m_keys}
    tok_split = [0, 0, 0]
    subs_cnt, active_conv_mk, last_mod_seen = 0, "", ""

    with open(t_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.startswith("{"):
                continue
            obj = json.loads(line)
            created_raw = str(obj.get("created_at") or "")
            day_s, s1, slot_s = to_1h_slot(created_raw, mtime)
            c_txt = str(obj.get("content") or "")
            if "Model Selection" in c_txt:
                m_hits = MODEL_CHANGE_RE.findall(c_txt)
                if m_hits:
                    raw_sel = m_hits[-1].strip()
                    active_conv_mk, sel_ok = classify_model_key_status(raw_sel, "")
                    if not sel_ok:
                        record_unmapped_model_hit(unmapped, raw_sel, 0, created_raw or day_s, day_s)
            raw_m = str(obj.get("model") or "").strip()
            if raw_m:
                cur_mk, raw_m_ok = classify_model_key_status(raw_m, "")
            else:
                cur_mk, raw_m_ok = (active_conv_mk or (main_mk if (main_mk and main_switch_date and day_s >= main_switch_date) else "argon")), True
            if raw_m_ok or not last_mod_seen:
                last_mod_seen = cur_mk
            d_steps[day_s], slot_steps[slot_s], s1_steps[s1] = d_steps.get(day_s, 0) + 1, slot_steps.get(slot_s, 0) + 1, s1_steps.get(s1, 0) + 1
            extra_chars, subs_added = _extract_tool_and_subagent_calls(obj, cur_mk, day_s, d_tools, d_models, m_counts)
            subs_cnt += subs_added
            step_chars = len(c_txt) + len(str(obj.get("thinking") or "")) + extra_chars
            is_planner, est_tok, u_in, c_in, out_t, step_cost, step_fore = _compute_step_tokens_and_cost(obj, cur_mk, day_s, step_chars, bg_dir)
            if raw_m and not raw_m_ok:
                record_unmapped_model_hit(unmapped, raw_m, est_tok, created_raw or day_s, day_s)

            d_tokens[day_s], s1_toks[s1] = d_tokens.get(day_s, 0) + est_tok, s1_toks.get(s1, 0) + est_tok
            d_cost[day_s], s1_cost[s1] = d_cost.get(day_s, 0) + step_cost, s1_cost.get(s1, 0) + step_cost
            sm_map, smt_map, smc_map = s1_models.setdefault(s1, {}), s1_mtoks.setdefault(s1, {}), s1_mcost.setdefault(s1, {})
            sm_map[cur_mk], smt_map[cur_mk], smc_map[cur_mk] = sm_map.get(cur_mk, 0) + 1, smt_map.get(cur_mk, 0) + est_tok, smc_map.get(cur_mk, 0) + step_cost

            if is_planner:
                m_counts[cur_mk], m_tokens[cur_mk], m_cost[cur_mk], m_fore[cur_mk] = m_counts.get(cur_mk, 0) + 1, m_tokens.get(cur_mk, 0) + est_tok, m_cost.get(cur_mk, 0) + step_cost, m_fore.get(cur_mk, 0) + step_fore
                tok_split[0], tok_split[1], tok_split[2] = tok_split[0] + u_in, tok_split[1] + c_in, tok_split[2] + out_t
                sp_p = s1_psplits.setdefault(s1, [0, 0, 0])
                sp_p[0], sp_p[1], sp_p[2] = sp_p[0] + u_in, sp_p[1] + c_in, sp_p[2] + out_t
                d_models.setdefault(day_s, {})[cur_mk] = d_models.get(day_s, {}).get(cur_mk, 0) + 1
                if raw_m or active_conv_mk:
                    exp_models.setdefault(day_s, {})[cur_mk] = exp_models.get(day_s, {}).get(cur_mk, 0) + 1
                d_mtoks.setdefault(day_s, {})[cur_mk] = d_mtoks.get(day_s, {}).get(cur_mk, 0) + est_tok
                d_mcost.setdefault(day_s, {})[cur_mk] = d_mcost.get(day_s, {}).get(cur_mk, 0) + step_cost
                d_mfore.setdefault(day_s, {})[cur_mk] = d_mfore.get(day_s, {}).get(cur_mk, 0) + step_fore
                sp_cur = d_msplits.setdefault(day_s, {}).setdefault(cur_mk, [0, 0, 0])
                sp_cur[0], sp_cur[1], sp_cur[2] = sp_cur[0] + u_in, sp_cur[1] + c_in, sp_cur[2] + out_t

    return {
        "mtime": mtime, "size": fsize, "day_steps": d_steps, "day_tools": d_tools, "day_tokens": d_tokens, "day_cost_micros": d_cost,
        "slot_steps": slot_steps, "slot_1h_steps": s1_steps, "slot_1h_tokens": s1_toks, "slot_1h_cost_micros": s1_cost,
        "slot_1h_planner_splits": s1_psplits, "slot_1h_models": s1_models, "slot_1h_model_tokens": s1_mtoks,
        "slot_1h_model_cost_micros": s1_mcost, "day_models": d_models, "explicit_day_models": exp_models, "unmapped_models": unmapped,
        "day_model_tokens": d_mtoks, "day_model_cost_micros": d_mcost, "day_model_forecast_micros": d_mfore,
        "day_model_token_splits": d_msplits, "model_counts": m_counts, "model_tokens": m_tokens, "model_cost_micros": m_cost,
        "model_forecast_micros": m_fore, "token_breakdown": tok_split, "subagents_spawned": subs_cnt, "last_conv_model": active_conv_mk or last_mod_seen,
    }


def scan_transcript_stats(brain_dir: Path, bg_dir: Path) -> dict[str, Any]:
    cache_file = bg_dir / "nexus_stats_cache.json"
    cache: dict[str, Any] = {"cache_version": CACHE_VERSION, "conversations": {}}
    if cache_file.exists():
        try:
            loaded = json.loads(cache_file.read_text(encoding="utf-8"))
            if loaded.get("cache_version") == CACHE_VERSION:
                cache = loaded
        except Exception:
            pass
    main_info = get_active_mainchat_model(brain_dir.parent if brain_dir else None)
    main_mk, main_switch_date = str(main_info.get("model_key") or "argon"), str(main_info.get("state_updated_date") or "")
    conv_cache, updated = cache.setdefault("conversations", {}), False
    if brain_dir.exists():
        for entry in brain_dir.iterdir():
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            t_path = entry / ".system_generated" / "logs" / "transcript.jsonl"
            if not t_path.exists():
                continue
            try:
                st = t_path.stat()
                mtime, fsize = round(st.st_mtime, 2), st.st_size
            except Exception:
                continue
            cached = conv_cache.get(entry.name)
            if cached and cached.get("mtime") == mtime and cached.get("size") == fsize:
                continue
            try:
                conv_cache[entry.name] = _scan_single_transcript(t_path, mtime, fsize, main_mk, main_switch_date, bg_dir)
                updated = True
            except Exception:
                continue
    if updated:
        try:
            bg_dir.mkdir(parents=True, exist_ok=True)
            with _CACHE_LOCK, open(bg_dir / ".nexus_stats_cache.lock", "a+", encoding="utf-8") as lf:
                fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
                fd, tmp_name = tempfile.mkstemp(prefix=".nexus_stats_cache.", dir=str(bg_dir))
                try:
                    os.fchmod(fd, 0o600)
                    with os.fdopen(fd, "w", encoding="utf-8") as fh:
                        fd = -1
                        json.dump(cache, fh)
                    os.replace(tmp_name, cache_file)
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
                finally:
                    fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
    return conv_cache
