"""tests/test_v420_showcase_and_docs.py — AGY-Nexus v4.2.0 Three-Route Site, Docs & Discoverability Suite."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import tomllib

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
WEB_DIR = REPO_ROOT / "web"
SITE_DIR = WEB_DIR / "site"
V9_DIR = WEB_DIR / "v9"

OAW_URLS = (
    "https://www.oaworkbench.org/",
    "https://projects.oaworkbench.org/",
    "https://learn.oaworkbench.org/",
)
QUIET_THEMES = ("white", "paper", "dark-paper", "dark")
REQUIRED_DOC_IDS = ("doc-quickstart", "doc-common-terms", "doc-architecture", "doc-how-it-is-built")
BANNED_PACING_TERMS = (
    "quota pacing",
    "quota-pacing",
    "weekly pacing",
    "partner_weekly_pacing",
    "ON PACE",
    ">WARM<",
    ">HOT<",
)


def _load_script_mod(name: str):
    path = SCRIPTS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _png_dimensions(png_path: Path) -> tuple[int, int]:
    raw = png_path.read_bytes()
    assert raw.startswith(b"\x89PNG\r\n\x1a\n") and raw[12:16] == b"IHDR"
    return struct.unpack(">II", raw[16:24])


def _iter_non_vendor_files(root: Path, *, exclude_vendor: bool = True):
    for fp in sorted(root.rglob("*")):
        if not fp.is_file():
            continue
        if exclude_vendor and "vendor" in fp.relative_to(root).parts:
            continue
        if fp.suffix.lower() in {".md", ".html", ".js", ".css", ".json", ".toml", ".svg", ".webmanifest"}:
            yield fp


def test_v420_three_route_build_and_relative_links(tmp_path: Path) -> None:
    """Verify build_showcase emits ./, ./demo/, ./docs/ with 0 privacy findings and subpath-safe links."""
    bgs = _load_script_mod("build_github_showcase")
    out_dir = tmp_path / "gh-pages"
    res = bgs.build_showcase(out_dir, refresh=False)
    assert res["ok"] is True and res["privacy_findings"] == 0 and res["chapters"] == 10
    assert bgs.scan_showcase_privacy(out_dir) == []

    landing_html = (out_dir / "index.html").read_text(encoding="utf-8")
    demo_html = (out_dir / "demo" / "index.html").read_text(encoding="utf-8")
    docs_html = (out_dir / "docs" / "index.html").read_text(encoding="utf-8")
    assert (out_dir / "docs" / "docs_data.js").is_file()
    for asset_name in ("oaw_topbar.css", "site_shell.css", "site_shell.js", "docs.css", "docs_app.js", "social-preview.png"):
        assert (out_dir / "assets" / asset_name).is_file()

    assert 'href="./demo/"' in landing_html and 'href="./docs/"' in landing_html
    assert 'href="./assets/oaw_topbar.css' in landing_html and 'href="./assets/site_shell.css' in landing_html and 'src="./assets/site_shell.js' in landing_html
    assert 'href="../"' in demo_html and 'href="../docs/"' in demo_html
    assert 'href="../v9/v9_shell.css?v=4.2.0"' in demo_html and 'href="../assets/oaw_topbar.css?v=4.2.0"' in demo_html and 'href="../manifest.webmanifest"' in demo_html
    assert 'href="../"' in docs_html and 'href="../demo/"' in docs_html and 'href="./"' in docs_html
    assert 'src="./docs_data.js' in docs_html and 'src="../assets/docs_app.js' in docs_html

    for route_name, html_text in (("index.html", landing_html), ("demo/index.html", demo_html), ("docs/index.html", docs_html)):
        bad_roots = re.findall(r'(?:href|src|content)="/(?:web|demo|docs|assets)/', html_text)
        assert not bad_roots, f"Non-subpath root-relative URLs in {route_name}: {bad_roots}"


def test_v420_showcase_bar_visibility_and_node_vm_toggle(tmp_path: Path) -> None:
    """Verify #v9ShowcaseBar is hidden in live HTML, shown in built demo/index.html, and toggled by V9.syncShowcaseBar."""
    bgs = _load_script_mod("build_github_showcase")
    out_dir = tmp_path / "gh-pages"
    bgs.build_showcase(out_dir, refresh=False)

    for live_path in (WEB_DIR / "index.html", V9_DIR / "index.html"):
        live_html = live_path.read_text(encoding="utf-8")
        assert '<nav id="v9ShowcaseBar" class="v9-showcase-bar hidden"' in live_html

    demo_html = (out_dir / "demo" / "index.html").read_text(encoding="utf-8")
    assert '<nav id="v9ShowcaseBar" class="v9-showcase-bar oaw-topbar"' in demo_html
    assert '<nav id="v9ShowcaseBar" class="v9-showcase-bar hidden"' not in demo_html

    vm_script = tmp_path / "showcase_bar_probe.cjs"
    vm_script.write_text(
        """
const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

function runProbe(isStatic, hostname, pathname) {
  const classes = new Set(["v9-showcase-bar", "hidden"]);
  const barEl = {
    classList: {
      toggle: (name, force) => {
        if (force === undefined) {
          if (classes.has(name)) { classes.delete(name); return false; }
          classes.add(name); return true;
        }
        if (force) classes.add(name); else classes.delete(name);
        return Boolean(force);
      },
      contains: (name) => classes.has(name),
    },
  };
  const ctx = {
    window: {
      AGY_STATIC_SHOWCASE: isStatic,
      location: { hostname, pathname, search: "", hash: "", href: `https://${hostname}${pathname}`, origin: `https://${hostname}` },
      history: { replaceState: () => {} },
      innerWidth: 1440,
      AgyV9: {},
    },
    document: {
      readyState: "complete",
      documentElement: { setAttribute: () => {} },
      getElementById: (id) => (id === "v9ShowcaseBar" ? barEl : null),
      querySelectorAll: () => [],
    },
    localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} },
    sessionStorage: { getItem: () => null, setItem: () => {} },
    URL,
    URLSearchParams,
  };
  vm.runInNewContext(fs.readFileSync("web/v9/v9_state.js", "utf-8"), ctx);
  return { V9: ctx.window.AgyV9, win: ctx.window, classes };
}

const staticRun = runProbe(true, "projects.oaworkbench.org", "/agy-nexus-mcp/demo/");
assert.strictEqual(staticRun.V9.isStaticShowcase(), true);
assert.strictEqual(staticRun.classes.has("hidden"), false);

const liveRun = runProbe(false, "localhost", "/web/");
assert.strictEqual(liveRun.V9.isStaticShowcase(), false);
assert.strictEqual(liveRun.classes.has("hidden"), true);
liveRun.win.AGY_STATIC_SHOWCASE = true;
liveRun.V9.syncShowcaseBar();
assert.strictEqual(liveRun.V9.isStaticShowcase(), true);
assert.strictEqual(liveRun.classes.has("hidden"), false);
liveRun.win.AGY_STATIC_SHOWCASE = false;
liveRun.V9.syncShowcaseBar();
assert.strictEqual(liveRun.classes.has("hidden"), true);
assert.strictEqual(liveRun.V9.toAbsUrl("javascript:alert(1)"), "");
assert.strictEqual(liveRun.V9.toAbsUrl("//evil.example/x"), "");
assert.strictEqual(staticRun.V9.toAbsUrl("../docs/"), "https://projects.oaworkbench.org/agy-nexus-mcp/docs/");
console.log("SHOWCASE_BAR_OK");
""",
        encoding="utf-8",
    )
    proc = subprocess.run(["node", str(vm_script)], cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"
    assert "SHOWCASE_BAR_OK" in proc.stdout


def test_v420_social_preview_metadata_topics_and_dry_run(tmp_path: Path, monkeypatch) -> None:
    """Verify 1280x640 clean social preview PNG, server.json, pyproject.toml, 14 topics, and dry-run."""
    bgs = _load_script_mod("build_github_showcase")
    ptg = _load_script_mod("publish_to_github")
    out_dir = tmp_path / "gh-pages"
    bgs.build_showcase(out_dir, refresh=False)

    for png_path in (REPO_ROOT / "docs" / "assets" / "social-preview.png", out_dir / "assets" / "social-preview.png"):
        assert png_path.is_file(), f"Missing {png_path}"
        assert _png_dimensions(png_path) == (1280, 640)
        assert bgs._inspect_png_privacy(png_path, set(), png_path.name) == []

    srv = json.loads((REPO_ROOT / "server.json").read_text(encoding="utf-8"))
    assert srv["version"] == "4.2.0"
    assert srv["websiteUrl"] == "https://projects.oaworkbench.org/agy-nexus-mcp/"
    assert len(srv["description"]) <= 100

    pyp = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyp["project"]["version"] == "4.2.0"
    assert pyp["project"]["urls"]["Homepage"] == "https://projects.oaworkbench.org/agy-nexus-mcp/"
    assert pyp["project"]["urls"]["Documentation"] == "https://projects.oaworkbench.org/agy-nexus-mcp/docs/"

    disc_txt = (REPO_ROOT / "docs" / "DISCOVERABILITY.md").read_text(encoding="utf-8")
    topics = re.findall(r"^\d+\.\s+`([a-z0-9-]+)`\s*$", disc_txt, flags=re.M)
    assert len(topics) == 14 and len(set(topics)) == 14

    monkeypatch.setattr(ptg, "_load_token_from_env_files", lambda: "")
    monkeypatch.setattr(sys, "argv", ["publish_to_github.py", "--dry-run"])
    assert ptg.main() == 0


def test_v420_zero_quota_pacing_terms(tmp_path: Path) -> None:
    """Verify zero quota-pacing or gauge-label terms exist across docs, site, UI, manifests, and built output."""
    bgs = _load_script_mod("build_github_showcase")
    out_dir = tmp_path / "gh-pages"
    bgs.build_showcase(out_dir, refresh=False)

    targets: list[Path] = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "CHANGELOG.md",
        REPO_ROOT / "server.json",
        REPO_ROOT / "pyproject.toml",
    ]
    for folder in (REPO_ROOT / "docs", SITE_DIR, V9_DIR, out_dir):
        targets.extend(_iter_non_vendor_files(folder, exclude_vendor=True))

    hits: list[str] = []
    for fp in targets:
        txt = fp.read_text(encoding="utf-8", errors="ignore")
        low = txt.lower()
        for term in BANNED_PACING_TERMS:
            matched = term in txt if term in {"ON PACE", ">WARM<", ">HOT<"} else term in low
            if matched:
                hits.append(f"{fp}: `{term}`")
    assert not hits, "Found disallowed quota-pacing terms:\n" + "\n".join(hits)


