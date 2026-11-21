#!/usr/bin/env python3
"""Unit tests for AGY Nexus v3.2.2 direct PNG exports (`⬇ Sheets` & `⬇ PNGs`), modal race fixes, and hardening."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import shutil
import subprocess

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = PROJECT_ROOT / "web"

_SHEET_DOM_HARNESS_JS = r"""
const assert = require("assert");
const downloads = [];
const revokedUrls = [];
let blobSeq = 0;
global.URL = {
  createObjectURL: (b) => { blobSeq += 1; return `blob:mock/${blobSeq}/${b.type || "unknown"}`; },
  revokeObjectURL: (u) => { revokedUrls.push(u); },
};
global.Blob = class MockBlob {
  constructor(parts, opts) { this.parts = parts; this.type = (opts && opts.type) || ""; }
  async arrayBuffer() {
    const buf = Buffer.concat(this.parts.map((p) => (Buffer.isBuffer(p) ? p : Buffer.from(p))));
    return buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
  }
};
global.File = class MockFile extends global.Blob {
  constructor(parts, name, opts) { super(parts, opts); this.name = name; }
};
global.Image = class MockImage {
  set src(_val) { this.naturalWidth = 800; this.naturalHeight = 500; if (this.onload) setImmediate(() => this.onload()); }
};
const mockCtx = {
  fillStyle: "", font: "", imageSmoothingEnabled: true, imageSmoothingQuality: "high",
  fillRect: () => {}, fillText: () => {}, drawImage: () => {}, measureText: (t) => ({ width: String(t).length * 8 }),
};
const createdEls = {};
function makeEl(tag, id) {
  const listeners = {}, children = [];
  const el = {
    tagName: tag.toUpperCase(), id: id || "", href: "", download: "", target: "", textContent: "",
    open: false, _innerHTML: "", _attrs: {},
    classList: { toggle: () => {}, add: () => {}, remove: () => {} },
    setAttribute: (k, v) => { el._attrs[k] = String(v); },
    getAttribute: (k) => el._attrs[k] || null,
    appendChild: (c) => children.push(c), remove: () => {}, replaceChildren: () => { el._innerHTML = ""; children.length = 0; },
    addEventListener: (ev, fn) => { (listeners[ev] ||= []).push(fn); },
    removeEventListener: (ev, fn) => { listeners[ev] = (listeners[ev] || []).filter((x) => x !== fn); },
    dispatchEvent: (ev) => { (listeners[ev.type] || []).forEach((fn) => fn(ev)); },
    click: () => {
      if (tag === "a") downloads.push({ href: el.href, download: el.download, target: el.target });
      (listeners.click || []).forEach((fn) => fn({ currentTarget: el }));
    },
    querySelector: (sel) => el._queries?.[sel] || null,
    querySelectorAll: (sel) => el._queryAll?.[sel] || [],
    getContext: () => mockCtx,
    toBlob: (cb, mime) => cb(new global.Blob([Buffer.from("PNG_BYTES")], { type: mime || "image/png" })),
    showModal: () => { el.open = true; },
    close: () => { el.open = false; setImmediate(() => el.dispatchEvent({ type: "close" })); },
  };
  Object.defineProperty(el, "innerHTML", { get: () => el._innerHTML, set: (v) => { el._innerHTML = String(v || ""); } });
  if (id) createdEls[id] = el;
  return el;
}
const dlg = makeEl("dialog", "sheetExportDialog");
makeEl("h3", "sheetExportTitle");
const batchBar = makeEl("div", "sheetExportBatchBar");
const gridEl = makeEl("div", "sheetPreviewGrid");
makeEl("button", "sheetExportCloseBtn");
const modalPngBtn = makeEl("button", "sheetModalPngsBtn");
batchBar._queries = {
  "#sheetModalPngsBtn": modalPngBtn,
  "#sheetModalZipBtn": makeEl("button", "sheetModalZipBtn"),
  "#sheetModalStatus": makeEl("span", "sheetModalStatus"),
};
batchBar._queryAll = { ".btn-share-batch": [] };
global.HTMLDialogElement = { prototype: { closedBy: "any" } };
global.document = { body: makeEl("body"), createElement: (tag) => makeEl(tag), getElementById: (id) => createdEls[id] || null };
const origSetTimeout = global.setTimeout;
global.setTimeout = (fn, ms) => origSetTimeout(fn, Math.min(ms, 2));
"""


def _run_node_harness(tmp_path: Path, filename: str, script_body: str) -> dict:
    node_bin = shutil.which("node")
    assert node_bin, "Node.js is required for frontend export tests"
    runner = tmp_path / filename
    runner.write_text(script_body, encoding="utf-8")
    proc = subprocess.run([node_bin, str(runner)], capture_output=True, text=True, check=True)
    return json.loads(proc.stdout.strip())


def test_sheet_builder_direct_png_downloads_and_modal(tmp_path: Path) -> None:
    """Verify downloadSheets emits PNGs only, modal prioritizes PNGs, share lock deduplicates, and reopen keeps grid."""
    script = _SHEET_DOM_HARNESS_JS + f"""
