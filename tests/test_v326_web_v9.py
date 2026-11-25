"""Tests for /web/v9 Quiet UI v9.3.0 prototype routing, asset allowlist, honesty, modularity, and hygiene."""
from __future__ import annotations

import asyncio
import re
from pathlib import Path

from agy_nexus.web_routes import PWA_ASSETS, handle_web_request

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = REPO_ROOT / "web"
V9_DIR = WEB_DIR / "v9"


def _run_web(path: str, method: str = "GET", web_dir: Path = WEB_DIR) -> tuple[bool, int, dict[str, str], bytes]:
    scope = {"type": "http", "method": method, "path": path, "headers": []}
    captured: list[dict] = []

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(msg: dict) -> None:
        captured.append(msg)

    handled = asyncio.run(handle_web_request(scope, receive, send, web_dir, path.rstrip("/"), method, []))
    if not captured:
        return handled, 0, {}, b""
    start = next(m for m in captured if m["type"] == "http.response.start")
    headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in start.get("headers", [])}
    body = b"".join(m.get("body", b"") for m in captured if m["type"] == "http.response.body")
    return handled, int(start["status"]), headers, body


def test_web_v9_routes_and_no_store_headers() -> None:
    """Both /web/v9 and /web/v9/index.html serve HTML with no-store cache headers."""
    for path in ("/web/v9", "/web/v9/index.html"):
        handled, status, hdrs, body = _run_web(path)
        assert handled is True
        assert status == 200
        assert "text/html" in hdrs.get("content-type", "")
        assert "no-store" in hdrs.get("cache-control", "")
        assert b"v9AnalyticsView" in body and b"v9WorkspaceView" in body

    handled_head, status_head, hdrs_head, body_head = _run_web("/web/v9", method="HEAD")
    assert handled_head is True and status_head == 200 and body_head == b""
    assert int(hdrs_head.get("content-length", "0")) > 1000


def test_all_web_v9_files_registered_in_pwa_assets() -> None:
    """Every static file under web/v9/ must be allowlisted in PWA_ASSETS and servable without mock fixtures."""
    assert V9_DIR.is_dir()
    assert not (V9_DIR / "demo_workspace.json").exists()
    assert "v9/demo_workspace.json" not in PWA_ASSETS
    files = [p for p in V9_DIR.rglob("*") if p.is_file()]
    assert len(files) >= 20
    missing = []
    for f in files:
        rel = f.relative_to(WEB_DIR).as_posix()
        if rel not in PWA_ASSETS:
            missing.append(rel)
    assert not missing, f"Unregistered web/v9 assets in PWA_ASSETS: {missing}"

    for probe in ("/web/v9/v9_shell.css", "/web/v9/v9_rail.css", "/web/v9/v9_app.js", "/web/v9/vendor/echarts.min.js"):
        handled, status, hdrs, body = _run_web(probe)
        assert handled is True and status == 200 and len(body) > 0
        assert hdrs.get("x-content-type-options") == "nosniff"


