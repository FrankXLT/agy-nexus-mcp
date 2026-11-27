/* SPDX-License-Identifier: Apache-2.0 */
/* AGY-Nexus Session Screenshot Gallery — Progressive Enhancement */

(() => {
  "use strict";

  const THEME_STORAGE_KEY = "agy_gallery_theme";
  const THEMES = ["white", "paper", "dark-paper", "dark"];
  const THEME_LABELS = { white: "White", paper: "Paper", "dark-paper": "Dark Paper", dark: "Dark" };
  const $id = (id) => document.getElementById(id);
  const isValidTheme = (v) => typeof v === "string" && THEMES.includes(v);

  function readUrlTheme() {
    try {
      const v = new URLSearchParams(window.location.search).get("theme");
      return isValidTheme(v) ? v : "";
    } catch (_) { return ""; }
  }

  function storageTheme(value) {
    try {
      if (value !== undefined) { window.localStorage.setItem(THEME_STORAGE_KEY, value); return value; }
      const v = window.localStorage.getItem(THEME_STORAGE_KEY);
      return isValidTheme(v) ? v : "";
    } catch (_) { return ""; }
  }

  function safeUrl(raw) {
    if (typeof raw !== "string") return "";
    const clean = String(raw || "").trim().replace(/[\u0000-\u0020\u007f]+/g, "");
    return /^(?:\/web\/media\/|https?:\/\/)/i.test(clean) ? clean : "";
  }

  function formatBytes(bytes) {
    if (typeof bytes !== "number" || !Number.isFinite(bytes) || bytes < 0) return "";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / 1048576).toFixed(2) + " MB";
  }

  function parseGalleryData() {
    const el = $id("galleryData");
    if (!el) return [];
    try {
      const parsed = JSON.parse(el.textContent || "[]");
      if (Array.isArray(parsed)) return parsed;
      if (parsed && typeof parsed === "object") {
        const list = parsed.items || parsed.images || parsed.screenshots || parsed.captures;
        return Array.isArray(list) ? list : [];
      }
    } catch (_) {}
    return [];
  }

  const isOutsideRect = (r, ev) => ev.clientX < r.left || ev.clientX > r.right || ev.clientY < r.top || ev.clientY > r.bottom;
  const pickSafeUrl = (...cands) => cands.map(safeUrl).find(Boolean) || "";

  function resolveItem(items, gridRoot, index) {
    const entry = items[index] && typeof items[index] === "object" ? items[index] : {};
    const btn = gridRoot ? gridRoot.querySelector('[data-gal-index="' + index + '"]') : null;
    const thumbImg = btn ? btn.querySelector("img") : null;
    const card = btn ? btn.closest(".gal-card") : null;
    const rawLink = card ? card.querySelector(".gal-raw-link, .gal-card-foot a") : null;
    const url = pickSafeUrl(entry.signed_url, entry.url, entry.src, entry.raw_url, entry.rawUrl, thumbImg && thumbImg.getAttribute("src"));
    const rawUrl = pickSafeUrl(entry.raw_url, entry.rawUrl, entry.signed_url, entry.url, rawLink && rawLink.getAttribute("href"), url);
    const title = String(entry.filename || entry.name || entry.title || entry.label || (thumbImg && thumbImg.alt) || "Screenshot #" + (index + 1));
    const seqRaw = entry.seq ?? entry.index;
    const seqNum = typeof seqRaw === "number" ? seqRaw : (Number.parseInt(String(seqRaw || ""), 10) || index + 1);
    const sizeBytes = entry.size_bytes ?? entry.sizeBytes ?? entry.bytes ?? entry.size;
    const sizeText = String(entry.size_human || entry.sizeHuman || entry.size_label || entry.sizeLabel || (typeof entry.size === "string" ? entry.size : formatBytes(sizeBytes)));
    return {
      url, rawUrl, title, alt: String(entry.alt || title), seqNum, sizeText,
      width: Number(entry.width || entry.w || 0), height: Number(entry.height || entry.h || 0),
    };
  }

  function formatMeta(item, index, total, natW, natH) {
    const parts = ["#" + String(item.seqNum).padStart(2, "0") + " (" + (index + 1) + "/" + total + ")"];
    const w = natW > 0 ? natW : item.width;
    const h = natH > 0 ? natH : item.height;
    if (w > 0 && h > 0) parts.push(w + "\u00d7" + h);
    if (item.sizeText) parts.push(item.sizeText);
    return parts.join(" \u00b7 ");
  }

  function initTheme() {
    const themeBtn = $id("galThemeBtn");
    const mq = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
    const urlTheme = readUrlTheme();
    const savedTheme = storageTheme();
    let pinnedTheme = Boolean(urlTheme || savedTheme);

    function applyTheme(theme, persist) {
      const next = isValidTheme(theme) ? theme : "white";
      document.documentElement.dataset.theme = next;
      if (persist) storageTheme(next);
      if (themeBtn) {
        const label = THEME_LABELS[next] || next;
        themeBtn.textContent = "Theme: " + label;
        themeBtn.setAttribute("aria-label", "Switch color theme (current: " + label + ")");
      }
    }

    applyTheme(urlTheme || savedTheme || (mq && mq.matches ? "dark" : "white"), false);
    if (mq && mq.addEventListener) {
      mq.addEventListener("change", (ev) => { if (!pinnedTheme) applyTheme(ev.matches ? "dark" : "white", false); });
    }
    if (themeBtn) {
      themeBtn.addEventListener("click", () => {
        const idx = THEMES.indexOf(document.documentElement.dataset.theme || "white");
        pinnedTheme = true;
        applyTheme(THEMES[(idx + 1) % THEMES.length], true);
      });
    }
  }

  function wireLightboxGestures(dlg, lbStage, getZoom, onStep) {
    document.addEventListener("keydown", (ev) => {
      if (!dlg.open || ev.metaKey || ev.ctrlKey || ev.altKey) return;
      if (ev.key === "ArrowLeft") { ev.preventDefault(); onStep(-1); }
      else if (ev.key === "ArrowRight") { ev.preventDefault(); onStep(1); }
    });
    const swipeTarget = lbStage || dlg;
    let startX = null, startY = null;
    swipeTarget.addEventListener("touchstart", (ev) => {
      if (!dlg.open || ev.touches.length !== 1) return;
      startX = ev.touches[0].clientX; startY = ev.touches[0].clientY;
    }, { passive: true });
    swipeTarget.addEventListener("touchend", (ev) => {
      if (!dlg.open || startX === null || ev.changedTouches.length !== 1) return;
      const dx = ev.changedTouches[0].clientX - startX;
      const dy = ev.changedTouches[0].clientY - startY;
      startX = null; startY = null;
      const canPanX = getZoom() === "native" && lbStage && lbStage.scrollWidth > lbStage.clientWidth + 2;
      if (!canPanX && Math.abs(dx) > 48 && Math.abs(dx) > Math.abs(dy) * 1.2) onStep(dx < 0 ? 1 : -1);
    }, { passive: true });
    if (!("closedBy" in HTMLDialogElement.prototype)) {
      let downOutside = false;
      dlg.addEventListener("pointerdown", (ev) => {
        downOutside = dlg.open && ev.target === dlg && isOutsideRect(dlg.getBoundingClientRect(), ev);
      });
      dlg.addEventListener("pointerup", (ev) => {
        if (downOutside && dlg.open && ev.target === dlg && isOutsideRect(dlg.getBoundingClientRect(), ev)) dlg.close();
        downOutside = false;
      });
      dlg.addEventListener("close", () => { downOutside = false; });
    }
  }

  function initLightbox(items) {
    const gridRoot = $id("galGrid"), dlg = $id("galLightbox"), lbImg = $id("galLbImg");
    const lbTitle = $id("galLbTitle"), lbMeta = $id("galLbMeta"), lbRawLink = $id("galLbRawLink");
    const fitBtn = $id("galLbFitBtn"), nativeBtn = $id("galLbNativeBtn");
    const prevBtn = $id("galLbPrevBtn"), nextBtn = $id("galLbNextBtn"), closeBtn = $id("galLbCloseBtn");
    const lbStage = $id("galLbStage") || (lbImg && lbImg.parentElement !== dlg ? lbImg.parentElement : null);
    const totalCount = Math.max(items.length, gridRoot ? gridRoot.querySelectorAll("[data-gal-index]").length : 0);
    if (!dlg || !lbImg || totalCount <= 0) return;

    let currentIndex = -1, zoomMode = "fit";

    function setZoom(mode) {
      zoomMode = mode === "native" ? "native" : "fit";
      const isFit = zoomMode === "fit";
      if (fitBtn) fitBtn.setAttribute("aria-pressed", String(isFit));
      if (nativeBtn) nativeBtn.setAttribute("aria-pressed", String(!isFit));
      for (const el of [lbStage, lbImg]) {
        if (!el) continue;
        el.classList.toggle("is-fit", isFit);
        el.classList.toggle("is-native", !isFit);
      }
    }

    function showIndex(idx) {
      currentIndex = ((idx % totalCount) + totalCount) % totalCount;
      const item = resolveItem(items, gridRoot, currentIndex);
      const imgSrc = safeUrl(item.url);
      const rawHref = safeUrl(item.rawUrl);
      if (lbTitle) lbTitle.textContent = item.title;
      if (lbRawLink) rawHref ? lbRawLink.setAttribute("href", rawHref) : lbRawLink.removeAttribute("href");
      if (lbMeta) lbMeta.textContent = formatMeta(item, currentIndex, totalCount, 0, 0);
      lbImg.setAttribute("alt", item.alt);
      imgSrc ? lbImg.setAttribute("src", imgSrc) : lbImg.removeAttribute("src");
      if (lbImg.complete && lbImg.naturalWidth > 0 && lbMeta) {
        lbMeta.textContent = formatMeta(item, currentIndex, totalCount, lbImg.naturalWidth, lbImg.naturalHeight);
      }
      if (prevBtn) prevBtn.disabled = totalCount <= 1;
      if (nextBtn) nextBtn.disabled = totalCount <= 1;
    }

    lbImg.addEventListener("load", () => {
      if (currentIndex < 0 || !dlg.open || !lbMeta || lbImg.naturalWidth <= 0) return;
      lbMeta.textContent = formatMeta(resolveItem(items, gridRoot, currentIndex), currentIndex, totalCount, lbImg.naturalWidth, lbImg.naturalHeight);
    });

    (gridRoot || document).addEventListener("click", (ev) => {
      const btn = ev.target instanceof Element ? ev.target.closest("[data-gal-index]") : null;
      if (!btn) return;
      const idx = Number.parseInt(btn.getAttribute("data-gal-index") || "", 10);
      if (!Number.isFinite(idx) || idx < 0 || idx >= totalCount) return;
      ev.preventDefault();
      if (!dlg.open) setZoom("fit");
      showIndex(idx);
      if (!dlg.open) typeof dlg.showModal === "function" ? dlg.showModal() : dlg.setAttribute("open", "");
    });

    const onClick = (el, fn) => { if (el) el.addEventListener("click", fn); };
    onClick(fitBtn, () => setZoom("fit"));
    onClick(nativeBtn, () => setZoom("native"));
    onClick(prevBtn, () => showIndex(currentIndex - 1));
    onClick(nextBtn, () => showIndex(currentIndex + 1));
    onClick(closeBtn, () => { if (dlg.open) dlg.close(); });
    wireLightboxGestures(dlg, lbStage, () => zoomMode, (delta) => showIndex(currentIndex + delta));
  }

  initTheme();
  initLightbox(parseGalleryData());
})();
