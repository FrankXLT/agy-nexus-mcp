/* SPDX-License-Identifier: Apache-2.0 */
/* Quiet Evidence — ECharts Option Builders for Gantt, Heatmap, Dumbbell & Forest */
(function (global) {
  'use strict';

  var HEATMAP_STOPS = [[239, 246, 255], [147, 197, 253], [253, 230, 138], [251, 191, 36], [110, 38, 14]];
  var HEATMAP_RAMP = ['#EFF6FF', '#93C5FD', '#FDE68A', '#FBBF24', '#6E260E'];

  function srgbLin(ch) {
    var s = ch / 255.0;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  }

  function heatmapCellInk(frac) {
    var u = Math.max(0, Math.min(1, Number.isFinite(frac) ? frac : 0));
    var seg = Math.min(3, Math.floor(u * 4));
    var f = (u - seg * 0.25) / 0.25;
    var c0 = HEATMAP_STOPS[seg], c1 = HEATMAP_STOPS[seg + 1];
    var r = Math.round(c0[0] + f * (c1[0] - c0[0]));
    var g = Math.round(c0[1] + f * (c1[1] - c0[1]));
    var b = Math.round(c0[2] + f * (c1[2] - c0[2]));
    var lum = 0.2126 * srgbLin(r) + 0.7152 * srgbLin(g) + 0.0722 * srgbLin(b);
    return (1.05 / (lum + 0.05)) >= ((lum + 0.05) / 0.0585) ? '#FFFFFF' : '#0F172A';
  }

  function clampX(x, cs) {
    var lo = cs ? cs.x : -1e6;
    var hi = cs ? (cs.x + cs.width) : 1e6;
    return Math.max(lo, Math.min(hi, x));
  }

  function baseTooltip(tokens) {
    return {
      trigger: 'item',
      renderMode: 'richText',
      backgroundColor: tokens.bgSurface,
      borderColor: tokens.borderStrong,
      borderWidth: 1,
      textStyle: { color: tokens.textPrimary, fontSize: 12, fontFamily: 'Inter, sans-serif' },
    };
  }

  function buildGanttOption(_doc, payload, tokens, hostW) {
    var tasks = payload.tasks || [];
    var cats = tasks.map(function (t) { return t.label; });
    var narrow = (hostW || 640) < 520;
    var leftPad = narrow ? 126 : 162;
    var data = tasks.map(function (t, i) {
      return [i, t.start, t.end, t.float || 0, t.critical ? 1 : 0, t.milestone ? 1 : 0];
    });
    var unit = payload.unit || 'd';
    var todayText = payload.todayLabel || ('Today (' + payload.todayMarker + unit + ')');
    var markLine = payload.todayMarker != null ? {
      symbol: ['none', 'none'],
      silent: true,
      lineStyle: { color: tokens.statusDanger, type: 'dashed', width: 1.6 },
      label: { show: true, formatter: todayText, color: tokens.statusDanger, fontSize: 11, fontWeight: 700, position: 'start', distance: 6, rotate: 0 },
      data: [{ xAxis: payload.todayMarker }],
    } : undefined;

    return {
      animation: false,
      tooltip: Object.assign(baseTooltip(tokens), {
        formatter: function (p) {
          var idx = p && Array.isArray(p.value) ? p.value[0] : -1;
          var t = tasks[idx] || {};
          var flt = t.float ? (' · +' + t.float + unit + ' float') : '';
          return (t.label || '') + '\n' + (t.start != null ? t.start : '') + ' → ' + (t.end != null ? t.end : '') + ' ' + unit + flt;
        },
      }),
      grid: { left: leftPad, right: narrow ? 14 : 24, top: 34, bottom: 44, containLabel: false },
      xAxis: {
        type: 'value',
        name: (payload.x && payload.x.name) || ('Schedule, t / ' + unit),
        nameLocation: 'middle',
        nameGap: 26,
        min: payload.x ? payload.x.min : 0,
        max: payload.x ? payload.x.max : undefined,
        interval: payload.x ? payload.x.interval : undefined,
        nameTextStyle: { color: tokens.textPrimary, fontWeight: 700, fontSize: narrow ? 11 : 11.5 },
        axisLabel: { color: tokens.textSecondary, fontSize: 11 },
        splitLine: { lineStyle: { color: tokens.borderHairline } },
      },
      yAxis: {
        type: 'category',
        inverse: true,
        data: cats,
        axisLine: { lineStyle: { color: tokens.borderStrong } },
        axisTick: { show: false },
        axisLabel: {
          color: tokens.textPrimary,
          fontSize: 11,
          lineHeight: narrow ? 13 : 14,
          width: narrow ? 118 : 154,
          overflow: 'break',
        },
        splitLine: { show: true, lineStyle: { color: tokens.borderHairline } },
      },
      series: [{
        type: 'custom',
        name: 'Schedule',
        renderItem: function (params, api) {
          var idx = api.value(0), s = api.value(1), e = api.value(2), flt = api.value(3);
          var crit = api.value(4) === 1, mile = api.value(5) === 1;
          var pS = api.coord([s, idx]), pE = api.coord([e, idx]), pF = api.coord([e + flt, idx]);
          if (!Number.isFinite(pS[0]) || !Number.isFinite(pE[0]) || !Number.isFinite(pS[1])) return null;
          var cs = params && params.coordSys ? params.coordSys : null;
          var xS = clampX(pS[0], cs), xE = clampX(pE[0], cs), xF = clampX(pF[0], cs);
          var h = Math.min(14, Math.max(8, api.size([0, 1])[1] * 0.52));
          if (mile) {
            return {
              type: 'polygon',
              shape: { points: [[xE, pE[1] - 7], [xE + 7, pE[1]], [xE, pE[1] + 7], [xE - 7, pE[1]]] },
              style: { fill: tokens.statusWarn, stroke: tokens.bgSurface, lineWidth: 1.2 },
            };
          }
          var children = [{
            type: 'rect',
            shape: { x: xS, y: pS[1] - h / 2, width: Math.max(4, xE - xS), height: h, r: 2.5 },
            style: { fill: crit ? tokens.accentFocal : tokens.bgElevated, stroke: crit ? tokens.bgSurface : tokens.accentFocal, lineWidth: crit ? 0.8 : 1.4 },
          }];
          if (flt > 0 && xF > xE + 2) {
            children.push({
              type: 'rect',
              shape: { x: xE, y: pS[1] - h * 0.36, width: xF - xE, height: h * 0.72, r: 2 },
              style: { fill: tokens.bgSurface, stroke: tokens.textSecondary, lineWidth: 1, lineDash: [3, 2] },
            });
          }
          return { type: 'group', children: children };
        },
        data: data,
        markLine: markLine,
      }],
    };
  }

  function buildHeatmapOption(_doc, payload, tokens, hostW) {
    var zMin = payload.min != null ? payload.min : 0, zMax = payload.max != null ? payload.max : 100;
    var zSpan = (zMax - zMin) || 1, leftPad = (hostW || 640) < 480 ? 10 : 16;
    var xCats = payload.xCategories || [], rawCells = payload.cells || [];
    if (payload.trimFutureWeeks && typeof global.QuietTimeBinning !== 'undefined' && global.QuietTimeBinning.trimTrailingFutureWeeks) {
      var trimmed = global.QuietTimeBinning.trimTrailingFutureWeeks(xCats, rawCells, { today: payload.todayIso });
      xCats = trimmed.weeks;
      rawCells = trimmed.cells;
    }
    var zeroStyle = (typeof global.QuietTimeBinning !== 'undefined' && global.QuietTimeBinning.heatmapZeroCellStyle)
      ? global.QuietTimeBinning.heatmapZeroCellStyle(tokens.bgSurface, tokens.borderHairline) : null;
    var data = rawCells.filter(Array.isArray).map(function (c) {
      var isZero = c[2] === 0;
      var lblColor = (isZero && zeroStyle && zeroStyle.labelColor) ? zeroStyle.labelColor : heatmapCellInk((c[2] - zMin) / zSpan);
      var item = { value: c, label: { color: lblColor } };
      if (isZero && zeroStyle) item.itemStyle = { color: zeroStyle.fill, borderColor: zeroStyle.borderColor, borderWidth: zeroStyle.borderWidth };
      return item;
    });
    return {
      animation: false,
      tooltip: Object.assign(baseTooltip(tokens), {
        formatter: function (p) {
          var v = (p && Array.isArray(p.value)) ? p.value : [0, 0, 0];
          var xc = xCats[v[0]] || '';
          var yc = (payload.yCategories || [])[v[1]] || '';
          return yc + ' · ' + xc + '\n' + v[2] + (payload.unit ? ' ' + payload.unit : '');
        },
      }),
      grid: { left: leftPad, right: 24, top: 20, bottom: 54, containLabel: true },
      xAxis: {
        type: 'category',
        position: 'top',
        data: xCats,
        axisLabel: { color: tokens.textPrimary, fontSize: 11, fontWeight: 600 },
        splitArea: { show: false },
      },
      yAxis: {
        type: 'category',
        data: payload.yCategories || [],
        axisLabel: { color: tokens.textPrimary, fontSize: 11, fontWeight: 600 },
      },
      visualMap: {
        min: zMin,
        max: zMax,
        orient: 'horizontal',
        left: 'center',
        bottom: 6,
        itemWidth: 11,
        itemHeight: 130,
        inRange: { color: HEATMAP_RAMP },
        text: [String(zMax), String(zMin)],
        textStyle: { color: tokens.textSecondary, fontSize: 11 },
      },
      series: [{
        type: 'heatmap',
        data: data,
        itemStyle: { borderColor: tokens.borderHairline || tokens.bgSurface, borderWidth: 1 },
        label: {
          show: payload.rigor !== 'L1',
          fontSize: 11,
          fontFamily: 'JetBrains Mono, monospace',
          fontWeight: 700,
          formatter: function (p) { return String((p.value && p.value[2] != null) ? p.value[2] : ''); },
        },
      }],
    };
  }

  function buildDumbbellOption(_doc, payload, tokens, hostW) {
    var items = payload.items || [];
    var cats = payload.categories || [];
    var narrow = (hostW || 640) < 520;
    var stems = items.map(function (it, i) { return [i, it.before, it.after]; });
    return {
      animation: false,
      tooltip: Object.assign(baseTooltip(tokens), { trigger: 'axis' }),
      legend: { top: 2, right: 12, textStyle: { color: tokens.textSecondary, fontSize: 11 } },
      grid: { left: 68, right: 24, top: 36, bottom: 48, containLabel: true },
      xAxis: {
        type: 'category',
        boundaryGap: true,
        data: cats,
        axisLabel: {
          color: tokens.textSecondary,
          fontSize: 11,
          interval: 0,
          formatter: function (v) {
            if (!narrow) return v;
            var lines = (typeof global.QuietSvgLayout !== 'undefined') ? global.QuietSvgLayout.wrapLabelLines(v, 10, 2) : String(v).split(' ');
            return lines.join('\n');
          },
        },
        axisLine: { lineStyle: { color: tokens.textPrimary } },
      },
      yAxis: {
        type: 'value',
        name: payload.y ? payload.y.name : '',
        nameLocation: 'middle',
        nameGap: 44,
        min: payload.y ? payload.y.min : undefined,
        max: payload.y ? payload.y.max : undefined,
        interval: payload.y ? payload.y.interval : undefined,
        nameTextStyle: { color: tokens.textPrimary, fontSize: 11, fontWeight: 700 },
        axisLabel: { color: tokens.textSecondary, fontSize: 11 },
        splitLine: { lineStyle: { color: tokens.borderHairline } },
      },
      series: [
        {
          type: 'custom',
          silent: true,
          tooltip: { show: false },
          renderItem: function (_p, api) {
            var xIdx = api.value(0), pB = api.coord([xIdx, api.value(1)]), pA = api.coord([xIdx, api.value(2)]);
            if (!Number.isFinite(pB[0]) || !Number.isFinite(pB[1]) || !Number.isFinite(pA[1])) return null;
            return { type: 'line', shape: { x1: pB[0], y1: pB[1], x2: pA[0], y2: pA[1] }, style: { stroke: tokens.borderStrong, lineWidth: 2 } };
          },
          data: stems,
        },
        {
          name: payload.beforeLabel || 'Baseline',
          type: 'scatter',
          symbolSize: 8,
          itemStyle: { color: tokens.bgSurface, borderColor: tokens.textSecondary, borderWidth: 1.8 },
          data: items.map(function (it) { return it.before; }),
        },
        {
          name: payload.afterLabel || 'After',
          type: 'scatter',
          symbolSize: 9,
          itemStyle: { color: tokens.accentFocal, borderColor: tokens.bgSurface, borderWidth: 1.2 },
          data: items.map(function (it) { return it.after; }),
        },
      ],
    };
  }

  function buildForestOption(_doc, payload, tokens, hostW) {
    var items = payload.items || [];
    var narrow = (hostW || 640) < 480;
    var leftPad = narrow ? 12 : 16;
    var data = items.map(function (it, i) { return [i, it.ciLow, it.estimate, it.ciHigh, it.pooled ? 1 : 0, it.sig ? 1 : 0]; });
    return {
      animation: false,
      tooltip: Object.assign(baseTooltip(tokens), {
        formatter: function (p) {
          var idx = p && Array.isArray(p.value) ? p.value[0] : -1;
          var it = items[idx] || {};
          return (it.label || '') + '\n' + it.estimate + ' (95% CI: ' + it.ciLow + ' to ' + it.ciHigh + ')';
        },
      }),
      grid: { left: leftPad, right: 24, top: 22, bottom: 44, containLabel: true },
      xAxis: {
        type: 'value',
        name: payload.x ? payload.x.name : 'Effect (95% CI)',
        nameLocation: 'middle',
        nameGap: 26,
        min: payload.x ? payload.x.min : undefined,
        max: payload.x ? payload.x.max : undefined,
        interval: payload.x ? payload.x.interval : undefined,
        nameTextStyle: { color: tokens.textPrimary, fontSize: 11.5, fontWeight: 700 },
        axisLabel: { color: tokens.textSecondary, fontSize: 11 },
        splitLine: { lineStyle: { color: tokens.borderHairline } },
      },
      yAxis: {
        type: 'category',
        data: payload.categories || [],
        axisLabel: {
          color: tokens.textPrimary,
          fontSize: 11,
          formatter: function (v) {
            var s = String(v || '');
            if (!narrow || s.length <= 16) return s;
            if (typeof global.QuietSvgLayout !== 'undefined') return global.QuietSvgLayout.wrapLabelLines(s, 15, 2).join('\n');
            return s;
          },
        },
        axisTick: { show: false },
      },
      series: [{
        type: 'custom',
        renderItem: function (params, api) {
          var yi = api.value(0), lo = api.coord([api.value(1), yi]), mid = api.coord([api.value(2), yi]), hi = api.coord([api.value(3), yi]);
          if (!Number.isFinite(lo[0]) || !Number.isFinite(mid[0]) || !Number.isFinite(hi[0]) || !Number.isFinite(mid[1])) return null;
          var cs = params && params.coordSys ? params.coordSys : null;
          var xLo = clampX(lo[0], cs), xMid = clampX(mid[0], cs), xHi = clampX(hi[0], cs);
          var col = api.value(5) === 1 ? tokens.accentFocal : tokens.textSecondary;
          var children = [
            { type: 'line', shape: { x1: xLo, y1: lo[1], x2: xHi, y2: hi[1] }, style: { stroke: col, lineWidth: 1.8 } },
            { type: 'line', shape: { x1: xLo, y1: lo[1] - 4, x2: xLo, y2: lo[1] + 4 }, style: { stroke: col, lineWidth: 1.4 } },
            { type: 'line', shape: { x1: xHi, y1: hi[1] - 4, x2: xHi, y2: hi[1] + 4 }, style: { stroke: col, lineWidth: 1.4 } },
          ];
          if (api.value(4) === 1) {
            children.push({ type: 'polygon', shape: { points: [[xMid, mid[1] - 6], [xMid + 7, mid[1]], [xMid, mid[1] + 6], [xMid - 7, mid[1]]] }, style: { fill: col, stroke: tokens.bgSurface, lineWidth: 1 } });
          } else {
            children.push({ type: 'rect', shape: { x: xMid - 4, y: mid[1] - 4, width: 8, height: 8 }, style: { fill: col, stroke: tokens.bgSurface, lineWidth: 1 } });
          }
          return { type: 'group', children: children };
        },
        data: data,
        markLine: {
          symbol: ['none', 'none'],
          silent: true,
          lineStyle: { color: tokens.textPrimary, type: 'dashed', width: 1.4 },
          label: { show: false },
          data: [{ xAxis: payload.nullValue != null ? payload.nullValue : 1 }],
        },
      }],
    };
  }

  function wrapAxisNames(axesOrAxis, maxChars, minGap) {
    var list = Array.isArray(axesOrAxis) ? axesOrAxis : (axesOrAxis ? [axesOrAxis] : []);
    var wrapped = false;
    list.forEach(function (ax) {
      if (!ax || typeof ax.name !== 'string' || ax.name.indexOf('\n') >= 0 || ax.name.length <= maxChars) return;
      var mid = Math.floor(ax.name.length * 0.56);
      var sp = ax.name.lastIndexOf(' ', mid);
      if (sp < 6) sp = ax.name.indexOf(' ', mid);
      if (sp > 3 && sp < ax.name.length - 3) {
        ax.name = ax.name.slice(0, sp) + '\n' + ax.name.slice(sp + 1);
        ax.nameTextStyle = Object.assign({}, ax.nameTextStyle, { fontSize: 11, lineHeight: 13 });
        ax.nameGap = Math.max(minGap, (ax.nameGap || minGap) - 6);
        wrapped = true;
      }
    });
    return wrapped;
  }

  function adaptMobileOpt(opt, payload, w, tokens) {
    if (!opt || !payload) return opt;
    var narrow = (w || 640) < 480;
    var kind = payload.kind || 'cartesian';
    var haloBg = tokens ? tokens.bgSurface : '#FFFFFF';
    var textSec = tokens ? tokens.textSecondary : '#475569';
    if (kind === 'stacked_bar') {
      if (opt.series && opt.series[0] && opt.series[0].markLine && Array.isArray(opt.series[0].markLine.data)) {
        opt.series[0].markLine.data.forEach(function (d) {
          if (Number(d.yAxis) < 0) d.label = Object.assign({}, d.label, { position: 'insideStartBottom', distance: 4, fontSize: 11, backgroundColor: haloBg, padding: [1, 4], borderRadius: 2 });
        });
      }
      if (narrow) {
        if (opt.legend) opt.legend = Object.assign({}, opt.legend, { left: 6, right: 6, itemGap: 6, itemWidth: 10, textStyle: { color: textSec, fontSize: 11 } });
        if (opt.grid) opt.grid = Object.assign({}, opt.grid, { left: 46, right: 12, top: 68, bottom: 44, containLabel: true });
      }
    } else if (kind === 'waterfall' && narrow) {
      if (opt.legend) opt.legend = Object.assign({}, opt.legend, { left: 6, right: 6, itemGap: 8, textStyle: { color: textSec, fontSize: 11 } });
      var wrappedWfY = wrapAxisNames(opt.yAxis, 14, 46);
      if (opt.grid) opt.grid = Object.assign({}, opt.grid, { left: wrappedWfY ? 64 : 52, right: 12, top: 52, bottom: 62, containLabel: true });
      if (opt.xAxis && opt.xAxis.axisLabel) {
        opt.xAxis.axisLabel = {
          color: textSec,
          fontSize: 11,
          lineHeight: 13,
          interval: 0,
          rotate: 0,
          formatter: function (v) {
            if (typeof global.QuietSvgLayout !== 'undefined') return global.QuietSvgLayout.wrapLabelLines(v, 9, 2).join('\n');
            var w = String(v).split(' ');
            return w.length >= 2 ? w.slice(0, Math.ceil(w.length / 2)).join(' ') + '\n' + w.slice(Math.ceil(w.length / 2)).join(' ') : v;
          },
        };
      }
      if (opt.series && opt.series[0] && opt.series[0].markLine && Array.isArray(opt.series[0].markLine.data)) {
        opt.series[0].markLine.data.forEach(function (d) {
          d.label = Object.assign({}, d.label, { position: 'insideStartTop', fontSize: 11, backgroundColor: haloBg, padding: [2, 5], borderRadius: 2 });
        });
      }
    } else if (kind === 'cartesian' && narrow) {
      if (opt.legend) opt.legend = Object.assign({}, opt.legend, { top: 2, left: 6, right: 6, itemGap: 6, itemWidth: 12, textStyle: { color: textSec, fontSize: 11 } });
      var maxAxChars = Math.max(18, Math.floor(((w || 320) - 96) / 10.5));
      var wrappedX = wrapAxisNames(opt.xAxis, maxAxChars, 20);
      wrapAxisNames(opt.yAxis, 22, 42);
      if (Array.isArray(opt.grid)) {
        opt.grid[0] = Object.assign({}, opt.grid[0], { right: 14, top: 58, bottom: wrappedX ? 140 : 132 });
        opt.grid[1] = Object.assign({}, opt.grid[1], { right: 14, bottom: wrappedX ? 54 : 46 });
        if (wrappedX && opt.graphic && opt.graphic[0]) opt.graphic[0] = Object.assign({}, opt.graphic[0], { bottom: 120 });
      } else if (opt.grid) {
        opt.grid = Object.assign({}, opt.grid, { right: 14, top: 56, bottom: wrappedX ? 58 : 52 });
      }
      (opt.series || []).forEach(function (sr) {
        if (sr.markPoint && Array.isArray(sr.markPoint.data)) {
          sr.markPoint.data.forEach(function (pt) { if (pt.label) pt.label.fontSize = 11; });
        }
        if (sr.markLine && Array.isArray(sr.markLine.data)) {
          sr.markLine.data.forEach(function (d) {
            var pos = (d.label && String(d.label.formatter || '').toLowerCase().indexOf('floor') >= 0) ? 'insideStartBottom' : 'insideEndTop';
            d.label = Object.assign({}, d.label, { position: pos, fontSize: 11, backgroundColor: haloBg, padding: [1, 4], borderRadius: 2 });
          });
        }
      });
    }
    return opt;
  }

  global.QuietEChartsExt = {
    adaptMobileOpt: adaptMobileOpt,
    buildOption: function (doc, payload, tokens, hostW) {
      if (payload.kind === 'gantt') return buildGanttOption(doc, payload, tokens, hostW);
      if (payload.kind === 'heatmap') return buildHeatmapOption(doc, payload, tokens, hostW);
      if (payload.kind === 'dumbbell') return buildDumbbellOption(doc, payload, tokens, hostW);
      if (payload.kind === 'forest') return buildForestOption(doc, payload, tokens, hostW);
      return null;
    },
  };
}(typeof window !== 'undefined' ? window : this));
