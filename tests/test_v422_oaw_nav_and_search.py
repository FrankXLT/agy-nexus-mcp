"""tests/test_v422_oaw_nav_and_search.py — Unified OAW Nav, Search Index & Lazy Modal Suite."""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
SITE_DIR = REPO_ROOT / "web" / "site"


def _load_script_mod(name: str):
    path = SCRIPTS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_v422_search_index_coverage_and_privacy_gate(tmp_path: Path, monkeypatch) -> None:
    """Verify build_showcase() emits complete search-index.json with 0 leaks while catching synthetic leaks."""
    bgs = _load_script_mod("build_github_showcase")
    out_dir = tmp_path / "gh-pages"
    res = bgs.build_showcase(out_dir, refresh=False)
    assert res["ok"] is True and res["privacy_findings"] == 0
    assert bgs.scan_showcase_privacy(out_dir) == []

    idx_path = out_dir / "search-index.json"
    assert idx_path.is_file(), "Missing search-index.json in built showcase"
    payload = json.loads(idx_path.read_text(encoding="utf-8"))
    assert payload["version"] == "1"
    assert payload["project"] == "agy-nexus-mcp"
    assert payload["projectTitle"] == "Antigravity Nexus"
    assert payload["mcpPackage"] == bgs.__version__

    items = payload["items"]
    assert isinstance(items, list) and len(items) >= 20
    by_id = {item["id"]: item for item in items}

    overview_items = [item for item in items if item["section"] == "Overview"]
    assert len(overview_items) >= 4
    assert all(item["path"].startswith("./") for item in overview_items)

    demo_items = [item for item in items if item["section"] == "Demo"]
    assert {item["id"] for item in demo_items} >= {"demo-analytics", "demo-workspace", "demo-heatmap", "demo-hierarchy"}
    assert "Analytics" in by_id["demo-analytics"]["title"] and by_id["demo-analytics"]["path"] == "./demo/"
    assert "Workspace" in by_id["demo-workspace"]["title"] and by_id["demo-workspace"]["path"] == "./demo/#workspace"

    docs_raw = (out_dir / "docs" / "docs_data.js").read_text(encoding="utf-8")
    docs_data = json.loads(docs_raw.split("window.AGY_DOCS_DATA = ", 1)[1].rstrip(";\n"))
    chapters = docs_data["chapters"]
    assert len(chapters) == 10
    sub_heading_re = re.compile(r'<h([2-4])\s+id="([^"]+)">([\s\S]*?)</h\1>')
    for ch in chapters:
        ch_entry = by_id.get(f"docs-{ch['id']}")
        assert ch_entry and ch_entry["section"] == "Docs" and ch_entry["path"] == f"./docs/#{ch['id']}"
        for _lvl, sub_id, _raw_title in sub_heading_re.findall(ch.get("html") or ""):
            sub_entry = by_id.get(f"docs-{sub_id}")
            assert sub_entry and sub_entry["section"] == "Docs" and sub_entry["path"] == f"./docs/#{sub_id}"
    assert "docs-two-doorway-isolation-passphrase-deadbolt" in by_id
    assert "docs-dual-pool-quota-model-routing-check" in by_id

    fake_home = tmp_path / "devon"
    sec_dir = fake_home / ".config" / "ag-bridge-mcp"
    sec_dir.mkdir(parents=True)
    (sec_dir / "secrets.env").write_text("BRIDGE_SECRET=SyntheticSecretToken9876\n", encoding="utf-8")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    bad_dir = tmp_path / "bad_privacy"
    bad_dir.mkdir()
    (bad_dir / "search-index.json").write_text(
        json.dumps({"url": "https://internal.oaworkbench.org/admin", "note": "SyntheticSecretToken9876"}),
        encoding="utf-8",
    )
    findings = bgs.scan_showcase_privacy(bad_dir)
    assert any("hashed private identifier" in f for f in findings)
    assert any("banned host/secret literal" in f for f in findings)

    lan_pat = re.compile(r"\b[a-z0-9-]+\.lan\b", re.IGNORECASE)
    ip_pat = re.compile(r"\b(?:192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)\b")
    extra_lits = bgs._load_extra_banned_literals()
    for idx, sample in enumerate(
        ("https://oaworkbench.org.lan/", "https://internal.projects.oaworkbench.org/", "/home/devon/secret.env")
    ):
        fp = bad_dir / f"leak_{idx}.json"
        fp.write_text(json.dumps({"leak": sample}), encoding="utf-8")
        assert bgs._scan_text_file_privacy(fp, fp.name, extra_lits, set(), lan_pat, ip_pat), (
            f"_scan_text_file_privacy failed to flag {sample}"
        )


