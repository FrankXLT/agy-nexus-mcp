#!/usr/bin/env python3
"""ag-bridge-mcp: Antigravity-to-Gemini Handshake MCP Server.

Provides a secure, authenticated bridge enabling Google Gemini (via Custom MCP)
to inspect active Antigravity conversations, conduct deep codebase research,
and cleanly hand off synthesized plans and instructions back to Antigravity.
"""

from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
from typing import Any
import urllib.error
import urllib.request

from fastmcp import FastMCP
import uvicorn

# -----------------------------------------------------------------------------
# 1. Configuration & Secrets Loading
# -----------------------------------------------------------------------------

def _load_env_file() -> None:
    """Load KEY=VALUE pairs into os.environ if not already present."""
    env_candidates = [
        Path(os.getenv("AG_BRIDGE_ENV_FILE", "/config/secrets.env")),
        Path.home() / ".config/ag-bridge-mcp/secrets.env",
    ]
    for candidate in env_candidates:
        try:
            if candidate.is_file():
                for line in candidate.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    os.environ.setdefault(k, v)
                break
        except Exception:
            continue

_load_env_file()

from ag_bridge_hygiene import (  # noqa: E402
    ENFORCE_MODULAR_HYGIENE,
    HARD_MAX_FILE_LINES,
    MAX_DIFF_CHARS,
    MAX_FILE_CHARS,
    MAX_FILES_PER_CALL,
    MAX_TASK_DOC_CHARS,
    MAX_TOTAL_FILE_CHARS,
    MAX_TRANSCRIPT_TURNS,
    MODULAR_HYGIENE_MARKDOWN_BLOCK,
    MODULAR_HYGIENE_STANDARDS,
    TARGET_FILE_LINES,
    TTL_SECONDS,
    parse_inline_line_spec,
    slice_file_content,
    slice_git_diff,
)
from ag_bridge_inventory import (
    CUSTOMIZATION_SCOPE_POLICY,
    build_interjection_directive,
    collect_agents_inventory,
    collect_plugin_bundles_summary,
    collect_rules_inventory,
    collect_skills_inventory,
    evaluate_session_customization_scope,
    resolve_customization_file,
)
from ag_bridge_stats import (
    build_nexus_stats_bundle,
    extract_pending_approval,
    get_live_quota_and_pool_status,
    get_wire_telemetry_summary,
    record_wire_telemetry,
)
from ag_bridge_workflows import (
    export_notebook_bundle,
    inspect_multi_repo_drift,
    stage_quarantine_handoff,
)

AGY_DATA_DIR = Path(os.getenv("AGY_DATA_DIR", str(Path.home() / ".gemini/antigravity"))).expanduser()
AGY_BRAIN_DIR = Path(os.getenv("AGY_BRAIN_DIR", str(AGY_DATA_DIR / "brain"))).expanduser()
AGY_DB_FILE = Path(os.getenv("AGY_DB_FILE", str(AGY_DATA_DIR / "conversation_summaries.db"))).expanduser()
AGY_PRESENCE_DIR = Path(os.getenv("AGY_PRESENCE_DIR", str(AGY_DATA_DIR / "presence"))).expanduser()
AGY_CONFIG_DIR = Path(os.getenv("AGY_CONFIG_DIR", str(Path.home() / ".gemini/config"))).expanduser()
AGY_GITLAB_DIR = Path(os.getenv("AGY_GITLAB_DIR", str(Path.home() / "gitlab"))).expanduser()
AGY_BG_DIR = Path(os.getenv("AGY_BG_DIR", str(AGY_DATA_DIR / "sidecar_data/ag-bridge-bg"))).expanduser()
AGY_HOST_BRIDGE_URL = os.getenv("AGY_HOST_BRIDGE_URL", "http://127.0.0.1:8098/agentapi")
BIND_HOST = os.getenv("BIND_HOST", "0.0.0.0")
BIND_PORT = int(os.getenv("BIND_PORT", "8765"))
PATH_SECRET = os.getenv("PATH_SECRET", "").strip()
PASS_HASH = os.getenv("PASS_HASH", "").strip().lower()
STATE_FILE = Path(os.getenv("AG_BRIDGE_STATE_FILE", str(AGY_BG_DIR / "session_state.json"))).expanduser()
ALLOW_LOCKED_STATS = os.getenv("AG_BRIDGE_ALLOW_LOCKED_STATS", "false").strip().lower() in ("1", "true", "yes")
ALLOW_LOCKED_STAGING = os.getenv("AG_BRIDGE_ALLOW_LOCKED_STAGING", "false").strip().lower() in ("1", "true", "yes")

# -----------------------------------------------------------------------------
# 2. Deadbolt State & Voice Passphrase Normalization
# -----------------------------------------------------------------------------

SESSION_STATE: dict[str, Any] = {
    "unlocked_at": 0.0,
    "selected_session": "",
    "selected_workspace": "",
    "selected_workspace_uris": [],
    "selected_project": "",
    "session_index_map": {},           # "1" -> conv_id
    "session_workspace_map": {},       # conv_id -> primary workspace_path
    "session_workspace_uris_map": {},  # conv_id -> list[str] of all workspace paths
    "session_project_map": {},         # conv_id -> project_id
    "session_title_map": {},           # conv_id -> title
}


def _clear_selected_session_state() -> None:
    """Clear selected session/workspace pointers when deadbolt expires or resets."""
    SESSION_STATE["selected_session"] = ""
    SESSION_STATE["selected_workspace"] = ""
    SESSION_STATE["selected_workspace_uris"] = []
    SESSION_STATE["selected_project"] = ""


def _save_session_state() -> None:
    """Persist core session state to disk so active workspace/session survives container restarts."""
    try:
        AGY_BG_DIR.mkdir(parents=True, exist_ok=True)
        persisted = {
            "unlocked_at": SESSION_STATE.get("unlocked_at", 0.0),
            "selected_session": SESSION_STATE.get("selected_session", ""),
            "selected_workspace": SESSION_STATE.get("selected_workspace", ""),
            "selected_workspace_uris": SESSION_STATE.get("selected_workspace_uris", []),
            "selected_project": SESSION_STATE.get("selected_project", ""),
        }
        STATE_FILE.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass


def _load_session_state() -> None:
    """Load persisted session state from disk on startup if present (clearing stale session if TTL expired)."""
    try:
        if STATE_FILE.is_file():
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                unlocked_at = float(data.get("unlocked_at") or 0.0)
                SESSION_STATE["unlocked_at"] = unlocked_at
                if (time.time() - unlocked_at) < TTL_SECONDS:
                    for key in ("selected_session", "selected_workspace", "selected_workspace_uris", "selected_project"):
                        if key in data and data[key] is not None:
                            SESSION_STATE[key] = data[key]
                else:
                    _clear_selected_session_state()
    except Exception:
        pass


_load_session_state()


def normalize_phrase(phrase: str) -> str:
    """Normalize spoken passphrase (lowercase, strip whitespace and punctuation) and compute SHA-256."""
    cleaned = re.sub(r"[^a-z0-9]", "", (phrase or "").lower())
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()


def verify_passphrase(spoken_passphrase: str, expected_hash: str = "") -> bool:
    """Constant-time verification of normalized passphrase (and spoken prefix wrappers) against expected SHA-256 hash."""
    target_hash = (expected_hash or PASS_HASH).strip().lower()
    if not target_hash or not spoken_passphrase:
        return False
    if hmac.compare_digest(normalize_phrase(spoken_passphrase), target_hash):
        return True
    # Handle voice/chat wrappers such as "The passphrase is ..." or "passphrase: ..."
    stripped = re.sub(
        r"^(?:my\s+|the\s+)?(?:spoken\s+|voice\s+)?(?:passphrase|password|passcode|code|secret|key)\s*(?:is|:|=)?\s*",
        "",
        spoken_passphrase.strip(),
        flags=re.I,
    )
    if stripped != spoken_passphrase and hmac.compare_digest(normalize_phrase(stripped), target_hash):
        return True
    tokens = re.findall(r"[A-Za-z0-9]+", spoken_passphrase)
    if 1 < len(tokens) <= 10:
        for i in range(len(tokens)):
            for j in range(i + 1, len(tokens) + 1):
                candidate = "".join(tokens[i:j])
                if hmac.compare_digest(normalize_phrase(candidate), target_hash):
                    return True
    return False


def is_unlocked(spoken_passphrase: str = "") -> bool:
    """Check if the session deadbolt is currently unlocked (or unlock inline if spoken_passphrase is valid) and refresh TTL."""
    if not PASS_HASH:
        return False
    now = time.time()
    was_expired = (now - float(SESSION_STATE.get("unlocked_at") or 0.0)) >= TTL_SECONDS
    if was_expired and SESSION_STATE.get("selected_session"):
        _clear_selected_session_state()
    if spoken_passphrase and verify_passphrase(spoken_passphrase):
        SESSION_STATE["unlocked_at"] = now
        _save_session_state()
        return True
    if not was_expired:
        SESSION_STATE["unlocked_at"] = now
        _save_session_state()
        return True
    return False


LOCKED_RESPONSE = json.dumps({
    "ok": False,
    "locked": True,
    "assistant_guidance": (
        "STOP IMMEDIATELY AND REPLY TO THE USER NOW: Do NOT call any more MCP tools in this turn "
        "(Google Gemini's UI confirmation card hangs on back-to-back tool calls). "
        "Ask the user for their spoken passphrase first, then call the tool in the NEXT turn."
    ),
    "message": (
        "Security Deadbolt Active. Voice/spoken passphrase verification required. "
        "Please ask the user for their spoken passphrase and call the tool in the next turn."
    ),
}, indent=2)

READONLY_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}

HANDOFF_ANNOTATIONS = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}

# -----------------------------------------------------------------------------
# 3. FastMCP Server Initialization
# -----------------------------------------------------------------------------

mcp = FastMCP(
    name="agy-nexus-mcp",
    instructions=(
        "AGY-NEXUS-MCP: Antigravity Mission Control, Cross-Session FTS5 Memory, Quota Overwatch & Governance MCP Server. "
        "Enables Gemini to authenticate via voice passphrase, discover and inspect active Antigravity conversations, "
        "explore local codebases in read-only mode, audit 4-layer Skills/Agents/Rules, view live Dual-Pool Quota & Activity Heatmaps, and dispatch synthesized research handoffs.\n"
        "AUTONOMOUS MULTI-FILE RESEARCH & WORKFLOW RULES:\n"
        "1. AUTONOMOUS FILE READING (NO MID-TASK NAG PROMPTS): When investigating a session, auditing code, or preparing an architectural handoff, "
        "figure out all the files you need to inspect, read them (batching comma-separated paths in `file_subpath='path1,path2,path3'` up to 12 files / 120 KB per call, "
        "and chaining additional read-only tool calls in the same turn whenever you discover more files to read), and come back to the user with the complete synthesis. "
        "NEVER stop mid-task to ask the user for permission to read another file or to read remaining lines of a file.\n"
        "2. USE BUNDLED ONE-SHOT PARAMETERS:\n"
        "- `load_session_into_gemini` returns full `task.md`, `implementation_plan.md`, `walkthrough.md`, `execution_status`, `git_summary`, `latest_assistant_response`, AND accepts optional comma-separated `include_files`.\n"
        "- `ask_workspace_readonly` reads up to 12 comma-separated files in full (`file_subpath='a.py,b.py,skill:name'`, up to 48 KB per file / 120 KB total per call), runs repo-wide `git grep` (`search_query`), and queries SQLite FTS5 history.\n"
        "- `manage_background_run(action='stats', period='current_month'|'last_month'|'last_90d'|'last_year', style='default'|'quick'|'rich')` returns the pre-rendered ASCII telemetry report + Dual-Pool Quota Pacing.\n"
        "3. LOCKED DEADBOLT ONLY: Only stop immediately to ask the user if `locked=True` (when the security deadbolt requires their spoken passphrase).\n"
        "4. PROJECT ROUTING: When calling `send_handoff_and_resume`, pass `session_identifier` (for existing sessions) or `project_name` and `workspace_path` (when `create_new_session=True`)."
    ),
)