const SB = require({json.dumps(str(WEB_DIR / "sheet_builder.js"))});
(async () => {{
  const items9 = Array.from({{ length: 9 }}, (_, i) => ({{
    name: `cap_${{i + 1}}.png`,
    signed_url: `/web/media/t/s/brain:c1/cap_${{i + 1}}.png`,
  }}));
  const statuses = [];
  await SB.downloadSheets(items9, "quiet-ui-skills", 2, (m) => statuses.push(m));
  assert.strictEqual(downloads.length, 5);
  assert.ok(downloads.every((d) => d.download.endsWith(".png") && !d.download.endsWith(".zip")));
  assert.strictEqual(downloads[0].download, "captures_quiet-ui-skills_2up_sheet01of05.png");
  assert.strictEqual(downloads[4].download, "captures_quiet-ui-skills_2up_sheet05of05.png");
  assert.strictEqual(statuses[statuses.length - 1], "Downloaded 5 sheet PNGs");

  downloads.length = 0;
  await SB.downloadSheets(items9.slice(0, 2), "quiet-ui-skills", 2, (m) => statuses.push(m));
  assert.strictEqual(downloads.length, 1);
  assert.strictEqual(downloads[0].download, "captures_quiet-ui-skills_2up_sheet01of01.png");

  // Concurrency lock: overlapping shareSheetsToGemini calls must not open modal twice
  let openModalCount = 0;
  const origShow = dlg.showModal;
  dlg.showModal = () => {{ openModalCount += 1; origShow(); }};
  await Promise.all([
    SB.shareSheetsToGemini(items9, "quiet-ui-skills", 2, null, () => {{}}),
    SB.shareSheetsToGemini(items9, "quiet-ui-skills", 2, null, () => {{}}),
  ]);
  assert.strictEqual(openModalCount, 1);

  // Reopen while dlg.open === true or immediately after async close(): new grid must survive next tick
  const sheets5 = await SB.buildSheetBlobs(items9, "quiet-ui-skills", 2);
  dlg.close();
  SB.openSheetExportModal(sheets5, "quiet-ui-skills", 2, null, false, () => {{}});
  await new Promise((r) => setImmediate(r));
  assert.ok(dlg.open && gridEl.innerHTML.includes("Sheet 5/5"));
  assert.ok(batchBar.innerHTML.includes("⬇ Download All 5 Sheet PNGs"));
  assert.ok(batchBar.innerHTML.includes("⬇ Sheets ZIP"));

  downloads.length = 0;
  modalPngBtn.click();
  await new Promise((r) => origSetTimeout(r, 40));
  assert.strictEqual(downloads.length, 5);
  assert.ok(downloads.every((d) => d.download.endsWith(".png")));

  SB.openSheetExportModal(sheets5.slice(0, 1), "quiet-ui-skills", 2, null, false, () => {{}});
  assert.ok(batchBar.innerHTML.includes("⬇ Download Sheet PNG") && !batchBar.innerHTML.includes("sheetModalZipBtn"));
  process.stdout.write(JSON.stringify({{ ok: true }}));
}})().catch((err) => {{ console.error(err); process.exit(1); }});
"""
    res = _run_node_harness(tmp_path, "test_sheets_direct.cjs", script)
    assert res["ok"] is True


def test_gallery_select_sequential_pngs_and_security(tmp_path: Path) -> None:
    """Verify downloadSequentialPngs Blob/fallback, HTTP error rejection, 401 trigger, filename/URL guard, and toolbar."""
    script = f"""
const assert = require("assert");
const downloads = [];
let blobSeq = 0, unauthCalls = 0;
global.URL = {{ createObjectURL: () => {{ blobSeq += 1; return `blob:png/${{blobSeq}}`; }}, revokeObjectURL: () => {{}} }};
global.Blob = class MockBlob {{
  constructor(parts, opts) {{ this.parts = parts; this.type = (opts && opts.type) || "image/png"; }}
}};
global.document = {{
  body: {{ appendChild: () => {{}} }},
  createElement: () => ({{
    href: "", download: "", target: "",
    click() {{ downloads.push({{ href: this.href, download: this.download, target: this.target }}); }},
    remove() {{}},
  }}),
}};
global.fetch = async (url) => {{
  const u = String(url);
  if (u.includes("http403")) return {{ ok: false, status: 403 }};
  if (u.includes("http401")) return {{ ok: false, status: 401 }};
  if (u.includes("neterr")) throw new Error("network fail");
  return {{ ok: true, status: 200, blob: async () => new global.Blob(["PNG"], {{ type: "image/png" }}) }};
}};
const origSetTimeout = global.setTimeout;
global.setTimeout = (fn, ms) => origSetTimeout(fn, Math.min(ms, 2));

