#!/usr/bin/env python3
"""agy_nexus.session_status — Session Health, In-Flight Mutex & Compaction Telemetry Engine."""
from __future__ import annotations
from datetime import datetime
import json
from pathlib import Path
import re
import sqlite3
import time
from typing import Any
from . import __version__
from agy_nexus.config import (
    AGY_BG_DIR,
    AGY_BRAIN_DIR,
    AGY_DB_FILE,
    SESSION_STATE,
)

def count_session_compactions(conv_id: str, brain_dir: Path = AGY_BRAIN_DIR) -> int:
    """Count context compaction events ('# Resuming from a compaction') in transcript.jsonl."""
    if not conv_id:
        return 0
    tpath = brain_dir / conv_id / ".system_generated" / "logs" / "transcript.jsonl"
    if not tpath.is_file():
        return 0
    try:
        count = 0
        with open(tpath, "rb") as f:
            for line in f:
                if b"# Resuming from a compaction" in line:
                    count += 1
        return count
    except Exception:
        return 0

def calculate_step_pacing(tpath: Path, max_idle_gap: float = 600.0) -> tuple[float, int, int]:
    """Calculate (avg_step_seconds, active_step_count, compaction_count) from transcript.jsonl.

    Filters out idle gaps > max_idle_gap seconds so multi-hour/multi-day pauses do not distort active execution pacing.
    """
    if not tpath.is_file():
        return 0.0, 0, 0
    active_seconds = 0.0
    step_pairs = 0
    prev_dt = None
    compactions = 0
    try:
        with open(tpath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if "# Resuming from a compaction" in line:
                    compactions += 1
                m = re.search(r'"created_at":\s*"([^"]+)"', line)
                if m:
                    try:
                        cur_dt = datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))
                        if prev_dt:
                            diff = (cur_dt - prev_dt).total_seconds()
                            if 0 <= diff <= max_idle_gap:
                                active_seconds += diff
                                step_pairs += 1
                        prev_dt = cur_dt
                    except Exception:
                        continue
        avg_s = round(active_seconds / max(1, step_pairs), 2) if step_pairs > 0 else 0.0
        return avg_s, step_pairs, compactions
    except Exception:
        return 0.0, 0, compactions

def generate_session_health_warning(step_count: int, compaction_count: int) -> str:
    """Generate session rotation advisory if step count or compaction count exceeds safety ceilings."""
    reasons: list[str] = []
    if step_count > 1500:
        reasons.append(f"step_count={step_count} (>1,500)")
    if compaction_count >= 10:
        reasons.append(f"compaction_count={compaction_count} (>=10)")
    if reasons:
        return (
            f"SESSION HEALTH WARNING: This session has accumulated {', '.join(reasons)}. "
            "Context compaction decay and Cortex tool call failures occur frequently in mega-sessions. "
            "It is strongly advised to rotate to a fresh session via create_new_session=True with a clean architectural handoff."
        )
    return ""

