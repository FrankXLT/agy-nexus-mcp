"""tests/test_v409_wave1_heatmap_and_ci.py — AGY-Nexus v4.0.9 Wave 1 Heatmap & PR CI Gate."""
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
WEB_DIR = REPO_ROOT / "web"
V9_DIR = WEB_DIR / "v9"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agy_nexus import polyglot_outline


def test_v409_wave1_theme_tokens_and_heatmap_css_budgets() -> None:
    """Verify matched-lightness grayscale tokens across all 4 themes, stepped dividers, soft-red ring, and <=500L budgets."""
    shell_css = (V9_DIR / "v9_shell.css").read_text(encoding="utf-8")
    assert len(shell_css.splitlines()) <= 500
    assert "!important" not in shell_css

    for theme_sel in ('[data-theme="white"]', '[data-theme="paper"]', '[data-theme="dark-paper"]', '[data-theme="dark"]'):
        m = re.search(rf"{re.escape(theme_sel)}\s*\{{([^}}]+)\}}", shell_css)
        assert m is not None, f"Missing theme block: {theme_sel}"
        blk = m.group(1)
        for tok in ("--v9-heat-out-0:", "--v9-heat-out-1:", "--v9-heat-out-2:", "--v9-heat-out-3:", "--v9-heat-out-4:", "--v9-heat-divider:", "--v9-heat-selected:"):
            assert tok in blk, f"Missing {tok} in {theme_sel}"

    an_css = (V9_DIR / "v9_analytics.css").read_text(encoding="utf-8")
    assert len(an_css.splitlines()) <= 500
    assert "!important" not in an_css
    assert "opacity: 0.28;" not in an_css
    for rule in (
        ".v9-heat-row { grid-column: 1 / -1; display: grid; grid-template-columns: subgrid; }",
        ".v9-heat-cell.is-selected",
        ".v9-heat-cell.has-month-left::before",
        ".v9-heat-cell.has-month-top::after",
        ".v9-heat-inspect-swatch",
        "forced-colors: active",
        "button.v9-heat-cell { min-block-size: 14px;",
    ):
        assert rule in an_css, f"Missing CSS rule: {rule}"

    hm_js = (V9_DIR / "v9_heatmap.js").read_text(encoding="utf-8")
    hm_lines = hm_js.splitlines()
    assert len(hm_lines) <= 500
    assert not re.search(r"[🔒✦⬇◀▶✓✕]", hm_js)
    _s, _f, syms = polyglot_outline.outline_code(".js", hm_lines)
    assert not any(int(sym.get("lines") or 0) > 100 for sym in syms)

    app_js = (V9_DIR / "v9_app.js").read_text(encoding="utf-8")
    assert len(app_js.splitlines()) <= 500
    assert 'st.heatSelectedDate = ""' in app_js and 'st.heatPeriodKey = ""' in app_js
    assert (WEB_DIR / "index.html").read_text(encoding="utf-8") == (V9_DIR / "index.html").read_text(encoding="utf-8")


