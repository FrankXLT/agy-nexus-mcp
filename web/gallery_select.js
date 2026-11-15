// AGY-NEXUS Overwatch — Multi-Select Gallery, Bulk ZIP, Web Share & Contact Sheet (v3.2.0)
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

  const selectedItems = new Map(); // rel_path -> item object
  let lastSelectedIndex = -1;
  let dragSelectActive = false;

  function clearSelection() {
    selectedItems.clear();
    lastSelectedIndex = -1;
  }

  function getSelectedList() {
    return Array.from(selectedItems.values());
  }

  function isSelected(relPath) {
    return selectedItems.has(relPath);
  }

  function toggleItem(item, checked, index) {
    if (checked) {
      selectedItems.set(item.rel_path, item);
      if (typeof index === "number") lastSelectedIndex = index;
    } else {
      selectedItems.delete(item.rel_path);
    }
  }

  function handleShiftSelect(items, currentIndex, checked) {
    if (lastSelectedIndex === -1 || lastSelectedIndex === currentIndex) {
      toggleItem(items[currentIndex], checked, currentIndex);
      return;
    }
    const start = Math.min(lastSelectedIndex, currentIndex);
    const end = Math.max(lastSelectedIndex, currentIndex);
    for (let i = start; i <= end; i++) {
      if (items[i]) toggleItem(items[i], checked, i);
    }
  }

  function selectAll(items) {
    (items || []).forEach((it, idx) => toggleItem(it, true, idx));
  }

  function renderBulkActionBarHtml(convId, totalAvailable) {
    const count = selectedItems.size;
    if (count === 0) return "";
    return `
      <div class="gallery-bulk-bar mono" id="galleryBulkBar">
        <div class="bulk-bar-left">
          <span class="bulk-pill cyan"><strong>${count}</strong> selected</span>
          <button type="button" class="btn btn-xs mono" id="bulkSelectAllBtn">Select All (${totalAvailable})</button>
          <button type="button" class="btn btn-xs mono" id="bulkClearBtn">Clear</button>
        </div>
        <div class="bulk-bar-actions">
          <button type="button" class="btn btn-xs btn-focal mono" id="bulkShareBtn" title="Share via Android OS Share Sheet">✦ Share to Gemini (${count})</button>
          <button type="button" class="btn btn-xs mono" id="bulkContactSheetBtn" title="Stitch high-DPI sheet to clipboard">📋 Copy Sheet for Chat</button>
          <button type="button" class="btn btn-xs mono" id="bulkDownloadZipBtn" title="Download ZIP archive">⬇ ZIP</button>
          <button type="button" class="btn btn-xs mono" id="bulkDownloadPngsBtn" title="Download individual PNGs">⬇ PNGs</button>
        </div>
      </div>
    `;
  }

  async function shareToGemini() {
    const list = getSelectedList();
    if (!list.length) return;
    try {
      const files = [];
      for (const item of list.slice(0, 10)) {
        const resp = await fetch(item.signed_url);
        const blob = await resp.blob();
        files.push(new File([blob], item.name || "capture.png", { type: blob.type || "image/png" }));
      }
      if (navigator.canShare && navigator.canShare({ files })) {
        await navigator.share({ files, title: "AGY-Nexus Captures", text: `Visual captures from session (${list.length} files)` });
      } else {
        alert("Web Share API is not supported on this browser/desktop. Use 'Copy Sheet for Chat' or 'Download ZIP'.");
      }
    } catch (err) {
      if (err.name !== "AbortError") alert(`Share failed: ${err.message}`);
    }
  }

  async function copyContactSheetForChat(openLightboxFn) {
    const list = getSelectedList();
    if (!list.length) return;
    const cols = list.length <= 4 ? 2 : 3;
    const rows = Math.ceil(list.length / cols);
    const cellW = 800, cellH = 500, hdrH = 36;
    const canvas = document.createElement("canvas");
    canvas.width = cols * cellW;
    canvas.height = rows * (cellH + hdrH);
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#0f172a";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    for (let i = 0; i < list.length; i++) {
      const it = list[i];
      const c = i % cols, r = Math.floor(i / cols);
      const x = c * cellW, y = r * (cellH + hdrH);
      ctx.fillStyle = "#1e293b";
      ctx.fillRect(x + 2, y + 2, cellW - 4, hdrH - 2);
      ctx.fillStyle = "#38bdf8";
      ctx.font = "bold 16px monospace";
      ctx.fillText(`[${i + 1}] ${it.name}`, x + 12, y + 24);

      try {
        const img = new Image();
        img.crossOrigin = "anonymous";
        await new Promise((res, rej) => {
          img.onload = res;
          img.onerror = rej;
          img.src = it.signed_url;
        });
        const scale = Math.min((cellW - 8) / img.naturalWidth, (cellH - 8) / img.naturalHeight);
        const dw = img.naturalWidth * scale, dh = img.naturalHeight * scale;
        const dx = x + (cellW - dw) / 2, dy = y + hdrH + (cellH - dh) / 2;
        ctx.drawImage(img, dx, dy, dw, dh);
      } catch (e) {
        ctx.fillStyle = "#ef4444";
        ctx.fillText("Failed to load image", x + 12, y + hdrH + 40);
      }
    }

    canvas.toBlob(async (blob) => {
      if (!blob) return;
      try {
        if (navigator.clipboard && window.ClipboardItem) {
          await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
        }
      } catch (err) {
        console.warn("ClipboardItem write failed:", err);
      }
      const sheetUrl = canvas.toDataURL("image/png");
      if (typeof openLightboxFn === "function") {
        openLightboxFn(sheetUrl, `Contact Sheet (${list.length} Captures)`, "Stitched for Gboard / Chat Paste");
      }
    }, "image/png");
  }

  async function downloadZip(convId, getApiHeadersFn, getBaseApiPathFn) {
    const list = getSelectedList();
    if (!list.length) return;
    try {
      const resp = await fetch(getBaseApiPathFn() + `/web/api/sessions/${encodeURIComponent(convId)}/download-zip`, {
        method: "POST",
        headers: { ...getApiHeadersFn(), "Content-Type": "application/json" },
        body: JSON.stringify({ files: list.map((i) => i.rel_path) }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        return alert(`Download failed: ${err.error || resp.statusText}`);
      }
      const blob = await resp.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `captures_${convId.slice(0, 8)}_${list.length}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (e) {
      alert(`ZIP download error: ${e.message}`);
    }
  }

  async function downloadSequentialPngs() {
    const list = getSelectedList();
    for (let i = 0; i < list.length; i++) {
      const it = list[i];
      const a = document.createElement("a");
      a.href = it.signed_url;
      a.download = it.name || `capture_${i + 1}.png`;
      a.target = "_blank";
      document.body.appendChild(a);
      a.click();
      a.remove();
      if (i < list.length - 1) await new Promise((r) => setTimeout(r, 220));
    }
  }

  function bindRubberBandMarquee(container, getItemsFn, onSelectionUpdate) {
    if (!container) return;
    let startX = 0, startY = 0, isDown = false;
    let box = null;

    container.addEventListener("pointerdown", (e) => {
      if (e.target.closest("button") || e.target.closest("input") || e.target.closest("a")) return;
      if (!dragSelectActive && !e.shiftKey && !e.ctrlKey && !e.metaKey) return;
      isDown = true;
      startX = e.clientX;
      startY = e.clientY;
      box = document.createElement("div");
      box.className = "gallery-marquee-box";
      box.style.left = `${startX}px`;
      box.style.top = `${startY}px`;
      box.style.width = "0px";
      box.style.height = "0px";
      document.body.appendChild(box);
    });

    window.addEventListener("pointermove", (e) => {
      if (!isDown || !box) return;
      const x1 = Math.min(startX, e.clientX), y1 = Math.min(startY, e.clientY);
      const x2 = Math.max(startX, e.clientX), y2 = Math.max(startY, e.clientY);
      box.style.left = `${x1}px`;
      box.style.top = `${y1}px`;
      box.style.width = `${x2 - x1}px`;
      box.style.height = `${y2 - y1}px`;

      const cards = container.querySelectorAll(".visual-thumb-card");
      const items = getItemsFn();
      cards.forEach((card, idx) => {
        const r = card.getBoundingClientRect();
        const intersects = !(r.right < x1 || r.left > x2 || r.bottom < y1 || r.top > y2);
        if (intersects && items[idx]) {
          selectedItems.set(items[idx].rel_path, items[idx]);
          card.classList.add("selected");
          const cb = card.querySelector(".gallery-item-cb");
          if (cb) cb.checked = true;
        }
      });
      if (typeof onSelectionUpdate === "function") onSelectionUpdate();
    });

    window.addEventListener("pointerup", () => {
      if (!isDown) return;
      isDown = false;
      if (box) { box.remove(); box = null; }
    });
  }

  function setDragSelectMode(active) {
    dragSelectActive = !!active;
  }

  function getDragSelectMode() {
    return dragSelectActive;
  }

  return {
    clearSelection, getSelectedList, isSelected, toggleItem, handleShiftSelect,
    selectAll, renderBulkActionBarHtml, shareToGemini, copyContactSheetForChat,
    downloadZip, downloadSequentialPngs, bindRubberBandMarquee,
    setDragSelectMode, getDragSelectMode,
  };
});
