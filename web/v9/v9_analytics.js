/* SPDX-License-Identifier: Apache-2.0 */
/* AGY-Nexus /web/v9 — Honest KPI Cards, Pool-Reconciled Model Breakdown, Wire Summary & Health */
(() => {
  const V9 = window.AgyV9;

  function formatResetCountdown(bucket, kind) {
    if (!bucket || typeof bucket !== "object") return "No LS data";
    if (!bucket.has_active_reset || !bucket.reset_time) {
      return Number(bucket.used_pct || 0) > 0.05 ? "Active · no timer" : "Standby · 100% left";
    }
    const targetMs = Date.parse(String(bucket.reset_time));
    if (!Number.isFinite(targetMs)) return "Timer active";
    const diffMs = targetMs - Date.now();
    if (diffMs <= 0) return "Reset due";
    const totalMin = Math.max(1, Math.floor(diffMs / 60000));
    const totalHr = Math.floor(totalMin / 60);
    const remMin = totalMin % 60;
    const days = Math.floor(totalHr / 24);
    const remHr = totalHr % 24;
    const rel = days >= 1 ? `in ${days}d ${remHr}h` : (totalHr >= 1 ? `in ${totalHr}h ${remMin}m` : `in ${totalMin}m`);
    let clock = "";
    try {
      const fmtOpts = (kind === "weekly" || days >= 1)
        ? { weekday: "short", hour: "numeric", minute: "2-digit" }
        : { hour: "numeric", minute: "2-digit" };
      clock = new Intl.DateTimeFormat(undefined, fmtOpts).format(new Date(targetMs));
    } catch (_err) { clock = ""; }
    return clock ? `${rel} (${clock})` : rel;
  }

  function formatSnapshotAge(ageSec) {
    if (ageSec == null || !Number.isFinite(Number(ageSec))) return "offline";
    const s = Math.max(0, Number(ageSec));
    if (s < 90) return "live";
    if (s < 3600) return `${Math.round(s / 60)}m ago`;
    if (s < 86400) return `${Math.round(s / 3600)}h ago`;
    return `${Math.round(s / 86400)}d ago`;
  }

  function renderKpiCards(b) {
    const grid = document.getElementById("v9KpiGrid");
    if (!grid) return;
    if (b && b.project_scope && V9.ProjectView && V9.ProjectView.renderProjectKpis(b)) return;
    const k = b.kpis || {};
    const p = b.period || {};
    const peak = k.peak_day || {};
    const metric = (V9.state && V9.state.metric) || "steps";
    const qc = V9.QuotaCards;
    const splitCardHtml = qc && qc.renderPoolSplitCard ? qc.renderPoolSplitCard(b, metric) : "";
    const quotaCardHtml = qc && qc.renderQuotaResetsCard ? qc.renderQuotaResetsCard(b) : "";

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
      ${splitCardHtml}
      ${quotaCardHtml}`;
  }

  function sumLayerTokens(modelSeries, modelKey, fallback) {
    const tLayers = modelSeries && modelSeries.token_layers;
    if (tLayers && Array.isArray(tLayers[modelKey]) && tLayers[modelKey].length) {
      return tLayers[modelKey].reduce((acc, v) => acc + Number(v || 0), 0);
    }
    return Number(fallback || 0);
  }

  function ensureModelTableHead(table) {
    const thead = table && table.tHead;
    if (!thead || !V9.TableSort) return;
    if (!thead.querySelector('[data-sort-table="models"]')) {
      const TS = V9.TableSort;
      thead.innerHTML = `<tr>${TS.thHtml("models", "name", "Model", { type: "text" })}${TS.thHtml("models", "calls", "Pool · Calls · Rate", { cls: "v9-col-secondary" })}${TS.thHtml("models", "share", "Share · 24h")}${TS.thHtml("models", "delta", 'Guide<span class="v9-col-secondary"> / Delta</span>', { cls: "num", rawLabel: true })}${TS.thHtml("models", "tokens", "Tokens", { cls: "num" })}${TS.thHtml("models", "cost", "Est. $", { cls: "num" })}</tr>`;
    } else {
      V9.TableSort.syncTheadSort(thead, "models");
    }
  }

  function renderModelTable(b, rerenderFn) {
    const tbody = document.getElementById("v9ModelTableBody");
    const subEl = document.getElementById("v9ModelPlotSub");
    if (!tbody) return;
    const metric = V9.state.metric || "steps";
    const rows = Array.isArray(b.model_usage_vs_target) ? b.model_usage_vs_target : [];
    const pools = (b.quota_and_pools && b.quota_and_pools.pools) || {};
    const gHealthy = !pools.google || pools.google.status === "HEALTHY";
    const totalCalls = rows.reduce((s, r) => s + Number(r.actual_calls || 0), 0);
    const totalUsd = rows.reduce((s, r) => s + Number(r.est_cost_usd || 0), 0);
    if (subEl) subEl.textContent = `${V9.fmtNum(totalCalls)} calls · ${V9.fmtUsd(totalUsd)}`;

    const table = tbody.closest && tbody.closest("table");
    ensureModelTableHead(table);
    const TS = V9.TableSort;
    const SB = V9.SparkBars;
    const ml = document.getElementById("v9ModelTableLegend");
    if (ml && SB && SB.renderTableLegend) ml.innerHTML = SB.renderTableLegend("models", metric);
    const enriched = SB
      ? SB.computeModelRows(rows, metric, b.model_series)
      : rows.map((m, origIdx) => {
          const act = Number(m.actual_pct || 0);
          const tgt = Number(m.target_pct || 0);
          const delta = m.delta_pct != null ? Number(m.delta_pct) : Number((act - tgt).toFixed(1));
          const tok = sumLayerTokens(b.model_series, m.model_key, m.est_tokens);
          return { m, origIdx, val: Number(m.actual_calls || 0), tok, actualPct: act, targetPct: tgt, deltaPct: delta, last24hPct: null };
        });
    const sorted = TS
      ? TS.sortItems(enriched, "models", {
          name: { type: "text", get: (e) => e.m.label || e.m.model_key || "" },
          calls: (e) => Number(e.m.actual_calls || 0),
          share: (e) => e.actualPct * 1e6 + Number(e.val || e.m.actual_calls || 0),
          delta: (e) => e.deltaPct,
          tokens: (e) => e.tok,
          cost: (e) => Number(e.m.est_cost_usd || 0),
        })
      : enriched;

    tbody.innerHTML = sorted.map((entry) => {
      const m = entry.m;
      const col = V9.getSeriesColor(entry.origIdx);
      const act = entry.actualPct;
      const tgt = entry.targetPct;
      const delta = entry.deltaPct;
      const deltaStr = `${delta > 0 ? "+" : ""}${delta.toFixed(1)}%`;
      const isGoogle = String(m.pool_key || m.pool || "").toLowerCase().includes("google");
      const warn = (!isGoogle || !gHealthy) && delta > 12.0;
      const deltaCls = warn ? "v9-delta-warn" : (delta >= 0 ? "v9-delta-pos" : "v9-delta-neg");
      const tok = entry.tok;
      const usd = Number(m.est_cost_usd || 0);
      const rateHint = m.rate_label ? ` · ${m.rate_label}` : "";
      const solo = V9.state.soloModel === m.model_key;
      const cls = ["v9-row-click", "va-row-compact", solo ? "is-solo" : (V9.state.soloModel ? "is-dim" : "")].filter(Boolean).join(" ");
      const barHtml = SB
        ? SB.renderModelCaretBar(entry, col)
        : `<span class="v9-inline-share"><span class="va-inline-bar" role="img" aria-label="${act.toFixed(1)}% share"><span class="va-inline-bar-fill" style="inline-size:${Math.min(100, act)}%;background:${col}"></span><span class="va-inline-bar-pin" style="inset-inline-start:${Math.min(100, tgt)}%"></span></span><span class="v9-inline-pct">${act.toFixed(1)}%</span></span>`;
      return `<tr class="${cls}" data-solo-model="${V9.escHtml(m.model_key)}">
        <td><span class="v9-swatch-dot" style="background:${col}"></span><span class="v9-cell-main">${V9.escHtml(m.label)}</span></td>
        <td class="v9-col-secondary"><span class="v9-cell-sub">${V9.escHtml(m.pool)} · ${V9.fmtNum(m.actual_calls)}${V9.escHtml(rateHint)}</span></td>
        <td class="v9-bar-cell">${barHtml}</td>
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
    if (TS && table) {
      TS.bindSortHeaders(table, "models", () => renderModelTable(V9.state.bundle || b, rerenderFn), () => sorted.length);
    }
  }

  function ensureSubagentTableHead(table) {
    const thead = table && table.tHead;
    if (!thead || !V9.TableSort) return;
    if (!thead.querySelector('[data-sort-table="subagents"]')) {
      const TS = V9.TableSort;
      thead.innerHTML = `<tr>${TS.thHtml("subagents", "name", "Role", { type: "text" })}${TS.thHtml("subagents", "model", "Model", { type: "text", cls: "v9-col-secondary" })}${TS.thHtml("subagents", "share", "Per-Run")}${TS.thHtml("subagents", "runs", "Runs", { cls: "num" })}${TS.thHtml("subagents", "tokens", "Tokens", { cls: "num" })}${TS.thHtml("subagents", "avg_tok", "Avg Tok/Run", { cls: "num v9-col-secondary" })}${TS.thHtml("subagents", "cost", "Est. $", { cls: "num" })}</tr>`;
    } else {
      V9.TableSort.syncTheadSort(thead, "subagents");
    }
  }

  const REGISTERED_SUBAGENT_ROLES = new Set([
    "flash-scout", "argon-architect", "flash-surgeon", "hydrogen-surgeon",
    "neon-surgeon", "argon-surgeon", "flash-auditor", "argon-sentinel",
    "carbon-sentinel", "claude-specialist", "claude-sentinel", "pool-failover",
  ]);

  function isRegisteredRole(item) {
    if (item && item.is_registered !== undefined) return Boolean(item.is_registered);
    return REGISTERED_SUBAGENT_ROLES.has(String((item && item.role) || "").trim().toLowerCase());
  }

  function renderSubagentRow(entry, scaleMax, metric, SB, extraCls) {
    const item = entry.item;
    const col = V9.getSeriesColor(entry.origIdx);
    const pct = Number(item.share_pct || 0);
    const solo = V9.state.soloSubagent === item.role;
    const cls = ["v9-row-click", "va-row-compact", extraCls || "", solo ? "is-solo" : (V9.state.soloSubagent ? "is-dim" : "")].filter(Boolean).join(" ");
    const barHtml = SB && entry.sm
      ? SB.renderSubagentWhisker(entry.sm, scaleMax, metric, col)
      : `<span class="v9-inline-share"><span class="va-inline-bar" role="img" aria-label="${pct}%"><span class="va-inline-bar-fill" style="inline-size:${Math.min(100, pct)}%;background:${col}"></span></span><span class="v9-inline-pct">${pct.toFixed(1)}%</span></span>`;
    const adjStatus = String(item.adjudication_status || (item.model_diverged ? "diverged" : "aligned")).toLowerCase();
    const adjText = item.adjudication_text || item.dominant_model_label || item.dominant_model_key || "—";
    const adjDesktop = `<span class="v9-adj-pill" data-adj="${V9.escHtml(adjStatus)}">${V9.escHtml(adjText)}</span>`;
    const adjMobile = adjText && adjText !== "—" ? `<span class="v9-sub-adj-mobile" data-adj="${V9.escHtml(adjStatus)}">${V9.escHtml(adjText)}</span>` : "";
    return `<tr class="${cls}" data-solo-sub="${V9.escHtml(item.role)}">
      <td><span class="v9-swatch-dot" style="background:${col}"></span><span class="v9-cell-main">${V9.escHtml(item.role)}</span>${adjMobile}</td>
      <td class="v9-col-secondary">${adjDesktop}</td>
      <td class="v9-bar-cell">${barHtml}</td>
      <td class="num">${entry.runs}</td>
      <td class="num">${V9.fmtNum(item.tokens)}</td>
      <td class="num v9-col-secondary v9-mono-num">${V9.fmtNum(entry.avgTok)}</td>
      <td class="num v9-mono-num">${V9.fmtUsd(item.est_cost_usd || 0)}</td>
    </tr>`;
  }

  function buildUnregSummaryRow(unregEntries, scaleMax, metric, fleetMeanTok, SB, isExpanded, isDim) {
    let runs = 0, tokens = 0, steps = 0, cost = 0, sharePct = 0, over120Runs = 0, maxSteps = 0;
    let min = Infinity, max = 0, latest = null, weightedSmSum = 0;
    unregEntries.forEach((e) => {
      const it = e.item || {};
      const r = Number(e.runs || 0);
      runs += r;
      tokens += Number(it.tokens || 0);
      steps += Number(it.steps || 0);
      cost += Number(it.est_cost_usd || 0);
      sharePct += Number(it.share_pct || 0);
      over120Runs += Number(it.over_120_runs || 0);
      const sm = e.sm;
      maxSteps = Math.max(maxSteps, Number(it.max_steps_per_run || (sm && sm.maxSteps) || 0));
      if (sm) {
        weightedSmSum += Number(sm.avg || 0) * r;
        if (Number.isFinite(sm.min)) min = Math.min(min, sm.min);
        if (Number.isFinite(sm.max)) max = Math.max(max, sm.max);
        if (sm.latest != null && Number.isFinite(sm.latest) && (latest === null || sm.latest > 0)) latest = sm.latest;
      }
    });
    const avgTok = runs > 0 ? Math.round(tokens / runs) : 0;
    const totMetric = metric === "cost" ? cost : (metric === "tokens" ? tokens : steps);
    const avg = totMetric > 0 ? totMetric / Math.max(1, runs) : (runs > 0 ? weightedSmSum / runs : 0);
    const burnRatio = fleetMeanTok > 0 ? avgTok / fleetMeanTok : 0;
    const isStepCapOver = over120Runs > 0 || maxSteps > 120;
    const aggSm = {
      min: Number.isFinite(min) ? min : 0, avg, max, latest: latest != null ? latest : avg,
      isStepCapOver, isHeavyBurn: !isStepCapOver && burnRatio > 2.5, over120Runs, maxSteps, burnRatio, runs,
    };
    const barHtml = SB && SB.renderSubagentWhisker
      ? SB.renderSubagentWhisker(aggSm, scaleMax, metric, "var(--text-muted)")
      : `<span class="v9-inline-share"><span class="va-inline-bar" role="img" aria-label="${sharePct.toFixed(1)}%"><span class="va-inline-bar-fill" style="inline-size:${Math.min(100, sharePct)}%;background:var(--text-muted)"></span></span><span class="v9-inline-pct">${sharePct.toFixed(1)}%</span></span>`;
    const roleLbl = `${unregEntries.length} ${unregEntries.length === 1 ? "role" : "roles"}`;
    const chev = '<svg class="v9-sub-chev" width="10" height="10" viewBox="0 0 10 10" aria-hidden="true"><path d="M3 2l4 3-4 3z" fill="currentColor"/></svg>';
    return `<tr class="va-row-compact v9-sub-rollup-row${isDim ? " is-dim" : ""}" data-sub-rollup="unregistered">
      <td><button type="button" class="v9-sub-rollup-btn" aria-expanded="${isExpanded ? "true" : "false"}">${chev}<span>Unregistered / Ad-hoc (${roleLbl})</span></button></td>
      <td class="v9-col-secondary"><span class="v9-adj-pill">Historical ad-hoc</span></td>
      <td class="v9-bar-cell">${barHtml}</td>
      <td class="num">${runs}</td>
      <td class="num">${V9.fmtNum(tokens)}</td>
      <td class="num v9-col-secondary v9-mono-num">${V9.fmtNum(avgTok)}</td>
      <td class="num v9-mono-num">${V9.fmtUsd(cost)}</td>
    </tr>`;
  }

  function renderSubagentTable(b, rerenderFn) {
    const tbody = document.getElementById("v9SubagentTableBody");
    const subEl = document.getElementById("v9SubPlotSub");
    if (!tbody) return;
    const metric = V9.state.metric || "steps";
    const list = Array.isArray(b.subagent_list) ? b.subagent_list : [];
    const totalRuns = list.reduce((s, r) => s + Number(r.runs || 0), 0);
    const totalTok = list.reduce((s, r) => s + Number(r.tokens || 0), 0);
    const fleetMeanTok = totalRuns > 0 ? totalTok / totalRuns : 0;

    const table = tbody.closest && tbody.closest("table");
    ensureSubagentTableHead(table);
    const TS = V9.TableSort;
    const SB = V9.SparkBars;
    const sl = document.getElementById("v9SubagentTableLegend");
    if (sl && SB && SB.renderTableLegend) sl.innerHTML = SB.renderTableLegend("subagents", metric);
    const enriched = list.map((item, origIdx) => {
      const runs = Number(item.runs || 0);
      const avgTok = Number(item.avg_tokens_per_run != null ? item.avg_tokens_per_run : (runs > 0 ? Math.round(Number(item.tokens || 0) / runs) : 0));
      const sm = SB ? SB.computeSubagentMetrics(item, metric, b.subagent_series, fleetMeanTok) : null;
      return { item, origIdx, runs, avgTok, sm };
    });
    const scaleMax = enriched.reduce((mx, e) => Math.max(mx, e.sm && Number.isFinite(e.sm.max) ? e.sm.max : 0), 0) || 1;
    const sorted = TS
      ? TS.sortItems(enriched, "subagents", {
          name: { type: "text", get: (e) => e.item.role || "" },
          model: { type: "text", get: (e) => e.item.dominant_model_label || e.item.dominant_model_key || "" },
          share: (e) => {
            if (e.sm && (metric !== "steps" || e.item.max_steps_per_run != null || e.item.steps != null)) {
              return (e.sm.max / scaleMax) * 1e12 + (e.sm.avg / scaleMax) * 1e-3;
            }
            return Number(e.item.share_pct || 0) * 1e9 + Number(e.item.steps || 0);
          },
          runs: (e) => e.runs,
          tokens: (e) => Number(e.item.tokens || 0),
          avg_tok: (e) => e.avgTok,
          cost: (e) => Number(e.item.est_cost_usd || 0),
        })
      : enriched;
    const regEntries = [], unregEntries = [];
    sorted.forEach((e) => (isRegisteredRole(e.item) ? regEntries : unregEntries).push(e));
    if (subEl) {
      subEl.textContent = unregEntries.length
        ? `${totalRuns} runs · ${regEntries.length} canonical + ${unregEntries.length} ad-hoc`
        : `${totalRuns} runs · ${regEntries.length} roles`;
    }
    const isExpanded = Boolean(V9.state.showUnregSubagents);
    const hasSoloUnreg = Boolean(V9.state.soloSubagent && unregEntries.some((e) => e.item.role === V9.state.soloSubagent));
    const rowsHtml = regEntries.map((entry) => renderSubagentRow(entry, scaleMax, metric, SB, ""));
    if (unregEntries.length > 0) {
      rowsHtml.push(buildUnregSummaryRow(unregEntries, scaleMax, metric, fleetMeanTok, SB, isExpanded, Boolean(V9.state.soloSubagent && !hasSoloUnreg)));
      if (isExpanded) {
        unregEntries.forEach((entry) => rowsHtml.push(renderSubagentRow(entry, scaleMax, metric, SB, "v9-sub-unreg-child")));
      }
    }
    tbody.innerHTML = rowsHtml.join("");
    tbody.querySelectorAll("tr[data-solo-sub]").forEach((tr) => {
      tr.addEventListener("click", () => {
        const role = tr.getAttribute("data-solo-sub") || "";
        V9.state.soloSubagent = V9.state.soloSubagent === role ? "" : role;
        if (typeof rerenderFn === "function") rerenderFn();
      });
    });
    tbody.querySelectorAll(".v9-sub-rollup-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const hadFocus = typeof document !== "undefined" && document.activeElement === btn;
        V9.state.showUnregSubagents = !V9.state.showUnregSubagents;
        renderSubagentTable(V9.state.bundle || b, rerenderFn);
        if (hadFocus) tbody.querySelector?.(".v9-sub-rollup-btn")?.focus?.();
      });
    });
    if (TS && table) {
      TS.bindSortHeaders(table, "subagents", () => renderSubagentTable(V9.state.bundle || b, rerenderFn), () => regEntries.length);
    }
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
        <span>Release: ${V9.escHtml((ch.version && ch.version.status_label) || b.version || "4.2.0")}</span>
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
    if (V9.CatalogBanner && V9.CatalogBanner.render) {
      V9.CatalogBanner.render(b, { onReload: actions && actions.reloadStats });
    }
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

  V9.Analytics = { renderAnalytics, renderKpiCards, formatResetCountdown, formatSnapshotAge };
})();