# -----------------------------------------------------------------------------
# 4. Internal Helper Routines
# -----------------------------------------------------------------------------

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

def _get_selected_session_quick_status() -> dict[str, Any]:
    """Return a compact status summary of the currently selected session and its latest background job."""
    conv_id = SESSION_STATE.get("selected_session", "")
    if not conv_id:
        return {}
    info: dict[str, Any] = {"conversation_id": conv_id}
    if AGY_DB_FILE.is_file():
        try:
            con = sqlite3.connect(f"file:{AGY_DB_FILE}?mode=ro", uri=True)
            row = con.execute(
                "SELECT status, step_count, last_modified_time, not_fully_idle, killed FROM conversation_summaries WHERE conversation_id = ?",
                (conv_id,),
            ).fetchone()
            con.close()
            if row:
                raw_status = str(row[0] or "")
                is_running = "RUNNING" in raw_status or bool(row[3])
                info["db_status"] = raw_status
                info["step_count"] = int(row[1] or 0)
                info["last_modified"] = str(row[2] or "")
                info["is_running"] = is_running
                info["summary"] = (
                    "RUNNING_IN_BACKGROUND"
                    if is_running
                    else "COMPLETED_AND_IDLE (Antigravity finished; do NOT call manage_background_run)"
                )
        except Exception:
            pass
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
    return info


def _run_repo_search(target_repo: Path, patterns: list[str], per_repo_cap: int, fixed_strings: bool = False) -> list[str]:
    """Run git grep (with fallback to GNU grep for host-backed worktrees) and return formatted matches."""
    if not patterns:
        return []
    matches: list[str] = []
    e_args: list[str] = []
    for pat in patterns:
        if pat:
            e_args.extend(["-e", pat])
    if not e_args:
        return []

    flag_mode = ["-F"] if fixed_strings else []
    if (target_repo / ".git").exists():
        try:
            cmd = ["git", "-c", "safe.directory=*", "grep", "-n", "-I", "-i", "--max-count=5"] + flag_mode + e_args
            proc = subprocess.run(cmd, cwd=str(target_repo), capture_output=True, text=True, timeout=4, check=False)
            if proc.returncode == 0 and proc.stdout:
                for line in proc.stdout.splitlines()[:per_repo_cap]:
                    matches.append(f"[{target_repo.name}] {line[:220]}")
                return matches
            if proc.returncode == 2 and not fixed_strings:
                return _run_repo_search(target_repo, patterns, per_repo_cap, fixed_strings=True)
            if proc.returncode in (0, 1):
                return []
        except Exception:
            pass

    # Fallback to GNU grep (handles worktrees whose parent .git lives outside container mounts)
    try:
        g_cmd = [
            "grep", "-rnI", "-i",
            "--exclude-dir=.git", "--exclude-dir=node_modules", "--exclude-dir=dist",
            "--exclude-dir=build", "--exclude-dir=.next", "--exclude-dir=coverage",
            "-m", "5",
        ] + flag_mode + e_args + ["."]
        proc = subprocess.run(g_cmd, cwd=str(target_repo), capture_output=True, text=True, timeout=4, check=False)
        if proc.returncode == 0 and proc.stdout:
            for line in proc.stdout.splitlines()[:per_repo_cap]:
                clean_line = line[2:] if line.startswith("./") else line
                matches.append(f"[{target_repo.name}] {clean_line[:220]}")
        elif proc.returncode == 2 and not fixed_strings:
            return _run_repo_search(target_repo, patterns, per_repo_cap, fixed_strings=True)
    except Exception:
        pass
    return matches


def _get_configured_mcp_servers() -> list[str]:
    """Return sorted list of configured MCP server names from AGY_DATA_DIR / 'mcp'."""
    mcp_dir = AGY_DATA_DIR / "mcp"
    if mcp_dir.is_dir():
        try:
            return sorted([d.name for d in mcp_dir.iterdir() if d.is_dir() and not d.name.startswith(".")])
        except Exception:
            pass
    return []


