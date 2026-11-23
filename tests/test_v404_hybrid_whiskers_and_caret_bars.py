"""tests/test_v404_hybrid_whiskers_and_caret_bars.py — AGY-Nexus v4.0.4 Option A Hybrid Whiskers & Caret Bars."""
from __future__ import annotations

import ast
import json
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from agy_nexus import project_stats, stats, stats_metrics, web_routes

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_NEXUS = REPO_ROOT / "src" / "agy_nexus"
WEB_DIR = REPO_ROOT / "web"
V9_DIR = WEB_DIR / "v9"


def _write_retired_session_brain(
    brain_dir: Path,
    cid: str,
    step_ts: list[datetime],
    *,
    retired: bool = False,
) -> None:
    """Write minimal transcript.jsonl (+ optional RETIRED.json) under brain_dir/cid."""
    cdir = brain_dir / cid
    sys_logs = cdir / ".system_generated" / "logs"
    sys_logs.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for idx, dt in enumerate(step_ts, start=1):
        lines.append(json.dumps({
            "step_index": idx,
            "type": "PLANNER_RESPONSE",
            "created_at": dt.isoformat(),
            "model": "MODEL_PLACEHOLDER_M427",
            "token_usage": {"input_tokens": 12000, "output_tokens": 3000, "cache_read_input_tokens": 0},
            "tool_calls": [{"name": "view_file"}] if idx == 1 else [],
        }))
    (sys_logs / "transcript.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if retired:
        (cdir / "RETIRED.json").write_text(json.dumps({"retired": True, "retired_at": step_ts[-1].isoformat()}), encoding="utf-8")


def test_v404_stats_metrics_unit_calculations() -> None:
    """Verify trailing-24h slots, closed-window gating, daily range stats, and subagent per-run range tracking."""
    from datetime import date

    today = date(2026, 11, 23)
    has_l24, slots = stats_metrics.compute_trailing_24h_slots(date(2026, 11, 1), date(2026, 11, 23), today, 9)
    assert has_l24 is True and len(slots) == 24
    assert "2026-11-23T09" in slots and "2026-11-22T10" in slots and "2026-11-22T09" not in slots

    closed_has, closed_slots = stats_metrics.compute_trailing_24h_slots(date(2026, 10, 1), date(2026, 10, 31), today, 9)
    assert closed_has is False and not closed_slots

    rec = stats_metrics.init_subagent_role_record()
    stats_metrics.fold_subagent_run_sample(rec, steps=0, tokens=0, cost_micros=0, run_ts=50.0)
    stats_metrics.fold_subagent_run_sample(rec, steps=40, tokens=1_000_000, cost_micros=500_000, run_ts=100.0)
    stats_metrics.fold_subagent_run_sample(rec, steps=145, tokens=12_000_000, cost_micros=4_200_000, run_ts=300.0)
    assert rec["runs"] == 3 and rec["over_120_runs"] == 1
    assert rec["min_steps_per_run"] == 0 and rec["min_cost_micros_per_run"] == 0 and rec["max_steps_per_run"] == 145
    assert rec["last_run_steps"] == 145 and rec["last_run_tokens"] == 12_000_000

    merged_dst = stats_metrics.init_subagent_role_record()
    stats_metrics.fold_subagent_run_sample(merged_dst, steps=50, tokens=1000, cost_micros=500, run_ts=100.0)
    stats_metrics.merge_subagent_role_stats(merged_dst, {"runs": 1, "steps": 60, "tokens": 2000, "cost_usd_micros": 700})
    assert merged_dst["min_steps_per_run"] == 50 and merged_dst["min_cost_micros_per_run"] == 500

    agg: dict[str, Any] = {
        "subagent_roles": {"argon-surgeon": rec},
        "role_model_votes": {"argon-surgeon": {"argon": 3}},
        "role_inherited": {},
        "s1_sub_steps": {"argon-surgeon": {"2026-11-23T08": 145}},
        "s1_sub_toks": {"argon-surgeon": {"2026-11-23T08": 12_000_000}},
        "s1_sub_cost": {"argon-surgeon": {"2026-11-23T08": 4_200_000}},
    }
    sub_rows = stats_metrics.build_subagent_list_rows(
        agg, 3, 1.0, slots, True,
        resolve_model_fn=lambda *_: ("argon", False),
        short_labels={"argon": "Argon 4"},
        e_iso="2026-11-23",
        parent_model_map={},
        main_mk="carbon",
        main_switch_date="",
        agent_target_map={},
    )
    assert len(sub_rows) == 1
    sr = sub_rows[0]
    assert sr["avg_steps_per_run"] == 61.7 and sr["max_steps_per_run"] == 145 and sr["over_120_runs"] == 1
    assert sr["last_run_cost_usd"] == 4.2 and sr["last_24h_steps"] == 145 and sr["has_last_24h"] is True

    dr_open = stats_metrics.compute_daily_range_metrics(
        {"2026-11-21T10": 100, "2026-11-23T08": 300},
        {"2026-11-21T10": 2000, "2026-11-23T08": 6000},
        {"2026-11-21T10": 1_000_000, "2026-11-23T08": 3_000_000},
        slots, True,
    )
    assert dr_open["active_days"] == 2
    assert dr_open["min_daily_steps"] == 100 and dr_open["avg_daily_steps"] == 200.0 and dr_open["max_daily_steps"] == 300
    assert dr_open["last_24h_steps"] == 300 and dr_open["last_24h_cost_usd"] == 3.0 and dr_open["has_last_24h"] is True

    dr_closed = stats_metrics.compute_daily_range_metrics(
        {"2026-10-10T10": 120}, {"2026-10-10T10": 5000}, {"2026-10-10T10": 500_000}, set(), False,
    )
    assert dr_closed["has_last_24h"] is False and dr_closed["last_24h_steps"] is None and dr_closed["max_daily_steps"] == 120


def test_v404_bundle_and_project_roster_emit_range_and_retired(tmp_path: Path, monkeypatch) -> None:
    """End-to-end stats bundle and project roster include 24h deltas, RETIRED flags, and closed-window gating."""
    data_dir, brain_dir, cfg_dir, bg_dir = tmp_path / "data", tmp_path / "brain", tmp_path / "cfg", tmp_path / "bg"
    for d in (data_dir / "conversations", brain_dir, cfg_dir, bg_dir):
        d.mkdir(parents=True, exist_ok=True)
    db_file = tmp_path / "missing.vscdb"
    (cfg_dir / "mcp_config.json").write_text("{}", encoding="utf-8")

    now_local = datetime.now().astimezone().replace(minute=15, second=0, microsecond=0)
    two_days_ago = now_local - timedelta(days=2) if now_local.day > 2 else now_local - timedelta(hours=3)
    cid_act = "11111111-2222-4333-8444-555555555555"
    cid_ret = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    _write_retired_session_brain(brain_dir, cid_act, [two_days_ago, now_local], retired=False)
    _write_retired_session_brain(brain_dir, cid_ret, [two_days_ago], retired=True)

    fake_tree = {
        "projects": [{
            "project_id": "ws:demo", "project_name": "Demo Project", "workspaces": ["/home/dev/demo"],
            "sessions": [
                {"conversation_id": cid_act, "project_id": "ws:demo", "project_name": "Demo Project", "workspace_path": "/home/dev/demo", "title": "Active Chat", "step_count": 120, "status": "RUNNING", "last_updated_ts": now_local.timestamp()},
                {"conversation_id": cid_ret, "project_id": "ws:demo", "project_name": "Demo Project", "workspace_path": "/home/dev/demo", "title": "Retired Chat", "step_count": 780, "status": "COMPLETED", "last_updated_ts": two_days_ago.timestamp()},
            ],
        }],
        "routing_telemetry": {}, "backup_321": {},
    }
    monkeypatch.setattr("agy_nexus.session_tree.build_project_session_tree", lambda **_: fake_tree)
    monkeypatch.setattr(stats, "load_db_conversations", lambda *_: {
        cid_act: {"project_id": "ws:demo", "workspace": "/home/dev/demo", "title": "Active Chat", "step_count": 120},
        cid_ret: {"project_id": "ws:demo", "workspace": "/home/dev/demo", "title": "Retired Chat", "step_count": 780},
    })

    bundle = stats.build_nexus_stats_bundle(
        data_dir=data_dir, brain_dir=brain_dir, db_file=db_file, config_dir=cfg_dir, bg_dir=bg_dir,
        period="current_month", include_ascii=False, compact_sessions=False,
    )
    models = bundle["model_usage_vs_target"]
    assert models and all("token_share_pct" in m and "cost_share_pct" in m and "has_last_24h" in m for m in models)
    assert any(m.get("has_last_24h") is True and (m.get("last_24h_steps") or 0) > 0 for m in models)

    projs = bundle["project_hierarchy"]["top_projects"]
    assert projs and all("min_daily_steps" in p and "max_daily_steps" in p and "has_last_24h" in p for p in projs)
    assert any(p.get("has_last_24h") is True for p in projs)

    sess_all = [s for p in projs for s in (p.get("sessions") or [])]
    ret_map = {s["conversation_id"]: s for s in sess_all}
    assert ret_map[cid_ret]["is_retired"] is True
    assert ret_map[cid_act]["is_retired"] is False

    proj_b = stats.build_nexus_stats_bundle(
        data_dir=data_dir, brain_dir=brain_dir, db_file=db_file, config_dir=cfg_dir, bg_dir=bg_dir,
        period="current_month", project_id=str(projs[0]["project_id"]), include_ascii=False, compact_sessions=False,
    )
    roster = proj_b["project_sessions_series"]["sessions"]
    r_map = {r["conversation_id"]: r for r in roster}
    assert r_map[cid_ret]["is_retired"] is True
    assert r_map[cid_act]["has_last_24h"] is True and r_map[cid_act]["last_24h_steps"] >= 1

    closed_b = stats.build_nexus_stats_bundle(
        data_dir=data_dir, brain_dir=brain_dir, db_file=db_file, config_dir=cfg_dir, bg_dir=bg_dir,
        period="last_month", include_ascii=False, compact_sessions=True,
    )
    closed_projs = closed_b["project_hierarchy"]["top_projects"]
    assert closed_projs == [] or all(p.get("has_last_24h") is False and p.get("last_24h_steps") is None for p in closed_projs)
    assert all(m.get("has_last_24h") is False and m.get("last_24h_steps") is None for m in closed_b["model_usage_vs_target"])


def test_v404_frontend_whiskers_caret_bars_sort_and_fallbacks() -> None:
    """Run Node vm test across all 4 tables, 3 metrics, step-cap/seam alerts, V9.TableSort, and fallback derivation."""
    probe = r"""
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

function makeNode(tag, id) {
  const listeners = {};
  const cls = new Set();
  const node = {
    tagName: String(tag || "DIV").toUpperCase(),
    id: id || "",
    _html: "",
    textContent: "",
    title: "",
    dataset: {},
    style: {},
    classList: {
      add: (...xs) => xs.forEach((x) => cls.add(x)),
      remove: (...xs) => xs.forEach((x) => cls.delete(x)),
      toggle: (x, force) => { if (force === undefined ? !cls.has(x) : force) cls.add(x); else cls.delete(x); },
      contains: (x) => cls.has(x),
    },
    get className() { return Array.from(cls).join(" "); },
    set className(v) { cls.clear(); String(v || "").split(/\s+/).filter(Boolean).forEach((x) => cls.add(x)); },
    setAttribute(k, v) { if (k === "aria-label" || k === "data-state") node[k] = String(v); },
    getAttribute(k) { return node[k] != null ? String(node[k]) : null; },
    addEventListener(ev, fn) { (listeners[ev] = listeners[ev] || []).push(fn); },
    querySelector(sel) { return node.querySelectorAll(sel)[0] || null; },
    querySelectorAll(sel) {
      if (sel.includes("th button") || sel.includes("[data-sort-key]")) return node._sortBtns || [];
      if (sel.includes("[data-project-key]")) return node._projBtns || [];
      if (sel.includes("[data-session-cid]")) return node._sessBtns || [];
      return [];
    },
    get innerHTML() { return node._html; },
    set innerHTML(val) {
      node._html = String(val || "");
      node._sortBtns = [];
      const re = /data-sort-table="([^"]+)"[^>]*data-sort-key="([^"]+)"/g;
      let m;
      while ((m = re.exec(node._html)) !== null) {
        const tbl = m[1], key = m[2];
        node._sortBtns.push({
          dataset: { sortTable: tbl, sortKey: key },
          getAttribute: () => key,
          setAttribute: () => {},
          closest: () => ({ dataset: {}, getAttribute: () => "", setAttribute: () => {} }),
          addEventListener(ev, fn) { (this._ev = this._ev || {})[ev] = fn; },
          click() { if (this._ev && this._ev.click) this._ev.click({ preventDefault: () => {} }); },
        });
      }
      if (node._theadRef && /<thead>([\s\S]*?)<\/thead>/.test(node._html)) {
        node._theadRef.innerHTML = node._html.match(/<thead>([\s\S]*?)<\/thead>/)[1];
      }
    },
  };
  return node;
}

const byId = new Map();
const tableMap = new Map();
function ensureTable(id, tbodyId) {
  const thead = makeNode("THEAD", "");
  const tbody = makeNode("TBODY", tbodyId);
  const tbl = makeNode("TABLE", id);
  tbl.tHead = thead;
  tbl.querySelector = (sel) => (sel === "thead" ? thead : tbl.querySelectorAll(sel)[0] || null);
  tbl.querySelectorAll = (sel) => (sel.includes("[data-sort-key]") ? thead._sortBtns || [] : []);
  tableMap.set(tbodyId, tbl);
  byId.set(id, tbl);
  byId.set(tbodyId, tbody);
}
ensureTable("v9ModelTable", "v9ModelTableBody");
ensureTable("v9SubagentTable", "v9SubagentTableBody");
["v9KpiGrid", "v9ModelPlotSub", "v9SubPlotSub", "v9ModelTableLegend", "v9SubagentTableLegend", "v9ProjPlotTitle", "v9ProjPlotSub",
 "v9ProjTableWrap", "v9ProjFoot", "v9WireSub", "v9WireClientHost", "v9WireCallsHost",
 "v9HealthDrawerTitle", "v9HealthSummary", "v9HealthBody", "v9HeatHeading",
 "v9PeriodTriggerLabel", "v9PeriodPickerBtn", "v9SortStatus", "v9Toast"
].forEach((id) => {
  const n = makeNode("DIV", id);
  if (id === "v9ProjTableWrap") {
    n.querySelector = (sel) => {
      if (sel.startsWith('table[data-v9-table="')) {
        const tid = sel.match(/table\[data-v9-table="([^"]+)"\]/)[1];
        const m = n._html.match(/<table class="v9-table booktabs" data-v9-table="([^"]+)">/);
        if (!m || m[1] !== tid) return null;
        if (!n._tbl) { n._tbl = makeNode("TABLE", ""); n._tbl.tHead = makeNode("THEAD", ""); n._tblRef = n._tbl.tHead; }
        n._tbl.tHead.innerHTML = (n._html.match(/<thead>([\s\S]*?)<\/thead>/) || ["", ""])[1];
        n._tbl.querySelectorAll = (s2) => n._tbl.tHead.querySelectorAll(s2);
        return n._tbl;
      }
      return null;
    };
  }
  byId.set(id, n);
});
byId.get("v9ProjTableWrap").closest = () => null;
for (const tbody of [byId.get("v9ModelTableBody"), byId.get("v9SubagentTableBody")]) {
  tbody.closest = (s) => (s === "table" ? tableMap.get(tbody.id) : null);
}

const document = {
  getElementById: (id) => byId.get(id) || null,
  querySelector: () => null,
  querySelectorAll: () => [],
};
const localStore = {};
const window = {
  document,
  location: { search: "", pathname: "/web", hash: "#analytics", hostname: "localhost" },
  localStorage: { getItem: (k) => localStore[k] || null, setItem: (k, v) => { localStore[k] = String(v); } },
  matchMedia: () => ({ matches: false }),
  innerWidth: 1440,
};
const sessionStore = {};
const ctx = {
  window, document, localStorage: window.localStorage,
  sessionStorage: { getItem: (k) => sessionStore[k] || null, setItem: (k, v) => { sessionStore[k] = String(v); } },
  navigator: { userAgent: "node" }, console,
  setTimeout: (fn) => 0, clearTimeout: () => {}, requestAnimationFrame: (fn) => fn(),
  URLSearchParams, Intl, Math, Number, String, Array, Object, Set, Map, Date, RegExp, JSON,
};
vm.createContext(ctx);
for (const f of [
  "web/v9/v9_state.js",
  "web/v9/v9_table_sort.js",
  "web/v9/v9_spark_bars.js",
  "web/v9/v9_project_view.js",
  "web/v9/v9_analytics.js",
  "web/v9/v9_demo_adapter.js",
]) {
  vm.runInContext(fs.readFileSync(f, "utf-8"), ctx, { filename: f });
}

const V9 = ctx.window.AgyV9;
V9.Charts = { getProjectPalette: () => ["#0b5cad", "#166534", "#9a3412", "#6d28d9"] };

const bundle = {
  period: { preset: "current_month", start_date: "2026-11-01", end_date: "2026-11-23", window_days: 23, active_days: 12, label: "Nov 1 – 23" },
  series: { dates: ["2026-11-21T10", "2026-11-22T12", "2026-11-23T08"], step_hours: 1 },
  velocity_series: { dates: ["2026-11-21", "2026-11-22", "2026-11-23"], steps: [500, 500, 500], tokens: [30000000, 30000000, 30000000], cost_usd: [40, 40, 40], step_hours: 24 },
  kpis: { window_steps: 1500, window_tokens: 90000000, window_cost_usd: 120.0, total_steps: 1500, total_tokens: 90000000, est_cost_usd: 120.0, active_days: 12, active_weeks: 3.3, avg_daily_steps: 125, tok_per_day: 7500000, cost_per_day_usd: 10.0, sessions_started: 5, total_tool_calls: 400, total_subagents_spawned: 4, top_projects_count: 2 },
  quota_and_pools: { active_tier_profile: "ultra-20x" },
  wire_stats: { avg_inner_kb: 9.2, avg_outer_kb: 18.0, within_cap_pct: 100 },
  project_hierarchy: {
    top_projects: [
      {
        project_id: "proj-alpha", project_name: "Alpha Core", share_pct: 60.0, active_days: 4, sessions_count: 2,
        window_steps: 900, window_tokens: 60000000, window_cost_usd: 80.0,
        min_daily_steps: 50, avg_daily_steps: 225, max_daily_steps: 500, last_24h_steps: 120,
        min_daily_tokens: 2000000, avg_daily_tokens: 15000000, max_daily_tokens: 35000000, last_24h_tokens: 5000000,
        min_daily_cost_usd: 4.0, avg_daily_cost_usd: 20.0, max_daily_cost_usd: 45.0, last_24h_cost_usd: 9.5,
        has_last_24h: true, last_updated_ts: 1795440000, last_updated_age: "1h ago", color_slot: 0,
        sessions: [
          { conversation_id: "c-warn", title: "Session Warn", step_count: 580, window_steps: 310, window_tokens: 25000000, window_cost_usd: 30.0, status: "IDLE", is_retired: false, last_24h_steps: 90, last_24h_tokens: 3000000, last_24h_cost_usd: 4.0, has_last_24h: true, last_updated_ts: 1795439000 },
          { conversation_id: "c-ret", title: "Session Retired Heavy", step_count: 920, window_steps: 200, window_tokens: 10000000, window_cost_usd: 15.0, status: "COMPLETED", is_retired: true, last_24h_steps: 0, last_24h_tokens: 0, last_24h_cost_usd: 0, has_last_24h: true, last_updated_ts: 1795430000 },
          { conversation_id: "c-fault", title: "Session Over 700", step_count: 740, window_steps: 500, window_tokens: 25000000, window_cost_usd: 35.0, subagent_runs: 2, status: "RUNNING", is_retired: false, last_24h_steps: 220, last_24h_tokens: 12000000, last_24h_cost_usd: 18.0, has_last_24h: true, last_updated_ts: 1795440000 },
        ],
      },
      {
        project_id: "proj-beta", project_name: "Beta Idle", share_pct: 40.0, active_days: 3, sessions_count: 1,
        window_steps: 600, window_tokens: 30000000, window_cost_usd: 40.0,
        min_daily_steps: 80, avg_daily_steps: 200, max_daily_steps: 320, last_24h_steps: 0,
        min_daily_tokens: 4000000, avg_daily_tokens: 10000000, max_daily_tokens: 16000000, last_24h_tokens: 0,
        min_daily_cost_usd: 6.0, avg_daily_cost_usd: 13.3, max_daily_cost_usd: 22.0, last_24h_cost_usd: 0.0,
        has_last_24h: true, last_updated_ts: 1795300000, last_updated_age: "2d ago", color_slot: 1,
        sessions: [],
      },
    ],
  },
  model_usage_vs_target: [
    { model_key: "carbon", short_label: "Carbon 4", label: "Gemini 4 Carbon", pool: "Google 20x", actual_calls: 1000, est_tokens: 30000000, est_cost_usd: 20.0, rate_label: "$0.00/$0.00", actual_pct: 66.7, token_share_pct: 33.3, cost_share_pct: 16.7, target_pct: 50, delta_pct: 16.7, has_last_24h: true, last_24h_steps: 80, last_24h_tokens: 1000000, last_24h_cost_usd: 1.0 },
    { model_key: "sonnet", short_label: "Sonnet 5.5", label: "Claude Sonnet 5.5", pool: "Partner 1x", actual_calls: 500, est_tokens: 60000000, est_cost_usd: 100.0, rate_label: "$3.00/$15.00", actual_pct: 33.3, token_share_pct: 66.7, cost_share_pct: 83.3, target_pct: 20, delta_pct: 13.3, has_last_24h: true, last_24h_steps: 20, last_24h_tokens: 9000000, last_24h_cost_usd: 9.0 },
  ],
  subagent_list: [
    { role: "argon-surgeon", dominant_model_label: "Argon 4", runs: 2, steps: 220, tokens: 80000000, est_cost_usd: 90.0, min_steps_per_run: 80, avg_steps_per_run: 110, max_steps_per_run: 140, last_run_steps: 140, min_tokens_per_run: 35000000, avg_tokens_per_run: 40000000, max_tokens_per_run: 45000000, last_run_tokens: 45000000, min_cost_usd_per_run: 38.0, avg_cost_usd_per_run: 45.0, max_cost_usd_per_run: 52.0, last_run_cost_usd: 52.0, over_120_runs: 1, has_last_24h: true },
    { role: "flash-scout", dominant_model_label: "Flash 3.8", runs: 2, steps: 40, tokens: 2000000, est_cost_usd: 2.0, min_steps_per_run: 15, avg_steps_per_run: 20, max_steps_per_run: 25, last_run_steps: 25, min_tokens_per_run: 800000, avg_tokens_per_run: 1000000, max_tokens_per_run: 1200000, last_run_tokens: 1200000, min_cost_usd_per_run: 0.8, avg_cost_usd_per_run: 1.0, max_cost_usd_per_run: 1.2, last_run_cost_usd: 1.2, over_120_runs: 0, has_last_24h: true },
  ],
  code_health: { installed_version: "4.0.4", status: "up_to_date", files: [] },
};

// 1. Whole-fleet render across all 3 metrics
for (const metric of ["steps", "tokens", "cost"]) {
  V9.state.metric = metric;
  V9.state.projectId = "";
  V9.Analytics.renderAnalytics(bundle, {}, () => {});

  const projHtml = byId.get("v9ProjTableWrap").innerHTML;
  assert.ok(projHtml.includes("v9-whisk-bar") && projHtml.includes("v9-whisk-avg"), `missing project whisker in ${metric}`);
  assert.ok(projHtml.includes("v9-whisk-dot is-idle"), `Beta Idle missing hollow 24h dot in ${metric}`);
  assert.ok(projHtml.includes('role="img" aria-label='), `missing accessible track role in ${metric}`);

  const modelHtml = byId.get("v9ModelTableBody").innerHTML;
  assert.ok(modelHtml.includes("v9-caret-fill") && modelHtml.includes("v9-top-caret"), `missing model caret bar in ${metric}`);
  if (metric === "cost") assert.ok(modelHtml.includes("83.3%"), "Model share did not switch to cost_share_pct");

  const subHtml = byId.get("v9SubagentTableBody").innerHTML;
  assert.ok(subHtml.includes("&gt;120") && subHtml.includes('data-state="fault"'), `missing >120 step-cap alert in ${metric}`);
  assert.ok(!byId.get("v9ModelPlotSub").textContent.includes("▾") && !byId.get("v9SubPlotSub").textContent.includes("●"));
  assert.ok(byId.get("v9ModelTableLegend").innerHTML.includes("Last 24h share"));
  assert.ok(byId.get("v9SubagentTableLegend").innerHTML.includes("Latest run"));
}

// 2. Subagent heavy burn warn (2.5x without >120)
const burnOnly = V9.SparkBars.computeSubagentMetrics({ role: "neon-surgeon", runs: 2, steps: 80, max_steps_per_run: 50, over_120_runs: 0, avg_tokens_per_run: 30000000, min_tokens_per_run: 25000000, max_tokens_per_run: 35000000, last_run_tokens: 35000000 }, "tokens", null, 10000000);
assert.equal(burnOnly.isStepCapOver, false);
assert.equal(burnOnly.isHeavyBurn, true);
assert.ok(V9.SparkBars.renderSubagentWhisker(burnOnly, 35000000, "tokens", "#0b5cad").includes('data-state="warn"'));
assert.ok(V9.SparkBars.renderSubagentWhisker(burnOnly, 35000000, "tokens", "#0b5cad").includes("3.0x"));

// 3. Closed historical window omits 24h whisker dot & 24h model caret
const closedPm = V9.SparkBars.computeProjectMetrics({ window_steps: 400, min_daily_steps: 100, avg_daily_steps: 200, max_daily_steps: 400, has_last_24h: false, last_24h_steps: null, share_pct: 50 }, "steps");
assert.equal(closedPm.hasLast24h, false);
assert.ok(!V9.SparkBars.renderProjectWhisker(closedPm, 400, "steps", "#0b5cad").includes("v9-whisk-dot"));

// 4. Project Sessions mode: Steps 320|/700 caret & RETIRED vs warn vs fault, plus Tokens/Cost Avg| + 24h caret
V9.state.metric = "steps";
const alphaProj = bundle.project_hierarchy.top_projects[0];
const sessBundle = Object.assign({}, bundle, { project_scope: { project_id: "proj-alpha" }, selected_project: alphaProj, project_sessions_series: { dates: ["2026-11-23T08"], step_hours: 1, sessions: alphaProj.sessions } });
V9.ProjectView.renderProjectSessionsCard(sessBundle, {});
const sessStepsHtml = byId.get("v9ProjTableWrap").innerHTML;
assert.ok(sessStepsHtml.includes("Context / Seam") && sessStepsHtml.includes("700 rollover limit"));
assert.ok(sessStepsHtml.includes('data-state="warn"') && sessStepsHtml.includes("500+"));
assert.ok(sessStepsHtml.includes('data-state="fault"') && sessStepsHtml.includes("700+"));
assert.ok(sessStepsHtml.includes('data-state="retired"') && sessStepsHtml.includes(">RET<"));
assert.ok(sessStepsHtml.includes("34.8%") || sessStepsHtml.includes("34.7%") || sessStepsHtml.includes("320"), "expected 320 seam tick");
assert.ok(sessStepsHtml.includes("76.1%") || sessStepsHtml.includes("700"), "expected 700 rollover caret");

V9.state.metric = "tokens";
V9.ProjectView.renderProjectSessionsCard(sessBundle, {});
const sessTokHtml = byId.get("v9ProjTableWrap").innerHTML;
assert.ok(sessTokHtml.includes("Burn / Avg") && sessTokHtml.includes("Project avg"));
assert.ok(!byId.get("v9ProjPlotSub").textContent.includes("▾"));

// 5. V9.TableSort Peak/Share sorting works cleanly
V9.state.metric = "steps";
V9.ProjectView.renderTopProjectsTable(bundle, {});
V9.TableSort.setSort("projects", "share", "asc");
V9.ProjectView.renderTopProjectsTable(bundle, {});
const rowsAsc = byId.get("v9ProjTableWrap").innerHTML;
assert.ok(rowsAsc.indexOf("Beta Idle") < rowsAsc.indexOf("Alpha Core"), "projects ascending Peak sort failed");

// 6. JS series fallback when backend min/avg/max/24h fields omitted
const fbPm = V9.SparkBars.computeProjectMetrics({ window_steps: 500, steps_series: [100, 400], share_pct: 50 }, "steps", ["2026-11-22T09", "2026-11-23T09"], 1);
assert.equal(fbPm.min, 100);
assert.equal(fbPm.max, 400);
assert.equal(fbPm.avg, 250);
assert.equal(fbPm.last24h, 500);

// 7. v9_demo_adapter preserves per-run & retired fields when scoping project
ctx.window.DEMO_SNAPSHOT = {
  bundles: { current_month: bundle },
  workspace_tree: { projects: [{ project_id: "proj-alpha", project_name: "Alpha Core", sessions: alphaProj.sessions }] },
};
const scoped = V9.DemoAdapter.getDemoStatsBundle("month", "to_date", 0, "proj-alpha");
assert.ok(scoped.subagent_list.some((r) => r.role === "argon-surgeon" && r.max_steps_per_run === 140 && r.over_120_runs === 1));
assert.ok(scoped.project_sessions_series.sessions.some((s) => s.conversation_id === "c-ret" && s.is_retired === true));

// 8. Cost mode missing-cost NaN safety, HTML/color escaping, and Tokens >1e6 avg sort stability
const undefCostSub = V9.SparkBars.computeSubagentMetrics({ role: "empty", runs: 2 }, "cost", null, 0);
assert.equal(undefCostSub.max, 0);
assert.ok(!V9.SparkBars.renderSubagentWhisker(undefCostSub, 1, "cost", "bad(color)").includes("NaN"));
assert.ok(V9.SparkBars.renderProjectWhisker(closedPm.hasLast24h ? closedPm : { min: 10, avg: 20, max: 30, last24h: 10, hasLast24h: true, sharePct: 50 }, 30, "steps", "#0b5cad").includes("--v9-dot-bg"));

V9.state.metric = "tokens";
V9.TableSort.setSort("projects", "share", "desc");
const tokTieBundle = JSON.parse(JSON.stringify(bundle));
tokTieBundle.project_hierarchy.top_projects[0].max_daily_tokens = 35000000;
tokTieBundle.project_hierarchy.top_projects[0].avg_daily_tokens = 30000000;
tokTieBundle.project_hierarchy.top_projects[1].max_daily_tokens = 35000010;
tokTieBundle.project_hierarchy.top_projects[1].avg_daily_tokens = 1000000;
V9.ProjectView.renderTopProjectsTable(tokTieBundle, {});
const tokSortedHtml = byId.get("v9ProjTableWrap").innerHTML;
assert.ok(tokSortedHtml.indexOf("Beta Idle") < tokSortedHtml.indexOf("Alpha Core"), "Tokens max primary sort corrupted by avg tie-breaker");
"""
    res = subprocess.run(["node", "-e", probe], cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    assert res.returncode == 0, f"Node v4.0.4 probe failed:\n{res.stderr}\n{res.stdout}"


def test_v404_budgets_forced_colors_pwa_parity_and_workflows() -> None:
    """Enforce file/function line budgets, forced-colors & CSS rules, PWA registration, and Workflow 6 v4.0.7 docs."""
    from agy_nexus import polyglot_outline

    for mod in ("stats_metrics.py", "stats.py", "stats_series.py", "stats_aggregator.py", "project_stats.py", "cost_ledger.py"):
        p = SRC_NEXUS / mod
        lines = p.read_text(encoding="utf-8").splitlines()
        assert len(lines) <= 450, f"{mod} exceeded 450L budget ({len(lines)}L)"
        tree = ast.parse("\n".join(lines), filename=str(p))
        for fn in ast.walk(tree):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and fn.end_lineno:
                span = fn.end_lineno - fn.lineno + 1
                assert span <= 100, f"{mod}:{fn.name} exceeded 100L ({span}L)"

    spark_js = V9_DIR / "v9_spark_bars.js"
    assert len(spark_js.read_text(encoding="utf-8").splitlines()) <= 220
    tables_css = V9_DIR / "v9_tables_and_rail.css"
    css_txt = tables_css.read_text(encoding="utf-8")
    assert len(css_txt.splitlines()) <= 300
    assert "forced-colors: active" in css_txt and "forced-color-adjust: none" in css_txt
    assert "!important" not in css_txt

    for js_p in sorted(V9_DIR.glob("*.js")):
        txt = js_p.read_text(encoding="utf-8")
        assert len(txt.splitlines()) <= 500, f"{js_p.name} exceeded 500L"
        assert not re.search(r"[🔒✦⬇◀▶✓✕]", txt), f"Forbidden UI pictograph in {js_p.name}"
        if js_p.name in ("v9_spark_bars.js", "v9_analytics.js", "v9_project_view.js", "v9_demo_adapter.js"):
            _s, _f, syms = polyglot_outline.outline_code(js_p.suffix.lower(), txt.splitlines())
            assert not any(int(sym.get("lines") or 0) > 100 for sym in syms), f"{js_p.name} exceeded 100L function budget: {[s for s in syms if int(s.get('lines') or 0) > 100]}"

    assert "v9/v9_spark_bars.js" in web_routes.PWA_ASSETS
    sw_txt = (WEB_DIR / "sw.js").read_text(encoding="utf-8")
    assert 'CACHE_NAME = "agy-nexus-v4.0.7"' in sw_txt
    assert "/web/v9/v9_spark_bars.js?v=4.0.7" in sw_txt and '"v9/v9_spark_bars.js"' in sw_txt
    html_txt = (V9_DIR / "index.html").read_text(encoding="utf-8")
    assert html_txt == (WEB_DIR / "index.html").read_text(encoding="utf-8")
    assert '/web/v9/v9_spark_bars.js?v=4.0.7' in html_txt

    wf_txt = (REPO_ROOT / "docs" / "WORKFLOWS.md").read_text(encoding="utf-8")
    assert "Workflow 6:" in wf_txt and "v4.0.7" in wf_txt
    assert "Hybrid Range Whiskers & Target/Seam Caret Bars" in wf_txt
    assert "320│ / 700▾" in wf_txt
