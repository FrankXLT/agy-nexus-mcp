#!/usr/bin/env python3
"""
agy_nexus.config — Environment, Paths, Deadbolt Authentication & FastMCP Instance.
"""

from __future__ import annotations

import fcntl
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
    """Load KEY=VALUE pairs into os.environ (populating empty placeholders) and derive public origin."""
    env_candidates = [
        Path(os.getenv("AG_BRIDGE_ENV_FILE", "/config/secrets.env")),
        Path.home() / ".config/ag-bridge-mcp/secrets.env",
    ]
    for candidate in env_candidates:
        try:
            if candidate.is_file():
                for raw_line in candidate.read_text(encoding="utf-8").splitlines():
                    line = raw_line.strip()
                    if line.startswith("# Gemini Connected Apps URL:"):
                        m_url = re.search(r"(https?://[A-Za-z0-9.-]+(?::\d+)?)", line)
                        if m_url and not m_url.group(1).endswith(".example.com") and not m_url.group(1).endswith("//example.com"):
                            if not os.environ.get("_DERIVED_SECRETS_PUBLIC_URL"):
                                os.environ["_DERIVED_SECRETS_PUBLIC_URL"] = m_url.group(1)
                        continue
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    kc, vc = k.strip(), v.strip().strip("'\"")
                    if vc and not os.environ.get(kc):
                        os.environ[kc] = vc
                    elif kc not in os.environ:
                        os.environ[kc] = vc
                break
        except Exception:
            continue

_load_env_file()

AGY_DATA_DIR = Path(os.getenv("AGY_DATA_DIR", str(Path.home() / ".gemini/antigravity"))).expanduser()
AGY_BRAIN_DIR = Path(os.getenv("AGY_BRAIN_DIR", str(AGY_DATA_DIR / "brain"))).expanduser()
AGY_DB_FILE = Path(os.getenv("AGY_DB_FILE", str(AGY_DATA_DIR / "conversation_summaries.db"))).expanduser()
AGY_PRESENCE_DIR = Path(os.getenv("AGY_PRESENCE_DIR", str(AGY_DATA_DIR / "presence"))).expanduser()
AGY_CONFIG_DIR = Path(os.getenv("AGY_CONFIG_DIR", str(Path.home() / ".gemini/config"))).expanduser()

# Canonical 3-pillar workspace topology (projects, workbooks, configuration)
AGY_WORKSPACE_DIR = Path(os.getenv("AGY_WORKSPACE_DIR", str(Path.home() / "agentic_workspace"))).expanduser()
AGY_PROJECTS_DIR = Path(os.getenv("AGY_PROJECTS_DIR", str(AGY_WORKSPACE_DIR / "projects"))).expanduser()
AGY_WORKBOOKS_DIR = Path(os.getenv("AGY_WORKBOOKS_DIR", str(AGY_WORKSPACE_DIR / "workbooks"))).expanduser()
AGY_CONFIGURATION_DIR = Path(os.getenv("AGY_CONFIGURATION_DIR", str(AGY_WORKSPACE_DIR / "configuration"))).expanduser()

# Backward-compatible AGY_GITLAB_DIR: explicit env -> AGY_PROJECTS_DIR (if exists) -> ~/gitlab fallback
if os.getenv("AGY_GITLAB_DIR"):
    AGY_GITLAB_DIR = Path(os.getenv("AGY_GITLAB_DIR", "")).expanduser()
elif AGY_PROJECTS_DIR.is_dir():
    AGY_GITLAB_DIR = AGY_PROJECTS_DIR
else:
    AGY_GITLAB_DIR = (Path.home() / "gitlab").expanduser()

