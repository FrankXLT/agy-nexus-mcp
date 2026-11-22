/* SPDX-License-Identifier: Apache-2.0 */
/* Quiet Evidence — Runtime Apache ECharts (SVG) + 5-Tab Ecosystem Viewer */
(function (global) {
  'use strict';

  var AUTO_VIEWS = {
    'v06-ai-drift-and-lineage-ide': true, 'v10-civic-capital-budget-deck': true, 'v11-treasury-stress-test-solver': true,
    'v12-stem-interactive-lab': true, 'v13-propulsion-archival-monograph': true, 'v18-home-assistant-companion-console': true,
    'v19-product-roadmap-and-triage': true, 'v20-student-capstone-lab-report': true, 'v21-field-anomaly-escalation-tsn': true,
  };
  var PALETTE_TOKENS = ['--accent-focal', '--status-warn', '--text-secondary', '--status-danger'];
  var ROOT_LISTENERS = new WeakSet();
  var RESIZE_OBSERVERS = new WeakMap();
  var HOST_RESIZE_CLEANUPS = new WeakMap();
  var COPY_TIMERS = new WeakMap();

  function getGlobal(name) {
    if (global[name]) return global[name];
    try {
      if (global.parent && global.parent !== global && global.parent[name]) return global.parent[name];
    } catch (_err) {}
    return null;
  }
  function getLib() { return getGlobal('echarts'); }
  function getLayers() { return getGlobal('QuietEChartsLayers'); }

  function cssVar(doc, token, fallback) {
    try {
      var val = getComputedStyle(doc.documentElement).getPropertyValue(token).trim();
      if (val) return val;
    } catch (_err) {}
    return fallback;
  }

  function readTokens(doc) {
    return {
      textPrimary: cssVar(doc, '--text-primary', '#0F172A'),
      textSecondary: cssVar(doc, '--text-secondary', '#475569'),
      borderHairline: cssVar(doc, '--border-hairline', '#E2E8F0'),
      borderStrong: cssVar(doc, '--border-strong', '#94A3B8'),
      bgSurface: cssVar(doc, '--bg-surface', '#FFFFFF'),
      bgElevated: cssVar(doc, '--bg-elevated', '#F8FAFC'),
      accentFocal: cssVar(doc, '--accent-focal', '#0369A1'),
      statusOk: cssVar(doc, '--status-ok', '#15803D'),
      statusWarn: cssVar(doc, '--status-warn', '#B45309'),
      statusDanger: cssVar(doc, '--status-danger', '#B91C1C'),
    };
  }

  function fmtLinearTick(v) {
    if (!Number.isFinite(v)) return '';
    if (Math.abs(v) < 1e-12) return '0';
    return String(Number(v.toPrecision(6)));
  }

  function resolveSeriesColor(doc, seriesSpec, idx, tokens) {
    var rawTok = seriesSpec && (seriesSpec.color || seriesSpec.token) ? (seriesSpec.color || seriesSpec.token) : PALETTE_TOKENS[idx % PALETTE_TOKENS.length];
    if (rawTok.indexOf('var(') === 0) rawTok = rawTok.slice(4, -1).split(',')[0].trim();
    if (rawTok.indexOf('#') === 0) return rawTok;
    if (!(seriesSpec && seriesSpec.colorExplicit) && rawTok === '--accent-focal' && idx > 0) rawTok = PALETTE_TOKENS[idx % PALETTE_TOKENS.length];
    var fallback = tokens.accentFocal;
    if (rawTok === '--status-warn') fallback = tokens.statusWarn;
    else if (rawTok === '--status-danger') fallback = tokens.statusDanger;
    else if (rawTok === '--text-secondary') fallback = tokens.textSecondary;
    else if (rawTok === '--text-primary') fallback = tokens.textPrimary;
    return cssVar(doc, rawTok, fallback);
  }

  function mapSymbol(glyph) {
    if (glyph === 'square') return 'rect';
    if (glyph === 'diamond') return 'diamond';
    if (glyph === 'triangle') return 'triangle';
    return 'circle';
  }

  function makeWhiskerSeries(name, color, pts, opacity, preMapped) {
    var coords = preMapped ? pts : [];
    if (!preMapped) {
      for (var i = 0; i < pts.length; i += 1) {
        var p = pts[i];
        if (p[1] !== null && p[1] !== undefined && p[2] > 0) coords.push([p[0], p[1] - p[2], p[1] + p[2]]);
      }
    }
    if (!coords.length) return null;
    return {
      name: name + ' u',
      type: 'custom',
      silent: true,
      tooltip: { show: false },
      legendHoverLink: false,
      z: 3,
      renderItem: function (params, api) {
        var xv = api.value(0);
        var low = api.coord([xv, api.value(1)]);
        var high = api.coord([xv, api.value(2)]);
        if (!low || !high || !Number.isFinite(low[0]) || !Number.isFinite(low[1]) || !Number.isFinite(high[0]) || !Number.isFinite(high[1])) return null;
        var cs = params && params.coordSys;
        var yTop = cs ? cs.y : -1e9, yBot = cs ? (cs.y + cs.height) : 1e9;
        var yLo = Math.max(yTop, Math.min(yBot, low[1]));
        var yHi = Math.max(yTop, Math.min(yBot, high[1]));
        var ch = [
          { type: 'line', shape: { x1: low[0], y1: yLo, x2: high[0], y2: yHi }, style: { stroke: color, lineWidth: 1.35, opacity: opacity } },
        ];
        if (high[1] >= yTop - 1 && high[1] <= yBot + 1) ch.push({ type: 'line', shape: { x1: high[0] - 4, y1: yHi, x2: high[0] + 4, y2: yHi }, style: { stroke: color, lineWidth: 1.35, opacity: opacity } });
        if (low[1] >= yTop - 1 && low[1] <= yBot + 1) ch.push({ type: 'line', shape: { x1: low[0] - 4, y1: yLo, x2: low[0] + 4, y2: yLo }, style: { stroke: color, lineWidth: 1.35, opacity: opacity } });
        return { type: 'group', children: ch };
      },
      data: coords,
    };
  }

  function buildEnvelopes(doc, payload, t) {
    var items = [];
    (payload.envelopes || []).forEach(function (env) {
      if (typeof env.value !== 'number' || !Number.isFinite(env.value)) return;
      var col = cssVar(doc, env.token || '--status-warn', env.type === 'abort' ? t.statusDanger : t.statusWarn);
      items.push({
        name: env.label || String(env.value),
        yAxis: env.value,
        lineStyle: { color: col, type: env.type === 'abort' ? 'dashdot' : 'dashed', width: 1.4 },
        label: { formatter: env.label || String(env.value), position: 'insideEndTop', color: col, fontSize: 11, fontWeight: 600, backgroundColor: t.bgSurface, padding: [2, 5], borderRadius: 2 },
      });
    });
    return items;
  }

  function buildCartesianOption(doc, rawPayload, activeTerm) {
    var t = readTokens(doc);
    var layers = getLayers();
    var payload = (layers && layers.mapCartesianPayload) ? layers.mapCartesianPayload(rawPayload) : rawPayload;
    var xMeta = payload.x || {};
    var yMeta = payload.y || {};
    var series = [];
    var envData = buildEnvelopes(doc, payload, t);
    var showWhiskers = payload.rigor !== 'L1';

    (payload.series || []).forEach(function (sr, idx) {
      var col = resolveSeriesColor(doc, sr, idx, t);
      var dimmed = activeTerm && sr.term && sr.term !== activeTerm;
      var opacity = dimmed ? 0.22 : 1.0;
      if (sr.epistemic === 'analytical_model') {
        if (sr.corridor && layers) {
          var band = layers.makeCorridorSeries(sr, col, opacity, 0);
          if (band) series.push(band);
        }
        series.push({
          id: sr.id || 'model-' + idx,
          name: sr.name || 'Model',
          type: 'line',
          showSymbol: false,
          smooth: false,
          data: sr.data || [],
          lineStyle: { color: col, width: dimmed ? 1.5 : 2.1, type: sr.dashed ? 'dashed' : 'solid', opacity: opacity },
          itemStyle: { color: col, opacity: opacity },
          z: 2,
        });
      } else {
        var isConn = sr.connectPiecewise !== undefined ? !!sr.connectPiecewise : !!sr.connect;
        var ptsData = (sr.data || []).map(function (p) { return p.length >= 4 ? [p[0], p[1], p[2], p[3]] : [p[0], p[1]]; });
        var baseMeas = {
          id: sr.id || 'meas-' + idx,
          name: sr.name || 'Measurement',
          type: isConn ? 'line' : 'scatter',
          encode: { x: 0, y: 1 },
          symbol: mapSymbol(sr.symbol),
          symbolSize: isConn ? 6.5 : 7.5,
          data: ptsData,
          itemStyle: { color: col, opacity: opacity },
          z: 4,
        };
        if (isConn) {
          baseMeas.connectNulls = false;
          baseMeas.showSymbol = true;
          baseMeas.smooth = false;
          baseMeas.lineStyle = { color: col, width: dimmed ? 1.5 : 2.1, opacity: opacity };
        }
        series.push(baseMeas);
        if (showWhiskers) {
          var whisker = sr.whiskers ? makeWhiskerSeries(sr.name || 'meas', col, sr.whiskers, opacity, true) : makeWhiskerSeries(sr.name || 'meas', col, sr.data || [], opacity, false);
          if (whisker) series.push(whisker);
        }
      }
    });

    if (layers) series = series.concat(layers.makeSlopedEnvelopes(payload, t, cssVar, doc, 0));
    if (envData.length) {
      series.push({
        type: 'line', silent: true, legendHoverLink: false, tooltip: { show: false },
        symbol: 'none', lineStyle: { opacity: 0 }, itemStyle: { opacity: 0 }, data: [],
        markLine: { silent: true, symbol: ['none', 'none'], data: envData }, z: 5,
      });
    }
    var xAxisBase = {
      type: xMeta.log ? 'log' : 'value',
      min: (xMeta.log && xMeta.min <= 0) || !Number.isFinite(xMeta.min) ? undefined : xMeta.min,
      max: (xMeta.log && xMeta.max <= 0) || !Number.isFinite(xMeta.max) ? undefined : xMeta.max,
      interval: !xMeta.log && Number.isFinite(xMeta.interval) ? xMeta.interval : undefined,
      name: xMeta.name || 'x',
      nameLocation: 'middle',
      nameGap: 28,
      nameTextStyle: { color: t.textSecondary, fontSize: 11.5, fontWeight: 600 },
      axisLine: { onZero: false, lineStyle: { color: t.textSecondary } },
      axisLabel: { color: t.textSecondary, fontSize: 11, hideOverlap: true, formatter: (xMeta.logMapped && layers) ? layers.fmtLogDecade : (xMeta.log ? undefined : fmtLinearTick) },
      splitLine: { lineStyle: { color: t.borderHairline, type: 'dashed' } },
    };
    var totalScatterPts = (payload.series || []).reduce(function (acc, sr) {
      return (sr.epistemic !== 'analytical_model' && !sr.connectPiecewise) ? acc + (sr.data || []).length : acc;
    }, 0);
    var opt = {
      animation: false,
      backgroundColor: 'transparent',
      textStyle: { fontFamily: 'Inter, system-ui, sans-serif', color: t.textPrimary },
      tooltip: {
        trigger: totalScatterPts >= 20 ? 'item' : 'axis',
        renderMode: 'richText',
        confine: true,
        backgroundColor: t.bgElevated,
        borderColor: t.borderStrong,
        borderWidth: 1,
        textStyle: { color: t.textPrimary, fontSize: 12 },
        valueFormatter: yMeta.logMapped ? function (v) { return typeof v === 'number' && Number.isFinite(v) ? Math.pow(10, v).toExponential(2) : ''; } : undefined,
      },
      legend: { top: 2, left: 64, right: 16, itemWidth: 16, itemHeight: 8, textStyle: { color: t.textSecondary, fontSize: 11 }, data: (payload.series || []).map(function (s) { return s.name; }) },
      grid: { left: (yMeta.log || yMeta.logMapped) ? 72 : 66, right: 24, top: 44, bottom: 52, containLabel: true },
      xAxis: xAxisBase,
      yAxis: {
        type: yMeta.log ? 'log' : 'value',
        min: (yMeta.log && yMeta.min <= 0) || !Number.isFinite(yMeta.min) ? undefined : yMeta.min,
        max: (yMeta.log && yMeta.max <= 0) || !Number.isFinite(yMeta.max) ? undefined : yMeta.max,
        interval: !yMeta.log && Number.isFinite(yMeta.interval) ? yMeta.interval : undefined,
        name: yMeta.name || 'y',
        nameLocation: 'middle',
        nameGap: (yMeta.log || yMeta.logMapped) ? 52 : 44,
        nameTextStyle: { color: t.textSecondary, fontSize: 11.5, fontWeight: 600 },
        axisLine: { lineStyle: { color: t.textSecondary } },
        axisLabel: { color: t.textSecondary, fontSize: 11, hideOverlap: true, formatter: (yMeta.logMapped && layers) ? layers.fmtLogDecade : (yMeta.log ? undefined : fmtLinearTick) },
        splitLine: { lineStyle: { color: t.borderHairline, type: 'dashed' } },
      },
      series: series,
    };
    return (payload.residuals && layers) ? layers.attachResidualStrip(opt, payload, t, xAxisBase) : opt;
  }

  function shouldEnableECharts(doc, wrap) {
    var rootMed = (doc.documentElement.dataset.medium || '').toLowerCase();
    var wrapMed = (wrap.dataset.medium || '').toLowerCase();
    if (rootMed === 'm1' || wrapMed === 'm1') return false;
    if (doc.defaultView && doc.defaultView.matchMedia && doc.defaultView.matchMedia('print').matches) return false;
    if (wrap.dataset.echartsMode === 'svg') return false;
    if (wrap.dataset.echartsMode === 'echarts') return true;
    return !!AUTO_VIEWS[doc.documentElement.dataset.view || ''];
  }

  function disposeWrap(wrap, lib) {
    var unobserve = HOST_RESIZE_CLEANUPS.get(wrap);
    if (typeof unobserve === 'function') { unobserve(); HOST_RESIZE_CLEANUPS.delete(wrap); }
    var host = wrap.querySelector('.qe-echarts-host');
    if (host) {
      if (lib && typeof lib.getInstanceByDom === 'function') {
        var existing = lib.getInstanceByDom(host);
        if (existing) existing.dispose();
      }
      host.hidden = true;
    }
    delete wrap.dataset.qeMountKey;
    wrap.dataset.echartsActive = 'false';
  }

  function mountWrap(doc, wrap, lib) {
    var host = wrap.querySelector('.qe-echarts-host'), scroll = wrap.querySelector('.va-figure-scroll');
    if (!host || !scroll || !lib || !shouldEnableECharts(doc, wrap)) { disposeWrap(wrap, lib); return; }
    var payload;
    try { payload = JSON.parse(wrap.dataset.quietEcharts || ''); } catch (_err) { disposeWrap(wrap, lib); return; }
    host.hidden = false;
    var avail = Math.round((scroll.clientWidth || wrap.clientWidth || 640) - 8), w = avail > 0 ? avail : 300;
    var ss = getGlobal('QuietEChartsSankeyStrip'), defaults = getGlobal('QuietEChartsDefaults');
    var isSS = payload.kind === 'sankey' || payload.kind === 'strip_chart';
    var hasRes = !!(payload.residuals && Array.isArray(payload.residuals.points) && payload.residuals.points.length);
    var h = (isSS && ss && typeof ss.calcHeight === 'function') ? ss.calcHeight(payload, w)
      : (hasRes ? Math.round(w < 500 ? 335 : Math.min(410, Math.max(365, w * 0.54))) : Math.round(w < 500 ? 255 : Math.min(340, Math.max(255, w * 0.44))));
    var maxH = parseFloat((doc.defaultView || global).getComputedStyle(host).maxBlockSize);
    if (isFinite(maxH) && maxH > 120) h = Math.min(h, Math.round(maxH));
    var mKey = [doc.documentElement.dataset.theme || '', doc.documentElement.dataset.medium || '', wrap.dataset.activeTerm || '', wrap.dataset.echartsMode || '', w, h].join('|');
    var inst = lib.getInstanceByDom(host);
    host.style.width = '100%';
    host.style.height = h + 'px';
    if (inst && wrap.dataset.qeMountKey === mKey) {
      inst.resize({ width: w, height: h });
      wrap.dataset.echartsActive = 'true';
      if (defaults && typeof defaults.observeChartResize === 'function' && !HOST_RESIZE_CLEANUPS.has(wrap)) {
        HOST_RESIZE_CLEANUPS.set(wrap, defaults.observeChartResize(host, inst, { onResize: function () { mountWrap(doc, wrap, lib); } }));
      }
      return;
    }
    if (!inst) {
      var staleClean = HOST_RESIZE_CLEANUPS.get(wrap);
      if (typeof staleClean === 'function') { staleClean(); HOST_RESIZE_CLEANUPS.delete(wrap); }
      inst = lib.init(host, null, { renderer: 'svg', width: w, height: h });
    }
    var tok = readTokens(doc), layers = getLayers(), ext = getGlobal('QuietEChartsExt');
    var isExtKind = payload.kind === 'gantt' || payload.kind === 'heatmap' || payload.kind === 'dumbbell' || payload.kind === 'forest';
    var opt = isSS ? (ss ? ss.buildOption(doc, payload, tok, w) : null)
      : payload.kind === 'cyclical_whisker' ? (defaults && defaults.buildCyclicalWhiskerOption ? defaults.buildCyclicalWhiskerOption(payload.buckets, Object.assign({ tokens: tok, containerWidth: w }, payload.opts || {})) : null)
      : payload.kind === 'waterfall' ? (layers ? layers.buildWaterfallOption(doc, payload, tok, buildEnvelopes(doc, payload, tok)) : null)
      : payload.kind === 'stacked_bar' ? (layers ? layers.buildStackedBarOption(doc, payload, tok, buildEnvelopes(doc, payload, tok), resolveSeriesColor) : null)
      : isExtKind ? (ext ? ext.buildOption(doc, payload, tok, w) : null)
      : buildCartesianOption(doc, payload, wrap.dataset.activeTerm || '');
    if (!opt) { disposeWrap(wrap, lib); return; }
    if (ext && typeof ext.adaptMobileOpt === 'function') opt = ext.adaptMobileOpt(opt, payload, w, tok);
    if (defaults && typeof defaults.normalizeOption === 'function') opt = defaults.normalizeOption(opt, payload, tok, w);
    inst.setOption(opt, true);
    inst.resize({ width: w, height: h });
    wrap.dataset.qeMountKey = mKey;
    wrap.dataset.echartsActive = 'true';
    if (defaults && typeof defaults.observeChartResize === 'function' && !HOST_RESIZE_CLEANUPS.has(wrap)) {
      HOST_RESIZE_CLEANUPS.set(wrap, defaults.observeChartResize(host, inst, { onResize: function () { mountWrap(doc, wrap, lib); } }));
    }
  }

  function activateEcoTab(tabBtn) {
    var wrap = tabBtn && tabBtn.closest('.qe-eco-drawer');
    if (!wrap) return;
    var targetId = tabBtn.getAttribute('aria-controls');
    wrap.querySelectorAll('.qe-eco-tab[role="tab"]').forEach(function (t) {
      var on = t === tabBtn;
      t.setAttribute('aria-selected', on ? 'true' : 'false');
      t.tabIndex = on ? 0 : -1;
    });
    wrap.querySelectorAll('.qe-eco-panel[role="tabpanel"]').forEach(function (p) {
      if (p.id === targetId) p.removeAttribute('hidden');
      else p.setAttribute('hidden', 'until-found');
    });
  }

  function copyEcoSnippet(btn) {
    var drawer = btn && btn.closest('.qe-eco-drawer');
    if (!drawer) return;
    var panel = drawer.querySelector('.qe-eco-panel:not([hidden]) pre');
    var status = drawer.querySelector('.qe-copy-status');
    var txt = panel ? panel.textContent : '';
    var done = function (msg) {
      if (!status) return;
      clearTimeout(COPY_TIMERS.get(status));
      status.textContent = msg;
      status.classList.add('is-visible');
      COPY_TIMERS.set(status, setTimeout(function () { status.classList.remove('is-visible'); status.textContent = ''; }, 2000));
    };
    var fallbackCopy = function () {
      var d = drawer.ownerDocument || global.document;
      if (!d || !d.body || typeof d.execCommand !== 'function') { done('Copy failed'); return; }
      var ta = d.createElement('textarea');
      ta.value = txt; ta.readOnly = true;
      ta.style.cssText = 'position:fixed;opacity:0;pointer-events:none;left:-9999px';
      d.body.appendChild(ta); ta.select();
      var ok = false;
      try { ok = !!d.execCommand('copy'); } catch (_err) {}
      d.body.removeChild(ta);
      if (btn && btn.focus) btn.focus();
      done(ok ? 'Copied' : 'Copy failed');
    };
    if (global.navigator && global.navigator.clipboard && global.navigator.clipboard.writeText) {
      global.navigator.clipboard.writeText(txt).then(function () { done('Copied'); }, fallbackCopy);
    } else { fallbackCopy(); }
  }

  function bindEvents(doc) {
    if (!ROOT_LISTENERS.has(doc)) {
      ROOT_LISTENERS.add(doc);
      doc.addEventListener('click', function (ev) {
        var btn = ev.target && ev.target.closest ? ev.target.closest('.qe-mode-btn[data-qe-mode]') : null;
        if (btn) {
          var mode = btn.dataset.qeMode || 'svg';
          var wrap = btn.closest('.qe-plot-wrap');
          if (wrap) {
            wrap.dataset.echartsMode = mode;
            wrap.querySelectorAll('.qe-mode-btn[data-qe-mode]').forEach(function (b) {
              var on = b.dataset.qeMode === mode;
              b.classList.toggle('is-active', on);
              b.setAttribute('aria-pressed', on ? 'true' : 'false');
            });
            boot(doc);
          }
          return;
        }
        var ecoTab = ev.target && ev.target.closest ? ev.target.closest('.qe-eco-tab[role="tab"]') : null;
        if (ecoTab) { activateEcoTab(ecoTab); return; }
        var copyBtn = ev.target && ev.target.closest ? ev.target.closest('.qe-copy-btn') : null;
        if (copyBtn) { copyEcoSnippet(copyBtn); return; }
        var termBtn = ev.target && ev.target.closest ? ev.target.closest('button[data-term], .qe-eq-term[data-term]') : null;
        if (termBtn) {
          var term = termBtn.dataset.term || '';
          var scopeEl = termBtn.closest('.qe-figure, .v9-stage-inner') || doc;
          var wraps = scopeEl.querySelectorAll('.qe-plot-wrap[data-quiet-echarts]');
          wraps.forEach(function (w) {
            if (term && scopeEl === doc && w.dataset.quietEcharts.indexOf('"' + term + '"') < 0) return;
            w.dataset.activeTerm = w.dataset.activeTerm === term ? '' : term;
          });
          boot(doc);
        }
      });
      doc.addEventListener('keydown', function (ev) {
        var tab = ev.target && ev.target.closest ? ev.target.closest('.qe-eco-tab[role="tab"]') : null;
        if (!tab) return;
        var list = tab.closest('[role="tablist"]');
        var tabs = list ? Array.prototype.slice.call(list.querySelectorAll('.qe-eco-tab[role="tab"]')) : [];
        var idx = tabs.indexOf(tab);
        if (idx < 0) return;
        var nxt = ev.key === 'ArrowRight' ? (idx + 1) % tabs.length : (ev.key === 'ArrowLeft' ? (idx - 1 + tabs.length) % tabs.length : (ev.key === 'Home' ? 0 : (ev.key === 'End' ? tabs.length - 1 : -1)));
        if (nxt >= 0) { ev.preventDefault(); activateEcoTab(tabs[nxt]); tabs[nxt].focus(); }
      });
      doc.addEventListener('beforematch', function (ev) {
        var panel = ev.target && ev.target.closest ? ev.target.closest('.qe-eco-panel[role="tabpanel"]') : null;
        var tid = panel && panel.getAttribute('aria-labelledby');
        if (tid) activateEcoTab(doc.getElementById(tid));
      }, true);
    }
    if (!RESIZE_OBSERVERS.has(doc) && typeof global.ResizeObserver === 'function') {
      var ro = new global.ResizeObserver(function () { refresh(doc); });
      if (doc.body) ro.observe(doc.body);
      RESIZE_OBSERVERS.set(doc, ro);
    }
  }

  function boot(docRef) {
    var doc = docRef || global.document;
    if (!doc) return;
    bindEvents(doc);
    var lib = getLib();
    doc.querySelectorAll('.qe-plot-wrap[data-quiet-echarts]').forEach(function (w) { mountWrap(doc, w, lib); });
  }

  function refresh(docRef) {
    var doc = docRef || global.document;
    if (doc) { var lib = getLib(); doc.querySelectorAll('.qe-plot-wrap[data-quiet-echarts]').forEach(function (w) { mountWrap(doc, w, lib); }); }
  }

  function disposeAll(docRef) {
    var doc = docRef || global.document;
    if (!doc) return;
    var ro = RESIZE_OBSERVERS.get(doc);
    if (ro) { ro.disconnect(); RESIZE_OBSERVERS.delete(doc); }
    var lib = getLib();
    doc.querySelectorAll('.qe-plot-wrap[data-quiet-echarts]').forEach(function (w) { disposeWrap(w, lib); });
  }

  global.QuietEChartsAdapter = { boot: boot, refresh: refresh, disposeAll: disposeAll };
}(window));
