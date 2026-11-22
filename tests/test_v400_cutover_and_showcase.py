"""tests/test_v400_cutover_and_showcase.py — AGY-Nexus v4.0.0 Live Cutover & GitHub Pages Showcase Suite."""
from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys

from starlette.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
SCRIPTS_DIR = REPO_ROOT / "scripts"
WEB_DIR = REPO_ROOT / "web"
V9_DIR = WEB_DIR / "v9"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import agy_nexus
from agy_nexus import web_routes
from agy_nexus.config import get_polyglot_mcp_token, get_praxis_mcp_token
from agy_nexus.server import build_nexus_http_app


def _load_script_mod(name: str):
    path = SCRIPTS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_v400_version_changelog_and_modular_budgets() -> None:
    """Verify 4.0.0 across pyproject, package, changelog archive split, scripts, and web/v9 modules."""
    assert agy_nexus.__version__ == "4.0.0"
    assert 'version = "4.0.0"' in (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    changelog_lines = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    assert 20 <= len(changelog_lines) <= 450, f"CHANGELOG.md unexpected size: {len(changelog_lines)}L"
    assert "## [4.0.0]" in changelog_lines[6]
    assert (REPO_ROOT / "docs" / "CHANGELOG_ARCHIVE.md").is_file()
    assert "## [2.9.0]" in (REPO_ROOT / "docs" / "CHANGELOG_ARCHIVE.md").read_text(encoding="utf-8")

    for py_path in (
        SCRIPTS_DIR / "build_github_showcase.py",
        SCRIPTS_DIR / "publish_to_github.py",
        SCRIPTS_DIR / "export_depersonalized_showcase.py",
    ):
        lines = py_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) <= 500, f"{py_path.name} exceeded 500L ({len(lines)}L)"
        tree = ast.parse("\n".join(lines), filename=str(py_path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_len = (node.end_lineno or node.lineno) - node.lineno + 1
                assert fn_len <= 100, f"{py_path.name}:{node.name} exceeded 100L ({fn_len}L)"

    for js_path in sorted(V9_DIR.glob("*.js")):
        assert len(js_path.read_text(encoding="utf-8").splitlines()) <= 500, f"{js_path.name} > 500L"


def test_v400_live_web_cutover_and_pwa_integrity() -> None:
    """Verify /web, /web/, /web/v9 serve identical Quiet UI v9.3.0 HTML and SW v4.0.0 assets."""
    web_html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    v9_html = (V9_DIR / "index.html").read_text(encoding="utf-8")
    assert web_html == v9_html
    assert 'id="v9ManifestLink" href="/web/manifest.webmanifest"' in web_html
    assert "v9_demo_docs.js?v=4.0.0" in web_html

    vendor_dir = V9_DIR / "vendor"
    assert "v9.3.0" in (vendor_dir / "THIRD_PARTY_LICENSES.txt").read_text(encoding="utf-8")
    assert ".va-rail-footer" in (vendor_dir / "quiet-evidence-bundle.css").read_text(encoding="utf-8")
    assert ".va-split-reader-gallery" in (vendor_dir / "quiet-evidence-bundle.css").read_text(encoding="utf-8")
    ev_js = (vendor_dir / "quiet-evidence-bundle.js").read_text(encoding="utf-8")
    assert "buildCyclicalWhiskerOption" in ev_js and "QuietPeriodStepper" in ev_js
    assert "Object.assign(root.QuietEChartsDefaults" in (vendor_dir / "echarts-layout-defaults.js").read_text(encoding="utf-8")

    secret = "test_v400_cutover_secret_token_00112233445566"
    app = build_nexus_http_app(secret, polyglot_token=get_polyglot_mcp_token(secret), praxis_token=get_praxis_mcp_token(secret))
    with TestClient(app) as client:
        r_health = client.get("/health")
        assert r_health.status_code == 200 and r_health.json()["version"] == "4.0.0"
        for route in ("/web", "/web/", "/web/index.html", "/web/v9", "/web/v9/index.html"):
            r = client.get(route)
            assert r.status_code == 200 and 'id="v9AppShell"' in r.text
            assert "no-store" in r.headers.get("cache-control", "")
        assert "v9/v9_demo_docs.js" in web_routes.PWA_ASSETS
        r_doc_js = client.get("/web/v9/v9_demo_docs.js?v=4.0.0")
        assert r_doc_js.status_code == 200 and "getDemoDocFile" in r_doc_js.text


def test_v400_js_static_showcase_url_mapping_and_6_presets(tmp_path: Path) -> None:
    """Verify static showcase flag, ./ asset URLs, clean history URLs, ./ Markdown images, and all 6 presets."""
    js_test = tmp_path / "test_showcase.cjs"
    js_test.write_text(
        """
const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

let replacedUrl = "";
const elStore = {
  v9DocContent: { innerHTML: "", querySelectorAll: () => [] },
  v9DocMeta: { textContent: "" },
};
const docStub = {
  documentElement: { setAttribute: () => {} },
  getElementById: (id) => elStore[id] || null,
  querySelectorAll: () => [],
};
const ctx = {
  window: {
    AGY_STATIC_SHOWCASE: true,
    location: { hostname: "example.github.io", pathname: "/agy-nexus-mcp/", search: "", hash: "#analytics", href: "https://example.github.io/agy-nexus-mcp/#analytics", origin: "https://example.github.io" },
    history: { replaceState: (_s, _t, u) => { replacedUrl = u; } },
    innerWidth: 1440,
  },
  document: docStub,
  localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
  sessionStorage: { getItem: () => null, setItem: () => {} },
  navigator: {},
  URLSearchParams,
};
ctx.window.AgyV9 = {};
for (const rel of ["web/v9/v9_state.js", "web/demo_snapshot.js", "web/v9/v9_demo_docs.js", "web/v9/v9_demo_adapter.js", "web/v9/v9_markdown.js"]) {
  vm.runInNewContext(fs.readFileSync(rel, "utf-8"), ctx);
}
const V9 = ctx.window.AgyV9;
assert.strictEqual(V9.isStaticShowcase(), true);
assert.strictEqual(V9.state.demoMode, true);
assert.strictEqual(V9.state.passphrase, "");
assert.strictEqual(V9.toAssetUrl("demo_thumb_desktop.png"), "./demo_thumb_desktop.png");
V9.syncUrlState();
assert.ok(!replacedUrl.includes("demo=1"), "Static showcase should omit ?demo=1 noise");

for (const [tf, hm] of [["month", "to_date"], ["month", "rolling"], ["quarter", "to_date"], ["quarter", "rolling"], ["year", "to_date"], ["year", "rolling"]]) {
  assert.strictEqual(V9.DemoAdapter.isPresetAvailable(tf, hm), true, `Missing preset ${tf}/${hm}`);
  assert.ok(V9.DemoAdapter.getDemoStatsBundle(tf, hm, 0), `Empty bundle for ${tf}/${hm}`);
}
assert.ok(V9.DemoAdapter.getDemoStatsBundle("month", "to_date", -1), "Missing last_month bundle");

const sessIds = Object.keys(ctx.window.DEMO_SNAPSHOT.demo_sessions || {});
assert.ok(sessIds.length >= 3, "Expected >=3 bundled demo sessions");
Promise.resolve(V9.DemoAdapter.getDemoSessionBucket(sessIds[0])).then(async (bucket) => {
  assert.ok(bucket.artifacts.length >= 3);
  assert.ok(bucket.visual_artifacts[0].signed_url.startsWith("./demo_thumb_"));
  const doc = await V9.DemoAdapter.getDemoDocFile("walkthrough.md", bucket);
  assert.ok(doc.content.includes("./demo_thumb_"));
  assert.strictEqual(V9.Markdown.sanitizeUrl("./demo_thumb_desktop.png", false), "./demo_thumb_desktop.png");
  assert.strictEqual(V9.Markdown.resolveImageUrl("./demo_thumb_desktop.png", bucket), "./demo_thumb_desktop.png");
  assert.strictEqual(V9.Markdown.sanitizeUrl("./../etc/passwd", false), "");
  assert.strictEqual(V9.Markdown.sanitizeUrl("//evil.com/x.png", false), "");
  assert.strictEqual(V9.Markdown.sanitizeUrl("javascript:alert(1)", false), "");
  console.log("SHOWCASE_JS_OK");
});
""",
        encoding="utf-8",
    )
    proc = subprocess.run(["node", str(js_test)], cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"
    assert "SHOWCASE_JS_OK" in proc.stdout


def test_v400_build_github_showcase_privacy_gate_and_dry_run(tmp_path: Path, monkeypatch) -> None:
    """Verify build_showcase produces 0-leak relative bundle, catches leaks cleanly, and dry-run succeeds."""
    bgs = _load_script_mod("build_github_showcase")
    ptg = _load_script_mod("publish_to_github")
    out_dir = tmp_path / "gh-pages"
    res = bgs.build_showcase(out_dir, refresh=False)
    assert res["ok"] is True and res["privacy_findings"] == 0 and res["files"] >= 35
    assert (out_dir / ".nojekyll").is_file()
    idx_txt = (out_dir / "index.html").read_text(encoding="utf-8")
    assert "window.AGY_STATIC_SHOWCASE = true;" in idx_txt
    assert 'href="/web/' not in idx_txt and 'src="/web/' not in idx_txt
    assert 'href="./v9/v9_shell.css?v=4.0.0"' in idx_txt

    mf = json.loads((out_dir / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert mf["id"] == "./" and mf["start_url"] == "./" and mf["icons"][0]["src"].startswith("./")

    # Negative leak tests: inject .lan, RFC1918 IP, and PNG tEXt chunk
    leak_dir = tmp_path / "leak-probe"
    leak_dir.mkdir()
    (leak_dir / "probe.js").write_text('const h = "nas-box.lan"; const ip = "192.168.1.99";', encoding="utf-8")
    sample_png = (out_dir / "demo_thumb_desktop.png").read_bytes()
    t_data = b"Author\x00test-leak"
    t_chunk = struct.pack(">I", len(t_data)) + b"tEXt" + t_data + b"\x00\x00\x00\x00"
    (leak_dir / "meta.png").write_bytes(sample_png[:-12] + t_chunk + sample_png[-12:])
    findings = bgs.scan_showcase_privacy(leak_dir)
    assert any(".lan" in f for f in findings)
    assert any("192.168.1.99" in f for f in findings)
    assert any("tEXt" in f for f in findings)

    # publish_to_github --dry-run must succeed without GITHUB_TOKEN
    monkeypatch.setattr(ptg, "_load_token_from_env_files", lambda: "")
    monkeypatch.setattr(sys, "argv", ["publish_to_github.py", "--dry-run"])
    assert ptg.main() == 0


import pytest


def test_v400_p1_hardening_png_sw_and_backend_budgets(tmp_path: Path) -> None:
    """Verify PNG bounds checks, SW canonicalCacheKey secret stripping, Markdown rel attrs, and backend <=100L fns."""
    bgs = _load_script_mod("build_github_showcase")
    sample_png = (WEB_DIR / "demo_thumb_desktop.png").read_bytes()

    # 1. PNG negative cases for strip_png_metadata & _inspect_png_privacy
    bad_sig = tmp_path / "not_png.png"
    bad_sig.write_bytes(b"NOTPNG000000")
    with pytest.raises(ValueError):
        bgs.strip_png_metadata(bad_sig, tmp_path / "out1.png")

    trunc_png = tmp_path / "trunc.png"
    trunc_png.write_bytes(b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 9999) + b"IHDR" + b"\x00" * 8)
    with pytest.raises(ValueError):
        bgs.strip_png_metadata(trunc_png, tmp_path / "out2.png")
    assert any("truncated" in f or "IEND" in f for f in bgs._inspect_png_privacy(trunc_png, set(), "trunc.png"))

    no_iend = tmp_path / "no_iend.png"
    no_iend.write_bytes(sample_png[:-12])
    with pytest.raises(ValueError):
        bgs.strip_png_metadata(no_iend, tmp_path / "out3.png")
    assert any("IEND" in f for f in bgs._inspect_png_privacy(no_iend, set(), "no_iend.png"))

    trailing_png = tmp_path / "trailing.png"
    trailing_png.write_bytes(sample_png + b"TRAILING")
    assert any("trailing" in f.lower() for f in bgs._inspect_png_privacy(trailing_png, set(), "trailing.png"))

    # 2. Markdown security + SW canonicalCacheKey secret stripping in Node VM
    vm_probe = tmp_path / "p1_js_probe.cjs"
    vm_probe.write_text(
        """
const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

const swCtx = {
  self: { location: { origin: "https://nexus.example.com", pathname: "/secret_tok/web/sw.js" }, addEventListener: () => {} },
  URL,
};
vm.runInNewContext(fs.readFileSync("web/sw.js", "utf-8"), swCtx);
assert.strictEqual(
  swCtx.canonicalCacheKey(new URL("https://nexus.example.com/secret_tok/web/v9/v9_app.js?v=4.0.0")),
  "https://nexus.example.com/web/v9/v9_app.js?v=4.0.0"
);

const docEl = { innerHTML: "", querySelectorAll: () => [] };
const mdCtx = {
  window: {
    location: { hostname: "example.github.io", pathname: "/agy-nexus-mcp/", search: "", hash: "" },
    history: { replaceState: () => {} }, innerWidth: 1440, AgyV9: {},
  },
  document: { documentElement: { setAttribute: () => {} }, getElementById: (id) => (id === "v9DocContent" ? docEl : null) },
  localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
  sessionStorage: { getItem: () => null, setItem: () => {} },
  DOMParser: class { parseFromString(html) { return { body: { querySelectorAll: () => [], innerHTML: html } }; } },
  URLSearchParams,
};
vm.runInNewContext(fs.readFileSync("web/v9/v9_state.js", "utf-8"), mdCtx);
vm.runInNewContext(fs.readFileSync("web/v9/v9_markdown.js", "utf-8"), mdCtx);
const MD = mdCtx.window.AgyV9.Markdown;
assert.strictEqual(MD.sanitizeUrl("/\\\\evil.com", false), "");
assert.strictEqual(MD.sanitizeUrl("/../etc/passwd", false), "");
assert.strictEqual(MD.sanitizeUrl("HTTPS://example.com/a", true), "HTTPS://example.com/a");
MD.renderDocument({ rel_path: "note.md", content: "[Ext](HTTPS://example.com/path)" }, {});
assert.ok(docEl.innerHTML.includes('rel="noopener noreferrer"'), docEl.innerHTML);
console.log("P1_JS_OK");
""",
        encoding="utf-8",
    )
    proc = subprocess.run(["node", str(vm_probe)], cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"
    assert "P1_JS_OK" in proc.stdout

    # 3. Backend AST <=100L functions & decorator/return integrity
    budget_fns = {
        "src/agy_nexus/web_routes.py": {"_serve_static_or_media", "_handle_web_stats", "handle_web_request"},
        "src/agy_nexus/tools_ops.py": {"_dispatch_models_action", "_handle_job_status_or_tail", "manage_background_run"},
        "src/agy_nexus/stats.py": {"build_nexus_stats_bundle", "_assemble_stats_output"},
        "src/agy_nexus/stats_series.py": {"_build_other_projects_rollup", "build_series_and_project_hierarchy"},
    }
    for rel, expected_fns in budget_fns.items():
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert len(text.splitlines()) <= 500, f"{rel} > 500L"
        tree = ast.parse(text, filename=rel)
        found: dict[str, int] = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in expected_fns:
                found[node.name] = (node.end_lineno or node.lineno) - node.lineno + 1
        assert set(found) == expected_fns, f"Missing expected functions in {rel}: {expected_fns - set(found)}"
        for fn_name, fn_len in found.items():
            assert fn_len <= 100, f"{rel}:{fn_name} exceeded 100L ({fn_len}L)"

    ops_txt = (REPO_ROOT / "src/agy_nexus/tools_ops.py").read_text(encoding="utf-8")
    assert "@mcp.tool(annotations=READONLY_ANNOTATIONS, output_schema=None)\ndef manage_background_run(" in ops_txt
    stats_txt = (REPO_ROOT / "src/agy_nexus/stats.py").read_text(encoding="utf-8")
    assert "return _assemble_stats_output(" in stats_txt