def test_classic_cross_link_navbar_invariance_and_workbench_dom() -> None:
    """Promoted /web matches /web/v9 cleanly; sw.js caches v9 assets and UI keeps navbar invariant."""
    live_html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    sw_js = (WEB_DIR / "sw.js").read_text(encoding="utf-8")
    v9_html = (V9_DIR / "index.html").read_text(encoding="utf-8")
    v9_analytics_css = (V9_DIR / "v9_analytics.css").read_text(encoding="utf-8")

    assert live_html == v9_html
    assert 'id="navV9Link"' not in live_html
    assert 'CACHE_NAME = "agy-nexus-v4.0.9"' in sw_js
    assert '"v9/v9_app.js"' in sw_js

    topbar_match = re.search(r"<header\b[^>]*class=\"v9-topbar\"[^>]*>([\s\S]*?)</header>", v9_html)
    assert topbar_match is not None
    assert 'id="v9MenuBtn"' in topbar_match.group(1), "Unified menu button must be pinned in sticky .v9-topbar"
    assert 'id="v9ActiveProjWrap"' in topbar_match.group(1) and 'id="v9PeriodPickerBtn"' in topbar_match.group(1)
    assert 'id="v9TopbarWorkspaceCtrl"' in topbar_match.group(1) and 'id="v9OpenUploadBtn"' in topbar_match.group(1)
    assert 'id="v9DocTabs"' in v9_html and 'id="v9DocSelect"' not in v9_html
    assert 'id="v9ProjectStrip"' not in v9_html and 'id="v9ResetProjBtn"' in v9_html
    assert 'id="v9HierarchyHost"' not in v9_html
    assert 'id="v9ProjTableWrap"' in v9_html and "v9_project_view.js" in v9_html
    assert 'id="v9WsProjBtn"' in v9_html and 'id="v9WsShortId"' in v9_html

    for removed in ("v9AnalyticsRailBtn", "v9SidebarToggleBtn", "v9RailResizer", "v9SettingsWrap"):
        assert f'id="{removed}"' not in v9_html
    assert 'id="v9AppShell"' in v9_html and 'id="v9NavRail"' in v9_html
    assert 'id="v9DailyStack"' in v9_html and 'id="v9SecondaryPair"' in v9_html
    assert "Activity by Hour of Day" in v9_html
    assert "max-inline-size: 1480px" in v9_analytics_css

    doc_hdr_match = re.search(r'<div class="va-pane-hdr v9-doc-hdr">([\s\S]*?)</div>\s*<div class="va-pane-body v9-doc-body">', v9_html)
    assert doc_hdr_match is not None
    assert "v9DocModeActions" in doc_hdr_match.group(1) and "v9DocRawBtn" in doc_hdr_match.group(1)
    assert "v9DocPrintBtn" in doc_hdr_match.group(1)
    assert 'id="v9PeriodPopover"' in v9_html and 'id="v9PeriodTodayBtn"' in v9_html
    for tf, hm in (("month", "to_date"), ("quarter", "to_date"), ("year", "to_date"), ("month", "rolling"), ("quarter", "rolling"), ("year", "rolling")):
        assert f'data-v9-tf="{tf}"' in v9_html and f'data-v9-mode="{hm}"' in v9_html
    assert "v9OpenAsciiBtn" not in v9_html and "v9AsciiDialog" not in v9_html
    assert "v9ModeGroup" not in v9_html and "v9WindowMeta" not in v9_html

    v9_ws_js = (V9_DIR / "v9_workspace.js").read_text(encoding="utf-8")
    v9_ws_css = (V9_DIR / "v9_workspace.css").read_text(encoding="utf-8")
    v9_shell_css = (V9_DIR / "v9_shell.css").read_text(encoding="utf-8")
    v9_charts_js = (V9_DIR / "v9_charts.js").read_text(encoding="utf-8")
    v9_hier_js = (V9_DIR / "v9_hierarchy.js").read_text(encoding="utf-8")
    v9_app_js = (V9_DIR / "v9_app.js").read_text(encoding="utf-8")
    v9_state_js = (V9_DIR / "v9_state.js").read_text(encoding="utf-8")
    v9_proj_js = (V9_DIR / "v9_project_view.js").read_text(encoding="utf-8")
    v9_gal_js = (V9_DIR / "v9_gallery.js").read_text(encoding="utf-8")
    v9_an_js = (V9_DIR / "v9_analytics.js").read_text(encoding="utf-8")
    v9_hm_js = (V9_DIR / "v9_heatmap.js").read_text(encoding="utf-8")
    v9_rail_css = (V9_DIR / "v9_rail.css").read_text(encoding="utf-8")
    v9_an_css = (V9_DIR / "v9_analytics.css").read_text(encoding="utf-8")

    for removed_ctl in ("v9ClassicLink", "v9AuthClassicLink", "v9VersionMeta", "v9LockBtn"):
        for src in (v9_html, v9_hier_js, v9_an_js, v9_app_js):
            assert removed_ctl not in src, f"{removed_ctl} must stay removed from /web/v9"

    assert '"plan.md"' in v9_ws_js and '"handoff.md"' in v9_ws_js
    assert "include_captures=0" in v9_ws_js and "pickLatestSessionId" in v9_ws_js and "syncResponsiveMode" in v9_ws_js
    assert "min-width: 960px" in v9_ws_css and "repeat(2, minmax(0, 1fr))" in v9_ws_css
    assert "container-type: inline-size" in v9_ws_css and "max-width: 759px" in v9_ws_css
    assert "min-width: 760px" in v9_ws_css and "min-width: 1280px" in v9_ws_css
    assert '[data-v9-wsmode="split"]' in v9_ws_css and ".v9-gal-desktop-cols" in v9_ws_css
    assert 'id="v9CapturesDialog"' in v9_html and 'id="v9OpenCapturesBtn"' in v9_html
    assert 'id="v9BillingCard"' in v9_html and "v9_billing.js" in v9_html
    assert "overflow: visible;" in v9_ws_css and "#v9GalStatus:empty" in v9_ws_css
    assert "max-width: 679px" in v9_shell_css and ".v9-brand-mark" in v9_shell_css
    assert "grid: { left: 52," in v9_charts_js and "top: 32" in v9_charts_js and "nameGap: 12" in v9_charts_js
    assert "<summary" not in v9_hier_js and "data-proj-toggle" in v9_hier_js
    assert "data-rail-analytics" in v9_hier_js and "data-rail-ws" not in v9_hier_js
    assert "v9-swatch-btn" in v9_hier_js and ">Compact<" in v9_hier_js and ">Comfortable<" in v9_hier_js
    assert "showAllSessionsForProject" in v9_hier_js and "slice(0, 5)" in v9_hier_js
    assert "project-captures" in v9_hier_js
    assert "v9GalMoreBtn" in v9_gal_js and "v9GalMorePopover" in v9_gal_js and "v9-gal-desktop-cols" in v9_gal_js
    assert "renderTopProjectsTable" in v9_proj_js and "buildProjectSessionsChartOption" in v9_proj_js
    assert 'include_ascii: "0"' in v9_app_js and "compact_sessions" in v9_app_js and "include_captures=0" in v9_app_js

    for src in (v9_html, v9_an_js, v9_app_js, v9_state_js, v9_an_css):
        assert "v9Ascii" not in src and "asciiTier" not in src and "v9-ascii-pre" not in src
    assert 'id="v9NavRail" class="v9-nav-rail"' in v9_html
    assert "inline-size: 100vw" in v9_rail_css and "inline-size: 50vw" in v9_rail_css
    assert "va-pane:not(.v9-nav-rail)" in v9_ws_css and "background-color: var(--bg-surface);" in v9_rail_css
    assert ">Activity Heatmap<" in v9_html and "52-Week Activity Heatmap" not in v9_html
    assert "d.future === true" in v9_hm_js
    assert "ceilingPct < 99.5" in v9_an_js
    assert "calls.length === 0" in v9_an_js
    assert "min-width: 350px" in v9_an_css and "repeat(2, minmax(0, 1fr))" in v9_an_css
    assert "flex-wrap: wrap;" in v9_ws_css


