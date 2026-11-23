#!/usr/bin/env python3
"""agy_nexus.workflow_gate — 4-Gate WF-XX & Common Terms Validation, Auto-Injection & Closeout Checks.

Enforces plain-language workflow grounding on send_handoff_and_resume (never bypassed by
allow_chained_publish=True), injects matched WF-XX sections and Common Terms into staged
handoffs, and verifies docs/WORKFLOWS.md updates before praxis_update_handoff completes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import subprocess
from typing import Any

import agy_nexus.config as cfg
from agy_nexus.retirement import build_suggested_actions
from agy_nexus.workflow_baseline import (
    PRIMARY_WORKFLOW_FILES,
    discover_project_workflows,
    evaluate_handoff_quality,
)

VALID_WORKFLOW_DELTAS = ("auto", "unchanged", "update_existing", "add_new", "bootstrap")
DOC_UPDATE_REQUIRED_DELTAS = ("bootstrap", "add_new", "update_existing")
_REPO_MARKER_FILES = (
    ".git",
    "README.md",
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "docs/WORKFLOWS.md",
    "docs/workflows.md",
    "WORKFLOWS.md",
)


def has_real_repo_markers(workspace_path: Path | str) -> bool:
    """Return True when workspace_path looks like a real repository rather than an empty sandbox."""
    if not workspace_path:
        return False
    ws = Path(workspace_path)
    if not ws.is_dir():
        return False
    return any((ws / rel).exists() for rel in _REPO_MARKER_FILES)


def find_workflows_doc_path(workspace_path: Path | str) -> Path | None:
    """Locate existing primary docs/WORKFLOWS.md (or sibling) in workspace_path safely."""
    if not workspace_path:
        return None
    ws = Path(workspace_path)
    if not ws.is_dir():
        return None
    ws_res = ws.resolve()
    for rel in ("docs/WORKFLOWS.md", "docs/workflows.md", "WORKFLOWS.md"):
        cand = ws / rel
        if cand.is_file():
            try:
                if cand.resolve().is_relative_to(ws_res):
                    return cand
            except OSError:
                continue
    return None


def get_workflows_doc_fingerprint(workspace_path: Path | str) -> tuple[float, str]:
    """Return (mtime, sha256[:16]) for docs/WORKFLOWS.md, or (0.0, '') if absent."""
    doc = find_workflows_doc_path(workspace_path)
    if not doc:
        return 0.0, ""
    try:
        st = doc.stat()
        digest = hashlib.sha256(doc.read_bytes()).hexdigest()[:16]
        return float(st.st_mtime), digest
    except OSError:
        return 0.0, ""


def _invalid_explicit_wf_tokens(raw_ids: str) -> list[str]:
    bad: list[str] = []
    for tok in re.split(r"[\s,;]+", (raw_ids or "").strip()):
        if tok and not re.fullmatch(r"WF[-_ ]?0*([1-9]\d?)", tok, re.IGNORECASE):
            bad.append(tok)
    return bad


def normalize_workflow_ids(raw_ids: str, body: str = "") -> list[str]:
    """Normalize explicit WF-XX arguments or scan body mentions into canonical ['WF-01', ...] list."""
    found: list[str] = []
    explicit = (raw_ids or "").strip()
    sources = [explicit] if explicit else ([body] if body else [])
    for src in sources:
        for m in re.finditer(r"\bWF[-_ ]?0*([1-9]\d?)\b", str(src), re.IGNORECASE):
            tag = f"WF-{int(m.group(1)):02d}"
            if tag not in found:
                found.append(tag)
    return found[:12]


def resolve_workflow_delta(
    handoff_mode: str,
    workflow_delta: str,
    workflow_status: str,
    body: str = "",
    *,
    create_new_project: bool = False,
) -> str:
    """Resolve effective workflow_delta from caller arg, handoff_mode, and create_new_project."""
    mode = (handoff_mode or "feature_update").strip().lower()
    if mode == "new_project" or create_new_project:
        return "bootstrap"
    raw = (workflow_delta or "auto").strip().lower()
    if raw in ("unchanged", "update_existing", "add_new", "bootstrap"):
        return raw
    if mode == "release_closeout":
        return "unchanged"
    if mode == "bug_or_visual_fix":
        return "update_existing"
    return "unchanged"


def _gate_error(
    *,
    status: str,
    error: str,
    guidance: str,
    project_name: str,
    conv_id: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct a structured pre-flight error payload with REPLY_PROMPT_GUIDANCE and 1-tap chips."""
    sa = build_suggested_actions(
        "ready_to_run", target=project_name or "project", conv_id=conv_id, handoff_id="", is_running=False
    )
    out: dict[str, Any] = {
        "ok": False,
        "status": status,
        "error": error,
        "suggested_actions": sa,
        "assistant_guidance": f"{guidance}\n\n{cfg.REPLY_PROMPT_GUIDANCE}",
    }
    if extra:
        out.update(extra)
    return out


