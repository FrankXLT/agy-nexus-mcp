#!/usr/bin/env python3
"""
agy_nexus.config — Environment, Paths, Deadbolt Authentication & FastMCP Instance.
"""

from __future__ import annotations

import contextvars
import copy
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import threading
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
    for candidate in [AGY_PROJECTS_DIR, AGY_WORKBOOKS_DIR, AGY_CONFIGURATION_DIR, AGY_GITLAB_DIR, AGY_GITLAB_DIR.parent / "github", Path.home() / "github"]:
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
        (Path.home() / "github").resolve(),
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

_STATE_LOCK = threading.RLock()


def _clear_selected_session_state() -> None:
    """Clear selected session/workspace pointers when deadbolt expires or resets."""
    with _STATE_LOCK:
        SESSION_STATE["selected_session"] = ""
        SESSION_STATE["selected_workspace"] = ""
        SESSION_STATE["selected_workspace_uris"] = []
        SESSION_STATE["selected_project"] = ""
        SESSION_STATE["active_contexts"] = {}


_SYNTH_SLOT_RE = re.compile(r"^(?:test-|conv-|demo-)|^([0-9a-fA-F])\1{7}-", re.IGNORECASE)


def prune_stale_context_slots(
    brain_dir: Path | None = None,
    db_file: Path | None = None,
    *,
    max_synthetic_age_s: float = 0.0,
) -> int:
    """Prune stale /tmp/ or synthetic test slots from SESSION_STATE['active_contexts']."""
    import sqlite3
    with _STATE_LOCK:
        contexts = SESSION_STATE.get("active_contexts")
        if not isinstance(contexts, dict) or not contexts:
            return 0
        items_snapshot = list(contexts.items())
    eff_brain, eff_db, now = brain_dir or AGY_BRAIN_DIR, db_file or AGY_DB_FILE, time.time()
    stale_ids: set[str] = set()
    db_candidates: list[str] = []
    for cid, slot in items_snapshot:
        slot_d = slot if isinstance(slot, dict) else {}
        ws_str = str(slot_d.get("workspace") or "").strip()
        if ws_str.startswith(("/tmp/", "/var/tmp/")) and not Path(ws_str).exists():
            stale_ids.add(cid)
            continue
        if _SYNTH_SLOT_RE.match(str(cid)):
            last_used = float(slot_d.get("last_used_at") or 0.0)
            if max_synthetic_age_s > 0.0 and last_used > 0.0 and (now - last_used) < max_synthetic_age_s:
                continue
            if not (eff_brain / str(cid)).is_dir():
                db_candidates.append(str(cid))
    if db_candidates:
        found_in_db: set[str] = set()
        if eff_db.is_file():
            try:
                con = sqlite3.connect(f"file:{eff_db}?mode=ro", uri=True)
                try:
                    marks = ",".join("?" for _ in db_candidates)
                    found_in_db = {str(r[0]) for r in con.execute(f"SELECT conversation_id FROM conversation_summaries WHERE conversation_id IN ({marks})", db_candidates).fetchall()}
                finally:
                    con.close()
            except Exception:
                pass
        stale_ids.update(cid for cid in db_candidates if cid not in found_in_db)
    if not stale_ids:
        return 0
    with _STATE_LOCK:
        contexts_live = SESSION_STATE.get("active_contexts")
        if not isinstance(contexts_live, dict):
            return 0
        for cid in stale_ids:
            contexts_live.pop(cid, None)
            for mkey in ("session_workspace_map", "session_workspace_uris_map", "session_project_map", "session_title_map"):
                if isinstance(SESSION_STATE.get(mkey), dict):
                    SESSION_STATE[mkey].pop(cid, None)
        if SESSION_STATE.get("selected_session") in stale_ids:
            SESSION_STATE["selected_session"] = ""
            SESSION_STATE["selected_workspace"] = ""
            SESSION_STATE["selected_workspace_uris"] = []
            SESSION_STATE["selected_project"] = ""
    return len(stale_ids)


