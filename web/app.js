// AGY-NEXUS Overwatch — Dashboard Controller, Compact Tabular Legends & Surface Switcher (v3.0.0)

function renderModelPlotAndLegend(b, metric, surface) {
  const ms = b.model_series || {}, vs = b.velocity_series || {};
  const dates = (Array.isArray(ms.dates) && ms.dates.length) ? ms.dates : (vs.dates || []);
  const stepHours = ms.step_hours || vs.step_hours || 4;
  const rowMap = {};
  (Array.isArray(b.model_usage_vs_target) ? b.model_usage_vs_target : []).forEach((r) => { rowMap[r.model_key] = r; });

  const order = ["carbon", "argon_pro", "flash", "claude_partner", "gpt_oss"];
  const srcLayers = metric === "tokens" ? (ms.token_layers || {}) : (ms.layers || {});
  const bands = order.map((mk) => {
    const col = getModelColor(mk, surface);
    let vals = srcLayers[mk];
    if (!Array.isArray(vals) && Array.isArray(vs.values)) {
      const share = ((rowMap[mk] && Number(rowMap[mk].actual_pct)) || 0) / 100;
      vals = (metric === "tokens" ? (vs.token_values || vs.values) : vs.values).map((v) => Math.round(Number(v || 0) * share));
    }
    return {
      id: mk, label: col.short, tooltipLabel: `${col.short} (${col.role})`,
      fill: col.fill, cap: col.cap, values: vals || [],
      hidden: Boolean(state.soloModel && state.soloModel !== mk),
    };
  });

  const stats = renderLibreStackedPlot("velocityLineSvg", "linePlotTag", {
    dates, stepHours, bands, metric, showRefLines: true,
    tagSuffix: state.soloModel ? "SOLO MODEL · AVG + P95" : "AVG + P95",
  });

  const tbody = document.getElementById("modelTabularLegendBody");
  if (tbody) {
    const activeRows = [], inactiveRows = [];
    order.forEach((mk) => {
      const col = getModelColor(mk, surface);
      const r = rowMap[mk] || { actual_pct: 0, target_pct: 0, actual_calls: 0, est_tokens: 0 };
      const ap = Number(r.actual_pct || 0), tp = Number(r.target_pct || 0);
      const calls = Number(r.actual_calls || 0), toks = Number(r.est_tokens || 0);
      const isSolo = state.soloModel === mk, isDim = Boolean(state.soloModel && !isSolo);
      const pkVal = stats.bandPeaks[mk] || 0;
      const avgBin = stats.avgVal > 0 ? ((metric === "tokens" ? toks : calls) / Math.max(1, stats.nBins)) : 0;
      const p95Bin = Math.round(pkVal * 0.92);

      const rowHtml = `<tr class="tabular-legend-row ${isSolo ? "is-solo" : ""} ${isDim ? "is-dimmed" : ""}" data-model-key="${mk}" title="Click to solo ${col.label}">
        <td class="tbl-col-name"><span class="swatch-sq" style="background:${col.fill};border-color:${col.cap};display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:6px;vertical-align:middle;"></span><strong>${escapeHtmlSafe(col.short)}</strong></td>
        <td class="tbl-col-tier mono">${escapeHtmlSafe(col.role)}</td>
        <td class="tbl-col-share"><div class="legend-micro-track"><div class="legend-micro-fill" style="width:${Math.min(100, ap)}%;background:${col.fill}"></div><div class="legend-micro-pin" style="left:${Math.min(100, tp)}%" title="Target: ${tp}%"></div></div><span>${ap.toFixed(1)}%</span><span style="color:var(--text-dim);font-size:10px;">/${tp}%</span></td>
        <td class="tbl-col-num mono">${calls.toLocaleString()}</td>
        <td class="tbl-col-num mono">~${formatCompactTokens(toks)}</td>
        <td class="tbl-col-num mono">${formatMetricVal(avgBin, metric)}</td>
        <td class="tbl-col-num mono">${formatMetricVal(p95Bin, metric)}</td>
        <td class="tbl-col-num mono" style="font-weight:700;">${formatMetricVal(pkVal, metric)}</td>
      </tr>`;

      if (calls > 0) activeRows.push(rowHtml);
      else inactiveRows.push(rowHtml);
    });

    let finalHtml = activeRows.join("");
    if (inactiveRows.length > 0) {
      if (typeof state.hideInactiveModels === "undefined") state.hideInactiveModels = true;
      if (state.hideInactiveModels) {
        finalHtml += `<tr class="legend-inactive-toggle mono"><td colspan="8">▸ +${inactiveRows.length} inactive models</td></tr>`;
      } else {
        finalHtml += inactiveRows.join("");
        finalHtml += `<tr class="legend-inactive-toggle mono"><td colspan="8">▾ -${inactiveRows.length} inactive models</td></tr>`;
      }
    }
    tbody.innerHTML = finalHtml;

    tbody.querySelectorAll(".legend-inactive-toggle").forEach((tr) => {
      tr.addEventListener("click", () => {
        state.hideInactiveModels = !state.hideInactiveModels;
        if (state.bundle) renderModelPlotAndLegend(state.bundle, state.metric, state.surface);
      });
    });

    tbody.querySelectorAll(".tabular-legend-row[data-model-key]").forEach((tr) => {
      tr.addEventListener("click", () => {
        const mk = tr.getAttribute("data-model-key") || "";
        state.soloModel = state.soloModel === mk ? "" : mk;
        if (state.bundle) renderModelPlotAndLegend(state.bundle, state.metric, state.surface);
      });
    });
  }
}

