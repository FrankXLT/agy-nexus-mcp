/* SPDX-License-Identifier: Apache-2.0 */
/* AGY-Nexus /web/v9 — 52-Week Mon-Sun Heatmap: Grayscale Out-of-Window, Stepped Month Dividers & Selection */
(() => {
  const V9 = window.AgyV9;
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const DOW_SUN_FIRST = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const IDLE_INSPECT_TEXT = "Hover or tap any day to inspect activity counts";

  function buildWeeksMatrix(series, weeksCount) {
    const list = Array.isArray(series) ? series : [];
    const allCols = [];
    for (let i = 0; i < list.length; i += 7) {
      allCols.push(list.slice(i, i + 7));
    }
    while (allCols.length > 0 && allCols[allCols.length - 1].every((d) => !d || d.future === true)) {
      allCols.pop();
    }
    const keepCols = Math.min(allCols.length, Math.max(12, Number(weeksCount || 53)));
    const cols = allCols.slice(Math.max(0, allCols.length - keepCols));
    return { cols, keepCols: cols.length };
  }

  function buildMonthLabels(cols) {
    const out = new Array(cols.length).fill("");
    let lastMonthKey = "";
    let lastShownCol = -4;
    cols.forEach((week, colIdx) => {
      const mon = week[0] && week[0].date ? week[0] : week.find((d) => d && d.date);
      if (!mon || !mon.date || mon.future) return;
      const mKey = String(mon.date).slice(0, 7);
      if (mKey === lastMonthKey) return;
      lastMonthKey = mKey;
      const lbl = MONTHS[Number(mKey.slice(5, 7)) - 1] || "";
      if (!lbl) return;
      if (colIdx > 0 && lastShownCol === 0 && colIdx < 2) {
        out[0] = "";
        out[colIdx] = lbl;
        lastShownCol = colIdx;
      } else if (colIdx - lastShownCol >= 2 && (cols.length < 3 || cols.length - colIdx >= 2)) {
        out[colIdx] = lbl;
        lastShownCol = colIdx;
      }
    });
    return out;
  }

  function resolveGridGeometry(colsCount, host) {
    const count = Math.max(1, Number(colsCount || 52));
    const vw = Number(window.innerWidth || 1280);
    const isNarrow = vw <= 639;
    const gapPx = 3;
    const dowReserve = isNarrow ? 20 : 36;
    const rawHostW = host && Number(host.clientWidth) > 0 ? Number(host.clientWidth) : 0;
    const fallbackW = isNarrow ? Math.max(280, vw - 26) : Math.min(1380, Math.max(320, vw - 56));
    const availGridW = Math.max(160, (rawHostW || fallbackW) - dowReserve);
    const rawCell = Math.floor((availGridW - Math.max(0, count - 1) * gapPx) / count);
    const cellPx = Math.max(8, Math.min(16, rawCell));
    const pitch = cellPx + gapPx;
    const gridW = count * cellPx + Math.max(0, count - 1) * gapPx;
    const gridH = 7 * cellPx + 6 * gapPx;
    return { cellPx, gapPx, pitch, gridW, gridH };
  }

  function stitchSegmentsToPath(segments) {
    const fmt = (n) => (Number.isInteger(n) ? String(n) : n.toFixed(2).replace(/\.?0+$/, ""));
    const key = (pt) => `${pt[0].toFixed(2)},${pt[1].toFixed(2)}`;
    const used = new Array(segments.length).fill(false);
    const adj = new Map();
    segments.forEach((seg, idx) => {
      [seg[0], seg[1]].forEach((pt) => {
        const k = key(pt);
        if (!adj.has(k)) adj.set(k, []);
        adj.get(k).push(idx);
      });
    });
    const nextAt = (pt) => (adj.get(key(pt)) || []).find((i) => !used[i]);
    const parts = [];
    for (let i = 0; i < segments.length; i += 1) {
      if (used[i]) continue;
      used[i] = true;
      const pts = [segments[i][0], segments[i][1]];
      let n;
      while ((n = nextAt(pts[pts.length - 1])) !== undefined) {
        used[n] = true;
        const [a, b] = segments[n];
        pts.push(key(a) === key(pts[pts.length - 1]) ? b : a);
      }
      while ((n = nextAt(pts[0])) !== undefined) {
        used[n] = true;
        const [a, b] = segments[n];
        pts.unshift(key(a) === key(pts[0]) ? b : a);
      }
      parts.push(`M${fmt(pts[0][0])} ${fmt(pts[0][1])}` + pts.slice(1).map((p) => `L${fmt(p[0])} ${fmt(p[1])}`).join(""));
    }
    return parts.join("");
  }

  function buildMonthDividerPath(cols, cellPx, gapPx) {
    const C = Array.isArray(cols) ? cols.length : 0;
    if (!C) return "";
    const pitch = cellPx + gapPx;
    const gridW = C * cellPx + Math.max(0, C - 1) * gapPx;
    const gridH = 7 * cellPx + 6 * gapPx;
    const m = (c, r) => {
      if (c < 0 || c >= C || r < 0 || r >= 7) return "";
      const d = cols[c][r];
      return d && !d.future && d.date ? String(d.date).slice(0, 7) : "";
    };
    const vOn = (c, r) => c > 0 && c < C && Boolean(m(c - 1, r) && m(c, r) && m(c - 1, r) !== m(c, r));
    const hOn = (c, r) => r > 0 && r < 7 && Boolean(m(c, r - 1) && m(c, r) && m(c, r - 1) !== m(c, r));
    const segs = [];
    for (let c = 1; c < C; c += 1) {
      for (let r = 0; r < 7; r += 1) {
        if (!vOn(c, r)) continue;
        let r1 = r;
        while (r1 + 1 < 7 && vOn(c, r1 + 1)) r1 += 1;
        const vx = c * pitch - gapPx / 2;
        const y0 = (hOn(c - 1, r) || hOn(c, r)) ? r * pitch - gapPx / 2 : (r === 0 ? 0 : r * pitch);
        const y1 = (r1 < 6 && (hOn(c - 1, r1 + 1) || hOn(c, r1 + 1))) ? (r1 + 1) * pitch - gapPx / 2 : (r1 === 6 ? gridH : r1 * pitch + cellPx);
        segs.push([[vx, y0], [vx, y1]]);
        r = r1;
      }
    }
    for (let r = 1; r < 7; r += 1) {
      for (let c = 0; c < C; c += 1) {
        if (!hOn(c, r)) continue;
        let c1 = c;
        while (c1 + 1 < C && hOn(c1 + 1, r)) c1 += 1;
        const hy = r * pitch - gapPx / 2;
        const x0 = (c > 0 && (vOn(c, r - 1) || vOn(c, r))) ? c * pitch - gapPx / 2 : (c === 0 ? 0 : c * pitch);
        const x1 = (c1 < C - 1 && (vOn(c1 + 1, r - 1) || vOn(c1 + 1, r))) ? (c1 + 1) * pitch - gapPx / 2 : (c1 === C - 1 ? gridW : c1 * pitch + cellPx);
        segs.push([[x0, hy], [x1, hy]]);
        c = c1;
      }
    }
    return stitchSegmentsToPath(segs);
  }

  function getMetricValue(cell, metric) {
    if (!cell) return 0;
    if (metric === "cost") return Number(cell.cost_usd || 0);
    if (metric === "tokens") return Number(cell.tokens || 0);
    return Number(cell.steps || 0);
  }

  function computeQuartiles(vals) {
    const nz = (Array.isArray(vals) ? vals : [])
      .map((v) => Number(v || 0))
      .filter((v) => Number.isFinite(v) && v > 0)
      .sort((a, b) => a - b);
    if (!nz.length) return [0, 0, 0];
    const pick = (p) => nz[Math.max(0, Math.floor(nz.length * p) - 1)];
    return [pick(0.25), pick(0.5), pick(0.75)];
  }

  function computeMetricLevel(cell, metric, quartiles) {
    const val = getMetricValue(cell, metric);
    if (val <= 0) return 0;
    const q = Array.isArray(quartiles) && quartiles.length === 3 ? quartiles : [0, 0, 0];
    if (q[2] <= 0) return 1;
    if (val <= q[0]) return 1;
    if (val <= q[1]) return 2;
    if (val <= q[2]) return 3;
    return 4;
  }

  function formatCalendarDate(isoDate) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(isoDate || ""));
    if (!m) return String(isoDate || "");
    const y = Number(m[1]), mo = Number(m[2]), da = Number(m[3]);
    const dt = new Date(Date.UTC(y, mo - 1, da));
    const dow = DOW_SUN_FIRST[dt.getUTCDay()] || "";
    const mon = MONTHS[mo - 1] || "";
    return `${dow}, ${mon} ${da}, ${y}`;
  }

  function resolveWindowTag(period) {
    if (!period || !period.timeframe) return "window";
    const tf = period.timeframe;
    const hm = period.horizon_mode || "to_date";
    const off = Number(period.offset || 0);
    if (hm === "rolling") {
      if (tf === "month") return "30d";
      if (tf === "quarter") return "90d";
      return "52w";
    }
    if (off !== 0) return String(period.label || "window").trim() || "window";
    if (tf === "month") return "MTD";
    if (tf === "quarter") return "QTD";
    if (tf === "year") return "YTD";
    return "window";
  }

  function resolvePeriodKey(b, raw) {
    const p = (b && b.period) || {};
    const scope = (b && b.project_scope && b.project_scope.project_id) || "";
    const endMarker = p.end_date || (raw.length && raw[raw.length - 1] ? raw[raw.length - 1].date : "");
    return `${p.key || ""}:${p.start_date || ""}:${endMarker}:${scope}`;
  }

  function isDayActive(d) {
    return Boolean(d && !d.future && (Number(d.steps || 0) > 0 || Number(d.tokens || 0) > 0 || Number(d.cost_usd || 0) > 0));
  }

  function resolveSelectedAndTabAnchor(cols, periodKey) {
    if (V9.state.heatPeriodKey && V9.state.heatPeriodKey !== periodKey) {
      V9.state.heatSelectedDate = "";
    }
    V9.state.heatPeriodKey = periodKey;
    const visibleDays = [];
    cols.forEach((week) => {
      for (let r = 0; r < 7; r += 1) {
        const d = week[r];
        if (d && d.date && !d.future) visibleDays.push(d);
      }
    });
    const pinned = V9.state.heatSelectedDate || "";
    let selectedDate = pinned && visibleDays.some((d) => d.date === pinned) ? pinned : "";
    if (!selectedDate) {
      const rev = [...visibleDays].reverse();
      const pick = rev.find((d) => d.in_window && isDayActive(d)) || rev.find((d) => isDayActive(d));
      selectedDate = pick ? pick.date : "";
    }
    V9.state.heatSelectedDate = selectedDate;
    const lastDay = visibleDays.length ? visibleDays[visibleDays.length - 1].date : "";
    return { selectedDate, tabAnchorDate: selectedDate || lastDay };
  }

  function formatReadoutText(d, metric, winTag) {
    const dateLabel = formatCalendarDate(d.date);
    const stepsPart = `${V9.fmtNum(d.steps || 0)} steps`;
    const tokPart = `${V9.fmtNum(d.tokens || 0)} tok`;
    const costPart = V9.fmtUsd(d.cost_usd || 0);
    const ordered = metric === "cost"
      ? [costPart, stepsPart, tokPart]
      : (metric === "tokens" ? [tokPart, stepsPart, costPart] : [stepsPart, tokPart, costPart]);
    const parts = [dateLabel, ...ordered, `${d.sessions || 0} chats`];
    if (!d.in_window && !d.future) parts.push(`Outside ${winTag}`);
    return parts.join(" · ");
  }

  function buildCellHtml(d, ctx) {
    if (!d || d.future) {
      return `<span class="v9-heat-cell is-future" data-level="0" aria-hidden="true"></span>`;
    }
    const cls = ["v9-heat-cell"];
    if (!d.in_window) cls.push("is-out");
    const isSel = ctx.selectedDate === d.date;
    if (isSel) cls.push("is-selected");
    const lvl = computeMetricLevel(d, ctx.metric, ctx.quartiles);
    const readout = formatReadoutText(d, ctx.metric, ctx.winTag);
    const outTitle = d.in_window ? "" : " (outside window)";
    const titleTxt = `${formatCalendarDate(d.date)}: ${V9.fmtNum(d.steps)} steps, ${V9.fmtNum(d.tokens)} tok, ${V9.fmtUsd(d.cost_usd || 0)}, ${d.sessions || 0} chats${outTitle}`;
    const tabIdx = ctx.tabAnchorDate === d.date ? "0" : "-1";
    return `<button type="button" role="gridcell" class="${cls.join(" ")}" data-level="${lvl}" data-date="${V9.escHtml(d.date)}" data-out="${d.in_window ? "0" : "1"}" data-readout="${V9.escHtml(readout)}" aria-selected="${isSel ? "true" : "false"}" aria-label="${V9.escHtml(readout)}" tabindex="${tabIdx}" title="${V9.escHtml(titleTxt)}"></button>`;
  }

  function buildGridRowsHtml(cols, ctx) {
    let rowsHtml = "";
    for (let r = 0; r < 7; r += 1) {
      let rowCells = "";
      for (let colIdx = 0; colIdx < cols.length; colIdx += 1) {
        rowCells += buildCellHtml(cols[colIdx][r], ctx);
      }
      rowsHtml += `<div class="v9-heat-row" role="row">${rowCells}</div>`;
    }
    return rowsHtml;
  }

  function updateInspectReadout(inspectEl, cellEl, isPreview) {
    if (!inspectEl) return;
    if (!cellEl) {
      inspectEl.textContent = IDLE_INSPECT_TEXT;
      return;
    }
    const lvl = cellEl.getAttribute("data-level") || "0";
    const isOut = cellEl.getAttribute("data-out") === "1";
    const txt = cellEl.getAttribute("data-readout") || "";
    const swCls = ["v9-heat-inspect-swatch", isOut ? "is-out" : "", isPreview ? "is-preview" : ""].filter(Boolean).join(" ");
    inspectEl.innerHTML = `<span class="${swCls}" data-level="${V9.escHtml(lvl)}" aria-hidden="true"></span><span class="v9-heat-inspect-txt">${V9.escHtml(txt)}</span>`;
  }

  function findSpatialCandidate(gridEl, currentEl, key) {
    if (!gridEl || !currentEl || typeof currentEl.getBoundingClientRect !== "function") return null;
    const isHoriz = key === "ArrowLeft" || key === "ArrowRight";
    const cur = currentEl.getBoundingClientRect();
    const curCx = (cur.left + cur.right) / 2;
    const curCy = (cur.top + cur.bottom) / 2;
    const tol = 2;
    const all = Array.from(gridEl.querySelectorAll("button.v9-heat-cell"));
    const candidates = [];
    for (const el of all) {
      if (el === currentEl) continue;
      if (typeof el.checkVisibility === "function" && !el.checkVisibility()) continue;
      const r = el.getBoundingClientRect();
      if (!r || r.width <= 0 || r.height <= 0) continue;
      let gap = -1;
      if (key === "ArrowRight" && r.left >= cur.right - tol) gap = Math.max(0, r.left - cur.right);
      else if (key === "ArrowLeft" && r.right <= cur.left + tol) gap = Math.max(0, cur.left - r.right);
      else if (key === "ArrowDown" && r.top >= cur.bottom - tol) gap = Math.max(0, r.top - cur.bottom);
      else if (key === "ArrowUp" && r.bottom <= cur.top + tol) gap = Math.max(0, cur.top - r.bottom);
      if (gap < 0) continue;
      const overlaps = isHoriz ? (r.top < cur.bottom - 1 && r.bottom > cur.top + 1) : (r.left < cur.right - 1 && r.right > cur.left + 1);
      const perp = isHoriz ? Math.abs(((r.top + r.bottom) / 2) - curCy) : Math.abs(((r.left + r.right) / 2) - curCx);
      candidates.push({ el, gap, overlaps, perp });
    }
    if (!candidates.length) return null;
    const aligned = candidates.filter((c) => c.overlaps);
    if (!aligned.length) return null;
    aligned.sort((a, b) => a.gap - b.gap || a.perp - b.perp);
    return aligned[0].el;
  }

  function bindHeatmapEvents(gridEl, inspectEl) {
    const pinCell = (cellEl, shouldFocus) => {
      if (!cellEl) return;
      gridEl.querySelectorAll("button.v9-heat-cell[tabindex='0'], button.v9-heat-cell.is-selected").forEach((prev) => {
        prev.classList.remove("is-selected");
        prev.setAttribute("aria-selected", "false");
        prev.setAttribute("tabindex", "-1");
      });
      cellEl.classList.add("is-selected");
      cellEl.setAttribute("aria-selected", "true");
      cellEl.setAttribute("tabindex", "0");
      V9.state.heatSelectedDate = cellEl.getAttribute("data-date") || "";
      updateInspectReadout(inspectEl, cellEl, false);
      if (shouldFocus) {
        cellEl.focus();
        if (typeof cellEl.scrollIntoView === "function") cellEl.scrollIntoView({ block: "nearest", inline: "nearest" });
      }
    };
    gridEl.querySelectorAll("button.v9-heat-cell").forEach((cell) => {
      cell.addEventListener("mouseenter", () => {
        const dt = cell.getAttribute("data-date") || "";
        updateInspectReadout(inspectEl, cell, dt !== V9.state.heatSelectedDate);
      });
      cell.addEventListener("click", () => pinCell(cell, false));
    });
    gridEl.addEventListener("mouseleave", () => {
      const pinned = gridEl.querySelector("button.v9-heat-cell.is-selected");
      updateInspectReadout(inspectEl, pinned, false);
    });
    gridEl.addEventListener("keydown", (ev) => {
      if (ev.altKey || ev.ctrlKey || ev.metaKey || ev.shiftKey) return;
      const target = ev.target && ev.target.closest ? ev.target.closest("button.v9-heat-cell") : null;
      if (!target || !gridEl.contains(target)) return;
      if (ev.key === "Home" || ev.key === "End") {
        const cells = Array.from(gridEl.querySelectorAll("button.v9-heat-cell"))
          .sort((a, b) => String(a.getAttribute("data-date") || "").localeCompare(String(b.getAttribute("data-date") || "")));
        const jump = ev.key === "Home" ? cells[0] : cells[cells.length - 1];
        if (!jump) return;
        ev.preventDefault();
        pinCell(jump, true);
        return;
      }
      if (!["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(ev.key)) return;
      const cand = findSpatialCandidate(gridEl, target, ev.key);
      if (!cand) return;
      ev.preventDefault();
      pinCell(cand, true);
    });
  }

  let lastHeatBundle = null;
  let lastHeatWidth = 0;
  let heatResizeTimer = null;

  function ensureHeatResizeHook(host) {
    if (!host || !host.dataset || host.dataset.v9HeatResizeBound) return;
    host.dataset.v9HeatResizeBound = "1";
    const onResize = () => {
      if (!lastHeatBundle || !V9.state.bundle || !host.clientWidth) return;
      const curW = Number(host.clientWidth);
      if (Math.abs(curW - lastHeatWidth) < 2) return;
      clearTimeout(heatResizeTimer);
      heatResizeTimer = setTimeout(() => {
        if (lastHeatBundle && V9.state.bundle && host.clientWidth) renderHeatmap(lastHeatBundle);
      }, 80);
    };
    if (typeof ResizeObserver === "function") {
      new ResizeObserver(onResize).observe(host);
    } else if (typeof window.addEventListener === "function") {
      window.addEventListener("resize", onResize);
    }
  }

  function reset() {
    clearTimeout(heatResizeTimer);
    heatResizeTimer = null;
    lastHeatBundle = null;
    lastHeatWidth = 0;
  }

  function renderHeatmap(b) {
    const host = document.getElementById("v9HeatHost");
    const summaryEl = document.getElementById("v9HeatSummary");
    const weeksBtn = document.getElementById("v9HeatWeeksBtn");
    if (!host) return;
    lastHeatBundle = b;
    lastHeatWidth = Number(host.clientWidth || 0) || Number(window.innerWidth || 0);
    ensureHeatResizeHook(host);
    const raw = Array.isArray(b && b.heatmap_series) ? b.heatmap_series : [];
    if (!raw.length) {
      host.innerHTML = `<div class="v9-empty">No activity history recorded yet.</div>`;
      return;
    }
    const isMobile = Number(window.innerWidth || 1280) <= 639;
    if (isMobile && !V9.state.heatPinned) V9.state.heatWeeks = 26;
    if (weeksBtn) {
      if (!weeksBtn.dataset.v9PinBound) {
        weeksBtn.dataset.v9PinBound = "1";
        weeksBtn.addEventListener("click", () => { V9.state.heatPinned = true; }, true);
      }
      weeksBtn.classList.toggle("hidden", !isMobile);
      weeksBtn.textContent = V9.state.heatWeeks <= 26 ? "Show 53w" : "Show 26w";
    }
    const { cols, keepCols } = buildWeeksMatrix(raw, isMobile ? V9.state.heatWeeks : 53);
    const { cellPx, gapPx, pitch, gridW, gridH } = resolveGridGeometry(keepCols, host);
    const monthLabels = buildMonthLabels(cols);
    const metric = V9.state.metric || "steps";
    const nonFuture = raw.filter((d) => d && !d.future);
    const winVals = nonFuture.filter((d) => d.in_window).map((d) => getMetricValue(d, metric)).filter((v) => v > 0);
    const poolVals = winVals.length >= 4 ? winVals : nonFuture.map((d) => getMetricValue(d, metric)).filter((v) => v > 0);
    const quartiles = computeQuartiles(poolVals);
    const activeCount = nonFuture.filter((d) => d.in_window && Number(d.steps || 0) > 0).length;
    if (summaryEl) summaryEl.textContent = `${keepCols}w view · ${activeCount} active days in window`;

    const winTag = resolveWindowTag(b && b.period);
    const periodKey = resolvePeriodKey(b, raw);
    const { selectedDate, tabAnchorDate } = resolveSelectedAndTabAnchor(cols, periodKey);
    const monthCellsHtml = monthLabels
      .map((lbl, idx) => (lbl && idx * pitch <= Math.max(0, gridW - 20) ? `<span class="v9-heat-month-lbl" style="inset-inline-start:${idx * pitch}px">${V9.escHtml(lbl)}</span>` : ""))
      .join("");
    const gridHtml = buildGridRowsHtml(cols, { metric, quartiles, winTag, selectedDate, tabAnchorDate });
    const dividerPath = buildMonthDividerPath(cols, cellPx, gapPx);
    const svgPath = dividerPath ? `<path class="v9-heat-divider-path" d="${dividerPath}"></path>` : "";

    host.innerHTML = `
      <div class="v9-heat-scroll">
        <div class="v9-heat-layout" style="--v9-heat-cell:${cellPx}px;--v9-heat-gap:${gapPx}px">
          <div class="v9-heat-dow" aria-hidden="true"><span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span><span>Sun</span></div>
          <div class="v9-heat-main">
            <div class="v9-heat-months" style="inline-size:${gridW}px">${monthCellsHtml}</div>
            <div class="v9-heat-grid-wrap" style="inline-size:${gridW}px;block-size:${gridH}px">
              <div class="v9-heat-grid" style="grid-template-columns:repeat(${keepCols},${cellPx}px)" role="grid" aria-label="Activity heatmap calendar">${gridHtml}</div>
              <svg class="v9-heat-divider-svg" viewBox="0 0 ${gridW} ${gridH}" width="${gridW}" height="${gridH}" aria-hidden="true">${svgPath}</svg>
            </div>
          </div>
        </div>
      </div>
      <div class="v9-heat-foot">
        <span id="v9HeatInspect" class="v9-heat-inspect">${V9.escHtml(IDLE_INSPECT_TEXT)}</span>
        <span class="v9-heat-scale">Less
          <span class="v9-heat-key" style="background:var(--v9-heat-0)"></span>
          <span class="v9-heat-key" style="background:var(--v9-heat-1)"></span>
          <span class="v9-heat-key" style="background:var(--v9-heat-2)"></span>
          <span class="v9-heat-key" style="background:var(--v9-heat-3)"></span>
          <span class="v9-heat-key" style="background:var(--v9-heat-4)"></span>
          More
        </span>
      </div>`;

    const gridEl = typeof host.querySelector === "function" ? host.querySelector(".v9-heat-grid") : null;
    const inspectEl = document.getElementById("v9HeatInspect");
    const pinnedEl = gridEl ? gridEl.querySelector("button.v9-heat-cell.is-selected") : null;
    updateInspectReadout(inspectEl, pinnedEl, false);
    if (gridEl) bindHeatmapEvents(gridEl, inspectEl);
  }

  V9.Heatmap = {
    renderHeatmap, buildWeeksMatrix, buildMonthLabels, resolveGridGeometry, buildMonthDividerPath,
    computeQuartiles, computeMetricLevel, formatCalendarDate, resolveWindowTag, findSpatialCandidate, reset,
  };
})();