def test_v422_nav_and_search_css_js_hygiene() -> None:
    """Verify oaw_topbar.css, docs.css, oaw_search.css, and oaw_search.js line budgets and accessibility hygiene."""
    topbar_css = (SITE_DIR / "oaw_topbar.css").read_text(encoding="utf-8")
    assert len(topbar_css.splitlines()) <= 500
    assert "!important" not in topbar_css
    assert "@layer shell" in topbar_css
    assert "@layer tokens, reset, base, layout, components;" not in topbar_css
    assert "@media (max-width: 899px)" in topbar_css and "@media (min-width: 900px)" in topbar_css
    assert "#btnViewSwitcher { display: none; }" in topbar_css
    assert "@media (min-width: 960px)" in topbar_css
    assert ".oaw-search-kbd { display: none; }" in topbar_css
    assert ".oaw-search-trigger { inline-size: auto;" in topbar_css

    docs_css = (SITE_DIR / "docs.css").read_text(encoding="utf-8")
    assert len(docs_css.splitlines()) <= 500
    assert "!important" not in docs_css
    assert ".docs-mobile-subbar {" in docs_css and "block-size: 38px;" in docs_css
    assert "@media (min-width: 960px)" in docs_css
    assert ".docs-rail {" in docs_css and ".docs-mobile-subbar { display: none; }" in docs_css

    search_css = (SITE_DIR / "oaw_search.css").read_text(encoding="utf-8")
    assert len(search_css.splitlines()) <= 400
    assert "!important" not in search_css
    assert "dialog.oaw-search-dialog:modal { overscroll-behavior: contain; }" in search_css
    backdrop_block = search_css.split("dialog.oaw-search-dialog::backdrop", 1)[1].split("}", 1)[0]
    assert "overscroll-behavior: contain;" in backdrop_block

    search_js = (SITE_DIR / "oaw_search.js").read_text(encoding="utf-8")
    assert len(search_js.splitlines()) <= 450
    assert "innerHTML" not in search_js
    assert "aria-modal" not in search_js
    assert not re.search(r'role["\']?\s*[:=]\s*["\']dialog["\']', search_js)


