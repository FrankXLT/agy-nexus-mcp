#!/usr/bin/env python3
"""
Unit and regression test suite for AGY Nexus v3.2.2:
- 7-day media-link docstrings (zero stale 30-minute media claims)
- Expanded visual artifact discovery (brain depth-3, git status -uall, repo visual folders)
- Session-isolated SQLite workspace resolution across bucket, markdown file, and zip endpoints
- Repository-aware ZIP downloads with member deduplication and traversal rejection
- 3.2.2 version consistency and modular line-count hygiene
"""
from __future__ import annotations

import ast
import base64
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import time
from typing import Any
from unittest.mock import patch
import zipfile

import pytest

import agy_nexus
import agy_nexus.bucket_api as bucket_api
import agy_nexus.config as cfg
import agy_nexus.media as media_mod
from agy_nexus.bucket_api import (
    build_session_zip,
    get_session_bucket_payload,
    get_session_file_payload,
    handle_bucket_api_request,
    rewrite_markdown_media_links,
)
from agy_nexus.media import discover_visual_artifacts, sign_media_url
from agy_nexus.tools_media import inspect_visual_artifacts
from agy_nexus.tools_session import load_session_into_gemini

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src" / "agy_nexus"
WEB_DIR = PROJECT_ROOT / "web"


def _make_test_db(db_path: Path, conv_id: str, ws_uri: str, title: str = "Quiet UI Pilot", project_id: str = "proj-1") -> None:
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            "CREATE TABLE conversation_summaries ("
            "conversation_id TEXT PRIMARY KEY, title TEXT, preview TEXT, step_count INTEGER, "
            "last_modified_time TEXT, workspace_uris TEXT, status TEXT, not_fully_idle INTEGER, "
            "killed INTEGER, parent_conversation_id TEXT, project_id TEXT)"
        )
        con.execute(
            "INSERT INTO conversation_summaries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (conv_id, title, title, 42, "2026-11-17 12:00:00+00:00", json.dumps([ws_uri]), "CASCADE_RUN_STATUS_IDLE", 0, 0, "", project_id),
        )
        con.commit()
    finally:
        con.close()


def test_v322_seven_day_media_docstrings_and_version() -> None:
    """Verify media-link docstrings advertise 7-day links (zero 30-min media claims) and version is 4.0.7."""
    assert agy_nexus.__version__ == "4.0.7"
    for target in (load_session_into_gemini, inspect_visual_artifacts, sign_media_url, media_mod):
        doc = (target.__doc__ or "").lower()
        assert "7-day" in doc, f"Missing 7-day description on {target}"
        assert "30-min" not in doc and "30-minute" not in doc, f"Stale 30-minute claim found on {target}"

    workflows_doc = (PROJECT_ROOT / "docs" / "WORKFLOWS.md").read_text(encoding="utf-8")
    assert "7-day" in workflows_doc
    assert "30-minute sliding-TTL deadbolt" in workflows_doc


