"""Wave 1 regression tests for v4.1.0 agent sync, Quota & Resets UI, subagent rollup, chart resize sync, and whisker bounds."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
SCRIPTS_DIR = REPO_ROOT / "scripts"
WEB_V9 = REPO_ROOT / "web" / "v9"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _extract_yaml_frontmatter(md_path: Path) -> str:
    raw = md_path.read_text(encoding="utf-8")
    parts = raw.split("---", 2)
    assert len(parts) >= 3 and parts[0].strip() == "", f"Missing YAML frontmatter in {md_path.name}"
    return parts[1]


def test_v410_agent_sync_and_yaml_hygiene() -> None:
    """Verify 13 tracked agents + README, carbon-sentinel presence, sync_agents --check count, and clean YAML tools lists."""
    agents_dir = REPO_ROOT / "agents"
    assert (agents_dir / "README.md").is_file()
    assert (agents_dir / "carbon-sentinel.md").is_file()

    agent_files = sorted(p for p in agents_dir.glob("*.md") if p.name.upper() != "README.MD")
    assert len(agent_files) == 13, [p.name for p in agent_files]

    proc = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "sync_agents.py"), "--check", "--json"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    report = json.loads(proc.stdout)
    assert report["ok"] is True and report["total"] == 13 and len(report["agents"]) == 13

    forbidden_yaml_tools = ("call_mcp_tool", "list_resources", "read_resource")
    sentinel_names = {"argon-sentinel.md", "carbon-sentinel.md", "claude-sentinel.md"}
    for md in agent_files:
        fm = _extract_yaml_frontmatter(md)
        for bad_tool in forbidden_yaml_tools:
            assert bad_tool not in fm, f"{bad_tool} found in YAML frontmatter of {md.name}"
        if md.name in sentinel_names:
            assert "run_command" not in fm, f"Sentinel {md.name} must not declare run_command in YAML"
            assert "inheritMcp: true" in fm, f"Sentinel {md.name} must enable inheritMcp: true"


def test_v410_thin_coordinator_handoff_templates() -> None:
    """Verify handoff_templates enforce <250 steps, all 12 canonical roles, anti-ad-hoc rules, and headings."""
    from agy_nexus import handoff_templates

    allowlisted = (
        "flash-scout", "argon-architect", "flash-surgeon", "hydrogen-surgeon",
        "neon-surgeon", "argon-surgeon", "flash-auditor", "argon-sentinel",
        "carbon-sentinel", "claude-specialist", "claude-sentinel", "pool-failover",
    )
    fast_footer = handoff_templates.build_execution_lifecycle_footer("fast", "bug_or_visual_fix", "Fix CSS padding.")
    plan_footer = handoff_templates.build_execution_lifecycle_footer("plan", "feature_update", "Implement feature.")
    fast_existing = handoff_templates.build_existing_session_lifecycle_text("fast", "bug_or_visual_fix", "Fix typo.", "Local only.")
    plan_existing = handoff_templates.build_existing_session_lifecycle_text("plan", "feature_update", "Add view.", "Local only.")

    assert "## Surgical Fast-Path Lifecycle (`fast` Mode — Thin-Coordinator Direct)" in fast_footer
    assert "## Mandatory 4-Step Execution Lifecycle & Thin-Coordinator Verification Gate" in plan_footer
    assert "Follow the Surgical Fast-Path Lifecycle (Thin-Coordinator Direct):" in fast_existing
    assert "Follow the Mandatory 4-Step Execution Lifecycle (Thin-Coordinator Hybrid):" in plan_existing

    for rendered in (fast_footer, plan_footer, fast_existing, plan_existing):
        assert "< 250" in rendered
        for role in allowlisted:
            assert role in rendered, f"Missing allowlisted role {role}"
        assert '"research"' in rendered and '"self"' in rendered
        assert "task-prefixed" in rendered


def test_v410_subagent_is_registered_and_quota_scrub(tmp_path: Path) -> None:
    """Verify is_registered tagging on subagent rows and complete removal of legacy Quota Pacing labels."""
    from agy_nexus import stats_aggregator, stats_metrics

    specs = stats_aggregator.load_agent_role_specs(tmp_path)
    assert specs["hydrogen-surgeon"]["is_subagent"] is True
    assert specs["carbon-sentinel"]["is_subagent"] is True
    assert specs["swarm-orchestrator"]["is_subagent"] is False

    agg = stats_aggregator.init_agg_state()
    for role, st in (
        ("flash-surgeon", 40), ("carbon-sentinel", 30), ("hydrogen-surgeon", 25),
        ("research", 20), ("wave4-auditor", 15), ("swarm-orchestrator", 10),
    ):
        agg["subagent_roles"][role] = {
            "steps": st, "tokens": st * 1000, "runs": 1, "cost_usd_micros": st * 100,
            "min_steps_per_run": st, "max_steps_per_run": st, "last_run_steps": st,
            "min_tokens_per_run": st * 1000, "max_tokens_per_run": st * 1000, "last_run_tokens": st * 1000,
            "min_cost_micros_per_run": st * 100, "max_cost_micros_per_run": st * 100, "last_run_cost_micros": st * 100,
            "over_120_runs": 0,
        }
        agg["role_model_votes"][role] = {"carbon": st}

    rows = stats_metrics.build_subagent_list_rows(
        agg, 1, 1.0, set(), False,
        resolve_model_fn=lambda *a: ("carbon", "default"),
        short_labels={"carbon": "Carbon 4"},
        e_iso="2026-11-25",
        parent_model_map={}, main_mk="carbon", main_switch_date="", agent_target_map={},
        agent_role_specs=specs,
    )
    by_role = {r["role"]: r for r in rows}
    for reg in ("flash-surgeon", "carbon-sentinel", "hydrogen-surgeon"):
        assert by_role[reg]["is_registered"] is True, reg
    for unreg in ("research", "wave4-auditor", "swarm-orchestrator"):
        assert by_role[unreg]["is_registered"] is False, unreg

    scrub_targets = (
        SRC_DIR / "agy_nexus" / "ascii_rich.py",
        SRC_DIR / "agy_nexus" / "ascii_default.py",
        SRC_DIR / "agy_nexus" / "telemetry_scanner.py",
        SRC_DIR / "agy_nexus" / "tools_ops.py",
        WEB_V9 / "v9_quota_cards.js",
        WEB_V9 / "v9_quota_cards.css",
        WEB_V9 / "v9_analytics.js",
    )
    legacy_tokens = ("Quota Pacing", "ON PACE", ">WARM<", ">HOT<", "partner_weekly_pacing")
    for path in scrub_targets:
        text = path.read_text(encoding="utf-8")
        for tok in legacy_tokens:
            assert tok not in text, f"Legacy token {tok!r} still present in {path.name}"


_QUOTA_RESETS_NODE_CJS = r"""
const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