_VM_DOM_SHIM = r"""const assert = require("assert"), fs = require("fs"), vm = require("vm");
function matchOne(el, sel) {
  for (const part of sel.split(",").map((s) => s.trim()).filter(Boolean)) {
    let rem = part, ok = true, m;
    const tm = rem.match(/^([a-zA-Z0-9*]+)/);
    if (tm) { if (tm[1] !== "*" && el.tagName !== tm[1].toUpperCase()) ok = false; rem = rem.slice(tm[0].length); }
    while (ok && rem) {
      if (rem[0] === "." && (m = rem.match(/^\.([\w-]+)/))) { ok = el.classList.contains(m[1]); rem = rem.slice(m[0].length); }
      else if (rem[0] === "#" && (m = rem.match(/^#([\w-]+)/))) { ok = el.id === m[1]; rem = rem.slice(m[0].length); }
      else if (rem[0] === "[" && (m = rem.match(/^\[([^=\]^]+)(?:(\^?=)"([^"]*)")?\]/))) {
        const v = el.getAttribute(m[1]);
        ok = m[2] === "=" ? v === m[3] : m[2] === "^=" ? (typeof v === "string" && v.startsWith(m[3])) : v !== null;
        rem = rem.slice(m[0].length);
      } else { ok = false; break; }
    }
    if (ok) return true;
  }
  return false;
}
class Element {
  constructor(tag) {
    this.tagName = String(tag || "DIV").toUpperCase(); this.children = []; this.parentNode = null;
    this._attrs = new Map(); this.dataset = {}; this._text = ""; this.value = "";
    this.hidden = false; this.open = false; this.isContentEditable = false; this._ev = new Map();
    this.classList = {
      add: (...cs) => { const s = new Set(this.className.split(/\s+/).filter(Boolean)); cs.forEach((c) => s.add(c)); this.className = [...s].join(" "); },
      remove: (...cs) => { const s = new Set(this.className.split(/\s+/).filter(Boolean)); cs.forEach((c) => s.delete(c)); this.className = [...s].join(" "); },
      toggle: (c, f) => { const on = f === undefined ? !this.classList.contains(c) : Boolean(f); on ? this.classList.add(c) : this.classList.remove(c); return on; },
      contains: (c) => this.className.split(/\s+/).filter(Boolean).includes(c),
    };
  }
  get id() { return this._attrs.get("id") || ""; } set id(v) { this.setAttribute("id", v); }
  get className() { return this._attrs.get("class") || ""; } set className(v) { this.setAttribute("class", v); }
  get parentElement() { return this.parentNode && this.parentNode.tagName !== "#FRAG" ? this.parentNode : null; }
  get textContent() { return this.children.length ? this.children.map((c) => c.textContent).join("") : this._text; } set textContent(v) { this.children = []; this._text = String(v ?? ""); }
  setAttribute(k, v) { const key = String(k); this._attrs.set(key, String(v)); if (key === "hidden") this.hidden = true; } getAttribute(k) { return this._attrs.has(String(k)) ? this._attrs.get(String(k)) : null; }
  hasAttribute(k) { return this._attrs.has(String(k)); } removeAttribute(k) { this._attrs.delete(String(k)); if (k === "hidden") this.hidden = false; }
  appendChild(n) { if (!n) return n; if (n.tagName === "#FRAG") { n.children.slice().forEach((c) => this.appendChild(c)); return n; } n.parentNode = this; this.children.push(n); return n; }
  append(...ns) { ns.forEach((n) => this.appendChild(typeof n === "string" ? Object.assign(new Element("#TEXT"), { _text: n }) : n)); } replaceChildren(...ns) { this.children = []; this.append(...ns); }
  closest(s) { for (let c = this; c && c.tagName !== "#FRAG"; c = c.parentNode) if (matchOne(c, s)) return c; return null; }
  querySelectorAll(s) { const out = []; const w = (n) => { for (const c of n.children) if (c.tagName !== "#TEXT") { if (matchOne(c, s)) out.push(c); w(c); } }; w(this); return out; }
  querySelector(s) { return this.querySelectorAll(s)[0] || null; } addEventListener(t, fn) { if (!this._ev.has(t)) this._ev.set(t, []); this._ev.get(t).push(fn); }
  dispatchEvent(ev) { const e = Object.assign({ defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } }, ev); if (!e.target) e.target = this; (this._ev.get(e.type) || []).forEach((fn) => fn(e)); return e; }
  focus() { doc.activeElement = this; } select() {} scrollIntoView() {}
}
const root = new Element("BODY"), docEv = new Map(), fetchCalls = [], localIndex = JSON.parse(fs.readFileSync(process.argv[2], "utf-8"));
const searchBtn = Object.assign(new Element("BUTTON"), { id: "btnGlobalSearch" }), pageBtn = Object.assign(new Element("BUTTON"), { id: "pageActionBtn" }), dummyInput = Object.assign(new Element("INPUT"), { id: "dummyInput" });
searchBtn.setAttribute("data-search-index", "./search-index.json"); searchBtn.setAttribute("aria-expanded", "false"); root.append(searchBtn, pageBtn, dummyInput);
const doc = {
  readyState: "complete", body: root, activeElement: root,
  getElementById: (id) => root.querySelector(`#${id}`), querySelector: (s) => root.querySelector(s), querySelectorAll: (s) => root.querySelectorAll(s),
  createElementNS: (_ns, tag) => new Element(tag), createDocumentFragment: () => new Element("#FRAG"), createTextNode: (t) => Object.assign(new Element("#TEXT"), { _text: String(t) }),
  addEventListener: (t, fn) => { if (!docEv.has(t)) docEv.set(t, []); docEv.get(t).push(fn); },
  createElement: (tag) => {
    const el = new Element(tag);
    if (String(tag).toLowerCase() === "dialog") {
      el.returnValue = ""; el.showModal = () => { el.open = true; el.setAttribute("open", ""); };
      el.close = (rv) => { if (rv !== undefined) el.returnValue = String(rv); el.open = false; el.removeAttribute("open"); el.dispatchEvent({ type: "close" }); };
    }
    return el;
  },
};
const fireDocKey = (opts) => { const ev = { defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }, target: doc.activeElement, ...opts }; (docEv.get("keydown") || []).forEach((fn) => fn(ev)); return ev; };
const loc = { href: "https://projects.oaworkbench.org/agy-nexus-mcp/", origin: "https://projects.oaworkbench.org", protocol: "https:", pathname: "/agy-nexus-mcp/", search: "", hash: "", assign: (u) => { loc.href = u; } };
const ctx = {
  window: { location: loc, history: { replaceState: () => {} }, matchMedia: () => ({ matches: false }) },
  location: loc, document: doc, Element, URL, requestAnimationFrame: (fn) => fn(), setTimeout: () => 1, clearTimeout: () => {},
  fetch: (url) => {
    fetchCalls.push(url);
    if (url === "https://projects.oaworkbench.org/agy-nexus-mcp/search-index.json") return Promise.resolve({ ok: true, json: async () => localIndex });
    if (url === "https://oaworkbench.org/search-index.json") return Promise.resolve({ ok: true, json: async () => ({ projectTitle: "OAW Home", items: [
      { title: "OAW Portal Home", summary: "Main hub", url: "https://oaworkbench.org/", section: "Home" }, { title: "Bad Backslash Host", summary: "Evil", url: "/\\evil.com", section: "Bad" },
      { title: "Bad Phish Host", summary: "Evil", url: "https://evil.example/phish", section: "Bad" }, { title: "Malformed Hash Edge", summary: "Hash test", url: "https://projects.oaworkbench.org/agy-nexus-mcp/#%ZZ", section: "Edge" },
    ] }) });
    return Promise.reject(new Error("Simulated offline sibling"));
  },
};
ctx.window.document = doc; vm.runInNewContext(fs.readFileSync(process.argv[3], "utf-8"), ctx);
"""