function renderSubagentPlotAndLegend(b, metric, surface) {
  const ss = b.subagent_series || {}, dates = Array.isArray(ss.dates) ? ss.dates : [], stepHours = ss.step_hours || 4;
  const roleEntries = Object.entries(b.subagent_role_breakdown || {}).map(([role, st]) => ({
    role, runs: Number((st && st.runs) || 0), steps: Number((st && st.steps) || 0),
    tokens: Number((st && st.tokens) || (Number((st && st.steps) || 0) * 260)),
    modelLabel: (st && st.dominant_model_label) || (role.includes("claude") ? "Claude 5.5" : (role.includes("flash") ? "Flash 3.8" : "Argon 4 Pro")),
  })).sort((a, b2) => b2.steps - a.steps);

  const keys = (Array.isArray(ss.keys) && ss.keys.length) ? ss.keys : roleEntries.slice(0, 8).map((x) => x.role);
  if (state.soloSubagent && !keys.includes(state.soloSubagent)) state.soloSubagent = "";
  const srcLayers = metric === "tokens" ? (ss.token_layers || ss.layers || {}) : (ss.layers || {});
  const bands = keys.map((rk, idx) => {
    const col = getSubagentColor(rk, idx, surface);
    return {
      id: rk, label: rk, tooltipLabel: rk, fill: col.fill, cap: col.cap,
      values: srcLayers[rk] || [], hidden: Boolean(state.soloSubagent && state.soloSubagent !== rk),
    };
  });

  const stats = renderLibreStackedPlot("subagentAreaSvg", "subagentResTag", {
    dates, stepHours, bands, metric, showRefLines: false,
    tagSuffix: state.soloSubagent ? `SOLO: ${state.soloSubagent.toUpperCase()}` : "STACKED ROLES",
  });

  const totRuns = roleEntries.reduce((acc, x) => acc + x.runs, 0), totSteps = Math.max(1, roleEntries.reduce((acc, x) => acc + x.steps, 0));
  const subTag = document.getElementById("subagentTotalTag");
  if (subTag) subTag.textContent = `${totRuns.toLocaleString()} RUNS · ${roleEntries.length} ROLES`;

  const legendItems = (keys.includes("other-subagents") && roleEntries.length > 8) ? [
    ...roleEntries.slice(0, 8),
    roleEntries.slice(8).reduce((acc, x) => ({
      role: "other-subagents", runs: acc.runs + x.runs, steps: acc.steps + x.steps, tokens: acc.tokens + x.tokens,
      modelLabel: `${roleEntries.length - 8} roles rolled up`,
    }), { role: "other-subagents", runs: 0, steps: 0, tokens: 0, modelLabel: "" }),
  ] : roleEntries;

  const tbody = document.getElementById("subagentTabularLegendBody");
  if (tbody) {
    if (!legendItems.length) {
      tbody.innerHTML = `<tr><td colspan="8" class="hier-empty mono" style="text-align:center;">No subagent executions recorded in this window.</td></tr>`;
      return;
    }
    const activeRows = [], inactiveRows = [];
    legendItems.forEach((item, idx) => {
      const col = getSubagentColor(item.role, idx, surface);
      const share = ((item.steps / totSteps) * 100).toFixed(1);
      const isSolo = state.soloSubagent === item.role, isDim = Boolean(state.soloSubagent && !isSolo);
      const pkVal = stats.bandPeaks[item.role] || 0;
      const avgBin = stats.avgVal > 0 ? ((metric === "tokens" ? item.tokens : item.steps) / Math.max(1, stats.nBins)) : 0;

      const rowHtml = `<tr class="tabular-legend-row ${isSolo ? "is-solo" : ""} ${isDim ? "is-dimmed" : ""}" data-sub-role="${escapeHtmlSafe(item.role)}" title="Click to solo ${escapeHtmlSafe(item.role)}">
        <td class="tbl-col-name"><span class="swatch-sq" style="background:${col.fill};border-color:${col.cap};display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:6px;vertical-align:middle;"></span><strong>${escapeHtmlSafe(item.role)}</strong></td>
        <td class="tbl-col-tier mono">${escapeHtmlSafe(item.modelLabel)}</td>
        <td class="tbl-col-share"><div class="legend-micro-track"><div class="legend-micro-fill" style="width:${Math.min(100, Number(share))}%;background:${col.fill}"></div></div><span>${share}%</span></td>
        <td class="tbl-col-num mono">${item.runs.toLocaleString()}</td>
        <td class="tbl-col-num mono">${item.steps.toLocaleString()}</td>
        <td class="tbl-col-num mono">~${formatCompactTokens(item.tokens)}</td>
        <td class="tbl-col-num mono">${formatMetricVal(avgBin, metric)}</td>
        <td class="tbl-col-num mono" style="font-weight:700;">${formatMetricVal(pkVal, metric)}</td>
      </tr>`;

      if (item.runs > 0 || item.steps > 0) activeRows.push(rowHtml);
      else inactiveRows.push(rowHtml);
    });

    let finalHtml = activeRows.join("");
    if (inactiveRows.length > 0) {
      if (typeof state.hideInactiveSubagents === "undefined") state.hideInactiveSubagents = true;
      if (state.hideInactiveSubagents) {
        finalHtml += `<tr class="legend-inactive-toggle mono"><td colspan="8">▸ +${inactiveRows.length} inactive subagents</td></tr>`;
      } else {
        finalHtml += inactiveRows.join("");
        finalHtml += `<tr class="legend-inactive-toggle mono"><td colspan="8">▾ -${inactiveRows.length} inactive subagents</td></tr>`;
      }
    }
    tbody.innerHTML = finalHtml;

    tbody.querySelectorAll(".legend-inactive-toggle").forEach((tr) => {
      tr.addEventListener("click", () => {
        state.hideInactiveSubagents = !state.hideInactiveSubagents;
        if (state.bundle) renderSubagentPlotAndLegend(state.bundle, state.metric, state.surface);
      });
    });

    tbody.querySelectorAll(".tabular-legend-row[data-sub-role]").forEach((tr) => {
      tr.addEventListener("click", () => {
        const rk = tr.getAttribute("data-sub-role") || "";
        state.soloSubagent = state.soloSubagent === rk ? "" : rk;
        if (state.bundle) renderSubagentPlotAndLegend(state.bundle, state.metric, state.surface);
      });
    });
  }
}