def get_workspace_pillar_roots() -> list[Path]:
    """Return existing resolved workspace pillar directories (projects, workbooks, configuration) plus legacy dirs if present."""
    roots: list[Path] = []
    seen: set[Path] = set()
    for candidate in [AGY_PROJECTS_DIR, AGY_WORKBOOKS_DIR, AGY_CONFIGURATION_DIR, AGY_GITLAB_DIR, AGY_GITLAB_DIR.parent / "github"]:
        try:
            if candidate.is_dir():
                res = candidate.resolve()
                if res not in seen:
                    seen.add(res)
                    roots.append(res)
        except OSError:
            pass
    return roots

def get_umbrella_roots() -> set[Path]:
    """Return resolved paths for parent umbrella directories that contain repos, NOT single-repo workspaces."""
    return {
        AGY_WORKSPACE_DIR.resolve(),
        AGY_PROJECTS_DIR.resolve(),
        AGY_WORKBOOKS_DIR.resolve(),
        AGY_CONFIGURATION_DIR.resolve(),
        AGY_GITLAB_DIR.resolve(),
        (AGY_GITLAB_DIR.parent / "github").resolve(),
        (AGY_DATA_DIR / "worktrees").resolve(),
    }

def get_antigravity_config_repo() -> Path:
    """Return path to antigravity-config repository under AGY_CONFIGURATION_DIR if present, else AGY_GITLAB_DIR."""
    cand = AGY_CONFIGURATION_DIR / "antigravity-config"
    if cand.is_dir() or cand.exists():
        return cand
    return AGY_GITLAB_DIR / "antigravity-config"

AGY_BG_DIR = Path(os.getenv("AGY_BG_DIR", str(AGY_DATA_DIR / "sidecar_data/ag-bridge-bg"))).expanduser()
AGY_HOST_BRIDGE_URL = os.getenv("AGY_HOST_BRIDGE_URL", "http://127.0.0.1:8098/agentapi")
BIND_HOST = os.getenv("BIND_HOST", "0.0.0.0")
BIND_PORT = int(os.getenv("BIND_PORT", "8765"))
PATH_SECRET = os.getenv("PATH_SECRET", "").strip()
PASS_HASH = os.getenv("PASS_HASH", "").strip().lower()
HOST_BRIDGE_TOKEN = os.getenv("HOST_BRIDGE_TOKEN", "").strip()
STATE_FILE = Path(os.getenv("AG_BRIDGE_STATE_FILE", str(AGY_BG_DIR / "session_state.json"))).expanduser()
ALLOW_LOCKED_STATS = os.getenv("AG_BRIDGE_ALLOW_LOCKED_STATS", "false").strip().lower() in ("1", "true", "yes")
ALLOW_LOCKED_STAGING = os.getenv("AG_BRIDGE_ALLOW_LOCKED_STAGING", "false").strip().lower() in ("1", "true", "yes")

