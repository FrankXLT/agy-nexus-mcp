#!/usr/bin/env python3
"""v3.2.2 Final Polish regression tests — Strict Most-Recent-First Tree & Frontend Recency Pills."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import time

import agy_nexus.bucket_api as bucket_api
import agy_nexus.config as cfg
import agy_nexus.media_discovery as md
import agy_nexus.session_status as session_status
import agy_nexus.session_tree as session_tree
import agy_nexus.sessions as sessions
from agy_nexus.handoff_queue import record_handoff_ticket

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _iso_utc(ts: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _patch_env(monkeypatch, tmp_path: Path) -> tuple[Path, Path, Path]:
    db_path = tmp_path / "conversation_summaries.db"
    brain_dir = tmp_path / "brain"
    bg_dir = tmp_path / "ag-bridge-bg"
    cfg_dir = tmp_path / "config"
    presence_dir = tmp_path / "presence"
    for d in (brain_dir, bg_dir, cfg_dir / "projects", presence_dir):
        d.mkdir(parents=True, exist_ok=True)
    for mod in (cfg, sessions, session_tree, session_status, bucket_api):
        for attr, val in (
            ("AGY_DB_FILE", db_path),
            ("AGY_BRAIN_DIR", brain_dir),
            ("AGY_BG_DIR", bg_dir),
            ("AGY_CONFIG_DIR", cfg_dir),
            ("AGY_PRESENCE_DIR", presence_dir),
        ):
            if hasattr(mod, attr):
                monkeypatch.setattr(mod, attr, val)
    fresh_state = {
        k: ({} if isinstance(v, dict) else (set() if isinstance(v, set) else v))
        for k, v in cfg.SESSION_STATE.items()
    }
    fresh_state.update({
        "selected_session": "", "selected_session_id": "", "selected_workspace": "",
        "active_contexts": {}, "session_index_map": {}, "session_workspace_map": {},
        "session_workspace_uris_map": {}, "session_project_map": {}, "session_title_map": {},
    })
    for mod in (cfg, sessions, session_tree, session_status, bucket_api):
        if hasattr(mod, "SESSION_STATE"):
            monkeypatch.setattr(mod, "SESSION_STATE", fresh_state)
    return db_path, brain_dir, cfg_dir / "projects"


def _create_db(db_path: Path, rows: list[tuple]) -> None:
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            "CREATE TABLE conversation_summaries ("
            "conversation_id TEXT PRIMARY KEY, title TEXT, preview TEXT, step_count INTEGER, "
            "last_modified_time TEXT, workspace_uris TEXT, status TEXT, not_fully_idle INTEGER, "
            "killed INTEGER, parent_conversation_id TEXT, project_id TEXT, last_user_input_time TEXT DEFAULT '')"
        )
        con.executemany(
            "INSERT INTO conversation_summaries ("
            "conversation_id, title, preview, step_count, last_modified_time, "
            "workspace_uris, status, not_fully_idle, killed, parent_conversation_id, project_id"
            ") VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
        con.commit()
    finally:
        con.close()


def _write_project(proj_dir: Path, pid: str, name: str, ws_path: str) -> None:
    payload = {
        "id": pid,
        "name": name,
        "projectResources": {"resources": [{"folderUri": f"file://{ws_path}"}]},
    }
    (proj_dir / f"{pid}.json").write_text(json.dumps(payload), encoding="utf-8")


def _seed_brain_file(brain_dir: Path, cid: str, filename: str, mtime: float, text: str = "{}\n") -> None:
    sdir = brain_dir / cid
    sdir.mkdir(parents=True, exist_ok=True)
    target = sdir / filename
    target.write_text(text, encoding="utf-8")
    os.utime(target, (mtime, mtime))
    os.utime(sdir, (mtime, mtime))


def test_iso_nanosecond_timestamp_normalization():
    ts_nano = md.parse_iso_epoch("2026-11-18T05:30:12.123456789Z")
    ts_hepta = md.parse_iso_epoch("2026-11-18T05:30:12.1234567+00:00")
    ts_sentinel = md.parse_iso_epoch("0001-01-01 00:00:00+00:00")
    assert ts_nano > 1_700_000_000
    assert abs(ts_nano - ts_hepta) < 1e-6
    assert ts_sentinel == 0.0


def test_older_pinned_running_does_not_beat_newer_unpinned_session(monkeypatch, tmp_path):
    db_path, brain_dir, proj_dir = _patch_env(monkeypatch, tmp_path)
    now = time.time()
    pid = "11111111-1111-4111-8111-111111111111"
    ws = str(tmp_path / "repos" / "quiet-ui-demo")
    _write_project(proj_dir, pid, "Quiet UI Demo", ws)
    old_ts, new_ts = now - 86400, now - 1800
    cid_old = "aaaaaaaa-0000-4000-8000-000000000001"
    cid_new = "bbbbbbbb-0000-4000-8000-000000000002"
    _create_db(db_path, [
        (cid_old, "Phase 0 Stale Running", "", 420, _iso_utc(old_ts), json.dumps([ws]), "RUNNING", 1, 0, "", pid),
        (cid_new, "Gate 4.1 Fresh Idle", "", 48, _iso_utc(new_ts), json.dumps([ws]), "IDLE", 0, 0, "", pid),
    ])
    _seed_brain_file(brain_dir, cid_old, "task.md", old_ts, "# old\n")
    _seed_brain_file(brain_dir, cid_new, "task.md", new_ts, "# new\n")
    sessions.SESSION_STATE["selected_session"] = cid_old
    sessions.SESSION_STATE["active_contexts"] = {"primary": {"conversation_id": cid_old, "conv_id": cid_old}}

    listed = sessions._list_saved_sessions_internal(limit=10)
    assert [s["conversation_id"] for s in listed] == [cid_new, cid_old]
    assert [s["index"] for s in listed] == ["1", "2"]

    tree = session_tree.build_project_session_tree(bg_dir=tmp_path / "ag-bridge-bg")
    assert len(tree["projects"]) == 1
    proj_sessions = tree["projects"][0]["sessions"]
    assert [s["conversation_id"] for s in proj_sessions] == [cid_new, cid_old]
    assert proj_sessions[1]["is_pinned"] is True
    assert proj_sessions[0]["last_updated_ts"] > proj_sessions[1]["last_updated_ts"]


def test_brand_new_0001_sentinel_session_with_fresh_brain_mtime_ranks_first(monkeypatch, tmp_path):
    db_path, brain_dir, proj_dir = _patch_env(monkeypatch, tmp_path)
    now = time.time()
    pid = "22222222-2222-4222-8222-222222222222"
    ws = str(tmp_path / "repos" / "sentinel-repo")
    _write_project(proj_dir, pid, "Sentinel Repo", ws)

    rows = []
    for i in range(215):
        ts = now - 7200 - (i * 60)
        cid = f"cccccccc-0000-4000-8000-{i:012d}"
        rows.append((cid, f"Historical {i}", "", 50, _iso_utc(ts), json.dumps([ws]), "IDLE", 0, 0, "", pid))
    for j in range(205):
        cid = f"dddddddd-0000-4000-8000-{j:012d}"
        rows.append((cid, f"Ancient Sentinel {j}", "", 5, "0001-01-01 00:00:00+00:00", json.dumps([ws]), "IDLE", 0, 0, "", pid))

    fresh_cid = "eeeeeeee-9999-4999-8999-999999999999"
    rows.append((fresh_cid, "Brand New Live Chat", "", 2, "0001-01-01 00:00:00+00:00", json.dumps([ws]), "IDLE", 1, 0, "", pid))
    _create_db(db_path, rows)
    _seed_brain_file(brain_dir, fresh_cid, "transcript.jsonl", now + 30.0, '{"step_index":0}\n')

    listed = sessions._list_saved_sessions_internal(limit=15)
    assert listed[0]["conversation_id"] == fresh_cid
    assert listed[0]["index"] == "1"
    assert listed[0]["last_updated_ts"] >= now + 29.0
    assert listed[0]["last_updated"] and not listed[0]["last_updated"].startswith("0001-")


def test_projects_sort_strictly_by_newest_activity_over_cumulative_steps(monkeypatch, tmp_path):
    db_path, brain_dir, proj_dir = _patch_env(monkeypatch, tmp_path)
    now = time.time()
    bg_dir = tmp_path / "ag-bridge-bg"
    pids = [
        ("p-legacy", "Legacy Heavy Repo", now - 2 * 86400, 5000, True),
        ("p-quiet", "Quiet Recent Repo", now - 300, 20, False),
        ("p-handoff", "Handoff Boosted Repo", now - 3 * 86400, 30, False),
        ("p-closed", "Closed Ticket Repo", now - 4 * 86400, 100, False),
    ]
    rows = []
    for idx, (pid, name, ts, steps, running) in enumerate(pids):
        ws = str(tmp_path / "repos" / pid)
        _write_project(proj_dir, pid, name, ws)
        cid = f"ffffffff-0000-4000-8000-00000000000{idx}"
        rows.append((cid, f"{name} Chat", "", steps, _iso_utc(ts), json.dumps([ws]), "RUNNING" if running else "IDLE", 1 if running else 0, 0, "", pid))
        _seed_brain_file(brain_dir, cid, "task.md", ts, "# task\n")
    _create_db(db_path, rows)

    staged = record_handoff_ticket(
        bg_dir, full_markdown="# Active Staged", chars_written=15, repo_slug="p-handoff",
        title="Urgent Staged Fix", project_id="p-handoff", project_name="Handoff Boosted Repo",
        workspace_path=str(tmp_path / "repos" / "p-handoff"), initial_status="STAGED",
    )
    record_handoff_ticket(
        bg_dir, full_markdown="# Completed Old", chars_written=14, repo_slug="p-closed",
        title="Already Done", project_id="p-closed", project_name="Closed Ticket Repo",
        workspace_path=str(tmp_path / "repos" / "p-closed"), initial_status="COMPLETED",
    )
    record_handoff_ticket(
        bg_dir, full_markdown="# Zero Session Completed", chars_written=24, repo_slug="p-zero-closed",
        title="No Sessions Closed", project_id="p-zero-closed", project_name="Zero Session Completed Repo",
        workspace_path=str(tmp_path / "repos" / "p-zero-closed"), initial_status="COMPLETED",
    )
    assert staged["handoff_id"] == "p-handoff-01"

    tree = session_tree.build_project_session_tree(bg_dir=bg_dir)
    ordered_names = [p["project_name"] for p in tree["projects"]]
    assert ordered_names == [
        "Handoff Boosted Repo", "Quiet Recent Repo", "Legacy Heavy Repo",
        "Closed Ticket Repo", "Zero Session Completed Repo",
    ]


def test_media_discovery_sentinel_ownership_window(tmp_path):
    db_path = tmp_path / "conversation_summaries.db"
    brain_root = tmp_path / "brain"
    ws = tmp_path / "repos" / "sentinel-ws"
    ws.mkdir(parents=True, exist_ok=True)
    now = time.time()
    cid_old = "10101010-0000-4000-8000-000000000001"
    cid_new = "10101010-0000-4000-8000-000000000002"
    _create_db(db_path, [
        (cid_old, "Older Active", "", 90, _iso_utc(now - 3600), json.dumps([str(ws)]), "IDLE", 0, 0, "", "p-sent"),
        (cid_new, "Brand New 0001", "", 1, "0001-01-01 00:00:00+00:00", json.dumps([str(ws)]), "IDLE", 1, 0, "", "p-sent"),
    ])
    _seed_brain_file(brain_root, cid_old, "task.md", now - 3600, "# old\n")
    _seed_brain_file(brain_root, cid_new, "task.md", now + 15.0, "# new\n")
    is_latest, start_ts, end_ts = md.resolve_session_ownership_window(
        cid_new, ws.resolve(), brain_dir=brain_root / cid_new, db_file=db_path,
    )
    assert is_latest is True
    assert start_ts >= (now - 3600) and end_ts >= now


def _run_explorer_node(driver_js: str, payload: dict) -> dict:
    explorer_code = (PROJECT_ROOT / "web" / "explorer.js").read_text(encoding="utf-8")
    preamble = r"""
