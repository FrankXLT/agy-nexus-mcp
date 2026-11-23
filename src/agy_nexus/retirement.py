#!/usr/bin/env python3
"""agy_nexus.retirement — Terminal Session Closeout, In-Place Retirement & 5-Phase Action Engine."""
from __future__ import annotations

from datetime import datetime, timezone
import html
import json
from pathlib import Path
import re
import subprocess
from typing import Any

from agy_nexus.config import AGY_BRAIN_DIR


def is_session_retired(conv_id: str, brain_dir: Path | None = None) -> bool:
    """Check if a session has an on-disk RETIRED.json manifest in its brain folder."""
    return bool(conv_id and ((brain_dir or AGY_BRAIN_DIR) / conv_id / "RETIRED.json").is_file())


def get_retirement_record(conv_id: str, brain_dir: Path | None = None) -> dict[str, Any] | None:
    """Read RETIRED.json from session brain folder if present."""
    if not conv_id:
        return None
    target = (brain_dir or AGY_BRAIN_DIR) / conv_id / "RETIRED.json"
    if not target.is_file():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8", errors="replace"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def record_session_retirement(
    conv_id: str,
    brain_dir: Path | None = None,
    final_commit_sha: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist RETIRED.json manifest in session brain folder with timestamp and final commit SHA."""
    if not conv_id:
        return {"ok": False, "error": "Missing conversation_id"}
    sess_dir = (brain_dir or AGY_BRAIN_DIR) / conv_id
    sess_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "ok": True,
        "conversation_id": conv_id,
        "retired_at": datetime.now(timezone.utc).isoformat(),
        "final_commit_sha": (final_commit_sha or "").strip(),
    }
    if metadata and isinstance(metadata, dict):
        payload.update(metadata)
    try:
        (sess_dir / "RETIRED.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        try:
            from agy_nexus.config import AGY_BG_DIR
            from agy_nexus.handoff_queue import reconcile_completed_tickets
            reconcile_completed_tickets(AGY_BG_DIR, brain_dir=brain_dir or AGY_BRAIN_DIR)
        except Exception:
            pass
        return payload
    except Exception as e:
        return {"ok": False, "error": f"Failed writing RETIRED.json: {e}"}


def is_closeout_intent(research_markdown: str = "", retire_session: bool = False, continuity: str = "") -> bool:
    """Detect if handoff intent indicates final closeout, publishing, or retirement."""
    if retire_session or (continuity or "").strip().lower() == "closeout":
        return True
    raw = (research_markdown or "").lower()
    closeout_keywords = (
        "closeout", "final publish", "release publish", "tag release",
        "clean up, push & deploy", "clean up & commit", "retire session", "retire",
    )
    return any(k in raw for k in closeout_keywords)


def infer_continuity_intent(
    research_markdown: str = "",
    allow_chained_publish: bool = False,
    is_clean_seam: bool = True,
    retire_session: bool = False,
) -> str:
    """Infer continuity intent ('closeout', 'continuation', 'new_topic') from handoff text and state."""
    if allow_chained_publish or retire_session or is_closeout_intent(research_markdown, retire_session):
        return "closeout"
    raw = (research_markdown or "").lower()
    if any(k in raw for k in ("v3.0.0", "new sprint", "phase 2", "next epic")) or re.search(r"\bv\d+\.\d+\.\d+\b", raw):
        return "new_topic"
    return "new_topic" if (is_clean_seam and (raw.startswith("#") or "handshake" in raw)) else "continuation"


def get_closeout_directives(
    ws_path: str = "",
    conv_id: str = "",
    retire_after_closeout: bool = False,
) -> str:
    """Generate Markdown directives for terminal session closeout and workspace cleanup."""
    cid_hint = conv_id or "<conv_id>"
    retire_line = (
        f"- **Deferred Final-Step Retirement (`retire_after_closeout=True`)**: Do NOT retire mid-run. Only **AFTER** `git commit` and `git push` succeed, call `record_session_retirement('{cid_hint}', final_commit_sha=<HEAD_SHA>)` (or write `brain/{cid_hint}/RETIRED.json` with `retired_at` and `final_commit_sha=<HEAD_SHA>`)."
        if retire_after_closeout
        else f"- **Persist RETIRED.json**: Write `brain/{cid_hint}/RETIRED.json` with `retired_at` timestamp and `final_commit_sha`."
    )
    directives = [
        "### Terminal Session Closeout & In-Place Retirement Directives",
        "- **Worktree Pruning**: Run `git worktree prune` to purge any detached or stale worktree references.",
        "- **Temp Cleanup**: Remove untracked verification temp files (e.g. scratch scripts and temporary logs).",
        "- **Mark Tickets Completed**: Ensure all active staged handoff tickets for this repository are marked `COMPLETED`.",
        retire_line,
    ]
    if ws_path:
        directives.append(f"- **Workspace Scope**: `{ws_path}`")
    return "\n".join(directives) + "\n\n"


def extract_prior_session_baton(
    prev_conv_id: str,
    brain_dir: Path | None = None,
    ws_path: str = "",
) -> str:
    """Extract a compact Prior Session Baton from a previous session's brain folder and git status."""
    if not prev_conv_id:
        return ""
    p_dir = (brain_dir or AGY_BRAIN_DIR) / prev_conv_id
    if not p_dir.is_dir():
        return ""
    parts = [f"## Prior Session Baton ({prev_conv_id})", f"- **Previous Session ID**: `{prev_conv_id}`"]
    t_file = p_dir / "task.md"
    if t_file.is_file():
        try:
            t_text = t_file.read_text(encoding="utf-8", errors="replace")
            t_lines = [l.strip() for l in t_text.splitlines() if l.strip().startswith(("#", "- [x]", "- [/]", "- [ ]"))]
            parts.append(f"- **Prior Task State**:\n" + ("\n".join(t_lines[:16]) if t_lines else t_text[:500]))
        except Exception:
            pass
    w_file = p_dir / "walkthrough.md"
    if w_file.is_file():
        try:
            w_text = w_file.read_text(encoding="utf-8", errors="replace")
            w_lines = [l.strip() for l in w_text.splitlines() if l.strip().startswith(("#", "### "))]
            parts.append(f"- **Prior Walkthrough Highlights**:\n" + ("\n".join(w_lines[:8]) if w_lines else w_text[:400]))
        except Exception:
            pass
    h_file = p_dir / "scratch" / "gemini_research_handoff.md"
    if h_file.is_file():
        try:
            from agy_nexus.workflow_baseline import extract_user_intent_from_handoff
            h_text = h_file.read_text(encoding="utf-8", errors="replace")
            intent_summary = extract_user_intent_from_handoff(h_text, max_chars=1200)
            if intent_summary:
                parts.append(f"- **Prior User Goal & Workflow Context**:\n{intent_summary}")
        except Exception:
            pass
    if ws_path and Path(ws_path).is_dir():
        try:
            proc = subprocess.run(["git", "-c", "safe.directory=*", "status", "--short"], cwd=ws_path, capture_output=True, text=True, timeout=3, check=False)
            git_st = proc.stdout.strip()
            if git_st:
                st_lines = git_st.splitlines()
                if len(st_lines) > 20:
                    git_st = "\n".join(st_lines[:20]) + f"\n... [{len(st_lines) - 20} more files]"
                parts.append(f"- **Current Git Working Tree Status**:\n```text\n{git_st}\n```")
        except Exception:
            pass
    return "\n\n".join(parts) + "\n\n"