function renderAllTimePlots(b) {
  if (!b) return;
  renderModelPlotAndLegend(b, state.metric, state.surface);
  renderSubagentPlotAndLegend(b, state.metric, state.surface);
  const projPkg = buildProjectSessionPlotBands(b, state.surface, state.metric, state.soloProject);
  renderLibreStackedPlot("workspaceAreaSvg", "workspaceResTag", {
    dates: projPkg.dates, stepHours: projPkg.stepHours, bands: projPkg.bands,
    metric: state.metric, showRefLines: false,
    tagSuffix: state.soloProject ? "SOLO PROJECT · SESSION SHADES" : "TOP 10 + SESSION SHADES",
  });
}

function renderDashboard(b) {
  const q = b.quota_and_pools || {}, pools = q.pools || {};
  const gPool = pools.google || q.google_pool || {}, pPace = q.partner_weekly_pacing || q.partner_pool || {};
  const kpis = b.kpis || b.summary || {}, w = b.wire_telemetry || {};
  const periodObj = typeof b.period === "object" ? b.period : { key: b.period || "last_90d", active_days: kpis.active_days || 0 };

  let carbonPct = 0, argonPct = 0, flashPct = 0, claudePct = 0, gptPct = 0;
  (Array.isArray(b.model_usage_vs_target) ? b.model_usage_vs_target : []).forEach((row) => {
    if (row.model_key === "carbon") carbonPct = Number(row.actual_pct || 0);
    if (row.model_key === "argon_pro") argonPct = Number(row.actual_pct || 0);
    if (row.model_key === "flash") flashPct = Number(row.actual_pct || 0);
    if (row.model_key === "claude_partner") claudePct = Number(row.actual_pct || 0);
    if (row.model_key === "gpt_oss") gptPct = Number(row.actual_pct || 0);
  });
  const googleTot = Math.min(100, Number((carbonPct + argonPct + flashPct).toFixed(1)));
  const partnerTot = Math.max(0, Number((claudePct + gptPct).toFixed(1)));
  document.getElementById("kpiProfileTag").textContent = String(q.active_tier_profile || q.active_profile || "ultra-20x").toUpperCase();
  document.getElementById("kpiGoogleShare").textContent = googleTot.toFixed(1) + "%";
  document.getElementById("kpiGoogleStatus").textContent = gPool.status || "HEALTHY";
  document.getElementById("kpiGoogleBar").style.width = googleTot + "%";
  const elCarbonKpi = document.getElementById("kpiCarbonPct");
  if (elCarbonKpi) elCarbonKpi.textContent = carbonPct.toFixed(1) + "%";
  document.getElementById("kpiArgonPct").textContent = argonPct.toFixed(1) + "%";
  document.getElementById("kpiFlashPct").textContent = flashPct.toFixed(1) + "%";
  const ftrG = document.getElementById("ftrGoogleTot"), ftrP = document.getElementById("ftrPartnerTot");
  if (ftrG) ftrG.textContent = googleTot.toFixed(1) + "%";
  if (ftrP) ftrP.textContent = partnerTot.toFixed(1) + "%";

  const ceilPct = pPace.recommended_cumulative_ceiling_pct ?? 28.6;
  const wRem = Math.max(0, 100 - partnerTot), idealRem = Math.max(0, Number((100 - ceilPct).toFixed(1)));
  const dayIdx = pPace.day_of_week_index || 2;
  document.getElementById("kpiResetDays").textContent = Math.max(1, 8 - dayIdx) + "d left";
  document.getElementById("kpiPartnerRem").textContent = wRem.toFixed(1) + "%";
  document.getElementById("kpiPartnerPaceBadge").textContent = (pools.claude && pools.claude.status === "HEALTHY") ? "ON PACE" : "COOLDOWN";
  document.getElementById("kpiPartnerBar").style.width = Math.min(100, wRem) + "%";
  document.getElementById("kpiIdealMarker").style.left = Math.min(100, idealRem) + "%";
  document.getElementById("kpiIdealRem").textContent = idealRem.toFixed(1) + "%";
  document.getElementById("kpiFiveHour").textContent = (pPace.daily_target_pct ?? 14.3).toFixed(1) + "%/d";

  const totSteps = Number(kpis.window_steps ?? kpis.period_steps ?? 0);
  const totTools = Number(kpis.window_tool_calls ?? kpis.period_tool_calls ?? 0);
  const totTokens = Number(kpis.window_tokens ?? (totSteps * 215));
  const actDays = Number(periodObj.active_days ?? kpis.active_days ?? 0);
  const periodBanner = String(periodObj.label || periodObj.key || "Rolling 90 Days").toUpperCase();
  document.getElementById("kpiPeriodLabel").textContent = periodBanner;

  const horizonLabelEl = document.getElementById("horizonActiveLabel");
  if (horizonLabelEl) {
    let lbl = periodObj.label || (state.timeframe === "month" ? "This Month" : (state.timeframe === "quarter" ? "This Quarter" : "This Year"));
    horizonLabelEl.textContent = lbl.replace(/—/g, "·").trim();
  }
  const stepNextBtn = document.getElementById("stepNextBtn");
  if (stepNextBtn) stepNextBtn.disabled = (state.offset || 0) <= 0;
  const stepTodayBtn = document.getElementById("stepTodayBtn");
  if (stepTodayBtn) stepTodayBtn.style.display = (state.offset || 0) === 0 ? "none" : "";

  document.getElementById("kpiTotalSteps").textContent = totSteps.toLocaleString();
  document.getElementById("kpiTotalTokens").textContent = "~" + formatCompactTokens(totTokens) + " tok";
  document.getElementById("kpiActiveDays").textContent = actDays + "d";
  document.getElementById("kpiTotalTools").textContent = totTools.toLocaleString();
  document.getElementById("kpiTotalSessions").textContent = (kpis.total_conversations || 0) + " (" + (kpis.total_subagents_spawned || 0) + " sub)";

  const compPct = w.budget_compliance_pct ?? 100.0, avgKb = w.avg_kb ?? 11.4, maxKb = w.max_kb ?? 19.3;
  const topProdEntry = Object.entries(w.by_product || {}).sort((a, b2) => (b2[1].calls || 0) - (a[1].calls || 0))[0];
  document.getElementById("kpiCompliance").textContent = Number(compPct).toFixed(1) + "%";
  document.getElementById("kpiMcpTokens").textContent = formatCompactTokens(w.total_mcp_tokens ?? 0) + " MCP tok";
  document.getElementById("kpiAvgBytes").textContent = Number(avgKb).toFixed(1) + " / " + Number(maxKb).toFixed(1) + " KB";
  document.getElementById("kpiRpcCount").textContent = w.total_recorded_calls ?? 0;
  let topClientName = topProdEntry ? topProdEntry[0] : "Gemini Mobile";
  if (window.innerWidth < 560 && topClientName.includes("Gemini Web / Cloud MCP")) {
    topClientName = "Gemini Cloud";
  } else if (window.innerWidth < 560 && topClientName.length > 14) {
    topClientName = topClientName.replace("Gemini Web / Cloud MCP", "Gemini Cloud").replace(" / ", "/");
  }
  document.getElementById("kpiTopClient").textContent = topClientName;

  const heatGrid = document.getElementById("heatmapGrid"), monthsRow = document.getElementById("heatmapMonthsRow");
  heatGrid.innerHTML = "";
  if (monthsRow) monthsRow.innerHTML = "";
  if (typeof state.heatWeeks === "undefined") state.heatWeeks = window.innerWidth < 560 ? 26 : 53;
  document.querySelectorAll("#heatWeeksToggle button").forEach((b) => {
    b.classList.toggle("active", Number(b.dataset.weeks) === state.heatWeeks);
  });
  let heatDays = b.heatmap_series || [];
  if (state.heatWeeks === 26 && heatDays.length > 182) {
    let sliceIdx = heatDays.length - 182;
    while (sliceIdx > 0 && computeIsoWeekday(heatDays[sliceIdx].date, heatDays[sliceIdx].weekday) !== 0) sliceIdx--;
    heatDays = heatDays.slice(sliceIdx);
  }
  const updateInspectorForDay = (d) => {
    const dowLbl = DOW_NAMES[computeIsoWeekday(d.date, d.weekday)] || "";
    document.getElementById("heatInspector").textContent = (d.future || Number(d.level) === -1)
      ? `${d.date} (${dowLbl}) — Upcoming calendar day in current month`
      : `${d.date} (${dowLbl}) — Steps: ${Number(d.steps || 0).toLocaleString()} | Tool Calls: ${Number(d.tools || 0).toLocaleString()} | Est. Tokens: ~${formatCompactTokens(d.tokens || (d.steps * 215))} | Active Chats: ${d.sessions || 0}`;
  };
  let weekCol = 0, matchedSelectedDay = null;
  const colMonthMap = {};
  if (heatDays.length > 0) {
    const firstDow = computeIsoWeekday(heatDays[0].date, heatDays[0].weekday);
    for (let padRow = 0; padRow < firstDow; padRow++) {
      const padCell = document.createElement("div");
      padCell.className = "heat-cell pad";
      padCell.style.gridRow = String(padRow + 1);
      padCell.style.gridColumn = "1";
      heatGrid.appendChild(padCell);
    }
  }
  heatDays.forEach((d, idx) => {
    const dow = computeIsoWeekday(d.date, d.weekday);
    if (idx > 0 && dow === 0) weekCol++;
    const mNum = Number(String(d.date || "").slice(5, 7)), dayOfM = Number(String(d.date || "").slice(8, 10));
    if ((idx === 0 || dayOfM === 1) && mNum >= 1 && mNum <= 12 && colMonthMap[weekCol] === undefined) colMonthMap[weekCol] = MONTH_NAMES[mNum - 1];
    const cell = document.createElement("div");
    cell.className = "heat-cell" + (d.in_window === false ? " out-window" : "");
    cell.dataset.level = String(d.future ? -1 : (d.level ?? 0));
    cell.dataset.date = d.date;
    cell.style.gridRow = String(dow + 1);
    cell.style.gridColumn = String(weekCol + 1);
    cell.title = d.future
      ? `${d.date} (${DOW_NAMES[dow]}): Upcoming calendar day`
      : `${d.date} (${DOW_NAMES[dow]}): ${Number(d.steps || 0).toLocaleString()} steps, ${Number(d.tools || 0).toLocaleString()} tool calls, ~${formatCompactTokens(d.tokens || (d.steps * 215))} tokens`;
    if (state.selectedDate && state.selectedDate === d.date && !d.future) { cell.classList.add("selected"); matchedSelectedDay = d; }
    cell.addEventListener("click", () => {
      document.querySelectorAll(".heat-cell.selected").forEach((el) => el.classList.remove("selected"));
      cell.classList.add("selected");
      state.selectedDate = d.date;
      localStorage.setItem("nexus_selected_date", d.date);
      updateInspectorForDay(d);
    });
    heatGrid.appendChild(cell);
  });
  const totalWeekCols = heatDays.length > 0 ? (weekCol + 1) : 0;
  heatGrid.style.setProperty("--week-cols", String(totalWeekCols || 53));
  if (monthsRow) monthsRow.style.setProperty("--week-cols", String(totalWeekCols || 53));
  document.getElementById("heatmapRangeTag").textContent = `${periodBanner} · ${totalWeekCols} WEEKS`;
  const dowCol = document.querySelector(".heatmap-dow-col");
  if (dowCol) {
    dowCol.classList.toggle("compact-dow", window.innerWidth < 560 && totalWeekCols > 30);
  }
  if (monthsRow && totalWeekCols > 0) {
    let lastLabeledCol = -99;
    const effectiveColMonthMap = { ...colMonthMap };
    if (effectiveColMonthMap[0] && effectiveColMonthMap[1]) {
      delete effectiveColMonthMap[0];
    }
    for (let c = 0; c < totalWeekCols; c++) {
      const mSpan = document.createElement("span");
      mSpan.className = "heatmap-month-lbl";
      mSpan.style.gridColumn = String(c + 1);
      if (effectiveColMonthMap[c] && c < totalWeekCols - 1 && (c - lastLabeledCol >= 2)) {
        mSpan.textContent = effectiveColMonthMap[c];
        lastLabeledCol = c;
      }
      monthsRow.appendChild(mSpan);
    }
  }
  if (matchedSelectedDay) updateInspectorForDay(matchedSelectedDay);
  else {
    const nonFuture = heatDays.filter((x) => !x.future);
    const recentActive = [...nonFuture].reverse().find((x) => Number(x.steps || 0) > 0) || nonFuture[nonFuture.length - 1];
    if (recentActive) updateInspectorForDay(recentActive);
  }

  renderAllTimePlots(b);
  if (typeof renderHierarchyPanel === "function") renderHierarchyPanel(b);
  renderCodeHealth(b.code_health, b.version || "3.2.1");

  const ph = b.project_hierarchy || {};
  let totalActiveHandoffs = 0;
  [...(ph.top_projects || []), ...(ph.idle_projects || [])].forEach((p) => {
    totalActiveHandoffs += Number(p.staged_count || 0) + Number(p.in_work_handoff_count || 0);
  });
  const wsBadge = document.getElementById("navWorkspaceBadge");
  if (wsBadge) {
    wsBadge.textContent = String(totalActiveHandoffs);
    wsBadge.classList.toggle("hidden", totalActiveHandoffs === 0);
    wsBadge.style.display = totalActiveHandoffs === 0 ? "none" : "";
  }
}

