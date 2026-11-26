/* SPDX-License-Identifier: Apache-2.0 */
/* AGY-Nexus Public Docs — TOC Builder, Live Search, Active Tracking & Copy Controls */
(() => {
  const QUICK_JUMPS = [["quickstart", "Quickstart"], ["common-terms", "Common Terms"], ["architecture", "Architecture"], ["how-it-is-built", "How It Is Built"]];
  const SVG_NS = "http://www.w3.org/2000/svg";
  const mql = (q) => (typeof window.matchMedia === "function" ? window.matchMedia(q) : null);
  const byId = (id) => document.getElementById(id);
  const reducedMotionMql = mql("(prefers-reduced-motion: reduce)");
  const desktopMql = mql("(min-width: 900px)");
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
    clearBtn.addEventListener("click", onReset);
    row.appendChild(clearBtn);
    for (const [slug, label] of QUICK_JUMPS) row.appendChild(mk("a", "docs-empty-jump", label, { href: `#doc-${slug}` }));
    emptyState.appendChild(row);
  }

  function buildChapters(data, tocList, articleHost) {
    const chapters = Array.isArray(data?.chapters) ? data.chapters : [];
    const records = [];
    const groupNodes = new Map();
    const codeSeqRef = { n: 0 };
    let lastGroup = "";
    tocList.replaceChildren();
    articleHost.replaceChildren();

    for (let i = 0; i < chapters.length; i += 1) {
      const ch = chapters[i] || {};
      const slug = String(ch.slug || ch.id || `section-${i + 1}`).replace(/^doc-/, "").trim();
      const anchorId = `doc-${slug}`;
      const title = String(ch.title || slug);
      const group = String(ch.group || "").trim();
      const summary = String(ch.summary || "").trim();
      const kw = Array.isArray(ch.keywords) ? ch.keywords.join(" ") : String(ch.keywords || "");

      if (group && group !== lastGroup) {
        lastGroup = group;
        const grpLi = mk("li", "docs-toc-group-label", group, { "aria-hidden": "true" });
        tocList.appendChild(grpLi);
        groupNodes.set(group, grpLi);
      }
      const li = mk("li", null, null, { "data-slug": slug });
      if (group) li.dataset.group = group;
      const tocLink = mk("a", "docs-toc-link", title, { href: `#${anchorId}` });
      li.appendChild(tocLink);
      tocList.appendChild(li);

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
      articleHost.appendChild(section);

      const plain = String(ch.plainText || prose.textContent || "");
      records.push({ slug, anchorId, title, group, tocItemEl: li, tocLink, sectionEl: section, haystack: `${title} ${group} ${summary} ${kw} ${plain} ${slug}`.toLowerCase() });
    }
    return { records, groupNodes };
  }

  function makePagerLink(dir, label, rec) {
    const attrs = { "data-dir": dir };
    if (rec) attrs.href = `#${rec.anchorId}`;
    else attrs["aria-disabled"] = "true";
    const el = mk(rec ? "a" : "span", "docs-pager-link", null, attrs);
    el.append(mk("span", "docs-pager-label", label), mk("span", "docs-pager-title", rec ? rec.title : "None"));
    return el;
  }

  function createStateController(dom, records, groupNodes) {
    const state = { visible: records.slice(), activeSlug: records[0]?.slug || "", scrollLockUntil: 0 };
    const total = records.length;

    function syncActiveUi(slug) {
      if (!state.visible.length) {
        for (const rec of records) rec.tocLink.removeAttribute("aria-current");
        dom.pagerEl.hidden = true;
        return;
      }
      const idx = Math.max(0, state.visible.findIndex((r) => r.slug === slug));
      state.activeSlug = state.visible[idx].slug;
      for (const rec of records) {
        if (rec.slug === state.activeSlug && !rec.sectionEl.hidden) rec.tocLink.setAttribute("aria-current", "true");
        else rec.tocLink.removeAttribute("aria-current");
      }
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
      if (dom.clearBtn) dom.clearBtn.hidden = trimmed.length === 0;
      const activeGroups = new Set();
      state.visible = [];
      for (const rec of records) {
        const matched = terms.length === 0 || terms.every((t) => rec.haystack.includes(t));
        rec.sectionEl.hidden = !matched;
        rec.tocItemEl.hidden = !matched;
        if (trimmed && matched) rec.sectionEl.setAttribute("data-search-match", "true");
        else rec.sectionEl.removeAttribute("data-search-match");
        if (matched) { state.visible.push(rec); if (rec.group) activeGroups.add(rec.group); }
      }
      for (const [grp, grpEl] of groupNodes.entries()) grpEl.hidden = !activeGroups.has(grp);
      const matches = state.visible.length;
      if (dom.statusEl) {
        dom.statusEl.textContent = trimmed ? `Showing ${matches} of ${total} sections for "${trimmed}"` : `Showing ${total} of ${total} sections`;
      }
      if (matches === 0) {
        if (dom.emptyQuery) dom.emptyQuery.textContent = trimmed || raw;
        if (dom.emptyState) { dom.emptyState.hidden = false; dom.emptyState.classList.remove("hidden"); }
      } else if (dom.emptyState) {
        dom.emptyState.hidden = true;
      }
      syncActiveUi(state.visible.some((r) => r.slug === state.activeSlug) ? state.activeSlug : (state.visible[0]?.slug || ""));
    }

    function jumpToSlug(rawSlug, updateHash = true) {
      const slug = String(rawSlug || "").replace(/^#?doc-/, "").trim();
      const targetRec = records.find((r) => r.slug === slug);
      if (!targetRec) return;
      if (targetRec.sectionEl.hidden) { if (dom.searchInput) dom.searchInput.value = ""; applyFilter(""); }
      state.scrollLockUntil = Date.now() + 450;
      syncActiveUi(targetRec.slug);
      if (updateHash && location.hash !== `#${targetRec.anchorId}`) history.replaceState(null, "", `#${targetRec.anchorId}`);
      targetRec.sectionEl.scrollIntoView({ behavior: reducedMotionMql?.matches ? "auto" : "smooth", block: "start" });
      if (dom.tocToggle && dom.tocNav && !desktopMql?.matches) {
        dom.tocNav.classList.remove("is-open");
        dom.tocToggle.setAttribute("aria-expanded", "false");
      }
    }

    const resetSearch = () => { if (dom.searchInput) { dom.searchInput.value = ""; dom.searchInput.focus(); } applyFilter(""); };
    return { state, syncActiveUi, applyFilter, jumpToSlug, resetSearch };
  }

  function bindInteractions(dom, records, ctrl) {
    ensureEmptyJumpActions(dom.emptyState, ctrl.resetSearch);
    if (dom.searchInput) {
      dom.searchInput.addEventListener("input", () => ctrl.applyFilter(dom.searchInput.value));
      dom.searchInput.addEventListener("keydown", (ev) => {
        if (ev.key === "Escape" && dom.searchInput.value) { ev.preventDefault(); ctrl.resetSearch(); }
      });
    }
    if (dom.clearBtn) dom.clearBtn.addEventListener("click", ctrl.resetSearch);
    document.addEventListener("click", (ev) => {
      if (ev.defaultPrevented) return;
      const origin = ev.target instanceof Element ? ev.target : ev.target?.parentElement;
      if (!origin) return;
      if (origin.closest("[data-docs-reset]")) { ev.preventDefault(); ctrl.resetSearch(); return; }
      const href = origin.closest('a[href^="#doc-"]')?.getAttribute("href") || "";
      if (href && records.some((r) => `#${r.anchorId}` === href)) { ev.preventDefault(); ctrl.jumpToSlug(href, true); }
    });
    if (dom.tocToggle && dom.tocNav) {
      dom.tocNav.dataset.collapsible = "true";
      dom.tocToggle.setAttribute("aria-expanded", "false");
      dom.tocToggle.addEventListener("click", () => {
        const nextOpen = !dom.tocNav.classList.contains("is-open");
        dom.tocNav.classList.toggle("is-open", nextOpen);
        dom.tocToggle.setAttribute("aria-expanded", String(nextOpen));
      });
    }
    if ("IntersectionObserver" in window && records.length) {
      const intersecting = new Set();
      const observer = new IntersectionObserver((entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) intersecting.add(entry.target);
          else intersecting.delete(entry.target);
        }
        if (Date.now() < ctrl.state.scrollLockUntil || !intersecting.size) return;
        const hit = ctrl.state.visible.find((r) => intersecting.has(r.sectionEl));
        if (hit && hit.slug !== ctrl.state.activeSlug) ctrl.syncActiveUi(hit.slug);
      }, { rootMargin: "-18% 0px -62% 0px", threshold: [0, 0.1] });
      for (const rec of records) observer.observe(rec.sectionEl);
    }
    window.addEventListener("hashchange", () => { if (location.hash.startsWith("#doc-")) ctrl.jumpToSlug(location.hash, false); });
    window.addEventListener("v9-theme-changed", (ev) => {
      if (ev.detail?.theme) document.documentElement.dataset.docsTheme = ev.detail.theme;
    });
  }

  function boot() {
    ensureCopyFallback();
    const tocList = byId("docsTocList");
    const articleHost = byId("docsArticleHost");
    if (!tocList || !articleHost) return;
    const data = window.AGY_DOCS_DATA || { chapters: [] };
    const heroMeta = byId("docsHeroMeta");
    if (heroMeta && (data.version || data.generatedAt)) {
      const metaParts = [];
      if (data.version) metaParts.push(`v${data.version}`);
      if (data.generatedAt) metaParts.push(`Updated ${data.generatedAt}`);
      heroMeta.textContent = metaParts.join(" · ");
    }
    if (byId("docsVersion") && data.version) byId("docsVersion").textContent = String(data.version);
    if (byId("docsGeneratedAt") && data.generatedAt) byId("docsGeneratedAt").textContent = String(data.generatedAt);

    let pagerEl = byId("docsPager");
    if (!pagerEl) {
      pagerEl = mk("nav", "docs-pager", null, { id: "docsPager", "aria-label": "Chapter navigation" });
      articleHost.insertAdjacentElement("afterend", pagerEl);
    }
    const dom = {
      searchInput: byId("docsSearchInput"), clearBtn: byId("docsSearchClearBtn"),
      statusEl: byId("docsSearchStatus"), emptyState: byId("docsEmptyState"),
      emptyQuery: byId("docsEmptyQuery"), tocNav: byId("docsTocNav") || tocList.closest("nav"),
      tocToggle: byId("docsTocToggle") || byId("docsTocToggleBtn"), pagerEl,
    };
    const { records, groupNodes } = buildChapters(data, tocList, articleHost);
    const ctrl = createStateController(dom, records, groupNodes);
    bindInteractions(dom, records, ctrl);
    ctrl.applyFilter(dom.searchInput ? dom.searchInput.value : "");
    if (location.hash.startsWith("#doc-")) ctrl.jumpToSlug(location.hash, false);
    window.AgyDocsApp = {
      applyFilter: ctrl.applyFilter,
      jumpToSlug: ctrl.jumpToSlug,
      getState: () => ({ activeSlug: ctrl.state.activeSlug, total: records.length, visible: ctrl.state.visible.length }),
    };
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})();
