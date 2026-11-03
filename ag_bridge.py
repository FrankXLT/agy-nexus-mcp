#!/usr/bin/env python3
"""
ag_bridge.py — Root entrypoint shim for agy-nexus-mcp (`src/agy_nexus`).

Preserves 100% backward compatibility with existing Docker Compose containers,
systemd service units, CLI scripts, and test suites while keeping all domain
modules cleanly organized inside `src/agy_nexus/` (<= 300 lines per file).
"""

from pathlib import Path
import sys

_SRC_DIR = Path(__file__).resolve().parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from agy_nexus.config import (  # noqa: E402, F401
    AGY_BG_DIR,
    AGY_BRAIN_DIR,
    AGY_CONFIG_DIR,
    AGY_DATA_DIR,
    AGY_DB_FILE,
    AGY_GITLAB_DIR,
    AGY_HOST_BRIDGE_URL,
    AGY_PRESENCE_DIR,
    BIND_HOST,
    BIND_PORT,
    LOCKED_RESPONSE,
    PASS_HASH,
    PATH_SECRET,
    SESSION_STATE,
    TTL_SECONDS,
    is_unlocked,
    mcp,
    normalize_phrase,
    verify_passphrase,
)
from agy_nexus.handoff import send_handoff_and_resume  # noqa: E402, F401
from agy_nexus.middleware import BridgeCompatMiddleware  # noqa: E402, F401
from agy_nexus.server import main, run_self_test  # noqa: E402, F401
from agy_nexus.tools_ops import list_models_and_agents, manage_background_run  # noqa: E402, F401
from agy_nexus.tools_session import (  # noqa: E402, F401
    list_saved_sessions,
    load_session_into_gemini,
    lock_bridge,
    unlock_sessions,
)
from agy_nexus.tools_workspace import ask_workspace_readonly, inspect_git_diff  # noqa: E402, F401

if __name__ == "__main__":
    main()
