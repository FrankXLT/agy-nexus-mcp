function renderDashboard(b) {
      const q = b.quota_and_pools || {};
      const pools = q.pools || {};
      const gPool = pools.google || q.google_pool || {};
      const pPace = q.partner_weekly_pacing || q.partner_pool || {};
      const kpis = b.kpis || b.summary || {};
      const w = b.wire_telemetry || {};
      const periodObj = typeof b.period === "object" ? b.period : { key: b.period || "last_90d", active_days: kpis.active_days || 0 };
      let argonPct = 70.3, flashPct = 29.6, claudePct = 0.1, gptPct = 0.0;
      if (Array.isArray(b.model_usage_vs_target)) {
        b.model_usage_vs_target.forEach((row) => {
          if (row.model_key === "argon_pro") argonPct = Number(row.actual_pct || 0);
          if (row.model_key === "flash") flashPct = Number(row.actual_pct || 0);
          if (row.model_key === "claude_partner") claudePct = Number(row.actual_pct || 0);
          if (row.model_key === "gpt_oss") gptPct = Number(row.actual_pct || 0); });
      }
      const googleTot = Math.min(100, Number((argonPct + flashPct).toFixed(1)));
      const partnerTot = Math.max(0, Number((claudePct + gptPct).toFixed(1)));
      document.getElementById("kpiProfileTag").textContent = String(q.active_tier_profile || q.active_profile || "ultra-20x").toUpperCase();
      document.getElementById("kpiGoogleShare").textContent = googleTot.toFixed(1) + "%";
      document.getElementById("kpiGoogleStatus").textContent = gPool.status || "HEALTHY";
      document.getElementById("kpiGoogleBar").style.width = googleTot + "%";
      document.getElementById("kpiArgonPct").textContent = argonPct.toFixed(1) + "%";
      document.getElementById("kpiFlashPct").textContent = flashPct.toFixed(1) + "%";
      const ceilPct = pPace.recommended_cumulative_ceiling_pct ?? 28.6;
      const wRem = Math.max(0, 100 - partnerTot);
      const idealRem = Math.max(0, Number((100 - ceilPct).toFixed(1)));
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
      const compPct = w.budget_compliance_pct ?? 100.0;
      const avgKb = w.avg_kb ?? 11.4;
      const maxKb = w.max_kb ?? 19.3;
      const mcpTok = w.total_mcp_tokens ?? 0;
      const byProd = w.by_product || {};
      const topProdEntry = Object.entries(byProd).sort((a, b) => (b[1].calls || 0) - (a[1].calls || 0))[0];
      document.getElementById("kpiCompliance").textContent = Number(compPct).toFixed(1) + "%";
      document.getElementById("kpiMcpTokens").textContent = formatCompactTokens(mcpTok) + " MCP tok";
      document.getElementById("kpiAvgBytes").textContent = Number(avgKb).toFixed(1) + " / " + Number(maxKb).toFixed(1) + " KB";
      document.getElementById("kpiRpcCount").textContent = w.total_recorded_calls ?? 0;
      document.getElementById("kpiTopClient").textContent = topProdEntry ? topProdEntry[0] : "Gemini Mobile";
      const setModelRow = (idTxt, idBar, val) => {
        document.getElementById(idTxt).textContent = val.toFixed(1) + "%";
        document.getElementById(idBar).style.width = Math.min(100, val) + "%"; };
      setModelRow("rowArgonActual", "barArgonActual", argonPct);
      setModelRow("rowFlashActual", "barFlashActual", flashPct);
      setModelRow("rowClaudeActual", "barClaudeActual", claudePct);
      setModelRow("rowGptActual", "barGptActual", gptPct);
      document.getElementById("ftrGoogleTot").textContent = googleTot.toFixed(1) + "%";
      document.getElementById("ftrPartnerTot").textContent = partnerTot.toFixed(1) + "%";
      const heatGrid = document.getElementById("heatmapGrid");
      const monthsRow = document.getElementById("heatmapMonthsRow");
      heatGrid.innerHTML = "";
      if (monthsRow) monthsRow.innerHTML = "";
      const heatDays = b.heatmap_series || [];
      const updateInspectorForDay = (d) => {
        const dowLbl = DOW_NAMES[computeIsoWeekday(d.date, d.weekday)] || "";
        if (d.future || Number(d.level) === -1) {
          document.getElementById("heatInspector").textContent =
            `${d.date} (${dowLbl}) — Upcoming calendar day in current month`;
          return; }
        document.getElementById("heatInspector").textContent =
          `${d.date} (${dowLbl}) — Steps: ${Number(d.steps || 0).toLocaleString()} | Tool Calls: ${Number(d.tools || 0).toLocaleString()} | Est. Tokens: ~${formatCompactTokens(d.tokens || (d.steps * 215))} | Active Chats: ${d.sessions || 0}`; };
      let weekCol = 0;
      const colMonthMap = {};
      let matchedSelectedDay = null;
      if (heatDays.length > 0) {
        const firstDow = computeIsoWeekday(heatDays[0].date, heatDays[0].weekday);
        for (let padRow = 0; padRow < firstDow; padRow++) {
          const padCell = document.createElement("div");
          padCell.className = "heat-cell pad";
          padCell.style.gridRow = String(padRow + 1);
          padCell.style.gridColumn = "1";
          heatGrid.appendChild(padCell); }
      }
      heatDays.forEach((d, idx) => {
        const dow = computeIsoWeekday(d.date, d.weekday);
        if (idx > 0 && dow === 0) {
          weekCol++; }
        const mNum = Number(String(d.date || "").slice(5, 7));
        const dayOfM = Number(String(d.date || "").slice(8, 10));
        if ((idx === 0 || dayOfM === 1) && mNum >= 1 && mNum <= 12 && colMonthMap[weekCol] === undefined) {
          colMonthMap[weekCol] = MONTH_NAMES[mNum - 1]; }
        const cell = document.createElement("div");
        cell.className = "heat-cell";
        if (d.in_window === false) {
          cell.classList.add("out-window"); }
        const lvl = d.future ? -1 : (d.level ?? 0);
        cell.dataset.level = String(lvl);
        cell.dataset.date = d.date;
        cell.dataset.dow = DOW_NAMES[dow];
        cell.style.gridRow = String(dow + 1);
        cell.style.gridColumn = String(weekCol + 1);
        if (d.future) {
          cell.title = `${d.date} (${DOW_NAMES[dow]}): Upcoming calendar day`;
        } else {
          cell.title = `${d.date} (${DOW_NAMES[dow]}): ${Number(d.steps || 0).toLocaleString()} steps, ${Number(d.tools || 0).toLocaleString()} tool calls, ~${formatCompactTokens(d.tokens || (d.steps * 215))} tokens`; }
        if (state.selectedDate && state.selectedDate === d.date && !d.future) {
          cell.classList.add("selected");
          matchedSelectedDay = d; }
        cell.addEventListener("click", () => {
          document.querySelectorAll(".heat-cell.selected").forEach(el => el.classList.remove("selected"));
          cell.classList.add("selected");
          state.selectedDate = d.date;
          localStorage.setItem("nexus_selected_date", d.date);
          updateInspectorForDay(d); });
        heatGrid.appendChild(cell); });
      const totalWeekCols = heatDays.length > 0 ? (weekCol + 1) : 0;
      document.getElementById("heatmapRangeTag").textContent = `${periodBanner} · ${totalWeekCols} WEEKS`;
      if (monthsRow && totalWeekCols > 0) {
        let lastLabeledCol = -99;
        for (let c = 0; c < totalWeekCols; c++) {
          const mSpan = document.createElement("span");
          mSpan.className = "heatmap-month-lbl";
          mSpan.style.gridColumn = String(c + 1);
          if (colMonthMap[c] && (c - lastLabeledCol >= 2)) {
            mSpan.textContent = colMonthMap[c];
            lastLabeledCol = c; }
          monthsRow.appendChild(mSpan); }
      }
      if (matchedSelectedDay) {
        updateInspectorForDay(matchedSelectedDay);
      } else {
        const nonFutureDays = heatDays.filter(x => !x.future);
        const recentActive = [...nonFutureDays].reverse().find(x => Number(x.steps || 0) > 0) || nonFutureDays[nonFutureDays.length - 1];
        if (recentActive) {
          updateInspectorForDay(recentActive); }
      }
      const svg = document.getElementById("velocityLineSvg");
      const velSeries = b.velocity_series || {};
      const validHeatDays = heatDays.filter(d => !d.future);
      let vDates = Array.isArray(velSeries.dates) && velSeries.dates.length ? velSeries.dates : validHeatDays.slice(-30).map(d => d.date);
      let vVals = Array.isArray(velSeries.values) && velSeries.values.length ? velSeries.values : validHeatDays.slice(-30).map(d => d.steps || 0);
      const resLabel = (velSeries.resolution || "4h sub-daily").toUpperCase();
      document.getElementById("linePlotTag").textContent = `${resLabel} // SOLID = ACTUAL, DASHED = AVG`;
      if (vDates.length > 0) {
        const W = 620, H = 185, padL = 44, padR = 14, padT = 14, padB = 24;
        const plotW = W - padL - padR;
        const plotH = H - padT - padB;
        const maxY = Math.max(100, ...vVals);
        const nonZeroVals = vVals.filter(v => v > 0);
        const targetYVal = Math.round(nonZeroVals.length ? (nonZeroVals.reduce((a, b) => a + b, 0) / nonZeroVals.length) : (maxY * 0.45));
        const xAt = (i) => padL + (vVals.length === 1 ? plotW / 2 : (i / (vVals.length - 1)) * plotW);
        const yAt = (v) => padT + plotH - (Math.min(maxY, v) / maxY) * plotH;
        const pts = vVals.map((v, i) => `${xAt(i).toFixed(1)},${yAt(v || 0).toFixed(1)}`).join(" ");
        const areaPts = `${xAt(0).toFixed(1)},${(padT + plotH).toFixed(1)} ${pts} ${xAt(vVals.length - 1).toFixed(1)},${(padT + plotH).toFixed(1)}`;
        const targetY = yAt(targetYVal).toFixed(1);
        svg.innerHTML = `
          <line class="grid-line" x1="${padL}" y1="${padT}" x2="${W - padR}" y2="${padT}" />
          <line class="grid-line" x1="${padL}" y1="${padT + plotH / 2}" x2="${W - padR}" y2="${padT + plotH / 2}" />
          <line class="grid-line" x1="${padL}" y1="${padT + plotH}" x2="${W - padR}" y2="${padT + plotH}" />
          <text class="axis-label" x="2" y="${padT + 4}">${maxY >= 1000 ? (maxY / 1000).toFixed(1) + "k" : maxY}</text>
          <text class="axis-label" x="2" y="${targetY - 3}">Avg:${targetYVal >= 1000 ? (targetYVal / 1000).toFixed(1) + "k" : targetYVal}</text>
          <text class="axis-label" x="2" y="${padT + plotH}">0</text>
          <polygon points="${areaPts}" fill="var(--accent-focal-dim)" />
          <line x1="${padL}" y1="${targetY}" x2="${W - padR}" y2="${targetY}" stroke="var(--text-secondary)" stroke-width="1.3" stroke-dasharray="5 4" />
          <polyline fill="none" stroke="var(--accent-focal)" stroke-width="1.8" points="${pts}" />
          <text class="axis-label" x="${padL}" y="${H - 4}">${vDates[0]}</text>
          <text class="axis-label" x="${W - padR - 92}" y="${H - 4}">${vDates[vDates.length - 1]}</text>
        `; }
      const rolesObj = b.subagent_role_breakdown || {};
      const roleEntries = Object.entries(rolesObj)
        .map(([role, stats]) => ({
          name: role,
          role,
          runs: Number((stats && stats.runs) || 0),
          steps: Number((stats && stats.steps) || 0),
          tokens: Number((stats && stats.tokens) || (Number((stats && stats.steps) || 0) * 240)),
        }))
        .sort((a, b) => b.steps - a.steps);
      renderStackedAreaChart("subagentAreaSvg", "subagentLegend", "subagentResTag", b.subagent_series, validHeatDays, roleEntries);
      const subBody = document.getElementById("subagentTableBody");
      if (subBody) {
        subBody.innerHTML = "";
        const totSubRuns = roleEntries.reduce((acc, x) => acc + x.runs, 0);
        const totSubSteps = Math.max(1, roleEntries.reduce((acc, x) => acc + x.steps, 0));
        const subTag = document.getElementById("subagentTotalTag");
        if (subTag) subTag.textContent = totSubRuns.toLocaleString() + " RUNS";
        roleEntries.forEach((item, idx) => {
          const rLow = item.role.toLowerCase();
          const poolLabel = rLow.includes("claude")
            ? "Claude 5.5"
            : (rLow.includes("flash") ? "Flash 3.8" : "Argon 4 Pro");
          const share = ((item.steps / totSubSteps) * 100).toFixed(1) + "%";
          const dotColor = idx < 5 ? SERIES_COLORS[idx % SERIES_COLORS.length] : SERIES_COLORS[5];
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td><span class="swatch-dot" style="background:${dotColor};margin-right:6px;"></span><strong class="mono">${item.role}</strong></td>
            <td style="color:var(--text-secondary)">${poolLabel}</td>
            <td class="mono">${item.runs.toLocaleString()}</td>
            <td class="mono">${item.steps.toLocaleString()}</td>
            <td class="mono">~${formatCompactTokens(item.tokens)}</td>
            <td class="mono">${share}</td>
          `;
          subBody.appendChild(tr); });
      }
      const wsList = (b.top_workspaces || []).map(w => ({
        name: w.workspace,
        workspace: w.workspace,
        sessions: w.sessions,
        steps: w.steps,
        tokens: Number(w.tokens || (w.steps * 215)),
      }));
      renderStackedAreaChart("workspaceAreaSvg", "workspaceLegend", "workspaceResTag", b.workspace_series, validHeatDays, wsList);
      const tbody = document.getElementById("workspaceTableBody");
      tbody.innerHTML = "";
      const totWsSteps = Math.max(1, wsList.reduce((acc, x) => acc + (x.steps || 0), 0));
      const wsTag = document.getElementById("workspaceTotalTag");
      if (wsTag) wsTag.textContent = wsList.length + " PROJECTS";
      wsList.forEach((ws, idx) => {
        const share = ((ws.steps / totWsSteps) * 100).toFixed(1) + "%";
        const dotColor = idx < 5 ? SERIES_COLORS[idx % SERIES_COLORS.length] : SERIES_COLORS[5];
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><span class="swatch-dot" style="background:${dotColor};margin-right:6px;"></span><strong>${ws.workspace}</strong></td>
          <td class="mono">${ws.sessions}</td>
          <td class="mono">${Number(ws.steps).toLocaleString()}</td>
          <td class="mono">~${formatCompactTokens(ws.tokens)}</td>
          <td class="mono">${share}</td>
        `;
        tbody.appendChild(tr); });
    }
    applyThemeAndDensity(state.surface, state.density);
    document.querySelectorAll(".tab-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.period === state.period);
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        state.period = btn.dataset.period;
        localStorage.setItem("nexus_period", state.period);
        fetchStats(state.period); });
    });
    const styleMenuWrap = document.getElementById("styleMenuWrap");
    const styleMenuBtn = document.getElementById("styleMenuBtn");
    const stylePopover = document.getElementById("stylePopover");
    styleMenuBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const isHidden = stylePopover.classList.toggle("hidden");
      styleMenuBtn.setAttribute("aria-expanded", String(!isHidden));
      if (appModePopover) appModePopover.classList.add("hidden"); });
    document.querySelectorAll(".theme-opt").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        applyThemeAndDensity(btn.dataset.theme, state.density); });
    });
    document.querySelectorAll(".density-opt").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        applyThemeAndDensity(state.surface, btn.dataset.density); });
    });
    const appModeWrap = document.getElementById("appModeWrap");
    const appModeBtn = document.getElementById("appModeBtn");
    const appModePopover = document.getElementById("appModePopover");
    const pwaInstallPromptBtn = document.getElementById("pwaInstallPromptBtn");
    const copyChromiumCmdBtn = document.getElementById("copyChromiumCmdBtn");
    const chromiumCmdInput = document.getElementById("chromiumCmdInput");
    let deferredPwaPrompt = null;
    if (chromiumCmdInput && window.location.protocol.startsWith("http")) {
      chromiumCmdInput.value = `google-chrome --app=${window.location.origin}${window.location.pathname}`; }
    const pwaHttpWarn = document.getElementById("pwaHttpWarn");
    if (pwaHttpWarn && window.location.protocol === "http:" && window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1") {
      pwaHttpWarn.classList.remove("hidden"); }
    if (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches) {
      const lbl = document.getElementById("appModeBtnLabel");
      if (lbl) lbl.textContent = "App ✓"; }
    window.addEventListener("beforeinstallprompt", (e) => {
      e.preventDefault();
      deferredPwaPrompt = e;
      if (pwaInstallPromptBtn) pwaInstallPromptBtn.classList.remove("hidden"); });
    if (appModeBtn && appModePopover) {
      appModeBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        if (deferredPwaPrompt) {
          deferredPwaPrompt.prompt();
          await deferredPwaPrompt.userChoice.catch(() => {});
          deferredPwaPrompt = null;
          return; }
        appModePopover.classList.toggle("hidden");
        stylePopover.classList.add("hidden"); });
    }
    if (pwaInstallPromptBtn) {
      pwaInstallPromptBtn.addEventListener("click", async () => {
        if (!deferredPwaPrompt) return;
        deferredPwaPrompt.prompt();
        await deferredPwaPrompt.userChoice.catch(() => {});
        deferredPwaPrompt = null;
        pwaInstallPromptBtn.classList.add("hidden");
        appModePopover.classList.add("hidden"); });
    }
    if (copyChromiumCmdBtn && chromiumCmdInput) {
      copyChromiumCmdBtn.addEventListener("click", () => {
        navigator.clipboard.writeText(chromiumCmdInput.value).catch(() => {});
        copyChromiumCmdBtn.textContent = "Copied!";
        setTimeout(() => { copyChromiumCmdBtn.textContent = "Copy"; }, 1500); });
    }
    if ("serviceWorker" in navigator && window.location.protocol.startsWith("http")) {
      const basePrefix = window.location.pathname.replace(/\/web\/?$/, "");
      const swPath = basePrefix + "/web/sw.js";
      const swScope = basePrefix ? (basePrefix + "/") : "/";
      navigator.serviceWorker.register(swPath, { scope: swScope }).catch(() => {}); }
    document.addEventListener("click", (e) => {
      if (styleMenuWrap && !styleMenuWrap.contains(e.target)) {
        stylePopover.classList.add("hidden");
        styleMenuBtn.setAttribute("aria-expanded", "false"); }
      if (appModeWrap && !appModeWrap.contains(e.target) && appModePopover) {
        appModePopover.classList.add("hidden"); }
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        stylePopover.classList.add("hidden");
        styleMenuBtn.setAttribute("aria-expanded", "false");
        if (appModePopover) appModePopover.classList.add("hidden"); }
    });
    document.getElementById("unlockForm").addEventListener("submit", (e) => {
      e.preventDefault();
      state.demoMode = false;
      localStorage.removeItem("nexus_demo_mode");
      state.passphrase = document.getElementById("passInput").value.trim();
      fetchStats(state.period); });
    document.getElementById("previewDemoBtn").addEventListener("click", () => {
      state.demoMode = true;
      localStorage.setItem("nexus_demo_mode", "1");
      document.getElementById("authOverlay").classList.add("hidden");
      document.getElementById("dashboardMain").classList.remove("hidden");
      fetchStats(state.period); });
    document.getElementById("lockBtn").addEventListener("click", () => {
      localStorage.removeItem("nexus_passphrase");
      sessionStorage.removeItem("nexus_passphrase");
      localStorage.removeItem("nexus_demo_mode");
      state.passphrase = "";
      state.demoMode = false;
      document.getElementById("passInput").value = "";
      document.getElementById("authOverlay").classList.remove("hidden");
      document.getElementById("dashboardMain").classList.add("hidden"); });
    if (state.passphrase || state.demoMode) {
      fetchStats(state.period); }
