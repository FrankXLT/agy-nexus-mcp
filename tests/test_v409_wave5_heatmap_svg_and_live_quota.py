"""tests/test_v409_wave5_heatmap_svg_and_live_quota.py — AGY-Nexus v4.0.9 Wave 5 Regression Suite."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import stat
import subprocess
import sys
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
SCRIPTS_DIR = REPO_ROOT / "scripts"
WEB_V9 = REPO_ROOT / "web" / "v9"
for p in (str(SRC_DIR), str(SCRIPTS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from agy_nexus import ascii_rich, ls_quota_probe, stats_metrics
import build_github_showcase


def test_wave5_ls_sanitize_filters_untouched_resets_and_strips_pii() -> None:
    """Verify untouched 100% rolling timers are suppressed and PII/secrets never enter snapshots."""
    now_ep = 1795600000.0  # 2026-11-25T09:46:40Z
    rolling_5h = datetime.fromtimestamp(now_ep + 5 * 3600 + 60, tz=timezone.utc).isoformat()
    real_5h = datetime.fromtimestamp(now_ep + 10200, tz=timezone.utc).isoformat()
    real_wk = datetime.fromtimestamp(now_ep + 345600, tz=timezone.utc).isoformat()

    raw_status = {
        "userStatus": {
            "email": "private-user@example.invalid",
            "apiKey": "secret-token-should-drop",
            "userTier": {"id": "g1-ultra-tier", "description": "Google AI Ultra (20x)", "availableCredits": [{"creditAmount": "2500"}]},
            "planStatus": {"planInfo": {"planName": "Ultra"}, "availablePromptCredits": 1000, "availableFlowCredits": 500},
            "cascadeModelConfigData": {
                "clientModelConfigs": [
                    {
                        "label": "Gemini 4 Carbon",
                        "modelOrAlias": {"model": "MODEL_PLACEHOLDER_M427"},
                        "quotaInfo": {"remainingFraction": 0.968, "resetTime": real_5h},
                    },
                    {
                        "label": "Claude Sonnet 5.5",
                        "modelOrAlias": {"model": "MODEL_PLACEHOLDER_M405"},
                        "quotaInfo": {"remainingFraction": 1.0, "resetTime": rolling_5h},
                    },
                ]
            },
        }
    }
    raw_summary = {
        "groups": [
            {
                "displayName": "Gemini Models",
                "buckets": [
                    {"bucketId": "gemini-5h", "window": "5h", "remainingFraction": 0.968, "resetTime": real_5h, "description": "Active 5h"},
                    {"bucketId": "gemini-weekly", "window": "weekly", "remainingFraction": 0.553, "resetTime": real_wk, "description": "Weekly pool"},
                ],
            },
            {
                "displayName": "Claude and GPT models",
                "buckets": [
                    {"bucketId": "3p-5h", "window": "5h", "remainingFraction": 1.0, "resetTime": rolling_5h, "description": ""},
                    {"bucketId": "3p-weekly", "window": "weekly", "remainingFraction": 1.0, "resetTime": real_wk, "description": "Weekly pool"},
                ],
            },
        ]
    }
    snap = ls_quota_probe.sanitize_ls_responses(raw_status, raw_summary, transport="https://127.0.0.1:44361", now_epoch=now_ep)
    dumped = json.dumps(snap)
    assert "private-user@example.invalid" not in dumped
    assert "secret-token-should-drop" not in dumped

    g5 = snap["pools"]["google"]["bucket_5h"]
    gw = snap["pools"]["google"]["bucket_weekly"]
    p5 = snap["pools"]["claude"]["bucket_5h"]
    pw = snap["pools"]["claude"]["bucket_weekly"]
    assert g5["used_pct"] == 3.2 and g5["has_active_reset"] is True
    assert gw["used_pct"] == 44.7 and gw["has_active_reset"] is True
    assert p5["used_pct"] == 0.0 and p5["has_active_reset"] is False and p5["reset_time"] is None
    assert pw["used_pct"] == 0.0 and pw["has_active_reset"] is True  # has explicit description -> kept


def test_wave5_snapshot_persistence_0600_stale_and_offline_preservation(tmp_path: Path) -> None:
    """Verify atomic 0600 persistence, offline bucket preservation, stale detection, and enrichment."""
    now_ep = 1795600000.0
    bg_dir = tmp_path / "bg"
    live = {
        "schema_version": 1,
        "captured_epoch": now_ep,
        "last_live_epoch": now_ep,
        "last_live_at": "2026-11-25T09:46:40+00:00",
        "ls_alive": True,
        "source": "antigravity_ls",
        "user_tier": {"id": "g1-ultra-tier", "description": "Google AI Ultra (20x)", "available_credits": 2500},
        "plan_status": {"available_prompt_credits": 1000, "available_flow_credits": 500},
        "pools": {
            "google": {"bucket_5h": {"used_pct": 12.5, "remaining_pct": 87.5, "has_active_reset": True, "reset_time": "2026-11-25T13:00:00+00:00"}},
            "claude": {"bucket_5h": {"used_pct": 0.0, "remaining_pct": 100.0, "has_active_reset": False}},
        },
        "client_model_configs": [{"model_key": "carbon", "label": "Gemini 4 Carbon"}],
    }
    ls_quota_probe.write_quota_snapshot(bg_dir, live, now_epoch=now_ep)
    snap_file = bg_dir / ls_quota_probe.SNAPSHOT_FILENAME
    assert snap_file.exists()
    assert stat.S_IMODE(snap_file.stat().st_mode) == 0o600

    fresh_read = ls_quota_probe.read_quota_snapshot(bg_dir, now_epoch=now_ep + 120)
    assert fresh_read["state"] == "LIVE" and fresh_read["is_fresh"] is True

    stale_read = ls_quota_probe.read_quota_snapshot(bg_dir, now_epoch=now_ep + 1200)
    assert stale_read["state"] == "STALE" and stale_read["is_fresh"] is False

    # When IDE exits (live_payload=None), last known buckets survive with ls_alive=False
    ls_quota_probe.write_quota_snapshot(bg_dir, None, now_epoch=now_ep + 1300)
    offline_read = ls_quota_probe.read_quota_snapshot(bg_dir, now_epoch=now_ep + 1320)
    assert offline_read["state"] == "IDE_OFFLINE" and offline_read["ls_alive"] is False
    assert offline_read["pools"]["google"]["bucket_5h"]["used_pct"] == 12.5

    pools_out = {"google": {"status": "HEALTHY"}, "claude": {"status": "HEALTHY"}}
    lq = ls_quota_probe.enrich_quota_and_pools(pools_out, bg_dir=bg_dir, allow_subprocess=False, now_epoch=now_ep + 1320)
    assert lq["state"] == "IDE_OFFLINE" and lq["credits"]["ai_credits"] == 2500
    assert pools_out["google"]["bucket_5h"]["used_pct"] == 12.5


def test_wave5_probe_prefers_https_or_falls_back_to_http() -> None:
    """Verify loopback probe handles self-signed HTTPS and falls back to HTTP without TLS errors."""
    now_ep = 1795600000.0
    sample_status = {"userStatus": {"cascadeModelConfigData": {"clientModelConfigs": []}}}
    sample_summary = {"groupQuota": []}

    def fake_rpc(scheme: str, port: int, method: str, csrf: str, timeout: float = 1.5) -> dict | None:
        assert csrf == "csrf-test"
        if scheme == "https":
            return None  # simulate TLS handshake closed -> falls back to http
        return sample_summary if "Summary" in method else sample_status

    with mock.patch.object(ls_quota_probe, "_discover_ls_listeners", return_value=("csrf-test", [44361, 46519])):
        with mock.patch.object(ls_quota_probe, "_post_loopback_rpc", side_effect=fake_rpc):
            res = ls_quota_probe.probe_local_language_server(now_epoch=now_ep)
    assert res is not None and res["ls_alive"] is True and res["transport"].startswith("http://127.0.0.1:")

    # Masked ss -tlnp Process column (ProtectHome=read-only systemd user unit) falls back to ephemeral 127.0.0.1 ports
    ps_mock = mock.Mock(stdout="language_server_linux --csrf_token tok123 --extension_server_port 41234\n")
    ss_masked = mock.Mock(stdout="LISTEN 0 4096 127.0.0.1:44361 0.0.0.0:*\nLISTEN 0 128 127.0.0.1:8765 0.0.0.0:*\n")
    with mock.patch("agy_nexus.ls_quota_probe.subprocess.run", side_effect=[ps_mock, ss_masked]):
        tok, found_ports = ls_quota_probe._discover_ls_listeners()
    assert tok == "tok123" and found_ports[0] == 44361 and 8765 not in found_ports and 41234 in found_ports


def test_wave5_pool_window_burn_and_ascii_rich_width() -> None:
    """Verify 5h/7d pool burn calculation and 76-col render_ascii_rich quota layout."""
    tz = timezone.utc
    now_loc = datetime(2026, 11, 25, 10, 0, tzinfo=tz)
    now_ep = now_loc.timestamp()
    win_start_5h = now_ep - 2 * 3600
    quota_info = {
        "live_quota": {"is_fresh": True, "state": "LIVE", "ls_alive": True},
        "pools": {
            "google": {
                "status": "HEALTHY", "call_share_pct": 85.0,
                "bucket_5h": {"used_pct": 14.2, "remaining_pct": 85.8, "has_active_reset": True, "window_start_epoch": win_start_5h, "reset_time": "2026-11-25T13:00:00+00:00"},
                "bucket_weekly": {"used_pct": 44.7, "remaining_pct": 55.3, "has_active_reset": True, "window_start_epoch": now_ep - 3 * 86400, "reset_time": "2026-11-29T10:00:00+00:00"},
            },
            "claude": {
                "status": "HEALTHY", "call_share_pct": 15.0,
                "bucket_5h": {"used_pct": 0.0, "remaining_pct": 100.0, "has_active_reset": False},
                "bucket_weekly": {"used_pct": 18.0, "remaining_pct": 82.0, "has_active_reset": True, "reset_time": "2026-11-29T10:00:00+00:00"},
            },
        },
    }
    cache = {
        "c1": {
            "last_conv_model": "carbon",
            "slot_1h_steps": {"2026-11-25T09": 120, "2026-11-23T15": 300},
            "slot_1h_tokens": {"2026-11-25T09": 1_000_000, "2026-11-23T15": 2_000_000},
            "slot_1h_cost_micros": {"2026-11-25T09": 2_500_000, "2026-11-23T15": 5_000_000},
        }
    }
    burns = stats_metrics.compute_pool_window_burn(
        cache, {"c1": {"is_subagent": False}}, quota_info, now_loc,
        specs={"carbon": {"pool_key": "google"}, "sonnet": {"pool_key": "claude"}},
        classify_fn=lambda k: k,
        compute_cost_fn=lambda *a, **kw: 0,
        split_fn=lambda t: (t // 2, t // 2, 0),
        resolve_root_fn=lambda c, _d: c,
        resolve_subagent_fn=lambda *a: ("carbon", "default"),
        parent_model_map={}, main_mk="carbon", main_switch_date="", agent_target_map={}, display_tz=tz, bg_dir=None,
    )
    assert burns["google"]["burn_5h"]["steps"] == 120 and burns["google"]["burn_5h"]["window_source"] == "reset_window"
    assert burns["google"]["burn_7d"]["steps"] == 420 and burns["google"]["burn_7d"]["cost_usd"] == 7.5

    bundle = {
        "period": {"label": "91d", "start_date": "2026-08-27", "end_date": "2026-11-25", "total_days": 91},
        "kpis": {"window_steps": 1200, "window_tool_calls": 400, "avg_daily_steps": 60, "active_days": 20, "total_conversations": 5, "total_subagents_spawned": 12, "window_tokens": 5000000, "window_cost_usd": 12.34, "tok_per_day": 250000, "cost_per_day_usd": 0.62},
        "quota_and_pools": quota_info,
        "code_health": {"version": {"installed": "4.0.9", "remote_latest": "4.0.9", "status": "up_to_date"}, "files_total": 10, "files_compliant": 10, "polyglot_total_symbols": 100},
        "wire_telemetry": {"pct_under_20kb": 100.0, "avg_inner_kb": 4.2, "max_inner_kb": 12.1, "total_calls": 10, "total_tokens": 5000, "client_breakdown": []},
        "heatmap_series": [], "sub_daily_series": [], "model_usage_vs_target": [], "top_workspaces": [], "subagent_list": [],
    }
    rich_out = ascii_rich.render_ascii_rich(bundle)
    assert "QUOTA USED vs RESET WINDOWS" in rich_out
    assert "G 5h: 14%u" in rich_out
    for ln in rich_out.splitlines():
        assert len(ln) == 76, f"Rich box line not 76 cols ({len(ln)}): {ln!r}"


_WAVE5_UI_PROBE_CJS = """
const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