def _check_greenfield_gate(
    *,
    raw_body: str,
    user_terms: str,
    wf_ids: list[str],
    quality: dict[str, Any],
    project_name: str,
    conv_id: str,
) -> dict[str, Any] | None:
    """Gate 1: Require Who & Goal, Common Terms, and >=2 WF-XX flows for greenfield projects."""
    missing: list[str] = []
    if not quality.get("has_goal_or_why"):
        missing.append("Who & Goal (plain-language purpose and target user)")
    has_terms = bool(user_terms.strip()) or bool(
        re.search(r"(?:common\s+terms|glossary|everyday\s+words)", raw_body or "", re.IGNORECASE)
    )
    if not has_terms:
        missing.append("Common Terms (user's everyday vocabulary -> UI/system meaning)")
    flow_tags = {
        f"WF-{int(n):02d}"
        for n in re.findall(r"\bWF[-_ ]?0*([1-9]\d?)\b", raw_body or "", re.IGNORECASE)
    }
    all_flows = flow_tags | set(wf_ids)
    if len(all_flows) < 2:
        missing.append("WF-01 & WF-02+ workflows (>=2 numbered journeys with empty/error states & 390px/900px/1440px steps)")
    if not missing:
        return None
    questions = [
        "1. Who uses this tool and what single problem are we solving in one plain sentence?",
        "2. What everyday names do you call the main things on screen (buttons, tabs, metrics, statuses)?",
        "3. Walk through the first 2 tasks step by step (what you tap, see, empty/error states, on phone vs tablet/desktop).",
    ]
    return _gate_error(
        status="NEEDS_WORKFLOW_SPEC",
        error=f"Greenfield handoff missing plain-language workflow spec: {'; '.join(missing)}.",
        guidance="STOP and ask the user 2-3 short plain-language questions before scaffolding a new project (do not invent specs on their behalf). Re-call send_handoff_and_resume with Who & Goal, Common Terms (or `user_terms`), and >=2 flows (`WF-01`, `WF-02`).",
        project_name=project_name, conv_id=conv_id, extra={"missing": missing, "questions_for_user": questions},
    )


def _check_brownfield_baseline_gate(*, workspace_path: str, wf_info: dict[str, Any], eff_delta: str, raw_body: str, user_terms: str, wf_ids: list[str], project_name: str, conv_id: str) -> dict[str, Any] | None:
    """Gate 2: Require explicit workflow_delta='bootstrap' + starter WF-XX/terms when baseline missing."""
    has_starter = bool(wf_ids or re.search(r"\bWF-0*[1-9]\d?\b", raw_body or "", re.I)) and bool(
        user_terms.strip() or re.search(r"common\s+terms|glossary|what\s+the\s+user", raw_body or "", re.I)
    )
    if eff_delta != "bootstrap" or not has_starter:
        src = str(wf_info.get("source_file") or "none")
        return _gate_error(
            status="WORKFLOW_BOOTSTRAP_REQUIRED",
            error=f"Repository '{workspace_path}' requires docs/WORKFLOWS.md bootstrap (status=MISSING_BASELINE, workflow_delta='{eff_delta}', has_starter={has_starter}, fallback={src}).",
            guidance="Explain to the user that this repo has no `docs/WORKFLOWS.md` baseline yet. Confirm main user journeys (`WF-01..WF-NN`) and everyday terms, then re-call `send_handoff_and_resume` with `workflow_delta=\"bootstrap\"`, `user_terms`, and initial `WF-01`+ flows.",
            project_name=project_name, conv_id=conv_id, extra={"workflow_status": "MISSING_BASELINE", "workspace_path": workspace_path},
        )
    return None


