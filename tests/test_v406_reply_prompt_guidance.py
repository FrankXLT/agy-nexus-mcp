"""tests/test_v406_reply_prompt_guidance.py — Enforce @Agy Nexus Mcp 1-tap FollowUp/ElicitationsGroup reply chips."""
from __future__ import annotations

import ast
import io
import json
from pathlib import Path
import sqlite3
import sys
import xml.etree.ElementTree as ET

import pytest
from starlette.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import agy_nexus
from agy_nexus import (
    config as cfg,
    handoff as handoff_mod,
    media as media_mod,
    media_discovery as mdisc_mod,
    retirement as ret_mod,
    routing as routing_mod,
    search as search_mod,
    session_status as ss_mod,
    session_tree as st_mod,
    sessions as sess_mod,
    target_resolver as tr_mod,
    tools_media as tmedia_mod,
    tools_ops as tops_mod,
    tools_session as tsession_mod,
    tools_workspace as tws_mod,
    virtual_uris as vu_mod,
    workflows as wf_mod,
    workspace as ws_mod,
)
from agy_nexus.retirement import build_suggested_actions, record_session_retirement
from agy_nexus.server import build_nexus_http_app


def _setup_sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path, Path, str, str]:
    brain_root = tmp_path / "brain"
    bg_dir = tmp_path / "bg"
    ws_dir = tmp_path / "ws"
    repo_dir = ws_dir / "projects" / "demo-chip-repo"
    db_file = tmp_path / "state.vscdb"
    cfg_dir = tmp_path / "cfg"
    (cfg_dir / "projects").mkdir(parents=True)
    bg_dir.mkdir(parents=True)
    brain_root.mkdir(parents=True)
    repo_dir.mkdir(parents=True)
    (repo_dir / "app.py").write_text("def hello():\n    return 'ok'\n", encoding="utf-8")
    con = sqlite3.connect(str(db_file))
    con.execute(
        "CREATE TABLE conversation_summaries (conversation_id TEXT PRIMARY KEY, title TEXT, preview TEXT, project_id TEXT, status TEXT, step_count INTEGER, last_modified_time TEXT, not_fully_idle INTEGER, killed INTEGER, workspace_uris TEXT, parent_conversation_id TEXT)"
    )
    con.commit()
    con.close()
    mods = (
        cfg, handoff_mod, tsession_mod, tws_mod, tops_mod, tmedia_mod, media_mod, mdisc_mod,
        sess_mod, ss_mod, st_mod, search_mod, routing_mod, tr_mod, ret_mod, vu_mod, wf_mod, ws_mod,
    )
    attrs = {
        "AGY_BRAIN_DIR": brain_root, "AGY_BG_DIR": bg_dir, "AGY_DB_FILE": db_file,
        "AGY_CONFIG_DIR": cfg_dir, "AGY_DATA_DIR": tmp_path,
        "AGY_WORKSPACE_DIR": ws_dir, "AGY_PROJECTS_DIR": ws_dir / "projects",
        "AGY_WORKBOOKS_DIR": ws_dir / "workbooks", "AGY_CONFIGURATION_DIR": ws_dir / "configuration",
        "AGY_GITLAB_DIR": ws_dir / "projects",
    }
    for mod in mods:
        for attr, val in attrs.items():
            if hasattr(mod, attr):
                monkeypatch.setattr(mod, attr, val)
    phrase = "canary reply chip open"
    monkeypatch.setattr(cfg, "PASS_HASH", cfg.normalize_phrase(phrase))
    return brain_root, bg_dir, db_file, repo_dir, phrase, "v406_secret_token_001122334455667788"


def _call_mcp(client: TestClient, secret: str, req_id: int, tool_name: str, arguments: dict) -> tuple[bytes, dict]:
    resp = client.post(
        f"/{secret}/mcp",
        json={"jsonrpc": "2.0", "id": req_id, "method": "tools/call", "params": {"name": tool_name, "arguments": arguments}},
    )
    assert resp.status_code == 200
    assert len(resp.content) < 20_480, f"{tool_name} exceeded 20 KB wire limit ({len(resp.content)}B)"
    payload = json.loads(resp.json()["result"]["content"][0]["text"])
    return resp.content, payload


