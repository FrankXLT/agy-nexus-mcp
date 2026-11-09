#!/usr/bin/env python3
"""
agy_nexus.server — FastMCP Server Bootstrap, Tool Registration & Automated Self-Test Suite.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
import shutil
import subprocess
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
    discover_visual_artifacts,
    sign_media_url,
    verify_and_resolve_media,
)
from agy_nexus.middleware import BridgeCompatMiddleware
from agy_nexus.search import _search_workspaces_and_history
from agy_nexus.session_tree import build_project_session_tree
from agy_nexus.sessions import _list_saved_sessions_internal, _load_projects_map
from agy_nexus.stats import build_nexus_stats_bundle
import agy_nexus.tools_ops  # noqa: F401
import agy_nexus.tools_session  # noqa: F401
import agy_nexus.tools_workspace  # noqa: F401
from agy_nexus.workflows import export_notebook_bundle, inspect_multi_repo_drift
from agy_nexus.workspace import _resolve_and_read_files


def run_self_test() -> int:
    """Run automated verification of deadbolt, normalization, session listing, stats engine, and FastMCP app routes."""
    print("[*] Running agy-nexus-mcp v2.5.0 automated self-test...")

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
    assert "ascii_mobile_report" in stats_bundle and "project_session_tree" in stats_bundle
    print(f"  [+] Telemetry & Activity Heatmap engine ({stats_bundle['summary']['period_steps']} steps indexed): PASS")

    # 5. FastMCP Stateless JSON Route Generation, /web HTML & JS Syntax Check
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
    node_bin = shutil.which("node")
    for js_name in ("charts.js", "hierarchy.js", "app.js", "sw.js"):
        js_path = app.web_dir / js_name
        assert js_path.is_file(), f"Missing web/{js_name}"
        js_text = js_path.read_text(encoding="utf-8")
        for ln_no, ln in enumerate(js_text.splitlines(), 1):
            if "//" in ln and "http://" not in ln and "https://" not in ln:
                comment_part = ln.split("//", 1)[1]
                assert not re.search(r"\}\s*$", comment_part), f"Commented closing brace in web/{js_name}:{ln_no}"
        if node_bin:
            proc = subprocess.run([node_bin, "--check", str(js_path)], capture_output=True, text=True, timeout=10, check=False)
            assert proc.returncode == 0, f"JS syntax error in web/{js_name}: {proc.stderr}"
    print("  [+] FastMCP stateless JSON HTTP route, /web dashboard & JS syntax check: PASS")

    # 6. Multi-Repo Drift Audit & Notebook Export Deduplication
    drift_res = inspect_multi_repo_drift(AGY_GITLAB_DIR, AGY_DATA_DIR, workspace_override="ALL")
    assert drift_res.get("ok") is True and "repositories" in drift_res
    with tempfile.TemporaryDirectory() as tmp_bg:
        pmap = _load_projects_map()
        nb_res1 = export_notebook_bundle(AGY_BRAIN_DIR, AGY_DB_FILE, Path(tmp_bg), pmap, limit=3)
        nb_res2 = export_notebook_bundle(AGY_BRAIN_DIR, AGY_DB_FILE, Path(tmp_bg), pmap, limit=3)
        assert nb_res2["unchanged"] == nb_res1["total_exported"], "Expected 100% SHA-256 deduplication on second Notebook export pass"
    print(f"  [+] Multi-repo drift audit ({drift_res['scanned_repositories_count']} repos) & Notebook SHA-256 deduplication ({nb_res1['total_exported']} bundles): PASS")

    # 7. Ephemeral HMAC /web/media/ Signing, Path Sandboxing & Visual Artifact Discovery
    cfg.PASS_HASH = expected_hash
    artifacts = discover_visual_artifacts("", str(AGY_GITLAB_DIR / "antigravity-config"), limit=5)
    assert isinstance(artifacts, list) and len(artifacts) > 0, "Expected visual artifacts in antigravity-config"
    assert verify_and_resolve_media(artifacts[0]["signed_url"])[2] == 200, "Expected 200 on valid signed media URL"
    signed_expired = sign_media_url("repo:antigravity-config", "docs/assets/dashboard-desktop.png", exp_ts=int(time.time()) - 10)
    assert verify_and_resolve_media(signed_expired)[2] == 403, "Expected 403 on expired media link"
    signed_traversal = sign_media_url("repo:antigravity-config", "../../etc/passwd.png")
    assert verify_and_resolve_media(signed_traversal)[2] == 403, "Expected 403 on path traversal media link"
    cfg.PASS_HASH = orig_hash
    print(f"  [+] Visual Artifact HMAC /web/media/ signing, sandbox & discovery ({len(artifacts)} artifacts): PASS")

    # 8. Parallel Session Isolation, 3-Tier Smart Path Resolver & 76-Col ASCII Session Tree
    tier2_res = _resolve_and_read_files(
        "antigravity-config/sidecars/ag-bridge-mcp/src/agy_nexus/session_tree.py",
        max_chars_per_file=500,
        ws=AGY_GITLAB_DIR,
    )
    assert isinstance(tier2_res, dict) and tier2_res.get("error") is None and tier2_res.get("auto_resolved_workspace"), f"3-tier path resolver failed: {tier2_res}"
    tree_bundle = build_project_session_tree(active_only=False, limit=10)
    assert "PROJECT -> CHAT -> SESSION ID HIERARCHY" in tree_bundle.get("ascii_tree", ""), "Missing ASCII tree header"
    print(f"  [+] Parallel Session Isolation, 3-Tier Path Resolver & 76-col Session Tree ({tree_bundle['projects_count']} projects): PASS")

    # 9. Content-Aware Skill Auto-Router, In-Flight Mutex & Session Health Telemetry
    from agy_nexus.inventory import _resolve_skill_directives
    from agy_nexus.session_status import (
        check_inflight_handoff_mutex,
        count_session_compactions,
        generate_session_health_warning,
    )
    import json
    ui_skills = _resolve_skill_directives("antigravity-config", "", "Refactor web/hierarchy.js and table UI components")
    assert "visual-architecture-system" in ui_skills and "modern-web-guidance" in ui_skills and "agy-nexus-stats" in ui_skills
    stack_skills = _resolve_skill_directives("my-repo", "", "Deploy docker-compose stack via Portainer")
    assert "portainer-gitops" in stack_skills
    auth_skills = _resolve_skill_directives("my-repo", "", "Review security deadbolt before publish_to_github")
    assert "dual-review" in auth_skills
    warn = generate_session_health_warning(1600, 12)
    assert "SESSION HEALTH WARNING" in warn and "1,500" in warn
    now_test = time.time()
    test_conv = "test-collision-session-uuid"
    test_job_file = AGY_BG_DIR / f"job-test-{int(now_test)}.json"
    AGY_BG_DIR.mkdir(parents=True, exist_ok=True)
    test_job_file.write_text(json.dumps({"job_id": f"job-test-{int(now_test)}", "conversation_id": test_conv, "started_at": "2026-11-09T00:00:00Z"}), encoding="utf-8")
    try:
        mutex_res = check_inflight_handoff_mutex(test_conv, AGY_BG_DIR, {"is_running": True}, max_age_seconds=300)
        assert mutex_res is not None and mutex_res["status"] == "ALREADY_RUNNING"
    finally:
        test_job_file.unlink(missing_ok=True)
    print("  [+] Content-Aware Skill Auto-Router, In-Flight Mutex & Session Health Warning: PASS")

    # 10. AST Undefined-Name Verifier, 1-Call outline: Reader & End-to-End load_session_into_gemini
    from agy_nexus.ast_outline import scan_package_undefined_names
    from agy_nexus.tools_session import load_session_into_gemini
    from agy_nexus.tools_workspace import ask_workspace_readonly
    undef_map = scan_package_undefined_names(Path(__file__).resolve().parent)
    assert not undef_map, f"Undefined Python names detected in agy_nexus: {undef_map}"
    cfg.PASS_HASH = expected_hash
    try:
        if sessions:
            loaded_raw = load_session_into_gemini("1", spoken_passphrase=test_phrase)
            loaded_obj = json.loads(loaded_raw)
            assert loaded_obj.get("ok") is True and "execution_status" in loaded_obj and "visual_artifacts" in loaded_obj and "compaction_count" in loaded_obj, f"load_session_into_gemini failed: {loaded_obj}"
        outline_raw = ask_workspace_readonly(
            question="Outline handoff.py",
            file_subpath="outline:src/agy_nexus/handoff.py",
            workspace=str(AGY_GITLAB_DIR / "antigravity-config"),
            spoken_passphrase=test_phrase,
        )
        outline_obj = json.loads(outline_raw)
        fd = outline_obj.get("file_details") or {}
        files_out = fd.get("files") or ([fd] if "path" in fd or "mode" in fd else [])
        assert files_out and files_out[0].get("mode") == "ast_outline" and files_out[0].get("ast_outline", {}).get("symbol_count", 0) > 0, f"outline: mode failed: {outline_obj}"
    finally:
        cfg.PASS_HASH = orig_hash
    print("  [+] AST Undefined-Name Verifier (0 errors), 1-Call outline: Reader & load_session_into_gemini: PASS")

    print("[✓] All agy-nexus-mcp v2.5.0 self-tests completed successfully!")
    return 0


def main() -> None:
    if "--self-test" in sys.argv:
        sys.exit(run_self_test())

    if len(PATH_SECRET) < 32:
        sys.exit("FATAL: PATH_SECRET must be at least 32 hex characters. Ensure secrets.env exists with mode 600.")
    if len(PASS_HASH) != 64:
        sys.exit("FATAL: PASS_HASH must be a 64-character SHA-256 hex string. Run init_secrets.py to configure.")

    print(f"[*] Starting agy-nexus-mcp v2.5.0 on {BIND_HOST}:{BIND_PORT} (stateless_http=True, json_response=True)", flush=True)
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
