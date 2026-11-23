#!/usr/bin/env python3
"""
Unit and regression test suite for AGY Nexus v2.9.0:
Sequential Read-Only Governance & Cross-Repo Slot Isolation.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

import pytest

import agy_nexus
from agy_nexus.config import (
    LOCKED_RESPONSE,
    SESSION_STATE,
    mcp,
    pin_session_context,
)
from agy_nexus.hygiene import slice_file_content, slice_git_diff
from agy_nexus.routing import _session_matches_workspace
from agy_nexus.tools_media import inspect_visual_artifacts
from agy_nexus.tools_ops import get_session_tree, list_models_and_agents, manage_background_run
from agy_nexus.tools_session import load_session_into_gemini
from agy_nexus.tools_workspace import _resolve_pinned_context, inspect_git_diff


def test_v290_version_bump() -> None:
    """Verify version is bumped to 4.0.5."""
    assert agy_nexus.__version__ == "4.0.5"


def test_fastmcp_instructions_sequential_governance() -> None:
    """Verify server instructions reflect sequential read-only governance and prohibit parallel calls."""
    instructions = mcp.instructions
    assert "SEQUENTIAL READ-ONLY GOVERNANCE (1 CALL AT A TIME, UP TO 4 HOPS/TURN)" in instructions
    assert "NEVER emit parallel simultaneous MCP calls in the same step" in instructions
    assert "You MAY issue up to 4 sequential read-only calls" in instructions
    assert "HARD STOP ON MUTATIONS & DEADBOLT" in instructions
    # Legacy blanket ban string must not be present
    assert "STRICT ONE-TOOL-CALL-PER-TURN RULE: Do NOT chain a second MCP tool after a successful response" not in instructions


def test_locked_response_preserves_hard_stop() -> None:
    """Verify LOCKED_RESPONSE preserves immediate stop-and-reply guidance."""
    locked_obj = json.loads(LOCKED_RESPONSE)
    assert locked_obj["ok"] is False
    assert locked_obj["locked"] is True
    assert "STOP IMMEDIATELY AND REPLY TO THE USER NOW" in locked_obj["assistant_guidance"]


def test_pagination_hints_permit_sequential_followups() -> None:
    """Verify pagination hints permit sequential same-turn follow-ups and forbid parallel calls."""
    file_slice = slice_file_content(
        full_text="line1\nline2\nline3\nline4\nline5\nline6\n",
        clean_path="sample.py",
        per_file_cap=12,
    )
    assert file_slice["truncated"] is True
    assert "next_range_hint" in file_slice
    assert "via a sequential follow-up call if needed—never in parallel" in file_slice["next_range_hint"]
    assert "in a subsequent turn if needed (do NOT call a second tool in this turn)" not in file_slice["next_range_hint"]

    diff_slice = slice_git_diff(
        diff_out="a" * 5000,
        offset_chars=0,
        max_diff_chars=2000,
    )
    assert diff_slice["diff_truncated"] is True
    assert "pagination_hint" in diff_slice
    assert "via a sequential follow-up call if needed—never in parallel" in diff_slice["pagination_hint"]


def test_session_matches_workspace_helper() -> None:
    """Verify _session_matches_workspace correctly identifies matching vs mismatched repositories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_a = Path(tmpdir) / "repo_a"
        repo_b = Path(tmpdir) / "repo_b"
        repo_a.mkdir()
        repo_b.mkdir()

        conv_id = "test-conv-matches-ws"
        pin_session_context(
            conv_id,
            title="Repo A Work",
            workspace=str(repo_a),
            workspace_uris=[str(repo_a)],
            set_default=True,
        )

        # repo_a matches
        assert _session_matches_workspace(conv_id, repo_a) is True
        assert _session_matches_workspace(conv_id, str(repo_a)) is True

        # repo_b does NOT match
        assert _session_matches_workspace(conv_id, repo_b) is False
        assert _session_matches_workspace(conv_id, str(repo_b)) is False


