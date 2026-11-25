"""tests/test_v405_gallery_select_all_scope.py — AGY-Nexus v4.0.8 Workspace Gallery Select-All Scope."""

from __future__ import annotations

import json
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

import agy_nexus
from agy_nexus import polyglot_outline, web_routes


def test_v405_gallery_select_all_node_vm(tmp_path: Path) -> None:
    """Execute gallery_select.js + v9_gallery.js in Node VM across 3+10, manual 3/3, 0+10, and Shift+Click boundary."""
    probe = tmp_path / "v405_gallery_scope_probe.cjs"
    probe.write_text(
        """
const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

function parseAttrs(raw) {
  const attrs = {};
  const attrRe = /([a-zA-Z0-9_-]+)(?:="([^"]*)")?/g;
  let m;
  while ((m = attrRe.exec(raw)) !== null) {
    attrs[m[1]] = m[2] !== undefined ? m[2] : "";
  }
  return attrs;
}

class FakeEl {
  constructor(tag = "div", attrs = {}, text = "") {
    this.tagName = tag.toUpperCase();
    this.attrs = { ...attrs };
    this.id = attrs.id || "";
    this.textContent = text;
    this.disabled = Object.prototype.hasOwnProperty.call(attrs, "disabled");
    this.dataset = {};
    this.listeners = {};
    this.children = [];
    this.parentElement = null;
    this.isConnected = true;
    const clsSet = new Set(String(attrs.class || "").split(/\\s+/).filter(Boolean));
    this.classList = {
      add: (...c) => c.forEach((x) => clsSet.add(x)),
      remove: (...c) => c.forEach((x) => clsSet.delete(x)),
      toggle: (x, force) => {
        if (force === undefined) { if (clsSet.has(x)) clsSet.delete(x); else clsSet.add(x); }
        else if (force) clsSet.add(x); else clsSet.delete(x);
      },
      contains: (x) => clsSet.has(x),
    };
    this._clsSet = clsSet;
    this._html = "";
  }
  set innerHTML(html) {
    this._html = String(html || "");
    this.children = [];
    if (this.id === "v9GalToolbar") this._parseToolbar(this._html);
    else if (this.id === "v9GalGrid" || this.id === "v9RepoAssetsGrid") this._parseCards(this._html);
  }
  get innerHTML() { return this._html; }
  _parseToolbar(html) {
    const cntM = /<span class="v9-gal-count">([^<]*)<\\/span>/.exec(html);
    if (cntM) {
      const sp = new FakeEl("span", { class: "v9-gal-count" }, cntM[1]);
      sp.parentElement = this;
      this.children.push(sp);
    }
    const btnRe = /<button\\s+([^>]*)>([\\s\\S]*?)<\\/button>/g;
    let bm;
    while ((bm = btnRe.exec(html)) !== null) {
      const attrs = parseAttrs(bm[1]);
      const txt = bm[2].replace(/<[^>]+>/g, "").trim();
      const b = new FakeEl("button", attrs, txt);
      b.parentElement = this;
      this.children.push(b);
    }
  }
  _parseCards(html) {
    const artRe = /<article\\s+([^>]*)>([\\s\\S]*?)<\\/article>/g;
    let am;
    while ((am = artRe.exec(html)) !== null) {
      const card = new FakeEl("article", parseAttrs(am[1]));
      card.parentElement = this;
      const selM = /<button\\s+([^>]*data-sel-idx="[^"]*"[^>]*)>([^<]*)<\\/button>/.exec(am[2]);
      if (selM) {
        const sb = new FakeEl("button", parseAttrs(selM[1]), selM[2]);
        sb.parentElement = card;
        card.children.push(sb);
      }
      this.children.push(card);
    }
  }
  getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; }
  setAttribute(k, v) { this.attrs[k] = String(v); if (k === "disabled") this.disabled = true; }
  addEventListener(ev, fn) { (this.listeners[ev] = this.listeners[ev] || []).push(fn); }
  dispatchClick(extra = {}) {
    if (this.disabled) return;
    const evt = { stopPropagation: () => {}, preventDefault: () => {}, shiftKey: false, ...extra, target: this };
    (this.listeners.click || []).forEach((fn) => fn(evt));
  }
  contains(node) {
    let cur = node;
    while (cur) { if (cur === this) return true; cur = cur.parentElement; }
    return false;
  }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
  querySelectorAll(sel) {
    const out = [];
    const walk = (el) => {
      for (const ch of el.children) {
        if (sel === ".v9-gal-card" && ch._clsSet.has("v9-gal-card")) out.push(ch);
        else if (sel === ".v9-gal-sel-btn" && ch._clsSet.has("v9-gal-sel-btn")) out.push(ch);
        else if (sel.startsWith("#") && ch.id === sel.slice(1)) out.push(ch);
        else if (sel === "[data-sel-idx]" && ch.getAttribute("data-sel-idx") !== null) out.push(ch);
        else if (sel === ".v9-gal-count" && ch._clsSet.has("v9-gal-count")) out.push(ch);
        walk(ch);
      }
    };
    walk(this);
    return out;
  }
}

const byId = {
  v9GalToolbar: new FakeEl("div", { id: "v9GalToolbar" }),
  v9GalGrid: new FakeEl("div", { id: "v9GalGrid" }),
  v9RepoAssetsGrid: new FakeEl("div", { id: "v9RepoAssetsGrid" }),
  v9RepoAssetsCount: new FakeEl("span", { id: "v9RepoAssetsCount" }, "0"),
  v9CapturesBtnCount: new FakeEl("span", { id: "v9CapturesBtnCount" }, "0"),
  v9GalStatus: new FakeEl("div", { id: "v9GalStatus" }),
};

const document = {
  getElementById: (id) => byId[id] || null,
  querySelectorAll: (sel) => {
    if (sel.includes("#v9GalGrid .v9-gal-card")) {
      return [...byId.v9GalGrid.querySelectorAll(".v9-gal-card"), ...byId.v9RepoAssetsGrid.querySelectorAll(".v9-gal-card")];
    }
    return [];
  },
  addEventListener: () => {},
  createElement: (tag) => new FakeEl(tag),
};

const ctx = {
  window: {
    innerWidth: 1440,
    AgyV9: {
      escHtml: (s) => String(s ?? ""),
      fmtBytes: (n) => `${n} B`,
      state: { demoMode: false, selectedSession: "sess-1" },
      Lightbox: { openSingle: () => {}, openCompare: () => {} },
      getBasePath: () => "",
    },
    SheetBuilder: { getPerSheet: () => 4, setPerSheet: () => {}, downloadSheets: () => {}, shareSheetsToGemini: () => {} },
  },
  document,
  navigator: {},
  URL,
  setTimeout,
  clearTimeout,
};
ctx.window.document = document;
ctx.self = ctx.window;

vm.runInNewContext(fs.readFileSync("web/gallery_select.js", "utf-8"), ctx);
const capturedGestureItems = {};
const origBind = ctx.window.GallerySelect.bindGalleryGestures;
ctx.window.GallerySelect.bindGalleryGestures = (grid, getItemsFn, syncFn) => {
  capturedGestureItems[grid.id] = getItemsFn;
  return origBind(grid, getItemsFn, syncFn);
};
vm.runInNewContext(fs.readFileSync("web/v9/v9_gallery.js", "utf-8"), ctx);

const GS = ctx.window.GallerySelect;
const Gal = ctx.window.AgyV9.Gallery;

const makeCaps = (n) => Array.from({ length: n }, (_, i) => ({
  name: `cap_${i + 1}.png`, scope: "brain", rel_path: `cap_${i + 1}.png`,
  signed_url: `/web/media/cap_${i + 1}.png`, width: 1440, height: 900,
}));
const makeRepoAssets = (n) => Array.from({ length: n }, (_, i) => ({
  name: `asset_${i + 1}.png`, scope: "repo", rel_path: `docs/assets/asset_${i + 1}.png`,
  signed_url: `/web/media/asset_${i + 1}.png`, width: 800, height: 600,
}));

// Scenario 1: 3 session captures + 10 collapsed Shared Repo Assets
const caps3 = makeCaps(3);
const repo10 = makeRepoAssets(10);
Gal.renderBucketGallery({ repo_slug: "agy-nexus-mcp", visual_artifacts: caps3, repo_visual_assets: repo10 });

assert.strictEqual(byId.v9GalToolbar.querySelector(".v9-gal-count").textContent, "3 captures");
assert.strictEqual(byId.v9RepoAssetsCount.textContent, "10");
assert.strictEqual(Gal.getSessionItems().length, 3);
assert.strictEqual(Gal.getItems().length, 13);

// Gesture isolation check: #v9GalGrid gets only 3 session items; #v9RepoAssetsGrid cannot touch 0..2
assert.strictEqual(capturedGestureItems.v9GalGrid().length, 3);
assert.strictEqual(capturedGestureItems.v9RepoAssetsGrid().slice(0, 3).filter(Boolean).length, 0);
assert.strictEqual(capturedGestureItems.v9RepoAssetsGrid().slice(3).length, 10);

let allBtn = byId.v9GalToolbar.querySelector("#v9GalAllBtn");
assert.strictEqual(allBtn.textContent, "All");
assert.strictEqual(allBtn.disabled, false);

// Click All -> selects ONLY the 3 session captures, never the 10 repo assets!
allBtn.dispatchClick();
assert.strictEqual(GS.getSelectedList().length, 3);
assert.ok(GS.getSelectedList().every((it) => it.scope === "brain"));
assert.strictEqual(byId.v9GalToolbar.querySelector(".v9-gal-count").textContent, "3 selected");
allBtn = byId.v9GalToolbar.querySelector("#v9GalAllBtn");
assert.strictEqual(allBtn.textContent, "Clear");

// Click Clear -> clears all 3
allBtn.dispatchClick();
assert.strictEqual(GS.getSelectedList().length, 0);
assert.strictEqual(byId.v9GalToolbar.querySelector(".v9-gal-count").textContent, "3 captures");
assert.strictEqual(byId.v9GalToolbar.querySelector("#v9GalAllBtn").textContent, "All");

// Manually select all 3 session captures one by one -> flips button to Clear
for (let i = 0; i < 3; i += 1) {
  byId.v9GalGrid.querySelectorAll("[data-sel-idx]")[i].dispatchClick();
}
assert.strictEqual(GS.getSelectedList().length, 3);
assert.strictEqual(byId.v9GalToolbar.querySelector("#v9GalAllBtn").textContent, "Clear");

// Cross-grid Shift+Click boundary: selecting repo[0] with Shift after session[2] must NOT span across grids
byId.v9RepoAssetsGrid.querySelectorAll("[data-sel-idx]")[0].dispatchClick({ shiftKey: true });
assert.strictEqual(GS.getSelectedList().length, 4);
assert.strictEqual(GS.isSelected(repo10[0]), true);
assert.strictEqual(GS.isSelected(repo10[1]), false);
// Clicking Clear clears BOTH session captures and the manually selected repo asset
byId.v9GalToolbar.querySelector("#v9GalAllBtn").dispatchClick();
assert.strictEqual(GS.getSelectedList().length, 0);

// Shift+Click within session grid works (0 -> 2 selects 0,1,2 only)
byId.v9GalGrid.querySelectorAll("[data-sel-idx]")[0].dispatchClick();
byId.v9GalGrid.querySelectorAll("[data-sel-idx]")[2].dispatchClick({ shiftKey: true });
assert.strictEqual(GS.getSelectedList().length, 3);
assert.ok(GS.getSelectedList().every((it) => it.scope === "brain"));

// Scenario 2: 0 session captures + 10 Shared Repo Assets
Gal.renderBucketGallery({ repo_slug: "agy-nexus-mcp", visual_artifacts: [], repo_visual_assets: repo10 });
assert.strictEqual(byId.v9GalToolbar.querySelector(".v9-gal-count").textContent, "0 captures");
allBtn = byId.v9GalToolbar.querySelector("#v9GalAllBtn");
assert.strictEqual(allBtn.textContent, "All");
assert.strictEqual(allBtn.disabled, true);
assert.strictEqual(GS.getSelectedList().length, 0);

// Manually toggle 1 repo asset -> All flips to Clear and becomes enabled
byId.v9RepoAssetsGrid.querySelectorAll("[data-sel-idx]")[0].dispatchClick();
assert.strictEqual(GS.getSelectedList().length, 1);
allBtn = byId.v9GalToolbar.querySelector("#v9GalAllBtn");
assert.strictEqual(allBtn.textContent, "Clear");
assert.strictEqual(allBtn.disabled, false);

// Clicking Clear clears the manual repo selection and disables All again
allBtn.dispatchClick();
assert.strictEqual(GS.getSelectedList().length, 0);
allBtn = byId.v9GalToolbar.querySelector("#v9GalAllBtn");
assert.strictEqual(allBtn.textContent, "All");
assert.strictEqual(allBtn.disabled, true);

// Reset clears both arrays cleanly
Gal.reset();
assert.strictEqual(Gal.getSessionItems().length, 0);
assert.strictEqual(Gal.getItems().length, 0);
console.log("OK_V405_GALLERY_SCOPE");
""",
        encoding="utf-8",
    )
    res = subprocess.run(["node", str(probe)], cwd=str(REPO_ROOT), capture_output=True, text=True, check=False)
    assert res.returncode == 0, f"Node v4.0.8 probe failed:\n{res.stderr}\n{res.stdout}"
    assert "OK_V405_GALLERY_SCOPE" in res.stdout


