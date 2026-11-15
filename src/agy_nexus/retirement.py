#!/usr/bin/env python3
"""agy_nexus.retirement — Terminal Session Closeout, In-Place Retirement & 5-Phase Action Engine."""
from __future__ import annotations

from datetime import datetime, timezone
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


def get_closeout_directives(ws_path: str = "") -> str:
    """Generate Markdown directives for terminal session closeout and workspace cleanup."""
    directives = [
        "### Terminal Session Closeout & In-Place Retirement Directives",
        "- **Worktree Pruning**: Run `git worktree prune` to purge any detached or stale worktree references.",
        "- **Temp Cleanup**: Remove untracked verification temp files (e.g. scratch scripts and temporary logs).",
        "- **Mark Tickets Completed**: Ensure all active staged handoff tickets for this repository are marked `COMPLETED`.",
        "- **Persist RETIRED.json**: Write `brain/<conv_id>/RETIRED.json` with `retired_at` timestamp and `final_commit_sha`.",
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


def build_suggested_actions(
    phase: str,
    target: str = "",
    conv_id: str = "",
    step_count: int = 0,
    catches_count: int = 0,
    is_running: bool = False,
) -> dict[str, Any]:
    """Generate job-focused 1-tap Yes transitions for Gemini clients."""
    tgt = target.strip() or "target"
    p_norm = (phase or "").strip().lower()

    if p_norm == "in_flight" or is_running:
        prompt = "Check in on the build?"
        return {
            "phase": "in_flight",
            "prompt": prompt,
            "actions": [prompt],
            "options": [{"label": "Yes", "value": f"Check in on {tgt} build" if tgt != "target" else "Check in on the build"}],
        }
    if p_norm in ("ready_to_ship", "audit_clean", "high_step_retirement") or step_count >= 900:
        prompt = f"Ship {tgt} to GitHub?"
        return {
            "phase": "ready_to_ship",
            "prompt": prompt,
            "actions": [prompt],
            "options": [{"label": "Yes", "value": f"Ship {tgt} to GitHub"}],
        }
    prompt = "Run these changes and update the live preview?"
    return {
        "phase": "ready_to_run",
        "prompt": prompt,
        "actions": [prompt],
        "options": [{"label": "Yes", "value": f"Run changes on {tgt}" if tgt != "target" else "Run these changes"}],
    }
