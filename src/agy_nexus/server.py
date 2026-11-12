#!/usr/bin/env python3
"""
agy_nexus.server — FastMCP Server Bootstrap, Tool Registration & Automated Self-Test Suite.
"""

from __future__ import annotations

import functools
import hashlib
import inspect
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any

import anyio
import uvicorn

from agy_nexus import __version__
import agy_nexus.config as cfg
from agy_nexus.config import (
    AGY_BG_DIR, AGY_BRAIN_DIR, AGY_CONFIG_DIR, AGY_DATA_DIR, AGY_DB_FILE, AGY_GITLAB_DIR,
    BIND_HOST, BIND_PORT, PASS_HASH, PATH_SECRET, SESSION_STATE, TTL_SECONDS,
    get_polyglot_mcp_token, is_unlocked, mcp, normalize_phrase, verify_passphrase,
)
import agy_nexus.handoff  # noqa: F401
from agy_nexus.media import discover_visual_artifacts, sign_media_url, verify_and_resolve_media
from agy_nexus.middleware import BridgeCompatMiddleware
from agy_nexus.search import _search_workspaces_and_history
from agy_nexus.session_tree import build_project_session_tree
from agy_nexus.sessions import _list_saved_sessions_internal, _load_projects_map
from agy_nexus.stats import build_nexus_stats_bundle
from agy_nexus.tools_media import run_multimodal_media_self_test
import agy_nexus.tools_ops  # noqa: F401
from agy_nexus.tools_polyglot import polyglot_mcp
import agy_nexus.tools_session  # noqa: F401
import agy_nexus.tools_workspace  # noqa: F401
from agy_nexus.workflows import export_notebook_bundle, inspect_multi_repo_drift
from agy_nexus.workspace import _resolve_and_read_files


def _offload_sync_mcp_tools(mcp_server: Any) -> int:
    """Wrap synchronous FastMCP tool callables in anyio.to_thread.run_sync so tools/call never blocks Uvicorn's event loop."""
    wrapped_count = 0
    tool_dicts: list[dict[str, Any]] = []
    tm = getattr(mcp_server, "_tool_manager", None)
    if tm is not None and isinstance(getattr(tm, "_tools", None), dict):
        tool_dicts.append(tm._tools)
    lp = getattr(mcp_server, "_local_provider", None)
    if lp is not None and isinstance(getattr(lp, "_components", None), dict):
        tool_dicts.append(lp._components)
    for tdict in tool_dicts:
        for tool_obj in tdict.values():
            orig_fn = getattr(tool_obj, "fn", None)
            if callable(orig_fn) and not inspect.iscoroutinefunction(orig_fn) and not getattr(orig_fn, "_agy_async_offloaded", False):
                @functools.wraps(orig_fn)
                async def _async_fn(*args: Any, __fn: Any = orig_fn, **kwargs: Any) -> Any:
                    return await anyio.to_thread.run_sync(functools.partial(__fn, *args, **kwargs))

                _async_fn.__signature__ = inspect.signature(orig_fn)  # type: ignore[attr-defined]
                _async_fn._agy_async_offloaded = True  # type: ignore[attr-defined]
                tool_obj.fn = _async_fn
                if hasattr(tool_obj, "is_async"):
                    tool_obj.is_async = True
                if hasattr(tool_obj, "_is_async"):
                    tool_obj._is_async = True
                wrapped_count += 1
    return wrapped_count


def build_nexus_http_app(path_secret: str, polyglot_token: str = "") -> BridgeCompatMiddleware:
    """Construct the dual-MCP stateless Streamable HTTP ASGI application."""
    _offload_sync_mcp_tools(mcp)
    _offload_sync_mcp_tools(polyglot_mcp)
    eff_poly_tok = (polyglot_token or get_polyglot_mcp_token(path_secret)).strip()
    raw_app = mcp.http_app(
        path=f"/{path_secret}/mcp",
        transport="http",
        stateless_http=True,
        json_response=True,
        host_origin_protection=False,
    )
    poly_app = polyglot_mcp.http_app(
        path=f"/polyglot/{eff_poly_tok}/mcp",
        transport="http",
        stateless_http=True,
        json_response=True,
        host_origin_protection=False,
    )
    return BridgeCompatMiddleware(raw_app, polyglot_app=poly_app, polyglot_token=eff_poly_tok)