def test_v405_version_budgets_pwa_and_workflows_contracts() -> None:
    """Verify v4.1.0 across package, PWA, WORKFLOWS.md, CHANGELOG.md, and <=350L/<=100L gallery module budgets."""
    assert agy_nexus.__version__ == "4.1.0"
    assert 'version = "4.1.0"' in (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    gal_txt = (V9_DIR / "v9_gallery.js").read_text(encoding="utf-8")
    gal_lines = gal_txt.splitlines()
    assert len(gal_lines) <= 350, f"v9_gallery.js exceeded 350L ({len(gal_lines)}L)"
    assert not re.search(r"[🔒✦⬇◀▶✓✕]", gal_txt), "Forbidden UI pictograph in v9_gallery.js"
    _s, _f, syms = polyglot_outline.outline_code(".js", gal_lines)
    assert not any(int(sym.get("lines") or 0) > 100 for sym in syms)

    sw_txt = (WEB_DIR / "sw.js").read_text(encoding="utf-8")
    assert 'CACHE_NAME = "agy-nexus-v4.1.0"' in sw_txt
    assert "/web/v9/v9_gallery.js?v=4.1.0" in sw_txt
    assert "v9/v9_gallery.js" in web_routes.PWA_ASSETS

    html_txt = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    assert html_txt == (V9_DIR / "index.html").read_text(encoding="utf-8")
    assert "/web/v9/v9_gallery.js?v=4.1.0" in html_txt

    wf_txt = (REPO_ROOT / "docs" / "WORKFLOWS.md").read_text(encoding="utf-8")
    assert "Workflow 6:" in wf_txt and "v4.0.8" in wf_txt
    assert "#v9GalAllBtn" in wf_txt and "Shared Repo Assets" in wf_txt

    ch_txt = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [4.1.0]" in ch_txt
