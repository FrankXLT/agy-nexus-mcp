#!/usr/bin/env python3
"""
agy_nexus.handoff — Research Handoff Synthesis, Repo-Slugged Queueing & Headless Wakeup Tool.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any

import agy_nexus.config as cfg
from agy_nexus.config import (
    AGY_CONFIG_DIR, AGY_DATA_DIR, AGY_GITLAB_DIR, ALLOW_LOCKED_STAGING,
    HANDOFF_ANNOTATIONS, LOCKED_RESPONSE, REPLY_PROMPT_GUIDANCE, SESSION_STATE,
    _compact_json, get_antigravity_config_repo, is_unlocked, mcp, pin_session_context,
)
from agy_nexus.handoff_queue import (
    canonicalize_handoff_id, mark_ticket_status,
    record_handoff_ticket, resolve_staged_ticket_for_resume,
)
from agy_nexus.handoff_templates import (
    build_execution_lifecycle_footer, build_existing_session_lifecycle_text,
    resolve_effective_execution_mode, resolve_execution_mode_with_reason,
)
from agy_nexus.hygiene import ENFORCE_MODULAR_HYGIENE, MODULAR_HYGIENE_MARKDOWN_BLOCK
from agy_nexus.inventory import (
    _resolve_skill_directives,  # noqa: F401
    build_interjection_directive, evaluate_session_customization_scope,
)
from agy_nexus.routing import (
    _resolve_session_identifier, _resolve_target_session_for_handoff, _session_matches_repo_hint,
)
from agy_nexus.retirement import (
    build_suggested_actions, get_closeout_directives, is_closeout_intent,
    is_session_retired, record_session_retirement,
)
from agy_nexus.session_status import (
    _get_selected_session_quick_status, check_context_exceeded,
    check_inflight_handoff_mutex, evaluate_rollover_posture, extract_prior_session_baton,
)
from agy_nexus.target_resolver import (
    _USER_BODY_END, _USER_BODY_START, apply_global_scope_isolation,
    extract_markdown_heading as _extract_markdown_heading,
    infer_workspace_and_project as _infer_workspace_and_project,
    post_host_bridge as _post_bridge, resolve_handoff_target,
    unwrap_staged_handoff_markdown as _unwrap_staged_handoff_markdown,
)
from agy_nexus.telemetry_scanner import get_active_mainchat_model
from agy_nexus.workflow_baseline import evaluate_handoff_quality  # noqa: F401
from agy_nexus.workflow_gate import validate_handoff_workflow_gates
from agy_nexus.workflows import stage_quarantine_handoff

MODE_MAPPING = {
    "feature_update": "feature_update", "new_project": "new_project",
    "bug_or_visual_fix": "bug_or_visual_fix", "release_closeout": "release_closeout",
    "intent": "feature_update", "visual_critique": "bug_or_visual_fix",
    "surgical_audit": "bug_or_visual_fix", "closeout": "release_closeout",
}


def _compose_handoff_document(
    *, ts_now: str, eff_exec_mode: str, eff_handoff_mode: str, allow_chained_publish: bool,
    model: str, effort: str, apply_hygiene: bool, body_clean: str, baton_block: str,
    activate_skills: str, target_agent_role: str, edit_scope_clean: str, active_ws: str,
    retire_session: bool = False, is_closeout: bool = False, conv_id: str = "", retire_after_closeout: bool = False,
    workflow_block: str = "",
) -> dict[str, Any]:
    """Assemble full wrapped handoff markdown plus proportional lifecycle prompt blocks."""
    interjection_block, cust_scope_info = build_interjection_directive(
        activate_skills=activate_skills, target_agent_role=target_agent_role,
        customization_edit_scope=edit_scope_clean, research_markdown=body_clean,
        workspace_str=active_ws, config_dir=AGY_CONFIG_DIR, data_dir=AGY_DATA_DIR,
        gitlab_dir=AGY_GITLAB_DIR, handoff_mode=eff_handoff_mode,
    )
    main_model_info = get_active_mainchat_model(AGY_DATA_DIR)
    header = (
        f"<!-- Handshake Gemini Research Handoff -->\n<!-- Generated: {ts_now} -->\n"
        f"<!-- Execution Mode: {eff_exec_mode} | Handoff Mode: {eff_handoff_mode} | Chained Publish: {allow_chained_publish} | Model: {model} | MainChat: {main_model_info.get('model_label', 'Gemini 4 Carbon')} | Effort: {effort} | Modular Hygiene: {apply_hygiene} -->\n\n"
    )
    stage_gate_block = (
        "> [!IMPORTANT]\n> **STAGE & PREVIEW ONLY (`allow_chained_publish=False`)**: Do NOT run `git push`, `publish_to_github.py`, or remote production stack redeployments in this turn.\n"
        "> Stage all changes locally, capture verification screenshots and diffs, and halt execution so Gemini and the user can inspect via `inspect_git_diff` / `/web/media/` links. **You MUST still restart the local `ag-bridge-mcp` service/container** whenever Python/web files change so fixes take effect in memory immediately.\n\n"
        if not allow_chained_publish else ""
    )
    closeout_block = get_closeout_directives(active_ws, conv_id=conv_id, retire_after_closeout=retire_after_closeout) if (retire_session or is_closeout) else ""
    subagent_footer = build_execution_lifecycle_footer(eff_exec_mode, eff_handoff_mode, body_clean)
    hygiene_suffix = f"\n{MODULAR_HYGIENE_MARKDOWN_BLOCK.strip()}\n" if (apply_hygiene and "Mandatory Modular Architecture" not in body_clean) else ""
    wrapped_user_body = f"{_USER_BODY_START}\n{body_clean}\n{_USER_BODY_END}"
    full_content = header + stage_gate_block + workflow_block + baton_block + closeout_block + wrapped_user_body + interjection_block + hygiene_suffix + subagent_footer + "\n"
    return {
        "full_content": full_content, "workflow_block": workflow_block, "stage_gate_block": stage_gate_block,
        "interjection_block": interjection_block, "closeout_block": closeout_block,
        "hygiene_suffix": hygiene_suffix, "subagent_footer": subagent_footer,
        "cust_scope_info": cust_scope_info, "main_model_info": main_model_info,
    }


def _write_or_append_scratch(
    target: Path,
    full_content: str,
    body_clean: str,
    baton_block: str,
    interjection_block: str,
    ts_now: str,
    is_resume_staged: bool,
    append_to_existing: bool,
) -> str:
    """Write or append handoff markdown to a session scratch file."""
    if is_resume_staged:
        if not target.is_file():
            target.write_text(full_content, encoding="utf-8")
        return "read_staged"
    if append_to_existing and target.is_file():
        existing_raw = target.read_text(encoding="utf-8", errors="replace").rstrip()
        if _USER_BODY_END in existing_raw:
            idx_end = existing_raw.rindex(_USER_BODY_END)
            updated = f"{existing_raw[:idx_end].rstrip()}\n\n---\n<!-- Appended: {ts_now} -->\n\n{body_clean}\n{existing_raw[idx_end:]}\n"
            target.write_text(updated, encoding="utf-8")
        else:
            target.write_text(f"{existing_raw}\n\n---\n<!-- Appended: {ts_now} -->\n\n{baton_block}{body_clean}{interjection_block}\n", encoding="utf-8")
        return "appended"
    target.write_text(full_content, encoding="utf-8")
    return "written"


def _run_headless_new_session(ctx: dict[str, Any]) -> str:
    """Spawn a brand-new headless Antigravity conversation and bind its handoff ticket."""
    title_clean, body_clean = ctx["title_clean"], ctx["body_clean"]
    eff_ws, eff_pid, eff_pname, repo_slug = ctx["eff_ws"], ctx["eff_pid"], ctx["eff_pname"], ctx["repo_slug"]
    doc, ts_now, model, effort = ctx["doc"], ctx["ts_now"], ctx["model"], ctx["effort"]
    eff_exec_mode, eff_handoff_mode = ctx["eff_exec_mode"], ctx["eff_handoff_mode"]
    allow_chained_publish, apply_hygiene, use_worktree = ctx["allow_chained_publish"], ctx["apply_hygiene"], ctx["use_worktree"]
    create_new_proj, eff_branch = bool(ctx.get("create_new_project")), str(ctx.get("default_branch") or "main")

    prompt_body = body_clean if len(body_clean) <= 4200 else f"{body_clean[:4200]}\n\n... [Full {len(body_clean)}-char specification written to session brain `scratch/gemini_research_handoff.md` — read that file first]"
    spawn_prompt = f"# {title_clean}\n\nThe user initiated this project from Google Gemini via `agy-nexus-mcp` (Handoff Mode: {eff_handoff_mode}, Execution Mode: {eff_exec_mode}).\n\n{doc['stage_gate_block']}{doc.get('workflow_block', '')}{ctx['baton_block']}{prompt_body}{doc['interjection_block']}{doc['hygiene_suffix']}{doc['subagent_footer']}\n\nPlease review session brain `scratch/gemini_research_handoff.md` and modular hygiene requirements above, create `task.md`, and execute in `{eff_exec_mode}` mode."
    bridge_response = _post_bridge({"action": "new-conversation", "model": model if model in ("flash_lite", "flash", "pro") else "pro", "title": title_clean, "prompt": spawn_prompt, "project_id": eff_pid, "project_name": eff_pname, "workspace_path": eff_ws, "create_new_project": create_new_proj, "default_branch": eff_branch})
    new_conv_id = str(bridge_response.get("conversation_id") or "").strip()
    pinned_ws = str(bridge_response.get("workspace_path") or eff_ws)
    pinned_pid = str(bridge_response.get("project_id") or eff_pid)
    pinned_pname = str(bridge_response.get("project_name") or eff_pname)
    bridge_ok = bool(bridge_response.get("ok"))
    job_id = f"job-{hashlib.sha256(f'{new_conv_id or title_clean}-{time.time()}'.encode()).hexdigest()[:8]}"

    resumed_tid = ctx.get("resumed_ticket_id") or ""
    defer_retire = bool(ctx.get("retire_after_closeout"))
    if resumed_tid:
        ticket = mark_ticket_status(cfg.AGY_BG_DIR, resumed_tid, "IN_WORK" if bridge_ok else "STAGED", conversation_id=new_conv_id, job_id=job_id, claim_method="headless_wakeup", retire_after_closeout=defer_retire) or {}
    else:
        ticket = record_handoff_ticket(
            cfg.AGY_BG_DIR, full_markdown=doc["full_content"], chars_written=len(body_clean), repo_slug=repo_slug,
            title=title_clean, project_id=pinned_pid, project_name=pinned_pname,
            workspace_path=pinned_ws, target_conversation_id=new_conv_id, rollover_from=ctx["auto_rollover_from"],
            execution_mode=eff_exec_mode, handoff_mode=eff_handoff_mode, allow_chained_publish=allow_chained_publish,
            initial_status="IN_WORK" if bridge_ok else "STAGED", claimed_by_conversation_id=new_conv_id if bridge_ok else "",
            job_id=job_id, supersede_handoff_id=ctx["supersede_handoff_id"], append_to_existing=ctx["append_to_existing"],
            create_new_project=create_new_proj, default_branch=eff_branch, retire_after_closeout=defer_retire,
            workflow_ids=ctx.get("workflow_ids", []), workflow_delta=ctx.get("workflow_delta", ""),
        )

    if new_conv_id:
        pin_session_context(new_conv_id, title=title_clean, project_id=pinned_pid, project_name=pinned_pname, workspace=pinned_ws, mode="WORKTREE" if use_worktree else "MAIN WRITER", last_tool="send_handoff_and_resume", set_default=True)
        scratch_dir = cfg.AGY_BRAIN_DIR / new_conv_id / "scratch"
        scratch_dir.mkdir(parents=True, exist_ok=True)
        handoff_file = scratch_dir / "gemini_research_handoff.md"
        write_mode = _write_or_append_scratch(handoff_file, doc["full_content"], body_clean, ctx["baton_block"], doc["interjection_block"], ts_now, ctx["is_resume_staged"], ctx["append_to_existing"])
    else:
        handoff_file = Path(str(ticket.get("handoff_file") or (cfg.AGY_BG_DIR / "latest_gemini_handoff.md")))
        write_mode = "read_staged" if ctx["is_resume_staged"] else "written"

    cfg.AGY_BG_DIR.mkdir(parents=True, exist_ok=True)
    hid = str(ticket.get("handoff_id") or "")
    job_meta: dict[str, Any] = {"job_id": job_id, "handoff_id": hid, "conversation_id": new_conv_id, "project_id": pinned_pid, "project_name": pinned_pname, "workspace_path": pinned_ws, "create_new_project": create_new_proj, "default_branch": eff_branch, "started_at": ts_now, "execution_mode": eff_exec_mode, "handoff_mode": eff_handoff_mode, "workflow_ids": ctx.get("workflow_ids", []), "workflow_delta": ctx.get("workflow_delta", ""), "allow_chained_publish": allow_chained_publish, "model": model, "active_mainchat_model": doc["main_model_info"], "effort": effort, "created_new_session": bool(new_conv_id and bridge_ok), "modular_hygiene_enforced": apply_hygiene, "customization_scope_info": doc["cust_scope_info"], "bridge_response": bridge_response}
    if defer_retire:
        job_meta["retire_after_closeout"] = True
    if ctx["auto_rollover_from"]:
        job_meta["auto_rollover_from"] = ctx["auto_rollover_from"]
    (cfg.AGY_BG_DIR / f"{job_id}.json").write_text(json.dumps(job_meta, indent=2) + "\n", encoding="utf-8")
    guidance = (
        f"STOP AND REPLY TO USER NOW: Handoff {hid} delivered and session resumed in background. Do NOT chain a second MCP tool after a successful response. {REPLY_PROMPT_GUIDANCE}"
        if bridge_ok else
        f"STOP AND REPLY TO USER NOW: Host bridge failed to spawn headless session ({bridge_response.get('error', 'bridge error')}); handoff {hid} remains staged at {handoff_file} (say 'Run handoff {hid}' in Antigravity IDE). {REPLY_PROMPT_GUIDANCE}"
    )
    t_stat = str(ticket.get("status", "IN_WORK"))
    out: dict[str, Any] = {"ok": bridge_ok, "status": "RESUMED" if bridge_ok else "FAILED", "handoff_id": hid, "handoff_status": t_stat, "ticket_status": t_stat, "created_new_session": bool(new_conv_id and bridge_ok), "create_new_project": create_new_proj, "default_branch": eff_branch, "resumed": bridge_ok, "write_mode": write_mode, "chars_written": len(body_clean), "execution_mode": eff_exec_mode, "modular_hygiene_enforced": apply_hygiene, "customization_scope_info": doc["cust_scope_info"], "active_mainchat_model": doc["main_model_info"], "job_id": job_id, "conversation_id": new_conv_id, "handoff_mode": eff_handoff_mode, "workflow_ids": ctx.get("workflow_ids", []), "workflow_delta": ctx.get("workflow_delta", ""), "allow_chained_publish": allow_chained_publish, "workspace_path": pinned_ws, "project_id": pinned_pid, "project_name": pinned_pname, "handoff_file": str(handoff_file), "assistant_guidance": guidance, "bridge_response": bridge_response}
    out["suggested_actions"] = build_suggested_actions("in_flight" if bridge_ok else "ready_to_run", target=repo_slug, conv_id=new_conv_id, is_running=bridge_ok, handoff_id=hid)
    if defer_retire:
        out["retire_after_closeout"] = True
    if ctx.get("coerced_from_fast"):
        out["coerced_from_fast"] = True
    if ctx["execution_mode_advisory"]:
        out["execution_mode_advisory"] = ctx["execution_mode_advisory"]
    if ctx["auto_rollover_from"]:
        out["auto_rollover_from"], out["auto_promoted_rollover"] = ctx["auto_rollover_from"], True
    if ctx["size_warning"]:
        out["size_warning"] = ctx["size_warning"]
    if ctx.get("handoff_advisory"):
        out["handoff_advisory"] = ctx["handoff_advisory"]
    return json.dumps(out, indent=2)


def _stage_new_chat_handoff(ctx: dict[str, Any]) -> str:
    """Stage an unclaimed `<repo-slug>-NN` ticket when no conversation_id is active (and pre-provision IDE project if greenfield)."""
    eff_ws, eff_pid, eff_pname, repo_slug = ctx["eff_ws"], ctx["eff_pid"], ctx["eff_pname"], ctx["repo_slug"]
    create_new_proj, eff_branch = bool(ctx.get("create_new_project")), str(ctx.get("default_branch") or "main")
    project_provisioned, ensure_warn = False, ""
    if create_new_proj and not ctx.get("target_exists"):
        ens = _post_bridge({"action": "ensure-project", "project_id": eff_pid, "project_name": eff_pname, "workspace_path": eff_ws, "create_new_project": True, "default_branch": eff_branch})
        if ens.get("ok"):
            eff_pid = str(ens.get("project_id") or eff_pid)
            eff_pname = str(ens.get("project_name") or eff_pname)
            eff_ws = str(ens.get("workspace_path") or eff_ws)
            project_provisioned = True
        else:
            err_s = str(ens.get("error") or "")
            if "outside allowed roots" in err_s.lower() or "direct child" in err_s.lower():
                return json.dumps({"ok": False, "status": "OUTSIDE_ALLOWED_ROOTS", "error": err_s}, indent=2)
            ensure_warn = err_s

    doc, title_clean, body_clean = ctx["doc"], ctx["title_clean"], ctx["body_clean"]
    defer_retire = bool(ctx.get("retire_after_closeout"))
    ticket = record_handoff_ticket(
        cfg.AGY_BG_DIR, full_markdown=doc["full_content"], chars_written=len(body_clean), repo_slug=repo_slug,
        title=title_clean, project_id=eff_pid, project_name=eff_pname, workspace_path=eff_ws,
        target_conversation_id="", rollover_from=ctx["auto_rollover_from"], execution_mode=ctx["eff_exec_mode"],
        handoff_mode=ctx["eff_handoff_mode"], allow_chained_publish=ctx["allow_chained_publish"],
        initial_status="STAGED", supersede_handoff_id=ctx["supersede_handoff_id"],
        append_to_existing=ctx["append_to_existing"], create_new_project=create_new_proj, default_branch=eff_branch,
        retire_after_closeout=defer_retire, workflow_ids=ctx.get("workflow_ids", []), workflow_delta=ctx.get("workflow_delta", ""),
    )
    hid, tfile = str(ticket["handoff_id"]), str(ticket["handoff_file"])
    sup_note = f" (superseded {', '.join(ticket['superseded_ids'])})" if ticket.get("superseded_ids") else ""
    out_staged: dict[str, Any] = {
        "ok": True, "status": "STAGED_ONLY", "handoff_id": hid, "handoff_status": "STAGED", "ticket_status": "STAGED",
        "superseded_ids": ticket.get("superseded_ids", []), "repo_slug": repo_slug, "project_id": eff_pid,
        "project_name": eff_pname or repo_slug, "workspace_path": eff_ws, "create_new_project": create_new_proj,
        "default_branch": eff_branch, "project_provisioned": project_provisioned, "resumed": False,
        "write_mode": "appended" if ctx["append_to_existing"] else "written", "chars_written": len(body_clean),
        "execution_mode": ctx["eff_exec_mode"], "handoff_mode": ctx["eff_handoff_mode"], "workflow_ids": ctx.get("workflow_ids", []), "workflow_delta": ctx.get("workflow_delta", ""), "modular_hygiene_enforced": ctx["apply_hygiene"],
        "customization_scope_info": doc["cust_scope_info"], "active_mainchat_model": doc["main_model_info"],
        "conversation_id": "", "handoff_file": tfile,
        "assistant_guidance": f"STOP AND REPLY TO USER NOW: Handoff `{hid}`{sup_note} is staged (UNCLAIMED) for `{repo_slug}` ({title_clean}). Tell the user they can open a new or existing chat on `{repo_slug}` in Antigravity IDE and say 'Run handoff {hid}' (picked up via agy-praxis-mcp without file paths). You MUST end your response with this exact prompt: 'Do you understand the risk and would you like me to override and resume it headlessly anyway?' {REPLY_PROMPT_GUIDANCE}",
        "message": f"Research handoff staged as {hid}{sup_note} at {tfile} without headless wakeup.",
    }
    out_staged["suggested_actions"] = build_suggested_actions("ready_to_run", target=repo_slug, conv_id="", handoff_id=hid)
    if defer_retire:
        out_staged["retire_after_closeout"] = True
    if ctx.get("coerced_from_fast"):
        out_staged["coerced_from_fast"] = True
    if ctx["execution_mode_advisory"]:
        out_staged["execution_mode_advisory"] = ctx["execution_mode_advisory"]
    if ensure_warn:
        out_staged["ensure_project_warning"] = ensure_warn
    if ctx["auto_rollover_from"]:
        out_staged["auto_rollover_from"] = ctx["auto_rollover_from"]
    if ctx["size_warning"]:
        out_staged["size_warning"] = ctx["size_warning"]
    if ctx.get("handoff_advisory"):
        out_staged["handoff_advisory"] = ctx["handoff_advisory"]
    return json.dumps(out_staged, indent=2)


def _run_headless_existing_session(ctx: dict[str, Any]) -> str:
    """Wake up an existing Antigravity conversation and mark its handoff ticket IN_WORK."""
    conv_id, conv_title, body_clean = ctx["conv_id"], ctx["conv_title"], ctx["body_clean"]
    eff_ws, eff_pid, eff_pname = ctx["eff_ws"], ctx["eff_pid"], ctx["eff_pname"]
    doc, ts_now, model, effort = ctx["doc"], ctx["ts_now"], ctx["model"], ctx["effort"]
    eff_exec_mode, eff_handoff_mode = ctx["eff_exec_mode"], ctx["eff_handoff_mode"]
    allow_chained_publish, apply_hygiene, use_worktree = ctx["allow_chained_publish"], ctx["apply_hygiene"], ctx["use_worktree"]
    handoff_file, other_writers, sess_mode = ctx["handoff_file"], ctx["other_writers"], ctx["sess_mode"]

    cfg.AGY_BG_DIR.mkdir(parents=True, exist_ok=True)
    job_id = f"job-{hashlib.sha256(f'{conv_id}-{time.time()}'.encode()).hexdigest()[:8]}"
    gate_directive = "STAGE & PREVIEW ONLY (allow_chained_publish=False): Stage changes locally, run visual checks/diffs, and do NOT push to GitHub or redeploy remote production stacks in this turn. You MUST still restart the local ag-bridge-mcp service/container whenever Python/web files change so fixes take effect in memory immediately. " if not allow_chained_publish else "CHAINED PUBLISH PERMITTED (allow_chained_publish=True): Ensure all verification and audit checks pass before publishing. "
    send_prompt_body = body_clean if len(body_clean) <= 2500 else f"{body_clean[:2500]}\n\n... [Full {len(body_clean)}-char specification written to `{handoff_file}` — read that file first]"
    lifecycle_text = build_existing_session_lifecycle_text(eff_exec_mode, eff_handoff_mode, body_clean, gate_directive)
    defer_retire = bool(ctx.get("retire_after_closeout"))
    defer_note = f"\n\n> **Deferred Session Retirement (`retire_after_closeout=True`)**: Do NOT retire mid-run. Only **AFTER** `git commit` and `git push` succeed, run `record_session_retirement('{conv_id}', final_commit_sha=<HEAD_SHA>)` (or write `brain/{conv_id}/RETIRED.json` with `retired_at` and `final_commit_sha=<HEAD_SHA>`)." if defer_retire else ""
    bridge_payload = {
        "action": "send-message", "conversation_id": conv_id, "project_id": eff_pid,
        "title": ctx["title_clean"] or conv_title or "Gemini Research Handoff",
        "prompt": (
            f"{doc['stage_gate_block']}# Gemini Follow-Up Handoff ({eff_handoff_mode.upper()} Mode | Execution Mode: {eff_exec_mode})\n\n"
            f"The user provided a new follow-up request via Google Gemini (`agy-nexus-mcp`).\n\n"
            f"{doc.get('workflow_block', '')}{ctx['baton_block']}{send_prompt_body}\n\n---\n{doc['interjection_block']}\n"
            f"{lifecycle_text}{defer_note}\n\nPlease review `{handoff_file}`, update `task.md`, and execute the next phase in `{eff_exec_mode}` mode."
        ),
    }
    bridge_response = _post_bridge(bridge_payload)
    bridge_ok = bool(bridge_response.get("ok"))
    hid = str(ctx["ticket"].get("handoff_id") or "")
    if hid:
        mark_ticket_status(cfg.AGY_BG_DIR, hid, "IN_WORK" if bridge_ok else "STAGED", conversation_id=conv_id, job_id=job_id, claim_method="headless_wakeup", retire_after_closeout=defer_retire)

    job_meta: dict[str, Any] = {"job_id": job_id, "handoff_id": hid, "conversation_id": conv_id, "conversation_title": conv_title, "project_id": eff_pid, "project_name": eff_pname, "workspace_path": eff_ws, "routing_reason": ctx["routing_reason"], "started_at": ts_now, "execution_mode": eff_exec_mode, "handoff_mode": eff_handoff_mode, "workflow_ids": ctx.get("workflow_ids", []), "workflow_delta": ctx.get("workflow_delta", ""), "allow_chained_publish": allow_chained_publish, "model": model, "active_mainchat_model": doc["main_model_info"], "effort": effort, "use_worktree": use_worktree, "mode": sess_mode, "other_running_sessions": other_writers, "modular_hygiene_enforced": apply_hygiene, "customization_scope_info": doc["cust_scope_info"], "bridge_response": bridge_response}
    if defer_retire:
        job_meta["retire_after_closeout"] = True
    (cfg.AGY_BG_DIR / f"{job_id}.json").write_text(json.dumps(job_meta, indent=2) + "\n", encoding="utf-8")
    guidance = (
        f"STOP AND REPLY TO USER NOW: Handoff {hid} delivered and session resumed in background. Do NOT chain a second MCP tool after a successful response. {REPLY_PROMPT_GUIDANCE}"
        if bridge_ok else
        f"STOP AND REPLY TO USER NOW: Host bridge wakeup failed ({bridge_response.get('error', 'bridge error')}); handoff {hid} remains staged at {handoff_file} for manual pickup. {REPLY_PROMPT_GUIDANCE}"
    )
    t_stat2 = "IN_WORK" if bridge_ok else "STAGED"
    out: dict[str, Any] = {"ok": bridge_ok, "status": "RESUMED" if bridge_ok else "FAILED", "handoff_id": hid, "handoff_status": t_stat2, "ticket_status": t_stat2, "resumed": bridge_ok, "write_mode": ctx["write_mode"], "chars_written": len(body_clean), "execution_mode": eff_exec_mode, "modular_hygiene_enforced": apply_hygiene, "customization_scope_info": doc["cust_scope_info"], "active_mainchat_model": doc["main_model_info"], "job_id": job_id, "conversation_id": conv_id, "conversation_title": conv_title, "project_id": eff_pid, "project_name": eff_pname, "workspace_path": eff_ws, "routing_reason": ctx["routing_reason"], "mode": sess_mode, "other_running_sessions": other_writers, "handoff_mode": eff_handoff_mode, "workflow_ids": ctx.get("workflow_ids", []), "workflow_delta": ctx.get("workflow_delta", ""), "allow_chained_publish": allow_chained_publish, "handoff_file": str(handoff_file), "assistant_guidance": guidance, "bridge_response": bridge_response}
    out["suggested_actions"] = build_suggested_actions("in_flight" if bridge_ok else "ready_to_run", target=eff_pname or ctx.get("repo_slug", "task"), conv_id=conv_id, is_running=bridge_ok, handoff_id=hid)
    warn_multi = f"Note: {len(other_writers)} other conversation(s) targeting this workspace are currently running; consider use_worktree=True for parallel edits." if (other_writers and not use_worktree) else ""
    for k_opt, v_opt in (("retire_after_closeout", defer_retire), ("coerced_from_fast", bool(ctx.get("coerced_from_fast"))), ("execution_mode_advisory", ctx["execution_mode_advisory"]), ("concurrent_writer_warning", warn_multi), ("size_warning", ctx["size_warning"]), ("handoff_advisory", ctx.get("handoff_advisory"))):
        if v_opt:
            out[k_opt] = v_opt
    return json.dumps(out, indent=2)


def _stage_or_run_existing_session(conv_id: str, routing_reason: str, base_ctx: dict[str, Any], force_interrupt: bool, resume_headless: bool, active_ws: str) -> str:
    """Stage or headlessly resume an existing Antigravity conversation."""
    scratch_dir = cfg.AGY_BRAIN_DIR / conv_id / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    conv_title, quick_st = SESSION_STATE.get("session_title_map", {}).get(conv_id, ""), _get_selected_session_quick_status(conv_id)
    other_writers = quick_st.get("other_running_sessions", [])
    eff_handoff_mode, allow_chained_publish, defer_retire = base_ctx["eff_handoff_mode"], base_ctx["allow_chained_publish"], bool(base_ctx.get("retire_after_closeout"))
    if resume_headless and not force_interrupt:
        mutex_check = check_inflight_handoff_mutex(conv_id, cfg.AGY_BG_DIR, quick_st, max_age_seconds=300)
        if mutex_check:
            return json.dumps({"ok": False, "status": "ALREADY_RUNNING", "conversation_id": conv_id, "conversation_title": conv_title, "active_job_id": mutex_check["active_job_id"], "elapsed_seconds": mutex_check["elapsed_seconds"], "started_at": mutex_check["started_at"], "handoff_mode": eff_handoff_mode, "allow_chained_publish": allow_chained_publish, "assistant_guidance": f"STOP AND REPLY TO USER NOW: Target session is currently RUNNING with an active background job (< 300s). Call load_session_into_gemini to inspect progress, or pass force_interrupt=True to override. {REPLY_PROMPT_GUIDANCE}", "suggested_actions": build_suggested_actions("in_flight", target=base_ctx.get("repo_slug", ""), conv_id=conv_id, is_running=True), "message": mutex_check["message"]}, indent=2)

    if base_ctx.get("retire_session") and not defer_retire:
        record_session_retirement(conv_id, cfg.AGY_BRAIN_DIR)
    doc, body_clean, title_clean, repo_slug = base_ctx["doc"], base_ctx["body_clean"], base_ctx["title_clean"], base_ctx["repo_slug"]
    eff_ws, eff_pid, eff_pname = base_ctx["eff_ws"], base_ctx["eff_pid"], base_ctx["eff_pname"]
    handoff_file = scratch_dir / "gemini_research_handoff.md"
    write_mode = _write_or_append_scratch(handoff_file, doc["full_content"], body_clean, base_ctx["baton_block"], doc["interjection_block"], base_ctx["ts_now"], base_ctx["is_resume_staged"], base_ctx["append_to_existing"])
    resumed_tid = base_ctx["resumed_ticket_id"]
    ticket = {"handoff_id": resumed_tid, "status": "STAGED", "superseded_ids": []} if resumed_tid else record_handoff_ticket(cfg.AGY_BG_DIR, full_markdown=doc["full_content"], chars_written=len(body_clean), repo_slug=repo_slug, title=title_clean, project_id=eff_pid, project_name=eff_pname, workspace_path=eff_ws or active_ws, target_conversation_id=conv_id, execution_mode=base_ctx["eff_exec_mode"], handoff_mode=eff_handoff_mode, allow_chained_publish=allow_chained_publish, initial_status="STAGED", supersede_handoff_id=base_ctx["supersede_handoff_id"], append_to_existing=base_ctx["append_to_existing"], retire_after_closeout=defer_retire, workflow_ids=base_ctx.get("workflow_ids", []), workflow_delta=base_ctx.get("workflow_delta", ""))
    sess_mode, eff_conv_ws = ("WORKTREE" if base_ctx["use_worktree"] else ("MAIN WRITER" if resume_headless else str(quick_st.get("mode") or "MAIN TREE"))), (eff_ws or active_ws)
    pin_session_context(conv_id, title=conv_title, project_id=eff_pid, project_name=eff_pname, workspace=eff_conv_ws, mode=sess_mode, last_tool="send_handoff_and_resume", set_default=True)
    if not resume_headless:
        hid, sup_note = str(ticket["handoff_id"]), (f" (superseded {', '.join(ticket['superseded_ids'])})" if ticket.get("superseded_ids") else "")
        out_local: dict[str, Any] = {"ok": True, "status": "STAGED_ONLY", "handoff_id": hid, "handoff_status": "STAGED", "ticket_status": "STAGED", "superseded_ids": ticket.get("superseded_ids", []), "repo_slug": repo_slug, "resumed": False, "write_mode": write_mode, "chars_written": len(body_clean), "execution_mode": base_ctx["eff_exec_mode"], "modular_hygiene_enforced": base_ctx["apply_hygiene"], "handoff_mode": eff_handoff_mode, "workflow_ids": base_ctx.get("workflow_ids", []), "workflow_delta": base_ctx.get("workflow_delta", ""), "allow_chained_publish": allow_chained_publish, "customization_scope_info": doc["cust_scope_info"], "active_mainchat_model": doc["main_model_info"], "conversation_id": conv_id, "conversation_title": conv_title, "project_id": eff_pid, "project_name": eff_pname or repo_slug, "workspace_path": eff_conv_ws, "routing_reason": routing_reason, "mode": sess_mode, "other_running_sessions": other_writers, "handoff_file": str(handoff_file), "ticket_file": str(ticket.get("handoff_file") or ""), "assistant_guidance": f"STOP AND REPLY TO USER NOW: Handoff `{hid}`{sup_note} is staged (UNCLAIMED) for `{repo_slug}` ({title_clean}). Advise the user they can say 'Run handoff {hid}' in any new or existing Antigravity chat on `{repo_slug}`. You MUST end your response with this exact prompt: 'Do you understand the risk and would you like me to override and resume it headlessly anyway?' {REPLY_PROMPT_GUIDANCE}", "message": f"Research handoff staged as {hid}{sup_note} ({len(body_clean)} chars) without headless wakeup."}
        out_local["suggested_actions"] = build_suggested_actions("ready_to_run", target=repo_slug, conv_id=conv_id, handoff_id=hid)
        for k_opt, v_opt in (("retire_after_closeout", defer_retire), ("coerced_from_fast", bool(base_ctx.get("coerced_from_fast"))), ("execution_mode_advisory", base_ctx["execution_mode_advisory"]), ("size_warning", base_ctx["size_warning"]), ("handoff_advisory", base_ctx.get("handoff_advisory"))):
            if v_opt:
                out_local[k_opt] = v_opt
        return json.dumps(out_local, indent=2)
    return _run_headless_existing_session({**base_ctx, "conv_id": conv_id, "conv_title": conv_title, "eff_ws": eff_conv_ws, "handoff_file": handoff_file, "write_mode": write_mode, "other_writers": other_writers, "sess_mode": sess_mode, "routing_reason": routing_reason, "ticket": ticket})


def _evaluate_target_session(
    conv_id: str,
    *,
    is_close: bool,
    workspace_path: str,
    raw_caller_body: str,
    session_continuity: str,
    allow_chained_publish: bool,
    retire_session: bool,
    is_resume_staged: bool,
) -> tuple[str, str, bool, str]:
    """Check retirement and rollover posture for an existing conversation."""
    if is_session_retired(conv_id, cfg.AGY_BRAIN_DIR) and not is_close:
        return "", f"retired_session_reset_from_{conv_id[:8]}", True, conv_id
    tgt_st = _get_selected_session_quick_status(conv_id)
    tgt_ws = str(tgt_st.get("workspace_path") or workspace_path or "")
    posture_info = evaluate_rollover_posture(
        conv_id, ws_path=tgt_ws, brain_dir=cfg.AGY_BRAIN_DIR,
        step_count=int(tgt_st.get("step_count") or 0), compaction_count=int(tgt_st.get("compaction_count") or 0),
        context_exceeded=bool(tgt_st.get("context_exceeded") or check_context_exceeded(conv_id, cfg.AGY_BRAIN_DIR)),
        continuity=session_continuity, research_markdown="" if is_resume_staged else raw_caller_body,
        allow_chained_publish=allow_chained_publish, retire_session=retire_session,
    )
    if posture_info.get("should_rollover"):
        return "", f"auto_promoted_rollover_from_{conv_id[:8]} ({posture_info['posture']}, steps={posture_info['step_count']}, continuity={posture_info.get('continuity')})", True, conv_id
    return conv_id, "", False, ""


def _hydrate_resume_staged(
    *,
    explicit_hid: str, rollover_ref_cid: str, pre_slug: str, pre_ws: str,
    workspace_path: str, eff_project_arg: str, implicit_hid_repo: str,
    session_title: str, project_name: str, repo_hint: str,
    create_new_project: bool, default_branch: str, session_identifier: str,
    raw_hm: str = "feature_update", raw_exec_mode: str = "auto",
) -> dict[str, Any]:
    """Resolve staged handoff ticket content (preserving staged lifecycle modes) or brain scratch fallback."""
    staged_tk = resolve_staged_ticket_for_resume(cfg.AGY_BG_DIR, handoff_id=explicit_hid, conv_id=rollover_ref_cid, repo_slug=pre_slug if (workspace_path or eff_project_arg or implicit_hid_repo or session_title or rollover_ref_cid) else "", workspace_path=pre_ws if (workspace_path or rollover_ref_cid) else "")
    if staged_tk:
        resumed_tid, body_clean = str(staged_tk["handoff_id"]), _unwrap_staged_handoff_markdown(Path(str(staged_tk["handoff_file"])).read_text(encoding="utf-8", errors="replace"))
        ws = workspace_path or str(staged_tk.get("workspace_path") or "")
        title = session_title or str(staged_tk.get("title") or "")
        pid, pname, slug = str(staged_tk.get("project_id") or ""), str(staged_tk.get("project_name") or ""), str(staged_tk.get("repo_slug") or "")
        if not project_name and pname and pname != "general" and not staged_tk.get("target_conversation_id"):
            project_name = pname
        if not repo_hint and slug and slug != "general" and not staged_tk.get("target_conversation_id"):
            repo_hint = slug
        cnp = bool(create_new_project or staged_tk.get("create_new_project"))
        branch = default_branch or str(staged_tk.get("default_branch") or "")
        force_new = bool(not staged_tk.get("target_conversation_id") and not session_identifier)
        staged_hm = str(staged_tk.get("handoff_mode") or "").strip().lower()
        staged_em = str(staged_tk.get("execution_mode") or "").strip().lower()
        eff_hm = MODE_MAPPING.get(staged_hm, staged_hm) if (raw_hm in ("", "feature_update") and staged_hm) else MODE_MAPPING.get(raw_hm, "feature_update")
        eff_em = "fast" if (raw_exec_mode in ("", "auto") and staged_em == "fast") else (raw_exec_mode or "auto")
        return {
            "resumed_tid": resumed_tid, "body_clean": body_clean, "ws": ws, "title": title, "pid": pid,
            "project_name": project_name, "repo_hint": repo_hint, "cnp": cnp, "branch": branch,
            "force_new": force_new, "handoff_mode": eff_hm, "exec_mode": eff_em,
            "retire_after_closeout": bool(staged_tk.get("retire_after_closeout")),
            "workflow_ids": staged_tk.get("workflow_ids", []), "workflow_delta": staged_tk.get("workflow_delta", ""),
        }
    if rollover_ref_cid and (cfg.AGY_BRAIN_DIR / rollover_ref_cid / "scratch" / "gemini_research_handoff.md").is_file():
        body_clean = _unwrap_staged_handoff_markdown((cfg.AGY_BRAIN_DIR / rollover_ref_cid / "scratch" / "gemini_research_handoff.md").read_text(encoding="utf-8", errors="replace"))
        return {"resumed_tid": "", "body_clean": body_clean, "ws": workspace_path, "title": session_title, "pid": "", "project_name": project_name, "repo_hint": repo_hint, "cnp": create_new_project, "branch": default_branch, "force_new": False, "handoff_mode": MODE_MAPPING.get(raw_hm, "feature_update"), "exec_mode": raw_exec_mode, "retire_after_closeout": False, "workflow_ids": [], "workflow_delta": ""}
    return {"resumed_tid": "", "body_clean": "", "ws": workspace_path, "title": session_title, "pid": "", "project_name": project_name, "repo_hint": repo_hint, "cnp": create_new_project, "branch": default_branch, "force_new": False, "handoff_mode": MODE_MAPPING.get(raw_hm, "feature_update"), "exec_mode": raw_exec_mode, "retire_after_closeout": False, "workflow_ids": [], "workflow_delta": ""}


@mcp.tool(annotations=HANDOFF_ANNOTATIONS, output_schema=None)
def send_handoff_and_resume(
    research_markdown: str, resume_headless: bool = False, execution_mode: str = "auto", handoff_mode: str = "feature_update",
    allow_chained_publish: bool = False, force_interrupt: bool = False, model: str = "pro", effort: str = "high",
    use_worktree: bool = False, create_new_session: bool = False, create_new_project: bool = False, default_branch: str = "",
    session_identifier: str = "", session_title: str = "", project_name: str = "", repo_hint: str = "",
    workspace_path: str = "", handoff_id: str = "", supersede_handoff_id: str = "", append_to_existing: bool = False,
    enforce_modular_hygiene: bool = True, activate_skills: str = "", target_agent_role: str = "",
    customization_edit_scope: str = "none", session_continuity: str = "auto", retire_session: bool = False,
    workflow_ids: str = "", workflow_delta: str = "auto", user_terms: str = "", spoken_passphrase: str = "",
) -> str:
    """Stage/wake handoff: bind WF-XX & delta ('auto'|'unchanged'|'update_existing'|'add_new'|'bootstrap') + terms."""
    caller_gave_ws, eff_project_arg = bool((workspace_path or "").strip()), (project_name or repo_hint).strip()
    if not is_unlocked(spoken_passphrase):
        if ALLOW_LOCKED_STAGING and not resume_headless and not create_new_session and not create_new_project:
            return _compact_json(stage_quarantine_handoff(bg_dir=cfg.AGY_BG_DIR, research_markdown=research_markdown, session_title=session_title, project_name=eff_project_arg, workspace_path=workspace_path))
        return LOCKED_RESPONSE
    ts_now, apply_hygiene = datetime.now(timezone.utc).isoformat(), bool(ENFORCE_MODULAR_HYGIENE and enforce_modular_hygiene)
    raw_hm, raw_exec_mode = (handoff_mode or "feature_update").strip().lower(), (execution_mode or "auto").strip().lower()
    eff_handoff_mode = MODE_MAPPING.get(raw_hm, "feature_update")
    execution_mode_advisory = "execution_mode='plan' was explicitly requested with allow_chained_publish=True and resume_headless=True; headless runs in 'plan' mode pause after planning." if (raw_exec_mode == "plan" and allow_chained_publish and resume_headless) else ""
    raw_caller_body = (research_markdown or "").strip()
    explicit_hid = canonicalize_handoff_id(handoff_id or (raw_caller_body if raw_caller_body.upper().startswith("RESUME_STAGED:") else ""))
    is_resume_staged = bool(raw_caller_body.upper().startswith("RESUME_STAGED") or (resume_headless and not raw_caller_body))
    size_warning = f"research_markdown was {len(raw_caller_body)} chars (recommended <= 24,000 chars per call)." if (not is_resume_staged and len(raw_caller_body) > 24000) else ""
    pre_staged = resolve_staged_ticket_for_resume(cfg.AGY_BG_DIR, handoff_id=explicit_hid) if (is_resume_staged and explicit_hid) else None
    is_pure_closeout = bool((eff_handoff_mode == "release_closeout" or (pre_staged and pre_staged.get("handoff_mode") == "release_closeout")) and not create_new_project)
    is_close = bool(is_pure_closeout or retire_session or is_closeout_intent(raw_caller_body, retire_session, session_continuity) or (pre_staged and pre_staged.get("retire_after_closeout")))
    implicit_hid_repo = explicit_hid.rsplit("-", 1)[0] if (explicit_hid and not session_identifier and not workspace_path and not eff_project_arg) else ""
    resolved_conv_id, routing_reason, auto_rollover_from = "", "create_new_session", ""
    if not create_new_session and (resume_headless or session_identifier):
        resolved_conv_id, routing_reason = _resolve_target_session_for_handoff(session_identifier=session_identifier, workspace_path=workspace_path, project_name=eff_project_arg or implicit_hid_repo, session_title=session_title, activate_skills=activate_skills, research_markdown="" if is_resume_staged else raw_caller_body)
        if resolved_conv_id:
            resolved_conv_id, extra_reason, create_new_session, auto_rollover_from = _evaluate_target_session(resolved_conv_id, is_close=is_close, workspace_path=workspace_path, raw_caller_body=raw_caller_body, session_continuity=session_continuity, allow_chained_publish=allow_chained_publish, retire_session=retire_session, is_resume_staged=is_resume_staged)
            routing_reason = extra_reason or routing_reason
    conv_id, body_clean, resumed_ticket_id, tk_pid, staged_defer_retire = ("" if create_new_session else resolved_conv_id), raw_caller_body, "", "", False
    rollover_ref_cid = conv_id or auto_rollover_from or (_resolve_session_identifier(session_identifier.strip()) if (create_new_session and session_identifier.strip() and not create_new_project) else "")
    pre_ws, _, _, pre_slug = _infer_workspace_and_project(workspace_path, eff_project_arg or implicit_hid_repo, session_title, activate_skills, "" if is_resume_staged else raw_caller_body, rollover_ref_cid)
    caller_cnp = bool(create_new_project)
    if is_resume_staged:
        hyd = _hydrate_resume_staged(explicit_hid=explicit_hid, rollover_ref_cid=rollover_ref_cid, pre_slug=pre_slug, pre_ws=pre_ws, workspace_path=workspace_path, eff_project_arg=eff_project_arg, implicit_hid_repo=implicit_hid_repo, session_title=session_title, project_name=project_name, repo_hint=repo_hint, create_new_project=create_new_project, default_branch=default_branch, session_identifier=session_identifier, raw_hm=raw_hm, raw_exec_mode=raw_exec_mode)
        if not hyd["body_clean"]:
            return json.dumps({"ok": False, "status": "NO_STAGED_HANDOFF_FOR_REPO", "error": f"No matching STAGED handoff found for '{explicit_hid or pre_slug}'. Pass handoff_id='<repo>-01' or provide research_markdown."}, indent=2)
        resumed_ticket_id, body_clean, workspace_path, session_title, tk_pid, project_name, repo_hint, create_new_project, default_branch, eff_handoff_mode, raw_exec_mode, staged_defer_retire = hyd["resumed_tid"], hyd["body_clean"], hyd["ws"], hyd["title"], hyd["pid"], hyd["project_name"], hyd["repo_hint"], hyd["cnp"], hyd["branch"], hyd["handoff_mode"], hyd["exec_mode"], bool(hyd.get("retire_after_closeout"))
        workflow_ids = workflow_ids or ",".join(hyd.get("workflow_ids") or [])
        workflow_delta = workflow_delta if workflow_delta != "auto" else (hyd.get("workflow_delta") or "auto")
        is_pure_closeout, is_close = bool((eff_handoff_mode == "release_closeout") and not create_new_project), bool(is_close or eff_handoff_mode == "release_closeout" or staged_defer_retire)
        if hyd["force_new"]:
            create_new_session, conv_id = True, ""
    eff_exec_mode, coerced_from_fast, coerced_reason = resolve_execution_mode_with_reason(raw_exec_mode, eff_handoff_mode, body_clean, allow_chained_publish, resume_headless)
    if coerced_reason:
        execution_mode_advisory = f"{execution_mode_advisory} {coerced_reason}".strip()
    tgt = resolve_handoff_target(workspace_path=workspace_path, project_name=project_name, repo_hint=repo_hint, session_title=session_title, activate_skills=activate_skills, body_clean=body_clean, conv_id=rollover_ref_cid, create_new_project=create_new_project, default_branch=default_branch, resume_headless=resume_headless, customization_edit_scope=customization_edit_scope, explicit_caller_ws=caller_gave_ws)
    if tgt["guard_error"]:
        return json.dumps(tgt["guard_error"], indent=2)
    eff_ws, eff_pid, eff_pname, repo_slug, eff_branch = tgt["eff_ws"], (tgt["eff_pid"] or tk_pid), tgt["eff_pname"], tgt["repo_slug"], tgt["default_branch"]
    if tgt["force_new_session"]:
        create_new_session, conv_id = True, ""
    active_ws, edit_scope_clean, pre_iso_cid = (eff_ws or ("" if tgt["has_target_spec"] else (SESSION_STATE.get("selected_workspace") or str(get_antigravity_config_repo())))), (customization_edit_scope or "none").strip().lower(), conv_id
    conv_id, create_new_session, create_new_project, routing_reason, eff_ws, active_ws, eff_pid, eff_pname, repo_slug = apply_global_scope_isolation(edit_scope_clean=edit_scope_clean, active_ws=active_ws, conv_id=conv_id, create_new_session=create_new_session, create_new_project=create_new_project, routing_reason=routing_reason, eff_ws=eff_ws, eff_pid=eff_pid, eff_pname=eff_pname, repo_slug=repo_slug, session_title=session_title, activate_skills=activate_skills, body_clean=body_clean)
    closeout_escalated = bool(resumed_ticket_id and not is_pure_closeout and (caller_cnp or (pre_staged and pre_staged.get("handoff_mode") == "release_closeout")))
    wf_gate = validate_handoff_workflow_gates(raw_body=body_clean, workspace_path=active_ws, eff_handoff_mode=eff_handoff_mode, create_new_project=create_new_project, workflow_ids=workflow_ids, workflow_delta=workflow_delta, user_terms=user_terms, is_pure_closeout=is_pure_closeout, is_resume_staged=bool(resumed_ticket_id), conv_id=conv_id, project_name=eff_pname or repo_slug, strict_workflow_gate=closeout_escalated)
    if wf_gate["guard_error"]:
        return json.dumps(wf_gate["guard_error"], indent=2)
    handoff_advisory = wf_gate["quality"].get("advisory", "")
    if conv_id and conv_id != pre_iso_cid and not create_new_session:
        conv_id, extra_iso, create_new_session, auto_rollover_from = _evaluate_target_session(conv_id, is_close=is_close, workspace_path=eff_ws, raw_caller_body=raw_caller_body, session_continuity=session_continuity, allow_chained_publish=allow_chained_publish, retire_session=retire_session, is_resume_staged=is_resume_staged)
        routing_reason = extra_iso or routing_reason
    baton_block = ""
    if create_new_session and rollover_ref_cid and not create_new_project and edit_scope_clean != "global":
        baton_block = extract_prior_session_baton(rollover_ref_cid, cfg.AGY_BRAIN_DIR, ws_path=active_ws)
    elif conv_id:
        tgt_st2 = _get_selected_session_quick_status(conv_id)
        if int(tgt_st2.get("step_count") or 0) >= 350 or bool(tgt_st2.get("context_exceeded") or check_context_exceeded(conv_id, cfg.AGY_BRAIN_DIR)):
            baton_block = extract_prior_session_baton(conv_id, cfg.AGY_BRAIN_DIR, ws_path=active_ws)
    retire_after_closeout = bool(staged_defer_retire or (retire_session and resume_headless and is_close))
    title_clean = session_title.strip() or _extract_markdown_heading(body_clean) or "Gemini Research Handoff"
    doc = _compose_handoff_document(ts_now=ts_now, eff_exec_mode=eff_exec_mode, eff_handoff_mode=eff_handoff_mode, allow_chained_publish=allow_chained_publish, model=model, effort=effort, apply_hygiene=apply_hygiene, body_clean=body_clean, baton_block=baton_block, activate_skills=activate_skills, target_agent_role=target_agent_role, edit_scope_clean=edit_scope_clean, active_ws=active_ws, retire_session=retire_session, is_closeout=is_close, conv_id=conv_id, retire_after_closeout=retire_after_closeout, workflow_block=wf_gate["workflow_block"])
    base_ctx = {"title_clean": title_clean, "body_clean": body_clean, "eff_ws": eff_ws, "eff_pid": eff_pid, "eff_pname": eff_pname, "repo_slug": repo_slug, "target_exists": tgt["target_exists"], "create_new_project": create_new_project, "default_branch": eff_branch, "doc": doc, "ts_now": ts_now, "model": model, "effort": effort, "eff_exec_mode": eff_exec_mode, "eff_handoff_mode": eff_handoff_mode, "workflow_ids": wf_gate["workflow_ids"], "workflow_delta": wf_gate["eff_delta"], "allow_chained_publish": allow_chained_publish, "apply_hygiene": apply_hygiene, "use_worktree": use_worktree, "baton_block": baton_block, "resumed_ticket_id": resumed_ticket_id, "auto_rollover_from": auto_rollover_from, "supersede_handoff_id": supersede_handoff_id, "append_to_existing": append_to_existing, "is_resume_staged": is_resume_staged, "execution_mode_advisory": execution_mode_advisory, "size_warning": size_warning, "handoff_advisory": handoff_advisory, "retire_session": retire_session, "retire_after_closeout": retire_after_closeout, "coerced_from_fast": coerced_from_fast}
    if not conv_id:
        return _run_headless_new_session(base_ctx) if resume_headless else _stage_new_chat_handoff(base_ctx)
    return _stage_or_run_existing_session(conv_id, routing_reason, base_ctx, force_interrupt, resume_headless, active_ws)
