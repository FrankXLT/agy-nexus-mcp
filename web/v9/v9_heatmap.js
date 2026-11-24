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
    let lastShownCol = -4;
    cols.forEach((week, colIdx) => {
      const firstOfMonth = week.find((d) => d && d.date && String(d.date).endsWith("-01"));
      const targetDay = firstOfMonth || (colIdx === 0 ? week.find((d) => d && d.date) : null);
      if (!targetDay) return;
      const m = Number(String(targetDay.date).slice(5, 7)) - 1;
      const lbl = MONTHS[m] || "";
      if (!lbl) return;
      if (colIdx > 0 && colIdx < 3 && lastShownCol === 0 && out[0]) {
        out[0] = "";
        out[colIdx] = lbl;
        lastShownCol = colIdx;
      } else if (colIdx - lastShownCol >= 3 && (cols.length < 2 || cols.length - colIdx >= 2)) {
        out[colIdx] = lbl;
        lastShownCol = colIdx;
      }
    });
    return out;
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

  function buildCellHtml(d, colIdx, r, cols, ctx) {
    if (!d) return `<span class="v9-heat-cell is-future" aria-hidden="true"></span>`;
    const curMonth = d.date ? String(d.date).slice(0, 7) : "";
    const leftDay = colIdx > 0 ? cols[colIdx - 1][r] : null;
    const topDay = r > 0 ? cols[colIdx][r - 1] : null;
    const hasMonthLeft = Boolean(curMonth && leftDay && leftDay.date && String(leftDay.date).slice(0, 7) !== curMonth);
    const hasMonthTop = Boolean(curMonth && topDay && topDay.date && String(topDay.date).slice(0, 7) !== curMonth);
    const cls = ["v9-heat-cell"];
    if (d.future) cls.push("is-future");
    else if (!d.in_window) cls.push("is-out");
    const isSel = !d.future && ctx.selectedDate === d.date;
    if (isSel) cls.push("is-selected");
    if (hasMonthLeft) {
      cls.push("has-month-left");
      if (r === 0) cls.push("is-row-top");
      else if (r === 6) cls.push("is-row-bot");
    }
    if (hasMonthTop) {
      cls.push("has-month-top");
      if (colIdx === 0) cls.push("is-col-first");
      if (colIdx === cols.length - 1) cls.push("is-col-last");
    }
    if (d.future) {
      const fTitle = `${formatCalendarDate(d.date)}: Upcoming calendar day`;
      return `<span class="${cls.join(" ")}" data-level="0" title="${V9.escHtml(fTitle)}" aria-hidden="true"></span>`;
    }
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
        rowCells += buildCellHtml(cols[colIdx][r], colIdx, r, cols, ctx);
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

  function renderHeatmap(b) {
    const host = document.getElementById("v9HeatHost");
    const summaryEl = document.getElementById("v9HeatSummary");
    const weeksBtn = document.getElementById("v9HeatWeeksBtn");
    if (!host) return;
    const raw = Array.isArray(b && b.heatmap_series) ? b.heatmap_series : [];
    if (!raw.length) {
      host.innerHTML = `<div class="v9-empty">No activity history recorded yet.</div>`;
      return;
    }
    const isMobile = window.innerWidth <= 560;
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
    const monthCellsHtml = monthLabels.map((lbl) => `<span class="v9-heat-month-cell">${V9.escHtml(lbl)}</span>`).join("");
    const gridHtml = buildGridRowsHtml(cols, { metric, quartiles, winTag, selectedDate, tabAnchorDate });
    const trackCols = `grid-template-columns:repeat(${keepCols},minmax(10px,1fr))`;

    host.innerHTML = `
      <div class="v9-heat-scroll">
        <div class="v9-heat-layout">
          <div class="v9-heat-dow" aria-hidden="true"><span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span><span>Sun</span></div>
          <div class="v9-heat-main">
            <div class="v9-heat-months" style="${trackCols}">${monthCellsHtml}</div>
            <div class="v9-heat-grid" style="${trackCols}" role="grid" aria-label="Activity heatmap calendar">${gridHtml}</div>
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
    renderHeatmap, buildWeeksMatrix, buildMonthLabels, computeQuartiles, computeMetricLevel,
    formatCalendarDate, resolveWindowTag, findSpatialCandidate,
  };
})();