def test_web_v9_offline_privacy_emoji_ban_and_modularity() -> None:
    """Authored web/v9 modules and backend project_stats obey <=500L, offline vendoring, zero Diurnal, emoji ban, and depersonalization."""
    personal_pat = re.compile(r"/home/(?!dev(?:/|$))[A-Za-z0-9_.-]+|192\.168\.[0-9]+\.[0-9]+|https?://[a-z0-9.-]*cdn|https?://unpkg\.com", re.I)
    pictograph_pat = re.compile(r"[🔒✦⬇◀▶✓✕]")
    for f in V9_DIR.rglob("*"):
        if not f.is_file():
            continue
        rel = f.relative_to(V9_DIR).as_posix()
        if rel.startswith("vendor/"):
            continue
        text = f.read_text(encoding="utf-8")
        lines = text.splitlines()
        assert len(lines) <= 500, f"{rel} exceeds 500-line module budget ({len(lines)} lines)"
        assert not personal_pat.search(text), f"Personal path/LAN IP/external CDN leak in {rel}"
        assert not pictograph_pat.search(text), f"Unicode pictograph glyph disallowed in {rel}"
        assert "diurnal" not in text.lower(), f"Remove 'diurnal' wording from {rel}"
        if f.suffix == ".css":
            assert "!important" not in text, f"Disallow !important in {rel}"

    proj_stats_py = (REPO_ROOT / "src" / "agy_nexus" / "project_stats.py").read_text(encoding="utf-8")
    assert len(proj_stats_py.splitlines()) <= 500
    assert "v9/v9_project_view.js" in (REPO_ROOT / "src" / "agy_nexus" / "web_routes.py").read_text(encoding="utf-8")

    field_report = (REPO_ROOT / "docs" / "QUIET_UI_V9_FIELD_REPORT.md").read_text(encoding="utf-8")
    workflows_doc = (REPO_ROOT / "docs" / "WORKFLOWS.md").read_text(encoding="utf-8")
    assert not personal_pat.search(field_report), "Personal path/IP leak in docs/QUIET_UI_V9_FIELD_REPORT.md"
    assert "diurnal" not in field_report.lower(), "Remove 'diurnal' from docs/QUIET_UI_V9_FIELD_REPORT.md"
    assert "diurnal" not in workflows_doc.lower(), "Remove 'diurnal' from docs/WORKFLOWS.md"
    assert (V9_DIR / "vendor" / "echarts.min.js").stat().st_size > 500_000
    assert "Apache License" in (V9_DIR / "vendor" / "THIRD_PARTY_LICENSES.txt").read_text(encoding="utf-8")
    assert len((WEB_DIR / "app.js").read_text(encoding="utf-8").splitlines()) <= 500


