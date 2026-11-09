#!/usr/bin/env python3
"""agy_nexus.sessions — SQLite Session Discovery & Live Status Helpers."""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
import time
from typing import Any
from agy_nexus.config import (
    AGY_BG_DIR,
    AGY_BRAIN_DIR,
    AGY_CONFIG_DIR,
    AGY_DB_FILE,
    AGY_GITLAB_DIR,
    AGY_PRESENCE_DIR,
    SESSION_STATE,
)
from agy_nexus.stats import extract_pending_approval

def _load_projects_map() -> dict[str, dict[str, Any]]:
    """Read Antigravity project JSON files from AGY_CONFIG_DIR/projects."""
    proj_map: dict[str, dict[str, Any]] = {}
    proj_dir = AGY_CONFIG_DIR / "projects"
    if not proj_dir.is_dir():
        return proj_map
    for pfile in sorted(proj_dir.glob("*.json")):
        try:
            data = json.loads(pfile.read_text(encoding="utf-8"))
            pid = str(data.get("id") or pfile.stem)
            name = str(data.get("name") or pid)
            paths: list[str] = []
            for res in data.get("projectResources", {}).get("resources", []):
                uri = (
                    res.get("gitFolder", {}).get("folderUri")
                    or res.get("folderUri")
                    or ""
                )
                if uri:
                    paths.append(uri.replace("file://", "").rstrip("/"))
            proj_map[pid] = {
                "project_id": pid,
                "name": name,
                "workspace_paths": paths,
            }
        except Exception:
            continue
    return proj_map

