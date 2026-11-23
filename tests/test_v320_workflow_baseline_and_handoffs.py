#!/usr/bin/env python3
"""
Unit and regression test suite for AGY Nexus v3.2.0:
- Plain-Language Workflow Baseline Discovery & Wire Formatting
- Handoff Quality Evaluator & Soft-Lint Advisories
- Cross-Session User Intent Extraction
- Ticket Auto-Reconciliation on RETIRED.json
- Unresolved Skill Path Filtering in Interjection Directives
- Modular Line Budget & 3.2.0 Version Consistency
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import pytest

import agy_nexus
from agy_nexus.handoff_queue import (
    record_handoff_ticket,
    reconcile_completed_tickets,
)
from agy_nexus.inventory import build_interjection_directive
from agy_nexus.retirement import (
    extract_prior_session_baton,
    record_session_retirement,
)
from agy_nexus.workflow_baseline import (
    discover_project_workflows,
    evaluate_handoff_quality,
    extract_user_intent_from_handoff,
    format_workflow_baseline_for_wire,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src" / "agy_nexus"
WEB_DIR = PROJECT_ROOT / "web"


def test_v320_version_consistency() -> None:
    """Verify package version is 4.0.3 across pyproject.toml, package, index.html, and sw.js."""
    assert agy_nexus.__version__ == "4.0.3"

    pyproject_text = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "4.0.3"' in pyproject_text

    index_html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    assert "?v=4.0.3" in index_html
    assert 'href="/web/v9/v9_shell.css?v=4.0.3"' in index_html

    sw_js = (WEB_DIR / "sw.js").read_text(encoding="utf-8")
    assert 'CACHE_NAME = "agy-nexus-v4.0.3"' in sw_js
    assert '"/web/v9/v9_shell.css?v=4.0.3"' in sw_js


def test_discover_project_workflows_on_repo(tmp_path: Path) -> None:
    """Verify discover_project_workflows finds docs/WORKFLOWS.md and README.md."""
    # Test on project root
    wf = discover_project_workflows(str(PROJECT_ROOT))
    assert wf["found"] is True
    assert wf["source_file"] == "docs/WORKFLOWS.md"
    assert len(wf["workflow_titles"]) >= 4
    assert any("Voice" in t or "Inspection" in t for t in wf["workflow_titles"])

    # Test wire formatting
    wire_text = format_workflow_baseline_for_wire(wf, max_chars=3000)
    assert "**Established Workflows (`docs/WORKFLOWS.md`)**:" in wire_text
    assert len(wire_text) <= 3000

    # Test fallback to README.md
    empty_repo = tmp_path / "empty_repo"
    empty_repo.mkdir()
    (empty_repo / "README.md").write_text("# Test Repo\n\n## Workflows\n### Quickstart Workflow\nRun the test.", encoding="utf-8")
    wf_fallback = discover_project_workflows(str(empty_repo))
    assert wf_fallback["found"] is True
    assert wf_fallback["source_file"] == "README.md"
    assert len(wf_fallback["workflow_titles"]) >= 1


def test_evaluate_handoff_quality_advisories() -> None:
    """Verify evaluate_handoff_quality identifies missing user goals and soft-lints."""
    # Bad handoff: only file directives and line numbers
    bad_handoff = "Go modify src/foo.py lines 45-50 and web/bar.js line 12. Fix the error."
    bad_res = evaluate_handoff_quality(bad_handoff, is_closeout=False)
    assert bad_res["has_goal_or_why"] is False
    assert bad_res["has_workflow"] is False
    assert bad_res["quality_score"] < 0.6
    assert "Handoff Quality Advisory" in bad_res["advisory"]
    assert "User Goal & Why" in bad_res["advisory"]

    # Good handoff: structured user goal and workflow
    good_handoff = (
        "# User Goal\n"
        "The user wants to view real-time battery voltage on mobile.\n\n"
        "# Workflow & Why It Matters\n"
        "When checking device status while walking around, the user needs immediate visual confirmation.\n\n"
        "## Technical Plan\n"
        "Update the sensor subscriber in `sensor.py`."
    )
    good_res = evaluate_handoff_quality(good_handoff, is_closeout=False)
    assert good_res["has_goal_or_why"] is True
    assert good_res["has_workflow"] is True
    assert good_res["quality_score"] >= 0.9
    assert good_res["advisory"] == ""

    # Closeout handoff: exempt from workflow advisory
    closeout_handoff = "Clean up, commit changes, tag v3.2.0, and retire session."
    closeout_res = evaluate_handoff_quality(closeout_handoff, is_closeout=True)
    assert closeout_res["advisory"] == ""


def test_extract_user_intent_from_handoff() -> None:
    """Verify extract_user_intent_from_handoff extracts goal and workflow sections."""
    handoff_text = (
        "<!-- BEGIN_USER_HANDOFF_BODY -->\n"
        "# Chemistry Data-Fusion Sprint\n\n"
        "## User Goal & Overview\n"
        "Allow chemical researchers to render 2D molecular SVGs directly from SMILES strings in chat.\n\n"
        "## Why It Matters\n"
        "Researchers need visual verification without opening desktop ChemDraw.\n\n"
        "## File Edits\n"
        "Modify smiles.py.\n"
        "<!-- END_USER_HANDOFF_BODY -->"
    )
    extracted = extract_user_intent_from_handoff(handoff_text, max_chars=800)
    assert "User Goal" in extracted or "Chemistry Data-Fusion" in extracted
    assert "render 2D molecular SVGs" in extracted
    assert len(extracted) <= 800


def test_reconcile_completed_tickets_with_retired_session(tmp_path: Path) -> None:
    """Verify reconcile_completed_tickets transitions tickets with RETIRED.json to COMPLETED."""
    bg_dir = tmp_path / "bg_dir"
    bg_dir.mkdir()
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()

    # Create a staged ticket
    conv_id = "test-conv-12345"
    ticket = record_handoff_ticket(
        bg_dir,
        full_markdown="# Test Handoff",
        chars_written=150,
        repo_slug="test-repo",
        title="Test Task",
        project_id="proj-1",
        project_name="Test Project",
        workspace_path="/tmp/test",
        target_conversation_id=conv_id,
        initial_status="IN_WORK",
    )
    assert ticket["status"] == "IN_WORK"
    hid = ticket["handoff_id"]

    # Reconcile before retirement (should remain IN_WORK since no db and no RETIRED.json)
    reconciled_early = reconcile_completed_tickets(bg_dir, db_file=tmp_path / "nonexistent.db", brain_dir=brain_dir)
    assert hid not in reconciled_early

    # Record retirement
    record_session_retirement(conv_id, brain_dir=brain_dir, final_commit_sha="fedcba654321")
    assert (brain_dir / conv_id / "RETIRED.json").is_file()

    # Reconcile after retirement (should mark ticket COMPLETED)
    reconciled_after = reconcile_completed_tickets(bg_dir, db_file=tmp_path / "nonexistent.db", brain_dir=brain_dir)
    assert hid in reconciled_after

    # Verify index status
    idx_data = json.loads((bg_dir / "staged_handoffs" / "index.json").read_text(encoding="utf-8"))
    reconciled_ticket = next(t for t in idx_data["tickets"] if t["handoff_id"] == hid)
    assert reconciled_ticket["status"] == "COMPLETED"


def test_prior_session_baton_with_intent(tmp_path: Path) -> None:
    """Verify extract_prior_session_baton includes user goal & workflow from prior session."""
    conv_id = "prior-conv-67890"
    sess_dir = tmp_path / conv_id
    sess_scratch = sess_dir / "scratch"
    sess_scratch.mkdir(parents=True)

    # Write task.md
    (sess_dir / "task.md").write_text("# Tasks\n- [x] Initial design\n- [ ] Execution\n", encoding="utf-8")

    # Write prior handoff
    handoff_text = (
        "# Prior User Goal\n"
        "Build the 4-surface Overwatch Dashboard.\n\n"
        "## Workflow\n"
        "Allow developers to monitor quotas on mobile foldables.\n"
    )
    (sess_scratch / "gemini_research_handoff.md").write_text(handoff_text, encoding="utf-8")

    baton = extract_prior_session_baton(conv_id, brain_dir=tmp_path)
    assert f"Prior Session Baton ({conv_id})" in baton
    assert "- **Prior Task State**:" in baton
    assert "- **Prior User Goal & Workflow Context**:" in baton
    assert "Overwatch Dashboard" in baton


def test_unresolved_skill_path_filtering() -> None:
    """Verify build_interjection_directive does not instruct view_file on (unresolved: ...) skills."""
    directive, meta = build_interjection_directive(
        activate_skills="agy-nexus-stats, non-existent-skill-xyz",
        target_agent_role="flash-auditor",
        customization_edit_scope="none",
        research_markdown="Test prompt",
        workspace_str=str(PROJECT_ROOT),
        config_dir=Path.home() / ".gemini/config",
        data_dir=Path.home() / ".gemini/antigravity",
        gitlab_dir=Path.home() / "gitlab",
    )
    # The non-existent skill should NOT have a "Read (unresolved: ...) via view_file" instruction
    assert "(unresolved: non-existent-skill-xyz) via `view_file`" not in directive
    # It should still note active skill context without broken view_file command
    assert "non-existent-skill-xyz" in directive


def test_v320_modular_hygiene_and_line_ceilings() -> None:
    """Verify line ceilings and function sizes across v3.2.0 modules."""
    files_to_check = {
        SRC_DIR / "workflow_baseline.py": 500,
        SRC_DIR / "handoff.py": 500,
        SRC_DIR / "handoff_queue.py": 550,
        SRC_DIR / "inventory.py": 500,
        SRC_DIR / "retirement.py": 250,
        SRC_DIR / "config.py": 500,
        SRC_DIR / "tools_session.py": 500,
    }

    for path, max_lines in files_to_check.items():
        assert path.exists(), f"File {path} does not exist"
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        assert line_count <= max_lines, (
            f"{path.name} exceeds budget: {line_count} lines (budget <= {max_lines})"
        )

    # Check function length in handoff.py (send_handoff_and_resume <= 95 lines)
    tree = ast.parse((SRC_DIR / "handoff.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            length = node.end_lineno - node.lineno + 1
            if node.name == "send_handoff_and_resume":
                assert length <= 95, f"send_handoff_and_resume is {length} lines (budget <= 95)"
            assert length <= 100, f"Function {node.name} exceeds 100L hard max: {length} lines"