def _save_session_state(*, prune: bool = True) -> None:
    """Atomically persist core session state and parallel active_contexts with flock + os.replace."""
    try:
        if prune:
            prune_stale_context_slots(max_synthetic_age_s=300.0)
        with _STATE_LOCK:
            persisted = {
                "unlocked_at": SESSION_STATE.get("unlocked_at", 0.0),
                "selected_session": SESSION_STATE.get("selected_session", ""),
                "selected_workspace": SESSION_STATE.get("selected_workspace", ""),
                "selected_workspace_uris": copy.deepcopy(SESSION_STATE.get("selected_workspace_uris", [])),
                "selected_project": SESSION_STATE.get("selected_project", ""),
                "active_contexts": copy.deepcopy(SESSION_STATE.get("active_contexts", {})),
                "pinned_calls": int(SESSION_STATE.get("pinned_calls") or 0),
                "auto_resolved_calls": int(SESSION_STATE.get("auto_resolved_calls") or 0),
            }
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        lock_path = STATE_FILE.with_suffix(".lock")
        tmp_path = STATE_FILE.with_suffix(f".tmp.{os.getpid()}.{threading.get_ident()}")
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
                with _STATE_LOCK:
                    unlocked_at = float(data.get("unlocked_at") or 0.0)
                    SESSION_STATE["unlocked_at"] = unlocked_at
                    SESSION_STATE["pinned_calls"] = int(data.get("pinned_calls") or 0)
                    SESSION_STATE["auto_resolved_calls"] = int(data.get("auto_resolved_calls") or 0)
                    if (time.time() - unlocked_at) < TTL_SECONDS:
                        for key in ("selected_session", "selected_workspace", "selected_workspace_uris", "selected_project", "active_contexts"):
                            if key in data and data[key] is not None:
                                SESSION_STATE[key] = data[key]
                        need_save = prune_stale_context_slots() > 0
                    else:
                        _clear_selected_session_state()
                        need_save = False
                if need_save:
                    _save_session_state(prune=False)
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
    with _STATE_LOCK:
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
        slot_copy = dict(slot)
    _save_session_state()
    return slot_copy

def normalize_phrase(phrase: str) -> str:
    """Normalize spoken passphrase (lowercase, strip whitespace and punctuation) and compute SHA-256."""
    cleaned = re.sub(r"[^a-z0-9]", "", (phrase or "").lower())
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


def verify_passphrase(spoken_passphrase: str, expected_hash: str = "") -> bool:
    """Constant-time verification of normalized passphrase (and spoken prefix wrappers) against expected SHA-256 hash."""
    target_hash = (expected_hash or PASS_HASH).strip().lower()
    if not target_hash or not spoken_passphrase or not _HEX64_RE.fullmatch(target_hash):
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
    if not PASS_HASH or not _HEX64_RE.fullmatch(PASS_HASH.strip().lower()):
        return False
    now = time.time()
    phrase_valid = bool(spoken_passphrase and verify_passphrase(spoken_passphrase))
    with _STATE_LOCK:
        was_expired = (now - float(SESSION_STATE.get("unlocked_at") or 0.0)) >= TTL_SECONDS
        if was_expired and SESSION_STATE.get("selected_session"):
            _clear_selected_session_state()
        if phrase_valid or not was_expired:
            SESSION_STATE["unlocked_at"] = now
            unlocked_ok = True
        else:
            unlocked_ok = False
    if unlocked_ok:
        _save_session_state()
        return True
    return False

REPLY_PROMPT_GUIDANCE = (
    "END-OF-TURN 1-TAP REPLY CHIPS: When presenting your final answer to the user, ALWAYS end your message with "
    "<FollowUp label=\"...\" query=\"@Agy Nexus Mcp ...\" /> (1 clear next step) or "
    "<ElicitationsGroup message=\"...\"><Elicitation label=\"...\" query=\"@Agy Nexus Mcp ...\" /></ElicitationsGroup> "
    "(2-3 choices). Every query MUST start with '@Agy Nexus Mcp ' and include exact session/handoff/project IDs "
    "(prefer suggested_actions.followup_xml when provided)."
)

