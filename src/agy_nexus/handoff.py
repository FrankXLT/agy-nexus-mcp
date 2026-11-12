#!/usr/bin/env python3
"""
agy_nexus.handoff — Research Handoff Synthesis, Scope-Isolation & Headless Session Wakeup Tool.
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
    AGY_BG_DIR,
    AGY_BRAIN_DIR,
    AGY_CONFIG_DIR,
    AGY_DATA_DIR,
    AGY_GITLAB_DIR,
    ALLOW_LOCKED_STAGING,
    HANDOFF_ANNOTATIONS,
    LOCKED_RESPONSE,
    SESSION_STATE,
    _compact_json,
    is_unlocked,
    mcp,
    pin_session_context,
)
from agy_nexus.hygiene import ENFORCE_MODULAR_HYGIENE, MODULAR_HYGIENE_MARKDOWN_BLOCK
from agy_nexus.inventory import (
    _resolve_skill_directives,
    build_interjection_directive,
    evaluate_session_customization_scope,
)
from agy_nexus.routing import (
    _resolve_session_identifier,
    _resolve_target_session_for_handoff,
    _session_matches_repo_hint,
)
from agy_nexus.session_status import (
    _get_selected_session_quick_status,
    check_context_exceeded,
    check_inflight_handoff_mutex,
    extract_prior_session_baton,
    find_latest_session_for_workspace,
)
from agy_nexus.sessions import resolve_canonical_project_for_workspace
from agy_nexus.workflows import stage_quarantine_handoff
from agy_nexus.workspace import _resolve_workspace_str
from agy_nexus.telemetry_scanner import get_active_mainchat_model

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
    """Extract pure user handoff markdown from an already-staged gemini_research_handoff.md to prevent double-wrapping on RESUME_STAGED."""
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
    workspace_path: str = "",
    append_to_existing: bool = False,
    enforce_modular_hygiene: bool = True,
    activate_skills: str = "",
    target_agent_role: str = "",
    customization_edit_scope: str = "none",
    spoken_passphrase: str = "",
) -> str:
    """Write synthesized Gemini research into an Antigravity conversation scratch folder (or create a brand-new conversation/project), enforcing the 3-Mode Middleman Protocol, Polyglot-First Modular Hygiene (<= 500 lines/file, ceiling 650L, functions <= 100L), and 4-Step Subagent Lifecycle.

    3-Mode Middleman Protocol (pass via handoff_mode):
      - 'intent' (Default): Pass user requirements, user flow, and acceptance criteria from multi-turn ideation WITHOUT inventing unverified code, CSS, or implementation mechanics from memory. Antigravity's local subagents (flash-scout, flash-surgeon, flash-auditor) inspect the codebase via agy-polyglot-mcp and design the implementation.
      - 'visual_critique': Translate user screenshots/artifacts into precise visual/UX delta critiques anchored to existing repo components and visual-architecture-system.
      - 'surgical_audit': Provide exact code/architecture fixes ONLY after reading target files via ask_workspace_readonly or load_session_into_gemini.

    Execution Mode ('execution_mode'):
      - 'auto' (Default): Resolves to 'fast' when both allow_chained_publish=True and resume_headless=True so autonomous runs do not pause at planning; otherwise resolves to 'plan'.
      - 'plan' / 'fast': Explicit override.

    Pass session_identifier ('1', conversation_id, title, or repo name) to target a specific session directly. Keep research_markdown <= 4,500 chars per call.

    Two-Step Headless Confirmation & Override Protocol:
      1. Default Write-Only Staging (resume_headless=False):
         Stages research notes to scratch/gemini_research_handoff.md (status="STAGED_ONLY", resumed=False) without calling agy RPCs.
         Gemini MUST inform the user that changes are staged, advise them to send/trigger it in the Antigravity app, and end with the exact prompt:
         "Do you understand the risk and would you like me to override and resume it headlessly anyway?"
      2. Zero-Reupload Override (RESUME_STAGED):
         If the user answers "Yes", call send_handoff_and_resume(..., resume_headless=True, research_markdown="RESUME_STAGED").
         This reads the already-staged file without double-wrapping or overwriting it and fires the headless wakeup RPC immediately.
    """
    if not is_unlocked(spoken_passphrase):
        if ALLOW_LOCKED_STAGING and not resume_headless and not create_new_session:
            return _compact_json(
                stage_quarantine_handoff(
                    bg_dir=AGY_BG_DIR, research_markdown=research_markdown,
                    session_title=session_title, project_name=project_name, workspace_path=workspace_path,
                )
            )
        return LOCKED_RESPONSE
    ts_now = datetime.now(timezone.utc).isoformat()
    apply_hygiene = bool(ENFORCE_MODULAR_HYGIENE and enforce_modular_hygiene)
    eff_handoff_mode = (handoff_mode or "intent").strip().lower()
    if eff_handoff_mode not in ("intent", "visual_critique", "surgical_audit"):
        eff_handoff_mode = "intent"

    raw_exec_mode = (execution_mode or "auto").strip().lower()
    execution_mode_advisory = ""
    if raw_exec_mode in ("", "auto"):
        eff_exec_mode = "fast" if (allow_chained_publish and resume_headless) else "plan"
    elif raw_exec_mode in ("fast", "plan"):
        eff_exec_mode = raw_exec_mode
        if eff_exec_mode == "plan" and allow_chained_publish and resume_headless:
            execution_mode_advisory = (
                "execution_mode='plan' was explicitly requested with allow_chained_publish=True and resume_headless=True; "
                "headless runs in 'plan' mode pause after planning. Pass execution_mode='fast' (or omit for 'auto') for autonomous execution."
            )
    else:
        eff_exec_mode = "fast" if (allow_chained_publish and resume_headless) else "plan"

    raw_caller_body = (research_markdown or "").strip()
    is_resume_staged = bool(resume_headless and (raw_caller_body == "RESUME_STAGED" or not raw_caller_body))
    size_warning = (
        f"research_markdown was {len(raw_caller_body)} chars (recommended <= 4,500 chars per call). Consider using append_to_existing=True for multi-part handoffs."
        if (not is_resume_staged and len(raw_caller_body) > 4500)
        else ""
    )

    resolved_conv_id, routing_reason = ("", "create_new_session")
    auto_rollover_from = ""
    if not create_new_session:
        resolved_conv_id, routing_reason = _resolve_target_session_for_handoff(
            session_identifier=session_identifier, workspace_path=workspace_path,
            project_name=project_name, session_title=session_title,
            activate_skills=activate_skills, research_markdown="" if is_resume_staged else raw_caller_body,
        )
        if resolved_conv_id:
            tgt_st = _get_selected_session_quick_status(resolved_conv_id)
            tgt_steps = int(tgt_st.get("step_count") or 0)
            tgt_exceeded = bool(tgt_st.get("context_exceeded") or check_context_exceeded(resolved_conv_id, AGY_BRAIN_DIR))
            if tgt_steps >= 380 or tgt_exceeded:
                auto_rollover_from = resolved_conv_id
                create_new_session = True
                routing_reason = f"auto_promoted_rollover_from_{resolved_conv_id[:8]} (steps={tgt_steps}, exceeded={tgt_exceeded})"
                resolved_conv_id = ""

    conv_id = "" if create_new_session else resolved_conv_id
    body_clean = raw_caller_body
    if is_resume_staged:
        target_check = (AGY_BRAIN_DIR / conv_id / "scratch" / "gemini_research_handoff.md") if conv_id else (AGY_BG_DIR / "latest_gemini_handoff.md")
        if not target_check.is_file() and (AGY_BG_DIR / "latest_gemini_handoff.md").is_file():
            target_check = AGY_BG_DIR / "latest_gemini_handoff.md"
        if target_check.is_file():
            body_clean = _unwrap_staged_handoff_markdown(target_check.read_text(encoding="utf-8", errors="replace"))
        else:
            return json.dumps({"ok": False, "status": "ERROR", "error": f"No staged handoff found to resume at {target_check}. Please provide research_markdown."}, indent=2)

    active_ws = workspace_path.strip() or SESSION_STATE.get("selected_workspace") or str(AGY_GITLAB_DIR / "antigravity-config")
    edit_scope_clean = (customization_edit_scope or "none").strip().lower()
    if edit_scope_clean == "global":
        scope_check = evaluate_session_customization_scope(active_ws, AGY_CONFIG_DIR, AGY_GITLAB_DIR)
        if not scope_check["is_global_config_session"] and not _session_matches_repo_hint(conv_id, "antigravity-config"):
            cfg_conv, cfg_reason = _resolve_target_session_for_handoff(
                session_identifier="", workspace_path=str(AGY_GITLAB_DIR / "antigravity-config"),
                project_name="antigravity-config", session_title=session_title,
                activate_skills=activate_skills, research_markdown=body_clean,
            )
            if cfg_conv and _session_matches_repo_hint(cfg_conv, "antigravity-config"):
                conv_id = cfg_conv
                create_new_session = False
                routing_reason = f"scope_isolation_routed_to_existing_config_session ({cfg_reason})"
                active_ws = str(AGY_GITLAB_DIR / "antigravity-config")
            elif resume_headless:
                create_new_session = True
                conv_id = ""
                workspace_path = str(AGY_GITLAB_DIR / "antigravity-config")
                active_ws = workspace_path
                if not project_name.strip():
                    project_name = "antigravity-config"

    baton_block = ""
    if create_new_session:
        prev_id = auto_rollover_from or (_resolve_session_identifier(session_identifier.strip()) if session_identifier.strip() else find_latest_session_for_workspace(active_ws))
        if prev_id:
            baton_block = extract_prior_session_baton(prev_id, AGY_BRAIN_DIR, ws_path=active_ws)
    elif conv_id:
        tgt_st = _get_selected_session_quick_status(conv_id)
        if int(tgt_st.get("step_count") or 0) >= 350 or bool(tgt_st.get("context_exceeded") or check_context_exceeded(conv_id, AGY_BRAIN_DIR)):
            baton_block = extract_prior_session_baton(conv_id, AGY_BRAIN_DIR, ws_path=active_ws)

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
        "1. **Scout (`agy-polyglot-mcp` / Serena LSP / `flash-scout`)**: Read all attached `SKILL.md` contracts first. Call `agy-polyglot-mcp` (`polyglot_map`, `polyglot_search`, `polyglot_outline`) or Serena's symbolic LSP tools first to locate exact `Lstart-Lend` spans; for multi-file discovery, dispatch `flash-scout` (`model='flash'`).\n"
        "2. **Implement (Main-Chat `Gemini 4 Carbon` / `argon-surgeon` / `flash-surgeon`)**: Execute 1–2 file surgical symbolic edits or complex state-machine logic directly in Main Chat (on **Gemini 4 Carbon**) or via `argon-surgeon` (`model='pro'`); fan out 3+ file or mechanical refactors (`<= 500 lines/file`, hard ceiling 650 lines, functions `<= 100` lines) to `flash-surgeon` (`model='flash'`).\n"
        "3. **Audit (`flash-auditor` & Intra-Google Dual-Review)**: Invoke `flash-auditor` (`model='flash'`) to run syntax/unit/smoke checks and verify `git diff` (or pit `argon-sentinel` `model='pro'` against Main-Chat **Gemini 4 Carbon** for architectural/security review) before marking `task.md` complete (Rule 8.1: the agent that wrote code never signs it off alone).\n"
        "4. **Visual & Preview Gate**: If any `.html`, `.css`, or frontend `.js` files were modified, run `~/.gemini/config/skills/visual-architecture-system/scripts/verify_visual_contract.py` against the local page and save desktop + mobile screenshots to the session artifact directory. When `allow_chained_publish=False`, halt at local staging + preview without pushing or redeploying (restarting the local `ag-bridge-mcp` service/container whenever Python/web files change so fixes take effect in memory immediately).\n"
    )
    hygiene_suffix = f"\n{MODULAR_HYGIENE_MARKDOWN_BLOCK.strip()}\n" if (apply_hygiene and "Mandatory Modular Architecture" not in body_clean) else ""
    wrapped_user_body = f"{_USER_BODY_START}\n{body_clean}\n{_USER_BODY_END}"
    full_content = header + stage_gate_block + baton_block + wrapped_user_body + interjection_block + hygiene_suffix + subagent_footer + "\n"

    def _write_or_append(target: Path) -> str:
        if is_resume_staged:
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

    inferred_heading = _extract_markdown_heading(body_clean)
    if not conv_id and resume_headless:
        title_clean = session_title.strip() or inferred_heading or "Gemini Handshake Project"
        eff_project_name = project_name.strip()
        eff_workspace_path = _resolve_workspace_str(workspace_path.strip()) if workspace_path.strip() else ""
        if not eff_workspace_path:
            gitlab_prefix_re = re.escape(str(AGY_GITLAB_DIR))
            m_target = re.search(rf"(?:Target\s+Workspace|Workspace|Repository|Directory)[^\n`/]*({gitlab_prefix_re}/[a-zA-Z0-9._-]+)", body_clean, re.I) or re.search(rf"({gitlab_prefix_re}/[a-zA-Z0-9._-]+)", body_clean)
            if m_target:
                eff_workspace_path = _resolve_workspace_str(m_target.group(1).rstrip("/"))
                eff_project_name = eff_project_name or Path(eff_workspace_path).name
        if not eff_project_name and not eff_workspace_path:
            eff_workspace_path = SESSION_STATE.get("selected_workspace", "")
        eff_project_id, resolved_pname = resolve_canonical_project_for_workspace(eff_workspace_path, eff_project_name)
        if resolved_pname:
            eff_project_name = resolved_pname
        if not eff_project_id and not eff_workspace_path:
            eff_project_id = SESSION_STATE.get("selected_project", "")
        prompt_body = body_clean if len(body_clean) <= 4200 else f"{body_clean[:4200]}\n\n... [Full {len(body_clean)}-char specification written to session brain `scratch/gemini_research_handoff.md` — read that file first]"
        spawn_prompt = f"# {title_clean}\n\nThe user initiated this project from Google Gemini via `agy-nexus-mcp` (Handoff Mode: {eff_handoff_mode}, Execution Mode: {eff_exec_mode}).\n\n{stage_gate_block}{baton_block}{prompt_body}{interjection_block}{hygiene_suffix}{subagent_footer}\n\nPlease review session brain `scratch/gemini_research_handoff.md` and modular hygiene requirements above, create `task.md`, and execute in `{eff_exec_mode}` mode."
        bridge_response = _post_bridge({"action": "new-conversation", "model": model if model in ("flash_lite", "flash", "pro") else "pro", "title": title_clean, "prompt": spawn_prompt, "project_id": eff_project_id, "project_name": eff_project_name, "workspace_path": eff_workspace_path})
        new_conv_id = str(bridge_response.get("conversation_id") or "").strip()
        pinned_ws = eff_workspace_path or str(bridge_response.get("workspace_path") or "")
        if new_conv_id:
            conv_id = new_conv_id
            pin_session_context(conv_id, title=title_clean, project_id=str(bridge_response.get("project_id") or eff_project_id), project_name=str(bridge_response.get("project_name") or eff_project_name), workspace=pinned_ws, mode="WORKTREE" if use_worktree else "MAIN WRITER", last_tool="send_handoff_and_resume", set_default=True)
            scratch_dir = AGY_BRAIN_DIR / conv_id / "scratch"
            scratch_dir.mkdir(parents=True, exist_ok=True)
            handoff_file = scratch_dir / "gemini_research_handoff.md"
        else:
            AGY_BG_DIR.mkdir(parents=True, exist_ok=True)
            handoff_file = AGY_BG_DIR / "latest_gemini_handoff.md"
        write_mode = _write_or_append(handoff_file)
        job_id = f"job-{hashlib.sha256(f'{conv_id or title_clean}-{time.time()}'.encode()).hexdigest()[:8]}"
        bridge_ok = bool(bridge_response.get("ok"))
        job_metadata: dict[str, Any] = {"job_id": job_id, "conversation_id": conv_id, "project_id": bridge_response.get("project_id", eff_project_id), "project_name": bridge_response.get("project_name", eff_project_name), "workspace_path": pinned_ws, "started_at": ts_now, "execution_mode": eff_exec_mode, "handoff_mode": eff_handoff_mode, "allow_chained_publish": allow_chained_publish, "model": model, "active_mainchat_model": main_model_info, "effort": effort, "created_new_session": bool(conv_id and bridge_ok), "modular_hygiene_enforced": apply_hygiene, "customization_scope_info": cust_scope_info, "bridge_response": bridge_response}
        if auto_rollover_from:
            job_metadata["auto_rollover_from"] = auto_rollover_from
        (AGY_BG_DIR / f"{job_id}.json").write_text(json.dumps(job_metadata, indent=2) + "\n", encoding="utf-8")
        new_guidance = (
            "STOP AND REPLY TO USER NOW: Handoff delivered and session resumed in background. Do NOT chain a second MCP tool after a successful response."
            if bridge_ok else
            f"STOP AND REPLY TO USER NOW: Host bridge failed to spawn headless session ({bridge_response.get('error', 'bridge error')}); handoff specification was saved to {handoff_file}."
        )
        out_new: dict[str, Any] = {"ok": bridge_ok, "status": "RESUMED" if bridge_ok else "FAILED", "created_new_session": bool(conv_id and bridge_ok), "resumed": bridge_ok, "write_mode": write_mode, "chars_written": len(body_clean), "execution_mode": eff_exec_mode, "modular_hygiene_enforced": apply_hygiene, "customization_scope_info": cust_scope_info, "active_mainchat_model": main_model_info, "job_id": job_id, "conversation_id": conv_id, "handoff_mode": eff_handoff_mode, "allow_chained_publish": allow_chained_publish, "workspace_path": pinned_ws, "project_id": bridge_response.get("project_id", eff_project_id), "project_name": bridge_response.get("project_name", eff_project_name), "handoff_file": str(handoff_file), "assistant_guidance": new_guidance, "bridge_response": bridge_response}
        if execution_mode_advisory:
            out_new["execution_mode_advisory"] = execution_mode_advisory
        if auto_rollover_from:
            out_new["auto_rollover_from"], out_new["auto_promoted_rollover"] = auto_rollover_from, True
        if size_warning:
            out_new["size_warning"] = size_warning
        return json.dumps(out_new, indent=2)

    if not conv_id:
        AGY_BG_DIR.mkdir(parents=True, exist_ok=True)
        handoff_file = AGY_BG_DIR / "latest_gemini_handoff.md"
        write_mode = _write_or_append(handoff_file)
        out_staged: dict[str, Any] = {
            "ok": True,
            "status": "STAGED_ONLY",
            "resumed": False,
            "write_mode": write_mode,
            "chars_written": len(body_clean),
            "execution_mode": eff_exec_mode,
            "modular_hygiene_enforced": apply_hygiene,
            "customization_scope_info": cust_scope_info,
            "active_mainchat_model": main_model_info,
            "conversation_id": "",
            "handoff_file": str(handoff_file),
            "assistant_guidance": (
                f"STOP AND REPLY TO USER NOW: Handoff is staged to Antigravity at {handoff_file}. "
                "Advise the user that changes are staged and they can send/trigger it in the Antigravity app. "
                "You MUST end your response with this exact prompt: 'Do you understand the risk and would you like me to override and resume it headlessly anyway?'"
            ),
            "message": f"Research handoff staged to {handoff_file} without headless wakeup.",
        }
        if size_warning:
            out_staged["size_warning"] = size_warning
        return json.dumps(out_staged, indent=2)

    scratch_dir = AGY_BRAIN_DIR / conv_id / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    conv_title = SESSION_STATE.get("session_title_map", {}).get(conv_id, "")
    quick_st = _get_selected_session_quick_status(conv_id)
    other_writers = quick_st.get("other_running_sessions", [])

    if resume_headless and not force_interrupt:
        mutex_check = check_inflight_handoff_mutex(conv_id, AGY_BG_DIR, quick_st, max_age_seconds=300)
        if mutex_check:
            return json.dumps({"ok": False, "status": "ALREADY_RUNNING", "conversation_id": conv_id, "conversation_title": conv_title, "active_job_id": mutex_check["active_job_id"], "elapsed_seconds": mutex_check["elapsed_seconds"], "started_at": mutex_check["started_at"], "handoff_mode": eff_handoff_mode, "allow_chained_publish": allow_chained_publish, "assistant_guidance": "STOP AND REPLY TO USER NOW: Target session is currently RUNNING with an active background job (< 300s). Call load_session_into_gemini to inspect progress, or pass force_interrupt=True to override.", "message": mutex_check["message"]}, indent=2)

    handoff_file = scratch_dir / "gemini_research_handoff.md"
    write_mode = _write_or_append(handoff_file)
    sess_mode = "WORKTREE" if use_worktree else ("MAIN WRITER" if resume_headless else str(quick_st.get("mode") or "MAIN TREE"))
    eff_conv_ws = str(quick_st.get("workspace_path") or SESSION_STATE.get("session_workspace_map", {}).get(conv_id) or active_ws)
    eff_conv_pid = str(SESSION_STATE.get("session_project_map", {}).get(conv_id) or "")
    eff_conv_pname = project_name.strip()
    if not eff_conv_pid:
        eff_conv_pid, resolved_conv_pname = resolve_canonical_project_for_workspace(eff_conv_ws, eff_conv_pname)
        if resolved_conv_pname and not eff_conv_pname:
            eff_conv_pname = resolved_conv_pname
    pin_session_context(conv_id, title=conv_title, project_id=eff_conv_pid, project_name=eff_conv_pname, workspace=eff_conv_ws, mode=sess_mode, last_tool="send_handoff_and_resume", set_default=True)
    if not resume_headless:
        out_local: dict[str, Any] = {
            "ok": True,
            "status": "STAGED_ONLY",
            "resumed": False,
            "write_mode": write_mode,
            "chars_written": len(body_clean),
            "execution_mode": eff_exec_mode,
            "modular_hygiene_enforced": apply_hygiene,
            "handoff_mode": eff_handoff_mode,
            "allow_chained_publish": allow_chained_publish,
            "customization_scope_info": cust_scope_info,
            "active_mainchat_model": main_model_info,
            "conversation_id": conv_id,
            "conversation_title": conv_title,
            "project_id": eff_conv_pid,
            "workspace_path": eff_conv_ws,
            "routing_reason": routing_reason,
            "mode": sess_mode,
            "other_running_sessions": other_writers,
            "handoff_file": str(handoff_file),
            "assistant_guidance": (
                f"STOP AND REPLY TO USER NOW: Handoff is staged to Antigravity at {handoff_file}. "
                "Advise the user that changes are staged and they can send/trigger it in the Antigravity app. "
                "You MUST end your response with this exact prompt: 'Do you understand the risk and would you like me to override and resume it headlessly anyway?'"
            ),
            "message": f"Research handoff successfully {write_mode} to {handoff_file} ({len(body_clean)} chars) without headless wakeup.",
        }
        if size_warning:
            out_local["size_warning"] = size_warning
        return json.dumps(out_local, indent=2)

    AGY_BG_DIR.mkdir(parents=True, exist_ok=True)
    job_id = f"job-{hashlib.sha256(f'{conv_id}-{time.time()}'.encode()).hexdigest()[:8]}"
    gate_directive = "STAGE & PREVIEW ONLY (allow_chained_publish=False): Stage changes locally, run visual checks/diffs, and do NOT push to GitHub or redeploy remote production stacks in this turn. You MUST still restart the local ag-bridge-mcp service/container whenever Python/web files change so fixes take effect in memory immediately. " if not allow_chained_publish else "CHAINED PUBLISH PERMITTED (allow_chained_publish=True): Ensure all verification and audit checks pass before publishing. "
    send_prompt_body = body_clean if len(body_clean) <= 2500 else f"{body_clean[:2500]}\n\n... [Full {len(body_clean)}-char specification written to `{handoff_file}` — read that file first]"
    bridge_payload = {
        "action": "send-message", "conversation_id": conv_id,
        "project_id": eff_conv_pid,
        "title": session_title.strip() or inferred_heading or conv_title or "Gemini Research Handoff",
        "prompt": (
            f"{stage_gate_block}# Gemini Follow-Up Handoff ({eff_handoff_mode.upper()} Mode | Execution Mode: {eff_exec_mode})\n\n"
            f"The user provided a new follow-up request via Google Gemini (`agy-nexus-mcp`).\n\n"
            f"{baton_block}{send_prompt_body}\n\n---\n{interjection_block}\n"
            "Follow the 4-Step Execution Lifecycle (Carbon 4 Main-Chat + Subagent Hybrid):\n"
            "1. Scout: Read attached SKILL.md contracts; use agy-polyglot-mcp (polyglot_map, polyglot_search, polyglot_outline) or Serena LSP tools directly for 1-2 files, or flash-scout (model='flash') for multi-file discovery.\n"
            "2. Implement: Execute 1-2 file surgical symbolic edits (replace_symbol_body) or complex logic directly in Main Chat (Gemini 4 Carbon) or via argon-surgeon (model='pro'); fan out 3+ file / mechanical refactors (<= 500 lines/file, ceiling 650L, functions <= 100L) to flash-surgeon (model='flash').\n"
            "3. Audit: Invoke flash-auditor (model='flash') or Intra-Google Dual-Review (argon-sentinel model='pro' vs Carbon 4) to verify git diff and run unit/smoke tests before marking task.md complete (Rule 8.1: no solo signoff).\n"
            f"4. Gate: {gate_directive}\n\nPlease review `{handoff_file}`, update `task.md`, and execute the next phase in `{eff_exec_mode}` mode."
        ),
    }
    bridge_response = _post_bridge(bridge_payload)
    bridge_ok = bool(bridge_response.get("ok"))
    job_metadata = {"job_id": job_id, "conversation_id": conv_id, "conversation_title": conv_title, "project_id": eff_conv_pid, "workspace_path": eff_conv_ws, "routing_reason": routing_reason, "started_at": ts_now, "execution_mode": eff_exec_mode, "handoff_mode": eff_handoff_mode, "allow_chained_publish": allow_chained_publish, "model": model, "active_mainchat_model": main_model_info, "effort": effort, "use_worktree": use_worktree, "mode": sess_mode, "other_running_sessions": other_writers, "modular_hygiene_enforced": apply_hygiene, "customization_scope_info": cust_scope_info, "bridge_response": bridge_response}
    (AGY_BG_DIR / f"{job_id}.json").write_text(json.dumps(job_metadata, indent=2) + "\n", encoding="utf-8")
    resumed_guidance = (
        "STOP AND REPLY TO USER NOW: Handoff delivered and session resumed in background. Do NOT chain a second MCP tool after a successful response."
        if bridge_ok else
        f"STOP AND REPLY TO USER NOW: Host bridge wakeup failed ({bridge_response.get('error', 'bridge error')}); handoff specification remains staged at {handoff_file} for manual pickup."
    )
    out_resumed: dict[str, Any] = {"ok": bridge_ok, "status": "RESUMED" if bridge_ok else "FAILED", "resumed": bridge_ok, "write_mode": write_mode, "chars_written": len(body_clean), "execution_mode": eff_exec_mode, "modular_hygiene_enforced": apply_hygiene, "customization_scope_info": cust_scope_info, "active_mainchat_model": main_model_info, "job_id": job_id, "conversation_id": conv_id, "conversation_title": conv_title, "project_id": eff_conv_pid, "workspace_path": eff_conv_ws, "routing_reason": routing_reason, "mode": sess_mode, "other_running_sessions": other_writers, "handoff_mode": eff_handoff_mode, "allow_chained_publish": allow_chained_publish, "handoff_file": str(handoff_file), "assistant_guidance": resumed_guidance, "bridge_response": bridge_response}
    if execution_mode_advisory:
        out_resumed["execution_mode_advisory"] = execution_mode_advisory
    if other_writers and not use_worktree:
        out_resumed["concurrent_writer_warning"] = f"Note: {len(other_writers)} other conversation(s) targeting this workspace are currently running; consider use_worktree=True for parallel edits."
    if size_warning:
        out_resumed["size_warning"] = size_warning
    return json.dumps(out_resumed, indent=2)
