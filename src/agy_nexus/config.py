#!/usr/bin/env python3
"""
agy_nexus.config — Environment, Paths, Deadbolt Authentication & FastMCP Instance.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import time
from typing import Any

from fastmcp import FastMCP

from agy_nexus.hygiene import TTL_SECONDS

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

def _compact_json(data: Any) -> str:
    """Serialize tool output with compact separators so large inventories/bundles stay well under Gemini's cloud proxy byte ceiling."""
    return json.dumps(data, separators=(",", ": "), ensure_ascii=False)