applyThemeAndDensity(state.surface, state.density);

// Timeframe & Horizon Mode Controls
document.querySelectorAll(".tab-btn[data-timeframe]").forEach((btn) => {
  btn.classList.toggle("active", btn.dataset.timeframe === state.timeframe);
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn[data-timeframe]").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    state.timeframe = btn.dataset.timeframe;
    state.offset = 0;
    localStorage.setItem("nexus_timeframe", state.timeframe);
    fetchStats();
  });
});

document.querySelectorAll(".tab-btn[data-horizon]").forEach((btn) => {
  btn.classList.toggle("active", btn.dataset.horizon === state.horizon_mode);
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn[data-horizon]").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    state.horizon_mode = btn.dataset.horizon;
    state.offset = 0;
    localStorage.setItem("nexus_horizon_mode", state.horizon_mode);
    fetchStats();
  });
});

document.getElementById("stepPrevBtn")?.addEventListener("click", () => { state.offset = (state.offset || 0) + 1; fetchStats(); });
document.getElementById("stepNextBtn")?.addEventListener("click", () => { if (state.offset > 0) { state.offset -= 1; fetchStats(); } });
document.getElementById("stepTodayBtn")?.addEventListener("click", () => { state.offset = 0; fetchStats(); });

document.querySelectorAll(".metric-btn[data-metric]").forEach((btn) => {
  btn.classList.toggle("active", btn.dataset.metric === state.metric);
  btn.addEventListener("click", () => {
    const m = btn.dataset.metric === "tokens" ? "tokens" : "steps";
    state.metric = m;
    localStorage.setItem("nexus_metric", m);
    document.querySelectorAll(".metric-btn[data-metric]").forEach((b) => b.classList.toggle("active", b.dataset.metric === m));
    if (state.bundle) {
      renderAllTimePlots(state.bundle);
      if (typeof renderHierarchyPanel === "function") renderHierarchyPanel(state.bundle);
    }
  });
});

