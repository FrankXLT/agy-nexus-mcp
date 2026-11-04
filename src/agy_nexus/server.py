#!/usr/bin/env python3
"""
agy_nexus.server — FastMCP Server Bootstrap, Tool Registration & Automated Self-Test Suite.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import tempfile
import time
import uvicorn

import agy_nexus.config as cfg
from agy_nexus.config import (
    AGY_BG_DIR,
    AGY_BRAIN_DIR,
    AGY_CONFIG_DIR,
    AGY_DATA_DIR,
    AGY_DB_FILE,
    AGY_GITLAB_DIR,
    BIND_HOST,
    BIND_PORT,
    PASS_HASH,
    PATH_SECRET,
    SESSION_STATE,
    TTL_SECONDS,
    is_unlocked,
    mcp,
    normalize_phrase,
    verify_passphrase,
)
import agy_nexus.handoff  # noqa: F401
from agy_nexus.media import (
    build_visual_artifact_content,
    generate_tiny_probe_png,
    sign_media_url,
    verify_and_resolve_media,
)
from agy_nexus.middleware import BridgeCompatMiddleware
from agy_nexus.search import _search_workspaces_and_history
from agy_nexus.sessions import _list_saved_sessions_internal, _load_projects_map
from agy_nexus.stats import build_nexus_stats_bundle
import agy_nexus.tools_ops  # noqa: F401
import agy_nexus.tools_session  # noqa: F401
import agy_nexus.tools_workspace  # noqa: F401
from agy_nexus.workflows import export_notebook_bundle, inspect_multi_repo_drift


def run_self_test() -> int:
    """Run automated verification of deadbolt, normalization, session listing, stats engine, and FastMCP app routes."""
    print("[*] Running agy-nexus-mcp v2.3 automated self-test...")

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
    orig_hash = cfg.PASS_HASH
    cfg.PASS_HASH = expected_hash
    assert is_unlocked() is False, "is_unlocked returned True when locked"
    assert is_unlocked(test_phrase) is True, "Inline passphrase unlock failed"
    assert is_unlocked() is True, "is_unlocked returned False when state valid"
    SESSION_STATE["unlocked_at"] = time.time() - (TTL_SECONDS + 10)
    assert is_unlocked() is False, "is_unlocked returned True when TTL expired"
    cfg.PASS_HASH = orig_hash
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
    drift_res = inspect_multi_repo_drift(AGY_GITLAB_DIR, AGY_DATA_DIR, workspace_override="ALL")
    assert drift_res.get("ok") is True and "repositories" in drift_res
    with tempfile.TemporaryDirectory() as tmp_bg:
        pmap = _load_projects_map()
        nb_res1 = export_notebook_bundle(AGY_BRAIN_DIR, AGY_DB_FILE, Path(tmp_bg), pmap, limit=3)
        nb_res2 = export_notebook_bundle(AGY_BRAIN_DIR, AGY_DB_FILE, Path(tmp_bg), pmap, limit=3)
        assert nb_res2["unchanged"] == nb_res1["total_exported"], "Expected 100% SHA-256 deduplication on second Notebook export pass"
    print(f"  [+] Multi-repo drift audit ({drift_res['scanned_repositories_count']} repos) & Notebook SHA-256 deduplication ({nb_res1['total_exported']} bundles): PASS")

    # 7. Ephemeral HMAC /web/media/ Signing, Path Sandboxing & MCP ImageContent Probe
    cfg.PASS_HASH = expected_hash
    probe_png = generate_tiny_probe_png(16, 16)
    assert probe_png.startswith(b"\x89PNG\r\n\x1a\n") and len(probe_png) < 200
    probe_blocks = build_visual_artifact_content("", "", "probe", {"ok": True})
    assert len(probe_blocks) == 2 and getattr(probe_blocks[1], "type", "") == "image"
    signed_expired = sign_media_url("repo:antigravity-config", "docs/assets/dashboard-desktop.png", exp_ts=int(time.time()) - 10)
    assert verify_and_resolve_media(signed_expired)[2] == 403, "Expected 403 on expired media link"
    signed_traversal = sign_media_url("repo:antigravity-config", "../../etc/passwd.png")
    assert verify_and_resolve_media(signed_traversal)[2] == 403, "Expected 403 on path traversal media link"
    cfg.PASS_HASH = orig_hash
    print(f"  [+] Visual Artifact HMAC /web/media/ signing, sandbox & MCP ImageContent probe ({len(probe_png)}B PNG): PASS")

    print("[✓] All agy-nexus-mcp v2.3 self-tests completed successfully!")
    return 0


def main() -> None:
    if "--self-test" in sys.argv:
        sys.exit(run_self_test())

    if len(PATH_SECRET) < 32:
        sys.exit("FATAL: PATH_SECRET must be at least 32 hex characters. Ensure secrets.env exists with mode 600.")
    if len(PASS_HASH) != 64:
        sys.exit("FATAL: PASS_HASH must be a 64-character SHA-256 hex string. Run init_secrets.py to configure.")

    print(f"[*] Starting agy-nexus-mcp v2.3 on {BIND_HOST}:{BIND_PORT} (stateless_http=True, json_response=True)", flush=True)
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
