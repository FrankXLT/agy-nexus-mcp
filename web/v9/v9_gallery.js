/* SPDX-License-Identifier: Apache-2.0 */
/* AGY-Nexus /web/v9 — Simplified 4-Control Gallery Toolbar, More Popover & Multi-Select */
(() => {
  const V9 = window.AgyV9;
  const DL_SVG = `<svg class="v9-gal-ico" width="12" height="12" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M8 2.5V10.5M5 7.5L8 10.5L11 7.5M2.5 13H13.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  const SHARE_SVG = `<svg class="v9-gal-ico" width="12" height="12" viewBox="0 0 16 16" fill="none" aria-hidden="true"><circle cx="12" cy="3.5" r="1.8" stroke="currentColor" stroke-width="1.5"/><circle cx="4" cy="8" r="1.8" stroke="currentColor" stroke-width="1.5"/><circle cx="12" cy="12.5" r="1.8" stroke="currentColor" stroke-width="1.5"/><path d="M5.6 7.1L10.4 4.4M5.6 8.9L10.4 11.6" stroke="currentColor" stroke-width="1.4"/></svg>`;
  const CARET_SVG = `<svg class="v9-caret-down" width="10" height="10" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  let currentVisualItems = [];
  let currentSessionItems = [];
  let currentRepoItems = [];
  let lastClickedGridId = "";
  let currentRepoSlug = "session";
  let currentSessionCapsCount = 0;
  let moreOpen = false;
  let globalDismissBound = false;

  function getCardKey(item) {
    return window.GallerySelect ? window.GallerySelect.getItemKey(item) : `${item.scope || ""}/${item.rel_path || item.name}`;
  }

  function closeMorePopover() {
    if (!moreOpen) return;
    moreOpen = false;
    const pop = document.getElementById("v9GalMorePopover");
    const btn = document.getElementById("v9GalMoreBtn");
    if (pop) {
      pop.classList.add("hidden");
      pop.style.removeProperty("inset-inline-start");
      pop.style.removeProperty("inset-inline-end");
    }
    if (btn) btn.setAttribute("aria-expanded", "false");
  }

  function openMorePopover() {
    const pop = document.getElementById("v9GalMorePopover");
    const btn = document.getElementById("v9GalMoreBtn");
    if (!pop || !btn) return;
    moreOpen = true;
    pop.style.removeProperty("inset-inline-start");
    pop.style.removeProperty("inset-inline-end");
    pop.classList.remove("hidden");
    btn.setAttribute("aria-expanded", "true");
    const r = pop.getBoundingClientRect();
    const pLeft = pop.parentElement ? pop.parentElement.getBoundingClientRect().left : 0;
    if (r.left < 12) {
      pop.style.insetInlineEnd = "auto";
      pop.style.insetInlineStart = `${Math.ceil(12 - pLeft)}px`;
    }
    const r2 = pop.getBoundingClientRect();
    if (r2.right > window.innerWidth - 12) {
      const cur = parseFloat(pop.style.insetInlineStart || "0");
      pop.style.insetInlineStart = `${cur - Math.ceil(r2.right - (window.innerWidth - 12))}px`;
    }
  }

  function ensureGlobalDismiss() {
    if (globalDismissBound) return;
    globalDismissBound = true;
    document.addEventListener("click", (e) => {
      const wrap = document.getElementById("v9GalMoreWrap");
      if (moreOpen && wrap && !wrap.contains(e.target)) closeMorePopover();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && moreOpen) closeMorePopover();
    });
  }

  function updateToolbar() {
    const bar = document.getElementById("v9GalToolbar");
    const GS = window.GallerySelect;
    const SB = window.SheetBuilder;
    if (!bar || !GS || !SB) return;
    ensureGlobalDismiss();
    moreOpen = false;
    const sel = GS.getSelectedList();
    const n = sel.length;
    const ps = SB.getPerSheet();
    const sheetCount = n ? Math.ceil(n / ps) : 0;
    const canSelectSession = currentSessionItems.length > 0;
    const allSel = canSelectSession ? currentSessionItems.every((it) => GS.isSelected(it)) : n > 0;
    const countLabel = n > 0
      ? `${n} selected`
      : `${currentSessionCapsCount} capture${currentSessionCapsCount === 1 ? "" : "s"}`;

    bar.innerHTML = `<span class="v9-gal-count">${V9.escHtml(countLabel)}</span>
      <div class="v9-gal-actions">
        <button type="button" class="v9-nav-btn" id="v9GalAllBtn"${(!canSelectSession && n === 0) ? " disabled" : ""}>${allSel ? "Clear" : "All"}</button>
        <button type="button" class="v9-nav-btn" id="v9GalCmpBtn"${n >= 2 ? "" : " disabled"}>Compare</button>
        <button type="button" class="v9-nav-btn" id="v9GalPngsBtn"${n ? "" : " disabled"}>${DL_SVG}<span>PNGs</span></button>
        <div class="v9-gal-more-wrap" id="v9GalMoreWrap">
          <button type="button" class="v9-nav-btn" id="v9GalMoreBtn" aria-haspopup="menu" aria-expanded="false" aria-controls="v9GalMorePopover"><span>More</span>${CARET_SVG}</button>
          <div id="v9GalMorePopover" class="v9-popover v9-gal-more-pop hidden" role="menu" aria-labelledby="v9GalMoreBtn">
            <button type="button" role="menuitem" class="v9-period-opt" id="v9GalSheetsBtn"${n ? "" : " disabled"}>${DL_SVG}<span class="v9-period-opt-title">Contact Sheet${n ? ` (${sheetCount})` : ""}</span></button>
            <button type="button" role="menuitem" class="v9-period-opt" id="v9GalZipBtn"${n ? "" : " disabled"}>${DL_SVG}<span class="v9-period-opt-title">Download ZIP</span></button>
            <button type="button" role="menuitem" class="v9-period-opt" id="v9GalShareBtn"${n ? "" : " disabled"}>${SHARE_SVG}<span class="v9-period-opt-title">Share</span></button>
            <div class="v9-gal-desktop-cols">
              <hr class="v9-menu-sep" />
              <div class="v9-pop-label" aria-hidden="true">Per Sheet</div>
              <div class="va-tb-group" role="group" aria-label="Per sheet columns">
                ${[2, 4, 8].map((v) => `<button type="button" class="va-tb-btn" data-v9-ps="${v}" aria-pressed="${ps === v}">${v}</button>`).join("")}
              </div>
            </div>
          </div>
        </div>
      </div>`;

    setStatus("");
    bindToolbarEvents(bar, GS, SB, allSel);
  }

  function bindToolbarEvents(bar, GS, SB, allSel) {
    bar.querySelector("#v9GalAllBtn")?.addEventListener("click", () => {
      if (allSel) GS.clearSelection();
      else if (currentSessionItems.length > 0) GS.selectAll(currentSessionItems);
      lastClickedGridId = "";
      syncCardSelectionDom();
    });
    bar.querySelector("#v9GalCmpBtn")?.addEventListener("click", () => {
      const picked = GS.getSelectedList();
      if (picked.length >= 2 && V9.Lightbox) V9.Lightbox.openCompare(picked.slice(0, 2), currentVisualItems, () => { lastClickedGridId = ""; syncCardSelectionDom(); });
    });
    bar.querySelector("#v9GalPngsBtn")?.addEventListener("click", async () => {
      if (V9.state.demoMode) await downloadDemoPngs(GS.getSelectedList());
      else GS.downloadSequentialPngs(setStatus, () => V9.handleUnauthorized?.("Session locked (401) — enter passphrase to export."));
    });
    bar.querySelector("#v9GalMoreBtn")?.addEventListener("click", (e) => {
      e.stopPropagation();
      if (moreOpen) closeMorePopover();
      else openMorePopover();
    });
    bar.querySelectorAll("[data-v9-ps]").forEach((b) => {
      b.addEventListener("click", () => { SB.setPerSheet(Number(b.getAttribute("data-v9-ps"))); updateToolbar(); });
    });
    bar.querySelector("#v9GalShareBtn")?.addEventListener("click", () => {
      closeMorePopover();
      SB.shareSheetsToGemini(GS.getSelectedList(), currentRepoSlug, SB.getPerSheet(), openSingleFromUrl, setStatus);
    });
    bar.querySelector("#v9GalSheetsBtn")?.addEventListener("click", () => {
      closeMorePopover();
      SB.downloadSheets(GS.getSelectedList(), currentRepoSlug, SB.getPerSheet(), setStatus);
    });
    bar.querySelector("#v9GalZipBtn")?.addEventListener("click", async () => {
      closeMorePopover();
      const cid = V9.state.selectedSession || "session";
      if (V9.state.demoMode) await downloadClientZip(GS.getSelectedList(), cid);
      else await GS.downloadZip(cid, () => (V9.state.passphrase ? { "X-Nexus-Passphrase": V9.state.passphrase } : {}), V9.getBasePath, () => V9.handleUnauthorized?.("Session locked (401) — enter passphrase to download ZIP."));
    });
  }

  function triggerBlobDownload(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
  }

  async function downloadDemoPngs(selected) {
    if (!selected.length) return;
    let okCount = 0;
    for (let i = 0; i < selected.length; i += 1) {
      const it = selected[i];
      if (!it || !it.signed_url) continue;
      try {
        const res = await fetch(it.signed_url);
        if (!res.ok) continue;
        triggerBlobDownload(await res.blob(), it.name || `capture_${i + 1}.png`);
        okCount += 1;
      } catch (_e) {}
    }
    setStatus(okCount ? `Downloaded ${okCount} PNG file(s)` : "PNG download failed");
  }

  async function downloadClientZip(selected, cid) {
    const SB = window.SheetBuilder;
    if (!SB || !selected.length) return;
    setStatus(`Building ZIP of ${selected.length} files...`);
    try {
      const entries = await Promise.all(selected.map(async (it, i) => {
        const r = await fetch(it.signed_url);
        return { name: it.name || `capture_${i + 1}.png`, data: new Uint8Array(await r.arrayBuffer()) };
      }));
      const fname = `captures_${cid.slice(0, 8)}_${selected.length}.zip`;
      triggerBlobDownload(new Blob([SB.buildStoreZip(entries)], { type: "application/zip" }), fname);
      setStatus(`Downloaded ${fname}`);
    } catch (err) {
      setStatus(`ZIP build error: ${err.message}`);
    }
  }

  function setStatus(msg) {
    const el = document.getElementById("v9GalStatus");
    if (el) el.textContent = msg || "";
  }

  function openSingleFromUrl(url, title, meta) {
    if (V9.Lightbox) V9.Lightbox.openSingle([{ name: title || "Sheet", signed_url: url, meta: meta || "" }], 0);
  }

  function syncCardSelectionDom() {
    const GS = window.GallerySelect;
    document.querySelectorAll("#v9GalGrid .v9-gal-card, #v9RepoAssetsGrid .v9-gal-card").forEach((card) => {
      const idx = Number(card.getAttribute("data-idx"));
      const item = currentVisualItems[idx];
      if (!item || !GS) return;
      const selIdx = GS.getSelectionIndex(item);
      const active = selIdx > 0;
      card.classList.toggle("is-selected", active);
      const btn = card.querySelector(".v9-gal-sel-btn");
      if (btn) {
        btn.classList.toggle("is-selected", active);
        btn.setAttribute("aria-pressed", String(active));
        btn.textContent = active ? String(selIdx) : "";
      }
    });
    updateToolbar();
  }

  function buildCardsHtml(items, offsetIdx) {
    const GS = window.GallerySelect;
    return items.map((item, i) => {
      const idx = offsetIdx + i;
      const selIdx = GS ? GS.getSelectionIndex(item) : 0;
      const active = selIdx > 0;
      const dimLabel = item.width && item.height ? `${item.width}×${item.height}` : V9.fmtBytes(item.size || 0);
      return `<article class="v9-gal-card visual-thumb-card${active ? " is-selected" : ""}" data-idx="${idx}" data-key="${V9.escHtml(getCardKey(item))}">
        <button type="button" class="va-overlay-control v9-gal-sel-btn${active ? " is-selected" : ""}" data-sel-idx="${idx}" aria-label="Select ${V9.escHtml(item.name)}" aria-pressed="${active}">${active ? selIdx : ""}</button>
        <button type="button" class="v9-gal-thumb-btn" data-open-idx="${idx}" aria-label="Preview ${V9.escHtml(item.name)}">
          <img class="v9-gal-thumb" src="${V9.escHtml(item.signed_url)}" alt="${V9.escHtml(item.name)}" loading="lazy" />
        </button>
        <div class="v9-gal-meta">
          <span class="v9-gal-name" title="${V9.escHtml(item.name)}">${V9.escHtml(item.name)}</span>
          <span class="v9-gal-foot-right">
            <span class="v9-dim-tag" data-dim-idx="${idx}">${V9.escHtml(dimLabel)}</span>
            ${item.workspace_url ? `<button type="button" class="v9-sess-id-btn v9-copy-link-btn" data-copy-link="${idx}" title="Copy 7d capture link">Copy Link</button>` : ""}
          </span>
        </div>
      </article>`;
    }).join("");
  }

  function getGridScopeItems(gridEl) {
    return gridEl && gridEl.id === "v9RepoAssetsGrid"
      ? new Array(currentSessionItems.length).concat(currentRepoItems)
      : currentSessionItems;
  }

  function wireGridEvents(gridEl) {
    const GS = window.GallerySelect;
    if (!gridEl) return;
    const gridKey = gridEl.id === "v9RepoAssetsGrid" ? "repo" : "session";
    gridEl.querySelectorAll("[data-sel-idx]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const idx = Number(btn.getAttribute("data-sel-idx"));
        const scopeItems = getGridScopeItems(gridEl);
        const item = scopeItems[idx];
        if (!item || !GS) return;
        const checked = !GS.isSelected(item);
        if (e.shiftKey && lastClickedGridId === gridKey) GS.handleShiftSelect(scopeItems, idx, checked);
        else GS.toggleItem(item, checked, idx);
        if (checked) lastClickedGridId = gridKey;
        syncCardSelectionDom();
      });
    });
    gridEl.querySelectorAll("[data-open-idx]").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (GS && GS.shouldSuppressClick()) return;
        const idx = Number(btn.getAttribute("data-open-idx"));
        if (V9.Lightbox) V9.Lightbox.openSingle(currentVisualItems, idx, () => { lastClickedGridId = ""; syncCardSelectionDom(); });
      });
    });
    gridEl.querySelectorAll("[data-copy-link]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const item = currentVisualItems[Number(btn.getAttribute("data-copy-link"))];
        if (item && item.workspace_url) V9.copyText(V9.toAbsUrl(item.workspace_url), "Copied 7d capture link");
      });
    });
    gridEl.querySelectorAll("img.v9-gal-thumb").forEach((img) => {
      img.addEventListener("load", () => {
        const card = img.closest("[data-idx]");
        const idx = card ? Number(card.getAttribute("data-idx")) : -1;
        const tag = card ? card.querySelector(`[data-dim-idx="${idx}"]`) : null;
        if (tag && img.naturalWidth) tag.textContent = `${img.naturalWidth}×${img.naturalHeight}`;
      });
    });
    if (GS && !gridEl.dataset.v9GesturesBound) {
      gridEl.dataset.v9GesturesBound = "1";
      GS.bindGalleryGestures(gridEl, () => getGridScopeItems(gridEl), () => { lastClickedGridId = gridKey; syncCardSelectionDom(); });
    }
  }

  function renderBucketGallery(bucket) {
    const gridEl = document.getElementById("v9GalGrid");
    const repoGridEl = document.getElementById("v9RepoAssetsGrid");
    const repoCountEl = document.getElementById("v9RepoAssetsCount");
    const GS = window.GallerySelect;
    if (!gridEl) return;
    if (GS) GS.clearSelection();
    lastClickedGridId = "";
    currentRepoSlug = (bucket && bucket.repo_slug) || "session";
    const sessionCaps = Array.isArray(bucket && bucket.visual_artifacts) ? bucket.visual_artifacts : [];
    const repoAssets = Array.isArray(bucket && bucket.repo_visual_assets) ? bucket.repo_visual_assets : [];
    currentSessionItems = sessionCaps;
    currentRepoItems = repoAssets;
    currentSessionCapsCount = sessionCaps.length;
    currentVisualItems = [...sessionCaps, ...repoAssets];
    const capCntEl = document.getElementById("v9CapturesBtnCount");
    if (capCntEl) capCntEl.textContent = String(currentSessionCapsCount);

    gridEl.innerHTML = sessionCaps.length ? buildCardsHtml(sessionCaps, 0) : `<div class="v9-empty">No session screenshots in this session yet.</div>`;
    if (repoCountEl) repoCountEl.textContent = String(repoAssets.length);
    if (repoGridEl) {
      repoGridEl.innerHTML = repoAssets.length ? buildCardsHtml(repoAssets, sessionCaps.length) : `<div class="v9-empty">No shared repo assets.</div>`;
    }
    wireGridEvents(gridEl);
    wireGridEvents(repoGridEl);
    updateToolbar();
  }

  function reset() {
    currentVisualItems = [];
    currentSessionItems = [];
    currentRepoItems = [];
    lastClickedGridId = "";
    currentRepoSlug = "session";
    currentSessionCapsCount = 0;
    closeMorePopover();
    ["v9CapturesBtnCount", "v9RepoAssetsCount"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.textContent = "0";
    });
    ["sheetExportDialog", "v9CapturesDialog"].forEach((id) => {
      const dlg = document.getElementById(id);
      if (dlg && dlg.open) dlg.close();
    });
    ["v9GalGrid", "v9RepoAssetsGrid", "v9GalToolbar"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.innerHTML = "";
    });
    setStatus("");
  }

  V9.Gallery = { renderBucketGallery, reset, getItems: () => currentVisualItems, getSessionItems: () => currentSessionItems };
})();