def _check_plain_language_and_wf_bindings(*, raw_body: str, wf_info: dict[str, Any], eff_delta: str, wf_ids: list[str], invalid_explicit_ids: list[str] = (), has_explicit_ids: bool = False, quality: dict[str, Any], project_name: str, conv_id: str) -> dict[str, Any] | None:
    """Gate 3 & 4: Reject bare code dumps and enforce valid WF-XX bindings on READY repos."""
    if not quality.get("has_goal_or_why") or not quality.get("has_workflow") or quality.get("is_code_only_dump"):
        return _gate_error(
            status="HANDOFF_REJECTED_PLAIN_LANGUAGE",
            error=quality.get("advisory") or "Handoff lacks Goal & Why and plain-language user interaction expectations.",
            guidance="Rewrite the handoff in plain language covering `# User Goal & Why`, `Common Terms`, and `# What the User Sees, Taps & Expects` instead of bare file paths or line-number code edits.",
            project_name=project_name, conv_id=conv_id, extra={"quality": quality},
        )
    if invalid_explicit_ids:
        return _gate_error(
            status="HANDOFF_REJECTED_PLAIN_LANGUAGE",
            error=f"Malformed workflow_ids token(s): {list(invalid_explicit_ids)}. Use canonical WF-01..WF-99 IDs.",
            guidance="Pass valid `WF-01`..`WF-99` identifiers in `workflow_ids` (e.g. `workflow_ids=\"WF-01,WF-02\"`).",
            project_name=project_name, conv_id=conv_id, extra={"invalid_workflow_ids": list(invalid_explicit_ids)},
        )
    if wf_info.get("workflow_status") == "READY" and eff_delta not in ("bootstrap", "add_new"):
        known_ids = {str(w.get("id") or "") for w in wf_info.get("workflows") or [] if w.get("id")}
        if known_ids:
            unknown = [wid for wid in wf_ids if wid not in known_ids] if has_explicit_ids else []
            matched = [wid for wid in wf_ids if wid in known_ids]
            if not matched or unknown:
                known_str = ", ".join(sorted(known_ids))
                return _gate_error(
                    status="HANDOFF_REJECTED_PLAIN_LANGUAGE",
                    error=f"Missing or unknown workflow_ids for docs/WORKFLOWS.md (available: {known_str}; got: {wf_ids}).",
                    guidance=f"Bind this task to valid existing workflows ({known_str}) via `workflow_ids=\"WF-01,...\"` or declare `workflow_delta=\"add_new\"` when introducing a new user journey.",
                    project_name=project_name, conv_id=conv_id, extra={"available_workflow_ids": sorted(known_ids), "provided_workflow_ids": wf_ids},
                )
    return None


