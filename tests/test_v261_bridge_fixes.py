#!/usr/bin/env python3
"""Comprehensive regression suite for agy-nexus-mcp v2.7.0 & agy-polyglot-mcp."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import time

from PIL import Image as PILImage
from starlette.testclient import TestClient

PKG_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PKG_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import agy_nexus
import agy_nexus.config as cfg
from agy_nexus.code_health import get_modular_hygiene_summary
from agy_nexus.handoff import _unwrap_staged_handoff_markdown, send_handoff_and_resume
from agy_nexus.hygiene import HARD_MAX_FILE_LINES, TARGET_FILE_LINES, slice_file_content
from agy_nexus.inventory import resolve_customization_file
from agy_nexus.media import get_public_base_url
from agy_nexus.polyglot_index import (
    polyglot_file_outline,
    polyglot_repo_map,
    polyglot_symbol_search,
    refresh_polyglot_index,
)
from agy_nexus.polyglot_outline import build_polyglot_outline
from agy_nexus.routing import _session_matches_repo_hint
from agy_nexus.search import _search_workspaces_and_history
from agy_nexus.server import build_nexus_http_app
from agy_nexus.sessions import NEXUS_PROJECT_ID, pick_primary_workspace_uri
from agy_nexus.tools_media import encode_image_to_webp_budget, inspect_visual_artifacts
from agy_nexus.tools_ops import get_session_tree
from agy_nexus.tools_session import load_session_into_gemini
from agy_nexus.tools_workspace import ask_workspace_readonly
from agy_nexus.workspace import _resolve_and_read_files


def test_version_and_modular_budget() -> None:
    assert agy_nexus.__version__ == "2.7.0"
    assert TARGET_FILE_LINES == 500
    assert HARD_MAX_FILE_LINES == 650
    assert not (SRC_DIR / "agy_nexus" / "ast_outline.py").exists(), "ast_outline.py must be removed"
    report = get_modular_hygiene_summary(SRC_DIR / "agy_nexus")
    assert not report["syntax_errors"], f"Syntax errors found: {report['syntax_errors']}"
    assert report["target_lines"] == 500 and report["ceiling_lines"] == 650
    assert report["violations_over_650"] == 0, f"Files exceeding 650-line ceiling: {report['modules']}"


def test_polyglot_incremental_sha256_index() -> None:
    with tempfile.TemporaryDirectory(dir=str(cfg.AGY_DATA_DIR / "worktrees")) as tmp_ws_str:
        ws = Path(tmp_ws_str)
        (ws / "pkg").mkdir()
        py_f = ws / "pkg" / "alpha.py"
        py_f.write_text(
            'class Engine:\n    """Core engine class."""\n    def run_fast(self, x: int) -> int:\n        """Execute fast path."""\n        return x + 1\n',
            encoding="utf-8",
        )
        md_f = ws / "README.md"
        md_f.write_text("# Demo Repo\nOverview text.\n## Architecture\nDetails here.\n", encoding="utf-8")

        idx1 = refresh_polyglot_index(ws, force=True)
        idx_file = Path(idx1["stats"]["index_file"])
        try:
            assert idx1["stats"]["reindexed"] == 2
            assert idx1["stats"]["reused"] == 0

            idx2 = refresh_polyglot_index(ws, force=True)
            assert idx2["stats"]["reindexed"] == 0
            assert idx2["stats"]["reused"] == 2

            time.sleep(0.02)
            py_f.write_text(
                'class Engine:\n    """Core engine class."""\n    def run_fast(self, x: int) -> int:\n        """Execute fast path."""\n        return x + 2\n\ndef helper_fn() -> str:\n    """New helper."""\n    return "ok"\n',
                encoding="utf-8",
            )
            idx3 = refresh_polyglot_index(ws, force=True)
            assert idx3["stats"]["reindexed"] == 1
            assert idx3["stats"]["reused"] == 1

            hits = polyglot_symbol_search("helper_fn", workspace=str(ws), force_refresh=True)
            assert hits["ok"] is True and hits["total_matches"] >= 1
            assert hits["matches"][0]["summary"] == "New helper."

            ol = polyglot_file_outline("pkg/alpha.py", workspace=str(ws), include_callers=False)
            assert ol["ok"] is True and ol["symbol_count"] >= 2
            rmap = polyglot_repo_map(workspace=str(ws), force_refresh=True)
            assert rmap["ok"] is True and rmap["matched_files"] == 2
        finally:
            idx_file.unlink(missing_ok=True)


def test_1b_visual_fidelity_and_zoom_warning(monkeypatch=None) -> None:
    assert "strip binary" in (inspect_visual_artifacts.__doc__ or "").lower()
    with tempfile.TemporaryDirectory() as td:
        img_p = Path(td) / "mobile_ui.png"
        im = PILImage.new("RGB", (1080, 1920), color=(24, 32, 48))
        im.save(img_p, format="PNG")
        webp_b, meta = encode_image_to_webp_budget(img_p, budget_bytes=9000, max_edge=840, region="top", min_quality=58)
        assert len(webp_b) <= 9000
        tw, th = [int(x) for x in meta["thumb_px"].split("x")]
        assert max(tw, th) <= 840
        assert meta["quality"] >= 58

    orig_pub = cfg.os.environ.get("AG_BRIDGE_PUBLIC_URL")
    cfg.os.environ["AG_BRIDGE_PUBLIC_URL"] = "https://ag-demo.example.net"
    try:
        assert get_public_base_url() == "https://ag-demo.example.net"
    finally:
        if orig_pub is None:
            cfg.os.environ.pop("AG_BRIDGE_PUBLIC_URL", None)
        else:
            cfg.os.environ["AG_BRIDGE_PUBLIC_URL"] = orig_pub


def test_2a_2b_3a_3b_4_virtual_uris_slices_and_sessions() -> None:
    phrase = "Unit Test Pass 2026!"
    expected_hash = hashlib.sha256(b"unittestpass2026").hexdigest()
    orig_hash = cfg.PASS_HASH
    orig_db = cfg.AGY_DB_FILE
    dummy_cid = "11111111-2222-3333-4444-555555555555"
    sdir = cfg.AGY_BRAIN_DIR / dummy_cid
    logs_dir = sdir / ".system_generated" / "logs"
    batch_dir = sdir / "scratch" / "uploads_20261111_demo"
    logs_dir.mkdir(parents=True, exist_ok=True)
    batch_dir.mkdir(parents=True, exist_ok=True)

    (batch_dir / "INDEX.md").write_text("# Uploaded Batch\nUniqueMarkerToken_XYZ987\n", encoding="utf-8")
    long_resp = "Paragraph line with detailed architectural verification findings. " * 110  # ~7,150 chars on 1 line
    (logs_dir / "transcript.jsonl").write_text(
        json.dumps({"type": "PLANNER_RESPONSE", "content": "<truncated 6000 bytes>"}) + "\n",
        encoding="utf-8",
    )
    (logs_dir / "transcript_full.jsonl").write_text(
        json.dumps({"type": "USER_INPUT", "content": "Please verify UniqueTranscriptNeedle_42"}) + "\n"
        + json.dumps({"type": "PLANNER_RESPONSE", "content": long_resp}) + "\n",
        encoding="utf-8",
    )

    cfg.PASS_HASH = expected_hash
    try:
        # 2a: load_session_into_gemini reads transcript_full.jsonl & expands > 2,000 chars dynamically
        loaded = json.loads(load_session_into_gemini(dummy_cid, spoken_passphrase=phrase))
        assert loaded["ok"] is True
        assert len(loaded["latest_assistant_response"]) > 4500, f"Expected >4500 chars, got {len(loaded['latest_assistant_response'])}"
        assert "<truncated" not in loaded["latest_assistant_response"]

        # 2a: transcript:latest wraps single-line JSONL turn so start_line/end_line pagination works
        tr_slice = json.loads(
            ask_workspace_readonly(
                question="Page latest turn",
                file_subpath="transcript:latest",
                start_line=1,
                end_line=25,
                session_identifier=dummy_cid,
                spoken_passphrase=phrase,
            )
        )
        fd_tr = tr_slice["file_details"]
        assert fd_tr["shown_start_line"] == 1 and fd_tr["shown_end_line"] <= 25
        assert fd_tr["total_lines"] > 30, "Single-line turn must wrap into multiple <=136-col lines"

        # 2b: nested brain: URIs & scratch upload folders resolve cleanly without flattening
        for uri in (
            "brain:scratch/uploads_20261111_demo/INDEX.md",
            f"brain:{dummy_cid}/scratch/uploads_20261111_demo/INDEX.md",
            "scratch/uploads_20261111_demo/INDEX.md",
        ):
            r_b = _resolve_and_read_files(uri, ws=PKG_ROOT, session_dir=sdir)
            assert "UniqueMarkerToken_XYZ987" in r_b.get("content", ""), f"Failed resolving {uri}: {r_b}"

        trav = _resolve_and_read_files("brain:../../etc/passwd", ws=PKG_ROOT, session_dir=sdir)
        assert "error" in trav

        # 3a: explicit start_line/end_line slice sets hit_char_cap=False and skips full-file AST/Polyglot outlining
        sl = slice_file_content("\n".join(f"line {i}" for i in range(1, 200)), "demo.py", 5000, explicit_start_line=20, explicit_end_line=40)
        assert sl["truncated"] is True and sl["hit_char_cap"] is False
        explicit_read = _resolve_and_read_files("src/agy_nexus/server.py", ws=PKG_ROOT, start_line=10, end_line=35)
        assert "polyglot_outline" not in explicit_read and "ast_outline" not in explicit_read, "Explicit line slices must not run full-file outline!"
        assert resolve_customization_file("src/agy_nexus/server.py", cfg.AGY_CONFIG_DIR, cfg.AGY_DATA_DIR, PKG_ROOT) is None
        assert resolve_customization_file("*/*", cfg.AGY_CONFIG_DIR, cfg.AGY_DATA_DIR, PKG_ROOT) is None

        # 3b: Tier-0 pinned session search finds needle in transcript_full.jsonl & brain/ under wall-clock budget
        t0 = time.monotonic()
        s_res = _search_workspaces_and_history(
            "UniqueTranscriptNeedle_42",
            primary_ws=PKG_ROOT,
            conv_id=dummy_cid,
            workspace_pinned=True,
        )
        elapsed = time.monotonic() - t0
        assert elapsed < 3.8, f"Pinned search took too long: {elapsed:.2f}s"
        assert len(s_res.get("pinned_session_matches", [])) >= 1

        # 4: Policy-safe stats via get_session_tree(include_stats=True) and telemetry:stats virtual URI
        tree_stats = json.loads(get_session_tree(include_stats=True, period="last_7d", spoken_passphrase=phrase))
        assert tree_stats["ok"] is True and "ascii_mobile_report" in tree_stats and "quota_and_pools" in tree_stats
        v_stats = _resolve_and_read_files("telemetry:stats:last_7d", ws=PKG_ROOT, session_dir=sdir)
        assert "content" in v_stats and len(v_stats["content"]) > 100
    finally:
        cfg.PASS_HASH = orig_hash
        cfg.AGY_DB_FILE = orig_db
        shutil.rmtree(sdir, ignore_errors=True)


def test_5a_5b_handoff_modes_unwrap_and_nexus_routing() -> None:
    # 5b: 'Google Nexus' must NEVER hijack multi-URI workspace to antigravity-config
    uris = ["/home/dev/gitlab/google-nexus-retro", "/home/dev/gitlab/antigravity-config"]
    assert pick_primary_workspace_uri(uris, "Google Nexus 5X Bootloader Study") == "/home/dev/gitlab/google-nexus-retro"
    assert pick_primary_workspace_uri(uris, "AGY Nexus MCP v2.7.0 Refactor") == "/home/dev/gitlab/antigravity-config"

    if (cfg.AGY_GITLAB_DIR / "agy-nexus-mcp").is_dir():
        assert (
            pick_primary_workspace_uri(["/home/dev/gitlab/antigravity-config"], "Bridge Maintenance", NEXUS_PROJECT_ID)
            == str(cfg.AGY_GITLAB_DIR / "agy-nexus-mcp")
        )

    fake_cid = "deadbeef-0000-1111-2222-333333333333"
    cfg.SESSION_STATE["session_title_map"][fake_cid] = "Google Nexus Phone Camera Comparison"
    cfg.SESSION_STATE["session_workspace_map"][fake_cid] = "/home/dev/gitlab/mobile-notes"
    cfg.SESSION_STATE["session_workspace_uris_map"][fake_cid] = ["/home/dev/gitlab/mobile-notes"]
    assert _session_matches_repo_hint(fake_cid, "antigravity-config") is False

    # 5a: _unwrap_staged_handoff_markdown removes wrapper blocks cleanly
    phrase = "Handoff Test 2026!"
    expected_hash = hashlib.sha256(b"handofftest2026").hexdigest()
    orig_hash = cfg.PASS_HASH
    dummy_cid = "22222222-3333-4444-5555-666666666666"
    sdir = cfg.AGY_BRAIN_DIR / dummy_cid
    sdir.mkdir(parents=True, exist_ok=True)
    cfg.PASS_HASH = expected_hash
    try:
        body_3800 = "# Autonomous Release Spec\n\n" + ("Detailed acceptance criterion line.\n" * 95)
        assert len(body_3800) < 4500
        staged = json.loads(
            send_handoff_and_resume(
                research_markdown=body_3800,
                session_identifier=dummy_cid,
                resume_headless=False,
                spoken_passphrase=phrase,
            )
        )
        assert staged["status"] == "STAGED_ONLY"
        assert staged["execution_mode"] == "plan"
        assert "size_warning" not in staged

        staged_file = Path(staged["handoff_file"])
        raw_staged_disk = staged_file.read_text(encoding="utf-8")
        unwrapped = _unwrap_staged_handoff_markdown(raw_staged_disk)
        assert unwrapped == body_3800.strip()
        assert "Mandatory 4-Step Execution Lifecycle" not in unwrapped
    finally:
        cfg.PASS_HASH = orig_hash
        shutil.rmtree(sdir, ignore_errors=True)


def test_6_streamable_http_405_and_polyglot_zero_trust_lan_guard() -> None:
    secret = "unit_test_secret_token_with_more_than_32_chars_abcdef"
    poly_tok = cfg.get_polyglot_mcp_token(secret)
    app = build_nexus_http_app(secret, poly_tok)

    with TestClient(app) as client:
        # MCP Streamable HTTP Spec: 405 on GET / DELETE / HEAD to */mcp
        r_get = client.get(f"/{secret}/mcp")
        assert r_get.status_code == 405
        assert "POST" in r_get.headers.get("allow", "")
        assert client.delete(f"/{secret}/mcp").status_code == 405
        assert client.options(f"/{secret}/mcp").status_code == 204
        assert client.get(f"/polyglot/{poly_tok}/mcp").status_code == 405

        # Health & Web remain 200
        r_h = client.get("/health")
        assert r_h.status_code == 200 and r_h.json()["version"] == "2.7.0"

        # Zero-Trust LAN Guard blocks reverse-proxied / public-domain / DNS-rebinding / cross-origin requests to /polyglot/*
        for bad_hdrs in (
            {"X-Forwarded-For": "198.51.100.7"},
            {"X-Real-IP": "198.51.100.7"},
            {"CF-Connecting-IP": "198.51.100.7"},
            {"Host": "ag-123456.example.net"},
            {"Host": "evil.example:8765"},
            {"Origin": "http://evil.example"},
            {"Origin": "null"},
        ):
            r_deny = client.post(
                f"/polyglot/{poly_tok}/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                headers=bad_hdrs,
            )
            assert r_deny.status_code == 403, f"Expected 403 for headers {bad_hdrs}, got {r_deny.status_code}"

        # Wrong token -> 404
        assert client.post("/polyglot/wrong_token/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).status_code == 404

        # Direct LAN POST to agy-polyglot-mcp succeeds with zero deadbolt passphrase
        r_tools = client.post(f"/polyglot/{poly_tok}/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert r_tools.status_code == 200
        tool_names = {t["name"] for t in r_tools.json()["result"]["tools"]}
        assert tool_names == {"polyglot_map", "polyglot_search", "polyglot_outline"}

        r_call = client.post(
            f"/polyglot/{poly_tok}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "polyglot_outline", "arguments": {"file_subpath": "src/agy_nexus/hygiene.py", "workspace": str(PKG_ROOT)}},
            },
        )
        assert r_call.status_code == 200
        call_payload = json.loads(r_call.json()["result"]["content"][0]["text"])
        assert call_payload["ok"] is True and call_payload["symbol_count"] >= 3


def test_7_dual_review_security_and_invariants() -> None:
    import agy_nexus.handoff as handoff_mod
    from agy_nexus.hygiene import is_sensitive_filename

    assert is_sensitive_filename("secrets.env") is True
    assert is_sensitive_filename(".env.local") is True
    assert is_sensitive_filename("mcp_config.json") is True
    assert is_sensitive_filename(".env.example") is False
    assert is_sensitive_filename("mcp_config.template.json") is False

    # Sensitive file denial, relative escape denial, and YAML scalar redaction
    with tempfile.TemporaryDirectory(dir=str(cfg.AGY_DATA_DIR / "worktrees")) as tmp_ws_str:
        ws = Path(tmp_ws_str)
        (ws / "secrets.env").write_text("API_KEY=top_secret_value_999\n", encoding="utf-8")
        (ws / "config.yaml").write_text("database:\n  password: super_secret_yaml_pw\n", encoding="utf-8")
        assert polyglot_file_outline("secrets.env", workspace=str(ws))["ok"] is False
        assert polyglot_file_outline("../escape.py", workspace=str(ws))["ok"] is False
        ref = refresh_polyglot_index(ws, force=True, rebuild_all=True)
        assert "secrets.env" not in ref["index"]["files"]
        yaml_ol = polyglot_file_outline("config.yaml", workspace=str(ws))
        assert yaml_ol["ok"] is True
        assert "super_secret_yaml_pw" not in yaml_ol["formatted_outline"]

    # Empty/system-only transcript safety on transcript:latest
    empty_cid = "33333333-4444-5555-6666-777777777777"
    sdir = cfg.AGY_BRAIN_DIR / empty_cid
    logs_dir = sdir / ".system_generated" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "transcript_full.jsonl").write_text(
        json.dumps({"step_index": 0, "type": "SYSTEM", "content": ""}) + "\n", encoding="utf-8"
    )
    phrase = "Invariant Test 2026!"
    orig_hash = cfg.PASS_HASH
    orig_post = handoff_mod._post_bridge
    cfg.PASS_HASH = hashlib.sha256(b"invarianttest2026").hexdigest()
    try:
        res_t = _resolve_and_read_files("transcript:latest", ws=PKG_ROOT, session_dir=sdir)
        assert res_t.get("error") and "No conversational turns" in res_t["error"]

        handoff_mod._post_bridge = lambda payload: {"ok": False, "error": "simulated_bridge_offline"}
        failed_res = json.loads(
            send_handoff_and_resume(
                research_markdown="# Test Failed Wakeup\n\nBody.",
                session_identifier=empty_cid,
                resume_headless=True,
                force_interrupt=True,
                spoken_passphrase=phrase,
            )
        )
        assert failed_res["ok"] is False
        assert failed_res["status"] == "FAILED"
        assert failed_res["resumed"] is False
    finally:
        handoff_mod._post_bridge = orig_post
        cfg.PASS_HASH = orig_hash
        shutil.rmtree(sdir, ignore_errors=True)


if __name__ == "__main__":
    test_version_and_modular_budget()
    test_polyglot_incremental_sha256_index()
    test_1b_visual_fidelity_and_zoom_warning()
    test_2a_2b_3a_3b_4_virtual_uris_slices_and_sessions()
    test_5a_5b_handoff_modes_unwrap_and_nexus_routing()
    test_6_streamable_http_405_and_polyglot_zero_trust_lan_guard()
    test_7_dual_review_security_and_invariants()
    print("[✓] All v2.7.0 bridge & agy-polyglot-mcp regression tests PASSED!")
