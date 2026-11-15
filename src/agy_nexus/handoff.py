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
    HANDOFF_ANNOTATIONS, LOCKED_RESPONSE, SESSION_STATE, _compact_json,
    get_antigravity_config_repo, is_unlocked, mcp, pin_session_context,
)
from agy_nexus.handoff_queue import (
    canonicalize_handoff_id, mark_ticket_status,
    record_handoff_ticket, resolve_staged_ticket_for_resume,
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
    build_suggested_actions,
    get_closeout_directives,
    is_closeout_intent,
    is_session_retired,
    record_session_retirement,
)
from agy_nexus.session_status import (
    _get_selected_session_quick_status, check_context_exceeded,
    check_inflight_handoff_mutex, evaluate_rollover_posture,
    extract_prior_session_baton,
)
from agy_nexus.target_resolver import (
    _USER_BODY_END,
    _USER_BODY_START,
    apply_global_scope_isolation,
    extract_markdown_heading as _extract_markdown_heading,
    infer_workspace_and_project as _infer_workspace_and_project,
    post_host_bridge as _post_bridge,
    resolve_handoff_target,
    unwrap_staged_handoff_markdown as _unwrap_staged_handoff_markdown,
)
from agy_nexus.telemetry_scanner import get_active_mainchat_model
from agy_nexus.workflows import stage_quarantine_handoff


