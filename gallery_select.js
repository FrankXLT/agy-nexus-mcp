// AGY-NEXUS Overwatch — Ordered Multi-Select, Google Photos Press-and-Glide Gestures, Direct PNGs & ZIP (v3.2.2)
(function (root, factory) {
  if (typeof define === "function" && define.amd) {
    define([], factory);
  } else if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.GallerySelect = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const selectedItems = new Map(); // scope/rel_path -> item object (insertion order = 1..K badge index)
  const DOWNLOAD_STAGGER_MS = 220;
  let lastSelectedIndex = -1;
  let suppressNextClickUntil = 0;
  let pngDownloadBusy = false;
  let activeGestureCleanup = null;

  const getItemKey = (it) => (typeof it === "string" ? it : (it?.scope ? `${it.scope}/${it.rel_path || it.name || ""}` : (it?.rel_path || it?.name || "")));
  const clearSelection = () => { selectedItems.clear(); lastSelectedIndex = -1; };
  const getSelectedList = () => Array.from(selectedItems.values());
  const isSelected = (itemOrKey) => { const k = getItemKey(itemOrKey); return k ? selectedItems.has(k) : false; };
  const shouldSuppressClick = () => Date.now() < suppressNextClickUntil;

  function getSelectionIndex(itemOrKey) {
    const targetKey = getItemKey(itemOrKey);
    if (!targetKey || !selectedItems.has(targetKey)) return 0;
    let idx = 1;
    for (const k of selectedItems.keys()) {
      if (k === targetKey) return idx;
      idx += 1;
    }
    return 0;
  }

  function toggleItem(item, checked, index) {
    const key = getItemKey(item);
    if (!key) return;
    if (checked) {
      if (!selectedItems.has(key)) selectedItems.set(key, item);
      if (typeof index === "number") lastSelectedIndex = index;
    } else {
      selectedItems.delete(key);
    }
  }

  function handleShiftSelect(items, currentIndex, checked) {
    if (lastSelectedIndex === -1 || lastSelectedIndex === currentIndex) {
      toggleItem(items[currentIndex], checked, currentIndex);
      return;
    }
    const start = Math.min(lastSelectedIndex, currentIndex), end = Math.max(lastSelectedIndex, currentIndex);
    for (let i = start; i <= end; i++) {
      if (items[i]) toggleItem(items[i], checked, i);
    }
  }

  const selectAll = (items) => (items || []).forEach((it, idx) => toggleItem(it, true, idx));
  function cleanupGestures() { if (typeof activeGestureCleanup === "function") { const fn = activeGestureCleanup; activeGestureCleanup = null; fn(); } }

  const SAFE_DL_URL_RE = /^(?:\/web\/media\/|https?:\/\/|data:image\/|blob:)/i;
  const cleanDlName = (name, idx) => String(name || "").split(/[\\/]/).pop().replace(/[^a-zA-Z0-9_.-]+/g, "_") || `capture_${idx || 1}.png`;

  function triggerDownload(target, filename, idx) {
    const isBlob = target && typeof target !== "string";
    if (!isBlob && !SAFE_DL_URL_RE.test(String(target || ""))) return false;
    const href = isBlob ? URL.createObjectURL(target) : String(target || "");
    if (!href) return false;
    const a = document.createElement("a");
    a.href = href;
    a.download = cleanDlName(filename, idx);
    document.body.appendChild(a);
    a.click();
    a.remove();
    if (isBlob) setTimeout(() => URL.revokeObjectURL(href), 4000);
    return true;
  }

  async function downloadZip(convId, getApiHeadersFn, getBaseApiPathFn, onUnauthorizedFn) {
    const list = getSelectedList();
    if (!list.length) return;
    try {
      const resp = await fetch(getBaseApiPathFn() + `/web/api/sessions/${encodeURIComponent(convId)}/download-zip`, {
        method: "POST",
        headers: { ...getApiHeadersFn(), "Content-Type": "application/json" },
        body: JSON.stringify({ files: list.map((i) => (i.scope ? `${i.scope}/${i.rel_path}` : i.rel_path)) }),
      });
      if (resp.status === 401 && typeof onUnauthorizedFn === "function") return onUnauthorizedFn();
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        return alert(`Download failed: ${err.error || resp.statusText}`);
      }
      triggerDownload(await resp.blob(), `captures_${convId.slice(0, 8)}_${list.length}.zip`);
    } catch (e) {
      alert(`ZIP download error: ${e.message}`);
    }
  }

  async function downloadSequentialPngs(onStatus, onUnauthorizedFn) {
    const selected = getSelectedList();
    if (!selected.length || pngDownloadBusy) return 0;
    const valid = selected.filter((it) => it && it.signed_url);
    if (!valid.length) { if (typeof onStatus === "function") onStatus("No downloadable image URLs"); return 0; }
    pngDownloadBusy = true;
    let downloaded = 0, failed = 0;
    try {
      for (let i = 0; i < valid.length; i++) {
        const it = valid[i], fname = cleanDlName(it.name || String(it.rel_path || "").split("/").pop(), i + 1);
        if (!SAFE_DL_URL_RE.test(String(it.signed_url || ""))) { failed += 1; continue; }
        if (typeof onStatus === "function") onStatus(`Downloading PNG ${i + 1}/${valid.length}...`);
        try {
          const resp = await fetch(it.signed_url);
          if (resp.status === 401) { if (typeof onUnauthorizedFn === "function") onUnauthorizedFn(); if (typeof onStatus === "function") onStatus("Session locked (401)"); return downloaded; }
          if (!resp.ok) { const e = new Error(`HTTP ${resp.status}`); e.httpStatus = resp.status; throw e; }
          if (triggerDownload(await resp.blob(), fname, i + 1)) downloaded += 1; else failed += 1;
        } catch (err) {
          if (!err?.httpStatus && triggerDownload(it.signed_url, fname, i + 1)) downloaded += 1;
          else failed += 1;
        }
        if (i < valid.length - 1) await new Promise((r) => setTimeout(r, DOWNLOAD_STAGGER_MS));
      }
      if (typeof onStatus === "function") {
        onStatus(downloaded ? `Downloaded ${downloaded} PNG${downloaded === 1 ? "" : "s"}${failed ? ` (${failed} failed)` : ""}` : "PNG download failed");
      }
      return downloaded;
    } finally { pngDownloadBusy = false; }
  }

  function applyMarqueeRect(grid, items, x1, y1, x2, y2, syncDomFn) {
    let changed = false;
    grid.querySelectorAll(".visual-thumb-card").forEach((card) => {
      const idx = Number(card.getAttribute("data-idx"));
      const r = card.getBoundingClientRect();
      if (!(r.right < x1 || r.left > x2 || r.bottom < y1 || r.top > y2) && items[idx] && !isSelected(items[idx])) {
        toggleItem(items[idx], true, idx);
        changed = true;
      }
    });
    if (changed && typeof syncDomFn === "function") syncDomFn();
  }

  function bindGalleryGestures(grid, getItemsFn, syncDomFn) {
    cleanupGestures();
    if (!grid) return;
    grid.addEventListener("dragstart", (e) => e.preventDefault());

    let g = null;
    const stopAutoScroll = () => { if (g?.rafId) { cancelAnimationFrame(g.rafId); g.rafId = 0; } };
    const tickAutoScroll = () => {
      if (!g || !g.sweeping || !grid.isConnected) return cleanup();
      if (g.lastY < 64) { window.scrollBy(0, -10); g.rafId = requestAnimationFrame(tickAutoScroll); }
      else if (g.lastY > window.innerHeight - 64) { window.scrollBy(0, 10); g.rafId = requestAnimationFrame(tickAutoScroll); }
      else g.rafId = 0;
    };
    const applyTouchSweepAt = (cx, cy) => {
      const card = document.elementFromPoint(cx, cy)?.closest(".visual-thumb-card");
      if (!card || !grid.contains(card)) return;
      const idx = Number(card.getAttribute("data-idx")), item = getItemsFn()[idx];
      if (!item || isSelected(item) === g.targetAction) return;
      toggleItem(item, g.targetAction, idx);
      if (typeof syncDomFn === "function") syncDomFn();
    };
    const onContextMenu = (e) => { if (g && (g.sweeping || g.holdTimer)) e.preventDefault(); };
    const onTouchMove = (e) => { if (g && g.sweeping) e.preventDefault(); };
    function cleanup() {
      if (!g) return;
      if (g.holdTimer) clearTimeout(g.holdTimer);
      stopAutoScroll();
      if (g.box) g.box.remove();
      grid.classList.remove("is-sweeping");
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
      window.removeEventListener("pointercancel", onPointerUp);
      window.removeEventListener("touchmove", onTouchMove);
      window.removeEventListener("contextmenu", onContextMenu);
      window.removeEventListener("blur", cleanup);
      if (activeGestureCleanup === cleanup) activeGestureCleanup = null;
      g = null;
    }
    function onPointerMove(e) {
      if (!g || e.pointerId !== g.pointerId) return;
      if (!grid.isConnected || (!g.isTouch && (e.buttons & 1) === 0)) return cleanup();
      const dist = Math.hypot(e.clientX - g.startX, e.clientY - g.startY);
      if (g.isTouch) {
        if (!g.sweeping) { if (dist > 10) cleanup(); return; }
        g.lastY = e.clientY;
        applyTouchSweepAt(e.clientX, e.clientY);
        if (!g.rafId && (g.lastY < 64 || g.lastY > window.innerHeight - 64)) g.rafId = requestAnimationFrame(tickAutoScroll);
        return;
      }
      if (!g.marquee) {
        if (dist <= 6) return;
        g.marquee = true;
        suppressNextClickUntil = Date.now() + 350;
        g.box = document.createElement("div");
        g.box.className = "gallery-marquee-box";
        document.body.appendChild(g.box);
      }
      const x1 = Math.min(g.startX, e.clientX), y1 = Math.min(g.startY, e.clientY);
      const x2 = Math.max(g.startX, e.clientX), y2 = Math.max(g.startY, e.clientY);
      Object.assign(g.box.style, { left: `${x1}px`, top: `${y1}px`, width: `${x2 - x1}px`, height: `${y2 - y1}px` });
      applyMarqueeRect(grid, getItemsFn(), x1, y1, x2, y2, syncDomFn);
    }
    function onPointerUp(e) {
      if (!g || e.pointerId !== g.pointerId) return;
      if (g.sweeping || g.marquee) suppressNextClickUntil = Date.now() + 350;
      cleanup();
    }

    grid.addEventListener("pointerdown", (e) => {
      if ((e.pointerType === "mouse" && e.button !== 0) || e.target.closest("button, a, summary")) return;
      cleanup();
      const isTouch = e.pointerType === "touch" || e.pointerType === "pen";
      const startCard = e.target.closest(".visual-thumb-card");
      if (isTouch && !startCard) return;
      g = { pointerId: e.pointerId, isTouch, startX: e.clientX, startY: e.clientY, lastY: e.clientY, holdTimer: 0, sweeping: false, marquee: false, targetAction: true, box: null, rafId: 0 };
      activeGestureCleanup = cleanup;
      if (isTouch) {
        const startIdx = Number(startCard.getAttribute("data-idx")), startItem = getItemsFn()[startIdx];
        if (!startItem) { g = null; activeGestureCleanup = null; return; }
        g.holdTimer = setTimeout(() => {
          if (!g || !grid.isConnected) return cleanup();
          g.holdTimer = 0; g.sweeping = true; g.targetAction = !isSelected(startItem);
          suppressNextClickUntil = Date.now() + 450;
          toggleItem(startItem, g.targetAction, startIdx);
          if (typeof syncDomFn === "function") syncDomFn();
          grid.classList.add("is-sweeping");
          if (typeof navigator !== "undefined" && navigator.vibrate) navigator.vibrate(15);
        }, 260);
        window.addEventListener("touchmove", onTouchMove, { passive: false });
        window.addEventListener("contextmenu", onContextMenu);
      }
      window.addEventListener("pointermove", onPointerMove);
      window.addEventListener("pointerup", onPointerUp);
      window.addEventListener("pointercancel", onPointerUp);
      window.addEventListener("blur", cleanup);
    });
  }

  return {
    getItemKey, clearSelection, getSelectedList, isSelected, getSelectionIndex,
    toggleItem, handleShiftSelect, selectAll, shouldSuppressClick, cleanupGestures,
    downloadZip, downloadSequentialPngs, bindGalleryGestures,
  };
});