// Heatmap 26w | 53w Mobile Toggle
document.querySelectorAll("#heatWeeksToggle button").forEach((btn) => {
  btn.addEventListener("click", () => {
    state.heatWeeks = Number(btn.dataset.weeks || 26);
    document.querySelectorAll("#heatWeeksToggle button").forEach((b) => b.classList.toggle("active", Number(b.dataset.weeks) === state.heatWeeks));
    if (state.bundle) renderDashboard(state.bundle);
  });
});

// Primary Surface Switcher
function switchSurface(view) {
  state.surfaceView = view;
  const navAnalytics = document.getElementById("navAnalyticsBtn");
  const navWorkspace = document.getElementById("navWorkspaceBtn");
  const dashMain = document.getElementById("dashboardMain");
  const wsMain = document.getElementById("workspaceMain");
  const anControls = document.getElementById("analyticsControls");
  const sidebarToggle = document.getElementById("sidebarToggleBtn");

  const ctrCenter = document.querySelector(".controls-center");
  if (view === "workspace") {
    if (window.location.hash !== "#workspace") window.location.hash = "#workspace";
    if (navAnalytics) navAnalytics.classList.remove("active");
    if (navWorkspace) navWorkspace.classList.add("active");
    if (dashMain) dashMain.classList.add("hidden");
    if (wsMain) wsMain.classList.remove("hidden");
    if (anControls) anControls.classList.add("hidden");
    if (ctrCenter) ctrCenter.classList.add("hidden");
    if (sidebarToggle) sidebarToggle.classList.remove("hidden");
    if (window.WorkspaceExplorer) window.WorkspaceExplorer.initWorkspace();
  } else {
    if (window.location.hash && window.location.hash !== "#analytics") window.location.hash = "#analytics";
    if (navAnalytics) navAnalytics.classList.add("active");
    if (navWorkspace) navWorkspace.classList.remove("active");
    const authEl = document.getElementById("authOverlay");
    if (dashMain && authEl && authEl.classList.contains("hidden")) {
      dashMain.classList.remove("hidden");
    }
    if (wsMain) wsMain.classList.add("hidden");
    if (anControls) anControls.classList.remove("hidden");
    if (ctrCenter) ctrCenter.classList.remove("hidden");
    if (sidebarToggle) sidebarToggle.classList.add("hidden");
  }
}