def check_context_exceeded(conv_id: str, brain_dir: Path = AGY_BRAIN_DIR) -> bool:
    """Check if the session encountered a genuine runtime 'Context window exceeded' error in recent transcript turns.

    Ignores user prompts, subagent tool arguments, git diffs, and conversational mentions.
    """
    if not conv_id:
        return False
    tpath = brain_dir / conv_id / ".system_generated" / "logs" / "transcript.jsonl"
    if not tpath.is_file():
        return False
    try:
        # Read the tail of the transcript file
        with open(tpath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        for line in reversed(lines[-60:]):
            if "Context window exceeded" not in line and "context_length_exceeded" not in line:
                continue
            try:
                entry = json.loads(line)
            except Exception:
                continue
            # Ignore user input and prompts
            if entry.get("type") in ("USER_INPUT", "user") or entry.get("source") in ("USER_EXPLICIT", "user"):
                continue
            status = str(entry.get("status") or "").upper()
            content = str(entry.get("content") or "")
            # Ignore diffs and tool output blocks
            if "[diff_block" in content or "diff --git" in content or "replace_file_content" in content:
                continue
            # Check explicit ERROR status or tool call execution failure
            if status == "ERROR":
                err_text = str(entry.get("error") or content)
                if "Context window exceeded" in err_text or "context_length_exceeded" in err_text:
                    return True
            # Real runtime tool failure emitted by model/planner
            if content.strip().startswith("An error occurred while calling the tool") and "Context window exceeded" in content:
                return True
            for k in ("error", "stateDetail", "failureMessage", "error_message"):
                v = str(entry.get(k) or "")
                if ("Context window exceeded" in v or "context_length_exceeded" in v) and "[diff_block" not in v:
                    return True
        return False
    except Exception:
        return False

def get_session_context_budget(step_count: int, context_exceeded: bool = False) -> str:
    """Classify session context budget into GREEN, AMBER, or ROLLOVER_RECOMMENDED."""
    if step_count > 350 or context_exceeded:
        return "ROLLOVER_RECOMMENDED (>350 steps or context exceeded)"
    if step_count >= 250:
        return "AMBER (250-350 steps)"
    return "GREEN (<250 steps)"

def get_session_telemetry(conv_id: str, brain_dir: Path = AGY_BRAIN_DIR, step_count: int = 0) -> dict[str, Any]:
    """Retrieve compaction count, active step pacing, and health warning for a conversation."""
    if not conv_id:
        return {
            "compaction_count": 0, "avg_step_seconds": 0.0, "session_health_warning": "",
            "context_budget": "GREEN (<250 steps)", "context_exceeded": False,
        }
    tpath = brain_dir / conv_id / ".system_generated" / "logs" / "transcript.jsonl"
    avg_s, _, compactions = calculate_step_pacing(tpath)
    warning = generate_session_health_warning(step_count, compactions)
    ctx_exceeded = check_context_exceeded(conv_id, brain_dir)
    budget = get_session_context_budget(step_count, ctx_exceeded)
    return {
        "compaction_count": compactions,
        "avg_step_seconds": avg_s,
        "session_health_warning": warning,
        "context_budget": budget,
        "context_exceeded": ctx_exceeded,
    }

def check_inflight_handoff_mutex(
    conv_id: str,
    bg_dir: Path = AGY_BG_DIR,
    db_status_info: dict[str, Any] | None = None,
    max_age_seconds: int = 300,
) -> dict[str, Any] | None:
    """Return an ALREADY_RUNNING collision payload if conv_id has a background job started < max_age_seconds ago."""
    if not conv_id or not bg_dir.is_dir():
        return None
    now_ts = time.time()
    try:
        job_files = sorted(bg_dir.glob("job-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for jf in job_files:
            try:
                jdata = json.loads(jf.read_text(encoding="utf-8"))
                if jdata.get("conversation_id") == conv_id:
                    age = now_ts - jf.stat().st_mtime
                    if age < max_age_seconds:
                        is_running = True
                        if db_status_info is not None:
                            is_running = bool(db_status_info.get("is_running", True))
                        if is_running:
                            job_id = jdata.get("job_id", jf.stem)
                            return {
                                "status": "ALREADY_RUNNING",
                                "active_job_id": job_id,
                                "elapsed_seconds": round(age, 1),
                                "started_at": jdata.get("started_at", ""),
                                "message": (
                                    f"Target session {conv_id[:8]} is currently RUNNING with background job "
                                    f"'{job_id}' started {round(age, 1)}s ago (< {max_age_seconds}s). "
                                    "Handoff withheld to prevent duplicate planner wakeup collisions. "
                                    "Call manage_background_run(action='status') to monitor progress, or pass force_interrupt=True to override."
                                ),
                            }
            except Exception:
                continue
    except Exception:
        pass
    return None

def _get_selected_session_quick_status(target_conv_id: str = "") -> dict[str, Any]:
    """Return a compact status summary of target_conv_id (or selected_session), its mode, and any concurrent writers on the same workspace."""
    conv_id = (target_conv_id or SESSION_STATE.get("selected_session") or "").strip()
    if not conv_id:
        return {}
    ws_path = str(SESSION_STATE.get("session_workspace_map", {}).get(conv_id) or SESSION_STATE.get("selected_workspace") or "")
    info: dict[str, Any] = {"conversation_id": conv_id, "workspace_path": ws_path}
    info["installed_version"] = __version__
    is_running = False
    other_running: list[dict[str, str]] = []
    if AGY_DB_FILE.is_file():
        try:
            con = sqlite3.connect(f"file:{AGY_DB_FILE}?mode=ro", uri=True)
            row = con.execute(
                "SELECT status, step_count, last_modified_time, not_fully_idle, killed, workspace_uris FROM conversation_summaries WHERE conversation_id = ?",
                (conv_id,),
            ).fetchone()
            if row:
                raw_status = str(row[0] or "")
                is_running = "RUNNING" in raw_status or bool(row[3])
                if not ws_path and row[5]:
                    try:
                        uris = json.loads(row[5])
                        if uris and isinstance(uris, list):
                            ws_path = re.sub(r"^file://", "", str(uris[0])).rstrip("/")
                            info["workspace_path"] = ws_path
                    except Exception:
                        pass
                info["db_status"] = raw_status
                info["step_count"] = int(row[1] or 0)
                info["last_modified"] = str(row[2] or "")
                info["is_running"] = is_running
                info["summary"] = (
                    "RUNNING_IN_BACKGROUND"
                    if is_running
                    else "COMPLETED_AND_IDLE (Antigravity finished; do NOT call manage_background_run)"
                )
            if ws_path:
                run_rows = con.execute(
                    "SELECT conversation_id, title, workspace_uris FROM conversation_summaries WHERE (status = 'CASCADE_RUN_STATUS_RUNNING' OR not_fully_idle = 1) AND (parent_conversation_id IS NULL OR parent_conversation_id = '') LIMIT 20"
                ).fetchall()
                for r_cid, r_title, r_uris in run_rows:
                    if str(r_cid) != conv_id and ws_path in str(r_uris or ""):
                        other_running.append({"conversation_id": str(r_cid), "title": str(r_title or "")})
            con.close()
        except Exception:
            pass
    if other_running:
        info["other_running_sessions"] = other_running
    info["mode"] = (
        "WORKTREE" if "/worktrees/" in ws_path
        else ("MAIN WRITER" if is_running else ("SHARED (READ-ONLY)" if other_running else "MAIN TREE"))
    )
    if AGY_BG_DIR.is_dir():
        try:
            job_files = sorted(AGY_BG_DIR.glob("job-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            for jf in job_files[:5]:
                jdata = json.loads(jf.read_text(encoding="utf-8"))
                if jdata.get("conversation_id") == conv_id:
                    info["latest_job_id"] = jdata.get("job_id", jf.stem)
                    info["latest_job_started_at"] = jdata.get("started_at", "")
                    break
        except Exception:
            pass
    # Attach telemetry (compactions, pacing, health warning)
    telem = get_session_telemetry(conv_id, AGY_BRAIN_DIR, step_count=info.get("step_count", 0))
    info.update(telem)
    return info

def extract_prior_session_baton(
    prev_conv_id: str, brain_dir: Path = AGY_BRAIN_DIR, ws_path: str = ""
) -> str:
    """Extract a compact Prior Session Baton from a previous session's brain folder and git status."""
    if not prev_conv_id:
        return ""
    p_dir = brain_dir / prev_conv_id
    if not p_dir.is_dir():
        return ""

    parts: list[str] = [
        f"## Prior Session Baton ({prev_conv_id})",
        f"- **Previous Session ID**: `{prev_conv_id}`",
    ]

    t_file = p_dir / "task.md"
    if t_file.is_file():
        try:
            t_text = t_file.read_text(encoding="utf-8", errors="replace")
            t_lines = [l.strip() for l in t_text.splitlines() if l.strip() and l.strip().startswith(("#", "- [x]", "- [/]", "- [ ]"))]
            t_summary = "\n".join(t_lines[:16]) if t_lines else t_text[:500]
            parts.append(f"- **Prior Task State**:\n{t_summary}")
        except Exception:
            pass

    w_file = p_dir / "walkthrough.md"
    if w_file.is_file():
        try:
            w_text = w_file.read_text(encoding="utf-8", errors="replace")
            w_lines = [l.strip() for l in w_text.splitlines() if l.strip() and l.strip().startswith(("#", "### "))]
            w_summary = "\n".join(w_lines[:8]) if w_lines else w_text[:400]
            parts.append(f"- **Prior Walkthrough Highlights**:\n{w_summary}")
        except Exception:
            pass

    git_st = ""
    if ws_path and Path(ws_path).is_dir():
        try:
            import subprocess
            proc = subprocess.run(
                ["git", "-c", "safe.directory=*", "status", "--short"],
                cwd=ws_path, capture_output=True, text=True, timeout=3, check=False,
            )
            git_st = proc.stdout.strip()
        except Exception:
            pass
    if git_st:
        st_lines = git_st.splitlines()
        if len(st_lines) > 20:
            git_st = "\n".join(st_lines[:20]) + f"\n... [{len(st_lines) - 20} more files]"
        parts.append(f"- **Current Git Working Tree Status**:\n```text\n{git_st}\n```")

    return "\n\n".join(parts) + "\n\n"

def find_latest_session_for_workspace(ws_path: str, db_file: Path = AGY_DB_FILE) -> str:
    """Find the most recent conversation_id for a given workspace path."""
    if not ws_path or not db_file.is_file():
        return ""
    try:
        con = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
        rows = con.execute(
            "SELECT conversation_id, workspace_uris FROM conversation_summaries WHERE parent_conversation_id IS NULL OR parent_conversation_id = '' ORDER BY last_modified_time DESC LIMIT 40"
        ).fetchall()
        con.close()
        for cid, uris_raw in rows:
            if uris_raw:
                try:
                    uris = json.loads(uris_raw)
                    for u in uris:
                        clean_u = re.sub(r"^file://", "", str(u)).rstrip("/")
                        if clean_u == ws_path or clean_u in ws_path or ws_path in clean_u:
                            return str(cid)
                except Exception:
                    if ws_path in str(uris_raw):
                        return str(cid)
    except Exception:
        pass
    return ""

