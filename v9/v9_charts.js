/* SPDX-License-Identifier: Apache-2.0 */
/* AGY-Nexus /web/v9 — 1-Col Daily ECharts Spine Stack, >=1100px Secondary Pair & Full-Width Wire */
(() => {
  const V9 = window.AgyV9;
  const chartMap = new Map();
  const resizeMap = new Map();
  const pendingMap = new Map();
  const PRIMARY_CHART_IDS = ["v9ModelChart", "v9SubagentChart", "v9ProjectChart"];
  const OPTIONAL_CHART_IDS = ["v9CadenceChart", "v9WireScatterWrap"];
  let layoutSyncRaf = 0;
  let syncingLayout = false;

  function isHostMeasurable(host) {
    return Boolean(host && host.clientWidth > 0 && host.clientHeight > 0);
  }

  function clearWatcher(map, id) {
    const unsub = map.get(id);
    if (typeof unsub === "function") unsub();
    map.delete(id);
  }

  function disposeChartEntry(id) {
    const existing = chartMap.get(id);
    if (existing && !existing.isDisposed()) existing.dispose();
    chartMap.delete(id);
    clearWatcher(resizeMap, id);
  }

  function measureSizeDelta(host, chart) {
    const w = Math.round(host.clientWidth || 0);
    const h = Math.round(host.clientHeight || 0);
    const cw = chart && chart.getWidth ? Math.round(chart.getWidth() || 0) : 0;
    const ch = chart && chart.getHeight ? Math.round(chart.getHeight() || 0) : 0;
    return { w, h, mismatch: cw <= 0 || ch <= 0 || Math.abs(cw - w) > 1 || Math.abs(ch - h) > 1 };
  }

  function ensureChartSize(host, chart) {
    if (!chart || chart.isDisposed() || !isHostMeasurable(host)) return;
    const { w, h, mismatch } = measureSizeDelta(host, chart);
    if (mismatch) chart.resize({ width: w, height: h });
  }

  function scheduleLayoutSync() {
    if (layoutSyncRaf) return;
    layoutSyncRaf = requestAnimationFrame(() => {
      layoutSyncRaf = 0;
      if (V9.state.bundle) syncChartsOnLayout(V9.state.bundle);
    });
  }

  function bindHostWatcher(map, id, host, handler) {
    clearWatcher(map, id);
    if (!host) return;
    const ro = typeof window.ResizeObserver === "function" ? new window.ResizeObserver(handler) : null;
    if (ro) ro.observe(host);
    window.addEventListener("resize", handler);
    map.set(id, () => {
      if (ro) ro.disconnect();
      window.removeEventListener("resize", handler);
    });
  }

  function watchUntilVisible(id, host) {
    bindHostWatcher(pendingMap, id, host, () => {
      if (host.isConnected === false || !isHostMeasurable(host)) return;
      clearWatcher(pendingMap, id);
      scheduleLayoutSync();
    });
  }

  function attachResizeWatcher(id, host, chart) {
    bindHostWatcher(resizeMap, id, host, () => {
      if (!chart || chart.isDisposed() || host.isConnected === false || !isHostMeasurable(host)) return;
      const { w, h, mismatch } = measureSizeDelta(host, chart);
      if (mismatch) {
        chart.resize({ width: w, height: h });
        if (V9.state.bundle) scheduleRealign();
      }
    });
  }

  function getOrInitChart(id) {
    const host = document.getElementById(id);
    if (!host || typeof window.echarts === "undefined") return null;
    if (!isHostMeasurable(host)) {
      disposeChartEntry(id);
      watchUntilVisible(id, host);
      return null;
    }
    clearWatcher(pendingMap, id);
    let chart = chartMap.get(id);
    if (chart && chart.getDom && chart.getDom() === host && !chart.isDisposed()) {
      ensureChartSize(host, chart);
      if (!resizeMap.has(id)) attachResizeWatcher(id, host, chart);
      return chart;
    }
    disposeChartEntry(id);
    chart = window.echarts.init(host, null, { renderer: "svg" });
    chartMap.set(id, chart);
    ensureChartSize(host, chart);
    attachResizeWatcher(id, host, chart);
    return chart;
  }

  function themeSpec() {
    return {
      text: V9.cssVar("--text-primary", "#0F172A"),
      sub: V9.cssVar("--text-secondary", "#334155"),
      muted: V9.cssVar("--text-muted", "#475569"),
      grid: V9.cssVar("--border-hairline", "#E2E8F0"),
      spine: V9.cssVar("--border-strong", "#CBD5E1"),
      surface: V9.cssVar("--bg-surface", "#FFFFFF"),
      elev: V9.cssVar("--bg-elevated", "#F8FAFC"),
      danger: V9.cssVar("--status-danger", "#B91C1C"),
    };
  }

  function isoWeekMonday(dayIso) {
    const parts = String(dayIso || "").split("-").map(Number);
    if (parts.length !== 3 || !Number.isFinite(parts[0])) return dayIso;
    const dt = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2]));
    const shift = (dt.getUTCDay() + 6) % 7;
    dt.setUTCDate(dt.getUTCDate() - shift);
    return dt.toISOString().slice(0, 10);
  }

  function binSeriesForDisplay(rawDates, layersObj, keys) {
    const dates = Array.isArray(rawDates) ? rawDates : [];
    if (!dates.length) return { dates: [], layers: layersObj || {}, binNote: "" };
    const daySet = new Set();
    let hasHours = false;
    dates.forEach((d) => {
      const s = String(d || "");
      if (/\s\d{2}:00$/.test(s)) hasHours = true;
      daySet.add(s.slice(0, 10));
    });
    if (daySet.size <= 3 && hasHours) {
      return { dates, layers: layersObj || {}, binNote: "1h" };
    }
    const useWeeks = daySet.size > 92;
    const bucketIdx = new Map();
    const outDates = [];
    const outLayers = {};
    (keys || []).forEach((k) => { outLayers[k] = []; });

    dates.forEach((d, idx) => {
      const dayIso = String(d || "").slice(0, 10);
      const bKey = useWeeks ? isoWeekMonday(dayIso) : dayIso;
      let bi = bucketIdx.get(bKey);
      if (bi === undefined) {
        bi = outDates.length;
        bucketIdx.set(bKey, bi);
        outDates.push(bKey);
        (keys || []).forEach((k) => outLayers[k].push(0));
      }
      (keys || []).forEach((k) => {
        const arr = layersObj && layersObj[k];
        if (Array.isArray(arr)) outLayers[k][bi] += Number(arr[idx] || 0);
      });
    });
    return { dates: outDates, layers: outLayers, binNote: useWeeks ? "weekly" : "daily" };
  }

  function formatShortDateLabel(raw) {
    const s = String(raw || "");
    if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(s)) return s.slice(5, 13);
    if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s.slice(5);
    return s;
  }

  function buildStackedSeriesList(keys, layersObj, labelsMap, colorsMap, soloKey) {
    const activeKeys = soloKey ? keys.filter((k) => k === soloKey) : keys;
    return activeKeys.map((k, idx) => ({
      name: labelsMap[k] || k,
      type: "bar",
      stack: "total",
      large: true,
      barMaxWidth: 28,
      emphasis: { focus: "series" },
      itemStyle: { color: colorsMap[k] || V9.getSeriesColor(idx), borderRadius: [1, 1, 0, 0] },
      data: Array.isArray(layersObj[k]) ? layersObj[k] : [],
    }));
  }

  function makeStackedBarOption(dates, seriesList, unitLabel, t, widthPx) {
    const formatted = dates.map(formatShortDateLabel);
    const axisFont = V9.cssVar("--font-mono", "monospace");
    const isCost = unitLabel === "USD";
    const fmtVal = (v) => (isCost ? V9.fmtUsd(v) : V9.fmtNum(v));
    return {
      animation: false,
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        renderMode: "richText",
        axisPointer: { type: "shadow" },
        confine: true,
        backgroundColor: t.elev,
        borderColor: t.spine,
        borderWidth: 1,
        valueFormatter: fmtVal,
        textStyle: { color: t.text, fontSize: 12, fontFamily: axisFont },
      },
      legend: { show: false },
      grid: { left: 52, right: 16, top: 32, bottom: 28, containLabel: false },
      xAxis: {
        type: "category",
        data: formatted,
        axisLine: { lineStyle: { color: t.spine } },
        axisTick: { show: false },
        axisLabel: {
          color: t.muted,
          fontSize: 11,
          fontFamily: axisFont,
          hideOverlap: true,
          interval: widthPx < 440 ? Math.max(1, Math.floor(formatted.length / 4)) : "auto",
        },
      },
      yAxis: {
        type: "value",
        name: unitLabel,
        nameLocation: "end",
        nameGap: 12,
        nameTextStyle: { color: t.muted, fontSize: 11, fontFamily: axisFont },
        splitNumber: 4,
        axisLine: { show: false },
        axisLabel: { color: t.muted, fontSize: 11, fontFamily: axisFont, margin: 8, formatter: fmtVal },
        splitLine: { lineStyle: { color: t.grid, type: "dashed" } },
      },
      series: seriesList,
    };
  }

  function buildPrimaryDailyOptions(b, metric, t, fullW) {
    const useCost = metric === "cost";
    const useTok = metric === "tokens";
    const unit = useCost ? "USD" : (useTok ? "tokens" : "steps");

    const mSeries = b.model_series || {};
    const mKeys = mSeries.keys || [];
    const mRawLayers = useCost
      ? (mSeries.cost_layers || mSeries.token_layers || mSeries.layers || {})
      : (useTok ? (mSeries.token_layers || mSeries.layers || {}) : (mSeries.layers || {}));
    const mBinned = binSeriesForDisplay(mSeries.dates || [], mRawLayers, mKeys);
    const mLabels = {};
    const mColors = {};
    mKeys.forEach((k, idx) => {
      const meta = (b.model_usage_vs_target || []).find((m) => m.model_key === k);
      mLabels[k] = meta ? meta.label : k;
      mColors[k] = V9.getSeriesColor(idx);
    });
    if (V9.state.soloModel && !mKeys.includes(V9.state.soloModel)) V9.state.soloModel = "";
    const optModel = makeStackedBarOption(mBinned.dates, buildStackedSeriesList(mKeys, mBinned.layers, mLabels, mColors, V9.state.soloModel), unit, t, fullW);
    optModel.yUnit = `model_${unit}`;

    const sSeries = b.subagent_series || {};
    const sKeys = sSeries.keys || [];
    const sRawLayers = useCost
      ? (sSeries.cost_layers || sSeries.token_layers || sSeries.layers || {})
      : (useTok ? (sSeries.token_layers || sSeries.layers || {}) : (sSeries.layers || {}));
    const sBinned = binSeriesForDisplay(sSeries.dates || mSeries.dates || [], sRawLayers, sKeys);
    const sColors = {};
    sKeys.forEach((k, idx) => { sColors[k] = V9.getSeriesColor(idx); });
    if (V9.state.soloSubagent && !sKeys.includes(V9.state.soloSubagent)) V9.state.soloSubagent = "";
    const optSub = makeStackedBarOption(sBinned.dates, buildStackedSeriesList(sKeys, sBinned.layers, {}, sColors, V9.state.soloSubagent), unit, t, fullW);
    optSub.yUnit = `subagent_${unit}`;

    let optProj;
    if (b.project_scope && b.project_sessions_series && V9.ProjectView && V9.ProjectView.buildProjectSessionsChartOption) {
      optProj = V9.ProjectView.buildProjectSessionsChartOption(b, metric, t, fullW, {
        makeStackedBarOption,
        binSeriesForDisplay,
        buildStackedSeriesList,
      });
    } else {
      const pHier = b.project_hierarchy || {};
      const projs = pHier.top_projects || [];
      const pKeys = projs.map((p) => p.project_id);
      const pLabels = {};
      const pColors = {};
      const pRawLayers = {};
      projs.forEach((p, idx) => {
        pLabels[p.project_id] = p.project_name;
        pColors[p.project_id] = V9.getSeriesColor(p.color_slot != null ? p.color_slot : idx);
        const arr = useCost ? (p.cost_series || p.tokens_series) : (useTok ? p.tokens_series : p.steps_series);
        if (Array.isArray(arr)) pRawLayers[p.project_id] = arr;
      });
      const pBinned = binSeriesForDisplay(pHier.dates || mSeries.dates || [], pRawLayers, pKeys);
      optProj = makeStackedBarOption(pBinned.dates, buildStackedSeriesList(pKeys, pBinned.layers, pLabels, pColors, ""), unit, t, fullW);
      optProj.yUnit = `project_${unit}`;
    }

    return [optModel, optSub, optProj];
  }

  function buildWireScatterOption(b, t, cardW) {
    const calls = (b.wire_telemetry && Array.isArray(b.wire_telemetry.recent_calls)) ? b.wire_telemetry.recent_calls : [];
    if (calls.length === 0) return { warmupCount: 0, opt: null };
    const narrow = Number(cardW || 600) < 480;
    const axisFont = V9.cssVar("--font-mono", "monospace");
    const pts = calls.map((c) => ({
      value: [Number(c.duration_ms || 0), Number(c.kb || 0)],
      tool: c.tool || c.rpc || "rpc",
      product: c.product || "",
      itemStyle: { color: c.under_20kb_budget === false ? t.danger : V9.getSeriesColor(0) },
    }));
    const opt = {
      animation: false,
      independentXSpan: true,
      yUnit: "wire_kb",
      backgroundColor: "transparent",
      tooltip: {
        trigger: "item", confine: true, backgroundColor: t.elev, borderColor: t.spine, textStyle: { color: t.text, fontSize: 12 },
        formatter: (p) => `${V9.escHtml(p.data.tool)}<br>${p.data.value[1].toFixed(2)} KB · ${Math.round(p.data.value[0])} ms`,
      },
      grid: { left: narrow ? 48 : 54, right: narrow ? 22 : 20, top: 32, bottom: 44, containLabel: false },
      xAxis: {
        type: "value", name: "latency (ms)", nameLocation: "middle", nameGap: 24,
        min: 0,
        splitNumber: narrow ? 3 : 5,
        max: (v) => Math.max(100, Math.ceil(v.max * 1.1)),
        nameTextStyle: { color: t.muted, fontSize: 11, fontFamily: axisFont },
        axisLine: { lineStyle: { color: t.spine } },
        axisLabel: { color: t.muted, fontSize: narrow ? 10 : 11, fontFamily: axisFont, hideOverlap: true },
        splitLine: { show: false },
      },
      yAxis: {
        type: "value", name: "KB", nameGap: 12, max: (v) => Math.max(25, Math.ceil(v.max * 1.18)),
        nameTextStyle: { color: t.muted, fontSize: 11, fontFamily: axisFont },
        axisLine: { show: false },
        axisLabel: { color: t.muted, fontSize: 11, fontFamily: axisFont, margin: 8, hideOverlap: true },
        splitLine: { lineStyle: { color: t.grid, type: "dashed" } },
      },
      series: [{
        type: "scatter", symbolSize: 9, data: pts,
        markLine: {
          silent: true, symbol: "none",
          lineStyle: { color: t.danger, type: "dashed", width: 1.4 },
          data: [{
            yAxis: 20,
            label: {
              formatter: "20 KB cap", position: "insideEndTop", distance: 6, color: t.danger, fontSize: 11, fontWeight: 600,
              backgroundColor: t.surface, borderColor: t.danger, borderWidth: 1, padding: [2, 6], borderRadius: 3,
              textBorderColor: t.surface, textBorderWidth: 3,
            },
          }],
        },
      }],
    };
    return { warmupCount: calls.length, opt };
  }

  let alignTimer = null;
  function scheduleRealign() {
    clearTimeout(alignTimer);
    alignTimer = setTimeout(() => {
      if (!V9.state.bundle) return;
      if (V9.state.surfaceView && V9.state.surfaceView !== "analytics") return;
      renderAllCharts(V9.state.bundle);
    }, 60);
  }

  function syncSecondaryAlignmentDom(isTwoUp) {
    const pairEl = document.getElementById("v9SecondaryPair");
    const cadCard = document.getElementById("v9CadenceCard");
    const billCard = document.getElementById("v9BillingCard");
    if (isTwoUp) {
      pairEl?.setAttribute("data-plot-align", "secondary-row");
      cadCard?.removeAttribute("data-plot-align");
      billCard?.removeAttribute("data-plot-align");
    } else {
      pairEl?.removeAttribute("data-plot-align");
      cadCard?.setAttribute("data-plot-align", "cadence-solo");
      billCard?.setAttribute("data-plot-align", "eff-solo");
    }
  }

  function disposeOrRenderHost(hostId, opt, emptyMsg) {
    const host = document.getElementById(hostId);
    if (!host) return;
    if (!opt) {
      disposeChartEntry(hostId);
      clearWatcher(pendingMap, hostId);
      host.innerHTML = `<div class="v9-warmup-box">${V9.escHtml(emptyMsg)}</div>`;
      return;
    }
    if (host.querySelector(".v9-warmup-box")) host.innerHTML = "";
    const ch = getOrInitChart(hostId);
    if (ch) {
      if (isHostMeasurable(host)) ensureChartSize(host, ch);
      ch.setOption(opt, true);
    }
  }

  function highlightSeries(chartId, seriesName, on) {
    const ch = chartMap.get(chartId);
    if (!ch || ch.isDisposed() || !seriesName) return;
    ch.dispatchAction({ type: on ? "highlight" : "downplay", seriesName });
  }

  function renderAllCharts(b) {
    if (!b) return;
    const t = themeSpec();
    const host1 = document.getElementById("v9ModelChart");
    const cadHost = document.getElementById("v9CadenceChart");
    const fullW = Math.max(280, Math.round((host1 && host1.clientWidth) || (window.innerWidth - 48)));
    const isTwoUp = window.innerWidth >= 1100;
    const cadW = Math.max(260, Math.round((cadHost && cadHost.clientWidth) || (isTwoUp ? fullW / 2 : fullW)));

    const [optModel, optSub, optProj] = buildPrimaryDailyOptions(b, V9.state.metric, t, fullW);
    if (window.QuietEChartsDefaults && typeof window.QuietEChartsDefaults.alignSharedAxes === "function") {
      window.QuietEChartsDefaults.alignSharedAxes([optModel, optSub, optProj], { containerWidth: window.innerWidth });
    }

    const cadPkg = V9.Billing ? V9.Billing.buildCadenceWhiskerOption(b, V9.state.metric, t, cadW) : { opt: null, subNote: "", footNote: "" };
    syncSecondaryAlignmentDom(isTwoUp);

    const wirePkg = buildWireScatterOption(b, t, fullW);
    [
      ["v9ModelChart", optModel],
      ["v9SubagentChart", optSub],
      ["v9ProjectChart", optProj],
    ].forEach(([id, opt]) => {
      const host = document.getElementById(id);
      const ch = getOrInitChart(id);
      if (ch) {
        if (isHostMeasurable(host)) ensureChartSize(host, ch);
        ch.setOption(opt, true);
      }
    });
    disposeOrRenderHost("v9CadenceChart", cadPkg.opt, "Hourly activity breakdown unavailable");

    const cadSub = document.getElementById("v9CadenceSub");
    const cadFoot = document.getElementById("v9CadenceFoot");
    if (cadSub) cadSub.textContent = cadPkg.subNote;
    if (cadFoot) cadFoot.textContent = cadPkg.footNote;

    disposeOrRenderHost("v9WireScatterWrap", wirePkg.opt, "Warming up — 0 samples collected");
  }

  function hostNeedsSync(id, optional) {
    const host = document.getElementById(id);
    if (!isHostMeasurable(host)) return false;
    if (optional && host.querySelector(".v9-warmup-box") && !pendingMap.has(id)) return false;
    const ch = chartMap.get(id);
    if (!ch || ch.isDisposed() || (ch.getDom && ch.getDom() !== host)) return true;
    return measureSizeDelta(host, ch).mismatch;
  }

  function syncChartsOnLayout(b) {
    if (!b || (V9.state.surfaceView && V9.state.surfaceView !== "analytics")) return;
    if (syncingLayout) return;
    if (layoutSyncRaf) { cancelAnimationFrame(layoutSyncRaf); layoutSyncRaf = 0; }
    const needsSync = PRIMARY_CHART_IDS.some((id) => hostNeedsSync(id, false))
      || OPTIONAL_CHART_IDS.some((id) => hostNeedsSync(id, true));
    if (!needsSync) return;
    try {
      syncingLayout = true;
      renderAllCharts(b);
    } finally {
      syncingLayout = false;
    }
  }

  function disposeAll() {
    clearTimeout(alignTimer);
    if (layoutSyncRaf) { cancelAnimationFrame(layoutSyncRaf); layoutSyncRaf = 0; }
    [pendingMap, resizeMap].forEach((m) => { m.forEach((fn) => { if (typeof fn === "function") fn(); }); m.clear(); });
    chartMap.forEach((c) => { if (c && !c.isDisposed()) c.dispose(); });
    chartMap.clear();
  }

  V9.Charts = { renderAllCharts, syncChartsOnLayout, disposeAll, scheduleRealign, highlightSeries };
})();
