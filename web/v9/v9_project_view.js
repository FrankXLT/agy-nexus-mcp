/* SPDX-License-Identifier: Apache-2.0 */
/* AGY-Nexus /web/v9 — Inline Top Projects Table & Dedicated Project Analytics */
(function () {
  const V9 = (window.AgyV9 = window.AgyV9 || {});

  function latestProjectSessionId(proj) {
    const list = (proj && proj.sessions) || [];
    let bestId = (proj && proj.latest_session_id) || "";
    let bestTs = -1;
    for (const s of list) {
      if (!s || !s.conversation_id) continue;
      const ts = Number(s.last_updated_ts || 0) || (s.last_updated ? Date.parse(s.last_updated) / 1000 : 0) || 0;
      if (!bestId || ts >= bestTs) {
        bestTs = ts;
        bestId = s.conversation_id;
      }
    }
    return bestId;
  }

  function findProjectInBundle(b, projectId) {
    if (!b || !projectId) return null;
    const h = b.project_hierarchy || {};
    const otherArr = Array.isArray(h.other_projects)
      ? h.other_projects
      : (h.other_projects && typeof h.other_projects === "object" ? [h.other_projects] : []);
    for (const grp of [h.top_projects || [], otherArr, h.idle_projects || []]) {
      const hit = grp.find((p) => p && p.project_id === projectId);
      if (hit) return hit;
    }
    return null;
  }

  function kpiCardMarkup(opts) {
    const state = opts.state || "nominal";
    const headRight = opts.pill
      ? `<span class="va-pill" data-variant="status" data-state="${V9.escHtml(state)}">${V9.escHtml(opts.pill)}</span>`
      : `<span class="va-meta-inline v9-mono-num">${V9.escHtml(opts.badge || "")}</span>`;
    const track = opts.hasTrack
      ? `<div class="va-kpi-gauge-track"><div class="va-kpi-gauge-fill" style="inline-size:${Math.min(100, Math.max(0, Number(opts.trackPct || 0))).toFixed(1)}%"></div></div>`
      : "";
    const metaHtml = (opts.meta || []).map((m) => `<span>${V9.escHtml(m)}</span>`).join("");
    return `<div class="va-kpi-gauge-card" data-state="${V9.escHtml(state === "fault" ? "warn" : state)}">
      <div class="va-kpi-gauge-head">
        <span class="va-kpi-gauge-label">${V9.escHtml(opts.label)}</span>
        ${headRight}
      </div>
      <div class="va-kpi-gauge-val">${opts.valueHtml || V9.escHtml(opts.value)}</div>
      ${track}
      <div class="va-kpi-gauge-stats">${metaHtml}</div>
    </div>`;
  }

  function renderProjectKpis(b) {
    const grid = document.getElementById("v9KpiGrid");
    if (!grid || !b || !b.project_scope) return false;
    const ps = b.project_scope;
    const k = b.kpis || {};
    const p = b.period || {};
    const cb = ps.context_budget || {};
    const seam = Math.max(1, Number(cb.rollover_seam_steps || 700));
    const maxSteps = Math.max(0, Number(cb.max_session_steps || 0));
    const rawPct = (maxSteps / seam) * 100;
    const clampedPct = Math.min(100, Math.max(0, Math.round(rawPct)));
    const budgetState = rawPct >= 95 ? "fault" : rawPct >= 75 ? "warn" : "nominal";
    const budgetPill = maxSteps > seam ? "OVER SEAM" : rawPct >= 75 ? "NEAR SEAM" : "NOMINAL";
    const totalSess = Number(ps.total_sessions || 0);
    const activeSess = Number(ps.active_sessions_count || 0);
    const sharePct = Number(ps.share_of_workstation_pct || 0).toFixed(1);
    const staged = Number(ps.staged_count || 0);
    const inWork = Number(ps.in_work_handoff_count || 0);
    const peak = k.peak_day || {};

    grid.innerHTML = [
      kpiCardMarkup({
        label: "Project Throughput",
        value: `${V9.fmtNum(k.window_steps || 0)} steps`,
        badge: `${ps.active_days || k.active_days || 0}/${Number(p.total_days || 0)}d`,
        meta: [
          `${sharePct}% of workstation`,
          `Avg ${V9.fmtNum(k.avg_daily_steps || 0)}/d`,
          `Peak ${V9.escHtml(peak.date || "—")}`,
        ],
      }),
      kpiCardMarkup({
        label: "Project Volume & Cost",
        value: V9.fmtNum(k.window_tokens || 0),
        badge: V9.fmtUsd(ps.window_cost_usd != null ? ps.window_cost_usd : (k.window_cost_usd || 0)),
        meta: [
          `${V9.fmtNum(ps.avg_tokens_per_session || 0)}/sess avg`,
          `${V9.fmtNum(k.total_subagents_spawned || 0)} subagents`,
          `${activeSess}/${totalSess} sess`,
        ],
      }),
      kpiCardMarkup({
        label: "Session Context Budget",
        valueHtml: `${clampedPct}% <span class="va-meta-inline">${V9.fmtNum(maxSteps)} / ${seam} steps</span>`,
        state: budgetState,
        pill: budgetPill,
        hasTrack: true,
        trackPct: clampedPct,
        meta: [
          `Max ${(cb.top_session_id || "").slice(0, 8) || "none"}`,
          `${ps.running_count || 0} running`,
          `${ps.idle_count || 0} idle`,
        ],
      }),
      kpiCardMarkup({
        label: "Handoff & Session Queue",
        value: `${staged} staged · ${inWork} active`,
        badge: `${ps.completed_count || 0} done`,
        meta: [
          `${activeSess}/${totalSess} active`,
          `${ps.active_days || k.active_days || 0} active days`,
          `${V9.fmtNum(ps.fleet_window_steps || 0)} fleet`,
        ],
      }),
    ].join("");
    return true;
  }

  function buildProjectSessionsChartOption(b, metric, t, fullW, helpers) {
    const pss = b && b.project_sessions_series;
    if (!pss || !(pss.keys || []).length) {
      return {
        backgroundColor: "transparent",
        graphic: { type: "text", left: "center", top: "middle", style: { text: "No session activity in this period", fill: t.muted, font: "12px sans-serif" } },
      };
    }
    const useCost = metric === "cost";
    const useTok = metric === "tokens";
    const unit = useCost ? "USD" : (useTok ? "tokens" : "steps");
    const keys = pss.keys || [];
    const labels = pss.labels || {};
    const colorMap = pss.colors || {};
    const rawLayers = useCost ? (pss.cost_layers || pss.token_layers || {}) : (useTok ? (pss.token_layers || {}) : (pss.layers || {}));
    const dates = pss.dates || [];
    const displayLabels = {};
    const colorsObj = {};
    keys.forEach((k, idx) => {
      const full = String(labels[k] || k);
      displayLabels[k] = full.length > 26 ? `${full.slice(0, 24)}..` : full;
      if (k === "__other_sessions__") {
        colorsObj[k] = "#94A3B8";
      } else {
        const slot = colorMap[k] !== undefined ? colorMap[k] : idx;
        colorsObj[k] = V9.getSeriesColor(slot);
      }
    });
    const binned = helpers.binSeriesForDisplay(dates, rawLayers, keys);
    const series = helpers.buildStackedSeriesList(keys, binned.layers, displayLabels, colorsObj, "");
    const opt = helpers.makeStackedBarOption(binned.dates, series, unit, t, fullW);
    opt.yUnit = `session_${unit}`;
    return opt;
  }

  function renderTopProjectsTable(b, actions) {
    const wrap = document.getElementById("v9ProjTableWrap");
    const foot = document.getElementById("v9ProjFoot");
    const titleEl = document.getElementById("v9ProjPlotTitle");
    const subEl = document.getElementById("v9ProjPlotSub");
    if (!wrap || !b) return;
    const h = b.project_hierarchy || {};
    const active = [...(h.top_projects || [])].filter((p) => p && !p.is_rollup);
    const otherCnt = (h.other_projects && !Array.isArray(h.other_projects) ? Number(h.other_projects.projects_count || 0) : 0);
    const idle = Array.isArray(h.idle_projects) ? h.idle_projects : [];
    if (titleEl) titleEl.textContent = "Top Projects (Daily)";
    if (subEl) subEl.textContent = `${h.active_projects_count || active.length} active · ${h.idle_projects_count || idle.length} idle`;
    if (!active.length) {
      wrap.innerHTML = `<div class="v9-empty">No project activity recorded in this time window.</div>`;
      if (foot) foot.textContent = "";
      return;
    }
    const totalSteps = active.reduce((acc, p) => acc + Number(p.window_steps || 0), 0) || 1;
    const rowsHtml = active.slice(0, 14).map((p) => {
      const pid = p.project_id || "";
      const color = V9.getSeriesColor(p.color_slot || 0);
      const pct = Number(p.share_pct != null ? p.share_pct : ((p.window_steps || 0) / totalSteps) * 100);
      const actSess = Number(p.active_sessions_count != null ? p.active_sessions_count : (p.sessions || []).length);
      const totSess = Number(p.total_sessions || (p.sessions || []).length || actSess);
      const latestSid = latestProjectSessionId(p);
      return `<tr class="v9-row-click v9-row-compact" data-proj-row="${V9.escHtml(pid)}" data-series-name="${V9.escHtml(p.project_name || pid)}">
        <td>
          <div class="v9-tbl-name-wrap">
            <span class="v9-swatch-dot" style="background:${color}"></span>
            <span class="v9-tbl-name-txt" title="${V9.escHtml(p.project_name)}">${V9.escHtml(p.project_name)}</span>
          </div>
          <div class="v9-cell-sub">${actSess}/${totSess} sess · ${V9.fmtNum(p.window_tokens || 0)} tok · ${V9.fmtUsd(p.window_cost_usd || 0)}</div>
        </td>
        <td class="v9-col-secondary num">${actSess} / ${totSess}</td>
        <td class="v9-bar-cell"><div class="v9-inline-share"><span class="va-inline-bar"><span class="va-inline-bar-fill" style="inline-size:${Math.min(100, pct).toFixed(1)}%;background:${color}"></span></span><span class="v9-inline-pct">${pct.toFixed(1)}%</span></div></td>
        <td class="num">${V9.fmtNum(p.window_steps || 0)}</td>
        <td class="v9-col-secondary num">${V9.fmtNum(p.window_tokens || 0)}</td>
        <td class="num v9-mono-num">${V9.fmtUsd(p.window_cost_usd || 0)}</td>
        <td class="num"><div class="v9-tbl-actions">
          <button type="button" class="v9-tbl-btn is-primary" data-proj-analytics="${V9.escHtml(pid)}">Analytics</button>
          <button type="button" class="v9-tbl-btn" data-proj-ws="${V9.escHtml(pid)}"${latestSid ? "" : " disabled"}>Workspace</button>
        </div></td>
      </tr>`;
    }).join("");
    wrap.innerHTML = `<table class="v9-table booktabs">
      <thead><tr><th>Project</th><th class="v9-col-secondary num">Sessions</th><th>Share</th><th class="num">Steps</th><th class="v9-col-secondary num">Tokens</th><th class="num">Est. $</th><th class="num">Actions</th></tr></thead>
      <tbody id="v9ProjTableBody">${rowsHtml}</tbody>
    </table>`;
    if (foot) {
      const hiddenNotes = [];
      if (otherCnt > 0) hiddenNotes.push(`${otherCnt} smaller project${otherCnt === 1 ? "" : "s"} rolled up`);
      if (idle.length > 0) hiddenNotes.push(`${idle.length} idle`);
      foot.textContent = hiddenNotes.length
        ? `${hiddenNotes.join(" · ")} (all accessible via [Menu]); hover any row to highlight stack or open Analytics / Workspace.`
        : "Hover a row to highlight its stack; click Analytics for project deep-dive or Workspace to jump straight to its latest session.";
    }
    bindTopProjectTableEvents(wrap, actions);
  }

  function bindTopProjectTableEvents(wrap, actions) {
    wrap.querySelectorAll("tr[data-proj-row]").forEach((tr) => {
      const seriesName = tr.getAttribute("data-series-name") || "";
      tr.addEventListener("mouseenter", () => V9.Charts && V9.Charts.highlightSeries("v9ProjectChart", seriesName, true));
      tr.addEventListener("mouseleave", () => V9.Charts && V9.Charts.highlightSeries("v9ProjectChart", seriesName, false));
      tr.addEventListener("click", (e) => {
        if (e.target.closest("button")) return;
        const pid = tr.getAttribute("data-proj-row");
        if (pid && actions && actions.openProjectAnalytics) actions.openProjectAnalytics(pid);
      });
    });
    wrap.querySelectorAll("[data-proj-analytics]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const pid = btn.getAttribute("data-proj-analytics");
        if (pid && actions && actions.openProjectAnalytics) actions.openProjectAnalytics(pid);
      });
    });
    wrap.querySelectorAll("[data-proj-ws]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const pid = btn.getAttribute("data-proj-ws");
        if (pid && actions && actions.openProjectWorkspace) actions.openProjectWorkspace(pid);
      });
    });
  }

  function renderProjectSessionsCard(b, actions) {
    const wrap = document.getElementById("v9ProjTableWrap");
    const foot = document.getElementById("v9ProjFoot");
    const titleEl = document.getElementById("v9ProjPlotTitle");
    const subEl = document.getElementById("v9ProjPlotSub");
    if (!wrap || !b || !b.project_scope) return;
    const ps = b.project_scope;
    const pss = b.project_sessions_series || {};
    const proj = findProjectInBundle(b, ps.project_id);
    const sessions = (pss.sessions && pss.sessions.length ? pss.sessions : (proj && proj.sessions) || []);
    const labelMap = pss.labels || {};
    if (titleEl) titleEl.textContent = "Project Sessions (Daily)";
    const actCount = ps.active_sessions_count != null ? ps.active_sessions_count : sessions.length;
    const totCount = ps.total_sessions != null ? ps.total_sessions : sessions.length;
    if (subEl) subEl.textContent = `${actCount} active · ${totCount} total`;
    if (!sessions.length) {
      wrap.innerHTML = `<div class="v9-empty">No active sessions found for ${V9.escHtml(ps.project_name || "this project")} in the current window.</div>`;
      if (foot) foot.textContent = "";
      return;
    }
    const maxShareSteps = sessions.reduce((acc, s) => acc + Number(s.window_steps != null ? s.window_steps : (s.step_count || 0)), 0) || 1;
    const rowsHtml = sessions.map((s, idx) => {
      const cid = s.conversation_id || "";
      const shortId = s.short_id || cid.slice(0, 8);
      const color = V9.getSeriesColor(s.color_slot != null ? s.color_slot : (s.shade_idx != null ? s.shade_idx : idx));
      const steps = Number(s.window_steps != null ? s.window_steps : (s.step_count || 0));
      const pct = Number(s.share_pct != null ? s.share_pct : (steps / maxShareSteps) * 100);
      const rawLegend = String(labelMap[cid] || "");
      const seriesName = rawLegend ? (rawLegend.length > 26 ? `${rawLegend.slice(0, 24)}..` : rawLegend) : "";
      const tone = s.is_running ? "run" : "idle";
      return `<tr class="v9-row-click v9-row-compact" data-sess-row="${V9.escHtml(cid)}" data-series-name="${V9.escHtml(seriesName)}">
        <td>
          <div class="v9-tbl-name-wrap">
            <span class="v9-swatch-dot" style="background:${color}"></span>
            <span class="v9-tbl-name-txt" title="${V9.escHtml(s.title || shortId)}">${V9.escHtml(s.title || shortId)}</span>
          </div>
          <div class="v9-cell-sub">${V9.escHtml(shortId)} · ${V9.escHtml(s.relative_age || "recent")} · ${V9.fmtUsd(s.window_cost_usd || 0)}</div>
        </td>
        <td class="v9-col-secondary"><span class="v9-status-tag" data-tone="${tone}">${V9.escHtml(s.status || "IDLE")}</span></td>
        <td class="v9-bar-cell"><div class="v9-inline-share"><span class="va-inline-bar"><span class="va-inline-bar-fill" style="inline-size:${Math.min(100, pct).toFixed(1)}%;background:${color}"></span></span><span class="v9-inline-pct">${pct.toFixed(1)}%</span></div></td>
        <td class="num">${V9.fmtNum(steps)}</td>
        <td class="v9-col-secondary num">${V9.fmtNum(s.window_tokens || 0)}</td>
        <td class="num v9-mono-num">${V9.fmtUsd(s.window_cost_usd || 0)}</td>
        <td class="num"><button type="button" class="v9-tbl-btn is-primary" data-open-sess="${V9.escHtml(cid)}"><span>Open</span><svg width="10" height="10" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M3.5 8H12.5M9 4.5L12.5 8L9 11.5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg></button></td>
      </tr>`;
    }).join("");
    wrap.innerHTML = `<table class="v9-table booktabs">
      <thead><tr><th>Session</th><th class="v9-col-secondary">Status</th><th>Share</th><th class="num">Steps</th><th class="v9-col-secondary num">Tokens</th><th class="num">Est. $</th><th class="num">Workspace</th></tr></thead>
      <tbody id="v9ProjSessionTableBody">${rowsHtml}</tbody>
    </table>`;
    if (foot) foot.textContent = "Click any session row or Open to inspect its deliverables, Markdown docs, and captures in Workspace.";
    wrap.querySelectorAll("tr[data-sess-row]").forEach((tr) => {
      const seriesName = tr.getAttribute("data-series-name") || "";
      if (seriesName) {
        tr.addEventListener("mouseenter", () => V9.Charts && V9.Charts.highlightSeries("v9ProjectChart", seriesName, true));
        tr.addEventListener("mouseleave", () => V9.Charts && V9.Charts.highlightSeries("v9ProjectChart", seriesName, false));
      }
      tr.addEventListener("click", () => {
        const cid = tr.getAttribute("data-sess-row");
        if (cid && actions && actions.openSessionWorkspace) actions.openSessionWorkspace(cid);
      });
    });
  }

  function renderProjectHealthDrawer(b) {
    const ps = b && b.project_scope;
    const titleEl = document.getElementById("v9HealthDrawerTitle");
    const summaryEl = document.getElementById("v9HealthSummary");
    const bodyEl = document.getElementById("v9HealthBody");
    if (!ps || !bodyEl) return false;
    const mh = ps.code_health || {};
    const wire = b.wire_telemetry || {};
    if (titleEl) titleEl.textContent = "Project Code Health & Modular Hygiene";
    if (!mh.available) {
      if (summaryEl) summaryEl.textContent = "Workspace path unavailable";
      bodyEl.innerHTML = `<div class="v9-empty">No local workspace directory mapped for ${V9.escHtml(ps.project_name || "this project")}.</div>`;
      return true;
    }
    const mods = mh.modules || [];
    const target = mh.target_lines || 500;
    const ceiling = mh.ceiling_lines || 650;
    if (summaryEl) summaryEl.textContent = `${mh.compliant_500 || 0}/${mh.total_modules || 0} <= ${target}L · ${mh.violations_over_650 || 0} > ${ceiling}L`;
    const rows = mods.slice(0, 14).map((m) => `<tr>
      <td><span class="v9-wrap-anywhere">${V9.escHtml(m.name)}</span></td>
      <td class="num">${V9.fmtNum(m.lines || 0)}</td>
      <td><span class="v9-status-tag" data-tone="${m.status === "compliant" ? "idle" : "warn"}">${V9.escHtml(m.status || "compliant")}</span></td>
    </tr>`).join("");
    bodyEl.innerHTML = `<div class="v9-health-strip">
      <span><strong>Workspace</strong> ${V9.escHtml(mh.workspace_path || ps.workspace_path || "—")}</span>
      <span><strong>Modules</strong> ${mh.total_modules || 0} (${V9.fmtNum(mh.total_lines || 0)}L)</span>
      <span><strong>&lt;= ${target}L</strong> ${mh.compliant_500 || 0}</span>
      <span><strong>${target + 1}-${ceiling}L Warn</strong> ${mh.warning_501_650 || 0}</span>
      <span><strong>&gt; ${ceiling}L Over</strong> ${mh.violations_over_650 || 0}</span>
      <span><strong>Wire Max</strong> ${wire.max_kb || 0} KB / ${wire.ceiling_kb || 20} KB</span>
    </div>
    ${rows ? `<div class="va-table-wrap v9-table-scroll"><table class="v9-table booktabs"><thead><tr><th>Module</th><th class="num">Lines</th><th>Budget</th></tr></thead><tbody>${rows}</tbody></table></div>` : ""}`;
    return true;
  }

  function renderProjectsOrSessionsCard(b, actions) {
    if (b && b.project_scope) renderProjectSessionsCard(b, actions);
    else renderTopProjectsTable(b, actions);
  }

  V9.ProjectView = {
    latestProjectSessionId,
    findProjectInBundle,
    renderProjectKpis,
    buildProjectSessionsChartOption,
    renderTopProjectsTable,
    renderProjectSessionsCard,
    renderProjectHealthDrawer,
    renderProjectsOrSessionsCard,
  };
})();
