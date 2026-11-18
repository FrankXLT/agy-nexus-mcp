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
import agy_nexus.config as cfg
from agy_nexus.config import (
    AGY_BG_DIR,
    AGY_BRAIN_DIR,
    AGY_CONFIG_DIR,
    AGY_DB_FILE,
    AGY_GITLAB_DIR,
    AGY_PRESENCE_DIR,
    AGY_PROJECTS_DIR,
    SESSION_STATE,
    get_antigravity_config_repo,
    get_workspace_pillar_roots,
)
from agy_nexus.media_discovery import parse_iso_epoch
from agy_nexus.stats import extract_pending_approval
from agy_nexus.uploads import validate_conv_id


_parse_iso_ts = parse_iso_epoch

NEXUS_TITLE_KEYWORDS: tuple[str, ...] = (
    "agy-nexus",
    "ag-bridge",
    "antigravity-config",
    "agy_nexus",
    "nexus mcp",
    "polyglot-mcp",
)
NEXUS_PROJECT_ID = "a97e4c10-2600-4a91-8b2c-1e75c90a0301"


def pick_primary_workspace_uri(clean_uris: list[str], title: str = "", project_id: str = "") -> str:
    """Pick deterministic primary workspace path from multi-root session URIs without hijacking unrelated titles like 'Google Nexus'."""
    if not clean_uris:
        return ""
    nexus_repo = (cfg.AGY_PROJECTS_DIR / "agy-nexus-mcp") if (cfg.AGY_PROJECTS_DIR / "agy-nexus-mcp").is_dir() else (cfg.AGY_GITLAB_DIR / "agy-nexus-mcp")
    is_nexus_proj = project_id == NEXUS_PROJECT_ID and nexus_repo.is_dir()
    if len(clean_uris) > 1 and (is_nexus_proj or any(k in (title or "").lower() for k in NEXUS_TITLE_KEYWORDS)):
        for suffix in ("/agy-nexus-mcp", "/antigravity-config"):
            for cu in clean_uris:
                if cu.endswith(suffix) or f"{suffix}/" in cu:
                    if is_nexus_proj and cu.endswith("/antigravity-config"):
                        return str(nexus_repo)
                    return cu
    if is_nexus_proj and clean_uris[0].endswith("/antigravity-config"):
        return str(nexus_repo)
    return clean_uris[0]


def _load_projects_map() -> dict[str, dict[str, Any]]:
    """Read Antigravity project JSON files from cfg.AGY_CONFIG_DIR/projects."""
    proj_map: dict[str, dict[str, Any]] = {}
    proj_dir = cfg.AGY_CONFIG_DIR / "projects"
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


def resolve_canonical_project_for_workspace(ws_path: str, project_hint: str = "") -> tuple[str, str]:
    """Resolve (project_id, project_name) for a workspace or hint, preferring dedicated single-repo projects over multi-repo umbrellas."""
    proj_map = _load_projects_map()
    hint_clean = (project_hint or "").strip()
    if hint_clean and hint_clean in proj_map:
        return hint_clean, str(proj_map[hint_clean].get("name") or hint_clean)

    ws_clean = re.sub(r"^file://", "", (ws_path or "").strip()).rstrip("/")
    alt_ws = ""
    if "/worktrees/" in ws_clean:
        m_wt = re.search(r"/worktrees/([^/]+)", ws_clean)
        if m_wt:
            slug = m_wt.group(1)
            for pillar in get_workspace_pillar_roots():
                cand = (pillar / slug).resolve()
                if cand.is_dir():
                    alt_ws = str(cand)
                    break
            if not alt_ws:
                alt_ws = str((cfg.AGY_GITLAB_DIR / slug).resolve())

    hint_lower = hint_clean.lower()
    if ws_clean:
        matches: list[tuple[int, int, str, str]] = []
        for pid, pinfo in proj_map.items():
            p_paths = [str(p).rstrip("/") for p in (pinfo.get("workspace_paths") or []) if p]
            pname = str(pinfo.get("name") or pid)
            matched = any(
                ws_clean == pp or ws_clean.startswith(pp + "/") or (alt_ws and alt_ws == pp)
                for pp in p_paths
            )
            if matched:
                hint_rank = 0 if (hint_lower and hint_lower == pname.lower()) else 1
                matches.append((hint_rank, max(1, len(p_paths)), pid, pname))
        if matches:
            matches.sort(key=lambda item: (item[0], item[1], item[3].lower()))
            return matches[0][2], matches[0][3]

    if hint_lower:
        name_matches: list[tuple[int, str, str]] = []
        for pid, pinfo in proj_map.items():
            pname = str(pinfo.get("name") or pid)
            p_paths = [str(p).rstrip("/") for p in (pinfo.get("workspace_paths") or []) if p]
            if pname.lower() == hint_lower or any(Path(pp).name.lower() == hint_lower for pp in p_paths):
                name_matches.append((max(1, len(p_paths)), pid, pname))
        if name_matches:
            name_matches.sort(key=lambda item: (item[0], item[2].lower()))
            return name_matches[0][1], name_matches[0][2]

    return "", hint_clean


