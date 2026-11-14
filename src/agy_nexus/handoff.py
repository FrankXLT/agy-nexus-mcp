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
import urllib.request

import agy_nexus.config as cfg
from agy_nexus.config import (
    AGY_CONFIG_DIR, AGY_DATA_DIR, AGY_GITLAB_DIR, AGY_WORKSPACE_DIR, ALLOW_LOCKED_STAGING,
    HANDOFF_ANNOTATIONS, LOCKED_RESPONSE, SESSION_STATE, _compact_json,
    get_antigravity_config_repo, get_umbrella_roots, get_workspace_pillar_roots,
    is_unlocked, mcp, pin_session_context,
)
from agy_nexus.handoff_queue import (
    canonicalize_handoff_id, mark_ticket_status, normalize_repo_slug,
    record_handoff_ticket, resolve_staged_ticket_for_resume,
)
from agy_nexus.hygiene import ENFORCE_MODULAR_HYGIENE, MODULAR_HYGIENE_MARKDOWN_BLOCK
from agy_nexus.inventory import (
    _resolve_skill_directives,  # noqa: F401
    build_interjection_directive, evaluate_session_customization_scope,
)
from agy_nexus.routing import (
    _extract_handoff_repo_hint, _resolve_session_identifier,
    _resolve_target_session_for_handoff, _session_matches_repo_hint,
)
from agy_nexus.session_status import (
    _get_selected_session_quick_status, check_context_exceeded,
    check_inflight_handoff_mutex, extract_prior_session_baton, find_latest_session_for_workspace,
)
from agy_nexus.sessions import resolve_canonical_project_for_workspace
from agy_nexus.telemetry_scanner import get_active_mainchat_model
from agy_nexus.workflows import stage_quarantine_handoff
from agy_nexus.workspace import _resolve_workspace_str

_USER_BODY_START = "<!-- BEGIN_USER_HANDOFF_BODY -->"
_USER_BODY_END = "<!-- END_USER_HANDOFF_BODY -->"


def _extract_markdown_heading(md_text: str) -> str:
    """Extract the first top-level Markdown heading for default session_title."""
    for ln in (md_text or "").splitlines():
        s = ln.strip()
        if not s or s.startswith("<!--"):
            continue
        m = re.match(r"^#{1,2}\s+(.+)$", s)
        if m:
            cleaned = re.sub(r"[`*_~]+", "", m.group(1)).strip()
            if cleaned:
                return cleaned[:90]
    return ""


def _unwrap_staged_handoff_markdown(staged_text: str) -> str:
    """Extract pure user handoff markdown from an already-staged handoff file to prevent double-wrapping."""
    txt = (staged_text or "").strip()
    if not txt:
        return ""
    if _USER_BODY_START in txt and _USER_BODY_END in txt:
        i0 = txt.index(_USER_BODY_START) + len(_USER_BODY_START)
        i1 = txt.rindex(_USER_BODY_END)
        if i1 >= i0:
            return txt[i0:i1].strip()
    txt = re.sub(r"^(?:<!--[^\n]*-->\s*\n)+", "", txt).lstrip()
    txt = re.sub(r"^>\s*\[!IMPORTANT\]\s*\n(?:>[^\n]*\n)+\s*", "", txt).lstrip()
    txt = re.sub(r"^## Prior Session Baton[\s\S]*?\n---\s*\n+", "", txt).lstrip()
    txt = re.sub(r"\n---\s*\n+## Mandatory 4-Step Execution Lifecycle[\s\S]*$", "", txt).rstrip()
    txt = re.sub(r"\n### Mandatory Modular Architecture[\s\S]*$", "", txt).rstrip()
    txt = re.sub(r"\n---\s*\n+## Antigravity Skill, Agent Role & Customization Scope Directive[\s\S]*$", "", txt).rstrip()
    return txt.strip()