def test_v406_instructions_locked_response_and_constant() -> None:
    """Verify REPLY_PROMPT_GUIDANCE, FastMCP Rule 5 XML tags, and LOCKED_RESPONSE @Agy Nexus Mcp reminder."""
    assert "STOP AND REPLY TO USER NOW" not in cfg.REPLY_PROMPT_GUIDANCE
    assert "<FollowUp" in cfg.REPLY_PROMPT_GUIDANCE and "<ElicitationsGroup" in cfg.REPLY_PROMPT_GUIDANCE
    assert "@Agy Nexus Mcp " in cfg.REPLY_PROMPT_GUIDANCE

    inst = cfg.mcp.instructions
    assert "<FollowUp" in inst and "<ElicitationsGroup" in inst and "@Agy Nexus Mcp " in inst
    assert "SEQUENTIAL READ-ONLY GOVERNANCE (1 CALL AT A TIME, UP TO 4 HOPS/TURN)" in inst

    locked = json.loads(cfg.LOCKED_RESPONSE)
    assert "STOP IMMEDIATELY AND REPLY TO THE USER NOW" in locked["assistant_guidance"]
    assert "@Agy Nexus Mcp" in locked["assistant_guidance"]


def test_v406_build_suggested_actions_xml_and_all_phases() -> None:
    """Verify all 4 lifecycle phases emit valid XML followup_xml with @Agy Nexus Mcp prefix and embedded IDs."""
    cid = "11112222-3333-4444-8555-666677778888"
    hid = "agy-nexus-mcp-47"
    tgt = 'nexus & "ui"'

    a_flight = build_suggested_actions("in_flight", target=tgt, conv_id=cid, handoff_id=hid, is_running=True)
    a_ship = build_suggested_actions("ready_to_ship", target=tgt, conv_id=cid, handoff_id=hid)
    a_run = build_suggested_actions("ready_to_run", target=tgt, conv_id=cid, handoff_id=hid)
    a_ret = build_suggested_actions("retired", target="agy-nexus-mcp", conv_id=cid, step_count=1200)

    assert a_flight["phase"] == "in_flight" and a_flight["prompt"] == "Check in on the build?"
    assert a_ship["phase"] == "ready_to_ship" and a_ship["prompt"] == f"Ship {tgt} to GitHub?"
    assert a_run["phase"] == "ready_to_run" and a_run["prompt"] == "Run these changes and update the live preview?"
    assert a_ret["phase"] == "retired" and a_ret["prompt"] == "Start next task or view session tree?"

    for idx, act in enumerate((a_flight, a_ship, a_run, a_ret)):
        assert act["options"][0]["label"] == "Yes"
        assert all(str(opt["value"]).startswith("@Agy Nexus Mcp ") for opt in act["options"])
        root = ET.fromstring(act["followup_xml"])
        if root.tag == "FollowUp":
            queries = [root.attrib["query"]]
        else:
            assert root.tag == "ElicitationsGroup"
            queries = [el.attrib["query"] for el in root.findall("Elicitation")]
            assert len(queries) >= 2
        assert all(q.startswith("@Agy Nexus Mcp ") for q in queries)
        if idx < 3:
            assert cid in queries[0] and tgt in queries[0]
        if idx in (0, 2):
            assert hid in queries[0]

    dirty = build_suggested_actions("in_flight", target="proj\x00\x07\r\n<bad>&'\"", conv_id="cid\n1", handoff_id="hid\x1f2")
    assert "\n" not in dirty["followup_xml"] and "\r" not in dirty["followup_xml"]
    assert "proj" in ET.fromstring(dirty["followup_xml"]).attrib["query"]
    null_safe = build_suggested_actions(None, target=None, conv_id=None, step_count=None, handoff_id=None)  # type: ignore[arg-type]
    assert null_safe["phase"] == "ready_to_run" and ET.fromstring(null_safe["followup_xml"]).tag == "ElicitationsGroup"


