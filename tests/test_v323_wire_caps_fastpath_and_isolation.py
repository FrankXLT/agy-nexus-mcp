#!/usr/bin/env python3
"""
Unit and regression test suite for AGY Nexus v3.2.3:
- Improvement 1: Praxis polyglot_map <= 18 KB cap, directory_summary & Praxis product classification
- Improvement 2: Two-Tier Surgical Fast-Path vs. Full 4-Step Dual-Review & tightened dual-review injection
- Improvement 3: pytest STATE_FILE isolation, stale test slot pruning & <= 17.5 KB get_session_tree guard
- Improvement 4: Separate MCP protocol handshakes from tools/call metrics & <= 9.5 KB tools/list budget
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import sqlite3
import time

import pytest
from starlette.testclient import TestClient

import agy_nexus
import agy_nexus.config as cfg
import agy_nexus.polyglot_index as pidx
from agy_nexus.handoff import send_handoff_and_resume
from agy_nexus.handoff_templates import (
    resolve_effective_execution_mode,
    should_inject_dual_review,
    touches_security_boundary,
)
from agy_nexus.inventory import _resolve_skill_directives
from agy_nexus.polyglot_index import polyglot_repo_map
from agy_nexus.server import build_nexus_http_app
from agy_nexus.session_tree import get_routing_telemetry
from agy_nexus.telemetry_scanner import (
    WIRE_TELEMETRY_RING,
    detect_product_name,
    get_wire_telemetry_summary,
)
from agy_nexus.tools_ops import get_session_tree
from agy_nexus.tools_praxis import polyglot_map

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src" / "agy_nexus"
WEB_DIR = PROJECT_ROOT / "web"


def test_v323_version_docs_and_modular_hygiene() -> None:
    """Verify v4.0.1 across package, docs, PWA shell, and strict <=500L/<=100L function budgets."""
    assert agy_nexus.__version__ == "4.0.1"
    assert 'version = "4.0.1"' in (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "## [4.0.1]" in (PROJECT_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    wf_doc = (PROJECT_ROOT / "docs" / "WORKFLOWS.md").read_text(encoding="utf-8")
    assert "Surgical Fast-Path" in wf_doc and "17.5 KB" in wf_doc

    sw_js = (WEB_DIR / "sw.js").read_text(encoding="utf-8")
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    assert 'CACHE_NAME = "agy-nexus-v4.0.1"' in sw_js
    assert "?v=4.0.1" in html and 'id="v9AppShell"' in html

    checked_modules = (
        "handoff_templates.py", "handoff.py", "polyglot_index.py", "telemetry_scanner.py",
        "middleware.py", "config.py", "session_tree.py", "tools_ops.py",
        "tools_praxis.py", "inventory.py", "tools_session.py", "tools_workspace.py",
        "tools_media.py", "target_resolver.py",
    )
    docstring_only_legacy_fns = {
        ("tools_ops.py", "manage_background_run"),
        ("tools_session.py", "load_session_into_gemini"),
        ("tools_workspace.py", "ask_workspace_readonly"),
        ("tools_workspace.py", "inspect_git_diff"),
    }
    for mod_name in checked_modules:
        path = SRC_DIR / mod_name
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) <= 500, f"{mod_name} exceeded 500L target ({len(lines)}L)"
        tree = ast.parse("\n".join(lines), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if (mod_name, node.name) in docstring_only_legacy_fns:
                    continue
                fn_len = node.end_lineno - node.lineno + 1
                assert fn_len <= 100, f"{mod_name}:{node.name} is {fn_len}L (>100L)"


def test_v323_polyglot_map_byte_cap_and_praxis_detection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify polyglot_map caps JSON <= 18 KB on a 150-file repo and Praxis classifies accurately."""
    ws = tmp_path / "worktrees" / "synth_150"
    idx_dir = tmp_path / "sidecar_data" / "polyglot_index"
    for mod_i in range(150):
        sub = ws / f"pkg_{mod_i % 6}"
        sub.mkdir(parents=True, exist_ok=True)
        (sub / f"mod_{mod_i:03d}.py").write_text(
            f'"""Module {mod_i} service."""\n'
            f"def handle_item_{mod_i}(val: int) -> int:\n"
            f'    """Process item {mod_i}."""\n'
            f"    return val + {mod_i}\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(pidx, "AGY_DATA_DIR", tmp_path)
    monkeypatch.setattr(pidx, "AGY_WORKSPACE_DIR", tmp_path)
    monkeypatch.setattr(pidx, "get_workspace_pillar_roots", lambda: [tmp_path])
    monkeypatch.setattr(pidx, "get_polyglot_index_dir", lambda: idx_dir)

    raw_tool_out = polyglot_map(workspace=str(ws), limit=200, force_refresh=True)
    assert len(raw_tool_out.encode("utf-8")) <= 17500
    parsed = json.loads(raw_tool_out)
    assert parsed["ok"] is True
    assert parsed["matched_files"] == 150
    assert parsed["shown_files"] < 150
    assert parsed["truncated"] is True
    assert "path_prefix=" in parsed["drilldown_hint"]
    assert sum(d["files"] for d in parsed["directory_summary"]) == 150

    focused = polyglot_repo_map(workspace=str(ws), path_prefix="pkg_0/", limit=50)
    assert focused["matched_files"] == 25
    assert focused["truncated"] is False

    # Praxis / IDE classification beats generic google / http-client UA
    assert detect_product_name("agy-praxis-mcp", "google-http-client/2.0", "polyglot_map") == "Antigravity IDE (Praxis MCP)"
    assert detect_product_name("", "Go-http-client/2.0", "praxis_handoff_inbox") == "Antigravity IDE (Praxis MCP)"
    assert detect_product_name("Antigravity", "google-api", "[rpc:initialize]", doorway="praxis") == "Antigravity IDE (Praxis MCP)"
    assert detect_product_name("", "google-http-client/2.0", "ask_workspace_readonly") == "Gemini Web / Cloud MCP"
    assert detect_product_name("", "GSA/15.1 Android", "unlock_sessions") == "Gemini Mobile"


def test_v323_surgical_fastpath_vs_full_dual_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify fast-path lifecycle applies only to compact non-security bugfixes/closeouts."""
    assert touches_security_boundary("Fix 2 non-security UI cards in explorer.js") is False
    for sec_txt in (
        "Update middleware.py LAN proxy check",
        "Harden bridge_security.py CIDR check",
        "Rotate PASS_HASH and PATH_SECRET",
        "Verify PRAXIS_MCP_TOKEN hmac check",
        "Fix deadbolt verify_passphrase handling",
        "Fix auth bypass on upload route",
    ):
        assert touches_security_boundary(sec_txt) is True

    assert resolve_effective_execution_mode("auto", "bug_or_visual_fix", "Fix padding", False, False) == "fast"
    assert resolve_effective_execution_mode("auto", "release_closeout", "Ship v3.2.3", False, False) == "fast"
    assert resolve_effective_execution_mode("auto", "bug_or_visual_fix", "Fix middleware.py", False, False) == "plan"
    assert resolve_effective_execution_mode("auto", "bug_or_visual_fix", "x" * 7000, False, False) == "plan"
    assert resolve_effective_execution_mode("auto", "feature_update", "Add charts", False, False) == "plan"

    # Tightened dual-review injection: incidental UI word 'auth' does not inject dual-review
    assert should_inject_dual_review("Adjust padding on auth badge in web/app.js", "bug_or_visual_fix") is False
    assert "dual-review" not in _resolve_skill_directives("agy-nexus-mcp", "", "Fix padding on auth label")
    assert "dual-review" in _resolve_skill_directives("agy-nexus-mcp", "", "Fix auth bypass in middleware.py")
    assert "dual-review" in _resolve_skill_directives("agy-nexus-mcp", "", "Closeout", handoff_mode="release_closeout")

    brain_dir, bg_dir = tmp_path / "brain", tmp_path / "bg"
    brain_dir.mkdir()
    bg_dir.mkdir()
    ws_repo = tmp_path / "projects" / "demo-ui"
    ws_repo.mkdir(parents=True)
    monkeypatch.setattr(cfg, "AGY_BRAIN_DIR", brain_dir)
    monkeypatch.setattr(cfg, "AGY_BG_DIR", bg_dir)
    monkeypatch.setattr(cfg, "AGY_WORKSPACE_DIR", tmp_path)
    monkeypatch.setattr(cfg, "AGY_PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(cfg, "AGY_GITLAB_DIR", tmp_path / "projects")
    monkeypatch.setattr("agy_nexus.handoff.is_unlocked", lambda p="": True)
    monkeypatch.setattr("agy_nexus.workspace.get_workspace_pillar_roots", lambda: [tmp_path / "projects"])

    fast_res = json.loads(send_handoff_and_resume(
        research_markdown="# User Goal\nFix mobile card margin in web/styles.css.",
        handoff_mode="bug_or_visual_fix",
        workspace_path=str(ws_repo),
        resume_headless=False,
    ))
    assert fast_res["execution_mode"] == "fast"
    fast_md = Path(fast_res["handoff_file"]).read_text(encoding="utf-8")
    assert "Surgical Fast-Path Lifecycle" in fast_md
    assert "Mandatory 4-Step Execution Lifecycle" not in fast_md

    sec_res = json.loads(send_handoff_and_resume(
        research_markdown="# User Goal\nFix deadbolt verify_passphrase edge case in middleware.py.",
        handoff_mode="bug_or_visual_fix",
        execution_mode="fast",
        workspace_path=str(ws_repo),
        resume_headless=False,
    ))
    sec_md = Path(sec_res["handoff_file"]).read_text(encoding="utf-8")
    assert "Mandatory 4-Step Execution Lifecycle" in sec_md
    assert "dual-review" in sec_md


def test_v323_state_isolation_slot_pruning_and_tree_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify pytest STATE_FILE isolation, stale test slot pruning, and <=17.5KB get_session_tree cap."""
    real_live_state = Path.home() / ".gemini/antigravity/sidecar_data/ag-bridge-bg/session_state.json"
    assert cfg.STATE_FILE != real_live_state
    assert str(tmp_path) in str(cfg.STATE_FILE)

    brain_dir = tmp_path / "brain"
    bg_dir = tmp_path / "bg"
    db_file = tmp_path / "conversation_summaries.db"
    real_ws = tmp_path / "real_repo"
    real_ws.mkdir()
    real_cid = "a9c8e7f6-1234-4abc-9def-0123456789ab"
    (brain_dir / real_cid).mkdir(parents=True)
    bg_dir.mkdir(parents=True)

    con = sqlite3.connect(str(db_file))
    con.execute("CREATE TABLE conversation_summaries (conversation_id TEXT PRIMARY KEY)")
    con.execute("INSERT INTO conversation_summaries VALUES (?)", (real_cid,))
    con.commit()
    con.close()

    cfg.SESSION_STATE["active_contexts"] = {
        "test-load-sync-conv": {"conversation_id": "test-load-sync-conv", "workspace": str(real_ws), "last_used_at": time.time() - 999},
        "conv-vision-test-a": {"conversation_id": "conv-vision-test-a", "workspace": "/tmp/nonexistent_dir_v323_xyz", "last_used_at": time.time()},
        "demo-session-1": {"conversation_id": "demo-session-1", "workspace": str(real_ws), "last_used_at": time.time()},
        "11111111-2222-3333-4444-555555555555": {"conversation_id": "11111111-2222-3333-4444-555555555555", "workspace": str(real_ws), "last_used_at": time.time()},
        real_cid: {"conversation_id": real_cid, "workspace": str(real_ws), "last_used_at": time.time()},
    }
    pruned = cfg.prune_stale_context_slots(brain_dir=brain_dir, db_file=db_file)
    assert pruned == 4
    assert list(cfg.SESSION_STATE["active_contexts"].keys()) == [real_cid]

    # Seed 12 valid slots + big tree to verify <= 8 slots and <= 17,500 byte compaction
    for idx in range(12):
        cid_k = f"f{idx:07x}-0000-4000-8000-00000000000{idx % 10}"
        (brain_dir / cid_k).mkdir(exist_ok=True)
        cfg.SESSION_STATE["active_contexts"][cid_k] = {
            "conversation_id": cid_k, "title": f"Session {idx}", "workspace": str(real_ws),
            "workspace_uris": [str(real_ws)] * 4, "last_used_at": time.time() - idx,
        }
    monkeypatch.setattr(cfg, "AGY_BRAIN_DIR", brain_dir)
    monkeypatch.setattr(cfg, "AGY_DB_FILE", db_file)
    rt = get_routing_telemetry()
    assert len(rt["slots"]) == 8
    assert all("workspace_uris" not in s for s in rt["slots"])

    huge_tree = "\n".join(f"  ├─ [#{i}] Long session title entry {'x' * 70}" for i in range(250))
    monkeypatch.setattr("agy_nexus.tools_ops.is_unlocked", lambda p="": True)
    monkeypatch.setattr(
        "agy_nexus.tools_ops.build_project_session_tree",
        lambda **kw: {
            "projects_count": 10, "sessions_count": 250, "projects": [{"id": i, "blob": "y" * 600} for i in range(10)],
            "routing_telemetry": rt, "backup_321": {"ok": True}, "ascii_tree": huge_tree,
        },
    )
    monkeypatch.setattr(
        "agy_nexus.tools_ops.build_nexus_stats_bundle",
        lambda **kw: {
            "period": {"key": "last_90d", "label": "Last 90 Days"},
            "ascii_mobile_report": "STATS\n" + ("S" * 4000),
            "kpis": {"window_steps": 420, "window_tokens": 120000},
            "quota_and_pools": {"recent_quota_events": list(range(10))},
        },
    )
    out_raw = get_session_tree(include_stats=True)
    assert len(out_raw.encode("utf-8")) <= 17500
    parsed_tree = json.loads(out_raw)
    assert "projects" not in parsed_tree
    assert parsed_tree["period_key"] == "last_90d"
    assert parsed_tree["totals"]["window_steps"] == 420


def test_v323_handshake_separation_and_tools_list_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify tools/list <= 9.5 KB and wire telemetry separates handshakes from tools/call."""
    bg_dir = tmp_path / "bg_wire"
    bg_dir.mkdir(parents=True)
    monkeypatch.setattr(cfg, "AGY_BG_DIR", bg_dir)
    WIRE_TELEMETRY_RING.clear()

    # Seed 2 historical '-' handshake records in ledger and verify zero-tool handshake summary
    ledger = bg_dir / "mcp_telemetry_ledger.jsonl"
    hist_hs = {"ts": "2026-11-18T10:00:00+00:00", "tool": "-", "product": "Gemini Web / Cloud MCP", "bytes": 12400, "kb": 12.11, "est_tokens": 3100, "under_20kb_budget": True, "duration_ms": 5.0}
    ledger.write_text(json.dumps(hist_hs) + "\n" + json.dumps(hist_hs) + "\n", encoding="utf-8")
    WIRE_TELEMETRY_RING.extend([hist_hs, hist_hs])
    hs_only = get_wire_telemetry_summary(bg_dir, limit=25)
    assert hs_only["total_recorded_calls"] == 0 and hs_only["by_product"] == {}
    assert hs_only["protocol_handshakes"]["calls"] == 2

    secret = "v323_unit_test_secret_token_more_than_32_chars"
    praxis_tok = cfg.get_praxis_mcp_token(secret)
    app = build_nexus_http_app(secret, cfg.get_polyglot_mcp_token(secret), praxis_tok)

    with TestClient(app) as client:
        r_init = client.post(
            f"/{secret}/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "Gemini", "version": "1"}}},
        )
        assert r_init.status_code == 200
        r_tl = client.post(f"/{secret}/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert r_tl.status_code == 200
        assert len(r_tl.content) <= 9500, f"tools/list too large: {len(r_tl.content)} bytes"
        assert len(r_tl.json()["result"]["tools"]) == 11

        # Reject spoofed userinfo Origin targeting localhost@evil.com
        r_spoof = client.post(
            f"/praxis/{praxis_tok}/mcp",
            headers={"Origin": "https://localhost:1@evil.com"},
            json={"jsonrpc": "2.0", "id": 9, "method": "tools/list"},
        )
        assert r_spoof.status_code == 403

        r_praxis = client.post(
            f"/praxis/{praxis_tok}/mcp",
            headers={"User-Agent": "google-http-client/2.0"},
            json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "polyglot_outline", "arguments": {"file_subpath": "src/agy_nexus/__init__.py", "workspace": str(PROJECT_ROOT)}}},
        )
        assert r_praxis.status_code == 200
        r_nexus = client.post(
            f"/{secret}/mcp",
            headers={"User-Agent": "google-http-client/2.0"},
            json={"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "lock_bridge", "arguments": {}}},
        )
        assert r_nexus.status_code == 200

    summary = get_wire_telemetry_summary(bg_dir, limit=25)
    assert summary["total_recorded_calls"] == 2
    assert "Antigravity IDE (Praxis MCP)" in summary["by_product"]
    assert "Gemini Web / Cloud MCP" in summary["by_product"]
    assert summary["protocol_handshakes"]["calls"] == 4
    assert summary["protocol_handshakes"]["tools_list_kb"] == round(len(r_tl.content) / 1024.0, 2)
    assert summary["protocol_handshakes"]["tools_list_kb"] <= 9.5


def test_v323_security_classifier_negation_and_resume_staged_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify negation window cannot bypass middleware/deadbolt checks and RESUME_STAGED keeps fast-path."""
    assert touches_security_boundary("Not touching css, modifying middleware.py") is True
    assert should_inject_dual_review("Not touching css, modifying middleware.py", "bug_or_visual_fix") is True
    assert touches_security_boundary("Fix XSS and path traversal in bucket_api.py") is True
    assert should_inject_dual_review("Fix XSS and path traversal in bucket_api.py", "bug_or_visual_fix") is True

    brain_dir, bg_dir = tmp_path / "brain", tmp_path / "bg"
    brain_dir.mkdir()
    bg_dir.mkdir()
    ws_repo = tmp_path / "projects" / "demo-ui"
    ws_repo.mkdir(parents=True)
    monkeypatch.setattr(cfg, "AGY_BRAIN_DIR", brain_dir)
    monkeypatch.setattr(cfg, "AGY_BG_DIR", bg_dir)
    monkeypatch.setattr(cfg, "AGY_WORKSPACE_DIR", tmp_path)
    monkeypatch.setattr(cfg, "AGY_PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(cfg, "AGY_GITLAB_DIR", tmp_path / "projects")
    monkeypatch.setattr("agy_nexus.handoff.is_unlocked", lambda p="": True)
    monkeypatch.setattr("agy_nexus.workspace.get_workspace_pillar_roots", lambda: [tmp_path / "projects"])

    staged = json.loads(send_handoff_and_resume(
        research_markdown="# User Goal\nFix button alignment in web/app.js.",
        handoff_mode="bug_or_visual_fix",
        workspace_path=str(ws_repo),
        resume_headless=False,
    ))
    assert staged["execution_mode"] == "fast"
    captured_bridge: list[dict[str, object]] = []
    monkeypatch.setattr("agy_nexus.handoff._post_bridge", lambda payload: captured_bridge.append(payload) or {"ok": True, "conversation_id": "a" * 8 + "-1111-4222-8333-" + "b" * 12})
    resumed = json.loads(send_handoff_and_resume(
        research_markdown="RESUME_STAGED",
        handoff_id=staged["handoff_id"],
        resume_headless=True,
    ))
    assert resumed["execution_mode"] == "fast"
    assert captured_bridge and "Surgical Fast-Path Lifecycle" in str(captured_bridge[0].get("prompt", ""))