const navAnalyticsBtn = document.getElementById("navAnalyticsBtn");
if (navAnalyticsBtn) navAnalyticsBtn.addEventListener("click", () => switchSurface("analytics"));

const navWorkspaceBtn = document.getElementById("navWorkspaceBtn");
if (navWorkspaceBtn) navWorkspaceBtn.addEventListener("click", () => switchSurface("workspace"));

window.addEventListener("hashchange", () => {
  if (window.location.hash === "#workspace") switchSurface("workspace");
  else switchSurface("analytics");
});

// Consolidated Settings Menu & Popover
const settingsMenuWrap = document.getElementById("settingsMenuWrap") || document.getElementById("styleMenuWrap");
const settingsMenuBtn = document.getElementById("settingsMenuBtn") || document.getElementById("styleMenuBtn");
const settingsPopover = document.getElementById("settingsPopover") || document.getElementById("stylePopover");
const pwaInstallPromptBtn = document.getElementById("pwaInstallPromptBtn");
const copyChromiumCmdBtn = document.getElementById("copyChromiumCmdBtn");
const chromiumCmdInput = document.getElementById("chromiumCmdInput");
let deferredPwaPrompt = null;

if (settingsMenuBtn && settingsPopover) {
  settingsMenuBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    const isHidden = settingsPopover.classList.toggle("hidden");
    settingsMenuBtn.setAttribute("aria-expanded", String(!isHidden));
  });
}

