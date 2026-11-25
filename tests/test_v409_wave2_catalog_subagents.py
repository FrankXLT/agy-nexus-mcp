"""tests/test_v409_wave2_catalog_subagents.py — AGY-Nexus v4.0.9 Wave 2 Price Book, Subagent Adjudication & PR Sync."""
from __future__ import annotations

import ast
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any

from starlette.testclient import TestClient
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
WEB_DIR = REPO_ROOT / "web"
V9_DIR = WEB_DIR / "v9"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agy_nexus import catalog_report, catalog_sync, config as cfg, model_pricing, polyglot_outline, stats, tools_ops, web_routes
from agy_nexus.server import build_nexus_http_app


def _hex_luma(hex_s: str) -> float:
    h = hex_s.lstrip("#")
    r, g, b = int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _load_catalog_sync_script():
    spec = importlib.util.spec_from_file_location("agy_catalog_sync_script", str(REPO_ROOT / "scripts" / "catalog_sync.py"))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["agy_catalog_sync_script"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_wave2_heatmap_grayscale_boost_across_all_4_themes() -> None:
    """Verify boosted --v9-heat-out-1..4 separation (>=7% distance on level 1) across all 4 themes."""
    shell_css = (V9_DIR / "v9_shell.css").read_text(encoding="utf-8")
    for theme_sel, is_light in (('[data-theme="white"]', True), ('[data-theme="paper"]', True), ('[data-theme="dark-paper"]', False), ('[data-theme="dark"]', False)):
        m = re.search(rf"{re.escape(theme_sel)}\s*\{{([^}}]+)\}}", shell_css)
        assert m is not None
        vals = {}
        for idx in range(5):
            tm = re.search(rf"--v9-heat-out-{idx}:\s*(#[0-9A-Fa-f]{{6}})", m.group(1))
            assert tm is not None, f"Missing --v9-heat-out-{idx} in {theme_sel}"
            vals[idx] = _hex_luma(tm.group(1))
        if is_light:
            assert vals[0] - vals[1] >= 0.14, f"{theme_sel} level-1 grayscale contrast too faint: {vals}"
            assert vals[0] > vals[1] > vals[2] > vals[3] > vals[4]
        else:
            assert vals[1] - vals[0] >= 0.14, f"{theme_sel} dark level-1 grayscale contrast too faint: {vals}"
            assert vals[0] < vals[1] < vals[2] < vals[3] < vals[4]


def test_wave2_two_file_price_book_override_accept_reset_and_auto_retire(tmp_path: Path) -> None:
    """Verify split model_catalog.json + cost_ledger.json, 0600 catalog_override.json accept/reset, and stale auto-retire."""
    cat, led = catalog_sync.load_bundled_catalog_pair()
    assert int(cat["catalog_revision"]) >= 2 and cat.get("updated_at")
    assert all("rate_epochs" not in m and isinstance(m.get("public_api"), dict) and isinstance(m.get("antigravity_ide"), dict) for m in cat["models"])
    assert len(led.get("models") or {}) == 8
    assert catalog_sync.validate_catalog_pair(cat, led) == []

    merged = model_pricing.load_model_catalog(data_dir=tmp_path)
    opus = next(m for m in merged["models"] if m["key"] == "claude_opus_5_5")
    assert opus["context_window"] == 200_000 and opus["api_context_window"] == 1_000_000

    # Newer upstream revision candidate
    cand_cat, cand_led = json.loads(json.dumps(cat)), json.loads(json.dumps(led))
    cand_cat["catalog_revision"] = int(cat["catalog_revision"]) + 1
    cand_cat["updated_at"] = "2026-12-10"
    cand_led["catalog_revision"] = cand_cat["catalog_revision"]
    cand_led["models"]["neon"]["rate_epochs"].append({
        "effective_from": "2026-12-10", "effective_to": None,
        "input_micros": 2500000, "output_micros": 12500000, "cache_read_micros": 125000,
        "source_url": "https://ai.google.dev/gemini-api/docs/pricing", "verified_at": "2026-12-10", "note": "Updated",
    })

    d_dir, bg_dir = tmp_path / "data", tmp_path / "bg"
    d_dir.mkdir()
    bg_dir.mkdir()
    st = catalog_sync.get_catalog_sync_status(
        d_dir, bg_dir, allow_network=True,
        upstream_fetcher=lambda: (True, cand_cat, cand_led, ""),
    )
    assert st["update_available"] is True and st["diff"]["revision_to"] == cand_cat["catalog_revision"]
    assert st["diff"]["ide_lock_violations"] == []

    acc = catalog_sync.accept_catalog_override(d_dir, bg_dir, on_change=model_pricing.clear_model_catalog_cache)
    assert acc["ok"] is True
    ov_file = d_dir / "catalog_override.json"
    assert ov_file.is_file() and (os.stat(ov_file).st_mode & 0o777) == 0o600
    eff = model_pricing.load_model_catalog(data_dir=d_dir)
    assert eff["override_active"] is True and eff["effective_catalog_revision"] == cand_cat["catalog_revision"]

    # Stale override auto-retires when bundled catches up
    ov_doc = json.loads(ov_file.read_text(encoding="utf-8"))
    ov_doc["catalog_revision"] = int(cat["catalog_revision"])
    ov_file.write_text(json.dumps(ov_doc), encoding="utf-8")
    _c, _l, meta = catalog_sync.get_effective_catalog_pair(d_dir)
    assert meta["retired_stale_override"] is True and meta["override_active"] is False and not ov_file.exists()

    # Re-accept & explicit reset
    assert catalog_sync.accept_catalog_override(d_dir, bg_dir, candidate_catalog=cand_cat, candidate_ledger=cand_led, on_change=model_pricing.clear_model_catalog_cache)["ok"]
    assert catalog_sync.reset_catalog_override(d_dir, on_change=model_pricing.clear_model_catalog_cache)["removed"] is True
    assert not ov_file.exists()

    # Offline fail-open preserves status without crashing when cache is cold
    bg_off = tmp_path / "bg_offline"
    bg_off.mkdir()
    st_off = catalog_sync.get_catalog_sync_status(
        d_dir, bg_off, allow_network=True, refresh=True,
        upstream_fetcher=lambda: (False, None, None, "Network offline"),
    )
    assert st_off["status"] == "OFFLINE" and st_off["update_available"] is False


def test_wave2_web_catalog_api_auth_gates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify /web/api/catalog/{status,accept,reset} fail closed (401) without passphrase and persist when unlocked."""
    phrase = "canary wave2 pricebook unlock"
    secret = "test_wave2_catalog_secret_0011223344556677"
    d_dir, bg_dir = tmp_path / "data", tmp_path / "bg"
    d_dir.mkdir()
    bg_dir.mkdir()
    monkeypatch.setattr(cfg, "PASS_HASH", cfg.normalize_phrase(phrase))
    monkeypatch.setattr(web_routes, "AGY_DATA_DIR", d_dir)
    monkeypatch.setattr(web_routes, "AGY_BG_DIR", bg_dir)
    cat, led = catalog_sync.load_bundled_catalog_pair()
    cand_cat, cand_led = json.loads(json.dumps(cat)), json.loads(json.dumps(led))
    cand_cat["catalog_revision"] = int(cat["catalog_revision"]) + 2
    cand_led["catalog_revision"] = cand_cat["catalog_revision"]
    (bg_dir / "catalog_sync_cache.json").write_text(
        json.dumps({
            "status": "OK",
            "upstream_branch": catalog_sync.resolve_catalog_upstream_branch(),
            "checked_at": "2026-11-24T12:00:00Z",
            "fetched_epoch": time.time(),
            "upstream_catalog": cand_cat,
            "upstream_ledger": cand_led,
        }),
        encoding="utf-8",
    )

    app = build_nexus_http_app(secret, polyglot_token=cfg.get_polyglot_mcp_token(secret), praxis_token=cfg.get_praxis_mcp_token(secret))
    with TestClient(app) as tc:
        assert tc.get("/web/api/catalog/status").status_code == 401
        assert tc.post("/web/api/catalog/accept").status_code == 401
        assert tc.post("/web/api/catalog/reset").status_code == 401

        hdr = {"X-Nexus-Passphrase": phrase}
        r_st = tc.get("/web/api/catalog/status", headers=hdr)
        assert r_st.status_code == 200 and r_st.json()["catalog_sync"]["update_available"] is True

        r_acc = tc.post("/web/api/catalog/accept", headers=hdr)
        assert r_acc.status_code == 200 and r_acc.json()["catalog_sync"]["override_active"] is True
        assert (d_dir / "catalog_override.json").is_file()

        r_rst = tc.post("/web/api/catalog/reset", headers=hdr)
        assert r_rst.status_code == 200 and r_rst.json()["catalog_sync"]["override_active"] is False
        assert not (d_dir / "catalog_override.json").exists()


def test_wave2_subagent_adjudication_and_unmapped_model_detection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify inherit subagents catch Carbon 4 redirection, unmapped M610 surfaces in stats/list_models_and_agents."""
    import sqlite3

    d_dir = tmp_path / "data"
    brain_dir = d_dir / "brain"
    bg_dir = d_dir / "sidecar_data" / "ag-bridge-bg"
    cfg_dir = tmp_path / "cfg"
    (cfg_dir / "agents").mkdir(parents=True)
    bg_dir.mkdir(parents=True)
    (d_dir / "antigravity_state.pbtxt").write_text('last_selected_agent_model: "MODEL_PLACEHOLDER_M427"\n', encoding="utf-8")

    # Root chat + inherited claude-sentinel + aligned flash-auditor + unmapped M610 step
    root_cid, sub_inh, sub_ok = "root-1111", "sub-sentinel", "sub-auditor"
    ts = "2026-11-24T15:00:00Z"
    for cid, lines in (
        (root_cid, [
            {"type": "PLANNER_RESPONSE", "created_at": ts, "model": "MODEL_PLACEHOLDER_M427", "content": "ok", "input_tokens": 1000, "output_tokens": 200},
            {"type": "PLANNER_RESPONSE", "created_at": ts, "model": "MODEL_PLACEHOLDER_M610", "content": "new model", "input_tokens": 500, "output_tokens": 100},
        ]),
        (sub_inh, [
            {"type": "PLANNER_RESPONSE", "created_at": ts, "content": "auditing diff", "input_tokens": 2000, "output_tokens": 300},
        ]),
        (sub_ok, [
            {"type": "PLANNER_RESPONSE", "created_at": ts, "model": "MODEL_PLACEHOLDER_M320", "content": "pytest pass", "input_tokens": 800, "output_tokens": 100},
        ]),
    ):
        tpath = brain_dir / cid / ".system_generated" / "logs" / "transcript.jsonl"
        tpath.parent.mkdir(parents=True, exist_ok=True)
        tpath.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")

    db_file = d_dir / "conversation_summaries.db"
    con = sqlite3.connect(str(db_file))
    con.execute("CREATE TABLE conversation_summaries (conversation_id TEXT, title TEXT, step_count INT, last_modified_time TEXT, workspace_uris TEXT, status TEXT, parent_conversation_id TEXT, agent_name TEXT, project_id TEXT)")
    con.executemany(
        "INSERT INTO conversation_summaries VALUES (?,?,?,?,?,?,?,?,?)",
        [
            (root_cid, "Root Chat", 2, ts, '["file:///home/dev/projects/demo-app"]', "IDLE", "", "", "ws:demo-app"),
            (sub_inh, "Claude Sentinel", 1, ts, '[]', "IDLE", root_cid, "claude-sentinel", "ws:demo-app"),
            (sub_ok, "Flash Auditor", 1, ts, '[]', "IDLE", root_cid, "flash-auditor", "ws:demo-app"),
        ],
    )
    con.commit()
    con.close()

    bundle = stats.build_nexus_stats_bundle(
        data_dir=d_dir, brain_dir=brain_dir, db_file=db_file, config_dir=cfg_dir, bg_dir=bg_dir,
        period="current_month", include_ascii=False,
    )
    subs = {r["role"]: r for r in bundle["subagent_list"]}
    cs = subs["claude-sentinel"]
    fa = subs["flash-auditor"]
    assert cs["model_diverged"] is True and cs["adjudication_status"] == "REDIRECTED"
    assert cs["intended_model_key"] == "claude_sonnet_5_5" and cs["actual_model_key"] == "carbon"
    assert "Intended: Sonnet 5.5" in cs["adjudication_text"] and "Carbon 4 (inherited)" in cs["adjudication_text"]
    assert fa["model_diverged"] is False and fa["adjudication_status"] == "ALIGNED"

    unmapped = bundle["unmapped_models"]
    assert len(unmapped) == 1 and unmapped[0]["id"] == "MODEL_PLACEHOLDER_M610" and unmapped[0]["steps"] == 1
    assert "https://github.com/FrankXLT/agy-nexus-mcp/issues/new?" in bundle["unmapped_issue_url"]
    assert "M610" in bundle["unmapped_issue_url"]

    # Check list_models_and_agents exposure within <20 KB wire limit
    phrase = "canary models audit"
    monkeypatch.setattr(cfg, "PASS_HASH", cfg.normalize_phrase(phrase))
    monkeypatch.setattr(tools_ops, "AGY_DATA_DIR", d_dir)
    monkeypatch.setattr(tools_ops, "AGY_BRAIN_DIR", brain_dir)
    monkeypatch.setattr(tools_ops, "AGY_DB_FILE", db_file)
    monkeypatch.setattr(tools_ops, "AGY_BG_DIR", bg_dir)
    monkeypatch.setattr(tools_ops, "AGY_CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(cfg, "SESSION_STATE", {**cfg.SESSION_STATE, "selected_workspace": str(REPO_ROOT), "unlocked_at": time.time()})
    raw = tools_ops.list_models_and_agents(include_skills=False, include_rules=False, style="json", spoken_passphrase=phrase)
    assert len(raw.encode("utf-8")) < 20_000
    parsed = json.loads(raw)
    assert parsed["unmapped_models"][0]["id"] == "MODEL_PLACEHOLDER_M610"
    assert any(a["role"] == "claude-sentinel" and a["diverged"] is True for a in parsed["subagent_adjudication"])


def test_wave2_catalog_sync_script_workflow_and_docs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify --render-docs --check, fail-closed CI numeric feed logic, IDE lock guard, and workflow/docs contracts."""
    import urllib.error

    proc = subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "catalog_sync.py"), "--render-docs", "--check"], cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stdout + proc.stderr

    sc_mod = _load_catalog_sync_script()
    cat, led = catalog_sync.load_bundled_catalog_pair()
    no_change, _, _, _ = sc_mod.apply_numeric_feed_updates(cat, led, {"anthropic": {}, "google": {}}, "2026-11-24")
    assert no_change is False

    def _raise_403(*_args, **_kwargs):
        raise urllib.error.HTTPError(sc_mod.MODELS_DEV_URL, 403, "Forbidden", {}, None)

    monkeypatch.setattr(sc_mod.urllib.request, "urlopen", _raise_403)
    ok_403, _d_403, err_403 = sc_mod._fetch_models_dev_feed()
    assert ok_403 is False and "403" in err_403

    chg, new_cat, new_led, summ = sc_mod.apply_numeric_feed_updates(
        cat, led,
        {
            "openrouter": {"claude-opus-5-5": {"cost": {"input": 99.0, "output": 99.0, "cache_read": 9.0}}},
            "anthropic": {"claude-opus-5-5": {"cost": {"input": 5.0, "output": 25.0, "cache_read": 0.25}, "limit": {"context": 1000000, "output": 128000}, "source_url": "https://evil.test/a)b"}},
            "google": {"gemini-4-carbon": {"cost": {"input": 2.5, "output": 12.0, "cache_read": 0.25}}},
        },
        "2026-11-25",
    )
    assert chg is True and set(summ["changed_models"]) == {"claude_opus_5_5", "carbon"}
    assert catalog_sync.assert_antigravity_ide_untouched(cat, new_cat) == []
    new_opus = next(m for m in new_cat["models"] if m["key"] == "claude_opus_5_5")
    assert new_opus["antigravity_ide"]["context_window"] == 200_000
    assert new_led["models"]["claude_opus_5_5"]["rate_epochs"][-1]["input_micros"] == 5_000_000
    assert new_led["models"]["claude_opus_5_5"]["rate_epochs"][-1]["source_url"] == sc_mod.MODELS_DEV_URL
    # Chronological future epoch preservation + non-inclusive prev_day + same-day idempotency
    carb_eps = new_led["models"]["carbon"]["rate_epochs"]
    assert carb_eps[0]["effective_to"] == "2026-11-24" and carb_eps[1]["effective_from"] == "2026-11-25" and carb_eps[1]["effective_to"] == "2026-11-30"
    assert carb_eps[-1]["effective_from"] == "2026-12-01" and carb_eps[-1]["effective_to"] is None
    idem, _, _, _ = sc_mod.apply_numeric_feed_updates(new_cat, new_led, {"google": {"gemini-4-carbon": {"cost": {"input": 2.5, "output": 12.0, "cache_read": 0.25}}}}, "2026-11-25")
    assert idem is False
    assert catalog_sync.is_safe_https_url("https://docs.anthropic.com/en/docs/about-claude/pricing") is True
    assert catalog_sync.is_safe_https_url("https://evil.test/foo)bar|baz") is False
    ok_pin, _, _, err_pin = catalog_sync._fetch_upstream_pair("https://evil.example.com/catalog")
    assert ok_pin is False and "unpinned" in err_pin.lower()

    wf_sync = (REPO_ROOT / ".github" / "workflows" / "catalog-sync.yml").read_text(encoding="utf-8")
    for tok in ("contents: write", "pull-requests: write", "models: read", "bot/catalog-sync", "bot/catalog-sync-develop", "RUNNER_TEMP", "git fetch origin", "gh models run", "pytest", "--render-docs --check"):
        assert tok in wf_sync, f"Missing workflow token: {tok}"
    assert "hashFiles('/tmp/" not in wf_sync

    contrib = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "Allow GitHub Actions to create and approve pull requests" in contrib and "Rulesets" in contrib
    wf_doc = (REPO_ROOT / "docs" / "WORKFLOWS.md").read_text(encoding="utf-8")
    assert "## Workflow 8: WF-08" in wf_doc and "catalog_override.json" in wf_doc


def test_wave2_banner_dom_probe_and_budgets(tmp_path: Path) -> None:
    """Verify Wave 2 Price Book banner, diff <dialog>, unmapped link, mobile adjudication cell, and <=500L/<=100L budgets."""
    probe = tmp_path / "v409_wave2_banner_probe.cjs"
    probe.write_text("""
const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

const mkEl = (id) => {
  const el = { id, innerHTML: "", textContent: "", disabled: false, open: false, returnValue: "", dataset: {}, _ls: {}, classList: { _s: new Set(), add(c){this._s.add(c)}, remove(c){this._s.delete(c)}, toggle(c,f){if(f)this._s.add(c);else this._s.delete(c);} }, addEventListener(e, fn){(this._ls[e]=this._ls[e]||[]).push(fn);}, click(){(this._ls.click||[]).forEach((fn)=>fn({currentTarget:el}));}, showModal(){if(this.open)throw new Error("InvalidStateError");this.open=true;}, close(){this.open=false;}, querySelectorAll:()=>[], closest:()=>null };
  return el;
};
const ids = ["v9CatalogAlertHost","v9CatalogDiffDialog","v9CatalogDiffBody","v9CatalogDiffAcceptBtn","v9CatalogDiffCloseBtn","v9CatalogDiffCancelBtn","v9SubagentTableBody","v9SubPlotSub","v9KpiGrid","v9ModelTableBody","v9WireScatterWrap","v9WireClientHost","v9WireCallsHost","v9HeatHeading","v9PeriodTriggerLabel","v9PeriodPickerBtn","v9HealthSummary","v9HealthBody"];
const byId = new Map(ids.map((i)=>[i, mkEl(i)]));
const agyNs = { state: { demoMode: false, passphrase: "secret", metric: "steps", soloSubagent: "" }, escHtml: (s)=>String(s??"").replace(/&/g,"&amp;").replace(/</g,"&lt;"), fmtNum: (n)=>String(n||0), fmtUsd: (n)=>"$"+Number(n||0).toFixed(2), fmtBytes: (n)=>String(n||0)+" B", cssVar: ()=>"#000", getSeriesColor: ()=>"#1D4ED8", apiFetch: async ()=>({ok:true}) };
const ctx = {
  window: { location: { search: "" }, AgyV9: agyNs },
  document: { getElementById: (id)=>byId.get(id)||null, querySelectorAll: ()=>[], createElement: ()=>mkEl("dyn") },
  URLSearchParams,
  console,
};
ctx.window.window = ctx.window;
vm.runInNewContext(fs.readFileSync("web/v9/v9_catalog_banner.js", "utf-8"), ctx);
vm.runInNewContext(fs.readFileSync("web/v9/v9_analytics.js", "utf-8"), ctx);

const bundle = {
  catalog_sync: { effective_revision: 2, upstream_revision: 3, bundled_revision: 2, update_available: true, override_active: false, diff: { revision_from: 2, revision_to: 3, updated_at: "2026-12-01", rate_changes: [{ model_key: "carbon", label: "Gemini 4 Carbon", effective_from: "2026-12-01", old_in: 2e6, old_out: 10e6, new_in: 4e6, new_out: 20e6 }], api_changes: [], new_models: [], ide_lock_violations: [], summary_lines: ["$ Gemini 4 Carbon: $2/$10 -> $4/$20"] } },
  unmapped_models: [{ id: "MODEL_PLACEHOLDER_M610", steps: 4, tokens: 1200, last_seen: "2026-11-24T15:00:00Z" }],
  unmapped_issue_url: "https://github.com/FrankXLT/agy-nexus-mcp/issues/new?title=M610",
  subagent_list: [{ role: "claude-sentinel", runs: 3, steps: 45, tokens: 20000, est_cost_usd: 0.4, share_pct: 60.0, adjudication_status: "REDIRECTED", adjudication_text: "Intended: Sonnet 5.5 · Ran: 84% Carbon 4 (inherited)", dominant_model_label: "Carbon 4 (inherit)" }],
  model_usage_vs_target: [], kpis: {}, summary: {}, quota_and_pools: {}, wire_telemetry: {}, code_health: {}, routing_telemetry: {}, backup_321: {},
};
ctx.window.AgyV9.Analytics.renderAnalytics(bundle, () => {}, {});
const hostHtml = byId.get("v9CatalogAlertHost").innerHTML;
assert.ok(hostHtml.includes("Price Book rev 3 available") && hostHtml.includes("Unmapped model code MODEL_PLACEHOLDER_M610 seen in 4 steps"));
assert.ok(hostHtml.includes("https://github.com/FrankXLT/agy-nexus-mcp/issues/new?title=M610"));

const subHtml = byId.get("v9SubagentTableBody").innerHTML;
assert.ok(subHtml.includes("v9-adj-pill") && subHtml.includes("v9-sub-adj-mobile"));
assert.ok(subHtml.includes("Intended: Sonnet 5.5") && subHtml.includes("84% Carbon 4 (inherited)"));

ctx.window.AgyV9.CatalogBanner.openDiffModal(bundle.catalog_sync);
ctx.window.AgyV9.CatalogBanner.openDiffModal(bundle.catalog_sync);
assert.strictEqual(byId.get("v9CatalogDiffDialog").open, true);
assert.ok(byId.get("v9CatalogDiffBody").innerHTML.includes("antigravity_ide preserved"));
ctx.window.AgyV9.CatalogBanner.reset();
assert.strictEqual(byId.get("v9CatalogDiffDialog").open, false);

// Reject unsafe URL schemes in unmapped GitHub issue links
const badBundle = Object.assign({}, bundle, { unmapped_issue_url: "javascript:alert(1)" });
ctx.window.AgyV9.CatalogBanner.render(badBundle);
assert.ok(!byId.get("v9CatalogAlertHost").innerHTML.includes("javascript:"));

// Demo showcase hides live Price Book update banner unless explicitly previewed
ctx.window.AgyV9.state.demoMode = true;
ctx.window.AgyV9.CatalogBanner.render(bundle);
assert.ok(!byId.get("v9CatalogAlertHost").innerHTML.includes("Price Book rev 3 available"));
console.log("V409_WAVE2_DOM_OK");
""", encoding="utf-8")
    res = subprocess.run(["node", str(probe)], cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    assert res.returncode == 0, f"{res.stdout}\n{res.stderr}"
    assert "V409_WAVE2_DOM_OK" in res.stdout

    for p in (SRC_DIR / "agy_nexus" / "catalog_sync.py", SRC_DIR / "agy_nexus" / "catalog_report.py", REPO_ROOT / "scripts" / "catalog_sync.py"):
        lines = p.read_text(encoding="utf-8").splitlines()
        assert len(lines) <= 500, f"{p.name} > 500L ({len(lines)}L)"
        tree = ast.parse("\n".join(lines), filename=str(p))
        for fn in ast.walk(tree):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and fn.end_lineno:
                assert fn.end_lineno - fn.lineno + 1 <= 100, f"{p.name}:{fn.name} > 100L"

    ban_css = (V9_DIR / "v9_catalog_banner.css").read_text(encoding="utf-8")
    ban_js = (V9_DIR / "v9_catalog_banner.js").read_text(encoding="utf-8")
    assert len(ban_css.splitlines()) <= 250 and "!important" not in ban_css
    assert len(ban_js.splitlines()) <= 350 and not re.search(r"[🔒✦⬇◀▶✓✕]", ban_js)
    assert "v9/v9_catalog_banner.css" in web_routes.PWA_ASSETS and "v9/v9_catalog_banner.js" in web_routes.PWA_ASSETS
    _s, _f, syms = polyglot_outline.outline_code(".js", ban_js.splitlines())
    assert not any(int(s.get("lines") or 0) > 100 for s in syms)