def _write_oaw_search_vm_probe(probe_path: Path) -> None:
    """Write a Node VM harness exercising lazy fetch, shortcuts, dedup retention, href safety, and dialog close."""
    probe_body = r"""(async () => {
  assert.strictEqual(fetchCalls.length, 0, "Zero fetch() calls allowed before opening modal");
  dummyInput.focus(); fireDocKey({ key: "/" });
  assert.strictEqual(doc.getElementById("oawSearchDialog"), null, "/ must be ignored inside <input>");
  assert.strictEqual(fetchCalls.length, 0);

  pageBtn.focus(); fireDocKey({ key: "/" });
  const dialog = doc.getElementById("oawSearchDialog");
  assert(dialog && dialog.open === true, "/ should open search dialog even when focus is on a page <button>");
  assert.strictEqual(searchBtn.getAttribute("aria-expanded"), "true");
  await new Promise((r) => setImmediate(r));
  assert(fetchCalls.includes("https://projects.oaworkbench.org/agy-nexus-mcp/search-index.json"));
  assert(!fetchCalls.some((u) => u.startsWith("https://oaworkbench.org/") || u.startsWith("https://learn.oaworkbench.org/") || u.startsWith("https://research.oaworkbench.org/")));

  const resultsEl = doc.getElementById("oawSearchResults"), links = resultsEl.querySelectorAll("a.oaw-search-item");
  assert(links.length >= 10 && links[0].getAttribute("aria-selected") === "true" && links[1].getAttribute("aria-selected") === "false");
  const input = doc.getElementById("oawSearchInput");
  input.dispatchEvent({ type: "keydown", key: "ArrowDown" });
  assert.strictEqual(links[0].getAttribute("aria-selected"), "false");
  assert.strictEqual(links[1].getAttribute("aria-selected"), "true");

  for (const expected of [
    ...localIndex.items.filter((i) => i.section === "Overview" && i.path === "./"),
    ...localIndex.items.filter((i) => i.section === "Demo" && i.path === "./demo/"),
  ]) {
    input.value = expected.title; input.dispatchEvent({ type: "input" });
    assert(resultsEl.textContent.includes(expected.title), `Dropped distinct item sharing ${expected.path}: ${expected.title}`);
  }
  input.value = ""; input.dispatchEvent({ type: "input" });

  dialog.close("stale-return");
  assert.strictEqual(dialog.open, false);
  assert.strictEqual(dialog.returnValue, "", "close event must reset dialog.returnValue");
  assert.strictEqual(searchBtn.getAttribute("aria-expanded"), "false");

  fireDocKey({ key: "k", ctrlKey: true }); assert.strictEqual(dialog.open, true, "Ctrl+K should open search dialog");
  fireDocKey({ key: "k", ctrlKey: true }); assert.strictEqual(dialog.open, false, "Ctrl+K while open should close dialog");
  fireDocKey({ key: "k", ctrlKey: true }); assert.strictEqual(dialog.open, true);

  const allBtn = dialog.querySelector('[data-search-scope="all"]');
  allBtn.dispatchEvent({ type: "click" });
  await new Promise((r) => setImmediate(r));
  assert.strictEqual(allBtn.getAttribute("aria-pressed"), "true");
  for (const u of ["https://oaworkbench.org/search-index.json", "https://learn.oaworkbench.org/search-index.json", "https://research.oaworkbench.org/search-index.json"]) {
    assert(fetchCalls.includes(u), `Missing lazy All OAW fetch: ${u}`);
  }
  input.value = "Portal"; input.dispatchEvent({ type: "input" });
  assert(resultsEl.textContent.includes("OAW Portal Home"), "Resolved pillar manifest item should render despite sibling rejections");

  for (const badQuery of ["Bad Backslash Host", "Bad Phish Host"]) {
    input.value = badQuery; input.dispatchEvent({ type: "input" });
    assert.strictEqual(resultsEl.querySelectorAll("a.oaw-search-item").length, 0, `Unsafe href must be dropped: ${badQuery}`);
  }
  for (const badHref of ["/\\evil.com", "https://evil.example/phish"]) {
    const badLink = new Element("A"); badLink.className = "oaw-search-item"; badLink.setAttribute("href", badHref);
    resultsEl.appendChild(badLink);
    const ev = resultsEl.dispatchEvent({ type: "click", button: 0, target: badLink });
    assert.strictEqual(ev.defaultPrevented, true, `Click must preventDefault unsafe href: ${badHref}`);
    assert.strictEqual(loc.href, "https://projects.oaworkbench.org/agy-nexus-mcp/");
  }

  input.value = "Malformed Hash Edge"; input.dispatchEvent({ type: "input" });
  assert(resultsEl.textContent.includes("Malformed Hash Edge"));
  input.dispatchEvent({ type: "keydown", key: "Enter" });
  assert.strictEqual(dialog.open, false, "Malformed #%ZZ hash navigation must close cleanly without throwing");
  console.log("OAW_SEARCH_VM_OK");
})().catch((err) => { console.error(err); process.exit(1); });
"""
    probe_path.write_text(_VM_DOM_SHIM + probe_body, encoding="utf-8")


def test_v422_oaw_search_modal_node_vm(tmp_path: Path) -> None:
    """Verify web/site/oaw_search.js lazy fetch, Ctrl+K / /, All OAW graceful errors, ArrowDown, and returnValue reset."""
    bgs = _load_script_mod("build_github_showcase")
    out_dir = tmp_path / "gh-pages"
    bgs.build_showcase(out_dir, refresh=False)

    probe_path = tmp_path / "oaw_search_vm_probe.cjs"
    _write_oaw_search_vm_probe(probe_path)
    proc = subprocess.run(
        ["node", str(probe_path), str(out_dir / "search-index.json"), str(SITE_DIR / "oaw_search.js")],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"{proc.stdout}\n{proc.stderr}"
    assert "OAW_SEARCH_VM_OK" in proc.stdout