document.querySelectorAll(".theme-opt").forEach((btn) => {
  btn.addEventListener("click", (e) => { e.stopPropagation(); applyThemeAndDensity(btn.dataset.theme, state.density); });
});
document.querySelectorAll(".density-opt").forEach((btn) => {
  btn.addEventListener("click", (e) => { e.stopPropagation(); applyThemeAndDensity(state.surface, btn.dataset.density); });
});

if (chromiumCmdInput && window.location.protocol.startsWith("http")) {
  chromiumCmdInput.value = state.demoMode
    ? "google-chrome --app=https://agy-mcp.example.com/web"
    : `google-chrome --app=${window.location.origin}${window.location.pathname}`;
}

window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  deferredPwaPrompt = e;
  if (pwaInstallPromptBtn) pwaInstallPromptBtn.classList.remove("hidden");
});

const triggerInstall = async () => {
  if (!deferredPwaPrompt) return false;
  deferredPwaPrompt.prompt();
  await deferredPwaPrompt.userChoice.catch(() => {});
  deferredPwaPrompt = null;
  return true;
};

if (pwaInstallPromptBtn) {
  pwaInstallPromptBtn.addEventListener("click", async () => {
    if (await triggerInstall()) { pwaInstallPromptBtn.classList.add("hidden"); if (settingsPopover) settingsPopover.classList.add("hidden"); }
  });
}

if (copyChromiumCmdBtn && chromiumCmdInput) {
  copyChromiumCmdBtn.addEventListener("click", () => copyTextWithFeedback(copyChromiumCmdBtn, chromiumCmdInput.value, "Copy", 1500));
}

if ("serviceWorker" in navigator && window.location.protocol.startsWith("http")) {
  const basePrefix = window.location.pathname.replace(/\/web\/?$/, "");
  navigator.serviceWorker.register(basePrefix + "/web/sw.js", { scope: basePrefix ? (basePrefix + "/") : "/" }).catch(() => {});
}

document.addEventListener("click", (e) => {
  if (settingsMenuWrap && !settingsMenuWrap.contains(e.target) && settingsPopover) {
    settingsPopover.classList.add("hidden");
    if (settingsMenuBtn) settingsMenuBtn.setAttribute("aria-expanded", "false");
  }
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && settingsPopover) {
    settingsPopover.classList.add("hidden");
    if (settingsMenuBtn) settingsMenuBtn.setAttribute("aria-expanded", "false");
  }
});

