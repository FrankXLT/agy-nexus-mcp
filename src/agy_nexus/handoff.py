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
    _save_session_state,
    is_unlocked,
    mcp,
)
from agy_nexus.hygiene import ENFORCE_MODULAR_HYGIENE, MODULAR_HYGIENE_MARKDOWN_BLOCK
from agy_nexus.inventory import build_interjection_directive, evaluate_session_customization_scope
from agy_nexus.routing import _resolve_target_session_for_handoff, _session_matches_repo_hint
from agy_nexus.workflows import stage_quarantine_handoff
from agy_nexus.workspace import _resolve_workspace_str
@mcp.tool(annotations=HANDOFF_ANNOTATIONS, output_schema=None)
def send_handoff_and_resume(
    research_markdown: str,
    resume_headless: bool = False,
    execution_mode: str = "plan",
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
    """Write synthesized Gemini research into an Antigravity conversation scratch folder (or create a brand-new conversation/project), automatically attaching Modular Hygiene standards, optional Skill/Agent Role interjection directives (activate_skills, target_agent_role), and enforcing Scope-Isolation. Pass session_identifier ('1', conversation_id, title, or repo name) to target a specific session directly. Keep research_markdown <= 4,500 chars per call."""
    if not is_unlocked(spoken_passphrase):
        if ALLOW_LOCKED_STAGING and not resume_headless and not create_new_session:
            return _compact_json(
                stage_quarantine_handoff(
                    bg_dir=AGY_BG_DIR,
                    research_markdown=research_markdown,
                    session_title=session_title,
                    project_name=project_name,
                    workspace_path=workspace_path,
                )
            )
        return LOCKED_RESPONSE
    ts_now = datetime.now(timezone.utc).isoformat()
    apply_hygiene = bool(ENFORCE_MODULAR_HYGIENE and enforce_modular_hygiene)
    resolved_conv_id, routing_reason = ("", "create_new_session")
    if not create_new_session:
        resolved_conv_id, routing_reason = _resolve_target_session_for_handoff(
            session_identifier=session_identifier,
            workspace_path=workspace_path,
            project_name=project_name,
            session_title=session_title,
            activate_skills=activate_skills,
            research_markdown=research_markdown,
        )
    active_ws = (
        workspace_path.strip()
        or SESSION_STATE.get("selected_workspace")
        or str(AGY_GITLAB_DIR / "antigravity-config")
    )
    # Enforce Scope-Isolation: if customization_edit_scope == 'global' while inside a feature project,
    # route to an existing antigravity-config session if available (or spawn a new one if none exists)
    edit_scope_clean = (customization_edit_scope or "none").strip().lower()
    if edit_scope_clean == "global":
        scope_check = evaluate_session_customization_scope(active_ws, AGY_CONFIG_DIR, AGY_GITLAB_DIR)
        if not scope_check["is_global_config_session"] and not _session_matches_repo_hint(resolved_conv_id, "antigravity-config"):
            cfg_conv, cfg_reason = _resolve_target_session_for_handoff(
                session_identifier="",
                workspace_path=str(AGY_GITLAB_DIR / "antigravity-config"),
                project_name="antigravity-config",
                session_title=session_title,
                activate_skills=activate_skills,
                research_markdown=research_markdown,
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
        activate_skills=activate_skills,
        target_agent_role=target_agent_role,
        customization_edit_scope=edit_scope_clean,
        research_markdown=research_markdown,
        workspace_str=active_ws,
        config_dir=AGY_CONFIG_DIR,
        data_dir=AGY_DATA_DIR,
        gitlab_dir=AGY_GITLAB_DIR,
    )
    header = (
        f"<!-- Handshake Gemini Research Handoff -->\n"
        f"<!-- Generated: {ts_now} -->\n"
        f"<!-- Execution Mode: {execution_mode} | Model: {model} | Effort: {effort} | Modular Hygiene: {apply_hygiene} -->\n\n"
    )
    body_clean = research_markdown.strip()
    hygiene_suffix = (
        f"\n{MODULAR_HYGIENE_MARKDOWN_BLOCK.strip()}\n"
        if (apply_hygiene and "Mandatory Modular Architecture" not in body_clean)
        else ""
    )
    full_content = header + body_clean + interjection_block + hygiene_suffix + "\n"
    size_warning = (
        f"research_markdown was {len(body_clean)} chars (recommended <= 4,500 chars per call). Consider using append_to_existing=True for multi-part handoffs."
        if len(body_clean) > 4500
        else ""
    )
    def _write_or_append(target: Path) -> str:
        if append_to_existing and target.is_file():
            existing = target.read_text(encoding="utf-8", errors="replace").rstrip()
            combined = f"{existing}\n\n---\n<!-- Appended: {ts_now} -->\n\n{body_clean}{interjection_block}\n"
            target.write_text(combined, encoding="utf-8")
            return "appended"
        target.write_text(full_content, encoding="utf-8")
        return "written"
    conv_id = "" if create_new_session else resolved_conv_id
    # If creating a new session or no session selected when resuming headless, spawn via Host Bridge
    if not conv_id and (create_new_session or resume_headless):
        title_clean = session_title.strip() or "Gemini Handshake Project"
        eff_project_name = project_name.strip()
        eff_workspace_path = _resolve_workspace_str(workspace_path.strip()) if workspace_path.strip() else ""
        eff_project_id = ""
        # Auto-extract target workspace / project from research_markdown if not explicitly passed
        if not eff_workspace_path:
            gitlab_prefix_re = re.escape(str(AGY_GITLAB_DIR))
            m_target = re.search(
                rf"(?:Target\s+Workspace|Workspace|Repository|Directory)[^\n`/]*({gitlab_prefix_re}/[a-zA-Z0-9._-]+)",
                research_markdown,
                re.I,
            )
            if not m_target:
                m_target = re.search(rf"({gitlab_prefix_re}/[a-zA-Z0-9._-]+)", research_markdown)
            if m_target:
                eff_workspace_path = _resolve_workspace_str(m_target.group(1).rstrip("/"))
                if not eff_project_name:
                    eff_project_name = Path(eff_workspace_path).name
        if not eff_project_name and not eff_workspace_path:
            eff_project_id = SESSION_STATE.get("selected_project", "")
            eff_workspace_path = SESSION_STATE.get("selected_workspace", "")
        prompt_body = (
            body_clean
            if len(body_clean) <= 4200
            else (
                f"{body_clean[:4200]}\n\n"
                f"... [Full {len(body_clean)}-char specification written to `scratch/gemini_research_handoff.md` — read that file first]"
            )
        )
        spawn_prompt = (
            f"# {title_clean}\n\n"
            f"The user initiated this project from Google Gemini via `ag-bridge-mcp`.\n\n"
            f"{prompt_body}{interjection_block}{hygiene_suffix}\n\n"
            f"Please review `scratch/gemini_research_handoff.md` and modular hygiene requirements above, create `task.md`, and begin in `{execution_mode}` mode."
        )
        bridge_payload = {
            "action": "new-conversation",
            "model": model if model in ("flash_lite", "flash", "pro") else "pro",
            "title": title_clean, "prompt": spawn_prompt,
            "project_id": eff_project_id, "project_name": eff_project_name,
            "workspace_path": eff_workspace_path,
        }
        bridge_response: dict[str, Any] = {}
        try:
            req = urllib.request.Request(
                AGY_HOST_BRIDGE_URL,
                data=json.dumps(bridge_payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                bridge_response = json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception as e:
            bridge_response = {"ok": False, "error": f"Failed reaching agy-incident-bridge at {AGY_HOST_BRIDGE_URL}: {e}"}
        new_conv_id = str(bridge_response.get("conversation_id") or "").strip()
        if new_conv_id:
            conv_id = new_conv_id
            SESSION_STATE["selected_session"] = conv_id
            if bridge_response.get("project_id"):
                SESSION_STATE["selected_project"] = str(bridge_response["project_id"])
            if bridge_response.get("workspace_path"):
                SESSION_STATE["selected_workspace"] = str(bridge_response["workspace_path"])
            _save_session_state()
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
            "model": model, "effort": effort,
            "created_new_session": True, "modular_hygiene_enforced": apply_hygiene,
            "customization_scope_info": cust_scope_info, "bridge_response": bridge_response,
        }
        (AGY_BG_DIR / f"{job_id}.json").write_text(json.dumps(job_metadata, indent=2) + "\n", encoding="utf-8")
        out_new: dict[str, Any] = {
            "ok": bridge_response.get("ok", False),
            "status": "RESUMED", "created_new_session": True,
            "resumed": True, "write_mode": write_mode,
            "chars_written": len(body_clean), "modular_hygiene_enforced": apply_hygiene,
            "customization_scope_info": cust_scope_info, "job_id": job_id,
            "conversation_id": conv_id,
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
    # If no session is selected and resume_headless is False, stage in AGY_BG_DIR
    if not conv_id:
        AGY_BG_DIR.mkdir(parents=True, exist_ok=True)
        handoff_file = AGY_BG_DIR / "latest_gemini_handoff.md"
        write_mode = _write_or_append(handoff_file)
        out_staged: dict[str, Any] = {
            "ok": True, "status": "STAGED",
            "resumed": False, "write_mode": write_mode,
            "chars_written": len(body_clean), "modular_hygiene_enforced": apply_hygiene,
            "customization_scope_info": cust_scope_info, "conversation_id": "",
            "handoff_file": str(handoff_file),
            "message": (
                "Research handoff staged to sidecar_data/ag-bridge-bg/latest_gemini_handoff.md. "
                "Pass create_new_session=True or resume_headless=True to spawn a live Antigravity session, "
                "or call load_session_into_gemini first to target an existing session."
            ),
        }
        if size_warning:
            out_staged["size_warning"] = size_warning
        return json.dumps(out_staged, indent=2)
    scratch_dir = AGY_BRAIN_DIR / conv_id / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    handoff_file = scratch_dir / "gemini_research_handoff.md"
    write_mode = _write_or_append(handoff_file)
    conv_title = SESSION_STATE.get("session_title_map", {}).get(conv_id, "")
    if not resume_headless:
        out_local: dict[str, Any] = {
            "ok": True, "status": "STAGED",
            "resumed": False, "write_mode": write_mode,
            "chars_written": len(body_clean), "modular_hygiene_enforced": apply_hygiene,
            "customization_scope_info": cust_scope_info, "conversation_id": conv_id,
            "conversation_title": conv_title, "routing_reason": routing_reason,
            "handoff_file": str(handoff_file),
            "assistant_guidance": "STOP AND REPLY TO USER NOW: Research handoff written to scratch/gemini_research_handoff.md.",
            "message": f"Research handoff successfully {write_mode} to scratch/gemini_research_handoff.md ({len(body_clean)} chars).",
        }
        if size_warning:
            out_local["size_warning"] = size_warning
        return json.dumps(out_local, indent=2)
    # Resume headless execution via AGY_HOST_BRIDGE_URL (/agentapi)
    AGY_BG_DIR.mkdir(parents=True, exist_ok=True)
    job_id = f"job-{hashlib.sha256(f'{conv_id}-{time.time()}'.encode()).hexdigest()[:8]}"
    bridge_payload = {
        "action": "send-message", "conversation_id": conv_id,
        "project_id": SESSION_STATE.get("session_project_map", {}).get(conv_id) or SESSION_STATE.get("selected_project", ""),
        "title": session_title.strip() or "Gemini Research Handoff",
        "prompt": (
            "I have synthesized deep architectural research and instructions into `scratch/gemini_research_handoff.md`. "
            "Please read `scratch/gemini_research_handoff.md`, update `task.md` accordingly, enforce the Modular Architecture & File Hygiene Standard (<= 300 lines/file), and proceed with execution."
        ),
    }
    bridge_response = {}
    try:
        req = urllib.request.Request(
            AGY_HOST_BRIDGE_URL,
            data=json.dumps(bridge_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            bridge_response = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as e:
        bridge_response = {"ok": False, "error": f"Failed reaching agy-incident-bridge at {AGY_HOST_BRIDGE_URL}: {e}"}
    job_metadata = {
        "job_id": job_id, "conversation_id": conv_id,
        "conversation_title": conv_title, "routing_reason": routing_reason,
        "started_at": ts_now, "execution_mode": execution_mode,
        "model": model, "effort": effort,
        "use_worktree": use_worktree, "modular_hygiene_enforced": apply_hygiene,
        "customization_scope_info": cust_scope_info, "bridge_response": bridge_response,
    }
    (AGY_BG_DIR / f"{job_id}.json").write_text(json.dumps(job_metadata, indent=2) + "\n", encoding="utf-8")
    out_resumed: dict[str, Any] = {
        "ok": bridge_response.get("ok", False),
        "status": "RESUMED", "resumed": True,
        "write_mode": write_mode, "chars_written": len(body_clean),
        "modular_hygiene_enforced": apply_hygiene, "customization_scope_info": cust_scope_info,
        "job_id": job_id, "conversation_id": conv_id,
        "conversation_title": conv_title, "routing_reason": routing_reason,
        "handoff_file": str(handoff_file),
        "assistant_guidance": "STOP AND REPLY TO USER NOW: Handoff delivered and Antigravity session resumed in the background. Do NOT call manage_background_run in this same turn.",
        "bridge_response": bridge_response,
    }
    if size_warning:
        out_resumed["size_warning"] = size_warning
    return json.dumps(out_resumed, indent=2)
