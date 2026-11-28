/* SPDX-License-Identifier: Apache-2.0 */
/* Open Agentic Workbench — Lazy Modal Search (Projects + All OAW, Zero Initial Fetch, Safe DOM) */
(() => {
  const SVG_NS = "http://www.w3.org/2000/svg";
  const FETCH_TIMEOUT_MS = 3000;
  const MAX_RENDERED = 40;
  const PROJECT_SIBLINGS = [
    { url: "https://projects.oaworkbench.org/search-index.json", label: "OAW Projects" },
    { url: "https://projects.oaworkbench.org/quiet-ui-skills/search-index.json", label: "Quiet UI Skills" },
    { url: "https://projects.oaworkbench.org/mcp-adv-netutils/search-index.json", label: "MCP Netutils" },
  ];
  const OAW_PILLARS = [
    { url: "https://oaworkbench.org/search-index.json", label: "OAW Home" },
    { url: "https://learn.oaworkbench.org/search-index.json", label: "OAW Learn" },
    { url: "https://research.oaworkbench.org/search-index.json", label: "OAW Research" },
  ];
  const ALLOWED_ORIGINS = new Set(["https://oaworkbench.org", "https://projects.oaworkbench.org", "https://learn.oaworkbench.org", "https://research.oaworkbench.org"]);

  const manifestCache = new Map();
  const resolvedResults = new Map();
  const state = {
    dialog: null, input: null, clearBtn: null, statusEl: null, resultsEl: null,
    emptyEl: null, emptyMsgEl: null, expandBtn: null, scopeBtns: [],
    scope: "projects", items: [], rendered: [], activeIdx: 0,
    settledScopes: new Set(), loadingScopes: new Set(), bound: false,
  };

  function el(tag, cls, text, attrs) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = String(text);
    if (attrs) for (const [k, v] of Object.entries(attrs)) if (v !== undefined && v !== null) n.setAttribute(k, String(v));
    return n;
  }

  function svgIcon(paths, size = 16) {
    const svg = document.createElementNS(SVG_NS, "svg");
    for (const [k, v] of [["width", size], ["height", size], ["viewBox", "0 0 16 16"], ["fill", "none"], ["aria-hidden", "true"]]) svg.setAttribute(k, String(v));
    for (const [tag, attrs] of paths) {
      const s = document.createElementNS(SVG_NS, tag);
      for (const [k, v] of Object.entries(attrs)) s.setAttribute(k, String(v));
      svg.appendChild(s);
    }
    return svg;
  }

  const reducedMotion = () => typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function isAllowedUrl(u, extraOrigin = "", baseProtocol = "") {
    if (!u || u.username || u.password) return false;
    const p = String(u.protocol || "").toLowerCase(), lp = String(window.location.protocol || "").toLowerCase();
    if (p === "file:") return lp === "file:" && (!baseProtocol || String(baseProtocol).toLowerCase() === "file:") && !u.host;
    if (p !== "https:" && !(p === "http:" && lp === "http:")) return false;
    return u.origin === window.location.origin || (Boolean(extraOrigin) && u.origin === extraOrigin) || ALLOWED_ORIGINS.has(u.origin);
  }

  function parseAllowedUrl(rawInput, baseHref = window.location.href, extraOrigin = "", baseProtocol = "") {
    if (typeof rawInput !== "string" || /[\u0000-\u001f\u007f]/.test(rawInput) || rawInput.includes("\\")) return null;
    const raw = rawInput.trim();
    if (!raw || raw.startsWith("\\\\") || /^\/[/\\]/.test(raw)) return null;
    if (/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(raw) && !/^(?:https?:\/\/|file:\/\/)/i.test(raw)) return null;
    try { const u = new URL(raw, baseHref); return isAllowedUrl(u, extraOrigin, baseProtocol) ? u : null; } catch (_err) { return null; }
  }

  const isSafeNavHref = (href) => Boolean(parseAllowedUrl(href, window.location.href, "", window.location.protocol));

  function resolveItemUrl(rawUrl, manifestUrl) {
    if (typeof rawUrl !== "string" && typeof rawUrl !== "number") return null;
    try {
      const base = new URL(manifestUrl, window.location.href);
      const r = parseAllowedUrl(String(rawUrl), base.href, base.origin !== "null" ? base.origin : "", base.protocol);
      if (!r) return null;
      const href = r.origin === window.location.origin ? `${r.pathname}${r.search}${r.hash}` : r.href;
      return isSafeNavHref(href) ? { href, urlKey: `${r.origin}${r.pathname.replace(/\/index\.html$/i, "/")}${r.search}${r.hash}` } : null;
    } catch (_err) { return null; }
  }

  function getLocalSource() {
    const parsed = parseAllowedUrl(document.getElementById("btnGlobalSearch")?.getAttribute("data-search-index") || "", window.location.href);
    let url = parsed && parsed.origin === window.location.origin ? parsed.href : "./search-index.json";
    if (url === "./search-index.json") { try { url = new URL(url, window.location.href).href; } catch (_err) {} }
    return { url, label: document.querySelector(".oaw-pill-label")?.textContent?.trim() || "Antigravity Nexus", isLocal: true };
  }

  function getScopeSources(scope) {
    const seen = new Set();
    return [getLocalSource(), ...PROJECT_SIBLINGS, ...(scope === "all" ? OAW_PILLARS : [])]
      .filter((src) => src.url && !seen.has(src.url) && seen.add(src.url));
  }

  function normalizeManifest(payload, manifestUrl, meta) {
    const rawList = Array.isArray(payload) ? payload
      : (payload?.items || payload?.entries || payload?.docs || payload?.pages || payload?.sections || payload?.chapters || payload?.results || payload?.records || []);
    if (!Array.isArray(rawList)) return [];
    const rootSrc = (!Array.isArray(payload) && (payload?.projectTitle || payload?.project || payload?.site || payload?.pillar || payload?.title || payload?.name)) || meta.label;
    const items = [];
    for (const e of rawList) {
      if (!e || typeof e !== "object") continue;
      const slugFallback = e.slug ? `#doc-${String(e.slug).replace(/^doc-/, "")}` : "";
      const navRaw = meta.isLocal ? (e.path || e.href || e.url || slugFallback) : (e.url || e.href || e.path || slugFallback);
      const urlInfo = resolveItemUrl(navRaw, manifestUrl);
      const title = String(e.title || e.heading || e.name || e.label || "").trim();
      if (!urlInfo || !title) continue;
      const canonInfo = e.url && meta.isLocal ? resolveItemUrl(e.url, manifestUrl) : null;
      const summary = String(e.summary || e.description || e.excerpt || e.snippet || e.text || "").trim();
      const section = String(e.section || e.group || e.category || e.type || "").trim();
      const source = String(e.project || e.site || e.pillar || e.source || rootSrc || "").trim();
      const kw = Array.isArray(e.keywords) ? e.keywords.join(" ") : (Array.isArray(e.tags) ? e.tags.join(" ") : String(e.keywords || e.tags || ""));
      const body = String(e.plainText || e.body || e.content || "").trim();
      const badge = source && section && source.toLowerCase() !== section.toLowerCase() ? `${source} · ${section}` : (source || section);
      items.push({
        title, summary, badge, href: urlInfo.href, dedupKey: `${(canonInfo || urlInfo).urlKey}::${title.toLowerCase()}`, isLocal: Boolean(meta.isLocal),
        titleLow: title.toLowerCase(), metaLow: `${section} ${source} ${kw}`.toLowerCase(),
        summaryLow: summary.toLowerCase(), bodyLow: body.toLowerCase(),
        haystack: `${title} ${section} ${source} ${kw} ${summary} ${body}`.toLowerCase(),
      });
    }
    return items;
  }

  async function fetchManifest(source) {
    if (manifestCache.has(source.url)) return manifestCache.get(source.url);
    const task = (async () => {
      let timer = null;
      try {
        let signal;
        if (typeof AbortSignal !== "undefined" && typeof AbortSignal.timeout === "function") signal = AbortSignal.timeout(FETCH_TIMEOUT_MS);
        else if (typeof AbortController !== "undefined") {
          const ctrl = new AbortController();
          signal = ctrl.signal;
          timer = setTimeout(() => ctrl.abort(), FETCH_TIMEOUT_MS);
        }
        const res = await fetch(source.url, { signal, headers: { Accept: "application/json" } });
        if (!res.ok) return { ok: false, url: source.url, items: [] };
        return { ok: true, url: source.url, items: normalizeManifest(await res.json(), source.url, source) };
      } catch (_err) {
        return { ok: false, url: source.url, items: [] };
      } finally { if (timer) clearTimeout(timer); }
    })();
    manifestCache.set(source.url, task);
    return task;
  }

  function rebuildScopeItems(scope) {
    const seen = new Set();
    const merged = [];
    for (const src of getScopeSources(scope)) {
      const entry = resolvedResults.get(src.url);
      if (!entry?.items?.length) continue;
      for (const item of entry.items) if (!seen.has(item.dedupKey)) { seen.add(item.dedupKey); merged.push(item); }
    }
    return merged;
  }

  async function loadScope(scope) {
    if (state.settledScopes.has(scope)) { state.items = rebuildScopeItems(scope); renderResults(); return; }
    state.loadingScopes.add(scope);
    renderResults();
    await Promise.allSettled(getScopeSources(scope).map((src) => fetchManifest(src).then((result) => {
      resolvedResults.set(src.url, result);
      if (state.scope === scope && (src.isLocal || (result.ok && result.items.length && !state.items.length))) {
        state.items = rebuildScopeItems(scope);
        renderResults();
      }
      return result;
    })));
    state.loadingScopes.delete(scope);
    state.settledScopes.add(scope);
    if (state.scope === scope) { state.items = rebuildScopeItems(scope); renderResults(); }
  }

  function scoreItems(items, rawQuery) {
    const q = String(rawQuery || "").trim().toLowerCase();
    if (!q) return items.slice();
    const terms = q.split(/\s+/).filter(Boolean);
    const scored = [];
    for (let i = 0; i < items.length; i += 1) {
      const item = items[i];
      if (!terms.every((t) => item.haystack.includes(t))) continue;
      let score = (item.isLocal ? 8 : 0) + (item.titleLow === q ? 120 : item.titleLow.startsWith(q) ? 80 : item.titleLow.includes(q) ? 50 : 0);
      for (const t of terms) {
        if (item.titleLow.includes(t)) score += 24;
        if (item.metaLow.includes(t)) score += 12;
        if (item.summaryLow.includes(t)) score += 6;
        if (item.bodyLow.includes(t)) score += 2;
      }
      scored.push({ item, score, idx: i });
    }
    scored.sort((a, b) => (b.score - a.score) || (a.idx - b.idx));
    return scored.map((entry) => entry.item);
  }

  function syncActiveItem(scrollIntoView = false) {
    if (!state.resultsEl || !state.input) return;
    const links = state.resultsEl.querySelectorAll("a.oaw-search-item");
    if (!links.length) { state.input.setAttribute("aria-expanded", "false"); state.input.removeAttribute("aria-activedescendant"); return; }
    state.activeIdx = ((state.activeIdx % links.length) + links.length) % links.length;
    state.input.setAttribute("aria-expanded", "true");
    links.forEach((link, idx) => link.setAttribute("aria-selected", idx === state.activeIdx ? "true" : "false"));
    const activeLink = links[state.activeIdx];
    if (activeLink) {
      state.input.setAttribute("aria-activedescendant", activeLink.id);
      if (scrollIntoView) activeLink.scrollIntoView({ block: "nearest" });
    }
  }

  function updateStatusText(trimmed, totalMatches, shownCount, loading) {
    const scopePhrase = state.scope === "all" ? "across OAW" : "in Projects";
    if (loading) {
      state.statusEl.setAttribute("aria-live", "off");
      state.statusEl.textContent = state.scope === "all" ? "Loading OAW indexes..." : "Loading Projects index...";
      return;
    }
    state.statusEl.setAttribute("aria-live", "polite");
    if (!state.items.length && state.settledScopes.has(state.scope)) { state.statusEl.textContent = `0 matches ${scopePhrase} (index unavailable)`; return; }
    const baseTotal = trimmed ? totalMatches : state.items.length;
    const noun = trimmed ? (baseTotal === 1 ? "match" : "matches") : (baseTotal === 1 ? "entry" : "entries");
    state.statusEl.textContent = shownCount < baseTotal ? `Showing ${shownCount} of ${baseTotal} ${noun} ${scopePhrase}` : `${baseTotal} ${noun} ${scopePhrase}`;
  }

  function renderResults() {
    if (!state.dialog || !state.resultsEl || !state.statusEl || !state.emptyEl) return;
    const prevKey = state.rendered[state.activeIdx]?.dedupKey || "";
    const trimmed = (state.input?.value || "").trim();
    const matches = scoreItems(state.items, trimmed);
    const visible = matches.slice(0, MAX_RENDERED);
    const loading = state.loadingScopes.has(state.scope) && !state.items.length;
    const keptIdx = prevKey ? visible.findIndex((item) => item.dedupKey === prevKey) : -1;
    state.rendered = visible;
    state.activeIdx = keptIdx >= 0 ? keptIdx : 0;

    const frag = document.createDocumentFragment();
    visible.forEach((item, idx) => {
      const li = el("li", null, null, { role: "none" });
      const link = el("a", "oaw-search-item", null, { id: `oawSearchOpt-${idx}`, role: "option", href: item.href, "aria-selected": idx === state.activeIdx ? "true" : "false" });
      const top = el("div", "oaw-search-item-top");
      top.appendChild(el("span", "oaw-search-item-title", item.title));
      if (item.badge) top.appendChild(el("span", "oaw-search-item-badge", item.badge));
      link.appendChild(top);
      if (item.summary) link.appendChild(el("span", "oaw-search-item-sub", item.summary));
      li.appendChild(link);
      frag.appendChild(li);
    });

    state.resultsEl.replaceChildren(frag);
    const hasResults = visible.length > 0;
    state.resultsEl.hidden = !hasResults;
    state.emptyEl.hidden = hasResults || loading;
    updateStatusText(trimmed, matches.length, visible.length, loading);
    if (!hasResults && !loading && state.emptyMsgEl) {
      const scopePhrase = state.scope === "all" ? "across OAW" : "in Projects";
      state.emptyMsgEl.textContent = !state.items.length ? `Search index unavailable ${scopePhrase}.`
        : (trimmed ? `No results matched "${trimmed}" ${scopePhrase}.` : `No entries available ${scopePhrase}.`);
      if (state.expandBtn) state.expandBtn.hidden = state.scope === "all" || !trimmed;
    }
    syncActiveItem(false);
  }

  function setScope(nextScope) {
    const scope = nextScope === "all" ? "all" : "projects";
    state.scope = scope;
    state.scopeBtns.forEach((btn) => {
      const active = btn.getAttribute("data-search-scope") === scope;
      btn.setAttribute("aria-pressed", String(active));
      btn.classList.toggle("is-active", active);
    });
    state.items = rebuildScopeItems(scope);
    loadScope(scope);
  }

  function syncTriggerState(isOpen) {
    const trigger = document.getElementById("btnGlobalSearch");
    if (trigger?.hasAttribute("aria-expanded")) trigger.setAttribute("aria-expanded", String(Boolean(isOpen)));
  }

  function navigateToHref(href) {
    if (!isSafeNavHref(href)) return;
    let targetUrl;
    try { targetUrl = new URL(href, window.location.href); } catch (_err) { return; }
    const norm = (p) => p.replace(/\/index\.html$/i, "/");
    const samePageHash = targetUrl.origin === window.location.origin && norm(targetUrl.pathname) === norm(window.location.pathname)
      && targetUrl.search === window.location.search && Boolean(targetUrl.hash);
    close();
    if (!samePageHash) { window.location.assign(targetUrl.href); return; }
    const hash = targetUrl.hash;
    let id = hash.slice(1);
    try { id = decodeURIComponent(id); } catch (_err) {}
    requestAnimationFrame(() => {
      if (window.location.hash !== hash) { try { window.location.hash = hash; } catch (_e) { history.replaceState(null, "", hash); } }
      const targetEl = id ? document.getElementById(id) : null;
      if (targetEl) {
        targetEl.scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", block: "start" });
        if (!targetEl.hasAttribute("tabindex")) targetEl.setAttribute("tabindex", "-1");
        targetEl.focus({ preventScroll: true });
      }
    });
  }

  function attachLightDismissFallback(dialog) {
    if (typeof HTMLDialogElement !== "undefined" && "closedBy" in HTMLDialogElement.prototype) return;
    const outsideRect = (ev) => { const r = dialog.getBoundingClientRect(); return ev.clientX < r.left || ev.clientX > r.right || ev.clientY < r.top || ev.clientY > r.bottom; };
    let pressedOut = false, sawPointer = false;
    dialog.addEventListener("pointerdown", (ev) => { sawPointer = true; pressedOut = outsideRect(ev); });
    dialog.addEventListener("pointerup", (ev) => {
      if (pressedOut && outsideRect(ev)) close();
      pressedOut = false;
      requestAnimationFrame(() => { sawPointer = false; });
    });
    dialog.addEventListener("pointercancel", () => { pressedOut = false; sawPointer = false; });
    dialog.addEventListener("click", (ev) => { if (!sawPointer && ev.target === dialog && outsideRect(ev)) close(); });
  }

  function bindDialogEvents(dialog) {
    dialog.addEventListener("close", () => { if ("returnValue" in dialog) dialog.returnValue = ""; syncTriggerState(false); });
    attachLightDismissFallback(dialog);
    state.clearBtn.addEventListener("click", () => { state.input.value = ""; state.activeIdx = 0; state.clearBtn.setAttribute("data-empty", "true"); renderResults(); state.input.focus(); });
    state.dialog.querySelector(".oaw-search-close").addEventListener("click", close);
    state.scopeBtns.forEach((btn) => btn.addEventListener("click", () => { setScope(btn.getAttribute("data-search-scope")); state.input.focus(); }));
    state.expandBtn.addEventListener("click", () => { setScope("all"); state.input.focus(); });
    state.input.addEventListener("input", () => { state.activeIdx = 0; state.clearBtn.setAttribute("data-empty", state.input.value ? "false" : "true"); renderResults(); });
    state.input.addEventListener("keydown", (ev) => {
      if (ev.isComposing || !state.rendered.length) return;
      if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
        ev.preventDefault(); state.activeIdx += ev.key === "ArrowDown" ? 1 : -1; syncActiveItem(true);
      } else if (ev.key === "Enter" && state.rendered[state.activeIdx]) {
        ev.preventDefault(); navigateToHref(state.rendered[state.activeIdx].href);
      }
    });
    state.resultsEl.addEventListener("focusin", (ev) => {
      const link = ev.target instanceof Element ? ev.target.closest("a.oaw-search-item") : null;
      const idx = link ? Array.prototype.indexOf.call(state.resultsEl.querySelectorAll("a.oaw-search-item"), link) : -1;
      if (idx >= 0) { state.activeIdx = idx; syncActiveItem(false); }
    });
    state.resultsEl.addEventListener("click", (ev) => {
      const link = (ev.target instanceof Element ? ev.target : ev.target?.parentElement)?.closest("a.oaw-search-item");
      if (!link) return;
      const href = link.getAttribute("href") || "";
      if (!isSafeNavHref(href)) { ev.preventDefault(); return; }
      if (ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey || ev.button !== 0) { close(); return; }
      ev.preventDefault(); navigateToHref(href);
    });
  }

  function ensureDialog() {
    if (state.dialog) return state.dialog;
    const dialog = el("dialog", "oaw-search-dialog", null, { id: "oawSearchDialog", closedby: "any", "aria-labelledby": "oawSearchTitle" });
    const title = el("h2", "sr-only", "Search Open Agentic Workbench", { id: "oawSearchTitle" });
    const panel = el("div", "oaw-search-panel");
    const header = el("search", "oaw-search-header", null, { "aria-label": "Search Open Agentic Workbench" });
    const icon = el("span", "oaw-search-icon", null, { "aria-hidden": "true" });
    icon.appendChild(svgIcon([["circle", { cx: "7", cy: "7", r: "4.8", stroke: "currentColor", "stroke-width": "1.6" }], ["path", { d: "M10.8 10.8 14 14", stroke: "currentColor", "stroke-width": "1.7", "stroke-linecap": "round" }]]));
    const label = el("label", "sr-only", "Search Open Agentic Workbench", { for: "oawSearchInput" });
    const input = el("input", "oaw-search-input", null, { id: "oawSearchInput", type: "search", autofocus: "", autocomplete: "off", spellcheck: "false", placeholder: "Search OAW & docs...", role: "combobox", "aria-autocomplete": "list", "aria-expanded": "false", "aria-controls": "oawSearchResults" });
    const clearBtn = el("button", "oaw-search-clear", "Clear", { type: "button", id: "oawSearchClearBtn", "aria-label": "Clear search query", "data-empty": "true" });
    const closeBtn = el("button", "oaw-search-close", null, { type: "button", id: "oawSearchCloseBtn", "aria-label": "Close search" });
    closeBtn.appendChild(svgIcon([["path", { d: "M4 4l8 8M12 4l-8 8", stroke: "currentColor", "stroke-width": "1.7", "stroke-linecap": "round" }]]));
    header.append(icon, label, input, clearBtn, closeBtn);
    const toolbar = el("div", "oaw-search-toolbar");
    const scopes = el("div", "oaw-search-scopes", null, { role: "group", "aria-label": "Search scope" });
    const projBtn = el("button", "oaw-scope-btn is-active", "Projects", { type: "button", "data-search-scope": "projects", "aria-pressed": "true" });
    const allBtn = el("button", "oaw-scope-btn", "All OAW", { type: "button", "data-search-scope": "all", "aria-pressed": "false" });
    scopes.append(projBtn, allBtn);
    const statusEl = el("span", "oaw-search-status", "", { id: "oawSearchStatus", role: "status", "aria-live": "off" });
    toolbar.append(scopes, statusEl);
    const body = el("div", "oaw-search-body");
    const resultsEl = el("ul", "oaw-search-results", null, { id: "oawSearchResults", role: "listbox", "aria-label": "Search results" });
    const emptyEl = el("div", "oaw-search-empty", null, { id: "oawSearchEmpty", hidden: "" });
    const emptyMsgEl = el("p", "oaw-search-empty-msg", "", { id: "oawSearchEmptyMsg" });
    const expandBtn = el("button", "oaw-search-empty-btn", "Search All OAW", { type: "button", id: "oawSearchExpandScopeBtn", hidden: "" });
    emptyEl.append(emptyMsgEl, expandBtn);
    body.append(resultsEl, emptyEl);
    const footer = el("div", "oaw-search-footer");
    for (const [keys, desc] of [[["↑", "↓"], "navigate"], [["Enter"], "open"], [["Esc"], "close"]]) {
      const hint = el("span", "oaw-search-hint");
      for (const k of keys) hint.appendChild(el("kbd", null, k));
      hint.appendChild(document.createTextNode(` ${desc}`));
      footer.appendChild(hint);
    }
    panel.append(header, toolbar, body, footer);
    dialog.append(title, panel);
    document.body.appendChild(dialog);
    Object.assign(state, { dialog, input, clearBtn, statusEl, resultsEl, emptyEl, emptyMsgEl, expandBtn, scopeBtns: [projBtn, allBtn] });
    bindDialogEvents(dialog);
    return dialog;
  }

  function open(opts = {}) {
    const dialog = ensureDialog();
    try { document.querySelectorAll("[popover]:popover-open").forEach((p) => { try { p.hidePopover(); } catch (_err) {} }); } catch (_err) {}
    if (opts && (opts.scope === "all" || opts.scope === "projects")) state.scope = opts.scope;
    if (!(dialog.open || dialog.hasAttribute("open"))) {
      if (typeof dialog.showModal === "function") { try { dialog.showModal(); } catch (_err) { dialog.setAttribute("open", ""); } }
      else dialog.setAttribute("open", "");
      syncTriggerState(true);
    }
    if (typeof opts?.query === "string") { state.input.value = opts.query; state.activeIdx = 0; }
    state.clearBtn.setAttribute("data-empty", state.input.value ? "false" : "true");
    setScope(state.scope);
    requestAnimationFrame(() => { state.input?.focus(); if (state.input?.value) state.input.select(); });
  }

  function close() {
    const dialog = state.dialog;
    if (!dialog) return;
    if (dialog.open || dialog.hasAttribute("open")) {
      if (typeof dialog.close === "function") { try { dialog.close(); } catch (_err) { dialog.removeAttribute("open"); } }
      if (dialog.open || dialog.hasAttribute("open")) dialog.removeAttribute("open");
    }
    if ("returnValue" in dialog) dialog.returnValue = "";
    syncTriggerState(false);
  }

  const isSlashBlocked = (n) => {
    if (!(n instanceof Element)) return false;
    if (n.isContentEditable || n.closest("input, textarea, select, dialog[open]")) return true;
    const ce = n.closest("[contenteditable]");
    return Boolean(ce && ce.getAttribute("contenteditable") !== "false");
  };

  function init() {
    if (state.bound) return;
    state.bound = true;
    document.addEventListener("click", (ev) => {
      if (ev.defaultPrevented) return;
      if ((ev.target instanceof Element ? ev.target : ev.target?.parentElement)?.closest("#btnGlobalSearch")) { ev.preventDefault(); open(); }
    });
    document.addEventListener("keydown", (ev) => {
      if (ev.defaultPrevented || ev.isComposing) return;
      if ((ev.ctrlKey || ev.metaKey) && !ev.altKey && !ev.shiftKey && String(ev.key || "").toLowerCase() === "k") {
        if (state.dialog && (state.dialog.open || state.dialog.hasAttribute("open"))) { ev.preventDefault(); close(); return; }
        if (!document.querySelector("dialog[open]")) { ev.preventDefault(); open(); }
        return;
      }
      if (ev.key === "/" && !ev.ctrlKey && !ev.metaKey && !ev.altKey) {
        if (!document.querySelector("dialog[open]") && !isSlashBlocked(document.activeElement) && !isSlashBlocked(ev.target)) { ev.preventDefault(); open(); }
      }
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();

  window.AgyOawSearch = { open, close };
})();