def _post_bridge(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        req = urllib.request.Request(cfg.AGY_HOST_BRIDGE_URL, data=json.dumps(payload).encode("utf-8"), headers=cfg.get_host_bridge_headers(), method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as e:
        return {"ok": False, "error": f"Failed reaching agy-incident-bridge at {cfg.AGY_HOST_BRIDGE_URL}: {e}"}


def _infer_workspace_and_project(
    workspace_path: str,
    project_name: str,
    session_title: str,
    activate_skills: str,
    body_clean: str,
    conv_id: str = "",
) -> tuple[str, str, str, str]:
    """Resolve (eff_workspace_path, eff_project_id, eff_project_name, repo_slug) consistently for both staging and headless wakeup."""
    eff_ws = _resolve_workspace_str(workspace_path.strip()) if workspace_path.strip() else ""
    eff_pname = project_name.strip()
    eff_pid = ""
    if conv_id:
        quick_st = _get_selected_session_quick_status(conv_id)
        if not eff_ws:
            eff_ws = str(quick_st.get("workspace_path") or SESSION_STATE.get("session_workspace_map", {}).get(conv_id) or "")
        eff_pid = str(SESSION_STATE.get("session_project_map", {}).get(conv_id) or "")

    if not eff_ws:
        m_target = None
        for p_root in get_workspace_pillar_roots():
            p_re = re.escape(str(p_root))
            m_target = re.search(rf"(?:Target\s+Workspace|Target\s+Repo|Workspace|Repository|Directory)[^\n`/]*({p_re}/[a-zA-Z0-9._-]+)", body_clean, re.I) or re.search(rf"({p_re}/[a-zA-Z0-9._-]+)", body_clean)
            if m_target:
                break
        if not m_target:
            ws_re = re.escape(str(AGY_WORKSPACE_DIR))
            m_target = re.search(rf"(?:Target\s+Workspace|Target\s+Repo|Workspace|Repository|Directory)[^\n`/]*({ws_re}/[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+)", body_clean, re.I) or re.search(rf"({ws_re}/[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+)", body_clean)
        if m_target:
            eff_ws = _resolve_workspace_str(m_target.group(1).rstrip("/"))
            eff_pname = eff_pname or Path(eff_ws).name

    repo_hint = _extract_handoff_repo_hint(eff_ws or workspace_path, eff_pname, session_title, activate_skills, body_clean)
    if not eff_ws and repo_hint:
        cand_ws = _resolve_workspace_str(repo_hint)
        if cand_ws and Path(cand_ws).is_dir():
            eff_ws = cand_ws
    if not eff_ws and not eff_pname:
        eff_ws = SESSION_STATE.get("selected_workspace", "")

    resolved_pid, resolved_pname = resolve_canonical_project_for_workspace(eff_ws, eff_pname or repo_hint)
    if not eff_pid and resolved_pid:
        eff_pid = resolved_pid
    if resolved_pname and not eff_pname:
        eff_pname = resolved_pname
    repo_slug = normalize_repo_slug(eff_ws, eff_pname, repo_hint, umbrella_roots=get_umbrella_roots())
    return eff_ws, eff_pid, eff_pname, repo_slug


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
    full_content = header + stage_gate_block + baton_block + wrapped_user_body + interjection_block + hygiene_suffix + subagent_footer + "\n"
    return {
        "full_content": full_content,
        "stage_gate_block": stage_gate_block,
        "interjection_block": interjection_block,
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

    prompt_body = body_clean if len(body_clean) <= 4200 else f"{body_clean[:4200]}\n\n... [Full {len(body_clean)}-char specification written to session brain `scratch/gemini_research_handoff.md` — read that file first]"
    spawn_prompt = f"# {title_clean}\n\nThe user initiated this project from Google Gemini via `agy-nexus-mcp` (Handoff Mode: {eff_handoff_mode}, Execution Mode: {eff_exec_mode}).\n\n{doc['stage_gate_block']}{ctx['baton_block']}{prompt_body}{doc['interjection_block']}{doc['hygiene_suffix']}{doc['subagent_footer']}\n\nPlease review session brain `scratch/gemini_research_handoff.md` and modular hygiene requirements above, create `task.md`, and execute in `{eff_exec_mode}` mode."
    bridge_response = _post_bridge({"action": "new-conversation", "model": model if model in ("flash_lite", "flash", "pro") else "pro", "title": title_clean, "prompt": spawn_prompt, "project_id": eff_pid, "project_name": eff_pname, "workspace_path": eff_ws})
    new_conv_id = str(bridge_response.get("conversation_id") or "").strip()
    pinned_ws = eff_ws or str(bridge_response.get("workspace_path") or "")
    bridge_ok = bool(bridge_response.get("ok"))
    job_id = f"job-{hashlib.sha256(f'{new_conv_id or title_clean}-{time.time()}'.encode()).hexdigest()[:8]}"

    resumed_tid = ctx.get("resumed_ticket_id") or ""
    if resumed_tid:
        ticket = mark_ticket_status(cfg.AGY_BG_DIR, resumed_tid, "IN_WORK" if bridge_ok else "STAGED", conversation_id=new_conv_id, job_id=job_id, claim_method="headless_wakeup") or {}
    else:
        ticket = record_handoff_ticket(
            cfg.AGY_BG_DIR, full_markdown=doc["full_content"], chars_written=len(body_clean), repo_slug=repo_slug,
            title=title_clean, project_id=str(bridge_response.get("project_id") or eff_pid), project_name=str(bridge_response.get("project_name") or eff_pname),
            workspace_path=pinned_ws, target_conversation_id=new_conv_id, rollover_from=ctx["auto_rollover_from"],
            execution_mode=eff_exec_mode, handoff_mode=eff_handoff_mode, allow_chained_publish=allow_chained_publish,
            initial_status="IN_WORK" if bridge_ok else "STAGED", claimed_by_conversation_id=new_conv_id if bridge_ok else "",
            job_id=job_id, supersede_handoff_id=ctx["supersede_handoff_id"], append_to_existing=ctx["append_to_existing"],
        )

    if new_conv_id:
        pin_session_context(new_conv_id, title=title_clean, project_id=str(bridge_response.get("project_id") or eff_pid), project_name=str(bridge_response.get("project_name") or eff_pname), workspace=pinned_ws, mode="WORKTREE" if use_worktree else "MAIN WRITER", last_tool="send_handoff_and_resume", set_default=True)
        scratch_dir = cfg.AGY_BRAIN_DIR / new_conv_id / "scratch"
        scratch_dir.mkdir(parents=True, exist_ok=True)
        handoff_file = scratch_dir / "gemini_research_handoff.md"
        write_mode = _write_or_append_scratch(handoff_file, doc["full_content"], body_clean, ctx["baton_block"], doc["interjection_block"], ts_now, ctx["is_resume_staged"], ctx["append_to_existing"])
    else:
        handoff_file = Path(str(ticket.get("handoff_file") or (cfg.AGY_BG_DIR / "latest_gemini_handoff.md")))
        write_mode = "read_staged" if ctx["is_resume_staged"] else "written"

    cfg.AGY_BG_DIR.mkdir(parents=True, exist_ok=True)
    hid = str(ticket.get("handoff_id") or "")
    job_meta: dict[str, Any] = {"job_id": job_id, "handoff_id": hid, "conversation_id": new_conv_id, "project_id": bridge_response.get("project_id", eff_pid), "project_name": bridge_response.get("project_name", eff_pname), "workspace_path": pinned_ws, "started_at": ts_now, "execution_mode": eff_exec_mode, "handoff_mode": eff_handoff_mode, "allow_chained_publish": allow_chained_publish, "model": model, "active_mainchat_model": doc["main_model_info"], "effort": effort, "created_new_session": bool(new_conv_id and bridge_ok), "modular_hygiene_enforced": apply_hygiene, "customization_scope_info": doc["cust_scope_info"], "bridge_response": bridge_response}
    if ctx["auto_rollover_from"]:
        job_meta["auto_rollover_from"] = ctx["auto_rollover_from"]
    (cfg.AGY_BG_DIR / f"{job_id}.json").write_text(json.dumps(job_meta, indent=2) + "\n", encoding="utf-8")
    guidance = (
        f"STOP AND REPLY TO USER NOW: Handoff {hid} delivered and session resumed in background. Do NOT chain a second MCP tool after a successful response."
        if bridge_ok else
        f"STOP AND REPLY TO USER NOW: Host bridge failed to spawn headless session ({bridge_response.get('error', 'bridge error')}); handoff {hid} remains staged at {handoff_file} (say 'Run handoff {hid}' in Antigravity IDE)."
    )
    t_stat = str(ticket.get("status", "IN_WORK"))
    out: dict[str, Any] = {"ok": bridge_ok, "status": "RESUMED" if bridge_ok else "FAILED", "handoff_id": hid, "handoff_status": t_stat, "ticket_status": t_stat, "created_new_session": bool(new_conv_id and bridge_ok), "resumed": bridge_ok, "write_mode": write_mode, "chars_written": len(body_clean), "execution_mode": eff_exec_mode, "modular_hygiene_enforced": apply_hygiene, "customization_scope_info": doc["cust_scope_info"], "active_mainchat_model": doc["main_model_info"], "job_id": job_id, "conversation_id": new_conv_id, "handoff_mode": eff_handoff_mode, "allow_chained_publish": allow_chained_publish, "workspace_path": pinned_ws, "project_id": bridge_response.get("project_id", eff_pid), "project_name": bridge_response.get("project_name", eff_pname), "handoff_file": str(handoff_file), "assistant_guidance": guidance, "bridge_response": bridge_response}
    if ctx["execution_mode_advisory"]:
        out["execution_mode_advisory"] = ctx["execution_mode_advisory"]
    if ctx["auto_rollover_from"]:
        out["auto_rollover_from"], out["auto_promoted_rollover"] = ctx["auto_rollover_from"], True
    if ctx["size_warning"]:
        out["size_warning"] = ctx["size_warning"]
    return json.dumps(out, indent=2)


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
    if ctx["execution_mode_advisory"]:
        out["execution_mode_advisory"] = ctx["execution_mode_advisory"]
    if other_writers and not use_worktree:
        out["concurrent_writer_warning"] = f"Note: {len(other_writers)} other conversation(s) targeting this workspace are currently running; consider use_worktree=True for parallel edits."
    if ctx["size_warning"]:
        out["size_warning"] = ctx["size_warning"]
    return json.dumps(out, indent=2)


@mcp.tool(annotations=HANDOFF_ANNOTATIONS, output_schema=None)
def send_handoff_and_resume(
    research_markdown: str,
    resume_headless: bool = False,
    execution_mode: str = "auto",
    handoff_mode: str = "intent",
    allow_chained_publish: bool = False,
    force_interrupt: bool = False,
    model: str = "pro",
    effort: str = "high",
    use_worktree: bool = False,
    create_new_session: bool = False,
    session_identifier: str = "",
    session_title: str = "",
    project_name: str = "",
    repo_hint: str = "",
    workspace_path: str = "",
    handoff_id: str = "",
    supersede_handoff_id: str = "",
    append_to_existing: bool = False,
    enforce_modular_hygiene: bool = True,
    activate_skills: str = "",
    target_agent_role: str = "",
    customization_edit_scope: str = "none",
    spoken_passphrase: str = "",
) -> str:
    """Stage a repo-prefixed Gemini handoff ticket (`<repo-slug>-01`, `<repo-slug>-02`, ...) or wake up Antigravity headlessly.

    - Default Write-Only Staging (`resume_headless=False`): Mints a collision-free `<repo-slug>-NN` ticket in `STAGED` (unclaimed) state (auto-superseding prior unclaimed tickets on the same repo + topic/session) so the user can open any new or existing Antigravity chat on that repo and say "Run handoff <repo-slug>-NN" (picked up natively via `agy-praxis-mcp`).
    - Zero-Reupload Override (`RESUME_STAGED`): Pass `resume_headless=True`, `research_markdown="RESUME_STAGED"` (and `handoff_id="<repo-slug>-NN"` or repo context) to promote that staged ticket to `IN_WORK` and fire the headless wakeup RPC without cross-project clobbering.
    """
    eff_project_arg = (project_name or repo_hint).strip()
    if not is_unlocked(spoken_passphrase):
        if ALLOW_LOCKED_STAGING and not resume_headless and not create_new_session:
            return _compact_json(stage_quarantine_handoff(bg_dir=cfg.AGY_BG_DIR, research_markdown=research_markdown, session_title=session_title, project_name=eff_project_arg, workspace_path=workspace_path))
        return LOCKED_RESPONSE

    ts_now = datetime.now(timezone.utc).isoformat()
    apply_hygiene = bool(ENFORCE_MODULAR_HYGIENE and enforce_modular_hygiene)
    eff_handoff_mode = (handoff_mode or "intent").strip().lower()
    if eff_handoff_mode not in ("intent", "visual_critique", "surgical_audit"):
        eff_handoff_mode = "intent"
    raw_exec_mode = (execution_mode or "auto").strip().lower()
    eff_exec_mode = ("fast" if (allow_chained_publish and resume_headless) else "plan") if raw_exec_mode not in ("fast", "plan") else raw_exec_mode
    execution_mode_advisory = (
        "execution_mode='plan' was explicitly requested with allow_chained_publish=True and resume_headless=True; headless runs in 'plan' mode pause after planning."
        if (raw_exec_mode == "plan" and allow_chained_publish and resume_headless) else ""
    )

    raw_caller_body = (research_markdown or "").strip()
    explicit_hid = canonicalize_handoff_id(handoff_id or (raw_caller_body if raw_caller_body.upper().startswith("RESUME_STAGED:") else ""))
    is_resume_staged = bool(raw_caller_body.upper().startswith("RESUME_STAGED") or (resume_headless and not raw_caller_body))
    size_warning = f"research_markdown was {len(raw_caller_body)} chars (recommended <= 4,500 chars per call)." if (not is_resume_staged and len(raw_caller_body) > 4500) else ""

    implicit_hid_repo = explicit_hid.rsplit("-", 1)[0] if (explicit_hid and not session_identifier and not workspace_path and not eff_project_arg) else ""
    resolved_conv_id, routing_reason, auto_rollover_from = "", "create_new_session", ""
    if not create_new_session:
        resolved_conv_id, routing_reason = _resolve_target_session_for_handoff(
            session_identifier=session_identifier, workspace_path=workspace_path, project_name=eff_project_arg or implicit_hid_repo,
            session_title=session_title, activate_skills=activate_skills, research_markdown="" if is_resume_staged else raw_caller_body,
        )
        if resolved_conv_id:
            tgt_st = _get_selected_session_quick_status(resolved_conv_id)
            tgt_steps = int(tgt_st.get("step_count") or 0)
            tgt_exceeded = bool(tgt_st.get("context_exceeded") or check_context_exceeded(resolved_conv_id, cfg.AGY_BRAIN_DIR))
            if tgt_steps >= 380 or tgt_exceeded:
                auto_rollover_from, create_new_session, resolved_conv_id = resolved_conv_id, True, ""
                routing_reason = f"auto_promoted_rollover_from_{auto_rollover_from[:8]} (steps={tgt_steps}, exceeded={tgt_exceeded})"

    conv_id = "" if create_new_session else resolved_conv_id
    body_clean, resumed_ticket_id = raw_caller_body, ""
    pre_ws, _, pre_pname, pre_slug = _infer_workspace_and_project(workspace_path, eff_project_arg, session_title, activate_skills, "" if is_resume_staged else raw_caller_body, conv_id)
    if is_resume_staged:
        staged_tk = resolve_staged_ticket_for_resume(cfg.AGY_BG_DIR, handoff_id=explicit_hid, conv_id=conv_id, repo_slug=pre_slug if (workspace_path or eff_project_arg or session_title or conv_id) else "", workspace_path=pre_ws)
        if staged_tk:
            resumed_ticket_id = str(staged_tk["handoff_id"])
            body_clean = _unwrap_staged_handoff_markdown(Path(str(staged_tk["handoff_file"])).read_text(encoding="utf-8", errors="replace"))
            workspace_path = workspace_path or str(staged_tk.get("workspace_path") or "")
            eff_project_arg = eff_project_arg or str(staged_tk.get("project_name") or "")
            session_title = session_title or str(staged_tk.get("title") or "")
            if not staged_tk.get("target_conversation_id") and not session_identifier:
                create_new_session, conv_id = True, ""
        elif conv_id and (cfg.AGY_BRAIN_DIR / conv_id / "scratch" / "gemini_research_handoff.md").is_file():
            body_clean = _unwrap_staged_handoff_markdown((cfg.AGY_BRAIN_DIR / conv_id / "scratch" / "gemini_research_handoff.md").read_text(encoding="utf-8", errors="replace"))
        else:
            return json.dumps({"ok": False, "status": "NO_STAGED_HANDOFF_FOR_REPO", "error": f"No matching STAGED handoff found for '{explicit_hid or pre_slug}'. Pass handoff_id='<repo>-01' or provide research_markdown."}, indent=2)

    eff_ws, eff_pid, eff_pname, repo_slug = _infer_workspace_and_project(workspace_path, eff_project_arg, session_title, activate_skills, body_clean, conv_id)
    active_ws = eff_ws or SESSION_STATE.get("selected_workspace") or str(get_antigravity_config_repo())
    edit_scope_clean = (customization_edit_scope or "none").strip().lower()
    if edit_scope_clean == "global":
        scope_check = evaluate_session_customization_scope(active_ws, AGY_CONFIG_DIR, AGY_GITLAB_DIR)
        if not scope_check["is_global_config_session"] and not _session_matches_repo_hint(conv_id, "antigravity-config"):
            cfg_conv, cfg_reason = _resolve_target_session_for_handoff("", str(get_antigravity_config_repo()), "antigravity-config", session_title, activate_skills, body_clean)
            if cfg_conv and _session_matches_repo_hint(cfg_conv, "antigravity-config"):
                conv_id, create_new_session, routing_reason = cfg_conv, False, f"scope_isolation_routed_to_existing_config_session ({cfg_reason})"
                eff_ws = active_ws = str(get_antigravity_config_repo())
                repo_slug = "antigravity-config"
            elif resume_headless:
                create_new_session, conv_id = True, ""
                eff_ws = active_ws = str(get_antigravity_config_repo())
                eff_pname, repo_slug = eff_pname or "antigravity-config", "antigravity-config"

    baton_block = ""
    if create_new_session:
        prev_id = auto_rollover_from or (_resolve_session_identifier(session_identifier.strip()) if session_identifier.strip() else find_latest_session_for_workspace(active_ws))
        if prev_id:
            baton_block = extract_prior_session_baton(prev_id, cfg.AGY_BRAIN_DIR, ws_path=active_ws)
    elif conv_id:
        tgt_st2 = _get_selected_session_quick_status(conv_id)
        if int(tgt_st2.get("step_count") or 0) >= 350 or bool(tgt_st2.get("context_exceeded") or check_context_exceeded(conv_id, cfg.AGY_BRAIN_DIR)):
            baton_block = extract_prior_session_baton(conv_id, cfg.AGY_BRAIN_DIR, ws_path=active_ws)

    title_clean = session_title.strip() or _extract_markdown_heading(body_clean) or "Gemini Research Handoff"
    doc = _compose_handoff_document(ts_now=ts_now, eff_exec_mode=eff_exec_mode, eff_handoff_mode=eff_handoff_mode, allow_chained_publish=allow_chained_publish, model=model, effort=effort, apply_hygiene=apply_hygiene, body_clean=body_clean, baton_block=baton_block, activate_skills=activate_skills, target_agent_role=target_agent_role, edit_scope_clean=edit_scope_clean, active_ws=active_ws)

    if not conv_id and resume_headless:
        return _run_headless_new_session({"title_clean": title_clean, "body_clean": body_clean, "eff_ws": eff_ws, "eff_pid": eff_pid, "eff_pname": eff_pname, "repo_slug": repo_slug, "doc": doc, "ts_now": ts_now, "model": model, "effort": effort, "eff_exec_mode": eff_exec_mode, "eff_handoff_mode": eff_handoff_mode, "allow_chained_publish": allow_chained_publish, "apply_hygiene": apply_hygiene, "use_worktree": use_worktree, "baton_block": baton_block, "resumed_ticket_id": resumed_ticket_id, "auto_rollover_from": auto_rollover_from, "supersede_handoff_id": supersede_handoff_id, "append_to_existing": append_to_existing, "is_resume_staged": is_resume_staged, "execution_mode_advisory": execution_mode_advisory, "size_warning": size_warning})

    if not conv_id:
        ticket = record_handoff_ticket(cfg.AGY_BG_DIR, full_markdown=doc["full_content"], chars_written=len(body_clean), repo_slug=repo_slug, title=title_clean, project_id=eff_pid, project_name=eff_pname, workspace_path=eff_ws, target_conversation_id="", rollover_from=auto_rollover_from, execution_mode=eff_exec_mode, handoff_mode=eff_handoff_mode, allow_chained_publish=allow_chained_publish, initial_status="STAGED", supersede_handoff_id=supersede_handoff_id, append_to_existing=append_to_existing)
        hid, tfile = str(ticket["handoff_id"]), str(ticket["handoff_file"])
        sup_note = f" (superseded {', '.join(ticket['superseded_ids'])})" if ticket.get("superseded_ids") else ""
        out_staged: dict[str, Any] = {"ok": True, "status": "STAGED_ONLY", "handoff_id": hid, "handoff_status": "STAGED", "ticket_status": "STAGED", "superseded_ids": ticket.get("superseded_ids", []), "repo_slug": repo_slug, "project_id": eff_pid, "project_name": eff_pname or repo_slug, "workspace_path": eff_ws, "resumed": False, "write_mode": "appended" if append_to_existing else "written", "chars_written": len(body_clean), "execution_mode": eff_exec_mode, "modular_hygiene_enforced": apply_hygiene, "customization_scope_info": doc["cust_scope_info"], "active_mainchat_model": doc["main_model_info"], "conversation_id": "", "handoff_file": tfile, "assistant_guidance": f"STOP AND REPLY TO USER NOW: Handoff `{hid}`{sup_note} is staged (UNCLAIMED) for `{repo_slug}` ({title_clean}). Tell the user they can open a new or existing chat on `{repo_slug}` in Antigravity IDE and say 'Run handoff {hid}' (picked up via agy-praxis-mcp without file paths). You MUST end your response with this exact prompt: 'Do you understand the risk and would you like me to override and resume it headlessly anyway?'", "message": f"Research handoff staged as {hid}{sup_note} at {tfile} without headless wakeup."}
        if auto_rollover_from:
            out_staged["auto_rollover_from"] = auto_rollover_from
        if size_warning:
            out_staged["size_warning"] = size_warning
        return json.dumps(out_staged, indent=2)

    scratch_dir = cfg.AGY_BRAIN_DIR / conv_id / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    conv_title = SESSION_STATE.get("session_title_map", {}).get(conv_id, "")
    quick_st = _get_selected_session_quick_status(conv_id)
    other_writers = quick_st.get("other_running_sessions", [])
    if resume_headless and not force_interrupt:
        mutex_check = check_inflight_handoff_mutex(conv_id, cfg.AGY_BG_DIR, quick_st, max_age_seconds=300)
        if mutex_check:
            return json.dumps({"ok": False, "status": "ALREADY_RUNNING", "conversation_id": conv_id, "conversation_title": conv_title, "active_job_id": mutex_check["active_job_id"], "elapsed_seconds": mutex_check["elapsed_seconds"], "started_at": mutex_check["started_at"], "handoff_mode": eff_handoff_mode, "allow_chained_publish": allow_chained_publish, "assistant_guidance": "STOP AND REPLY TO USER NOW: Target session is currently RUNNING with an active background job (< 300s). Call load_session_into_gemini to inspect progress, or pass force_interrupt=True to override.", "message": mutex_check["message"]}, indent=2)

    handoff_file = scratch_dir / "gemini_research_handoff.md"
    write_mode = _write_or_append_scratch(handoff_file, doc["full_content"], body_clean, baton_block, doc["interjection_block"], ts_now, is_resume_staged, append_to_existing)
    if resumed_ticket_id:
        ticket = {"handoff_id": resumed_ticket_id, "status": "STAGED", "superseded_ids": []}
    else:
        ticket = record_handoff_ticket(cfg.AGY_BG_DIR, full_markdown=doc["full_content"], chars_written=len(body_clean), repo_slug=repo_slug, title=title_clean, project_id=eff_pid, project_name=eff_pname, workspace_path=eff_ws or active_ws, target_conversation_id=conv_id, execution_mode=eff_exec_mode, handoff_mode=eff_handoff_mode, allow_chained_publish=allow_chained_publish, initial_status="STAGED", supersede_handoff_id=supersede_handoff_id, append_to_existing=append_to_existing)

    sess_mode = "WORKTREE" if use_worktree else ("MAIN WRITER" if resume_headless else str(quick_st.get("mode") or "MAIN TREE"))
    eff_conv_ws = eff_ws or active_ws
    pin_session_context(conv_id, title=conv_title, project_id=eff_pid, project_name=eff_pname, workspace=eff_conv_ws, mode=sess_mode, last_tool="send_handoff_and_resume", set_default=True)
    if not resume_headless:
        hid = str(ticket["handoff_id"])
        sup_note = f" (superseded {', '.join(ticket['superseded_ids'])})" if ticket.get("superseded_ids") else ""
        out_local: dict[str, Any] = {"ok": True, "status": "STAGED_ONLY", "handoff_id": hid, "handoff_status": "STAGED", "ticket_status": "STAGED", "superseded_ids": ticket.get("superseded_ids", []), "repo_slug": repo_slug, "resumed": False, "write_mode": write_mode, "chars_written": len(body_clean), "execution_mode": eff_exec_mode, "modular_hygiene_enforced": apply_hygiene, "handoff_mode": eff_handoff_mode, "allow_chained_publish": allow_chained_publish, "customization_scope_info": doc["cust_scope_info"], "active_mainchat_model": doc["main_model_info"], "conversation_id": conv_id, "conversation_title": conv_title, "project_id": eff_pid, "project_name": eff_pname or repo_slug, "workspace_path": eff_conv_ws, "routing_reason": routing_reason, "mode": sess_mode, "other_running_sessions": other_writers, "handoff_file": str(handoff_file), "ticket_file": str(ticket.get("handoff_file") or ""), "assistant_guidance": f"STOP AND REPLY TO USER NOW: Handoff `{hid}`{sup_note} is staged (UNCLAIMED) for `{repo_slug}` ({title_clean}). Advise the user they can say 'Run handoff {hid}' in any new or existing Antigravity chat on `{repo_slug}`. You MUST end your response with this exact prompt: 'Do you understand the risk and would you like me to override and resume it headlessly anyway?'", "message": f"Research handoff staged as {hid}{sup_note} ({len(body_clean)} chars) without headless wakeup."}
        if size_warning:
            out_local["size_warning"] = size_warning
        return json.dumps(out_local, indent=2)

    return _run_headless_existing_session({"conv_id": conv_id, "conv_title": conv_title, "title_clean": title_clean, "body_clean": body_clean, "eff_ws": eff_conv_ws, "eff_pid": eff_pid, "eff_pname": eff_pname, "doc": doc, "ts_now": ts_now, "model": model, "effort": effort, "eff_exec_mode": eff_exec_mode, "eff_handoff_mode": eff_handoff_mode, "allow_chained_publish": allow_chained_publish, "apply_hygiene": apply_hygiene, "use_worktree": use_worktree, "baton_block": baton_block, "handoff_file": handoff_file, "write_mode": write_mode, "other_writers": other_writers, "sess_mode": sess_mode, "routing_reason": routing_reason, "ticket": ticket, "execution_mode_advisory": execution_mode_advisory, "size_warning": size_warning})