def _list_saved_sessions_internal(
    limit: int = 15,
    status_filter: str = "ALL",
    include_subagents: bool = False,
) -> list[dict[str, Any]]:
    """Scan SQLite conversation_summaries.db and return live sessions."""
    results: list[dict[str, Any]] = []
    sf = (status_filter or "ALL").strip().upper()
    is_unfiltered = sf in ("ALL", "")
    if is_unfiltered:
        SESSION_STATE["session_index_map"].clear()
    projects_map = _load_projects_map()
    db_queried_ok = False
    if AGY_DB_FILE.is_file():
        try:
            con = sqlite3.connect(f"file:{AGY_DB_FILE}?mode=ro", uri=True)
            cur = con.cursor()
            query = """
                SELECT conversation_id, title, preview, step_count, last_modified_time,
                       workspace_uris, status, not_fully_idle, killed, parent_conversation_id, project_id
                FROM conversation_summaries
                WHERE (? = 1 OR parent_conversation_id IS NULL OR parent_conversation_id = '')
                ORDER BY last_modified_time DESC
                LIMIT ?
            """
            rows = cur.execute(query, (1 if include_subagents else 0, max(limit * 3, 45))).fetchall()
            con.close()
            db_queried_ok = True
            idx_counter = 1
            for row in rows:
                conv_id = str(row[0] or "")
                title = str(row[1] or "Untitled Conversation")
                step_count = int(row[3] or 0)
                last_modified = str(row[4] or "")
                raw_uris = str(row[5] or "[]")
                db_status = str(row[6] or "")
                not_fully_idle = bool(row[7])
                killed = bool(row[8])
                project_id = str(row[10] or "")
                project_name = projects_map.get(project_id, {}).get("name", project_id)
                workspace_path = ""
                workspace_uris_list: list[str] = []
                clean_uris: list[str] = []
                try:
                    workspace_uris_list = json.loads(raw_uris) if raw_uris else []
                    if workspace_uris_list and isinstance(workspace_uris_list, list):
                        clean_uris = [re.sub(r"^file://", "", str(u)).rstrip("/") for u in workspace_uris_list if u]
                        workspace_path = clean_uris[0] if clean_uris else ""
                        if len(clean_uris) > 1 and any(k in title.lower() for k in ("mcp", "antigravity", "nexus", "bridge")):
                            for cu in clean_uris:
                                if cu.endswith("/antigravity-config"):
                                    workspace_path = cu
                                    break
                except Exception:
                    pass
                if not workspace_path and project_id in projects_map:
                    p_paths = projects_map[project_id].get("workspace_paths", [])
                    if p_paths:
                        workspace_path = p_paths[0]
                        if not clean_uris:
                            clean_uris = list(p_paths)
                SESSION_STATE["session_workspace_map"][conv_id] = workspace_path
                SESSION_STATE["session_workspace_uris_map"][conv_id] = clean_uris or ([workspace_path] if workspace_path else [])
                SESSION_STATE["session_project_map"][conv_id] = project_id
                SESSION_STATE["session_title_map"][conv_id] = title
                has_gui_lock = (AGY_PRESENCE_DIR / f"{conv_id}.lock").exists()
                transcript_path = AGY_BRAIN_DIR / conv_id / ".system_generated" / "logs" / "transcript.jsonl"
                task_path = AGY_BRAIN_DIR / conv_id / "task.md"
                task_preview = ""
                task_counts = {"unchecked": 0, "in_progress": 0, "completed": 0}
                if task_path.is_file():
                    try:
                        task_text = task_path.read_text(encoding="utf-8", errors="replace")
                        for line in task_text.splitlines():
                            line_s = line.strip()
                            if line_s.startswith(("- [ ]", "* [ ]")):
                                task_counts["unchecked"] += 1
                                if not task_preview:
                                    task_preview = line_s
                            elif line_s.startswith(("- [/]", "* [/]")):
                                task_counts["in_progress"] += 1
                                if not task_preview:
                                    task_preview = line_s
                            elif line_s.startswith(("- [x]", "* [x]")):
                                task_counts["completed"] += 1
                        if not task_preview and task_text:
                            content_lines = [l.strip() for l in task_text.splitlines() if l.strip() and not l.strip().startswith("#")]
                            task_preview = " | ".join(content_lines[:2])
                    except Exception:
                        pass
                # Derive live status
                live_status = "IDLE"
                if killed:
                    live_status = "KILLED"
                elif db_status == "CASCADE_RUN_STATUS_RUNNING" or not_fully_idle:
                    live_status = "RUNNING"
                    if transcript_path.is_file():
                        try:
                            if (time.time() - transcript_path.stat().st_mtime) > 300:
                                live_status = "STALLED_WAITING_APPROVAL"
                        except Exception:
                            pass
                else:
                    if task_counts["in_progress"] > 0:
                        live_status = "RUNNING"
                    elif task_counts["completed"] > 0 and task_counts["unchecked"] == 0:
                        live_status = "COMPLETED"
                    elif task_counts["unchecked"] > 0:
                        live_status = "IDLE"
                    else:
                        live_status = "IDLE"
                # Flexible status_filter matching
                if not is_unfiltered:
                    if sf in ("STALLED", "STALLED_WAITING_APPROVAL", "WAITING"):
                        if live_status != "STALLED_WAITING_APPROVAL":
                            continue
                    elif sf in ("RUNNING", "ACTIVE"):
                        if live_status not in ("RUNNING", "STALLED_WAITING_APPROVAL"):
                            continue
                    elif sf in ("COMPLETED", "DONE"):
                        if live_status != "COMPLETED":
                            continue
                    elif sf == "IDLE":
                        if live_status not in ("IDLE", "COMPLETED"):
                            continue
                    elif sf not in live_status:
                        continue
                idx_str = str(idx_counter)
                if is_unfiltered or idx_str not in SESSION_STATE["session_index_map"]:
                    SESSION_STATE["session_index_map"][idx_str] = conv_id
                sess_obj: dict[str, Any] = {
                    "index": idx_str,
                    "conversation_id": conv_id,
                    "title": title,
                    "project_id": project_id,
                    "project_name": project_name,
                    "workspace_path": workspace_path,
                    "workspace_uris": workspace_uris_list,
                    "status": live_status,
                    "step_count": step_count,
                    "last_updated": last_modified,
                    "has_gui_lock": has_gui_lock,
                    "task_preview": task_preview[:200] if task_preview else "No active task checklist",
                }
                if step_count > 1500:
                    sess_obj["session_health_warning"] = f"SESSION HEALTH WARNING: step_count={step_count} (>1,500). Consider rotating via create_new_session=True."
                if live_status in ("STALLED_WAITING_APPROVAL", "RUNNING"):
                    pending = extract_pending_approval(transcript_path)
                    if pending:
                        sess_obj["pending_approval"] = pending
                results.append(sess_obj)
                idx_counter += 1
                if len(results) >= limit:
                    break
        except Exception as e:
            results.append({"error": f"Failed to query conversation_summaries.db: {e}"})
    # Fallback brain directory scan ONLY if SQLite DB could not be queried
    if not db_queried_ok and not results and AGY_BRAIN_DIR.is_dir():
        idx_counter = 1
        for session_dir in sorted(AGY_BRAIN_DIR.iterdir(), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True):
            if not session_dir.is_dir() or session_dir.name.startswith("."):
                continue
            conv_id = session_dir.name
            task_path = session_dir / "task.md"
            task_preview = ""
            if task_path.is_file():
                try:
                    task_preview = task_path.read_text(encoding="utf-8", errors="replace")[:200]
                except Exception:
                    pass
            idx_str = str(idx_counter)
            SESSION_STATE["session_index_map"][idx_str] = conv_id
            results.append({
                "index": idx_str,
                "conversation_id": conv_id,
                "title": conv_id,
                "workspace_path": str(AGY_GITLAB_DIR),
                "workspace_uris": [],
                "status": "IDLE",
                "step_count": 0,
                "last_updated": datetime.fromtimestamp(session_dir.stat().st_mtime, tz=timezone.utc).isoformat(),
                "has_gui_lock": False,
                "task_preview": task_preview,
            })
            idx_counter += 1
            if len(results) >= limit:
                break
    return results

from agy_nexus.session_status import _get_selected_session_quick_status  # noqa: E402
