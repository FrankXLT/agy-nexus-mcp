/* SPDX-License-Identifier: Apache-2.0 */
/* AGY-Nexus /web/v9 — Snapshot Demo Adapter (Uses DEMO_SNAPSHOT & Existing Static Thumbs Only) */
(() => {
  const V9 = window.AgyV9;
  function cloneJson(obj) {
    return JSON.parse(JSON.stringify(obj));
  }

  function resolveDemoSnapshotSpec(timeframe, mode, offset) {
    const tf = timeframe || "month";
    const hm = mode || "to_date";
    const off = Number(offset || 0);
    if (tf === "month" && hm === "to_date") {
      if (off < 0) return { key: "last_month", canPrev: false, canNext: true };
      return { key: "current_month", canPrev: true, canNext: false };
    }
    if (tf === "month" && hm === "rolling") {
      return { key: "last_30d", canPrev: false, canNext: false };
    }
    if (tf === "quarter" && hm === "to_date") {
      return { key: "qtd", canPrev: false, canNext: false };
    }
    if (tf === "quarter" && hm === "rolling") {
      return { key: "last_90d", canPrev: false, canNext: false };
    }
    if (tf === "year" && hm === "to_date") {
      return { key: "ytd", canPrev: false, canNext: false };
    }
    if (tf === "year" && hm === "rolling") {
      return { key: "last_year", canPrev: false, canNext: false };
    }
    return { key: "current_month", canPrev: false, canNext: false };
  }

  function isPresetAvailable(timeframe, mode) {
    const snap = window.DEMO_SNAPSHOT;
    if (!snap || !snap.bundles) return false;
    const spec = resolveDemoSnapshotSpec(timeframe, mode, 0);
    return Boolean(snap.bundles[spec.key]);
  }

  function getDemoStatsBundle(timeframe, mode, offset) {
    const snap = window.DEMO_SNAPSHOT;
    if (!snap || !snap.bundles) return null;
    const spec = resolveDemoSnapshotSpec(timeframe, mode, offset);
    const raw = snap.bundles[spec.key] || snap.bundles.current_month || Object.values(snap.bundles)[0];
    if (!raw) return null;
    const bundle = cloneJson(raw);
    if (!bundle.code_health && snap.code_health) bundle.code_health = cloneJson(snap.code_health);
    return bundle;
  }

  function getDemoBounds(timeframe, mode, offset) {
    return resolveDemoSnapshotSpec(timeframe, mode, offset);
  }

  function getDemoWorkspaceTree() {
    const snap = window.DEMO_SNAPSHOT;
    if (snap && snap.workspace_tree) return cloneJson(snap.workspace_tree);
    return { ok: true, version: "4.0.2", queue: { staged_count: 0, tickets: [] }, projects: [] };
  }

  function getDemoSessionBucket(sessionId) {
    const tree = V9.state.wsTree || getDemoWorkspaceTree();
    if (V9.DemoDocs) return V9.DemoDocs.getDemoSessionBucket(sessionId, tree);
    return Promise.resolve({ ok: true, conversation_id: sessionId || "demo-session", artifacts: [], uploads: [], visual_artifacts: [], repo_visual_assets: [] });
  }

  function getDemoDocFile(relPath, bucket) {
    if (V9.DemoDocs) return V9.DemoDocs.getDemoDocFile(relPath, bucket);
    return Promise.resolve({ ok: true, rel_path: relPath || "session-summary.md", content: "", raw_content: "", size: 0 });
  }

  function hierarchyProjects(h) {
    if (!h) return [];
    const other = Array.isArray(h.other_projects)
      ? h.other_projects
      : (h.other_projects && typeof h.other_projects === "object" ? [h.other_projects] : []);
    return [...(h.top_projects || []), ...other, ...(h.idle_projects || [])];
  }

  function enrichHierarchy(h) {
    if (!h) return;
    let total = 0;
    let bestId = "";
    let bestTs = -1;
    for (const p of hierarchyProjects(h)) {
      const list = p.sessions || [];
      total += list.length;
      for (const s of list) {
        if (!s.last_updated_ts && s.last_updated) {
          const parsed = Date.parse(s.last_updated);
          if (Number.isFinite(parsed)) s.last_updated_ts = parsed / 1000;
        }
        const ts = Number(s.last_updated_ts || 0);
        if (s.conversation_id && (!bestId || ts >= bestTs)) {
          bestTs = ts;
          bestId = s.conversation_id;
        }
      }
    }
    const snapProjs = (typeof window !== "undefined" && window.DEMO_SNAPSHOT && window.DEMO_SNAPSHOT.workspace_tree && window.DEMO_SNAPSHOT.workspace_tree.projects) || [];
    const wsTotal = snapProjs.reduce((sum, p) => sum + ((p.sessions && p.sessions.length) || 0), 0);
    if (!h.total_sessions_count) h.total_sessions_count = wsTotal || total;
    if (!h.latest_session_id && bestId) h.latest_session_id = bestId;
  }

  function buildScopedProjectSeries(proj, dates) {
    const winStepsOf = (s) => Number(s && s.window_steps != null ? s.window_steps : (proj.is_idle ? 0 : (s && s.step_count) || 0));
    const list = [...(proj.sessions || [])].sort(
      (a, b) => winStepsOf(b) - winStepsOf(a) || Number((b && b.step_count) || 0) - Number((a && a.step_count) || 0)
    );
    const n = dates.length;
    const keys = [];
    const labels = {};
    const colors = {};
    const layers = {};
    const tokenLayers = {};
    const pTotal = list.reduce((acc, s) => acc + winStepsOf(s), 0) || 1;
    const pSeriesSteps = Array.isArray(proj.steps_series) ? proj.steps_series : [];
    const pSeriesToks = Array.isArray(proj.tokens_series) ? proj.tokens_series : [];
    const roster = [];
    const overflowSteps = new Array(n).fill(0);
    const overflowTok = new Array(n).fill(0);
    let otherCount = 0;
    let activeIdx = 0;
    list.forEach((s, idx) => {
      const cid = s.conversation_id || `sess-${idx}`;
      const steps = winStepsOf(s);
      const isAct = steps > 0;
      const share = isAct ? Number(((steps / pTotal) * 100).toFixed(1)) : 0;
      const slot = isAct ? (activeIdx < 11 ? activeIdx : 11) : 11;
      roster.push(Object.assign({}, s, { short_id: cid.slice(0, 8), share_pct: share, color_slot: slot }));
      if (!isAct) return;
      const weight = steps / pTotal;
      const ss = Array.isArray(s.steps_series) && s.steps_series.length
        ? s.steps_series
        : pSeriesSteps.map((v) => Math.round(Number(v || 0) * weight));
      const ts = Array.isArray(s.tokens_series) && s.tokens_series.length
        ? s.tokens_series
        : pSeriesToks.map((v) => Math.round(Number(v || 0) * weight));
      if (activeIdx < 11) {
        keys.push(cid);
        labels[cid] = s.title || cid.slice(0, 8);
        colors[cid] = activeIdx;
        layers[cid] = Array.from({ length: n }, (_, i) => Number(ss[i] || 0));
        tokenLayers[cid] = Array.from({ length: n }, (_, i) => Number(ts[i] || 0));
      } else {
        otherCount += 1;
        for (let i = 0; i < n; i += 1) {
          overflowSteps[i] += Number(ss[i] || 0);
          overflowTok[i] += Number(ts[i] || 0);
        }
      }
      activeIdx += 1;
    });
    const ovfCost = new Array(n).fill(0);
    const pTokTotal = list.reduce((a, s) => a + Number((s && (s.window_tokens != null ? s.window_tokens : s.tokens)) || 0), 0) || Number(proj.window_tokens || 0);
    const pCostTotal = Number(proj.window_cost_usd || 0);
    const pSeriesCost = Array.isArray(proj.cost_series) && proj.cost_series.length ? proj.cost_series : [];
    const costPerTok = pTokTotal > 0 && pCostTotal > 0 ? pCostTotal / pTokTotal : 0;
    const costLayers = {};
    for (const cid of keys) {
      if (cid === "__other_sessions__") continue;
      const tArr = tokenLayers[cid] || [];
      costLayers[cid] = tArr.map((tv, i) => {
        if (costPerTok > 0) return Number((Number(tv || 0) * costPerTok).toFixed(4));
        const fs = Number(pSeriesCost[i] || 0);
        return Number((fs * ((Number(pSeriesToks[i] || 0) > 0 ? Number(tv || 0) / Number(pSeriesToks[i]) : 0))).toFixed(4));
      });
    }
    if (otherCount > 0) {
      const ovf = proj.overflow_sessions_series || {};
      const hasOvfSteps = overflowSteps.some((v) => v > 0);
      keys.push("__other_sessions__");
      labels.__other_sessions__ = `Other (${otherCount} sessions)`;
      colors.__other_sessions__ = 11;
      layers.__other_sessions__ = (hasOvfSteps || !Array.isArray(ovf.steps_series)) ? overflowSteps : ovf.steps_series.slice(0, n);
      tokenLayers.__other_sessions__ = (hasOvfSteps || !Array.isArray(ovf.tokens_series)) ? overflowTok : ovf.tokens_series.slice(0, n);
      for (let i = 0; i < n; i += 1) ovfCost[i] = Number((Number(tokenLayers.__other_sessions__[i] || 0) * costPerTok).toFixed(4));
      costLayers.__other_sessions__ = ovfCost;
    }
    return {
      dates,
      step_hours: 1,
      resolution: "1h base slots",
      keys,
      layers,
      token_layers: tokenLayers,
      cost_layers: costLayers,
      labels,
      colors,
      sessions: roster,
    };
  }

  function roundUsd(val, digits = 2) {
    const n = Number(val || 0);
    const factor = 10 ** digits;
    return Math.round(n * factor) / factor;
  }

  function scaleLayerMap(dates, fleetSteps, pStepsArr, srcLayers, floatDigits = 0) {
    const out = {};
    const fleetSum = fleetSteps.reduce((a, b) => a + Number(b || 0), 0) || 1;
    const pSum = pStepsArr.reduce((a, b) => a + Number(b || 0), 0);
    const ratio = pSum / fleetSum;
    for (const [k, arr] of Object.entries(srcLayers || {})) {
      out[k] = (arr || []).map((v, i) => {
        const fs = Number(fleetSteps[i] || 0);
        const slotRatio = fs > 0 && i < pStepsArr.length ? Number(pStepsArr[i] || 0) / fs : ratio;
        const scaled = Number(v || 0) * Math.max(0, Math.min(1, slotRatio));
        return floatDigits > 0 ? roundUsd(scaled, floatDigits) : Math.round(scaled);
      });
    }
    return out;
  }

  function scopeHeatmapForProject(raw, dates, pStepsArr, pTokArr, sessCount, projCostUsd, pTokTotal) {
    const dayMap = {};
    dates.forEach((d, i) => {
      const day = String(d || "").slice(0, 10);
      if (!day) return;
      if (!dayMap[day]) dayMap[day] = { steps: 0, tokens: 0 };
      dayMap[day].steps += Number(pStepsArr[i] || 0);
      dayMap[day].tokens += Number(pTokArr[i] || 0);
    });
    const maxDaySteps = Math.max(1, ...Object.values(dayMap).map((x) => x.steps));
    const costPerTok = pTokTotal > 0 ? Number(projCostUsd || 0) / pTokTotal : 0;
    let activeDays = 0;
    let peakDay = { date: "", steps: 0 };
    if (Array.isArray(raw.heatmap_series)) {
      raw.heatmap_series.forEach((cell) => {
        const d = dayMap[cell.date] || { steps: 0, tokens: 0 };
        cell.steps = d.steps;
        cell.tokens = d.tokens;
        cell.cost_usd = roundUsd(d.tokens * costPerTok, 4);
        cell.tools = Math.round(d.steps * 0.62);
        cell.sessions = d.steps > 0 ? Math.max(1, sessCount) : 0;
        cell.level = d.steps <= 0 ? 0 : Math.min(4, Math.max(1, Math.ceil((d.steps / maxDaySteps) * 4)));
        if (d.steps > 0 && cell.in_window) activeDays += 1;
        if (cell.in_window && d.steps >= peakDay.steps) peakDay = { date: cell.date, steps: d.steps };
      });
    }
    return { activeDays, peakDay };
  }

  function buildDemoProjectScope(proj, wsProj, snap, opts) {
    const sessions = proj.sessions || [];
    const maxSess = sessions.reduce(
      (best, s) => (Number(s.step_count || s.window_steps || 0) > Number(best.step_count || best.window_steps || 0) ? s : best),
      sessions[0] || {}
    );
    const maxSteps = Number(maxSess.step_count || maxSess.window_steps || 0);
    const runCnt = sessions.filter((s) => s.is_running).length;
    const ch = (snap && snap.code_health && snap.code_health.modular_hygiene) || {};
    return {
      project_id: proj.project_id,
      project_name: proj.project_name,
      workspace_path: (sessions[0] && sessions[0].workspace_path) || `/workspace/${proj.project_name}`,
      color_slot: proj.color_slot || 0,
      fleet_window_steps: opts.fleetSteps,
      share_of_workstation_pct: Number((proj.share_pct != null ? proj.share_pct : opts.shareRatio * 100).toFixed(1)),
      total_sessions: sessions.length,
      active_sessions_count: Number(
        proj.active_sessions_count != null
          ? proj.active_sessions_count
          : (proj.is_idle ? 0 : sessions.filter((s) => Number((s && s.window_steps) || 0) > 0).length)
      ),
      running_count: runCnt,
      idle_count: Math.max(0, sessions.length - runCnt),
      window_cost_usd: roundUsd(opts.pCost, 2),
      avg_cost_per_session: roundUsd(opts.pCost / Math.max(1, sessions.length), 2),
      avg_tokens_per_session: Math.round(opts.pTok / Math.max(1, sessions.length)),
      staged_count: Number(proj.staged_count || (wsProj && wsProj.staged_count) || 0),
      in_work_handoff_count: Number(proj.in_work_handoff_count || (wsProj && wsProj.in_work_count) || 0),
      completed_count: Number((wsProj && wsProj.completed_count) || 0),
      staged_handoffs: proj.staged_handoffs || (wsProj && wsProj.staged_handoffs) || [],
      active_days: opts.activeDays,
      context_budget: {
        max_session_steps: maxSteps,
        rollover_seam_steps: 700,
        budget_pct: Math.min(100, Number(((maxSteps / 700) * 100).toFixed(1))),
        top_session_id: maxSess.conversation_id || "",
        top_session_title: maxSess.title || "",
        running_count: runCnt,
        idle_count: Math.max(0, sessions.length - runCnt),
      },
      code_health: {
        available: true,
        workspace_path: `/workspace/${proj.project_name}`,
        target_lines: 500,
        ceiling_lines: 650,
        total_modules: ch.total_modules || 24,
        compliant_500: ch.compliant_500 || 24,
        warning_501_650: ch.warning_501_650 || 0,
        violations_over_650: ch.violations_over_650 || 0,
        total_lines: ch.total_lines || 6400,
        modules: (ch.modules || []).slice(0, 14),
      },
    };
  }

  function synthesizeWsFallbackProject(projectId, wsProj, otherProjects) {
    if (!wsProj) return null;
    const ovfStepsArr = Array.isArray(otherProjects && otherProjects.steps_series) ? otherProjects.steps_series : [];
    const ovfTokArr = Array.isArray(otherProjects && otherProjects.tokens_series) ? otherProjects.tokens_series : [];
    const ovfSess = (otherProjects && Array.isArray(otherProjects.sessions)) ? otherProjects.sessions : [];
    const wsIds = new Set((wsProj.sessions || []).map((s) => s.conversation_id));
    const matched = ovfSess.filter((s) => s && wsIds.has(s.conversation_id));
    const ovfTotal = Math.max(1, Number((otherProjects && otherProjects.window_steps) || ovfStepsArr.reduce((a, b) => a + b, 0) || 1));
    const mSteps = matched.reduce((a, s) => a + Number(s.window_steps || 0), 0);
    const mTok = matched.reduce((a, s) => a + Number(s.window_tokens || 0), 0);
    const mCost = matched.reduce((a, s) => a + Number(s.window_cost_usd || 0), 0);
    const mRatio = mSteps > 0 ? mSteps / ovfTotal : 0;
    return {
      project_id: projectId,
      project_name: wsProj.project_name || projectId,
      sessions: matched.length ? matched : (wsProj.sessions || []).map((s) => Object.assign({}, s, { window_steps: 0, window_tokens: 0, window_cost_usd: 0 })),
      color_slot: 10, window_steps: mSteps, window_tokens: mTok, window_cost_usd: roundUsd(mCost, 2),
      active_sessions_count: matched.filter((s) => Number((s && s.window_steps) || 0) > 0).length,
      steps_series: mSteps > 0 && ovfStepsArr.length ? ovfStepsArr.map((v) => Math.round(Number(v || 0) * mRatio)) : [],
      tokens_series: mSteps > 0 && ovfTokArr.length ? ovfTokArr.map((v) => Math.round(Number(v || 0) * mRatio)) : [],
      is_idle: mSteps <= 0,
    };
  }

  function resolveScopedProject(projectId, snap, h, wsProj) {
    const allProjs = hierarchyProjects(h);
    const direct = allProjs.find((p) => p && p.project_id === projectId && !p.is_rollup);
    if (direct) return direct;
    if (h.other_projects && Array.isArray(h.other_projects.sessions)) {
      const mSess = h.other_projects.sessions.filter((s) => s && s.project_id === projectId);
      if (mSess.length) {
        return {
          project_id: projectId, project_name: mSess[0].project_name || (wsProj && wsProj.project_name) || projectId,
          sessions: mSess, color_slot: 10,
          window_steps: mSess.reduce((a, s) => a + Number(s.window_steps || 0), 0),
          window_tokens: mSess.reduce((a, s) => a + Number(s.window_tokens || 0), 0),
          window_cost_usd: roundUsd(mSess.reduce((a, s) => a + Number(s.window_cost_usd || 0), 0), 2),
          active_sessions_count: mSess.filter((s) => Number((s && s.window_steps) || 0) > 0).length,
        };
      }
    }
    const fallbackProj = wsProj || Object.values((snap && snap.bundles) || {}).reduce(
      (hit, b) => hit || hierarchyProjects((b && b.project_hierarchy) || {}).find((p) => p && p.project_id === projectId && !p.is_rollup),
      null
    );
    return synthesizeWsFallbackProject(projectId, fallbackProj, h.other_projects) || {
      project_id: projectId,
      project_name: (fallbackProj && fallbackProj.project_name) || projectId,
      sessions: [],
      color_slot: 10,
      window_steps: 0,
      window_tokens: 0,
      active_sessions_count: 0,
      is_idle: true,
    };
  }

  function getScopedDemoStatsBundle(timeframe, mode, offset, projectId) {
    const raw = getDemoStatsBundle(timeframe, mode, offset);
    if (!raw) return raw;
    enrichHierarchy(raw.project_hierarchy);
    if (!projectId) return raw;
    const snap = window.DEMO_SNAPSHOT || null;
    const wsProj = ((snap && snap.workspace_tree && snap.workspace_tree.projects) || []).find(
      (p) => p && p.project_id === projectId
    );
    const h = raw.project_hierarchy || {};
    const proj = resolveScopedProject(projectId, snap, h, wsProj);
    const dates = h.dates || (raw.velocity_series && raw.velocity_series.dates) || [];
    const pStepsArr = Array.isArray(proj.steps_series) && proj.steps_series.length ? proj.steps_series : dates.map(() => 0);
    const pTokArr = Array.isArray(proj.tokens_series) && proj.tokens_series.length ? proj.tokens_series : dates.map(() => 0);
    const sessions = proj.sessions || [];
    const fleetSteps = Number((raw.kpis && (raw.kpis.window_steps || raw.kpis.period_steps)) || 1);
    const pSteps = Number(proj.window_steps != null ? proj.window_steps : pStepsArr.reduce((a, b) => a + b, 0));
    const pTok = Number(proj.window_tokens != null ? proj.window_tokens : pTokArr.reduce((a, b) => a + b, 0));
    const fleetSeries = (raw.velocity_series && raw.velocity_series.values) || [];
    const shareRatio = fleetSteps > 0 ? pSteps / fleetSteps : 0;
    const pCost = proj.window_cost_usd != null ? Number(proj.window_cost_usd) : roundUsd(Number((raw.kpis && raw.kpis.window_cost_usd) || 0) * shareRatio, 2);
    const fleetCost = Number((raw.kpis && raw.kpis.window_cost_usd) || 0);
    const costRatio = fleetCost > 0 ? pCost / fleetCost : shareRatio;
    const pForeUsd = roundUsd(Number((raw.kpis && raw.kpis.forecast_cost_usd) || fleetCost) * costRatio, 2);
    const hm = scopeHeatmapForProject(raw, dates, pStepsArr, pTokArr, sessions.length, pCost, pTok);
    const costPerTok = pTok > 0 ? pCost / pTok : 0;
    if (raw.velocity_series) {
      const vLen = (raw.velocity_series.dates || []).length;
      raw.velocity_series.values = pStepsArr.slice(0, vLen);
      raw.velocity_series.token_values = pTokArr.slice(0, vLen);
      raw.velocity_series.cost_values = pTokArr.slice(0, vLen).map((tk) => roundUsd(Number(tk || 0) * costPerTok, 4));
    }
    if (raw.model_series) {
      raw.model_series.layers = scaleLayerMap(dates, fleetSeries, pStepsArr, raw.model_series.layers);
      raw.model_series.token_layers = scaleLayerMap(dates, fleetSeries, pStepsArr, raw.model_series.token_layers);
      if (raw.model_series.cost_layers) raw.model_series.cost_layers = scaleLayerMap(dates, fleetSeries, pStepsArr, raw.model_series.cost_layers, 4);
    }
    if (Array.isArray(raw.model_usage_vs_target)) {
      raw.model_usage_vs_target = raw.model_usage_vs_target.map((m) => Object.assign({}, m, {
        calls: Math.round((m.calls || 0) * shareRatio),
        actual_calls: Math.round((m.actual_calls != null ? m.actual_calls : (m.calls || 0)) * shareRatio),
        tokens: Math.round((m.tokens || 0) * shareRatio), est_tokens: Math.round((m.est_tokens != null ? m.est_tokens : (m.tokens || 0)) * shareRatio),
        est_cost_usd: roundUsd((m.est_cost_usd || 0) * costRatio, 2), forecast_cost_usd: roundUsd((m.forecast_cost_usd || 0) * costRatio, 2),
        share_pct: Number((m.share_pct || 0).toFixed(1)),
      }));
    }
    const subRuns = sessions.reduce((acc, s) => acc + Number(s.subagent_runs || 0), 0);
    if (subRuns <= 0) {
      if (raw.subagent_series) { raw.subagent_series.keys = []; raw.subagent_series.layers = {}; raw.subagent_series.token_layers = {}; raw.subagent_series.cost_layers = {}; }
      raw.subagent_list = [];
    } else {
      const subRatio = subRuns / Math.max(1, Number((raw.kpis && raw.kpis.total_subagents_spawned) || subRuns));
      if (raw.subagent_series) {
        raw.subagent_series.layers = scaleLayerMap(dates, fleetSeries, pStepsArr, raw.subagent_series.layers);
        raw.subagent_series.token_layers = scaleLayerMap(dates, fleetSeries, pStepsArr, raw.subagent_series.token_layers);
        if (raw.subagent_series.cost_layers) raw.subagent_series.cost_layers = scaleLayerMap(dates, fleetSeries, pStepsArr, raw.subagent_series.cost_layers, 4);
      }
      if (Array.isArray(raw.subagent_list)) {
        raw.subagent_list = raw.subagent_list.map((r) => Object.assign({}, r, {
          runs: Math.max(0, Math.round((r.runs || 0) * subRatio)), tokens: Math.max(0, Math.round((r.tokens || 0) * subRatio)),
          est_cost_usd: roundUsd((r.est_cost_usd || 0) * subRatio, 2),
        })).filter((r) => r.runs > 0);
      }
    }
    raw.project_sessions_series = buildScopedProjectSeries(proj, dates);
    const avgCostDay = roundUsd(pCost / Math.max(1, hm.activeDays), 2);
    raw.kpis = Object.assign({}, raw.kpis, {
      total_conversations: sessions.length, total_subagents_spawned: subRuns, window_steps: pSteps, period_steps: pSteps,
      window_tool_calls: Math.round(Number((raw.kpis && raw.kpis.window_tool_calls) || 0) * shareRatio),
      window_tokens: pTok, window_cost_usd: pCost, forecast_cost_usd: pForeUsd, cost_per_day_usd: avgCostDay, active_days: hm.activeDays,
      avg_daily_steps: Number((pSteps / Math.max(1, hm.activeDays)).toFixed(1)), tok_per_day: Math.round(pTok / Math.max(1, hm.activeDays)), peak_day: hm.peakDay,
    });
    if (raw.billing_comparison) {
      const bc = raw.billing_comparison;
      raw.billing_comparison = Object.assign({}, bc, {
        historical_usd: pCost, forecast_usd: pForeUsd, avg_usd_per_active_day: avgCostDay, active_days: Math.max(1, hm.activeDays),
        forecast_delta_usd: roundUsd(pForeUsd - pCost, 2), forecast_delta_pct: pCost > 0 ? Number((((pForeUsd - pCost) / pCost) * 100).toFixed(1)) : 0,
        tiers: (bc.tiers || []).map((t) => { const sw = Number(t.window_cost_usd || t.monthly_usd || 0); return Object.assign({}, t, { net_savings_usd: roundUsd(pCost - sw, 2), value_multiplier: sw > 0 ? roundUsd(pCost / sw, 2) : 0 }); }),
      });
    }
    raw.hourly_whiskers = null;
    raw.project_scope = buildDemoProjectScope(proj, wsProj, snap, { fleetSteps, pTok, pCost, shareRatio, activeDays: hm.activeDays });
    return raw;
  }

  V9.DemoAdapter = {
    getDemoStatsBundle: getScopedDemoStatsBundle,
    getDemoBounds,
    isPresetAvailable,
    getDemoWorkspaceTree,
    getDemoSessionBucket,
    getDemoDocFile,
  };
})();
