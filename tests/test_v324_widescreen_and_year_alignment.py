#!/usr/bin/env python3
"""
tests/test_v324_widescreen_and_year_alignment.py — AGY-Nexus v3.2.4 Verification Suite.

Covers:
1. Year timeframe (ytd & last_year) 24h daily slot grid and full calendar horizon alignment.
2. /web & /web/sw.js no-store Cache-Control headers, PWA_ASSETS parity, and SW root HTML exclusion.
3. /web/api/workspace/tree version payload & updateVersionBadge() hydration on direct #workspace visits.
4. Heatmap collision-safe month header engine (2026 Jan..Dec & partial col-0 stub override).
5. Resizable Workspace splitter (clampWidth, drag/keyboard persistence, double-click reset).
6. Gallery toolbar ("Per Sheet", disabled Share styling) & empty-ring unselected badges.
7. charts.js YTD demo period mapping and Pure White / widescreen CSS contracts.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import re
import subprocess
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agy_nexus import __version__
from agy_nexus import bucket_api, stats, web_routes
from agy_nexus.stats_series import build_base_slot_grid


def _run_node(tmp_path: Path, js_code: str) -> str:
    """Execute a temporary CommonJS verification script via Node.js."""
    runner = tmp_path / "node_check.cjs"
    preamble = f'const __repoRoot = {json.dumps(str(REPO_ROOT))};\nconst __webMod = (n) => require(require("path").join(__repoRoot, "web", n));\n'
    runner.write_text(preamble + js_code, encoding="utf-8")
    res = subprocess.run(["node", str(runner)], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True)
    return res.stdout.strip()


def _asgi_get(req_path: str) -> tuple[int, dict[str, str], bytes]:
    """Invoke handle_web_request directly via an in-memory ASGI collector."""
    captured: dict[str, object] = {"status": 0, "headers": {}, "body": bytearray()}

    async def _receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def _send(msg: dict[str, object]) -> None:
        if msg["type"] == "http.response.start":
            captured["status"] = int(msg["status"])
            captured["headers"] = {
                k.decode("latin1").lower(): v.decode("latin1")
                for k, v in (msg.get("headers") or [])
            }
        elif msg["type"] == "http.response.body":
            captured["body"].extend(msg.get("body") or b"")

    async def _run() -> bool:
        return await web_routes.handle_web_request(
            {"type": "http", "method": "GET", "path": req_path},
            _receive,
            _send,
            REPO_ROOT / "web",
            req_path,
            "GET",
            [],
        )

    handled = asyncio.run(_run())
    assert handled is True, f"Route was not handled: {req_path}"
    return int(captured["status"]), dict(captured["headers"]), bytes(captured["body"])


def test_year_timeframe_24h_slots_and_full_calendar_alignment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Year periods must force 24h daily slots and preserve the full Year span across all series."""
    today = datetime.now(stats.DISPLAY_TZ).date()
    today_iso = today.strftime("%Y-%m-%d")
    short_days = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(58, -1, -1)]

    for key in ("ytd", "last_year", "year", "year_rolling", "year_2025"):
        labels, _groups, step_h, res_lbl = build_base_slot_grid(key, short_days, today_iso, 16)
        assert step_h == 24
        assert res_lbl == "24h daily"
        assert labels == short_days

    for key in ("current_month", "last_90d"):
        _labels, _groups, step_h, res_lbl = build_base_slot_grid(key, short_days[-14:], today_iso, 16)
        assert step_h == 1
        assert res_lbl == "1h base slots"

    act_day = (today - timedelta(days=3)).strftime("%Y-%m-%d")
    fake_cache = {
        "sess-late": {
            "day_steps": {act_day: 25},
            "day_tokens": {act_day: 5000},
            "day_tools": {act_day: 4},
            "day_models": {act_day: {"carbon": 25}},
            "day_model_tokens": {act_day: {"carbon": 5000}},
            "slot_1h_steps": {f"{act_day}T10": 25},
            "slot_1h_tokens": {f"{act_day}T10": 5000},
            "slot_1h_models": {f"{act_day}T10": {"carbon": 25}},
            "slot_1h_model_tokens": {f"{act_day}T10": {"carbon": 5000}},
            "last_conv_model": "carbon",
        }
    }
    monkeypatch.setattr(stats, "scan_transcript_stats", lambda *_a, **_kw: fake_cache)
    monkeypatch.setattr(stats, "get_code_health_summary", lambda *_a, **_kw: {"version": {"installed": __version__, "status": "staged_locally"}})

    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    (tmp_path / "bg").mkdir(parents=True, exist_ok=True)
    (tmp_path / "brain").mkdir(parents=True, exist_ok=True)

    ytd = stats.build_nexus_stats_bundle(
        data_dir=tmp_path, brain_dir=tmp_path / "brain", db_file=tmp_path / "missing.db",
        agy_config_dir=tmp_path / "cfg", bg_dir=tmp_path / "bg",
        timeframe="year", horizon_mode="to_date", anchor_date=today_iso,
    )
    jan1 = f"{today.year}-01-01"
    expected_ytd_days = (today - date(today.year, 1, 1)).days + 1
    assert ytd["period"]["key"] == "ytd"
    assert ytd["period"]["resolution"] == "24h daily"
    assert ytd["velocity_series"]["step_hours"] == 24
    assert ytd["velocity_series"]["dates"][0] == jan1
    assert ytd["velocity_series"]["dates"][-1] == today_iso
    assert len(ytd["velocity_series"]["dates"]) == expected_ytd_days
    assert len(ytd["model_series"]["dates"]) == expected_ytd_days
    assert len(ytd["workspace_series"]["dates"]) == expected_ytd_days
    assert len(ytd["subagent_series"]["dates"]) == expected_ytd_days
    assert len(ytd["project_hierarchy"]["dates"]) == expected_ytd_days

    rolling = stats.build_nexus_stats_bundle(
        data_dir=tmp_path, brain_dir=tmp_path / "brain", db_file=tmp_path / "missing.db",
        agy_config_dir=tmp_path / "cfg", bg_dir=tmp_path / "bg",
        timeframe="year", horizon_mode="rolling", anchor_date=today_iso,
    )
    assert rolling["period"]["key"] == "last_year"
    assert rolling["period"]["resolution"] == "24h daily"
    assert rolling["velocity_series"]["step_hours"] == 24
    assert len(rolling["velocity_series"]["dates"]) == 364