def test_cross_repo_slot_isolation_in_resolve_pinned_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify _resolve_pinned_context does not clobber selected_session's active slot when reading repo_b."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_a = Path(tmpdir) / "repo_a"
        repo_b = Path(tmpdir) / "repo_b"
        repo_a.mkdir()
        repo_b.mkdir()

        monkeypatch.setattr("agy_nexus.tools_workspace._resolve_workspace_str", lambda w: str(repo_b) if "repo_b" in w or w == str(repo_b) else str(repo_a))

        conv_a = "conv-slot-test-a"
        pin_session_context(
            conv_a,
            title="Repo A Task",
            workspace=str(repo_a),
            workspace_uris=[str(repo_a)],
            set_default=True,
        )

        assert SESSION_STATE.get("selected_session") == conv_a
        assert SESSION_STATE["active_contexts"][conv_a]["workspace"] == str(repo_a)
        assert SESSION_STATE["session_workspace_map"][conv_a] == str(repo_a)

        # Call _resolve_pinned_context with explicit repo_b and NO session_identifier
        resolved_cid, resolved_ws, extra_uris = _resolve_pinned_context(
            session_identifier="",
            workspace=str(repo_b),
            tool_name="ask_workspace_readonly",
        )

        # resolved_cid must be cleared to "" to isolate repo_b from conv_a
        assert resolved_cid == ""
        assert resolved_ws == repo_b
        assert extra_uris == []

        # conv_a slot must remain completely unchanged!
        assert SESSION_STATE.get("selected_session") == conv_a
        assert SESSION_STATE["active_contexts"][conv_a]["workspace"] == str(repo_a)
        assert SESSION_STATE["session_workspace_map"][conv_a] == str(repo_a)


def test_cross_repo_slot_isolation_in_inspect_visual_artifacts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify inspect_visual_artifacts does not mutate conv_a slot when workspace=repo_b is passed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_a = Path(tmpdir) / "repo_a"
        repo_b = Path(tmpdir) / "repo_b"
        repo_a.mkdir()
        repo_b.mkdir()

        monkeypatch.setattr("agy_nexus.tools_media._resolve_workspace_str", lambda w: str(repo_b) if "repo_b" in w or w == str(repo_b) else str(repo_a))
        monkeypatch.setattr("agy_nexus.tools_media._is_strict_child", lambda p, roots: True)
        monkeypatch.setattr("agy_nexus.tools_media.is_unlocked", lambda phrase="": True)

        conv_a = "conv-vision-test-a"
        pin_session_context(
            conv_a,
            title="Vision Task A",
            workspace=str(repo_a),
            workspace_uris=[str(repo_a)],
            set_default=True,
        )

        # Calling inspect_visual_artifacts for repo_b without session_identifier
        results = inspect_visual_artifacts(
            targets="sample.png",
            session_identifier="",
            workspace=str(repo_b),
            spoken_passphrase="",
        )
        assert isinstance(results, list)

        # Ensure conv_a's workspace slot is STILL repo_a, NOT repo_b
        assert SESSION_STATE["active_contexts"][conv_a]["workspace"] == str(repo_a)
        assert SESSION_STATE["session_workspace_map"][conv_a] == str(repo_a)


def test_real_workspace_cross_repo_slot_isolation() -> None:
    """Verify slot isolation with real existing project workspaces on disk."""
    ws_nexus = Path(__file__).resolve().parents[1]
    ws_sibling = next(
        (p for p in sorted(ws_nexus.parent.iterdir()) if p.is_dir() and p != ws_nexus and not p.name.startswith(".")),
        None,
    )
    if ws_sibling is None or not ws_nexus.is_dir():
        pytest.skip("Sibling project workspace not present")

    conv_sib = "conv-real-sibling-test"
    pin_session_context(
        conv_sib,
        title="Sibling Workspace Task",
        workspace=str(ws_sibling),
        workspace_uris=[str(ws_sibling)],
        set_default=True,
    )

    resolved_cid, resolved_ws, extra_uris = _resolve_pinned_context(
        session_identifier="",
        workspace="agy-nexus-mcp",
        tool_name="ask_workspace_readonly",
    )
    assert resolved_cid == ""
    assert resolved_ws.resolve() == ws_nexus.resolve()

    # Slot must be preserved
    assert SESSION_STATE["active_contexts"][conv_sib]["workspace"] == str(ws_sibling)
    assert SESSION_STATE["session_workspace_map"][conv_sib] == str(ws_sibling)