def test_discover_visual_artifacts_brain_depth_git_and_folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify discover_visual_artifacts scans brain depth-3, git status -uall, and custom visual folders newest-first."""
    brain_root = tmp_path / "brain"
    ws_root = tmp_path / "projects"
    repo_dir = ws_root / "quiet-ui-skills"
    conv_id = "conv-quiet-ui-v322"

    (brain_root / conv_id / "scratch" / "gate4").mkdir(parents=True)
    (repo_dir / "screenshots_gate4").mkdir(parents=True)
    (repo_dir / "proofs").mkdir(parents=True)
    (repo_dir / "docs" / "pilot").mkdir(parents=True)
    (repo_dir / "docs" / "assets").mkdir(parents=True)
    (repo_dir / "node_modules" / "pkg").mkdir(parents=True)
    (repo_dir / "custom_dir").mkdir(parents=True)

    subprocess.run(["git", "init", "-q"], cwd=str(repo_dir), check=True)

    old_asset = repo_dir / "docs" / "assets" / "legacy.png"
    old_asset.write_bytes(b"\x89PNG\r\n\x1a\nold")
    old_ts = time.time() - 3600
    os.utime(old_asset, (old_ts, old_ts))

    brain_nested = brain_root / conv_id / "scratch" / "gate4" / "nested_brain.png"
    brain_nested.write_bytes(b"\x89PNG\r\n\x1a\nbrain")
    gate_shot = repo_dir / "screenshots_gate4" / "01_v01_icu_desktop_white.png"
    gate_shot.write_bytes(b"\x89PNG\r\n\x1a\ngate4")
    proof_shot = repo_dir / "proofs" / "proof_shot.webp"
    proof_shot.write_bytes(b"RIFF\x00\x00\x00\x00WEBP")
    pilot_shot = repo_dir / "docs" / "pilot" / "pilot_fig.png"
    pilot_shot.write_bytes(b"\x89PNG\r\n\x1a\npilot")
    git_untracked = repo_dir / "custom_dir" / "untracked_capture.png"
    git_untracked.write_bytes(b"\x89PNG\r\n\x1a\ncustom")
    ignored_mod = repo_dir / "node_modules" / "pkg" / "icon.png"
    ignored_mod.write_bytes(b"\x89PNG\r\n\x1a\nmod")

    now_ts = time.time()
    os.utime(gate_shot, (now_ts + 20, now_ts + 20))
    os.utime(brain_nested, (now_ts + 15, now_ts + 15))
    os.utime(git_untracked, (now_ts + 10, now_ts + 10))

    monkeypatch.setattr(cfg, "AGY_BRAIN_DIR", brain_root)
    monkeypatch.setattr(cfg, "AGY_PROJECTS_DIR", ws_root)
    monkeypatch.setattr(cfg, "AGY_WORKBOOKS_DIR", tmp_path / "workbooks")
    monkeypatch.setattr(cfg, "AGY_CONFIGURATION_DIR", tmp_path / "configuration")
    monkeypatch.setattr(cfg, "AGY_GITLAB_DIR", ws_root)

    found = discover_visual_artifacts(conv_id, workspace_path=str(repo_dir), limit=35, relative=True)
    rel_paths = [item["rel_path"] for item in found]

    assert "screenshots_gate4/01_v01_icu_desktop_white.png" in rel_paths
    assert "scratch/gate4/nested_brain.png" in rel_paths
    assert "proofs/proof_shot.webp" in rel_paths
    assert "docs/pilot/pilot_fig.png" in rel_paths
    assert "custom_dir/untracked_capture.png" in rel_paths
    assert "docs/assets/legacy.png" in rel_paths
    assert not any("node_modules" in p for p in rel_paths)

    assert found[0]["name"] == "01_v01_icu_desktop_white.png"
    assert isinstance(found[0]["mtime"], float) and found[0]["mtime"] > found[-1]["mtime"]
    assert found[0]["scope"] == "repo:quiet-ui-skills"
    assert "scope=repo%3Aquiet-ui-skills" in found[0]["workspace_url"]


def test_bucket_and_file_resolve_sqlite_ignoring_selected_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify bucket & file APIs resolve conv_id workspace from SQLite even when selected_workspace points elsewhere."""
    brain_root = tmp_path / "brain"
    ws_root = tmp_path / "projects"
    target_repo = ws_root / "quiet-ui-skills"
    other_repo = ws_root / "unrelated-repo"
    conv_id = "2f85383e-91a1-428a-8084-39cb4746e869"

    (brain_root / conv_id).mkdir(parents=True)
    (target_repo / "screenshots_gate4").mkdir(parents=True)
    (other_repo / "screenshots").mkdir(parents=True)

    shot = target_repo / "screenshots_gate4" / "01_v01_icu_desktop_white.png"
    shot.write_bytes(b"\x89PNG\r\n\x1a\ntarget")
    (other_repo / "screenshots" / "wrong_repo.png").write_bytes(b"\x89PNG\r\n\x1a\nwrong")

    walkthrough = brain_root / conv_id / "walkthrough.md"
    walkthrough.write_text(
        f"Abs: ![s1](file://{shot})\nRel: ![s2](./screenshots_gate4/01_v01_icu_desktop_white.png)\n",
        encoding="utf-8",
    )

    db_file = tmp_path / "conversation_summaries.db"
    _make_test_db(db_file, conv_id, f"file://{target_repo}", title="Quiet UI Phase 4")

    monkeypatch.setattr(cfg, "AGY_BRAIN_DIR", brain_root)
    monkeypatch.setattr(cfg, "AGY_PROJECTS_DIR", ws_root)
    monkeypatch.setattr(cfg, "AGY_GITLAB_DIR", ws_root)
    monkeypatch.setattr(bucket_api, "AGY_BRAIN_DIR", brain_root)
    monkeypatch.setattr(bucket_api, "AGY_DB_FILE", db_file)
    monkeypatch.setitem(cfg.SESSION_STATE, "selected_workspace", str(other_repo))
    monkeypatch.setitem(cfg.SESSION_STATE, "session_workspace_map", {})
    monkeypatch.setitem(cfg.SESSION_STATE, "session_project_name_map", {})
    monkeypatch.setitem(cfg.SESSION_STATE, "session_project_map", {})
    monkeypatch.setitem(cfg.SESSION_STATE, "session_title_map", {})
    monkeypatch.setitem(cfg.SESSION_STATE, "active_contexts", {})

    bucket = get_session_bucket_payload(conv_id)
    assert bucket["ok"] is True
    assert bucket["workspace_path"] == str(target_repo)
    assert bucket["title"] == "Quiet UI Phase 4"
    vis_names = [v["name"] for v in bucket["visual_artifacts"]]
    assert "01_v01_icu_desktop_white.png" in vis_names
    assert "wrong_repo.png" not in vis_names
    assert bucket["visual_artifacts"][0]["scope"] == "repo:quiet-ui-skills"
    assert isinstance(bucket["visual_artifacts"][0]["mtime"], float)

    # Clear map again so get_session_file_payload must resolve SQLite independently
    cfg.SESSION_STATE["session_workspace_map"].clear()
    status_code, file_payload = get_session_file_payload(conv_id, "walkthrough.md")
    assert status_code == 200
    assert file_payload["ok"] is True
    assert file_payload["content"].count("/web/media/") == 2
    assert "/repo:quiet-ui-skills/screenshots_gate4/01_v01_icu_desktop_white.png" in file_payload["content"]