def test_round5_project_stats_and_lazy_captures_optimizations(tmp_path) -> None:
    """Verify include_ascii=0, compact_sessions=1, project_id scope, include_captures=0, and lazy project-captures."""
    from agy_nexus import bucket_api, stats

    whole = stats.build_nexus_stats_bundle(
        timeframe="month",
        horizon_mode="to_date",
        offset=0,
        include_ascii=False,
        compact_sessions=True,
    )
    assert "ascii" not in whole or not whole.get("ascii")
    hier = whole["project_hierarchy"]
    assert "total_sessions_count" in hier
    top = hier.get("top_projects") or []
    if top:
        assert "overflow_sessions_series" not in top[0]
        pid = top[0]["project_id"]
        scoped = stats.build_nexus_stats_bundle(
            timeframe="month",
            horizon_mode="to_date",
            offset=0,
            project_id=pid,
            include_ascii=False,
        )
        assert scoped["project_scope"]["project_id"] == pid
        assert "context_budget" in scoped["project_scope"]
        assert "project_sessions_series" in scoped

    tree_fast = bucket_api.build_workspace_tree_payload(include_captures=False)
    assert tree_fast["ok"] is True
    assert tree_fast["captures_included"] is False
    if top:
        cap = bucket_api.get_project_captures_payload(top[0]["project_id"])
        assert cap["ok"] is True
        assert isinstance(cap["counts"], dict)


def test_round5_http_routes(monkeypatch) -> None:
    """Verify live ASGI HTTP handlers for Round 5 routes, locked 401 gate, and query params."""
    from starlette.testclient import TestClient
    from agy_nexus import config as cfg
    from agy_nexus.server import build_nexus_http_app

    phrase = "canary round5 http check"
    monkeypatch.setattr(cfg, "PASS_HASH", cfg.normalize_phrase(phrase))
    secret = "r5_test_secret_token_32_characters"
    app = build_nexus_http_app(secret, cfg.get_polyglot_mcp_token(secret), cfg.get_praxis_mcp_token(secret))
    with TestClient(app) as client:
        assert client.get("/web/v9").status_code == 200
        js_res = client.get("/web/v9/v9_project_view.js?v=3.2.6")
        assert js_res.status_code == 200 and "renderTopProjectsTable" in js_res.text

        assert client.get("/web/api/stats").status_code == 401
        hdrs = {"X-Nexus-Passphrase": phrase}

        st_res = client.get("/web/api/stats?timeframe=month&horizon_mode=to_date&offset=0&include_ascii=0&compact_sessions=1", headers=hdrs)
        assert st_res.status_code == 200
        st_data = st_res.json()
        assert not st_data.get("ascii")
        assert "total_sessions_count" in (st_data.get("project_hierarchy") or {})

        tr_res = client.get("/web/api/workspace/tree?include_captures=0", headers=hdrs)
        assert tr_res.status_code == 200 and tr_res.json().get("captures_included") is False

        top = (st_data.get("project_hierarchy") or {}).get("top_projects") or []
        if top:
            pid = top[0]["project_id"]
            sc_res = client.get(f"/web/api/stats?project_id={pid}&include_ascii=0", headers=hdrs)
            assert sc_res.status_code == 200
            sc_data = sc_res.json()
            assert (sc_data.get("project_scope") or {}).get("project_id") == pid
            assert "project_sessions_series" in sc_data

            cp_res = client.get(f"/web/api/workspace/project-captures?project_id={pid}", headers=hdrs)
            assert cp_res.status_code == 200 and cp_res.json().get("ok") is True and isinstance(cp_res.json().get("counts"), dict)