function noop() {}
const kpiGrid = { innerHTML: "" };
const heatHost = {
  _html: "", clientWidth: 1360, dataset: {},
  set innerHTML(v) { this._html = v; },
  get innerHTML() { return this._html; },
  querySelector: () => null,
};
const ctx = {
  window: { innerWidth: 1440, AgyV9: {} },
  document: {
    getElementById: (id) => ({
      v9HeatHost: heatHost, v9KpiGrid: kpiGrid,
      v9HeatInspect: { innerHTML: "", textContent: "" },
      v9HeatSummary: { textContent: "" },
      v9HeatWeeksBtn: { dataset: {}, classList: { toggle: noop }, addEventListener: noop, textContent: "" },
    }[id] || null),
  },
  setTimeout, clearTimeout, Date, Math, Number, String, Array, Object, Set, Map, JSON, RegExp, Intl,
};
ctx.window.AgyV9 = {
  state: { metric: "steps", heatWeeks: 53, heatPinned: false, heatSelectedDate: "", heatPeriodKey: "" },
  escHtml: (s) => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;"),
  fmtNum: (n) => Math.round(Number(n || 0)).toLocaleString("en-US"),
  fmtUsd: (n) => `$${Number(n || 0).toFixed(2)}`,
};
vm.runInNewContext(fs.readFileSync("web/v9/v9_heatmap.js", "utf-8"), ctx);
vm.runInNewContext(fs.readFileSync("web/v9/v9_analytics.js", "utf-8"), ctx);