def test_v420_docs_data_anchors_links_and_token_svgs(tmp_path: Path) -> None:
    """Verify docs_data.js parses in Node VM, exposes required anchors, has no broken .md links, and uses token SVGs."""
    bgs = _load_script_mod("build_github_showcase")
    out_dir = tmp_path / "gh-pages"
    bgs.build_showcase(out_dir, refresh=False)

    docs_js_path = out_dir / "docs" / "docs_data.js"
    probe = tmp_path / "docs_data_probe.cjs"
    probe.write_text(
        """
const fs = require("fs");
const vm = require("vm");
const ctx = { window: {} };
vm.runInNewContext(fs.readFileSync(process.argv[2], "utf-8"), ctx);
process.stdout.write(JSON.stringify(ctx.window.AGY_DOCS_DATA));
""",
        encoding="utf-8",
    )
    proc = subprocess.run(["node", str(probe), str(docs_js_path)], cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["version"] == "4.2.0"

    chapters = payload["chapters"]
    by_id = {ch["id"]: ch for ch in chapters}
    for req_id in REQUIRED_DOC_IDS:
        assert req_id in by_id, f"Missing required chapter anchor #{req_id}"

    for ch in chapters:
        html_str = ch["html"]
        for href in re.findall(r'href="([^"]+)"', html_str):
            if href.startswith(("http://", "https://", "mailto:", "#")):
                continue
            assert not re.search(r"\.md(?:$|[?#])", href, flags=re.I), f"Unrewritten relative .md link in {ch['id']}: {href}"

    arch_html = by_id["doc-architecture"]["html"]
    svgs = re.findall(r"<svg[\s\S]*?</svg>", arch_html)
    assert len(svgs) == 2
    for svg in svgs:
        assert "var(--" in svg
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", svg), f"Hardcoded hex color found in architecture SVG: {svg[:120]}"
        for attr_val in re.findall(r'(?:fill|stroke)="([^"]+)"', svg):
            assert attr_val == "none" or attr_val.startswith(("var(--", "url(#")), f"Non-token SVG paint: {attr_val}"


def test_v420_oaw_switcher_themes_and_empty_state_targets(tmp_path: Path) -> None:
    """Verify OAW portfolio links, all 4 Quiet UI themes in #siteThemeSelect, and #docsEmptyState jump targets."""
    bgs = _load_script_mod("build_github_showcase")
    out_dir = tmp_path / "gh-pages"
    bgs.build_showcase(out_dir, refresh=False)

    for html_path in (
        SITE_DIR / "index.html",
        SITE_DIR / "docs.html",
        WEB_DIR / "index.html",
        V9_DIR / "index.html",
        out_dir / "index.html",
        out_dir / "demo" / "index.html",
        out_dir / "docs" / "index.html",
        out_dir / "docs" / "docs_data.js",
    ):
        txt = html_path.read_text(encoding="utf-8")
        assert "research.oaworkbench.org" not in txt, f"Unconfigured research domain present in {html_path}"
        if html_path.suffix == ".html":
            for url in OAW_URLS:
                assert url in txt, f"Missing OAW URL {url} in {html_path}"

    demo_html = (out_dir / "demo" / "index.html").read_text(encoding="utf-8")
    assert 'class="v9-showcase-bar oaw-topbar"' in demo_html
    assert 'aria-current="page" data-oaw-tab="demo"' in demo_html
    for route_path, active_tab in ((out_dir / "index.html", "overview"), (out_dir / "demo" / "index.html", "demo"), (out_dir / "docs" / "index.html", "docs")):
        rt_txt = route_path.read_text(encoding="utf-8")
        assert 'class="oaw-wordmark"' in rt_txt and "OAW Projects" in rt_txt
        assert "Antigravity Nexus" in rt_txt and "Quiet User Interface Skills" in rt_txt
        assert 'https://projects.oaworkbench.org/quiet-ui-skills/' in rt_txt
        assert f'data-oaw-tab="{active_tab}"' in rt_txt and f'aria-current="page" data-oaw-tab="{active_tab}"' in rt_txt
        assert "@FrankXLT" in rt_txt
        for theme in QUIET_THEMES:
            assert f'data-theme-opt="{theme}"' in rt_txt, f"Missing theme option {theme} in {route_path}"

    overview_html = (SITE_DIR / "index.html").read_text(encoding="utf-8")
    assert '<span class="bridge-term">Two-Doorway Setup</span>' in overview_html
    assert '<span class="bridge-term">ag-bridge-mcp</span>' not in overview_html
    assert "Steer Your Coding Workstation from Gemini &amp; Track Quota % Left" in overview_html
    assert not re.search(r"<hr\b", overview_html, re.I), "Overview landing page must have zero <hr> dividers"
    for fpath in sorted(SITE_DIR.glob("*")):
        if fpath.is_file():
            assert len(fpath.read_text(encoding="utf-8").splitlines()) <= 500, f"{fpath.name} exceeds 500 lines"

    sdb = _load_script_mod("site_docs_builder")
    rendered_q = sdb._render_inline("[Query](https://projects.oaworkbench.org/?a=1&b=2)", "docs/GUIDE.md")
    assert "a=1&amp;b=2" in rendered_q and "&amp;amp;" not in rendered_q

    bad_dir = tmp_path / "bad_privacy"
    bad_dir.mkdir()
    (bad_dir / "probe.html").write_text("http://172.17.0.10:8098 internal.oaworkbench.org", encoding="utf-8")
    bad_hits = bgs.scan_showcase_privacy(bad_dir)
    assert any("172.17.0.10" in h for h in bad_hits) and any("hashed private identifier" in h for h in bad_hits)

    docs_html = (SITE_DIR / "docs.html").read_text(encoding="utf-8")
    empty_match = re.search(r'<section id="docsEmptyState"[\s\S]*?</section>', docs_html)
    assert empty_match, "Missing #docsEmptyState in web/site/docs.html"
    empty_block = empty_match.group(0)
    assert 'data-docs-reset="1"' in empty_block
    for req_id in REQUIRED_DOC_IDS:
        assert f'href="#{req_id}"' in empty_block, f"Missing #{req_id} jump target in #docsEmptyState"

    docs_app_js = (SITE_DIR / "docs_app.js").read_text(encoding="utf-8")
    assert 'id="docsTocToggle"' in docs_html and 'byId("docsTocToggle")' in docs_app_js
    assert 'id="docsHeroMeta"' in docs_html and 'byId("docsHeroMeta")' in docs_app_js
    v9_shell_css = (V9_DIR / "v9_shell.css").read_text(encoding="utf-8")
    assert "#v9ShowcaseBar.oaw-topbar" in v9_shell_css and "z-index: 40" in v9_shell_css
    v9_state_js = (V9_DIR / "v9_state.js").read_text(encoding="utf-8")
    assert 's.includes("\\\\")' in v9_state_js
    for site_html_name in ("index.html", "docs.html"):
        site_txt = (SITE_DIR / site_html_name).read_text(encoding="utf-8")
        assert 'referrerpolicy="no-referrer"' in site_txt, f"Missing no-referrer on external font link in {site_html_name}"
