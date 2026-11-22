#!/usr/bin/env python3
"""
Unit and regression test suite for AGY Nexus v3.1.0:
Unified Shell, Multi-Select Gallery, Canonical PWA Deep Links & In-Place Session Retirement.
"""

from __future__ import annotations

import ast
import io
import json
import os
from pathlib import Path
import re
import tempfile
import time
from typing import Any
import zipfile

import pytest

import agy_nexus
from agy_nexus.web_routes import PWA_ASSETS
from agy_nexus.bucket_api import (
    build_session_zip,
    get_session_bucket_payload,
    get_session_file_payload,
)
from agy_nexus.code_health import get_modular_hygiene_summary
from agy_nexus.media import (
    MEDIA_TTL_SECONDS,
    _is_public_hostname,
    build_workspace_deep_link,
    compute_media_hmac,
    get_public_base_url,
    record_verified_public_origin,
    sign_media_url,
    verify_and_resolve_media,
)
from agy_nexus.retirement import (
    build_suggested_actions,
    extract_prior_session_baton,
    get_closeout_directives,
    get_retirement_record,
    infer_continuity_intent,
    is_closeout_intent,
    is_session_retired,
    record_session_retirement,
)
from agy_nexus.session_status import evaluate_rollover_posture


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src" / "agy_nexus"
WEB_DIR = PROJECT_ROOT / "web"