def run_self_test() -> int:
    """Run automated verification of deadbolt, normalization, session listing, stats engine, Polyglot index, and FastMCP app routes."""
    print(f"[*] Running agy-nexus-mcp v{__version__} automated self-test...")

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
    from agy_nexus.telemetry_scanner import classify_model_key
    assert "ascii_mobile_report" in stats_bundle and "model_series" in stats_bundle and "project_hierarchy" in stats_bundle
    assert classify_model_key("MODEL_PLACEHOLDER_M427") == "carbon", "Expected M427 to classify as carbon"
    print(f"  [+] Telemetry & Activity Heatmap engine ({stats_bundle['summary']['period_steps']} steps indexed): PASS")

    # 5. FastMCP Stateless JSON Route Generation, 405 Spec Compliance, Dual Polyglot Mount, /web HTML & JS Syntax Check
    test_secret = "test_path_secret_at_least_32_characters_long_12345"
    test_poly_tok = get_polyglot_mcp_token(test_secret)
    app = build_nexus_http_app(test_secret, test_poly_tok)
    assert app is not None and app.web_html_path.is_file(), "Failed generating Starlette HTTP app or missing web/index.html"
    from starlette.testclient import TestClient
    with TestClient(app) as tc:
        assert tc.get(f"/{test_secret}/mcp").status_code == 405, "Expected 405 on GET /{secret}/mcp"
        assert tc.delete(f"/{test_secret}/mcp").status_code == 405, "Expected 405 on DELETE /{secret}/mcp"
        assert tc.get("/health").status_code == 200, "Expected 200 on GET /health"
        assert tc.post(f"/polyglot/{test_poly_tok}/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers={"X-Forwarded-For": "203.0.113.9"}).status_code == 403
        r_poly = tc.post(f"/polyglot/{test_poly_tok}/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert r_poly.status_code == 200 and len(r_poly.json()["result"]["tools"]) == 3, f"agy-polyglot-mcp tools/list failed: {r_poly.text}"
        r_nex = tc.post(f"/{test_secret}/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        nex_tools = [t["name"] for t in r_nex.json()["result"]["tools"]]
        assert r_nex.status_code == 200 and len(nex_tools) == 11, f"agy-nexus-mcp expected 11 tools, got {len(nex_tools)}: {nex_tools}"
        assert "polyglot_map" not in nex_tools and len(r_nex.content) < 20_000, f"tools/list budget or isolation violated ({len(r_nex.content)} bytes)"
    node_bin = shutil.which("node")
    for js_name in ("palettes.js", "charts.js", "demo_data.js", "hierarchy.js", "uploads.js", "health.js", "app.js", "sw.js"):
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
    print("  [+] FastMCP stateless HTTP 405 spec compliance, agy-polyglot-mcp mount, /web & JS syntax check: PASS")

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

    # 10. Polyglot Syntax & Modular Budget Verifier, Incremental SHA-256 Index, outline: Reader & load_session_into_gemini
    from agy_nexus.code_health import get_modular_hygiene_summary
    from agy_nexus.polyglot_index import polyglot_repo_map, polyglot_symbol_search
    from agy_nexus.tools_session import load_session_into_gemini
    from agy_nexus.tools_workspace import ask_workspace_readonly
    pkg_root = Path(__file__).resolve().parents[2]
    hyg_map = get_modular_hygiene_summary(Path(__file__).resolve().parent)
    assert not hyg_map["syntax_errors"] and hyg_map["violations_over_650"] == 0, f"Modular hygiene failed: {hyg_map}"
    pmap_res = polyglot_repo_map(workspace=str(pkg_root), path_prefix="src/agy_nexus", limit=40)
    assert pmap_res.get("ok") is True and pmap_res.get("matched_files", 0) >= 25, f"polyglot_repo_map failed: {pmap_res}"
    psearch_res = polyglot_symbol_search("load_session_into_gemini", workspace=str(pkg_root))
    assert psearch_res.get("ok") is True and psearch_res.get("total_matches", 0) >= 1, f"polyglot_symbol_search failed: {psearch_res}"
    cfg.PASS_HASH = expected_hash
    try:
        if sessions:
            loaded_raw = load_session_into_gemini("1", spoken_passphrase=test_phrase)
            loaded_obj = json.loads(loaded_raw)
            assert loaded_obj.get("ok") is True and "execution_status" in loaded_obj and "visual_artifacts" in loaded_obj and "compaction_count" in loaded_obj, f"load_session_into_gemini failed: {loaded_obj}"
            assert "context_budget" in loaded_obj["execution_status"], f"Missing context_budget: {loaded_obj['execution_status']}"
            from agy_nexus.session_status import extract_prior_session_baton
            top_cid = str(sessions[0].get("conversation_id") or "")
            baton_res = extract_prior_session_baton(top_cid, AGY_BRAIN_DIR, ws_path=str(pkg_root))
            assert "## Prior Session Baton" in baton_res, f"Baton extraction failed for {top_cid}: {baton_res}"
        poly_targets = [
            ("src/agy_nexus/handoff.py", "python", str(pkg_root)),
            ("README.md", "markdown", str(pkg_root)),
            ("docker-compose.yml", "yaml", str(pkg_root)),
            ("web/app.js", "javascript", str(pkg_root)),
        ]
        if (AGY_GITLAB_DIR / "antigravity-config" / "mcp_config.template.json").is_file():
            poly_targets.append(("mcp_config.template.json", "json", str(AGY_GITLAB_DIR / "antigravity-config")))
        for subpath, expected_lang, target_ws in poly_targets:
            outline_raw = ask_workspace_readonly(
                question=f"Outline {subpath}",
                file_subpath=f"outline:{subpath}",
                workspace=target_ws,
                spoken_passphrase=test_phrase,
            )
            outline_obj = json.loads(outline_raw)
            fd = outline_obj.get("file_details") or {}
            files_out = fd.get("files") or ([fd] if "path" in fd or "mode" in fd else [])
            assert files_out and files_out[0].get("mode") in ("polyglot_outline", "ast_outline"), f"outline: mode failed for {subpath}: {outline_obj}"
            ast_ol = files_out[0].get("polyglot_outline") or files_out[0].get("ast_outline", {})
            assert ast_ol.get("symbol_count", 0) > 0, f"Expected symbols in {subpath}: {ast_ol}"
            assert ast_ol.get("language") == expected_lang, f"Language mismatch for {subpath}: expected {expected_lang}, got {ast_ol.get('language')}"
    finally:
        cfg.PASS_HASH = orig_hash
    print("  [+] Polyglot Syntax & Modular Budget Verifier (0 errors), Incremental SHA-256 Index & outline: Reader: PASS", flush=True)

    # 11. Context Exceeded Immunity, Timestamped Upload Batches & Two-Step Headless Staging
    from agy_nexus.session_status import check_context_exceeded
    from agy_nexus.uploads import validate_conv_id, sanitize_filename, save_scratch_upload_batch, list_scratch_upload_batches
    from agy_nexus.handoff import send_handoff_and_resume

    assert check_context_exceeded("c4ee22ce-6f46-4c3f-8869-79718c464196") is False, "False positive on active session"
    assert check_context_exceeded("52b90635-5178-4462-a5cf-0f117626c5a6") is True, "Expected True on historic error session"
    assert validate_conv_id("../../etc") is False and validate_conv_id("c4ee22ce-6f46-4c3f-8869-79718c464196") is True
    assert sanitize_filename("../bad/name.txt") == "name.txt"

    uploads_js_src = (app.web_dir / "uploads.js").read_text(encoding="utf-8")
    assert "/web/api/sessions/" in uploads_js_src and "nexus_passphrase" in uploads_js_src, "uploads.js missing /web/ route or nexus_passphrase key"

    dummy_cid = "00000000-0000-0000-0000-000000000000"
    dummy_dir = AGY_BRAIN_DIR / dummy_cid
    dummy_dir.mkdir(parents=True, exist_ok=True)
    cfg.PASS_HASH = expected_hash
    try:
        files = [("test_a.txt", b"hello world", "text/plain"), ("test_b.json", b'{"k": 1}', "application/json")]
        res_upload = save_scratch_upload_batch(dummy_cid, files, label="selftest", brain_dir=AGY_BRAIN_DIR)
        assert res_upload.get("ok") is True and res_upload.get("file_count") == 2
        batch_folder = Path(res_upload["batch_folder"])
        assert (batch_folder / "INDEX.md").is_file() and (batch_folder / "01_test_a.txt").is_file()

        import asyncio
        mp_bound = "----NexusSelfTestBoundary99"
        mp_body = (
            f"--{mp_bound}\r\nContent-Disposition: form-data; name=\"label\"\r\n\r\nasgi_e2e\r\n"
            f"--{mp_bound}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"shot_01.png\"\r\nContent-Type: image/png\r\n\r\nPNGDATA\r\n"
            f"--{mp_bound}--\r\n"
        ).encode("utf-8")
        asgi_out: list[dict] = []
        sent_body = False
        async def _recv() -> dict:
            nonlocal sent_body
            if not sent_body:
                sent_body = True
                return {"type": "http.request", "body": mp_body, "more_body": False}
            return {"type": "http.request", "body": b"", "more_body": False}
        async def _send(msg: dict) -> None:
            asgi_out.append(msg)
        asyncio.run(app({
            "type": "http", "method": "POST", "path": f"/web/api/sessions/{dummy_cid}/upload", "query_string": b"",
            "headers": [(b"content-type", f"multipart/form-data; boundary={mp_bound}".encode()), (b"x-nexus-passphrase", test_phrase.encode())],
        }, _recv, _send))
        assert asgi_out and asgi_out[0].get("status") == 200, f"ASGI /web/api/sessions upload failed: {asgi_out}"
        batches = list_scratch_upload_batches(dummy_cid, brain_dir=AGY_BRAIN_DIR)
        assert len(batches) == 2, f"Expected 2 distinct collision-free batches, got {len(batches)}"

        staged_raw = send_handoff_and_resume(
            research_markdown="# Self Test Staging\nStaged markdown body.",
            session_identifier=dummy_cid,
            spoken_passphrase=test_phrase,
            resume_headless=False,
        )
        staged_obj = json.loads(staged_raw)
        assert staged_obj.get("ok") is True and staged_obj.get("status") == "STAGED_ONLY" and staged_obj.get("resumed") is False
        assert "Do you understand the risk" in staged_obj.get("assistant_guidance", "")
        staged_file = dummy_dir / "scratch" / "gemini_research_handoff.md"
        assert staged_file.is_file() and "Staged markdown body." in staged_file.read_text(encoding="utf-8")

        repo_root = Path(__file__).resolve().parents[2]
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        from http.server import ThreadingHTTPServer
        import threading
        import urllib.error
        import urllib.request
        import host_bridge.agy_host_bridge as hb_mod
        from host_bridge.bridge_security import (
            DEFAULT_BIND_HOST,
            derive_bridge_token,
            guard_cli_positional,
            is_client_ip_allowed,
            resolve_allowed_git_roots,
            sanitize_conv_id,
            sanitize_git_ref,
        )

        assert DEFAULT_BIND_HOST == "127.0.0.1", f"Expected 127.0.0.1 default bind, got {DEFAULT_BIND_HOST}"
        assert is_client_ip_allowed("127.0.0.1") and is_client_ip_allowed("172.18.0.5")
        assert not is_client_ip_allowed("192.168.1.99") and not is_client_ip_allowed("192.168.31.143")
        assert Path.home().resolve() not in resolve_allowed_git_roots(AGY_GITLAB_DIR, AGY_DATA_DIR)
        assert sanitize_git_ref("--output=/tmp/pwn") == "output/tmp/pwn"
        assert sanitize_conv_id("--csrf_token") == "csrf_token" and guard_cli_positional("--help").startswith("\n")

        orig_bridge_url, orig_path_sec, orig_hb_tok = cfg.AGY_HOST_BRIDGE_URL, cfg.PATH_SECRET, cfg.HOST_BRIDGE_TOKEN
        cfg.PATH_SECRET, cfg.HOST_BRIDGE_TOKEN = test_secret, ""
        expected_bridge_tok = derive_bridge_token(path_secret=test_secret, explicit_token="")
        hb_mod.BRIDGE_TOKEN_OVERRIDE = expected_bridge_tok
        hb_mod.HostBridgeHandler.quiet_logs = True
        hb_srv = ThreadingHTTPServer(("127.0.0.1", 0), hb_mod.HostBridgeHandler)
        hb_thread = threading.Thread(target=hb_srv.serve_forever, daemon=True)
        hb_thread.start()
        hb_url = f"http://127.0.0.1:{hb_srv.server_port}/agentapi"
        cfg.AGY_HOST_BRIDGE_URL = hb_url
        try:
            def _hb_call(body_obj: dict, hdrs: dict[str, str]) -> tuple[int, dict]:
                req_hb = urllib.request.Request(hb_url, data=json.dumps(body_obj).encode("utf-8"), headers=hdrs, method="POST")
                try:
                    with urllib.request.urlopen(req_hb, timeout=5) as r_hb:
                        return r_hb.status, json.loads(r_hb.read().decode("utf-8"))
                except urllib.error.HTTPError as e_hb:
                    return e_hb.code, json.loads(e_hb.read().decode("utf-8"))

            assert _hb_call({"action": "discover"}, {"Content-Type": "application/json"})[0] == 401, "Expected 401 without X-Bridge-Token"
            assert _hb_call({"action": "discover"}, {"Content-Type": "application/json", "X-Bridge-Token": "wrong_token_" + "0" * 40})[0] == 401
            assert _hb_call({"action": "discover"}, {"Content-Type": "application/json", "X-Bridge-Token": expected_bridge_tok, "Origin": "https://evil.example"})[0] == 403
            st_home, body_home = _hb_call({"action": "git-inspect", "workspace_path": str(Path.home())}, cfg.get_host_bridge_headers())
            assert st_home == 200 and body_home.get("ok") is False and "outside allowed roots" in str(body_home.get("error", ""))
            st_nc, body_nc = _hb_call({"action": "new-conversation", "prompt": "hi", "workspace_path": str(Path.home())}, cfg.get_host_bridge_headers())
            assert st_nc == 200 and body_nc.get("ok") is False and "outside allowed roots" in str(body_nc.get("error", ""))
            st_git, body_git = _hb_call({"action": "git-inspect", "workspace_path": str(AGY_GITLAB_DIR / "antigravity-config"), "summary_only": True}, cfg.get_host_bridge_headers())
            assert st_git == 200 and body_git.get("ok") is True, f"Authenticated git-inspect failed: {body_git}"

            captured_payloads: list[dict] = []
            def _mock_handler(p: dict) -> dict:
                captured_payloads.append(p)
                return {"ok": True, "returncode": 0, "conversation_id": p.get("conversation_id", dummy_cid)}

            hb_mod.MOCK_ACTION_HANDLER = _mock_handler
            res_override_raw = send_handoff_and_resume(
                research_markdown="RESUME_STAGED",
                session_identifier=dummy_cid,
                spoken_passphrase=test_phrase,
                resume_headless=True,
                allow_chained_publish=True,
                force_interrupt=True,
            )
            res_override = json.loads(res_override_raw)
            assert "Staged markdown body." in staged_file.read_text(encoding="utf-8")
            assert res_override.get("ok") is True and res_override.get("write_mode") == "read_staged"
            assert res_override.get("execution_mode") == "fast", f"Expected auto->fast on chained headless publish, got {res_override.get('execution_mode')}"
            assert captured_payloads and "<!-- Handshake Gemini Research Handoff -->" not in captured_payloads[0].get("prompt", ""), "RESUME_STAGED double-wrapped header!"
        finally:
            hb_mod.MOCK_ACTION_HANDLER = None
            hb_mod.BRIDGE_TOKEN_OVERRIDE = ""
            hb_srv.shutdown()
            hb_srv.server_close()
            cfg.AGY_HOST_BRIDGE_URL, cfg.PATH_SECRET, cfg.HOST_BRIDGE_TOKEN = orig_bridge_url, orig_path_sec, orig_hb_tok
    finally:
        cfg.PASS_HASH = orig_hash
        shutil.rmtree(dummy_dir, ignore_errors=True)
        for job_p in AGY_BG_DIR.glob(f"*{dummy_cid}*"):
            job_p.unlink(missing_ok=True)
    print("  [+] Context Exceeded Immunity, Timestamped Upload Batches & Two-Step Headless Override Gate: PASS")
    print("  [+] Host Bridge CWE-306 & CWE-88 Zero-Trust Auth, Loopback Default, CIDR & Root Sandbox: PASS")
    run_multimodal_media_self_test(test_phrase, expected_hash)
    print("  [+] Public Media Origin Resolution & <20 KB Multimodal WebP ImageContent MCP Endpoint: PASS")

    print(f"[✓] All agy-nexus-mcp v{__version__} self-tests completed successfully!")
    return 0


def main() -> None:
    if "--self-test" in sys.argv:
        sys.exit(run_self_test())

    if len(PATH_SECRET) < 32:
        sys.exit("FATAL: PATH_SECRET must be at least 32 hex characters. Ensure secrets.env exists with mode 600.")
    if len(PASS_HASH) != 64:
        sys.exit("FATAL: PASS_HASH must be a 64-character SHA-256 hex string. Run init_secrets.py to configure.")

    poly_tok = get_polyglot_mcp_token(PATH_SECRET)
    print(f"[*] Starting agy-nexus-mcp v{__version__} on {BIND_HOST}:{BIND_PORT} (stateless_http=True, json_response=True)", flush=True)
    print(
        f"[*] Nexus MCP: /{PATH_SECRET[:6]}...{PATH_SECRET[-4:]}/mcp | "
        f"Polyglot MCP (LAN-only): /polyglot/{poly_tok[:6]}...{poly_tok[-4:]}/mcp | "
        f"Web Overwatch: /{PATH_SECRET[:6]}...{PATH_SECRET[-4:]}/web",
        flush=True,
    )
    app = build_nexus_http_app(PATH_SECRET, poly_tok)
    uvicorn.run(
        app,
        host=BIND_HOST,
        port=BIND_PORT,
        log_level="info",
        access_log=False,
        timeout_keep_alive=65,
    )


if __name__ == "__main__":
    main()
