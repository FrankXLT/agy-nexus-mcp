// AGY-NEXUS Overwatch — Mon-Sun Activity Heatmap & Collision-Safe Month Header Engine (v3.2.4)
(function (root, factory) {
  if (typeof define === "function" && define.amd) {
    define([], factory);
  } else if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    const api = factory();
    root.HeatmapRenderer = api;
    root.computeHeatmapMonthCols = api.computeHeatmapMonthCols;
    root.renderDailyHeatmap = api.renderDailyHeatmap;
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const FALLBACK_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const FALLBACK_DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  function getIsoWeekday(dateStr, fallbackWd) {
    if (typeof computeIsoWeekday === "function") return computeIsoWeekday(dateStr, fallbackWd);
    if (typeof fallbackWd === "number" && fallbackWd >= 0 && fallbackWd <= 6) return fallbackWd;
    const parts = String(dateStr || "").split("-").map(Number);
    if (parts.length === 3 && !isNaN(parts[0])) {
      return (new Date(Date.UTC(parts[0], parts[1] - 1, parts[2])).getUTCDay() + 6) % 7;
    }
    return 0;
  }

  function computeHeatmapMonthCols(heatDays) {
    const months = typeof MONTH_NAMES !== "undefined" ? MONTH_NAMES : FALLBACK_MONTHS;
    const colMonthMap = {};
    let weekCol = 0;
    (heatDays || []).forEach((d, idx) => {
      const dow = getIsoWeekday(d.date, d.weekday);
      if (idx > 0 && dow === 0) weekCol++;
      const mNum = Number(String(d.date || "").slice(5, 7));
      const dayOfM = Number(String(d.date || "").slice(8, 10));
      if (mNum >= 1 && mNum <= 12) {
        // When a partial prior-month stub shares col 0 (e.g. Dec 29-31 before Jan 1), let day 1 replace it.
        if (dayOfM === 1) colMonthMap[weekCol] = months[mNum - 1];
        else if (idx === 0 && colMonthMap[weekCol] === undefined) colMonthMap[weekCol] = months[mNum - 1];
      }
    });
    const totalWeekCols = heatDays && heatDays.length > 0 ? (weekCol + 1) : 0;
    const effective = { ...colMonthMap };
    if (effective[0] && effective[1]) delete effective[0];
    return { colMonthMap: effective, totalWeekCols };
  }

  function renderDailyHeatmap(b, periodBanner) {
    const heatGrid = document.getElementById("heatmapGrid");
    const monthsRow = document.getElementById("heatmapMonthsRow");
    if (!heatGrid) return;
    heatGrid.replaceChildren();
    if (monthsRow) monthsRow.replaceChildren();

    const dowNames = typeof DOW_NAMES !== "undefined" ? DOW_NAMES : FALLBACK_DOW;
    const fmtTok = typeof formatCompactTokens === "function" ? formatCompactTokens : (n) => String(Math.round(Number(n || 0)));
    if (typeof state.heatWeeks === "undefined") state.heatWeeks = window.innerWidth < 560 ? 26 : 53;
    document.querySelectorAll("#heatWeeksToggle button").forEach((btn) => {
      btn.classList.toggle("active", Number(btn.dataset.weeks) === state.heatWeeks);
    });

    let heatDays = b.heatmap_series || [];
    if (state.heatWeeks === 26 && heatDays.length > 182) {
      let endIdx = heatDays.length - 1;
      while (endIdx > 0 && heatDays[endIdx].future) endIdx--;
      while (endIdx + 1 < heatDays.length && getIsoWeekday(heatDays[endIdx + 1].date, heatDays[endIdx + 1].weekday) !== 0) endIdx++;
      let sliceIdx = Math.max(0, endIdx - 181);
      while (sliceIdx > 0 && getIsoWeekday(heatDays[sliceIdx].date, heatDays[sliceIdx].weekday) !== 0) sliceIdx--;
      heatDays = heatDays.slice(sliceIdx, endIdx + 1);
    }

    const updateInspectorForDay = (d) => {
      const dowLbl = dowNames[getIsoWeekday(d.date, d.weekday)] || "";
      const inspEl = document.getElementById("heatInspector");
      if (!inspEl) return;
      inspEl.textContent = (d.future || Number(d.level) === -1)
        ? `${d.date} (${dowLbl}) — Upcoming calendar day in current period`
        : `${d.date} (${dowLbl}) — Steps: ${Number(d.steps || 0).toLocaleString()} | Tool Calls: ${Number(d.tools || 0).toLocaleString()} | Est. Tokens: ~${fmtTok(d.tokens || (d.steps * 215))} | Active Chats: ${d.sessions || 0}`;
    };

    let weekCol = 0;
    let matchedSelectedDay = null;
    if (heatDays.length > 0) {
      const firstDow = getIsoWeekday(heatDays[0].date, heatDays[0].weekday);
      for (let padRow = 0; padRow < firstDow; padRow++) {
        const padCell = document.createElement("div");
        padCell.className = "heat-cell pad";
        padCell.style.gridRow = String(padRow + 1);
        padCell.style.gridColumn = "1";
        heatGrid.appendChild(padCell);
      }
    }

    heatDays.forEach((d, idx) => {
      const dow = getIsoWeekday(d.date, d.weekday);
      if (idx > 0 && dow === 0) weekCol++;
      const cell = document.createElement("div");
      cell.className = "heat-cell" + (d.in_window === false ? " out-window" : "");
      cell.dataset.level = String(d.future ? -1 : (d.level ?? 0));
      cell.dataset.date = d.date;
      cell.style.gridRow = String(dow + 1);
      cell.style.gridColumn = String(weekCol + 1);
      cell.title = d.future
        ? `${d.date} (${dowNames[dow]}): Upcoming calendar day`
        : `${d.date} (${dowNames[dow]}): ${Number(d.steps || 0).toLocaleString()} steps, ${Number(d.tools || 0).toLocaleString()} tool calls, ~${fmtTok(d.tokens || (d.steps * 215))} tokens`;
      if (state.selectedDate && state.selectedDate === d.date && !d.future) {
        cell.classList.add("selected");
        matchedSelectedDay = d;
      }
      cell.addEventListener("click", () => {
        document.querySelectorAll(".heat-cell.selected").forEach((el) => el.classList.remove("selected"));
        cell.classList.add("selected");
        state.selectedDate = d.date;
        localStorage.setItem("nexus_selected_date", d.date);
        updateInspectorForDay(d);
      });
      heatGrid.appendChild(cell);
    });

    const { colMonthMap, totalWeekCols } = computeHeatmapMonthCols(heatDays);
    heatGrid.style.setProperty("--week-cols", String(totalWeekCols || 53));
    if (monthsRow) monthsRow.style.setProperty("--week-cols", String(totalWeekCols || 53));
    const rangeEl = document.getElementById("heatmapRangeTag");
    if (rangeEl) rangeEl.textContent = `${periodBanner} · ${totalWeekCols} WEEKS`;
    const dowCol = document.querySelector(".heatmap-dow-col");
    if (dowCol) dowCol.classList.toggle("compact-dow", window.innerWidth < 560 && totalWeekCols > 30);

    if (monthsRow && totalWeekCols > 0) {
      let lastLabeledCol = -99;
      for (let c = 0; c < totalWeekCols; c++) {
        const mSpan = document.createElement("span");
        mSpan.className = "heatmap-month-lbl";
        mSpan.style.gridColumn = String(c + 1);
        if (colMonthMap[c] && c < totalWeekCols - 1 && (c - lastLabeledCol >= 2)) {
          mSpan.textContent = colMonthMap[c];
          lastLabeledCol = c;
        }
        monthsRow.appendChild(mSpan);
      }
    }

    if (matchedSelectedDay) {
      updateInspectorForDay(matchedSelectedDay);
    } else {
      const nonFuture = heatDays.filter((x) => !x.future);
      const recentActive = [...nonFuture].reverse().find((x) => Number(x.steps || 0) > 0) || nonFuture[nonFuture.length - 1];
      if (recentActive) updateInspectorForDay(recentActive);
    }
  }

  return { computeHeatmapMonthCols, renderDailyHeatmap };
});
