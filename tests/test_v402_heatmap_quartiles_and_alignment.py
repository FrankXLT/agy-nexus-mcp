"""tests/test_v402_heatmap_quartiles_and_alignment.py — AGY-Nexus v4.0.2 Activity Heatmap Suite."""
from __future__ import annotations

from datetime import date, timedelta
import json
from pathlib import Path
import re
import subprocess
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
WEB_DIR = REPO_ROOT / "web"
V9_DIR = WEB_DIR / "v9"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agy_nexus import __version__, stats


def _make_fake_cache(anchor_day: date) -> dict[str, dict]:
    """Build synthetic multi-month daily telemetry with a huge anchor-day spike."""
    day_steps, day_tokens, day_tools, day_models, day_model_toks, day_cost = {}, {}, {}, {}, {}, {}
    s1_st, s1_tk, s1_cs, s1_m, s1_mt = {}, {}, {}, {}, {}
    for delta in range(75):
        d_iso = (anchor_day - timedelta(days=delta)).strftime("%Y-%m-%d")
        is_spike = delta == 0
        st = 3200 if is_spike else (450 + (delta % 5) * 180)
        tok = 1_250_000_000 if is_spike else (300_000_000 + (delta % 5) * 60_000_000)
        cost_m = 335_000_000 if is_spike else (80_000_000 + (delta % 5) * 11_000_000)
        day_steps[d_iso], day_tokens[d_iso], day_tools[d_iso] = st, tok, st // 2
        day_models[d_iso], day_model_toks[d_iso] = {"carbon": st}, {"carbon": tok}
        day_cost[d_iso] = cost_m
        s1_st[f"{d_iso}T10"], s1_tk[f"{d_iso}T10"], s1_cs[f"{d_iso}T10"] = st, tok, cost_m
        s1_m[f"{d_iso}T10"], s1_mt[f"{d_iso}T10"] = {"carbon": st}, {"carbon": tok}
    return {
        "sess-heatmap-spike": {
            "day_steps": day_steps,
            "day_tokens": day_tokens,
            "day_tools": day_tools,
            "day_models": day_models,
            "day_model_tokens": day_model_toks,
            "day_cost_micros": day_cost,
            "slot_1h_steps": s1_st,
            "slot_1h_tokens": s1_tk,
            "slot_1h_cost_micros": s1_cs,
            "slot_1h_models": s1_m,
            "slot_1h_model_tokens": s1_mt,
            "last_conv_model": "carbon",
        }
    }


