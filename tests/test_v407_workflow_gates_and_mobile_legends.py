"""tests/test_v407_workflow_gates_and_mobile_legends.py — AGY-Nexus v4.0.7 Workflows, Gates & Visual Legends."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import time

import pytest
from starlette.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
V9_DIR = REPO_ROOT / "web" / "v9"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import agy_nexus
from agy_nexus import (
    config as cfg,
    handoff as handoff_mod,
    polyglot_outline,
    retirement as ret_mod,
    routing as routing_mod,
    search as search_mod,
    session_status as ss_mod,
    session_tree as st_mod,
    sessions as sess_mod,
    target_resolver as tr_mod,
    tools_praxis as praxis_mod,
    tools_session as tsession_mod,
    tools_workspace as tws_mod,
    virtual_uris as vu_mod,
    workflow_baseline as wb_mod,
    workflows as wf_mod,
    workspace as ws_mod,
)
from agy_nexus.server import build_nexus_http_app
from agy_nexus.tools_praxis import praxis_update_handoff


def _setup_sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path, Path, str, str]:
    brain_root = tmp_path / "brain"
    bg_dir = tmp_path / "bg"
    ws_root = tmp_path / "ws"
    proj_dir = ws_root / "projects"
    db_file = tmp_path / "state.vscdb"
    cfg_dir = tmp_path / "cfg"
    (cfg_dir / "projects").mkdir(parents=True)
    bg_dir.mkdir(parents=True)
    brain_root.mkdir(parents=True)
    proj_dir.mkdir(parents=True)
    con = sqlite3.connect(str(db_file))
    con.execute(
        "CREATE TABLE conversation_summaries (conversation_id TEXT PRIMARY KEY, title TEXT, preview TEXT, "
        "project_id TEXT, status TEXT, step_count INTEGER, last_modified_time TEXT, "
        "not_fully_idle INTEGER, killed INTEGER, workspace_uris TEXT, parent_conversation_id TEXT)"
    )
    con.commit()
    con.close()
    mods = (cfg, handoff_mod, praxis_mod, tsession_mod, tws_mod, sess_mod, ss_mod, st_mod, search_mod, routing_mod, tr_mod, ret_mod, vu_mod, wf_mod, ws_mod)
    attrs = {
        "AGY_BRAIN_DIR": brain_root, "AGY_BG_DIR": bg_dir, "AGY_DB_FILE": db_file,
        "AGY_CONFIG_DIR": cfg_dir, "AGY_DATA_DIR": tmp_path,
        "AGY_WORKSPACE_DIR": ws_root, "AGY_PROJECTS_DIR": proj_dir,
        "AGY_WORKBOOKS_DIR": ws_root / "workbooks", "AGY_CONFIGURATION_DIR": ws_root / "configuration",
        "AGY_GITLAB_DIR": proj_dir,
    }
    for mod in mods:
        for attr, val in attrs.items():
            if hasattr(mod, attr):
                monkeypatch.setattr(mod, attr, val)
    phrase = "canary workflow gates open"
    monkeypatch.setattr(cfg, "PASS_HASH", cfg.normalize_phrase(phrase))
    return brain_root, bg_dir, proj_dir, db_file, phrase, "v407_secret_001122334455667788"


def _mcp_call(client: TestClient, secret: str, req_id: int, tool_name: str, arguments: dict) -> dict:
    resp = client.post(
        f"/{secret}/mcp",
        json={"jsonrpc": "2.0", "id": req_id, "method": "tools/call", "params": {"name": tool_name, "arguments": arguments}},
    )
    assert resp.status_code == 200
    assert len(resp.content) < 20_480, f"{tool_name} exceeded 20 KB wire cap ({len(resp.content)}B)"
    return json.loads(resp.json()["result"]["content"][0]["text"])


def test_v407_workflows_doc_glossary_structure_and_wire_readin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify WORKFLOWS.md has Common Terms + WF-01..WF-07, zero banned words, and full read-in without cutoff."""
    wf_txt = (REPO_ROOT / "docs" / "WORKFLOWS.md").read_text(encoding="utf-8")
    assert "## Common Terms Glossary" in wf_txt
    for n in range(1, 8):
        assert f"## Workflow {n}: WF-0{n}" in wf_txt
    for banned in ("diurnal", "plain-english", "posture", "surface"):
        assert banned not in wf_txt.lower(), f"Banned term '{banned}' found in docs/WORKFLOWS.md"

    wf_info = wb_mod.discover_project_workflows(REPO_ROOT)
    assert wf_info["workflow_status"] == "READY"
    assert len(wf_info["workflows"]) == 7
    assert [w["id"] for w in wf_info["workflows"]] == [f"WF-0{n}" for n in range(1, 8)]
    assert len(wf_info["common_terms"]) >= 4

    wire = wb_mod.format_workflow_baseline_for_wire(wf_info, max_chars=1200)
    assert len(wire) <= 1200
    assert "**Established Workflows (`docs/WORKFLOWS.md`)**:" in wire
    assert "**Common Terms**:" in wire
    for n in range(1, 8):
        assert f"WF-0{n}" in wire

    # Live read-in tools expose READY vs MISSING_BASELINE accurately
    brain_root, _bg, proj_dir, _db, phrase, secret = _setup_sandbox(tmp_path, monkeypatch)
    brown_repo = proj_dir / "brownfield-app"
    brown_repo.mkdir(parents=True)
    (brown_repo / "README.md").write_text("# Brownfield App\n## Workflows\n### Deploy Flow\nRun deploy.\n", encoding="utf-8")
    cid_b = "12121212-3434-4567-89ab-0123456789cd"
    (brain_root / cid_b / "scratch").mkdir(parents=True)
    cfg.pin_session_context(cid_b, title="Brownfield Inspect", project_name="Brownfield App", workspace=str(brown_repo), set_default=True)
    monkeypatch.setattr(tsession_mod, "_collect_git_summary", lambda _p: {"branch": "main", "status_short": ""})

    app = build_nexus_http_app(secret, cfg.get_polyglot_mcp_token(secret), cfg.get_praxis_mcp_token(secret))
    with TestClient(app) as client:
        _mcp_call(client, secret, 1, "unlock_sessions", {"spoken_passphrase": phrase})
        loaded = _mcp_call(client, secret, 2, "load_session_into_gemini", {"session_identifier": cid_b})
        assert loaded["project_workflows"]["workflow_status"] == "MISSING_BASELINE"
        baseline_resp = _mcp_call(client, secret, 3, "ask_workspace_readonly", {
            "question": "Check workflow baseline", "file_subpath": "workflow:baseline", "workspace": str(brown_repo),
        })
        txt = json.dumps(baseline_resp)
        assert "MISSING_BASELINE" in txt

        # Now copy real docs/WORKFLOWS.md into brown_repo and confirm READY index returns all WF-01..WF-07
        (brown_repo / "docs").mkdir()
        shutil.copy2(REPO_ROOT / "docs" / "WORKFLOWS.md", brown_repo / "docs" / "WORKFLOWS.md")
        loaded_ready = _mcp_call(client, secret, 4, "load_session_into_gemini", {"session_identifier": cid_b})
        assert loaded_ready["project_workflows"]["workflow_status"] == "READY"
        assert len(loaded_ready["project_workflows"]["workflows"]) == 7
        assert len(loaded_ready["project_workflows"]["common_terms"]) >= 4


