"""tests/test_v403_table_sort_and_rail_pin.py — AGY-Nexus v4.0.3 Sortable Tables, Sidebar Pinning & Drift Match Suite."""
from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import re
import subprocess
import sys
import time

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
SCRIPTS_DIR = REPO_ROOT / "scripts"
WEB_DIR = REPO_ROOT / "web"
V9_DIR = WEB_DIR / "v9"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agy_nexus import __version__, session_tree, stats, web_routes


def _load_script_mod(name: str):
    path = SCRIPTS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_backend_project_and_session_age_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """top_projects, idle_projects, and project_sessions_series must expose last_updated_ts & relative_age."""
    now_ts = time.time()
    older_ts = now_ts - 15 * 86400
    newer_ts = now_ts - 15 * 3600 - 120
    idle_ts = now_ts - 4 * 86400

    sess_cache = {
        "sess-old-heavy": {
            "day_steps": {"2026-11-08": 900},
            "day_tokens": {"2026-11-08": 5_000_000},
            "day_tools": {"2026-11-08": 400},
            "day_cost_micros": {"2026-11-08": 12_000_000},
            "day_models": {"2026-11-08": {"carbon": 900}},
            "day_model_tokens": {"2026-11-08": {"carbon": 5_000_000}},
            "slot_1h_steps": {"2026-11-08T10": 900},
            "slot_1h_tokens": {"2026-11-08T10": 5_000_000},
            "slot_1h_cost_micros": {"2026-11-08T10": 12_000_000},
            "slot_1h_models": {"2026-11-08T10": {"carbon": 900}},
            "slot_1h_model_tokens": {"2026-11-08T10": {"carbon": 5_000_000}},
            "last_conv_model": "carbon",
        },
        "sess-new-light": {
            "day_steps": {"2026-11-23": 120},
            "day_tokens": {"2026-11-23": 800_000},
            "day_tools": {"2026-11-23": 50},
            "day_cost_micros": {"2026-11-23": 2_400_000},
            "day_models": {"2026-11-23": {"argon": 120}},
            "day_model_tokens": {"2026-11-23": {"argon": 800_000}},
            "slot_1h_steps": {"2026-11-23T09": 120},
            "slot_1h_tokens": {"2026-11-23T09": 800_000},
            "slot_1h_cost_micros": {"2026-11-23T09": 2_400_000},
            "slot_1h_models": {"2026-11-23T09": {"argon": 120}},
            "slot_1h_model_tokens": {"2026-11-23T09": {"argon": 800_000}},
            "last_conv_model": "argon",
        },
    }
    db_convs = {
        "sess-old-heavy": {"project_id": "proj-alpha", "title": "Alpha Old Heavy", "last_updated_ts": older_ts, "is_subagent": False, "step_count": 900, "workspace": "/tmp/ws-alpha"},
        "sess-new-light": {"project_id": "proj-beta", "title": "Beta Recent Run", "last_updated_ts": newer_ts, "is_subagent": False, "step_count": 120, "workspace": "/tmp/ws-beta"},
        "sess-idle-1": {"project_id": "proj-idle", "title": "Idle Chat", "last_updated_ts": idle_ts, "is_subagent": False, "step_count": 45, "workspace": "/tmp/ws-idle"},
    }
    projects_meta = {
        "proj-alpha": {"name": "Alpha", "workspace_paths": ["/tmp/ws-alpha"]},
        "proj-beta": {"name": "Beta", "workspace_paths": ["/tmp/ws-beta"]},
        "proj-idle": {"name": "Idle Gamma", "workspace_paths": ["/tmp/ws-idle"]},
    }
    tree_bundle = {
        "projects": [
            {
                "project_id": "proj-alpha",
                "project_name": "Alpha",
                "is_running": False,
                "sessions": [
                    {
                        "conversation_id": "sess-old-heavy",
                        "project_id": "proj-alpha",
                        "project_name": "Alpha",
                        "workspace_path": "/tmp/ws-alpha",
                        "title": "Alpha Old Heavy",
                        "status": "COMPLETED",
                        "is_running": False,
                        "last_updated_ts": older_ts,
                        "relative_age": "15d ago",
                        "step_count": 900,
                    }
                ],
            },
            {
                "project_id": "proj-beta",
                "project_name": "Beta",
                "is_running": True,
                "sessions": [
                    {
                        "conversation_id": "sess-new-light",
                        "project_id": "proj-beta",
                        "project_name": "Beta",
                        "workspace_path": "/tmp/ws-beta",
                        "title": "Beta Recent Run",
                        "status": "RUNNING",
                        "is_running": True,
                        "last_updated_ts": newer_ts,
                        "relative_age": "15h ago",
                        "step_count": 120,
                    },
                ],
            },
            {
                "project_id": "proj-idle",
                "project_name": "Idle Gamma",
                "is_running": False,
                "sessions": [
                    {
                        "conversation_id": "sess-idle-1",
                        "project_id": "proj-idle",
                        "project_name": "Idle Gamma",
                        "workspace_path": "/tmp/ws-idle",
                        "title": "Idle Chat",
                        "status": "IDLE",
                        "is_running": False,
                        "last_updated_ts": idle_ts,
                        "relative_age": "4d ago",
                        "step_count": 45,
                    }
                ],
            },
        ]
    }

    class _FixedDt(stats.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 23, 12, 0, 0, tzinfo=tz)

    for sub in ("cfg", "bg", "brain"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(stats, "datetime", _FixedDt)
    monkeypatch.setattr(stats, "scan_transcript_stats", lambda *_a, **_kw: sess_cache)
    monkeypatch.setattr(stats, "load_db_conversations", lambda *_a, **_kw: db_convs)
    monkeypatch.setattr(stats, "load_projects_meta", lambda *_a, **_kw: projects_meta)
    monkeypatch.setattr(session_tree, "build_project_session_tree", lambda *_a, **_kw: tree_bundle)
    monkeypatch.setattr(stats, "get_code_health_summary", lambda *_a, **_kw: {"version": {"installed": __version__, "status": "up_to_date"}})
    monkeypatch.setattr(stats, "merge_and_persist_cost_ledger", lambda *_a, **_kw: {"entries": {}})
    monkeypatch.setattr(stats, "load_cost_ledger", lambda *_a, **_kw: {"entries": {}})

    fleet = stats.build_nexus_stats_bundle(
        data_dir=tmp_path, brain_dir=tmp_path / "brain", db_file=tmp_path / "missing.db",
        agy_config_dir=tmp_path / "cfg", bg_dir=tmp_path / "bg",
        timeframe="month", horizon_mode="to_date", anchor_date="2026-11-23", include_ascii=False,
    )
    hier = fleet["project_hierarchy"]
    top = {p["project_id"]: p for p in hier["top_projects"]}
    assert top["proj-alpha"]["last_updated_ts"] == pytest.approx(older_ts)
    assert top["proj-alpha"]["relative_age"] == "15d ago"
    assert top["proj-beta"]["last_updated_ts"] == pytest.approx(newer_ts)
    assert top["proj-beta"]["relative_age"] == "15h ago"
    beta_cost = float(top["proj-beta"]["sessions"][0]["window_cost_usd"])
    assert beta_cost > 0

    idle = {p["project_id"]: p for p in hier["idle_projects"]}
    assert "proj-idle" in idle
    assert idle["proj-idle"]["last_updated_ts"] == pytest.approx(idle_ts)
    assert idle["proj-idle"]["relative_age"] == "4d ago"

    scoped_bundle = stats.build_nexus_stats_bundle(
        data_dir=tmp_path, brain_dir=tmp_path / "brain", db_file=tmp_path / "missing.db",
        agy_config_dir=tmp_path / "cfg", bg_dir=tmp_path / "bg",
        timeframe="month", horizon_mode="to_date", anchor_date="2026-11-23",
        project_id="proj-beta", include_ascii=False,
    )
    scoped = scoped_bundle["project_sessions_series"]
    assert scoped_bundle["project_scope"]["project_id"] == "proj-beta"
    s0 = scoped["sessions"][0]
    assert s0["conversation_id"] == "sess-new-light"
    assert s0["last_updated_ts"] == pytest.approx(newer_ts)
    assert s0["relative_age"] == "15h ago"
    assert s0["status"] == "RUNNING" and s0["is_running"] is True
    assert s0["window_steps"] == 120 and s0["window_tokens"] == 800_000 and s0["window_cost_usd"] == pytest.approx(beta_cost)


def test_drift_script_ignores_legacy_opus5_and_flags_real_opus55_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    """check_model_drift._check_public_rate_feeds must ignore claude-opus-5 while catching claude-opus-5-5 drift."""
    cmd = _load_script_mod("check_model_drift")
    assert "opus-5" not in cmd._PUBLIC_FEED_MODEL_TOKENS
    assert "sonnet-5" not in cmd._PUBLIC_FEED_MODEL_TOKENS
    assert "opus-5-5" in cmd._PUBLIC_FEED_MODEL_TOKENS and "sonnet-5-5" in cmd._PUBLIC_FEED_MODEL_TOKENS

    def fake_get(url: str, timeout: float = 4.0):
        if "models.dev" in url:
            return True, {
                "anthropic": {
                    "models": {
                        "claude-opus-5": {"cost": {"input": 5.0, "output": 25.0}},
                        "claude-sonnet-5": {"cost": {"input": 3.0, "output": 15.0}},
                        "claude-opus-5-5": {"cost": {"input": 4.0, "output": 20.0}},
                        "claude-sonnet-5-5": {"cost": {"input": 2.0, "output": 10.0}},
                    }
                }
            }, ""
        return True, {"claude-opus-5": {}, "claude-opus-5-5": {}, "gemini-4-carbon": {}}, ""

    monkeypatch.setattr(cmd, "_http_get_json", fake_get)
    sources, findings = cmd._check_public_rate_feeds({}, "2026-11-23")
    assert findings == []
    assert sources["models_dev"]["matched_models"] == 2
    assert sources["litellm"]["matched_models"] == 2

    def fake_get_drifted(url: str, timeout: float = 4.0):
        if "models.dev" in url:
            return True, {
                "anthropic": {
                    "models": {
                        "claude-opus-5-5": {"cost": {"input": 4.5, "output": 22.0}},
                    }
                }
            }, ""
        return True, {}, ""

    monkeypatch.setattr(cmd, "_http_get_json", fake_get_drifted)
    _src2, findings2 = cmd._check_public_rate_feeds({}, "2026-11-23")
    assert len(findings2) == 1
    assert "claude-opus-5-5" in findings2[0]["model"]


def test_v9_table_sort_all_4_tables_swatch_and_focus_preservation(tmp_path: Path) -> None:
    """Verify V9.TableSort across Top Projects (pre-slice), Project Sessions (Age/Status), Models & Subagents."""
    probe = tmp_path / "v403_table_sort_probe.cjs"
    probe.write_text(
        """
const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

function parseButtons(html) {
  const ths = [];
  const re = /<th\\b([^>]*)>([\\s\\S]*?)<\\/th>/g;
  let m;
  while ((m = re.exec(String(html || ""))) !== null) {
    const thAttrs = m[1] || "";
    const inner = m[2] || "";
    const ariaM = /aria-sort="([^"]+)"/.exec(thAttrs);
    const btnM = /<button\\b([^>]*)>([\\s\\S]*?)<\\/button>/.exec(inner);
    let btn = null;
    if (btnM) {
      const bAttrs = btnM[1] || "";
      const bInner = btnM[2] || "";
      const lblM = /<span class="v9-th-lbl">([\\s\\S]*?)<\\/span>/.exec(bInner);
      const tbl = (/data-sort-table="([^"]+)"/.exec(bAttrs) || [])[1] || "";
      const key = (/data-sort-key="([^"]+)"/.exec(bAttrs) || [])[1] || "";
      const defDir = (/data-default-dir="([^"]+)"/.exec(bAttrs) || [])[1] || "desc";
      btn = {
        attrs: { "data-sort-table": tbl, "data-sort-key": key, "data-default-dir": defDir },
        getAttribute(k) { return this.attrs[k] ?? null; },
        closest(sel) { return sel.includes(`data-sort-table="${tbl}"`) ? this : null; },
        querySelector(sel) { return sel === ".v9-th-lbl" ? { textContent: lblM ? lblM[1] : "" } : null; },
        focus() { doc.activeElement = this; },
      };
    }
    const attrs = {};
    if (ariaM) attrs["aria-sort"] = ariaM[1];
    ths.push({
      attrs,
      btn,
      setAttribute(k, v) { this.attrs[k] = String(v); },
      removeAttribute(k) { delete this.attrs[k]; },
      getAttribute(k) { return this.attrs[k] ?? null; },
      querySelector(sel) {
        if (!btn) return null;
        if (sel.includes(`data-sort-table="${btn.attrs["data-sort-table"]}"`) &&
            (!sel.includes("data-sort-key") || sel.includes(`data-sort-key="${btn.attrs["data-sort-key"]}"`))) {
          return btn;
        }
        return null;
      },
    });
  }
  return ths;
}

function makeTableEl(tableId, theadEl, tbodyEl) {
  const listeners = {};
  const tbl = {
    attrs: { "data-v9-table": tableId },
    dataset: {},
    tHead: theadEl,
    addEventListener(type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
    contains(target) {
      if (!target) return false;
      return theadEl._ths.some((t) => t.btn === target);
    },
    querySelectorAll: () => [],
    querySelector(sel) {
      for (const th of theadEl._ths) {
        if (th.btn) {
          const t = th.btn.attrs["data-sort-table"];
          const k = th.btn.attrs["data-sort-key"];
          if (sel === `[data-sort-table="${t}"][data-sort-key="${k}"]`) return th.btn;
        }
      }
      return null;
    },
    dispatchClickOnHeader(colKey) {
      const th = theadEl._ths.find((t) => t.btn && t.btn.attrs["data-sort-key"] === colKey);
      assert.ok(th && th.btn, `Missing sortable header key ${colKey} on table ${tableId}`);
      doc.activeElement = th.btn;
      for (const fn of listeners.click || []) {
        fn({ target: th.btn, stopPropagation() {} });
      }
    },
  };
  tbodyEl._ownerTable = tbl;
  return tbl;
}

function makeEl(id) {
  let html = "";
  const listeners = {};
  const el = {
    id,
    dataset: {},
    style: {},
    classList: { toggle() {}, add() {}, remove() {}, contains() { return false; } },
    setAttribute() {},
    removeAttribute() {},
    get innerHTML() { return html; },
    set innerHTML(v) {
      html = String(v || "");
      el._ths = parseButtons(html);
      // When #v9ProjTableWrap receives a mounted table HTML string, track its table/thead/tbody nodes.
      const tblM = /<table\\b[^>]*data-v9-table="([^"]+)"/.exec(html);
      if (tblM) {
        const theadM = /<thead[^>]*>([\\s\\S]*?)<\\/thead>/.exec(html);
        const bodyIdM = /<tbody\\b[^>]*id="([^"]+)"[^>]*>([\\s\\S]*?)<\\/tbody>/.exec(html);
        const thNode = makeEl(id + "_thead");
        thNode.innerHTML = theadM ? theadM[1] : "";
        const tbNode = bodyIdM ? makeEl(bodyIdM[1]) : makeEl(id + "_tbody");
        tbNode.innerHTML = bodyIdM ? bodyIdM[2] : "";
        els[tbNode.id] = tbNode;
        el._mountedTable = makeTableEl(tblM[1], thNode, tbNode);
      }
    },
    _ths: [],
    _mountedTable: null,
    _ownerTable: null,
    textContent: "",
    disabled: false,
    hidden: false,
    closest(sel) {
      if (sel === "table") return el._ownerTable;
      return null;
    },
    addEventListener(type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
    querySelectorAll(sel) {
      if (sel === "th") return el._ths;
      return [];
    },
    querySelector(sel) {
      if (el._mountedTable && sel.includes("data-v9-table")) {
        const tid = el._mountedTable.attrs["data-v9-table"];
        if (sel.includes(`data-v9-table="${tid}"`)) return el._mountedTable;
      }
      for (const th of el._ths) {
        if (th.btn) {
          const t = th.btn.attrs["data-sort-table"];
          const k = th.btn.attrs["data-sort-key"];
          if (sel === `[data-sort-table="${t}"][data-sort-key="${k}"]` || sel === `[data-sort-table="${t}"]`) {
            return th.btn;
          }
        }
      }
      return null;
    },
  };
  return el;
}

const els = {};
for (const id of [
  "v9KpiGrid",
  "v9ProjTableWrap", "v9ProjFoot", "v9ProjPlotTitle", "v9ProjPlotSub", "v9ProjScopeSelect",
  "v9ModelPlotSub", "v9ModelTableHead", "v9ModelTableBody",
  "v9SubPlotSub", "v9SubagentTableHead", "v9SubagentTableBody",
  "v9SortStatus", "v9WireSub", "v9WireClientHost", "v9WireCallsHost",
  "v9HealthDrawerTitle", "v9HealthSummary", "v9HealthBody",
  "v9HeatHeading", "v9PeriodTriggerLabel", "v9PeriodPickerBtn",
]) els[id] = makeEl(id);

const modelTable = makeTableEl("models", els.v9ModelTableHead, els.v9ModelTableBody);
const subTable = makeTableEl("subagents", els.v9SubagentTableHead, els.v9SubagentTableBody);
els.v9ModelTableHead.querySelectorAll = (s) => (s === "th" ? els.v9ModelTableHead._ths : []);

const doc = {
  activeElement: null,
  body: { dataset: {} },
  documentElement: { setAttribute() {}, dataset: {} },
  getElementById: (id) => els[id] || null,
  querySelectorAll: () => [],
  querySelector: () => null,
};

const win = {
  innerWidth: 1440,
  location: { search: "", pathname: "/web", hostname: "localhost", hash: "" },
  history: { replaceState() {} },
  AgyPalettes: { hexToRgba: (c) => c, resolveSeriesColors: (n) => Array.from({ length: n }, (_, i) => `#c${i}`) },
  localStorage: { getItem: () => null, setItem() {} },
  sessionStorage: { getItem: () => null, setItem() {}, removeItem() {} },
};

const ctx = {
  window: win,
  document: doc,
  localStorage: win.localStorage,
  sessionStorage: win.sessionStorage,
  Intl,
  URLSearchParams,
};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync("web/v9/v9_state.js", "utf-8"), ctx);
const V9 = ctx.window.AgyV9;
Object.assign(V9, {
  escHtml: (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"),
  fmtNum: (n) => String(Math.round(Number(n || 0))),
  fmtTokens: (n) => `${Math.round(Number(n || 0) / 1000)}K`,
  fmtUsd: (n) => `$${Number(n || 0).toFixed(2)}`,
  projectDisplayName: (p) => String(p?.project_name || p?.project_id || ""),
  isDemoMode: () => false,
  PALETTE: ["#111111", "#222222", "#333333", "#444444", "#555555", "#666666"],
});
vm.runInContext(fs.readFileSync("web/v9/v9_table_sort.js", "utf-8"), ctx);
vm.runInContext(fs.readFileSync("web/v9/v9_project_view.js", "utf-8"), ctx);
vm.runInContext(fs.readFileSync("web/v9/v9_analytics.js", "utf-8"), ctx);

// 1. Unit checks for V9.TableSort
assert.strictEqual(V9.TableSort.parseRelativeAgeSeconds("15h ago"), 15 * 3600);
assert.strictEqual(V9.TableSort.parseRelativeAgeSeconds("15d ago"), 15 * 86400);
assert.ok(V9.TableSort.statusRank({ is_running: true, status: "RUNNING" }) > V9.TableSort.statusRank({ status: "COMPLETED" }));

// 2. Top Projects: >14 projects — 15th project has newest age ("1h ago") and lowest steps
const projects = [];
for (let i = 0; i < 15; i++) {
  projects.push({
    project_id: `p-${i}`,
    project_name: i === 14 ? "Zebra Fresh" : `Proj ${String(i).padStart(2, "0")}`,
    last_updated_ts: i === 14 ? 2000000000 : 1900000000 - i * 86400,
    relative_age: i === 14 ? "1h ago" : `${i + 2}d ago`,
    active_sessions_count: 15 - i,
    share_pct: i === 14 ? 0.5 : 8 - i * 0.4,
    window_steps: i === 14 ? 5 : 1000 - i * 40,
    window_tokens: i === 14 ? 5000 : 500000 - i * 20000,
    window_cost_usd: i === 14 ? 0.25 : 40 - i,
  });
}
const fleetBundle = { project_hierarchy: { top_projects: projects, idle_projects: [], active_projects_count: 15, idle_projects_count: 0 } };
V9.state.bundle = fleetBundle;
V9.ProjectView.renderTopProjectsTable(fleetBundle, {});
const projTbl = els.v9ProjTableWrap._mountedTable;
assert.ok(projTbl && projTbl.tHead.innerHTML.includes(">Age<"), "Top Projects must render dedicated Age column");
assert.ok(!projTbl.tHead.innerHTML.includes('aria-sort="none"'), "Inactive columns must omit aria-sort");
assert.strictEqual(projTbl.tHead._ths.find((t) => t.btn?.attrs["data-sort-key"] === "steps").attrs["aria-sort"], "descending");
assert.ok(!els.v9ProjTableBody.innerHTML.includes("Zebra Fresh"), "15th project excluded under default Steps sort slice");

// Sort Top Projects by Age desc (newest first) -> surfaces 15th project to row 1 BEFORE slice(0,14)!
projTbl.dispatchClickOnHeader("age");
assert.strictEqual(V9.TableSort.getSort("projects").key, "age");
assert.strictEqual(V9.TableSort.getSort("projects").dir, "desc");
assert.ok(els.v9ProjTableBody.innerHTML.indexOf("Zebra Fresh") < els.v9ProjTableBody.innerHTML.indexOf("Proj 00"));
assert.strictEqual(projTbl.tHead._ths.find((t) => t.btn?.attrs["data-sort-key"] === "age").attrs["aria-sort"], "descending");
assert.strictEqual(doc.activeElement.attrs["data-sort-key"], "age", "Focus must remain on clicked Age header button");
assert.ok(els.v9SortStatus.textContent.includes("Age") && els.v9SortStatus.textContent.includes("descending"));

// 3. Project Sessions: 15h ago lower-step session buried under 15d ago heavy session
const scopedBundle = {
  project_scope: { project_id: "proj-x", project_name: "Proj X" },
  project_sessions_series: {
    project_id: "proj-x",
    project_name: "Proj X",
    sessions: [
      { conversation_id: "s-heavy", title: "Old Heavy", relative_age: "15d ago", window_steps: 900, window_tokens: 900000, window_cost_usd: 45, status: "COMPLETED", is_running: false },
      { conversation_id: "s-fresh", title: "Fresh Active", relative_age: "15h ago", window_steps: 40, window_tokens: 120000, window_cost_usd: 2.5, status: "RUNNING", is_running: true },
    ],
  },
};
V9.state.bundle = scopedBundle;
V9.ProjectView.renderProjectSessionsCard(scopedBundle, {});
const sessTbl = els.v9ProjTableWrap._mountedTable;
assert.ok(els.v9ProjSessionTableBody.innerHTML.indexOf("Old Heavy") < els.v9ProjSessionTableBody.innerHTML.indexOf("Fresh Active"));
assert.ok(els.v9ProjSessionTableBody.innerHTML.includes("15h ago") && els.v9ProjSessionTableBody.innerHTML.includes("15d ago"));

sessTbl.dispatchClickOnHeader("age");
assert.ok(els.v9ProjSessionTableBody.innerHTML.indexOf("Fresh Active") < els.v9ProjSessionTableBody.innerHTML.indexOf("Old Heavy"));
assert.ok(els.v9ProjSessionTableBody.innerHTML.includes(`style="background:${V9.getSeriesColor(1)}"`), "Fresh Active must keep canonical swatch index 1");

// Sort by Status desc (RUNNING > COMPLETED) -> toggle to asc (COMPLETED > RUNNING)
sessTbl.dispatchClickOnHeader("status");
assert.ok(els.v9ProjSessionTableBody.innerHTML.indexOf("Fresh Active") < els.v9ProjSessionTableBody.innerHTML.indexOf("Old Heavy"));
sessTbl.dispatchClickOnHeader("status");
assert.ok(els.v9ProjSessionTableBody.innerHTML.indexOf("Old Heavy") < els.v9ProjSessionTableBody.innerHTML.indexOf("Fresh Active"));

// 4. Model Workload & Subagent Workload sorting preserving canonical swatches
const analyticsBundle = {
  summary: { period_label: "MTD", days: 23, active_days: 10 },
  model_usage_vs_target: [
    { key: "carbon", label: "Gemini 4 Carbon", pool: "google", actual_calls: 100, actual_pct: 60, target_pct: 50, delta_pct: 10, tokens: 200000, est_cost_usd: 2.0 },
    { key: "argon", label: "Gemini 4 Argon", pool: "google", actual_calls: 50, actual_pct: 40, target_pct: 50, delta_pct: -10, tokens: 800000, est_cost_usd: 9.0 },
  ],
  subagent_list: [
    { role: "flash-scout", model_label: "Gemini 3.8 Flash", runs: 8, tokens: 100000, est_cost_usd: 0.4, share_pct: 70 },
    { role: "argon-sentinel", model_label: "Gemini 4 Argon", runs: 2, tokens: 400000, est_cost_usd: 3.1, share_pct: 30 },
  ],
  project_hierarchy: { top_projects: projects, idle_projects: [] },
};
V9.state.bundle = analyticsBundle;
V9.Analytics.renderAnalytics(analyticsBundle, () => {}, {});
assert.ok(els.v9ModelTableBody.innerHTML.indexOf("Gemini 4 Carbon") < els.v9ModelTableBody.innerHTML.indexOf("Gemini 4 Argon"));
modelTable.dispatchClickOnHeader("cost");
assert.ok(els.v9ModelTableBody.innerHTML.indexOf("Gemini 4 Argon") < els.v9ModelTableBody.innerHTML.indexOf("Gemini 4 Carbon"));
assert.ok(els.v9ModelTableBody.innerHTML.includes(`style="background:${V9.getSeriesColor(1)}"`), "Argon preserves origIdx 1 color");

assert.ok(els.v9SubagentTableBody.innerHTML.indexOf("flash-scout") < els.v9SubagentTableBody.innerHTML.indexOf("argon-sentinel"));
subTable.dispatchClickOnHeader("tokens");
assert.ok(els.v9SubagentTableBody.innerHTML.indexOf("argon-sentinel") < els.v9SubagentTableBody.innerHTML.indexOf("flash-scout"));
assert.ok(els.v9SubagentTableBody.innerHTML.includes(`style="background:${V9.getSeriesColor(1)}"`), "argon-sentinel preserves origIdx 1 color");

// Re-render same static subagent table with 4 rows and confirm WeakMap updates rowCountFn (no stale "2 rows" closure)
const expandedBundle = Object.assign({}, analyticsBundle, {
  subagent_list: analyticsBundle.subagent_list.concat([
    { role: "flash-surgeon", model_label: "Gemini 3.8 Flash", runs: 5, tokens: 250000, est_cost_usd: 0.9, share_pct: 10 },
    { role: "argon-surgeon", model_label: "Gemini 4 Argon", runs: 1, tokens: 90000, est_cost_usd: 0.7, share_pct: 5 },
  ]),
});
V9.state.bundle = expandedBundle;
V9.Analytics.renderAnalytics(expandedBundle, () => {}, {});
subTable.dispatchClickOnHeader("cost");
assert.ok(els.v9SortStatus.textContent.includes("4 rows"), "WeakMap bindSortHeaders must announce updated 4 rows, got: " + els.v9SortStatus.textContent);
""",
        encoding="utf-8",
    )
    res = subprocess.run(["node", str(probe)], cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    assert res.returncode == 0, f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"


def test_v9_hierarchy_desktop_pinning_and_burger_panel_icons(tmp_path: Path) -> None:
    """Verify >=1100px desktop pinning (.is-rail-pinned, ◧ vs ☰ icons, persistent rail, <1100px overlay)."""
    probe = tmp_path / "v403_rail_pin_probe.cjs"
    probe.write_text(
        """
const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

function makeClassList(initial) {
  const set = new Set(initial || []);
  return {
    add(...args) { for (const a of args) if (a) set.add(a); },
    remove(...args) { for (const a of args) set.delete(a); },
    toggle(c, force) {
      if (force === true) set.add(c);
      else if (force === false) set.delete(c);
      else if (set.has(c)) set.delete(c);
      else set.add(c);
    },
    contains(c) { return set.has(c); },
  };
}

function makeSubIcon(cls) {
  return { classList: makeClassList([cls]) };
}

function makeEl(id, extra) {
  const attrs = {};
  const listeners = {};
  let html = "";
  const el = Object.assign({
    id,
    attrs,
    dataset: {},
    style: {},
    hidden: false,
    textContent: "",
    classList: makeClassList([]),
    setAttribute(k, v) { attrs[k] = String(v); },
    removeAttribute(k) { delete attrs[k]; },
    getAttribute(k) { return attrs[k] ?? null; },
    focus() { if (ctx && ctx.document) ctx.document.activeElement = this; },
    addEventListener(t, fn) { (listeners[t] = listeners[t] || []).push(fn); },
    click() { for (const fn of listeners.click || []) fn({ stopPropagation() {}, preventDefault() {}, target: this }); },
    querySelectorAll(sel) {
      const m = /\\[([^=\\]]+)/.exec(sel);
      if (m && html.includes(m[1])) {
        const attrName = m[1];
        const re = new RegExp(`${attrName}="([^"]+)"`, "g");
        const found = [];
        let x;
        while ((x = re.exec(html)) !== null) {
          const val = x[1];
          const b = makeEl(attrName + "_" + val);
          b.setAttribute(attrName, val);
          found.push(b);
          if (attrName === "data-rail-analytics") el._analyticsBtns.push(b);
        }
        return found;
      }
      return [];
    },
    querySelector: () => null,
    contains: () => false,
    _analyticsBtns: [],
    get innerHTML() { return html; },
    set innerHTML(v) {
      html = String(v || "");
      el._analyticsBtns = [];
    },
  }, extra || {});
  return el;
}

const burgerIcon = makeSubIcon("v9-menu-icon-burger");
const panelIcon = makeSubIcon("v9-menu-icon-panel");
panelIcon.classList.add("hidden");

const els = {
  v9AppShell: makeEl("v9AppShell"),
  v9NavRail: makeEl("v9NavRail", {
    querySelector(sel) {
      if (sel === "#v9RailPinBtn") return els.v9RailPinBtn;
      if (sel === "#v9RailCloseBtn") return els.v9RailCloseBtn;
      return null;
    },
    contains(t) { return t === els.v9RailPinBtn || t === els.v9RailCloseBtn; },
  }),
  v9WsBackdrop: makeEl("v9WsBackdrop"),
  v9MenuBtn: makeEl("v9MenuBtn", {
    querySelector(sel) {
      if (sel === ".v9-menu-icon-burger") return burgerIcon;
      if (sel === ".v9-menu-icon-panel") return panelIcon;
      return null;
    },
  }),
  v9RailPinBtn: makeEl("v9RailPinBtn"),
  v9RailCloseBtn: makeEl("v9RailCloseBtn"),
};

const store = { nexus_v9_rail_pinned: "1" };
let openedProjAnalytics = 0;
let chartResizeCalls = 0;
const win = {
  innerWidth: 1440,
  location: { search: "", pathname: "/web", hostname: "localhost", hash: "" },
  history: { replaceState() {} },
  localStorage: {
    getItem(k) { return Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null; },
    setItem(k, v) { store[k] = String(v); },
  },
  addEventListener() {},
  requestAnimationFrame(cb) { cb(); },
  AgyV9: {},
};

const ctx = {
  window: win,
  document: {
    activeElement: null,
    body: { dataset: {} },
    documentElement: { setAttribute() {}, dataset: {} },
    getElementById: (id) => els[id] || null,
    addEventListener() {},
    querySelector: () => null,
  },
  localStorage: win.localStorage,
  sessionStorage: { getItem: () => null, setItem() {}, removeItem() {} },
  requestAnimationFrame: win.requestAnimationFrame,
  URLSearchParams,
};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync("web/v9/v9_state.js", "utf-8"), ctx);
const V9 = ctx.window.AgyV9;
Object.assign(V9, {
  escHtml: (s) => String(s == null ? "" : s),
  fmtNum: (n) => String(n || 0),
  projectDisplayName: (p) => p.project_name || p.project_id,
  PALETTE: ["#111111", "#222222", "#333333"],
  Charts: { scheduleRealign: () => { chartResizeCalls++; } },
  state: Object.assign(V9.state, {
    demoMode: false,
    passphrase: "",
    surfaceView: "analytics",
    bundle: {
      project_hierarchy: {
        top_projects: [{ project_id: "proj-1", project_name: "Proj 1", share_pct: 100, window_steps: 50, sessions: [] }],
        idle_projects: [],
      },
    },
  }),
});
vm.runInContext(fs.readFileSync("web/v9/v9_hierarchy.js", "utf-8"), ctx);

const actions = { openProjectAnalytics: () => { openedProjAnalytics++; } };
V9.Hierarchy.wireRailEvents(actions);

// 0. Locked screen must NEVER show or pin the rail even if localStorage === "1"
V9.Hierarchy.syncRailLayout();
assert.ok(!els.v9AppShell.classList.contains("is-rail-pinned"));
assert.ok(!els.v9NavRail.classList.contains("is-pinned"));

// 1. Unlocked desktop (1440px) with localStorage.nexus_v9_rail_pinned === "1"
V9.state.demoMode = true;
V9.Hierarchy.syncRailLayout({ forceRender: true });
assert.strictEqual(V9.Hierarchy.isDesktopPinned(), true);
assert.ok(els.v9AppShell.classList.contains("is-rail-pinned"));
assert.ok(els.v9NavRail.classList.contains("is-pinned"));
assert.strictEqual(els.v9NavRail.attrs["aria-hidden"], "false");
assert.strictEqual(els.v9NavRail.attrs.role, undefined, "Docked rail must strip role=dialog");
assert.strictEqual(els.v9NavRail.attrs["aria-modal"], undefined);
assert.ok(burgerIcon.classList.contains("hidden"), "Hamburger icon hidden when pinned");
assert.ok(!panelIcon.classList.contains("hidden"), "Docked panel icon visible when pinned");
assert.ok(els.v9NavRail.innerHTML.includes('id="v9RailPinBtn"') && els.v9NavRail.innerHTML.includes('aria-pressed="true"'));

// Clicking a project analytics icon in pinned rail keeps pinned rail open
assert.ok(els.v9NavRail._analyticsBtns.length === 1);
els.v9NavRail._analyticsBtns[0].click();
assert.strictEqual(openedProjAnalytics, 1);
assert.ok(els.v9NavRail.classList.contains("is-pinned"), "Pinned rail must stay docked after project selection");

// 2. Mobile / tablet (< 1100px) demotes to overlay + hamburger icon WITHOUT overwriting localStorage
win.innerWidth = 900;
V9.Hierarchy.syncRailLayout();
assert.strictEqual(V9.Hierarchy.isDesktopPinned(), false);
assert.ok(!els.v9AppShell.classList.contains("is-rail-pinned"));
assert.ok(!els.v9NavRail.classList.contains("is-pinned"));
assert.ok(!els.v9NavRail.classList.contains("is-drawer-open"));
assert.ok(!burgerIcon.classList.contains("hidden"), "Mobile <1100px must show hamburger SVG");
assert.ok(panelIcon.classList.contains("hidden"));
assert.strictEqual(store.nexus_v9_rail_pinned, "1", "Narrow resize must preserve saved pin preference");

// Opening overlay and clicking project closes drawer + sets role=dialog
V9.Hierarchy.applyRailVisibility(true);
assert.ok(els.v9NavRail.classList.contains("is-drawer-open"));
assert.strictEqual(els.v9NavRail.attrs.role, "dialog");
assert.strictEqual(els.v9NavRail.attrs["aria-modal"], "true");
els.v9NavRail._analyticsBtns[0].click();
assert.ok(!els.v9NavRail.classList.contains("is-drawer-open"), "Unpinned overlay drawer must close after selection");

// 3. Resizing back to desktop (>= 1100px) restores pinned rail; clicking #v9MenuBtn unpins + closes + shows hamburger
win.innerWidth = 1440;
V9.Hierarchy.syncRailLayout();
assert.strictEqual(V9.Hierarchy.isDesktopPinned(), true);
els.v9MenuBtn.click();
assert.strictEqual(store.nexus_v9_rail_pinned, "0");
assert.strictEqual(V9.Hierarchy.isDesktopPinned(), false);
assert.ok(!els.v9AppShell.classList.contains("is-rail-pinned"));
assert.ok(!els.v9NavRail.classList.contains("is-drawer-open"));
assert.ok(!burgerIcon.classList.contains("hidden"));
assert.ok(panelIcon.classList.contains("hidden"));
assert.ok(chartResizeCalls >= 1);

// 4. Pin then unpin with focus on #v9RailPinBtn keeps focus inside modal dialog across DOM rebuild
V9.Hierarchy.toggleRailPin();
assert.strictEqual(V9.Hierarchy.isDesktopPinned(), true);
ctx.document.activeElement = els.v9RailPinBtn;
V9.Hierarchy.toggleRailPin();
assert.strictEqual(els.v9NavRail.attrs.role, "dialog");
assert.strictEqual(ctx.document.activeElement, els.v9RailPinBtn, "Focus must stay inside modal dialog after unpinning");
""",
        encoding="utf-8",
    )
    res = subprocess.run(["node", str(probe)], cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    assert res.returncode == 0, f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"


def test_v403_budgets_pwa_assets_no_pictographs_and_workflows() -> None:
    """Verify <=500L module budgets, 0 !important, zero pictographs in web/v9, PWA parity & WORKFLOWS.md v4.0.3."""
    for js_path in sorted(V9_DIR.glob("*.js")):
        lines = js_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) <= 500, f"{js_path.name} exceeded 500L ({len(lines)}L)"
        txt = "\n".join(lines)
        assert not re.search(r"[🔒✦⬇◀▶✓✕]", txt), f"Forbidden UI pictograph found in {js_path.name}"

    for css_path in sorted(V9_DIR.glob("*.css")):
        txt = css_path.read_text(encoding="utf-8")
        assert len(txt.splitlines()) <= 500, f"{css_path.name} exceeded 500L"
        assert "!important" not in txt, f"!important forbidden in {css_path.name}"

    assert "v9/v9_table_sort.js" in web_routes.PWA_ASSETS
    assert "v9/v9_tables_and_rail.css" in web_routes.PWA_ASSETS
    sw_txt = (WEB_DIR / "sw.js").read_text(encoding="utf-8")
    assert f'CACHE_NAME = "agy-nexus-v{__version__}"' in sw_txt
    assert f"v9/v9_table_sort.js?v={__version__}" in sw_txt
    assert f"v9/v9_tables_and_rail.css?v={__version__}" in sw_txt
    assert (WEB_DIR / "index.html").read_text(encoding="utf-8") == (V9_DIR / "index.html").read_text(encoding="utf-8")

    wf_txt = (REPO_ROOT / "docs" / "WORKFLOWS.md").read_text(encoding="utf-8")
    assert "Workflow 6:" in wf_txt and "v4.0.3" in wf_txt
    assert "Multi-Column Table Sorting" in wf_txt
    assert "Desktop Rail Pinning" in wf_txt
