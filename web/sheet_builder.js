// AGY-NEXUS Overwatch — Aspect-Aware 2/4/8 High-Res Sheet Builder (3072px Ceiling) & Client STORE ZIP (v3.2.2)
(function (root, factory) {
  if (typeof define === "function" && define.amd) {
    define([], factory);
  } else if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.SheetBuilder = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const STORAGE_KEY = "nexus_sheet_group_size";
  const MAX_EDGE = 3072;
  const PADDING = 12;
  const GUTTER = 10;
  const LABEL_H = 30;
  const MIN_CELL_W = 280;
  const GEMINI_PROMPT_MAX_FILES = 10;

  function normalizePerSheet(v) {
    const n = Number(v);
    return n === 2 || n === 4 || n === 8 ? n : 4;
  }

  function getPerSheet() {
    try {
      return normalizePerSheet(typeof localStorage !== "undefined" ? localStorage.getItem(STORAGE_KEY) : 4);
    } catch (_e) {
      return 4;
    }
  }

  function setPerSheet(v) {
    const clean = normalizePerSheet(v);
    try {
      if (typeof localStorage !== "undefined") localStorage.setItem(STORAGE_KEY, String(clean));
    } catch (_e) {}
    return clean;
  }

  function partitionChunks(items, perSheet) {
    const size = normalizePerSheet(perSheet);
    const list = Array.isArray(items) ? items : [];
    const chunks = [];
    for (let i = 0; i < list.length; i += size) chunks.push(list.slice(i, i + size));
    return chunks;
  }

  function getLayoutCandidates(chunkLen, perSheet) {
    if (chunkLen <= 1) return [[1, 1]];
    if (chunkLen === 2) return [[1, 2], [2, 1]];
    if (chunkLen === 3) return [[1, 3], [3, 1], [2, 2]];
    if (chunkLen === 4 || normalizePerSheet(perSheet) === 4) return [[2, 2], [1, 4], [4, 1]];
    return [[2, 4], [4, 2], [3, 3]];
  }

  function chooseSheetLayout(dimsList, perSheet) {
    const n = dimsList.length;
    if (!n) return null;
    const candidates = getLayoutCandidates(n, perSheet);
    let best = null;

    for (let k = 0; k < candidates.length; k++) {
      const cols = Math.max(1, Math.min(candidates[k][0], n));
      const rows = Math.max(1, Math.ceil(n / cols));
      const maxCellW = Math.floor((MAX_EDGE - 2 * PADDING - Math.max(0, cols - 1) * GUTTER) / cols);
      const maxCellH = Math.floor((MAX_EDGE - 2 * PADDING - Math.max(0, rows - 1) * GUTTER) / rows) - LABEL_H;
      if (maxCellW < 40 || maxCellH < 40) continue;

      const colW = new Array(cols).fill(Math.min(MIN_CELL_W, maxCellW));
      const rowH = new Array(rows).fill(0);
      const placements = [];
      let scaleSum = 0;

      for (let i = 0; i < n; i++) {
        const w = Math.max(1, Number(dimsList[i]?.w) || 800);
        const h = Math.max(1, Number(dimsList[i]?.h) || 500);
        const col = i % cols;
        const row = Math.floor(i / cols);
        const scale = Math.min(1.0, maxCellW / w, maxCellH / h);
        const drawW = Math.max(1, Math.round(w * scale));
        const drawH = Math.max(1, Math.round(h * scale));
        scaleSum += scale;
        if (drawW > colW[col]) colW[col] = drawW;
        if (drawH + LABEL_H > rowH[row]) rowH[row] = drawH + LABEL_H;
        placements.push({ col, row, drawW, drawH, scale, natW: w, natH: h });
      }

      const canvasW = Math.min(MAX_EDGE, PADDING * 2 + colW.reduce((a, b) => a + b, 0) + Math.max(0, cols - 1) * GUTTER);
      const canvasH = Math.min(MAX_EDGE, PADDING * 2 + rowH.reduce((a, b) => a + b, 0) + Math.max(0, rows - 1) * GUTTER);
      const avgScale = scaleSum / n;
      const aspectDiff = Math.abs(canvasW - canvasH) / Math.max(canvasW, canvasH);
      const score = avgScale * 1000 - aspectDiff * 0.5 - (canvasW * canvasH) / 1e9;
      if (!best || score > best.score) best = { score, avgScale, cols, rows, canvasW, canvasH, colW, rowH, placements };
    }
    return best;
  }

  let CRC_TABLE = null;
  function crc32(bytes) {
    if (!CRC_TABLE) {
      CRC_TABLE = new Uint32Array(256);
      for (let i = 0; i < 256; i++) {
        let c = i;
        for (let k = 0; k < 8; k++) c = (c & 1) ? (0xedb88320 ^ (c >>> 1)) : (c >>> 1);
        CRC_TABLE[i] = c >>> 0;
      }
    }
    let crc = 0xffffffff;
    for (let i = 0; i < bytes.length; i++) crc = CRC_TABLE[(crc ^ bytes[i]) & 0xff] ^ (crc >>> 8);
    return (crc ^ 0xffffffff) >>> 0;
  }

  function buildStoreZip(entries) {
    const enc = new TextEncoder();
    const parts = [];
    const centrals = [];
    let offset = 0;
    for (let i = 0; i < entries.length; i++) {
      const nameBytes = enc.encode(String(entries[i].name || `sheet_${i + 1}.png`));
      const data = entries[i].data instanceof Uint8Array ? entries[i].data : new Uint8Array(entries[i].data);
      const sum = crc32(data);
      const loc = new Uint8Array(30 + nameBytes.length);
      const lv = new DataView(loc.buffer);
      lv.setUint32(0, 0x04034b50, true); lv.setUint16(4, 20, true); lv.setUint16(8, 0, true);
      lv.setUint32(14, sum, true); lv.setUint32(18, data.length, true); lv.setUint32(22, data.length, true);
      lv.setUint16(26, nameBytes.length, true);
      loc.set(nameBytes, 30);
      parts.push(loc, data);

      const cen = new Uint8Array(46 + nameBytes.length);
      const cv = new DataView(cen.buffer);
      cv.setUint32(0, 0x02014b50, true); cv.setUint16(4, 20, true); cv.setUint16(6, 20, true);
      cv.setUint32(16, sum, true); cv.setUint32(20, data.length, true); cv.setUint32(24, data.length, true);
      cv.setUint16(28, nameBytes.length, true); cv.setUint32(42, offset, true);
      cen.set(nameBytes, 46);
      centrals.push(cen);
      offset += loc.length + data.length;
    }
    const cdSize = centrals.reduce((a, b) => a + b.length, 0);
    const eocd = new Uint8Array(22);
    const ev = new DataView(eocd.buffer);
    ev.setUint32(0, 0x06054b50, true);
    ev.setUint16(8, entries.length, true); ev.setUint16(10, entries.length, true);
    ev.setUint32(12, cdSize, true); ev.setUint32(16, offset, true);

    const out = new Uint8Array(offset + cdSize + 22);
    let pos = 0;
    for (let i = 0; i < parts.length; i++) { out.set(parts[i], pos); pos += parts[i].length; }
    for (let i = 0; i < centrals.length; i++) { out.set(centrals[i], pos); pos += centrals[i].length; }
    out.set(eocd, pos);
    return out;
  }

  function formatSheetFilename(repoSlug, perSheet, idx, total) {
    const slug = String(repoSlug || "session").replace(/[^a-zA-Z0-9_.-]+/g, "_") || "session";
    const p2 = (n) => String(n).padStart(2, "0");
    return `captures_${slug}_${normalizePerSheet(perSheet)}up_sheet${p2(idx + 1)}of${p2(total)}.png`;
  }

  function fitHeaderText(ctx, prefix, name, suffix, maxWidth) {
    const full = `${prefix}${name}${suffix}`;
    if (ctx.measureText(full).width <= maxWidth) return full;
    for (let keep = Math.max(8, name.length - 4); keep >= 6; keep -= 2) {
      const head = name.slice(0, Math.ceil(keep * 0.45));
      const tail = name.slice(-Math.floor(keep * 0.55));
      const cand = `${prefix}${head}…${tail}${suffix}`;
      if (ctx.measureText(cand).width <= maxWidth) return cand;
    }
    return `${prefix}${name.slice(0, 10)}…${suffix}`;
  }

  function loadImageElement(url) {
    return new Promise((resolve) => {
      const img = new Image();
      const s = String(url || "");
      if (!s.startsWith("data:") && !s.startsWith("/") && !s.startsWith("./")) img.crossOrigin = "anonymous";
      img.onload = () => resolve({ img, w: img.naturalWidth || 800, h: img.naturalHeight || 500, ok: true });
      img.onerror = () => resolve({ img: null, w: 800, h: 500, ok: false });
      img.src = url;
    });
  }

  async function renderChunkToSheet(chunk, startIdx, totalItems, sheetIdx, totalSheets, repoSlug, perSheet) {
    const loaded = await Promise.all(chunk.map((it) => loadImageElement(it.signed_url)));
    const layout = chooseSheetLayout(loaded.map((l) => ({ w: l.w, h: l.h })), perSheet);
    if (!layout) return null;

    const canvas = document.createElement("canvas");
    canvas.width = layout.canvasW;
    canvas.height = layout.canvasH;
    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.fillStyle = "#0f172a";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const colX = [];
    let cx = PADDING;
    for (let c = 0; c < layout.cols; c++) { colX.push(cx); cx += layout.colW[c] + GUTTER; }
    const rowY = [];
    let ry = PADDING;
    for (let r = 0; r < layout.rows; r++) { rowY.push(ry); ry += layout.rowH[r] + GUTTER; }

    for (let i = 0; i < chunk.length; i++) {
      const pl = layout.placements[i], it = chunk[i], ld = loaded[i];
      const cellX = colX[pl.col], cellY = rowY[pl.row];
      const cellW = layout.colW[pl.col], cellH = layout.rowH[pl.row];

      ctx.fillStyle = "#111827";
      ctx.fillRect(cellX, cellY, cellW, cellH);
      ctx.fillStyle = "#1e293b";
      ctx.fillRect(cellX, cellY, cellW, LABEL_H);

      ctx.fillStyle = "#93c5fd";
      ctx.font = "bold 15px monospace";
      const prefix = `[${startIdx + i + 1}/${totalItems}] `;
      const suffix = ` (${ld.w}x${ld.h})`;
      const hdr = fitHeaderText(ctx, prefix, String(it.name || "capture"), suffix, cellW - 14);
      ctx.fillText(hdr, cellX + 8, cellY + 20);

      if (ld.ok && ld.img) {
        const dx = cellX + Math.round((cellW - pl.drawW) / 2);
        const dy = cellY + LABEL_H + Math.round((cellH - LABEL_H - pl.drawH) / 2);
        ctx.drawImage(ld.img, dx, dy, pl.drawW, pl.drawH);
      } else {
        ctx.fillStyle = "#ef4444";
        ctx.fillText("Image load failed", cellX + 12, cellY + LABEL_H + 34);
      }
    }

    const outW = canvas.width, outH = canvas.height;
    let blob = null;
    try {
      blob = await new Promise((res, rej) => {
        try {
          canvas.toBlob((b) => (b ? res(b) : rej(new Error("Canvas PNG encoding failed"))), "image/png");
        } catch (err) {
          rej(err);
        }
      });
    } finally {
      canvas.width = 0;
      canvas.height = 0;
    }
    const name = formatSheetFilename(repoSlug, perSheet, sheetIdx, totalSheets);
    return { name, blob, width: outW, height: outH, sheetIdx, totalSheets, count: chunk.length };
  }

  async function buildSheetBlobs(items, repoSlug, perSheet, onProgress) {
    const ps = normalizePerSheet(perSheet);
    const chunks = partitionChunks(items, ps);
    const sheets = [];
    let offset = 0;
    for (let i = 0; i < chunks.length; i++) {
      if (typeof onProgress === "function") onProgress(`Rendering sheet ${i + 1}/${chunks.length}...`);
      const s = await renderChunkToSheet(chunks[i], offset, items.length, i, chunks.length, repoSlug, ps);
      if (s && s.blob) sheets.push(s);
      offset += chunks[i].length;
    }
    return sheets;
  }

  const DOWNLOAD_STAGGER_MS = 220;
  let sheetBuildBusy = false;
  let sheetDownloadBusy = false;
  let sheetModalSeq = 0;
  let activeSheetModalCleanup = null;
  let activeSheetModalCloseListener = null;

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

  async function downloadGeneratedSheetsIndividually(sheets, onStatus) {
    if (!sheets || !sheets.length || sheetDownloadBusy) return 0;
    sheetDownloadBusy = true;
    try {
      for (let i = 0; i < sheets.length; i++) {
        if (sheets.length > 1 && typeof onStatus === "function") {
          onStatus(`Downloading sheet ${i + 1}/${sheets.length}...`);
        }
        triggerBlobDownload(sheets[i].blob, sheets[i].name);
        if (i < sheets.length - 1) await new Promise((r) => setTimeout(r, DOWNLOAD_STAGGER_MS));
      }
      if (typeof onStatus === "function") {
        onStatus(sheets.length === 1 ? `Downloaded ${sheets[0].name}` : `Downloaded ${sheets.length} sheet PNGs`);
      }
      return sheets.length;
    } finally {
      sheetDownloadBusy = false;
    }
  }

  async function downloadSheets(items, repoSlug, perSheet, onStatus) {
    if (!items || !items.length || sheetBuildBusy || sheetDownloadBusy) return;
    let sheets = [];
    sheetBuildBusy = true;
    try {
      sheets = await buildSheetBlobs(items, repoSlug, perSheet, onStatus);
    } catch (err) {
      if (typeof onStatus === "function") onStatus(`Sheet export failed: ${err?.message || "canvas error"}`);
      return;
    } finally {
      sheetBuildBusy = false;
    }
    if (!sheets.length) return;
    await downloadGeneratedSheetsIndividually(sheets, onStatus);
  }

  function renderModalBatchBar(batchBar, sheets, repoSlug, perSheet, files, canShareFiles, onStatus) {
    if (!batchBar) return;
    const isMulti = sheets.length > 1;
    let bh = `<button type="button" class="btn btn-xs btn-focal mono" id="sheetModalPngsBtn">${isMulti ? `⬇ Download All ${sheets.length} Sheet PNGs` : "⬇ Download Sheet PNG"}</button>`;
    if (isMulti) bh += `<button type="button" class="btn btn-xs mono" id="sheetModalZipBtn">⬇ Sheets ZIP</button>`;
    if (canShareFiles) {
      for (let b = 0; b < files.length; b += GEMINI_PROMPT_MAX_FILES) {
        const end = Math.min(files.length, b + GEMINI_PROMPT_MAX_FILES);
        bh += `<button type="button" class="btn btn-xs mono btn-share-batch" data-start="${b}" data-end="${end}">✦ Share Batch (${b + 1}–${end})</button>`;
      }
    }
    bh += `<span class="gallery-live-status mono" id="sheetModalStatus" role="status"></span>`;
    batchBar.innerHTML = bh;
    const modalStatusEl = batchBar.querySelector("#sheetModalStatus");
    const updateModalStatus = (msg) => {
      if (modalStatusEl) modalStatusEl.textContent = msg || "";
      if (typeof onStatus === "function") onStatus(msg);
    };
    batchBar.querySelector("#sheetModalPngsBtn")?.addEventListener("click", () => {
      downloadGeneratedSheetsIndividually(sheets, updateModalStatus);
    });
    batchBar.querySelector("#sheetModalZipBtn")?.addEventListener("click", async () => {
      const entries = await Promise.all(sheets.map(async (s) => ({ name: s.name, data: new Uint8Array(await s.blob.arrayBuffer()) })));
      const slug = String(repoSlug || "session").replace(/[^a-zA-Z0-9_.-]+/g, "_") || "session";
      const zipName = `sheets_${slug}_${normalizePerSheet(perSheet)}up_${sheets.length}sheets.zip`;
      triggerBlobDownload(new Blob([buildStoreZip(entries)], { type: "application/zip" }), zipName);
      updateModalStatus(`Downloaded ${zipName}`);
    });
    batchBar.querySelectorAll(".btn-share-batch").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const s = Number(btn.getAttribute("data-start")), e = Number(btn.getAttribute("data-end"));
        try { await navigator.share({ files: files.slice(s, e), title: `AGY-Nexus Sheets ${s + 1}-${e}` }); } catch (_err) {}
      });
    });
  }

  function openSheetExportModal(sheets, repoSlug, perSheet, openLightboxFn, canShareFiles, onStatus) {
    const escAttr = (v) => String(v || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
    const dlg = document.getElementById("sheetExportDialog");
    if (!dlg) {
      if (sheets[0] && typeof openLightboxFn === "function") {
        const fbUrl = URL.createObjectURL(sheets[0].blob);
        openLightboxFn(fbUrl, sheets[0].name, `${sheets[0].width}×${sheets[0].height}`);
        setTimeout(() => URL.revokeObjectURL(fbUrl), 60000);
      }
      return;
    }
    if (activeSheetModalCloseListener) dlg.removeEventListener?.("close", activeSheetModalCloseListener);
    activeSheetModalCloseListener = null;
    if (typeof activeSheetModalCleanup === "function") activeSheetModalCleanup();
    const seq = ++sheetModalSeq;

    const titleEl = document.getElementById("sheetExportTitle");
    const batchBar = document.getElementById("sheetExportBatchBar");
    const gridEl = document.getElementById("sheetPreviewGrid");
    const closeBtn = document.getElementById("sheetExportCloseBtn");
    const urls = sheets.map((s) => URL.createObjectURL(s.blob));
    const files = sheets.map((s) => new File([s.blob], s.name, { type: "image/png" }));

    if (titleEl) titleEl.textContent = `Sheet Export (${sheets.length} ${sheets.length > 1 ? "sheets" : "sheet"} · ${normalizePerSheet(perSheet)}/sheet)`;
    renderModalBatchBar(batchBar, sheets, repoSlug, perSheet, files, canShareFiles, onStatus);

    if (gridEl) {
      gridEl.innerHTML = sheets.map((s, idx) => `<div class="sheet-preview-card mono"><img src="${urls[idx]}" class="sheet-preview-thumb" data-idx="${idx}" alt="${escAttr(s.name)}" /><div class="doc-card-meta"><span>Sheet ${idx + 1}/${sheets.length}</span><span>${s.width}×${s.height}</span></div><div class="ws-header-right"><button type="button" class="btn btn-xs mono btn-copy-sheet" data-idx="${idx}">Copy PNG</button><button type="button" class="btn btn-xs mono btn-save-sheet" data-idx="${idx}">Save PNG</button></div></div>`).join("");
      gridEl.querySelectorAll(".sheet-preview-thumb").forEach((im) => {
        im.onclick = () => { const i = Number(im.getAttribute("data-idx")); if (typeof openLightboxFn === "function") openLightboxFn(urls[i], sheets[i].name, `${sheets[i].width}×${sheets[i].height}`); };
      });
      gridEl.querySelectorAll(".btn-copy-sheet").forEach((b) => {
        b.onclick = async () => {
          const i = Number(b.getAttribute("data-idx"));
          try { await navigator.clipboard.write([new ClipboardItem({ "image/png": sheets[i].blob })]); b.textContent = "Copied!"; } catch (_e) { b.textContent = "Copy failed"; }
          setTimeout(() => { b.textContent = "Copy PNG"; }, 1200);
        };
      });
      gridEl.querySelectorAll(".btn-save-sheet").forEach((b) => {
        b.onclick = () => { const i = Number(b.getAttribute("data-idx")); triggerBlobDownload(sheets[i].blob, sheets[i].name); };
      });
    }

    let cleaned = false;
    const cleanup = () => {
      if (cleaned) return;
      cleaned = true;
      urls.forEach((u) => URL.revokeObjectURL(u));
      if (gridEl) gridEl.replaceChildren();
      if (activeSheetModalCleanup === cleanup) activeSheetModalCleanup = null;
    };
    const onClose = () => {
      if (seq !== sheetModalSeq || dlg.open) return;
      dlg.removeEventListener?.("close", onClose);
      if (activeSheetModalCloseListener === onClose) activeSheetModalCloseListener = null;
      cleanup();
    };
    activeSheetModalCleanup = cleanup;
    activeSheetModalCloseListener = onClose;
    dlg.addEventListener("close", onClose);
    if (closeBtn) closeBtn.onclick = () => dlg.close();
    dlg.onclick = (e) => {
      if ("closedBy" in HTMLDialogElement.prototype || e.target !== dlg) return;
      const r = dlg.getBoundingClientRect();
      if (r.top <= e.clientY && e.clientY <= r.top + r.height && r.left <= e.clientX && e.clientX <= r.left + r.width) return;
      dlg.close();
    };
    if (!dlg.open) typeof dlg.showModal === "function" ? dlg.showModal() : dlg.setAttribute("open", "");
    if (typeof onStatus === "function" && files.length > GEMINI_PROMPT_MAX_FILES) {
      onStatus(`${files.length} sheets exceed 10-file Gemini cap; share in batches.`);
    }
  }

  async function shareSheetsToGemini(items, repoSlug, perSheet, openLightboxFn, onStatus) {
    if (!items || !items.length || sheetBuildBusy || sheetDownloadBusy) return;
    sheetBuildBusy = true;
    try {
      const sheets = await buildSheetBlobs(items, repoSlug, perSheet, onStatus);
      if (!sheets.length) return;
      const files = sheets.map((s) => new File([s.blob], s.name, { type: "image/png" }));
      const canShare = Boolean(typeof navigator !== "undefined" && navigator.canShare && navigator.canShare({ files: files.slice(0, 1) }));
      if (canShare && files.length <= GEMINI_PROMPT_MAX_FILES) {
        try {
          await navigator.share({ files, title: "AGY-Nexus Captures", text: `${items.length} captures across ${sheets.length} sheet(s)` });
          if (typeof onStatus === "function") onStatus(`Shared ${sheets.length} sheet(s)`);
          return;
        } catch (err) {
          if (err?.name === "AbortError") return;
        }
      }
      if (!canShare && sheets[0] && typeof navigator !== "undefined" && navigator.clipboard && window.ClipboardItem) {
        try {
          await navigator.clipboard.write([new ClipboardItem({ "image/png": sheets[0].blob })]);
          if (typeof onStatus === "function") onStatus("Copied Sheet 1 to clipboard");
        } catch (_e) {}
      }
      openSheetExportModal(sheets, repoSlug, perSheet, openLightboxFn, canShare, onStatus);
    } catch (err) {
      if (typeof onStatus === "function") onStatus(`Sheet share failed: ${err?.message || "canvas error"}`);
    } finally {
      sheetBuildBusy = false;
    }
  }

  return {
    MAX_EDGE, PADDING, GUTTER, LABEL_H, MIN_CELL_W, GEMINI_PROMPT_MAX_FILES,
    normalizePerSheet, getPerSheet, setPerSheet, partitionChunks, getLayoutCandidates,
    chooseSheetLayout, crc32, buildStoreZip, formatSheetFilename,
    buildSheetBlobs, downloadGeneratedSheetsIndividually, downloadSheets, openSheetExportModal, shareSheetsToGemini,
  };
});
