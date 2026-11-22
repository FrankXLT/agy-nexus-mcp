#!/usr/bin/env python3
"""tests/test_v325_efficiency_and_hygiene.py — AGY-Nexus v3.2.5 Efficiency & Modular Hygiene Suite."""
from __future__ import annotations

import ast
import io
import json
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any

from PIL import Image as PilImage
import pytest
from starlette.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import agy_nexus
from agy_nexus import (
    bucket_api,
    bucket_scanner,
    code_health,
    config as cfg,
    handoff as handoff_mod,
    handoff_queue,
    media as media_mod,
    media_discovery as mdisc_mod,
    polyglot_outline,
    retirement as ret_mod,
    routing as routing_mod,
    search as search_mod,
    session_status as ss_mod,
    session_tree as st_mod,
    sessions as sess_mod,
    target_resolver as tr_mod,
    tools_media as tm_mod,
    tools_ops as to_mod,
    tools_session as ts_mod,
    tools_workspace as tw_mod,
    uploads as up_mod,
    virtual_uris as vu_mod,
    workflows as wf_mod,
    workspace as ws_mod,
)
from agy_nexus.handoff_templates import resolve_execution_mode_with_reason
from agy_nexus.media_discovery import read_image_dimensions_fast
from agy_nexus.retirement import is_session_retired
from agy_nexus.server import build_nexus_http_app


def _setup_isolated_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, Path, str, str]:
    """Isolate brain, bg, workspace, data, DB, and passphrase to tmp_path."""
    data_dir = tmp_path / "data"
    brain_root = data_dir / "brain"
    bg_dir = tmp_path / "bg"
    ws_dir = tmp_path / "ws"
    proj_dir = ws_dir / "projects"
    db_file = data_dir / "conversation_summaries.db"
    for d in (brain_root, bg_dir, proj_dir, data_dir / "worktrees", ws_dir / "workbooks", ws_dir / "configuration"):
        d.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_file))
    con.execute(
        "CREATE TABLE conversation_summaries (conversation_id TEXT PRIMARY KEY, title TEXT, project_id TEXT, status TEXT, step_count INTEGER, last_modified_time TEXT, not_fully_idle INTEGER, killed INTEGER, workspace_uris TEXT)"
    )
    con.commit()
    con.close()

    attrs = {
        "AGY_DATA_DIR": data_dir, "AGY_BRAIN_DIR": brain_root, "AGY_BG_DIR": bg_dir,
        "AGY_DB_FILE": db_file, "AGY_WORKSPACE_DIR": ws_dir, "AGY_PROJECTS_DIR": proj_dir,
        "AGY_WORKBOOKS_DIR": ws_dir / "workbooks", "AGY_CONFIGURATION_DIR": ws_dir / "configuration",
        "AGY_GITLAB_DIR": proj_dir, "AGY_CONFIG_DIR": tmp_path / "cfg",
    }
    all_mods = (
        cfg, tm_mod, ts_mod, tw_mod, to_mod, ws_mod, vu_mod, media_mod, mdisc_mod,
        sess_mod, ss_mod, st_mod, search_mod, routing_mod, tr_mod, handoff_mod,
        ret_mod, bucket_api, bucket_scanner, up_mod, wf_mod,
    )
    for mod in all_mods:
        for k, v in attrs.items():
            if hasattr(mod, k):
                monkeypatch.setattr(mod, k, v)

    phrase = "canary v325 vault open"
    monkeypatch.setattr(cfg, "PASS_HASH", cfg.normalize_phrase(phrase))
    monkeypatch.setenv("AG_BRIDGE_PUBLIC_URL", "https://nexus-v325.example.invalid")
    return brain_root, bg_dir, proj_dir, phrase, "v325_test_secret_token_32_characters"


