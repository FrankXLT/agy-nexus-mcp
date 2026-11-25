"""tests/test_v409_wave4_develop_soak_and_node24.py — AGY-Nexus v4.0.9 Wave 4 Develop Soak & Node 24 Actions."""
from __future__ import annotations

import ast
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import time

import pytest
from starlette.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agy_nexus import catalog_sync, catalog_validator, config as cfg, web_routes
from agy_nexus.server import build_nexus_http_app


def _load_catalog_sync_script():
    spec = importlib.util.spec_from_file_location("agy_catalog_sync_script_w4", str(REPO_ROOT / "scripts" / "catalog_sync.py"))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["agy_catalog_sync_script_w4"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_wave4_branch_allowlist_and_cache_invalidation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify AGY_CATALOG_BRANCH strict {'main','develop'} allowlist, git auto-detect, and branch-change cache invalidation."""
    # 1. Explicit allowlist and fail-closed on unexpected values
    monkeypatch.setenv("AGY_CATALOG_BRANCH", "develop")
    assert catalog_sync.resolve_catalog_upstream_branch(tmp_path) == "develop"
    assert catalog_sync.get_upstream_base_url().endswith("/develop/src/agy_nexus/data")

    monkeypatch.setenv("AGY_CATALOG_BRANCH", "  DEVELOP ")
    assert catalog_sync.resolve_catalog_upstream_branch(tmp_path) == "develop"

    for bad_branch in ("feature/evil", "../main", "staging", "v4.0.8", "main;rm"):
        monkeypatch.setenv("AGY_CATALOG_BRANCH", bad_branch)
        assert catalog_sync.resolve_catalog_upstream_branch(REPO_ROOT) == "main"

    # 2. Unset env: standalone wheel/container without .git -> main; local git develop -> develop; detached HEAD -> main
    monkeypatch.delenv("AGY_CATALOG_BRANCH", raising=False)
    no_git = tmp_path / "standalone_pkg"
    no_git.mkdir()
    assert catalog_sync.resolve_catalog_upstream_branch(no_git) == "main"

    git_repo = tmp_path / "git_checkout"
    (git_repo / ".git").mkdir(parents=True)
    monkeypatch.setattr(
        catalog_sync.subprocess,
        "run",
        lambda *_a, **_kw: subprocess.CompletedProcess([], 0, stdout="develop\n", stderr=""),
    )
    assert catalog_sync.resolve_catalog_upstream_branch(git_repo) == "develop"
    monkeypatch.setattr(
        catalog_sync.subprocess,
        "run",
        lambda *_a, **_kw: subprocess.CompletedProcess([], 0, stdout="HEAD\n", stderr=""),
    )
    assert catalog_sync.resolve_catalog_upstream_branch(git_repo) == "main"

    # 3. Cache invalidation when upstream_branch changes + /web/api/catalog/status field
    d_dir, bg_dir = tmp_path / "data", tmp_path / "bg"
    d_dir.mkdir()
    bg_dir.mkdir()
    cat, led = catalog_sync.load_bundled_catalog_pair()
    cand_cat, cand_led = deepcopy(cat), deepcopy(led)
    cand_cat["catalog_revision"] = int(cat["catalog_revision"]) + 1
    cand_led["catalog_revision"] = cand_cat["catalog_revision"]

    monkeypatch.setenv("AGY_CATALOG_BRANCH", "main")
    st_main = catalog_sync.get_catalog_sync_status(
        d_dir, bg_dir, allow_network=True, refresh=True,
        upstream_fetcher=lambda: (True, cand_cat, cand_led, ""),
    )
    assert st_main["upstream_branch"] == "main" and st_main["update_available"] is True

    # Switching to develop invalidates cached main snapshot offline and blocks stale override accept
    monkeypatch.setenv("AGY_CATALOG_BRANCH", "develop")
    st_stale = catalog_sync.get_catalog_sync_status(d_dir, bg_dir, allow_network=False)
    assert st_stale["upstream_branch"] == "develop"
    assert st_stale["status"] == "NOT_CHECKED" and st_stale["update_available"] is False and st_stale["diff"] is None
    acc_stale = catalog_sync.accept_catalog_override(d_dir, bg_dir, allow_fetch=False)
    assert acc_stale["ok"] is False

    # Refreshing on develop persists upstream_branch=develop and exposes it via /web/api/catalog/status
    st_dev = catalog_sync.get_catalog_sync_status(
        d_dir, bg_dir, allow_network=True,
        upstream_fetcher=lambda: (True, cat, led, ""),
    )
    assert st_dev["upstream_branch"] == "develop" and st_dev["status"] == "OK" and st_dev["update_available"] is False

    phrase = "canary wave4 branch status"
    secret = "test_wave4_catalog_secret_0011223344556677"
    monkeypatch.setattr(cfg, "PASS_HASH", cfg.normalize_phrase(phrase))
    monkeypatch.setattr(web_routes, "AGY_DATA_DIR", d_dir)
    monkeypatch.setattr(web_routes, "AGY_BG_DIR", bg_dir)
    app = build_nexus_http_app(secret, polyglot_token=cfg.get_polyglot_mcp_token(secret), praxis_token=cfg.get_praxis_mcp_token(secret))
    with TestClient(app) as tc:
        resp = tc.get("/web/api/catalog/status", headers={"X-Nexus-Passphrase": phrase})
        assert resp.status_code == 200
        assert resp.json()["catalog_sync"]["upstream_branch"] == "develop"


def test_wave4_16mib_feed_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify 16 MiB models.dev feed parse cap while stored catalogs stay <=256 KB and cmd_sync_ci stays isolated."""
    sc_mod = _load_catalog_sync_script()
    assert sc_mod.MAX_FEED_BYTES == 16 * 1024 * 1024 and catalog_validator.MAX_CATALOG_BYTES == 262_144

    big_feed = {
        "anthropic": {"models": {}},
        "google": {"models": {}},
        "filler_provider": {"models": {f"m{i}": {"note": "x" * 1024} for i in range(4400)}},
    }
    big_bytes = json.dumps(big_feed).encode("utf-8")
    assert 4 * 1024 * 1024 < len(big_bytes) < sc_mod.MAX_FEED_BYTES

    class _FakeResp:
        def __init__(self, payload: bytes) -> None:
            self.status, self._payload = 200, payload

        def read(self, n: int = -1) -> bytes:
            return self._payload[:n] if n >= 0 else self._payload

        def __enter__(self):
            return self

        def __exit__(self, *_a) -> None:
            return None

    monkeypatch.setattr(sc_mod.urllib.request, "urlopen", lambda *_a, **_kw: _FakeResp(big_bytes))
    ok_big, parsed_big, err_big = sc_mod._fetch_models_dev_feed()
    assert ok_big is True and err_big == "" and "google" in parsed_big

    cat, led = catalog_sync.load_bundled_catalog_pair()
    tmp_cat_p, tmp_led_p, tmp_hist_p = tmp_path / "model_catalog.json", tmp_path / "cost_ledger.json", tmp_path / "PRICING_HISTORY.md"
    tmp_cat_p.write_text(json.dumps(cat), encoding="utf-8")
    tmp_led_p.write_text(json.dumps(led), encoding="utf-8")
    monkeypatch.setattr(sc_mod, "REPO_CATALOG_PATH", tmp_cat_p)
    monkeypatch.setattr(sc_mod, "REPO_LEDGER_PATH", tmp_led_p)
    monkeypatch.setattr(sc_mod, "DOCS_HISTORY_PATH", tmp_hist_p)
    monkeypatch.setattr(sc_mod, "load_bundled_catalog_pair", lambda: (deepcopy(cat), deepcopy(led)))

    feed_path, sum_path = tmp_path / "big_feed.json", tmp_path / "summary.json"
    feed_path.write_bytes(big_bytes)
    assert sc_mod.cmd_sync_ci(str(feed_path), str(sum_path)) == 0
    assert json.loads(sum_path.read_text(encoding="utf-8"))["changed"] is False

    monkeypatch.setattr(sc_mod.urllib.request, "urlopen", lambda *_a, **_kw: _FakeResp(b"{" + (b" " * (sc_mod.MAX_FEED_BYTES + 64)) + b"}"))
    ok_over, _d_over, err_over = sc_mod._fetch_models_dev_feed()
    assert ok_over is False and "exceeds" in err_over.lower()


def test_wave4_curated_token_floor_and_rate_updates() -> None:
    """Verify lower feed output/context limits never downgrade curated limits while verified rate deltas apply."""
    sc_mod = _load_catalog_sync_script()
    cat, led = catalog_sync.load_bundled_catalog_pair()
    test_day = "2026-11-25"

    def _cur_usd(mk: str) -> dict[str, float]:
        eps = led["models"][mk]["rate_epochs"]
        ep = eps[sc_mod._active_epoch_idx(eps, test_day)]
        return {k: ep[f"{k}_micros"] / 1_000_000 for k in ("input", "output", "cache_read")}

    no_down, _, _, _ = sc_mod.apply_numeric_feed_updates(
        cat,
        led,
        {
            "google": {
                "gemini-4-carbon": {"cost": _cur_usd("carbon"), "limit": {"context": 500000, "output": 32768}},
                "gemini-4-neon": {"cost": _cur_usd("neon"), "limit": {"context": 1048576, "output": 65536}},
                "gemini-4-hydrogen": {"cost": _cur_usd("hydrogen"), "limit": {"context": 1048576, "output": 65536}},
            },
            "anthropic": {},
        },
        test_day,
    )
    assert no_down is False

    carb_cur = _cur_usd("carbon")
    new_in_usd = 1.8 if abs(carb_cur["input"] - 1.8) > 1e-6 else 1.7
    argon_pub = next(m["public_api"] for m in cat["models"] if m["key"] == "argon")
    higher_out = max(131072, int(argon_pub["api_max_output_tokens"]) * 2)
    chg, new_cat, new_led, summ = sc_mod.apply_numeric_feed_updates(
        cat,
        led,
        {
            "google": {
                "gemini-4-carbon": {"cost": {"input": new_in_usd, "output": 9.0, "cache_read": 0.09}, "limit": {"context": 1048576, "output": 32768}},
                "gemini-4-argon": {"cost": _cur_usd("argon"), "limit": {"context": 1048576, "output": higher_out}},
            },
            "anthropic": {},
        },
        test_day,
    )
    assert chg is True and set(summ["changed_models"]) == {"carbon", "argon"}
    carb = next(m for m in new_cat["models"] if m["key"] == "carbon")
    argo = next(m for m in new_cat["models"] if m["key"] == "argon")
    assert carb["public_api"]["api_max_output_tokens"] >= 262144 and argo["public_api"]["api_max_output_tokens"] == higher_out
    day_ep = next(ep for ep in new_led["models"]["carbon"]["rate_epochs"] if ep["effective_from"] == test_day)
    assert day_ep["input_micros"] == int(round(new_in_usd * 1_000_000))


def test_wave4_node24_workflows_branch_sync_banner_and_budgets(tmp_path: Path) -> None:
    """Verify zero Node 20 deprecated actions across all workflows, develop soak triggers, banner label, and <=500L budgets."""
    wf_dir = REPO_ROOT / ".github" / "workflows"
    deprecated = (
        "actions/checkout@v4",
        "actions/setup-python@v5",
        "actions/setup-node@v4",
        "docker/setup-qemu-action@v3",
        "docker/setup-buildx-action@v3",
        "docker/login-action@v3",
        "docker/build-push-action@v6",
        'node-version: "20"',
    )
    for wf_path in sorted(wf_dir.glob("*.yml")):
        txt = wf_path.read_text(encoding="utf-8")
        for old in deprecated:
            assert old not in txt, f"Deprecated Node 20 reference '{old}' left in {wf_path.name}"
        assert "actions/checkout@v6" in txt
        assert "actions/setup-python@v6" in txt
        assert "actions/setup-node@v6" in txt and 'node-version: "24"' in txt

    sync_yml = (wf_dir / "catalog-sync.yml").read_text(encoding="utf-8")
    for tok in (
        "catalog-sync-${{ github.ref_name || 'main' }}",
        "ref: ${{ github.ref_name || 'main' }}",
        "bot/catalog-sync-develop",
        "bot/catalog-sync",
        ".github/workflows/catalog-sync.yml",
        "scripts/catalog_sync.py",
        "src/agy_nexus/catalog_sync.py",
    ):
        assert tok in sync_yml, f"Missing token in catalog-sync.yml: {tok}"

    pub_yml = (wf_dir / "publish-mcp.yml").read_text(encoding="utf-8")
    for tok in ("docker/setup-qemu-action@v4", "docker/setup-buildx-action@v4", "docker/login-action@v4", "docker/build-push-action@v7"):
        assert tok in pub_yml

    probe = tmp_path / "wave4_banner_branch.cjs"
    probe.write_text("""
const assert = require("assert");
const fs = require("fs");
const vm = require("vm");
const mkEl = (id) => ({ id, innerHTML: "", disabled: false, open: false, returnValue: "", dataset: {}, classList: { toggle(){} }, addEventListener(){} });
const byId = new Map(["v9CatalogAlertHost","v9CatalogDiffDialog","v9CatalogDiffBody","v9CatalogDiffAcceptBtn","v9CatalogDiffCloseBtn","v9CatalogDiffCancelBtn"].map((i)=>[i, mkEl(i)]));
const ctx = { window: { location: { search: "" }, AgyV9: { state: { demoMode: false, passphrase: "p" }, escHtml: (s)=>String(s??"") } }, document: { getElementById: (id)=>byId.get(id)||null }, URLSearchParams };
ctx.window.window = ctx.window;
vm.runInNewContext(fs.readFileSync("web/v9/v9_catalog_banner.js", "utf-8"), ctx);
ctx.window.AgyV9.CatalogBanner.render({ catalog_sync: { upstream_branch: "develop", effective_revision: 2, upstream_revision: 3, bundled_revision: 2, update_available: true, override_active: false, diff: { summary_lines: ["$ Carbon"] } } });
assert.ok(byId.get("v9CatalogAlertHost").innerHTML.includes("staged on develop"));
console.log("WAVE4_BANNER_OK");
""", encoding="utf-8")
    proc = subprocess.run(["node", str(probe)], cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    assert proc.returncode == 0 and "WAVE4_BANNER_OK" in proc.stdout, proc.stdout + proc.stderr

    wf_doc = (REPO_ROOT / "docs" / "WORKFLOWS.md").read_text(encoding="utf-8")
    for banned in ("diurnal", "plain-english", "posture", "surface"):
        assert banned not in wf_doc.lower()
    for p in (SRC_DIR / "agy_nexus" / "catalog_sync.py", SRC_DIR / "agy_nexus" / "tools_ops.py", REPO_ROOT / "scripts" / "catalog_sync.py", Path(__file__)):
        lines = p.read_text(encoding="utf-8").splitlines()
        assert len(lines) <= 500, f"{p.name} > 500L ({len(lines)}L)"
        tree = ast.parse("\n".join(lines), filename=str(p))
        for fn in ast.walk(tree):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and fn.end_lineno:
                assert fn.end_lineno - fn.lineno + 1 <= 100, f"{p.name}:{fn.name} > 100L"
