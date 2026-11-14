#!/usr/bin/env python3
"""Regression tests for agy-praxis-mcp doorway & repo-prefixed incremental handoff queue (v2.8.0)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

PKG_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PKG_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import agy_nexus.config as cfg
import agy_nexus.handoff as handoff_mod
from agy_nexus.handoff import send_handoff_and_resume
from agy_nexus.routing import _resolve_session_identifier
from agy_nexus.session_tree import build_project_session_tree
from agy_nexus.stats_series import build_series_and_project_hierarchy
from agy_nexus.tools_praxis import (
    praxis_claim_handoff,
    praxis_handoff_inbox,
    praxis_mcp,
    praxis_update_handoff,
)
from agy_nexus.workspace import _resolve_and_read_files


def test_repo_prefixed_incremental_queue_and_supersede() -> None:
    assert praxis_mcp.name == "agy-praxis-mcp"
    phrase = "Praxis Queue 2026!"
    orig_hash = cfg.PASS_HASH
    orig_bg = cfg.AGY_BG_DIR
    orig_brain = cfg.AGY_BRAIN_DIR
    cfg.PASS_HASH = hashlib.sha256(b"praxisqueue2026").hexdigest()

    with tempfile.TemporaryDirectory() as tmp_root_str:
        tmp_root = Path(tmp_root_str)
        cfg.AGY_BG_DIR = tmp_root / "bg"
        cfg.AGY_BRAIN_DIR = tmp_root / "brain"
        cfg.AGY_BG_DIR.mkdir(parents=True, exist_ok=True)
        cfg.AGY_BRAIN_DIR.mkdir(parents=True, exist_ok=True)
        try:
            # 1. Stage two distinct topics for quiet-ui-skills (no session ID -> brand-new chats!)
            r1 = json.loads(
                send_handoff_and_resume(
                    research_markdown="# 4-Surface Perceptual Heatmap\n\nImplement OKLCH multi-hue sequential ramp.",
                    repo_hint="quiet-ui-skills",
                    resume_headless=False,
                    spoken_passphrase=phrase,
                )
            )
            assert r1["ok"] is True
            assert r1["handoff_id"] == "quiet-ui-skills-01"
            assert r1["ticket_status"] == "STAGED"

            r2 = json.loads(
                send_handoff_and_resume(
                    research_markdown="# Hierarchical Tree Handoff Rows\n\nAdd staged/in-work rows under project cards.",
                    repo_hint="quiet-ui-skills",
                    resume_headless=False,
                    spoken_passphrase=phrase,
                )
            )
            assert r2["ok"] is True
            assert r2["handoff_id"] == "quiet-ui-skills-02"
            assert r2["ticket_status"] == "STAGED"
            # Verify neither file clobbered the other on disk
            assert Path(r1["handoff_file"]).exists() and Path(r2["handoff_file"]).exists()
            assert Path(r1["handoff_file"]) != Path(r2["handoff_file"])
            assert "OKLCH multi-hue" in Path(r1["handoff_file"]).read_text(encoding="utf-8")
            assert "Hierarchical Tree" in Path(r2["handoff_file"]).read_text(encoding="utf-8")

            # 2. Independent counter per repo slug
            r_other = json.loads(
                send_handoff_and_resume(
                    research_markdown="# OAW Core State Machine\n\nRefactor worker queue.",
                    repo_hint="oaw-core",
                    resume_headless=False,
                    spoken_passphrase=phrase,
                )
            )
            assert r_other["handoff_id"] == "oaw-core-01"

            # 3. Re-staging the SAME repo + topic while unclaimed auto-supersedes quiet-ui-skills-01!
            r3 = json.loads(
                send_handoff_and_resume(
                    research_markdown="# 4-Surface Perceptual Heatmap\n\nUpdated spec with Dark Paper gold peak.",
                    repo_hint="quiet-ui-skills",
                    resume_headless=False,
                    spoken_passphrase=phrase,
                )
            )
            assert r3["handoff_id"] == "quiet-ui-skills-03"
            assert r3["superseded_ids"] == ["quiet-ui-skills-01"]

            inbox = json.loads(praxis_handoff_inbox(workspace="/home/dev/workspaces/quiet-ui-skills", include_superseded=True))
            by_id = {t["handoff_id"]: t for t in inbox["tickets"]}
            assert by_id["quiet-ui-skills-01"]["status"] == "SUPERSEDED"
            assert by_id["quiet-ui-skills-01"]["superseded_by"] == "quiet-ui-skills-03"
            assert by_id["quiet-ui-skills-02"]["status"] == "STAGED"
            assert by_id["quiet-ui-skills-03"]["status"] == "STAGED"
            assert "oaw-core-01" not in by_id

            # Claiming a SUPERSEDED ticket without force=True must fail cleanly
            sup_claim = json.loads(praxis_claim_handoff(handoff_id="quiet-ui-skills-01", workspace="/home/dev/workspaces/quiet-ui-skills"))
            assert sup_claim["ok"] is False and sup_claim["status"] == "SUPERSEDED"
        finally:
            cfg.PASS_HASH = orig_hash
            cfg.AGY_BG_DIR = orig_bg
            cfg.AGY_BRAIN_DIR = orig_brain


def test_ide_disambiguation_claim_and_cross_repo_resume_isolation() -> None:
    phrase = "Praxis Claim 2026!"
    orig_hash = cfg.PASS_HASH
    orig_bg = cfg.AGY_BG_DIR
    orig_brain = cfg.AGY_BRAIN_DIR
    orig_post = handoff_mod._post_bridge
    cfg.PASS_HASH = hashlib.sha256(b"praxisclaim2026").hexdigest()

    with tempfile.TemporaryDirectory() as tmp_root_str:
        tmp_root = Path(tmp_root_str)
        cfg.AGY_BG_DIR = tmp_root / "bg"
        cfg.AGY_BRAIN_DIR = tmp_root / "brain"
        cfg.AGY_BG_DIR.mkdir(parents=True, exist_ok=True)
        cfg.AGY_BRAIN_DIR.mkdir(parents=True, exist_ok=True)
        other_cid = "88888888-1111-2222-3333-444444444444"
        (cfg.AGY_BRAIN_DIR / other_cid).mkdir(parents=True, exist_ok=True)
        cfg.SESSION_STATE["session_workspace_map"][other_cid] = "/home/dev/workspaces/unrelated-service"
        cfg.SESSION_STATE["session_title_map"][other_cid] = "Unrelated Service Audit"
        try:
            send_handoff_and_resume(
                research_markdown="# Spec Alpha\n\nAlpha acceptance criteria.",
                repo_hint="quiet-ui-skills",
                resume_headless=False,
                spoken_passphrase=phrase,
            )
            send_handoff_and_resume(
                research_markdown="# Spec Beta\n\nBeta acceptance criteria.",
                repo_hint="quiet-ui-skills",
                resume_headless=False,
                spoken_passphrase=phrase,
            )

            # 1. Cross-repo RESUME_STAGED isolation (both implicit and explicit handoff_id)
            cross_res = json.loads(
                send_handoff_and_resume(
                    research_markdown="RESUME_STAGED",
                    session_identifier=other_cid,
                    resume_headless=False,
                    spoken_passphrase=phrase,
                )
            )
            assert cross_res["ok"] is False and cross_res["status"] == "NO_STAGED_HANDOFF_FOR_REPO"

            cross_explicit = json.loads(
                send_handoff_and_resume(
                    research_markdown="RESUME_STAGED:quiet-ui-skills-01",
                    session_identifier=other_cid,
                    resume_headless=False,
                    spoken_passphrase=phrase,
                )
            )
            assert cross_explicit["ok"] is False and cross_explicit["status"] == "NO_STAGED_HANDOFF_FOR_REPO"

            # 2. Ambiguous claim when 2 unclaimed tickets exist for the same workspace and no handoff_id is given
            ambig = json.loads(praxis_claim_handoff(workspace="/home/dev/workspaces/quiet-ui-skills"))
            assert ambig["ok"] is False
            assert ambig["status"] == "AMBIGUOUS_MULTIPLE_STAGED"
            assert {c["handoff_id"] for c in ambig["candidates"]} == {"quiet-ui-skills-01", "quiet-ui-skills-02"}

            # 3. Explicit claim by handoff_id binds new IDE conversation_id and unwraps clean spec markdown
            new_ide_cid = "aaaa1111-2222-3333-4444-555555555555"
            (cfg.AGY_BRAIN_DIR / new_ide_cid).mkdir(parents=True, exist_ok=True)
            claimed_1 = json.loads(
                praxis_claim_handoff(
                    handoff_id="quiet-ui-skills-01",
                    workspace="/home/dev/workspaces/quiet-ui-skills",
                    conversation_id=new_ide_cid,
                )
            )
            assert claimed_1["ok"] is True
            assert claimed_1["status"] == "CLAIMED"
            assert claimed_1["ticket"]["status"] == "IN_WORK"
            assert claimed_1["ticket"]["claimed_by_conversation_id"] == new_ide_cid
            assert claimed_1["specification_markdown"].startswith("# Spec Alpha")
            assert "Mandatory 4-Step" not in claimed_1["specification_markdown"]

            # IN_WORK tickets cannot be superseded via praxis_update_handoff
            bad_sup = json.loads(praxis_update_handoff("quiet-ui-skills-01", status="SUPERSEDED"))
            assert bad_sup["ok"] is False

            # 4. _resolve_session_identifier resolves 'quiet-ui-skills-01' directly to new_ide_cid!
            resolved_cid = _resolve_session_identifier("quiet-ui-skills-01")
            assert resolved_cid == new_ide_cid

            # 5. Now only 1 unclaimed STAGED ticket remains for quiet-ui-skills -> auto-claim succeeds!
            second_ide_cid = "bbbb1111-2222-3333-4444-555555555555"
            claimed_2 = json.loads(
                praxis_claim_handoff(
                    workspace="/home/dev/workspaces/quiet-ui-skills",
                    conversation_id=second_ide_cid,
                )
            )
            assert claimed_2["ok"] is True
            assert claimed_2["handoff_id"] == "quiet-ui-skills-02"
            assert claimed_2["specification_markdown"].startswith("# Spec Beta")

            # 6. Mark quiet-ui-skills-01 COMPLETED via praxis_update_handoff, and verify re-claim without force=True is blocked
            upd = json.loads(praxis_update_handoff("quiet-ui-skills-01", status="COMPLETED", notes="Shipped in PR #42"))
            assert upd["ok"] is True
            assert upd["ticket"]["status"] == "COMPLETED"
            reclaim_done = json.loads(praxis_claim_handoff(handoff_id="quiet-ui-skills-01", conversation_id=second_ide_cid))
            assert reclaim_done["ok"] is False and reclaim_done["status"] == "ALREADY_COMPLETED"

            # 7. Virtual URI praxis:handoffs works via workspace resolver
            quiet_ws_dir = tmp_root / "quiet-ui-skills"
            quiet_ws_dir.mkdir(parents=True, exist_ok=True)
            v_res = _resolve_and_read_files("praxis:handoffs", ws=quiet_ws_dir, session_dir=None)
            assert "error" not in v_res and "quiet-ui-skills-02" in v_res.get("content", "")
        finally:
            cfg.SESSION_STATE["session_workspace_map"].pop(other_cid, None)
            cfg.SESSION_STATE["session_title_map"].pop(other_cid, None)
            shutil.rmtree(cfg.AGY_BRAIN_DIR, ignore_errors=True)
            handoff_mod._post_bridge = orig_post
            cfg.PASS_HASH = orig_hash
            cfg.AGY_BG_DIR = orig_bg
            cfg.AGY_BRAIN_DIR = orig_brain


def test_dashboard_hierarchy_tree_includes_zero_session_staged_handoffs() -> None:
    phrase = "Hierarchy Tree 2026!"
    orig_hash = cfg.PASS_HASH
    orig_bg = cfg.AGY_BG_DIR
    orig_brain = cfg.AGY_BRAIN_DIR
    cfg.PASS_HASH = hashlib.sha256(b"hierarchytree2026").hexdigest()

    with tempfile.TemporaryDirectory() as tmp_root_str:
        tmp_root = Path(tmp_root_str)
        cfg.AGY_BG_DIR = tmp_root / "bg"
        cfg.AGY_BRAIN_DIR = tmp_root / "brain"
        cfg.AGY_BG_DIR.mkdir(parents=True, exist_ok=True)
        cfg.AGY_BRAIN_DIR.mkdir(parents=True, exist_ok=True)
        try:
            send_handoff_and_resume(
                research_markdown="# Brand New Repo Spec\n\nZero prior IDE sessions exist yet.",
                repo_hint="brand-new-widget-repo",
                resume_headless=False,
                spoken_passphrase=phrase,
            )
            tree = build_project_session_tree(limit=20)
            proj_names = {p["project_name"]: p for p in tree["projects"]}
            assert "brand-new-widget-repo" in proj_names
            new_proj = proj_names["brand-new-widget-repo"]
            assert new_proj["staged_count"] == 1
            assert new_proj["staged_handoffs"][0]["handoff_id"] == "brand-new-widget-repo-01"
            assert "[HANDOFF brand-new-widget-repo-01]" in tree["ascii_tree"]

            series_bundle = build_series_and_project_hierarchy(
                period_key="today",
                trimmed_days=["2026-11-13"],
                today_iso="2026-11-13",
                now_hour=17,
                s1_tot_steps={},
                s1_tot_toks={},
                s1_mod_steps={},
                s1_mod_toks={},
                s1_sub_steps={},
                s1_sub_toks={},
                s1_ws_steps={},
                all_ws_list=[],
                subagent_list=[],
                root_sess_stats={},
                db_convs={},
                projects_map={},
                tree_bundle=tree,
            )
            ph = series_bundle["project_hierarchy"]
            all_h_projs = list(ph["top_projects"]) + list(ph["idle_projects"])
            by_name = {p["project_name"]: p for p in all_h_projs}
            assert "brand-new-widget-repo" in by_name
            assert by_name["brand-new-widget-repo"]["staged_count"] == 1
        finally:
            cfg.PASS_HASH = orig_hash
            cfg.AGY_BG_DIR = orig_bg
            cfg.AGY_BRAIN_DIR = orig_brain


if __name__ == "__main__":
    test_repo_prefixed_incremental_queue_and_supersede()
    test_ide_disambiguation_claim_and_cross_repo_resume_isolation()
    test_dashboard_hierarchy_tree_includes_zero_session_staged_handoffs()
    print("[✓] All agy-praxis-mcp & repo-prefixed handoff queue tests PASSED!")
