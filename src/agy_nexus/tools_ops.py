#!/usr/bin/env python3
"""agy_nexus.tools_ops — Background Job Monitor, Telemetry Stats & 4-Layer Inventory Tools."""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
from typing import Any
import urllib.request
import agy_nexus.config as cfg
from agy_nexus.config import (
    AGY_BG_DIR,
    AGY_BRAIN_DIR,
    AGY_CONFIG_DIR,
    AGY_DATA_DIR,
    AGY_DB_FILE,
    AGY_GITLAB_DIR,
    AGY_PRESENCE_DIR,
    ALLOW_LOCKED_STATS,
    LOCKED_RESPONSE,
    READONLY_ANNOTATIONS,
    SESSION_STATE,
    TTL_SECONDS,
    _compact_json,
    is_unlocked,
    mcp,
)
from agy_nexus.hygiene import (
    MAX_DIFF_CHARS,
    MAX_FILE_CHARS,
    MAX_FILES_PER_CALL,
    MAX_TOTAL_FILE_CHARS,
    MAX_TRANSCRIPT_TURNS,
    MODULAR_HYGIENE_STANDARDS,
    _summarize_jsonl_line,
    parse_inline_line_spec,
    slice_file_content,
)
from agy_nexus.inventory import (
    CUSTOMIZATION_SCOPE_POLICY,
    collect_agents_inventory,
    collect_plugin_bundles_summary,
    collect_rules_inventory,
    collect_skills_inventory,
    evaluate_session_customization_scope,
    resolve_customization_file,
)
from agy_nexus.search import _get_configured_mcp_servers
from agy_nexus.session_tree import build_project_session_tree
from agy_nexus.sessions import _list_saved_sessions_internal, _load_projects_map
from agy_nexus.stats import (
    build_nexus_stats_bundle,
    extract_pending_approval,
    get_live_quota_and_pool_status,
    get_wire_telemetry_summary,
)
from agy_nexus.workflows import export_notebook_bundle

@mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
def get_session_tree(
    active_only: bool = False,
    project_filter: str = "",
    limit: int = 25,
    include_stats: bool = False,
    period: str = "last_90d",
    style: str = "default",
    spoken_passphrase: str = "",
) -> str:
    """Return a copy-ready 76-column ASCII Project -> Chat -> Session ID hierarchy tree (with untruncated UUIDs and workspace paths), parallel context slot telemetry, 3-2-1 backup status, and optional policy-safe Dual-Pool Quota & Activity Heatmap stats (include_stats=True, period='last_90d'|'current_month'|'last_month'|'last_year', style='default'|'quick'|'rich')."""
    if not is_unlocked(spoken_passphrase):
        if not (ALLOW_LOCKED_STATS and include_stats):
            return LOCKED_RESPONSE
    eff_lim = min(limit, 12) if include_stats else limit
    tree_bundle = build_project_session_tree(active_only=active_only, project_filter=project_filter, limit=eff_lim, bg_dir=AGY_BG_DIR)
    stats_extra: dict[str, Any] = {}
    if include_stats:
        bundle = build_nexus_stats_bundle(
            data_dir=AGY_DATA_DIR, brain_dir=AGY_BRAIN_DIR, db_file=AGY_DB_FILE,
            config_dir=AGY_CONFIG_DIR, bg_dir=AGY_BG_DIR, period=period, style=style,
        )
        stats_extra = {
            "period_key": bundle.get("period_key"),
            "ascii_mobile_report": bundle.get("ascii_mobile_report"),
            "totals": bundle.get("totals"),
            "quota_and_pools": bundle.get("quota_and_pools"),
        }
    out_payload = {
        "ok": True,
        "action": "get_session_tree_with_stats" if include_stats else "get_session_tree",
        "assistant_guidance": (
            "STOP AND REPLY TO USER NOW: Do NOT chain a second MCP tool after a successful response (all data is already included below). "
            "However, if a tool call fails with permission_denied or an immediate error, you MAY automatically invoke ask_workspace_readonly(question='Stats', file_subpath='telemetry:stats') or load_session_into_gemini once as a same-turn fallback without asking the user to reply 'Go'. "
            + (
                "Render ascii_mobile_report inside a fenced ```text block first (plus ascii_tree if session hierarchy was requested)."
                if include_stats
                else "Render ascii_tree verbatim inside a fenced ```text block so the user can copy untruncated session_id and workspace values."
            )
        ),
        **stats_extra,
        **tree_bundle,
    }
    out_s = _compact_json(out_payload)
    if include_stats and len(out_s.encode("utf-8")) > 19200:
        out_payload.pop("projects", None)
        out_s = _compact_json(out_payload)
    return out_s

@mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
def manage_background_run(
    action: str = "status",
    job_id: str = "",
    tail_lines: int = 40,
    period: str = "last_90d",
    style: str = "default",
    client_product: str = "",
    client_tokens_reported: int = 0,
    spoken_passphrase: str = "",
) -> str:
    """Retrieve live Dual-Pool Quota Pacing, Activity Heatmaps, and Wire Telemetry (action='stats' or action='telemetry', period='last_90d'|'current_month'|'last_month'|'last_year', style='default'|'quick'|'rich'), render 76-col Project -> Chat -> Session ID hierarchy tree (action='sessions' or action='session_status'), or export session plans/walkthroughs for Gemini Notebook (action='export_notebook').
    NOTE: For routine session 'Check-in' or checking active execution status, PREFER calling load_session_into_gemini or ask_workspace_readonly directly to avoid Gemini Mobile verb-permission collisions."""
    action_clean = action.strip().lower()
    is_stats_action = action_clean in ("stats", "dashboard", "quota", "heatmap", "telemetry", "wire", "logs")
    if not is_unlocked(spoken_passphrase):
        if not (ALLOW_LOCKED_STATS and is_stats_action):
            return LOCKED_RESPONSE
    if action_clean in ("sessions", "session_status", "session_tree", "tree"):
        tree_bundle = build_project_session_tree(active_only=(style.strip().lower() == "active"), project_filter=job_id.strip() if job_id.strip().lower() != "latest" else "", limit=max(5, min(tail_lines, 40)), bg_dir=AGY_BG_DIR)
        return _compact_json({
            "ok": True, "action": action_clean,
            "assistant_guidance": (
                "STOP AND REPLY TO USER NOW: Display ascii_tree verbatim inside a fenced ```text code block first "
                "so the user can copy untruncated session_id and workspace values. "
                "Do NOT chain a second MCP tool after a successful response (all data is already included below). "
                "However, if a tool call fails with permission_denied or an immediate error, you MAY automatically invoke ask_workspace_readonly or load_session_into_gemini once as a same-turn fallback without asking the user to reply 'Go'."
            ),
            **tree_bundle,
        })
    if action_clean in ("export_notebook", "notebook", "sync_notebook"):
        export_res = export_notebook_bundle(brain_dir=AGY_BRAIN_DIR, db_file=AGY_DB_FILE, bg_dir=AGY_BG_DIR, projects_map=_load_projects_map())
        return _compact_json({
            "ok": True, "action": "export_notebook",
            "assistant_guidance": (
                "STOP AND REPLY TO USER NOW: Session walkthrough.md and implementation_plan.md artifacts have been exported with SHA-256 deduplication. "
                "Do NOT chain a second MCP tool after a successful response (all data is already included below). "
                "However, if a tool call fails with permission_denied or an immediate error, you MAY automatically invoke ask_workspace_readonly or load_session_into_gemini once as a same-turn fallback without asking the user to reply 'Go'."
            ),
            **export_res,
        })
    if action_clean in ("stats", "dashboard", "quota", "heatmap"):
        bundle = build_nexus_stats_bundle(data_dir=AGY_DATA_DIR, brain_dir=AGY_BRAIN_DIR, db_file=AGY_DB_FILE, config_dir=AGY_CONFIG_DIR, bg_dir=AGY_BG_DIR, period=period, style=style)
        drop_keys = {"heatmap_series", "velocity_series", "model_series", "workspace_series", "subagent_series", "project_hierarchy", "ascii_mobile_dashboard", "ascii_report_default", "ascii_report_quick", "ascii_report_rich", "summary", "project_session_tree"}
        compact_bundle = {k: v for k, v in bundle.items() if k not in drop_keys}
        return _compact_json({
            "ok": True, "action": "stats",
            "assistant_guidance": (
                "STOP AND REPLY TO USER NOW: Display ascii_mobile_report inside a fenced ```text code block first followed by a concise 3-bullet summary of Google 20x Pool share, Partner Weekly Pacing vs Target, and Top Projects. "
                "Do NOT chain a second MCP tool after a successful response (all data is already included below). "
                "However, if a tool call fails with permission_denied or an immediate error, you MAY automatically invoke ask_workspace_readonly or load_session_into_gemini once as a same-turn fallback without asking the user to reply 'Go'."
            ),
            **compact_bundle,
        })
    if action_clean in ("telemetry", "wire", "logs"):
        return _compact_json({
            "ok": True, "action": "telemetry",
            "assistant_guidance": (
                "STOP AND REPLY TO USER NOW with the wire telemetry and quota summary below. "
                "Do NOT chain a second MCP tool after a successful response (all data is already included below). "
                "However, if a tool call fails with permission_denied or an immediate error, you MAY automatically invoke ask_workspace_readonly or load_session_into_gemini once as a same-turn fallback without asking the user to reply 'Go'."
            ),
            "wire_telemetry": get_wire_telemetry_summary(AGY_BG_DIR, limit=25),
            "quota_and_pools": get_live_quota_and_pool_status(AGY_DATA_DIR, AGY_CONFIG_DIR),
        })
    conv_id = SESSION_STATE.get("selected_session", "")
    job_file: Path | None = None
    job_data: dict[str, Any] = {}
    safe_job_id = re.sub(r"[^a-zA-Z0-9_-]", "", job_id.strip())
    if safe_job_id and safe_job_id.lower() != "latest":
        cand_file = AGY_BG_DIR / f"{safe_job_id}.json"
        if cand_file.is_file():
            job_file = cand_file
            try:
                job_data = json.loads(job_file.read_text(encoding="utf-8"))
                conv_id = str(job_data.get("conversation_id") or conv_id)
            except Exception:
                pass
    if not job_file and AGY_BG_DIR.is_dir():
        try:
            for jf in sorted(AGY_BG_DIR.glob("job-*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
                jdata = json.loads(jf.read_text(encoding="utf-8"))
                if not conv_id or jdata.get("conversation_id") == conv_id:
                    job_file, job_data = jf, jdata
                    safe_job_id = str(jdata.get("job_id") or jf.stem)
                    conv_id = str(jdata.get("conversation_id") or conv_id)
                    break
        except Exception:
            pass
    if not conv_id:
        sessions = _list_saved_sessions_internal(limit=1, status_filter="ALL")
        if sessions and sessions[0].get("conversation_id"):
            conv_id = str(sessions[0]["conversation_id"])
    if not conv_id:
        return json.dumps({"ok": False, "error": "No session selected and no valid job_id provided."}, indent=2)
    db_info: dict[str, Any] = {}
    if AGY_DB_FILE.is_file():
        try:
            con = sqlite3.connect(f"file:{AGY_DB_FILE}?mode=ro", uri=True)
            try:
                row = con.execute("SELECT title, status, step_count, last_modified_time, not_fully_idle, killed FROM conversation_summaries WHERE conversation_id = ?", (conv_id,)).fetchone()
            finally:
                con.close()
            if row:
                db_info = {"title": row[0], "status": row[1], "step_count": row[2], "last_modified": row[3], "not_fully_idle": bool(row[4]), "killed": bool(row[5])}
        except Exception:
            pass
    transcript_file = AGY_BRAIN_DIR / conv_id / ".system_generated" / "logs" / "transcript.jsonl"
    raw_lines: list[str] = []
    if transcript_file.is_file():
        try:
            all_lines = [l for l in transcript_file.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
            raw_lines = all_lines[-max(1, min(tail_lines, 60)):]
        except Exception:
            pass
    parsed_tail = [_summarize_jsonl_line(l) for l in raw_lines]
    pending_app = extract_pending_approval(transcript_file)
    if action_clean == "tail":
        return json.dumps({
            "ok": True, "conversation_id": conv_id, "job_id": safe_job_id,
            "assistant_guidance": (
                "STOP AND REPLY TO USER NOW with the transcript tail below. "
                "Do NOT chain a second MCP tool after a successful response (all data is already included below). "
                "However, if a tool call fails with permission_denied or an immediate error, you MAY automatically invoke ask_workspace_readonly or load_session_into_gemini once as a same-turn fallback without asking the user to reply 'Go'."
            ),
            "pending_approval": pending_app, "tail_lines_count": len(parsed_tail), "transcript_tail": parsed_tail,
        }, indent=2)
    if action_clean == "stop":
        if job_file and job_file.is_file():
            job_data["stopped_at"] = datetime.now(timezone.utc).isoformat()
            job_file.write_text(json.dumps(job_data, indent=2) + "\n", encoding="utf-8")
        return json.dumps({
            "ok": True, "action": "stop", "conversation_id": conv_id, "job_id": safe_job_id,
            "assistant_guidance": "STOP AND REPLY TO USER NOW.", "message": "Job status marked as stopped.",
        }, indent=2)
    stats_fallback = build_nexus_stats_bundle(data_dir=AGY_DATA_DIR, brain_dir=AGY_BRAIN_DIR, db_file=AGY_DB_FILE, config_dir=AGY_CONFIG_DIR, bg_dir=AGY_BG_DIR, period=period or "last_90d")
    return _compact_json({
        "ok": True, "action": "status", "conversation_id": conv_id, "job_id": safe_job_id,
        "assistant_guidance": (
            "STOP AND REPLY TO USER NOW: Do NOT chain a second MCP tool after a successful response (all data is already included below). "
            "However, if a tool call fails with permission_denied or an immediate error, you MAY automatically invoke ask_workspace_readonly or load_session_into_gemini once as a same-turn fallback without asking the user to reply 'Go'. "
            "If the user asked for stats, display ascii_mobile_report inside a ```text block now; otherwise report the job/session status."
        ),
        "ascii_mobile_report": stats_fallback.get("ascii_mobile_report", ""),
        "quota_and_pools": stats_fallback.get("quota_and_pools", {}),
        "job_metadata": job_data, "db_info": db_info, "pending_approval": pending_app,
        "has_gui_lock": (AGY_PRESENCE_DIR / f"{conv_id}.lock").is_file(),
        "recent_events_count": len(parsed_tail), "recent_sample": parsed_tail[-4:] if parsed_tail else [],
    })
@mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
def list_models_and_agents(
    include_skills: bool = True,
    include_rules: bool = True,
    skill_scope_filter: str = "core",
    inspect_name: str = "",
    spoken_passphrase: str = "",
) -> str:
    """List Antigravity agent roles, core skills (workspace, user_global, builtin), installed plugin skill bundles (pass skill_scope_filter='all' or 'plugin:<name>' to expand plugin descriptions), global & workspace rules, Customization Scope-Isolation policy, modular hygiene standards, live Dual-Pool Quota Pacing, and Language Server connectivity. Pass inspect_name (e.g. 'agy-nexus-stats', 'argon-sentinel', 'GEMINI.md') to read a specific item."""
    if not is_unlocked(spoken_passphrase):
        return LOCKED_RESPONSE
    ws_str = SESSION_STATE.get("selected_workspace") or str(AGY_GITLAB_DIR / "antigravity-config")
    ws_path = Path(ws_str).resolve() if ws_str and Path(ws_str).is_dir() else None
    agents_list = collect_agents_inventory(AGY_CONFIG_DIR, ws_path)
    skills_list = (
        collect_skills_inventory(AGY_CONFIG_DIR, AGY_DATA_DIR, ws_path, scope_filter=skill_scope_filter)
        if include_skills
        else []
    )
    plugin_bundles = collect_plugin_bundles_summary(AGY_CONFIG_DIR) if include_skills else []
    rules_inv = collect_rules_inventory(AGY_CONFIG_DIR, ws_path) if include_rules else {}
    session_scope = evaluate_session_customization_scope(ws_str, AGY_CONFIG_DIR, AGY_GITLAB_DIR)
    quota_status = get_live_quota_and_pool_status(AGY_DATA_DIR, AGY_CONFIG_DIR)
    inspected_item: dict[str, Any] = {}
    if inspect_name.strip():
        clean_q, in_s, in_e, in_c = parse_inline_line_spec(inspect_name.strip())
        q_cand = (clean_q or inspect_name.strip()).strip()
        safe_q = q_cand if re.fullmatch(r"(?:(?:skill|skills|agent|agents|rule|rules|global|workspace):)?[A-Za-z0-9_.-]{1,80}", q_cand) and ".." not in q_cand else ""
        resolved_f = resolve_customization_file(safe_q, AGY_CONFIG_DIR, AGY_DATA_DIR, ws_path) if safe_q else None
        if resolved_f and resolved_f.is_file():
            raw_txt = resolved_f.read_text(encoding="utf-8", errors="replace")
            slice_meta = slice_file_content(
                full_text=raw_txt,
                clean_path=resolved_f.name,
                per_file_cap=min(MAX_FILE_CHARS, 7500),
                inline_start_line=in_s,
                inline_end_line=in_e,
                center_line=in_c,
            )
            inspected_item = {
                "requested": inspect_name.strip(), "path": str(resolved_f),
                **slice_meta,
            }
        else:
            inspected_item = {"requested": inspect_name.strip(), "error": f"Could not resolve skill, agent, or rule '{inspect_name}'."}
    active_profile = quota_status.get("active_profile", "ultra-20x")
    ls_discovery: dict[str, Any] = {}
    try:
        req = urllib.request.Request(
            cfg.AGY_HOST_BRIDGE_URL,
            data=json.dumps({"action": "discover"}).encode("utf-8"),
            headers=cfg.get_host_bridge_headers(),
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            ls_discovery = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as e:
        ls_discovery = {"ok": False, "error": str(e)}
    ls_reachable = bool(ls_discovery.get("ok") and ls_discovery.get("ls_address"))
    ls_compact: dict[str, Any] = {
        "ok": bool(ls_discovery.get("ok")), "ls_reachable": ls_reachable,
        "ls_address": ls_discovery.get("ls_address", ""),
        "projects_count": len(ls_discovery.get("projects") or []),
    }
    if ls_discovery.get("error"):
        ls_compact["error"] = ls_discovery["error"]
    out_payload: dict[str, Any] = {
        "ok": True, "status": "OK",
        "assistant_guidance": (
            "STOP AND REPLY TO USER NOW: Do NOT chain a second MCP tool after a successful response (all data is already included below). "
            "However, if a tool call fails with permission_denied or an immediate error, you MAY automatically invoke ask_workspace_readonly or load_session_into_gemini once as a same-turn fallback without asking the user to reply 'Go'."
        ),
        "active_profile": active_profile, "quota_and_pools": quota_status,
        "customization_scope_policy": CUSTOMIZATION_SCOPE_POLICY, "session_customization_scope": session_scope,
        "agents_count": len(agents_list), "agents": agents_list,
        "skills_count": len(skills_list), "skills": skills_list,
        "plugin_skill_bundles": plugin_bundles, "rules_inventory": rules_inv,
        "configured_mcp_servers": _get_configured_mcp_servers(), "project_hygiene_standards": MODULAR_HYGIENE_STANDARDS,
        "context_window_config": {
            "ttl_seconds": TTL_SECONDS, "max_file_chars": MAX_FILE_CHARS,
            "max_total_file_chars": MAX_TOTAL_FILE_CHARS, "max_files_per_call": MAX_FILES_PER_CALL,
            "max_diff_chars": MAX_DIFF_CHARS, "max_transcript_turns": MAX_TRANSCRIPT_TURNS,
        },
        "language_server": ls_compact,
    }
    if inspected_item:
        out_payload["inspected_item"] = inspected_item
    out_json = _compact_json(out_payload)
    if len(out_json.encode("utf-8")) > 19200 and inspected_item and isinstance(inspected_item.get("content"), str):
        content_s = inspected_item["content"]
        excess = len(out_json.encode("utf-8")) - 18500
        new_len = max(1200, len(content_s) - max(excess, 1500))
        inspected_item["content"] = content_s[:new_len] + "\n... [compacted for <20KB wire ceiling — use ask_workspace_readonly with start_line/end_line]"
        inspected_item["truncated"] = True
        out_json = _compact_json(out_payload)
    if len(out_json.encode("utf-8")) > 19200 and isinstance(out_payload.get("skills"), list):
        for sk in out_payload["skills"]:
            if isinstance(sk, dict) and "description" in sk:
                sk["description"] = str(sk["description"])[:60]
        out_json = _compact_json(out_payload)
    return out_json
