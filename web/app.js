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
  const gPool = pools.google || q.google_pool || {}, pWin = q.partner_weekly_window || q.partner_pool || {};
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

  const ceilPct = pWin.recommended_cumulative_ceiling_pct ?? 28.6;
  const wRem = Math.max(0, 100 - partnerTot), idealRem = Math.max(0, Number((100 - ceilPct).toFixed(1)));
  const dayIdx = pWin.day_of_week_index || 2;
  document.getElementById("kpiResetDays").textContent = Math.max(1, 8 - dayIdx) + "d left";
  document.getElementById("kpiPartnerRem").textContent = wRem.toFixed(1) + "%";
  document.getElementById("kpiPartnerPaceBadge").textContent = (pools.claude && pools.claude.status === "HEALTHY") ? "OK" : "COOLDOWN";
  document.getElementById("kpiPartnerBar").style.width = Math.min(100, wRem) + "%";
  document.getElementById("kpiIdealMarker").style.left = Math.min(100, idealRem) + "%";
  document.getElementById("kpiIdealRem").textContent = idealRem.toFixed(1) + "%";
  document.getElementById("kpiFiveHour").textContent = (pWin.daily_target_pct ?? 14.3).toFixed(1) + "%/d";

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
  if (stepNextBtn) stepNextBtn.disabled = (state.offset || 0) >= 0;
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
  const hs = w.protocol_handshakes || {};
  const rpcEl = document.getElementById("kpiRpcCount");
  rpcEl.textContent = w.total_recorded_calls ?? 0;
  rpcEl.title = hs.calls
    ? `${w.total_recorded_calls ?? 0} tool calls · ${hs.calls} protocol handshakes (${Number(hs.tools_list_kb || 0).toFixed(1)} KB tools/list)`
    : `${w.total_recorded_calls ?? 0} tool calls`;
  let topClientName = topProdEntry ? topProdEntry[0] : "Gemini Mobile";
  if (window.innerWidth < 560 && topClientName.includes("Gemini Web / Cloud MCP")) {
    topClientName = "Gemini Cloud";
  } else if (window.innerWidth < 560 && topClientName.length > 14) {
    topClientName = topClientName.replace("Gemini Web / Cloud MCP", "Gemini Cloud").replace(" / ", "/");
  }
  document.getElementById("kpiTopClient").textContent = topClientName;

  if (typeof renderDailyHeatmap === "function") {
    renderDailyHeatmap(b, periodBanner);
  }

  renderAllTimePlots(b);
  if (typeof renderHierarchyPanel === "function") renderHierarchyPanel(b);
  renderCodeHealth(b.code_health, b.version || "3.2.5");

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

document.getElementById("stepPrevBtn")?.addEventListener("click", () => { state.offset = Math.min(0, Number(state.offset) || 0) - 1; fetchStats(); });
document.getElementById("stepNextBtn")?.addEventListener("click", () => { if ((Number(state.offset) || 0) < 0) { state.offset = Math.min(0, (Number(state.offset) || 0) + 1); fetchStats(); } });
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

function syncV9CrossLink() {
  const link = document.getElementById("navV9Link");
  if (link) link.href = `${window.location.pathname.replace(/\/web(?:\/index\.html)?\/?$/, "")}/web/v9${state.demoMode ? "?demo=1" : ""}#${state.surfaceView === "workspace" ? "workspace" : "analytics"}`;
}
function switchSurface(view) {
  state.surfaceView = view;
  const navAn = document.getElementById("navAnalyticsBtn"), navWs = document.getElementById("navWorkspaceBtn");
  const dashMain = document.getElementById("dashboardMain"), wsMain = document.getElementById("workspaceMain");
  const anCtrl = document.getElementById("analyticsControls"), sideBtn = document.getElementById("sidebarToggleBtn");
  const ctrCenter = document.querySelector(".controls-center"), authEl = document.getElementById("authOverlay");
  const isUnlockedView = Boolean(authEl && authEl.classList.contains("hidden"));
  if (view === "workspace") {
    if (window.location.hash !== "#workspace") window.location.hash = "#workspace";
    navAn?.classList.remove("active"); navWs?.classList.add("active");
    dashMain?.classList.add("hidden");
    if (wsMain && isUnlockedView) wsMain.classList.remove("hidden");
    anCtrl?.classList.add("hidden"); ctrCenter?.classList.add("hidden"); sideBtn?.classList.remove("hidden");
    if (window.WorkspaceExplorer && isUnlockedView) window.WorkspaceExplorer.initWorkspace();
  } else {
    if (window.location.hash && window.location.hash !== "#analytics") window.location.hash = "#analytics";
    navAn?.classList.add("active"); navWs?.classList.remove("active");
    if (dashMain && isUnlockedView) dashMain.classList.remove("hidden");
    wsMain?.classList.add("hidden");
    anCtrl?.classList.remove("hidden"); ctrCenter?.classList.remove("hidden"); sideBtn?.classList.add("hidden");
  }
  syncV9CrossLink();
}
document.getElementById("navAnalyticsBtn")?.addEventListener("click", () => switchSurface("analytics"));
document.getElementById("navWorkspaceBtn")?.addEventListener("click", () => switchSurface("workspace"));
window.addEventListener("hashchange", () => switchSurface(window.location.hash === "#workspace" ? "workspace" : "analytics"));
syncV9CrossLink();