def _clean_chip_text(val: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f-\x9f\ufffe\uffff]+", " ", str(val or ""))).strip()


def _elicit_group(msg: str, items: list[tuple[str, str]]) -> str:
    esc = lambda s: html.escape(_clean_chip_text(s), quote=True)
    inner = "".join(f'<Elicitation label="{esc(lbl)}" query="{esc(qry)}" />' for lbl, qry in items)
    return f'<ElicitationsGroup message="{esc(msg)}">{inner}</ElicitationsGroup>'


def build_suggested_actions(
    phase: str, target: str = "", conv_id: str = "", step_count: int = 0,
    catches_count: int = 0, is_running: bool = False, handoff_id: str = "",
) -> dict[str, Any]:
    """Generate job-focused 1-tap Yes transitions and @Agy Nexus Mcp XML reply chips."""
    tgt = _clean_chip_text(target) or "target"
    tgt_short = tgt if len(tgt) <= 24 else tgt[:21] + "..."
    cid, hid, p_norm = _clean_chip_text(conv_id), _clean_chip_text(handoff_id), _clean_chip_text(phase).lower()
    ref_lbl = hid or tgt_short
    if p_norm == "retired" and not is_running:
        prompt = "Start next task or view session tree?"
        q1 = "@Agy Nexus Mcp Show get_session_tree(include_stats=True, style='rich') across workspaces."
        q2 = f"@Agy Nexus Mcp Inspect {tgt} workspace for the next task."
        xml = _elicit_group("Session retired cleanly — what next?", [("View active session tree", q1), (f"Start a fresh session on {tgt_short}", q2)])
        return {"phase": "retired", "prompt": prompt, "actions": [prompt], "options": [{"label": "Yes", "value": q1}, {"label": f"Inspect {tgt_short}", "value": q2}], "followup_xml": xml}
    if p_norm == "in_flight" or is_running:
        prompt = "Check in on the build?"
        ctx_meta = f" ({hid}, {tgt})" if hid else f" ({tgt})"
        q1 = f"@Agy Nexus Mcp Check in on {cid}{ctx_meta} to inspect build progress, visual captures, and test status." if cid else (f"@Agy Nexus Mcp Check in on {hid or tgt} build" if (hid or tgt != "target") else "@Agy Nexus Mcp Check in on the build")
        lbl = f"Check in on {tgt_short} build" if tgt != "target" else "Check in on the build"
        return {"phase": "in_flight", "prompt": prompt, "actions": [prompt], "options": [{"label": "Yes", "value": q1}], "followup_xml": f'<FollowUp label="{html.escape(_clean_chip_text(lbl), quote=True)}" query="{html.escape(_clean_chip_text(q1), quote=True)}" />'}
    if p_norm in ("ready_to_ship", "audit_clean", "high_step_retirement") or (step_count or 0) >= 900:
        prompt = f"Ship {tgt} to GitHub?"
        q1 = f"@Agy Nexus Mcp Run release_closeout on {cid} ({tgt}, allow_chained_publish=True, retire_session=True) to verify tests, commit, tag, push to GitHub, and retire the session." if cid else f"@Agy Nexus Mcp Ship {tgt} to GitHub"
        q2 = f"@Agy Nexus Mcp Inspect git diff on {cid or tgt}"
        xml = _elicit_group(f"Ready to ship {tgt_short} or make adjustments?", [(f"Ship {tgt_short} to GitHub & retire session", q1), (f"Inspect git diff on {tgt_short}", q2)])
        return {"phase": "ready_to_ship", "prompt": prompt, "actions": [prompt], "options": [{"label": "Yes", "value": q1}, {"label": f"Inspect git diff on {tgt_short}", "value": q2}], "followup_xml": xml}
    prompt = "Run these changes and update the live preview?"
    ctx_run = f" (session {cid})" if cid else ""
    q1 = f"@Agy Nexus Mcp Launch {hid or tgt} headlessly on {tgt}{ctx_run} and update the live preview."
    q2 = f"@Agy Nexus Mcp Check in on {hid or cid or tgt}"
    xml = _elicit_group(f"How would you like to run {ref_lbl}?", [(f"Launch {ref_lbl} headlessly now", q1), ("Check in after running in IDE", q2)])
    return {"phase": "ready_to_run", "prompt": prompt, "actions": [prompt], "options": [{"label": "Yes", "value": q1}, {"label": "Check in after running in IDE", "value": q2}], "followup_xml": xml}