def test_v407_four_workflow_gates_non_bypass_and_praxis_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify Gates 1-4, allow_chained_publish non-bypass, WF-XX injection, and WORKFLOW_DOC_NOT_UPDATED gate."""
    brain_root, bg_dir, proj_dir, _db, phrase, secret = _setup_sandbox(tmp_path, monkeypatch)
    ready_repo = proj_dir / "ready-app"
    (ready_repo / "docs").mkdir(parents=True)
    (ready_repo / "pyproject.toml").write_text('[project]\nname = "ready-app"\n', encoding="utf-8")
    shutil.copy2(REPO_ROOT / "docs" / "WORKFLOWS.md", ready_repo / "docs" / "WORKFLOWS.md")

    brown_repo = proj_dir / "brown-missing"
    brown_repo.mkdir(parents=True)
    (brown_repo / "README.md").write_text("# Brown Missing\nExisting code.\n", encoding="utf-8")

    # Legacy false-positive bypass "Edit user.py step 1 line 10" must be flagged as code dump
    bad_q = wb_mod.evaluate_handoff_quality("Edit src/user.py step 1 line 10 to fix endpoint.", is_closeout=False)
    assert bad_q["has_goal_or_why"] is False and bad_q["is_code_only_dump"] is True
    monkeypatch.setattr(handoff_mod, "_post_bridge", lambda p: {
        "ok": True, "workspace_path": p.get("workspace_path", ""),
        "project_id": p.get("project_id") or "mock-pid", "project_name": p.get("project_name", "Mock"),
    })

    app = build_nexus_http_app(secret, cfg.get_polyglot_mcp_token(secret), cfg.get_praxis_mcp_token(secret))
    with TestClient(app) as client:
        _mcp_call(client, secret, 10, "unlock_sessions", {"spoken_passphrase": phrase})

        # Gate 1: Greenfield new_project rejected cleanly until Who & Goal + Common Terms + >=2 WF-XX flows exist
        gf_path = str(proj_dir / "fresh-gf")
        g1_block = _mcp_call(client, secret, 11, "send_handoff_and_resume", {
            "research_markdown": "Build a quick todo tracker app.",
            "handoff_mode": "new_project", "create_new_project": True,
            "workspace_path": "projects/fresh-gf", "project_name": "Fresh GF", "resume_headless": False,
        })
        assert g1_block["ok"] is False and g1_block["status"] == "NEEDS_WORKFLOW_SPEC"
        assert not Path(gf_path).exists()
        assert "@Agy Nexus Mcp " in g1_block["suggested_actions"]["followup_xml"]

        # Provide complete greenfield spec -> succeeds with workflow_delta='bootstrap'
        g1_ok = _mcp_call(client, secret, 12, "send_handoff_and_resume", {
            "research_markdown": (
                "# Fresh GF\n\n## Who & Goal\nThe user wants a mobile task tracker so they can triage chores cleanly.\n\n"
                "## Common Terms\n- **Focus Card**: Primary daily task panel.\n\n"
                "## WF-01 — Quick Capture\nUser taps Add, sees Focus Card across 390px/900px/1440px, sees empty state or error retry.\n\n"
                "## WF-02 — Daily Review\nUser expects completed items archived on tap.\n"
            ),
            "handoff_mode": "new_project", "create_new_project": True,
            "workspace_path": "projects/fresh-gf", "project_name": "Fresh GF", "resume_headless": False,
        })
        assert g1_ok["ok"] is True and g1_ok["workflow_delta"] == "bootstrap"

        # Gate 2: Brownfield repo missing docs/WORKFLOWS.md rejects until workflow_delta='bootstrap'
        g2_block = _mcp_call(client, secret, 13, "send_handoff_and_resume", {
            "research_markdown": "# User Goal\nThe user wants faster search.\n\n## Workflow\nUser taps search bar and sees instant hits.",
            "handoff_mode": "feature_update", "workspace_path": str(brown_repo), "resume_headless": False,
        })
        assert g2_block["ok"] is False and g2_block["status"] == "WORKFLOW_BOOTSTRAP_REQUIRED"

        g2_boot = _mcp_call(client, secret, 14, "send_handoff_and_resume", {
            "research_markdown": (
                "# User Goal\nThe user wants instant search.\n\n"
                "## Common Terms\n- **Result Card**: Search match row.\n\n"
                "## WF-01 — Search Flow\nUser taps Search and sees Result Card results."
            ),
            "handoff_mode": "feature_update", "workflow_delta": "bootstrap", "workflow_ids": "WF-01",
            "user_terms": "Result Card = match row", "workspace_path": str(brown_repo), "resume_headless": False,
        })
        assert g2_boot["ok"] is True and g2_boot["workflow_delta"] == "bootstrap"
        boot_hid = g2_boot["handoff_id"]

        # Gate 3 & allow_chained_publish=True non-bypass: bare code dump rejected even with allow_chained_publish=True!
        g3_dump = _mcp_call(client, secret, 15, "send_handoff_and_resume", {
            "research_markdown": "Modify src/routes.py lines 40-55 and styles.css line 10.",
            "handoff_mode": "feature_update", "allow_chained_publish": True,
            "workflow_ids": "WF-03", "workflow_delta": "unchanged",
            "workspace_path": str(ready_repo), "resume_headless": False,
        })
        assert g3_dump["ok"] is False and g3_dump["status"] == "HANDOFF_REJECTED_PLAIN_LANGUAGE"

        # Invalid/unknown workflow_ids on READY repo rejected cleanly
        g3_bad_id = _mcp_call(client, secret, 16, "send_handoff_and_resume", {
            "research_markdown": "# User Goal\nThe user wants crisp chart buttons.\n\n## Workflow\nUser taps chart legend and sees toggle.",
            "handoff_mode": "bug_or_visual_fix", "allow_chained_publish": True,
            "workflow_ids": "WF-99", "workspace_path": str(ready_repo), "resume_headless": False,
        })
        assert g3_bad_id["ok"] is False and g3_bad_id["status"] == "HANDOFF_REJECTED_PLAIN_LANGUAGE"

        # Valid bug_or_visual_fix defaults workflow_delta='update_existing' & injects WF-03 + Common Terms
        g4_ok = _mcp_call(client, secret, 17, "send_handoff_and_resume", {
            "research_markdown": (
                "# Fix Mobile Topbar & Legend\n\n## User Goal\nThe user wants bigger tap targets on folded phone screens.\n\n"
                "## What the User Sees & Taps\nUser taps menu button and sees 40px targets on 390px and 56px bar on 900px."
            ),
            "handoff_mode": "bug_or_visual_fix", "allow_chained_publish": True,
            "workflow_ids": "WF-03", "user_terms": "Topbar Row = sticky nav strip",
            "workspace_path": str(ready_repo), "resume_headless": False,
        })
        assert g4_ok["ok"] is True
        assert g4_ok["workflow_delta"] == "update_existing"
        assert g4_ok["workflow_ids"] == ["WF-03"]
        h_text = Path(g4_ok["handoff_file"]).read_text(encoding="utf-8")
        assert "Grounded Repository Workflows & Common Terms" in h_text
        assert "Workflow 3: WF-03" in h_text and "Topbar Row = sticky nav strip" in h_text
        upd_hid = g4_ok["handoff_id"]

        # release_closeout IS exempt from plain-language body gate
        rc_ok = _mcp_call(client, secret, 18, "send_handoff_and_resume", {
            "research_markdown": "Commit, tag, push v4.0.7.",
            "handoff_mode": "release_closeout", "allow_chained_publish": True,
            "workspace_path": str(ready_repo), "resume_headless": False,
        })
        assert rc_ok["ok"] is True

        # Praxis closeout check: WORKFLOW_DOC_NOT_UPDATED until docs/WORKFLOWS.md actually created/updated
        blk_boot = json.loads(praxis_update_handoff(handoff_id=boot_hid, status="COMPLETED"))
        assert blk_boot["ok"] is False and blk_boot["status"] == "WORKFLOW_DOC_NOT_UPDATED"
        (brown_repo / "docs").mkdir(exist_ok=True)
        (brown_repo / "docs" / "WORKFLOWS.md").write_text("## Common Terms\n- **Result Card**: row.\n\n## Workflow 1: WF-01 — Search\nSee results.\n", encoding="utf-8")
        ok_boot = json.loads(praxis_update_handoff(handoff_id=boot_hid, status="COMPLETED"))
        assert ok_boot["ok"] is True and ok_boot["ticket"]["status"] == "COMPLETED"

        blk_upd = json.loads(praxis_update_handoff(handoff_id=upd_hid, status="COMPLETED"))
        assert blk_upd["ok"] is False and blk_upd["status"] == "WORKFLOW_DOC_NOT_UPDATED"
        wf_doc = ready_repo / "docs" / "WORKFLOWS.md"
        wf_doc.write_text(wf_doc.read_text(encoding="utf-8") + "\n<!-- updated -->\n", encoding="utf-8")
        ok_upd = json.loads(praxis_update_handoff(handoff_id=upd_hid, status="COMPLETED"))
        assert ok_upd["ok"] is True and ok_upd["ticket"]["status"] == "COMPLETED"

    # Line budgets & tools/list <= 8600B
    assert len((SRC_DIR / "agy_nexus" / "workflow_gate.py").read_text(encoding="utf-8").splitlines()) <= 500
    assert len((SRC_DIR / "agy_nexus" / "workflow_baseline.py").read_text(encoding="utf-8").splitlines()) <= 500


def test_v407_mobile_topbar_css_hourly_legend_and_table_legends(tmp_path: Path) -> None:
    """Verify <680px/680-1099px CSS rules, v9_billing.js hourly legend across 4 themes, and 4 table legends."""
    shell_css = (V9_DIR / "v9_shell.css").read_text(encoding="utf-8")
    assert "!important" not in shell_css
    assert len(shell_css.splitlines()) <= 500
    assert re.search(r"@media\s*\(max-width:\s*679px\)[\s\S]*min-block-size:\s*40px", shell_css)
    assert re.search(r"@media\s*\(max-width:\s*679px\)[\s\S]*inline-size:\s*18px;\s*block-size:\s*18px", shell_css)
    assert re.search(r"@media\s*\(max-width:\s*679px\)[\s\S]*min-block-size:\s*36px[\s\S]*min-inline-size:\s*36px", shell_css)
    assert re.search(r"@media\s*\(min-width:\s*680px\)\s*and\s*\(max-width:\s*1099px\)[\s\S]*block-size:\s*56px[\s\S]*min-block-size:\s*36px", shell_css)

    probe = tmp_path / "v407_ui_probe.js"
    probe.write_text(
        r"""