const vm = require('vm');
function mkEl(id) {
  return { id, innerHTML: '', textContent: '', value: '', style: {}, dataset: {},
    classList: { toggle() {}, add() {}, remove() {}, contains() { return false; } },
    addEventListener() {}, setAttribute() {}, closest() { return null; },
    querySelectorAll() { return []; }, querySelector() { return null; },
  };
}
function makeEnv(searchStr, payload) {
  const els = new Map(), selectedFetches = [];
  const getEl = (id) => { if (!els.has(id)) els.set(id, mkEl(id)); return els.get(id); };
  const noop = { getItem: () => '', setItem: () => {}, removeItem: () => {} };
  const ctx = {
    location: { search: searchStr, hash: '#workspace', pathname: '/web' },
    navigator: {}, history: { replaceState() {} }, localStorage: noop, sessionStorage: noop,
    setTimeout, clearTimeout, URLSearchParams, Map, Set, Array, Number, String, JSON, Math, Promise, console,
    state: { demoMode: false }, addEventListener() {},
    getBaseApiPath: () => '', getApiHeaders: () => ({}),
    escapeHtmlSafe: (s) => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\"/g,'&quot;'),
    document: { getElementById: getEl, querySelectorAll: () => [], querySelector: () => null, addEventListener() {} },
    fetch: async (url) => {
      const m = String(url).match(/\/web\/api\/sessions\/([^/?]+)\/bucket/);
      if (m) {
        selectedFetches.push(m[1]);
        await new Promise((r) => setTimeout(r, 15));
      }
      if (String(url).includes('/workspace/tree')) return { status: 200, json: async () => payload };
      return { status: 200, json: async () => ({ ok: true, visual_artifacts: [], repo_visual_assets: [], artifacts: [], uploads: [], queue_tickets: [] }) };
    },
  };
  ctx.window = ctx; ctx.self = ctx; ctx.globalThis = ctx;
  vm.runInNewContext(process.argv[1], ctx);
  return { explorer: ctx.WorkspaceExplorer, selectedFetches, getEl, ctx };
}
"""
    script = f"{preamble}\n(async () => {{\n  const payload = JSON.parse(process.argv[2]);\n{driver_js}\n}})();"
    proc = subprocess.run(["node", "-e", script, explorer_code, json.dumps(payload)], capture_output=True, text=True, check=True, timeout=15)
    return json.loads(proc.stdout)


def test_workspace_tree_payload_and_frontend_auto_select_and_age_pills(monkeypatch, tmp_path):
    db_path, brain_dir, proj_dir = _patch_env(monkeypatch, tmp_path)
    now = time.time()
    pid = "33333333-3333-4333-8333-333333333333"
    ws = str(tmp_path / "repos" / "nexus-demo")
    _write_project(proj_dir, pid, "Nexus Demo", ws)
    cid_fresh, cid_stale = "12121212-0000-4000-8000-000000000001", "12121212-0000-4000-8000-000000000002"
    _create_db(db_path, [
        (cid_stale, "Stale Selected", "", 300, _iso_utc(now - 7200), json.dumps([ws]), "RUNNING", 1, 0, "", pid),
        (cid_fresh, "Fresh Active", "", 15, _iso_utc(now - 240), json.dumps([ws]), "IDLE", 0, 0, "", pid),
    ])
    _seed_brain_file(brain_dir, cid_stale, "task.md", now - 7200, "# s\n")
    _seed_brain_file(brain_dir, cid_fresh, "task.md", now - 240, "# f\n")

    payload = bucket_api.build_workspace_tree_payload()
    assert payload["ok"] is True
    sess_list = payload["projects"][0]["sessions"]
    assert [s["conversation_id"] for s in sess_list] == [cid_fresh, cid_stale]
    assert all(float(s.get("last_updated_ts") or 0) > 0 and s.get("relative_age") for s in sess_list)
    assert payload["projects"][0]["last_updated_ts"] == sess_list[0]["last_updated_ts"]
    assert ".tree-age-pill" in (PROJECT_ROOT / "web" / "workspace.css").read_text(encoding="utf-8")

    out = _run_explorer_node("""
      const rA = makeEnv('', payload); await rA.explorer.loadWorkspaceTree();
      const staleP = Object.assign({}, payload, { selected_session: payload.projects[0].sessions[1].conversation_id });
      const rStale = makeEnv('', staleP); await rStale.explorer.loadWorkspaceTree();
      const rDeep = makeEnv('?session=deep-link-999', payload); await rDeep.explorer.loadWorkspaceTree();
      const rBad = makeEnv('?session=../../bad', payload); await rBad.explorer.loadWorkspaceTree();
      console.log(JSON.stringify({ a: rA.selectedFetches, html: rA.getEl('workspaceTreeRoot').innerHTML, stale: rStale.selectedFetches, deep: rDeep.selectedFetches, bad: rBad.selectedFetches }));
    """, payload)
    assert out["a"] == [cid_fresh]
    assert out["stale"] == [cid_fresh]
    assert 'class="tree-age-pill mono">4m</span>' in out["html"]
    assert out["deep"] == []
    assert out["bad"] == [cid_fresh]


def test_frontend_handoff_only_top_project_and_no_duplicate_bucket_race():
    payload = {
        "ok": True,
        "selected_session": "s-stale",
        "projects": [
            {"project_name": "Handoff Only", "staged_count": 1, "sessions": []},
            {"project_name": "Stale Boosted", "sessions": [{"conversation_id": "s-stale", "title": "Old", "last_updated_ts": 100.0, "relative_age": "3d ago"}]},
            {"project_name": "Fresher Repo", "sessions": [{"conversation_id": "s-freshest", "title": "Fresh", "last_updated_ts": 900.0, "relative_age": "5m ago"}]},
        ],
    }
    out = _run_explorer_node("""
      const r1 = makeEnv('', payload); await r1.explorer.loadWorkspaceTree();
      const r2 = makeEnv('?session=s-stale', payload);
      await Promise.all([r2.explorer.selectSession('s-stale'), r2.explorer.loadWorkspaceTree()]);
      const rDemoDeep = makeEnv('?session=demo-deep', payload);
      rDemoDeep.ctx.state.demoMode = true; rDemoDeep.ctx.DEMO_WORKSPACE_TREE = payload;
      await rDemoDeep.explorer.loadWorkspaceTree();
      console.log(JSON.stringify({ handoffTop: r1.selectedFetches, raceFetches: r2.selectedFetches, demoDeepTree: rDemoDeep.getEl('workspaceTreeRoot').innerHTML }));
    """, payload)
    assert out["handoffTop"] == ["s-freshest"]
    assert out["raceFetches"] == ["s-stale"]
    assert 'class="tree-session-item active"' not in out["demoDeepTree"]


def test_conv_id_traversal_and_symlink_guards(monkeypatch, tmp_path):
    db_path, brain_dir, proj_dir = _patch_env(monkeypatch, tmp_path)
    secret_dir = tmp_path / "outside"
    secret_dir.mkdir()
    (secret_dir / "task.md").write_text("- [ ] SECRET LEAK", encoding="utf-8")
    (brain_dir / "symlinked-cid").symlink_to(secret_dir)
    pid = "44444444-4444-4444-8444-444444444444"
    ws = str(tmp_path / "repos" / "safe-ws")
    _write_project(proj_dir, pid, "Safe WS", ws)
    _create_db(db_path, [
        ("../../outside", "Traversal Row", "", 10, _iso_utc(time.time()), json.dumps([ws]), "IDLE", 0, 0, "", pid),
        ("symlinked-cid", "Symlink Row", "", 10, _iso_utc(time.time() - 60), json.dumps([ws]), "IDLE", 0, 0, "", pid),
        ("valid-cid-01", "Safe Row", "", 10, _iso_utc(time.time() - 120), json.dumps([ws]), "IDLE", 0, 0, "", pid),
    ])
    listed = sessions._list_saved_sessions_internal(limit=10)
    assert [s["conversation_id"] for s in listed] == ["symlinked-cid", "valid-cid-01"]
    assert listed[0]["task_preview"] == "No active task checklist"
    assert session_status.count_session_compactions("../outside", brain_dir=brain_dir) == 0
    assert session_status.count_session_compactions("symlinked-cid", brain_dir=brain_dir) == 0