def test_backend_trailing_52w_strip_and_in_window_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Both to_date (MTD/QTD/YTD) and rolling presets must emit a trailing 52-53w strip anchored at end_d."""
    anchor = date(2026, 11, 22)
    fake_cache = _make_fake_cache(anchor)
    monkeypatch.setattr(stats, "scan_transcript_stats", lambda *_a, **_kw: fake_cache)
    monkeypatch.setattr(stats, "get_code_health_summary", lambda *_a, **_kw: {"version": {"installed": __version__, "status": "up_to_date"}})
    monkeypatch.setattr(stats, "merge_and_persist_cost_ledger", lambda *_a, **_kw: {"entries": {}})
    monkeypatch.setattr(stats, "load_cost_ledger", lambda *_a, **_kw: {"entries": {}})
    for sub in ("cfg", "bg", "brain"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)

    # Mock today = 2026-11-22 via stats.datetime
    class _FixedDt(stats.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 22, 18, 0, 0, tzinfo=tz)

    monkeypatch.setattr(stats, "datetime", _FixedDt)

    mtd = stats.build_nexus_stats_bundle(
        data_dir=tmp_path, brain_dir=tmp_path / "brain", db_file=tmp_path / "missing.db",
        agy_config_dir=tmp_path / "cfg", bg_dir=tmp_path / "bg",
        timeframe="month", horizon_mode="to_date", anchor_date="2026-11-22", include_ascii=False,
    )
    hm_mtd = mtd["heatmap_series"]
    assert len(hm_mtd) == 364
    assert hm_mtd[0]["date"] == "2025-11-24"
    assert hm_mtd[-1]["date"] == "2026-11-22"
    assert all(not c["future"] for c in hm_mtd)
    in_win_mtd = [c["date"] for c in hm_mtd if c["in_window"]]
    assert len(in_win_mtd) == 22 and in_win_mtd[0] == "2026-11-01" and in_win_mtd[-1] == "2026-11-22"

    r90 = stats.build_nexus_stats_bundle(
        data_dir=tmp_path, brain_dir=tmp_path / "brain", db_file=tmp_path / "missing.db",
        agy_config_dir=tmp_path / "cfg", bg_dir=tmp_path / "bg",
        timeframe="quarter", horizon_mode="rolling", anchor_date="2026-11-22", include_ascii=False,
    )
    hm_90 = r90["heatmap_series"]
    assert len(hm_90) == 364
    assert hm_90[0]["date"] == "2025-11-24" and hm_90[-1]["date"] == "2026-11-22"
    in_win_90 = [c["date"] for c in hm_90 if c["in_window"]]
    assert len(in_win_90) == 91 and in_win_90[0] == "2026-08-24" and in_win_90[-1] == "2026-11-22"

    # Late-December YTD in a Sunday-Jan-1 year (2023-12-31) must still preserve 2023-01-01 in chart_days.
    class _FixedDt2023(stats.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2023, 12, 31, 18, 0, 0, tzinfo=tz)

    monkeypatch.setattr(stats, "datetime", _FixedDt2023)
    ytd_2023 = stats.build_nexus_stats_bundle(
        data_dir=tmp_path, brain_dir=tmp_path / "brain", db_file=tmp_path / "missing.db",
        agy_config_dir=tmp_path / "cfg", bg_dir=tmp_path / "bg",
        timeframe="year", horizon_mode="to_date", anchor_date="2023-12-31", include_ascii=False,
    )
    assert ytd_2023["velocity_series"]["dates"][0] == "2023-01-01"
    assert len(ytd_2023["velocity_series"]["dates"]) == 365


def test_v9_heatmap_quartiles_month_headers_and_full_width_grid(tmp_path: Path) -> None:
    """Verify uniform quartiles across Steps/Tokens/Cost, 1st-of-month headers, fallback, and matched track grids."""
    probe = tmp_path / "v9_heatmap_check.cjs"
    probe.write_text(
        """
const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

const summaryEl = { textContent: "" };
const hostEl = { innerHTML: "", querySelectorAll: () => [] };
const btnEl = { dataset: {}, classList: { toggle: () => {} }, addEventListener: () => {}, textContent: "" };

const ctx = {
  window: { innerWidth: 1440, AgyV9: {} },
  document: {
    getElementById: (id) => ({ v9HeatHost: hostEl, v9HeatSummary: summaryEl, v9HeatWeeksBtn: btnEl }[id] || null),
  },
};
ctx.window.AgyV9 = {
  state: { metric: "steps", heatWeeks: 53, heatPinned: false },
  escHtml: (s) => String(s == null ? "" : s),
  fmtNum: (n) => String(n),
  fmtUsd: (n) => `$${Number(n || 0).toFixed(2)}`,
};
vm.runInNewContext(fs.readFileSync("web/v9/v9_heatmap.js", "utf-8"), ctx);
const HM = ctx.window.AgyV9.Heatmap;

// 1. Trailing 52w strip ending Sun 2026-11-22: Nov 1 is Sunday in col 48 (Oct 26 - Nov 1)
const series = [];
const start = new Date(Date.UTC(2025, 10, 24));
for (let i = 0; i < 364; i++) {
  const d = new Date(start.getTime() + i * 86400000);
  const iso = d.toISOString().slice(0, 10);
  const inWin = iso >= "2026-08-24";
  const isSpike = iso === "2026-11-22";
  const isActive = iso >= "2026-10-01";
  const steps = isSpike ? 3500 : (isActive ? 400 + (i % 7) * 140 : 0);
  const tokens = isSpike ? 1_250_000_000 : (isActive ? 300_000_000 + (i % 7) * 45_000_000 : 0);
  const cost_usd = isSpike ? 335 : (isActive ? 80 + (i % 7) * 8 : 0);
  series.push({ date: iso, weekday: i % 7, steps, tokens, cost_usd, sessions: isActive ? 3 : 0, level: 1, future: false, in_window: inWin });
}

const { cols, keepCols } = HM.buildWeeksMatrix(series, 53);
assert.strictEqual(keepCols, 52);
const mLabels = HM.buildMonthLabels(cols);
assert.strictEqual(mLabels[48], "Nov", "Nov 1 (Sun) must label week col 48 (Oct 26 - Nov 1)");
assert.strictEqual(mLabels[49], "", "Mon Nov 2 must not steal Nov label");
assert.strictEqual(mLabels[1], "Dec");
assert.strictEqual(mLabels[0], "", "Col 0 mid-month stub cleared when col 1 starts Dec");
assert.strictEqual(mLabels[5], "Jan");