def _parse_task_checklist(task_path: Path) -> tuple[str, dict[str, int]]:
    """Parse task.md checklist counts and preview line."""
    task_preview = ""
    task_counts = {"unchecked": 0, "in_progress": 0, "completed": 0}
    if not task_path.is_file():
        return task_preview, task_counts
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
    return task_preview, task_counts


def _derive_session_live_status(
    killed: bool,
    db_status: str,
    not_fully_idle: bool,
    transcript_path: Path,
    task_counts: dict[str, int],
) -> str:
    """Derive live session status from SQLite flags, transcript mtime, and task checklist."""
    if killed:
        return "KILLED"
    if db_status == "CASCADE_RUN_STATUS_RUNNING" or not_fully_idle:
        if transcript_path.is_file():
            try:
                if (time.time() - transcript_path.stat().st_mtime) > 300:
                    return "STALLED_WAITING_APPROVAL"
            except Exception:
                pass
        return "RUNNING"
    if task_counts["in_progress"] > 0:
        return "RUNNING"
    if task_counts["completed"] > 0 and task_counts["unchecked"] == 0:
        return "COMPLETED"
    return "IDLE"


def _matches_status_filter(sf: str, live_status: str) -> bool:
    """Return True when live_status satisfies a flexible status_filter token."""
    if sf in ("STALLED", "STALLED_WAITING_APPROVAL", "WAITING"):
        return live_status == "STALLED_WAITING_APPROVAL"
    if sf in ("RUNNING", "ACTIVE"):
        return live_status in ("RUNNING", "STALLED_WAITING_APPROVAL")
    if sf in ("COMPLETED", "DONE"):
        return live_status == "COMPLETED"
    if sf == "IDLE":
        return live_status in ("IDLE", "COMPLETED")
    return sf in live_status


def _safe_mtime(path: Path) -> float:
    """Return file/dir mtime as UTC epoch seconds, or 0.0 if missing/unreadable."""
    try:
        return float(path.stat().st_mtime) if path.exists() else 0.0
    except OSError:
        return 0.0


def _safe_conv_subdir(base_dir: Path, conv_id: str) -> Path | None:
    """Return validated non-symlink session subdirectory inside base_dir, or None on invalid/escaping conv_id."""
    if not validate_conv_id(conv_id):
        return None
    try:
        root_res = base_dir.resolve()
        cand = base_dir / conv_id.strip()
        if cand.is_symlink() or not cand.resolve().is_relative_to(root_res):
            return None
        return cand
    except OSError:
        return None


def _compute_session_activity_ts(conv_id: str, db_iso: str = "") -> tuple[float, str, Path]:
    """Compute effective_ts = max(db_ts, transcript_mtime, task_md_mtime, brain_dir_mtime) and normalized ISO string."""
    db_ts = _parse_iso_ts(db_iso)
    sess_dir = _safe_conv_subdir(cfg.AGY_BRAIN_DIR, conv_id)
    if sess_dir is None:
        return db_ts, db_iso, cfg.AGY_BRAIN_DIR / "__invalid_conv__"
    logs_dir = sess_dir / ".system_generated" / "logs"
    t_full = logs_dir / "transcript_full.jsonl"
    t_comp = logs_dir / "transcript.jsonl"
    transcript_path = t_full if t_full.is_file() else t_comp
    effective_ts = max(db_ts, _safe_mtime(sess_dir), _safe_mtime(sess_dir / "task.md"), _safe_mtime(t_full), _safe_mtime(t_comp))
    eff_iso = datetime.fromtimestamp(effective_ts, tz=timezone.utc).isoformat() if (effective_ts > db_ts and effective_ts > 0.0) else db_iso
    return effective_ts, eff_iso, transcript_path


