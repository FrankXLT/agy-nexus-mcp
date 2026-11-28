/* SPDX-License-Identifier: Apache-2.0 */
/* AGY-Nexus Public Docs — Shared Outline Rail, Mobile Sheet, Search & Copy Controls */
(() => {
  const QUICK_JUMPS = [
    ["quickstart", "Quickstart"],
    ["common-terms", "Common Terms"],
    ["architecture", "Architecture"],
    ["how-it-is-built", "How It Is Built"],
  ];
  const RAIL_QUICK_JUMPS = [
    ...QUICK_JUMPS.map(([slug, label]) => ({ label, href: `#doc-${slug}`, jumpId: `doc-${slug}`, slug })),
    { label: "Live Studio Demo", href: "../demo/", jumpId: "", slug: "" },
  ];
  const SVG_NS = "http://www.w3.org/2000/svg";
  const byId = (id) => document.getElementById(id);
  const reducedMotionMql = typeof window.matchMedia === "function" ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
  const desktopMql = typeof window.matchMedia === "function" ? window.matchMedia("(min-width: 960px)") : null;
  const copyTimers = new WeakMap();
  let lastCopyMsg = "";

  function mk(tag, cls, text, attrs) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = String(text);
    if (attrs) for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    return node;
  }

  function makeSvgIcon(cls, shapes) {
    const svg = document.createElementNS(SVG_NS, "svg");
    const attrs = { class: cls, viewBox: "0 0 24 24", width: "16", height: "16", fill: "none", stroke: "currentColor", "stroke-width": "2", "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" };
    for (const [k, v] of Object.entries(attrs)) svg.setAttribute(k, v);
    for (const [tag, sAttrs] of shapes) {
      const node = document.createElementNS(SVG_NS, tag);
      for (const [k, v] of Object.entries(sAttrs)) node.setAttribute(k, v);
      svg.appendChild(node);
    }
    return svg;
  }

  function isEditableElement(el) {
    if (!el || el === document.body || el === document.documentElement) return false;
    if (el.isContentEditable || el.getAttribute?.("contenteditable") === "true" || el.getAttribute?.("contenteditable") === "") return true;
    const tag = String(el.tagName || "").toUpperCase();
    return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
  }

  function sanitizeFragment(htmlStr) {
    const URL_ATTRS = new Set(["href", "xlink:href", "src", "formaction", "action", "data", "poster"]);
    const tpl = document.createElement("template");
    tpl.innerHTML = String(htmlStr || "");
    for (const bad of tpl.content.querySelectorAll("script, iframe, object, embed, style, link, foreignObject, animate, set, use, base, meta, form")) bad.remove();
    const walker = document.createTreeWalker(tpl.content, NodeFilter.SHOW_ELEMENT);
    for (let el; (el = walker.nextNode()); ) {
      for (const attr of Array.from(el.attributes)) {
        const name = attr.name.toLowerCase();
        const cleanVal = attr.value.replace(/[\u0000-\u0020\u007f]+/g, "");
        if (name.startsWith("on") || name === "srcdoc" || (URL_ATTRS.has(name) && /^(?:javascript|vbscript|data):/i.test(cleanVal))) {
          el.removeAttribute(attr.name);
        }
      }
    }
    return tpl.content;
  }

  function enhanceCodeBlocks(rootEl, codeSeqRef) {
    for (const pre of Array.from(rootEl.querySelectorAll("pre"))) {
      if (!pre.hasAttribute("tabindex")) pre.setAttribute("tabindex", "0");
      if (!pre.id) { codeSeqRef.n += 1; pre.id = `docs-code-${codeSeqRef.n}`; }
      let box = pre.closest(".copy-box");
      if (!box) { box = mk("div", "copy-box"); pre.parentNode.insertBefore(box, pre); box.appendChild(pre); }
      if (box.querySelector(".copy-btn")) continue;
      const btn = mk("button", "copy-btn", null, { type: "button", command: "--copy", commandfor: pre.id, "aria-label": "Copy code block" });
      btn.append(
        makeSvgIcon("icon-copy", [["path", { d: "M11 9h9a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-9a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2Z" }], ["path", { d: "M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" }]]),
        makeSvgIcon("icon-check", [["polyline", { points: "20 6 9 17 4 12" }]]),
      );
      const ctrl = mk("div", "copy-control");
      ctrl.append(btn, mk("span", "copy-tip", "", { role: "status" }));
      box.appendChild(ctrl);
    }
  }

  function wrapBareTables(rootEl) {
    for (const table of Array.from(rootEl.querySelectorAll("table"))) {
      if (table.closest(".doc-table-wrap, .va-table-wrap")) continue;
      const wrap = mk("div", "doc-table-wrap", null, { tabindex: "0", role: "region", "aria-label": "Reference table" });
      table.parentNode.insertBefore(wrap, table);
      wrap.appendChild(table);
    }
  }

  function reportLocalCopy(button, ok) {
    const sib = button.nextElementSibling;
    const tip = sib?.getAttribute("role") === "status" ? sib : button.parentElement?.querySelector('[role="status"]');
    clearTimeout(copyTimers.get(button));
    button.removeAttribute("data-copied");
    button.removeAttribute("data-failed");
    let msg = ok ? "Copied" : "Copy failed";
    if (msg === lastCopyMsg) msg += "\u00A0";
    lastCopyMsg = msg;
    if (tip) tip.textContent = "";
    void button.offsetWidth;
    button.setAttribute(ok ? "data-copied" : "data-failed", "true");
    requestAnimationFrame(() => { if (tip) tip.textContent = msg; });
    copyTimers.set(button, setTimeout(() => {
      button.removeAttribute("data-copied");
      button.removeAttribute("data-failed");
      if (tip) tip.textContent = "";
    }, 2000));
  }

  async function runLocalCopy(button, targetEl) {
    if (!button) return;
    const target = targetEl || byId(button.getAttribute("commandfor") || "");
    const text = String(target ? (target.matches("input, textarea") ? target.value : (target.innerText || target.textContent || "")) : "").trim();
    if (!text) { reportLocalCopy(button, false); return; }
    try {
      if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable");
      await navigator.clipboard.writeText(text);
      reportLocalCopy(button, true);
    } catch (_err) {
      reportLocalCopy(button, false);
    }
  }

  function ensureCopyFallback() {
    if (window.AgySiteShell || document.documentElement.dataset.agyDocsCopyBound === "1") return;
    document.documentElement.dataset.agyDocsCopyBound = "1";
    document.addEventListener("command", (ev) => { if (ev.command === "--copy") runLocalCopy(ev.source, ev.target); }, true);
    if (!("CommandEvent" in window)) {
      document.addEventListener("click", (ev) => {
        if (ev.defaultPrevented) return;
        const origin = ev.target instanceof Element ? ev.target : ev.target?.parentElement;
        const btn = origin?.closest('button[command="--copy"]');
        if (btn) runLocalCopy(btn, byId(btn.getAttribute("commandfor") || ""));
      });
    }
  }

  function ensureEmptyJumpActions(emptyState, onReset) {
    if (!emptyState || emptyState.querySelector('a[href="#doc-quickstart"]')) return;
    const row = mk("div", "docs-empty-actions");
    const clearBtn = mk("button", "site-btn site-btn-primary", "Clear search", { type: "button" });
    clearBtn.addEventListener("click", () => onReset(true));
    row.appendChild(clearBtn);
    for (const [slug, label] of QUICK_JUMPS) row.appendChild(mk("a", "docs-empty-jump", label, { href: `#doc-${slug}` }));
    emptyState.appendChild(row);
  }

  function extractSubsections(prose) {
    let headings = Array.from(prose.querySelectorAll("h2[id]"));
    if (!headings.length) {
      const h3s = Array.from(prose.querySelectorAll("h3[id]"));
      if (h3s.length <= 6) headings = h3s;
    }
    return headings
      .map((h) => ({ id: String(h.id || "").trim(), title: String(h.textContent || "").trim() }))
      .filter((item) => item.id && item.title);
  }

  function buildChapters(data, articleHost) {
    const chapters = Array.isArray(data?.chapters) ? data.chapters : [];
    const records = [];
    const codeSeqRef = { n: 0 };
    const fragHost = document.createDocumentFragment();

    for (let i = 0; i < chapters.length; i += 1) {
      const ch = chapters[i] || {};
      const slug = String(ch.slug || ch.id || `section-${i + 1}`).replace(/^doc-/, "").trim();
      const anchorId = `doc-${slug}`;
      const title = String(ch.title || slug);
      const group = String(ch.group || "").trim();
      const summary = String(ch.summary || "").trim();
      const kw = Array.isArray(ch.keywords) ? ch.keywords.join(" ") : String(ch.keywords || "");

      const section = mk("section", "docs-chapter", null, { id: anchorId, "data-slug": slug, tabindex: "-1" });
      const header = mk("header", "docs-chapter-header");
      if (group) header.appendChild(mk("span", "docs-chapter-kicker", group));
      header.appendChild(mk("h2", "docs-chapter-title", title));
      if (summary) header.appendChild(mk("p", "docs-chapter-summary", summary));

      const prose = mk("div", "docs-prose");
      const frag = sanitizeFragment(ch.html || "");
      const firstEl = frag.firstElementChild;
      if (firstEl && /^H[12]$/.test(firstEl.tagName) && firstEl.textContent.trim().toLowerCase() === title.toLowerCase()) firstEl.remove();
      prose.appendChild(frag);
      wrapBareTables(prose);
      enhanceCodeBlocks(prose, codeSeqRef);
      section.append(header, prose);
      fragHost.appendChild(section);

      const plain = String(ch.plainText || prose.textContent || "");
      records.push({
        slug, anchorId, title, num: ch.num != null ? String(ch.num).trim() : "", group,
        subsections: extractSubsections(prose), sectionEl: section,
        haystack: `${title} ${group} ${summary} ${kw} ${plain} ${slug}`.toLowerCase(),
      });
    }
    articleHost.replaceChildren(fragHost);
    return records;
  }

  function buildOutlineList(listEl, records) {
    if (!listEl) return [];
    const useLi = /^(UL|OL)$/i.test(String(listEl.tagName || ""));
    const frag = document.createDocumentFragment(), jumpLinks = [];
    const addTitle = (label) => frag.appendChild(mk(useLi ? "li" : "div", "docs-rail-title", label));
    const addLink = (cls, label, href, jumpId, slug, railRole = "") => {
      const attrs = { href, ...(jumpId ? { "data-doc-jump": jumpId } : {}), ...(slug ? { "data-slug": slug } : {}), ...(railRole ? { "data-rail-role": railRole } : {}) };
      const link = mk("a", cls, label, attrs);
      if (jumpId) jumpLinks.push(link);
      if (useLi) { const li = mk("li"); li.appendChild(link); frag.appendChild(li); } else frag.appendChild(link);
    };
    addTitle("QUICK JUMPS");
    for (const item of RAIL_QUICK_JUMPS) addLink("docs-rail-link", item.label, item.href, item.jumpId, item.slug, "quick");
    addTitle("GUIDES");
    for (const rec of records) {
      addLink("docs-rail-link", rec.title, `#${rec.anchorId}`, rec.anchorId, rec.slug);
      for (const sub of rec.subsections) addLink("docs-rail-link docs-rail-sub", sub.title, `#${sub.id}`, sub.id, rec.slug);
    }
    listEl.replaceChildren(frag);
    return jumpLinks;
  }

  function makePagerLink(dir, label, rec) {
    const attrs = { "data-dir": dir };
    if (rec) { attrs.href = `#${rec.anchorId}`; attrs["data-doc-jump"] = rec.anchorId; attrs["data-slug"] = rec.slug; }
    else attrs["aria-disabled"] = "true";
    const el = mk(rec ? "a" : "span", "docs-pager-link", null, attrs);
    el.append(mk("span", "docs-pager-label", label), mk("span", "docs-pager-title", rec ? rec.title : "None"));
    return el;
  }

  function resolveTarget(records, rawTarget) {
    const clean = String(rawTarget || "").replace(/^#/, "").trim();
    if (!clean) return null;
    const chapterMatch = records.find((r) => r.anchorId === clean);
    if (chapterMatch) return { rec: chapterMatch, el: chapterMatch.sectionEl, targetId: chapterMatch.anchorId };
    const targetEl = byId(clean);
    const chapterEl = targetEl?.closest(".docs-chapter, .docs-section");
    const rec = chapterEl ? records.find((r) => r.sectionEl === chapterEl) : null;
    if (rec) return { rec, el: targetEl, targetId: clean };
    const slugMatch = records.find((r) => r.slug === clean.replace(/^doc-/, ""));
    return slugMatch ? { rec: slugMatch, el: slugMatch.sectionEl, targetId: slugMatch.anchorId } : null;
  }

  function createStateController(dom, records) {
    const state = { visible: records.slice(), activeSlug: records[0]?.slug || "", activeTargetId: records[0]?.anchorId || "", scrollLockUntil: 0 };
    const total = records.length;

    function syncActiveUi(slug, targetId = "") {
      const curTitleEl = dom.currentChapterTitle || byId("docsCurrentChapterTitle");
      if (!state.visible.length) {
        state.activeSlug = "";
        state.activeTargetId = "";
        for (const link of dom.outlineLinks) link.removeAttribute("aria-current");
        if (curTitleEl) curTitleEl.textContent = "No matching guides";
        dom.pagerEl.hidden = true;
        return;
      }
      const idx = Math.max(0, state.visible.findIndex((r) => r.slug === slug));
      const activeRec = state.visible[idx];
      state.activeSlug = activeRec.slug;
      state.activeTargetId = targetId || activeRec.anchorId;
      for (const link of dom.outlineLinks) {
        if (link.dataset.railRole !== "quick" && link.dataset.docJump === state.activeTargetId && !activeRec.sectionEl.hidden) link.setAttribute("aria-current", "location");
        else link.removeAttribute("aria-current");
      }
      if (curTitleEl) curTitleEl.textContent = activeRec.num ? `${activeRec.num}. ${activeRec.title}` : activeRec.title;
      dom.pagerEl.hidden = false;
      dom.pagerEl.replaceChildren(
        makePagerLink("prev", "Previous chapter", idx > 0 ? state.visible[idx - 1] : null),
        makePagerLink("next", "Next chapter", idx < state.visible.length - 1 ? state.visible[idx + 1] : null),
      );
    }

    function applyFilter(rawValue) {
      const raw = String(rawValue || "");
      const trimmed = raw.trim();
      const terms = trimmed ? trimmed.toLowerCase().split(/\s+/) : [];
      if (dom.clearBtn) dom.clearBtn.hidden = false;
      state.visible = [];
      for (const rec of records) {
        const matched = terms.length === 0 || terms.every((t) => rec.haystack.includes(t));
        rec.sectionEl.hidden = !matched;
        if (trimmed && matched) rec.sectionEl.setAttribute("data-search-match", "true");
        else rec.sectionEl.removeAttribute("data-search-match");
        if (matched) state.visible.push(rec);
      }
      const matches = state.visible.length;
      if (dom.statusEl) dom.statusEl.textContent = matches === 0 ? "0 matching sections" : `${matches} of ${total} ${total === 1 ? "guide" : "guides"}`;
      if (dom.emptyState) {
        const hasMatches = matches > 0;
        if (!hasMatches && dom.emptyQuery) dom.emptyQuery.textContent = trimmed || raw;
        dom.emptyState.hidden = hasMatches;
        dom.emptyState.classList.toggle("hidden", hasMatches);
      }
      const kept = state.visible.some((r) => r.slug === state.activeSlug);
      const nextSlug = kept ? state.activeSlug : (state.visible[0]?.slug || "");
      syncActiveUi(nextSlug, kept ? state.activeTargetId : (nextSlug ? `doc-${nextSlug}` : ""));
    }

    function jumpToTarget(rawTarget, updateHash = true, moveFocus = true) {
      const hit = resolveTarget(records, rawTarget);
      if (!hit) return false;
      if (hit.rec.sectionEl.hidden) { if (dom.searchInput) dom.searchInput.value = ""; applyFilter(""); }
      state.scrollLockUntil = Date.now() + 550;
      syncActiveUi(hit.rec.slug, hit.targetId);
      if (updateHash && location.hash !== `#${hit.targetId}`) history.replaceState(null, "", `#${hit.targetId}`);
      dom.closeTocDialog?.();
      hit.el.scrollIntoView?.({ behavior: reducedMotionMql?.matches ? "auto" : "smooth", block: "start" });
      if (moveFocus && typeof hit.el.focus === "function") {
        if (!hit.el.hasAttribute("tabindex")) hit.el.setAttribute("tabindex", "-1");
        hit.el.focus({ preventScroll: true });
      }
      return true;
    }

    const jumpToSlug = (rawSlug, updateHash = true, moveFocus = true) => {
      const clean = String(rawSlug || "").replace(/^#/, "").trim();
      if (!clean) return false;
      const target = !String(rawSlug || "").startsWith("#") && !clean.startsWith("doc-") && records.some((r) => r.slug === clean)
        ? `#doc-${clean}` : `#${clean}`;
      return jumpToTarget(target, updateHash, moveFocus);
    };

    function resetSearch(focusInput = false) {
      if (dom.searchInput) { dom.searchInput.value = ""; if (focusInput) dom.searchInput.focus(); }
      applyFilter("");
    }

    return { state, syncActiveUi, applyFilter, jumpToSlug, jumpToTarget, resetSearch };
  }

  function bindDialogSheet(dom) {
    const { tocDialog, tocToggle, tocNav } = dom;
    const syncExpanded = (open) => { if (tocToggle) tocToggle.setAttribute("aria-expanded", String(Boolean(open))); };
    if (!tocDialog) {
      if (tocToggle && tocNav) {
        tocNav.dataset.collapsible = "true";
        syncExpanded(false);
        tocToggle.addEventListener("click", () => {
          const open = !tocNav.classList.contains("is-open");
          tocNav.classList.toggle("is-open", open);
          syncExpanded(open);
        });
      }
      return () => { if (tocToggle && tocNav && !desktopMql?.matches) { tocNav.classList.remove("is-open"); syncExpanded(false); } };
    }

    const isOpen = () => Boolean(tocDialog.open || tocDialog.hasAttribute("open"));
    const openDialog = () => {
      if (isOpen()) return;
      if (typeof tocDialog.showModal === "function") { try { tocDialog.showModal(); } catch (_e) { tocDialog.setAttribute("open", ""); } }
      else tocDialog.setAttribute("open", "");
      syncExpanded(true);
    };
    const closeDialog = () => {
      if (isOpen()) {
        if (typeof tocDialog.close === "function") { try { tocDialog.close(); } catch (_e) { tocDialog.removeAttribute("open"); } }
        if (isOpen()) tocDialog.removeAttribute("open");
      }
      syncExpanded(false);
    };

    syncExpanded(isOpen());
    if (tocToggle) tocToggle.addEventListener("click", () => (isOpen() ? closeDialog() : openDialog()));
    tocDialog.addEventListener("open", () => syncExpanded(true));
    tocDialog.addEventListener("close", () => { if ("returnValue" in tocDialog) tocDialog.returnValue = ""; syncExpanded(false); });
    tocDialog.addEventListener("toggle", (ev) => syncExpanded(ev.newState ? ev.newState === "open" : isOpen()));
    tocDialog.addEventListener("click", (ev) => {
      const origin = ev.target instanceof Element ? ev.target : ev.target?.parentElement;
      if (origin?.closest("[data-close-dialog], a[href]")) closeDialog();
    });
    if (typeof HTMLDialogElement === "undefined" || !("closedBy" in HTMLDialogElement.prototype)) {
      const outside = (ev) => {
        const r = tocDialog.getBoundingClientRect();
        return ev.clientX < r.left || ev.clientX > r.right || ev.clientY < r.top || ev.clientY > r.bottom;
      };
      let pressedOut = false;
      tocDialog.addEventListener("pointerdown", (ev) => { pressedOut = outside(ev); });
      tocDialog.addEventListener("pointerup", (ev) => { if (pressedOut && outside(ev)) closeDialog(); pressedOut = false; });
      tocDialog.addEventListener("pointercancel", () => { pressedOut = false; });
    }
    if (desktopMql) {
      const onBp = (ev) => { if (ev?.matches ?? desktopMql.matches) closeDialog(); };
      if (typeof desktopMql.addEventListener === "function") desktopMql.addEventListener("change", onBp);
      else if (typeof desktopMql.addListener === "function") desktopMql.addListener(onBp);
    }
    return closeDialog;
  }

  function bindInteractions(dom, records, ctrl) {
    ensureEmptyJumpActions(dom.emptyState, ctrl.resetSearch);
    if (dom.searchInput) {
      dom.searchInput.addEventListener("input", () => ctrl.applyFilter(dom.searchInput.value));
      dom.searchInput.addEventListener("keydown", (ev) => {
        if (ev.key === "Escape" && dom.searchInput.value) { ev.preventDefault(); ctrl.resetSearch(true); }
      });
    }
    if (dom.clearBtn) dom.clearBtn.addEventListener("click", () => ctrl.resetSearch(true));
    function handleKey(ev) {
      if (ev.key === "Escape") {
        if (dom.tocDialog?.open || dom.tocDialog?.hasAttribute?.("open") || dom.tocNav?.classList.contains("is-open")) {
          ev.preventDefault();
          dom.closeTocDialog?.();
          dom.tocToggle?.focus?.();
        }
        return;
      }
      if (ev.key !== "/" || window.AgyOawSearch) return;
      if (!dom.searchInput || ev.defaultPrevented || ev.ctrlKey || ev.metaKey || ev.altKey || ev.shiftKey || ev.isComposing) return;
      if (document.querySelector("dialog[open]")) return;
      if (isEditableElement(document.activeElement) || (ev.target instanceof Element && isEditableElement(ev.target))) return;
      ev.preventDefault();
      dom.searchInput.focus();
    }
    document.addEventListener("keydown", handleKey);
    document.addEventListener("click", (ev) => {
      if (ev.defaultPrevented) return;
      const origin = ev.target instanceof Element ? ev.target : ev.target?.parentElement;
      if (!origin) return;
      if (origin.closest("[data-docs-reset]")) { ev.preventDefault(); ctrl.resetSearch(true); return; }
      const jumpEl = origin.closest('[data-doc-jump], [data-docs-jump], a[href^="#"]');
      if (!jumpEl) return;
      const rawTarget = jumpEl.getAttribute("data-doc-jump") || jumpEl.getAttribute("data-docs-jump") || jumpEl.getAttribute("href") || "";
      if (resolveTarget(records, rawTarget)) { ev.preventDefault(); ctrl.jumpToTarget(rawTarget, true); }
    });
    if ("IntersectionObserver" in window && records.length) {
      const intersecting = new Set();
      const observer = new IntersectionObserver((entries) => {
        for (const entry of entries) (entry.isIntersecting ? intersecting.add(entry.target) : intersecting.delete(entry.target));
        if (Date.now() < ctrl.state.scrollLockUntil || !ctrl.state.visible.length || !intersecting.size) return;
        const hit = ctrl.state.visible.find((r) => intersecting.has(r.sectionEl));
        if (!hit) return;
        const hasCurrent = dom.outlineLinks.some((a) => a.getAttribute("aria-current") === "location");
        if (hit.slug !== ctrl.state.activeSlug || !hasCurrent) ctrl.syncActiveUi(hit.slug, hit.anchorId);
      }, { rootMargin: "-18% 0px -62% 0px", threshold: [0, 0.1] });
      for (const rec of records) observer.observe(rec.sectionEl);
    }
    window.addEventListener("hashchange", () => { if (location.hash.length > 1 && resolveTarget(records, location.hash)) ctrl.jumpToTarget(location.hash, false); });
    window.addEventListener("v9-theme-changed", (ev) => { if (ev.detail?.theme) document.documentElement.dataset.docsTheme = ev.detail.theme; });
  }

  function boot() {
    ensureCopyFallback();
    const tocList = byId("docsTocList"), articleHost = byId("docsArticleHost");
    if (!tocList || !articleHost) return;
    const modalList = byId("docsTocModalList"), data = window.AGY_DOCS_DATA || { chapters: [] }, heroMeta = byId("docsHeroMeta");
    if (heroMeta && (data.version || data.generatedAt)) {
      heroMeta.textContent = [data.version ? `v${data.version}` : "", data.generatedAt ? `Updated ${data.generatedAt}` : ""].filter(Boolean).join(" · ");
    }
    if (byId("docsVersion") && data.version) byId("docsVersion").textContent = String(data.version);
    if (byId("docsGeneratedAt") && data.generatedAt) byId("docsGeneratedAt").textContent = String(data.generatedAt);

    const pagerEl = byId("docsPager") || articleHost.insertAdjacentElement("afterend", mk("nav", "docs-pager", null, { id: "docsPager", "aria-label": "Chapter navigation" }));
    const records = buildChapters(data, articleHost);
    const outlineLinks = [...buildOutlineList(tocList, records), ...buildOutlineList(modalList, records)];
    const dom = {
      searchInput: byId("docsSearchInput"), clearBtn: byId("docsSearchClearBtn"), statusEl: byId("docsSearchStatus"),
      emptyState: byId("docsEmptyState"), emptyQuery: byId("docsEmptyQuery"), tocNav: byId("docsTocNav") || tocList.closest("nav"),
      tocToggle: byId("docsTocToggle") || byId("docsTocToggleBtn"), tocDialog: byId("docsTocDialog"),
      currentChapterTitle: byId("docsCurrentChapterTitle"), pagerEl, outlineLinks,
    };
    if (dom.clearBtn) dom.clearBtn.hidden = false;
    dom.closeTocDialog = bindDialogSheet(dom);
    const ctrl = createStateController(dom, records);
    bindInteractions(dom, records, ctrl);
    ctrl.applyFilter(dom.searchInput ? dom.searchInput.value : "");
    if (location.hash.length > 1 && resolveTarget(records, location.hash)) ctrl.jumpToTarget(location.hash, false, false);
    window.AgyDocsApp = {
      applyFilter: ctrl.applyFilter, jumpToSlug: ctrl.jumpToSlug,
      getState: () => ({ activeSlug: ctrl.state.activeSlug, activeTargetId: ctrl.state.activeTargetId, total: records.length, visible: ctrl.state.visible.length }),
    };
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})();