LOCKED_RESPONSE = json.dumps({
    "ok": False,
    "locked": True,
    "assistant_guidance": (
        "STOP IMMEDIATELY AND REPLY TO THE USER NOW: Do NOT call any more MCP tools in this turn "
        "(Google Gemini's UI confirmation card hangs on back-to-back tool calls). "
        "Ask the user for their spoken passphrase first, then call the tool via @Agy Nexus Mcp in the NEXT turn "
        "(and always prefix any <FollowUp> / <ElicitationsGroup> chip query with '@Agy Nexus Mcp ')."
    ),
    "message": (
        "Security Deadbolt Active. Voice/spoken passphrase verification required "
        "(configure a 64-hex PASS_HASH or AG_BRIDGE_ENV_FILE when running in --stdio mode). "
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
        "AGY-NEXUS-MCP: Antigravity Mission Control, Cross-Session Memory, Quota Overwatch & Handoff Server.\n"
        "1. PLAIN-LANGUAGE STAGE HANDOFFS (`send_handoff_and_resume`): Pass `workflow_ids` (e.g. 'WF-01,WF-03'), `workflow_delta` ('unchanged'|'update_existing'|'add_new'|'bootstrap'), and `user_terms`; explain what the user sees, taps, and expects (never code/line dumps). Ask 2-3 quick plain-language questions before `new_project` (`Who & Goal`, `Common Terms`, >=2 `WF-XX` flows across 390px/900px/1440px + empty/error states) or when a brownfield repo reports `MISSING_BASELINE` (`workflow_delta='bootstrap'`). Modes: "
        "'feature_update' (default), 'new_project', 'bug_or_visual_fix' (defaults `update_existing`), 'release_closeout' (only zero-edit exempt mode). "
        "Keep `execution_mode='auto'` so compact non-security fixes/closeouts use `fast` while features/security stay in `plan`.\n"
        "2. SEQUENTIAL READ-ONLY GOVERNANCE (1 CALL AT A TIME, UP TO 4 HOPS/TURN):\n"
        "- NEVER emit parallel simultaneous MCP calls in the same step (causes UI confirmation hangs).\n"
        "- You MAY issue up to 4 sequential read-only calls (`get_session_tree`, `load_session_into_gemini`, `ask_workspace_readonly`, `inspect_git_diff`, `inspect_visual_artifacts`, `list_saved_sessions`, `list_models_and_agents`) per turn (`call -> wait -> next`).\n"
        "- On permission_denied/immediate error, auto-fallback sequentially once to `ask_workspace_readonly` or `load_session_into_gemini`.\n"
        "- HARD STOP ON MUTATIONS & DEADBOLT: `send_handoff_and_resume` and `LOCKED_RESPONSE` end the turn—reply to the user immediately.\n"
        "3. 1-CALL SUPER-CALLS: Call `load_session_into_gemini(session_identifier='1'|'latest'|<keyword>, include_files=...)` directly for check-ins (skip `list_saved_sessions`). Batch up to 12 files/virtual URIs in `ask_workspace_readonly(file_subpath='a.py,outline:b.py,workflow:baseline,transcript:latest')`.\n"
        "4. ROUTING & CONTINUITY: Pass `session_identifier` (or `project_name` + `workspace_path` with `create_new_session=True`) and `session_continuity='auto'|'continuation'|'closeout'|'new_topic'`.\n"
        "5. END-OF-TURN 1-TAP REPLY CHIPS (`@Agy Nexus Mcp` REQUIRED): ALWAYS end EVERY final user-facing reply with "
        "<FollowUp label=\"...\" query=\"@Agy Nexus Mcp ...\" /> (1 clear next step) or "
        "<ElicitationsGroup message=\"...\"><Elicitation label=\"...\" query=\"@Agy Nexus Mcp ...\" /></ElicitationsGroup> (2-3 choices). "
        "Every `query` MUST start with `@Agy Nexus Mcp ` and embed the exact `conversation_id`, `handoff_id`, and `project_name` "
        "(prefer `suggested_actions.followup_xml` when returned).\n"
        "6. OPT-IN GEMINI VM VISUAL AUDIT: Share clickable `signed_url` screenshot & showcase HTML links at zero extra token cost. "
        "Gemini's Linux workspace CAN fetch them (`curl -A 'Mozilla/5.0 (compatible; Google-Agent; +https://developers.google.com/crawling/docs/crawlers-fetchers/google-agent)'` + `view_file`), "
        "but NEVER auto-fetch images unprompted—ALWAYS prompt first with `<Elicitation label=\"Have Gemini audit screenshots in VM (uses extra tokens)\" ... />`.\n"
        "7. EMBEDDED PLAIN-LABEL WEB LINKS: Whenever `gallery_url` or verified `verified_urls` are returned by `load_session_into_gemini` or `inspect_visual_artifacts`, ALWAYS present them as tappable embedded Markdown links using plain English labels (such as `[Open Session Gallery](<gallery_url>)`, `[Open in Antigravity Web](<workspace_url>)`, or `[Open Documentation](...)`). NEVER place raw domain names or URLs inside the `[...]` square brackets and NEVER dump URLs inside fenced code blocks."
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

def get_praxis_mcp_token(secret: str = "") -> str:
    """Return explicit PRAXIS_MCP_TOKEN (or POLYGLOT_MCP_TOKEN fallback) or domain-separated HMAC-SHA256 derived from PATH_SECRET for local LAN IDE routing."""
    explicit = (os.getenv("PRAXIS_MCP_TOKEN", "").strip() or os.getenv("POLYGLOT_MCP_TOKEN", "").strip())
    if (not secret or secret == PATH_SECRET) and len(explicit) >= 32:
        return explicit
    seed = (secret or PATH_SECRET).strip()
    return hmac.new(seed.encode("utf-8"), b"agy-praxis-mcp-v1", hashlib.sha256).hexdigest()[:48] if len(seed) >= 32 else ""

def get_polyglot_mcp_token(secret: str = "") -> str:
    """Return explicit POLYGLOT_MCP_TOKEN or legacy domain-separated HMAC-SHA256 derived from PATH_SECRET."""
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


_MCP_REQUEST_CTX: contextvars.ContextVar[dict[str, str] | None] = contextvars.ContextVar("_MCP_REQUEST_CTX", default=None)
