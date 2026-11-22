/* SPDX-License-Identifier: Apache-2.0 */
/* AGY-Nexus /web/v9 — 52-Week Mon-Sun Heatmap with Leading-Stub-Safe Month Headers */
(() => {
  const V9 = window.AgyV9;
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

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
    let lastMonth = -1;
    let lastShownCol = -4;
    cols.forEach((week, colIdx) => {
      const firstReal = week.find((d) => d && d.date);
      if (!firstReal) return;
      const m = Number(String(firstReal.date).slice(5, 7)) - 1;
      if (m !== lastMonth) {
        lastMonth = m;
        if (colIdx > 0 && colIdx < 3 && lastShownCol === 0 && out[0]) {
          out[0] = "";
          out[colIdx] = MONTHS[m] || "";
          lastShownCol = colIdx;
        } else if (colIdx - lastShownCol >= 3 && (cols.length < 2 || cols.length - colIdx >= 2)) {
          out[colIdx] = MONTHS[m] || "";
          lastShownCol = colIdx;
        }
      }
    });
    return out;
  }

  function computeMetricLevel(cell, maxTokens, maxCost) {
    if (V9.state.metric === "cost") {
      const c = Number(cell.cost_usd || 0);
      if (c <= 0 || maxCost <= 0) return 0;
      const ratio = c / maxCost;
      if (ratio > 0.65) return 4;
      if (ratio > 0.38) return 3;
      if (ratio > 0.16) return 2;
      return 1;
    }
    if (V9.state.metric !== "tokens") return Number(cell.level || 0);
    const tok = Number(cell.tokens || 0);
    if (tok <= 0 || maxTokens <= 0) return 0;
    const ratio = tok / maxTokens;
    if (ratio > 0.65) return 4;
    if (ratio > 0.38) return 3;
    if (ratio > 0.16) return 2;
    return 1;
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
    if (isMobile && !V9.state.heatPinned) {
      V9.state.heatWeeks = 26;
    }
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
    const maxTok = raw.reduce((mx, d) => Math.max(mx, Number(d.tokens || 0)), 0);
    const maxCost = raw.reduce((mx, d) => Math.max(mx, Number(d.cost_usd || 0)), 0);
    const activeCount = raw.filter((d) => d.in_window && !d.future && Number(d.steps || 0) > 0).length;
    if (summaryEl) summaryEl.textContent = `${keepCols}w view · ${activeCount} active days in window`;

    const monthCellsHtml = monthLabels.map((lbl) => `<span class="v9-heat-month-cell">${V9.escHtml(lbl)}</span>`).join("");
    let gridHtml = "";
    cols.forEach((week, colIdx) => {
      for (let r = 0; r < 7; r += 1) {
        const d = week[r];
        if (!d) {
          gridHtml += `<span class="v9-heat-cell is-future" aria-hidden="true"></span>`;
          continue;
        }
        const lvl = d.future ? 0 : computeMetricLevel(d, maxTok, maxCost);
        const cls = ["v9-heat-cell"];
        if (d.future) cls.push("is-future");
        else if (!d.in_window) cls.push("is-out");
        const desc = `${d.date}: ${V9.fmtNum(d.steps)} steps, ${V9.fmtNum(d.tokens)} tok, ${V9.fmtUsd(d.cost_usd || 0)}, ${d.sessions || 0} chats`;
        gridHtml += `<span class="${cls.join(" ")}" data-level="${lvl}" data-idx="${colIdx}-${r}" data-desc="${V9.escHtml(desc)}" title="${V9.escHtml(desc)}"></span>`;
      }
    });

    host.innerHTML = `
      <div class="v9-heat-scroll" tabindex="0" role="region" aria-label="Activity heatmap">
        <div class="v9-heat-layout">
          <div class="v9-heat-dow" aria-hidden="true">
            <span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span><span>Sun</span>
          </div>
          <div class="v9-heat-main">
            <div class="v9-heat-months" style="grid-template-columns:repeat(${keepCols},minmax(9px,22px))">${monthCellsHtml}</div>
            <div class="v9-heat-grid">${gridHtml}</div>
          </div>
        </div>
      </div>
      <div class="v9-heat-foot">
        <span id="v9HeatInspect">Hover or tap any day to inspect activity counts</span>
        <span class="v9-heat-scale">Less
          <span class="v9-heat-key" style="background:var(--v9-heat-0)"></span>
          <span class="v9-heat-key" style="background:var(--v9-heat-1)"></span>
          <span class="v9-heat-key" style="background:var(--v9-heat-2)"></span>
          <span class="v9-heat-key" style="background:var(--v9-heat-3)"></span>
          <span class="v9-heat-key" style="background:var(--v9-heat-4)"></span>
          More
        </span>
      </div>`;

    const inspectEl = document.getElementById("v9HeatInspect");
    const showDesc = (el) => {
      const text = el && el.getAttribute("data-desc");
      if (inspectEl && text) inspectEl.textContent = text;
    };
    host.querySelectorAll(".v9-heat-cell[data-desc]").forEach((cell) => {
      cell.addEventListener("mouseenter", () => showDesc(cell));
      cell.addEventListener("click", () => showDesc(cell));
    });
  }

  V9.Heatmap = { renderHeatmap };
})();
