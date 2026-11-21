// AGY-NEXUS Overwatch — Drag-Resizable Workspace Tree Splitter & Width Persistence (v3.2.5)
(function (root, factory) {
  if (typeof define === "function" && define.amd) {
    define([], factory);
  } else if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.WorkspaceResizer = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const STORAGE_KEY = "nexus_tree_width";
  const MIN_W = 220;
  const MAX_W = 480;
  let initialized = false;

  function clampWidth(rawWidth, viewportWidth) {
    const vp = Number(viewportWidth || (typeof window !== "undefined" ? window.innerWidth : 1440)) || 1440;
    const dynamicMax = Math.max(MIN_W, Math.min(MAX_W, vp - 360));
    const num = Math.round(Number(rawWidth) || 0);
    return Math.max(MIN_W, Math.min(dynamicMax, num));
  }

  function getStoredWidth() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      const val = Number(raw);
      return Number.isFinite(val) && val >= MIN_W ? clampWidth(val) : null;
    } catch (_) {
      return null;
    }
  }

  function syncAriaValue(resizer, pane) {
    if (!resizer) return;
    const stored = getStoredWidth();
    const isHiddenRail = pane && (pane.classList.contains("slim") || pane.classList.contains("zen"));
    const curW = stored || (!isHiddenRail && pane ? Math.round(pane.getBoundingClientRect().width || 300) : 300);
    resizer.setAttribute("aria-valuenow", String(clampWidth(curW)));
  }

  function applyWidth(layout, resizer, pane, widthPx, persist) {
    if (!layout) return;
    const clamped = clampWidth(widthPx);
    layout.style.setProperty("--ws-tree-custom-w", `${clamped}px`);
    if (persist) {
      try { localStorage.setItem(STORAGE_KEY, String(clamped)); } catch (_) {}
    }
    syncAriaValue(resizer, pane);
  }

  function resetWidth(layout, resizer, pane) {
    if (!layout) return;
    layout.style.removeProperty("--ws-tree-custom-w");
    try { localStorage.removeItem(STORAGE_KEY); } catch (_) {}
    syncAriaValue(resizer, pane);
  }

  function init() {
    if (initialized) return;
    const layout = document.getElementById("workspaceLayout") || document.querySelector(".workspace-layout");
    const pane = document.getElementById("workspaceTreePane");
    const resizer = document.getElementById("workspaceResizer");
    if (!layout || !pane || !resizer) return;
    initialized = true;

    const saved = getStoredWidth();
    if (saved !== null) layout.style.setProperty("--ws-tree-custom-w", `${saved}px`);
    syncAriaValue(resizer, pane);

    let dragging = false;
    let moved = false;
    let startX = 0;
    let startW = 280;
    let rafId = 0;
    let pendingW = 280;

    resizer.addEventListener("pointerdown", (e) => {
      if (window.innerWidth <= 780 || pane.classList.contains("slim") || pane.classList.contains("zen")) return;
      if (e.button !== undefined && e.button !== 0) return;
      e.preventDefault();
      dragging = true;
      moved = false;
      startX = e.clientX;
      startW = pane.getBoundingClientRect().width || 280;
      pendingW = startW;
      layout.classList.add("is-resizing");
      resizer.classList.add("is-dragging");
      try { resizer.setPointerCapture(e.pointerId); } catch (_) {}
    });

    resizer.addEventListener("pointermove", (e) => {
      if (!dragging) return;
      if (!moved && Math.abs(e.clientX - startX) < 2) return;
      moved = true;
      pendingW = clampWidth(startW + (e.clientX - startX));
      if (!rafId) {
        rafId = requestAnimationFrame(() => {
          rafId = 0;
          applyWidth(layout, resizer, pane, pendingW, false);
        });
      }
    });

    const finishDrag = (e) => {
      if (!dragging) return;
      dragging = false;
      if (rafId) { cancelAnimationFrame(rafId); rafId = 0; }
      layout.classList.remove("is-resizing");
      resizer.classList.remove("is-dragging");
      try { if (e && resizer.hasPointerCapture?.(e.pointerId)) resizer.releasePointerCapture(e.pointerId); } catch (_) {}
      if (moved) applyWidth(layout, resizer, pane, pendingW, true);
      moved = false;
    };
    resizer.addEventListener("pointerup", finishDrag);
    resizer.addEventListener("pointercancel", finishDrag);

    resizer.addEventListener("dblclick", () => {
      if (window.innerWidth <= 780) return;
      resetWidth(layout, resizer, pane);
    });

    resizer.addEventListener("keydown", (e) => {
      if (window.innerWidth <= 780 || pane.classList.contains("slim") || pane.classList.contains("zen")) return;
      const cur = pane.getBoundingClientRect().width || 280;
      const step = e.shiftKey ? 40 : 16;
      if (e.key === "ArrowLeft") { e.preventDefault(); applyWidth(layout, resizer, pane, cur - step, true); }
      else if (e.key === "ArrowRight") { e.preventDefault(); applyWidth(layout, resizer, pane, cur + step, true); }
      else if (e.key === "Home") { e.preventDefault(); applyWidth(layout, resizer, pane, MIN_W, true); }
      else if (e.key === "End") { e.preventDefault(); applyWidth(layout, resizer, pane, MAX_W, true); }
      else if (e.key === "Enter") { e.preventDefault(); resetWidth(layout, resizer, pane); }
    });
  }

  return { init, clampWidth, resetWidth };
});