const fs = require("fs");
const vm = require("vm");
const assert = require("assert");
const byId = new Map();
function makeNode(tag, id) {
  const n = {
    tagName: tag, id: id || "", textContent: "", _html: "", _legend: "", children: [], style: {}, dataset: {}, _attrs: {},
    classList: { _s: new Set(), add(c){this._s.add(c);}, remove(c){this._s.delete(c);}, contains(c){return this._s.has(c);} },
    addEventListener(){}, setAttribute(k, v){ this._attrs[k] = String(v); }, getAttribute(k){ return this._attrs[k] ?? null; }, removeAttribute(k){ delete this._attrs[k]; },
    querySelector: () => null, querySelectorAll: () => [], closest: () => null,
  };
  Object.defineProperty(n, "innerHTML", { get(){ return this._html + (this._legend || ""); }, set(v){ this._html = String(v); this._legend = ""; } });
  return n;
}
["v9KpiGrid","v9ModelPlotSub","v9SubPlotSub","v9ModelTableLegend","v9SubagentTableLegend",
 "v9ProjPlotTitle","v9ProjPlotSub","v9ProjTableWrap","v9ProjFoot","v9ModelTableBody","v9SubagentTableBody"
].forEach((id) => byId.set(id, makeNode("DIV", id)));
const mkTbl = (tid, tbodyId) => {
  const th = makeNode("THEAD", "");
  const tbl = makeNode("TABLE", tid);
  tbl.tHead = th;
  tbl.setAttribute("data-v9-table", tid);
  byId.get(tbodyId).closest = () => tbl;
};
mkTbl("models", "v9ModelTableBody");
mkTbl("subagents", "v9SubagentTableBody");
byId.get("v9ProjTableWrap").querySelector = (sel) => {
  const wrap = byId.get("v9ProjTableWrap");
  if (sel === ".v9-table-legend-host") return { set innerHTML(v) { wrap._legend = v; }, get innerHTML() { return wrap._legend || ""; } };
  if (sel === "table") return makeNode("TABLE", "");
  if (sel === "tbody") return makeNode("TBODY", "");
  if (sel === "thead") return makeNode("THEAD", "");
  return null;
};