def build_workflow_injection_block(
    *,
    wf_info: dict[str, Any],
    wf_ids: list[str],
    eff_delta: str,
    user_terms: str = "",
    max_chars: int = 2400,
) -> str:
    """Build compact grounded Common Terms + matched WF-XX Markdown block for scratch/gemini_research_handoff.md."""
    src = str(wf_info.get("source_file") or "docs/WORKFLOWS.md")
    terms = list(wf_info.get("common_terms") or [])
    sections = dict(wf_info.get("sections") or {})
    if not wf_info.get("found") and not wf_ids and not user_terms.strip():
        if eff_delta in ("bootstrap", "add_new", "update_existing"):
            return f"### Grounded Workflow Delta (`{eff_delta}`)\n- Keep `docs/WORKFLOWS.md` updated cleanly for every user journey touched.\n\n---\n\n"
        return ""

    parts = [f"### Grounded Repository Workflows & Common Terms (`{src}` · `workflow_delta={eff_delta}`)"]
    if wf_ids:
        parts.append(f"- **Bound Workflows**: `{'`, `'.join(wf_ids)}`")
    if terms or user_terms.strip():
        parts.append("- **Common Terms**:")
        for item in terms[:8]:
            parts.append(f"  - **{item['term']}**: {item['meaning'][:140]}")
        if user_terms.strip():
            parts.append(f"  - **Caller Terms**: {user_terms.strip()[:260]}")

    matched_secs = [sections[wid] for wid in wf_ids if wid in sections]
    if not matched_secs and sections:
        matched_secs = [f"- **{w['id']}** — {w['title']}: {w['summary']}" for w in (wf_info.get("workflows") or [])[:6]]
    if matched_secs:
        parts.append("\n#### Referenced Workflow Baselines")
        rem = max(400, max_chars - len("\n".join(parts)) - 60)
        per = max(180, rem // max(1, len(matched_secs)))
        for sec in matched_secs[:4]:
            snippet = sec.strip()
            if len(snippet) > per:
                snippet = snippet[:per].rstrip() + "\n... [see docs/WORKFLOWS.md]"
            parts.append(snippet)

    out = "\n".join(parts).strip()
    if len(out) > max_chars:
        out = out[:max_chars - 24].rstrip() + "\n... [compacted]"
    return out + "\n\n---\n\n"


def validate_handoff_workflow_gates(
    *,
    raw_body: str,
    workspace_path: str,
    eff_handoff_mode: str,
    create_new_project: bool,
    workflow_ids: str = "",
    workflow_delta: str = "auto",
    user_terms: str = "",
    is_pure_closeout: bool = False,
    is_resume_staged: bool = False,
    conv_id: str = "",
    project_name: str = "",
    strict_workflow_gate: bool = False,
) -> dict[str, Any]:
    """Run all 4 plain-language workflow pre-flight gates and build the grounded injection block."""
    wf_info = discover_project_workflows(workspace_path)
    wf_status = str(wf_info.get("workflow_status") or "MISSING_BASELINE")
    wf_ids = normalize_workflow_ids(workflow_ids, raw_body)
    invalid_explicit_ids = _invalid_explicit_wf_tokens(workflow_ids)
    has_explicit_ids = bool((workflow_ids or "").strip())
    delta_arg = (workflow_delta or "auto").strip().lower()
    if delta_arg not in VALID_WORKFLOW_DELTAS:
        delta_arg = "auto"
    eff_delta = resolve_workflow_delta(
        eff_handoff_mode, delta_arg, wf_status, raw_body, create_new_project=create_new_project
    )

    if is_pure_closeout or (is_resume_staged and not invalid_explicit_ids and not strict_workflow_gate):
        wf_block = "" if is_pure_closeout else build_workflow_injection_block(
            wf_info=wf_info, wf_ids=wf_ids, eff_delta=eff_delta, user_terms=user_terms,
        )
        return {
            "guard_error": None,
            "wf_info": wf_info,
            "workflow_status": wf_status,
            "workflow_ids": wf_ids,
            "eff_delta": "unchanged" if is_pure_closeout else eff_delta,
            "quality": {"has_goal_or_why": True, "has_workflow": True, "advisory": "", "quality_score": 1.0},
            "workflow_block": wf_block,
        }

    quality = evaluate_handoff_quality(raw_body, is_closeout=False)
    is_mcp_call = cfg._MCP_REQUEST_CTX.get() is not None
    explicit_args = bool(has_explicit_ids or user_terms.strip() or delta_arg != "auto")
    is_real_repo = has_real_repo_markers(workspace_path)
    is_new_proj = eff_handoff_mode == "new_project" or create_new_project

    guard_error: dict[str, Any] | None = None
    if is_new_proj and (strict_workflow_gate or is_mcp_call or explicit_args or (eff_handoff_mode == "new_project" and create_new_project)):
        guard_error = _check_greenfield_gate(
            raw_body=raw_body, user_terms=user_terms, wf_ids=wf_ids,
            quality=quality, project_name=project_name, conv_id=conv_id,
        )
    elif not is_new_proj and wf_status == "MISSING_BASELINE" and (strict_workflow_gate or explicit_args or (is_mcp_call and is_real_repo)):
        guard_error = _check_brownfield_baseline_gate(
            workspace_path=workspace_path, wf_info=wf_info, eff_delta=eff_delta,
            raw_body=raw_body, user_terms=user_terms, wf_ids=wf_ids, project_name=project_name, conv_id=conv_id,
        )

    if not guard_error and (strict_workflow_gate or explicit_args or (is_mcp_call and (is_real_repo or is_new_proj))):
        guard_error = _check_plain_language_and_wf_bindings(
            raw_body=raw_body, wf_info=wf_info, eff_delta=eff_delta,
            wf_ids=wf_ids, invalid_explicit_ids=invalid_explicit_ids, has_explicit_ids=has_explicit_ids,
            quality=quality, project_name=project_name, conv_id=conv_id,
        )

    if guard_error:
        return {"guard_error": guard_error, "wf_info": wf_info, "workflow_status": wf_status, "workflow_ids": wf_ids, "eff_delta": eff_delta, "quality": quality, "workflow_block": ""}

    wf_block = build_workflow_injection_block(
        wf_info=wf_info, wf_ids=wf_ids, eff_delta=eff_delta, user_terms=user_terms,
    )
    return {
        "guard_error": None,
        "wf_info": wf_info,
        "workflow_status": wf_status,
        "workflow_ids": wf_ids,
        "eff_delta": eff_delta,
        "quality": quality,
        "workflow_block": wf_block,
    }


def _git_touched_workflows(ws: Path, created_at_iso: str) -> bool:
    """Return True if git shows docs/WORKFLOWS.md modified in working tree or committed since created_at."""
    if not (ws / ".git").exists():
        return False
    paths = ("docs/WORKFLOWS.md", "docs/workflows.md", "WORKFLOWS.md")
    try:
        st = subprocess.run(
            ["git", "-C", str(ws), "status", "--porcelain", "--", *paths],
            capture_output=True, text=True, timeout=4, check=False,
        )
        if st.returncode == 0 and st.stdout.strip():
            return True
        if created_at_iso:
            lg = subprocess.run(
                ["git", "-C", str(ws), "log", "--name-only", "--format=", f"--since={created_at_iso}", "--", *paths],
                capture_output=True, text=True, timeout=4, check=False,
            )
            if lg.returncode == 0 and lg.stdout.strip():
                return True
    except Exception:
        pass
    return False


def verify_workflow_doc_updated_for_completion(ticket: dict[str, Any] | None) -> dict[str, Any]:
    """Gate WF-05 completion when ticket requires bootstrap/add_new/update_existing docs/WORKFLOWS.md edit."""
    if not ticket:
        return {"ok": True}
    delta = str(ticket.get("workflow_delta") or "unchanged").strip().lower()
    if delta not in DOC_UPDATE_REQUIRED_DELTAS:
        return {"ok": True}

    ws_str = str(ticket.get("workspace_path") or "").strip()
    if not ws_str:
        return {
            "ok": False,
            "status": "WORKFLOW_DOC_NOT_UPDATED",
            "handoff_id": ticket.get("handoff_id", ""),
            "workflow_delta": delta,
            "error": "Ticket lacks workspace_path; cannot verify docs/WORKFLOWS.md update.",
        }
    ws = Path(ws_str)
    doc = find_workflows_doc_path(ws)
    if not doc or not doc.read_text(encoding="utf-8", errors="replace").strip():
        return {
            "ok": False,
            "status": "WORKFLOW_DOC_NOT_UPDATED",
            "handoff_id": ticket.get("handoff_id", ""),
            "workflow_delta": delta,
            "error": (
                f"Ticket {ticket.get('handoff_id')} has workflow_delta='{delta}', "
                f"but '{ws / 'docs' / 'WORKFLOWS.md'}' does not exist or is empty. "
                "Create/update docs/WORKFLOWS.md with Common Terms and WF-XX journeys before marking COMPLETED."
            ),
        }

    cur_mtime, cur_sha = get_workflows_doc_fingerprint(ws)
    prev_sha = str(ticket.get("workflows_doc_sha256") or "")
    prev_mtime = float(ticket.get("workflows_doc_mtime") or 0.0)
    created_iso = str(ticket.get("created_at") or "")
    if prev_sha:
        if cur_sha != prev_sha:
            return {"ok": True}
    else:
        if delta == "bootstrap":
            return {"ok": True}
        if prev_mtime > 0.0 and cur_mtime > prev_mtime + 0.001:
            return {"ok": True}
        if created_iso:
            try:
                c_ep = datetime.fromisoformat(created_iso.replace("Z", "+00:00")).timestamp()
                if cur_mtime > c_ep + 0.001:
                    return {"ok": True}
            except Exception:
                pass
        if _git_touched_workflows(ws, created_iso):
            return {"ok": True}

    return {
        "ok": False,
        "status": "WORKFLOW_DOC_NOT_UPDATED",
        "handoff_id": ticket.get("handoff_id", ""),
        "workflow_delta": delta,
        "error": (
            f"Ticket {ticket.get('handoff_id')} declared workflow_delta='{delta}', "
            "but docs/WORKFLOWS.md was not created or modified since ticket creation. "
            "Update docs/WORKFLOWS.md first, then re-call praxis_update_handoff(status='COMPLETED')."
        ),
    }