def test_v325_cloud_visual_fastpath_and_header_dimensions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify <2ms header dimension parsing, bounded JPEG guard, and Cloud MCP metadata-only visual fast path."""
    brain_root, _bg, proj_dir, phrase, secret = _setup_isolated_env(tmp_path, monkeypatch)
    cid = "11112222-3333-4444-5555-666677778888"
    bdir = brain_root / cid / "scratch" / "uploads_20261120_100000"
    bdir.mkdir(parents=True)
    (proj_dir / "demo-vis").mkdir(parents=True)

    specs = [("01_shot.png", "PNG", (2560, 1440)), ("02_shot.webp", "WEBP", (1280, 720)), ("03_shot.gif", "GIF", (800, 600)), ("04_shot.jpg", "JPEG", (1904, 971))]
    for idx, (fname, fmt, sz) in enumerate(specs, 1):
        buf = io.BytesIO()
        PilImage.new("RGB", sz, (20 * idx, 60, 140)).save(buf, format=fmt)
        fpath = bdir / fname
        fpath.write_bytes(buf.getvalue())
        assert read_image_dimensions_fast(fpath) == sz

    bad_jpg = tmp_path / "malformed.jpg"
    bad_jpg.write_bytes(b"\xff\xd8" + (b"\x11" * 400_000))
    t_bad0 = time.perf_counter()
    assert read_image_dimensions_fast(bad_jpg) is None
    assert (time.perf_counter() - t_bad0) < 0.05

    app = build_nexus_http_app(secret, cfg.get_polyglot_mcp_token(secret), cfg.get_praxis_mcp_token(secret))
    with TestClient(app) as client:
        r_cloud = client.post(
            f"/{secret}/mcp",
            headers={"User-Agent": "Google-HTTP-Client/1.1"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "inspect_visual_artifacts", "arguments": {"targets": "#01", "session_identifier": cid, "spoken_passphrase": phrase}}},
        )
        assert r_cloud.status_code == 200 and len(r_cloud.content) < 4096
        c_blocks = r_cloud.json()["result"]["content"]
        assert len(c_blocks) == 1 and c_blocks[0]["type"] == "text"
        c_meta = json.loads(c_blocks[0]["text"])
        assert c_meta["cloud_fast_path"] is True and c_meta["returned_images"] == 0
        assert c_meta["items"][0]["original_px"] == "2560x1440" and "/web/media/" in c_meta["items"][0]["signed_url"]

        r_opt = client.post(
            f"/{secret}/mcp",
            headers={"User-Agent": "Google-HTTP-Client/1.1"},
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "inspect_visual_artifacts", "arguments": {"targets": "#01", "session_identifier": cid, "include_thumbnails": True, "spoken_passphrase": phrase}}},
        )
        opt_blocks = r_opt.json()["result"]["content"]
        assert json.loads(opt_blocks[0]["text"])["returned_images"] >= 1
        assert any(b.get("type") == "image" and b.get("mimeType") == "image/webp" for b in opt_blocks[1:])

        r_loc = client.post(
            f"/{secret}/mcp",
            headers={"User-Agent": "testclient"},
            json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "inspect_visual_artifacts", "arguments": {"targets": "#04", "session_identifier": cid, "spoken_passphrase": phrase}}},
        )
        loc_blocks = r_loc.json()["result"]["content"]
        assert json.loads(loc_blocks[0]["text"])["returned_images"] >= 1
        assert any(b.get("type") == "image" and b.get("mimeType") == "image/webp" for b in loc_blocks[1:])


def test_v325_outer_wire_caps_and_tools_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify <=18.5KB inner / <=20KB HTTP wire caps (including 'repositories' drift & single include_files) and compact tools/list."""
    brain_root, _bg, proj_dir, phrase, secret = _setup_isolated_env(tmp_path, monkeypatch)
    cid = "22223333-4444-5555-6666-777788889999"
    sess_dir = brain_root / cid
    (sess_dir / ".system_generated" / "logs").mkdir(parents=True)
    repo_dir = proj_dir / "wire-cap-repo"
    repo_dir.mkdir(parents=True)

    fnames: list[str] = []
    for i in range(8):
        fn = f"mod_{i}.py"
        fnames.append(fn)
        body = f'def fn_{i}():\n    s = "quote_\\"_{i}"\n' + ('    x = "abc\\ndef"\n' * 650)
        (repo_dir / fn).write_text(body[:12000], encoding="utf-8")
    for doc_name in ("task.md", "implementation_plan.md", "walkthrough.md"):
        (sess_dir / doc_name).write_text('# Doc\n"quoted line"\n' * 350, encoding="utf-8")
    (sess_dir / ".system_generated" / "logs" / "transcript_full.jsonl").write_text(
        json.dumps({"step_index": 1, "type": "PLANNER_RESPONSE", "content": 'Line "quote"\n' * 900}) + "\n", encoding="utf-8",
    )
    (sess_dir / ".system_generated" / "logs" / "transcript.jsonl").write_text(
        "\n".join(json.dumps({"step_index": i, "type": "TOOL", "content": '"q"\n' * 300}) for i in range(45)) + "\n", encoding="utf-8",
    )
    for i in range(6):
        (sess_dir / f"cap_{i:02d}.png").write_bytes(b"\x89PNG\r\n\x1a\n" + (b"\x00" * 32))

    drift_repos = [
        {"repo": f"r-{i}", "branch": "main", "status_short": ("M f.py\n" * 40), "diff_stat": (" f.py | 120 +\n" * 20), "untracked_files": [f"u_{j}.py" for j in range(15)]}
        for i in range(25)
    ]
    monkeypatch.setattr(tw_mod, "inspect_multi_repo_drift", lambda **_kw: {"ok": True, "repositories": drift_repos, "repos_scanned": 25})
    monkeypatch.setattr(tw_mod, "_host_git_inspect", lambda *_a, **_kw: {"branch": "main", "status_short": "M big.py\n" * 60, "diff_stat": " big.py | 900 +\n" * 20, "diff": ('+ "escaped_quote"\n' * 1200), "untracked_files": [f"tmp_{i}.txt" for i in range(90)]})
    monkeypatch.setattr(ts_mod, "_collect_git_summary", lambda _wp: {"branch": "main", "status_short": 'M "q.py"\n' * 80, "diff_stat": " q.py | 99 +\n" * 40, "untracked_files": [f"u_{i}.py" for i in range(60)]})

    app = build_nexus_http_app(secret, cfg.get_polyglot_mcp_token(secret), cfg.get_praxis_mcp_token(secret))
    with TestClient(app) as client:
        rt_list = client.post(f"/{secret}/mcp", json={"jsonrpc": "2.0", "id": 10, "method": "tools/list", "params": {}})
        assert rt_list.status_code == 200 and len(rt_list.content) <= 8600
        tools = rt_list.json()["result"]["tools"]
        assert len(tools) == 11
        for t in tools:
            assert t.get("_meta") != {"fastmcp": {"tags": []}}
            assert t.get("title") != str(t.get("name", "")).replace("_", " ").title()
        vis_t = next(t for t in tools if t["name"] == "inspect_visual_artifacts")
        assert "strip binary" in vis_t["description"].lower() and "7-day" in vis_t["description"].lower()

        calls = [
            ("ask_workspace_readonly", {"question": "Read 8 files", "file_subpath": ",".join(fnames), "workspace": str(repo_dir), "spoken_passphrase": phrase}),
            ("inspect_git_diff", {"workspace_override": "ALL", "spoken_passphrase": phrase}),
            ("inspect_git_diff", {"workspace_override": str(repo_dir), "spoken_passphrase": phrase}),
            ("load_session_into_gemini", {"session_identifier": cid, "include_files": "mod_0.py", "spoken_passphrase": phrase}),
            ("manage_background_run", {"action": "tail", "tail_lines": 50, "spoken_passphrase": phrase}),
            ("list_models_and_agents", {"skill_scope_filter": "all", "spoken_passphrase": phrase}),
        ]
        cfg.pin_session_context(cid, workspace=str(repo_dir), set_default=True)
        for idx, (tname, targs) in enumerate(calls, 11):
            resp = client.post(f"/{secret}/mcp", json={"jsonrpc": "2.0", "id": idx, "method": "tools/call", "params": {"name": tname, "arguments": targs}})
            assert resp.status_code == 200 and len(resp.content) <= 20480, f"{tname} HTTP={len(resp.content)}"
            inner_txt = resp.json()["result"]["content"][0]["text"]
            assert len(inner_txt.encode("utf-8")) <= 18500, f"{tname} raw={len(inner_txt.encode('utf-8'))}"
            assert len(json.dumps(inner_txt, ensure_ascii=False).encode("utf-8")) <= 20480


