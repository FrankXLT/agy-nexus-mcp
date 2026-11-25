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
    REPLY_PROMPT_GUIDANCE,
    SESSION_STATE,
    TTL_SECONDS,
    _compact_json,
    get_antigravity_config_repo,
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
    compact_payload_to_wire_budget,
    parse_inline_line_spec,
    slice_file_content,
    within_wire_budget,
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

def _compact_session_tree_payload(out_payload: dict[str, Any], max_bytes: int = 17500) -> str:
    """Guarantee get_session_tree inner + escaped JSON stays strictly within wire budget."""
    out_s = _compact_json(out_payload)
    if within_wire_budget(out_s, max_raw_bytes=max_bytes, max_escaped_bytes=19600):
        return out_s
    rt = out_payload.get("routing_telemetry")
    if isinstance(rt, dict) and isinstance(rt.get("slots"), list):
        rt["slots"] = rt["slots"][:5]
    out_payload.pop("projects", None)
    out_s = _compact_json(out_payload)
    if within_wire_budget(out_s, max_raw_bytes=max_bytes, max_escaped_bytes=19600):
        return out_s
    if isinstance(rt, dict) and isinstance(rt.get("slots"), list):
        rt["slots"] = []
    qp = out_payload.get("quota_and_pools")
    if isinstance(qp, dict) and isinstance(qp.get("recent_quota_events"), list):
        qp["recent_quota_events"] = qp["recent_quota_events"][-2:]
    out_s = _compact_json(out_payload)
    if not within_wire_budget(out_s, max_raw_bytes=max_bytes, max_escaped_bytes=19600) and isinstance(out_payload.get("ascii_tree"), str):
        suffix = "\n... [compacted for <20KB wire ceiling — pass project_filter='<name>' or limit=5]"
        lines = out_payload["ascii_tree"].splitlines()
        while not within_wire_budget(out_s, max_raw_bytes=max_bytes, max_escaped_bytes=19600) and len(lines) > 6:
            lines = lines[: max(6, len(lines) - max(1, len(lines) // 4))]
            out_payload["ascii_tree"] = "\n".join(lines) + suffix
            out_s = _compact_json(out_payload)
    return compact_payload_to_wire_budget(out_payload, serializer=_compact_json, max_raw_bytes=max_bytes, max_escaped_bytes=19600)


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
    """Return 76-col Project->Chat->Session ID ASCII tree, slots & optional stats (include_stats=True, period, style=default|quick|rich)."""
    unlocked_now = is_unlocked(spoken_passphrase)
    if not unlocked_now and not (ALLOW_LOCKED_STATS and include_stats):
        return LOCKED_RESPONSE
    eff_lim = min(limit, 12) if include_stats else limit
    tree_bundle = (
        build_project_session_tree(active_only=active_only, project_filter=project_filter, limit=eff_lim, bg_dir=AGY_BG_DIR)
        if unlocked_now
        else {"locked": True, "ascii_tree": "[Locked — unlock_sessions required for project/session titles and slots]"}
    )
    stats_extra: dict[str, Any] = {}
    if include_stats:
        bundle = build_nexus_stats_bundle(
            data_dir=AGY_DATA_DIR, brain_dir=AGY_BRAIN_DIR, db_file=AGY_DB_FILE,
            config_dir=AGY_CONFIG_DIR, bg_dir=AGY_BG_DIR, period=period, style=style,
        )
        period_obj = bundle.get("period") if isinstance(bundle.get("period"), dict) else {}
        stats_extra = {
            "period_key": bundle.get("period_key") or period_obj.get("key"),
            "ascii_mobile_report": bundle.get("ascii_mobile_report"),
            "totals": bundle.get("totals") or bundle.get("kpis") or bundle.get("summary"),
            "quota_and_pools": bundle.get("quota_and_pools"),
        }
    out_payload = {
        "ok": True,
        "action": "get_session_tree_with_stats" if include_stats else "get_session_tree",
        "assistant_guidance": (
            (
                "Display ascii_mobile_report inside a fenced ```text block first (plus ascii_tree if session hierarchy was requested). "
                if include_stats
                else "Display ascii_tree verbatim inside a fenced ```text block so the user can copy untruncated session_id and workspace values. "
            )
            + "Sequential read-only follow-up calls (e.g. load_session_into_gemini or ask_workspace_readonly) are permitted (one call at a time, never in parallel). "
            + REPLY_PROMPT_GUIDANCE
        ),
        **stats_extra,
        **tree_bundle,
    }
    return _compact_session_tree_payload(out_payload, max_bytes=17500)

def _dispatch_models_action(style_clean: str) -> str:
    from agy_nexus.ascii_models import render_ascii_models_status
    from agy_nexus.catalog_report import build_unmapped_issue_url, finalize_unmapped_models
    from agy_nexus.catalog_sync import get_catalog_sync_status
    from agy_nexus.cost_ledger import read_model_drift_status
    from agy_nexus.model_pricing import load_model_catalog

    if style_clean == "ascii":
        return compact_payload_to_wire_budget({
            "ok": True, "action": "models", "style": "ascii",
            "assistant_guidance": (
                "Display ascii_models_report verbatim inside a fenced ```text code block. "
                "Sequential read-only follow-up calls are permitted (one call at a time, never in parallel). "
                + REPLY_PROMPT_GUIDANCE
            ),
            "ascii_models_report": render_ascii_models_status(data_dir=AGY_DATA_DIR, agy_config_dir=AGY_CONFIG_DIR, bg_dir=AGY_BG_DIR),
        }, serializer=_compact_json)
    drift = read_model_drift_status(AGY_BG_DIR)
    unmapped = finalize_unmapped_models({}, drift_status=drift)
    return compact_payload_to_wire_budget({
        "ok": True, "action": "models", "style": style_clean,
        "assistant_guidance": (
            "Structured 8-model pricing catalog and latest drift check retrieved below. "
            "Sequential read-only follow-up calls are permitted (one call at a time, never in parallel). "
            + REPLY_PROMPT_GUIDANCE
        ),
        "quota_and_pools": get_live_quota_and_pool_status(AGY_DATA_DIR, AGY_CONFIG_DIR, bg_dir=AGY_BG_DIR),
        "model_drift_status": drift,
        "catalog_sync": get_catalog_sync_status(data_dir=AGY_DATA_DIR, bg_dir=AGY_BG_DIR, allow_network=False),
        "unmapped_models": unmapped,
        "unmapped_issue_url": build_unmapped_issue_url(unmapped),
        "models": load_model_catalog().get("models") or [],
    }, serializer=_compact_json)


def _handle_job_status_or_tail(action_clean: str, job_id: str, tail_lines: int, period: str) -> str:
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
        return compact_payload_to_wire_budget({
            "ok": True, "conversation_id": conv_id, "job_id": safe_job_id,
            "assistant_guidance": f"Transcript tail retrieved below. Sequential read-only follow-up calls are permitted (one call at a time, never in parallel). {REPLY_PROMPT_GUIDANCE}",
            "pending_approval": pending_app, "tail_lines_count": len(parsed_tail), "transcript_tail": parsed_tail,
        }, serializer=_compact_json)
    if action_clean == "stop":
        if job_file and job_file.is_file():
            job_data["stopped_at"] = datetime.now(timezone.utc).isoformat()
            job_file.write_text(json.dumps(job_data, indent=2) + "\n", encoding="utf-8")
        return json.dumps({"ok": True, "action": "stop", "conversation_id": conv_id, "job_id": safe_job_id, "assistant_guidance": "STOP AND REPLY TO USER NOW.", "message": "Job status marked as stopped."}, indent=2)
    stats_fallback = build_nexus_stats_bundle(data_dir=AGY_DATA_DIR, brain_dir=AGY_BRAIN_DIR, db_file=AGY_DB_FILE, config_dir=AGY_CONFIG_DIR, bg_dir=AGY_BG_DIR, period=period or "last_90d")
    return compact_payload_to_wire_budget({
        "ok": True, "action": "status", "conversation_id": conv_id, "job_id": safe_job_id,
        "assistant_guidance": f"Job and session status retrieved below. If the user asked for stats, display ascii_mobile_report inside a ```text block now; otherwise report the job/session status. Sequential read-only follow-up calls are permitted (one call at a time, never in parallel). {REPLY_PROMPT_GUIDANCE}",
        "ascii_mobile_report": stats_fallback.get("ascii_mobile_report", ""),
        "quota_and_pools": stats_fallback.get("quota_and_pools", {}),
        "job_metadata": job_data, "db_info": db_info, "pending_approval": pending_app,
        "has_gui_lock": (AGY_PRESENCE_DIR / f"{conv_id}.lock").is_file(),
        "recent_events_count": len(parsed_tail), "recent_sample": parsed_tail[-4:] if parsed_tail else [],
    }, serializer=_compact_json)


@mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
def manage_background_run(
    action: str = "status", job_id: str = "", tail_lines: int = 40, period: str = "last_90d",
    style: str = "default", client_product: str = "", client_tokens_reported: int = 0, spoken_passphrase: str = "",
) -> str:
    """Get Quota/Heatmaps/Wire Stats (action=stats|telemetry|models, period=last_90d|current_month|last_month|last_year, style=default|quick|rich|ascii), tree, or export_notebook."""
    action_clean = action.strip().lower()
    style_clean = (style or "default").strip().lower()
    is_models_action = action_clean in ("models", "model_status", "models_status")
    is_deadbolt_safe_models = is_models_action and style_clean == "ascii"
    is_stats_action = action_clean in ("stats", "dashboard", "quota", "heatmap", "telemetry", "wire", "logs")
    if not is_unlocked(spoken_passphrase):
        if not (is_deadbolt_safe_models or (ALLOW_LOCKED_STATS and is_stats_action)):
            return LOCKED_RESPONSE
    if is_models_action:
        return _dispatch_models_action(style_clean)
    if action_clean in ("sessions", "session_status", "session_tree", "tree"):
        tree_bundle = build_project_session_tree(active_only=(style_clean == "active"), project_filter=job_id.strip() if job_id.strip().lower() != "latest" else "", limit=max(5, min(tail_lines, 40)), bg_dir=AGY_BG_DIR)
        return compact_payload_to_wire_budget({
            "ok": True, "action": action_clean,
            "assistant_guidance": f"Display ascii_tree verbatim inside a fenced ```text code block first so the user can copy untruncated session_id and workspace values. Sequential read-only follow-up calls are permitted (one call at a time, never in parallel). {REPLY_PROMPT_GUIDANCE}",
            **tree_bundle,
        }, serializer=_compact_json)
    if action_clean in ("export_notebook", "notebook", "sync_notebook"):
        export_res = export_notebook_bundle(brain_dir=AGY_BRAIN_DIR, db_file=AGY_DB_FILE, bg_dir=AGY_BG_DIR, projects_map=_load_projects_map())
        return compact_payload_to_wire_budget({
            "ok": True, "action": "export_notebook",
            "assistant_guidance": f"Session walkthrough.md and implementation_plan.md artifacts have been exported with SHA-256 deduplication. Sequential read-only follow-up calls are permitted (one call at a time, never in parallel). {REPLY_PROMPT_GUIDANCE}",
            **export_res,
        }, serializer=_compact_json)
    if action_clean in ("stats", "dashboard", "quota", "heatmap"):
        bundle = build_nexus_stats_bundle(data_dir=AGY_DATA_DIR, brain_dir=AGY_BRAIN_DIR, db_file=AGY_DB_FILE, config_dir=AGY_CONFIG_DIR, bg_dir=AGY_BG_DIR, period=period, style=style)
        drop_keys = {
            "heatmap_series", "velocity_series", "model_series", "workspace_series", "subagent_series",
            "project_hierarchy", "ascii_mobile_dashboard", "ascii_report_default", "ascii_report_quick",
            "ascii_report_rich", "summary", "project_session_tree", "hourly_whiskers", "all_workspaces",
            "subagent_role_breakdown", "wire_telemetry", "code_health", "routing_telemetry", "backup_321",
        }
        compact_bundle = {k: v for k, v in bundle.items() if k not in drop_keys}
        return compact_payload_to_wire_budget({
            "ok": True, "action": "stats",
            "assistant_guidance": f"Display ascii_mobile_report inside a fenced ```text code block first followed by a concise 3-bullet summary of Google 20x Pool share, Dual-Pool Quota & Resets, and Top Projects. Sequential read-only follow-up calls are permitted (one call at a time, never in parallel). {REPLY_PROMPT_GUIDANCE}",
            **compact_bundle,
        }, serializer=_compact_json)
    if action_clean in ("telemetry", "wire", "logs"):
        return compact_payload_to_wire_budget({
            "ok": True, "action": "telemetry",
            "assistant_guidance": f"Wire telemetry and quota summary retrieved below. Sequential read-only follow-up calls are permitted (one call at a time, never in parallel). {REPLY_PROMPT_GUIDANCE}",
            "wire_telemetry": get_wire_telemetry_summary(AGY_BG_DIR, limit=25),
            "quota_and_pools": get_live_quota_and_pool_status(AGY_DATA_DIR, AGY_CONFIG_DIR, bg_dir=AGY_BG_DIR),
        }, serializer=_compact_json)
    return _handle_job_status_or_tail(action_clean, job_id, tail_lines, period)
def _build_models_ascii_response() -> str:
    """Build deadbolt-safe <=76-col 8-model, subagent, pricing & drift report payload."""
    from agy_nexus.ascii_models import render_ascii_models_status

    quota_status = get_live_quota_and_pool_status(AGY_DATA_DIR, AGY_CONFIG_DIR, bg_dir=AGY_BG_DIR)
    active_profile = quota_status.get("active_tier_profile", quota_status.get("active_profile", "ultra-20x"))
    return compact_payload_to_wire_budget({
        "ok": True,
        "status": "OK",
        "style": "ascii",
        "active_profile": active_profile,
        "assistant_guidance": (
            "Display ascii_models_report verbatim inside a fenced ```text code block. "
            "Sequential read-only follow-up calls are permitted (one call at a time, never in parallel). "
            + REPLY_PROMPT_GUIDANCE
        ),
        "ascii_models_report": render_ascii_models_status(
            data_dir=AGY_DATA_DIR, agy_config_dir=AGY_CONFIG_DIR, bg_dir=AGY_BG_DIR,
        ),
    }, serializer=_compact_json)


def _inspect_customization_item(inspect_name: str, ws_path: Path | None) -> dict[str, Any]:
    """Resolve and line-slice a single requested skill, agent, or rule file."""
    clean_q, in_s, in_e, in_c = parse_inline_line_spec(inspect_name.strip())
    q_cand = (clean_q or inspect_name.strip()).strip()
    safe_q = (
        q_cand
        if re.fullmatch(r"(?:(?:skill|skills|agent|agents|rule|rules|global|workspace):)?[A-Za-z0-9_.-]{1,80}", q_cand) and ".." not in q_cand
        else ""
    )
    resolved_f = resolve_customization_file(safe_q, AGY_CONFIG_DIR, AGY_DATA_DIR, ws_path) if safe_q else None
    if resolved_f and resolved_f.is_file():
        slice_meta = slice_file_content(
            full_text=resolved_f.read_text(encoding="utf-8", errors="replace"),
            clean_path=resolved_f.name,
            per_file_cap=min(MAX_FILE_CHARS, 7500),
            inline_start_line=in_s,
            inline_end_line=in_e,
            center_line=in_c,
        )
        return {"requested": inspect_name.strip(), "path": str(resolved_f), **slice_meta}
    return {"requested": inspect_name.strip(), "error": f"Could not resolve skill, agent, or rule '{inspect_name}'."}


def _discover_host_bridge_summary() -> dict[str, Any]:
    """Query Host Companion discover endpoint briefly for live Language Server metadata."""
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
    out: dict[str, Any] = {
        "ok": bool(ls_discovery.get("ok")),
        "ls_reachable": bool(ls_discovery.get("ok") and ls_discovery.get("ls_address")),
        "ls_address": ls_discovery.get("ls_address", ""),
        "projects_count": len(ls_discovery.get("projects") or []),
    }
    if ls_discovery.get("error"):
        out["error"] = ls_discovery["error"]
    return out


def _collect_runtime_model_audit() -> dict[str, Any]:
    from agy_nexus.catalog_sync import get_catalog_sync_status
    from agy_nexus.stats import build_nexus_stats_bundle

    sync = get_catalog_sync_status(data_dir=AGY_DATA_DIR, bg_dir=AGY_BG_DIR, allow_network=False)
    compact_sync = {
        k: sync.get(k) for k in (
            "status", "upstream_branch", "checked_at", "bundled_revision", "effective_revision",
            "upstream_revision", "override_active", "update_available", "local_repo_dirty",
        )
    }
    sub_adj: list[dict[str, Any]] = []
    unmapped: list[dict[str, Any]] = []
    unmapped_url = ""
    try:
        b = build_nexus_stats_bundle(
            brain_dir=AGY_BRAIN_DIR, db_file=AGY_DB_FILE, agy_config_dir=AGY_CONFIG_DIR,
            bg_dir=AGY_BG_DIR, data_dir=AGY_DATA_DIR, period="last_30d",
            include_ascii=False, compact_sessions=True,
        )
        for r in (b.get("subagent_list") or [])[:20]:
            sub_adj.append({
                "role": r.get("role"), "runs": r.get("runs"),
                "intended": r.get("intended_model_label"), "actual": r.get("actual_model_label"),
                "actual_pct": r.get("actual_dominant_pct"), "inherited": r.get("is_inherited"),
                "diverged": r.get("model_diverged"), "status": r.get("adjudication_status"),
                "text": r.get("adjudication_text"),
            })
        unmapped = b.get("unmapped_models") or []
        unmapped_url = str(b.get("unmapped_issue_url") or "")
    except Exception:
        pass
    return {
        "subagent_adjudication": sub_adj,
        "unmapped_models": unmapped,
        "unmapped_issue_url": unmapped_url,
        "catalog_sync": compact_sync,
    }


@mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
def list_models_and_agents(
    include_skills: bool = True,
    include_rules: bool = True,
    skill_scope_filter: str = "core",
    inspect_name: str = "",
    style: str = "json",
    spoken_passphrase: str = "",
) -> str:
    """List Antigravity agents, skills (skill_scope_filter=core|all|plugin:<name>), rules, scope policy, Quota & Resets & LS status. Pass style='ascii' with include_skills=False, include_rules=False for deadbolt-safe 76-col matrix."""
    style_clean = (style or "json").strip().lower()
    is_deadbolt_safe_ascii = (
        style_clean == "ascii"
        and not include_skills
        and not include_rules
        and not (inspect_name or "").strip()
    )
    if not is_unlocked(spoken_passphrase) and not is_deadbolt_safe_ascii:
        return LOCKED_RESPONSE
    if is_deadbolt_safe_ascii:
        return _build_models_ascii_response()

    ws_str = SESSION_STATE.get("selected_workspace") or str(get_antigravity_config_repo())
    ws_path = Path(ws_str).resolve() if ws_str and Path(ws_str).is_dir() else None
    agents_list = collect_agents_inventory(AGY_CONFIG_DIR, ws_path)
    skills_list = collect_skills_inventory(AGY_CONFIG_DIR, AGY_DATA_DIR, ws_path, scope_filter=skill_scope_filter) if include_skills else []
    plugin_bundles = collect_plugin_bundles_summary(AGY_CONFIG_DIR) if include_skills else []
    rules_inv = collect_rules_inventory(AGY_CONFIG_DIR, ws_path) if include_rules else {}
    session_scope = evaluate_session_customization_scope(ws_str, AGY_CONFIG_DIR, AGY_GITLAB_DIR)
    quota_status = get_live_quota_and_pool_status(AGY_DATA_DIR, AGY_CONFIG_DIR, bg_dir=AGY_BG_DIR)
    inspected_item = _inspect_customization_item(inspect_name, ws_path) if inspect_name.strip() else {}
    active_profile = quota_status.get("active_tier_profile", quota_status.get("active_profile", "ultra-20x"))
    runtime_audit = _collect_runtime_model_audit()
    out_payload: dict[str, Any] = {
        "ok": True, "status": "OK",
        "assistant_guidance": (
            "Agents, skills, rules, and model quota inventory retrieved successfully. "
            "You may synthesize your response directly, or issue a sequential read-only follow-up call (e.g. inspect_name or ask_workspace_readonly, one call at a time, up to 4 sequential hops/turn—never in parallel). "
            + REPLY_PROMPT_GUIDANCE
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
        "language_server": _discover_host_bridge_summary(),
        **runtime_audit,
    }
    if inspected_item:
        out_payload["inspected_item"] = inspected_item
    out_json = _compact_json(out_payload)
    if not within_wire_budget(out_json) and inspected_item and isinstance(inspected_item.get("content"), str):
        content_s = inspected_item["content"]
        excess = len(out_json.encode("utf-8")) - 17500
        inspected_item["content"] = content_s[: max(900, len(content_s) - max(excess, 1500))] + "\n... [compacted for <20KB wire ceiling — use ask_workspace_readonly with start_line/end_line]"
        inspected_item["truncated"] = True
        out_json = _compact_json(out_payload)
    if not within_wire_budget(out_json) and isinstance(out_payload.get("skills"), list):
        for sk in out_payload["skills"]:
            if isinstance(sk, dict) and "description" in sk:
                sk["description"] = str(sk["description"])[:60]
    return compact_payload_to_wire_budget(out_payload, serializer=_compact_json)