const HM = ctx.window.AgyV9.Heatmap;
const AN = ctx.window.AgyV9.Analytics;

const g1440 = HM.resolveGridGeometry(53, { clientWidth: 1360 });
assert.strictEqual(g1440.cellPx, 16);
assert.strictEqual(g1440.gapPx, 3);
const g1440Pinned = HM.resolveGridGeometry(53, { clientWidth: 1100 });
assert.strictEqual(g1440Pinned.cellPx, 16);
assert.strictEqual(g1440Pinned.gapPx, 3);

ctx.window.innerWidth = 900;
const g900 = HM.resolveGridGeometry(53, { clientWidth: 840 });
assert.strictEqual(g900.cellPx, 12);
assert.strictEqual(g900.gapPx, 3);

ctx.window.innerWidth = 390;
const g390 = HM.resolveGridGeometry(26, { clientWidth: 360 });
assert.strictEqual(g390.cellPx, 10);
assert.strictEqual(g390.gapPx, 3);

ctx.window.innerWidth = 1440;
const series = [];
const start = new Date(Date.UTC(2025, 10, 24));
for (let i = 0; i < 371; i++) {
  const d = new Date(start.getTime() + i * 86400000);
  const iso = d.toISOString().slice(0, 10);
  const future = iso > "2026-11-25";
  series.push({ date: iso, weekday: i % 7, steps: future ? 0 : 800, tokens: 100000, cost_usd: 1.5, future, in_window: !future && iso >= "2026-11-01" });
}
const { cols } = HM.buildWeeksMatrix(series, 53);
const labels = HM.buildMonthLabels(cols);
assert.strictEqual(labels[49], "Nov");
assert.strictEqual(labels[48], "");
const dPath = HM.buildMonthDividerPath(cols, 16, 3);
assert.ok(dPath.includes("M") && dPath.includes("L"));
const segCoords = Array.from(dPath.matchAll(/[ML]([0-9.]+) ([0-9.]+)/g)).map((m) => [Number(m[1]), Number(m[2])]);
assert.ok(segCoords.length >= 20, "Expected stepped month divider coordinates");
for (const [x, y] of segCoords) {
  const xHalf = Math.abs((x % 1) - 0.5) < 1e-6;
  const yHalf = Math.abs((y % 1) - 0.5) < 1e-6;
  assert.ok(xHalf || Number.isInteger(x), `Unexpected x coordinate ${x}`);
  assert.ok(yHalf || Number.isInteger(y), `Unexpected y coordinate ${y}`);
  if (x > 0 && x < g1440.gridW) assert.ok(xHalf, `Inner divider x=${x} must snap to .5 gutter center`);
}
HM.renderHeatmap({ period: { key: "current_month", start_date: "2026-11-01", end_date: "2026-11-25" }, heatmap_series: series });
assert.ok(!heatHost.innerHTML.includes("has-month-left"));
assert.ok(!heatHost.innerHTML.includes("Upcoming calendar day"));
assert.ok(heatHost.innerHTML.includes(`style="inset-inline-start:${49 * 19}px">Nov</span>`));
assert.ok(heatHost.innerHTML.includes(`viewBox="0 0 ${g1440.gridW} ${g1440.gridH}"`));
assert.ok(heatHost.innerHTML.includes("--v9-heat-cell:16px;--v9-heat-gap:3px"));