SESSION_STATE: dict[str, Any] = {
    "unlocked_at": 0.0,
    "selected_session": "",
    "selected_workspace": "",
    "selected_workspace_uris": [],
    "selected_project": "",
    "active_contexts": {},             # conv_id -> slot dict for parallel chat isolation
    "pinned_calls": 0,
    "auto_resolved_calls": 0,
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
    SESSION_STATE["active_contexts"] = {}

def _save_session_state() -> None:
    """Atomically persist core session state and parallel active_contexts with flock + os.replace."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        lock_path = STATE_FILE.with_suffix(".lock")
        tmp_path = STATE_FILE.with_suffix(f".tmp.{os.getpid()}")
        persisted = {
            "unlocked_at": SESSION_STATE.get("unlocked_at", 0.0),
            "selected_session": SESSION_STATE.get("selected_session", ""),
            "selected_workspace": SESSION_STATE.get("selected_workspace", ""),
            "selected_workspace_uris": SESSION_STATE.get("selected_workspace_uris", []),
            "selected_project": SESSION_STATE.get("selected_project", ""),
            "active_contexts": SESSION_STATE.get("active_contexts", {}),
            "pinned_calls": int(SESSION_STATE.get("pinned_calls") or 0),
            "auto_resolved_calls": int(SESSION_STATE.get("auto_resolved_calls") or 0),
        }
        with open(lock_path, "a+", encoding="utf-8") as lf:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
            try:
                tmp_path.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")
                os.replace(tmp_path, STATE_FILE)
            finally:
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass

def _load_session_state() -> None:
    """Load persisted session state from disk with shared flock if present."""
    try:
        if STATE_FILE.is_file():
            lock_path = STATE_FILE.with_suffix(".lock")
            with open(lock_path, "a+", encoding="utf-8") as lf:
                fcntl.flock(lf.fileno(), fcntl.LOCK_SH)
                try:
                    data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                finally:
                    fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
            if isinstance(data, dict):
                unlocked_at = float(data.get("unlocked_at") or 0.0)
                SESSION_STATE["unlocked_at"] = unlocked_at
                SESSION_STATE["pinned_calls"] = int(data.get("pinned_calls") or 0)
                SESSION_STATE["auto_resolved_calls"] = int(data.get("auto_resolved_calls") or 0)
                if (time.time() - unlocked_at) < TTL_SECONDS:
                    for key in ("selected_session", "selected_workspace", "selected_workspace_uris", "selected_project", "active_contexts"):
                        if key in data and data[key] is not None:
                            SESSION_STATE[key] = data[key]
                else:
                    _clear_selected_session_state()
    except Exception:
        pass

_load_session_state()

def pin_session_context(
    conv_id: str,
    title: str = "",
    project_id: str = "",
    project_name: str = "",
    workspace: str = "",
    workspace_uris: list[str] | None = None,
    mode: str = "PINNED",
    last_tool: str = "",
    set_default: bool = True,
) -> dict[str, Any]:
    """Record or update an isolated context slot in active_contexts for parallel Gemini chats."""
    if not conv_id:
        return {}
    contexts = SESSION_STATE.setdefault("active_contexts", {})
    existing = contexts.get(conv_id, {}) if isinstance(contexts, dict) else {}
    eff_title = title or existing.get("title") or SESSION_STATE["session_title_map"].get(conv_id, "")
    eff_proj_id = project_id or existing.get("project_id") or SESSION_STATE["session_project_map"].get(conv_id, "")
    eff_ws = workspace or existing.get("workspace") or SESSION_STATE["session_workspace_map"].get(conv_id, "")
    eff_uris = workspace_uris if workspace_uris is not None else (existing.get("workspace_uris") or SESSION_STATE["session_workspace_uris_map"].get(conv_id, []))
    slot = {
        "conversation_id": conv_id,
        "title": eff_title,
        "project_id": eff_proj_id,
        "project_name": project_name or existing.get("project_name") or eff_proj_id,
        "workspace": eff_ws,
        "workspace_uris": eff_uris,
        "mode": mode or existing.get("mode") or "PINNED",
        "last_tool": last_tool or existing.get("last_tool") or "session",
        "last_used_at": time.time(),
    }
    contexts[conv_id] = slot
    if len(contexts) > 25:
        oldest_k = min(contexts.keys(), key=lambda k: float(contexts[k].get("last_used_at") or 0.0))
        if oldest_k != conv_id:
            contexts.pop(oldest_k, None)
    if eff_ws:
        SESSION_STATE["session_workspace_map"][conv_id] = eff_ws
    if eff_proj_id:
        SESSION_STATE["session_project_map"][conv_id] = eff_proj_id
    if eff_title:
        SESSION_STATE["session_title_map"][conv_id] = eff_title
    if eff_uris:
        SESSION_STATE["session_workspace_uris_map"][conv_id] = list(eff_uris)
    if set_default:
        SESSION_STATE["selected_session"] = conv_id
        if eff_ws:
            SESSION_STATE["selected_workspace"] = eff_ws
        if eff_uris:
            SESSION_STATE["selected_workspace_uris"] = list(eff_uris)
        if eff_proj_id:
            SESSION_STATE["selected_project"] = eff_proj_id
    _save_session_state()
    return slot

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
                if hmac.compare_digest(normalize_phrase("".join(tokens[i:j])), target_hash):
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
        "CRITICAL GEMINI WEB / MOBILE PLATFORM RULES (MANDATORY):\n"
        "1. STRICT ONE-TOOL-CALL-PER-TURN RULE: Do NOT chain a second MCP tool after a successful response (all data is already included). "
        "However, if a tool call fails with permission_denied or an immediate error, you MAY automatically invoke ask_workspace_readonly or load_session_into_gemini once as a same-turn fallback without asking the user to reply 'Go'.\n"
        "2. ONE-SHOT BUNDLED SUPER-CALLS (GET ALL FILES & CONTEXT IN 1 CALL):\n"
        "- Do NOT call `list_saved_sessions` first when the user asks to inspect or load a session: call `load_session_into_gemini(session_identifier='1'|'latest'|<project_or_title_keyword>|<uuid>, include_files='path1,path2')` directly in 1 shot! It resolves `'1'`, `'latest'`, project names, or title keywords automatically and returns `task.md`, `implementation_plan.md`, `walkthrough.md`, `execution_status`, `git_summary`, `visual_artifacts`, and `included_files`.\n"
        "- When exploring code with `ask_workspace_readonly`, batch all needed files or virtual URIs in a single comma-separated `file_subpath='a.py,outline:b.py,transcript:latest,brain:scratch/notes.md'` (up to 12 items per call). Even if you only pass `question` / `search_query`, `ask_workspace_readonly` automatically searches the pinned session, Polyglot semantic index, and repository in that same single call!\n"
        "- For live telemetry/quota stats, PREFER calling `get_session_tree(include_stats=True, period='last_90d'|'current_month'|'last_month'|'last_year', style='default'|'quick'|'rich')` (or `ask_workspace_readonly(question='Latest stats', file_subpath='telemetry:stats:last_90d:default')`) to avoid Gemini policy blocks on background-run verbs, and render `ascii_mobile_report`.\n"
        "3. PROJECT ROUTING: When calling `send_handoff_and_resume`, pass `session_identifier` (for existing sessions) or `project_name` and `workspace_path` (when `create_new_session=True`)."
    ),
)

# -----------------------------------------------------------------------------
# 4. Internal Helper Routines
# -----------------------------------------------------------------------------

def get_host_bridge_token() -> str:
    """Return explicit HOST_BRIDGE_TOKEN or domain-separated HMAC-SHA256 derived from PATH_SECRET."""
    if len(HOST_BRIDGE_TOKEN) >= 32:
        return HOST_BRIDGE_TOKEN
    return hmac.new(PATH_SECRET.encode("utf-8"), b"agy-host-bridge-agentapi-v1", hashlib.sha256).hexdigest() if len(PATH_SECRET) >= 32 else ""

def get_polyglot_mcp_token(secret: str = "") -> str:
    """Return explicit POLYGLOT_MCP_TOKEN or domain-separated HMAC-SHA256 derived from PATH_SECRET for local LAN IDE routing."""
    explicit = os.getenv("POLYGLOT_MCP_TOKEN", "").strip()
    if (not secret or secret == PATH_SECRET) and len(explicit) >= 32:
        return explicit
    seed = (secret or PATH_SECRET).strip()
    return hmac.new(seed.encode("utf-8"), b"agy-polyglot-mcp-v1", hashlib.sha256).hexdigest()[:48] if len(seed) >= 32 else ""

def get_host_bridge_headers() -> dict[str, str]:
    """Build JSON + X-Bridge-Token headers for authenticated /agentapi requests."""
    tok = get_host_bridge_token()
    return {"Content-Type": "application/json", **({"X-Bridge-Token": tok} if tok else {})}

def _compact_json(data: Any) -> str:
    """Serialize tool output with compact separators so large inventories/bundles stay well under Gemini's cloud proxy byte ceiling."""
    return json.dumps(data, separators=(",", ": "), ensure_ascii=False)