const settingsMenuWrap = document.getElementById("settingsMenuWrap") || document.getElementById("styleMenuWrap");
const settingsMenuBtn = document.getElementById("settingsMenuBtn") || document.getElementById("styleMenuBtn");
const settingsPopover = document.getElementById("settingsPopover") || document.getElementById("stylePopover");
const pwaInstallPromptBtn = document.getElementById("pwaInstallPromptBtn");
const copyChromiumCmdBtn = document.getElementById("copyChromiumCmdBtn"), chromiumCmdInput = document.getElementById("chromiumCmdInput");
let deferredPwaPrompt = null;

settingsMenuBtn?.addEventListener("click", (e) => {
  e.stopPropagation();
  if (!settingsPopover) return;
  settingsMenuBtn.setAttribute("aria-expanded", String(!settingsPopover.classList.toggle("hidden")));
});
document.querySelectorAll(".theme-opt").forEach((b) => b.addEventListener("click", (e) => { e.stopPropagation(); applyThemeAndDensity(b.dataset.theme, state.density); }));
document.querySelectorAll(".density-opt").forEach((b) => b.addEventListener("click", (e) => { e.stopPropagation(); applyThemeAndDensity(state.surface, b.dataset.density); }));

if (chromiumCmdInput && window.location.protocol.startsWith("http")) {
  chromiumCmdInput.value = state.demoMode ? "google-chrome --app=https://agy-mcp.example.com/web" : `google-chrome --app=${window.location.origin}${window.location.pathname}`;
}
window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); deferredPwaPrompt = e; pwaInstallPromptBtn?.classList.remove("hidden"); });
pwaInstallPromptBtn?.addEventListener("click", async () => {
  if (!deferredPwaPrompt) return;
  deferredPwaPrompt.prompt(); await deferredPwaPrompt.userChoice.catch(() => {}); deferredPwaPrompt = null;
  pwaInstallPromptBtn.classList.add("hidden"); settingsPopover?.classList.add("hidden");
});
if (copyChromiumCmdBtn && chromiumCmdInput) {
  copyChromiumCmdBtn.addEventListener("click", () => copyTextWithFeedback(copyChromiumCmdBtn, chromiumCmdInput.value, "Copy", 1500));
}
if ("serviceWorker" in navigator && window.location.protocol.startsWith("http")) {
  const basePrefix = window.location.pathname.replace(/\/web\/?$/, "");
  const hadCtrl = Boolean(navigator.serviceWorker.controller);
  let swReloading = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (!hadCtrl || swReloading) return;
    try { if (sessionStorage.getItem("nexus_sw_reloaded") === "3.2.5") return; sessionStorage.setItem("nexus_sw_reloaded", "3.2.5"); } catch (_) {}
    swReloading = true; window.location.reload();
  });
  navigator.serviceWorker.register(basePrefix + "/web/sw.js", { scope: basePrefix ? (basePrefix + "/") : "/", updateViaCache: "none" }).catch(() => {});
}
document.addEventListener("click", (e) => {
  if (settingsMenuWrap && !settingsMenuWrap.contains(e.target) && settingsPopover) {
    settingsPopover.classList.add("hidden"); settingsMenuBtn?.setAttribute("aria-expanded", "false");
  }
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && settingsPopover) { settingsPopover.classList.add("hidden"); settingsMenuBtn?.setAttribute("aria-expanded", "false"); }
});

function clearSensitiveView() {
  state.bundle = null; state.soloModel = ""; state.soloSubagent = ""; state.soloProject = "";
  if (typeof lastHierarchyBundle !== "undefined") lastHierarchyBundle = null;
  ["hierarchyProjectList", "heatmapGrid", "modelTabularLegendBody", "subagentTabularLegendBody", "velocityLineSvg", "subagentAreaSvg", "workspaceAreaSvg"].forEach((id) => {
    const el = document.getElementById(id); if (el) el.innerHTML = "";
  });
  ["uploadDialog", "lightboxModal", "sheetExportDialog"].forEach((id) => {
    const dlg = document.getElementById(id); if (dlg?.open) dlg.close();
  });
  window.GallerySelect?.cleanupGestures?.();
  window.GalleryView?.resetLightboxState?.();
  window.WorkspaceExplorer?.resetSensitiveState?.();
}

