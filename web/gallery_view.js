// AGY-NEXUS Overwatch — Gallery Toolbar, Numbered Cards, In-Place DOM Sync & Lightbox Viewer (v3.2.2)
(function (root, factory) {
  if (typeof define === "function" && define.amd) {
    define(["./gallery_select", "./sheet_builder"], factory);
  } else if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./gallery_select"), require("./sheet_builder"));
  } else {
    root.GalleryView = factory(root.GallerySelect, root.SheetBuilder);
  }
})(typeof self !== "undefined" ? self : this, function (GallerySelect, SheetBuilder) {
  "use strict";

  let lbItems = [], lbIndex = 0, lbKeyHandler = null, lbTouchStart = null, lbCopyTimer = 0;
  let lastCtx = null;

  const esc = (s) => String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  const toAbsUrl = (url) => (!url || url.startsWith("http://") || url.startsWith("https://")) ? (url || "") : `${window.location.origin}${url.startsWith("/") ? "" : "/"}${url}`;

  function formatRelativeAge(mtime) {
    if (!mtime) return "";
    const sec = Math.max(0, Math.floor(Date.now() / 1000 - Number(mtime)));
    return sec < 60 ? `${sec}s ago` : (sec < 3600 ? `${Math.floor(sec / 60)}m ago` : (sec < 86400 ? `${Math.floor(sec / 3600)}h ago` : `${Math.floor(sec / 86400)}d ago`));
  }

  function formatThumbLabel(name) {
    const raw = String(name || "");
    if (raw.length <= 56) return raw;
    return `${raw.slice(0, 24)}…${raw.slice(-28)}`;
  }

  function resetLightboxState() {
    lbItems = [];
    lbIndex = 0;
    lbTouchStart = null;
    if (lbCopyTimer) { clearTimeout(lbCopyTimer); lbCopyTimer = 0; }
    if (lbKeyHandler) { window.removeEventListener("keydown", lbKeyHandler); lbKeyHandler = null; }
    const imgEl = document.getElementById("lightboxImg");
    const copyBtn = document.getElementById("lightboxCopyLinkBtn");
    const dlg = document.getElementById("lightboxModal");
    if (imgEl) imgEl.removeAttribute("src");
    if (copyBtn) copyBtn.textContent = "Copy 7d Link";
    const bodyEl = dlg?.querySelector(".lightbox-body");
    if (bodyEl) { bodyEl.ontouchstart = null; bodyEl.ontouchend = null; }
    if (dlg?.open) dlg.close();
  }

  function renderLightboxCurrent() {
    const cur = lbItems[lbIndex] || {};
    const imgEl = document.getElementById("lightboxImg"), titleEl = document.getElementById("lightboxTitle");
    const metaEl = document.getElementById("lightboxMeta"), copyBtn = document.getElementById("lightboxCopyLinkBtn");
    const prevBtn = document.getElementById("lightboxPrevBtn"), nextBtn = document.getElementById("lightboxNextBtn");
    const selBtn = document.getElementById("lightboxSelectBtn");
    const url = cur.signed_url || "", multi = lbItems.length > 1;
    if (lbCopyTimer) { clearTimeout(lbCopyTimer); lbCopyTimer = 0; }
    if (imgEl) imgEl.src = url;
    if (titleEl) titleEl.textContent = multi ? `[${lbIndex + 1}/${lbItems.length}] ${cur.name || "Preview"}` : (cur.name || "Visual Artifact Preview");
    if (metaEl) metaEl.textContent = cur.meta || `${cur.scope ? cur.scope + " · " : ""}${cur.rel_path || ""}${cur.mtime ? " · " + formatRelativeAge(cur.mtime) : ""}`;
    if (prevBtn) prevBtn.classList.toggle("hidden", !multi);
    if (nextBtn) nextBtn.classList.toggle("hidden", !multi);
    if (selBtn) {
      const canSel = Boolean(cur.rel_path || cur.scope);
      selBtn.classList.toggle("hidden", !canSel);
      const sIdx = canSel ? GallerySelect.getSelectionIndex(cur) : 0;
      selBtn.setAttribute("aria-pressed", sIdx > 0 ? "true" : "false");
      selBtn.textContent = sIdx > 0 ? `✓ Selected (#${sIdx})` : "✓ Select";
    }
    if (copyBtn) {
      copyBtn.textContent = "Copy 7d Link";
      copyBtn.onclick = () => {
        navigator.clipboard?.writeText(toAbsUrl(url));
        copyBtn.textContent = "Copied!";
        if (lbCopyTimer) clearTimeout(lbCopyTimer);
        lbCopyTimer = setTimeout(() => { copyBtn.textContent = "Copy 7d Link"; lbCopyTimer = 0; }, 1200);
      };
    }
  }

  function stepLightbox(delta) {
    if (lbItems.length <= 1) return;
    lbIndex = (lbIndex + delta + lbItems.length) % lbItems.length;
    renderLightboxCurrent();
  }

  function openLightbox(itemsOrUrl, indexOrTitle, meta) {
    const dlg = document.getElementById("lightboxModal");
    if (!dlg) return window.open(typeof itemsOrUrl === "string" ? itemsOrUrl : itemsOrUrl?.[0]?.signed_url, "_blank");
    if (Array.isArray(itemsOrUrl)) {
      lbItems = itemsOrUrl;
      lbIndex = Math.max(0, Math.min(Number(indexOrTitle) || 0, Math.max(0, lbItems.length - 1)));
    } else {
      lbItems = [{ signed_url: itemsOrUrl, name: indexOrTitle || "Preview", meta: meta || "" }];
      lbIndex = 0;
    }
    renderLightboxCurrent();
    const pBtn = document.getElementById("lightboxPrevBtn"), nBtn = document.getElementById("lightboxNextBtn");
    const cBtn = document.getElementById("lightboxCloseBtn"), sBtn = document.getElementById("lightboxSelectBtn");
    if (pBtn) pBtn.onclick = () => stepLightbox(-1);
    if (nBtn) nBtn.onclick = () => stepLightbox(1);
    if (cBtn) cBtn.onclick = () => dlg.close();
    if (sBtn) sBtn.onclick = () => {
      const cur = lbItems[lbIndex];
      if (!cur) return;
      GallerySelect.toggleItem(cur, !GallerySelect.isSelected(cur), lbIndex);
      renderLightboxCurrent();
      syncGalleryDomState(document.getElementById("workspaceStage"), lastCtx?.getSessionCount?.() ?? 0);
    };
    const bodyEl = dlg.querySelector(".lightbox-body");
    if (bodyEl) {
      bodyEl.ontouchstart = (e) => { lbTouchStart = e.changedTouches?.[0] ? { x: e.changedTouches[0].clientX, y: e.changedTouches[0].clientY } : null; };
      bodyEl.ontouchend = (e) => {
        if (!lbTouchStart || !e.changedTouches?.[0]) return;
        const dx = e.changedTouches[0].clientX - lbTouchStart.x, dy = e.changedTouches[0].clientY - lbTouchStart.y;
        lbTouchStart = null;
        if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.2) stepLightbox(dx < 0 ? 1 : -1);
      };
    }
    if (lbKeyHandler) window.removeEventListener("keydown", lbKeyHandler);
    lbKeyHandler = (e) => { if (e.key === "ArrowLeft") stepLightbox(-1); else if (e.key === "ArrowRight") stepLightbox(1); };
    window.addEventListener("keydown", lbKeyHandler);
    dlg.addEventListener("close", resetLightboxState, { once: true });
    dlg.onclick = (e) => {
      if ("closedBy" in HTMLDialogElement.prototype || e.target !== dlg) return;
      const r = dlg.getBoundingClientRect();
      if (r.top <= e.clientY && e.clientY <= r.top + r.height && r.left <= e.clientX && e.clientX <= r.left + r.width) return;
      dlg.close();
    };
    if (!dlg.open) typeof dlg.showModal === "function" ? dlg.showModal() : dlg.setAttribute("open", "");
  }

  function renderToolbarHtml(sessionLen) {
    const totalLen = Math.max(0, Number(sessionLen) || 0);
    const per = SheetBuilder ? SheetBuilder.getPerSheet() : 4;
    const selN = GallerySelect.getSelectedList().length, sheets = selN ? Math.ceil(selN / per) : 0;
    const summaryTxt = selN ? `${selN} selected → ${sheets} sheet${sheets === 1 ? "" : "s"} (${per}/sheet)` : `Session Captures (${totalLen})`;
    const capWarn = sheets > 10 ? `<span class="gallery-tb-warn mono">${sheets} sheets · >10 Gemini cap</span>` : "";
    const presets = [2, 4, 8].map((n) => `<button type="button" class="preset-btn mono" data-per="${n}" aria-pressed="${per === n}">${n}</button>`).join("");
    return `<div class="gallery-toolbar mono ${selN ? "has-selection" : ""}" id="secVisualArtifacts" role="toolbar" aria-label="Session gallery actions"><div class="gallery-tb-left"><span id="gallerySelectionSummary" class="gallery-tb-status ${selN ? "active" : ""}">${summaryTxt}</span>${capWarn}<span id="galleryLiveStatus" class="gallery-live-status" role="status"></span></div><div class="gallery-tb-right"><div class="gallery-preset-pill" role="group" aria-label="Images per sheet"><span class="gallery-preset-lbl" title="Number of images stitched onto each sheet PNG">Per Sheet</span>${presets}</div><div role="group" aria-label="Export actions" style="display:flex;gap:5px;flex-wrap:wrap;"><button type="button" class="btn btn-xs gallery-tb-btn mono" id="bulkSelectAllBtn" ${totalLen ? "" : "disabled"}>Select All (${totalLen})</button><button type="button" class="btn btn-xs gallery-tb-btn mono" id="bulkClearBtn" ${selN ? "" : "disabled"}>Clear</button><button type="button" class="btn btn-xs btn-focal gallery-tb-btn mono" id="bulkShareBtn" title="Share stitched sheets to Gemini" ${selN ? "" : "disabled"}>✦ Share Sheets${selN ? ` (${sheets})` : ""}</button><button type="button" class="btn btn-xs gallery-tb-btn mono" id="bulkSheetsDownloadBtn" title="Download individual stitched sheet PNGs" ${selN ? "" : "disabled"}>⬇ Sheets${selN ? ` (${sheets})` : ""}</button><button type="button" class="btn btn-xs gallery-tb-btn mono" id="bulkDownloadPngsBtn" title="Download selected individual original PNGs" ${selN ? "" : "disabled"}>⬇ PNGs${selN ? ` (${selN})` : ""}</button><button type="button" class="btn btn-xs gallery-tb-btn mono" id="bulkDownloadZipBtn" title="Download optional ZIP archive of selected originals" ${selN ? "" : "disabled"}>⬇ ZIP${selN ? ` (${selN})` : ""}</button></div></div></div>`;
  }

  function renderCardsHtml(items) {
    return items.map((v, idx) => {
      const selIdx = GallerySelect.getSelectionIndex(v), key = GallerySelect.getItemKey(v);
      const ageStr = formatRelativeAge(v.mtime), metaLbl = `${v.scope ? v.scope + " · " : ""}${v.rel_path || v.name}${ageStr ? " · " + ageStr : ""}`;
      const dimAttrs = (v.width && v.height) ? ` width="${Number(v.width)}" height="${Number(v.height)}"` : "";
      return `<div class="visual-thumb-card mono ${selIdx > 0 ? "selected" : ""}" data-idx="${idx}" data-sel-key="${esc(key)}" data-url="${esc(v.signed_url)}" data-name="${esc(v.name)}" data-rel="${esc(v.rel_path)}" data-scope="${esc(v.scope || "")}" data-meta="${esc(metaLbl)}"><button type="button" class="gallery-select-hit" data-idx="${idx}" aria-pressed="${selIdx > 0}" aria-label="${selIdx > 0 ? `Selected #${selIdx}` : "Select image"}"><span class="gallery-select-badge mono">${selIdx > 0 ? selIdx : ""}</span></button><button type="button" class="gallery-zoom-btn" data-idx="${idx}" title="Zoom / Preview" aria-label="Zoom preview">⤢</button><div class="visual-thumb-frame"><img src="${esc(v.signed_url)}" alt="${esc(v.name)}" class="visual-thumb-img" loading="lazy" decoding="async"${dimAttrs} draggable="false" /><span class="thumb-dim-badge mono hidden"></span></div><span class="thumb-lbl" title="${esc(metaLbl)}">${esc(formatThumbLabel(v.name))}</span><div class="thumb-card-ftr"><span class="thumb-age">${esc(ageStr)}</span><button type="button" class="btn btn-xs mono btn-copy-link" style="font-size:10px;padding:1px 6px;">Copy Link</button></div></div>`;
    }).join("");
  }

  function syncGalleryDomState(stageEl, sessionLen) {
    if (!stageEl) return;
    const tb = stageEl.querySelector(".gallery-toolbar");
    const sCount = typeof sessionLen === "number" ? sessionLen : (lastCtx?.getSessionCount?.() ?? 0);
    const per = SheetBuilder ? SheetBuilder.getPerSheet() : 4;
    const selN = GallerySelect.getSelectedList().length, sheets = selN ? Math.ceil(selN / per) : 0;

    stageEl.querySelectorAll(".visual-thumb-card[data-sel-key]").forEach((card) => {
      const selIdx = GallerySelect.getSelectionIndex(card.getAttribute("data-sel-key"));
      card.classList.toggle("selected", selIdx > 0);
      const hit = card.querySelector(".gallery-select-hit"), badge = card.querySelector(".gallery-select-badge");
      if (hit) { hit.setAttribute("aria-pressed", selIdx > 0 ? "true" : "false"); hit.setAttribute("aria-label", selIdx > 0 ? `Selected #${selIdx}` : "Select image"); }
      if (badge) badge.textContent = selIdx > 0 ? String(selIdx) : "";
    });
    if (!tb) return;
    tb.classList.toggle("has-selection", selN > 0);
    const sumEl = tb.querySelector("#gallerySelectionSummary");
    if (sumEl) {
      sumEl.textContent = selN ? `${selN} selected → ${sheets} sheet${sheets === 1 ? "" : "s"} (${per}/sheet)` : `Session Captures (${sCount})`;
      sumEl.classList.toggle("active", selN > 0);
    }
    let warnEl = tb.querySelector(".gallery-tb-warn");
    if (sheets > 10) {
      if (!warnEl && sumEl) { warnEl = document.createElement("span"); warnEl.className = "gallery-tb-warn mono"; sumEl.after(warnEl); }
      if (warnEl) warnEl.textContent = `${sheets} sheets · >10 Gemini cap`;
    } else if (warnEl) warnEl.remove();
    tb.querySelectorAll(".preset-btn").forEach((b) => b.setAttribute("aria-pressed", Number(b.getAttribute("data-per")) === per ? "true" : "false"));
    const cBtn = tb.querySelector("#bulkClearBtn"), sBtn = tb.querySelector("#bulkShareBtn");
    const dBtn = tb.querySelector("#bulkSheetsDownloadBtn"), pBtn = tb.querySelector("#bulkDownloadPngsBtn"), zBtn = tb.querySelector("#bulkDownloadZipBtn");
    if (cBtn) cBtn.disabled = !selN;
    if (sBtn) { sBtn.disabled = !selN; sBtn.textContent = selN ? `✦ Share Sheets (${sheets})` : "✦ Share Sheets"; }
    if (dBtn) { dBtn.disabled = !selN; dBtn.textContent = selN ? `⬇ Sheets (${sheets})` : "⬇ Sheets"; }
    if (pBtn) { pBtn.disabled = !selN; pBtn.textContent = selN ? `⬇ PNGs (${selN})` : "⬇ PNGs"; }
    if (zBtn) { zBtn.disabled = !selN; zBtn.textContent = selN ? `⬇ ZIP (${selN})` : "⬇ ZIP"; }
  }

  function bindGridCards(grid, items, stageEl, ctx) {
    if (ctx) lastCtx = ctx;
    if (!grid || !items.length) return;
    GallerySelect.bindGalleryGestures(grid, () => items, () => syncGalleryDomState(stageEl, ctx?.getSessionCount?.() ?? items.length));
    grid.querySelectorAll(".visual-thumb-card").forEach((card) => {
      const idx = Number(card.getAttribute("data-idx")), img = card.querySelector(".visual-thumb-img"), dimEl = card.querySelector(".thumb-dim-badge");
      const updateDim = () => { if (dimEl && img?.naturalWidth) { dimEl.textContent = `${img.naturalWidth}×${img.naturalHeight}`; dimEl.classList.remove("hidden"); } };
      if (img) { if (img.complete && img.naturalWidth) updateDim(); else img.addEventListener("load", updateDim, { once: true }); }
      card.querySelector(".gallery-select-hit")?.addEventListener("click", (e) => {
        e.stopPropagation();
        if (e.shiftKey) GallerySelect.handleShiftSelect(items, idx, !GallerySelect.isSelected(items[idx]));
        else GallerySelect.toggleItem(items[idx], !GallerySelect.isSelected(items[idx]), idx);
        syncGalleryDomState(stageEl, ctx?.getSessionCount?.() ?? items.length);
      });
      card.querySelector(".gallery-zoom-btn")?.addEventListener("click", (e) => { e.stopPropagation(); openLightbox(items, idx); });
      card.querySelector(".btn-copy-link")?.addEventListener("click", (e) => {
        e.stopPropagation();
        navigator.clipboard?.writeText(toAbsUrl(card.getAttribute("data-url")));
        const b = e.currentTarget; b.textContent = "Copied!"; setTimeout(() => { b.textContent = "Copy Link"; }, 1200);
      });
      card.addEventListener("click", (e) => {
        if (e.target.closest("button") || GallerySelect.shouldSuppressClick()) return;
        if (GallerySelect.getSelectedList().length > 0 || e.shiftKey) {
          if (e.shiftKey) GallerySelect.handleShiftSelect(items, idx, !GallerySelect.isSelected(items[idx]));
          else GallerySelect.toggleItem(items[idx], !GallerySelect.isSelected(items[idx]), idx);
          syncGalleryDomState(stageEl, ctx?.getSessionCount?.() ?? items.length);
        } else openLightbox(items, idx);
      });
    });
  }

  function bindToolbarActions(stageEl, sessionItems, ctx) {
    if (ctx) lastCtx = ctx;
    const tb = stageEl.querySelector(".gallery-toolbar");
    if (!tb) return;
    const setStatus = (msg) => { const el = tb.querySelector("#galleryLiveStatus"); if (el) el.textContent = msg || ""; };
    tb.querySelectorAll(".preset-btn").forEach((b) => b.addEventListener("click", () => { SheetBuilder?.setPerSheet(Number(b.getAttribute("data-per"))); syncGalleryDomState(stageEl, sessionItems.length); }));
    tb.querySelector("#bulkSelectAllBtn")?.addEventListener("click", () => { GallerySelect.selectAll(sessionItems); syncGalleryDomState(stageEl, sessionItems.length); });
    tb.querySelector("#bulkClearBtn")?.addEventListener("click", () => { GallerySelect.clearSelection(); syncGalleryDomState(stageEl, sessionItems.length); setStatus(""); });
    tb.querySelector("#bulkShareBtn")?.addEventListener("click", () => SheetBuilder?.shareSheetsToGemini(GallerySelect.getSelectedList(), ctx.repoSlug, SheetBuilder.getPerSheet(), openLightbox, setStatus));
    tb.querySelector("#bulkSheetsDownloadBtn")?.addEventListener("click", () => SheetBuilder?.downloadSheets(GallerySelect.getSelectedList(), ctx.repoSlug, SheetBuilder.getPerSheet(), setStatus));
    tb.querySelector("#bulkDownloadPngsBtn")?.addEventListener("click", () => GallerySelect.downloadSequentialPngs(setStatus, ctx.onUnauthorized));
    tb.querySelector("#bulkDownloadZipBtn")?.addEventListener("click", () => {
      if (ctx.isDemo?.()) {
        setStatus("ZIP archive export requires an unlocked live session; use ⬇ Sheets or ⬇ PNGs in Demo Mode.");
        return;
      }
      GallerySelect.downloadZip(ctx.sessionId, ctx.getApiHeaders, ctx.getBaseApiPath, ctx.onUnauthorized);
    });
  }

  return { formatRelativeAge, formatThumbLabel, resetLightboxState, openLightbox, renderToolbarHtml, renderCardsHtml, syncGalleryDomState, bindGridCards, bindToolbarActions };
});