def _search_workspaces_and_history(search_query: str, primary_ws: Path | None = None) -> dict[str, Any]:
    """Search across all local Git repositories, worktrees, configured MCP servers, and SQLite conversation history."""
    available_repos: list[str] = []
    repo_dirs: list[Path] = []
    if AGY_GITLAB_DIR.is_dir():
        for entry in sorted(AGY_GITLAB_DIR.iterdir()):
            if entry.is_dir() and not entry.name.startswith(".") and not entry.is_symlink():
                available_repos.append(entry.name)
                if (entry / ".git").exists():
                    repo_dirs.append(entry)

    # Dynamically include any active worktrees under AGY_DATA_DIR / "worktrees"
    wt_root = AGY_DATA_DIR / "worktrees"
    if wt_root.is_dir():
        for proj_wt in sorted(wt_root.iterdir()):
            if proj_wt.is_dir() and not proj_wt.name.startswith("."):
                wt_dirs = sorted([d for d in proj_wt.iterdir() if d.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)
                if wt_dirs:
                    available_repos.append(f"{proj_wt.name} ({wt_dirs[0].name})")
                    repo_dirs.append(wt_dirs[0])

    configured_mcps = _get_configured_mcp_servers()

    grep_matches: list[str] = []
    fts_matches: list[dict[str, Any]] = []
    q = (search_query or "").strip()
    if q:
        search_targets: list[Path] = []
        if primary_ws and primary_ws.is_dir() and primary_ws != AGY_GITLAB_DIR:
            search_targets.append(primary_ws)
        priority_env = [p.strip() for p in os.getenv("AGY_PRIORITY_REPOS", "antigravity-config").split(",") if p.strip()]
        for priority_name in priority_env:
            pdir = AGY_GITLAB_DIR / priority_name
            if pdir in repo_dirs and pdir not in search_targets:
                search_targets.append(pdir)
        for rdir in repo_dirs:
            if rdir not in search_targets:
                search_targets.append(rdir)

        for idx, target_repo in enumerate(search_targets):
            if len(grep_matches) >= 35:
                break
            per_repo_cap = 10 if idx == 0 else 6
            grep_matches.extend(_run_repo_search(target_repo, [q], per_repo_cap))

        # If exact phrase returned 0 matches and query has multiple words, retry with OR-ed keywords
        if not grep_matches:
            keywords = [w for w in re.findall(r"[A-Za-z0-9_.-]{3,}", q) if w.lower() not in {"and", "the", "for", "with", "from"}][:5]
            if len(keywords) > 1:
                for idx, target_repo in enumerate(search_targets):
                    if len(grep_matches) >= 35:
                        break
                    per_repo_cap = 10 if idx == 0 else 6
                    grep_matches.extend(_run_repo_search(target_repo, keywords, per_repo_cap))

        if AGY_DB_FILE.is_file():
            try:
                con = sqlite3.connect(f"file:{AGY_DB_FILE}?mode=ro", uri=True)
                cur = con.cursor()
                like_pat = f"%{q}%"
                title_sql = """
                    SELECT conversation_id, title, substr(preview, 1, 200), last_modified_time
                    FROM conversation_summaries
                    WHERE title LIKE ? OR preview LIKE ?
                    ORDER BY last_modified_time DESC
                    LIMIT 5
                """
                seen_ids: set[str] = set()
                for r in cur.execute(title_sql, (like_pat, like_pat)).fetchall():
                    seen_ids.add(str(r[0]))
                    fts_matches.append({
                        "conversation_id": r[0],
                        "title": r[1],
                        "preview": r[2],
                        "last_modified": r[3],
                    })

                tokens = [t for t in re.findall(r"[A-Za-z0-9_]{2,}", q) if t.upper() not in ("AND", "OR", "NOT", "NEAR")][:6]
                if tokens:
                    fts_expr = " OR ".join(f'"{t}"' for t in tokens)
                    fts_sql = """
                        SELECT conversation_id, title,
                               snippet(conversations_fts, 13, '[', ']', '...', 15),
                               snippet(conversations_fts, 14, '[', ']', '...', 15)
                        FROM conversations_fts
                        WHERE conversations_fts MATCH ?
                        LIMIT 6
                    """
                    for r in cur.execute(fts_sql, (fts_expr,)).fetchall():
                        if str(r[0]) not in seen_ids:
                            seen_ids.add(str(r[0]))
                            fts_matches.append({
                                "conversation_id": r[0],
                                "title": r[1],
                                "user_snippet": r[2],
                                "agent_snippet": r[3],
                            })
                con.close()
            except Exception:
                pass

    return {
        "available_repositories": available_repos,
        "configured_mcp_servers": configured_mcps,
        "code_search_matches": grep_matches[:35],
        "historical_session_matches": fts_matches[:8],
    }

def _compact_json(data: Any) -> str:
    """Serialize tool output with compact separators so large inventories/bundles stay well under Gemini's cloud proxy byte ceiling."""
    return json.dumps(data, separators=(",", ": "), ensure_ascii=False)


# -----------------------------------------------------------------------------
# 5. MCP Tools Implementation
# -----------------------------------------------------------------------------

@mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
def unlock_sessions(spoken_passphrase: str, search_query: str = "", style: str = "default") -> str:
    """Verify user spoken passphrase against the deadbolt hash, unlock sessions, return active conversations and projects, and optionally search workspaces/history in a single step."""
    if not verify_passphrase(spoken_passphrase):
        return _compact_json({
            "ok": False,
            "locked": True,
            "error": "Passphrase verification failed. Deadbolt remains locked."
        })

    now = time.time()
    was_expired = (now - float(SESSION_STATE.get("unlocked_at") or 0.0)) >= TTL_SECONDS
    if was_expired:
        _clear_selected_session_state()
    SESSION_STATE["unlocked_at"] = now
    sessions = _list_saved_sessions_internal(limit=12, status_filter="ALL")
    if sessions and not SESSION_STATE.get("selected_session"):
        top = sessions[0]
        top_id = str(top.get("conversation_id") or "")
        SESSION_STATE["selected_session"] = top_id
        SESSION_STATE["selected_workspace"] = str(top.get("workspace_path") or "")
        SESSION_STATE["selected_workspace_uris"] = SESSION_STATE["session_workspace_uris_map"].get(top_id, [])
        SESSION_STATE["selected_project"] = str(top.get("project_id") or "")
    _save_session_state()

    projects_map = _load_projects_map()
    stats_bundle = build_nexus_stats_bundle(
        data_dir=AGY_DATA_DIR,
        brain_dir=AGY_BRAIN_DIR,
        db_file=AGY_DB_FILE,
        config_dir=AGY_CONFIG_DIR,
        bg_dir=AGY_BG_DIR,
        period="last_90d",
        style=style,
    )
    sel_id = SESSION_STATE.get("selected_session", "")
    payload: dict[str, Any] = {
        "ok": True,
        "locked": False,
        "message": "Deadbolt unlocked. Session list and live telemetry stats retrieved successfully.",
        "assistant_guidance": (
            "Deadbolt unlocked. If the user asked for stats, display ascii_mobile_report inside a ```text block now. "
            "If the user asked to inspect a session or codebase, proceed directly to load_session_into_gemini or ask_workspace_readonly "
            "(batching needed files via comma-separated file_subpath) without asking for confirmation."
        ),
        "ttl_seconds": TTL_SECONDS,
        "selected_session": sel_id,
        "selected_session_title": SESSION_STATE["session_title_map"].get(sel_id, ""),
        "ascii_mobile_report": stats_bundle.get("ascii_mobile_report", ""),
        "quota_and_pools": stats_bundle.get("quota_and_pools", {}),
        "available_projects": list(projects_map.values()),
        "active_sessions_count": len(sessions),
        "sessions": sessions,
    }
    if search_query.strip():
        payload["search_results"] = _search_workspaces_and_history(search_query.strip())
    return _compact_json(payload)


@mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
def lock_bridge() -> str:
    """Manually engage the security deadbolt immediately, clearing active session selections."""
    SESSION_STATE["unlocked_at"] = 0.0
    SESSION_STATE["selected_session"] = ""
    SESSION_STATE["selected_workspace"] = ""
    SESSION_STATE["selected_workspace_uris"] = []
    SESSION_STATE["selected_project"] = ""
    _save_session_state()
    return _compact_json({
        "ok": True,
        "locked": True,
        "message": "Security Deadbolt engaged. Bridge locked. Passphrase required to re-authenticate."
    })


@mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
def list_saved_sessions(
    limit: int = 15,
    status_filter: str = "ALL",
    include_subagents: bool = False,
    spoken_passphrase: str = "",
) -> str:
    """List recent Antigravity conversations with execution status, project, workspace, step count, and task previews."""
    if not is_unlocked(spoken_passphrase):
        return LOCKED_RESPONSE

    sessions = _list_saved_sessions_internal(
        limit=max(1, min(limit, 30)),
        status_filter=status_filter,
        include_subagents=include_subagents,
    )
    projects_map = _load_projects_map()
    return _compact_json({
        "ok": True,
        "assistant_guidance": (
            "Sessions listed. If the user asked to inspect a specific session or codebase, call load_session_into_gemini "
            "or ask_workspace_readonly directly to gather all needed files before replying."
        ),
        "count": len(sessions),
        "available_projects": list(projects_map.values()),
        "sessions": sessions,
    })


def _resolve_workspace_str(ws_input: str) -> str:
    """Resolve short repo names, case-insensitive project names, or URIs to a canonical workspace path."""
    raw = re.sub(r"^file://", "", (ws_input or "").strip()).rstrip("/")
    if not raw:
        raw = SESSION_STATE.get("selected_workspace") or str(AGY_GITLAB_DIR / "antigravity-config")

    # 1. If it's an existing directory on disk (and not the bare AGY_GITLAB_DIR parent when a repo is needed)
    p = Path(raw)
    if p.is_absolute() and p.is_dir():
        return str(p.resolve())

    # 2. Check case-insensitive match under AGY_GITLAB_DIR
    target_name = p.name if p.is_absolute() else raw.strip("/")
    if AGY_GITLAB_DIR.is_dir() and target_name:
        exact_gitlab = AGY_GITLAB_DIR / target_name
        if exact_gitlab.is_dir():
            return str(exact_gitlab.resolve())
        for entry in AGY_GITLAB_DIR.iterdir():
            if entry.is_dir() and entry.name.lower() == target_name.lower():
                return str(entry.resolve())

    # 3. Check project map by project name or project_id
    projects_map = _load_projects_map()
    q_lower = target_name.lower()
    for pid, pinfo in projects_map.items():
        pname = str(pinfo.get("name") or "").lower()
        p_paths = pinfo.get("workspace_paths") or []
        if q_lower and (q_lower == pid.lower() or q_lower == pname or q_lower in pname):
            if p_paths:
                return str(p_paths[0])

    # 4. Check worktrees under AGY_DATA_DIR / "worktrees"
    wt_root = AGY_DATA_DIR / "worktrees"
    if wt_root.is_dir() and target_name:
        for proj_wt in wt_root.iterdir():
            if proj_wt.is_dir() and proj_wt.name.lower() == q_lower:
                sub_wts = sorted([d for d in proj_wt.iterdir() if d.is_dir()], key=lambda x: x.stat().st_mtime, reverse=True)
                if sub_wts:
                    return str(sub_wts[0].resolve())

    return raw


def _resolve_and_read_files(
    file_subpath_csv: str,
    ws: Path,
    session_dir: Path | None = None,
    max_chars_per_file: int = MAX_FILE_CHARS,
    max_total_chars: int = MAX_TOTAL_FILE_CHARS,
    start_line: int = 0,
    end_line: int = 0,
) -> dict[str, Any]:
    """Read one or more comma/semicolon-separated file subpaths across workspace, worktrees, brain session directory, or GitLab root, supporting line ranges and centered target lines."""
    raw_items = [p.strip() for p in re.split(r"[,;\n]+", file_subpath_csv or "") if p.strip()]
    if not raw_items:
        return {}

    search_roots: list[Path] = []
    if ws.is_dir():
        search_roots.append(ws.resolve())
    elif (AGY_DATA_DIR / "worktrees" / ws.name).is_dir():
        proj_wt = AGY_DATA_DIR / "worktrees" / ws.name
        sub_wts = sorted([d for d in proj_wt.iterdir() if d.is_dir()], key=lambda x: x.stat().st_mtime, reverse=True)
        if sub_wts:
            search_roots.append(sub_wts[0].resolve())

    for extra_uri in SESSION_STATE.get("selected_workspace_uris", []):
        clean_u = re.sub(r"^file://", "", str(extra_uri)).rstrip("/")
        if clean_u:
            ep = Path(clean_u)
            if ep.is_dir() and ep.resolve() not in search_roots:
                search_roots.append(ep.resolve())

    if not search_roots:
        search_roots.append(AGY_GITLAB_DIR.resolve())

    allowed = tuple(
        set(search_roots)
        | {
            AGY_GITLAB_DIR.resolve(),
            AGY_DATA_DIR.resolve(),
            AGY_BRAIN_DIR.resolve(),
            (AGY_DATA_DIR / "worktrees").resolve(),
            AGY_CONFIG_DIR.resolve(),
            (AGY_DATA_DIR / "builtin").resolve(),
        }
    )
    items_slice = raw_items[:MAX_FILES_PER_CALL]
    remaining_total_chars = max_total_chars
    files_list: list[dict[str, Any]] = []

    for raw_sub in items_slice:
        per_file_cap = min(max_chars_per_file, max(4000, remaining_total_chars))
        cleaned = re.sub(r"^file://", "", raw_sub.strip())
        # Strip leading "[repo_name] " prefix if copied from code_search_matches
        cleaned = re.sub(r"^\[[^\]]+\]\s*", "", cleaned)
        cleaned_no_line, in_start, in_end, in_center = parse_inline_line_spec(cleaned)

        candidates: list[Path] = []
        cust_match = resolve_customization_file(cleaned_no_line or cleaned, AGY_CONFIG_DIR, AGY_DATA_DIR, ws if ws.is_dir() else None)
        if cust_match:
            candidates.append(cust_match)
        for variant in (cleaned, cleaned_no_line):
            if not variant:
                continue
            if variant.startswith("/"):
                candidates.append(Path(os.path.normpath(variant)).resolve())
            norm_sub = os.path.normpath(variant).lstrip("/")
            for sroot in search_roots:
                candidates.append((sroot / norm_sub).resolve())
                if norm_sub.startswith("packages/"):
                    candidates.append((sroot / norm_sub[len("packages/"):]).resolve())
                else:
                    candidates.append((sroot / "packages" / norm_sub).resolve())
                if norm_sub.startswith(f"{sroot.name}/"):
                    candidates.append((sroot / norm_sub[len(sroot.name) + 1:]).resolve())
            if session_dir and session_dir.is_dir():
                candidates.append((session_dir / norm_sub).resolve())
                candidates.append((session_dir / "scratch" / Path(norm_sub).name).resolve())
                candidates.append((session_dir / Path(norm_sub).name).resolve())
            candidates.append((AGY_GITLAB_DIR / norm_sub).resolve())
            candidates.append((AGY_CONFIG_DIR / norm_sub).resolve())

        target_path = candidates[0] if candidates else (ws / raw_sub).resolve()
        for cand in candidates:
            try:
                if cand.is_file():
                    target_path = cand
                    break
            except Exception:
                continue

        is_sensitive_cfg = target_path.name.startswith(("config.json", "mcp_config.json", "secrets.env"))
        is_safe = (not is_sensitive_cfg) and any(target_path.is_relative_to(a) for a in allowed)
        if not is_safe:
            files_list.append({"requested": raw_sub, "error": "Access denied: path outside authorized workspace boundaries."})
        elif target_path.is_file():
            try:
                full_text = target_path.read_text(encoding="utf-8", errors="replace")
                slice_meta = slice_file_content(
                    full_text=full_text,
                    clean_path=cleaned_no_line or target_path.name,
                    per_file_cap=per_file_cap,
                    explicit_start_line=start_line,
                    explicit_end_line=end_line,
                    inline_start_line=in_start,
                    inline_end_line=in_end,
                    center_line=in_center,
                )
                remaining_total_chars = max(4000, remaining_total_chars - len(slice_meta.get("content", "")))
                entry_obj: dict[str, Any] = {
                    "requested": raw_sub,
                    "path": str(target_path),
                    "bytes": target_path.stat().st_size,
                    **slice_meta,
                }
                files_list.append(entry_obj)
            except Exception as e:
                files_list.append({"requested": raw_sub, "error": f"Error reading file: {e}"})
        else:
            nearby: list[str] = []
            try:
                base_root = search_roots[0]
                probe = (base_root / os.path.normpath(cleaned_no_line).lstrip("/")).resolve()
                cur_dir = probe.parent
                while cur_dir != base_root and not cur_dir.is_dir() and cur_dir.is_relative_to(base_root):
                    cur_dir = cur_dir.parent
                if cur_dir.is_dir() and cur_dir.is_relative_to(base_root):
                    for p_item in sorted(cur_dir.rglob("*")):
                        if p_item.is_file() and ".git" not in p_item.parts and "node_modules" not in p_item.parts:
                            nearby.append(str(p_item.relative_to(base_root)))
                            if len(nearby) >= 15:
                                break
            except Exception:
                pass
            err_entry: dict[str, Any] = {"requested": raw_sub, "error": f"File not found: {raw_sub}"}
            if nearby:
                err_entry["existing_files_in_parent"] = nearby
            files_list.append(err_entry)

    if len(files_list) == 1:
        return files_list[0]
    return {"count": len(files_list), "files": files_list}


def _host_git_inspect(
    ws_path: str,
    target_branch: str = "HEAD",
    include_untracked: bool = True,
    summary_only: bool = False,
    file_path: str = "",
) -> dict[str, Any]:
    """Fallback to agy-incident-bridge host git-inspect when a workspace or worktree parent .git lives on the host."""
    try:
        req = urllib.request.Request(
            AGY_HOST_BRIDGE_URL,
            data=json.dumps({
                "action": "git-inspect",
                "workspace_path": ws_path,
                "target_branch": target_branch,
                "include_untracked": include_untracked,
                "summary_only": summary_only,
                "file_path": file_path,
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
            if isinstance(data, dict) and data.get("ok"):
                return data
    except Exception:
        pass
    return {}


def _collect_git_summary(ws: Path | str) -> dict[str, Any]:
    """Return branch, short status, diff stat, and untracked files list for a workspace (with host-bridge fallback)."""
    ws_str = str(ws)
    ws_path = Path(ws_str)
    if ws_path.is_dir() and ws_path.resolve() != AGY_GITLAB_DIR.resolve():
        try:
            branch_proc = subprocess.run(
                ["git", "-c", "safe.directory=*", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(ws_path), capture_output=True, text=True, timeout=4, check=False,
            )
            if branch_proc.returncode == 0:
                status_proc = subprocess.run(
                    ["git", "-c", "safe.directory=*", "status", "--short"],
                    cwd=str(ws_path), capture_output=True, text=True, timeout=4, check=False,
                )
                stat_proc = subprocess.run(
                    ["git", "-c", "safe.directory=*", "diff", "--stat", "HEAD", "--"],
                    cwd=str(ws_path), capture_output=True, text=True, timeout=4, check=False,
                )
                untracked_proc = subprocess.run(
                    ["git", "-c", "safe.directory=*", "ls-files", "--others", "--exclude-standard"],
                    cwd=str(ws_path), capture_output=True, text=True, timeout=4, check=False,
                )
                untracked = [l.strip() for l in untracked_proc.stdout.splitlines() if l.strip()][:80]
                return {
                    "current_branch": branch_proc.stdout.strip(),
                    "status_short": status_proc.stdout.strip(),
                    "diff_stat": stat_proc.stdout.strip(),
                    "untracked_files": untracked,
                }
        except Exception:
            pass

    if ws_str and Path(ws_str) != AGY_GITLAB_DIR:
        host_res = _host_git_inspect(ws_str, target_branch="HEAD", include_untracked=True, summary_only=True)
        if host_res:
            return {
                "current_branch": host_res.get("current_branch", ""),
                "status_short": host_res.get("status_short", ""),
                "diff_stat": host_res.get("diff_stat", ""),
                "untracked_files": host_res.get("untracked_files", [])[:80],
            }
    return {}


def _compact_markdown(text: str, max_chars: int = 5500) -> str:
    """Keep markdown under max_chars while preserving all section headings, intro, and the latest trailing sections."""
    if len(text) <= max_chars:
        return text
    toc_cap = max(300, int(max_chars * 0.14))
    head_cap = max(600, int(max_chars * 0.35))
    tail_cap = max(800, int(max_chars * 0.43))
    headings = [line.strip() for line in text.splitlines() if line.lstrip().startswith("#")][:40]
    toc = "\n".join(headings)[:toc_cap]
    head_part = text[:head_cap]
    tail_part = text[-tail_cap:]
    return (
        f"[Document Outline ({len(text)} total chars — use ask_workspace_readonly(file_subpath=..., start_line=..., end_line=...) for middle sections)]:\n"
        f"{toc}\n\n"
        f"--- [Beginning] ---\n{head_part}\n\n"
        f"... [middle omitted] ...\n\n"
        f"--- [End (Latest Checkpoints)] ---\n{tail_part}"
    )


def _resolve_session_identifier(ident_raw: str) -> str:
    """Resolve index ('1', '#1'), conversation UUID/prefix, title keyword, project name, or workspace URI to a conversation_id."""
    ident = (ident_raw or "").strip()
    if not ident:
        return ""
    ident_num = re.sub(r"^(?:session|index|item|#)\s*", "", ident, flags=re.I).strip()
    conv_id = SESSION_STATE["session_index_map"].get(ident_num) or SESSION_STATE["session_index_map"].get(ident, "")
    if conv_id and (AGY_BRAIN_DIR / conv_id).is_dir():
        return conv_id

    candidate_id = re.sub(r"[^a-zA-Z0-9_-]", "", ident)
    if candidate_id and len(candidate_id) >= 32 and (AGY_BRAIN_DIR / candidate_id).is_dir():
        return candidate_id

    sessions = _list_saved_sessions_internal(limit=25, status_filter="ALL", include_subagents=False)
    conv_id = SESSION_STATE["session_index_map"].get(ident_num) or SESSION_STATE["session_index_map"].get(ident, "")
    if conv_id and (AGY_BRAIN_DIR / conv_id).is_dir():
        return conv_id

    ident_lower = ident.lower()
    for s in sessions:
        sid = str(s.get("conversation_id", ""))
        all_uris = " ".join(str(u) for u in (s.get("workspace_uris") or [])).lower()
        if (
            ident_lower == sid.lower()
            or (len(ident_lower) >= 6 and sid.lower().startswith(ident_lower))
            or ident_lower in str(s.get("title", "")).lower()
            or ident_lower in str(s.get("project_name", "")).lower()
            or ident_lower in str(s.get("workspace_path", "")).lower()
            or ident_lower in all_uris
        ):
            return sid
    return candidate_id if (candidate_id and (AGY_BRAIN_DIR / candidate_id).is_dir()) else ""


def _session_matches_repo_hint(conv_id: str, repo_hint: str) -> bool:
    """Return True if conv_id's workspace_uris, workspace_path, project mapping, or title matches repo_hint."""
    if not conv_id or not repo_hint:
        return False
    rh = repo_hint.lower().strip("/")
    uris = SESSION_STATE.get("session_workspace_uris_map", {}).get(conv_id) or []
    ws = str(SESSION_STATE.get("session_workspace_map", {}).get(conv_id) or "")
    title = str(SESSION_STATE.get("session_title_map", {}).get(conv_id) or "").lower()
    all_paths = [ws.lower()] + [str(u).lower() for u in uris]
    for p in all_paths:
        if rh in p or p.endswith("/" + rh):
            return True
    if rh == "antigravity-config" and any(k in title for k in ("mcp", "antigravity", "nexus", "bridge")):
        return True
    for pinfo in _load_projects_map().values():
        pname = str(pinfo.get("name") or "").lower()
        p_paths = [str(x).lower() for x in (pinfo.get("workspace_paths") or [])]
        if any(rh in pp for pp in p_paths) and pname and pname in title:
            return True
    return rh in title


def _extract_handoff_repo_hint(
    workspace_path: str,
    project_name: str,
    session_title: str,
    activate_skills: str,
    research_markdown: str,
) -> str:
    """Extract target repository name from handoff parameters, local git directories, or markdown."""
    for explicit in (workspace_path, project_name):
        clean_exp = (explicit or "").strip().rstrip("/")
        if clean_exp:
            resolved = _resolve_workspace_str(clean_exp)
            if resolved:
                return Path(resolved).name.lower()
    md = f"{session_title or ''}\n{activate_skills or ''}\n{research_markdown or ''}"
    gitlab_re = re.escape(str(AGY_GITLAB_DIR))
    m_repo = re.search(rf"{gitlab_re}/([a-zA-Z0-9._-]+)", md)
    if m_repo:
        return m_repo.group(1).lower()
    if any(k in md.lower() for k in ("sidecars/ag-bridge-mcp", "ag_bridge.py", "ag_bridge_stats.py", "agy-nexus-stats", "agy-nexus-mcp")):
        return "antigravity-config"
    known_repos: list[str] = ["antigravity-config"]
    if AGY_GITLAB_DIR.is_dir():
        known_repos.extend(d.name.lower() for d in AGY_GITLAB_DIR.iterdir() if d.is_dir() and not d.name.startswith("."))
    wt_root = AGY_DATA_DIR / "worktrees"
    if wt_root.is_dir():
        known_repos.extend(d.name.lower() for d in wt_root.iterdir() if d.is_dir() and not d.name.startswith("."))
    for known_repo in dict.fromkeys(known_repos):
        if len(known_repo) >= 3 and re.search(rf"\b{re.escape(known_repo)}\b", md, re.I):
            return known_repo
    return ""


def _resolve_target_session_for_handoff(
    session_identifier: str,
    workspace_path: str,
    project_name: str,
    session_title: str,
    activate_skills: str,
    research_markdown: str,
) -> tuple[str, str]:
    """Deterministically resolve the target conversation_id for send_handoff_and_resume and guard against stale cross-project misrouting."""
    ident_clean = (session_identifier or "").strip()
    if ident_clean:
        ident_num = re.sub(r"^(?:session|index|item|#)\s*", "", ident_clean, flags=re.I).strip()
        cached_conv = SESSION_STATE["session_index_map"].get(ident_num) or SESSION_STATE["session_index_map"].get(ident_clean, "")
        if cached_conv and (AGY_BRAIN_DIR / cached_conv).is_dir():
            SESSION_STATE["selected_session"] = cached_conv
            SESSION_STATE["selected_workspace"] = SESSION_STATE["session_workspace_map"].get(cached_conv, "")
            SESSION_STATE["selected_workspace_uris"] = SESSION_STATE["session_workspace_uris_map"].get(cached_conv, [])
            SESSION_STATE["selected_project"] = SESSION_STATE["session_project_map"].get(cached_conv, "")
            _save_session_state()
            return cached_conv, f"explicit_session_identifier ({ident_clean})"

    sessions = _list_saved_sessions_internal(limit=20, status_filter="ALL", include_subagents=False)

    # 1. Explicit session_identifier always wins
    if ident_clean:
        resolved = _resolve_session_identifier(ident_clean)
        if resolved:
            SESSION_STATE["selected_session"] = resolved
            SESSION_STATE["selected_workspace"] = SESSION_STATE["session_workspace_map"].get(resolved, "")
            SESSION_STATE["selected_workspace_uris"] = SESSION_STATE["session_workspace_uris_map"].get(resolved, [])
            SESSION_STATE["selected_project"] = SESSION_STATE["session_project_map"].get(resolved, "")
            _save_session_state()
            return resolved, f"explicit_session_identifier ({ident_clean})"

    # 2. Check repo/project hint from handoff markdown & arguments against selected_session
    repo_hint = _extract_handoff_repo_hint(workspace_path, project_name, session_title, activate_skills, research_markdown)
    current_conv = SESSION_STATE.get("selected_session", "")

    if repo_hint:
        if current_conv and _session_matches_repo_hint(current_conv, repo_hint):
            return current_conv, f"selected_session_matched_repo ({repo_hint})"
        # Current selected_session is missing or belongs to a DIFFERENT repo (e.g., stale session from another project)!
        for s in sessions:
            sid = str(s.get("conversation_id") or "")
            if _session_matches_repo_hint(sid, repo_hint):
                prev_note = f"overrode mismatched session {current_conv[:8]}" if current_conv else "auto-selected"
                SESSION_STATE["selected_session"] = sid
                SESSION_STATE["selected_workspace"] = SESSION_STATE["session_workspace_map"].get(sid, "")
                SESSION_STATE["selected_workspace_uris"] = SESSION_STATE["session_workspace_uris_map"].get(sid, [])
                SESSION_STATE["selected_project"] = SESSION_STATE["session_project_map"].get(sid, "")
                _save_session_state()
                return sid, f"auto_matched_repo:{repo_hint} ({prev_note})"

    # 3. Fallback to current_conv or #1 most recently modified session
    if current_conv and (AGY_BRAIN_DIR / current_conv).is_dir():
        return current_conv, "selected_session"
    if sessions:
        top_id = str(sessions[0].get("conversation_id") or "")
        if top_id:
            SESSION_STATE["selected_session"] = top_id
            SESSION_STATE["selected_workspace"] = SESSION_STATE["session_workspace_map"].get(top_id, "")
            SESSION_STATE["selected_workspace_uris"] = SESSION_STATE["session_workspace_uris_map"].get(top_id, [])
            SESSION_STATE["selected_project"] = SESSION_STATE["session_project_map"].get(top_id, "")
            _save_session_state()
            return top_id, "most_recent_session_fallback"
    return "", "none"


@mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
def load_session_into_gemini(
    session_identifier: str,
    spoken_passphrase: str = "",
    include_files: str = "",
) -> str:
    """Load complete conversation context in a single call (live execution_status, git_summary with untracked files, Antigravity's latest_assistant_response, task.md, implementation_plan.md, walkthrough.md, and recent transcript turns).

    IMPORTANT: Because execution_status and git_summary are already included in this response, DO NOT chain manage_background_run or inspect_git_diff after calling this tool—reply directly to the user!
    """
    if not is_unlocked(spoken_passphrase):
        return LOCKED_RESPONSE

    ident = session_identifier.strip()
    conv_id = _resolve_session_identifier(ident)
    session_dir = AGY_BRAIN_DIR / conv_id if conv_id else AGY_BRAIN_DIR / "__missing__"
    if not conv_id or not session_dir.is_dir():
        return json.dumps({"ok": False, "error": f"Session directory not found for session_identifier '{ident}'."}, indent=2)

    SESSION_STATE["selected_session"] = conv_id
    workspace = SESSION_STATE["session_workspace_map"].get(conv_id, "")
    workspace_uris: list[str] = []
    project_id = SESSION_STATE["session_project_map"].get(conv_id, "")
    db_status_info: dict[str, Any] = {}
    if AGY_DB_FILE.is_file():
        try:
            con = sqlite3.connect(f"file:{AGY_DB_FILE}?mode=ro", uri=True)
            row = con.execute(
                "SELECT workspace_uris, project_id, status, step_count, last_modified_time, not_fully_idle, killed FROM conversation_summaries WHERE conversation_id = ?",
                (conv_id,),
            ).fetchone()
            con.close()
            if row:
                if row[0]:
                    uris = json.loads(row[0])
                    if uris and isinstance(uris, list):
                        workspace_uris = [re.sub(r"^file://", "", str(u)).rstrip("/") for u in uris if u]
                        if not workspace and workspace_uris:
                            workspace = workspace_uris[0]
                if not project_id and row[1]:
                    project_id = str(row[1])
                db_status_info = {
                    "db_status": str(row[2] or "CASCADE_RUN_STATUS_IDLE"),
                    "step_count": int(row[3] or 0),
                    "last_modified": str(row[4] or ""),
                    "is_running": bool(row[5]) or str(row[2] or "") == "CASCADE_RUN_STATUS_RUNNING",
                    "not_fully_idle": bool(row[5]),
                    "killed": bool(row[6]),
                    "summary": (
                        "RUNNING" if (bool(row[5]) or str(row[2] or "") == "CASCADE_RUN_STATUS_RUNNING")
                        else "COMPLETED_AND_IDLE (Antigravity finished; do NOT call manage_background_run)"
                    ),
                }
        except Exception:
            pass

    projects_map = _load_projects_map()
    project_name = projects_map.get(project_id, {}).get("name", project_id)
    if not workspace and project_id in projects_map:
        p_paths = projects_map[project_id].get("workspace_paths", [])
        if p_paths:
            workspace = p_paths[0]
            if not workspace_uris:
                workspace_uris = list(p_paths)
    if not workspace:
        workspace = str(AGY_GITLAB_DIR)
    SESSION_STATE["selected_workspace"] = workspace
    SESSION_STATE["selected_workspace_uris"] = workspace_uris
    SESSION_STATE["selected_project"] = project_id
    _save_session_state()

    has_inc = bool(include_files.strip())
    task_cap = MAX_TASK_DOC_CHARS
    plan_cap = 24000
    walk_cap = 24000
    resp_cap = 8000
    turns_cap = MAX_TRANSCRIPT_TURNS

    # Read artifacts with generous full-document budget (only compacting if a massive artifact exceeds 24,000 chars)
    task_file = session_dir / "task.md"
    task_raw = task_file.read_text(encoding="utf-8", errors="replace") if task_file.is_file() else ""
    task_content = _compact_markdown(task_raw, max_chars=task_cap) if task_raw else ""

    plan_file = session_dir / "implementation_plan.md"
    plan_raw = plan_file.read_text(encoding="utf-8", errors="replace") if plan_file.is_file() else ""
    plan_content = _compact_markdown(plan_raw, max_chars=plan_cap) if plan_raw else ""

    walk_file = session_dir / "walkthrough.md"
    walk_raw = walk_file.read_text(encoding="utf-8", errors="replace") if walk_file.is_file() else ""
    walk_content = _compact_markdown(walk_raw, max_chars=walk_cap) if walk_raw else ""

    scratch_dir = session_dir / "scratch"
    scratch_files = [f.name for f in scratch_dir.iterdir() if f.is_file()][:20] if scratch_dir.is_dir() else []

    # Read recent transcript turns AND capture Antigravity's latest final assistant response text
    transcript_file = session_dir / ".system_generated" / "logs" / "transcript.jsonl"
    recent_turns: list[dict[str, Any]] = []
    latest_assistant_response = ""
    if transcript_file.is_file():
        try:
            lines = transcript_file.read_text(encoding="utf-8", errors="replace").splitlines()
            for line in lines:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    etype = entry.get("type") or entry.get("role") or ""
                    if etype in ("USER_INPUT", "user"):
                        content = str(entry.get("content") or entry.get("text") or "")
                        recent_turns.append({
                            "type": "USER_INPUT",
                            "created_at": entry.get("created_at", ""),
                            "content": content[:500],
                        })
                    elif etype in ("PLANNER_RESPONSE", "assistant", "model"):
                        content = str(entry.get("content") or entry.get("text") or "").strip()
                        thinking = str(entry.get("thinking") or "").strip()
                        tool_calls_raw = entry.get("tool_calls", [])
                        tool_summary: list[str] = []
                        if isinstance(tool_calls_raw, list):
                            for tc in tool_calls_raw[:6]:
                                if isinstance(tc, dict):
                                    tool_summary.append(tc.get("name") or tc.get("toolAction") or "call")
                        if content:
                            latest_assistant_response = content[:resp_cap]
                        if content or thinking or tool_summary:
                            turn_obj: dict[str, Any] = {
                                "type": "PLANNER_RESPONSE",
                                "created_at": entry.get("created_at", ""),
                            }
                            if content:
                                turn_obj["content"] = content[:650]
                            elif thinking:
                                turn_obj["thinking_preview"] = thinking[:250]
                            if tool_summary:
                                turn_obj["tool_calls"] = tool_summary
                            recent_turns.append(turn_obj)
                except Exception:
                    continue
            recent_turns = recent_turns[-turns_cap:]
        except Exception as e:
            recent_turns.append({"error": f"Failed reading transcript: {e}"})

    ws_path = Path(workspace) if workspace else AGY_GITLAB_DIR
    git_summary = _collect_git_summary(ws_path)
    pending_app = extract_pending_approval(transcript_file)
    if pending_app:
        db_status_info["pending_approval"] = pending_app
    included_files = (
        _resolve_and_read_files(
            include_files,
            ws=ws_path,
            session_dir=session_dir,
            max_chars_per_file=MAX_FILE_CHARS,
            max_total_chars=MAX_TOTAL_FILE_CHARS,
        )
        if has_inc
        else {}
    )

    payload: dict[str, Any] = {
        "ok": True,
        "status": "LOADED",
        "conversation_id": conv_id,
        "project_id": project_id,
        "project_name": project_name,
        "workspace_path": workspace,
        "assistant_guidance": (
            "Session context loaded (execution_status, git_summary, task_content, implementation_plan, walkthrough, and recent turns). "
            "If you need to inspect any source files, skills, or scripts to complete your analysis or build a handoff, "
            "call ask_workspace_readonly now (batching comma-separated paths in file_subpath='f1,f2,f3')—do NOT stop mid-task to ask the user for permission to read files."
        ),
        "project_hygiene_standards": MODULAR_HYGIENE_STANDARDS,
        "execution_status": db_status_info,
        "git_summary": git_summary,
        "latest_assistant_response": latest_assistant_response,
        "task_content": task_content,
        "implementation_plan": plan_content,
        "walkthrough": walk_content,
        "scratch_files": scratch_files,
        "recent_transcript_turns": recent_turns,
    }
    if included_files:
        payload["included_files"] = included_files
    return _compact_json(payload)


@mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
def ask_workspace_readonly(
    question: str,
    search_query: str = "",
    file_subpath: str = "",
    start_line: int = 0,
    end_line: int = 0,
    spoken_passphrase: str = "",
) -> str:
    """Read-only codebase explorer querying one or up to 12 comma-separated files in full (up to 48 KB per file / 120 KB total per call; also supports line ranges via start_line/end_line or inline 'path/file.py:100-350' / 'path/file.py:420' syntax, plus 'skill:<name>' / 'agent:<name>' / 'rule:<name>'), git grep across local repositories, and SQLite FTS5 conversation history."""
    if not is_unlocked(spoken_passphrase):
        return LOCKED_RESPONSE

    ws_str = SESSION_STATE.get("selected_workspace") or str(AGY_GITLAB_DIR)
    ws = Path(ws_str)
    if not ws.is_dir() and not (AGY_DATA_DIR / "worktrees" / ws.name).is_dir():
        ws = AGY_GITLAB_DIR

    conv_id = SESSION_STATE.get("selected_session", "")
    session_dir = (AGY_BRAIN_DIR / conv_id) if conv_id else None
    file_result = _resolve_and_read_files(
        file_subpath,
        ws=ws,
        session_dir=session_dir,
        max_chars_per_file=MAX_FILE_CHARS,
        max_total_chars=MAX_TOTAL_FILE_CHARS,
        start_line=start_line,
        end_line=end_line,
    )

    effective_query = search_query.strip()
    if not effective_query and not file_subpath.strip() and question.strip():
        # Extract meaningful keywords only when no explicit file_subpath was requested
        words = [w for w in re.findall(r"[A-Za-z0-9_-]{4,}", question) if w.lower() not in {"find", "existing", "project", "current", "what", "where", "with", "from", "that", "this", "read", "check", "audit"}]
        if words:
            effective_query = words[0]

    search_bundle = (
        _search_workspaces_and_history(effective_query, primary_ws=ws if ws.is_dir() else None)
        if effective_query
        else {
            "configured_mcp_servers": _get_configured_mcp_servers(),
            "available_repositories": [],
            "code_search_matches": [],
            "historical_session_matches": [],
        }
    )

    out_ws: dict[str, Any] = {
        "ok": True,
        "question": question,
        "workspace": str(ws),
        "assistant_guidance": (
            "Workspace query complete. If you identified additional files to inspect (or if a >1,000-line file has truncated=True and you need its remaining lines), "
            "call ask_workspace_readonly again immediately in this turn (batching comma-separated file_subpath='f1,f2,f3')—NEVER stop mid-task to ask the user whether you should read another file or section."
        ),
        "selected_session_status": _get_selected_session_quick_status(),
        "file_details": file_result,
        "code_search_matches": search_bundle["code_search_matches"],
        "historical_session_matches": search_bundle["historical_session_matches"],
    }
    if not file_subpath.strip():
        out_ws["configured_mcp_servers"] = search_bundle["configured_mcp_servers"]
        out_ws["available_repositories"] = search_bundle["available_repositories"]
    return _compact_json(out_ws)


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
            "title": title_clean,
            "prompt": spawn_prompt,
            "project_id": eff_project_id,
            "project_name": eff_project_name,
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
            "job_id": job_id,
            "conversation_id": conv_id,
            "project_id": bridge_response.get("project_id", eff_project_id),
            "project_name": bridge_response.get("project_name", eff_project_name),
            "workspace_path": bridge_response.get("workspace_path", eff_workspace_path),
            "started_at": ts_now,
            "execution_mode": execution_mode,
            "model": model,
            "effort": effort,
            "created_new_session": True,
            "modular_hygiene_enforced": apply_hygiene,
            "customization_scope_info": cust_scope_info,
            "bridge_response": bridge_response,
        }
        (AGY_BG_DIR / f"{job_id}.json").write_text(json.dumps(job_metadata, indent=2) + "\n", encoding="utf-8")
        out_new: dict[str, Any] = {
            "ok": bridge_response.get("ok", False),
            "status": "RESUMED",
            "created_new_session": True,
            "resumed": True,
            "write_mode": write_mode,
            "chars_written": len(body_clean),
            "modular_hygiene_enforced": apply_hygiene,
            "customization_scope_info": cust_scope_info,
            "job_id": job_id,
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
            "ok": True,
            "status": "STAGED",
            "resumed": False,
            "write_mode": write_mode,
            "chars_written": len(body_clean),
            "modular_hygiene_enforced": apply_hygiene,
            "customization_scope_info": cust_scope_info,
            "conversation_id": "",
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
            "ok": True,
            "status": "STAGED",
            "resumed": False,
            "write_mode": write_mode,
            "chars_written": len(body_clean),
            "modular_hygiene_enforced": apply_hygiene,
            "customization_scope_info": cust_scope_info,
            "conversation_id": conv_id,
            "conversation_title": conv_title,
            "routing_reason": routing_reason,
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
        "action": "send-message",
        "conversation_id": conv_id,
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
        "job_id": job_id,
        "conversation_id": conv_id,
        "conversation_title": conv_title,
        "routing_reason": routing_reason,
        "started_at": ts_now,
        "execution_mode": execution_mode,
        "model": model,
        "effort": effort,
        "use_worktree": use_worktree,
        "modular_hygiene_enforced": apply_hygiene,
        "customization_scope_info": cust_scope_info,
        "bridge_response": bridge_response,
    }
    (AGY_BG_DIR / f"{job_id}.json").write_text(json.dumps(job_metadata, indent=2) + "\n", encoding="utf-8")

    out_resumed: dict[str, Any] = {
        "ok": bridge_response.get("ok", False),
        "status": "RESUMED",
        "resumed": True,
        "write_mode": write_mode,
        "chars_written": len(body_clean),
        "modular_hygiene_enforced": apply_hygiene,
        "customization_scope_info": cust_scope_info,
        "job_id": job_id,
        "conversation_id": conv_id,
        "conversation_title": conv_title,
        "routing_reason": routing_reason,
        "handoff_file": str(handoff_file),
        "assistant_guidance": "STOP AND REPLY TO USER NOW: Handoff delivered and Antigravity session resumed in the background. Do NOT call manage_background_run in this same turn.",
        "bridge_response": bridge_response,
    }
    if size_warning:
        out_resumed["size_warning"] = size_warning
    return json.dumps(out_resumed, indent=2)


def _summarize_jsonl_line(raw_line: str) -> dict[str, Any]:
    """Parse a raw transcript.jsonl line into a compact, readable summary object."""
    try:
        entry = json.loads(raw_line)
        if not isinstance(entry, dict):
            return {"raw": raw_line[:300]}
        summary: dict[str, Any] = {
            "step_index": entry.get("step_index"),
            "type": entry.get("type") or entry.get("role") or "EVENT",
            "status": entry.get("status", ""),
            "created_at": entry.get("created_at", ""),
        }
        content = str(entry.get("content") or entry.get("text") or "").strip()
        if content:
            summary["content_preview"] = content[:350]
        tool_calls = entry.get("tool_calls")
        if isinstance(tool_calls, list) and tool_calls:
            summary["tools"] = [str(tc.get("name") or tc.get("toolAction") or "call") for tc in tool_calls[:5] if isinstance(tc, dict)]
        return summary
    except Exception:
        return {"raw": raw_line[:300]}


@mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
def manage_background_run(
    action: str = "status",
    job_id: str = "",
    tail_lines: int = 40,
    period: str = "last_90d",
    style: str = "default",
    client_product: str = "",
    client_tokens_reported: int = 0,
    spoken_passphrase: str = "",
) -> str:
    """Monitor background jobs, inspect live transcript progress, review session status, export session plans/walkthroughs for Gemini Notebook (action='export_notebook'), or retrieve live Dual-Pool Quota Pacing, Activity Heatmaps, and Wire Telemetry (action='stats' or action='telemetry', period='last_90d'|'current_month'|'last_month'|'last_year', style='default'|'quick'|'rich'). Optionally pass client_product ('Gemini Mobile', 'Gemini Web', 'Antigravity IDE') and client_tokens_reported to log client telemetry."""
    action_clean = action.strip().lower()
    is_stats_action = action_clean in ("stats", "dashboard", "quota", "heatmap", "telemetry", "wire", "logs")
    if not is_unlocked(spoken_passphrase):
        if not (ALLOW_LOCKED_STATS and is_stats_action):
            return LOCKED_RESPONSE

    if action_clean in ("export_notebook", "notebook", "sync_notebook"):
        export_res = export_notebook_bundle(
            brain_dir=AGY_BRAIN_DIR,
            db_file=AGY_DB_FILE,
            bg_dir=AGY_BG_DIR,
            projects_map=_load_projects_map(),
        )
        return _compact_json({
            "ok": True,
            "action": "export_notebook",
            "assistant_guidance": (
                "STOP AND REPLY TO USER NOW: Session walkthrough.md and implementation_plan.md artifacts have been exported "
                "with SHA-256 deduplication so unchanged files never trigger duplicate syncs."
            ),
            **export_res,
        })

    if action_clean in ("stats", "dashboard", "quota", "heatmap"):
        bundle = build_nexus_stats_bundle(
            data_dir=AGY_DATA_DIR,
            brain_dir=AGY_BRAIN_DIR,
            db_file=AGY_DB_FILE,
            config_dir=AGY_CONFIG_DIR,
            bg_dir=AGY_BG_DIR,
            period=period,
            style=style,
        )
        compact_bundle = {
            k: v
            for k, v in bundle.items()
            if k
            not in (
                "heatmap_series",
                "velocity_series",
                "workspace_series",
                "subagent_series",
                "ascii_mobile_dashboard",
                "ascii_report_default",
                "ascii_report_quick",
                "ascii_report_rich",
                "summary",
            )
        }
        return _compact_json({
            "ok": True,
            "action": "stats",
            "assistant_guidance": (
                "STOP AND REPLY TO USER NOW: Display ascii_mobile_report inside a fenced ```text code block first "
                "followed by a concise 3-bullet summary of Google 20x Pool share, Partner Weekly Pacing vs Target, and Top Projects."
            ),
            **compact_bundle,
        })

    if action_clean in ("telemetry", "wire", "logs"):
        return _compact_json({
            "ok": True,
            "action": "telemetry",
            "assistant_guidance": "STOP AND REPLY TO USER NOW with the wire telemetry and quota summary below.",
            "wire_telemetry": get_wire_telemetry_summary(AGY_BG_DIR, limit=25),
            "quota_and_pools": get_live_quota_and_pool_status(AGY_DATA_DIR, AGY_CONFIG_DIR),
        })

    conv_id = SESSION_STATE.get("selected_session", "")

    job_file: Path | None = None
    job_data: dict[str, Any] = {}
    safe_job_id = re.sub(r"[^a-zA-Z0-9_-]", "", job_id.strip())
    if safe_job_id and safe_job_id.lower() != "latest":
        cand_file = AGY_BG_DIR / f"{safe_job_id}.json"
        if cand_file.is_file():
            job_file = cand_file
            try:
                job_data = json.loads(job_file.read_text(encoding="utf-8"))
                conv_id = str(job_data.get("conversation_id") or conv_id)
            except Exception:
                pass

    # If no specific job_file found, locate latest job for conv_id (or newest global job)
    if not job_file and AGY_BG_DIR.is_dir():
        try:
            job_files = sorted(AGY_BG_DIR.glob("job-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            for jf in job_files:
                jdata = json.loads(jf.read_text(encoding="utf-8"))
                if not conv_id or jdata.get("conversation_id") == conv_id:
                    job_file = jf
                    job_data = jdata
                    safe_job_id = str(jdata.get("job_id") or jf.stem)
                    conv_id = str(jdata.get("conversation_id") or conv_id)
                    break
        except Exception:
            pass

    # If still no conv_id, default to most recent session in SQLite
    if not conv_id:
        sessions = _list_saved_sessions_internal(limit=1, status_filter="ALL")
        if sessions and sessions[0].get("conversation_id"):
            conv_id = str(sessions[0]["conversation_id"])

    if not conv_id:
        return json.dumps({"ok": False, "error": "No session selected and no valid job_id provided."}, indent=2)

    # Read live status from DB
    db_info: dict[str, Any] = {}
    if AGY_DB_FILE.is_file():
        try:
            con = sqlite3.connect(f"file:{AGY_DB_FILE}?mode=ro", uri=True)
            row = con.execute(
                "SELECT title, status, step_count, last_modified_time, not_fully_idle, killed FROM conversation_summaries WHERE conversation_id = ?",
                (conv_id,)
            ).fetchone()
            con.close()
            if row:
                db_info = {
                    "title": row[0],
                    "status": row[1],
                    "step_count": row[2],
                    "last_modified": row[3],
                    "not_fully_idle": bool(row[4]),
                    "killed": bool(row[5]),
                }
        except Exception:
            pass

    transcript_file = AGY_BRAIN_DIR / conv_id / ".system_generated" / "logs" / "transcript.jsonl"
    raw_lines: list[str] = []
    if transcript_file.is_file():
        try:
            all_lines = [l for l in transcript_file.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
            raw_lines = all_lines[-max(1, min(tail_lines, 60)):]
        except Exception:
            pass

    parsed_tail = [_summarize_jsonl_line(l) for l in raw_lines]
    pending_app = extract_pending_approval(transcript_file)

    if action_clean == "tail":
        return json.dumps({
            "ok": True,
            "conversation_id": conv_id,
            "job_id": safe_job_id,
            "assistant_guidance": "STOP AND REPLY TO USER NOW with the transcript tail below.",
            "pending_approval": pending_app,
            "tail_lines_count": len(parsed_tail),
            "transcript_tail": parsed_tail,
        }, indent=2)

    if action_clean == "stop":
        if job_file and job_file.is_file():
            job_data["stopped_at"] = datetime.now(timezone.utc).isoformat()
            job_file.write_text(json.dumps(job_data, indent=2) + "\n", encoding="utf-8")
        return json.dumps({
            "ok": True,
            "action": "stop",
            "conversation_id": conv_id,
            "job_id": safe_job_id,
            "assistant_guidance": "STOP AND REPLY TO USER NOW.",
            "message": "Job status marked as stopped.",
        }, indent=2)

    # Default action: status (also attach ascii_mobile_report & quota_and_pools so stats queries never need a 2nd tool call)
    stats_fallback = build_nexus_stats_bundle(
        data_dir=AGY_DATA_DIR,
        brain_dir=AGY_BRAIN_DIR,
        db_file=AGY_DB_FILE,
        config_dir=AGY_CONFIG_DIR,
        bg_dir=AGY_BG_DIR,
        period=period or "last_90d",
    )
    return _compact_json({
        "ok": True,
        "action": "status",
        "conversation_id": conv_id,
        "job_id": safe_job_id,
        "assistant_guidance": (
            "STOP AND REPLY TO USER NOW: Do NOT chain another tool call in this turn. "
            "If the user asked for stats, display ascii_mobile_report inside a ```text block now; otherwise report the job/session status."
        ),
        "ascii_mobile_report": stats_fallback.get("ascii_mobile_report", ""),
        "quota_and_pools": stats_fallback.get("quota_and_pools", {}),
        "job_metadata": job_data,
        "db_info": db_info,
        "pending_approval": pending_app,
        "has_gui_lock": (AGY_PRESENCE_DIR / f"{conv_id}.lock").is_file(),
        "recent_events_count": len(parsed_tail),
        "recent_sample": parsed_tail[-4:] if parsed_tail else [],
    })


@mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
def inspect_git_diff(
    target_branch: str = "HEAD",
    include_untracked: bool = True,
    workspace_override: str = "",
    file_path: str = "",
    offset_chars: int = 0,
    start_line: int = 0,
    end_line: int = 0,
    spoken_passphrase: str = "",
) -> str:
    """Inspect active git status, untracked files, and branch diffs across the target repository (or pass workspace_override='ALL' / comma-separated repo names for a 1-turn multi-repo drift audit). Supports filtering to a specific file_path (e.g. 'src/worker.ts') and paging through large diffs via offset_chars or start_line/end_line."""
    if not is_unlocked(spoken_passphrase):
        return LOCKED_RESPONSE

    raw_override = workspace_override.strip()
    if raw_override.upper() in ("ALL", "*", "ALL_REPOS") or "," in raw_override or ";" in raw_override:
        drift_bundle = inspect_multi_repo_drift(
            gitlab_dir=AGY_GITLAB_DIR,
            data_dir=AGY_DATA_DIR,
            workspace_override=raw_override,
            include_untracked=include_untracked,
        )
        return _compact_json({
            "assistant_guidance": (
                "STOP AND REPLY TO USER NOW: Multi-repository drift audit completed in a single turn. "
                "Do NOT chain a second tool call in this turn."
            ),
            "selected_session_status": _get_selected_session_quick_status(),
            **drift_bundle,
        })

    ws_str = _resolve_workspace_str(raw_override)
    ws = Path(ws_str)
    if ws == AGY_GITLAB_DIR or ws_str == str(AGY_GITLAB_DIR):
        ws = (AGY_GITLAB_DIR / "antigravity-config").resolve()
        ws_str = str(ws)

    safe_branch = re.sub(r"[^a-zA-Z0-9_./~^-]", "", target_branch.strip()).lstrip("-") or "HEAD"
    safe_file_path = ""
    if file_path.strip():
        norm_fp = os.path.normpath(file_path.strip()).lstrip("/")
        if not norm_fp.startswith(".."):
            safe_file_path = norm_fp

    configured_mcps = _get_configured_mcp_servers()

    allowed_local_roots = (AGY_GITLAB_DIR.resolve(), (AGY_DATA_DIR / "worktrees").resolve())
    if ws.is_dir():
        ws_res = ws.resolve()
        if any(ws_res.is_relative_to(r) for r in allowed_local_roots):
            try:
                branch_proc = subprocess.run(
                    ["git", "-c", "safe.directory=*", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=str(ws_res), capture_output=True, text=True, timeout=5, check=False
                )
                if branch_proc.returncode == 0:
                    current_branch = branch_proc.stdout.strip()
                    status_proc = subprocess.run(
                        ["git", "-c", "safe.directory=*", "status", "--short"],
                        cwd=str(ws_res), capture_output=True, text=True, timeout=5, check=False
                    )
                    stat_proc = subprocess.run(
                        ["git", "-c", "safe.directory=*", "diff", "--stat", safe_branch, "--"],
                        cwd=str(ws_res), capture_output=True, text=True, timeout=5, check=False
                    )
                    if stat_proc.returncode != 0 and safe_branch != "HEAD":
                        safe_branch = "HEAD"
                        stat_proc = subprocess.run(
                            ["git", "-c", "safe.directory=*", "diff", "--stat", "HEAD", "--"],
                            cwd=str(ws_res), capture_output=True, text=True, timeout=5, check=False
                        )
                    untracked_files: list[str] = []
                    if include_untracked:
                        untracked_proc = subprocess.run(
                            ["git", "-c", "safe.directory=*", "ls-files", "--others", "--exclude-standard"],
                            cwd=str(ws_res), capture_output=True, text=True, timeout=5, check=False
                        )
                        untracked_files = [l.strip() for l in untracked_proc.stdout.splitlines() if l.strip()][:120]

                    diff_cmd = ["git", "-c", "safe.directory=*", "diff", safe_branch, "--"]
                    if safe_file_path:
                        diff_cmd.append(safe_file_path)
                    diff_proc = subprocess.run(
                        diff_cmd,
                        cwd=str(ws_res), capture_output=True, text=True, timeout=10, check=False
                    )
                    diff_meta = slice_git_diff(
                        diff_out=diff_proc.stdout,
                        offset_chars=offset_chars,
                        max_diff_chars=MAX_DIFF_CHARS,
                        file_path=safe_file_path,
                        start_line=start_line,
                        end_line=end_line,
                    )
                    return _compact_json({
                        "ok": True,
                        "workspace": str(ws_res),
                        "assistant_guidance": (
                            "Git diff inspection complete. If you need to inspect any modified or untracked files in full, "
                            "call ask_workspace_readonly immediately (batching comma-separated file_subpath) before replying."
                        ),
                        "selected_session_status": _get_selected_session_quick_status(),
                        "configured_mcp_servers": configured_mcps,
                        "branch": current_branch,
                        "current_branch": current_branch,
                        "status_short": status_proc.stdout.strip(),
                        "diff_stat": stat_proc.stdout.strip(),
                        "untracked_files": untracked_files,
                        "target_branch": safe_branch,
                        **diff_meta,
                    })
            except Exception:
                pass

    # Fallback to host git-inspect for host-backed repositories/worktrees
    host_res = _host_git_inspect(
        ws_str,
        target_branch=safe_branch,
        include_untracked=include_untracked,
        summary_only=False,
        file_path=safe_file_path,
    )
    if host_res:
        br = host_res.get("branch") or host_res.get("current_branch", "")
        diff_meta = slice_git_diff(
            diff_out=str(host_res.get("diff", "")),
            offset_chars=offset_chars,
            max_diff_chars=MAX_DIFF_CHARS,
            file_path=safe_file_path,
            start_line=start_line,
            end_line=end_line,
        )
        return _compact_json({
            "ok": True,
            "workspace": host_res.get("workspace", ws_str),
            "assistant_guidance": (
                "Git diff inspection complete. If you need to inspect any modified or untracked files in full, "
                "call ask_workspace_readonly immediately (batching comma-separated file_subpath) before replying."
            ),
            "selected_session_status": _get_selected_session_quick_status(),
            "configured_mcp_servers": configured_mcps,
            "branch": br,
            "current_branch": br,
            "status_short": host_res.get("status_short", ""),
            "diff_stat": host_res.get("diff_stat", ""),
            "untracked_files": host_res.get("untracked_files", []),
            "target_branch": safe_branch,
            **diff_meta,
        })

    return _compact_json({"ok": False, "error": f"Unable to inspect git repository for workspace '{ws_str}'."})


@mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)
def list_models_and_agents(
    include_skills: bool = True,
    include_rules: bool = True,
    skill_scope_filter: str = "core",
    inspect_name: str = "",
    spoken_passphrase: str = "",
) -> str:
    """List Antigravity agent roles, core skills (workspace, user_global, builtin), installed plugin skill bundles (pass skill_scope_filter='all' or 'plugin:<name>' to expand plugin descriptions), global & workspace rules, Customization Scope-Isolation policy, modular hygiene standards, live Dual-Pool Quota Pacing, and Language Server connectivity. Pass inspect_name (e.g. 'agy-nexus-stats', 'argon-sentinel', 'GEMINI.md') to read a specific item."""
    if not is_unlocked(spoken_passphrase):
        return LOCKED_RESPONSE

    ws_str = SESSION_STATE.get("selected_workspace") or str(AGY_GITLAB_DIR / "antigravity-config")
    ws_path = Path(ws_str).resolve() if ws_str and Path(ws_str).is_dir() else None

    agents_list = collect_agents_inventory(AGY_CONFIG_DIR, ws_path)
    skills_list = (
        collect_skills_inventory(AGY_CONFIG_DIR, AGY_DATA_DIR, ws_path, scope_filter=skill_scope_filter)
        if include_skills
        else []
    )
    plugin_bundles = collect_plugin_bundles_summary(AGY_CONFIG_DIR) if include_skills else []
    rules_inv = collect_rules_inventory(AGY_CONFIG_DIR, ws_path) if include_rules else {}
    session_scope = evaluate_session_customization_scope(ws_str, AGY_CONFIG_DIR, AGY_GITLAB_DIR)
    quota_status = get_live_quota_and_pool_status(AGY_DATA_DIR, AGY_CONFIG_DIR)

    inspected_item: dict[str, Any] = {}
    if inspect_name.strip():
        clean_q, in_s, in_e, in_c = parse_inline_line_spec(inspect_name.strip())
        resolved_f = resolve_customization_file(clean_q or inspect_name.strip(), AGY_CONFIG_DIR, AGY_DATA_DIR, ws_path)
        if resolved_f and resolved_f.is_file():
            raw_txt = resolved_f.read_text(encoding="utf-8", errors="replace")
            slice_meta = slice_file_content(
                full_text=raw_txt,
                clean_path=resolved_f.name,
                per_file_cap=MAX_FILE_CHARS,
                inline_start_line=in_s,
                inline_end_line=in_e,
                center_line=in_c,
            )
            inspected_item = {
                "requested": inspect_name.strip(),
                "path": str(resolved_f),
                **slice_meta,
            }
        else:
            inspected_item = {"requested": inspect_name.strip(), "error": f"Could not resolve skill, agent, or rule '{inspect_name}'."}

    active_profile = quota_status.get("active_profile", "ultra-20x")

    ls_discovery: dict[str, Any] = {}
    try:
        req = urllib.request.Request(
            AGY_HOST_BRIDGE_URL,
            data=json.dumps({"action": "discover"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            ls_discovery = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as e:
        ls_discovery = {"ok": False, "error": str(e)}

    ls_reachable = bool(ls_discovery.get("ok") and ls_discovery.get("ls_address"))
    ls_compact: dict[str, Any] = {
        "ok": bool(ls_discovery.get("ok")),
        "ls_reachable": ls_reachable,
        "ls_address": ls_discovery.get("ls_address", ""),
        "projects_count": len(ls_discovery.get("projects") or []),
    }
    if ls_discovery.get("error"):
        ls_compact["error"] = ls_discovery["error"]

    out_payload: dict[str, Any] = {
        "ok": True,
        "status": "OK",
        "assistant_guidance": (
            "Inventory loaded. If you need to read specific skills, agents, or rules, call ask_workspace_readonly "
            "with comma-separated skill:<name> / agent:<name> paths immediately in this turn without asking the user first."
        ),
        "active_profile": active_profile,
        "quota_and_pools": quota_status,
        "customization_scope_policy": CUSTOMIZATION_SCOPE_POLICY,
        "session_customization_scope": session_scope,
        "agents_count": len(agents_list),
        "agents": agents_list,
        "skills_count": len(skills_list),
        "skills": skills_list,
        "plugin_skill_bundles": plugin_bundles,
        "rules_inventory": rules_inv,
        "configured_mcp_servers": _get_configured_mcp_servers(),
        "project_hygiene_standards": MODULAR_HYGIENE_STANDARDS,
        "context_window_config": {
            "ttl_seconds": TTL_SECONDS,
            "max_file_chars": MAX_FILE_CHARS,
            "max_total_file_chars": MAX_TOTAL_FILE_CHARS,
            "max_files_per_call": MAX_FILES_PER_CALL,
            "max_diff_chars": MAX_DIFF_CHARS,
            "max_transcript_turns": MAX_TRANSCRIPT_TURNS,
        },
        "language_server": ls_compact,
    }
    if inspected_item:
        out_payload["inspected_item"] = inspected_item
    return _compact_json(out_payload)


# -----------------------------------------------------------------------------
# 6. Stateless Cloud Compatibility, /web Overwatch Dashboard & Wire Telemetry
# -----------------------------------------------------------------------------

class BridgeCompatMiddleware:
    """ASGI wrapper serving /web Overwatch dashboard, HTTP method discovery, and sanitized JSON-RPC telemetry."""

    def __init__(self, app: Any) -> None:
        self.app = app
        self.web_dir = Path(__file__).resolve().parent / "web"
        self.web_html_path = self.web_dir / "index.html"
        self.pwa_assets = {
            "manifest.webmanifest": b"application/manifest+json; charset=utf-8",
            "sw.js": b"application/javascript; charset=utf-8",
            "icon.svg": b"image/svg+xml",
            "icon-192.png": b"image/png",
            "icon-512.png": b"image/png",
        }

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        t0 = time.time()
        method = str(scope.get("method", "")).upper()
        req_path = str(scope.get("path", "") or "").rstrip("/")
        raw_qs = (scope.get("query_string") or b"").decode("latin-1", errors="ignore")
        headers = list(scope.get("headers", []))

        # 0. Redirect bare root GET / -> /web
        if method == "GET" and req_path == "":
            await send({
                "type": "http.response.start",
                "status": 302,
                "headers": [(b"location", b"/web"), (b"content-length", b"0")],
            })
            await send({"type": "http.response.body", "body": b""})
            return

        # 1. Serve /web dashboard HTML (accessible at /web or /{PATH_SECRET}/web)
        if method == "GET" and (req_path.endswith("/web") or req_path.endswith("/web/index.html")):
            html_bytes = self.web_html_path.read_bytes() if self.web_html_path.is_file() else b"<h1>Dashboard not found</h1>"
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"text/html; charset=utf-8"),
                    (b"content-length", str(len(html_bytes)).encode("ascii")),
                    (b"cache-control", b"no-cache"),
                ],
            })
            await send({"type": "http.response.body", "body": html_bytes})
            print(f"[agy-nexus] http=GET rpc=web_ui tool=- status=200 bytes={len(html_bytes)} ms=1", flush=True)
            return

        # 1b. Serve Chromium PWA static assets (/web/manifest.webmanifest, /web/sw.js, /web/icon-*.png, /web/icon.svg)
        if method == "GET" and "/web/" in req_path:
            asset_name = req_path.rsplit("/web/", 1)[-1]
            if asset_name in self.pwa_assets:
                asset_path = self.web_dir / asset_name
                if asset_path.is_file():
                    asset_bytes = asset_path.read_bytes()
                    resp_hdrs = [
                        (b"content-type", self.pwa_assets[asset_name]),
                        (b"content-length", str(len(asset_bytes)).encode("ascii")),
                        (b"cache-control", b"no-cache"),
                    ]
                    if asset_name == "sw.js":
                        resp_hdrs.append((b"service-worker-allowed", b"/"))
                    await send({"type": "http.response.start", "status": 200, "headers": resp_hdrs})
                    await send({"type": "http.response.body", "body": asset_bytes})
                    return

        # 2. Serve /web/api/stats JSON (authenticated by X-Nexus-Passphrase header)
        if method in ("GET", "POST") and req_path.endswith("/web/api/stats"):
            supplied_pass = ""
            for hk, hv in headers:
                if hk.lower() == b"x-nexus-passphrase":
                    supplied_pass = hv.decode("utf-8", errors="ignore").strip()
                    break
            period_val = "current_month"
            for kv in raw_qs.split("&"):
                if kv.startswith("period="):
                    period_val = kv.split("=", 1)[1].strip() or "current_month"
            if not verify_passphrase(supplied_pass):
                err_b = json.dumps({"ok": False, "error": "Invalid spoken deadbolt passphrase."}).encode("utf-8")
                await send({
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(err_b)).encode("ascii"))],
                })
                await send({"type": "http.response.body", "body": err_b})
                print("[agy-nexus] http=GET rpc=web_stats_unauthorized tool=- status=401 bytes=0 ms=1", flush=True)
                return
            bundle = build_nexus_stats_bundle(
                data_dir=AGY_DATA_DIR,
                brain_dir=AGY_BRAIN_DIR,
                db_file=AGY_DB_FILE,
                config_dir=AGY_CONFIG_DIR,
                bg_dir=AGY_BG_DIR,
                period=period_val,
            )
            ok_b = json.dumps({"ok": True, **bundle}).encode("utf-8")
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(ok_b)).encode("ascii")),
                    (b"cache-control", b"no-cache"),
                ],
            })
            await send({"type": "http.response.body", "body": ok_b})
            elapsed_ms = int((time.time() - t0) * 1000)
            print(f"[agy-nexus] http=GET rpc=web_stats tool={period_val} status=200 bytes={len(ok_b)} ms={elapsed_ms}", flush=True)
            return

        if method == "HEAD":
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json"), (b"content-length", b"0")],
            })
            await send({"type": "http.response.body", "body": b""})
            print("[agy-nexus] http=HEAD rpc=health tool=- status=200 bytes=0 ms=0", flush=True)
            return

        if method == "OPTIONS":
            await send({
                "type": "http.response.start",
                "status": 204,
                "headers": [
                    (b"allow", b"GET, POST, HEAD, DELETE, OPTIONS"),
                    (b"content-length", b"0"),
                ],
            })
            await send({"type": "http.response.body", "body": b""})
            print("[agy-nexus] http=OPTIONS rpc=preflight tool=- status=204 bytes=0 ms=0", flush=True)
            return

        if method in ("GET", "DELETE"):
            body = json.dumps({"ok": True, "service": "agy-nexus-mcp", "version": "2.2.0", "transport": "streamable-http", "stateless": True, "web_dashboard": "/web"}).encode("utf-8")
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"x-accel-buffering", b"no"),
                    (b"cache-control", b"no-cache, no-transform"),
                ],
            })
            await send({"type": "http.response.body", "body": body})
            print(f"[agy-nexus] http={method} rpc=probe tool=- status=200 bytes={len(body)} ms=0", flush=True)
            return

        # Normalize Accept header on POST so cloud MCP clients sending only application/json never get 406
        new_headers: list[tuple[bytes, bytes]] = []
        found_accept = False
        user_agent_str = ""
        header_product_str = ""
        for k, v in headers:
            kl = k.lower()
            if kl == b"accept":
                found_accept = True
                val_str = v.decode("latin-1", errors="ignore")
                if "application/json" not in val_str or "text/event-stream" not in val_str:
                    v = b"application/json, text/event-stream"
            elif kl == b"user-agent":
                user_agent_str = v.decode("utf-8", errors="ignore").strip()
            elif kl == b"x-client-product":
                header_product_str = v.decode("utf-8", errors="ignore").strip()
            new_headers.append((k, v))
        if not found_accept:
            new_headers.append((b"accept", b"application/json, text/event-stream"))
        scope["headers"] = new_headers

        rpc_summary: dict[str, Any] = {
            "method": method,
            "rpc": "",
            "tool": "",
            "status": 0,
            "bytes": 0,
            "req_bytes": 0,
            "product": header_product_str,
            "user_agent": user_agent_str,
            "reported_tokens": 0,
        }
        body_chunks: list[bytes] = []

        async def wrapped_receive() -> dict[str, Any]:
            msg = await receive()
            if msg.get("type") == "http.request":
                chunk = msg.get("body") or b""
                if chunk:
                    body_chunks.append(chunk)
                if not msg.get("more_body", False) and body_chunks:
                    try:
                        full_body = b"".join(body_chunks)
                        rpc_summary["req_bytes"] = len(full_body)
                        data = json.loads(full_body.decode("utf-8", errors="ignore"))
                        if isinstance(data, dict):
                            rpc_summary["rpc"] = str(data.get("method") or "")
                            params = data.get("params")
                            if isinstance(params, dict):
                                if params.get("name"):
                                    rpc_summary["tool"] = str(params.get("name"))
                                c_info = params.get("clientInfo")
                                if isinstance(c_info, dict) and c_info.get("name") and not rpc_summary["product"]:
                                    rpc_summary["product"] = str(c_info.get("name"))
                                t_args = params.get("arguments")
                                if isinstance(t_args, dict):
                                    if t_args.get("client_product"):
                                        rpc_summary["product"] = str(t_args.get("client_product"))
                                    if t_args.get("client_tokens_reported"):
                                        rpc_summary["reported_tokens"] = int(t_args.get("client_tokens_reported") or 0)
                    except Exception:
                        pass
            return msg

        async def wrapped_send(msg: dict[str, Any]) -> None:
            if msg.get("type") == "http.response.start":
                rpc_summary["status"] = int(msg.get("status", 0))
                resp_headers = list(msg.get("headers") or [])
                existing_keys = {k.lower() for k, _ in resp_headers}
                if b"x-accel-buffering" not in existing_keys:
                    resp_headers.append((b"x-accel-buffering", b"no"))
                if b"cache-control" not in existing_keys:
                    resp_headers.append((b"cache-control", b"no-cache, no-transform"))
                msg = {**msg, "headers": resp_headers}
            elif msg.get("type") == "http.response.body":
                rpc_summary["bytes"] = int(rpc_summary["bytes"]) + len(msg.get("body") or b"")
            await send(msg)

        try:
            await self.app(scope, wrapped_receive, wrapped_send)
        finally:
            elapsed_ms = int((time.time() - t0) * 1000)
            tel_event = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "http": rpc_summary["method"],
                "rpc": rpc_summary["rpc"] or "-",
                "tool": rpc_summary["tool"] or "-",
                "status": rpc_summary["status"],
                "bytes": rpc_summary["bytes"],
                "req_bytes": rpc_summary["req_bytes"],
                "product": rpc_summary["product"],
                "user_agent": rpc_summary["user_agent"],
                "reported_tokens": rpc_summary["reported_tokens"],
                "ms": elapsed_ms,
            }
            record_wire_telemetry(tel_event, AGY_BG_DIR)
            print(
                f"[agy-nexus] http={tel_event['http']} rpc={tel_event['rpc']} "
                f"tool={tel_event['tool']} status={tel_event['status']} bytes={tel_event['bytes']} ms={elapsed_ms}",
                flush=True,
            )