document.getElementById("unlockForm").addEventListener("submit", (e) => {
  e.preventDefault(); state.demoMode = false; localStorage.removeItem("nexus_demo_mode"); syncV9CrossLink();
  state.passphrase = document.getElementById("passInput").value.trim(); fetchStats(state.period);
});
document.getElementById("previewDemoBtn").addEventListener("click", () => {
  state.demoMode = true; localStorage.setItem("nexus_demo_mode", "1"); syncV9CrossLink();
  document.getElementById("authOverlay").classList.add("hidden");
  document.getElementById(state.surfaceView === "workspace" ? "workspaceMain" : "dashboardMain")?.classList.remove("hidden");
  fetchStats(urlPeriod ? state.period : undefined);
});
document.getElementById("lockBtn").addEventListener("click", () => {
  localStorage.removeItem("nexus_passphrase"); sessionStorage.removeItem("nexus_passphrase"); localStorage.removeItem("nexus_demo_mode");
  state.passphrase = ""; state.demoMode = false; clearSensitiveView(); syncV9CrossLink();
  document.getElementById("passInput").value = "";
  document.getElementById("authOverlay").classList.remove("hidden");
  document.getElementById("dashboardMain").classList.add("hidden");
  document.getElementById("workspaceMain")?.classList.add("hidden");
});
if (state.passphrase || state.demoMode) fetchStats((state.demoMode && !urlPeriod) ? undefined : state.period);
if (window.location.hash === "#workspace") switchSurface("workspace");
function buildSignedMediaUrl(session, artifact, t, sig, scopeParam) {
  const effScope = scopeParam || `brain:${session}`;
  return `/web/media/${encodeURIComponent(t)}/${encodeURIComponent(sig)}/${encodeURIComponent(effScope).replace(/%3A/gi, ":")}/${artifact}`;
}
function renderUnauthenticatedMediaViewer(session, artifact, t, sig, scopeParam) {
  const mediaUrl = buildSignedMediaUrl(session, artifact, t, sig, scopeParam), fileName = artifact.split("/").pop() || "Visual Artifact";
  ["authOverlay", "dashboardMain", "workspaceMain"].forEach((id) => document.getElementById(id)?.classList.add("hidden"));
  let viewer = document.getElementById("unauthMediaViewer");
  if (!viewer) { viewer = document.createElement("div"); viewer.id = "unauthMediaViewer"; viewer.className = "unauth-media-viewer"; document.body.appendChild(viewer); }
  viewer.innerHTML = `<div class="unauth-viewer-bar mono"><span class="unauth-viewer-title">${escapeHtmlSafe(fileName)}</span><button type="button" class="btn btn-primary mono" id="unauthUnlockBtn">↗ Unlock Full Workspace</button></div><div class="unauth-viewer-body"><img src="${escapeHtmlSafe(mediaUrl)}" alt="${escapeHtmlSafe(fileName)}" class="unauth-viewer-img" /></div>`;
  document.getElementById("unauthUnlockBtn")?.addEventListener("click", () => { viewer.remove(); document.getElementById("authOverlay")?.classList.remove("hidden"); });
}
function handleWorkspaceDeepLink() {
  const params = new URLSearchParams(window.location.search);
  const view = params.get("view"), rawSess = params.get("session") || "", artifact = params.get("artifact");
  const session = /^[a-zA-Z0-9_-]{1,64}$/.test(rawSess) ? rawSess : "";
  const t = params.get("t"), sig = params.get("sig"), scopeParam = params.get("scope") || "";
  if (view !== "workspace" && !session) return;
  const hasAuth = Boolean(state.passphrase || localStorage.getItem("nexus_passphrase") || state.demoMode);
  if (hasAuth) {
    switchSurface("workspace");
    if (session && window.WorkspaceExplorer) {
      window.WorkspaceExplorer.selectSession(session).then(() => {
        if (!artifact) return;
        if (/\.(png|jpe?g|webp|gif|svg)$/i.test(artifact) && t && sig) {
          window.WorkspaceExplorer.openLightbox(buildSignedMediaUrl(session, artifact, t, sig, scopeParam), artifact.split("/").pop());
        } else {
          window.WorkspaceExplorer.viewFile(artifact, artifact.split("/").pop());
        }
      });
    }
  } else if (session && artifact && t && sig) {
    renderUnauthenticatedMediaViewer(session, artifact, t, sig, scopeParam);
  } else {
    switchSurface("workspace");
  }
}
handleWorkspaceDeepLink();
