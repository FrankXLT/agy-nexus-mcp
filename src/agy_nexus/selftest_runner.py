#!/usr/bin/env python3
"""
agy_nexus.self_test — Automated Non-Destructive Self-Test Suite.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import http.server
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any
import urllib.error
import urllib.request

from starlette.testclient import TestClient

from agy_nexus import __version__
import agy_nexus.config as cfg
from agy_nexus.config import (
    AGY_BG_DIR, AGY_BRAIN_DIR, AGY_CONFIG_DIR, AGY_DATA_DIR, AGY_DB_FILE,
    AGY_GITLAB_DIR, AGY_PROJECTS_DIR, AGY_WORKSPACE_DIR, SESSION_STATE,
    TTL_SECONDS, get_antigravity_config_repo, get_polyglot_mcp_token,
    get_praxis_mcp_token, is_unlocked, normalize_phrase, verify_passphrase,
)
from agy_nexus.hygiene import resolve_source_repo_root
from agy_nexus.media import discover_visual_artifacts, sign_media_url, verify_and_resolve_media
from agy_nexus.search import _search_workspaces_and_history
from agy_nexus.session_tree import build_project_session_tree
from agy_nexus.sessions import _list_saved_sessions_internal, _load_projects_map
from agy_nexus.stats import build_nexus_stats_bundle
from agy_nexus.tools_media import run_multimodal_media_self_test
from agy_nexus.workflows import export_notebook_bundle, inspect_multi_repo_drift
from agy_nexus.workspace import _resolve_and_read_files


def _test_deadbolt_and_search(test_phrase: str, expected_hash: str) -> list[dict[str, Any]]:
    """Verify deadbolt phrase hashing, TTL expiry, and read-only SQLite + search."""
    calc_hash = normalize_phrase(test_phrase)
    assert calc_hash == expected_hash, f"Normalization mismatch: {calc_hash} != {expected_hash}"
    assert verify_passphrase(test_phrase, expected_hash) is True, "verify_passphrase failed"
    assert verify_passphrase("Wrong phrase", expected_hash) is False, "accepted invalid phrase"
    print("  [+] Deadbolt normalization and verification: PASS")

    SESSION_STATE["unlocked_at"] = 0.0
    orig_hash = cfg.PASS_HASH
    cfg.PASS_HASH = expected_hash
    try:
        assert is_unlocked() is False, "is_unlocked returned True when locked"
        assert is_unlocked(test_phrase) is True, "Inline passphrase unlock failed"
        assert is_unlocked() is True, "is_unlocked returned False when valid"
        SESSION_STATE["unlocked_at"] = time.time() - (TTL_SECONDS + 10)
        assert is_unlocked() is False, "is_unlocked returned True when expired"
    finally:
        cfg.PASS_HASH = orig_hash
    print("  [+] Deadbolt TTL and inline passphrase unlock transitions: PASS")

    sessions = _list_saved_sessions_internal(limit=3, status_filter="ALL")
    assert isinstance(sessions, list), "Expected session listing list"
    search_res = _search_workspaces_and_history("antigravity")
    assert "available_repositories" in search_res, "Expected available_repositories"
    print(f"  [+] Conversation SQLite indexing ({len(sessions)} sessions, {len(search_res['available_repositories'])} repos): PASS")
    return sessions


def _test_stats_and_http_routes(test_secret: str) -> Any:
    """Verify 8-model stats bundle, dual-MCP HTTP routes, and web JS syntax."""
    from agy_nexus.model_pricing import classify_model_key, get_canonical_model_keys
    from agy_nexus.server import build_nexus_http_app

    stats_bundle = build_nexus_stats_bundle(
        data_dir=AGY_DATA_DIR, brain_dir=AGY_BRAIN_DIR, db_file=AGY_DB_FILE,
        config_dir=AGY_CONFIG_DIR, bg_dir=AGY_BG_DIR, period="current_month",
    )
    assert "ascii_mobile_report" in stats_bundle and "model_series" in stats_bundle and "project_hierarchy" in stats_bundle
    expected_8 = {
        "MODEL_PLACEHOLDER_M427": "carbon",
        "MODEL_PLACEHOLDER_M417": "argon",
        "MODEL_PLACEHOLDER_M532": "neon",
        "MODEL_PLACEHOLDER_M525": "hydrogen",
        "MODEL_PLACEHOLDER_M318": "flash_3_8",
        "MODEL_PLACEHOLDER_M400": "claude_opus_5_5",
        "MODEL_PLACEHOLDER_M403": "claude_sonnet_5_5",
        "MODEL_OPENAI_GPT_OSS_120B_MEDIUM": "gpt_oss_120b",
    }
    assert len(get_canonical_model_keys()) == 8
    for raw_id, exp_mk in expected_8.items():
        assert classify_model_key(raw_id) == exp_mk, f"Expected {raw_id} -> {exp_mk}"
    print(f"  [+] Telemetry & 8-Model Cost Engine ({stats_bundle['summary']['period_steps']} steps indexed): PASS")

    praxis_tok, poly_tok = get_praxis_mcp_token(test_secret), get_polyglot_mcp_token(test_secret)
    app = build_nexus_http_app(test_secret, polyglot_token=poly_tok, praxis_token=praxis_tok)
    assert app is not None and app.web_html_path.is_file(), "Missing HTTP app or web/index.html"
    with TestClient(app) as tc:
        assert tc.get(f"/{test_secret}/mcp").status_code == 405 and tc.delete(f"/{test_secret}/mcp").status_code == 405
        assert tc.get("/health").status_code == 200
        assert tc.post(f"/praxis/{praxis_tok}/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers={"X-Forwarded-For": "203.0.113.9"}).status_code == 403
        assert tc.post(f"/polyglot/{poly_tok}/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers={"X-Forwarded-For": "203.0.113.9"}).status_code == 403
        r_praxis = tc.post(f"/praxis/{praxis_tok}/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        r_poly = tc.post(f"/polyglot/{poly_tok}/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        praxis_tools = [t["name"] for t in r_praxis.json()["result"]["tools"]]
        assert r_praxis.status_code == 200 and r_poly.status_code == 200 and len(praxis_tools) == 6
        assert "praxis_claim_handoff" in praxis_tools and "polyglot_map" in praxis_tools
        r_nex = tc.post(f"/{test_secret}/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        nex_tools = [t["name"] for t in r_nex.json()["result"]["tools"]]
        assert r_nex.status_code == 200 and len(nex_tools) == 11 and "polyglot_map" not in nex_tools and len(r_nex.content) < 20_000
    node_bin = shutil.which("node")
    js_checks = (
        "demo_snapshot.js", "gallery_select.js", "sheet_builder.js", "sw.js",
        "palettes.js", "charts.js", "demo_data.js", "hierarchy.js", "uploads.js", "heatmap.js",
        "workspace_resizer.js", "health.js", "markdown_renderer.js", "gallery_view.js", "explorer.js", "app.js",
        "v9/v9_state.js", "v9/v9_table_sort.js", "v9/v9_spark_bars.js",
        "v9/v9_demo_docs.js", "v9/v9_demo_adapter.js", "v9/v9_catalog_banner.js", "v9/v9_billing.js",
        "v9/v9_charts.js", "v9/v9_heatmap.js", "v9/v9_analytics.js", "v9/v9_project_view.js",
        "v9/v9_hierarchy.js", "v9/v9_markdown.js", "v9/v9_workspace.js", "v9/v9_gallery.js",
        "v9/v9_lightbox.js", "v9/v9_app.js",
    )
    for js_name in js_checks:
        js_path = app.web_dir / js_name
        assert js_path.is_file(), f"Missing web/{js_name}"
        for ln_no, ln in enumerate(js_path.read_text(encoding="utf-8").splitlines(), 1):
            if "//" in ln and "http://" not in ln and "https://" not in ln:
                assert not re.search(r"\}\s*$", ln.split("//", 1)[1]), f"Commented brace in web/{js_name}:{ln_no}"
        if node_bin:
            proc = subprocess.run([node_bin, "--check", str(js_path)], capture_output=True, text=True, timeout=10, check=False)
            assert proc.returncode == 0, f"JS syntax error in web/{js_name}: {proc.stderr}"
    print("  [+] FastMCP stateless HTTP 405 spec compliance, agy-praxis-mcp (+ /polyglot/) mount, /web & JS syntax check: PASS")
    return app


def _ensure_probe_git_repo(probe_dir: Path) -> Path:
    shutil.rmtree(probe_dir, ignore_errors=True)
    probe_dir.mkdir(parents=True, exist_ok=True)
    for cmd in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "selftest@example.com"],
        ["git", "config", "user.name", "SelfTest"],
    ):
        subprocess.run(cmd, cwd=str(probe_dir), check=True)
    (probe_dir / "README.md").write_text("# probe\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(probe_dir), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=str(probe_dir), check=True)
    return probe_dir


def _test_drift_media_and_isolation(test_phrase: str, expected_hash: str, orig_hash: str) -> None:
    """Verify multi-repo drift, HMAC media signing, 3-tier path resolver, and git diff."""
    drift_res = inspect_multi_repo_drift(AGY_GITLAB_DIR, AGY_DATA_DIR, workspace_override="ALL")
    assert drift_res.get("ok") is True and "repositories" in drift_res
    with tempfile.TemporaryDirectory() as tmp_bg:
        pmap = _load_projects_map()
        nb_res1 = export_notebook_bundle(AGY_BRAIN_DIR, AGY_DB_FILE, Path(tmp_bg), pmap, limit=3)
        nb_res2 = export_notebook_bundle(AGY_BRAIN_DIR, AGY_DB_FILE, Path(tmp_bg), pmap, limit=3)
        assert nb_res2["unchanged"] == nb_res1["total_exported"]
    print(f"  [+] Multi-repo drift audit ({drift_res['scanned_repositories_count']} repos) & Notebook SHA-256 deduplication ({nb_res1['total_exported']} bundles): PASS")

    test_repo_dir = resolve_source_repo_root(__file__) or AGY_CONFIG_DIR
    cfg.PASS_HASH = expected_hash
    try:
        artifacts = discover_visual_artifacts("", str(test_repo_dir), limit=5)
        assert isinstance(artifacts, list) and len(artifacts) > 0
        assert verify_and_resolve_media(artifacts[0]["signed_url"])[2] == 200
        assert verify_and_resolve_media(sign_media_url(f"repo:{test_repo_dir.name}", "docs/assets/dashboard-desktop.png", exp_ts=int(time.time()) - 10))[2] == 403
        assert verify_and_resolve_media(sign_media_url(f"repo:{test_repo_dir.name}", "../../etc/passwd.png"))[2] == 403
    finally:
        cfg.PASS_HASH = orig_hash
    print(f"  [+] Visual Artifact HMAC /web/media/ signing, sandbox & discovery ({len(artifacts)} artifacts): PASS")

    tier2_ws = next(
        (d for d in (AGY_PROJECTS_DIR, AGY_GITLAB_DIR, test_repo_dir.parent) if d.is_dir() and (d / test_repo_dir.name).is_dir()),
        test_repo_dir.parent,
    )
    tier2_res = _resolve_and_read_files(
        f"{test_repo_dir.name}/src/agy_nexus/session_tree.py", max_chars_per_file=500,
        ws=tier2_ws,
    )
    assert isinstance(tier2_res, dict) and tier2_res.get("error") is None and tier2_res.get("auto_resolved_workspace")
    tree_bundle = build_project_session_tree(active_only=False, limit=10)
    assert "PROJECT -> CHAT -> SESSION ID HIERARCHY" in tree_bundle.get("ascii_tree", "")
    from agy_nexus.tools_workspace import inspect_git_diff
    cfg.PASS_HASH = expected_hash
    tmp_probe_git = AGY_DATA_DIR / "worktrees" / "_selftest_git_probe"
    try:
        target_diff_ws = test_repo_dir if (test_repo_dir / ".git").exists() else _ensure_probe_git_repo(tmp_probe_git)
        single_diff_obj = json.loads(inspect_git_diff(workspace_override=str(target_diff_ws), spoken_passphrase=test_phrase))
        assert single_diff_obj.get("ok") is True and "branch" in single_diff_obj
    finally:
        cfg.PASS_HASH = orig_hash
        shutil.rmtree(tmp_probe_git, ignore_errors=True)
    print(f"  [+] Parallel Session Isolation, 3-Tier Path Resolver, Session Tree & Single-Repo Git Diff ({tree_bundle['projects_count']} projects): PASS")


def _test_skills_polyglot_and_outline(sessions: list[dict[str, Any]], test_phrase: str, expected_hash: str, orig_hash: str) -> None:
    """Verify skill routing, mutex/health warnings, modular hygiene, and outline reader."""
    from agy_nexus.code_health import get_modular_hygiene_summary
    from agy_nexus.inventory import _resolve_skill_directives
    from agy_nexus.polyglot_index import polyglot_repo_map, polyglot_symbol_search
    from agy_nexus.session_status import check_inflight_handoff_mutex, extract_prior_session_baton, generate_session_health_warning
    from agy_nexus.tools_session import load_session_into_gemini
    from agy_nexus.tools_workspace import ask_workspace_readonly

    ui_skills = _resolve_skill_directives("antigravity-config", "", "Refactor web/hierarchy.js and table UI components")
    assert "visual-architecture-system" in ui_skills and "modern-web-guidance" in ui_skills and "agy-nexus-stats" in ui_skills
    assert "portainer-gitops" in _resolve_skill_directives("my-repo", "", "Deploy docker-compose stack via Portainer")
    assert "dual-review" in _resolve_skill_directives("my-repo", "", "Review security deadbolt before publish_to_github")
    assert "SESSION HEALTH WARNING" in generate_session_health_warning(1600, 12)
    test_conv = "test-collision-session-uuid"
    test_job_file = AGY_BG_DIR / f"job-test-{int(time.time())}.json"
    AGY_BG_DIR.mkdir(parents=True, exist_ok=True)
    test_job_file.write_text(json.dumps({"job_id": test_job_file.stem, "conversation_id": test_conv, "started_at": "2026-11-09T00:00:00Z"}), encoding="utf-8")
    try:
        mutex_res = check_inflight_handoff_mutex(test_conv, AGY_BG_DIR, {"is_running": True}, max_age_seconds=300)
        assert mutex_res is not None and mutex_res["status"] == "ALREADY_RUNNING"
    finally:
        test_job_file.unlink(missing_ok=True)
    print("  [+] Content-Aware Skill Auto-Router, In-Flight Mutex & Session Health Warning: PASS")

    pkg_root = resolve_source_repo_root(__file__)
    hyg_map = get_modular_hygiene_summary(Path(__file__).resolve().parent)
    assert not hyg_map["syntax_errors"] and hyg_map["violations_over_650"] == 0, f"Modular hygiene failed: {hyg_map}"
    assert polyglot_repo_map(workspace=str(pkg_root), path_prefix="src/agy_nexus", limit=40).get("matched_files", 0) >= 25
    assert polyglot_symbol_search("load_session_into_gemini", workspace=str(pkg_root)).get("total_matches", 0) >= 1
    cfg.PASS_HASH = expected_hash
    try:
        if sessions:
            loaded_obj = json.loads(load_session_into_gemini("1", spoken_passphrase=test_phrase))
            assert loaded_obj.get("ok") is True and "context_budget" in loaded_obj.get("execution_status", {})
            top_cid = str(sessions[0].get("conversation_id") or "")
            assert "## Prior Session Baton" in extract_prior_session_baton(top_cid, AGY_BRAIN_DIR, ws_path=str(pkg_root))
        poly_targets = [
            ("src/agy_nexus/handoff.py", "python", str(pkg_root)),
            ("README.md", "markdown", str(pkg_root)),
            ("docker-compose.yml", "yaml", str(pkg_root)),
            ("web/app.js", "javascript", str(pkg_root)),
        ]
        ag_cfg = get_antigravity_config_repo()
        if (ag_cfg / "mcp_config.template.json").is_file():
            poly_targets.append(("mcp_config.template.json", "json", str(ag_cfg)))
        for subpath, expected_lang, target_ws in poly_targets:
            outline_obj = json.loads(ask_workspace_readonly(question=f"Outline {subpath}", file_subpath=f"outline:{subpath}", workspace=target_ws, spoken_passphrase=test_phrase))
            fd = outline_obj.get("file_details") or {}
            files_out = fd.get("files") or ([fd] if "path" in fd or "mode" in fd else [])
            ast_ol = files_out[0].get("polyglot_outline") or files_out[0].get("ast_outline", {})
            assert ast_ol.get("symbol_count", 0) > 0 and ast_ol.get("language") == expected_lang
    finally:
        cfg.PASS_HASH = orig_hash
    print("  [+] Polyglot Syntax & Modular Budget Verifier (0 errors), Incremental SHA-256 Index & outline: Reader: PASS", flush=True)


def _run_host_bridge_checks(dummy_dir: Path, dummy_cid: str, test_phrase: str, test_secret: str) -> None:
    """Exercise repo-prefixed handoff queue and Host Bridge zero-trust security gates."""
    from agy_nexus.handoff import send_handoff_and_resume
    repo_root = resolve_source_repo_root(__file__)
    if repo_root is not None and str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    import host_bridge.agy_host_bridge as hb_mod
    from host_bridge.bridge_security import (
        DEFAULT_BIND_HOST, derive_bridge_token, guard_cli_positional, is_client_ip_allowed,
        resolve_allowed_git_roots, sanitize_conv_id, sanitize_git_ref,
    )

    staged_obj = json.loads(send_handoff_and_resume(
        research_markdown="# Self Test Staging\nStaged markdown body.",
        session_identifier=dummy_cid, spoken_passphrase=test_phrase, resume_headless=False,
    ))
    staged_file = dummy_dir / "scratch" / "gemini_research_handoff.md"
    assert staged_obj.get("ok") is True and staged_obj.get("status") == "STAGED_ONLY" and str(staged_obj.get("handoff_id", "")).endswith("-01")
    assert staged_file.is_file() and "Staged markdown body." in staged_file.read_text(encoding="utf-8")

    assert DEFAULT_BIND_HOST == "127.0.0.1" and is_client_ip_allowed("127.0.0.1") and not is_client_ip_allowed("203.0.113.42")
    assert Path.home().resolve() not in resolve_allowed_git_roots(AGY_GITLAB_DIR, AGY_DATA_DIR, AGY_WORKSPACE_DIR)
    assert sanitize_git_ref("--output=/tmp/pwn") == "output/tmp/pwn" and sanitize_conv_id("--csrf_token") == "csrf_token"
    assert guard_cli_positional("--help").startswith("\n")

    orig_url, orig_sec, orig_tok = cfg.AGY_HOST_BRIDGE_URL, cfg.PATH_SECRET, cfg.HOST_BRIDGE_TOKEN
    cfg.PATH_SECRET, cfg.HOST_BRIDGE_TOKEN = test_secret, ""
    exp_tok = derive_bridge_token(path_secret=test_secret, explicit_token="")
    hb_mod.BRIDGE_TOKEN_OVERRIDE = exp_tok
    hb_mod.HostBridgeHandler.quiet_logs = True
    hb_srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), hb_mod.HostBridgeHandler)
    threading.Thread(target=hb_srv.serve_forever, daemon=True).start()
    cfg.AGY_HOST_BRIDGE_URL = f"http://127.0.0.1:{hb_srv.server_port}/agentapi"
    tmp_hb_git = AGY_DATA_DIR / "worktrees" / "_selftest_hb_git"
    try:
        def _hb(body: dict, hdrs: dict[str, str]) -> tuple[int, dict]:
            req = urllib.request.Request(cfg.AGY_HOST_BRIDGE_URL, data=json.dumps(body).encode("utf-8"), headers=hdrs, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=5) as r:
                    return r.status, json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                return e.code, json.loads(e.read().decode("utf-8"))

        assert _hb({"action": "discover"}, {"Content-Type": "application/json"})[0] == 401
        assert _hb({"action": "discover"}, {"Content-Type": "application/json", "X-Bridge-Token": "wrong_" + "0" * 40})[0] == 401
        assert _hb({"action": "discover"}, {"Content-Type": "application/json", "X-Bridge-Token": exp_tok, "Origin": "https://evil.example"})[0] == 403
        assert _hb({"action": "git-inspect", "workspace_path": str(Path.home())}, cfg.get_host_bridge_headers())[1].get("ok") is False
        cfg_repo = get_antigravity_config_repo()
        git_inspect_ws = cfg_repo if (cfg_repo / ".git").exists() else (repo_root if (repo_root is not None and (repo_root / ".git").exists()) else _ensure_probe_git_repo(tmp_hb_git))
        assert _hb({"action": "git-inspect", "workspace_path": str(git_inspect_ws), "summary_only": True}, cfg.get_host_bridge_headers())[1].get("ok") is True

        captured: list[dict] = []
        hb_mod.MOCK_ACTION_HANDLER = lambda p: (captured.append(p) or {"ok": True, "returncode": 0, "conversation_id": p.get("conversation_id", dummy_cid)})
        res_ov = json.loads(send_handoff_and_resume(
            research_markdown="RESUME_STAGED", session_identifier=dummy_cid, spoken_passphrase=test_phrase,
            resume_headless=True, allow_chained_publish=True, force_interrupt=True,
        ))
        assert res_ov.get("ok") is True and res_ov.get("write_mode") == "read_staged" and res_ov.get("execution_mode") == "fast"
        assert captured and "<!-- Handshake Gemini Research Handoff -->" not in captured[0].get("prompt", "")
    finally:
        hb_mod.MOCK_ACTION_HANDLER = None
        hb_mod.BRIDGE_TOKEN_OVERRIDE = ""
        hb_srv.shutdown()
        hb_srv.server_close()
        shutil.rmtree(tmp_hb_git, ignore_errors=True)
        cfg.AGY_HOST_BRIDGE_URL, cfg.PATH_SECRET, cfg.HOST_BRIDGE_TOKEN = orig_url, orig_sec, orig_tok


def _test_uploads_staging_and_host_bridge(app: Any, test_phrase: str, test_secret: str, expected_hash: str, orig_hash: str) -> None:
    """Verify synthetic context exceeded immunity, batch uploads, staging, and Host Bridge."""
    from agy_nexus.session_status import check_context_exceeded
    from agy_nexus.uploads import list_scratch_upload_batches, sanitize_filename, save_scratch_upload_batch, validate_conv_id

    with tempfile.TemporaryDirectory() as synth_str:
        sb = Path(synth_str)
        for sid, row in (
            ("synth-clean", {"type": "USER_INPUT", "source": "USER_EXPLICIT", "content": "Context window exceeded?"}),
            ("synth-exceeded", {"type": "PLANNER_RESPONSE", "status": "ERROR", "error": "Context window exceeded"}),
        ):
            lp = sb / sid / ".system_generated" / "logs" / "transcript.jsonl"
            lp.parent.mkdir(parents=True, exist_ok=True)
            lp.write_text(json.dumps(row) + "\n", encoding="utf-8")
        assert check_context_exceeded("synth-clean", brain_dir=sb) is False and check_context_exceeded("synth-exceeded", brain_dir=sb) is True
    assert validate_conv_id("../../etc") is False and validate_conv_id("11111111-1111-4111-8111-111111111111") is True
    assert sanitize_filename("../bad/name.txt") == "name.txt" and "/web/api/sessions/" in (app.web_dir / "uploads.js").read_text(encoding="utf-8")

    dummy_cid = "00000000-0000-0000-0000-000000000000"
    dummy_dir = AGY_BRAIN_DIR / dummy_cid
    dummy_dir.mkdir(parents=True, exist_ok=True)
    cfg.PASS_HASH = expected_hash
    try:
        res_up = save_scratch_upload_batch(dummy_cid, [("test_a.txt", b"hello world", "text/plain"), ("test_b.json", b'{"k": 1}', "application/json")], label="selftest", brain_dir=AGY_BRAIN_DIR)
        assert res_up.get("ok") is True and res_up.get("file_count") == 2 and (Path(res_up["batch_folder"]) / "INDEX.md").is_file()
        bound = "----NexusSelfTestBoundary99"
        mp_body = (f"--{bound}\r\nContent-Disposition: form-data; name=\"label\"\r\n\r\nasgi_e2e\r\n--{bound}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"shot_01.png\"\r\nContent-Type: image/png\r\n\r\nPNGDATA\r\n--{bound}--\r\n").encode("utf-8")
        out_msgs, sent = [], False
        async def _recv() -> dict:
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": mp_body, "more_body": False}
            return {"type": "http.request", "body": b"", "more_body": False}
        asyncio.run(app({"type": "http", "method": "POST", "path": f"/web/api/sessions/{dummy_cid}/upload", "query_string": b"", "headers": [(b"content-type", f"multipart/form-data; boundary={bound}".encode()), (b"x-nexus-passphrase", test_phrase.encode())]}, _recv, lambda m: out_msgs.append(m) or asyncio.sleep(0)))
        assert out_msgs and out_msgs[0].get("status") == 200 and len(list_scratch_upload_batches(dummy_cid, brain_dir=AGY_BRAIN_DIR)) == 2
        orig_bg = cfg.AGY_BG_DIR
        with tempfile.TemporaryDirectory() as tmp_bg:
            cfg.AGY_BG_DIR = Path(tmp_bg)
            try:
                _run_host_bridge_checks(dummy_dir, dummy_cid, test_phrase, test_secret)
            finally:
                cfg.AGY_BG_DIR = orig_bg
    finally:
        cfg.PASS_HASH = orig_hash
        shutil.rmtree(dummy_dir, ignore_errors=True)
    print("  [+] Context Exceeded Immunity, Repo-Prefixed Handoff Queue & Two-Step Headless Override Gate: PASS")
    print("  [+] Host Bridge CWE-306 & CWE-88 Zero-Trust Auth, Loopback Default, CIDR & Root Sandbox: PASS")
    run_multimodal_media_self_test(test_phrase, expected_hash)
    print("  [+] Public Media Origin Resolution & <20 KB Multimodal WebP ImageContent MCP Endpoint: PASS")


def run_self_test() -> int:
    """Run automated verification in an isolated STATE_FILE sandbox without mutating live session_state.json."""
    orig_state_file, orig_state = cfg.STATE_FILE, copy.deepcopy(cfg.SESSION_STATE)
    with tempfile.TemporaryDirectory() as tmp_state_dir:
        cfg.STATE_FILE = Path(tmp_state_dir) / "session_state.json"
        try:
            print(f"[*] Running agy-nexus-mcp v{__version__} automated self-test...")
            test_phrase = "Example Bridge 2026!"
            expected_hash = hashlib.sha256(b"examplebridge2026").hexdigest()
            test_secret = "test_path_secret_at_least_32_characters_long_12345"
            sessions = _test_deadbolt_and_search(test_phrase, expected_hash)
            app = _test_stats_and_http_routes(test_secret)
            _test_drift_media_and_isolation(test_phrase, expected_hash, cfg.PASS_HASH)
            _test_skills_polyglot_and_outline(sessions, test_phrase, expected_hash, cfg.PASS_HASH)
            _test_uploads_staging_and_host_bridge(app, test_phrase, test_secret, expected_hash, cfg.PASS_HASH)
            print(f"[✓] All agy-nexus-mcp v{__version__} self-tests completed successfully!")
            return 0
        finally:
            cfg.STATE_FILE = orig_state_file
            cfg.SESSION_STATE.clear()
            cfg.SESSION_STATE.update(orig_state)