_HEATMAP_DOM_PROBE_JS = """
const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

function parseAttrs(raw) {
  const attrs = {};
  const re = /([a-zA-Z0-9_-]+)="([^"]*)"/g;
  let m;
  while ((m = re.exec(raw)) !== null) attrs[m[1]] = m[2];
  return attrs;
}

function makeFakeElement(tag, attrs, colIdx, rowIdx, gridRef, docRef) {
  const listeners = {};
  const clsSet = new Set((attrs.class || "").split(/\\s+/).filter(Boolean));
  const el = {
    tagName: tag.toUpperCase(),
    attrs: Object.assign({}, attrs),
    classList: {
      add: (c) => { clsSet.add(c); el.attrs.class = Array.from(clsSet).join(" "); },
      remove: (c) => { clsSet.delete(c); el.attrs.class = Array.from(clsSet).join(" "); },
      contains: (c) => clsSet.has(c),
    },
    getAttribute: (k) => (k === "class" ? el.attrs.class : (el.attrs[k] !== undefined ? el.attrs[k] : null)),
    setAttribute: (k, v) => { el.attrs[k] = String(v); if (k === "class") { clsSet.clear(); String(v).split(/\\s+/).filter(Boolean).forEach((c) => clsSet.add(c)); } },
    addEventListener: (ev, fn) => { (listeners[ev] = listeners[ev] || []).push(fn); },
    dispatch: (ev, extra) => {
      const payload = Object.assign({ target: el, preventDefaultCalled: false, preventDefault() { this.preventDefaultCalled = true; } }, extra || {});
      (listeners[ev] || []).forEach((fn) => fn(payload));
      if (gridRef) (gridRef._listeners[ev] || []).forEach((fn) => fn(payload));
      return payload;
    },
    closest: (sel) => (sel === "button.v9-heat-cell" && el.tagName === "BUTTON" && clsSet.has("v9-heat-cell") ? el : null),
    checkVisibility: () => true,
    getBoundingClientRect: () => ({ left: colIdx * 18, right: colIdx * 18 + 14, top: rowIdx * 17, bottom: rowIdx * 17 + 14, width: 14, height: 14 }),
    focus: () => { docRef.activeElement = el; },
    scrollIntoView: () => {},
  };
  return el;
}

const inspectEl = { innerHTML: "", textContent: "" };
const summaryEl = { textContent: "" };
const btnEl = { dataset: {}, classList: { toggle: () => {} }, addEventListener: () => {}, textContent: "" };
let cells = [];
let gridObj = null;
const docStub = {
  activeElement: null,
  getElementById: (id) => ({ v9HeatHost: hostEl, v9HeatInspect: inspectEl, v9HeatSummary: summaryEl, v9HeatWeeksBtn: btnEl }[id] || null),
};
const hostEl = {
  _html: "",
  set innerHTML(val) {
    this._html = val;
    cells = [];
    gridObj = {
      _listeners: {},
      contains: (el) => cells.includes(el),
      addEventListener: (ev, fn) => { (gridObj._listeners[ev] = gridObj._listeners[ev] || []).push(fn); },
      querySelectorAll: (sel) => (
        (sel.includes("tabindex='0'") || sel.includes("is-selected"))
          ? cells.filter((c) => c.getAttribute("tabindex") === "0" || c.classList.contains("is-selected"))
          : cells
      ),
      querySelector: (sel) => (sel.includes("is-selected") ? (cells.find((c) => c.classList.contains("is-selected")) || null) : null),
      dispatch: (ev, extra) => {
        const payload = Object.assign({ preventDefaultCalled: false, preventDefault() { this.preventDefaultCalled = true; } }, extra || {});
        (gridObj._listeners[ev] || []).forEach((fn) => fn(payload));
        return payload;
      },
    };
    const rowRe = /<div class="v9-heat-row" role="row">([\\s\\S]*?)<\\/div>/g;
    let rm;
    let rIdx = 0;
    while ((rm = rowRe.exec(val)) !== null) {
      const cellRe = /<(button|span)\\b([^>]*)>/g;
      let cm;
      let cIdx = 0;
      while ((cm = cellRe.exec(rm[1])) !== null) {
        if (cm[1] === "button") cells.push(makeFakeElement("button", parseAttrs(cm[2]), cIdx, rIdx, gridObj, docStub));
        cIdx += 1;
      }
      rIdx += 1;
    }
  },
  get innerHTML() { return this._html; },
  querySelector: (sel) => (sel === ".v9-heat-grid" ? gridObj : null),
};

const ctx = { window: { innerWidth: 1440, AgyV9: {} }, document: docStub };
ctx.window.AgyV9 = {
  state: { metric: "steps", heatWeeks: 53, heatPinned: false, heatSelectedDate: "", heatPeriodKey: "" },
  escHtml: (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;"),
  fmtNum: (n) => Math.round(Number(n || 0)).toLocaleString("en-US"),
  fmtUsd: (n) => `$${Number(n || 0).toFixed(2)}`,
};
vm.runInNewContext(fs.readFileSync("web/v9/v9_heatmap.js", "utf-8"), ctx);
const V9 = ctx.window.AgyV9;
const HM = V9.Heatmap;

const series = [];
const start = new Date(Date.UTC(2025, 10, 24));
for (let i = 0; i < 371; i++) {
  const d = new Date(start.getTime() + i * 86400000);
  const iso = d.toISOString().slice(0, 10);
  const future = iso > "2026-11-24";
  const inWin = !future && iso >= "2026-11-01";
  const isActive = !future && iso >= "2026-09-01";
  series.push({
    date: iso, weekday: i % 7,
    steps: isActive ? (iso === "2026-11-24" ? 3840 : 1200 + (i % 5) * 300) : 0,
    tokens: isActive ? (iso === "2026-11-24" ? 308800000 : 120000000) : 0,
    cost_usd: isActive ? (iso === "2026-11-24" ? 77.35 : 22.5) : 0,
    sessions: isActive ? 5 : 0, future, in_window: inWin,
  });
}

const mtdPeriod = { key: "current_month", timeframe: "month", horizon_mode: "to_date", offset: 0, start_date: "2026-11-01", end_date: "2026-11-24" };
HM.renderHeatmap({ period: mtdPeriod, heatmap_series: series });

const nov1 = cells.find((c) => c.getAttribute("data-date") === "2026-11-01");
const nov2 = cells.find((c) => c.getAttribute("data-date") === "2026-11-02");
const oct31 = cells.find((c) => c.getAttribute("data-date") === "2026-10-31");
assert.ok(nov1.classList.contains("has-month-left") && nov1.classList.contains("has-month-top") && nov1.classList.contains("is-row-bot"));
assert.ok(nov2.classList.contains("has-month-left") && nov2.classList.contains("is-row-top"));
assert.ok(!oct31.classList.contains("has-month-left") && !oct31.classList.contains("has-month-top"));

const nov24 = cells.find((c) => c.getAttribute("data-date") === "2026-11-24");
assert.ok(nov24.classList.contains("is-selected") && nov24.getAttribute("aria-selected") === "true");
assert.strictEqual(nov24.getAttribute("tabindex"), "0");
assert.ok(inspectEl.innerHTML.includes("v9-heat-inspect-swatch"));
assert.ok(inspectEl.innerHTML.includes("Tue, Nov 24, 2026") && inspectEl.innerHTML.includes("3,840 steps"));

const oct15 = cells.find((c) => c.getAttribute("data-date") === "2026-10-15");
assert.ok(oct15.classList.contains("is-out"));
oct15.dispatch("click");
assert.strictEqual(V9.state.heatSelectedDate, "2026-10-15");
assert.ok(oct15.classList.contains("is-selected") && !nov24.classList.contains("is-selected"));
assert.ok(inspectEl.innerHTML.includes("Thu, Oct 15, 2026") && inspectEl.innerHTML.includes("Outside MTD"));
assert.ok(inspectEl.innerHTML.includes("v9-heat-inspect-swatch is-out"));

nov24.dispatch("mouseenter");
assert.ok(inspectEl.innerHTML.includes("Tue, Nov 24, 2026") && inspectEl.innerHTML.includes("is-preview"));
gridObj.dispatch("mouseleave");
assert.ok(inspectEl.innerHTML.includes("Thu, Oct 15, 2026") && !inspectEl.innerHTML.includes("is-preview"));

V9.state.metric = "cost";
HM.renderHeatmap({ period: mtdPeriod, heatmap_series: series });
assert.strictEqual(V9.state.heatSelectedDate, "2026-10-15");
assert.ok(inspectEl.innerHTML.includes("Thu, Oct 15, 2026") && inspectEl.innerHTML.includes("$22.50") && inspectEl.innerHTML.includes("Outside MTD"));

const oct15Re = cells.find((c) => c.getAttribute("data-date") === "2026-10-15");
oct15Re.focus();
const evRight = oct15Re.dispatch("keydown", { key: "ArrowRight" });
assert.strictEqual(evRight.preventDefaultCalled, true);
assert.strictEqual(V9.state.heatSelectedDate, "2026-10-22");
const monCell = cells.find((c) => c.getAttribute("data-date") === "2026-10-19");
monCell.focus();
assert.strictEqual(monCell.dispatch("keydown", { key: "ArrowUp" }).preventDefaultCalled, false);
const nov24Btn = cells.find((c) => c.getAttribute("data-date") === "2026-11-24");
nov24Btn.focus();
assert.strictEqual(nov24Btn.dispatch("keydown", { key: "ArrowDown" }).preventDefaultCalled, false);
monCell.focus();
monCell.dispatch("keydown", { key: "End" });
assert.strictEqual(V9.state.heatSelectedDate, "2026-11-24");

const octPeriod = { key: "last_month", timeframe: "month", horizon_mode: "to_date", offset: -1, label: "Oct 2026", start_date: "2026-10-01", end_date: "2026-10-31" };
const octSeries = series.filter((d) => d.date <= "2026-11-01").map((d) => Object.assign({}, d, { future: false, in_window: d.date >= "2026-10-01" && d.date <= "2026-10-31" }));
HM.renderHeatmap({ period: octPeriod, heatmap_series: octSeries });
assert.strictEqual(V9.state.heatSelectedDate, "2026-10-31");

const zeroWin = series.map((d) => Object.assign({}, d, d.in_window ? { steps: 0, tokens: 0, cost_usd: 0, sessions: 0 } : {}));
V9.state.heatSelectedDate = "";
HM.renderHeatmap({ period: { key: "empty_win", timeframe: "month", horizon_mode: "to_date", offset: 0, start_date: "2026-11-01", end_date: "2026-11-24" }, heatmap_series: zeroWin });
assert.strictEqual(V9.state.heatSelectedDate, "2026-10-31");
assert.ok(inspectEl.innerHTML.includes("Outside MTD"));

const allZero = series.map((d) => Object.assign({}, d, { steps: 0, tokens: 0, cost_usd: 0, sessions: 0 }));
HM.renderHeatmap({ period: { key: "all_zero", timeframe: "month", horizon_mode: "to_date", offset: 0, start_date: "2026-11-01", end_date: "2026-11-24" }, heatmap_series: allZero });
assert.strictEqual(V9.state.heatSelectedDate, "");
assert.strictEqual(inspectEl.textContent, "Hover or tap any day to inspect activity counts");
console.log("V409_HEATMAP_OK");
"""