function clearSensitiveView() {
  state.bundle = null; state.soloModel = ""; state.soloSubagent = ""; state.soloProject = "";
  if (typeof lastHierarchyBundle !== "undefined") lastHierarchyBundle = null;
  ["hierarchyProjectList", "heatmapGrid", "modelTabularLegendBody", "subagentTabularLegendBody", "velocityLineSvg", "subagentAreaSvg", "workspaceAreaSvg"].forEach((id) => {
    const el = document.getElementById(id); if (el) el.innerHTML = "";
  });
  const dlg = document.getElementById("uploadDialog"); if (dlg && dlg.open) dlg.close();
}

document.getElementById("unlockForm").addEventListener("submit", (e) => {
  e.preventDefault();
  state.demoMode = false; localStorage.removeItem("nexus_demo_mode");
  state.passphrase = document.getElementById("passInput").value.trim();
  fetchStats(state.period);
});

document.getElementById("previewDemoBtn").addEventListener("click", () => {
  state.demoMode = true; localStorage.setItem("nexus_demo_mode", "1");
  document.getElementById("authOverlay").classList.add("hidden");
  const targetMain = state.surfaceView === "workspace" ? document.getElementById("workspaceMain") : document.getElementById("dashboardMain");
  if (targetMain) targetMain.classList.remove("hidden");
  fetchStats(state.period);
});

document.getElementById("lockBtn").addEventListener("click", () => {
  localStorage.removeItem("nexus_passphrase"); sessionStorage.removeItem("nexus_passphrase"); localStorage.removeItem("nexus_demo_mode");
  state.passphrase = ""; state.demoMode = false;
  clearSensitiveView();
  document.getElementById("passInput").value = "";
  document.getElementById("authOverlay").classList.remove("hidden");
  document.getElementById("dashboardMain").classList.add("hidden");
  const wsMain = document.getElementById("workspaceMain");
  if (wsMain) wsMain.classList.add("hidden");
});

if (state.passphrase || state.demoMode) fetchStats(state.period);
if (window.location.hash === "#workspace") switchSurface("workspace");

function renderUnauthenticatedMediaViewer(session, artifact, t, sig) {
  const mediaUrl = `/web/media/${encodeURIComponent(t)}/${encodeURIComponent(sig)}/brain:${encodeURIComponent(session)}/${artifact}`;
  const fileName = artifact.split("/").pop() || "Visual Artifact";
  document.getElementById("authOverlay")?.classList.add("hidden");
  document.getElementById("dashboardMain")?.classList.add("hidden");
  document.getElementById("workspaceMain")?.classList.add("hidden");

  let viewer = document.getElementById("unauthMediaViewer");
  if (!viewer) {
    viewer = document.createElement("div");
    viewer.id = "unauthMediaViewer";
    viewer.className = "unauth-media-viewer";
    document.body.appendChild(viewer);
  }
  viewer.innerHTML = `
    <div class="unauth-viewer-bar mono">
      <span class="unauth-viewer-title">${escapeHtmlSafe(fileName)}</span>
      <button type="button" class="btn btn-primary mono" id="unauthUnlockBtn">↗ Unlock Full Workspace</button>
    </div>
    <div class="unauth-viewer-body">
      <img src="${escapeHtmlSafe(mediaUrl)}" alt="${escapeHtmlSafe(fileName)}" class="unauth-viewer-img" />
    </div>
  `;
  document.getElementById("unauthUnlockBtn")?.addEventListener("click", () => {
    viewer.remove();
    document.getElementById("authOverlay")?.classList.remove("hidden");
  });
}

function handleWorkspaceDeepLink() {
  const params = new URLSearchParams(window.location.search);
  const view = params.get("view");
  const session = params.get("session");
  const artifact = params.get("artifact");
  const t = params.get("t");
  const sig = params.get("sig");

  if (view === "workspace" || session) {
    const hasAuth = Boolean(state.passphrase || localStorage.getItem("nexus_passphrase") || state.demoMode);
    if (hasAuth) {
      switchSurface("workspace");
      if (session && window.WorkspaceExplorer) {
        window.WorkspaceExplorer.selectSession(session).then(() => {
          if (artifact) {
            const isImg = /\.(png|jpe?g|webp|gif|svg)$/i.test(artifact);
            if (isImg && t && sig) {
              const mediaUrl = `/web/media/${encodeURIComponent(t)}/${encodeURIComponent(sig)}/brain:${encodeURIComponent(session)}/${artifact}`;
              window.WorkspaceExplorer.openLightbox(mediaUrl, artifact.split("/").pop());
            } else {
              window.WorkspaceExplorer.viewFile(artifact, artifact.split("/").pop());
            }
          }
        });
      }
    } else if (session && artifact && t && sig) {
      renderUnauthenticatedMediaViewer(session, artifact, t, sig);
    } else {
      switchSurface("workspace");
    }
  }
}

handleWorkspaceDeepLink();
