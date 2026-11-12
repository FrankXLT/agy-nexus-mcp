#!/usr/bin/env python3
"""
agy-nexus-mcp — Wire Telemetry Ledger, Quota Pool Pacing & Transcript Mtime Scanner
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

CACHE_VERSION = 6
WIRE_TELEMETRY_RING: list[dict[str, Any]] = []
MAX_WIRE_RING = 200
MODEL_CHANGE_RE = re.compile(
    r"changed setting `?Model Selection`? from .+? to `?([^\n`]+?)`?\.(?:\s+No need|\s*</USER_SETTINGS_CHANGE>|\s*$)",
    re.MULTILINE,
)

ANTIGRAVITY_MODEL_PLACEHOLDERS: dict[str, dict[str, str]] = {
    "MODEL_PLACEHOLDER_M417": {"id": "MODEL_PLACEHOLDER_M417", "model_key": "carbon", "label": "Gemini 4 Carbon", "pool": "20x Google Ultra", "subagent_inherit": "Gemini 4 Carbon"},
    "MODEL_PLACEHOLDER_M427": {"id": "MODEL_PLACEHOLDER_M427", "model_key": "carbon", "label": "Gemini 4 Carbon", "pool": "20x Google Ultra", "subagent_inherit": "Gemini 4 Carbon"},
    "MODEL_PLACEHOLDER_M322": {"id": "MODEL_PLACEHOLDER_M322", "model_key": "flash", "label": "Gemini 3.8 Flash", "pool": "20x Google Ultra", "subagent_inherit": "Gemini 3.8 Flash"},
}

def get_active_mainchat_model(data_dir: Path | None = None) -> dict[str, Any]:
    """Read last_selected_agent_model from antigravity_state.pbtxt and resolve physical model metadata."""
    base = data_dir or Path(os.getenv("AGY_DATA_DIR", str(Path.home() / ".gemini/antigravity"))).expanduser()
    pb_file = base / "antigravity_state.pbtxt"
    raw_ph, switched_iso = "MODEL_PLACEHOLDER_M417", ""
    if pb_file.is_file():
        try:
            txt = pb_file.read_text(encoding="utf-8", errors="replace")
            m = re.search(r"last_selected_agent_model:\s*([A-Za-z0-9_.-]+)", txt)
            if m: raw_ph = m.group(1).strip()
            switched_iso = datetime.fromtimestamp(pb_file.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            pass
    is_carb = any(k in raw_ph.lower() for k in ("417", "427", "carbon"))
    info = dict(ANTIGRAVITY_MODEL_PLACEHOLDERS.get(raw_ph, {"id": raw_ph, "model_key": classify_model_key(raw_ph, ""), "label": "Gemini 4 Carbon" if is_carb else "Gemini 4 Argon (Pro)", "pool": "20x Google Ultra", "subagent_inherit": "Gemini 4 Carbon" if is_carb else "Gemini 4 Argon"}))
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
    "ultra-20x": {
        "carbon": {"label": "Gemini 4 Carbon", "pool": "20x Google Ultra", "target_pct": 25.0},
        "argon_pro": {"label": "Gemini 4 Argon (Pro)", "pool": "20x Google Ultra", "target_pct": 40.0},
        "flash": {"label": "Gemini 3.8 Flash", "pool": "20x Google Ultra", "target_pct": 25.0},
        "claude_partner": {"label": "Claude Sonnet/Opus 5.5", "pool": "Partner Pool (Weekly)", "target_pct": 8.0},
        "gpt_oss": {"label": "GPT-OSS 120B", "pool": "Partner Pool (Failover)", "target_pct": 2.0},
    },
    "ultra-5x": {
        "carbon": {"label": "Gemini 4 Carbon", "pool": "5x Google Pool", "target_pct": 15.0},
        "argon_pro": {"label": "Gemini 4 Argon (Pro)", "pool": "5x Google Pool", "target_pct": 25.0},
        "flash": {"label": "Gemini 3.8 Flash", "pool": "5x Google Pool", "target_pct": 35.0},
        "claude_partner": {"label": "Claude Sonnet/Opus 5.5", "pool": "Partner Pool (Weekly)", "target_pct": 20.0},
        "gpt_oss": {"label": "GPT-OSS 120B", "pool": "Partner Pool (Failover)", "target_pct": 5.0},
    },
}
def detect_product_name(raw_product: str = "", user_agent: str = "", tool_name: str = "") -> str:
    s = f"{raw_product or ''} {user_agent or ''}".lower()
    if any(k in s for k in ("mobile", "android", "iphone", "gsa/")): return "Gemini Mobile"
    if "web_ui" in tool_name or "web_stats" in tool_name or "mozilla" in s: return "Web Dashboard"
    if any(k in s for k in ("gemini", "google", "vertex", "http-client")): return "Gemini Web / Cloud MCP"
    return "Antigravity IDE" if ("antigravity" in s or "agy" in s) else (raw_product.strip() or "Gemini MCP Client")

def record_wire_telemetry(tool_or_event: str | dict[str, Any], payload_or_bg_dir: Any = "", duration_ms: float = 0.0, *, bg_dir: Path | None = None, product: str = "", reported_tokens: int = 0) -> dict[str, Any]:
    """Record wire payload size, estimated context tokens, product source, and latency for MCP calls."""
    req_bytes, user_agent = 0, ""
    if isinstance(tool_or_event, dict):
        byte_len, req_bytes = int(tool_or_event.get("bytes", 0) or 0), int(tool_or_event.get("req_bytes", 0) or 0)
        tool_name, dur = str(tool_or_event.get("tool") or tool_or_event.get("rpc") or "mcp"), float(tool_or_event.get("ms", duration_ms) or 0.0)
        product, user_agent = str(tool_or_event.get("product") or product or ""), str(tool_or_event.get("user_agent") or "")
        reported_tokens = int(tool_or_event.get("reported_tokens", reported_tokens) or 0)
        if isinstance(payload_or_bg_dir, Path) and bg_dir is None:
            bg_dir = payload_or_bg_dir
    else:
        byte_len, tool_name, dur = len(str(payload_or_bg_dir or "").encode("utf-8")), str(tool_or_event or "mcp"), float(duration_ms or 0.0)
    est_tokens = reported_tokens if reported_tokens > 0 else max(1, round((byte_len + req_bytes) / 4.0))
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "tool": tool_name, "product": detect_product_name(product, user_agent, tool_name), "bytes": byte_len, "kb": round(byte_len / 1024.0, 2), "est_tokens": est_tokens, "under_20kb_budget": byte_len <= 20480, "duration_ms": round(dur, 1)}
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
    """Return summary metrics, product breakdown, and recent entries from the persistent wire telemetry ledger."""
    lim = int(bg_dir_or_limit) if isinstance(bg_dir_or_limit, int) else int(limit or 25)
    bg_dir = bg_dir_or_limit if isinstance(bg_dir_or_limit, Path) else (Path(os.getenv("AGY_DATA_DIR", str(Path.home() / ".gemini/antigravity"))).expanduser() / "sidecar_data/ag-bridge-bg")
    records = list(WIRE_TELEMETRY_RING)
    ledger_path = bg_dir / "mcp_telemetry_ledger.jsonl"
    if not records and ledger_path.exists():
        try:
            lines = ledger_path.read_text(encoding="utf-8", errors="replace").splitlines()[-MAX_WIRE_RING:]
            records = [json.loads(line) for line in lines if line.strip().startswith("{")]
        except Exception:
            records = []
    if not records:
        return {"total_recorded_calls": 0, "avg_kb": 0.0, "max_kb": 0.0, "total_mcp_tokens": 0, "budget_compliance_pct": 100.0, "by_product": {}, "recent_calls": []}
    recent = list(reversed(records[-max(1, min(lim, 100)) :]))
    kb_vals, compliant = [float(x.get("kb", 0.0)) for x in records], sum(1 for x in records if x.get("under_20kb_budget", True))
    tot_tokens = sum(int(x.get("est_tokens", 0) or round(int(x.get("bytes", 0)) / 4.0)) for x in records)
    by_prod: dict[str, dict[str, int]] = {}
    for x in records:
        rec = by_prod.setdefault(str(x.get("product") or "Gemini MCP Client"), {"calls": 0, "tokens": 0, "bytes": 0})
        rec["calls"], rec["tokens"], rec["bytes"] = rec["calls"] + 1, rec["tokens"] + int(x.get("est_tokens", 0) or round(int(x.get("bytes", 0)) / 4.0)), rec["bytes"] + int(x.get("bytes", 0))
    return {"total_recorded_calls": len(records), "avg_kb": round(sum(kb_vals) / len(kb_vals), 2), "max_kb": round(max(kb_vals), 2), "total_mcp_tokens": tot_tokens, "budget_compliance_pct": round((compliant / len(records)) * 100.0, 1), "by_product": by_prod, "recent_calls": recent}

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

def get_live_quota_and_pool_status(data_or_config_dir: Path, config_dir: Path | None = None) -> dict[str, Any]:
    """Read live Dual-Pool Quota Pacing (`ultra-20x` vs `ultra-5x`), active Main-Chat model, 429 cooldowns, and Partner Pool weekly pace."""
    agy_config_dir = config_dir if config_dir is not None else data_or_config_dir
    data_dir = data_or_config_dir if config_dir is not None else None
    q_file = Path(os.getenv("QUOTA_STATE_FILE", str(Path.home() / ".cache/antigravity/quota_state.json"))).expanduser()
    p_file = agy_config_dir / ".active-tier-profile"
    active_profile = "ultra-20x"
    if p_file.exists():
        try:
            active_profile = p_file.read_text(encoding="utf-8").strip() or "ultra-20x"
        except Exception:
            pass
    state_data: dict[str, Any] = {"pools": {"google": {}, "claude": {}, "gpt_oss": {}}, "events": []}
    if q_file.exists():
        try:
            state_data = json.loads(q_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    now_epoch, pools_out = int(time.time()), {}
    for pk in ("google", "claude", "gpt_oss"):
        pi = (state_data.get("pools") or {}).get(pk) or {}
        rem = max(0, int(pi.get("cooldown_until", 0) or 0) - now_epoch)
        pools_out[pk] = {"status": "COOLDOWN_429" if rem > 0 else "HEALTHY", "cooldown_remaining_seconds": rem, "total_429_count": int(pi.get("count_429", 0) or 0), "last_reason": str(pi.get("last_reason", ""))}
    day_idx = datetime.now(timezone.utc).weekday() + 1
    return {"active_tier_profile": active_profile, "active_mainchat_model": get_active_mainchat_model(data_dir), "pools": pools_out, "partner_weekly_pacing": {"day_of_week_index": day_idx, "daily_target_pct": 14.28, "recommended_cumulative_ceiling_pct": round(min(100.0, day_idx * 14.28), 1)}, "target_model_allocation": MODEL_TARGET_ALLOCATION.get(active_profile, MODEL_TARGET_ALLOCATION["ultra-20x"]), "recent_quota_events": (state_data.get("events") or [])[-8:]}

def classify_model_key(raw_model: str, agent_name: str = "") -> str:
    s = f"{raw_model or ''} {agent_name or ''}".lower()
    if any(k in s for k in ("claude", "sonnet", "opus")): return "claude_partner"
    if "gpt" in s or "120b" in s: return "gpt_oss"
    if "flash" in s or "m322" in s: return "flash"
    if any(k in s for k in ("carbon", "m417", "m427")): return "carbon"
    return "argon_pro"

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

def scan_transcript_stats(brain_dir: Path, bg_dir: Path) -> dict[str, Any]:
    cache_file = bg_dir / "nexus_stats_cache.json"
    cache: dict[str, Any] = {"cache_version": CACHE_VERSION, "conversations": {}}
    if cache_file.exists():
        try:
            loaded = json.loads(cache_file.read_text(encoding="utf-8"))
            if loaded.get("cache_version") == CACHE_VERSION: cache = loaded
        except Exception:
            pass
    main_info = get_active_mainchat_model(brain_dir.parent if brain_dir else None)
    main_mk, main_switch_date = str(main_info.get("model_key") or "argon_pro"), str(main_info.get("state_updated_date") or "")
    conv_cache, updated = cache.setdefault("conversations", {}), False
    if brain_dir.exists():
        for entry in brain_dir.iterdir():
            if not entry.is_dir() or entry.name.startswith("."): continue
            t_path = entry / ".system_generated" / "logs" / "transcript.jsonl"
            if not t_path.exists(): continue
            try:
                st = t_path.stat()
                mtime, fsize = round(st.st_mtime, 2), st.st_size
            except Exception:
                continue
            cached = conv_cache.get(entry.name)
            if cached and cached.get("mtime") == mtime and cached.get("size") == fsize: continue
            d_steps, d_tools, d_tokens, slot_steps, d_models, d_mtoks = {}, {}, {}, {}, {}, {}
            s1_steps, s1_toks, s1_models, s1_mtoks = {}, {}, {}, {}
            m_counts = {"carbon": 0, "argon_pro": 0, "flash": 0, "claude_partner": 0, "gpt_oss": 0}
            m_tokens = {"carbon": 0, "argon_pro": 0, "flash": 0, "claude_partner": 0, "gpt_oss": 0}
            subs_cnt, active_conv_mk = 0, ""
            try:
                with open(t_path, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        if not line.startswith("{"): continue
                        obj = json.loads(line)
                        day_s, s1, slot_s = to_1h_slot(str(obj.get("created_at") or ""), mtime)
                        c_txt = str(obj.get("content") or "")
                        if "Model Selection" in c_txt:
                            m_hits = MODEL_CHANGE_RE.findall(c_txt)
                            if m_hits: active_conv_mk = classify_model_key(m_hits[-1], "")
                        raw_m = str(obj.get("model") or "")
                        cur_mk = classify_model_key(raw_m, "") if raw_m else (active_conv_mk or (main_mk if (main_mk == "carbon" and main_switch_date and day_s >= main_switch_date) else "argon_pro"))
                        d_steps[day_s], slot_steps[slot_s], s1_steps[s1] = d_steps.get(day_s, 0) + 1, slot_steps.get(slot_s, 0) + 1, s1_steps.get(s1, 0) + 1
                        step_chars = len(c_txt) + len(str(obj.get("thinking") or ""))
                        tcs = obj.get("tool_calls")
                        if isinstance(tcs, list) and tcs:
                            d_tools[day_s] = d_tools.get(day_s, 0) + len(tcs)
                            for tc in tcs:
                                if isinstance(tc, dict):
                                    step_chars += len(str(tc.get("arguments") or tc.get("args") or ""))
                                    if tc.get("name") == "invoke_subagent":
                                        args = tc.get("arguments") or tc.get("args") or {}
                                        for s in (args.get("Subagents") if isinstance(args, dict) else []) or []:
                                            if isinstance(s, dict):
                                                subs_cnt += 1
                                                raw_sm, role_s = str(s.get("Model") or ""), str(s.get("TypeName") or s.get("Role") or "")
                                                is_inh = raw_sm.lower() in ("inherit", "") and not any(k in role_s.lower() for k in ("claude", "flash", "argon", "gpt"))
                                                mk = cur_mk if is_inh else classify_model_key(raw_sm, role_s)
                                                m_counts[mk] = m_counts.get(mk, 0) + 1
                                                dm = d_models.setdefault(day_s, {})
                                                dm[mk] = dm.get(mk, 0) + 1
                        est_tok = max(12, round(step_chars / 4.0))
                        d_tokens[day_s], s1_toks[s1] = d_tokens.get(day_s, 0) + est_tok, s1_toks.get(s1, 0) + est_tok
                        sm_map, smt_map = s1_models.setdefault(s1, {}), s1_mtoks.setdefault(s1, {})
                        sm_map[cur_mk], smt_map[cur_mk] = sm_map.get(cur_mk, 0) + 1, smt_map.get(cur_mk, 0) + est_tok
                        if obj.get("type") == "PLANNER_RESPONSE":
                            m_counts[cur_mk], m_tokens[cur_mk] = m_counts.get(cur_mk, 0) + 1, m_tokens.get(cur_mk, 0) + est_tok
                            dm, dtk = d_models.setdefault(day_s, {}), d_mtoks.setdefault(day_s, {})
                            dm[cur_mk], dtk[cur_mk] = dm.get(cur_mk, 0) + 1, dtk.get(cur_mk, 0) + est_tok
                conv_cache[entry.name] = {"mtime": mtime, "size": fsize, "day_steps": d_steps, "day_tools": d_tools, "day_tokens": d_tokens, "slot_steps": slot_steps, "slot_1h_steps": s1_steps, "slot_1h_tokens": s1_toks, "slot_1h_models": s1_models, "slot_1h_model_tokens": s1_mtoks, "day_models": d_models, "day_model_tokens": d_mtoks, "model_counts": m_counts, "model_tokens": m_tokens, "subagents_spawned": subs_cnt, "last_conv_model": active_conv_mk}
                updated = True
            except Exception:
                continue
    if updated:
        try:
            bg_dir.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(cache), encoding="utf-8")
        except Exception:
            pass
    return conv_cache