@pytest.mark.asyncio
async def test_build_session_zip_repo_files_dedup_and_traversal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify build_session_zip & /download-zip include brain + repo captures, deduplicate names, and block traversal."""
    brain_root = tmp_path / "brain"
    ws_root = tmp_path / "projects"
    repo_dir = ws_root / "quiet-ui-skills"
    conv_id = "conv-zip-repo-test"

    (brain_root / conv_id / "screenshots_gate4").mkdir(parents=True)
    (repo_dir / "screenshots_gate4").mkdir(parents=True)
    (repo_dir / "README.md").write_text("# Docs", encoding="utf-8")

    b_shot = brain_root / conv_id / "screenshots_gate4" / "01_v01.png"
    b_shot.write_bytes(b"\x89PNG\r\n\x1a\nbrain_copy")
    r_shot1 = repo_dir / "screenshots_gate4" / "01_v01.png"
    r_shot1.write_bytes(b"\x89PNG\r\n\x1a\nrepo_copy")
    r_shot2 = repo_dir / "screenshots_gate4" / "02_v02.png"
    r_shot2.write_bytes(b"\x89PNG\r\n\x1a\nrepo_only")

    db_file = tmp_path / "conversation_summaries.db"
    _make_test_db(db_file, conv_id, str(repo_dir), title="Zip Test")

    monkeypatch.setattr(cfg, "AGY_BRAIN_DIR", brain_root)
    monkeypatch.setattr(cfg, "AGY_PROJECTS_DIR", ws_root)
    monkeypatch.setattr(cfg, "AGY_GITLAB_DIR", ws_root)
    monkeypatch.setattr(bucket_api, "AGY_BRAIN_DIR", brain_root)
    monkeypatch.setattr(bucket_api, "AGY_DB_FILE", db_file)
    monkeypatch.setitem(cfg.SESSION_STATE, "session_workspace_map", {})
    monkeypatch.setitem(cfg.SESSION_STATE, "active_contexts", {})

    # 1. Explicit scoped + bare repo requests with duplicate filename deduplication
    st, payload, ctype = build_session_zip(
        conv_id,
        [
            f"brain:{conv_id}/screenshots_gate4/01_v01.png",
            "repo:quiet-ui-skills/screenshots_gate4/01_v01.png",
            "screenshots_gate4/02_v02.png",
        ],
        brain_dir=brain_root,
        ws_path=str(repo_dir),
    )
    assert st == 200 and ctype == "application/zip"
    with zipfile.ZipFile(io.BytesIO(payload), "r") as zf:
        names = sorted(zf.namelist())
        assert names == ["01_v01.png", "01_v01_2.png", "02_v02.png"]

    # 2. Traversal, cross-session brain, and non-media file rejections (403)
    for bad in ("../../etc/passwd", "brain:other-conv/screenshots_gate4/01_v01.png", "README.md", "secrets.env"):
        bad_st, _, _ = build_session_zip(conv_id, [bad], brain_dir=brain_root, ws_path=str(repo_dir))
        assert bad_st == 403, f"Expected 403 for {bad}, got {bad_st}"

    # 3. End-to-end ASGI POST /web/api/sessions/{cid}/download-zip
    sent: list[dict[str, Any]] = []
    req_body = json.dumps({"files": ["repo:quiet-ui-skills/screenshots_gate4/02_v02.png"]}).encode("utf-8")

    async def recv() -> dict[str, Any]:
        return {"type": "http.request", "body": req_body, "more_body": False}

    async def snd(ev: dict[str, Any]) -> None:
        sent.append(ev)

    with patch("agy_nexus.bucket_api.verify_passphrase", return_value=True):
        await handle_bucket_api_request(
            scope={"type": "http", "method": "POST", "path": f"/web/api/sessions/{conv_id}/download-zip"},
            receive=recv,
            send=snd,
            req_path=f"/web/api/sessions/{conv_id}/download-zip",
            method="POST",
            headers=[(b"x-nexus-passphrase", b"ok")],
        )
    assert sent[0]["status"] == 200
    with zipfile.ZipFile(io.BytesIO(sent[1]["body"]), "r") as zf:
        assert zf.namelist() == ["02_v02.png"]

    # 4. Symlink bypass protection in default ZIP (requested_files=None) & media discovery
    outside_secret = tmp_path / "secrets.env"
    outside_secret.write_text("SECRET=should_never_leak\n", encoding="utf-8")
    (repo_dir / ".env").write_text("REPO_SECRET=no\n", encoding="utf-8")
    (brain_root / conv_id / "leak_outside.png").symlink_to(outside_secret)
    (repo_dir / "screenshots_gate4" / "leak_repo.png").symlink_to(repo_dir / ".env")

    discovered = discover_visual_artifacts(conv_id, workspace_path=str(repo_dir), limit=40, relative=True)
    disc_names = {d["name"] for d in discovered}
    assert "leak_outside.png" not in disc_names
    assert "leak_repo.png" not in disc_names
    assert "secrets.env" not in disc_names
    assert ".env" not in disc_names

    st_all, zip_all, _ = build_session_zip(conv_id, None, brain_dir=brain_root, ws_path=str(repo_dir))
    assert st_all == 200
    with zipfile.ZipFile(io.BytesIO(zip_all), "r") as zf:
        all_names = set(zf.namelist())
        assert "01_v01.png" in all_names
        assert "02_v02.png" in all_names
        assert "leak_outside.png" not in all_names
        assert "leak_repo.png" not in all_names
        assert "secrets.env" not in all_names
        assert ".env" not in all_names

    # 5. Reject malformed JSON and non-list 'files' in /download-zip
    for bad_body in (b"{bad json", json.dumps({"files": 123}).encode("utf-8"), json.dumps({"files": "str"}).encode("utf-8")):
        bad_sent: list[dict[str, Any]] = []

        async def bad_recv(body: bytes = bad_body) -> dict[str, Any]:
            return {"type": "http.request", "body": body, "more_body": False}

        async def bad_snd(ev: dict[str, Any]) -> None:
            bad_sent.append(ev)

        with patch("agy_nexus.bucket_api.verify_passphrase", return_value=True):
            await handle_bucket_api_request(
                scope={"type": "http", "method": "POST", "path": f"/web/api/sessions/{conv_id}/download-zip"},
                receive=bad_recv,
                send=bad_snd,
                req_path=f"/web/api/sessions/{conv_id}/download-zip",
                method="POST",
                headers=[(b"x-nexus-passphrase", b"ok")],
            )
        assert bad_sent[0]["status"] == 400


def test_inspect_visual_artifacts_unresolved_session_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify unresolved session_identifier fails closed instead of reading selected_workspace."""
    other_repo = tmp_path / "projects" / "other-repo"
    (other_repo / "screenshots").mkdir(parents=True)
    (other_repo / "screenshots" / "other.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    monkeypatch.setattr("agy_nexus.tools_media.is_unlocked", lambda p="": True)
    monkeypatch.setattr("agy_nexus.tools_media._resolve_session_identifier", lambda ident: "")
    monkeypatch.setitem(cfg.SESSION_STATE, "selected_workspace", str(other_repo))

    res = inspect_visual_artifacts(session_identifier="nonexistent-session-xyz")
    parsed = json.loads(res[0].text)
    assert parsed["ok"] is False
    assert "not found" in parsed["error"].lower()

    explorer_js = (WEB_DIR / "explorer.js").read_text(encoding="utf-8")
    assert 'data-copy="${escapeHtmlSafe(cid)}"' in explorer_js
    app_js = (WEB_DIR / "app.js").read_text(encoding="utf-8")
    assert "/^[a-zA-Z0-9_-]{1,64}$/.test(" in app_js


def test_session_vs_shared_repo_asset_separation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify session captures exclude committed/other-session repo assets into repo_visual_assets."""
    brain_root = tmp_path / "brain"
    ws_root = tmp_path / "projects"
    repo_dir = ws_root / "quiet-ui-skills"
    old_cid, new_cid = "phase0-old-session", "gate4-active-session"

    (brain_root / old_cid).mkdir(parents=True)
    (brain_root / new_cid / "screenshots_gate4").mkdir(parents=True)
    (repo_dir / "docs" / "assets").mkdir(parents=True)
    (repo_dir / "screenshots_gate4").mkdir(parents=True)

    subprocess.run(["git", "init", "-q"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.email", "ci@example.com"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.name", "CI"], cwd=str(repo_dir), check=True)

    logo = repo_dir / "docs" / "assets" / "logo.svg"
    logo.write_text("<svg xmlns='http://www.w3.org/2000/svg' width='64' height='64'/>", encoding="utf-8")
    hero = repo_dir / "docs" / "assets" / "hero.png"
    hero.write_bytes(b"\x89PNG\r\n\x1a\nhero")
    subprocess.run(["git", "add", "docs/assets"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "commit shared repo assets"], cwd=str(repo_dir), check=True)

    gate4_brain = brain_root / new_cid / "screenshots_gate4" / "01_v01.png"
    gate4_brain.write_bytes(b"\x89PNG\r\n\x1a\nbrain")
    gate4_uncommitted = repo_dir / "screenshots_gate4" / "02_uncommitted.png"
    gate4_uncommitted.write_bytes(b"\x89PNG\r\n\x1a\nrepo_new")

    now_dt = datetime.now(timezone.utc)
    old_dt = now_dt - timedelta(hours=3)
    db_file = tmp_path / "conversation_summaries.db"
    con = sqlite3.connect(str(db_file))
    con.execute(
        "CREATE TABLE conversation_summaries ("
        "conversation_id TEXT PRIMARY KEY, title TEXT, preview TEXT, step_count INTEGER, "
        "last_modified_time TEXT, last_user_input_time TEXT, workspace_uris TEXT, status TEXT, "
        "not_fully_idle INTEGER, killed INTEGER, parent_conversation_id TEXT, project_id TEXT)"
    )
    con.execute(
        "INSERT INTO conversation_summaries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (old_cid, "Phase 0 Audit", "Phase 0", 12, old_dt.isoformat(), (old_dt - timedelta(hours=1)).isoformat(), json.dumps([f"file://{repo_dir}"]), "CASCADE_RUN_STATUS_IDLE", 0, 0, "", "proj-q"),
    )
    con.execute(
        "INSERT INTO conversation_summaries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (new_cid, "Gate 4 Capture", "Gate 4", 24, now_dt.isoformat(), (now_dt - timedelta(minutes=20)).isoformat(), json.dumps([f"file://{repo_dir}"]), "CASCADE_RUN_STATUS_IDLE", 0, 0, "", "proj-q"),
    )
    con.commit()
    con.close()

    monkeypatch.setattr(cfg, "AGY_BRAIN_DIR", brain_root)
    monkeypatch.setattr(cfg, "AGY_PROJECTS_DIR", ws_root)
    monkeypatch.setattr(cfg, "AGY_GITLAB_DIR", ws_root)
    monkeypatch.setattr(cfg, "AGY_DB_FILE", db_file)
    monkeypatch.setattr(bucket_api, "AGY_BRAIN_DIR", brain_root)
    monkeypatch.setattr(bucket_api, "AGY_DB_FILE", db_file)
    monkeypatch.setitem(cfg.SESSION_STATE, "session_workspace_map", {})
    monkeypatch.setitem(cfg.SESSION_STATE, "active_contexts", {})

    old_bucket = get_session_bucket_payload(old_cid)
    assert old_bucket["ok"] is True
    assert old_bucket["visual_artifacts"] == []
    repo_names = {x["name"] for x in old_bucket["repo_visual_assets"]}
    assert {"logo.svg", "hero.png"}.issubset(repo_names)

    new_bucket = get_session_bucket_payload(new_cid)
    assert new_bucket["ok"] is True
    new_vis_names = {x["name"] for x in new_bucket["visual_artifacts"]}
    assert new_vis_names == {"01_v01.png", "02_uncommitted.png"}
    assert all(x["category"] == "session" for x in new_bucket["visual_artifacts"])
    new_repo_names = {x["name"] for x in new_bucket["repo_visual_assets"]}
    assert {"logo.svg", "hero.png"}.issubset(new_repo_names)
    assert all(x["category"] == "repo_asset" for x in new_bucket["repo_visual_assets"])
    assert media_mod.count_brain_visual_captures(old_cid, media_mod.ALLOWED_MEDIA_EXTENSIONS, brain_root) == 0
    assert media_mod.count_brain_visual_captures(new_cid, media_mod.ALLOWED_MEDIA_EXTENSIONS, brain_root) == 1


def test_sheet_builder_math_and_store_zip(tmp_path: Path) -> None:
    """Verify sheet_builder.js 2/4/8 3072px layout optimization, order selection, and CRC32 STORE ZIP."""
    node_bin = shutil.which("node")
    assert node_bin, "Node.js is required for frontend sheet_builder unit tests"
    runner = tmp_path / "verify_sheet_math.cjs"
    runner.write_text(
        f"""
const assert = require("assert");
const SB = require({json.dumps(str(WEB_DIR / "sheet_builder.js"))});
const GS = require({json.dumps(str(WEB_DIR / "gallery_select.js"))});

const items20 = Array.from({{ length: 20 }}, (_, i) => ({{ scope: "brain:s1", rel_path: `img_${{i+1}}.png`, name: `img_${{i+1}}.png` }}));
assert.strictEqual(SB.partitionChunks(items20, 4).length, 5);
assert.strictEqual(SB.partitionChunks(items20, 2).length, 10);
assert.strictEqual(SB.partitionChunks(items20, 8).map((c) => c.length).join(","), "8,8,4");

const portLayout = SB.chooseSheetLayout([{{ w: 780, h: 1688 }}, {{ w: 780, h: 1688 }}], 2);
assert.strictEqual(portLayout.cols, 2);
assert.strictEqual(portLayout.rows, 1);
assert.ok(portLayout.canvasW <= 3072 && portLayout.canvasH <= 3072);
assert.ok(portLayout.placements.every((p) => p.scale <= 1.0 && p.scale > 0.99));

const wideLayout = SB.chooseSheetLayout([{{ w: 2400, h: 1500 }}, {{ w: 2400, h: 1500 }}], 2);
assert.strictEqual(wideLayout.cols, 1);
assert.strictEqual(wideLayout.rows, 2);
assert.ok(wideLayout.canvasW <= 3072 && wideLayout.canvasH <= 3072);

const quadLayout = SB.chooseSheetLayout(Array.from({{ length: 4 }}, () => ({{ w: 1440, h: 900 }})), 4);
assert.strictEqual(quadLayout.cols, 2);
assert.strictEqual(quadLayout.rows, 2);
assert.ok(quadLayout.canvasW <= 3072 && quadLayout.canvasH <= 3072);
assert.ok(quadLayout.placements.every((p) => p.scale === 1.0));

GS.clearSelection();
GS.toggleItem(items20[0], true, 0);
GS.toggleItem(items20[2], true, 2);
GS.toggleItem(items20[5], true, 5);
assert.strictEqual(GS.getSelectionIndex(items20[0]), 1);
assert.strictEqual(GS.getSelectionIndex(items20[2]), 2);
assert.strictEqual(GS.getSelectionIndex(items20[5]), 3);
GS.toggleItem(items20[2], false, 2);
assert.strictEqual(GS.getSelectionIndex(items20[5]), 2);

const zBytes = SB.buildStoreZip([
  {{ name: "sheet01.png", data: Buffer.from("PNGDATA_ONE") }},
  {{ name: "sheet02.png", data: Buffer.from("PNGDATA_TWO") }},
]);
process.stdout.write(Buffer.from(zBytes).toString("base64"));
""",
        encoding="utf-8",
    )
    proc = subprocess.run([node_bin, str(runner)], capture_output=True, text=True, check=True)
    zip_bytes = base64.b64decode(proc.stdout.strip())
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        assert zf.testzip() is None
        assert zf.namelist() == ["sheet01.png", "sheet02.png"]
        assert zf.read("sheet01.png") == b"PNGDATA_ONE"
        assert zf.read("sheet02.png") == b"PNGDATA_TWO"


def test_v322_modular_hygiene_and_line_ceilings() -> None:
    """Verify file line budgets, removed Drag-Select button, and <= 100L Python functions across v3.2.2."""
    budgets = {
        SRC_DIR / "media.py": 500,
        SRC_DIR / "media_discovery.py": 500,
        SRC_DIR / "bucket_api.py": 550,
        SRC_DIR / "bucket_zip.py": 500,
        SRC_DIR / "tools_media.py": 500,
        WEB_DIR / "styles.css": 500,
        WEB_DIR / "workspace.css": 500,
        WEB_DIR / "gallery_select.js": 260,
        WEB_DIR / "gallery_view.js": 500,
        WEB_DIR / "sheet_builder.js": 500,
        WEB_DIR / "explorer.js": 480,
    }
    for path, limit in budgets.items():
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) <= limit, f"{path.name} has {len(lines)} lines (limit <= {limit})"
        if path.suffix == ".py":
            tree = ast.parse("\n".join(lines), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    fn_len = node.end_lineno - node.lineno + 1 if hasattr(node, "end_lineno") else 0
                    assert fn_len <= 100, f"{path.name}:{node.name} is {fn_len}L (>100L)"
        elif path.name in ("explorer.js", "gallery_select.js", "gallery_view.js", "workspace.css"):
            assert "btn-toggle-drag-select" not in "\n".join(lines)


def test_v322_dual_review_p1_security_and_window_fixes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify P1 fixes: empty PASS_HASH 403, staged_handoffs containment, uploads scope/mtime, worktree depth-2, and window non-overlap."""
    import agy_nexus.bucket_zip as bucket_zip
    import agy_nexus.media_discovery as media_disc
    import agy_nexus.uploads as uploads_mod

    brain_root = tmp_path / "brain"
    bg_dir = tmp_path / "bg"
    data_dir = tmp_path / "agy_data"
    conv_id = "p1-security-conv"
    (brain_root / conv_id / "scratch" / "uploads_20261117_120000").mkdir(parents=True)
    (bg_dir / "staged_handoffs").mkdir(parents=True)
    wt_repo = data_dir / "worktrees" / "bucket-1" / "demo-wt"
    wt_repo.mkdir(parents=True)

    cap_img = brain_root / conv_id / "scratch" / "uploads_20261117_120000" / "cap.png"
    cap_img.write_bytes(b"\x89PNG\r\n\x1a\ncap")
    (brain_root / conv_id / "ok.png").write_bytes(b"\x89PNG\r\n\x1a\nok")

    monkeypatch.setattr(cfg, "AGY_BRAIN_DIR", brain_root)
    monkeypatch.setattr(cfg, "AGY_DATA_DIR", data_dir)
    monkeypatch.setattr(cfg, "PASS_HASH", "test-pass-hash")
    monkeypatch.setattr(bucket_api, "AGY_BRAIN_DIR", brain_root)
    monkeypatch.setattr(bucket_api, "AGY_BG_DIR", bg_dir)
    monkeypatch.setattr(uploads_mod, "AGY_BRAIN_DIR", brain_root)

    # 1. Empty PASS_HASH fails closed with 403
    signed_rel = sign_media_url(f"brain:{conv_id}", "ok.png", relative=True)
    monkeypatch.setattr(cfg, "PASS_HASH", "")
    resolved, _, status, msg = media_mod.verify_and_resolve_media(signed_rel)
    assert resolved is None and status == 403 and "configured" in msg.lower()
    monkeypatch.setattr(cfg, "PASS_HASH", "test-pass-hash")

    # 2. staged_handoffs/ isolation, symlink rejection, and 10 MB read limit
    ok_handoff = bg_dir / "staged_handoffs" / "demo-01.md"
    ok_handoff.write_text("# Demo Handoff\n", encoding="utf-8")
    outside_bg = bg_dir / "bridge_state.json"
    outside_bg.write_text('{"secret":1}', encoding="utf-8")
    (bg_dir / "staged_handoffs" / "leak.md").symlink_to(outside_bg)

    st_ok, pay_ok = get_session_file_payload(conv_id, "staged_handoffs/demo-01.md")
    assert st_ok == 200 and pay_ok["ok"] is True
    st_sym, _ = get_session_file_payload(conv_id, "staged_handoffs/leak.md")
    assert st_sym == 403
    st_out, _ = get_session_file_payload(conv_id, "bridge_state.json")
    assert st_out == 404

    huge_md = brain_root / conv_id / "huge.md"
    with huge_md.open("wb") as fh:
        fh.truncate(bucket_api.MAX_DOC_BYTES + 8)
    st_big, _ = get_session_file_payload(conv_id, "huge.md")
    assert st_big == 413

    # 3. scan_session_uploads & uploads.list_scratch_upload_batches emit scope and mtime
    sc_batches = bucket_api.scan_session_uploads(conv_id)
    assert len(sc_batches) == 1
    sc_img = sc_batches[0]["signed_images"][0]
    assert sc_img["scope"] == f"brain:{conv_id}" and float(sc_img["mtime"]) > 0
    up_batches = uploads_mod.list_scratch_upload_batches(conv_id, brain_dir=brain_root)
    assert up_batches[0]["signed_images"][0]["scope"] == f"brain:{conv_id}"
    assert float(up_batches[0]["signed_images"][0]["mtime"]) > 0

    # 4. Depth-2 worktree scope lookup & ZIP cap constant sanity
    assert media_mod._resolve_scope_base_dir("repo:demo-wt") == wt_repo.resolve()
    assert bucket_zip.MAX_ZIP_FILES == 100

    # 5. Ownership window ignores stale idle gap after prev_end & prevents prev_end overlap
    now_dt = datetime.now(timezone.utc)
    now_ts = now_dt.timestamp()
    db_file = tmp_path / "conv_win.db"
    con = sqlite3.connect(str(db_file))
    con.execute(
        "CREATE TABLE conversation_summaries ("
        "conversation_id TEXT PRIMARY KEY, title TEXT, preview TEXT, step_count INTEGER, "
        "last_modified_time TEXT, last_user_input_time TEXT, workspace_uris TEXT, status TEXT, "
        "not_fully_idle INTEGER, killed INTEGER, parent_conversation_id TEXT, project_id TEXT)"
    )
    con.execute(
        "INSERT INTO conversation_summaries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("sess-old", "Old", "Old", 5, (now_dt - timedelta(days=2)).isoformat(), (now_dt - timedelta(days=2, hours=1)).isoformat(), json.dumps([f"file://{wt_repo}"]), "IDLE", 0, 0, "", "p1"),
    )
    con.execute(
        "INSERT INTO conversation_summaries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("sess-new", "New", "New", 8, now_dt.isoformat(), (now_dt - timedelta(minutes=10)).isoformat(), json.dumps([f"file://{wt_repo}"]), "IDLE", 0, 0, "", "p1"),
    )
    con.commit()
    con.close()

    is_lat, s_ts, e_ts = media_disc.resolve_session_ownership_window("sess-new", wt_repo.resolve(), brain_root / conv_id, db_file)
    assert is_lat is True
    assert s_ts > now_ts - 3600.0
    assert e_ts >= now_ts

    # Adjacent non-overlap test: prev ended 20s ago, curr started 50s ago -> clamped to prev_end
    con = sqlite3.connect(str(db_file))
    prev_end_dt = now_dt - timedelta(seconds=20)
    con.execute("UPDATE conversation_summaries SET last_modified_time = ? WHERE conversation_id = 'sess-old'", (prev_end_dt.isoformat(),))
    con.execute("UPDATE conversation_summaries SET last_user_input_time = ? WHERE conversation_id = 'sess-new'", ((now_dt - timedelta(seconds=50)).isoformat(),))
    con.commit()
    con.close()
    os.utime(cap_img, (now_ts - 15, now_ts - 15))
    os.utime(brain_root / conv_id / "ok.png", (now_ts - 15, now_ts - 15))
    _, adj_start, _ = media_disc.resolve_session_ownership_window("sess-new", wt_repo.resolve(), brain_root / conv_id, db_file)
    assert adj_start >= prev_end_dt.timestamp() - 1.0


@pytest.mark.asyncio
async def test_v322_zip_limits_and_frontend_hardening(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify ZIP count/body/file size limits and frontend XSS, canvas release, and mobile CSS order."""
    import agy_nexus.bucket_zip as bucket_zip

    brain_root = tmp_path / "brain"
    conv_id = "zip-cap-conv"
    (brain_root / conv_id).mkdir(parents=True)
    monkeypatch.setattr(cfg, "AGY_BRAIN_DIR", brain_root)
    monkeypatch.setattr(bucket_api, "AGY_BRAIN_DIR", brain_root)

    st_cnt, _, _ = build_session_zip(conv_id, [f"f_{i}.png" for i in range(bucket_zip.MAX_ZIP_FILES + 1)], brain_dir=brain_root)
    assert st_cnt == 400

    big_png = brain_root / conv_id / "too_big.png"
    with big_png.open("wb") as fh:
        fh.truncate(bucket_zip.MAX_ZIP_FILE_BYTES + 16)
    st_sz, _, _ = build_session_zip(conv_id, ["too_big.png"], brain_dir=brain_root)
    assert st_sz == 413

    sent: list[dict[str, Any]] = []

    async def recv_big() -> dict[str, Any]:
        return {"type": "http.request", "body": b"a" * (bucket_zip.MAX_ZIP_REQ_BODY + 1), "more_body": False}

    async def snd(ev: dict[str, Any]) -> None:
        sent.append(ev)

    await bucket_zip.handle_download_zip(recv_big, snd, conv_id, ws_path="", brain_dir=brain_root)
    assert sent[0]["status"] == 413

    explorer_js = (WEB_DIR / "explorer.js").read_text(encoding="utf-8")
    assert '<pre class="raw-pre mono">${escapeHtmlSafe(' in explorer_js
    assert "handleUnauthorized" in explorer_js and "resetSensitiveState" in explorer_js

    sheet_js = (WEB_DIR / "sheet_builder.js").read_text(encoding="utf-8")
    assert "canvas.width = 0" in sheet_js and "escAttr(s.name)" in sheet_js

    ws_css = (WEB_DIR / "workspace.css").read_text(encoding="utf-8")
    assert ws_css.index(".workspace-tree-pane.zen {") < ws_css.index(".workspace-tree-pane.slim, .workspace-tree-pane.zen {")