# -----------------------------------------------------------------------------
# 7. Self-Test & Server Startup
# -----------------------------------------------------------------------------

def run_self_test() -> int:
    """Run automated verification of deadbolt, normalization, session listing, stats engine, and FastMCP app routes."""
    print("[*] Running agy-nexus-mcp v2.2 automated self-test...")

    # 1. Normalization & Passphrase Verification
    test_phrase = "Example Bridge 2026!"
    expected_hash = hashlib.sha256(b"examplebridge2026").hexdigest()
    calc_hash = normalize_phrase(test_phrase)
    assert calc_hash == expected_hash, f"Normalization mismatch: {calc_hash} != {expected_hash}"
    assert verify_passphrase(test_phrase, expected_hash) is True, "verify_passphrase failed on valid phrase"
    assert verify_passphrase("Wrong phrase", expected_hash) is False, "verify_passphrase accepted invalid phrase"
    print("  [+] Deadbolt normalization and verification: PASS")

    # 2. TTL & Inline Unlock State
    SESSION_STATE["unlocked_at"] = 0.0
    orig_hash = PASS_HASH
    globals()["PASS_HASH"] = expected_hash
    assert is_unlocked() is False, "is_unlocked returned True when locked"
    assert is_unlocked(test_phrase) is True, "Inline passphrase unlock failed"
    assert is_unlocked() is True, "is_unlocked returned False when state valid"
    SESSION_STATE["unlocked_at"] = time.time() - (TTL_SECONDS + 10)
    assert is_unlocked() is False, "is_unlocked returned True when TTL expired"
    globals()["PASS_HASH"] = orig_hash
    print("  [+] Deadbolt TTL and inline passphrase unlock transitions: PASS")

    # 3. Session Listing & Multi-Repo Search
    sessions = _list_saved_sessions_internal(limit=3, status_filter="ALL")
    assert isinstance(sessions, list), "Expected session listing to return a list"
    search_res = _search_workspaces_and_history("antigravity")
    assert "available_repositories" in search_res, "Expected available_repositories in search bundle"
    print(f"  [+] Conversation SQLite indexing ({len(sessions)} sessions, {len(search_res['available_repositories'])} repos): PASS")

    # 4. Stats Bundle & Mobile ASCII Renderer
    stats_bundle = build_nexus_stats_bundle(
        data_dir=AGY_DATA_DIR,
        brain_dir=AGY_BRAIN_DIR,
        db_file=AGY_DB_FILE,
        config_dir=AGY_CONFIG_DIR,
        bg_dir=AGY_BG_DIR,
        period="current_month",
    )
    assert "ascii_mobile_report" in stats_bundle and "quota_and_pools" in stats_bundle
    print(f"  [+] Telemetry & Activity Heatmap engine ({stats_bundle['summary']['period_steps']} steps indexed): PASS")

    # 5. FastMCP Stateless JSON Route Generation & /web HTML Check
    test_secret = "test_path_secret_at_least_32_characters_long_12345"
    raw_app = mcp.http_app(
        path=f"/{test_secret}/mcp",
        transport="http",
        stateless_http=True,
        json_response=True,
        host_origin_protection=False,
    )
    app = BridgeCompatMiddleware(raw_app)
    assert app is not None and app.web_html_path.is_file(), "Failed generating Starlette HTTP app or missing web/index.html"
    print("  [+] FastMCP stateless JSON HTTP route & /web Overwatch dashboard mounting: PASS")

    # 6. Multi-Repo Drift Audit & Notebook Export Deduplication
    import tempfile
    drift_res = inspect_multi_repo_drift(AGY_GITLAB_DIR, AGY_DATA_DIR, workspace_override="ALL")
    assert drift_res.get("ok") is True and "repositories" in drift_res
    with tempfile.TemporaryDirectory() as tmp_bg:
        pmap = _load_projects_map()
        nb_res1 = export_notebook_bundle(AGY_BRAIN_DIR, AGY_DB_FILE, Path(tmp_bg), pmap, limit=3)
        nb_res2 = export_notebook_bundle(AGY_BRAIN_DIR, AGY_DB_FILE, Path(tmp_bg), pmap, limit=3)
        assert nb_res2["unchanged"] == nb_res1["total_exported"], "Expected 100% SHA-256 deduplication on second Notebook export pass"
    print(f"  [+] Multi-repo drift audit ({drift_res['scanned_repositories_count']} repos) & Notebook SHA-256 deduplication ({nb_res1['total_exported']} bundles): PASS")

    print("[✓] All agy-nexus-mcp v2.2 self-tests completed successfully!")
    return 0


def main() -> None:
    if "--self-test" in sys.argv:
        sys.exit(run_self_test())

    if len(PATH_SECRET) < 32:
        sys.exit("FATAL: PATH_SECRET must be at least 32 hex characters. Ensure secrets.env exists with mode 600.")
    if len(PASS_HASH) != 64:
        sys.exit("FATAL: PASS_HASH must be a 64-character SHA-256 hex string. Run init_secrets.py to configure.")

    print(f"[*] Starting agy-nexus-mcp v2.2 on {BIND_HOST}:{BIND_PORT} (stateless_http=True, json_response=True)", flush=True)
    print(f"[*] MCP Route: /{PATH_SECRET[:6]}...{PATH_SECRET[-4:]}/mcp | Web Overwatch: /{PATH_SECRET[:6]}...{PATH_SECRET[-4:]}/web", flush=True)
    raw_app = mcp.http_app(
        path=f"/{PATH_SECRET}/mcp",
        transport="http",
        stateless_http=True,
        json_response=True,
        host_origin_protection=False,
    )
    app = BridgeCompatMiddleware(raw_app)
    uvicorn.run(app, host=BIND_HOST, port=BIND_PORT, log_level="info", access_log=False)


if __name__ == "__main__":
    main()
