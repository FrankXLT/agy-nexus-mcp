/* SPDX-License-Identifier: Apache-2.0 */
/* Quiet Evidence — ECharts Metrology Layers (Corridors, Envelopes, Residuals, Waterfall) */
(function (global) {
  'use strict';

  function fmtNum(v) {
    if (!Number.isFinite(v)) return '';
    if (Math.abs(v) < 1e-12) return '0';
    return String(Number(v.toPrecision(6)));
  }

  function mapLineType(style) {
    if (style === 'dash-dot' || style === 'dashdot') return [8, 3, 2, 3];
    if (style === 'dotted') return 'dotted';
    if (style === 'solid') return 'solid';
    return 'dashed';
  }

  function makeCorridorSeries(sr, col, opacity, axisIdx) {
    var band = sr && sr.corridor;
    if (!Array.isArray(band) || band.length < 2) return null;
    return {
      name: (sr.name || 'Model') + ' corridor',
      type: 'custom',
      xAxisIndex: axisIdx || 0,
      yAxisIndex: axisIdx || 0,
      silent: true,
      tooltip: { show: false },
      legendHoverLink: false,
      z: 1,
      data: [band[0]],
      renderItem: function (params, api) {
        if (params.dataIndex !== 0) return null;
        var sys = params.coordSys || {};
        var yTop = Number.isFinite(sys.y) ? sys.y : -1e9;
        var yBot = Number.isFinite(sys.y) && Number.isFinite(sys.height) ? sys.y + sys.height : 1e9;
        var up = [];
        var lo = [];
        for (var i = 0; i < band.length; i += 1) {
          var pt = band[i];
          var cLo = api.coord([pt[0], pt[1]]);
          var cHi = api.coord([pt[0], pt[2]]);
          if (!cLo || !cHi || !Number.isFinite(cHi[0]) || !Number.isFinite(cHi[1]) || !Number.isFinite(cLo[1])) continue;
          up.push([cHi[0], Math.max(yTop, Math.min(yBot, cHi[1]))]);
          lo.push([cLo[0], Math.max(yTop, Math.min(yBot, cLo[1]))]);
        }
        if (up.length < 2) return null;
        var poly = up.concat(lo.reverse());
        return { type: 'polygon', shape: { points: poly }, style: { fill: col, opacity: 0.14 * opacity } };
      },
    };
  }

  function makeSlopedEnvelopes(payload, t, cssVar, doc, axisIdx) {
    var out = [];
    (payload.envelopes || []).forEach(function (env, idx) {
      if (!Array.isArray(env.points) || env.points.length < 2) return;
      var col = cssVar(doc, env.token || '--status-warn', env.type === 'abort' ? t.statusDanger : t.statusWarn);
      var midIdx = Math.max(0, Math.min(env.points.length - 1, Math.floor(env.points.length * 0.42)));
      var anchorPt = env.points[midIdx];
      out.push({
        id: 'env-sloped-' + idx,
        name: env.label || ('Envelope ' + idx),
        type: 'line',
        xAxisIndex: axisIdx || 0,
        yAxisIndex: axisIdx || 0,
        showSymbol: false,
        silent: true,
        tooltip: { show: false },
        legendHoverLink: false,
        data: env.points,
        lineStyle: { color: col, width: 1.7, type: mapLineType(env.strokeStyle || (env.type === 'abort' ? 'dash-dot' : 'dashed')) },
        itemStyle: { color: col },
        markPoint: env.label ? {
          silent: true,
          symbol: 'rect',
          symbolSize: [1, 1],
          itemStyle: { opacity: 0 },
          data: [{ coord: [anchorPt[0], anchorPt[1]] }],
          label: {
            show: true,
            position: env.direction === 'lower' ? 'bottom' : 'top',
            distance: 6,
            formatter: env.label,
            color: col,
            fontSize: 11,
            fontWeight: 600,
            backgroundColor: t.bgSurface,
            borderColor: col,
            borderWidth: 0.6,
            borderRadius: 3,
            padding: [2, 5],
          },
        } : undefined,
        z: 3,
      });
    });
    return out;
  }

  function attachResidualStrip(opt, payload, t, xAxisBase) {
    var res = payload && payload.residuals;
    if (!res || !Array.isArray(res.points) || !res.points.length) return opt;
    opt.grid = [
      { left: 72, right: 24, top: 44, bottom: 132, containLabel: false },
      { left: 72, right: 24, bottom: 46, height: 64, containLabel: false },
    ];
    opt.xAxis = [
      Object.assign({}, xAxisBase, { gridIndex: 0, name: '', axisLabel: { show: false } }),
      Object.assign({}, xAxisBase, { gridIndex: 1 }),
    ];
    opt.yAxis.gridIndex = 0;
    opt.yAxis.nameGap = 52;
    opt.yAxis = [
      opt.yAxis,
      {
        type: 'value',
        gridIndex: 1,
        min: -3,
        max: 3,
        interval: 1,
        splitLine: { show: false },
        axisLine: { lineStyle: { color: t.textSecondary } },
        axisTick: { show: false },
        axisLabel: {
          color: t.textSecondary,
          fontSize: 10,
          formatter: function (v) { return v === 2 ? '+2\u03c3' : (v === -2 ? '\u22122\u03c3' : (v === 0 ? '0' : '')); },
        },
      },
    ];
    opt.graphic = [
      {
        type: 'text',
        left: 76,
        bottom: 112,
        silent: true,
        style: { text: res.label || 'Normalized Residuals', fill: t.textSecondary, font: '600 10.5px Inter, system-ui, sans-serif' },
      },
    ];
    opt.series.forEach(function (s) {
      s.xAxisIndex = 0;
      s.yAxisIndex = 0;
    });
    opt.series.push({
      id: 'qe-residual-lollipops',
      name: 'Residuals',
      type: 'custom',
      xAxisIndex: 1,
      yAxisIndex: 1,
      silent: true,
      tooltip: { show: false },
      legendHoverLink: false,
      z: 4,
      data: res.points,
      markArea: {
        silent: true,
        itemStyle: { color: t.borderHairline, opacity: 0.42 },
        data: [[{ yAxis: -2 }, { yAxis: 2 }]],
      },
      markLine: {
        silent: true,
        symbol: ['none', 'none'],
        label: { show: false },
        data: [
          { yAxis: 0, lineStyle: { color: t.borderStrong, width: 1, type: 'solid' } },
          { yAxis: 2, lineStyle: { color: t.borderStrong, width: 0.9, type: 'dashed' } },
          { yAxis: -2, lineStyle: { color: t.borderStrong, width: 0.9, type: 'dashed' } },
        ],
      },
      renderItem: function (_params, api) {
        var xv = api.value(0);
        var rv = api.value(1);
        var p0 = api.coord([xv, 0]);
        var p1 = api.coord([xv, rv]);
        if (!p0 || !p1 || !Number.isFinite(p0[0]) || !Number.isFinite(p0[1]) || !Number.isFinite(p1[1])) return null;
        return {
          type: 'group',
          children: [
            { type: 'line', shape: { x1: p0[0], y1: p0[1], x2: p1[0], y2: p1[1] }, style: { stroke: t.accentFocal, lineWidth: 1.35 } },
            { type: 'circle', shape: { cx: p1[0], cy: p1[1], r: 3.1 }, style: { fill: t.bgSurface, stroke: t.accentFocal, lineWidth: 1.5 } },
          ],
        };
      },
    });
    return opt;
  }

  function buildWaterfallOption(doc, payload, t, envData) {
    var yMeta = payload.y || {};
    var kinds = payload.stepKinds || [];
    var cats = payload.categories || [];
    var unit = payload.unit ? ' ' + payload.unit : '';
    var spans = payload.spans || [];
    if (!spans.length) {
      var bases = payload.bases || [], tots = payload.totals || [], pos = payload.positive || [], neg = payload.negative || [], sig = payload.signedValues || [];
      spans = cats.map(function (_c, idx) {
        if (tots[idx] !== '-' && tots[idx] !== undefined && tots[idx] !== null) {
          var tv = Number(tots[idx]); return [Math.min(0, tv), Math.max(0, tv), tv, kinds[idx] || 'total'];
        }
        var b = Number(bases[idx] || 0);
        if (pos[idx] !== '-' && pos[idx] !== undefined && pos[idx] !== null) { var pv = Number(pos[idx]); return [b, b + pv, pv, 'inc']; }
        var nv = Number(neg[idx] || 0);
        return [b, b + nv, Number(sig[idx] !== undefined ? sig[idx] : -nv), 'dec'];
      });
    }
    var totItems = [], incItems = [], decItems = [];
    spans.forEach(function (sp, idx) {
      var lo = Number(sp[0]), hi = Number(sp[1]), sVal = Number(sp[2]), k = String(sp[3] || '');
      if (k === 'start' || k === 'total') {
        var isStart = k === 'start';
        totItems.push({
          value: [idx, lo, hi, sVal],
          itemStyle: { color: isStart ? t.bgElevated : t.statusOk, borderColor: isStart ? t.borderStrong : t.statusOk, borderWidth: 1.5 },
          label: { color: isStart ? t.textPrimary : t.statusOk },
        });
      } else if (sVal >= 0) {
        incItems.push({ value: [idx, lo, hi, sVal], itemStyle: { color: t.accentFocal, borderColor: t.accentFocal }, label: { color: t.accentFocal } });
      } else {
        decItems.push({ value: [idx, lo, hi, sVal], itemStyle: { color: t.statusWarn, borderColor: t.statusWarn }, label: { color: t.statusWarn } });
      }
    });
    function makeSpanSeries(name, itemColor, items, isInc) {
      return {
        name: name,
        type: 'custom',
        encode: { x: 0, y: [1, 2], tooltip: 3 },
        itemStyle: { color: itemColor },
        label: {
          show: true,
          fontSize: 10,
          fontWeight: 700,
          formatter: function (p) {
            var v = p.value && Number(p.value[3]);
            if (!Number.isFinite(v)) return '';
            if (isInc === null) return v.toFixed(1) + unit;
            return (v >= 0 ? '+' : '\u2212') + Math.abs(v).toFixed(1) + unit;
          },
        },
        renderItem: function (_params, api) {
          var idx = api.value(0), lo = api.value(1), hi = api.value(2), sVal = api.value(3);
          var x = api.coord([idx, 0])[0];
          var yTop = api.coord([idx, hi])[1];
          var yBot = api.coord([idx, lo])[1];
          var bw = Math.min(50, api.size([1, 0])[0] * 0.58);
          var r = sVal >= 0 ? [3, 3, 0, 0] : [0, 0, 3, 3];
          var lblPos = sVal >= 0 ? 'top' : 'bottom';
          return {
            type: 'rect',
            shape: { x: x - bw / 2, y: yTop, width: bw, height: Math.max(2, yBot - yTop), r: r },
            style: api.style(),
            textConfig: { position: lblPos, distance: 5 },
          };
        },
        data: items,
      };
    }
    var wfSeries = [
      makeSpanSeries('Total / Balance', t.statusOk, totItems, null),
      makeSpanSeries('Increase', t.accentFocal, incItems, true),
      makeSpanSeries('Reduction / Cost', t.statusWarn, decItems, false),
    ];
    if (envData.length) {
      wfSeries[0].markLine = {
        silent: true,
        symbol: ['none', 'none'],
        data: envData.map(function (e) {
          return Object.assign({}, e, {
            label: Object.assign({}, e.label, { position: 'insideMiddleTop', backgroundColor: t.bgSurface, padding: [1, 5], borderRadius: 2 }),
          });
        }),
      };
    }
    return {
      animation: false,
      backgroundColor: 'transparent',
      textStyle: { fontFamily: 'Inter, system-ui, sans-serif', color: t.textPrimary },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        renderMode: 'richText',
        confine: true,
        backgroundColor: t.bgElevated,
        borderColor: t.borderStrong,
        borderWidth: 1,
        textStyle: { color: t.textPrimary, fontSize: 12 },
        formatter: function (params) {
          var p = (params || [])[0];
          if (!p || !p.value) return '';
          var idx = p.value[0], v = Number(p.value[3]);
          var sStr = (kinds[idx] === 'start' || kinds[idx] === 'total') ? v.toFixed(1) : ((v >= 0 ? '+' : '\u2212') + Math.abs(v).toFixed(1));
          return (cats[idx] || '') + '\n' + p.seriesName + ': ' + sStr + unit;
        },
      },
      legend: { top: 2, left: 64, textStyle: { color: t.textSecondary, fontSize: 11 }, data: ['Total / Balance', 'Increase', 'Reduction / Cost'] },
      grid: { left: 66, right: 24, top: 44, bottom: 56, containLabel: true },
      xAxis: {
        type: 'category',
        data: payload.categories || [],
        axisLine: { onZero: false, lineStyle: { color: t.textSecondary } },
        axisLabel: { color: t.textSecondary, fontSize: 10.5, interval: 0, formatter: function (v) { var w = String(v).split(' '); return w.length === 2 ? w.join('\n') : v; } },
      },
      yAxis: {
        type: 'value',
        min: Number.isFinite(yMeta.min) ? yMeta.min : undefined,
        max: Number.isFinite(yMeta.max) ? yMeta.max : undefined,
        interval: Number.isFinite(yMeta.interval) ? yMeta.interval : undefined,
        name: yMeta.name || payload.yName || 'Value',
        nameLocation: 'middle',
        nameGap: 44,
        nameTextStyle: { color: t.textSecondary, fontSize: 11.5, fontWeight: 600 },
        axisLine: { lineStyle: { color: t.textSecondary } },
        axisLabel: { color: t.textSecondary, fontSize: 11, hideOverlap: true, formatter: fmtNum },
        splitLine: { lineStyle: { color: t.borderHairline, type: 'dashed' } },
      },
      series: wfSeries,
    };
  }

  function buildStackedBarOption(doc, payload, t, envData, resolveSeriesColor) {
    var yMeta = payload.y || {};
    var series = (payload.series || []).map(function (sr, idx) {
      var col = resolveSeriesColor(doc, sr, idx, t);
      if (sr.seriesType === 'line') {
        return { id: sr.id, name: sr.name, type: 'line', showSymbol: false, symbol: 'circle', symbolSize: 5, smooth: false, data: sr.data || [], lineStyle: { color: col, width: 2.2 }, itemStyle: { color: col }, z: 5 };
      }
      return { id: sr.id, name: sr.name, type: 'bar', stack: sr.stack || 'energy', barMaxWidth: 20, itemStyle: { color: col, borderRadius: [1.5, 1.5, 1.5, 1.5] }, data: sr.data || [], z: 3 };
    });
    if (series.length && envData.length) series[0].markLine = { silent: true, symbol: ['none', 'none'], data: envData };
    return {
      animation: false,
      backgroundColor: 'transparent',
      textStyle: { fontFamily: 'Inter, system-ui, sans-serif', color: t.textPrimary },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, renderMode: 'richText', confine: true, backgroundColor: t.bgElevated, borderColor: t.borderStrong, borderWidth: 1, textStyle: { color: t.textPrimary, fontSize: 12 } },
      legend: { top: 2, left: 48, right: 12, itemWidth: 14, itemHeight: 8, textStyle: { color: t.textSecondary, fontSize: 11 }, data: (payload.series || []).map(function (s) { return s.name; }) },
      grid: { left: 56, right: 20, top: 48, bottom: 48, containLabel: true },
      xAxis: {
        type: 'category',
        data: payload.categories || [],
        name: (payload.x || {}).name || 'Hour of Day',
        nameLocation: 'middle',
        nameGap: 26,
        nameTextStyle: { color: t.textSecondary, fontSize: 11, fontWeight: 600 },
        axisLine: { onZero: true, lineStyle: { color: t.textSecondary } },
        axisLabel: { color: t.textSecondary, fontSize: 11, interval: (payload.categories || []).length <= 12 ? 0 : function (i) { return i % 4 === 0; } },
      },
      yAxis: {
        type: 'value',
        min: Number.isFinite(yMeta.min) ? yMeta.min : undefined,
        max: Number.isFinite(yMeta.max) ? yMeta.max : undefined,
        interval: Number.isFinite(yMeta.interval) ? yMeta.interval : undefined,
        name: yMeta.name || 'Power (kW)',
        nameLocation: 'middle',
        nameGap: 40,
        nameTextStyle: { color: t.textSecondary, fontSize: 11, fontWeight: 600 },
        axisLine: { lineStyle: { color: t.textSecondary } },
        axisLabel: { color: t.textSecondary, fontSize: 11, hideOverlap: true, formatter: fmtNum },
        splitLine: { lineStyle: { color: t.borderHairline, type: 'dashed' } },
      },
      series: series,
    };
  }

  function fmtLogDecade(exp) {
    if (!Number.isFinite(exp)) return '';
    var r = Math.round(exp);
    if (Math.abs(exp - r) > 0.05) return '';
    if (r >= -3 && r <= 4) {
      var v = Math.pow(10, r);
      return r < 0 ? v.toFixed(-r) : v.toLocaleString('en-US');
    }
    var sup = { '-': '\u207b', '0': '\u2070', '1': '\u00b9', '2': '\u00b2', '3': '\u00b3', '4': '\u2074', '5': '\u2075', '6': '\u2076', '7': '\u2077', '8': '\u2078', '9': '\u2079' };
    return '10' + String(r).split('').map(function (c) { return sup[c] || c; }).join('');
  }

  function mapCartesianPayload(payload) {
    if (!payload || payload.kind !== 'cartesian') return payload;
    var xm = payload.x || {}, ym = payload.y || {};
    var xLog = !!xm.log, yLog = !!ym.log;
    if (!xLog && !yLog) return payload;
    var tx = function (v) { return xLog ? (typeof v === 'number' && v > 0 && Number.isFinite(v) ? Math.log10(v) : null) : v; };
    var ty = function (v) { return yLog ? (typeof v === 'number' && v > 0 && Number.isFinite(v) ? Math.log10(v) : null) : v; };
    var yFloor = (yLog && ym.min > 0) ? ym.min * 0.5 : 1e-30;
    var newSeries = (payload.series || []).map(function (sr) {
      var outS = Object.assign({}, sr);
      if (sr.epistemic === 'analytical_model') {
        outS.data = (sr.data || []).map(function (p) { return [tx(p[0]), ty(p[1])]; }).filter(function (p) { return p[0] !== null && p[1] !== null; });
        if (Array.isArray(sr.corridor)) {
          outS.corridor = sr.corridor.map(function (c) {
            return [tx(c[0]), ty(Math.max(yFloor, c[1])), ty(Math.max(yFloor, c[2]))];
          }).filter(function (c) { return c[0] !== null && c[1] !== null && c[2] !== null; });
        }
      } else {
        var wh = [];
        outS.data = (sr.data || []).map(function (p) {
          var mx = tx(p[0]), my = p[1] === null ? null : ty(p[1]);
          if (my !== null && mx !== null && p[2] > 0 && (!yLog || p[1] > 0)) {
            var loR = yLog ? Math.max(yFloor, p[1] - p[2]) : (p[1] - p[2]);
            var hiR = p[1] + p[2];
            var loM = ty(loR), hiM = ty(hiR);
            if (loM !== null && hiM !== null) wh.push([mx, loM, hiM]);
          }
          return [mx, my, p[0], p[1]];
        });
        outS.whiskers = wh;
      }
      return outS;
    });
    var newEnv = (payload.envelopes || []).map(function (e) {
      var oe = Object.assign({}, e);
      if (Array.isArray(e.points)) oe.points = e.points.map(function (p) { return [tx(p[0]), ty(p[1])]; }).filter(function (p) { return p[0] !== null && p[1] !== null; });
      else if (typeof e.value === 'number') oe.value = ty(e.value);
      return oe;
    });
    var newRes = payload.residuals ? Object.assign({}, payload.residuals, {
      points: (payload.residuals.points || []).map(function (p) { return [tx(p[0]), p[1]]; }).filter(function (p) { return p[0] !== null; }),
    }) : undefined;
    return Object.assign({}, payload, {
      x: Object.assign({}, xm, { log: false, logMapped: xLog, min: xLog ? tx(xm.min) : xm.min, max: xLog ? tx(xm.max) : xm.max, interval: xLog ? 1 : xm.interval }),
      y: Object.assign({}, ym, { log: false, logMapped: yLog, min: yLog ? ty(ym.min) : ym.min, max: yLog ? ty(ym.max) : ym.max, interval: yLog ? 1 : ym.interval }),
      series: newSeries,
      envelopes: newEnv,
      residuals: newRes,
    });
  }

  global.QuietEChartsLayers = {
    fmtLogDecade: fmtLogDecade,
    mapCartesianPayload: mapCartesianPayload,
    makeCorridorSeries: makeCorridorSeries,
    makeSlopedEnvelopes: makeSlopedEnvelopes,
    attachResidualStrip: attachResidualStrip,
    buildWaterfallOption: buildWaterfallOption,
    buildStackedBarOption: buildStackedBarOption,
  };
}(window));