def _compose_handoff_document(
    *,
    ts_now: str,
    eff_exec_mode: str,
    eff_handoff_mode: str,
    allow_chained_publish: bool,
    model: str,
    effort: str,
    apply_hygiene: bool,
    body_clean: str,
    baton_block: str,
    activate_skills: str,
    target_agent_role: str,
    edit_scope_clean: str,
    active_ws: str,
    retire_session: bool = False,
    is_closeout: bool = False,
) -> dict[str, Any]:
    """Assemble full wrapped handoff markdown plus reusable prompt blocks."""
    interjection_block, cust_scope_info = build_interjection_directive(
        activate_skills=activate_skills, target_agent_role=target_agent_role,
        customization_edit_scope=edit_scope_clean, research_markdown=body_clean,
        workspace_str=active_ws, config_dir=AGY_CONFIG_DIR, data_dir=AGY_DATA_DIR, gitlab_dir=AGY_GITLAB_DIR,
    )
    main_model_info = get_active_mainchat_model(AGY_DATA_DIR)
    header = (
        f"<!-- Handshake Gemini Research Handoff -->\n"
        f"<!-- Generated: {ts_now} -->\n"
        f"<!-- Execution Mode: {eff_exec_mode} | Handoff Mode: {eff_handoff_mode} | Chained Publish: {allow_chained_publish} | Model: {model} | MainChat: {main_model_info.get('model_label', 'Gemini 4 Carbon')} | Effort: {effort} | Modular Hygiene: {apply_hygiene} -->\n\n"
    )
    stage_gate_block = (
        "> [!IMPORTANT]\n> **STAGE & PREVIEW ONLY (`allow_chained_publish=False`)**: Do NOT run `git push`, `publish_to_github.py`, or remote production stack redeployments in this turn.\n"
        "> Stage all changes locally, capture verification screenshots and diffs, and halt execution so Gemini and the user can inspect via `inspect_git_diff` / `/web/media/` links. **You MUST still restart the local `ag-bridge-mcp` service/container** whenever Python/web files change so fixes take effect in memory immediately.\n\n"
        if not allow_chained_publish else ""
    )
    closeout_block = get_closeout_directives(active_ws) if (retire_session or is_closeout) else ""
    subagent_footer = (
        "\n---\n\n"
        "## Mandatory 4-Step Execution Lifecycle & Verification Gate (Carbon 4 Main-Chat + Subagent Hybrid)\n\n"
        "1. **Scout (`agy-praxis-mcp` / Serena LSP / `flash-scout`)**: Read all attached `SKILL.md` contracts first. Call `agy-praxis-mcp` (`polyglot_map`, `polyglot_search`, `polyglot_outline`) or Serena's symbolic LSP tools first to locate exact `Lstart-Lend` spans; for multi-file discovery, dispatch `flash-scout` (`model='flash'`).\n"
        "2. **Implement (Main-Chat `Gemini 4 Carbon` / `argon-surgeon` / `flash-surgeon`)**: Execute 1–2 file surgical symbolic edits or complex state-machine logic directly in Main Chat (on **Gemini 4 Carbon**) or via `argon-surgeon` (`model='pro'`); fan out 3+ file or mechanical refactors (`<= 500 lines/file`, hard ceiling 650 lines, functions `<= 100` lines) to `flash-surgeon` (`model='flash'`).\n"
        "3. **Audit (`flash-auditor` & Intra-Google Dual-Review)**: Invoke `flash-auditor` (`model='flash'`) to run syntax/unit/smoke checks and verify `git diff` (or pit `argon-sentinel` `model='pro'` against Main-Chat **Gemini 4 Carbon** for architectural/security review) before marking `task.md` complete (Rule 8.1: the agent that wrote code never signs it off alone).\n"
        "4. **Visual & Preview Gate**: If any `.html`, `.css`, or frontend `.js` files were modified, run `~/.gemini/config/skills/visual-architecture-system/scripts/verify_visual_contract.py` against the local page and save desktop + mobile screenshots to the session artifact directory. When `allow_chained_publish=False`, halt at local staging + preview without pushing or redeploying (restarting the local `ag-bridge-mcp` service/container whenever Python/web files change so fixes take effect in memory immediately).\n"
    )
    hygiene_suffix = f"\n{MODULAR_HYGIENE_MARKDOWN_BLOCK.strip()}\n" if (apply_hygiene and "Mandatory Modular Architecture" not in body_clean) else ""
    wrapped_user_body = f"{_USER_BODY_START}\n{body_clean}\n{_USER_BODY_END}"
    full_content = header + stage_gate_block + baton_block + closeout_block + wrapped_user_body + interjection_block + hygiene_suffix + subagent_footer + "\n"
    return {
        "full_content": full_content,
        "stage_gate_block": stage_gate_block,
        "interjection_block": interjection_block,
        "closeout_block": closeout_block,
        "hygiene_suffix": hygiene_suffix,
        "subagent_footer": subagent_footer,
        "cust_scope_info": cust_scope_info,
        "main_model_info": main_model_info,
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
    spawn_prompt = f"# {title_clean}\n\nThe user initiated this project from Google Gemini via `agy-nexus-mcp` (Handoff Mode: {eff_handoff_mode}, Execution Mode: {eff_exec_mode}).\n\n{doc['stage_gate_block']}{ctx['baton_block']}{prompt_body}{doc['interjection_block']}{doc['hygiene_suffix']}{doc['subagent_footer']}\n\nPlease review session brain `scratch/gemini_research_handoff.md` and modular hygiene requirements above, create `task.md`, and execute in `{eff_exec_mode}` mode."
    bridge_response = _post_bridge({"action": "new-conversation", "model": model if model in ("flash_lite", "flash", "pro") else "pro", "title": title_clean, "prompt": spawn_prompt, "project_id": eff_pid, "project_name": eff_pname, "workspace_path": eff_ws, "create_new_project": create_new_proj, "default_branch": eff_branch})
    new_conv_id = str(bridge_response.get("conversation_id") or "").strip()
    pinned_ws = str(bridge_response.get("workspace_path") or eff_ws)
    pinned_pid = str(bridge_response.get("project_id") or eff_pid)
    pinned_pname = str(bridge_response.get("project_name") or eff_pname)
    bridge_ok = bool(bridge_response.get("ok"))
    job_id = f"job-{hashlib.sha256(f'{new_conv_id or title_clean}-{time.time()}'.encode()).hexdigest()[:8]}"

    resumed_tid = ctx.get("resumed_ticket_id") or ""
    if resumed_tid:
        ticket = mark_ticket_status(cfg.AGY_BG_DIR, resumed_tid, "IN_WORK" if bridge_ok else "STAGED", conversation_id=new_conv_id, job_id=job_id, claim_method="headless_wakeup") or {}
    else:
        ticket = record_handoff_ticket(
            cfg.AGY_BG_DIR, full_markdown=doc["full_content"], chars_written=len(body_clean), repo_slug=repo_slug,
            title=title_clean, project_id=pinned_pid, project_name=pinned_pname,
            workspace_path=pinned_ws, target_conversation_id=new_conv_id, rollover_from=ctx["auto_rollover_from"],
            execution_mode=eff_exec_mode, handoff_mode=eff_handoff_mode, allow_chained_publish=allow_chained_publish,
            initial_status="IN_WORK" if bridge_ok else "STAGED", claimed_by_conversation_id=new_conv_id if bridge_ok else "",
            job_id=job_id, supersede_handoff_id=ctx["supersede_handoff_id"], append_to_existing=ctx["append_to_existing"],
            create_new_project=create_new_proj, default_branch=eff_branch,
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
    job_meta: dict[str, Any] = {"job_id": job_id, "handoff_id": hid, "conversation_id": new_conv_id, "project_id": pinned_pid, "project_name": pinned_pname, "workspace_path": pinned_ws, "create_new_project": create_new_proj, "default_branch": eff_branch, "started_at": ts_now, "execution_mode": eff_exec_mode, "handoff_mode": eff_handoff_mode, "allow_chained_publish": allow_chained_publish, "model": model, "active_mainchat_model": doc["main_model_info"], "effort": effort, "created_new_session": bool(new_conv_id and bridge_ok), "modular_hygiene_enforced": apply_hygiene, "customization_scope_info": doc["cust_scope_info"], "bridge_response": bridge_response}
    if ctx["auto_rollover_from"]:
        job_meta["auto_rollover_from"] = ctx["auto_rollover_from"]
    (cfg.AGY_BG_DIR / f"{job_id}.json").write_text(json.dumps(job_meta, indent=2) + "\n", encoding="utf-8")
    guidance = (
        f"STOP AND REPLY TO USER NOW: Handoff {hid} delivered and session resumed in background. Do NOT chain a second MCP tool after a successful response."
        if bridge_ok else
        f"STOP AND REPLY TO USER NOW: Host bridge failed to spawn headless session ({bridge_response.get('error', 'bridge error')}); handoff {hid} remains staged at {handoff_file} (say 'Run handoff {hid}' in Antigravity IDE)."
    )
    t_stat = str(ticket.get("status", "IN_WORK"))
    out: dict[str, Any] = {"ok": bridge_ok, "status": "RESUMED" if bridge_ok else "FAILED", "handoff_id": hid, "handoff_status": t_stat, "ticket_status": t_stat, "created_new_session": bool(new_conv_id and bridge_ok), "create_new_project": create_new_proj, "default_branch": eff_branch, "resumed": bridge_ok, "write_mode": write_mode, "chars_written": len(body_clean), "execution_mode": eff_exec_mode, "modular_hygiene_enforced": apply_hygiene, "customization_scope_info": doc["cust_scope_info"], "active_mainchat_model": doc["main_model_info"], "job_id": job_id, "conversation_id": new_conv_id, "handoff_mode": eff_handoff_mode, "allow_chained_publish": allow_chained_publish, "workspace_path": pinned_ws, "project_id": pinned_pid, "project_name": pinned_pname, "handoff_file": str(handoff_file), "assistant_guidance": guidance, "bridge_response": bridge_response}
    out["suggested_actions"] = build_suggested_actions("in_flight", target=repo_slug, conv_id=new_conv_id, is_running=bridge_ok)
    if ctx["execution_mode_advisory"]:
        out["execution_mode_advisory"] = ctx["execution_mode_advisory"]
    if ctx["auto_rollover_from"]:
        out["auto_rollover_from"], out["auto_promoted_rollover"] = ctx["auto_rollover_from"], True
    if ctx["size_warning"]:
        out["size_warning"] = ctx["size_warning"]
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
    ticket = record_handoff_ticket(
        cfg.AGY_BG_DIR, full_markdown=doc["full_content"], chars_written=len(body_clean), repo_slug=repo_slug,
        title=title_clean, project_id=eff_pid, project_name=eff_pname, workspace_path=eff_ws,
        target_conversation_id="", rollover_from=ctx["auto_rollover_from"], execution_mode=ctx["eff_exec_mode"],
        handoff_mode=ctx["eff_handoff_mode"], allow_chained_publish=ctx["allow_chained_publish"],
        initial_status="STAGED", supersede_handoff_id=ctx["supersede_handoff_id"],
        append_to_existing=ctx["append_to_existing"], create_new_project=create_new_proj, default_branch=eff_branch,
    )
    hid, tfile = str(ticket["handoff_id"]), str(ticket["handoff_file"])
    sup_note = f" (superseded {', '.join(ticket['superseded_ids'])})" if ticket.get("superseded_ids") else ""
    out_staged: dict[str, Any] = {
        "ok": True, "status": "STAGED_ONLY", "handoff_id": hid, "handoff_status": "STAGED", "ticket_status": "STAGED",
        "superseded_ids": ticket.get("superseded_ids", []), "repo_slug": repo_slug, "project_id": eff_pid,
        "project_name": eff_pname or repo_slug, "workspace_path": eff_ws, "create_new_project": create_new_proj,
        "default_branch": eff_branch, "project_provisioned": project_provisioned, "resumed": False,
        "write_mode": "appended" if ctx["append_to_existing"] else "written", "chars_written": len(body_clean),
        "execution_mode": ctx["eff_exec_mode"], "modular_hygiene_enforced": ctx["apply_hygiene"],
        "customization_scope_info": doc["cust_scope_info"], "active_mainchat_model": doc["main_model_info"],
        "conversation_id": "", "handoff_file": tfile,
        "assistant_guidance": f"STOP AND REPLY TO USER NOW: Handoff `{hid}`{sup_note} is staged (UNCLAIMED) for `{repo_slug}` ({title_clean}). Tell the user they can open a new or existing chat on `{repo_slug}` in Antigravity IDE and say 'Run handoff {hid}' (picked up via agy-praxis-mcp without file paths). You MUST end your response with this exact prompt: 'Do you understand the risk and would you like me to override and resume it headlessly anyway?'",
        "message": f"Research handoff staged as {hid}{sup_note} at {tfile} without headless wakeup.",
    }
    out_staged["suggested_actions"] = build_suggested_actions("ready_to_run", target=repo_slug, conv_id="")
    if ensure_warn:
        out_staged["ensure_project_warning"] = ensure_warn
    if ctx["auto_rollover_from"]:
        out_staged["auto_rollover_from"] = ctx["auto_rollover_from"]
    if ctx["size_warning"]:
        out_staged["size_warning"] = ctx["size_warning"]
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
    bridge_payload = {
        "action": "send-message", "conversation_id": conv_id, "project_id": eff_pid,
        "title": ctx["title_clean"] or conv_title or "Gemini Research Handoff",
        "prompt": (
            f"{doc['stage_gate_block']}# Gemini Follow-Up Handoff ({eff_handoff_mode.upper()} Mode | Execution Mode: {eff_exec_mode})\n\n"
            f"The user provided a new follow-up request via Google Gemini (`agy-nexus-mcp`).\n\n"
            f"{ctx['baton_block']}{send_prompt_body}\n\n---\n{doc['interjection_block']}\n"
            "Follow the 4-Step Execution Lifecycle (Carbon 4 Main-Chat + Subagent Hybrid):\n"
            "1. Scout: Read attached SKILL.md contracts; use agy-praxis-mcp (polyglot_map, polyglot_search, polyglot_outline) or Serena LSP tools directly for 1-2 files, or flash-scout (model='flash') for multi-file discovery.\n"
            "2. Implement: Execute 1-2 file surgical symbolic edits (replace_symbol_body) or complex logic directly in Main Chat (Gemini 4 Carbon) or via argon-surgeon (model='pro'); fan out 3+ file / mechanical refactors (<= 500 lines/file, ceiling 650L, functions <= 100L) to flash-surgeon (model='flash').\n"
            "3. Audit: Invoke flash-auditor (model='flash') or Intra-Google Dual-Review (argon-sentinel model='pro' vs Carbon 4) to verify git diff and run unit/smoke tests before marking task.md complete (Rule 8.1: no solo signoff).\n"
            f"4. Gate: {gate_directive}\n\nPlease review `{handoff_file}`, update `task.md`, and execute the next phase in `{eff_exec_mode}` mode."
        ),
    }
    bridge_response = _post_bridge(bridge_payload)
    bridge_ok = bool(bridge_response.get("ok"))
    hid = str(ctx["ticket"].get("handoff_id") or "")
    if hid:
        mark_ticket_status(cfg.AGY_BG_DIR, hid, "IN_WORK" if bridge_ok else "STAGED", conversation_id=conv_id, job_id=job_id, claim_method="headless_wakeup")

    job_meta = {"job_id": job_id, "handoff_id": hid, "conversation_id": conv_id, "conversation_title": conv_title, "project_id": eff_pid, "project_name": eff_pname, "workspace_path": eff_ws, "routing_reason": ctx["routing_reason"], "started_at": ts_now, "execution_mode": eff_exec_mode, "handoff_mode": eff_handoff_mode, "allow_chained_publish": allow_chained_publish, "model": model, "active_mainchat_model": doc["main_model_info"], "effort": effort, "use_worktree": use_worktree, "mode": sess_mode, "other_running_sessions": other_writers, "modular_hygiene_enforced": apply_hygiene, "customization_scope_info": doc["cust_scope_info"], "bridge_response": bridge_response}
    (cfg.AGY_BG_DIR / f"{job_id}.json").write_text(json.dumps(job_meta, indent=2) + "\n", encoding="utf-8")
    guidance = (
        f"STOP AND REPLY TO USER NOW: Handoff {hid} delivered and session resumed in background. Do NOT chain a second MCP tool after a successful response."
        if bridge_ok else
        f"STOP AND REPLY TO USER NOW: Host bridge wakeup failed ({bridge_response.get('error', 'bridge error')}); handoff {hid} remains staged at {handoff_file} for manual pickup."
    )
    t_stat2 = "IN_WORK" if bridge_ok else "STAGED"
    out: dict[str, Any] = {"ok": bridge_ok, "status": "RESUMED" if bridge_ok else "FAILED", "handoff_id": hid, "handoff_status": t_stat2, "ticket_status": t_stat2, "resumed": bridge_ok, "write_mode": ctx["write_mode"], "chars_written": len(body_clean), "execution_mode": eff_exec_mode, "modular_hygiene_enforced": apply_hygiene, "customization_scope_info": doc["cust_scope_info"], "active_mainchat_model": doc["main_model_info"], "job_id": job_id, "conversation_id": conv_id, "conversation_title": conv_title, "project_id": eff_pid, "project_name": eff_pname, "workspace_path": eff_ws, "routing_reason": ctx["routing_reason"], "mode": sess_mode, "other_running_sessions": other_writers, "handoff_mode": eff_handoff_mode, "allow_chained_publish": allow_chained_publish, "handoff_file": str(handoff_file), "assistant_guidance": guidance, "bridge_response": bridge_response}
    out["suggested_actions"] = build_suggested_actions("in_flight", target=eff_pname or ctx.get("repo_slug", "task"), conv_id=conv_id, is_running=bridge_ok)
    if ctx["execution_mode_advisory"]:
        out["execution_mode_advisory"] = ctx["execution_mode_advisory"]
    if other_writers and not use_worktree:
        out["concurrent_writer_warning"] = f"Note: {len(other_writers)} other conversation(s) targeting this workspace are currently running; consider use_worktree=True for parallel edits."
    if ctx["size_warning"]:
        out["size_warning"] = ctx["size_warning"]
    return json.dumps(out, indent=2)


def _stage_or_run_existing_session(conv_id: str, routing_reason: str, base_ctx: dict[str, Any], force_interrupt: bool, resume_headless: bool, active_ws: str) -> str:
    """Stage or headlessly resume an existing Antigravity conversation."""
    scratch_dir = cfg.AGY_BRAIN_DIR / conv_id / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    conv_title, quick_st = SESSION_STATE.get("session_title_map", {}).get(conv_id, ""), _get_selected_session_quick_status(conv_id)
    other_writers = quick_st.get("other_running_sessions", [])
    eff_handoff_mode, allow_chained_publish = base_ctx["eff_handoff_mode"], base_ctx["allow_chained_publish"]
    if resume_headless and not force_interrupt:
        mutex_check = check_inflight_handoff_mutex(conv_id, cfg.AGY_BG_DIR, quick_st, max_age_seconds=300)
        if mutex_check:
            return json.dumps({"ok": False, "status": "ALREADY_RUNNING", "conversation_id": conv_id, "conversation_title": conv_title, "active_job_id": mutex_check["active_job_id"], "elapsed_seconds": mutex_check["elapsed_seconds"], "started_at": mutex_check["started_at"], "handoff_mode": eff_handoff_mode, "allow_chained_publish": allow_chained_publish, "assistant_guidance": "STOP AND REPLY TO USER NOW: Target session is currently RUNNING with an active background job (< 300s). Call load_session_into_gemini to inspect progress, or pass force_interrupt=True to override.", "message": mutex_check["message"]}, indent=2)

    doc, body_clean, title_clean, repo_slug = base_ctx["doc"], base_ctx["body_clean"], base_ctx["title_clean"], base_ctx["repo_slug"]
    eff_ws, eff_pid, eff_pname = base_ctx["eff_ws"], base_ctx["eff_pid"], base_ctx["eff_pname"]
    handoff_file = scratch_dir / "gemini_research_handoff.md"
    write_mode = _write_or_append_scratch(handoff_file, doc["full_content"], body_clean, base_ctx["baton_block"], doc["interjection_block"], base_ctx["ts_now"], base_ctx["is_resume_staged"], base_ctx["append_to_existing"])
    resumed_tid = base_ctx["resumed_ticket_id"]
    ticket = {"handoff_id": resumed_tid, "status": "STAGED", "superseded_ids": []} if resumed_tid else record_handoff_ticket(cfg.AGY_BG_DIR, full_markdown=doc["full_content"], chars_written=len(body_clean), repo_slug=repo_slug, title=title_clean, project_id=eff_pid, project_name=eff_pname, workspace_path=eff_ws or active_ws, target_conversation_id=conv_id, execution_mode=base_ctx["eff_exec_mode"], handoff_mode=eff_handoff_mode, allow_chained_publish=allow_chained_publish, initial_status="STAGED", supersede_handoff_id=base_ctx["supersede_handoff_id"], append_to_existing=base_ctx["append_to_existing"])
    sess_mode, eff_conv_ws = ("WORKTREE" if base_ctx["use_worktree"] else ("MAIN WRITER" if resume_headless else str(quick_st.get("mode") or "MAIN TREE"))), (eff_ws or active_ws)
    pin_session_context(conv_id, title=conv_title, project_id=eff_pid, project_name=eff_pname, workspace=eff_conv_ws, mode=sess_mode, last_tool="send_handoff_and_resume", set_default=True)
    if base_ctx.get("retire_session"):
        record_session_retirement(conv_id, cfg.AGY_BRAIN_DIR)
    if not resume_headless:
        hid, sup_note = str(ticket["handoff_id"]), (f" (superseded {', '.join(ticket['superseded_ids'])})" if ticket.get("superseded_ids") else "")
        out_local: dict[str, Any] = {"ok": True, "status": "STAGED_ONLY", "handoff_id": hid, "handoff_status": "STAGED", "ticket_status": "STAGED", "superseded_ids": ticket.get("superseded_ids", []), "repo_slug": repo_slug, "resumed": False, "write_mode": write_mode, "chars_written": len(body_clean), "execution_mode": base_ctx["eff_exec_mode"], "modular_hygiene_enforced": base_ctx["apply_hygiene"], "handoff_mode": eff_handoff_mode, "allow_chained_publish": allow_chained_publish, "customization_scope_info": doc["cust_scope_info"], "active_mainchat_model": doc["main_model_info"], "conversation_id": conv_id, "conversation_title": conv_title, "project_id": eff_pid, "project_name": eff_pname or repo_slug, "workspace_path": eff_conv_ws, "routing_reason": routing_reason, "mode": sess_mode, "other_running_sessions": other_writers, "handoff_file": str(handoff_file), "ticket_file": str(ticket.get("handoff_file") or ""), "assistant_guidance": f"STOP AND REPLY TO USER NOW: Handoff `{hid}`{sup_note} is staged (UNCLAIMED) for `{repo_slug}` ({title_clean}). Advise the user they can say 'Run handoff {hid}' in any new or existing Antigravity chat on `{repo_slug}`. You MUST end your response with this exact prompt: 'Do you understand the risk and would you like me to override and resume it headlessly anyway?'", "message": f"Research handoff staged as {hid}{sup_note} ({len(body_clean)} chars) without headless wakeup."}
        out_local["suggested_actions"] = build_suggested_actions("ready_to_run", target=repo_slug, conv_id=conv_id)
        if base_ctx["size_warning"]:
            out_local["size_warning"] = base_ctx["size_warning"]
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
) -> tuple[str, str, str, str, str, str, str, bool, str, bool]:
    """Resolve staged handoff ticket content or brain scratch fallback."""
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
        return resumed_tid, body_clean, ws, title, pid, project_name, repo_hint, cnp, branch, force_new
    if rollover_ref_cid and (cfg.AGY_BRAIN_DIR / rollover_ref_cid / "scratch" / "gemini_research_handoff.md").is_file():
        body_clean = _unwrap_staged_handoff_markdown((cfg.AGY_BRAIN_DIR / rollover_ref_cid / "scratch" / "gemini_research_handoff.md").read_text(encoding="utf-8", errors="replace"))
        return "", body_clean, workspace_path, session_title, "", project_name, repo_hint, create_new_project, default_branch, False
    return "", "", workspace_path, session_title, "", project_name, repo_hint, create_new_project, default_branch, False


@mcp.tool(annotations=HANDOFF_ANNOTATIONS, output_schema=None)
def send_handoff_and_resume(
    research_markdown: str, resume_headless: bool = False, execution_mode: str = "auto", handoff_mode: str = "intent",
    allow_chained_publish: bool = False, force_interrupt: bool = False, model: str = "pro", effort: str = "high",
    use_worktree: bool = False, create_new_session: bool = False, create_new_project: bool = False, default_branch: str = "",
    session_identifier: str = "", session_title: str = "", project_name: str = "", repo_hint: str = "",
    workspace_path: str = "", handoff_id: str = "", supersede_handoff_id: str = "", append_to_existing: bool = False,
    enforce_modular_hygiene: bool = True, activate_skills: str = "", target_agent_role: str = "",
    customization_edit_scope: str = "none", session_continuity: str = "auto", retire_session: bool = False,
    spoken_passphrase: str = "",
) -> str:
    """Stage a repo-prefixed Gemini handoff ticket (`<repo-slug>-01`, ...) or wake up Antigravity headlessly.

    - Default Write-Only Staging (`resume_headless=False`): Mints an unclaimed `<repo-slug>-NN` ticket in `STAGED` state.
    - Zero-Reupload Override (`RESUME_STAGED`): Promotes staged ticket to `IN_WORK` and wakes up Antigravity.
    - Greenfield Guardrail (`create_new_project=True`): Non-existent targets fail closed with `PROJECT_NOT_FOUND` unless explicitly set.
    - In-Place Closeout & Retirement (`retire_session=True` / `session_continuity="closeout"`): Runs in-place; writes RETIRED.json.
    """
    caller_gave_ws, eff_project_arg = bool((workspace_path or "").strip()), (project_name or repo_hint).strip()
    if not is_unlocked(spoken_passphrase):
        if ALLOW_LOCKED_STAGING and not resume_headless and not create_new_session and not create_new_project:
            return _compact_json(stage_quarantine_handoff(bg_dir=cfg.AGY_BG_DIR, research_markdown=research_markdown, session_title=session_title, project_name=eff_project_arg, workspace_path=workspace_path))
        return LOCKED_RESPONSE

    ts_now, apply_hygiene = datetime.now(timezone.utc).isoformat(), bool(ENFORCE_MODULAR_HYGIENE and enforce_modular_hygiene)
    eff_handoff_mode = (handoff_mode or "intent").strip().lower()
    eff_handoff_mode = eff_handoff_mode if eff_handoff_mode in ("intent", "visual_critique", "surgical_audit") else "intent"
    raw_exec_mode = (execution_mode or "auto").strip().lower()
    eff_exec_mode = ("fast" if (allow_chained_publish and resume_headless) else "plan") if raw_exec_mode not in ("fast", "plan") else raw_exec_mode
    execution_mode_advisory = "execution_mode='plan' was explicitly requested with allow_chained_publish=True and resume_headless=True; headless runs in 'plan' mode pause after planning." if (raw_exec_mode == "plan" and allow_chained_publish and resume_headless) else ""

    raw_caller_body = (research_markdown or "").strip()
    explicit_hid = canonicalize_handoff_id(handoff_id or (raw_caller_body if raw_caller_body.upper().startswith("RESUME_STAGED:") else ""))
    is_resume_staged = bool(raw_caller_body.upper().startswith("RESUME_STAGED") or (resume_headless and not raw_caller_body))
    size_warning = f"research_markdown was {len(raw_caller_body)} chars (recommended <= 4,500 chars per call)." if (not is_resume_staged and len(raw_caller_body) > 4500) else ""
    is_close = bool(retire_session or (session_continuity or "").strip().lower() == "closeout" or allow_chained_publish or is_closeout_intent(raw_caller_body, retire_session, session_continuity))

    implicit_hid_repo = explicit_hid.rsplit("-", 1)[0] if (explicit_hid and not session_identifier and not workspace_path and not eff_project_arg) else ""
    resolved_conv_id, routing_reason, auto_rollover_from = "", "create_new_session", ""
    if not create_new_session and (resume_headless or session_identifier):
        resolved_conv_id, routing_reason = _resolve_target_session_for_handoff(session_identifier=session_identifier, workspace_path=workspace_path, project_name=eff_project_arg or implicit_hid_repo, session_title=session_title, activate_skills=activate_skills, research_markdown="" if is_resume_staged else raw_caller_body)
        if resolved_conv_id:
            resolved_conv_id, extra_reason, create_new_session, auto_rollover_from = _evaluate_target_session(resolved_conv_id, is_close=is_close, workspace_path=workspace_path, raw_caller_body=raw_caller_body, session_continuity=session_continuity, allow_chained_publish=allow_chained_publish, retire_session=retire_session, is_resume_staged=is_resume_staged)
            if extra_reason:
                routing_reason = extra_reason

    conv_id, body_clean, resumed_ticket_id, tk_pid = ("" if create_new_session else resolved_conv_id), raw_caller_body, "", ""
    rollover_ref_cid = conv_id or auto_rollover_from or (_resolve_session_identifier(session_identifier.strip()) if (create_new_session and session_identifier.strip() and not create_new_project) else "")
    pre_ws, _, _, pre_slug = _infer_workspace_and_project(workspace_path, eff_project_arg or implicit_hid_repo, session_title, activate_skills, "" if is_resume_staged else raw_caller_body, rollover_ref_cid)
    if is_resume_staged:
        resumed_ticket_id, body_clean, workspace_path, session_title, tk_pid, project_name, repo_hint, create_new_project, default_branch, force_new = _hydrate_resume_staged(explicit_hid=explicit_hid, rollover_ref_cid=rollover_ref_cid, pre_slug=pre_slug, pre_ws=pre_ws, workspace_path=workspace_path, eff_project_arg=eff_project_arg, implicit_hid_repo=implicit_hid_repo, session_title=session_title, project_name=project_name, repo_hint=repo_hint, create_new_project=create_new_project, default_branch=default_branch, session_identifier=session_identifier)
        if not body_clean:
            return json.dumps({"ok": False, "status": "NO_STAGED_HANDOFF_FOR_REPO", "error": f"No matching STAGED handoff found for '{explicit_hid or pre_slug}'. Pass handoff_id='<repo>-01' or provide research_markdown."}, indent=2)
        if force_new:
            create_new_session, conv_id = True, ""

    tgt = resolve_handoff_target(workspace_path=workspace_path, project_name=project_name, repo_hint=repo_hint, session_title=session_title, activate_skills=activate_skills, body_clean=body_clean, conv_id=rollover_ref_cid, create_new_project=create_new_project, default_branch=default_branch, resume_headless=resume_headless, customization_edit_scope=customization_edit_scope, explicit_caller_ws=caller_gave_ws)
    if tgt["guard_error"]:
        return json.dumps(tgt["guard_error"], indent=2)
    eff_ws, eff_pid, eff_pname, repo_slug, eff_branch = tgt["eff_ws"], (tgt["eff_pid"] or tk_pid), tgt["eff_pname"], tgt["repo_slug"], tgt["default_branch"]
    if tgt["force_new_session"]:
        create_new_session, conv_id = True, ""

    active_ws, edit_scope_clean = (eff_ws or ("" if tgt["has_target_spec"] else (SESSION_STATE.get("selected_workspace") or str(get_antigravity_config_repo())))), (customization_edit_scope or "none").strip().lower()
    conv_id, create_new_session, create_new_project, routing_reason, eff_ws, active_ws, eff_pid, eff_pname, repo_slug = apply_global_scope_isolation(
        edit_scope_clean=edit_scope_clean, active_ws=active_ws, conv_id=conv_id, create_new_session=create_new_session, create_new_project=create_new_project,
        routing_reason=routing_reason, eff_ws=eff_ws, eff_pid=eff_pid, eff_pname=eff_pname, repo_slug=repo_slug, session_title=session_title, activate_skills=activate_skills, body_clean=body_clean,
    )

    baton_block = ""
    if create_new_session and rollover_ref_cid and not create_new_project and edit_scope_clean != "global":
        baton_block = extract_prior_session_baton(rollover_ref_cid, cfg.AGY_BRAIN_DIR, ws_path=active_ws)
    elif conv_id:
        tgt_st2 = _get_selected_session_quick_status(conv_id)
        if int(tgt_st2.get("step_count") or 0) >= 350 or bool(tgt_st2.get("context_exceeded") or check_context_exceeded(conv_id, cfg.AGY_BRAIN_DIR)):
            baton_block = extract_prior_session_baton(conv_id, cfg.AGY_BRAIN_DIR, ws_path=active_ws)

    if retire_session and conv_id:
        record_session_retirement(conv_id, cfg.AGY_BRAIN_DIR)

    title_clean = session_title.strip() or _extract_markdown_heading(body_clean) or "Gemini Research Handoff"
    doc = _compose_handoff_document(ts_now=ts_now, eff_exec_mode=eff_exec_mode, eff_handoff_mode=eff_handoff_mode, allow_chained_publish=allow_chained_publish, model=model, effort=effort, apply_hygiene=apply_hygiene, body_clean=body_clean, baton_block=baton_block, activate_skills=activate_skills, target_agent_role=target_agent_role, edit_scope_clean=edit_scope_clean, active_ws=active_ws, retire_session=retire_session, is_closeout=is_close)
    base_ctx = {"title_clean": title_clean, "body_clean": body_clean, "eff_ws": eff_ws, "eff_pid": eff_pid, "eff_pname": eff_pname, "repo_slug": repo_slug, "target_exists": tgt["target_exists"], "create_new_project": create_new_project, "default_branch": eff_branch, "doc": doc, "ts_now": ts_now, "model": model, "effort": effort, "eff_exec_mode": eff_exec_mode, "eff_handoff_mode": eff_handoff_mode, "allow_chained_publish": allow_chained_publish, "apply_hygiene": apply_hygiene, "use_worktree": use_worktree, "baton_block": baton_block, "resumed_ticket_id": resumed_ticket_id, "auto_rollover_from": auto_rollover_from, "supersede_handoff_id": supersede_handoff_id, "append_to_existing": append_to_existing, "is_resume_staged": is_resume_staged, "execution_mode_advisory": execution_mode_advisory, "size_warning": size_warning, "retire_session": retire_session}
    if not conv_id:
        return _run_headless_new_session(base_ctx) if resume_headless else _stage_new_chat_handoff(base_ctx)
    return _stage_or_run_existing_session(conv_id, routing_reason, base_ctx, force_interrupt, resume_headless, active_ws)
