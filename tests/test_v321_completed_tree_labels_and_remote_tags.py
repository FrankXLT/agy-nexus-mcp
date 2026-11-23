#!/usr/bin/env python3
"""
Unit and regression test suite for AGY Nexus v3.2.1:
- [✓ COMPLETED] vs [⊘ SUPERSEDED] ticket label rendering in ASCII session tree
- Historical closed-ticket (COMPLETED + SUPERSEDED) bounding per project in _attach_handoffs_to_groups
- (+N older completed) summary rendering when historical closed tickets are truncated
- Highest semantic version selection across /releases/latest and /tags in _fetch_remote_version()
- 3.2.1 version consistency and <= 500L modular hygiene
"""
from __future__ import annotations

import ast
import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import urllib.request
import pytest

import agy_nexus
from agy_nexus.code_health import _fetch_remote_version, compare_versions
from agy_nexus.handoff_queue import record_handoff_ticket
from agy_nexus.session_tree import (
    _attach_handoffs_to_groups,
    build_project_session_tree,
    render_ascii_session_tree,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src" / "agy_nexus"
WEB_DIR = PROJECT_ROOT / "web"


def test_v321_version_consistency() -> None:
    """Verify package version is 4.0.7 across pyproject.toml, package, index.html, and sw.js."""
    assert agy_nexus.__version__ == "4.0.7"

    pyproject_text = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "4.0.7"' in pyproject_text

    index_html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    assert "?v=4.0.7" in index_html
    assert 'href="/web/v9/v9_shell.css?v=4.0.7"' in index_html

    sw_js = (WEB_DIR / "sw.js").read_text(encoding="utf-8")
    assert 'CACHE_NAME = "agy-nexus-v4.0.7"' in sw_js
    assert '"/web/v9/v9_shell.css?v=4.0.7"' in sw_js


def test_render_ascii_session_tree_completed_label() -> None:
    """Verify render_ascii_session_tree renders [✓ COMPLETED] and never [⊘ SUPERSEDED] for COMPLETED tickets."""
    projects_list = [
        {
            "project_id": "ws:test-repo",
            "project_name": "Test Repo",
            "project_index": 1,
            "shared_repo": False,
            "staged_count": 1,
            "in_work_handoff_count": 1,
            "completed_count": 1,
            "superseded_count": 1,
            "workspaces": ["/home/dev/workspaces/test-repo"],
            "staged_handoffs": [
                {
                    "handoff_id": "test-repo-01",
                    "sequence": 1,
                    "repo_slug": "test-repo",
                    "title": "Staged Sprint Ticket",
                    "status": "STAGED",
                    "execution_mode": "plan",
                    "handoff_mode": "feature_update",
                    "relative_age": "5m ago",
                    "claimed_by_conversation_id": "",
                    "target_conversation_id": "",
                },
                {
                    "handoff_id": "test-repo-02",
                    "sequence": 2,
                    "repo_slug": "test-repo",
                    "title": "Active Sprint Ticket",
                    "status": "IN_WORK",
                    "execution_mode": "fast",
                    "handoff_mode": "bug_or_visual_fix",
                    "relative_age": "2m ago",
                    "claimed_by_conversation_id": "conv-1234",
                },
                {
                    "handoff_id": "test-repo-03",
                    "sequence": 3,
                    "repo_slug": "test-repo",
                    "title": "Finished Sprint Ticket",
                    "status": "COMPLETED",
                    "execution_mode": "plan",
                    "handoff_mode": "release_closeout",
                    "relative_age": "1h ago",
                    "claimed_by_conversation_id": "conv-5678",
                },
                {
                    "handoff_id": "test-repo-04",
                    "sequence": 4,
                    "repo_slug": "test-repo",
                    "title": "Superseded Ticket",
                    "status": "SUPERSEDED",
                    "superseded_by": "test-repo-05",
                    "execution_mode": "plan",
                    "handoff_mode": "feature_update",
                    "relative_age": "2h ago",
                },
            ],
            "sessions": [
                {
                    "index": "1",
                    "title": "Active Coding Session",
                    "conversation_id": "conv-1234-uuid",
                    "workspace_path": "/home/dev/workspaces/test-repo",
                    "status_badge": "[● RUNNING]",
                    "mode": "MAIN WRITER",
                    "step_count": 42,
                    "relative_age": "1m ago",
                }
            ],
        }
    ]
    routing = {"ttl_remaining_min": 25.0, "active_slots": 1, "pinned_calls": 3}
    backup = {"short_sha": "abc1234", "status_label": "3-2-1 VERIFIED", "bundle_size_kb": 12, "age": "10m ago"}

    tree_str = render_ascii_session_tree(projects_list, routing, backup)

    # Assertions for all 4 distinct states
    assert "[HANDOFF test-repo-01] Staged Sprint Ticket" in tree_str
    assert "[◈ STAGED · UNCLAIMED]" in tree_str
    assert "[HANDOFF test-repo-02] Active Sprint Ticket" in tree_str
    assert "[▶ IN-WORK]" in tree_str
    assert "[HANDOFF test-repo-03] Finished Sprint Ticket" in tree_str
    assert "[✓ COMPLETED]" in tree_str
    assert "[HANDOFF test-repo-04] Superseded Ticket" in tree_str
    assert "[⊘ SUPERSEDED -> test-repo-05]" in tree_str

    # Invariant: COMPLETED ticket must NEVER contain superseded text
    lines = tree_str.split("\n")
    completed_handoff_idx = next(i for i, line in enumerate(lines) if "Finished Sprint Ticket" in line)
    assert "[✓ COMPLETED]" in lines[completed_handoff_idx + 1]
    assert "SUPERSEDED" not in lines[completed_handoff_idx + 1]


def test_attach_handoffs_to_groups_closed_ticket_bounding(tmp_path: Path) -> None:
    """Verify _attach_handoffs_to_groups keeps 100% active tickets, caps closed at 4, and counts accurately."""
    bg_dir = tmp_path / "bg_dir"
    ws = "/home/dev/workspaces/open-agentic-workbench"
    ws_path = Path(ws)

    # Create 1 STAGED, 1 IN_WORK, 6 COMPLETED, 2 SUPERSEDED tickets
    record_handoff_ticket(
        bg_dir,
        workspace_path=str(ws_path),
        repo_slug="open-agentic-workbench",
        title="Active Staged Ticket",
        full_markdown="# User Goal\nBuild feature",
        chars_written=50,
    )
    t_in_work = record_handoff_ticket(
        bg_dir,
        workspace_path=str(ws_path),
        repo_slug="open-agentic-workbench",
        title="Active In-Work Ticket",
        full_markdown="# User Goal\nIn work",
        chars_written=50,
    )
    # Update status to IN_WORK
    from agy_nexus.handoff_queue import mark_ticket_status
    mark_ticket_status(bg_dir, t_in_work["handoff_id"], "IN_WORK", conversation_id="conv-inwork")

    # Add 6 completed tickets
    for i in range(1, 7):
        t_c = record_handoff_ticket(
            bg_dir,
            workspace_path=str(ws_path),
            repo_slug="open-agentic-workbench",
            title=f"Completed Ticket {i}",
            full_markdown=f"# User Goal\nDone {i}",
            chars_written=50,
        )
        mark_ticket_status(bg_dir, t_c["handoff_id"], "COMPLETED", conversation_id=f"conv-c-{i}")

    # Add 2 superseded tickets
    for i in range(1, 3):
        t_s = record_handoff_ticket(
            bg_dir,
            workspace_path=str(ws_path),
            repo_slug="open-agentic-workbench",
            title=f"Superseded Ticket {i}",
            full_markdown=f"# User Goal\nSuper {i}",
            chars_written=50,
        )
        mark_ticket_status(bg_dir, t_s["handoff_id"], "SUPERSEDED")

    grouped: dict[str, dict] = {}
    projects_map = {
        "p-oaw": {
            "name": "Open Agentic Workbench",
            "workspace_paths": [str(ws_path)],
        }
    }

    _attach_handoffs_to_groups(grouped, projects_map, bg_dir, active_only=False, pf_clean="")

    pg = grouped.get("p-oaw")
    assert pg is not None
    # Verify counts reflect full totals
    assert pg["staged_count"] == 1
    assert pg["in_work_handoff_count"] == 1
    assert pg["completed_count"] == 6
    assert pg["superseded_count"] == 2

    # Verify staged_handoffs contains all active tickets + at most 4 closed tickets
    staged_handoffs = pg["staged_handoffs"]
    active_in_staged = [h for h in staged_handoffs if h["status"] in ("STAGED", "IN_WORK")]
    closed_in_staged = [h for h in staged_handoffs if h["status"] in ("COMPLETED", "SUPERSEDED")]

    assert len(active_in_staged) == 2, "100% of active tickets (STAGED + IN_WORK) must be visible"
    assert len(closed_in_staged) == 4, "Historical closed tickets must be bounded at 4"
    assert len(staged_handoffs) == 6

    # Verify render_ascii_session_tree displays the (+N older completed) note
    pg["sessions"] = []
    tree_str = render_ascii_session_tree([pg], {}, {})
    # 6 completed total - 4 completed shown = 2 older completed
    assert "(+2 older completed)" in tree_str


def test_fetch_remote_version_highest_semver() -> None:
    """Verify _fetch_remote_version compares highest semver across /releases/latest and /tags."""
    # Case A: GitHub release is older (v2.7.0) but tag is newer (v3.2.0)
    def mock_urlopen_release_older(req, timeout=2.0):
        url = req.full_url
        if "releases/latest" in url:
            data = json.dumps({"tag_name": "v2.7.0", "name": "v2.7.0"}).encode("utf-8")
        else:
            data = json.dumps([
                {"name": "v3.2.0"},
                {"name": "v3.1.0"},
                {"name": "v2.7.0"},
            ]).encode("utf-8")
        resp = MagicMock()
        resp.read.return_value = data
        resp.__enter__.return_value = resp
        return resp

    with patch.object(urllib.request, "urlopen", side_effect=mock_urlopen_release_older):
        ver = _fetch_remote_version()
        assert ver == "v3.2.0", f"Expected v3.2.0 (highest semver from tags), got {ver}"

    # Case B: GitHub release is newer (v3.3.0) than tags (v3.2.0)
    def mock_urlopen_release_newer(req, timeout=2.0):
        url = req.full_url
        if "releases/latest" in url:
            data = json.dumps({"tag_name": "v3.3.0", "name": "v3.3.0"}).encode("utf-8")
        else:
            data = json.dumps([{"name": "v3.2.0"}]).encode("utf-8")
        resp = MagicMock()
        resp.read.return_value = data
        resp.__enter__.return_value = resp
        return resp

    with patch.object(urllib.request, "urlopen", side_effect=mock_urlopen_release_newer):
        ver = _fetch_remote_version()
        assert ver == "v3.3.0", f"Expected v3.3.0 (highest semver from release), got {ver}"

    # Case C: releases/latest returns 404/error, tags succeeds
    def mock_urlopen_tags_only(req, timeout=2.0):
        url = req.full_url
        if "releases/latest" in url:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, io.BytesIO(b""))
        data = json.dumps([{"name": "v3.2.1"}]).encode("utf-8")
        resp = MagicMock()
        resp.read.return_value = data
        resp.__enter__.return_value = resp
        return resp

    with patch.object(urllib.request, "urlopen", side_effect=mock_urlopen_tags_only):
        ver = _fetch_remote_version()
        assert ver == "v3.2.1"

    # Case D: Both fail
    with patch.object(urllib.request, "urlopen", side_effect=urllib.error.URLError("Connection refused")):
        ver = _fetch_remote_version()
        assert ver is None


def test_compare_versions_with_matched_tag() -> None:
    """Verify compare_versions reports up_to_date when remote tag matches installed version."""
    res = compare_versions(installed="3.2.0", remote="v3.2.0")
    assert res["status"] == "up_to_date"
    assert "Up to Date" in res["status_label"]

    res_staged = compare_versions(installed="3.2.1", remote="v3.2.0")
    assert res_staged["status"] == "staged_locally"
    assert "Staged Locally (v3.2.1 > v3.2.0)" in res_staged["status_label"]


def test_v321_modular_hygiene_and_line_ceilings() -> None:
    """Verify line ceilings and function sizes across modified modules."""
    files_to_check = [
        SRC_DIR / "session_tree.py",
        SRC_DIR / "code_health.py",
    ]
    for f in files_to_check:
        lines = f.read_text(encoding="utf-8").splitlines()
        line_count = len(lines)
        assert line_count <= 500, f"{f.name} exceeds 500 lines ({line_count} lines)"

        tree = ast.parse("\n".join(lines), filename=str(f))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_len = node.end_lineno - node.lineno + 1 if hasattr(node, "end_lineno") else 0
                assert fn_len <= 100, f"Function {node.name} in {f.name} is {fn_len} lines (exceeds 100)"