const future5h = new Date(Date.now() + 7500000).toISOString();
const futureWk = new Date(Date.now() + 345600000).toISOString();
AN.renderKpiCards({
  period: { total_days: 30 },
  kpis: { active_days: 10, window_steps: 500, window_tokens: 1000000, window_cost_usd: 4.5 },
  quota_and_pools: {
    active_tier_profile: "ultra-20x",
    active_mainchat_model: { label: "Gemini 4 Carbon" },
    live_quota: { state: "LIVE", ls_alive: true, is_fresh: true, snapshot_age_seconds: 5 },
    partner_weekly_pacing: { recommended_cumulative_ceiling_pct: 57.1, daily_target_pct: 14.28 },
    pools: {
      google: {
        status: "HEALTHY", call_share_pct: 84.0,
        bucket_5h: { used_pct: 14.2, remaining_pct: 85.8, has_active_reset: true, reset_time: future5h },
        bucket_weekly: { used_pct: 44.7, remaining_pct: 55.3, has_active_reset: true, reset_time: futureWk },
        burn_5h: { steps: 120, tokens: 900000, cost_usd: 3.2 },
        burn_7d: { steps: 1500, tokens: 12000000, cost_usd: 42.1 },
      },
      claude: {
        status: "HEALTHY", call_share_pct: 16.0, total_429_count: 0,
        bucket_5h: { used_pct: 0.0, remaining_pct: 100.0, has_active_reset: false },
        bucket_weekly: { used_pct: 18.5, remaining_pct: 81.5, has_active_reset: true, reset_time: futureWk },
        burn_5h: { steps: 0, tokens: 0, cost_usd: 0.0 },
        burn_7d: { steps: 200, tokens: 2000000, cost_usd: 8.4 },
      },
    },
  },
  model_usage_vs_target: [],
});
assert.ok(kpiGrid.innerHTML.includes("Google 20x Pool"));
assert.ok(kpiGrid.innerHTML.includes("Partner Pool"));
assert.ok(kpiGrid.innerHTML.includes("14.2%") && kpiGrid.innerHTML.includes("85.8% left"));
assert.ok(kpiGrid.innerHTML.includes('role="progressbar"'));
assert.ok(kpiGrid.innerHTML.includes("Standby · 100% left"));
assert.ok(kpiGrid.innerHTML.includes("Wk 44.7% used"));

