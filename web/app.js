// AGY-NEXUS Overwatch — Dashboard Controller, 1-to-3 Column Combined Plot Legends & Controls (v2.6.0)

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

  const gridEl = document.getElementById("modelLegendGrid");
  if (gridEl) {
    gridEl.innerHTML = order.map((mk) => {
      const col = getModelColor(mk, surface);
      const r = rowMap[mk] || { actual_pct: 0, target_pct: 0, actual_calls: 0, est_tokens: 0 };
      const ap = Number(r.actual_pct || 0), tp = Number(r.target_pct || 0);
      const calls = Number(r.actual_calls || 0), toks = Number(r.est_tokens || 0);
      const isSolo = state.soloModel === mk, isDim = Boolean(state.soloModel && !isSolo);
      return `<button type="button" class="legend-cell ${isSolo ? "is-solo" : ""} ${isDim ? "is-dimmed" : ""}" data-model-key="${mk}" title="Click to solo ${col.label} on plot">
        <div class="lcell-top">
          <span class="lcell-name"><span class="swatch-sq" style="background:${col.fill};border-color:${col.cap}"></span><strong>${escapeHtmlSafe(col.short)}</strong><span class="lcell-sub">${escapeHtmlSafe(col.role)}</span></span>
          <span class="mono lcell-pct"><strong>${ap.toFixed(1)}%</strong> <span class="lcell-dim">/ ${tp}%</span></span>
        </div>
        <div class="lcell-bar-track"><div class="lcell-bar-fill" style="width:${Math.min(100, ap)}%;background:${col.fill}"></div><div class="lcell-bar-pin" style="left:${Math.min(100, tp)}%" title="Target ${tp}%"></div></div>
        <div class="lcell-meta mono"><span>${calls.toLocaleString()} calls</span><span>~${formatCompactTokens(toks)} tok</span><span>Pk ${formatMetricVal(stats.bandPeaks[mk] || 0, metric)}</span></div>
      </button>`;
    }).join("");

    gridEl.querySelectorAll(".legend-cell[data-model-key]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const mk = btn.getAttribute("data-model-key") || "";
        state.soloModel = state.soloModel === mk ? "" : mk;
        if (state.bundle) renderModelPlotAndLegend(state.bundle, state.metric, state.surface);
      });
    });
  }

  const unit = metric === "tokens" ? "tok" : "steps";
  const setTxt = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  setTxt("ftrModelAvg", `${formatMetricVal(stats.avgVal, metric)} ${unit}`);
  setTxt("ftrModelP95", `${formatMetricVal(stats.p95Val, metric)} ${unit}`);
  setTxt("ftrModelPeak", `${formatMetricVal(stats.peakVal, metric)} ${unit}`);
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

  const gridEl = document.getElementById("subagentLegendGrid");
  if (gridEl) {
    if (!legendItems.length) {
      gridEl.innerHTML = `<div class="hier-empty mono" style="grid-column:1/-1">No subagent executions recorded in this window.</div>`;
      return;
    }
    gridEl.innerHTML = legendItems.map((item, idx) => {
      const col = getSubagentColor(item.role, idx, surface);
      const share = ((item.steps / totSteps) * 100).toFixed(1);
      const isSolo = state.soloSubagent === item.role, isDim = Boolean(state.soloSubagent && !isSolo);
      const pkVal = stats.bandPeaks[item.role] || 0;
      return `<button type="button" class="legend-cell ${isSolo ? "is-solo" : ""} ${isDim ? "is-dimmed" : ""}" data-sub-role="${escapeHtmlSafe(item.role)}" title="Click to solo ${escapeHtmlSafe(item.role)} on plot">
        <div class="lcell-top"><span class="lcell-name"><span class="swatch-sq" style="background:${col.fill};border-color:${col.cap}"></span><strong class="mono">${escapeHtmlSafe(item.role)}</strong></span><span class="mono lcell-pct"><strong>${share}%</strong></span></div>
        <div class="lcell-meta mono"><span class="lcell-sub">${escapeHtmlSafe(item.modelLabel)}</span><span>${item.runs.toLocaleString()} runs</span><span>${item.steps.toLocaleString()} stp · ~${formatCompactTokens(item.tokens)}</span>${pkVal > 0 ? `<span>Pk ${formatMetricVal(pkVal, metric)}</span>` : ""}</div>
      </button>`;
    }).join("");

    gridEl.querySelectorAll(".legend-cell[data-sub-role]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const rk = btn.getAttribute("data-sub-role") || "";
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
  document.getElementById("kpiTopClient").textContent = topProdEntry ? topProdEntry[0] : "Gemini Mobile";

  const heatGrid = document.getElementById("heatmapGrid"), monthsRow = document.getElementById("heatmapMonthsRow");
  heatGrid.innerHTML = "";
  if (monthsRow) monthsRow.innerHTML = "";
  const heatDays = b.heatmap_series || [];
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
  document.getElementById("heatmapRangeTag").textContent = `${periodBanner} · ${totalWeekCols} WEEKS`;
  if (monthsRow && totalWeekCols > 0) {
    let lastLabeledCol = -99;
    for (let c = 0; c < totalWeekCols; c++) {
      const mSpan = document.createElement("span");
      mSpan.className = "heatmap-month-lbl";
      mSpan.style.gridColumn = String(c + 1);
      if (colMonthMap[c] && (c - lastLabeledCol >= 2)) { mSpan.textContent = colMonthMap[c]; lastLabeledCol = c; }
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
  renderCodeHealth(b.code_health, b.version || "2.6.0");
}

applyThemeAndDensity(state.surface, state.density);

document.querySelectorAll(".tab-btn[data-period]").forEach((btn) => {
  btn.classList.toggle("active", btn.dataset.period === state.period);
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn[data-period]").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    state.period = btn.dataset.period;
    state.soloProject = ""; state.soloSubagent = "";
    localStorage.setItem("nexus_period", state.period);
    fetchStats(state.period);
  });
});

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

const styleMenuWrap = document.getElementById("styleMenuWrap");
const styleMenuBtn = document.getElementById("styleMenuBtn");
const stylePopover = document.getElementById("stylePopover");
const appModeWrap = document.getElementById("appModeWrap");
const appModeBtn = document.getElementById("appModeBtn");
const appModePopover = document.getElementById("appModePopover");
const pwaInstallPromptBtn = document.getElementById("pwaInstallPromptBtn");
const copyChromiumCmdBtn = document.getElementById("copyChromiumCmdBtn");
const chromiumCmdInput = document.getElementById("chromiumCmdInput");
let deferredPwaPrompt = null;

styleMenuBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  const isHidden = stylePopover.classList.toggle("hidden");
  styleMenuBtn.setAttribute("aria-expanded", String(!isHidden));
  if (appModePopover) appModePopover.classList.add("hidden");
});
document.querySelectorAll(".theme-opt").forEach((btn) => {
  btn.addEventListener("click", (e) => { e.stopPropagation(); applyThemeAndDensity(btn.dataset.theme, state.density); });
});
document.querySelectorAll(".density-opt").forEach((btn) => {
  btn.addEventListener("click", (e) => { e.stopPropagation(); applyThemeAndDensity(state.surface, btn.dataset.density); });
});
if (chromiumCmdInput && window.location.protocol.startsWith("http")) {
  chromiumCmdInput.value = `google-chrome --app=${window.location.origin}${window.location.pathname}`;
}
const pwaHttpWarn = document.getElementById("pwaHttpWarn");
if (pwaHttpWarn && window.location.protocol === "http:" && window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1") {
  pwaHttpWarn.classList.remove("hidden");
}
if (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches) {
  const lbl = document.getElementById("appModeBtnLabel");
  if (lbl) lbl.textContent = "App ✓";
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
if (appModeBtn && appModePopover) {
  appModeBtn.addEventListener("click", async (e) => {
    e.stopPropagation();
    if (await triggerInstall()) return;
    appModePopover.classList.toggle("hidden");
    stylePopover.classList.add("hidden");
  });
}
if (pwaInstallPromptBtn) {
  pwaInstallPromptBtn.addEventListener("click", async () => {
    if (await triggerInstall()) { pwaInstallPromptBtn.classList.add("hidden"); appModePopover.classList.add("hidden"); }
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
  if (styleMenuWrap && !styleMenuWrap.contains(e.target)) { stylePopover.classList.add("hidden"); styleMenuBtn.setAttribute("aria-expanded", "false"); }
  if (appModeWrap && !appModeWrap.contains(e.target) && appModePopover) appModePopover.classList.add("hidden");
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") { stylePopover.classList.add("hidden"); styleMenuBtn.setAttribute("aria-expanded", "false"); if (appModePopover) appModePopover.classList.add("hidden"); }
});
function clearSensitiveView() {
  state.bundle = null; state.soloModel = ""; state.soloSubagent = ""; state.soloProject = "";
  if (typeof lastHierarchyBundle !== "undefined") lastHierarchyBundle = null;
  ["hierarchyProjectList", "heatmapGrid", "modelLegendGrid", "subagentLegendGrid", "velocityLineSvg", "subagentAreaSvg", "workspaceAreaSvg"].forEach((id) => {
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
  document.getElementById("dashboardMain").classList.remove("hidden");
  fetchStats(state.period);
});
document.getElementById("lockBtn").addEventListener("click", () => {
  localStorage.removeItem("nexus_passphrase"); sessionStorage.removeItem("nexus_passphrase"); localStorage.removeItem("nexus_demo_mode");
  state.passphrase = ""; state.demoMode = false;
  clearSensitiveView();
  document.getElementById("passInput").value = "";
  document.getElementById("authOverlay").classList.remove("hidden");
  document.getElementById("dashboardMain").classList.add("hidden");
});
if (state.passphrase || state.demoMode) fetchStats(state.period);
