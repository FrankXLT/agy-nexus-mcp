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

def get_session_telemetry(conv_id: str, brain_dir: Path = AGY_BRAIN_DIR, step_count: int = 0) -> dict[str, Any]:
    """Retrieve compaction count, active step pacing, and health warning for a conversation."""
    if not conv_id:
        return {"compaction_count": 0, "avg_step_seconds": 0.0, "session_health_warning": ""}
    tpath = brain_dir / conv_id / ".system_generated" / "logs" / "transcript.jsonl"
    avg_s, _, compactions = calculate_step_pacing(tpath)
    warning = generate_session_health_warning(step_count, compactions)
    return {
        "compaction_count": compactions,
        "avg_step_seconds": avg_s,
        "session_health_warning": warning,
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