const ctx = {
  window: { AgyV9: {} },
  document: { getElementById: () => null },
  Date, Math, Number, String, Array, Object, Set, Map, JSON, RegExp, Intl,
};
ctx.window.AgyV9 = {
  state: { metric: "steps" },
  escHtml: (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;"),
  fmtNum: (n) => String(Math.round(Number(n || 0))),
  fmtUsd: (n) => `$${Number(n || 0).toFixed(2)}`,
};
vm.runInNewContext(fs.readFileSync("web/v9/v9_quota_cards.js", "utf-8"), ctx);
const QC = ctx.window.AgyV9.QuotaCards;

const future5h = new Date(Date.now() + 2 * 3600000).toISOString();
const futureWk = new Date(Date.now() + 3 * 86400000).toISOString();

function makeBundle(g5, gw, p5, pw, gStatus = "HEALTHY", pStatus = "HEALTHY") {
  return {
    quota_and_pools: {
      active_tier_profile: "ultra-20x",
      live_quota: { state: "LIVE", ls_alive: true, is_fresh: true, snapshot_age_seconds: 5 },
      pools: {
        google: { status: gStatus, call_share_pct: 90, total_429_count: 0, bucket_5h: g5, bucket_weekly: gw, burn_5h: { steps: 10, cost_usd: 0.5 }, burn_7d: { steps: 100, cost_usd: 2.0 } },
        claude: { status: pStatus, call_share_pct: 10, total_429_count: 0, bucket_5h: p5, bucket_weekly: pw, burn_5h: { steps: 0, cost_usd: 0 }, burn_7d: { steps: 0, cost_usd: 0 } },
      },
    },
    model_usage_vs_target: [],
  };
}

// 10% used (remaining_pct omitted) -> 90.0 progress value & OK (>=25%) + untouched Standby + Partner Wk countdown
const html10 = QC.renderQuotaResetsCard(makeBundle(
  { used_pct: 10.0, has_active_reset: true, reset_time: future5h },
  { used_pct: 0.0, remaining_pct: 100.0, has_active_reset: false },
  { used_pct: 0.0, remaining_pct: 100.0, has_active_reset: false },
  { used_pct: 0.0, remaining_pct: 100.0, has_active_reset: true, reset_time: futureWk }
));
assert.ok(html10.includes('class="v9-qr-prog" data-level="ok" value="90.0"'));
assert.ok(html10.includes(">OK<") && html10.includes("90% left"));
assert.ok(html10.includes("Standby · 100% left"));
assert.ok(html10.includes('<span class="v9-p-standby-full">Partner: </span>100% left<span class="v9-qr-standby-word"> · Standby</span> · Wk '));
assert.ok(html10.includes('<span class="v9-qr-prefix-short">G 5h</span>') && html10.includes('<span class="v9-qr-rst-pfx">resets in </span>'));
assert.ok(!html10.includes("Partner 5h") && !html10.includes("Partner Wk"));

// Exact 25% boundary -> OK; 24.9% and 10.0% -> LOW LEFT; 9.9% and COOLDOWN_429 -> NEAR LIMIT
const html25 = QC.renderQuotaResetsCard(makeBundle(
  { used_pct: 75.0, remaining_pct: 25.0, has_active_reset: true, reset_time: future5h },
  { used_pct: 0.0, remaining_pct: 100.0, has_active_reset: false },
  { used_pct: 0.0, remaining_pct: 100.0, has_active_reset: false },
  { used_pct: 0.0, remaining_pct: 100.0, has_active_reset: false }
));
assert.ok(html25.includes(">OK<") && html25.includes('data-level="ok"'));

for (const rem of [24.9, 10.0]) {
  const htmlLow = QC.renderQuotaResetsCard(makeBundle(
    { used_pct: 100 - rem, remaining_pct: rem, has_active_reset: true, reset_time: future5h },
    { used_pct: 0.0, remaining_pct: 100.0, has_active_reset: false },
    { used_pct: 0.0, remaining_pct: 100.0, has_active_reset: false },
    { used_pct: 0.0, remaining_pct: 100.0, has_active_reset: false }
  ));
  assert.ok(htmlLow.includes(">LOW LEFT<") && htmlLow.includes('data-level="low"'));
}

const htmlNearRem = QC.renderQuotaResetsCard(makeBundle(
  { used_pct: 90.1, remaining_pct: 9.9, has_active_reset: true, reset_time: future5h },
  { used_pct: 0.0, remaining_pct: 100.0, has_active_reset: false },
  { used_pct: 0.0, remaining_pct: 100.0, has_active_reset: false },
  { used_pct: 0.0, remaining_pct: 100.0, has_active_reset: false }
));
assert.ok(htmlNearRem.includes(">NEAR LIMIT<") && htmlNearRem.includes('data-level="near"'));

const htmlCd = QC.renderQuotaResetsCard(makeBundle(
  { used_pct: 40.0, remaining_pct: 60.0, has_active_reset: true, reset_time: future5h },
  { used_pct: 0.0, remaining_pct: 100.0, has_active_reset: false },
  { used_pct: 0.0, remaining_pct: 100.0, has_active_reset: false },
  { used_pct: 0.0, remaining_pct: 100.0, has_active_reset: false },
  "COOLDOWN_429"
));
assert.ok(htmlCd.includes(">NEAR LIMIT<") && htmlCd.includes('data-level="near"'));

// Partner auto-expand when Partner remaining_pct < 100%
const htmlPartner = QC.renderQuotaResetsCard(makeBundle(
  { used_pct: 10.0, remaining_pct: 90.0, has_active_reset: true, reset_time: future5h },
  { used_pct: 20.0, remaining_pct: 80.0, has_active_reset: true, reset_time: futureWk },
  { used_pct: 12.0, remaining_pct: 88.0, has_active_reset: true, reset_time: future5h },
  { used_pct: 5.0, remaining_pct: 95.0, has_active_reset: true, reset_time: futureWk }
));
assert.ok(htmlPartner.includes("Partner 5h") && htmlPartner.includes("88% left"));
assert.ok(htmlPartner.includes("Partner Wk") && htmlPartner.includes("95% left"));
assert.ok(htmlPartner.includes('<span class="v9-qr-prefix-short">P 5h</span>') && htmlPartner.includes('<span class="v9-qr-prefix-short">P Wk</span>'));
console.log("V410_QUOTA_CARDS_OK");
"""


def test_v410_quota_resets_card_states_node(tmp_path: Path) -> None:
    """Verify Card 4 Quota & Resets remaining %, levels, Standby, Partner auto-expand, and mobile short prefixes."""
    probe = tmp_path / "quota_resets_probe.cjs"
    probe.write_text(_QUOTA_RESETS_NODE_CJS, encoding="utf-8")
    proc = subprocess.run(["node", str(probe)], cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    assert "V410_QUOTA_CARDS_OK" in proc.stdout

    qc_css = (WEB_V9 / "v9_quota_cards.css").read_text(encoding="utf-8")
    assert "@container (max-width: 215px)" in qc_css and "@media (max-width: 479px)" in qc_css
    assert ".v9-qr-standby-word" in qc_css and ".v9-stage .v9-qr-standby-word" in qc_css


_ROLLUP_CHARTS_WHISKERS_CJS = r"""
const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

function makeTbody() {
  return {
    _html: "", buttons: [], soloRows: [],
    set innerHTML(v) {
      this._html = String(v || "");
      this.buttons = [];
      this.soloRows = [];
      for (const m of this._html.matchAll(/class="v9-sub-rollup-btn" aria-expanded="(true|false)"/g)) {
        const listeners = [];
        this.buttons.push({
          expanded: m[1],
          addEventListener: (ev, fn) => { if (ev === "click") listeners.push(fn); },
          click: () => listeners.forEach((fn) => fn()),
        });
      }
      for (const m of this._html.matchAll(/<tr class="([^"]*)" data-solo-sub="([^"]*)">/g)) {
        const listeners = [];
        const cls = m[1], role = m[2];
        this.soloRows.push({
          cls, role,
          getAttribute: (k) => (k === "data-solo-sub" ? role : null),
          addEventListener: (ev, fn) => { if (ev === "click") listeners.push(fn); },
          click: () => listeners.forEach((fn) => fn()),
        });
      }
    },
    get innerHTML() { return this._html; },
    querySelectorAll: function (sel) {
      if (sel === ".v9-sub-rollup-btn") return this.buttons;
      if (sel === "tr[data-solo-sub]") return this.soloRows;
      return [];
    },
    closest: () => null,
  };
}

const subBody = makeTbody();
const subPlotSub = { textContent: "" };
const chartHosts = {};
for (const id of ["v9ModelChart", "v9SubagentChart", "v9ProjectChart", "v9CadenceChart", "v9WireScatterWrap"]) {
  chartHosts[id] = {
    id, clientWidth: 0, clientHeight: 0, isConnected: true, innerHTML: "",
    querySelector: () => null, setAttribute: () => {}, removeAttribute: () => {},
  };
}
const observers = [];
const initCalls = [];
const resizeCalls = [];
const rafQueue = [];

class FakeResizeObserver {
  constructor(cb) { this.cb = cb; this.targets = []; observers.push(this); }
  observe(el) { this.targets.push(el); }
  disconnect() { this.targets = []; }
}

const ctx = {
  window: {
    innerWidth: 1440,
    ResizeObserver: FakeResizeObserver,
    addEventListener: () => {},
    removeEventListener: () => {},
    echarts: {
      init: (host) => {
        initCalls.push(host.id);
        let cw = host.clientWidth, ch = host.clientHeight;
        return {
          getDom: () => host, isDisposed: () => false, dispose: () => {},
          getWidth: () => cw, getHeight: () => ch,
          resize: ({ width, height }) => { cw = width; ch = height; resizeCalls.push([host.id, width, height]); },
          setOption: () => {}, dispatchAction: () => {},
        };
      },
    },
    AgyV9: {},
  },
  document: {
    getElementById: (id) => ({
      v9SubagentTableBody: subBody, v9SubPlotSub: subPlotSub,
      v9KpiGrid: { innerHTML: "" }, v9ModelTableBody: makeTbody(),
      ...chartHosts,
    }[id] || null),
  },
  requestAnimationFrame: (fn) => { rafQueue.push(fn); return rafQueue.length; },
  cancelAnimationFrame: () => {},
  setTimeout, clearTimeout, Date, Math, Number, String, Array, Object, Set, Map, JSON, RegExp, Intl,
};
ctx.window.AgyV9 = {
  state: { metric: "steps", surfaceView: "analytics", showUnregSubagents: false, soloSubagent: "", bundle: null },
  escHtml: (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;"),
  fmtNum: (n) => String(Math.round(Number(n || 0))),
  fmtUsd: (n) => `$${Number(n || 0).toFixed(2)}`,
  cssVar: (_k, fb) => fb,
  getSeriesColor: () => "#2563eb",
};
vm.runInNewContext(fs.readFileSync("web/v9/v9_table_sort.js", "utf-8"), ctx);
vm.runInNewContext(fs.readFileSync("web/v9/v9_spark_bars.js", "utf-8"), ctx);
vm.runInNewContext(fs.readFileSync("web/v9/v9_quota_cards.js", "utf-8"), ctx);
vm.runInNewContext(fs.readFileSync("web/v9/v9_analytics.js", "utf-8"), ctx);
vm.runInNewContext(fs.readFileSync("web/v9/v9_charts.js", "utf-8"), ctx);

// (a) Unregistered subagent rollup + singular '1 role' + soloSubagent on child row
const mkSub = (role, isReg, steps) => ({
  role, is_registered: isReg, runs: 2, steps, tokens: steps * 1000, est_cost_usd: 0.5,
  share_pct: 10, avg_steps_per_run: steps / 2, min_steps_per_run: 5, max_steps_per_run: steps - 5,
  last_run_steps: 10, dominant_model_key: "carbon", dominant_model_label: "Carbon 4",
});
const bundle3 = {
  period: { total_days: 30 }, kpis: {},
  subagent_list: [
    mkSub("flash-surgeon", true, 60),
    mkSub("research", false, 30),
    mkSub("wave4-auditor", false, 20),
    mkSub("swarm-orchestrator", false, 10),
  ],
  model_series: { dates: ["2026-11-25"], keys: ["carbon"], layers: { carbon: [10] } },
  subagent_series: { dates: ["2026-11-25"], keys: ["flash-surgeon"], layers: { "flash-surgeon": [10] } },
  project_hierarchy: { dates: ["2026-11-25"], top_projects: [] },
  wire_telemetry: { recent_calls: [{ duration_ms: 12, kb: 1.5, tool: "ask" }] },
  billing_comparison: {},
};
ctx.window.AgyV9.state.bundle = bundle3;
let rerenders = 0;
const rerender = () => { rerenders += 1; ctx.window.AgyV9.Analytics.renderAnalytics(bundle3, rerender, {}); };
ctx.window.AgyV9.Analytics.renderAnalytics(bundle3, rerender, {});
assert.ok(subBody.innerHTML.includes("Unregistered / Ad-hoc (3 roles)"));
assert.strictEqual(subBody.buttons[0].expanded, "false");
assert.ok(!subBody.innerHTML.includes("v9-sub-unreg-child"));

subBody.buttons[0].click();
assert.strictEqual(subBody.buttons[0].expanded, "true");
assert.strictEqual((subBody.innerHTML.match(/v9-sub-unreg-child/g) || []).length, 3);
const childRow = subBody.soloRows.find((r) => r.role === "research");
assert.ok(childRow, "Expected clickable child row for research");
childRow.click();
assert.strictEqual(ctx.window.AgyV9.state.soloSubagent, "research");
assert.strictEqual(rerenders, 1);
assert.ok(subBody.innerHTML.includes('class="v9-row-click va-row-compact v9-sub-unreg-child is-solo" data-solo-sub="research"'));

ctx.window.AgyV9.state.showUnregSubagents = false;
ctx.window.AgyV9.state.soloSubagent = "";
const bundle1 = Object.assign({}, bundle3, { subagent_list: [mkSub("flash-surgeon", true, 60), mkSub("research", false, 20)] });
ctx.window.AgyV9.Analytics.renderAnalytics(bundle1, () => {}, {});
assert.ok(subBody.innerHTML.includes("Unregistered / Ad-hoc (1 role)"));

// (b) V9.Charts 0x0 deferral, ResizeObserver init when w>0, and syncChartsOnLayout stale width catch
ctx.window.AgyV9.Charts.renderAllCharts(bundle3);
assert.strictEqual(initCalls.length, 0, "Hidden 0x0 hosts must defer echarts.init");
for (const h of Object.values(chartHosts)) { h.clientWidth = 800; h.clientHeight = 260; }
observers.forEach((ob) => ob.cb());
while (rafQueue.length) rafQueue.shift()();
assert.ok(initCalls.includes("v9ModelChart") && initCalls.includes("v9SubagentChart") && initCalls.includes("v9ProjectChart"));

for (const h of Object.values(chartHosts)) { h.clientWidth = 640; h.clientHeight = 260; }
const beforeSync = resizeCalls.length;
ctx.window.AgyV9.Charts.syncChartsOnLayout(bundle3);
assert.ok(resizeCalls.length > beforeSync && resizeCalls.some((c) => c[0] === "v9ModelChart" && c[1] === 640));

// (c) Whisker clamping near 100%
const spHtml = ctx.window.AgyV9.SparkBars.renderSubagentWhisker(
  { min: 99.5, avg: 99.8, max: 100, latest: 100, runs: 2, isStepCapOver: false, isHeavyBurn: false, burnRatio: 1.0 },
  100, "steps", "#2563eb"
);
const wm = /class="v9-whisk-bar" style="inset-inline-start:([0-9.]+)%;inline-size:([0-9.]+)%/.exec(spHtml);
assert.ok(wm, "Expected whisker bar style");
assert.ok(Number(wm[1]) + Number(wm[2]) <= 100.0001, `Whisker overflowed 100%: ${wm[1]} + ${wm[2]}`);
console.log("V410_ROLLUP_CHARTS_OK");
"""


def test_v410_subagent_rollup_charts_sync_and_whiskers_node(tmp_path: Path) -> None:
    """Verify unregistered subagent rollup, Charts 0x0 deferral + ResizeObserver sync, whisker clamp, and CSS rules."""
    probe = tmp_path / "rollup_charts_whiskers_probe.cjs"
    probe.write_text(_ROLLUP_CHARTS_WHISKERS_CJS, encoding="utf-8")
    proc = subprocess.run(["node", str(probe)], cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    assert "V410_ROLLUP_CHARTS_OK" in proc.stdout

    spark_js = (WEB_V9 / "v9_spark_bars.js").read_text(encoding="utf-8")
    assert "function renderWhiskerMarkup" in spark_js and "100 - barLeft" in spark_js

    css_text = (WEB_V9 / "v9_tables_and_rail.css").read_text(encoding="utf-8")
    assert len(css_text.splitlines()) <= 300
    assert ".v9-spk-track" in css_text and "padding-inline: 5px;" in css_text
    assert "@media (max-width: 1099px)" in css_text and "flex-direction: column" in css_text