def test_v409_wave1_heatmap_dividers_selection_hover_and_keyboard(tmp_path: Path) -> None:
    """Verify stepped Oct/Nov dividers, auto-selection, metric-switch pinning, hover revert, and arrow-key spatial grid."""
    probe = tmp_path / "v409_heatmap_dom.cjs"
    probe.write_text(_HEATMAP_DOM_PROBE_JS, encoding="utf-8")
    proc = subprocess.run(["node", str(probe)], cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    assert "V409_HEATMAP_OK" in proc.stdout


def test_v409_wave1_ci_workflow_contributing_and_workflows_doc() -> None:
    """Verify .github/workflows/ci.yml verify gate, CONTRIBUTING.md, and docs/WORKFLOWS.md Wave 1 updates."""
    ci_yml = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for token in (
        "pull_request:", "push:", "- main", "- develop", "verify:",
        "pytest", "python3 ag_bridge.py --self-test", "python3 -m agy_nexus.tools_praxis --self-test",
        "python3 scripts/sync_agents.py --check", "python3 scripts/build_github_showcase.py",
        "docker build", "--stdio",
    ):
        assert token in ci_yml, f"Missing CI token: {token}"

    contrib = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "develop" in contrib and ".github/workflows/ci.yml" in contrib and "verify" in contrib

    wf_doc = (REPO_ROOT / "docs" / "WORKFLOWS.md").read_text(encoding="utf-8")
    for banned in ("diurnal", "plain-english", "posture", "surface"):
        assert banned not in wf_doc.lower(), f"Banned word '{banned}' in docs/WORKFLOWS.md"
    for expected in ("Out-of-Window Grayscale", "Stepped Month Divider", "Selected Cell Ring", "Protected-`main` PR CI Gate (`verify`)"):
        assert expected in wf_doc, f"Missing '{expected}' in docs/WORKFLOWS.md"
