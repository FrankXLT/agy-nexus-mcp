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
from agy_nexus.config import (
    AGY_BG_DIR,
    AGY_BRAIN_DIR,
    AGY_CONFIG_DIR,
    AGY_DATA_DIR,
    AGY_GITLAB_DIR,
    AGY_HOST_BRIDGE_URL,
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
from agy_nexus.routing import _resolve_target_session_for_handoff, _session_matches_repo_hint
from agy_nexus.session_status import (
    _get_selected_session_quick_status,
    check_inflight_handoff_mutex,
)
from agy_nexus.workflows import stage_quarantine_handoff
from agy_nexus.workspace import _resolve_workspace_str

def _post_bridge(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        req = urllib.request.Request(AGY_HOST_BRIDGE_URL, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as e:
        return {"ok": False, "error": f"Failed reaching agy-incident-bridge at {AGY_HOST_BRIDGE_URL}: {e}"}

@mcp.tool(annotations=HANDOFF_ANNOTATIONS, output_schema=None)
def send_handoff_and_resume(
    research_markdown: str,
    resume_headless: bool = False,
    execution_mode: str = "plan",
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
    """Write synthesized Gemini research into an Antigravity conversation scratch folder (or create a brand-new conversation/project), enforcing the 3-Mode Middleman Protocol, Modular Hygiene (<= 300 lines/file), and 4-Step Subagent Lifecycle.

    3-Mode Middleman Protocol (pass via handoff_mode):
      - 'intent' (Default): Pass user requirements, user flow, and acceptance criteria from multi-turn ideation WITHOUT inventing unverified code, CSS, or implementation mechanics from memory. Antigravity's local subagents (flash-scout, flash-surgeon, flash-auditor) inspect the codebase and design the implementation.
      - 'visual_critique': Translate user screenshots/artifacts into precise visual/UX delta critiques anchored to existing repo components and visual-architecture-system.
      - 'surgical_audit': Provide exact code/architecture fixes ONLY after reading target files via ask_workspace_readonly or load_session_into_gemini.

    Gemini High Task Mode (formerly Spark) Project Manager Workflow:
      Gemini acts as an autonomous PM orchestrating multi-step execution:
      1. Scout repo context with ask_workspace_readonly / load_session_into_gemini.
      2. Dispatch Stage & Preview handoffs (allow_chained_publish=False, handoff_mode='intent').
      3. Verify visual contract screenshots and git diffs (inspect_artifact_image / inspect_git_diff).
      4. Approve release only after all verification gates pass (allow_chained_publish=True).

    Pass session_identifier ('1', conversation_id, title, or repo name) to target a specific session directly. Keep research_markdown <= 4,500 chars per call.
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
    resolved_conv_id, routing_reason = ("", "create_new_session")
    if not create_new_session:
        resolved_conv_id, routing_reason = _resolve_target_session_for_handoff(
            session_identifier=session_identifier, workspace_path=workspace_path,
            project_name=project_name, session_title=session_title,
            activate_skills=activate_skills, research_markdown=research_markdown,
        )
    active_ws = workspace_path.strip() or SESSION_STATE.get("selected_workspace") or str(AGY_GITLAB_DIR / "antigravity-config")
    edit_scope_clean = (customization_edit_scope or "none").strip().lower()
    if edit_scope_clean == "global":
        scope_check = evaluate_session_customization_scope(active_ws, AGY_CONFIG_DIR, AGY_GITLAB_DIR)
        if not scope_check["is_global_config_session"] and not _session_matches_repo_hint(resolved_conv_id, "antigravity-config"):
            cfg_conv, cfg_reason = _resolve_target_session_for_handoff(
                session_identifier="", workspace_path=str(AGY_GITLAB_DIR / "antigravity-config"),
                project_name="antigravity-config", session_title=session_title,
                activate_skills=activate_skills, research_markdown=research_markdown,
            )
            if cfg_conv and _session_matches_repo_hint(cfg_conv, "antigravity-config"):
                resolved_conv_id = cfg_conv
                routing_reason = f"scope_isolation_routed_to_existing_config_session ({cfg_reason})"
                active_ws = str(AGY_GITLAB_DIR / "antigravity-config")
            elif resume_headless:
                create_new_session = True
                resolved_conv_id = ""
                workspace_path = str(AGY_GITLAB_DIR / "antigravity-config")
                active_ws = workspace_path
                if not project_name.strip():
                    project_name = "antigravity-config"
    interjection_block, cust_scope_info = build_interjection_directive(
        activate_skills=activate_skills, target_agent_role=target_agent_role,
        customization_edit_scope=edit_scope_clean, research_markdown=research_markdown,
        workspace_str=active_ws, config_dir=AGY_CONFIG_DIR, data_dir=AGY_DATA_DIR, gitlab_dir=AGY_GITLAB_DIR,
    )
    header = (
        f"<!-- Handshake Gemini Research Handoff -->\n"
        f"<!-- Generated: {ts_now} -->\n"
        f"<!-- Execution Mode: {execution_mode} | Handoff Mode: {eff_handoff_mode} | Chained Publish: {allow_chained_publish} | Model: {model} | Effort: {effort} | Modular Hygiene: {apply_hygiene} -->\n\n"
    )
    stage_gate_block = (
        "> [!IMPORTANT]\n"
        "> **STAGE & PREVIEW ONLY (`allow_chained_publish=False`)**: Do NOT run `git push`, `publish_to_github.py`, or container redeployments in this turn.\n"
        "> Stage all changes locally, capture verification screenshots and diffs, and halt execution so Gemini and the user can inspect via `inspect_artifact_image` / `inspect_git_diff`.\n\n"
        if not allow_chained_publish
        else ""
    )
    subagent_footer = (
        "\n---\n\n"
        "## Mandatory 4-Step Subagent Execution Lifecycle & Verification Gate\n\n"
        "1. **Scout (`flash-scout`)**: Read all attached `SKILL.md` contracts first; use `flash-scout` to inspect existing repo patterns, imports, and file structures before planning edits.\n"
        "2. **Implement (`flash-surgeon` / `argon-surgeon`)**: Delegate modular file edits (`<= 300 lines/file`, hard ceiling 400 lines) to subagents rather than soloing 10+ file edits in the parent context.\n"
        "3. **Audit (`flash-auditor`)**: Invoke `flash-auditor` (`model='flash'`) to run syntax/unit/smoke checks and verify `git diff` before marking `task.md` complete (Rule 8.1: the agent that wrote code never signs it off alone).\n"
        "4. **Visual & Preview Gate**: If any `.html`, `.css`, or frontend `.js` files were modified, run `~/.gemini/config/skills/visual-architecture-system/scripts/verify_visual_contract.py` against the local page and save desktop + mobile screenshots to the session artifact directory. When `allow_chained_publish=False`, halt at local staging + preview without pushing or redeploying.\n"
    )
    body_clean = research_markdown.strip()
    hygiene_suffix = f"\n{MODULAR_HYGIENE_MARKDOWN_BLOCK.strip()}\n" if (apply_hygiene and "Mandatory Modular Architecture" not in body_clean) else ""
    full_content = header + stage_gate_block + body_clean + interjection_block + hygiene_suffix + subagent_footer + "\n"
    size_warning = f"research_markdown was {len(body_clean)} chars (recommended <= 4,500 chars per call). Consider using append_to_existing=True for multi-part handoffs." if len(body_clean) > 4500 else ""

    def _write_or_append(target: Path) -> str:
        if append_to_existing and target.is_file():
            existing = target.read_text(encoding="utf-8", errors="replace").rstrip()
            target.write_text(f"{existing}\n\n---\n<!-- Appended: {ts_now} -->\n\n{body_clean}{interjection_block}\n", encoding="utf-8")
            return "appended"
        target.write_text(full_content, encoding="utf-8")
        return "written"

    conv_id = "" if create_new_session else resolved_conv_id
    if not conv_id and (create_new_session or resume_headless):
        title_clean = session_title.strip() or "Gemini Handshake Project"
        eff_project_name = project_name.strip()
        eff_workspace_path = _resolve_workspace_str(workspace_path.strip()) if workspace_path.strip() else ""
        eff_project_id = ""
        if not eff_workspace_path:
            gitlab_prefix_re = re.escape(str(AGY_GITLAB_DIR))
            m_target = re.search(rf"(?:Target\s+Workspace|Workspace|Repository|Directory)[^\n`/]*({gitlab_prefix_re}/[a-zA-Z0-9._-]+)", research_markdown, re.I) or re.search(rf"({gitlab_prefix_re}/[a-zA-Z0-9._-]+)", research_markdown)
            if m_target:
                eff_workspace_path = _resolve_workspace_str(m_target.group(1).rstrip("/"))
                if not eff_project_name:
                    eff_project_name = Path(eff_workspace_path).name
        if not eff_project_name and not eff_workspace_path:
            eff_project_id = SESSION_STATE.get("selected_project", "")
            eff_workspace_path = SESSION_STATE.get("selected_workspace", "")
        prompt_body = body_clean if len(body_clean) <= 4200 else f"{body_clean[:4200]}\n\n... [Full {len(body_clean)}-char specification written to `scratch/gemini_research_handoff.md` — read that file first]"
        spawn_prompt = (
            f"# {title_clean}\n\nThe user initiated this project from Google Gemini via `ag-bridge-mcp` (Handoff Mode: {eff_handoff_mode}).\n\n"
            f"{stage_gate_block}{prompt_body}{interjection_block}{hygiene_suffix}{subagent_footer}\n\n"
            f"Please review `scratch/gemini_research_handoff.md` and modular hygiene requirements above, create `task.md`, and begin in `{execution_mode}` mode."
        )
        bridge_payload = {
            "action": "new-conversation", "model": model if model in ("flash_lite", "flash", "pro") else "pro",
            "title": title_clean, "prompt": spawn_prompt, "project_id": eff_project_id,
            "project_name": eff_project_name, "workspace_path": eff_workspace_path,
        }
        bridge_response = _post_bridge(bridge_payload)
        new_conv_id = str(bridge_response.get("conversation_id") or "").strip()
        if new_conv_id:
            conv_id = new_conv_id
            pin_session_context(
                conv_id, title=title_clean,
                project_id=str(bridge_response.get("project_id") or eff_project_id),
                project_name=str(bridge_response.get("project_name") or eff_project_name),
                workspace=str(bridge_response.get("workspace_path") or eff_workspace_path),
                mode="WORKTREE" if use_worktree else "MAIN WRITER",
                last_tool="send_handoff_and_resume", set_default=True,
            )
            scratch_dir = AGY_BRAIN_DIR / conv_id / "scratch"
            scratch_dir.mkdir(parents=True, exist_ok=True)
            handoff_file = scratch_dir / "gemini_research_handoff.md"
            write_mode = _write_or_append(handoff_file)
        else:
            AGY_BG_DIR.mkdir(parents=True, exist_ok=True)
            handoff_file = AGY_BG_DIR / "latest_gemini_handoff.md"
            write_mode = _write_or_append(handoff_file)
        AGY_BG_DIR.mkdir(parents=True, exist_ok=True)
        job_id = f"job-{hashlib.sha256(f'{conv_id or title_clean}-{time.time()}'.encode()).hexdigest()[:8]}"
        job_metadata = {
            "job_id": job_id, "conversation_id": conv_id,
            "project_id": bridge_response.get("project_id", eff_project_id),
            "project_name": bridge_response.get("project_name", eff_project_name),
            "workspace_path": bridge_response.get("workspace_path", eff_workspace_path),
            "started_at": ts_now, "execution_mode": execution_mode,
            "handoff_mode": eff_handoff_mode, "allow_chained_publish": allow_chained_publish,
            "model": model, "effort": effort, "created_new_session": True,
            "modular_hygiene_enforced": apply_hygiene, "customization_scope_info": cust_scope_info,
            "bridge_response": bridge_response,
        }
        (AGY_BG_DIR / f"{job_id}.json").write_text(json.dumps(job_metadata, indent=2) + "\n", encoding="utf-8")
        out_new: dict[str, Any] = {
            "ok": bridge_response.get("ok", False), "status": "RESUMED", "created_new_session": True,
            "resumed": True, "write_mode": write_mode, "chars_written": len(body_clean),
            "modular_hygiene_enforced": apply_hygiene, "customization_scope_info": cust_scope_info,
            "job_id": job_id, "conversation_id": conv_id,
            "handoff_mode": eff_handoff_mode, "allow_chained_publish": allow_chained_publish,
            "project_id": bridge_response.get("project_id", eff_project_id),
            "project_name": bridge_response.get("project_name", eff_project_name),
            "workspace_path": bridge_response.get("workspace_path", eff_workspace_path),
            "handoff_file": str(handoff_file),
            "assistant_guidance": "STOP AND REPLY TO USER NOW: Handoff delivered and Antigravity session resumed in the background. Do NOT call manage_background_run in this same turn.",
            "bridge_response": bridge_response,
        }
        if size_warning:
            out_new["size_warning"] = size_warning
        return json.dumps(out_new, indent=2)

    if not conv_id:
        AGY_BG_DIR.mkdir(parents=True, exist_ok=True)
        handoff_file = AGY_BG_DIR / "latest_gemini_handoff.md"
        write_mode = _write_or_append(handoff_file)
        out_staged: dict[str, Any] = {
            "ok": True, "status": "STAGED", "resumed": False, "write_mode": write_mode,
            "chars_written": len(body_clean), "modular_hygiene_enforced": apply_hygiene,
            "customization_scope_info": cust_scope_info, "conversation_id": "", "handoff_file": str(handoff_file),
            "message": "Research handoff staged to sidecar_data/ag-bridge-bg/latest_gemini_handoff.md. Pass create_new_session=True or resume_headless=True to spawn a live Antigravity session.",
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
            out_collision: dict[str, Any] = {
                "ok": False,
                "status": "ALREADY_RUNNING",
                "conversation_id": conv_id,
                "conversation_title": conv_title,
                "active_job_id": mutex_check["active_job_id"],
                "elapsed_seconds": mutex_check["elapsed_seconds"],
                "started_at": mutex_check["started_at"],
                "handoff_mode": eff_handoff_mode,
                "allow_chained_publish": allow_chained_publish,
                "assistant_guidance": (
                    "STOP AND REPLY TO USER NOW: Target session is currently RUNNING with an active background job (< 300s). "
                    "Do NOT call send_handoff_and_resume again immediately. "
                    "Call manage_background_run(action='status') to monitor progress, or pass force_interrupt=True to override."
                ),
                "message": mutex_check["message"],
            }
            return json.dumps(out_collision, indent=2)

    handoff_file = scratch_dir / "gemini_research_handoff.md"
    write_mode = _write_or_append(handoff_file)
    sess_mode = "WORKTREE" if use_worktree else ("MAIN WRITER" if resume_headless else str(quick_st.get("mode") or "MAIN TREE"))
    pin_session_context(conv_id, title=conv_title, workspace=str(quick_st.get("workspace_path") or active_ws), mode=sess_mode, last_tool="send_handoff_and_resume", set_default=True)
    if not resume_headless:
        out_local: dict[str, Any] = {
            "ok": True, "status": "STAGED", "resumed": False, "write_mode": write_mode,
            "chars_written": len(body_clean), "modular_hygiene_enforced": apply_hygiene,
            "handoff_mode": eff_handoff_mode, "allow_chained_publish": allow_chained_publish,
            "customization_scope_info": cust_scope_info, "conversation_id": conv_id,
            "conversation_title": conv_title, "routing_reason": routing_reason,
            "mode": sess_mode, "other_running_sessions": other_writers,
            "handoff_file": str(handoff_file),
            "assistant_guidance": "STOP AND REPLY TO USER NOW: Research handoff written to scratch/gemini_research_handoff.md.",
            "message": f"Research handoff successfully {write_mode} to scratch/gemini_research_handoff.md ({len(body_clean)} chars).",
        }
        if size_warning:
            out_local["size_warning"] = size_warning
        return json.dumps(out_local, indent=2)

    AGY_BG_DIR.mkdir(parents=True, exist_ok=True)
    job_id = f"job-{hashlib.sha256(f'{conv_id}-{time.time()}'.encode()).hexdigest()[:8]}"
    gate_directive = (
        "STAGE & PREVIEW ONLY (allow_chained_publish=False): Stage changes locally, run visual checks/diffs, and do NOT push to GitHub or redeploy live containers in this turn. "
        if not allow_chained_publish
        else "CHAINED PUBLISH PERMITTED (allow_chained_publish=True): Ensure all verification and audit checks pass before publishing. "
    )
    bridge_payload = {
        "action": "send-message", "conversation_id": conv_id,
        "project_id": SESSION_STATE.get("session_project_map", {}).get(conv_id) or SESSION_STATE.get("selected_project", ""),
        "title": session_title.strip() or "Gemini Research Handoff",
        "prompt": (
            f"I have synthesized deep architectural research and instructions ({eff_handoff_mode} mode) into `scratch/gemini_research_handoff.md`.\n\n"
            "Follow the 4-Step Subagent Execution Lifecycle:\n"
            "1. Scout: Read attached SKILL.md contracts and inspect repo patterns via flash-scout.\n"
            "2. Implement: Delegate modular edits (<= 300 lines/file) to subagents (flash-surgeon / argon-surgeon).\n"
            "3. Audit: Invoke flash-auditor (model='flash') to verify git diff and run unit/smoke tests before marking task.md complete (Rule 8.1: no solo signoff).\n"
            f"4. Gate: {gate_directive}\n\n"
            "Please read `scratch/gemini_research_handoff.md`, update `task.md`, and execute the next phase."
        ),
    }
    bridge_response = _post_bridge(bridge_payload)
    job_metadata = {
        "job_id": job_id, "conversation_id": conv_id, "conversation_title": conv_title,
        "routing_reason": routing_reason, "started_at": ts_now, "execution_mode": execution_mode,
        "handoff_mode": eff_handoff_mode, "allow_chained_publish": allow_chained_publish,
        "model": model, "effort": effort, "use_worktree": use_worktree, "mode": sess_mode,
        "other_running_sessions": other_writers, "modular_hygiene_enforced": apply_hygiene,
        "customization_scope_info": cust_scope_info, "bridge_response": bridge_response,
    }
    (AGY_BG_DIR / f"{job_id}.json").write_text(json.dumps(job_metadata, indent=2) + "\n", encoding="utf-8")
    out_resumed: dict[str, Any] = {
        "ok": bridge_response.get("ok", False), "status": "RESUMED", "resumed": True,
        "write_mode": write_mode, "chars_written": len(body_clean),
        "modular_hygiene_enforced": apply_hygiene, "customization_scope_info": cust_scope_info,
        "job_id": job_id, "conversation_id": conv_id, "conversation_title": conv_title,
        "routing_reason": routing_reason, "mode": sess_mode, "other_running_sessions": other_writers,
        "handoff_mode": eff_handoff_mode, "allow_chained_publish": allow_chained_publish,
        "handoff_file": str(handoff_file),
        "assistant_guidance": "STOP AND REPLY TO USER NOW: Handoff delivered and Antigravity session resumed in the background. Do NOT call manage_background_run in this same turn.",
        "bridge_response": bridge_response,
    }
    if other_writers and not use_worktree:
        out_resumed["concurrent_writer_warning"] = f"Note: {len(other_writers)} other conversation(s) targeting this workspace are currently running; consider use_worktree=True for parallel edits."
    if size_warning:
        out_resumed["size_warning"] = size_warning
    return json.dumps(out_resumed, indent=2)