def test_web_routes_no_store_headers_and_pwa_assets_parity() -> None:
    """/web HTML & sw.js must send no-store headers and register v4.0.8 Quiet UI JS assets."""
    assert "v9/v9_heatmap.js" in web_routes.PWA_ASSETS
    assert "v9/v9_workspace.js" in web_routes.PWA_ASSETS

    for route in ("/web", "/web/index.html", "/web/v9", "/web/sw.js"):
        st, hdrs, _body = _asgi_get(route)
        assert st == 200
        assert hdrs.get("cache-control") == "no-store, no-cache, must-revalidate"
        if route.endswith("sw.js"):
            assert hdrs.get("service-worker-allowed") == "/"

    for asset in ("/web/v9/v9_heatmap.js", "/web/v9/v9_workspace.js"):
        st, hdrs, body = _asgi_get(asset)
        assert st == 200
        assert "application/javascript" in hdrs.get("content-type", "")
        assert len(body) > 200

    html_txt = (REPO_ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert '/web/v9/v9_heatmap.js?v=4.0.9' in html_txt
    assert '/web/v9/v9_workspace.js?v=4.0.9' in html_txt


def test_sw_excludes_root_html_from_shell_cache(tmp_path: Path) -> None:
    """Service Worker must never precache or runtime-cache /web or /web/index.html HTML."""
    out = _run_node(
        tmp_path,
        """
const assert = require("assert");
const fs = require("fs");
const vm = require("vm");
const swCode = fs.readFileSync("web/sw.js", "utf-8");
const ctx = {
  self: { location: { origin: "https://nexus.example.com" }, addEventListener: () => {}, skipWaiting: () => {}, clients: { claim: () => {} } },
  caches: { open: async () => ({ addAll: async () => {}, put: async () => {} }), keys: async () => [], match: async () => null },
  URL,
};
vm.runInNewContext(swCode + "; globalThis.__sw = { CACHE_NAME, SHELL_ASSETS, SHELL_NAMES, isCacheableShellAsset };", ctx);
const sw = ctx.__sw;
assert.ok(sw.CACHE_NAME.includes("4.0.9"));
assert.ok(!sw.SHELL_ASSETS.includes("/web"));
assert.ok(!sw.SHELL_ASSETS.includes("/web/index.html"));
assert.ok(sw.SHELL_ASSETS.includes("/web/v9/v9_heatmap.js?v=4.0.9"));
assert.ok(sw.SHELL_ASSETS.includes("/web/v9/v9_workspace.js?v=4.0.9"));
const bareReq = { headers: new Map() };
assert.strictEqual(sw.isCacheableShellAsset(new URL("https://nexus.example.com/web"), bareReq), false);
assert.strictEqual(sw.isCacheableShellAsset(new URL("https://nexus.example.com/web/index.html"), bareReq), false);
assert.strictEqual(sw.isCacheableShellAsset(new URL("https://nexus.example.com/web/v9/v9_heatmap.js"), bareReq), true);
assert.strictEqual(sw.isCacheableShellAsset(new URL("https://nexus.example.com/secret_tok/web/v9/v9_heatmap.js"), bareReq), true);
assert.strictEqual(sw.isCacheableShellAsset(new URL("https://nexus.example.com/web/v9/v9_heatmap.js"), { headers: new Map([["X-Nexus-Passphrase", "abc"]]) }), false);
console.log("SW_OK");
""",
    )
    assert out == "SW_OK"


def test_workspace_tree_payload_exposes_version_and_hydrates_badge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Workspace tree API must include version metadata so direct /web#workspace loads update #versionLabel."""
    monkeypatch.setattr(bucket_api, "build_project_session_tree", lambda **_kw: {"projects": []})
    monkeypatch.setattr(bucket_api, "list_handoff_tickets", lambda *_a, **_kw: {"tickets": []})
    monkeypatch.setattr(
        bucket_api,
        "get_code_health_summary",
        lambda *_a, **_kw: {"version": {"installed": __version__, "remote": "3.2.3", "status": "staged_locally", "status_label": "Staged Locally"}},
    )
    payload = bucket_api.build_workspace_tree_payload()
    assert payload["ok"] is True
    assert payload["version"] == __version__
    assert payload["version_info"]["installed"] == __version__

    out = _run_node(
        tmp_path,
        f"""
const assert = require("assert");
const els = {{
  versionDot: {{ className: "status-dot-6px amber" }},
  versionLabel: {{ textContent: "v3.2.2" }},
  versionTag: {{ title: "" }},
}};
global.document = {{ getElementById: (id) => els[id] || null }};
global.window = {{}};
const {{ updateVersionBadge }} = __webMod("health.js");
const dotCls = updateVersionBadge({{ installed: "{__version__}", status: "staged_locally", status_label: "Staged Locally" }}, "{__version__}");
assert.strictEqual(dotCls, "cyan");
assert.strictEqual(els.versionLabel.textContent, "v{__version__}");
assert.strictEqual(els.versionDot.className, "status-dot-6px cyan");
console.log("BADGE_OK");
""",
    )
    assert out == "BADGE_OK"


def test_heatmap_month_headers_include_jan_2026_and_prior_stub_override(tmp_path: Path) -> None:
    """2026 53-week Monday-aligned heatmap must display Jan (plus Feb..Dec) instead of Dec..Feb."""
    out = _run_node(
        tmp_path,
        """
const assert = require("assert");
const { computeHeatmapMonthCols } = __webMod("heatmap.js");
const days = [];
for (let d = new Date(Date.UTC(2025, 11, 29)); d <= new Date(Date.UTC(2026, 11, 31)); d.setUTCDate(d.getUTCDate() + 1)) {
  days.push({ date: d.toISOString().slice(0, 10) });
}
const { colMonthMap, totalWeekCols } = computeHeatmapMonthCols(days);
assert.strictEqual(totalWeekCols, 53);
assert.strictEqual(colMonthMap[0], "Jan");
const rendered = [];
let lastLabeledCol = -99;
for (let c = 0; c < totalWeekCols; c++) {
  if (colMonthMap[c] && c < totalWeekCols - 1 && (c - lastLabeledCol >= 2)) {
    rendered.push(colMonthMap[c]);
    lastLabeledCol = c;
  }
}
assert.deepStrictEqual(rendered, ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]);

// Prior month stub in col 0 followed by Mon day-1 in col 1 drops col 0 stub cleanly.
const decMonDays = [];
for (let d = new Date(Date.UTC(2025, 10, 26)); d <= new Date(Date.UTC(2026, 0, 10)); d.setUTCDate(d.getUTCDate() + 1)) {
  decMonDays.push({ date: d.toISOString().slice(0, 10) });
}
const res2 = computeHeatmapMonthCols(decMonDays);
assert.strictEqual(res2.colMonthMap[0], undefined);
assert.strictEqual(res2.colMonthMap[1], "Dec");
console.log("HEATMAP_OK");
""",
    )
    assert out == "HEATMAP_OK"


def test_workspace_resizer_clamp_drag_keyboard_and_reset(tmp_path: Path) -> None:
    """WorkspaceResizer must clamp widths [220, 480], persist pointer/keyboard edits, and reset on dblclick."""
    out = _run_node(
        tmp_path,
        """
const assert = require("assert");
const store = new Map();
global.localStorage = { getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v)), removeItem: (k) => store.delete(k) };
const listeners = {};
const props = new Map();
const layout = { classList: { add: () => {}, remove: () => {} }, style: { setProperty: (k, v) => props.set(k, v), removeProperty: (k) => props.delete(k) } };
const pane = { classList: { contains: () => false }, getBoundingClientRect: () => ({ width: Number((props.get("--ws-tree-custom-w") || "300px").replace("px", "")) }) };
const attrs = {};
const resizer = {
  classList: { add: () => {}, remove: () => {} },
  setAttribute: (k, v) => { attrs[k] = v; },
  addEventListener: (ev, fn) => { listeners[ev] = fn; },
  setPointerCapture: () => {}, hasPointerCapture: () => false, releasePointerCapture: () => {},
};
global.window = { innerWidth: 1920 };
global.requestAnimationFrame = (fn) => { fn(); return 1; };
global.cancelAnimationFrame = () => {};
global.document = { getElementById: (id) => ({ workspaceLayout: layout, workspaceTreePane: pane, workspaceResizer: resizer }[id] || null), querySelector: () => null };

const WR = __webMod("workspace_resizer.js");
assert.strictEqual(WR.clampWidth(100, 1920), 220);
assert.strictEqual(WR.clampWidth(600, 1920), 480);
assert.strictEqual(WR.clampWidth(420, 620), 260);

WR.init();
// Zero-drag click on resizer must not overwrite density width in localStorage.
listeners.pointerdown({ button: 0, clientX: 300, pointerId: 1, preventDefault: () => {} });
listeners.pointerup({ pointerId: 1 });
assert.strictEqual(store.has("nexus_tree_width"), false);

listeners.pointerdown({ button: 0, clientX: 300, pointerId: 1, preventDefault: () => {} });
listeners.pointermove({ clientX: 365 });
listeners.pointerup({ pointerId: 1 });
assert.strictEqual(store.get("nexus_tree_width"), "365");
assert.strictEqual(props.get("--ws-tree-custom-w"), "365px");
assert.strictEqual(attrs["aria-valuenow"], "365");

listeners.keydown({ key: "ArrowRight", shiftKey: false, preventDefault: () => {} });
assert.strictEqual(store.get("nexus_tree_width"), "381");
listeners.keydown({ key: "Home", preventDefault: () => {} });
assert.strictEqual(store.get("nexus_tree_width"), "220");
listeners.dblclick();
assert.strictEqual(store.has("nexus_tree_width"), false);
assert.strictEqual(props.has("--ws-tree-custom-w"), false);
console.log("RESIZER_OK");
""",
    )
    assert out == "RESIZER_OK"


def test_gallery_view_per_sheet_and_unselected_empty_badge(tmp_path: Path) -> None:
    """Gallery toolbar must say Per Sheet (not Grid) and unselected cards must render an empty ring without ✓."""
    out = _run_node(
        tmp_path,
        """
const assert = require("assert");
global.localStorage = { getItem: () => null, setItem: () => {} };
global.window = { location: { origin: "https://nexus.example.com" } };
const GallerySelect = __webMod("gallery_select.js");
const GalleryView = __webMod("gallery_view.js");
GallerySelect.clearSelection();
const tbHtml = GalleryView.renderToolbarHtml(3);
assert.ok(tbHtml.includes("Per Sheet"));
assert.ok(!tbHtml.includes(">Grid<"));
assert.ok(/id="bulkShareBtn"[^>]*disabled/.test(tbHtml));
const item = { name: "capture.png", rel_path: "capture.png", scope: "brain:abc", signed_url: "/web/media/x" };
const cardHtml = GalleryView.renderCardsHtml([item]);
assert.ok(cardHtml.includes('aria-pressed="false"'));
assert.ok(cardHtml.includes('<span class="gallery-select-badge mono"></span>'));
assert.ok(!cardHtml.includes('<span class="gallery-select-badge mono">✓</span>'));
GallerySelect.toggleItem(item, true, 0);
const selHtml = GalleryView.renderCardsHtml([item]);
assert.ok(selHtml.includes('<span class="gallery-select-badge mono">1</span>'));
GallerySelect.clearSelection();
console.log("GALLERY_OK");
""",
    )
    assert out == "GALLERY_OK"


def test_charts_ytd_demo_mapping_and_widescreen_css_contracts(tmp_path: Path) -> None:
    """charts.js must map Year+Current to ytd demo snapshots and CSS/HTML must uphold widescreen & contrast contracts."""
    out = _run_node(
        tmp_path,
        """
const assert = require("assert");
const fs = require("fs");
const vm = require("vm");
const code = fs.readFileSync("web/charts.js", "utf-8");
const ctx = {
  localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
  sessionStorage: { getItem: () => null },
  window: { location: { search: "", hash: "" }, innerWidth: 2560, addEventListener: () => {} },
  document: { documentElement: { setAttribute: () => {} }, getElementById: () => null, querySelectorAll: () => [] },
  ResizeObserver: undefined,
  URLSearchParams,
};
vm.runInNewContext(code + "; globalThis.__charts = { VALID_PERIODS, periodPresetMap, state, resolveDemoPeriodKey };", ctx);
const c = ctx.__charts;
assert.ok(c.VALID_PERIODS.includes("ytd"));
assert.deepStrictEqual(JSON.parse(JSON.stringify(c.periodPresetMap.ytd)), { timeframe: "year", horizon: "to_date", offset: 0 });
assert.deepStrictEqual(JSON.parse(JSON.stringify(c.periodPresetMap.last_month)), { timeframe: "month", horizon: "to_date", offset: -1 });
c.state.timeframe = "year";
c.state.horizon_mode = "to_date";
assert.strictEqual(c.resolveDemoPeriodKey(), "ytd");
c.state.horizon_mode = "rolling";
assert.strictEqual(c.resolveDemoPeriodKey(), "last_year");
c.state.timeframe = "month";
c.state.offset = -1;
assert.strictEqual(c.resolveDemoPeriodKey(), "last_month");
console.log("CHARTS_OK");
""",
    )
    assert out == "CHARTS_OK"

    styles_css = (REPO_ROOT / "web" / "styles.css").read_text(encoding="utf-8")
    ws_css = (REPO_ROOT / "web" / "workspace.css").read_text(encoding="utf-8")
    index_html = (REPO_ROOT / "web" / "index.html").read_text(encoding="utf-8")
    explorer_js = (REPO_ROOT / "web" / "explorer.js").read_text(encoding="utf-8")
    bzip_py = (REPO_ROOT / "src" / "agy_nexus" / "bucket_zip.py").read_text(encoding="utf-8")

    assert re.search(r"\[data-surface=\"white\"\][^}]*--bg-canvas:\s*#f8fafc", styles_css)
    assert re.search(r"\[data-surface=\"white\"\][^}]*--bg-card:\s*#ffffff", styles_css)
    assert "min(1960px, calc(100% - 32px))" in styles_css
    assert ".btn-focal:disabled" in styles_css
    assert ".workspace-main" in ws_css and "max-width: none; margin: 0;" in ws_css
    assert "@supports not (scrollbar-color: auto)" in ws_css
    assert "scrollbar-width: auto;" in ws_css
    assert "-webkit-line-clamp: 2" in ws_css and "line-clamp: 2" in ws_css
    assert 'id="v9NavRail"' in index_html and 'id="v9WsSplit"' in index_html
    assert 'id="v9PassInput"' in index_html
    assert "tree-session-children" not in explorer_js
    assert "no-store, no-cache, private" in bzip_py
