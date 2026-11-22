/* SPDX-License-Identifier: Apache-2.0 */
/* AGY-Nexus /web/v9 — Lightbox Viewer (Fit | 1:1 Native Zoom & 2-Up Compare, SVG Icons Only) */
(() => {
  const V9 = window.AgyV9;
  const CHK_SVG = `<svg width="12" height="12" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M3.5 8.5L6.5 11.5L12.5 4.5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  const lbState = {
    items: [],
    idx: 0,
    zoomMode: "fit",
    compareMode: false,
    compareItems: [],
    onSelectToggle: null,
  };

  function getCurrentItem() {
    return lbState.items[lbState.idx] || null;
  }

  function updateToolbarButtons() {
    const cur = getCurrentItem();
    const fitBtn = document.getElementById("v9LbFitBtn");
    const natBtn = document.getElementById("v9LbNativeBtn");
    const cmpBtn = document.getElementById("v9LbCompareBtn");
    const selBtn = document.getElementById("v9LbSelBtn");
    const prevBtn = document.getElementById("v9LbPrevBtn");
    const nextBtn = document.getElementById("v9LbNextBtn");
    const copyBtn = document.getElementById("v9LbCopyLinkBtn");

    if (fitBtn) fitBtn.setAttribute("aria-pressed", String(!lbState.compareMode && lbState.zoomMode === "fit"));
    if (natBtn) natBtn.setAttribute("aria-pressed", String(!lbState.compareMode && lbState.zoomMode === "native"));
    if (cmpBtn) {
      cmpBtn.setAttribute("aria-pressed", String(lbState.compareMode));
      cmpBtn.disabled = lbState.items.length < 2 && lbState.compareItems.length < 2;
    }
    if (prevBtn) prevBtn.disabled = lbState.compareMode || lbState.idx <= 0;
    if (nextBtn) nextBtn.disabled = lbState.compareMode || lbState.idx >= lbState.items.length - 1;
    if (selBtn) {
      const selected = Boolean(cur && window.GallerySelect && window.GallerySelect.isSelected(cur));
      selBtn.classList.toggle("hidden", lbState.compareMode || !cur);
      selBtn.innerHTML = `${CHK_SVG}<span>${selected ? "Selected" : "Select"}</span>`;
      selBtn.setAttribute("aria-pressed", String(selected));
    }
    if (copyBtn) copyBtn.classList.toggle("hidden", lbState.compareMode || !cur || !cur.workspace_url);
  }

  function renderLightboxStage() {
    const titleEl = document.getElementById("v9LbTitle");
    const metaEl = document.getElementById("v9LbMeta");
    const stageEl = document.getElementById("v9LbStage");
    const dlgEl = document.getElementById("v9LightboxDialog");
    if (!stageEl) return;
    updateToolbarButtons();

    const isCompare = Boolean(lbState.compareMode && lbState.compareItems.length >= 2);
    dlgEl?.classList.toggle("is-compare", isCompare);
    stageEl.classList.toggle("is-compare", isCompare);

    if (isCompare) {
      const [a, b] = lbState.compareItems;
      if (titleEl) titleEl.textContent = `Compare: ${a.name || "A"} vs ${b.name || "B"}`;
      if (metaEl) metaEl.textContent = "Side-by-side comparison";
      stageEl.classList.remove("is-native");
      stageEl.innerHTML = `<div class="va-compare-grid v9-compare-grid" id="v9CmpGrid" data-orient="side-by-side">
        <figure class="v9-cmp-figure">
          <img class="va-media-contain" src="${V9.escHtml(a.signed_url || a.url)}" alt="${V9.escHtml(a.name || "Capture A")}" />
          <figcaption class="v9-cmp-cap" data-cmp-cap="0">${V9.escHtml(a.name || "Capture A")}</figcaption>
        </figure>
        <figure class="v9-cmp-figure">
          <img class="va-media-contain" src="${V9.escHtml(b.signed_url || b.url)}" alt="${V9.escHtml(b.name || "Capture B")}" />
          <figcaption class="v9-cmp-cap" data-cmp-cap="1">${V9.escHtml(b.name || "Capture B")}</figcaption>
        </figure>
      </div>`;
      stageEl.querySelectorAll("img").forEach((img, idx) => {
        img.addEventListener("load", () => {
          const cap = stageEl.querySelector(`[data-cmp-cap="${idx}"]`);
          const name = idx === 0 ? (a.name || "A") : (b.name || "B");
          if (cap && img.naturalWidth) cap.textContent = `${name} (${img.naturalWidth}×${img.naturalHeight})`;
        });
      });
      return;
    }

    const cur = getCurrentItem();
    if (!cur) return;
    const isNative = lbState.zoomMode === "native";
    if (titleEl) titleEl.textContent = cur.name || "Image Preview";
    if (metaEl) metaEl.textContent = cur.meta || "Loading dimensions...";
    stageEl.classList.toggle("is-native", isNative);
    stageEl.innerHTML = `<img id="v9LbImg" class="${isNative ? "v9-lb-img-native" : "v9-lb-img-fit"}" src="${V9.escHtml(cur.signed_url || cur.url)}" alt="${V9.escHtml(cur.name || "Preview")}" />`;
    const imgEl = stageEl.querySelector("#v9LbImg");
    imgEl?.addEventListener("load", () => {
      if (metaEl && imgEl.naturalWidth) {
        const sizeNote = cur.size ? ` · ${V9.fmtBytes(cur.size)}` : "";
        metaEl.textContent = `${imgEl.naturalWidth} × ${imgEl.naturalHeight} px${sizeNote} · ${isNative ? "1:1 pixel zoom (scroll to pan)" : "Fit to viewport"}`;
      }
    });
  }

  function openSingle(items, index, onSelectToggle) {
    lbState.items = Array.isArray(items) ? items : [];
    lbState.idx = Math.max(0, Math.min(lbState.items.length - 1, Number(index || 0)));
    lbState.zoomMode = "fit";
    lbState.compareMode = false;
    lbState.onSelectToggle = onSelectToggle || null;
    lbState.compareItems = lbState.items.length >= 2
      ? [lbState.items[lbState.idx], lbState.items[(lbState.idx + 1) % lbState.items.length]]
      : [];
    renderLightboxStage();
    document.getElementById("v9LightboxDialog")?.showModal();
  }

  function openCompare(pair, allItems, onSelectToggle) {
    if (!Array.isArray(pair) || pair.length < 2) return;
    lbState.items = Array.isArray(allItems) && allItems.length ? allItems : pair;
    lbState.compareItems = pair.slice(0, 2);
    lbState.idx = Math.max(0, lbState.items.indexOf(pair[0]));
    lbState.zoomMode = "fit";
    lbState.compareMode = true;
    lbState.onSelectToggle = onSelectToggle || null;
    renderLightboxStage();
    document.getElementById("v9LightboxDialog")?.showModal();
  }

  function reset() {
    const dlg = document.getElementById("v9LightboxDialog");
    if (dlg) {
      dlg.classList.remove("is-compare");
      if (dlg.open) dlg.close();
    }
    lbState.items = [];
    lbState.compareItems = [];
    lbState.idx = 0;
    lbState.zoomMode = "fit";
    lbState.compareMode = false;
    lbState.onSelectToggle = null;
    const stageEl = document.getElementById("v9LbStage");
    if (stageEl) {
      stageEl.classList.remove("is-compare", "is-native");
      stageEl.innerHTML = "";
    }
  }

  function bindEvents() {
    const dlg = document.getElementById("v9LightboxDialog");
    document.getElementById("v9LbCloseBtn")?.addEventListener("click", () => dlg?.close());
    document.getElementById("v9LbFitBtn")?.addEventListener("click", () => {
      lbState.compareMode = false;
      lbState.zoomMode = "fit";
      renderLightboxStage();
    });
    document.getElementById("v9LbNativeBtn")?.addEventListener("click", () => {
      lbState.compareMode = false;
      lbState.zoomMode = "native";
      renderLightboxStage();
    });
    document.getElementById("v9LbCompareBtn")?.addEventListener("click", () => {
      const sel = window.GallerySelect ? window.GallerySelect.getSelectedList() : [];
      if (sel.length >= 2) lbState.compareItems = sel.slice(0, 2);
      else if (lbState.items.length >= 2) {
        lbState.compareItems = [lbState.items[lbState.idx], lbState.items[(lbState.idx + 1) % lbState.items.length]];
      }
      if (lbState.compareItems.length >= 2) {
        lbState.compareMode = true;
        renderLightboxStage();
      }
    });
    document.getElementById("v9LbPrevBtn")?.addEventListener("click", () => {
      if (lbState.idx > 0) { lbState.idx -= 1; renderLightboxStage(); }
    });
    document.getElementById("v9LbNextBtn")?.addEventListener("click", () => {
      if (lbState.idx < lbState.items.length - 1) { lbState.idx += 1; renderLightboxStage(); }
    });
    document.getElementById("v9LbSelBtn")?.addEventListener("click", () => {
      const cur = getCurrentItem();
      if (!cur || !window.GallerySelect) return;
      const checked = !window.GallerySelect.isSelected(cur);
      window.GallerySelect.toggleItem(cur, checked, lbState.idx);
      updateToolbarButtons();
      if (typeof lbState.onSelectToggle === "function") lbState.onSelectToggle();
    });
    document.getElementById("v9LbCopyLinkBtn")?.addEventListener("click", () => {
      const cur = getCurrentItem();
      if (cur && cur.workspace_url) V9.copyText(V9.toAbsUrl(cur.workspace_url), "Copied 7d capture link");
    });
    document.addEventListener("keydown", (e) => {
      if (!dlg?.open || lbState.compareMode) return;
      if (e.key === "ArrowLeft" && lbState.idx > 0) { lbState.idx -= 1; renderLightboxStage(); }
      if (e.key === "ArrowRight" && lbState.idx < lbState.items.length - 1) { lbState.idx += 1; renderLightboxStage(); }
    });
  }

  bindEvents();
  V9.Lightbox = { openSingle, openCompare, reset };
})();