def test_v310_version_bump() -> None:
    """Verify package version is bumped to 4.0.0 across pyproject.toml and package."""
    assert agy_nexus.__version__ == "4.0.0"

    pyproject_text = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "4.0.0"' in pyproject_text

    manifest_data = json.loads((WEB_DIR / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest_data.get("handle_links") == "preferred"
    assert "launch_handler" in manifest_data


def test_modular_hygiene_and_line_ceilings() -> None:
    """Enforce strict line ceilings on all modified and newly extracted modules."""
    files_to_check = {
        SRC_DIR / "retirement.py": 220,
        SRC_DIR / "handoff.py": 500,
        SRC_DIR / "session_status.py": 470,
        SRC_DIR / "target_resolver.py": 500,
        SRC_DIR / "media.py": 500,
        SRC_DIR / "bucket_api.py": 650,
        SRC_DIR / "config.py": 500,
        SRC_DIR / "stats.py": 500,
        WEB_DIR / "gallery_select.js": 260,
        WEB_DIR / "explorer.js": 480,
        WEB_DIR / "markdown_renderer.js": 500,
        WEB_DIR / "styles.css": 650,
    }

    for path, max_lines in files_to_check.items():
        assert path.exists(), f"File {path} does not exist"
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        assert line_count <= max_lines, (
            f"{path.name} exceeds budget: {line_count} lines (budget <= {max_lines})"
        )

    # Check function lengths in handoff.py (specifically send_handoff_and_resume <= 95L)
    tree = ast.parse((SRC_DIR / "handoff.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            length = node.end_lineno - node.lineno + 1
            if node.name == "send_handoff_and_resume":
                assert length <= 95, (
                    f"send_handoff_and_resume exceeds 95L budget: {length} lines"
                )
            assert length <= 100, f"Function {node.name} exceeds 100L hard max: {length} lines"


def test_media_origin_filtering() -> None:
    """Verify _is_public_hostname rejects 12-hex container hostnames and LAN hosts."""
    assert not _is_public_hostname("a1b2c3d4e5f6")
    assert not _is_public_hostname("a1b2c3d4e5f6.bridge-test.org")
    assert _is_public_hostname("ag-a1b2c3d4.bridge-test.org")
    assert not _is_public_hostname("localhost")
    assert not _is_public_hostname("node.lan")
    assert not _is_public_hostname("192.168.1.50")
    assert not _is_public_hostname("example.com")

    # Synthetic public domain
    assert _is_public_hostname("agy-mcp.bridge-test.org")
    assert _is_public_hostname("overwatch.bridge-test.org")


def test_media_query_parameter_tolerance_and_deep_link(tmp_path: Path) -> None:
    """Verify media route handles trailing query parameters and generates valid workspace_url."""
    # Test query param tolerance in verify_and_resolve_media
    now_ts = int(time.time())
    exp_ts = now_ts + 3600
    sig = compute_media_hmac(exp_ts, "brain:test-conv", "scratch/test.png")
    valid_req = f"/web/media/{exp_ts}/{sig}/brain%3Atest-conv/scratch/test.png?hl=en-US&zoom=1"

    # Directory won't exist but the parser should strip query string and proceed past traversal/sig checks
    _, _, status, err = verify_and_resolve_media(valid_req)
    # Status should be 404 (scope directory not found) not 400 (malformed) or 403 (invalid sig)
    assert status == 404
    assert "not found" in err.lower()

    # Test build_workspace_deep_link
    link = build_workspace_deep_link("test-conv-123", "scratch/diagram.png")
    assert "/web?" in link
    assert "view=workspace" in link
    assert "session=test-conv-123" in link
    assert "artifact=scratch%2Fdiagram.png" in link or "artifact=scratch/diagram.png" in link
    assert "sig=" in link


def test_bucket_api_zip_creation_and_traversal(tmp_path: Path) -> None:
    """Verify build_session_zip creates valid archive and blocks traversal."""
    conv_id = "test-session-zip"
    brain_dir = tmp_path / conv_id
    scratch_dir = brain_dir / "scratch"
    scratch_dir.mkdir(parents=True)

    img1 = scratch_dir / "test1.png"
    img1.write_bytes(b"\x89PNG\r\n\x1a\nfakeimage1")
    img2 = scratch_dir / "test2.jpg"
    img2.write_bytes(b"\xff\xd8\xff\xe0fakeimage2")

    # 1. Successful zip of all visual files
    status, payload_b, ctype = build_session_zip(conv_id, None, brain_dir=tmp_path)
    assert status == 200
    assert ctype == "application/zip"
    with zipfile.ZipFile(io.BytesIO(payload_b), "r") as zf:
        names = zf.namelist()
        assert "test1.png" in names
        assert "test2.jpg" in names

    # 2. Specific requested file
    status2, payload_b2, _ = build_session_zip(conv_id, ["scratch/test1.png"], brain_dir=tmp_path)
    assert status2 == 200
    with zipfile.ZipFile(io.BytesIO(payload_b2), "r") as zf:
        assert zf.namelist() == ["test1.png"]

    # 3. Path traversal rejection
    status3, _, _ = build_session_zip(conv_id, ["../../etc/passwd"], brain_dir=tmp_path)
    assert status3 == 403

    status4, _, _ = build_session_zip(conv_id, ["/etc/shadow"], brain_dir=tmp_path)
    assert status4 == 403


def test_terminal_session_closeout_and_retirement(tmp_path: Path) -> None:
    """Verify retirement manifest recording, detection, and closeout directives."""
    conv_id = "retire-test-conv"

    # Initially not retired
    assert not is_session_retired(conv_id, brain_dir=tmp_path)
    assert get_retirement_record(conv_id, brain_dir=tmp_path) is None

    # Record retirement
    rec = record_session_retirement(
        conv_id,
        brain_dir=tmp_path,
        final_commit_sha="abcdef123456",
        metadata={"release_version": "v3.1.0"},
    )
    assert rec["ok"] is True
    assert rec["final_commit_sha"] == "abcdef123456"

    # Verify detection
    assert is_session_retired(conv_id, brain_dir=tmp_path)
    stored = get_retirement_record(conv_id, brain_dir=tmp_path)
    assert stored is not None
    assert stored["final_commit_sha"] == "abcdef123456"
    assert stored["release_version"] == "v3.1.0"

    # Verify closeout directives
    directives = get_closeout_directives("/test/workspace")
    assert "git worktree prune" in directives
    assert "RETIRED.json" in directives
    assert "/test/workspace" in directives

    # Verify closeout intent detection
    assert is_closeout_intent(retire_session=True)
    assert is_closeout_intent(continuity="closeout")
    assert is_closeout_intent("Please clean up, push & deploy and finish the task")
    assert not is_closeout_intent("Let's add a small feature to web/app.js")


def test_rollover_posture_closeout_exemption(tmp_path: Path) -> None:
    """Verify session_continuity='closeout' exempts session from step-cap rollover."""
    conv_id = "test-high-step-conv"
    sess_dir = tmp_path / conv_id
    sess_dir.mkdir(parents=True)

    # High step session (step_count = 1550) normally rolls over
    p_normal = evaluate_rollover_posture(
        conv_id,
        step_count=1550,
        compaction_count=1,
        brain_dir=tmp_path,
        session_continuity="auto",
    )
    assert p_normal["posture"] == "HARD_ROLLOVER"
    assert p_normal["should_rollover"] is True

    # With session_continuity='closeout', it is exempt and executes in-place
    p_closeout = evaluate_rollover_posture(
        conv_id,
        step_count=1550,
        compaction_count=1,
        brain_dir=tmp_path,
        session_continuity="closeout",
    )
    assert p_closeout["posture"] == "CLOSEOUT_IN_PLACE"
    assert p_closeout["should_rollover"] is False

    # Retired session returns RETIRED posture
    record_session_retirement(conv_id, brain_dir=tmp_path)
    p_retired_close = evaluate_rollover_posture(
        conv_id,
        step_count=100,
        compaction_count=0,
        brain_dir=tmp_path,
        session_continuity="closeout",
    )
    assert p_retired_close["posture"] == "RETIRED"
    assert p_retired_close["should_rollover"] is False

    p_retired_fresh = evaluate_rollover_posture(
        conv_id,
        step_count=100,
        compaction_count=0,
        brain_dir=tmp_path,
        session_continuity="new_topic",
    )
    assert p_retired_fresh["posture"] == "RETIRED"
    assert p_retired_fresh["should_rollover"] is True


def test_suggested_actions_job_first() -> None:
    """Verify job-focused 1-tap Yes transitions for Gemini clients."""
    # 1. in_flight
    a_flight = build_suggested_actions("in_flight", target="agy-nexus-mcp", conv_id="abcdef123456")
    assert a_flight["phase"] == "in_flight"
    assert a_flight["prompt"] == "Check in on the build?"
    assert a_flight["options"][0]["label"] == "Yes"

    # 2. ready_to_ship (replaces plumbing audit_clean / high_step_retirement)
    a_ship = build_suggested_actions("ready_to_ship", target="agy-nexus-mcp")
    assert a_ship["phase"] == "ready_to_ship"
    assert a_ship["prompt"] == "Ship agy-nexus-mcp to GitHub?"
    assert a_ship["options"][0]["label"] == "Yes"

    a_clean = build_suggested_actions("audit_clean", target="agy-nexus-mcp")
    assert a_clean["phase"] == "ready_to_ship"
    assert a_clean["prompt"] == "Ship agy-nexus-mcp to GitHub?"

    a_retire = build_suggested_actions("high_step_retirement", target="agy-nexus-mcp", step_count=1050)
    assert a_retire["phase"] == "ready_to_ship"
    assert a_retire["prompt"] == "Ship agy-nexus-mcp to GitHub?"

    # 3. ready_to_run (default / pre_dispatch)
    a_run = build_suggested_actions("ready_to_run", target="agy-nexus-mcp")
    assert a_run["phase"] == "ready_to_run"
    assert a_run["prompt"] == "Run these changes and update the live preview?"
    assert a_run["options"][0]["label"] == "Yes"

    a_pre = build_suggested_actions("pre_dispatch", target="agy-nexus-mcp")
    assert a_pre["phase"] == "ready_to_run"
    assert a_pre["prompt"] == "Run these changes and update the live preview?"


def test_pwa_assets_and_shell_names_integrity() -> None:
    """Assert every <script src="/web/..."> and <link href="/web/..."> in web/index.html exists in PWA_ASSETS and sw.js SHELL_NAMES."""
    html_text = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    sw_text = (WEB_DIR / "sw.js").read_text(encoding="utf-8")

    shell_names_match = re.search(r"const SHELL_NAMES = new Set\(\[\s*([\s\S]*?)\s*\]\);", sw_text)
    assert shell_names_match, "SHELL_NAMES not found in sw.js"
    raw_entries = [s.strip().strip('"\'') for s in shell_names_match.group(1).split(",") if s.strip()]
    shell_names = {s for s in raw_entries if s}

    script_srcs = re.findall(r'<script\s+[^>]*src="/web/([^"?]+)', html_text)
    link_hrefs = re.findall(r'<link\s+[^>]*href="/web/([^"?]+)', html_text)
    referenced_assets = set(script_srcs + link_hrefs)
    assert len(referenced_assets) >= 10, f"Expected >= 10 assets, found {len(referenced_assets)}"

    for asset in referenced_assets:
        assert asset in PWA_ASSETS, f"Asset '{asset}' referenced in index.html is missing from PWA_ASSETS"
        assert asset in shell_names, f"Asset '{asset}' referenced in index.html is missing from sw.js SHELL_NAMES"
