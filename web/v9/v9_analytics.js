/* SPDX-License-Identifier: Apache-2.0 */
/* AGY-Nexus /web/v9 — Honest KPI Cards, Pool-Reconciled Model Breakdown, Wire Summary & Health */
(() => {
  const V9 = window.AgyV9;

  function renderKpiCards(b) {
    const grid = document.getElementById("v9KpiGrid");
    if (!grid) return;
    if (b && b.project_scope && V9.ProjectView && V9.ProjectView.renderProjectKpis(b)) return;
    const k = b.kpis || {};
    const p = b.period || {};
    const qp = b.quota_and_pools || {};
    const pools = qp.pools || {};
    const gPool = pools.google || {};
    const pPool = pools.claude || {};
    const pacing = qp.partner_weekly_pacing || {};
    const models = Array.isArray(b.model_usage_vs_target) ? b.model_usage_vs_target : [];

    const peak = k.peak_day || {};
    const googlePct = models
      .filter((m) => String(m.pool || "").toLowerCase().includes("google"))
      .reduce((acc, m) => acc + Number(m.actual_pct || 0), 0);
    const partnerPct = models
      .filter((m) => String(m.pool || "").toLowerCase().includes("partner"))
      .reduce((acc, m) => acc + Number(m.actual_pct || 0), 0);

    const hasCeiling = pacing.recommended_cumulative_ceiling_pct != null;
    const partnerCeiling = hasCeiling ? Number(pacing.recommended_cumulative_ceiling_pct) : 0;
    const partnerFillPct = Math.min(100, Math.max(0, partnerPct));
    const partnerPinPct = Math.min(100, Math.max(0, partnerCeiling));
    const googleWarn = gPool.status && gPool.status !== "HEALTHY";
    const partnerWarn = (pPool.status && pPool.status !== "HEALTHY") || (hasCeiling && partnerPct > partnerCeiling);
    const mainModel = (qp.active_mainchat_model && qp.active_mainchat_model.label) || "Gemini 4 Carbon";

    grid.innerHTML = `
      <div class="va-kpi-gauge-card" data-state="nominal">
        <div class="va-kpi-gauge-head">
          <span class="va-kpi-gauge-label">Activity Throughput</span>
          <span class="va-meta-inline v9-mono-num">${Number(k.active_days || 0)}/${Number(p.total_days || 0)}d</span>
        </div>
        <div class="va-kpi-gauge-val">${V9.fmtNum(k.window_steps)} steps</div>
        <div class="va-kpi-gauge-stats">
          <span>${V9.fmtNum(k.avg_daily_steps)}/d avg</span>
          <span>${V9.fmtNum(k.window_tool_calls)} tools</span>
          <span>Peak ${V9.escHtml(peak.date || "—")}</span>
        </div>
      </div>
      <div class="va-kpi-gauge-card" data-state="nominal">
        <div class="va-kpi-gauge-head">
          <span class="va-kpi-gauge-label">Token Volume &amp; Cost</span>
          <span class="va-meta-inline v9-mono-num">${V9.fmtUsd(k.window_cost_usd || 0)}</span>
        </div>
        <div class="va-kpi-gauge-val">${V9.fmtNum(k.window_tokens)}</div>
        <div class="va-kpi-gauge-stats">
          <span>${V9.fmtNum(k.tok_per_day)}/d</span>
          <span>${V9.fmtUsd(k.cost_per_day_usd || 0)}/d</span>
          <span>${Number(k.total_conversations || 0)}c · ${Number(k.total_subagents_spawned || 0)}r</span>
        </div>
      </div>
      <div class="va-kpi-gauge-card" data-state="${googleWarn ? "warn" : "nominal"}">
        <div class="va-kpi-gauge-head">
          <span class="va-kpi-gauge-label">Google 20x Pool</span>
          <span class="va-pill" data-variant="status" data-state="${googleWarn ? "warn" : "nominal"}">${V9.escHtml(gPool.status || "HEALTHY")}</span>
        </div>
        <div class="va-kpi-gauge-val">${googlePct.toFixed(1)}% <span class="va-meta-inline">call share</span></div>
        <div class="va-kpi-gauge-track"><div class="va-kpi-gauge-fill" style="inline-size:${Math.min(100, Math.max(0, googlePct)).toFixed(1)}%"></div></div>
        <div class="va-kpi-gauge-stats">
          <span>Main: ${V9.escHtml(mainModel)}</span>
          <span>${V9.escHtml(qp.active_tier_profile || "ultra-20x")}</span>
        </div>
      </div>
      <div class="va-kpi-gauge-card" data-state="${partnerWarn ? "warn" : "nominal"}">
        <div class="va-kpi-gauge-head">
          <span class="va-kpi-gauge-label">Partner Weekly Pacing</span>
          <span class="va-pill" data-variant="status" data-state="${partnerWarn ? "warn" : "nominal"}">${V9.escHtml(pPool.status || "HEALTHY")}</span>
        </div>
        <div class="va-kpi-gauge-val">${partnerPct.toFixed(1)}%</div>
        <div class="va-kpi-gauge-track">
          <div class="va-kpi-gauge-fill" style="inline-size:${partnerFillPct.toFixed(1)}%"></div>
          ${hasCeiling && partnerCeiling < 99.5 ? `<span class="va-kpi-gauge-target" style="inset-inline-start:${partnerPinPct.toFixed(1)}%" title="Cumulative ceiling ${Number(partnerCeiling)}% (${Number(pacing.daily_target_pct || 14.28)}%/d)"></span>` : ""}
        </div>
        <div class="va-kpi-gauge-stats">
          ${hasCeiling ? `<span>Ceiling ${Number(partnerCeiling)}%</span><span>${Number(pacing.daily_target_pct || 14.28)}%/d</span>` : ""}
          <span>429s: ${Number(pPool.total_429_count || 0)}</span>
        </div>
      </div>`;
  }

  function sumLayerTokens(modelSeries, modelKey, fallback) {
    const tLayers = modelSeries && modelSeries.token_layers;
    if (tLayers && Array.isArray(tLayers[modelKey]) && tLayers[modelKey].length) {
      return tLayers[modelKey].reduce((acc, v) => acc + Number(v || 0), 0);
    }
    return Number(fallback || 0);
  }

  function renderModelTable(b, rerenderFn) {
    const tbody = document.getElementById("v9ModelTableBody");
    const subEl = document.getElementById("v9ModelPlotSub");
    if (!tbody) return;
    const rows = Array.isArray(b.model_usage_vs_target) ? b.model_usage_vs_target : [];
    const pools = (b.quota_and_pools && b.quota_and_pools.pools) || {};
    const gHealthy = !pools.google || pools.google.status === "HEALTHY";
    const totalCalls = rows.reduce((s, r) => s + Number(r.actual_calls || 0), 0);
    const totalUsd = rows.reduce((s, r) => s + Number(r.est_cost_usd || 0), 0);
    if (subEl) subEl.textContent = `${V9.fmtNum(totalCalls)} calls · ${V9.fmtUsd(totalUsd)} · click row to solo`;

    tbody.innerHTML = rows.map((m, idx) => {
      const col = V9.getSeriesColor(idx);
      const act = Number(m.actual_pct || 0);
      const tgt = Number(m.target_pct || 0);
      const delta = m.delta_pct != null ? Number(m.delta_pct) : Number((act - tgt).toFixed(1));
      const deltaStr = `${delta > 0 ? "+" : ""}${delta.toFixed(1)}%`;
      const isGoogle = String(m.pool_key || m.pool || "").toLowerCase().includes("google");
      const warn = (!isGoogle || !gHealthy) && delta > 12.0;
      const deltaCls = warn ? "v9-delta-warn" : (delta >= 0 ? "v9-delta-pos" : "v9-delta-neg");
      const tok = sumLayerTokens(b.model_series, m.model_key, m.est_tokens);
      const usd = Number(m.est_cost_usd || 0);
      const rateHint = m.rate_label ? ` · ${m.rate_label}` : "";
      const solo = V9.state.soloModel === m.model_key;
      const cls = ["v9-row-click", "va-row-compact", solo ? "is-solo" : (V9.state.soloModel ? "is-dim" : "")].filter(Boolean).join(" ");
      return `<tr class="${cls}" data-solo-model="${V9.escHtml(m.model_key)}">
        <td><span class="v9-swatch-dot" style="background:${col}"></span><span class="v9-cell-main">${V9.escHtml(m.label)}</span></td>
        <td class="v9-col-secondary"><span class="v9-cell-sub">${V9.escHtml(m.pool)} · ${V9.fmtNum(m.actual_calls)}${V9.escHtml(rateHint)}</span></td>
        <td><span class="v9-inline-share"><span class="va-inline-bar" aria-label="${act}%"><span class="va-inline-bar-fill" style="inline-size:${Math.min(100, act)}%;background:${col}"></span><span class="va-inline-bar-pin" style="inset-inline-start:${Math.min(100, tgt)}%"></span></span><span class="v9-inline-pct">${act.toFixed(1)}%</span></span></td>
        <td class="num">${tgt.toFixed(0)}% <span class="${deltaCls}">(${V9.escHtml(deltaStr)})</span></td>
        <td class="num">${V9.fmtNum(tok)}</td>
        <td class="num v9-mono-num">${V9.fmtUsd(usd)}</td>
      </tr>`;
    }).join("");
    tbody.querySelectorAll("tr[data-solo-model]").forEach((tr) => {
      tr.addEventListener("click", () => {
        const key = tr.getAttribute("data-solo-model") || "";
        V9.state.soloModel = V9.state.soloModel === key ? "" : key;
        rerenderFn();
      });
    });
  }

  function renderSubagentTable(b, rerenderFn) {
    const tbody = document.getElementById("v9SubagentTableBody");
    const subEl = document.getElementById("v9SubPlotSub");
    if (!tbody) return;
    const list = Array.isArray(b.subagent_list) ? b.subagent_list : [];
    const totalRuns = list.reduce((s, r) => s + Number(r.runs || 0), 0);
    if (subEl) subEl.textContent = `${totalRuns} runs · ${list.length} roles`;
    tbody.innerHTML = list.map((item, idx) => {
      const col = V9.getSeriesColor(idx);
      const pct = Number(item.share_pct || 0);
      const runs = Number(item.runs || 0);
      const avgTok = Number(item.avg_tokens_per_run != null ? item.avg_tokens_per_run : (runs > 0 ? Math.round(Number(item.tokens || 0) / runs) : 0));
      const solo = V9.state.soloSubagent === item.role;
      const cls = ["v9-row-click", "va-row-compact", solo ? "is-solo" : (V9.state.soloSubagent ? "is-dim" : "")].filter(Boolean).join(" ");
      return `<tr class="${cls}" data-solo-sub="${V9.escHtml(item.role)}">
        <td><span class="v9-swatch-dot" style="background:${col}"></span><span class="v9-cell-main">${V9.escHtml(item.role)}</span></td>
        <td class="v9-col-secondary"><span class="v9-cell-sub">${V9.escHtml(item.dominant_model_label || item.dominant_model_key || "—")}</span></td>
        <td><span class="v9-inline-share"><span class="va-inline-bar" aria-label="${pct}%"><span class="va-inline-bar-fill" style="inline-size:${Math.min(100, pct)}%;background:${col}"></span></span><span class="v9-inline-pct">${pct.toFixed(1)}%</span></span></td>
        <td class="num">${runs}</td>
        <td class="num">${V9.fmtNum(item.tokens)}</td>
        <td class="num v9-col-secondary v9-mono-num">${V9.fmtNum(avgTok)}</td>
        <td class="num v9-mono-num">${V9.fmtUsd(item.est_cost_usd || 0)}</td>
      </tr>`;
    }).join("");
    tbody.querySelectorAll("tr[data-solo-sub]").forEach((tr) => {
      tr.addEventListener("click", () => {
        const role = tr.getAttribute("data-solo-sub") || "";
        V9.state.soloSubagent = V9.state.soloSubagent === role ? "" : role;
        rerenderFn();
      });
    });
  }

  function renderWireSection(b) {
    const wire = b.wire_telemetry || {};
    const subEl = document.getElementById("v9WireSub");
    const clientHost = document.getElementById("v9WireClientHost");
    const callsHost = document.getElementById("v9WireCallsHost");
    const calls = Array.isArray(wire.recent_calls) ? wire.recent_calls : [];
    const totalCalls = Number(wire.total_recorded_calls || calls.length || 0);
    if (subEl) {
      const warmup = calls.length === 0 ? " · Warming up — 0 samples collected" : "";
      subEl.textContent = `${totalCalls} calls · avg ${(wire.avg_kb || 0).toFixed(2)} KB · max ${(wire.max_kb || 0).toFixed(2)} KB · ${wire.budget_compliance_pct != null ? `${wire.budget_compliance_pct}%` : "100%"} <= 20 KB${warmup}`;
    }
    if (clientHost) {
      const entries = Object.entries(wire.by_product || {});
      const hs = wire.protocol_handshakes || {};
      const items = entries.map(([name, info], idx) => `
        <span class="v9-wire-client-item">
          <span class="v9-swatch-dot" style="background:${V9.getSeriesColor(idx)}"></span>
          <span>${V9.escHtml(name)}: ${V9.fmtNum(info.calls || 0)} (${V9.fmtNum(info.tokens || 0)} tok)</span>
        </span>`).join("");
      clientHost.innerHTML = `
        <div class="v9-wire-clients">${items || `<span class="va-meta-inline">No client calls recorded yet.</span>`}</div>
        <div class="va-meta-inline v9-wrap-anywhere">Protocol handshakes (excluded): ${hs.calls || 0} calls · ${V9.fmtBytes(hs.bytes || 0)} · tools/list ${(hs.tools_list_kb || 0).toFixed(1)} KB</div>`;
    }
    if (callsHost) {
      const recent = calls.slice(0, 15);
      callsHost.innerHTML = recent.length
        ? `<table class="v9-table booktabs">
            <thead><tr><th>Call &amp; Client</th><th class="num">Size / ms</th><th>Budget</th></tr></thead>
            <tbody>${recent.map((c) => `<tr>
              <td>
                <div class="v9-cell-main v9-wrap-anywhere">${V9.escHtml(c.tool || c.rpc)}</div>
                <div class="v9-cell-sub v9-wrap-anywhere">${V9.escHtml(String(c.ts || "").slice(11, 19))} · ${V9.escHtml(c.product || "—")}</div>
              </td>
              <td class="num">
                <div>${Number(c.kb || 0).toFixed(2)} KB</div>
                <div class="v9-cell-sub">${Math.round(Number(c.duration_ms || 0))} ms</div>
              </td>
              <td><span class="va-pill" data-variant="status" data-state="${c.under_20kb_budget === false ? "fault" : "nominal"}">${c.under_20kb_budget === false ? "OVER 20KB" : "OK"}</span></td>
            </tr>`).join("")}</tbody>
          </table>`
        : `<div class="v9-empty">No wire tool calls captured in window.</div>`;
    }
  }

  function renderHealthSection(b) {
    if (b && b.project_scope && V9.ProjectView && V9.ProjectView.renderProjectHealthDrawer(b)) return;
    const titleEl = document.getElementById("v9HealthDrawerTitle");
    if (titleEl) titleEl.textContent = "Workstation Code Health, Routing & 3-2-1 Backup";
    const ch = b.code_health || {};
    const rt = b.routing_telemetry || {};
    const bk = b.backup_321 || {};
    const mh = ch.modular_hygiene || {};
    const sumEl = document.getElementById("v9HealthSummary");
    const bodyEl = document.getElementById("v9HealthBody");
    const over650 = Number(mh.violations_over_650 || 0);
    if (sumEl) {
      sumEl.textContent = `${mh.compliant_500 || 0}/${mh.total_modules || 0} <=500L · ${over650} >650L · Slots ${rt.active_slots || 0} · Backup ${bk.short_sha || "—"}`;
    }
    if (!bodyEl) return;
    const watch = Array.isArray(mh.watchlist_and_exceptions) ? mh.watchlist_and_exceptions.slice(0, 12) : [];
    bodyEl.innerHTML = `
      <div class="v9-health-strip" style="padding-block:0.5rem">
        <span>Release: ${V9.escHtml((ch.version && ch.version.status_label) || b.version || "4.0.0")}</span>
        <span>Praxis Symbols: ${(ch.polyglot_health && ch.polyglot_health.total_symbols) || 0}</span>
        <span>Pinned Slots: ${rt.active_slots || 0} (${rt.pinned_calls || 0} pinned / ${rt.auto_resolved_calls || 0} auto)</span>
        <span>3-2-1 Backup: ${V9.escHtml(bk.status_label || "—")} (${V9.escHtml(bk.age || "—")})</span>
      </div>
      <div class="va-table-wrap v9-table-scroll" tabindex="0" role="region" aria-label="Module size watchlist">
        <table class="v9-table booktabs">
          <thead><tr><th>Module</th><th class="num">Lines</th><th class="num">Symbols</th><th class="num">&gt;100L Fns</th><th>Status</th></tr></thead>
          <tbody>${watch.map((m) => `<tr>
            <td>${V9.escHtml(m.name)}</td>
            <td class="num">${m.lines || 0}</td>
            <td class="num">${m.symbols || 0}</td>
            <td class="num">${m.long_functions || 0}</td>
            <td><span class="va-pill" data-variant="status" data-state="${m.lines > 650 ? "fault" : (m.lines > 500 ? "warn" : "nominal")}">${V9.escHtml(m.status || "ok")}</span></td>
          </tr>`).join("")}</tbody>
        </table>
      </div>`;
  }

  const SHORT_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function parseIsoParts(iso) {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ""));
    if (!m) return null;
    return { y: Number(m[1]), m: Number(m[2]), d: Number(m[3]) };
  }

  function formatShortSpan(startIso, endIso) {
    const s = parseIsoParts(startIso);
    const e = parseIsoParts(endIso);
    if (!s || !e) return "";
    const sm = SHORT_MONTHS[s.m - 1] || "";
    const em = SHORT_MONTHS[e.m - 1] || "";
    if (s.y === e.y && s.m === e.m) return `${sm} ${s.d}–${e.d}`;
    return `${sm} ${s.d}–${em} ${e.d}`;
  }

  function formatPeriodLabels(p) {
    const tf = p.timeframe || V9.state.timeframe || "month";
    const hm = p.horizon_mode || V9.state.mode || "to_date";
    const off = p.offset != null ? Number(p.offset) : Number(V9.state.offset || 0);
    const span = formatShortSpan(p.start_date, p.end_date);
    const lbl = String(p.label || "").trim();
    let longPrefix = lbl || "Window";
    let shortPrefix = longPrefix;

    if (hm === "rolling") {
      if (tf === "month") { longPrefix = off === 0 ? "Last 30d" : "30d"; shortPrefix = "30d"; }
      else if (tf === "quarter") { longPrefix = off === 0 ? "Last 90d" : "90d"; shortPrefix = "90d"; }
      else { longPrefix = off === 0 ? "Last 52w" : "52w"; shortPrefix = "52w"; }
    } else if (tf === "month") {
      shortPrefix = off === 0 ? "MTD" : (lbl.split(" ")[0] || "Mon");
    } else if (tf === "quarter") {
      shortPrefix = off === 0 ? "QTD" : (lbl.split(" ").pop() || "Qtr");
    } else if (tf === "year") {
      longPrefix = off === 0 ? `${lbl || "Year"} YTD` : (lbl || "Year");
      shortPrefix = off === 0 ? "YTD" : (lbl || "Year");
    }
    return {
      longText: span ? `${longPrefix} · ${span}` : longPrefix,
      shortText: span ? `${shortPrefix} · ${span}` : shortPrefix,
      fullTitle: `${lbl || longPrefix}${p.start_date ? ` (${p.start_date} .. ${p.end_date || ""})` : ""}`,
    };
  }

  function renderAnalytics(b, rerenderFn, actions) {
    renderKpiCards(b);
    renderModelTable(b, rerenderFn);
    renderSubagentTable(b, rerenderFn);
    if (V9.Billing && V9.Billing.renderBillingCard) V9.Billing.renderBillingCard(b);
    if (V9.ProjectView && V9.ProjectView.renderProjectsOrSessionsCard) {
      V9.ProjectView.renderProjectsOrSessionsCard(b, actions || {});
    }
    renderWireSection(b);
    renderHealthSection(b);
    const heatHdr = document.getElementById("v9HeatHeading");
    if (heatHdr) heatHdr.textContent = (b && b.project_scope) ? "Project Activity Heatmap" : "Activity Heatmap";
    const p = b.period || {};
    const fmt = formatPeriodLabels(p);
    const trigLabel = document.getElementById("v9PeriodTriggerLabel");
    const trigBtn = document.getElementById("v9PeriodPickerBtn");
    if (trigLabel) {
      trigLabel.innerHTML = `<span class="v9-p-long">${V9.escHtml(fmt.longText)}</span><span class="v9-p-short" aria-hidden="true">${V9.escHtml(fmt.shortText)}</span>`;
    }
    if (trigBtn) trigBtn.title = fmt.fullTitle;
  }

  V9.Analytics = { renderAnalytics };
})();