def _scan_fallback_brain_sessions(limit: int) -> list[dict[str, Any]]:
    """Fallback brain directory scan ONLY if SQLite DB could not be queried."""
    candidates: list[dict[str, Any]] = []
    if not cfg.AGY_BRAIN_DIR.is_dir():
        return candidates
    ws_fallback = str(cfg.AGY_PROJECTS_DIR if cfg.AGY_PROJECTS_DIR.is_dir() else cfg.AGY_GITLAB_DIR)
    for session_dir in cfg.AGY_BRAIN_DIR.iterdir():
        if session_dir.is_symlink() or not session_dir.is_dir() or session_dir.name.startswith("."):
            continue
        conv_id = session_dir.name
        sess_dir = _safe_conv_subdir(cfg.AGY_BRAIN_DIR, conv_id)
        if sess_dir is None:
            continue
        eff_ts, eff_iso, _ = _compute_session_activity_ts(conv_id)
        task_preview, _ = _parse_task_checklist(sess_dir / "task.md")
        candidates.append({
            "index": "0",
            "conversation_id": conv_id,
            "title": conv_id,
            "workspace_path": ws_fallback,
            "workspace_uris": [],
            "status": "IDLE",
            "step_count": 0,
            "last_updated": eff_iso,
            "last_updated_ts": eff_ts,
            "has_gui_lock": False,
            "task_preview": task_preview[:200] if task_preview else "",
        })
    candidates.sort(key=lambda s: float(s.get("last_updated_ts") or 0.0), reverse=True)
    results = candidates[:limit]
    for idx_counter, s in enumerate(results, 1):
        idx_str = str(idx_counter)
        s["index"] = idx_str
        SESSION_STATE["session_index_map"][idx_str] = s["conversation_id"]
    return results