def test_v325_plan_coercion_and_deferred_closeout_retirement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify multi-feature/new_project plan coercion, deferred closeout retirement, mutex safety, and RESUME_STAGED continuity."""
    brain_root, bg_dir, proj_dir, phrase, _sec = _setup_isolated_env(tmp_path, monkeypatch)
    ws_repo = proj_dir / "coercion-repo"
    ws_repo.mkdir(parents=True)

    assert resolve_execution_mode_with_reason("fast", "new_project", "# Goal\nCreate app", False, False)[:2] == ("plan", True)
    deliv_4 = "# Goal\n1. One\n2. Two\n3. Three\n4. Four\n"
    assert resolve_execution_mode_with_reason("fast", "feature_update", deliv_4, False, False)[:2] == ("plan", True)
    assert resolve_execution_mode_with_reason("fast", "feature_update", "x" * 2300, False, False)[:2] == ("plan", True)
    assert resolve_execution_mode_with_reason("auto", "feature_update", "Compact tweak", True, True)[:2] == ("fast", False)
    assert resolve_execution_mode_with_reason("auto", "bug_or_visual_fix", "Fix auth bypass in upload", True, True)[:2] == ("plan", False)

    res_np = json.loads(handoff_mod.send_handoff_and_resume(research_markdown="# User Goal\nScaffold service", handoff_mode="new_project", execution_mode="fast", workspace_path=str(ws_repo), resume_headless=False, spoken_passphrase=phrase))
    assert res_np["execution_mode"] == "plan" and res_np["coerced_from_fast"] is True

    res_feat = json.loads(handoff_mod.send_handoff_and_resume(research_markdown=deliv_4, handoff_mode="feature_update", execution_mode="fast", workspace_path=str(ws_repo), resume_headless=False, spoken_passphrase=phrase))
    assert res_feat["execution_mode"] == "plan" and res_feat["coerced_from_fast"] is True
    assert "Mandatory 4-Step Execution Lifecycle" in Path(res_feat["handoff_file"]).read_text(encoding="utf-8")

    # Headless wakeup failure preserves retire_after_closeout=True and retry RESUME_STAGED preserves it
    cid_h = "33334444-5555-6666-7777-888899990000"
    (brain_root / cid_h).mkdir(parents=True)
    cfg.pin_session_context(cid_h, workspace=str(ws_repo), set_default=True)
    monkeypatch.setattr(handoff_mod, "_post_bridge", lambda _p: {"ok": False, "error": "bridge offline"})
    res_fail = json.loads(handoff_mod.send_handoff_and_resume(research_markdown="# User Goal\nCloseout & release", handoff_mode="release_closeout", session_identifier=cid_h, workspace_path=str(ws_repo), resume_headless=True, retire_session=True, allow_chained_publish=True, spoken_passphrase=phrase))
    assert res_fail["retire_after_closeout"] is True and res_fail["ticket_status"] == "STAGED"
    assert not is_session_retired(cid_h, brain_root)

    sent_prompts: list[dict[str, Any]] = []
    monkeypatch.setattr(handoff_mod, "_post_bridge", lambda payload: (sent_prompts.append(payload), {"ok": True, "conversation_id": cid_h})[1])
    res_close = json.loads(handoff_mod.send_handoff_and_resume(research_markdown="RESUME_STAGED", handoff_id=res_fail["handoff_id"], session_identifier=cid_h, workspace_path=str(ws_repo), resume_headless=True, allow_chained_publish=True, force_interrupt=True, spoken_passphrase=phrase))
    assert res_close["retire_after_closeout"] is True and not is_session_retired(cid_h, brain_root)
    idx_doc = json.loads((bg_dir / "staged_handoffs" / "index.json").read_text(encoding="utf-8"))
    t_match = next(t for t in idx_doc["tickets"] if t["handoff_id"] == res_close["handoff_id"])
    assert t_match.get("retire_after_closeout") is True
    assert json.loads((bg_dir / f"{res_close['job_id']}.json").read_text(encoding="utf-8")).get("retire_after_closeout") is True
    assert "record_session_retirement" in sent_prompts[0]["prompt"] and "RETIRED.json" in sent_prompts[0]["prompt"]

    # Non-headless retire_session=True writes RETIRED.json immediately and keeps new STAGED ticket STAGED
    cid_imm = "44445555-6666-7777-8888-999900001111"
    (brain_root / cid_imm).mkdir(parents=True)
    res_imm = json.loads(handoff_mod.send_handoff_and_resume(research_markdown="# User Goal\nRetire now", handoff_mode="release_closeout", session_identifier=cid_imm, workspace_path=str(ws_repo), resume_headless=False, retire_session=True, spoken_passphrase=phrase))
    assert is_session_retired(cid_imm, brain_root) is True
    idx_doc2 = json.loads((bg_dir / "staged_handoffs" / "index.json").read_text(encoding="utf-8"))
    imm_tk = next(t for t in idx_doc2["tickets"] if t["handoff_id"] == res_imm["handoff_id"])
    assert imm_tk["status"] == "STAGED"


def test_v325_100pct_500l_compliance_and_compat_exports() -> None:
    """Verify 100% <=500L compliance globally, <=100L functions on v3.2.5 modules, YAML redaction, version parity, and compat exports."""
    exempt_legacy_fns = {
        ("workspace.py", "_resolve_and_read_files"), ("search.py", "_search_workspaces_and_history"),
        ("tools_session.py", "load_session_into_gemini"), ("tools_ops.py", "manage_background_run"),
        ("tools_workspace.py", "inspect_git_diff"), ("tools_workspace.py", "ask_workspace_readonly"),
    }
    v325_fn_checked = {
        "polyglot_lang_outliners.py", "polyglot_outline.py", "handoff_queue_store.py",
        "handoff_queue.py", "bucket_scanner.py", "bucket_api.py", "hygiene.py",
        "tools_media.py", "media_discovery.py", "middleware.py", "config.py",
        "handoff_templates.py", "retirement.py", "handoff.py", "tools_ops.py",
        "tools_session.py", "tools_workspace.py", "telemetry_scanner.py", "search.py",
    }
    for folder, pat in ((SRC_DIR / "agy_nexus", "*.py"), (REPO_ROOT / "host_bridge", "*.py"), (REPO_ROOT / "web", "*.js")):
        for fpath in sorted(folder.glob(pat)):
            lines = fpath.read_text(encoding="utf-8").splitlines()
            assert len(lines) <= 500, f"{fpath.name} exceeded 500 lines ({len(lines)}L)"
            if fpath.suffix == ".py" and fpath.name in v325_fn_checked:
                tree = ast.parse("\n".join(lines), filename=str(fpath))
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (fpath.name, node.name) not in exempt_legacy_fns:
                        assert (node.end_lineno - node.lineno + 1) <= 100, f"{fpath.name}:{node.name} > 100L"

    hyg = code_health.get_modular_hygiene_summary(SRC_DIR / "agy_nexus")
    assert hyg["warning_501_650"] == 0 and hyg["violations_over_650"] == 0 and not hyg["syntax_errors"]

    _s, fmt_y, _sym = polyglot_outline.outline_yaml(["secrets:", "  - name: ghp_realTokenShouldRedact999", "  - name: public_label"])
    assert "ghp_realTokenShouldRedact999" not in "\n".join(fmt_y) and "[REDACTED]" in "\n".join(fmt_y)

    assert agy_nexus.__version__ == "4.0.1"
    assert 'version = "4.0.1"' in (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "?v=4.0.1" in (REPO_ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert 'CACHE_NAME = "agy-nexus-v4.0.1"' in (REPO_ROOT / "web" / "sw.js").read_text(encoding="utf-8")

    for fn in ("outline_markdown", "outline_json", "outline_yaml", "_outline_html_css", "_clean_one_liner"):
        assert callable(getattr(polyglot_outline, fn))
    for sym in ("VALID_HANDOFF_STATES", "STATE_DISPLAY_LABELS", "canonicalize_handoff_id", "normalize_repo_slug", "slugify_token"):
        assert hasattr(handoff_queue, sym)
    for fn in ("rewrite_markdown_media_links", "scan_session_uploads", "scan_session_artifacts"):
        assert callable(getattr(bucket_api, fn))
