/* SPDX-License-Identifier: Apache-2.0 */
/* AGY-Nexus /web/v9 — Option A Hybrid Range Whiskers & Target/Seam Caret Bars */
(() => {
  const V9 = (window.AgyV9 = window.AgyV9 || {});
  const CARET_SVG = '<svg width="8" height="5" viewBox="0 0 8 6" aria-hidden="true"><path d="M4 6L0.4 0.5H7.6L4 6Z" fill="currentColor"/></svg>';

  const clampPct = (v) => Math.max(0, Math.min(100, Number.isFinite(v) ? v : 0));
  const fin = (v, fb = 0) => (v != null && Number.isFinite(Number(v)) ? Number(v) : fb);
  const ESC_MAP = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  const esc = (s) => (V9.escHtml ? V9.escHtml(s) : String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ESC_MAP[c]));
  const safeCol = (c) => (typeof c === "string" && /^(#[0-9a-fA-F]{3,8}|var\(--[a-zA-Z0-9_-]+\)|rgba?\([0-9.,\s%]+\))$/.test(c.trim()) ? c.trim() : "var(--accent)");
  const fmtNum = (n) => (V9.fmtNum ? V9.fmtNum(fin(n, 0)) : String(Math.round(fin(n, 0))));
  const fmtUsd = (n) => (V9.fmtUsd ? V9.fmtUsd(fin(n, 0)) : `$${fin(n, 0).toFixed(2)}`);

  function fmtMetric(val, metric, compact) {
    const n = fin(val, 0);
    if (metric === "cost") return fmtUsd(n);
    if (metric === "tokens") return fmtNum(n);
    if (compact && n > 0 && n < 10) return Number(n.toFixed(1)).toString();
    return fmtNum(n);
  }

  function sumLayer(layerMap, key, fallback) {
    const arr = layerMap && layerMap[key];
    return Array.isArray(arr) && arr.length ? arr.reduce((a, b) => a + fin(b, 0), 0) : fin(fallback, 0);
  }

  function trailing24hFromSeries(arr, dates, stepHours) {
    if (!Array.isArray(arr) || !arr.length) return null;
    const stepH = Math.max(1, fin(stepHours || (String(dates?.[0] || "").length > 10 ? 1 : 24), 24));
    const take = Math.max(1, Math.min(arr.length, Math.round(24 / stepH)));
    let sum = 0;
    for (let i = arr.length - take; i < arr.length; i += 1) sum += fin(arr[i], 0);
    return sum;
  }

  function computeProjectMetrics(p, metric, dates, stepHours) {
    const m = metric === "cost" ? "cost_usd" : (metric === "tokens" ? "tokens" : "steps");
    let min = p[`min_daily_${m}`], avg = p[`avg_daily_${m}`], max = p[`max_daily_${m}`], l24 = p[`last_24h_${m}`];
    if (max == null || avg == null) {
      const arr = metric === "cost" ? p.cost_series : (metric === "tokens" ? p.tokens_series : p.steps_series);
      const daySums = new Map();
      if (Array.isArray(arr) && arr.length) {
        arr.forEach((v, idx) => {
          const d = String((dates && dates[idx]) || idx).slice(0, 10);
          daySums.set(d, (daySums.get(d) || 0) + fin(v, 0));
        });
      }
      const nz = Array.from(daySums.values()).filter((v) => v > 0);
      if (nz.length) {
        min = Math.min(...nz); max = Math.max(...nz);
        avg = nz.reduce((a, b) => a + b, 0) / nz.length;
        if (l24 == null && p.has_last_24h !== false) l24 = trailing24hFromSeries(arr, dates, stepHours);
      } else {
        const tot = fin(metric === "cost" ? p.window_cost_usd : (metric === "tokens" ? p.window_tokens : p.window_steps), 0);
        min = tot; avg = tot; max = tot;
        if (l24 == null) l24 = p.has_last_24h === false ? null : 0;
      }
    }
    const hasL24 = p.has_last_24h != null ? Boolean(p.has_last_24h) : l24 != null;
    return { min: fin(min, 0), avg: fin(avg, 0), max: fin(max, 0), last24h: hasL24 && l24 != null ? fin(l24, 0) : null, hasLast24h: hasL24, sharePct: fin(p.share_pct, 0) };
  }

  function computeSubagentMetrics(item, metric, subSeries, fleetMeanTok) {
    const runs = Math.max(1, fin(item.runs, 1));
    const fld = metric === "cost" ? "cost_usd" : (metric === "tokens" ? "tokens" : "steps");
    const tot = fin(metric === "cost" ? item.est_cost_usd : (metric === "tokens" ? item.tokens : item.steps), 0);
    const avg = fin(item[`avg_${fld}_per_run`], tot / runs);
    const min = fin(item[`min_${fld}_per_run`], avg);
    const max = fin(item[`max_${fld}_per_run`], avg);
    let l24 = item[`last_24h_${fld}`];
    if (l24 == null && item.has_last_24h !== false && subSeries) {
      const lMap = metric === "cost" ? subSeries.cost_layers : (metric === "tokens" ? subSeries.token_layers : subSeries.layers);
      if (lMap && lMap[item.role]) l24 = trailing24hFromSeries(lMap[item.role], subSeries.dates, subSeries.step_hours);
    }
    const latest = item[`last_run_${fld}`] != null ? fin(item[`last_run_${fld}`], avg) : (l24 != null ? fin(l24, avg) : avg);
    const maxSteps = fin(item.max_steps_per_run, 0), over120 = fin(item.over_120_runs, 0);
    const isStepCapOver = over120 > 0 || maxSteps > 120;
    const avgTok = fin(item.avg_tokens_per_run, fin(item.tokens, 0) / runs);
    const burnRatio = fleetMeanTok > 0 ? avgTok / fleetMeanTok : 0;
    return {
      min, avg, max, latest, last24h: item.has_last_24h === false ? null : (l24 != null ? fin(l24, 0) : null),
      hasLast24h: item.has_last_24h !== false && (item[`last_run_${fld}`] != null || l24 != null),
      isStepCapOver, isHeavyBurn: !isStepCapOver && burnRatio > 2.5, over120Runs: over120, maxSteps, burnRatio, runs,
    };
  }

  function computeModelRows(rows, metric, modelSeries) {
    const ms = modelSeries || {};
    const stepH = ms.step_hours || 1, dates = ms.dates || [];
    const lMap = metric === "cost" ? ms.cost_layers : (metric === "tokens" ? ms.token_layers : ms.layers);
    const raw = (rows || []).map((m, origIdx) => {
      const mk = m.model_key || m.key || "";
      const val = metric === "cost" ? fin(m.est_cost_usd, 0)
        : (metric === "tokens" ? sumLayer(ms.token_layers, mk, m.est_tokens) : fin(m.actual_calls, 0));
      let l24 = metric === "cost" ? m.last_24h_cost_usd : (metric === "tokens" ? m.last_24h_tokens : m.last_24h_steps);
      if (l24 == null && m.has_last_24h !== false && lMap && lMap[mk]) l24 = trailing24hFromSeries(lMap[mk], dates, stepH);
      return { m, origIdx, val, l24: m.has_last_24h === false ? null : (l24 != null ? fin(l24, 0) : null) };
    });
    const totVal = raw.reduce((s, r) => s + r.val, 0);
    const totL24 = raw.reduce((s, r) => s + (r.l24 != null ? r.l24 : 0), 0);
    return raw.map((r) => {
      const pre = metric === "cost" ? r.m.cost_share_pct : (metric === "tokens" ? r.m.token_share_pct : r.m.actual_pct);
      const actualPct = totVal > 0 ? (metric === "steps" && r.m.actual_pct != null ? fin(r.m.actual_pct, 0) : (r.val / totVal) * 100) : fin(pre, 0);
      const targetPct = fin(r.m.target_pct, 0);
      const last24hPct = (r.m.has_last_24h !== false && totL24 > 0 && r.l24 != null) ? (r.l24 / totL24) * 100 : null;
      return { m: r.m, origIdx: r.origIdx, val: r.val, tok: sumLayer(ms.token_layers, r.m.model_key || r.m.key, r.m.est_tokens), actualPct, targetPct, deltaPct: Number((actualPct - targetPct).toFixed(1)), last24hPct };
    });
  }

  function computeSessionRows(sessions, metric, pss) {
    const dates = (pss && pss.dates) || [], stepH = (pss && pss.step_hours) || 1;
    const lMap = pss ? (metric === "cost" ? pss.cost_layers : (metric === "tokens" ? pss.token_layers : pss.layers)) : null;
    const items = (sessions || []).map((s, origIdx) => {
      const cid = s.conversation_id || "";
      const windowSteps = fin(s.window_steps != null ? s.window_steps : s.step_count, 0);
      const stepCount = fin(s.step_count != null ? s.step_count : windowSteps, 0);
      const tokens = fin(s.window_tokens != null ? s.window_tokens : s.tokens, 0);
      const costUsd = fin(s.window_cost_usd, 0);
      const isRetired = Boolean(s.is_retired) || String(s.status || "").trim().toUpperCase() === "RETIRED";
      let l24 = metric === "cost" ? s.last_24h_cost_usd : (metric === "tokens" ? s.last_24h_tokens : s.last_24h_steps);
      if (l24 == null && s.has_last_24h !== false && lMap && lMap[cid]) l24 = trailing24hFromSeries(lMap[cid], dates, stepH);
      const val = metric === "cost" ? costUsd : (metric === "tokens" ? tokens : stepCount);
      const state = isRetired ? "retired" : (stepCount >= 700 ? "fault" : (stepCount >= 500 ? "warn" : "nominal"));
      return { s, origIdx, cid, windowSteps, stepCount, tokens, costUsd, val, isRetired, state, last24h: s.has_last_24h === false ? null : (l24 != null ? fin(l24, 0) : null) };
    });
    const actVals = items.map((e) => e.val).filter((v) => v > 0);
    const avgActive = actVals.length ? actVals.reduce((a, b) => a + b, 0) / actVals.length : 0;
    const maxVal = items.reduce((m, e) => Math.max(m, e.val, e.last24h || 0), 0);
    const scaleMax = metric === "steps" ? Math.max(750, maxVal) : Math.max(1e-6, maxVal, avgActive);
    return { items, avgActive, scaleMax };
  }

  function renderWhiskerMarkup({ min, avg, max, dot, hasDot, scaleMax, color, state, tip, readout, flagHtml }) {
    const den = Math.max(1e-6, fin(scaleMax || max, 1));
    const mnP = clampPct((fin(min, 0) / den) * 100), mxP = clampPct((fin(max, 0) / den) * 100), avP = clampPct((fin(avg, 0) / den) * 100);
    const barW = Math.max(3, mxP - mnP);
    const barCol = safeCol(state === "fault" ? "var(--status-danger)" : (state === "warn" ? "var(--status-warn)" : color));
    const tether = mnP > 1.5 ? `<span class="v9-whisk-tether" style="inline-size:${mnP.toFixed(1)}%"></span>` : "";
    let dotHtml = "";
    if (hasDot && dot != null) {
      const idle = fin(dot, 0) <= 0;
      const dP = idle ? 0 : clampPct((fin(dot, 0) / den) * 100);
      dotHtml = `<span class="v9-whisk-dot${idle ? " is-idle" : ""}" style="inset-inline-start:${dP.toFixed(1)}%;--v9-dot-bg:${idle ? "var(--bg-surface)" : esc(barCol)};--v9-dot-bd:${idle ? "var(--text-muted)" : "var(--bg-surface)"}"></span>`;
    }
    return `<div class="v9-spk"${state ? ` data-state="${esc(state)}"` : ""} title="${esc(tip)}"><span class="v9-spk-track" role="img" aria-label="${esc(tip)}"><span class="v9-spk-rail">${tether}<span class="v9-whisk-bar" style="inset-inline-start:${mnP.toFixed(1)}%;inline-size:${barW.toFixed(1)}%;background:${esc(barCol)}"></span><span class="v9-whisk-avg" style="inset-inline-start:${avP.toFixed(1)}%"></span>${dotHtml}</span></span><span class="v9-spk-val">${esc(readout)}${flagHtml || ""}</span></div>`;
  }

  function renderProjectWhisker(pm, scaleMax, metric, color) {
    const l24Txt = pm.hasLast24h && pm.last24h != null ? fmtMetric(pm.last24h, metric, true) : "N/A";
    const tip = `Active-Day Avg: ${fmtMetric(pm.avg, metric, true)} · Peak Day: ${fmtMetric(pm.max, metric, true)} · Last 24h: ${l24Txt} · Share: ${fin(pm.sharePct, 0).toFixed(1)}%`;
    return renderWhiskerMarkup({ min: pm.min, avg: pm.avg, max: pm.max, dot: pm.last24h, hasDot: pm.hasLast24h, scaleMax, color, state: "", tip, readout: `${fmtMetric(pm.avg, metric, true)}/d` });
  }

  function renderSubagentWhisker(sm, scaleMax, metric, color) {
    const state = sm.isStepCapOver ? "fault" : (sm.isHeavyBurn ? "warn" : "");
    const bStr = fin(sm.burnRatio, 0).toFixed(1);
    const flagHtml = sm.isStepCapOver ? ` <span class="v9-cap-flag is-fault">&gt;120</span>` : (sm.isHeavyBurn ? ` <span class="v9-cap-flag is-warn">${esc(bStr)}x</span>` : "");
    const capNote = sm.isStepCapOver ? ` · CAP ALERT: ${sm.over120Runs || 1} run(s) >120 steps (max ${sm.maxSteps || Math.round(fin(sm.max, 0))}s)` : (sm.isHeavyBurn ? ` · HEAVY BURN: ${bStr}x fleet mean` : "");
    const tip = `Avg/Run: ${fmtMetric(sm.avg, metric, true)} · Max/Run: ${fmtMetric(sm.max, metric, true)} · Latest: ${fmtMetric(sm.latest, metric, true)} · Runs: ${sm.runs}${capNote}`;
    return renderWhiskerMarkup({ min: sm.min, avg: sm.avg, max: sm.max, dot: sm.latest, hasDot: sm.latest != null, scaleMax, color, state, tip, readout: `${fmtMetric(sm.avg, metric, true)} avg · ${fmtMetric(sm.max, metric, true)} max`, flagHtml });
  }

  function renderModelCaretBar(mm, color) {
    const actPct = fin(mm.actualPct, 0), tgtPct = fin(mm.targetPct, 0);
    const actP = clampPct(actPct), tgtP = clampPct(tgtPct);
    const l24Str = mm.last24hPct != null ? `${fin(mm.last24hPct, 0).toFixed(1)}%` : "N/A";
    const tip = `Window: ${actPct.toFixed(1)}% · Last 24h: ${l24Str} · Guide: ${tgtPct.toFixed(0)}%`;
    let caret = "";
    if (mm.last24hPct != null) {
      const idle = fin(mm.last24hPct, 0) <= 0;
      caret = `<span class="v9-top-caret${idle ? " is-idle" : ""}" style="inset-inline-start:${clampPct(mm.last24hPct).toFixed(1)}%">${CARET_SVG}</span>`;
    }
    return `<div class="v9-spk" title="${esc(tip)}"><span class="v9-spk-track" role="img" aria-label="${esc(tip)}"><span class="v9-spk-rail"><span class="v9-caret-fill" style="inline-size:${actP.toFixed(1)}%;background:${esc(safeCol(color))}"></span><span class="v9-whisk-avg" style="inset-inline-start:${tgtP.toFixed(1)}%"></span>${caret}</span></span><span class="v9-spk-val">${actPct.toFixed(1)}%</span></div>`;
  }

  function renderSessionCaretBar(sm, scaleMax, avgActive, metric, color) {
    const den = Math.max(1e-6, fin(scaleMax, 1));
    if (metric === "steps") {
      const ctxP = clampPct((sm.stepCount / den) * 100), winP = clampPct((sm.windowSteps / den) * 100);
      const seamP = clampPct((320 / den) * 100), rollP = clampPct((700 / den) * 100);
      const barCol = safeCol(sm.state === "retired" ? "var(--text-muted)" : (sm.state === "fault" ? "var(--status-danger)" : (sm.state === "warn" ? "var(--status-warn)" : color)));
      const baseOp = winP < ctxP - 0.5 ? " is-muted" : "";
      const winOv = winP > 0 && winP < ctxP - 0.5 ? `<span class="v9-caret-fill" style="inline-size:${winP.toFixed(1)}%;background:${esc(barCol)}"></span>` : "";
      const flag = sm.state === "fault" ? ` <span class="v9-cap-flag is-fault">700+</span>` : (sm.state === "warn" ? ` <span class="v9-cap-flag is-warn">500+</span>` : (sm.isRetired ? ` <span class="v9-cap-flag is-muted">RET</span>` : ""));
      const tip = `Context: ${fmtNum(sm.stepCount)} steps (${fmtNum(sm.windowSteps)} in window) · Clean Seam: 320 · Rollover: 700 · ${sm.isRetired ? "RETIRED" : (sm.s.status || "IDLE")}`;
      return `<div class="v9-spk" data-state="${esc(sm.state)}" title="${esc(tip)}"><span class="v9-spk-track" role="img" aria-label="${esc(tip)}"><span class="v9-spk-rail"><span class="v9-caret-fill${baseOp}" style="inline-size:${ctxP.toFixed(1)}%;background:${esc(barCol)}"></span>${winOv}<span class="v9-whisk-avg" style="inset-inline-start:${seamP.toFixed(1)}%"></span><span class="v9-top-caret is-seam${sm.state === "fault" || sm.state === "warn" ? " is-alert" : ""}" style="inset-inline-start:${rollP.toFixed(1)}%">${CARET_SVG}</span></span></span><span class="v9-spk-val">${fmtNum(sm.stepCount)}s${flag}</span></div>`;
    }
    const fillP = clampPct((sm.val / den) * 100), avgP = clampPct((avgActive / den) * 100);
    const l24Str = sm.last24h != null ? fmtMetric(sm.last24h, metric, true) : "N/A";
    const tip = `Session: ${fmtMetric(sm.val, metric, true)} · Project Avg: ${fmtMetric(avgActive, metric, true)} · Last 24h: ${l24Str}`;
    let caret = "";
    if (sm.last24h != null) {
      const idle = fin(sm.last24h, 0) <= 0;
      caret = `<span class="v9-top-caret${idle ? " is-idle" : ""}" style="inset-inline-start:${clampPct((sm.last24h / den) * 100).toFixed(1)}%">${CARET_SVG}</span>`;
    }
    return `<div class="v9-spk" title="${esc(tip)}"><span class="v9-spk-track" role="img" aria-label="${esc(tip)}"><span class="v9-spk-rail"><span class="v9-caret-fill" style="inline-size:${fillP.toFixed(1)}%;background:${esc(safeCol(color))}"></span><span class="v9-whisk-avg" style="inset-inline-start:${avgP.toFixed(1)}%"></span>${caret}</span></span><span class="v9-spk-val">${esc(fmtMetric(sm.val, metric, true))}</span></div>`;
  }

  function renderTableLegend(kind, metric) {
    const it = (cls, lbl, inner = "") => `<span class="v9-lg-item"><span class="v9-lg-sw is-${cls}">${inner}</span>${esc(lbl)}</span>`;
    let body = "";
    if (kind === "models") body = `${it("fill", "Window share")}${it("avg", "Guide target")}${it("caret", "Last 24h share", CARET_SVG)}<span class="v9-lg-hint">Tap row to solo</span>`;
    else if (kind === "subagents") body = `${it("bar", "Min–Max / run")}${it("avg", "Avg / run")}${it("dot", "Latest run")}<span class="v9-lg-item"><span class="v9-cap-flag is-fault">&gt;120</span>Any run &gt;120 steps</span>`;
    else if (kind === "projects") body = `${it("bar", "Active-day Min–Peak")}${it("avg", "Avg / day")}${it("dot", "Last 24h")}${it("idle", "Idle 24h")}`;
    else if (kind === "sessions") body = metric === "steps" ? `${it("fill", "Session steps")}${it("avg", "320 clean seam")}${it("caret", "700 rollover limit", CARET_SVG)}` : `${it("fill", "Session total")}${it("avg", "Project avg")}${it("caret", "Last 24h", CARET_SVG)}`;
    return body ? `<div class="v9-table-legend" role="note" aria-label="Table bar key">${body}</div>` : "";
  }

  V9.SparkBars = { computeProjectMetrics, computeSubagentMetrics, computeModelRows, computeSessionRows, renderProjectWhisker, renderSubagentWhisker, renderModelCaretBar, renderSessionCaretBar, renderTableLegend };
})();