def test_readonly_tools_guidance_strings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify read-only tools guidance strings permit sequential calls and have no STOP AND REPLY."""
    monkeypatch.setattr("agy_nexus.tools_ops.is_unlocked", lambda phrase="": True)
    # 1. get_session_tree
    tree_out = get_session_tree(include_stats=False)
    tree_data = json.loads(tree_out)
    assert "STOP AND REPLY TO USER NOW: Do NOT chain a second MCP tool" not in tree_data["assistant_guidance"]
    assert "Sequential read-only follow-up calls" in tree_data["assistant_guidance"]

    # 2. list_models_and_agents
    models_out = list_models_and_agents(include_skills=False, include_rules=False)
    models_data = json.loads(models_out)
    assert "STOP AND REPLY TO USER NOW: Do NOT chain a second MCP tool" not in models_data["assistant_guidance"]
    assert "sequential read-only follow-up call" in models_data["assistant_guidance"]

    # 3. manage_background_run actions
    bg_tree_out = manage_background_run(action="tree")
    bg_tree_data = json.loads(bg_tree_out)
    assert "STOP AND REPLY TO USER NOW" not in bg_tree_data["assistant_guidance"]
    assert "Sequential read-only follow-up calls are permitted" in bg_tree_data["assistant_guidance"]

    bg_stats_out = manage_background_run(action="stats")
    bg_stats_data = json.loads(bg_stats_out)
    assert "STOP AND REPLY TO USER NOW" not in bg_stats_data["assistant_guidance"]
    assert "Sequential read-only follow-up calls are permitted" in bg_stats_data["assistant_guidance"]

    bg_telem_out = manage_background_run(action="telemetry")
    bg_telem_data = json.loads(bg_telem_out)
    assert "STOP AND REPLY TO USER NOW" not in bg_telem_data["assistant_guidance"]
    assert "Sequential read-only follow-up calls are permitted" in bg_telem_data["assistant_guidance"]


def test_inspect_git_diff_selected_session_status_conv_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify inspect_git_diff returns selected_session_status keyed to resolved conv_id."""
    monkeypatch.setattr("agy_nexus.tools_workspace.is_unlocked", lambda phrase="": True)
    conv_id = "test-diff-conv-id"
    pin_session_context(
        conv_id,
        title="Diff Session",
        workspace=str(Path.cwd()),
        workspace_uris=[str(Path.cwd())],
        set_default=True,
    )
    res = inspect_git_diff(session_identifier=conv_id)
    data = json.loads(res)
    assert data.get("ok") is True
    assert data["selected_session_status"].get("conversation_id") == conv_id


def test_load_session_into_gemini_execution_status_workspace_sync(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify load_session_into_gemini synchronizes execution_status['workspace_path']."""
    monkeypatch.setattr("agy_nexus.tools_session.is_unlocked", lambda phrase="": True)
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()
    conv_id = "test-load-sync-conv"
    sess_dir = brain_dir / conv_id
    sess_dir.mkdir()
    (sess_dir / "task.md").write_text("# Task\n- [ ] do test\n", encoding="utf-8")
    monkeypatch.setattr("agy_nexus.tools_session.AGY_BRAIN_DIR", brain_dir)
    monkeypatch.setattr("agy_nexus.config.AGY_BRAIN_DIR", brain_dir)
    monkeypatch.setattr("agy_nexus.tools_session._resolve_session_identifier", lambda ident: conv_id)
    target_ws = str(Path.cwd().resolve())
    monkeypatch.setattr(
        "agy_nexus.tools_session.SESSION_STATE",
        {
            **SESSION_STATE,
            "session_workspace_map": {conv_id: target_ws},
        },
    )

    res = load_session_into_gemini(session_identifier=conv_id)
    data = json.loads(res)
    assert data.get("ok") is True
    assert data.get("workspace_path") == target_ws
    assert data["execution_status"].get("workspace_path") == target_ws