const GS = require({json.dumps(str(WEB_DIR / "gallery_select.js"))});
const SB = require({json.dumps(str(WEB_DIR / "sheet_builder.js"))});
const GV = require({json.dumps(str(WEB_DIR / "gallery_view.js"))});

(async () => {{
  GS.clearSelection();
  GS.selectAll([
    {{ scope: "brain:s1", rel_path: "a.png", name: "../evil a.png", signed_url: "/web/media/1/sig/brain:s1/a.png" }},
    {{ scope: "brain:s1", rel_path: "err.png", name: "err.png", signed_url: "/web/media/1/sig/brain:s1/http403.png" }},
    {{ scope: "brain:s1", rel_path: "neterr.png", name: "neterr.png", signed_url: "/web/media/1/sig/brain:s1/neterr.png" }},
    {{ scope: "brain:s1", rel_path: "bad.png", name: "bad.png", signed_url: "javascript:alert(1)" }},
  ]);
  const statuses = [];
  const count = await GS.downloadSequentialPngs((m) => statuses.push(m), () => {{ unauthCalls += 1; }});
  assert.strictEqual(count, 2);
  assert.strictEqual(downloads.length, 2);
  assert.strictEqual(downloads[0].href, "blob:png/1");
  assert.strictEqual(downloads[0].download, "evil_a.png");
  assert.strictEqual(downloads[1].href, "/web/media/1/sig/brain:s1/neterr.png");
  assert.ok(downloads.every((d) => d.target === ""));
  assert.strictEqual(statuses[statuses.length - 1], "Downloaded 2 PNGs (2 failed)");

  // 401 stops loop and invokes onUnauthorizedFn
  GS.clearSelection();
  GS.selectAll([{{ scope: "brain:s1", rel_path: "u.png", name: "u.png", signed_url: "/web/media/1/sig/brain:s1/http401.png" }}]);
  await GS.downloadSequentialPngs((m) => statuses.push(m), () => {{ unauthCalls += 1; }});
  assert.strictEqual(unauthCalls, 1);

  const toolbarHtml = GV.renderToolbarHtml(3);
  assert.ok(toolbarHtml.includes('id="bulkShareBtn"') && toolbarHtml.includes('id="bulkSheetsDownloadBtn"'));
  assert.ok(toolbarHtml.includes('id="bulkDownloadPngsBtn"') && toolbarHtml.includes('id="bulkDownloadZipBtn"'));
  assert.ok(!toolbarHtml.includes("Raw ZIP"));
  process.stdout.write(JSON.stringify({{ ok: true, count }}));
}})().catch((err) => {{ console.error(err); process.exit(1); }});
"""
    res = _run_node_harness(tmp_path, "test_png_seq.cjs", script)
    assert res["ok"] is True


def test_sw_cache_bust_and_workflows_docs() -> None:
    """Verify SW cache version bump, ?v=3.2.5 parity, clean gallery_view.js labels, and updated docs."""
    sw_text = (WEB_DIR / "sw.js").read_text(encoding="utf-8")
    html_text = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    gv_text = (WEB_DIR / "gallery_view.js").read_text(encoding="utf-8")
    wf_text = (PROJECT_ROOT / "docs" / "WORKFLOWS.md").read_text(encoding="utf-8")

    assert 'CACHE_NAME = "agy-nexus-overwatch-v3.2.5-b1"' in sw_text
    for asset in ("gallery_select.js?v=3.2.5", "sheet_builder.js?v=3.2.5", "gallery_view.js?v=3.2.5", "explorer.js?v=3.2.5", "workspace.css?v=3.2.5", "demo_data.js?v=3.2.5"):
        assert asset in sw_text
        assert asset in html_text

    assert "Raw ZIP" not in gv_text
    assert "bulkDownloadPngsBtn" in gv_text
    assert "⬇ PNGs" in gv_text and "⬇ ZIP" in gv_text
    assert "⬇ PNGs (N)" in wf_text and "⬇ ZIP (N)" in wf_text

    lines = Path(__file__).read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 500
    tree = ast.parse("\n".join(lines))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            assert (node.end_lineno - node.lineno + 1) <= 100