AN.renderKpiCards({
  period: { total_days: 30 }, kpis: {},
  quota_and_pools: { live_quota: { state: "IDE_OFFLINE", ls_alive: false }, pools: { google: { status: "HEALTHY", call_share_pct: 90 }, claude: { status: "HEALTHY", call_share_pct: 10 } } },
  model_usage_vs_target: [],
});
assert.ok(kpiGrid.innerHTML.includes("IDE Offline") && kpiGrid.innerHTML.includes("IDE OFFLINE"));
console.log("V409_WAVE5_UI_OK");
"""


def test_wave5_heatmap_svg_dividers_and_kpi_quota_dom(tmp_path: Path) -> None:
    """Verify SVG stepped divider geometry, future-cell clipping, Monday headers, Pool KPIs, and demo countdown shift."""
    probe = tmp_path / "wave5_ui_probe.cjs"
    probe.write_text(_WAVE5_UI_PROBE_CJS, encoding="utf-8")
    proc = subprocess.run(["node", str(probe)], cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    assert "V409_WAVE5_UI_OK" in proc.stdout


def test_wave5_malformed_ls_values_and_demo_sanitizer_budget() -> None:
    """Verify malformed LS credit/non-dict shapes fail closed safely and demo files obey <=500L budgets."""
    bad = ls_quota_probe.sanitize_ls_responses(
        {
            "userStatus": {
                "userTier": {"availableCredits": [{"creditAmount": "NaN"}, {"creditAmount": "bad"}]},
                "planStatus": {"availablePromptCredits": "not-an-int", "availableFlowCredits": True},
                "cascadeModelConfigData": "not-a-dict",
            }
        },
        {"groups": [{"displayName": "Gemini Models", "buckets": [{"window": "5h", "remainingFraction": "NaN"}]}]},
        now_epoch=1795600000.0,
    )
    assert bad["user_tier"]["available_credits"] == 0
    assert bad["plan_status"]["available_prompt_credits"] == 0 and bad["plan_status"]["available_flow_credits"] == 0
    assert bad["pools"]["google"]["bucket_5h"]["used_pct"] == 0.0

    sanitized = build_github_showcase.sanitize_demo_quota_and_pools(
        {
            "active_tier_profile": "ultra-20x",
            "secret_host_Leak": "expanse.lan",
            "active_mainchat_model": {"model_key": "carbon", "label": "Gemini 4 Carbon", "secret": "drop"},
            "pools": {"google": {"call_share_pct": 88.2, "bucket_5h": {"used_pct": 9.5, "reset_time": "2026-11-25T15:00:00Z"}}},
        },
        [],
    )
    raw_dump = json.dumps(sanitized)
    assert "secret_host_Leak" not in raw_dump and "expanse.lan" not in raw_dump and "drop" not in raw_dump
    assert "2026-11-25T15:00:00Z" not in raw_dump
    assert sanitized["pools"]["google"]["bucket_5h"]["offset_seconds"] == 10320

    for rel in ("v9_analytics.css", "v9_shell.css", "v9_heatmap.js", "v9_analytics.js", "v9_demo_adapter.js", "v9_app.js"):
        p = WEB_V9 / rel
        lines = p.read_text(encoding="utf-8").splitlines()
        assert len(lines) <= 500, f"{rel} exceeded 500L ({len(lines)})"
        assert "!important" not in p.read_text(encoding="utf-8"), f"!important found in {rel}"

    an_css = (WEB_V9 / "v9_analytics.css").read_text(encoding="utf-8")
    assert "stroke-width: 1; stroke-linecap: butt; stroke-linejoin: miter;" in an_css
    assert "outline: 2px solid Highlight; outline-offset: -2px;" in an_css
    assert ":is(.v9-card, .va-card):has(#v9HeatHost)" in an_css
    assert "--v9-heat-cell: 16px; --v9-heat-gap: 3px;" in an_css
    assert "--v9-heat-cell: 10px; --v9-heat-gap: 3px;" in an_css
    assert "window.innerWidth <= 560" not in (WEB_V9 / "v9_app.js").read_text(encoding="utf-8")