def _build_session_entry(row: tuple[Any, ...], projects_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Assemble one normalized session dict from a SQLite row plus filesystem activity timestamps."""
    conv_id, title = str(row[0] or "").strip(), str(row[1] or "Untitled Conversation")
    step_count, last_modified = int(row[3] or 0), str(row[4] or "")
    raw_uris, db_status = str(row[5] or "[]"), str(row[6] or "")
    not_fully_idle, killed = bool(row[7]), bool(row[8])
    project_id = str(row[10] or "")
    project_name = projects_map.get(project_id, {}).get("name", project_id)
    workspace_path, workspace_uris_list, clean_uris = "", [], []
    try:
        workspace_uris_list = json.loads(raw_uris) if raw_uris else []
        if workspace_uris_list and isinstance(workspace_uris_list, list):
            clean_uris = [re.sub(r"^file://", "", str(u)).rstrip("/") for u in workspace_uris_list if u]
            workspace_path = pick_primary_workspace_uri(clean_uris, title, project_id)
    except Exception:
        pass
    if not workspace_path and project_id in projects_map:
        p_paths = projects_map[project_id].get("workspace_paths", [])
        if p_paths:
            workspace_path = p_paths[0]
            clean_uris = clean_uris or list(p_paths)
    SESSION_STATE["session_workspace_map"][conv_id] = workspace_path
    SESSION_STATE["session_workspace_uris_map"][conv_id] = clean_uris or ([workspace_path] if workspace_path else [])
    SESSION_STATE["session_project_map"][conv_id] = project_id
    SESSION_STATE["session_title_map"][conv_id] = title

    eff_ts, eff_iso, transcript_path = _compute_session_activity_ts(conv_id, last_modified)
    sess_dir = _safe_conv_subdir(cfg.AGY_BRAIN_DIR, conv_id)
    task_md = (sess_dir / "task.md") if sess_dir is not None else (cfg.AGY_BRAIN_DIR / "__invalid_task__")
    task_preview, task_counts = _parse_task_checklist(task_md)
    live_status = _derive_session_live_status(killed, db_status, not_fully_idle, transcript_path, task_counts)
    lock_path = (cfg.AGY_PRESENCE_DIR / f"{conv_id}.lock") if validate_conv_id(conv_id) else None
    sess_obj: dict[str, Any] = {
        "index": "0",
        "conversation_id": conv_id,
        "title": title,
        "project_id": project_id,
        "project_name": project_name,
        "workspace_path": workspace_path,
        "workspace_uris": workspace_uris_list,
        "status": live_status,
        "step_count": step_count,
        "last_updated": eff_iso,
        "last_updated_ts": eff_ts,
        "has_gui_lock": bool(lock_path and not lock_path.is_symlink() and lock_path.exists()),
        "task_preview": task_preview[:200] if task_preview else "No active task checklist",
    }
    if step_count > 1500:
        sess_obj["session_health_warning"] = f"SESSION HEALTH WARNING: step_count={step_count} (>1,500). Consider rotating via create_new_session=True."
    if live_status in ("STALLED_WAITING_APPROVAL", "RUNNING") and transcript_path.is_file():
        pending = extract_pending_approval(transcript_path)
        if pending:
            sess_obj["pending_approval"] = pending
    return sess_obj


def _list_saved_sessions_internal(
    limit: int = 15,
    status_filter: str = "ALL",
    include_subagents: bool = False,
) -> list[dict[str, Any]]:
    """Scan SQLite conversation_summaries.db and return live sessions sorted strictly by last_updated_ts descending."""
    results: list[dict[str, Any]] = []
    sf = (status_filter or "ALL").strip().upper()
    is_unfiltered = sf in ("ALL", "")
    if is_unfiltered:
        SESSION_STATE["session_index_map"].clear()
    projects_map = _load_projects_map()
    db_queried_ok = False
    if cfg.AGY_DB_FILE.is_file():
        try:
            sub_flag = 1 if include_subagents else 0
            cols = (
                "conversation_id, title, preview, step_count, last_modified_time, "
                "workspace_uris, status, not_fully_idle, killed, parent_conversation_id, project_id"
            )
            parent_cond = "(? = 1 OR parent_conversation_id IS NULL OR parent_conversation_id = '')"
            con = sqlite3.connect(f"file:{cfg.AGY_DB_FILE}?mode=ro", uri=True)
            try:
                cur = con.cursor()
                rows_recent = cur.execute(
                    f"SELECT {cols} FROM conversation_summaries WHERE {parent_cond} ORDER BY last_modified_time DESC LIMIT ?",
                    (sub_flag, max(limit * 4, 200)),
                ).fetchall()
                rows_sentinel = cur.execute(
                    f"SELECT {cols} FROM conversation_summaries WHERE {parent_cond} "
                    "AND (last_modified_time IS NULL OR last_modified_time = '' OR last_modified_time LIKE '0001-%') "
                    "ORDER BY rowid DESC LIMIT 200",
                    (sub_flag,),
                ).fetchall()
            finally:
                con.close()
            db_queried_ok = True
            seen_ids: set[str] = set()
            scored: list[tuple[float, tuple[Any, ...]]] = []
            for row in [*rows_recent, *rows_sentinel]:
                cid = str(row[0] or "").strip()
                if not validate_conv_id(cid) or cid in seen_ids:
                    continue
                seen_ids.add(cid)
                eff_ts, _, _ = _compute_session_activity_ts(cid, str(row[4] or ""))
                scored.append((eff_ts, row))
            scored.sort(key=lambda pair: pair[0], reverse=True)
            to_build = scored[:limit] if is_unfiltered else scored
            for _, row in to_build:
                sess_obj = _build_session_entry(row, projects_map)
                if not is_unfiltered and not _matches_status_filter(sf, str(sess_obj.get("status") or "")):
                    continue
                results.append(sess_obj)
                if len(results) >= limit:
                    break
            results.sort(key=lambda s: float(s.get("last_updated_ts") or 0.0), reverse=True)
            for idx_counter, sess_obj in enumerate(results, 1):
                idx_str = str(idx_counter)
                sess_obj["index"] = idx_str
                if is_unfiltered or idx_str not in SESSION_STATE["session_index_map"]:
                    SESSION_STATE["session_index_map"][idx_str] = sess_obj["conversation_id"]
        except Exception as e:
            results.append({"error": f"Failed to query conversation_summaries.db: {e}"})
    if not db_queried_ok and not results:
        return _scan_fallback_brain_sessions(limit)
    return results

from agy_nexus.session_status import _get_selected_session_quick_status  # noqa: E402