def test_v406_all_tools_emit_reply_guidance_and_stay_under_wire_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify every MCP tool embeds REPLY_PROMPT_GUIDANCE and lifecycle suggested_actions under <20 KB."""
    brain_root, _bg, db_file, repo_dir, phrase, secret = _setup_sandbox(tmp_path, monkeypatch)
    cid_ship = "aaaa1111-2222-4333-8444-555566667777"
    cid_ret = "bbbb1111-2222-4333-8444-555566667777"
    cid_run = "cccc1111-2222-4333-8444-555566667777"
    for cid in (cid_ship, cid_ret, cid_run):
        sdir = brain_root / cid
        (sdir / "scratch").mkdir(parents=True)
        (sdir / "task.md").write_text("# Task\n- [x] Verify chips\n", encoding="utf-8")
        cfg.pin_session_context(cid, title=f"Session {cid[:4]}", project_name="Demo Repo", workspace=str(repo_dir), set_default=True)
    record_session_retirement(cid_ret, brain_dir=brain_root, final_commit_sha="deadbeef")
    con = sqlite3.connect(str(db_file))
    con.execute(
        "INSERT INTO conversation_summaries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (cid_run, "Running Chip Build", "", "", "CASCADE_RUN_STATUS_RUNNING", 42, "2026-11-23T18:00:00Z", 1, 0, json.dumps([f"file://{repo_dir}"]), ""),
    )
    con.commit()
    con.close()

    from PIL import Image as PilImage
    buf = io.BytesIO()
    PilImage.new("RGB", (64, 64), (24, 96, 180)).save(buf, format="PNG")
    (brain_root / cid_ship / "scratch" / "01_preview.png").write_bytes(buf.getvalue())

    monkeypatch.setattr(ws_mod, "_collect_git_summary", lambda _p: {"branch": "main", "status_short": ""})
    monkeypatch.setattr(tsession_mod, "_collect_git_summary", lambda _p: {"branch": "main", "status_short": ""})
    monkeypatch.setattr(tws_mod, "_host_git_inspect", lambda *a, **kw: {"workspace": str(repo_dir), "branch": "main", "status_short": "", "diff_stat": "", "diff": "", "untracked_files": []})
    monkeypatch.setattr(handoff_mod, "_post_bridge", lambda _p: {"ok": True, "conversation_id": cid_ship})

    app = build_nexus_http_app(secret, cfg.get_polyglot_mcp_token(secret), cfg.get_praxis_mcp_token(secret))
    with TestClient(app) as client:
        for req_i, (tname, targs) in enumerate((
            ("unlock_sessions", {"spoken_passphrase": phrase}),
            ("list_saved_sessions", {"spoken_passphrase": phrase}),
            ("ask_workspace_readonly", {"question": "Read app.py", "file_subpath": "app.py", "workspace": str(repo_dir)}),
            ("inspect_git_diff", {"workspace_override": str(repo_dir)}),
            ("inspect_git_diff", {"workspace_override": "ALL"}),
            ("inspect_visual_artifacts", {"targets": "#01", "session_identifier": cid_ship}),
            ("get_session_tree", {"include_stats": False}),
            ("get_session_tree", {"include_stats": True}),
            ("list_models_and_agents", {"include_skills": False, "include_rules": False, "style": "json"}),
            ("list_models_and_agents", {"include_skills": False, "include_rules": False, "style": "ascii"}),
            ("manage_background_run", {"action": "tree"}),
            ("manage_background_run", {"action": "stats"}),
            ("manage_background_run", {"action": "telemetry"}),
            ("manage_background_run", {"action": "models", "style": "ascii"}),
            ("manage_background_run", {"action": "status"}),
            ("manage_background_run", {"action": "tail"}),
        ), 1):
            _, pay = _call_mcp(client, secret, req_i, tname, targs)
            assert cfg.REPLY_PROMPT_GUIDANCE in pay["assistant_guidance"], f"{tname} missing REPLY_PROMPT_GUIDANCE"

        _, stop_pay = _call_mcp(client, secret, 30, "manage_background_run", {"action": "stop"})
        assert "STOP AND REPLY TO USER NOW" in stop_pay["assistant_guidance"]

        for req_i, (cid_t, exp_phase, exp_tag) in enumerate((
            (cid_run, "in_flight", "FollowUp"),
            (cid_ship, "ready_to_ship", "ElicitationsGroup"),
            (cid_ret, "retired", "ElicitationsGroup"),
        ), 31):
            _, loaded = _call_mcp(client, secret, req_i, "load_session_into_gemini", {"session_identifier": cid_t})
            assert cfg.REPLY_PROMPT_GUIDANCE in loaded["assistant_guidance"]
            assert loaded["suggested_actions"]["phase"] == exp_phase
            assert ET.fromstring(loaded["suggested_actions"]["followup_xml"]).tag == exp_tag

        _, staged = _call_mcp(client, secret, 35, "send_handoff_and_resume", {
            "research_markdown": "# User Goal\nVerify 1-tap chips.\n\n# Workflow & Why It Matters\nKeep chips clickable.",
            "workspace_path": str(repo_dir), "resume_headless": False,
        })
        assert cfg.REPLY_PROMPT_GUIDANCE in staged["assistant_guidance"]
        assert "Do you understand the risk" in staged["assistant_guidance"]
        assert staged["handoff_id"] in staged["suggested_actions"]["followup_xml"]
        assert "@Agy Nexus Mcp " in staged["suggested_actions"]["followup_xml"]

        _, resumed = _call_mcp(client, secret, 36, "send_handoff_and_resume", {
            "research_markdown": "# User Goal\nRun headless chip verification.",
            "session_identifier": cid_ship, "workspace_path": str(repo_dir), "resume_headless": True,
        })
        assert cfg.REPLY_PROMPT_GUIDANCE in resumed["assistant_guidance"]
        assert resumed["handoff_id"] in resumed["suggested_actions"]["followup_xml"]
        assert cid_ship in resumed["suggested_actions"]["followup_xml"]

        monkeypatch.setattr(handoff_mod, "_post_bridge", lambda _p: {"ok": False, "error": "offline"})
        _, failed_res = _call_mcp(client, secret, 37, "send_handoff_and_resume", {
            "research_markdown": "# User Goal\nVerify offline fallback chip.",
            "session_identifier": cid_ship, "workspace_path": str(repo_dir), "resume_headless": True, "force_interrupt": True,
        })
        assert failed_res["suggested_actions"]["phase"] == "ready_to_run"
        assert failed_res["handoff_id"] in failed_res["suggested_actions"]["followup_xml"]


def test_v406_version_docs_and_modular_line_budgets() -> None:
    """Verify 4.2.0 version parity, preserved WORKFLOWS 1-6, and strict <=500L / <=220L budgets."""
    assert agy_nexus.__version__ == "4.2.0"
    assert 'version = "4.2.0"' in (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "## [4.2.0]" in (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()[6]
    wf_txt = (REPO_ROOT / "docs" / "WORKFLOWS.md").read_text(encoding="utf-8")
    for n in range(1, 7):
        assert f"## Workflow {n}:" in wf_txt
    assert "v4.1.0" in wf_txt and "@Agy Nexus Mcp" in wf_txt and "<FollowUp" in wf_txt
    assert (REPO_ROOT / "web" / "index.html").read_text(encoding="utf-8") == (REPO_ROOT / "web" / "v9" / "index.html").read_text(encoding="utf-8")
    assert 'CACHE_NAME = "agy-nexus-v4.2.0"' in (REPO_ROOT / "web" / "sw.js").read_text(encoding="utf-8")

    budgets = {
        "retirement.py": 220, "handoff.py": 500, "tools_media.py": 500,
        "config.py": 500, "tools_session.py": 500, "tools_workspace.py": 500, "tools_ops.py": 500,
    }
    for fname, cap in budgets.items():
        p = SRC_DIR / "agy_nexus" / fname
        lines = p.read_text(encoding="utf-8").splitlines()
        assert len(lines) <= cap, f"{fname} exceeded {cap}L ({len(lines)}L)"
        ast.parse("\n".join(lines), filename=str(p))