const ctx = {
  window: { AgyV9: {}, innerWidth: 390, location: { hostname: "nexus.example.com", pathname: "/web", search: "", hash: "", origin: "https://nexus.example.com" } },
  location: { hostname: "nexus.example.com", pathname: "/web", search: "", hash: "", origin: "https://nexus.example.com" },
  localStorage: { getItem: () => null, setItem() {} },
  sessionStorage: { getItem: () => null, setItem() {} },
  URLSearchParams,
  URL,
  document: { documentElement: { dataset: { theme: "white" } }, getElementById: (id) => byId.get(id) || null, querySelectorAll: () => [], createElement: (tag) => makeNode(tag, "") },
  echarts: null, console, Math, Number, String, Array, Object, Date, Map, Set, JSON,
};
ctx.window = ctx;
ctx.window.AgyV9 = {};
ctx.window.innerWidth = 390;
for (const f of ["web/v9/v9_state.js", "web/v9/v9_table_sort.js", "web/v9/v9_spark_bars.js", "web/v9/v9_billing.js", "web/v9/v9_analytics.js", "web/v9/v9_project_view.js"]) {
  vm.runInNewContext(fs.readFileSync(f, "utf-8"), ctx);
}
const V9 = ctx.AgyV9;
if (!V9.getTheme) V9.getTheme = () => ({ surface: "#ffffff", elev: "#f1f5f9", spine: "#cbd5e1", text: "#0f172a", sub: "#475569", muted: "#64748b", grid: "#e2e8f0" });
// 1. Check buildCadenceWhiskerOption across all 4 themes
const hwSteps = Array.from({ length: 24 }, () => ({ min: 10, avg: 30, max: 60, last_24h: 25, active_days: 4 }));
const hwHours = Array.from({ length: 24 }, (_, i) => `${String(i).padStart(2, "0")}h`);
for (const theme of ["white", "paper", "dark-paper", "dark"]) {
  ctx.document.documentElement.dataset.theme = theme;
  const tObj = V9.getTheme();
  const stemCol = V9.getSeriesColor(1), avgCol = V9.getSeriesColor(0), l24Col = V9.getSeriesColor(2);
  const built = V9.Billing.buildCadenceWhiskerOption({
    hourly_whiskers: { hours: hwHours, steps: hwSteps, has_last_24h: true, active_days_count: 4 },
  }, "steps", tObj, 640);
  const opt = built.opt;
  assert.equal(opt.series[0].itemStyle.color, stemCol, `${theme} range color mismatch`);
  assert.equal(opt.series[1].itemStyle.color, avgCol, `${theme} avg color mismatch`);
  assert.equal(opt.series[2].itemStyle.color, l24Col, `${theme} l24 color mismatch`);
  assert.ok(opt.legend.data[0].icon.startsWith("path://") && opt.legend.data[0].itemStyle.color === stemCol);
  assert.ok(opt.legend.data[1].icon.startsWith("path://") && opt.legend.data[1].itemStyle.color === avgCol);
  assert.equal(opt.legend.data[2].icon, "circle");
  assert.equal(opt.legend.data[2].itemStyle.color, l24Col);
}
// 2. Check all 4 table legends + reactive sessions mode + subagent avg/max readout
const sessRow = { conversation_id: "c-1", title: "Session 1", step_count: 350, window_steps: 200, tokens: 50000, window_tokens: 40000, window_cost_usd: 0.4, last_24h_tokens: 10000, last_24h_cost_usd: 0.1 };
const bundle = {
  period: { key: "current_month", label: "MTD" }, kpis: { window_steps: 200 },
  model_balance: [{ model_key: "carbon", label: "Gemini 4 Carbon", pool: "Google 20x", actual_pct: 60, target_pct: 50, est_tokens: 40000, est_cost_usd: 0.4 }],
  model_series: { dates: ["2026-11-23T10"], step_hours: 1, layers: { carbon: [200] }, tokens_layers: { carbon: [40000] }, cost_layers: { carbon: [0.4] } },
  subagent_list: [{ role: "argon-surgeon", runs: 2, steps: 90, avg_steps_per_run: 45, min_steps_per_run: 20, max_steps_per_run: 70, last_run_steps: 70, tokens: 10000, avg_tokens_per_run: 5000, min_tokens_per_run: 2000, max_tokens_per_run: 8000, last_run_tokens: 8000, est_cost_usd: 0.1 }],
  project_hierarchy: { top_projects: [{ project_id: "p1", project_name: "Demo", window_steps: 200, min_daily_steps: 50, avg_daily_steps: 100, max_daily_steps: 200, last_24h_steps: 120, sessions: [sessRow] }], idle_projects: [] },
};
for (const metric of ["steps", "tokens", "cost"]) {
  V9.state.metric = metric;
  V9.Analytics.renderAnalytics(bundle, {}, () => {});
  assert.ok(byId.get("v9ModelTableLegend").innerHTML.includes("Window share") && byId.get("v9ModelTableLegend").innerHTML.includes("Tap row to solo"));
  assert.ok(byId.get("v9SubagentTableLegend").innerHTML.includes("Min–Max / run") && byId.get("v9SubagentTableLegend").innerHTML.includes("&gt;120"));
  assert.ok(byId.get("v9SubagentTableBody").innerHTML.includes("avg") && byId.get("v9SubagentTableBody").innerHTML.includes("max"));
  assert.ok(byId.get("v9ProjTableWrap").innerHTML.includes("Active-day Min–Peak") && byId.get("v9ProjTableWrap").innerHTML.includes("Idle 24h"));
  V9.ProjectView.renderProjectSessionsCard(Object.assign({}, bundle, { project_scope: { project_id: "p1" }, project_sessions_series: { dates: ["2026-11-23T10"], step_hours: 1, sessions: [sessRow] } }), {});
  const sHtml = byId.get("v9ProjTableWrap").innerHTML;
  if (metric === "steps") assert.ok(sHtml.includes("320 clean seam") && sHtml.includes("700 rollover limit"));
  else assert.ok(sHtml.includes("Session total") && sHtml.includes("Project avg") && sHtml.includes("Last 24h"));
}
console.log("OK_V407_UI");
""",
        encoding="utf-8",
    )
    res = subprocess.run(["node", str(probe)], cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    assert res.returncode == 0, f"v407 UI Node probe failed:\n{res.stderr}\n{res.stdout}"
    assert "OK_V407_UI" in res.stdout


def test_v407_opt_in_gemini_vm_visual_audit_and_sentinel_hardening(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify Opt-In Gemini VM visual audit chips/hints, <=220L retirement cap, and sentinel gate fixes."""
    import xml.etree.ElementTree as ET
    from PIL import Image as PilImage
    from agy_nexus import media as media_mod, tools_media as tmedia_mod, workflow_gate as wg_mod

    inst = str(cfg.mcp.instructions or "")
    assert "OPT-IN GEMINI VM VISUAL AUDIT" in inst and "Google-Agent" in inst and "uses extra tokens" in inst
    assert "Google-Agent" in media_mod.VISUAL_INSPECTION_HINT and "uses extra tokens" in media_mod.VISUAL_INSPECTION_HINT

    cid = "abcdef12-3456-4789-abcd-1234567890ef"
    for ph in ("ready_to_ship", "retired", "ready_to_run"):
        sa = ret_mod.build_suggested_actions(ph, target="agy-nexus-mcp", conv_id=cid, has_visuals=True)
        assert sa["options"][0]["label"] == "Yes"
        assert any("uses extra tokens" in o["label"] for o in sa["options"])
        root = ET.fromstring(sa["followup_xml"])
        assert root.tag == "ElicitationsGroup"
        assert any("uses extra tokens" in (el.attrib.get("label") or "") and (el.attrib.get("query") or "").startswith("@Agy Nexus Mcp ") for el in root)

    sa_vis = ret_mod.build_suggested_actions("inspect_visual_artifacts", target="agy-nexus-mcp", conv_id=cid)
    assert sa_vis["phase"] == "inspect_visual_artifacts"
    assert any("Have Gemini audit screenshots in VM (uses extra tokens)" == o["label"] for o in sa_vis["options"])
    assert ET.fromstring(sa_vis["followup_xml"]).tag == "ElicitationsGroup"

    # Parse ### WF-XX + prefixed H2 headings + block external symlinked WORKFLOWS.md
    sub_repo = tmp_path / "sub_wf"
    (sub_repo / "docs").mkdir(parents=True)
    (sub_repo / "docs" / "WORKFLOWS.md").write_text(
        "## Common Terms\n- **Token**: usage unit.\n\n## User Workflows\n### WF-01 — Quick Start\nTap go.\n\n## Core Workflow: WF-03 — Charts\nSee plot.\n",
        encoding="utf-8",
    )
    parsed = wb_mod.discover_project_workflows(sub_repo)
    assert [w["id"] for w in parsed["workflows"]] == ["WF-01", "WF-03"]

    outside_doc = tmp_path / "outside_secret.md"
    outside_doc.write_text("# Secret\n## WF-01 — Leak\nBad", encoding="utf-8")
    sym_repo = tmp_path / "sym_repo"
    (sym_repo / "docs").mkdir(parents=True)
    (sym_repo / "docs" / "WORKFLOWS.md").symlink_to(outside_doc)
    (sym_repo / "README.md").symlink_to(outside_doc)
    assert wb_mod.discover_project_workflows(sym_repo)["workflow_status"] == "MISSING_BASELINE"
    assert wb_mod.discover_project_workflows(sym_repo)["found"] is False
    assert wg_mod.find_workflows_doc_path(sym_repo) is None
    assert wg_mod.resolve_workflow_delta("new_project", "unchanged", "READY") == "bootstrap"
    assert wg_mod.resolve_workflow_delta("feature_update", "unchanged", "READY", create_new_project=True) == "bootstrap"

    # Pre-existing dirty docs/WORKFLOWS.md cannot satisfy cur_sha == prev_sha completion check
    dirty_repo = tmp_path / "dirty_git"
    (dirty_repo / "docs").mkdir(parents=True)
    subprocess.run(["git", "init", str(dirty_repo)], capture_output=True, check=True)
    wf_p = dirty_repo / "docs" / "WORKFLOWS.md"
    wf_p.write_text("# Docs\n## Workflow 1: WF-01 — Init\nInitial.\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(dirty_repo), "add", "."], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(dirty_repo), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "init"], capture_output=True, check=True)
    wf_p.write_text("# Docs\n## Workflow 1: WF-01 — Init\nAlready dirty before ticket.\n", encoding="utf-8")
    fp_m, fp_s = wg_mod.get_workflows_doc_fingerprint(dirty_repo)
    chk = wg_mod.verify_workflow_doc_updated_for_completion({
        "handoff_id": "dirty-01", "workspace_path": str(dirty_repo), "workflow_delta": "update_existing",
        "workflows_doc_mtime": fp_m, "workflows_doc_sha256": fp_s, "created_at": "2020-01-01T00:00:00+00:00",
    })
    assert chk["ok"] is False and chk["status"] == "WORKFLOW_DOC_NOT_UPDATED"

    # inspect_visual_artifacts response includes suggested_actions + visual_inspection_hint
    brain_dir = tmp_path / "brain"
    up_dir = brain_dir / cid / "scratch" / "uploads_20261123_120000"
    up_dir.mkdir(parents=True)
    PilImage.new("RGB", (64, 64), (30, 80, 140)).save(up_dir / "shot.png", format="PNG")
    monkeypatch.setattr(cfg, "AGY_BRAIN_DIR", brain_dir)
    monkeypatch.setattr(tmedia_mod, "AGY_BRAIN_DIR", brain_dir)
    monkeypatch.setattr(tmedia_mod, "is_unlocked", lambda p="": True)
    blocks = tmedia_mod.inspect_visual_artifacts(targets="#01", session_identifier=cid, include_thumbnails=False)
    vis_json = json.loads(blocks[0].text)
    assert vis_json["ok"] is True
    assert "Google-Agent" in vis_json["visual_inspection_hint"]
    assert vis_json["suggested_actions"]["phase"] == "inspect_visual_artifacts"

    # Line caps preserved
    assert len((SRC_DIR / "agy_nexus" / "retirement.py").read_text(encoding="utf-8").splitlines()) <= 220
    assert len((SRC_DIR / "agy_nexus" / "tools_media.py").read_text(encoding="utf-8").splitlines()) <= 500
    assert len((SRC_DIR / "agy_nexus" / "media.py").read_text(encoding="utf-8").splitlines()) <= 500
    assert len((SRC_DIR / "agy_nexus" / "workflow_gate.py").read_text(encoding="utf-8").splitlines()) <= 500