// Spacing guard >= 3 columns between visible month labels
const labelCols = mLabels.map((lbl, idx) => (lbl ? idx : -1)).filter((x) => x >= 0);
for (let i = 1; i < labelCols.length; i++) {
  assert.ok(labelCols[i] - labelCols[i - 1] >= 3, `Labels too close at ${labelCols[i - 1]} and ${labelCols[i]}`);
}

// 2. Quartiles prevent spike washout across Steps, Tokens, and $ Cost
for (const metric of ["steps", "tokens", "cost"]) {
  ctx.window.AgyV9.state.metric = metric;
  HM.renderHeatmap({ heatmap_series: series });
  assert.ok(hostEl.innerHTML.includes(`v9-heat-months" style="grid-template-columns:repeat(52,minmax(10px,1fr))"`));
  assert.ok(hostEl.innerHTML.includes(`v9-heat-grid" style="grid-template-columns:repeat(52,minmax(10px,1fr))"`));
  const lvl3or4 = (hostEl.innerHTML.match(/data-level="(?:3|4)"/g) || []).length;
  assert.ok(lvl3or4 >= 12, `Metric ${metric} collapsed under spike day: only ${lvl3or4} level 3/4 cells`);
}

// 3. Fallback when < 4 active days exist in window (e.g. only Nov 21-22 in_window)
const sparseWinSeries = series.map((c) => Object.assign({}, c, { in_window: c.date >= "2026-11-21" }));
ctx.window.AgyV9.state.metric = "cost";
HM.renderHeatmap({ heatmap_series: sparseWinSeries });
assert.ok(hostEl.innerHTML.includes('class="v9-heat-cell is-out"'), "Out-of-window cells must get is-out");
assert.ok(hostEl.innerHTML.includes("(outside window)"), "Out-of-window tooltip must note outside window");
// 2026-10-15 ($112) is below P75 of strip if spike is $335, should still get >= level 2 (not 0 or flattened)
assert.strictEqual(HM.computeMetricLevel({ cost_usd: 112 }, "cost", HM.computeQuartiles([80, 88, 96, 104, 112, 120, 128, 335])), 3);

// 4. Mobile 26w default
ctx.window.innerWidth = 390;
ctx.window.AgyV9.state.heatPinned = false;
HM.renderHeatmap({ heatmap_series: series });
assert.ok(hostEl.innerHTML.includes("grid-template-columns:repeat(26,minmax(10px,1fr))"));
console.log("V9_HEATMAP_OK");
""",
        encoding="utf-8",
    )
    proc = subprocess.run(["node", str(probe)], cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"
    assert "V9_HEATMAP_OK" in proc.stdout


def test_v402_heatmap_css_and_workflows_contracts() -> None:
    """Verify v9_analytics.css zero !important, <=500L, .is-out dimming, full-width tracks, and WORKFLOWS.md v4.0.2."""
    css_txt = (V9_DIR / "v9_analytics.css").read_text(encoding="utf-8")
    assert len(css_txt.splitlines()) <= 500
    assert "!important" not in css_txt
    assert "justify-content: start;" not in css_txt
    assert "grid-auto-columns: minmax(10px, 1fr);" in css_txt
    assert "filter: grayscale(0.92); opacity: 0.28;" in css_txt
    assert '.v9-heat-cell.is-out[data-level="0"] { opacity: 0.42; }' in css_txt
    assert ".v9-heat-cell.is-out:hover { filter: grayscale(0.25); opacity: 0.85; }" in css_txt
    assert re.search(r"@media \(max-width:\s*639px\)[\s\S]*\.v9-heat-grid\s*\{\s*gap:\s*2px;\s*\}", css_txt)

    wf_txt = (REPO_ROOT / "docs" / "WORKFLOWS.md").read_text(encoding="utf-8")
    assert "Workflow 6:" in wf_txt and "v4.0.6" in wf_txt
    assert "Consistent Quartile Buckets Across Metrics" in wf_txt
    assert "Clear Out-of-Window Desaturation" in wf_txt
    assert "Full-Width Trailing 52-Week Strip & 1st-of-Month Headers" in wf_txt
