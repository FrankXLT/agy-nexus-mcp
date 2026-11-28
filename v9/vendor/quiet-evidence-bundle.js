/* SPDX-License-Identifier: Apache-2.0 */
/**
 * Quiet UI Pillar 2 — Progressive-Enhancement Evidence Runtime (<= 250L, zero deps).
 * Features:
 *   1. Synchronized multi-channel waveform cursor readout ([data-qe-scope="true"])
 *   2. Pedagogical Flow equation-to-visual term highlighting ([data-term])
 *   3. Spec drawer metadata & copy-JSON feedback
 */
(function (window, document) {
  'use strict';

  var termsBound = false;

  function findNearestSample(samples, targetT, maxGap) {
    if (!Array.isArray(samples) || samples.length === 0) return null;
    for (let i = 0; i < samples.length - 1; i++) {
      const a = samples[i];
      const b = samples[i + 1];
      if (!Array.isArray(a) || !Array.isArray(b) || a.length < 2 || b.length < 2) continue;
      const t0 = Number(a[0]);
      const t1 = Number(b[0]);
      if (targetT >= t0 && targetT <= t1) {
        if (Math.abs(targetT - t0) < 1e-6 && a[1] !== null && a[1] !== undefined) return a;
        if (Math.abs(targetT - t1) < 1e-6 && b[1] !== null && b[1] !== undefined) return b;
        if (a[1] === null || a[1] === undefined || b[1] === null || b[1] === undefined) {
          return null;
        }
        if (Number.isFinite(maxGap) && maxGap > 0 && (t1 - t0) > maxGap) {
          return null;
        }
      }
    }
    let best = null;
    let bestDt = Infinity;
    for (let i = 0; i < samples.length; i++) {
      const s = samples[i];
      if (!Array.isArray(s) || s.length < 2) continue;
      const dt = Math.abs(Number(s[0]) - targetT);
      if (dt < bestDt) {
        bestDt = dt;
        best = s;
      }
    }
    return best;
  }

  function renderScopeAtTime(svg, meta, targetT) {
    if (!Number.isFinite(meta.x0) || !Number.isFinite(meta.pw) || meta.pw <= 0) return;
    if (!Number.isFinite(meta.t_min) || !Number.isFinite(meta.t_span) || meta.t_span <= 0) return;
    const t = Math.max(meta.t_min, Math.min(meta.t_min + meta.t_span, targetT));
    const clampedX = meta.x0 + ((t - meta.t_min) / meta.t_span) * meta.pw;
    svg.dataset.qeCursorT = String(t);

    const cursorLine = svg.querySelector('.qe-live-cursor');
    if (cursorLine) {
      cursorLine.setAttribute('x1', clampedX.toFixed(1));
      cursorLine.setAttribute('x2', clampedX.toFixed(1));
      cursorLine.setAttribute('visibility', 'visible');
    }

    const wrap = svg.closest('.qe-waveform-wrap') || svg.closest('.qe-plot-wrap');
    const readout = wrap ? wrap.querySelector('.qe-scope-readout') : null;
    if (!readout) return;

    const gapLim = Number(meta.max_gap);
    const vals = (meta.channels || []).map(function (ch) {
      const cid = String((ch && ch.id) || 'CH').toUpperCase();
      const s = findNearestSample(ch && ch.samples, t, gapLim);
      if (!s || s[1] === null || s[1] === undefined) {
        return cid + ': DROPOUT';
      }
      const vStr = typeof s[1] === 'number' ? Number(s[1]).toFixed(2) : String(s[1]);
      return cid + ': ' + vStr + (ch.unit ? '\u00a0' + ch.unit : '');
    });
    readout.textContent = 't = ' + t.toFixed(2) + '\u00a0' + (meta.t_unit || '') + '  |  ' + vals.join('  |  ');
  }

  function updateScopeCursor(svg, meta, clientX) {
    const rect = svg.getBoundingClientRect();
    const vb = svg.viewBox && svg.viewBox.baseVal;
    if (!rect.width || !vb || !vb.width || !meta.pw || meta.pw <= 0) return;
    const svgX = ((clientX - rect.left) / rect.width) * vb.width;
    const clampedX = Math.max(meta.x0, Math.min(meta.x0 + meta.pw, svgX));
    const t = meta.t_min + ((clampedX - meta.x0) / meta.pw) * meta.t_span;
    renderScopeAtTime(svg, meta, t);
  }

  function clearScopeCursor(svg) {
    const cursorLine = svg.querySelector('.qe-live-cursor');
    if (cursorLine) cursorLine.setAttribute('visibility', 'hidden');
    const wrap = svg.closest('.qe-waveform-wrap') || svg.closest('.qe-plot-wrap');
    const readout = wrap ? wrap.querySelector('.qe-scope-readout') : null;
    if (readout) {
      if (readout._qeDefaultNodes && readout._qeDefaultNodes.length) {
        readout.replaceChildren.apply(readout, readout._qeDefaultNodes.map(function (n) { return n.cloneNode(true); }));
      } else if (readout.dataset.default) {
        readout.textContent = readout.dataset.default;
      }
    }
  }

  function initWaveforms() {
    document.querySelectorAll('svg[data-qe-scope="true"]').forEach(function (svg) {
      if (svg.dataset.qeScopeBound === '1') return;
      const wrap = svg.closest('.qe-waveform-wrap') || svg.closest('.qe-plot-wrap');
      const dataEl = wrap ? wrap.querySelector('.qe-scope-data') : null;
      const roEl = wrap ? wrap.querySelector('.qe-scope-readout') : null;
      if (roEl && !roEl._qeDefaultNodes) roEl._qeDefaultNodes = Array.from(roEl.childNodes, function (n) { return n.cloneNode(true); });
      if (!dataEl) return;
      let meta = null;
      try {
        meta = JSON.parse(dataEl.textContent || '{}');
      } catch (_err) {
        return;
      }
      svg.dataset.qeScopeBound = '1';
      svg.addEventListener('pointermove', function (ev) { updateScopeCursor(svg, meta, ev.clientX); });
      svg.addEventListener('pointerdown', function (ev) { updateScopeCursor(svg, meta, ev.clientX); });
      svg.addEventListener('pointerleave', function () { clearScopeCursor(svg); });
      svg.addEventListener('keydown', function (ev) {
        const curT = Number(svg.dataset.qeCursorT || meta.t_min);
        const dt = Number(meta.dt);
        const step = (Number.isFinite(dt) && dt > 0 && ((meta.t_span || 1) / dt) <= 200) ? dt : ((meta.t_span || 1) / 40);
        if (ev.key === 'ArrowRight') { ev.preventDefault(); renderScopeAtTime(svg, meta, curT + step); }
        else if (ev.key === 'ArrowLeft') { ev.preventDefault(); renderScopeAtTime(svg, meta, curT - step); }
        else if (ev.key === 'Home') { ev.preventDefault(); renderScopeAtTime(svg, meta, meta.t_min); }
        else if (ev.key === 'End') { ev.preventDefault(); renderScopeAtTime(svg, meta, meta.t_min + meta.t_span); }
        else if (ev.key === 'Escape') { clearScopeCursor(svg); }
      });
    });
  }

  function setActiveTerm(scopeRoot, termKey) {
    if (!scopeRoot) return;
    scopeRoot.querySelectorAll('[data-term]').forEach(function (el) {
      if (!termKey) {
        el.classList.remove('is-term-active', 'is-term-dimmed');
      } else if (el.getAttribute('data-term') === termKey) {
        el.classList.add('is-term-active');
        el.classList.remove('is-term-dimmed');
      } else {
        el.classList.remove('is-term-active');
        el.classList.add('is-term-dimmed');
      }
    });
  }

  function initPedagogicalTerms() {
    if (termsBound) return;
    termsBound = true;
    const resolveScope = function (ev) {
      const target = ev.target && ev.target.closest ? ev.target.closest('[data-term]') : null;
      if (!target) return null;
      return { target: target, scope: target.closest('.qe-pedagogy-scope') || target.closest('.qe-figure') || document };
    };
    document.addEventListener('pointerover', function (ev) { const r = resolveScope(ev); if (r) setActiveTerm(r.scope, r.target.getAttribute('data-term')); });
    document.addEventListener('pointerout', function (ev) { const r = resolveScope(ev); if (r) setActiveTerm(r.scope, r.scope.dataset.pinnedTerm || null); });
    document.addEventListener('click', function (ev) {
      const btn = ev.target && ev.target.closest ? ev.target.closest('button[data-term], .qe-eq-term[data-term]') : null;
      if (!btn) return;
      const scope = btn.closest('.qe-pedagogy-scope') || btn.closest('.qe-figure') || document;
      const term = btn.getAttribute('data-term');
      const next = (scope.dataset.pinnedTerm === term) ? '' : (term || '');
      if (next) scope.dataset.pinnedTerm = next;
      else delete scope.dataset.pinnedTerm;
      setActiveTerm(scope, next || null);
      scope.querySelectorAll('button[data-term], .qe-eq-term[data-term]').forEach(function (b) {
        b.setAttribute('aria-pressed', (next && b.getAttribute('data-term') === next) ? 'true' : 'false');
      });
    });
    document.addEventListener('focusin', function (ev) { const r = resolveScope(ev); if (r) setActiveTerm(r.scope, r.target.getAttribute('data-term')); });
    document.addEventListener('focusout', function (ev) { const r = resolveScope(ev); if (r) setActiveTerm(r.scope, r.scope.dataset.pinnedTerm || null); });
  }

  function copyWithFallback(txt, btn, defaultLabel, statusEl) {
    const label = defaultLabel || 'Copy JSON Spec';
    const markCopied = function (msg) {
      if (statusEl) {
        statusEl.textContent = msg;
        statusEl.classList.add('is-visible');
        window.setTimeout(function () { statusEl.classList.remove('is-visible'); statusEl.textContent = ''; }, 1800);
      } else {
        btn.textContent = msg;
        window.setTimeout(function () { btn.textContent = label; }, 1400);
      }
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(txt).then(function () { markCopied('Copied'); }).catch(function () {});
      return;
    }
    const ta = document.createElement('textarea');
    ta.value = txt;
    ta.setAttribute('readonly', '');
    ta.style.cssText = 'position:fixed;opacity:0;pointer-events:none;left:-9999px';
    document.body.appendChild(ta);
    ta.select();
    try { if (document.execCommand('copy')) markCopied('Copied'); } catch (_err) {}
    document.body.removeChild(ta);
  }

  function initSpecDrawers() {
    document.querySelectorAll('.qe-spec-drawer').forEach(function (dlg) {
      if (dlg.querySelector('.qe-copy-spec-btn')) return;
      const pre = dlg.querySelector('pre');
      if (!pre) return;
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'va-pill-btn qe-copy-spec-btn';
      btn.textContent = 'Copy JSON Spec';
      btn.addEventListener('click', function () { copyWithFallback(pre.textContent || '', btn, 'Copy JSON Spec'); });
      pre.parentNode.insertBefore(btn, pre);
    });
  }

  function activateEcoTabFallback(tabBtn) {
    const wrap = tabBtn && tabBtn.closest('.qe-eco-drawer');
    if (!wrap) return;
    const targetId = tabBtn.getAttribute('aria-controls');
    wrap.querySelectorAll('.qe-eco-tab[role="tab"]').forEach(function (t) {
      const on = t === tabBtn;
      t.setAttribute('aria-selected', on ? 'true' : 'false');
      t.tabIndex = on ? 0 : -1;
    });
    wrap.querySelectorAll('.qe-eco-panel[role="tabpanel"]').forEach(function (p) {
      if (p.id === targetId) p.removeAttribute('hidden');
      else p.setAttribute('hidden', 'until-found');
    });
  }

  function initEcoAndModeFallback() {
    const hideUnusedModebars = function () {
      const hasEcharts = typeof window.echarts !== 'undefined' || (window.parent && window.parent !== window && typeof window.parent.echarts !== 'undefined');
      if (typeof window.QuietEChartsAdapter === 'undefined' && !hasEcharts) {
        document.querySelectorAll('.qe-plot-modebar').forEach(function (bar) { bar.hidden = true; });
      }
    };
    if (typeof queueMicrotask === 'function') queueMicrotask(hideUnusedModebars);
    else window.setTimeout(hideUnusedModebars, 0);
    if (typeof window.QuietEChartsAdapter !== 'undefined' || document.documentElement.dataset.qeEcoFallback === '1') return;
    document.documentElement.dataset.qeEcoFallback = '1';
    document.addEventListener('click', function (ev) {
      if (typeof window.QuietEChartsAdapter !== 'undefined') return;
      const tab = ev.target && ev.target.closest ? ev.target.closest('.qe-eco-tab[role="tab"]') : null;
      if (tab) { activateEcoTabFallback(tab); return; }
      const copyBtn = ev.target && ev.target.closest ? ev.target.closest('.qe-copy-btn') : null;
      if (copyBtn) {
        const drw = copyBtn.closest('.qe-eco-drawer');
        const pre = drw && drw.querySelector('.qe-eco-panel:not([hidden]) pre');
        if (pre) copyWithFallback(pre.textContent || '', copyBtn, copyBtn.textContent, drw.querySelector('.qe-copy-status'));
      }
    });
    document.addEventListener('keydown', function (ev) {
      if (typeof window.QuietEChartsAdapter !== 'undefined') return;
      const tab = ev.target && ev.target.closest ? ev.target.closest('.qe-eco-tab[role="tab"]') : null;
      if (!tab) return;
      const list = tab.closest('[role="tablist"]');
      const tabs = list ? Array.prototype.slice.call(list.querySelectorAll('.qe-eco-tab[role="tab"]')) : [];
      const idx = tabs.indexOf(tab);
      if (idx < 0) return;
      const nxt = ev.key === 'ArrowRight' ? (idx + 1) % tabs.length : (ev.key === 'ArrowLeft' ? (idx - 1 + tabs.length) % tabs.length : (ev.key === 'Home' ? 0 : (ev.key === 'End' ? tabs.length - 1 : -1)));
      if (nxt >= 0) { ev.preventDefault(); activateEcoTabFallback(tabs[nxt]); tabs[nxt].focus(); }
    });
    document.addEventListener('beforematch', function (ev) {
      if (typeof window.QuietEChartsAdapter !== 'undefined') return;
      const panel = ev.target && ev.target.closest ? ev.target.closest('.qe-eco-panel[role="tabpanel"]') : null;
      const tid = panel && panel.getAttribute('aria-labelledby');
      if (tid) activateEcoTabFallback(document.getElementById(tid));
    }, true);
  }

  function boot() {
    initWaveforms();
    initPedagogicalTerms();
    initSpecDrawers();
    initEcoAndModeFallback();
  }

  if (typeof document !== 'undefined' && document) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', boot);
    } else {
      boot();
    }
  }

  window.QuietEvidenceRuntime = { boot: boot, setActiveTerm: setActiveTerm };
})(window, typeof document !== 'undefined' ? document : null);


// SPDX-License-Identifier: Apache-2.0
(function (root) {
  'use strict';

  var _measureCtx = null;

  function getMeasureCtx() {
    if (_measureCtx) return _measureCtx;
    if (typeof document !== 'undefined' && document.createElement) {
      var canvas = document.createElement('canvas');
      if (canvas && canvas.getContext) _measureCtx = canvas.getContext('2d');
    }
    return _measureCtx;
  }

  function measureTextPx(text, fontSpec) {
    var s = String(text == null ? '' : text);
    var ctx = getMeasureCtx();
    if (ctx) {
      ctx.font = fontSpec || '11px Inter, system-ui, sans-serif';
      return ctx.measureText(s).width;
    }
    return s.length * 6.8;
  }

  function roundClean(v) {
    return Math.abs(v) < 1e-12 ? 0 : Number(v.toFixed(10));
  }

  function niceStep125(rawStep) {
    if (!Number.isFinite(rawStep) || rawStep <= 0) return 1;
    var exp = Math.floor(Math.log10(rawStep));
    var pow = Math.pow(10, exp);
    var frac = rawStep / pow;
    var mant = 1;
    if (frac > 5) mant = 10;
    else if (frac > 2) mant = 5;
    else if (frac > 1) mant = 2;
    return mant * pow;
  }

  function niceScale125(minVal, maxVal, opts) {
    var cfg = opts || {};
    var targetTicks = Math.max(2, Number(cfg.targetTicks || 5));
    var lo = Number(minVal);
    var hi = Number(maxVal);
    if (!Number.isFinite(lo)) lo = 0;
    if (!Number.isFinite(hi)) hi = lo + 1;
    if (cfg.includeZero) {
      lo = Math.min(lo, 0);
      hi = Math.max(hi, 0);
    }
    if (lo > hi) { var tmp = lo; lo = hi; hi = tmp; }
    if (Math.abs(hi - lo) < 1e-9) {
      var pad = Math.abs(lo) > 1e-6 ? Math.abs(lo) * 0.2 : 1;
      lo = cfg.includeZero && lo >= 0 ? 0 : lo - pad;
      hi = hi + pad;
    }
    var step = niceStep125((hi - lo) / (targetTicks - 1));
    var sMin = roundClean(Math.floor(lo / step + 1e-9) * step);
    if (cfg.clampMin !== undefined && cfg.clampMin !== null && Number.isFinite(Number(cfg.clampMin))) {
      sMin = Math.max(Number(cfg.clampMin), sMin);
    }
    var sMax = roundClean(Math.ceil(hi / step - 1e-9) * step);
    if (sMax <= sMin) sMax = roundClean(sMin + step);
    var ticks = [];
    var guard = 0;
    for (var cur = sMin; cur <= sMax + step * 1e-4 && guard < 24; cur += step, guard += 1) {
      ticks.push(roundClean(cur));
    }
    return { min: sMin, max: sMax, step: roundClean(step), ticks: ticks };
  }

  function formatTick(v, step) {
    if (!Number.isFinite(v)) return '';
    if (Math.abs(v) < 1e-12) return '0';
    var st = Math.abs(Number(step || 1));
    var dec = st >= 1 ? 0 : Math.min(4, Math.max(1, Math.ceil(-Math.log10(st)) + 1));
    return roundClean(v).toLocaleString(undefined, { maximumFractionDigits: dec });
  }

  function firstUnclosedIdx(str) {
    var p = [], b = [];
    for (var i = 0; i < str.length; i += 1) {
      var c = str[i];
      if (c === '(') p.push(i);
      else if (c === ')' && p.length) p.pop();
      else if (c === '[') b.push(i);
      else if (c === ']' && b.length) b.pop();
    }
    var ip = p.length ? p[0] : Infinity;
    var ib = b.length ? b[0] : Infinity;
    var m = Math.min(ip, ib);
    return Number.isFinite(m) ? m : -1;
  }

  function balanceDelimiters(str) {
    var out = String(str || '').replace(/[\s,(\[:/-]+$/, '');
    var guard = 0;
    while (guard < 8) {
      var idx = firstUnclosedIdx(out);
      if (idx === -1) break;
      if (idx > 0) {
        out = out.slice(0, idx).replace(/[\s,(\[:/-]+$/, '');
      } else {
        out = out.slice(1).replace(/^[\s(\[]+/, '');
      }
      guard += 1;
    }
    return out;
  }

  function truncateTokenSafe(str, limit) {
    var cut = Math.max(2, limit - 1);
    var head = balanceDelimiters(str.slice(0, cut).replace(/\s+\S*$/, '') || str.slice(0, cut));
    return (head || str.replace(/[(\[]/g, '').slice(0, cut)) + '\u2026';
  }

  function wrapLabelLines(text, maxChars, maxLines) {
    var raw = String(text == null ? '' : text).trim().replace(/\s+/g, ' ');
    var limit = Math.max(6, Number(maxChars || 18));
    var capLines = Math.max(1, Number(maxLines || 2));
    if (!raw || raw.length <= limit) return raw ? [balanceDelimiters(raw) || raw] : [''];
    var words = raw.split(' ');
    var lines = [];
    var cur = '';
    for (var i = 0; i < words.length; i += 1) {
      var w = words[i];
      if (!cur) {
        cur = w;
      } else if ((cur.length + 1 + w.length) <= limit) {
        cur += ' ' + w;
      } else {
        lines.push(cur);
        if (lines.length >= capLines) {
          cur = '';
          break;
        }
        cur = w;
      }
    }
    if (cur && lines.length < capLines) lines.push(cur);
    if (lines.length === 1 && lines[0].length > limit) {
      return [truncateTokenSafe(lines[0], limit)];
    }
    var consumedWords = lines.join(' ').split(' ').length;
    if (consumedWords < words.length || (lines.length === capLines && lines.join(' ').length < raw.length)) {
      lines[lines.length - 1] = truncateTokenSafe(lines[lines.length - 1], limit);
    }
    for (var li = 0; li < lines.length - 1; li += 1) {
      if (firstUnclosedIdx(lines[li]) !== -1 && firstUnclosedIdx(lines.join(' ')) !== -1) {
        lines[li] = balanceDelimiters(lines[li]) || lines[li].replace(/[(\[]/g, '');
      }
    }
    return lines;
  }

  function isMonoLabelSet(list) {
    if (!list.length) return false;
    var hits = 0;
    for (var i = 0; i < list.length; i += 1) {
      var s = String(list[i] == null ? '' : list[i]).trim();
      if (/[_/\\:]|[a-z]+-[a-z0-9-]+|^0x[0-9a-f]+$|^\d{2,}h$/i.test(s)) hits += 1;
    }
    return hits * 2 >= list.length;
  }

  function measureCategoryGutter(labels, opts) {
    var cfg = opts || {};
    var list = Array.isArray(labels) ? labels : [];
    var numOr = function (v, d) { var n = Number(v); return v != null && v !== '' && Number.isFinite(n) ? n : d; };
    var minPx = Math.max(0, numOr(cfg.minPx, 64)), maxPx = Math.max(minPx, numOr(cfg.maxPx, 220));
    var axisMargin = Math.max(0, numOr(cfg.axisLabelMargin, 8));
    var padPx = Math.max(0, numOr(cfg.padPx, 12)) + axisMargin;
    var maxChars = Math.max(6, numOr(cfg.maxChars, 24));
    var ff = String(cfg.fontFamily || '').toLowerCase();
    var isMono = cfg.mono === true || ff === 'mono' || ff.indexOf('mono') >= 0 || (cfg.mono !== false && !cfg.fontFamily && !cfg.font && isMonoLabelSet(list));
    var fontMatch = (String(cfg.font || '').match(/(\d+(?:\.\d+)?)px/i) || [])[1];
    var rawFs = numOr(cfg.fontSize, fontMatch ? Number(fontMatch) : NaN);
    var fSize = rawFs > 0 ? rawFs : (isMono ? 12 : 11);
    var fontSpec = cfg.font || (fSize + 'px ' + (isMono ? 'JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, monospace' : 'Inter, system-ui, sans-serif'));
    var maxW = 0;
    var wrappedLabels = list.map(function (lbl) {
      var lines = wrapLabelLines(lbl, maxChars, cfg.maxLines || 2);
      lines.forEach(function (ln) {
        var measured = measureTextPx(ln, fontSpec);
        if (isMono) measured = Math.max(measured, ln.length * fSize * 0.64);
        maxW = Math.max(maxW, measured);
      });
      return lines.join('\n');
    });
    return { gutterPx: Math.max(minPx, Math.min(maxPx, Math.ceil(maxW + padPx))), maxLinePx: Math.ceil(maxW), wrappedLabels: wrappedLabels, mono: isMono };
  }

  function filterNonOverlappingTicks(ticks, opts) {
    var list = Array.isArray(ticks) ? ticks.slice() : [];
    var cfg = opts || {};
    var axis = cfg.axis === 'y' ? 'y' : 'x';
    var gap = Math.max(2, Number(cfg.minGapPx != null ? cfg.minGapPx : 10));
    var fontSpec = cfg.font || '11px JetBrains Mono, monospace';
    var lineH = Number(cfg.lineHeightPx || 14);
    var keepEnds = !!cfg.keepEnds;
    list.sort(function (a, b) { return Number(a.pos || 0) - Number(b.pos || 0); });
    var kept = [];
    var lastEnd = -Infinity;
    list.forEach(function (tk, idx) {
      var pos = Number(tk.pos || 0);
      var lbl = String(tk.label != null ? tk.label : tk.value);
      var span = axis === 'x' ? Math.max(18, measureTextPx(lbl, fontSpec)) : lineH;
      var lo = pos - span * 0.5;
      var hi = pos + span * 0.5;
      var isLast = idx === list.length - 1;
      if (lo >= lastEnd + gap) {
        kept.push(tk);
        lastEnd = hi;
      } else if (keepEnds && isLast && kept.length > 0) {
        var prev = kept[kept.length - 1];
        var prevSpan = axis === 'x' ? Math.max(18, measureTextPx(String(prev.label != null ? prev.label : prev.value), fontSpec)) : lineH;
        if (kept.length > 1) {
          var beforePrev = kept[kept.length - 2];
          var bSpan = axis === 'x' ? Math.max(18, measureTextPx(String(beforePrev.label != null ? beforePrev.label : beforePrev.value), fontSpec)) : lineH;
          if ((lo - (Number(beforePrev.pos || 0) + bSpan * 0.5)) >= gap && (lo - (Number(prev.pos || 0) + prevSpan * 0.5)) < gap) {
            kept[kept.length - 1] = tk;
            lastEnd = hi;
          }
        }
      }
    });
    return kept;
  }

  function placeReferenceLabel(docOrSvg, opts) {
    var cfg = opts || {};
    var doc = (docOrSvg && docOrSvg.ownerDocument) ? docOrSvg.ownerDocument : (typeof document !== 'undefined' ? document : null);
    var svgNS = 'http://www.w3.org/2000/svg';
    var text = String(cfg.text || '');
    var plotX0 = Number(cfg.plotX0 != null ? cfg.plotX0 : 0);
    var plotX1 = Number(cfg.plotX1 != null ? cfg.plotX1 : 600);
    var plotY0 = Number(cfg.plotY0 != null ? cfg.plotY0 : 0);
    var plotY1 = Number(cfg.plotY1 != null ? cfg.plotY1 : 260);
    var fontSpec = cfg.font || '600 11px JetBrains Mono, monospace';
    var estW = Math.ceil(measureTextPx(text, fontSpec));
    var x = Number(cfg.x != null ? cfg.x : (plotX1 - 8));
    var y = Number(cfg.y != null ? cfg.y : (plotY0 + 14));
    var anchor = cfg.anchor || (x > (plotX0 + plotX1) * 0.6 ? 'end' : (x < (plotX0 + plotX1) * 0.4 ? 'start' : 'middle'));
    var padX = 6;
    if (anchor === 'start') {
      var minS = plotX0 + padX, maxS = Math.max(minS, plotX1 - estW - padX);
      x = Math.max(minS, Math.min(maxS, x));
    } else if (anchor === 'end') {
      var minE = Math.min(plotX1 - padX, plotX0 + estW + padX), maxE = Math.max(minE, plotX1 - padX);
      x = Math.max(minE, Math.min(maxE, x));
    } else {
      var midLo = Math.min(plotX1 - padX, plotX0 + estW * 0.5 + padX), midHi = Math.max(midLo, plotX1 - estW * 0.5 - padX);
      x = Math.max(midLo, Math.min(midHi, x));
    }
    var yLo = plotY0 + 13, yHi = Math.max(yLo, plotY1 - 6);
    y = Math.max(yLo, Math.min(yHi, y));
    var haloColor = cfg.haloColor || 'var(--bg-surface, #FFFFFF)';
    var fillColor = cfg.fill || 'var(--text-secondary, #334155)';
    if (!doc || typeof doc.createElementNS !== 'function') {
      return { x: x, y: y, anchor: anchor, text: text, estWidth: estW };
    }
    var setAttrs = function (el, map) { Object.keys(map).forEach(function (k) { el.setAttribute(k, String(map[k])); }); return el; };
    var g = setAttrs(doc.createElementNS(svgNS, 'g'), { 'data-role': 'ref-label' });
    var rx = anchor === 'start' ? x - 4 : (anchor === 'end' ? x - estW - 4 : x - estW * 0.5 - 4);
    g.appendChild(setAttrs(doc.createElementNS(svgNS, 'rect'), { x: rx.toFixed(1), y: (y - 11.5).toFixed(1), width: (estW + 8).toFixed(1), height: 15, rx: 2, fill: haloColor, 'fill-opacity': 0.94, stroke: 'none' }));
    var txt = setAttrs(doc.createElementNS(svgNS, 'text'), { x: x.toFixed(1), y: y.toFixed(1), 'text-anchor': anchor, 'font-family': cfg.fontFamily || 'var(--font-mono, ui-monospace)', 'font-size': cfg.fontSize || 11, 'font-weight': cfg.fontWeight || 600, fill: fillColor, stroke: haloColor, 'stroke-width': 3.2, 'stroke-linejoin': 'round', 'paint-order': 'stroke fill' });
    txt.textContent = text;
    g.appendChild(txt);
    if (docOrSvg && docOrSvg.nodeType === 1) docOrSvg.appendChild(g);
    return g;
  }

  function toEpochMs(val) {
    if (typeof val === 'number') return Number.isFinite(val) ? val : NaN;
    if (val instanceof Date) return val.getTime();
    if (typeof val === 'string' && val.trim() !== '') {
      var trimmed = val.trim();
      return /^-?\d+(?:\.\d+)?$/.test(trimmed) ? Number(trimmed) : Date.parse(trimmed);
    }
    return NaN;
  }

  function buildCanonicalTimeGrid(startMs, endMs, stepMs, opts) {
    var s = toEpochMs(startMs);
    var e = toEpochMs(endMs);
    var step = Number(stepMs);
    if (!Number.isFinite(s) || !Number.isFinite(e) || !Number.isFinite(step) || step <= 0 || e < s) {
      return [];
    }
    var cfg = opts || {};
    if (cfg.align) s = Math.floor(s / step) * step;
    var maxBuckets = Math.max(1, Math.min(10000, Number(cfg.maxBuckets || 5000)));
    var intStep = Number.isInteger(s) && Number.isInteger(step);
    var out = [];
    for (var i = 0; i < maxBuckets; i += 1) {
      var cur = s + i * step;
      if (cur > e + step * 1e-6) break;
      out.push(intStep ? Math.round(cur) : roundClean(cur));
    }
    return out;
  }

  function extractNumericValues(node, out, depth) {
    var d = depth || 0;
    if (node == null || typeof node === 'boolean') return;
    if (typeof node === 'number') {
      if (Number.isFinite(node)) out.push(node);
      return;
    }
    if (Array.isArray(node)) {
      if (d >= 2 && node.length === 2 && (node[0] == null || typeof node[0] !== 'object') && (node[1] == null || typeof node[1] !== 'object')) {
        if (node[1] !== null && node[1] !== undefined && node[1] !== '' && typeof node[1] !== 'boolean') {
          var yPair = Number(node[1]);
          if (Number.isFinite(yPair)) out.push(yPair);
        }
        return;
      }
      for (var i = 0; i < node.length; i += 1) extractNumericValues(node[i], out, d + 1);
      return;
    }
    if (typeof node === 'object') {
      if (Array.isArray(node.data)) extractNumericValues(node.data, out, 1);
      else if (node.value !== undefined && node.value !== null && typeof node.value !== 'boolean') {
        if (Array.isArray(node.value)) extractNumericValues(node.value, out, 2);
        else {
          var vObj = Number(node.value);
          if (Number.isFinite(vObj)) out.push(vObj);
        }
      }
    }
  }

  function sharedNiceScale125(seriesArrays, opts) {
    var vals = [];
    extractNumericValues(seriesArrays, vals, 0);
    var cfg = Object.assign({}, opts || {});
    if (!vals.length) return niceScale125(0, 1, cfg);
    var lo = Math.min.apply(null, vals);
    var hi = Math.max.apply(null, vals);
    if (cfg.includeZero === undefined) cfg.includeZero = lo >= 0;
    if (cfg.headroomRatio) {
      var span = hi - lo;
      hi += (span > 0 ? span : (Math.abs(hi) || 1)) * Number(cfg.headroomRatio);
    }
    return niceScale125(lo, hi, cfg);
  }

  function maxLabelWidthPx(labels, fontSpec) {
    var list = Array.isArray(labels) ? labels : [];
    var isMono = String(fontSpec || '').toLowerCase().indexOf('mono') >= 0 || isMonoLabelSet(list);
    var fSize = Number(((String(fontSpec || '').match(/(\d+(?:\.\d+)?)px/i) || [])[1]) || (isMono ? 12 : 11));
    var w = 0;
    for (var i = 0; i < list.length; i += 1) {
      var lines = String(list[i] == null ? '' : list[i]).split('\n');
      for (var j = 0; j < lines.length; j += 1) {
        var measured = measureTextPx(lines[j], fontSpec);
        if (isMono) measured = Math.max(measured, lines[j].length * fSize * 0.64);
        w = Math.max(w, measured);
      }
    }
    return Math.ceil(w);
  }

  function measureCellGutters(cell, cfg) {
    var tickFont = cell.tickFont || cfg.tickFont || '11px JetBrains Mono, monospace';
    var yTicks = cell.yTicks || cell.leftTicks || cell.ticks || [], rTicks = cell.rightTicks || [];
    var hasRight = !!(cell.hasRightAxis || rTicks.length || cell.rightTitle);
    var leftW = Math.max(cell.minLeft || cfg.minLeft || 44, (yTicks.length ? maxLabelWidthPx(yTicks, tickFont) + 12 : 44) + (cell.yLabel || cell.leftTitle ? 18 : 0));
    var rightW = Math.max(cell.minRight || cfg.minRight || (hasRight ? 48 : 16), hasRight ? maxLabelWidthPx(rTicks, tickFont) + 14 + (cell.rightTitle ? 18 : 0) : 16);
    var topH = Math.max(cell.minTop || cfg.minTop || 20, (cell.titleHeight || 0) + (cell.topLegendHeight || (cell.hasTopLegend ? 28 : 0)) + (cell.hasTopYName ? 26 : 16));
    var botH = Math.max(cell.minBottom || cfg.minBottom || 34, (cell.xTicks && cell.xTicks.length ? 22 : 14) + (cell.xLabel || cell.bottomTitle ? 18 : 0) + (cell.bottomLegendHeight || (cell.hasBottomLegend ? 30 : 0)));
    return {
      left: Math.min(cfg.maxLeft || 224, leftW), right: Math.min(cfg.maxRight || 160, rightW),
      top: topH, bottom: botH, padX: Number(cell.containerPadX || 0), stageHeight: Number(cell.stageHeight || 0),
    };
  }

  function computeGridFrameGutters(plotsMatrix, opts) {
    var cfg = opts || {}, mat = [];
    if (Array.isArray(plotsMatrix) && plotsMatrix.length) {
      if (Array.isArray(plotsMatrix[0])) mat = plotsMatrix;
      else if (cfg.orientation === 'row') mat = [plotsMatrix];
      else mat = plotsMatrix.map(function (p) { return [p]; });
    }
    var rows = mat.length, cols = mat.reduce(function (m, row) { return Math.max(m, Array.isArray(row) ? row.length : 0); }, 0);
    var colLeft = [], colRight = [], colPadX = [], rowTop = [], rowBottom = [], rowStageH = [], r, c, raw = [];
    for (c = 0; c < cols; c += 1) { colLeft[c] = 0; colRight[c] = 0; colPadX[c] = 0; }
    for (r = 0; r < rows; r += 1) {
      rowTop[r] = 0; rowBottom[r] = 0; rowStageH[r] = 0; raw[r] = [];
      var row = Array.isArray(mat[r]) ? mat[r] : [];
      for (c = 0; c < row.length; c += 1) {
        if (!row[c]) { raw[r][c] = null; continue; }
        var g = measureCellGutters(row[c], cfg);
        raw[r][c] = g;
        colLeft[c] = Math.max(colLeft[c], g.left); colRight[c] = Math.max(colRight[c], g.right); colPadX[c] = Math.max(colPadX[c], g.padX);
        rowTop[r] = Math.max(rowTop[r], g.top); rowBottom[r] = Math.max(rowBottom[r], g.bottom); rowStageH[r] = Math.max(rowStageH[r], g.stageHeight);
      }
    }
    var cells = [];
    for (r = 0; r < rows; r += 1) {
      cells[r] = [];
      for (c = 0; c < cols; c += 1) {
        if (!raw[r] || !raw[r][c]) { cells[r][c] = null; continue; }
        cells[r][c] = { row: r, col: c, left: colLeft[c], right: colRight[c], top: rowTop[r], bottom: rowBottom[r], padX: colPadX[c], stageHeight: rowStageH[r], containLabel: false };
      }
    }
    return { rows: rows, cols: cols, colLeft: colLeft, colRight: colRight, colPadX: colPadX, rowTop: rowTop, rowBottom: rowBottom, rowStageHeight: rowStageH, cells: cells };
  }

  var api = {
    niceScale125: niceScale125, formatTick: formatTick, wrapLabelLines: wrapLabelLines,
    measureCategoryGutter: measureCategoryGutter, filterNonOverlappingTicks: filterNonOverlappingTicks,
    placeReferenceLabel: placeReferenceLabel, buildCanonicalTimeGrid: buildCanonicalTimeGrid,
    sharedNiceScale125: sharedNiceScale125, computeGridFrameGutters: computeGridFrameGutters,
  };
  root.QuietSvgLayout = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
}(typeof window !== 'undefined' ? window : globalThis));


// SPDX-License-Identifier: Apache-2.0
(function (root) {
  'use strict';

  function parseUtcMs(raw) {
    if (typeof raw === 'number') return Number.isFinite(raw) ? raw : NaN;
    if (raw instanceof Date) return raw.getTime();
    if (typeof raw !== 'string') return NaN;
    var s = raw.trim();
    if (!s) return NaN;
    if (/^-?\d+(?:\.\d+)?$/.test(s)) {
      var num = Number(s);
      return Number.isFinite(num) ? num : NaN;
    }
    var m = s.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2})(?::(\d{2})(?::(\d{2}))?)?)?$/);
    if (m) {
      var yr = Number(m[1]), mo = Number(m[2]), dy = Number(m[3]), hh = Number(m[4] || 0), mi = Number(m[5] || 0), ss = Number(m[6] || 0);
      var ms = Date.UTC(yr, mo - 1, dy, hh, mi, ss), dt = new Date(ms);
      return (dt.getUTCFullYear() === yr && dt.getUTCMonth() === mo - 1 && dt.getUTCDate() === dy &&
        dt.getUTCHours() === hh && dt.getUTCMinutes() === mi && dt.getUTCSeconds() === ss) ? ms : NaN;
    }
    var w = s.match(/^(\d{4})-W(\d{2})$/);
    if (w) {
      var wk = Number(w[2]);
      if (wk < 1 || wk > 53) return NaN;
      var j4 = new Date(Date.UTC(Number(w[1]), 0, 4)), d4 = j4.getUTCDay() || 7;
      return j4.getTime() + ((wk - 1) * 7 + (1 - d4)) * 86400000;
    }
    var ts = Date.parse(s);
    return Number.isFinite(ts) ? ts : NaN;
  }

  function pad2(n) { return n < 10 ? '0' + n : String(n); }

  function utcBucketInfo(ms, bin, cfg) {
    var dt = new Date(ms), y = dt.getUTCFullYear(), mo = pad2(dt.getUTCMonth() + 1), d = pad2(dt.getUTCDate());
    if (bin === '1h') return { sortMs: Date.UTC(y, dt.getUTCMonth(), dt.getUTCDate(), dt.getUTCHours()), key: y + '-' + mo + '-' + d + ' ' + pad2(dt.getUTCHours()) + ':00' };
    if (bin === '1d') return { sortMs: Date.UTC(y, dt.getUTCMonth(), dt.getUTCDate()), key: y + '-' + mo + '-' + d };
    var mon = new Date(Date.UTC(y, dt.getUTCMonth(), dt.getUTCDate())), day = mon.getUTCDay() || 7;
    var monMs = mon.getTime() + (1 - day) * 86400000;
    if (cfg && cfg.weekFormat === 'monday') {
      var md = new Date(monMs);
      return { sortMs: monMs, key: md.getUTCFullYear() + '-' + pad2(md.getUTCMonth() + 1) + '-' + pad2(md.getUTCDate()) };
    }
    var thu = new Date(mon.getTime() + (4 - day) * 86400000);
    var wk = Math.ceil(((thu.getTime() - Date.UTC(thu.getUTCFullYear(), 0, 1)) / 86400000 + 1) / 7);
    return { sortMs: monMs, key: thu.getUTCFullYear() + '-W' + pad2(wk) };
  }

  /** Deterministically bin hourly/daily UTC series into 1h (<=3d), 1d (4-92d), or ISO 1w (>92d) sums. */
  function binTimeSeries(dates, layersObj, opts) {
    var cfg = opts || {}, rawDates = Array.isArray(dates) ? dates : [], srcLayers = layersObj && typeof layersObj === 'object' ? layersObj : {};
    var names = Object.keys(srcLayers), parsed = [], minTs = Infinity, maxTs = -Infinity;
    for (var i = 0; i < rawDates.length; i += 1) {
      var ms = parseUtcMs(rawDates[i]);
      if (!Number.isFinite(ms)) continue;
      parsed.push({ idx: i, ms: ms });
      if (ms < minTs) minTs = ms;
      if (ms > maxTs) maxTs = ms;
    }
    if (!parsed.length) {
      var emptyL = {};
      names.forEach(function (nm) { emptyL[nm] = []; });
      return { dates: [], layers: emptyL, bin: cfg.bin || '1h', spanDays: 0 };
    }
    var spanDays = Math.max(0, (maxTs - minTs) / 86400000);
    var hLim = cfg.hourlyMaxDays != null ? Number(cfg.hourlyMaxDays) : 3, dLim = cfg.dailyMaxDays != null ? Number(cfg.dailyMaxDays) : 92;
    var bin = cfg.bin || (spanDays <= hLim ? '1h' : (spanDays <= dLim ? '1d' : '1w')), buckets = Object.create(null);
    parsed.forEach(function (pt) {
      var info = utcBucketInfo(pt.ms, bin, cfg);
      if (!buckets[info.key]) {
        var initVals = {};
        names.forEach(function (nm) { initVals[nm] = 0; });
        buckets[info.key] = { key: info.key, sortMs: info.sortMs, vals: initVals };
      }
      var b = buckets[info.key];
      names.forEach(function (nm) {
        var arr = srcLayers[nm], v = Array.isArray(arr) ? Number(arr[pt.idx]) : 0;
        if (Number.isFinite(v)) b.vals[nm] += v;
      });
    });
    var ordered = Object.keys(buckets).map(function (k) { return buckets[k]; }).sort(function (a, b) { return a.sortMs - b.sortMs; });
    var outDates = ordered.map(function (b) { return b.key; }), outLayers = {};
    names.forEach(function (nm) { outLayers[nm] = ordered.map(function (b) { return Math.round(b.vals[nm] * 1e9) / 1e9; }); });
    return { dates: outDates, layers: outLayers, bin: bin, spanDays: Math.round(spanDays * 100) / 100 };
  }

  function parseCssRgb(str) {
    var s = String(str || '').trim();
    var m3 = s.match(/^#([0-9a-f]{3})$/i);
    if (m3) {
      var h3 = m3[1];
      return [parseInt(h3[0] + h3[0], 16), parseInt(h3[1] + h3[1], 16), parseInt(h3[2] + h3[2], 16)];
    }
    var m = s.match(/^#([0-9a-f]{6})$/i);
    if (m) return [parseInt(m[1].slice(0, 2), 16), parseInt(m[1].slice(2, 4), 16), parseInt(m[1].slice(4, 6), 16)];
    var r = s.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i);
    return r ? [Number(r[1]), Number(r[2]), Number(r[3])] : null;
  }

  function relLum(rgb) {
    if (!rgb) return 1;
    var f = function (c) { var s = c / 255; return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(rgb[0]) + 0.7152 * f(rgb[1]) + 0.0722 * f(rgb[2]);
  }

  function isValidCellForCol(c) {
    return Array.isArray(c) && c[0] != null && c[0] !== '' && Number.isFinite(Number(c[0]));
  }

  /** Trim trailing week columns whose cells lie strictly in the future and provide zero-cell contrast styling. */
  function trimTrailingFutureWeeks(weeks, cells, opts) {
    var wkList = Array.isArray(weeks) ? weeks.slice() : [], cellList = Array.isArray(cells) ? cells.filter(isValidCellForCol) : [];
    var cfg = opts || {};
    var todayMs = cfg.today != null ? parseUtcMs(cfg.today) : Date.now();
    var cutoff = Number.isFinite(todayMs) ? todayMs : Date.now();
    var endCol = wkList.length;
    while (endCol > 0) {
      var wkMs = parseUtcMs(wkList[endCol - 1]);
      var colHasData = cellList.some(function (c) {
        if (Number(c[0]) !== endCol - 1 || c.future || c[2] == null) return false;
        var v = Number(c[2]);
        return Number.isFinite(v) && v !== 0;
      });
      if ((Number.isFinite(wkMs) && wkMs > cutoff) || (!colHasData && cfg.dropEmptyTrailing)) endCol -= 1;
      else break;
    }
    return {
      weeks: wkList.slice(0, endCol),
      cells: cellList.filter(function (c) { var col = Number(c[0]); return col >= 0 && col < endCol; }),
    };
  }

  function heatmapZeroCellStyle(cardBg, borderHairline) {
    var lum = relLum(parseCssRgb(cardBg) || [255, 255, 255]);
    var isDark = lum < 0.2;
    var fill = isDark ? '#435266' : '#E2E8F0';
    var bd = borderHairline && String(borderHairline).trim().toLowerCase() !== fill.toLowerCase() ? borderHairline : (isDark ? '#64748B' : '#CBD5E1');
    if (isDark && bd.toLowerCase() === '#1e293b') bd = '#64748B';
    return {
      fill: fill,
      borderColor: bd,
      borderWidth: 1,
      labelColor: isDark ? '#F1F5F9' : '#0F172A',
      minDeltaLuminance: 0.06,
    };
  }

  var api = {
    parseUtcMs: parseUtcMs,
    binTimeSeries: binTimeSeries,
    trimTrailingFutureWeeks: trimTrailingFutureWeeks,
    heatmapZeroCellStyle: heatmapZeroCellStyle,
  };
  root.QuietTimeBinning = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
}(typeof window !== 'undefined' ? window : globalThis));


// SPDX-License-Identifier: Apache-2.0
(function (root) {
  'use strict';

  function ensureGridContainLabel(opt) {
    if (!opt) return opt;
    if (Array.isArray(opt.grid)) opt.grid = opt.grid.map(function (g) { return Object.assign({ containLabel: true }, g || {}); });
    else if (opt.grid && typeof opt.grid === 'object') opt.grid = Object.assign({ containLabel: true }, opt.grid);
    return opt;
  }

  function applyNiceLinearAxisBounds(opt, payload) {
    if (!opt || !payload || !root.QuietSvgLayout || (payload.y && (payload.y.log || payload.y.logMapped))) return opt;
    var yAxes = Array.isArray(opt.yAxis) ? opt.yAxis : (opt.yAxis ? [opt.yAxis] : []);
    if (!yAxes[0] || yAxes[0].type !== 'value' || yAxes[0].max !== undefined) return opt;
    var vals = [];
    (payload.series || []).forEach(function (sr) {
      (sr.data || []).forEach(function (pt) {
        var raw = Array.isArray(pt) ? pt[1] : (pt && typeof pt === 'object' ? pt.value : pt);
        if (raw !== null && raw !== undefined && raw !== '' && typeof raw !== 'boolean' && Number.isFinite(Number(raw))) vals.push(Number(raw));
      });
    });
    (payload.envelopes || []).forEach(function (env) { if (typeof env.value === 'number' && Number.isFinite(env.value)) vals.push(env.value); });
    if (vals.length) {
      var rawMin = Math.min.apply(null, vals), rawMax = Math.max.apply(null, vals);
      var lo = yAxes[0].min !== undefined ? Number(yAxes[0].min) : rawMin, span = rawMax - rawMin;
      var hi = rawMax + (span > 0 ? span * 0.06 : (Math.abs(rawMax) * 0.06 || 1));
      var sc = root.QuietSvgLayout.niceScale125(lo, hi, { targetTicks: 5, includeZero: lo >= 0 });
      if (yAxes[0].min === undefined) yAxes[0].min = sc.min;
      yAxes[0].max = sc.max;
      if (yAxes[0].interval === undefined) yAxes[0].interval = sc.step;
    }
    return opt;
  }

  function applySafeMarkLines(opt, tokens) {
    if (!opt || !Array.isArray(opt.series)) return opt;
    var haloBg = (tokens && tokens.bgSurface) ? tokens.bgSurface : '#FFFFFF';
    opt.series.forEach(function (sr) {
      if (!sr || !sr.markLine || !Array.isArray(sr.markLine.data)) return;
      var parentLbl = sr.markLine.label || {};
      sr.markLine.data = sr.markLine.data.map(function (entry) {
        if (!entry || typeof entry !== 'object' || entry.xAxis !== undefined || (parentLbl.position && !(entry.label && entry.label.position))) return entry;
        var lbl = Object.assign({}, entry.label || {}), rawTxt = String(lbl.formatter || entry.name || '').toLowerCase();
        if (!lbl.position) lbl.position = rawTxt.indexOf('floor') >= 0 ? 'insideStartBottom' : 'insideEndTop';
        if (lbl.distance === undefined) lbl.distance = 4;
        if (!lbl.fontSize || lbl.fontSize < 11) lbl.fontSize = 11;
        if (!lbl.backgroundColor) lbl.backgroundColor = haloBg;
        if (!lbl.padding) lbl.padding = [2, 5];
        if (!lbl.borderRadius) lbl.borderRadius = 2;
        return Object.assign({}, entry, { label: lbl });
      });
    });
    return opt;
  }

  function applySafeLegendLayout(opt, containerWidth) {
    if (!opt || !opt.legend) return opt;
    var yAxes = Array.isArray(opt.yAxis) ? opt.yAxis : (opt.yAxis ? [opt.yAxis] : []);
    var baseGridIdx = (yAxes[0] && yAxes[0].gridIndex) || 0;
    var hasRightYAxis = yAxes.length > 1 && yAxes.some(function (ax, idx) {
      return !!ax && (ax.position === 'right' || (idx > 0 && (ax.gridIndex === undefined || ax.gridIndex === baseGridIdx)));
    });
    var w = Number(containerWidth || 0), isNarrow = w > 0 && w < 640;
    var legends = Array.isArray(opt.legend) ? opt.legend : [opt.legend];
    var needBottomPad = false, maxItems = 0;
    legends.forEach(function (lg) {
      if (!lg || typeof lg !== 'object' || lg.show === false) return;
      maxItems = Math.max(maxItems, Array.isArray(lg.data) ? lg.data.length : (Array.isArray(opt.series) ? opt.series.length : 0));
      var isScroll = lg.type === 'scroll', optInScroll = !!(lg.quietAllowScroll || lg.allowScroll);
      if (isScroll && (isNarrow || !optInScroll)) {
        lg.type = 'plain';
        if (lg.orient === 'vertical') lg.orient = 'horizontal';
        delete lg.top; lg.bottom = 0; lg.left = 'center'; delete lg.right;
        if (lg.itemGap == null) lg.itemGap = 10;
        needBottomPad = true;
      } else if (hasRightYAxis && lg.bottom == null) {
        if (lg.orient === 'vertical') lg.orient = 'horizontal';
        delete lg.top; lg.bottom = 0;
        if (lg.left == null || lg.left === 'right' || typeof lg.left === 'number') { lg.left = 'center'; delete lg.right; }
        needBottomPad = true;
      } else if (hasRightYAxis && lg.bottom != null) { needBottomPad = true; }
    });
    if (needBottomPad) {
      var minBot = (isNarrow && maxItems >= 3) ? 46 : 38;
      if (Array.isArray(opt.grid) && opt.grid.length) {
        var gi = opt.grid.length - 1;
        if (opt.grid[gi] && typeof opt.grid[gi] === 'object') opt.grid[gi] = Object.assign({ containLabel: true }, opt.grid[gi], { bottom: Math.max(Number(opt.grid[gi].bottom) || 0, minBot) });
      } else if (opt.grid && typeof opt.grid === 'object') {
        opt.grid = Object.assign({ containLabel: true }, opt.grid, { bottom: Math.max(Number(opt.grid.bottom) || 0, minBot) });
      } else opt.grid = { containLabel: true, bottom: minBot };
    }
    return opt;
  }

  function normalizeOption(opt, payload, tokens, containerWidth) {
    if (!opt) return opt;
    ensureGridContainLabel(opt);
    applySafeMarkLines(opt, tokens);
    applySafeLegendLayout(opt, containerWidth);
    if (payload && (payload.kind === 'cartesian' || !payload.kind)) applyNiceLinearAxisBounds(opt, payload);
    return opt;
  }

  function getTimeBinning() {
    if (root.QuietTimeBinning) return root.QuietTimeBinning;
    if (typeof require === 'function') { try { return require('./quiet-time-binning.js'); } catch (_err) {} }
    return null;
  }

  function parseUtcMs(raw) {
    var tb = getTimeBinning();
    if (tb && tb.parseUtcMs) return tb.parseUtcMs(raw);
    if (typeof raw === 'number') return Number.isFinite(raw) ? raw : NaN;
    var ts = Date.parse(String(raw || ''));
    return Number.isFinite(ts) ? ts : NaN;
  }

  function binTimeSeries(dates, layersObj, opts) {
    var tb = getTimeBinning();
    return tb ? tb.binTimeSeries(dates, layersObj, opts) : { dates: dates || [], layers: layersObj || {}, bin: '1h', spanDays: 0 };
  }

  function getSvgLayout() {
    if (root.QuietSvgLayout) return root.QuietSvgLayout;
    if (typeof require === 'function') { try { return require('./quiet-svg-chart-layout.js'); } catch (_err) {} }
    return null;
  }

  function toMatrix(matrixOrList, opts) {
    if (!Array.isArray(matrixOrList) || !matrixOrList.length) return [];
    if (Array.isArray(matrixOrList[0])) return matrixOrList;
    return (opts && opts.orientation === 'row') ? [matrixOrList] : matrixOrList.map(function (opt) { return [opt]; });
  }

  function inferAxisUnit(opt, ax, optKey, axKey) {
    if (opt && opt[optKey]) return String(opt[optKey]).trim();
    if (ax && ax[axKey]) return String(ax[axKey]).trim();
    if (ax && ax.name) {
      var m = String(ax.name).match(/(?:\(([^)]+)\)|\/\s*([^\s/]+))\s*$/);
      if (m) return (m[1] || m[2]).trim();
    }
    return '__default__';
  }

  function classifyXFormat(arr) {
    var list = Array.isArray(arr) ? arr.filter(function (v) { return v !== null && v !== undefined && String(v).trim() !== ''; }) : [];
    if (!list.length) return 'empty';
    var counts = { iso_date: 0, iso_week: 0, clock_hour: 0, weekday: 0, cat: 0 };
    list.forEach(function (v) {
      var s = String(v).trim();
      if (/^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2})?/.test(s)) counts.iso_date += 1;
      else if (/^\d{4}-W\d{2}$/.test(s)) counts.iso_week += 1;
      else if (/^(?:\d{1,2}h|\d{1,2}:\d{2})$/i.test(s)) counts.clock_hour += 1;
      else if (/^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)$/i.test(s)) counts.weekday += 1;
      else counts.cat += 1;
    });
    var best = 'cat', bestN = 0;
    Object.keys(counts).forEach(function (k) { if (counts[k] > bestN) { bestN = counts[k]; best = k; } });
    return best;
  }

  function syncColumnXSpans(mat, opts) {
    var cols = mat.reduce(function (m, r) { return Math.max(m, r.length); }, 0);
    var fillVal = opts && opts.fillValue !== undefined ? opts.fillValue : 0, forcedX = (opts && (opts.timeGrid || opts.xBuckets)) || null;
    for (var c = 0; c < cols; c += 1) {
      var groups = {};
      for (var r = 0; r < mat.length; r += 1) {
        var opt = mat[r] && mat[r][c], xAx = opt && (Array.isArray(opt.xAxis) ? opt.xAxis[0] : opt.xAxis);
        if (!xAx || opt.independentXSpan || xAx.quietIndependentSpan) continue;
        var evKey = opt.eventKey != null ? opt.eventKey : (opts && opts.eventKey != null ? opts.eventKey : '');
        var xKey = inferAxisUnit(opt, xAx, 'xUnit', 'quietUnit') + '|' + String(evKey) + '|' + String(xAx.type || 'category');
        if (!groups[xKey]) groups[xKey] = [];
        groups[xKey].push({ opt: opt, xAx: xAx });
      }
      Object.keys(groups).forEach(function (k) {
        var grp = groups[k];
        if (grp.length < 2 && !forcedX) return;
        var xType = grp[0].xAx.type || 'category';
        if (xType === 'category') {
          if (!forcedX && grp.length >= 2) {
            var fmts = Object.create(null);
            grp.forEach(function (entry) { var fm = classifyXFormat(entry.xAx.data); if (fm !== 'empty') fmts[fm] = true; });
            if (Object.keys(fmts).length > 1) { grp.forEach(function (entry) { entry.opt.independentXSpan = true; }); return; }
          }
          var seen = Object.create(null), union = forcedX ? forcedX.slice() : [];
          if (!forcedX) {
            grp.forEach(function (e) { (e.xAx.data || []).forEach(function (l) { var sk = String(l); if (!seen[sk]) { seen[sk] = true; union.push(l); } }); });
            if (union.length > 1 && union.every(function (v) { return typeof v === 'number' || /^\d{4}-\d{2}-\d{2}|^\d{4}-W\d{2}|^\d{1,2}:\d{2}/.test(String(v)); })) {
              union.sort(function (a, b) {
                if (typeof a === 'number' && typeof b === 'number') return a - b;
                var ta = parseUtcMs(String(a)), tb = parseUtcMs(String(b));
                return (Number.isFinite(ta) && Number.isFinite(tb)) ? ta - tb : String(a).localeCompare(String(b));
              });
            }
          }
          grp.forEach(function (entry) {
            var oldCats = Array.isArray(entry.xAx.data) ? entry.xAx.data : [];
            (entry.opt.series || []).forEach(function (sr) {
              if (!Array.isArray(sr.data)) return;
              var byCat = Object.create(null);
              sr.data.forEach(function (pt, idx) {
                if (Array.isArray(pt)) byCat[String(pt[0])] = pt[1];
                else if (idx < oldCats.length) byCat[String(oldCats[idx])] = pt;
              });
              if (oldCats.length || sr.data.every(function (pt) { return Array.isArray(pt); })) {
                sr.data = union.map(function (b) { var bk = String(b); return Object.prototype.hasOwnProperty.call(byCat, bk) ? byCat[bk] : fillVal; });
              }
            });
            entry.xAx.data = union.slice();
          });
        } else if (xType === 'time' || xType === 'value') {
          var isT = xType === 'time', xs = [];
          var parseX = function (rawV) {
            if (rawV === null || rawV === undefined || rawV === '' || typeof rawV === 'boolean') return NaN;
            return isT ? parseUtcMs(rawV) : Number(rawV);
          };
          grp.forEach(function (entry) {
            [entry.xAx.min, entry.xAx.max].forEach(function (v) { var n = parseX(v); if (Number.isFinite(n)) xs.push(n); });
            (entry.opt.series || []).forEach(function (sr) {
              (sr.data || []).forEach(function (pt) {
                var rawX = Array.isArray(pt) ? pt[0] : (pt && typeof pt === 'object' && Array.isArray(pt.value) ? pt.value[0] : NaN);
                var xv = parseX(rawX);
                if (Number.isFinite(xv)) xs.push(xv);
              });
            });
          });
          if (forcedX && forcedX.length) {
            [forcedX[0], forcedX[forcedX.length - 1]].forEach(function (v) { var n = parseX(v); if (Number.isFinite(n)) xs.push(n); });
          }
          if (xs.length) {
            var loX = Math.min.apply(null, xs), hiX = Math.max.apply(null, xs);
            grp.forEach(function (entry) { entry.xAx.min = loX; entry.xAx.max = hiX; });
          }
        }
      });
    }
  }

  function collectAxisYValues(opt, axisIdx) {
    var vals = [], stackPos = {}, stackNeg = {};
    (opt.series || []).forEach(function (sr) {
      if (!sr || Number(sr.yAxisIndex || 0) !== axisIdx) return;
      var sKey = sr.stack ? String(sr.stack) : null;
      if (sKey && !stackPos[sKey]) { stackPos[sKey] = {}; stackNeg[sKey] = {}; }
      (sr.data || []).forEach(function (pt, idx) {
        var raw = Array.isArray(pt) ? pt[1] : (pt && typeof pt === 'object' ? (Array.isArray(pt.value) ? pt.value[1] : pt.value) : pt);
        if (raw === null || raw === undefined || raw === '' || typeof raw === 'boolean') return;
        var v = Number(raw);
        if (!Number.isFinite(v)) return;
        if (sKey) {
          var bk = Array.isArray(pt) ? String(pt[0]) : (pt && typeof pt === 'object' && Array.isArray(pt.value) ? String(pt.value[0]) : String(idx));
          if (v >= 0) stackPos[sKey][bk] = (stackPos[sKey][bk] || 0) + v; else stackNeg[sKey][bk] = (stackNeg[sKey][bk] || 0) + v;
        } else vals.push(v);
      });
      if (sr.markLine && Array.isArray(sr.markLine.data)) {
        sr.markLine.data.forEach(function (ml) { var mv = ml && ml.yAxis !== undefined ? Number(ml.yAxis) : NaN; if (Number.isFinite(mv)) vals.push(mv); });
      }
    });
    [stackPos, stackNeg].forEach(function (map) {
      Object.keys(map).forEach(function (sk) { Object.keys(map[sk]).forEach(function (bk) { vals.push(map[sk][bk]); }); });
    });
    return vals;
  }

  function syncUnitYSpans(mat, opts, svgLayout) {
    if (!svgLayout || (opts && opts.alignY === false)) return;
    var groups = {};
    mat.forEach(function (row) {
      row.forEach(function (opt) {
        if (!opt) return;
        var yAxes = Array.isArray(opt.yAxis) ? opt.yAxis : (opt.yAxis ? [opt.yAxis] : []), y0 = yAxes[0];
        if (!y0 || (y0.type && y0.type !== 'value') || opt.independentYSpan || y0.quietZoomedScale || y0.quietIndependentSpan) return;
        var uk = inferAxisUnit(opt, y0, 'yUnit', 'quietUnit');
        if (!groups[uk]) groups[uk] = [];
        groups[uk].push({ opt: opt, y0: y0 });
      });
    });
    Object.keys(groups).forEach(function (uk) {
      var grp = groups[uk], allVals = [];
      grp.forEach(function (entry) { Array.prototype.push.apply(allVals, collectAxisYValues(entry.opt, 0)); });
      if (!allVals.length) return;
      var sc = svgLayout.sharedNiceScale125(allVals, { targetTicks: (opts && opts.targetYTicks) || 5, includeZero: opts ? opts.includeZero : undefined, headroomRatio: (opts && opts.headroomRatio != null) ? opts.headroomRatio : 0.06 });
      grp.forEach(function (entry) {
        var hadMax = entry.y0.max !== undefined;
        if (grp.length > 1 || entry.y0.min === undefined) entry.y0.min = sc.min;
        if (grp.length > 1 || !hadMax) entry.y0.max = sc.max;
        if (grp.length > 1 || (!hadMax && entry.y0.interval === undefined)) entry.y0.interval = sc.step;
      });
    });
  }

  function formatAxisTickList(ax, fallbackVals, svgLayout) {
    var lo = ax && ax.min != null && Number.isFinite(Number(ax.min)) ? Number(ax.min) : (fallbackVals.length ? Math.min.apply(null, fallbackVals) : 0);
    var hi = ax && ax.max != null && Number.isFinite(Number(ax.max)) ? Number(ax.max) : (fallbackVals.length ? Math.max.apply(null, fallbackVals) : 100);
    var sc = svgLayout ? svgLayout.niceScale125(lo, hi, { targetTicks: 5 }) : { ticks: [lo, hi], step: (hi - lo) || 1 };
    var fmt = ax && ax.axisLabel && typeof ax.axisLabel.formatter === 'function' ? ax.axisLabel.formatter : null;
    return sc.ticks.map(function (v) { return fmt ? String(fmt(v)) : (svgLayout ? svgLayout.formatTick(v, sc.step) : String(v)); });
  }

  function measureYAxisDescriptor(ax, fallbackVals, svgLayout) {
    if (ax && ax.type === 'category' && Array.isArray(ax.data) && ax.data.length && svgLayout && svgLayout.measureCategoryGutter) {
      var al = ax.axisLabel || {};
      var mg = svgLayout.measureCategoryGutter(ax.data, { fontFamily: al.fontFamily, fontSize: al.fontSize, axisLabelMargin: al.margin });
      return { ticks: mg.wrappedLabels, minGutter: mg.gutterPx };
    }
    return { ticks: formatAxisTickList(ax, fallbackVals, svgLayout), minGutter: 0 };
  }

  var _baseGridMap = typeof WeakMap === 'function' ? new WeakMap() : null;

  function alignPlotGridFrames(matrixOrList, opts) {
    var cfg = opts || {}, svgLayout = getSvgLayout(), mat = toMatrix(matrixOrList, cfg);
    if (!mat.length) return matrixOrList;
    mat.forEach(function (row) {
      row.forEach(function (opt) {
        if (!opt) return;
        var rawG = Array.isArray(opt.grid) ? (opt.grid[0] || {}) : (opt.grid || {});
        if (_baseGridMap && !_baseGridMap.has(opt)) _baseGridMap.set(opt, Object.assign({}, rawG));
        applySafeMarkLines(opt, cfg.tokens);
        applySafeLegendLayout(opt, cfg.containerWidth);
      });
    });
    var collapseCols = !!(cfg.collapseColumns || (Number(cfg.containerWidth || 0) > 0 && Number(cfg.containerWidth) < (cfg.stackBreakpoint || 780)));
    var spanMat = collapseCols ? mat.reduce(function (a, r) { r.forEach(function (o) { if (o) a.push([o]); }); return a; }, []) : mat;
    syncColumnXSpans(spanMat, cfg);
    syncUnitYSpans(mat, cfg, svgLayout);
    if (!svgLayout) return matrixOrList;
    var descMat = mat.map(function (row) {
      return row.map(function (opt) {
        if (!opt) return null;
        var yAxes = Array.isArray(opt.yAxis) ? opt.yAxis : (opt.yAxis ? [opt.yAxis] : []), xAx = Array.isArray(opt.xAxis) ? opt.xAxis[0] : opt.xAxis;
        var g0 = Array.isArray(opt.grid) ? (opt.grid[0] || {}) : (opt.grid || {}), baseG = (_baseGridMap && _baseGridMap.get(opt)) || g0;
        var lg = Array.isArray(opt.legend) ? opt.legend[0] : opt.legend, lgOn = !!(lg && lg.show !== false);
        var hasBotLg = !!(lgOn && (lg.bottom != null || lg.top === 'bottom')), hasTopLg = !!(lgOn && !hasBotLg);
        var lgItems = Array.isArray(lg && lg.data) ? lg.data.length : (Array.isArray(opt.series) ? opt.series.length : 0);
        var lgBotFloor = hasBotLg ? (((Number(cfg.containerWidth || 0) > 0 && Number(cfg.containerWidth) < 640) && lgItems >= 3) ? 46 : 38) : 0;
        var baseBot = typeof baseG.bottom === 'number' ? baseG.bottom : null, y0 = yAxes[0] || {}, y1 = yAxes.length > 1 ? yAxes[1] : null;
        var primDesc = measureYAxisDescriptor(y0, collectAxisYValues(opt, 0), svgLayout);
        var secDesc = y1 ? measureYAxisDescriptor(y1, collectAxisYValues(opt, 1).length ? collectAxisYValues(opt, 1) : [0, 100], svgLayout) : { ticks: [], minGutter: 0 };
        var titleObj = Array.isArray(opt.title) ? opt.title[0] : opt.title;
        var hasTopYName = !!(y0.name && (!y0.nameLocation || y0.nameLocation === 'end'));
        if (hasTopYName && (y0.nameGap == null || Number(y0.nameGap) < 12)) y0.nameGap = 12;
        return {
          yTicks: primDesc.ticks, rightTicks: secDesc.ticks, hasRightAxis: !!y1, rightTitle: y1 ? y1.name : '',
          yLabel: y0.name && y0.nameLocation === 'middle' ? y0.name : '', hasTopYName: hasTopYName,
          titleHeight: (titleObj && titleObj.show !== false && titleObj.text) ? 28 : 0,
          xTicks: xAx && Array.isArray(xAx.data) && xAx.data.length ? xAx.data : ['0', '1'], xLabel: xAx && xAx.name ? xAx.name : '',
          hasTopLegend: hasTopLg, hasBottomLegend: hasBotLg, topLegendHeight: hasTopLg ? 28 : 0, bottomLegendHeight: lgBotFloor,
          minLeft: Math.max(typeof baseG.left === 'number' ? baseG.left : (cfg.minLeft || 44), primDesc.minGutter),
          minRight: Math.max(typeof baseG.right === 'number' ? baseG.right : (cfg.minRight || (y1 ? 48 : 16)), secDesc.minGutter),
          minTop: Math.max(typeof baseG.top === 'number' ? baseG.top : (cfg.minTop || 24), hasTopYName ? 30 : 24),
          minBottom: Math.max(baseBot !== null ? baseBot : (cfg.minBottom || 34), lgBotFloor),
          stageHeight: Number(opt.quietStageHeight || cfg.stageHeight || 0), containerPadX: Number(opt.quietContainerPadX || 0),
        };
      });
    });
    var applyCell = function (opt, cell) {
      if (!opt || !cell) return;
      if (Array.isArray(opt.grid) && opt.grid.length) {
        opt.grid[0] = Object.assign({}, opt.grid[0], { containLabel: false, left: cell.left, right: cell.right, top: cell.top });
        if (opt.grid.length === 1) opt.grid[0].bottom = cell.bottom;
      } else opt.grid = Object.assign({}, opt.grid || {}, { containLabel: false, left: cell.left, right: cell.right, top: cell.top, bottom: cell.bottom });
    };
    var flatIdx = [], gutterInput = collapseCols ? descMat.reduce(function (acc, row, r) {
      row.forEach(function (cell, c) { if (cell) { flatIdx.push([r, c, acc.length]); acc.push([cell]); } });
      return acc;
    }, []) : descMat;
    var gutters = svgLayout.computeGridFrameGutters(gutterInput, Object.assign({ maxLeft: 224 }, cfg));
    if (collapseCols) flatIdx.forEach(function (t) { applyCell(mat[t[0]][t[1]], gutters.cells[t[2]] && gutters.cells[t[2]][0]); });
    else mat.forEach(function (row, r) { row.forEach(function (opt, c) { applyCell(opt, gutters.cells[r] && gutters.cells[r][c]); }); });
    return matrixOrList;
  }

  function observeChartResize(hostEl, chart, opts) {
    if (!hostEl || !chart || typeof chart.resize !== 'function') return function () {};
    var raf = typeof root.requestAnimationFrame === 'function' ? root.requestAnimationFrame.bind(root) : function (fn) { return setTimeout(fn, 16); };
    var cancelRaf = typeof root.cancelAnimationFrame === 'function' ? root.cancelAnimationFrame.bind(root) : clearTimeout;
    var lastW = Math.round(hostEl.clientWidth || 0), rafId = 0, dead = false, ro = null, onWin = null;
    var cleanup = function () {
      dead = true;
      if (rafId) { cancelRaf(rafId); rafId = 0; }
      if (ro) { ro.disconnect(); ro = null; }
      if (onWin && typeof root.removeEventListener === 'function') { root.removeEventListener('resize', onWin); onWin = null; }
    };
    var trigger = function () {
      if (dead || (chart.isDisposed && chart.isDisposed())) { cleanup(); return; }
      if (rafId) return;
      rafId = raf(function () {
        rafId = 0;
        if (dead || (chart.isDisposed && chart.isDisposed())) { cleanup(); return; }
        var w = Math.round(hostEl.clientWidth || 0);
        if (w <= 0 || w === lastW) return;
        lastW = w;
        if (opts && typeof opts.onResize === 'function') opts.onResize(w, chart, hostEl); else chart.resize();
      });
    };
    if (typeof root.ResizeObserver === 'function') {
      ro = new root.ResizeObserver(function () {
        if (dead || (chart.isDisposed && chart.isDisposed())) { cleanup(); return; }
        var w = Math.round(hostEl.clientWidth || 0);
        if (w > 0 && w !== lastW) trigger();
      });
      ro.observe(hostEl);
      return cleanup;
    }
    if (typeof root.addEventListener === 'function') { onWin = trigger; root.addEventListener('resize', onWin); }
    return cleanup;
  }

  function alignSharedAxes(optionsArray, opts) { return alignPlotGridFrames(optionsArray, Object.assign({ orientation: 'column' }, opts || {})); }
  function trimTrailingFutureWeeks(weeks, cells, opts) {
    var tb = getTimeBinning();
    return (tb && typeof tb.trimTrailingFutureWeeks === 'function')
      ? tb.trimTrailingFutureWeeks(weeks, cells, opts)
      : { weeks: Array.isArray(weeks) ? weeks.slice() : [], cells: Array.isArray(cells) ? cells.slice() : [] };
  }

  var api = {
    ensureGridContainLabel: ensureGridContainLabel, applyNiceLinearAxisBounds: applyNiceLinearAxisBounds,
    applySafeMarkLines: applySafeMarkLines, applySafeLegendLayout: applySafeLegendLayout,
    alignPlotGridFrames: alignPlotGridFrames, alignSharedAxes: alignSharedAxes,
    observeChartResize: observeChartResize, normalizeOption: normalizeOption,
    binTimeSeries: binTimeSeries, trimTrailingFutureWeeks: trimTrailingFutureWeeks,
  };
  root.QuietEChartsDefaults = Object.assign(root.QuietEChartsDefaults || {}, api);
  if (typeof module === 'object' && module.exports) module.exports = api;
}(typeof window !== 'undefined' ? window : globalThis));


// SPDX-License-Identifier: Apache-2.0
(function (root) {
  'use strict';

  function readThemeTokens(doc) {
    var d = doc || (typeof document !== 'undefined' ? document : null);
    var cs = (d && d.documentElement && typeof getComputedStyle === 'function')
      ? getComputedStyle(d.documentElement) : null;
    var pick = function (tok, fb) {
      try {
        var v = cs ? cs.getPropertyValue(tok).trim() : '';
        return v || fb;
      } catch (_e) {
        return fb;
      }
    };
    return {
      textPrimary: pick('--text-primary', '#0F172A'),
      textSecondary: pick('--text-secondary', '#475569'),
      borderHairline: pick('--border-hairline', '#E2E8F0'),
      borderStrong: pick('--border-strong', '#94A3B8'),
      bgSurface: pick('--bg-surface', '#FFFFFF'),
      bgElevated: pick('--bg-elevated', '#F8FAFC'),
      accentFocal: pick('--accent-focal', '#1D4ED8'),
    };
  }

  function nice125(lo, hi, targetTicks) {
    if (root.QuietSvgLayout && typeof root.QuietSvgLayout.niceScale125 === 'function') {
      return root.QuietSvgLayout.niceScale125(lo, hi, { targetTicks: targetTicks || 5, includeZero: lo >= 0 });
    }
    var a = lo >= 0 ? 0 : lo;
    var span = Math.max(1e-9, hi - a);
    var raw = span / Math.max(2, (targetTicks || 5) - 1);
    var p = Math.pow(10, Math.floor(Math.log10(raw)));
    var f = raw / p;
    var m = f <= 1 ? 1 : (f <= 2 ? 2 : (f <= 5 ? 5 : 10));
    var step = m * p;
    var sMin = Math.floor(a / step) * step;
    var sMax = Math.ceil(hi / step) * step;
    return { min: sMin, max: sMax === sMin ? sMin + step : sMax, step: step };
  }

  function finiteNum(v) {
    if (v === null || v === undefined || v === '' || typeof v === 'boolean') return null;
    var n = Number(v);
    return Number.isFinite(n) ? n : null;
  }

  function normalizeCyclicalBuckets(buckets) {
    return (Array.isArray(buckets) ? buckets : []).map(function (b, idx) {
      var item = b && typeof b === 'object' ? b : {};
      var label = String(item.label != null ? item.label : (item.slot != null ? item.slot : (item.hour != null ? item.hour : (item.day != null ? item.day : idx))));
      var vals = Array.isArray(item.values) ? item.values.map(finiteNum).filter(function (v) { return v !== null; }) : [];
      var rawN = [item.activeDays, item.active_days, item.nActive, item.n_active, item.n, item.samples].find(function (v) { return v != null; });
      var activeDays = finiteNum(rawN);
      var min = finiteNum(item.min);
      var max = finiteNum(item.max);
      var avg = finiteNum(item.avg != null ? item.avg : item.mean);
      var recent = finiteNum(item.recent != null ? item.recent : (item.last24h != null ? item.last24h : (item.current != null ? item.current : item.today)));
      if (vals.length) {
        if (min === null) min = Math.min.apply(null, vals);
        if (max === null) max = Math.max.apply(null, vals);
        if (avg === null) avg = vals.reduce(function (s, x) { return s + x; }, 0) / vals.length;
        if (activeDays === null) activeDays = vals.length;
      }
      if (min !== null && max !== null && min > max) {
        var t = min; min = max; max = t;
      }
      if (avg === null && min !== null && max !== null) avg = (min + max) * 0.5;
      if (min !== null && max === null) max = avg !== null ? Math.max(min, avg) : min;
      if (max !== null && min === null) min = avg !== null ? Math.min(max, avg) : max;
      var hasObs = (activeDays === null || activeDays > 0) && min !== null && max !== null;
      return {
        idx: idx,
        label: label,
        min: hasObs ? min : null,
        avg: hasObs ? avg : null,
        max: hasObs ? max : null,
        recent: recent,
        activeDays: activeDays !== null ? activeDays : (hasObs ? 1 : 0),
      };
    });
  }

  function buildCyclicalWhiskerOption(buckets, opts) {
    var cfg = opts || {};
    var tok = cfg.tokens || readThemeTokens(cfg.document);
    var rows = normalizeCyclicalBuckets(buckets);
    var labels = rows.map(function (r) { return r.label; });
    var yVals = [];
    rows.forEach(function (r) {
      [r.min, r.avg, r.max, r.recent].forEach(function (v) { if (v !== null) yVals.push(v); });
    });
    var rawLo = yVals.length ? Math.min.apply(null, yVals) : 0;
    var rawHi = yVals.length ? Math.max.apply(null, yVals) : 10;
    var span = rawHi - rawLo;
    var padHi = rawHi + (span > 0 ? span * 0.08 : (Math.abs(rawHi) * 0.08 || 1));
    var ySc = nice125(rawLo >= 0 ? 0 : rawLo, padHi, 5);
    var unit = String(cfg.unit || '').trim();
    var rangeLabel = String(cfg.rangeLabel || 'Min–Max');
    var avgLabel = String(cfg.avgLabel || 'Active Avg');
    var recentLabel = String(cfg.recentLabel || 'Last 24h');
    var showLegend = cfg.showLegend !== false;
    var cw = Number(cfg.containerWidth || 640);
    var xInterval = cfg.xInterval !== undefined ? cfg.xInterval : (labels.length > 16 ? (cw < 480 ? 3 : 2) : 0);
    var yName = String(cfg.yName || (unit ? 'Activity / (' + unit + ')' : 'Per-Day Activity'));

    var stemData = rows.map(function (r) {
      return r.min === null ? [r.idx, null, null, null, r.recent, r.activeDays] : [r.idx, r.min, r.max, r.avg, r.recent, r.activeDays];
    });
    var avgData = rows.map(function (r) { return r.avg === null ? [r.idx, null] : [r.idx, r.avg]; });
    var recentData = rows.map(function (r) { return r.recent === null ? [r.idx, null] : [r.idx, r.recent]; });
    var fmtVal = function (v) {
      if (v === null || v === undefined || !Number.isFinite(Number(v))) return '—';
      var n = Number(v), absN = Math.abs(n);
      var s = absN > 0 && absN < 1 ? n.toFixed(2).replace(/0+$/, '').replace(/\.$/, '') : (Math.abs(n - Math.round(n)) < 0.05 ? String(Math.round(n)) : n.toFixed(1));
      return s + (unit ? ' ' + unit : '');
    };

    var opt = {
      animation: false,
      backgroundColor: 'transparent',
      textStyle: { fontFamily: 'Inter, system-ui, sans-serif', color: tok.textPrimary },
      tooltip: {
        trigger: 'axis',
        renderMode: 'richText',
        confine: true,
        backgroundColor: tok.bgElevated,
        borderColor: tok.borderStrong,
        borderWidth: 1,
        textStyle: { color: tok.textPrimary, fontSize: 12 },
        formatter: function (params) {
          var first = Array.isArray(params) ? params[0] : params;
          var idx = first && first.dataIndex != null ? Number(first.dataIndex) : 0;
          var r = rows[idx];
          if (!r) return '';
          var hdr = r.label + (r.activeDays ? ' (n=' + r.activeDays + ' active days)' : ' (0 active days)');
          if (r.min === null) return hdr + '\nNo observations recorded';
          return [
            hdr,
            rangeLabel + ': ' + fmtVal(r.min) + ' – ' + fmtVal(r.max),
            avgLabel + ': ' + fmtVal(r.avg),
            recentLabel + ': ' + fmtVal(r.recent),
          ].join('\n');
        },
      },
      legend: {
        show: showLegend,
        bottom: 0,
        left: 'center',
        itemWidth: 14,
        itemHeight: 8,
        itemGap: 14,
        textStyle: { color: tok.textSecondary, fontSize: 11 },
        data: [rangeLabel, avgLabel, recentLabel],
      },
      grid: { left: 48, right: 16, top: 32, bottom: showLegend ? 56 : 36, containLabel: true },
      xAxis: {
        type: 'category',
        name: String(cfg.xName || ''),
        nameLocation: 'middle',
        nameGap: 24,
        data: labels,
        axisLine: { lineStyle: { color: tok.textSecondary } },
        axisTick: { alignWithLabel: true },
        axisLabel: { color: tok.textSecondary, fontSize: 11, interval: xInterval, hideOverlap: true },
      },
      yAxis: {
        type: 'value',
        name: yName,
        nameLocation: 'end',
        nameGap: 12,
        nameTextStyle: { color: tok.textSecondary, fontSize: 11, fontWeight: 600, align: 'left' },
        min: ySc.min,
        max: ySc.max,
        interval: ySc.step,
        axisLine: { lineStyle: { color: tok.textSecondary } },
        axisLabel: { color: tok.textSecondary, fontSize: 11 },
        splitLine: { lineStyle: { color: tok.borderHairline, type: 'dashed' } },
      },
      series: [
        {
          id: 'cyclical-range',
          name: rangeLabel,
          type: 'custom',
          z: 2,
          itemStyle: { color: tok.textSecondary },
          renderItem: function (params, api) {
            var xv = api.value(0), lo = api.value(1), hi = api.value(2);
            if (lo === null || hi === null || !Number.isFinite(lo) || !Number.isFinite(hi)) return null;
            var pLo = api.coord([xv, lo]), pHi = api.coord([xv, hi]);
            if (!pLo || !pHi || !Number.isFinite(pLo[0]) || !Number.isFinite(pLo[1]) || !Number.isFinite(pHi[1])) return null;
            var cs = params && params.coordSys;
            var catW = (cs && labels.length) ? (cs.width / labels.length) : 16;
            var cap = Math.min(4.5, Math.max(2.5, catW * 0.22));
            return {
              type: 'group',
              children: [
                { type: 'line', shape: { x1: pLo[0], y1: pLo[1], x2: pHi[0], y2: pHi[1] }, style: { stroke: tok.textSecondary, lineWidth: 1.5, opacity: 0.72 } },
                { type: 'line', shape: { x1: pHi[0] - cap, y1: pHi[1], x2: pHi[0] + cap, y2: pHi[1] }, style: { stroke: tok.textSecondary, lineWidth: 1.5, opacity: 0.72 } },
                { type: 'line', shape: { x1: pLo[0] - cap, y1: pLo[1], x2: pLo[0] + cap, y2: pLo[1] }, style: { stroke: tok.textSecondary, lineWidth: 1.5, opacity: 0.72 } },
              ],
            };
          },
          data: stemData,
        },
        {
          id: 'cyclical-avg',
          name: avgLabel,
          type: 'custom',
          z: 3,
          itemStyle: { color: tok.textPrimary },
          renderItem: function (params, api) {
            var xv = api.value(0), av = api.value(1);
            if (av === null || !Number.isFinite(av)) return null;
            var pt = api.coord([xv, av]);
            if (!pt || !Number.isFinite(pt[0]) || !Number.isFinite(pt[1])) return null;
            var cs = params && params.coordSys;
            var catW = (cs && labels.length) ? (cs.width / labels.length) : 16;
            var half = Math.min(9, Math.max(4, catW * 0.34));
            return {
              type: 'line',
              shape: { x1: pt[0] - half, y1: pt[1], x2: pt[0] + half, y2: pt[1] },
              style: { stroke: tok.textPrimary, lineWidth: 2.4 },
            };
          },
          data: avgData,
        },
        {
          id: 'cyclical-recent',
          name: recentLabel,
          type: 'scatter',
          z: 4,
          symbol: 'circle',
          symbolSize: 7.5,
          itemStyle: { color: tok.accentFocal, borderColor: tok.bgSurface, borderWidth: 1.5 },
          data: recentData,
        },
      ],
    };
    return opt;
  }

  root.QuietEChartsDefaults = root.QuietEChartsDefaults || {};
  root.QuietEChartsDefaults.buildCyclicalWhiskerOption = buildCyclicalWhiskerOption;
  var api = { buildCyclicalWhiskerOption: buildCyclicalWhiskerOption, normalizeCyclicalBuckets: normalizeCyclicalBuckets };
  root.QuietCyclicalWhiskers = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
}(typeof window !== 'undefined' ? window : globalThis));


// SPDX-License-Identifier: Apache-2.0
(function (root) {
  'use strict';

  function positionPopover(trigger, popover) {
    if (!trigger || !popover) return;
    var hasLinkedAnchor = popover.hasAttribute('popover') && popover.id &&
      trigger.getAttribute('popovertarget') === popover.id &&
      typeof CSS !== 'undefined' && typeof CSS.supports === 'function' &&
      CSS.supports('position-area', 'block-end');
    if (hasLinkedAnchor) return;
    var doc = popover.ownerDocument;
    var tr = trigger.getBoundingClientRect();
    var vw = (root.innerWidth || (doc && doc.documentElement && doc.documentElement.clientWidth) || 1024);
    var vh = (root.innerHeight || (doc && doc.documentElement && doc.documentElement.clientHeight) || 768);
    var isRtl = doc && ((doc.documentElement && doc.documentElement.dir === 'rtl') || doc.dir === 'rtl');
    popover.style.positionArea = 'none';
    popover.style.position = 'fixed';
    var pr = popover.getBoundingClientRect();
    var popW = Math.max(pr.width || 240, 220), popH = Math.max(pr.height || 180, 140);
    var anchorX = isRtl ? (tr.right - popW) : tr.left;
    var left = Math.max(8, Math.min(vw - popW - 8, anchorX));
    var spaceBelow = vh - tr.bottom - 12;
    var spaceAbove = tr.top - 12;
    var top;
    if (popH <= spaceBelow || spaceBelow >= spaceAbove) top = Math.max(8, Math.min(vh - popH - 8, tr.bottom + 6));
    else top = Math.max(8, tr.top - popH - 6);
    popover.style.left = Math.round(left) + 'px';
    popover.style.top = Math.round(top) + 'px';
  }

  function isPopOpen(pop) {
    if (!pop) return false;
    return pop.dataset.open === 'true' || (typeof pop.matches === 'function' && pop.matches(':is(:popover-open, .\\:popover-open)'));
  }

  function closeOtherPopovers(doc, exceptStepper) {
    if (!doc) return;
    doc.querySelectorAll('.va-period-stepper').forEach(function (st) {
      if (st !== exceptStepper) closePopover(st, false);
    });
  }

  function closePopover(stepper, restoreFocus) {
    if (!stepper) return;
    var trigger = stepper.querySelector('.va-period-trigger');
    var pop = stepper.querySelector('.va-preset-popover');
    if (!pop || !isPopOpen(pop)) return;
    pop.dataset.open = 'false';
    if (!(pop.hasAttribute('popover') && trigger && pop.id && trigger.getAttribute('popovertarget') === pop.id)) {
      pop.setAttribute('hidden', '');
    }
    if (pop.hasAttribute('popover') && typeof pop.hidePopover === 'function') {
      try { if (pop.matches(':is(:popover-open, .\\:popover-open)')) pop.hidePopover(); } catch (_e) {}
    }
    if (trigger) {
      trigger.setAttribute('aria-expanded', 'false');
      if (restoreFocus) trigger.focus({ preventScroll: true });
    }
  }

  function openPopover(stepper, focusFirst) {
    if (!stepper) return;
    var trigger = stepper.querySelector('.va-period-trigger');
    var pop = stepper.querySelector('.va-preset-popover');
    if (!trigger || !pop) return;
    closeOtherPopovers(stepper.ownerDocument, stepper);
    pop.removeAttribute('hidden');
    pop.dataset.open = 'true';
    trigger.setAttribute('aria-expanded', 'true');
    if (pop.hasAttribute('popover') && typeof pop.showPopover === 'function') {
      try { if (!pop.matches(':is(:popover-open, .\\:popover-open)')) pop.showPopover({ source: trigger }); } catch (_e) {}
    }
    positionPopover(trigger, pop);
    if (focusFirst) {
      var items = [].slice.call(pop.querySelectorAll('.va-preset-item:not(:disabled)'));
      var active = pop.querySelector('.va-preset-item[aria-checked="true"]:not(:disabled)') || items[0];
      if (active) active.focus({ preventScroll: true });
    }
  }

  function applyPresetChoice(stepper, item) {
    if (!stepper || !item || item.disabled) return;
    var val = item.dataset.preset || item.textContent.trim();
    var lbl = item.dataset.label || item.textContent.trim();
    var spanTxt = item.dataset.span || '';
    stepper.dataset.value = val;
    stepper.querySelectorAll('.va-preset-item').forEach(function (b) {
      b.setAttribute('aria-checked', b === item ? 'true' : 'false');
    });
    var lblEl = stepper.querySelector('[data-period-label]');
    if (lblEl) lblEl.textContent = spanTxt ? (lbl + ' · ' + spanTxt) : lbl;
    var todayBtn = stepper.querySelector('[data-period-today]');
    if (todayBtn) todayBtn.hidden = item.dataset.atToday === 'true';
    closePopover(stepper, true);
    if (typeof root.CustomEvent === 'function') {
      stepper.dispatchEvent(new root.CustomEvent('quiet:period-change', { bubbles: true, detail: { preset: val, label: lbl, span: spanTxt } }));
    }
  }

  function bindStepper(stepper) {
    if (!stepper || stepper.dataset.quietBound === '1') return;
    stepper.dataset.quietBound = '1';
    var doc = stepper.ownerDocument;
    var trigger = stepper.querySelector('.va-period-trigger');
    var pop = stepper.querySelector('.va-preset-popover');
    if (trigger && pop) {
      var isNativeLinked = pop.hasAttribute('popover') && !!pop.id && trigger.getAttribute('popovertarget') === pop.id;
      if (isNativeLinked) {
        pop.removeAttribute('hidden');
        pop.addEventListener('toggle', function (ev) {
          var opening = ev && ev.newState === 'open';
          pop.dataset.open = opening ? 'true' : 'false';
          trigger.setAttribute('aria-expanded', opening ? 'true' : 'false');
          if (opening) {
            closeOtherPopovers(doc, stepper);
            positionPopover(trigger, pop);
          }
        });
      } else {
        trigger.addEventListener('click', function (ev) {
          if (isPopOpen(pop)) closePopover(stepper, false);
          else openPopover(stepper, ev.detail === 0);
        });
      }
      trigger.addEventListener('keydown', function (ev) {
        if (ev.key === 'ArrowDown') { ev.preventDefault(); openPopover(stepper, true); }
        else if (ev.key === 'Escape') { closePopover(stepper, true); }
      });
      pop.addEventListener('keydown', function (ev) {
        var items = [].slice.call(pop.querySelectorAll('.va-preset-item:not(:disabled)'));
        if (ev.key === 'Escape') { ev.preventDefault(); closePopover(stepper, true); return; }
        if (!items.length) return;
        var idx = items.indexOf(doc.activeElement);
        if (ev.key === 'ArrowDown') { ev.preventDefault(); items[(idx + 1) % items.length].focus(); }
        else if (ev.key === 'ArrowUp') { ev.preventDefault(); items[(idx - 1 + items.length) % items.length].focus(); }
        else if (ev.key === 'Home') { ev.preventDefault(); items[0].focus(); }
        else if (ev.key === 'End') { ev.preventDefault(); items[items.length - 1].focus(); }
      });
      pop.addEventListener('click', function (ev) {
        var item = ev.target && ev.target.closest ? ev.target.closest('.va-preset-item') : null;
        if (item) applyPresetChoice(stepper, item);
      });
    }
    stepper.addEventListener('click', function (ev) {
      var stepBtn = ev.target && ev.target.closest ? ev.target.closest('[data-period-step]') : null;
      if (stepBtn && typeof root.CustomEvent === 'function') {
        stepper.dispatchEvent(new root.CustomEvent('quiet:period-change', { bubbles: true, detail: { step: Number(stepBtn.dataset.periodStep || 0), preset: stepper.dataset.value || '' } }));
      }
      var todayBtn = ev.target && ev.target.closest ? ev.target.closest('[data-period-today]') : null;
      if (todayBtn && !todayBtn.hidden) {
        todayBtn.hidden = true;
        if (typeof root.CustomEvent === 'function') {
          stepper.dispatchEvent(new root.CustomEvent('quiet:period-change', { bubbles: true, detail: { today: true, preset: stepper.dataset.value || '' } }));
        }
      }
    });
  }

  function expandActiveBranches(rail) {
    if (!rail) return;
    rail.querySelectorAll('.va-tree-dest[aria-current="page"], .va-tree-dest.is-active').forEach(function (dest) {
      var grp = dest.closest('.va-tree-group, .va-tree-children');
      while (grp && rail.contains(grp)) {
        grp.hidden = false;
        var parentRow = grp.previousElementSibling;
        var caret = parentRow && parentRow.querySelector ? parentRow.querySelector('.va-tree-caret') : null;
        if (caret) caret.setAttribute('aria-expanded', 'true');
        grp = grp.parentElement ? grp.parentElement.closest('.va-tree-group, .va-tree-children') : null;
      }
    });
  }

  function applyTreeChildCaps(rail) {
    if (!rail || !rail.ownerDocument) return;
    var doc = rail.ownerDocument;
    rail.querySelectorAll('.va-tree-children, .va-tree-group').forEach(function (grp) {
      if (grp.dataset.treeCap === 'false' || grp.querySelector(':scope > .va-tree-more')) return;
      var parsedMax = parseInt(grp.dataset.maxVisible || '5', 10);
      var maxVis = Math.max(1, Number.isFinite(parsedMax) ? parsedMax : 5);
      var kids = [].slice.call(grp.children).filter(function (el) {
        return !el.classList.contains('va-tree-more') && !el.classList.contains('va-tree-group') && !el.classList.contains('va-tree-children');
      });
      if (kids.length <= maxVis) return;
      var actIdx = kids.findIndex(function (el) {
        return el.matches('.is-active, [aria-current="page"]') || !!el.querySelector('.is-active, [aria-current="page"]');
      });
      var hiddenKids = [];
      kids.forEach(function (el, idx) {
        var keep = actIdx >= maxVis ? (idx < maxVis - 1 || idx === actIdx) : (idx < maxVis);
        if (!keep) {
          el.hidden = true;
          el.dataset.treeOverflow = '1';
          hiddenKids.push(el);
          var sub = el.nextElementSibling;
          if (sub && (sub.classList.contains('va-tree-group') || sub.classList.contains('va-tree-children')) && !sub.hidden) {
            sub.hidden = true;
            sub.dataset.treeOverflow = '1';
          }
        }
      });
      if (hiddenKids.length) {
        var btn = doc.createElement('button');
        btn.type = 'button';
        btn.className = 'va-tree-more';
        btn.textContent = '+ Show ' + hiddenKids.length + ' older…';
        grp.appendChild(btn);
      }
    });
  }

  function getBackdropFor(rail, doc) {
    if (rail && rail.nextElementSibling && rail.nextElementSibling.classList && rail.nextElementSibling.classList.contains('va-drawer-backdrop')) {
      return rail.nextElementSibling;
    }
    return doc ? doc.querySelector('.va-drawer-backdrop') : null;
  }

  function getTriggersFor(rail, doc) {
    if (!rail || !doc) return [];
    if (rail.id) {
      return [].slice.call(doc.querySelectorAll('[aria-controls="' + rail.id + '"], [data-rail-trigger="' + rail.id + '"]'));
    }
    return [].slice.call(doc.querySelectorAll('[data-rail-trigger=""]'));
  }

  function setRailOpen(rail, backdrop, open, restoreFocus) {
    if (!rail) return;
    if (open) expandActiveBranches(rail);
    rail.dataset.open = open ? 'true' : 'false';
    rail.classList.toggle('is-open', !!open);
    var doc = rail.ownerDocument;
    var isOverlay = rail.dataset.mode === 'overlay' || (root.innerWidth || 1200) < 1080;
    var bd = backdrop || getBackdropFor(rail, doc);
    if (bd) {
      var showBd = !!(open && isOverlay);
      bd.dataset.open = showBd ? 'true' : 'false';
      bd.classList.toggle('is-open', showBd);
    }
    var trigs = getTriggersFor(rail, doc);
    trigs.forEach(function (btn) { btn.setAttribute('aria-expanded', open ? 'true' : 'false'); });
    if (!open && restoreFocus && trigs[0] && typeof trigs[0].focus === 'function') trigs[0].focus({ preventScroll: true });
  }

  function bindRail(rail) {
    if (!rail || rail.dataset.quietBound === '1') return;
    rail.dataset.quietBound = '1';
    applyTreeChildCaps(rail);
    var doc = rail.ownerDocument;
    var backdrop = getBackdropFor(rail, doc);
    if (backdrop) backdrop.addEventListener('click', function () { setRailOpen(rail, backdrop, false, true); });
    rail.addEventListener('click', function (ev) {
      var moreBtn = ev.target && ev.target.closest ? ev.target.closest('.va-tree-more') : null;
      if (moreBtn) {
        var grp = moreBtn.closest('.va-tree-children, .va-tree-group');
        if (grp) {
          var firstShown = null;
          [].slice.call(grp.children).forEach(function (el) {
            if (el.hidden && el.dataset.treeOverflow === '1') {
              el.hidden = false;
              delete el.dataset.treeOverflow;
              if (!firstShown) firstShown = el;
            }
          });
          moreBtn.remove();
          var focusEl = firstShown && (firstShown.matches('button, a') ? firstShown : firstShown.querySelector('button, a'));
          if (focusEl && typeof focusEl.focus === 'function') focusEl.focus({ preventScroll: true });
        }
        return;
      }
      var caret = ev.target && ev.target.closest ? ev.target.closest('.va-tree-caret') : null;
      if (caret) {
        ev.stopPropagation();
        var exp = caret.getAttribute('aria-expanded') === 'true';
        caret.setAttribute('aria-expanded', exp ? 'false' : 'true');
        var row = caret.closest('.va-tree-row');
        var next = row ? row.nextElementSibling : null;
        var sub = (next && (next.classList.contains('va-tree-group') || next.classList.contains('va-tree-children'))) ? next : null;
        if (sub) sub.hidden = exp;
        return;
      }
      var dest = ev.target && ev.target.closest ? ev.target.closest('.va-tree-dest') : null;
      if (dest) {
        rail.querySelectorAll('.va-tree-dest').forEach(function (d) { d.removeAttribute('aria-current'); d.classList.remove('is-active'); });
        dest.setAttribute('aria-current', 'page');
        dest.classList.add('is-active');
        if (rail.dataset.mode === 'overlay' || (root.innerWidth || 1200) < 1080) setRailOpen(rail, backdrop, false, false);
        if (typeof root.CustomEvent === 'function') {
          rail.dispatchEvent(new root.CustomEvent('quiet:tree-navigate', { bubbles: true, detail: { target: dest.dataset.target || '', label: dest.textContent.trim() } }));
        }
        return;
      }
      if (ev.target && ev.target.closest && ev.target.closest('[data-rail-close]')) setRailOpen(rail, backdrop, false, true);
    });
  }

  function bindModalSheets(scope) {
    if (!scope || !scope.querySelectorAll) return;
    if (typeof HTMLDialogElement !== 'undefined' && !('closedBy' in HTMLDialogElement.prototype)) {
      scope.querySelectorAll('dialog.va-modal-sheet[closedby="any"]').forEach(function (dlg) {
        if (dlg.dataset.quietClosedBy === '1') return;
        dlg.dataset.quietClosedBy = '1';
        var pressedOut = false;
        var outside = function (ev) {
          if (ev.target !== dlg || (ev.button != null && ev.button !== 0)) return false;
          var r = dlg.getBoundingClientRect();
          return ev.clientX < r.left || ev.clientX > r.right || ev.clientY < r.top || ev.clientY > r.bottom;
        };
        dlg.addEventListener('pointerdown', function (ev) { pressedOut = outside(ev); });
        dlg.addEventListener('pointercancel', function () { pressedOut = false; });
        dlg.addEventListener('pointerup', function (ev) { if (pressedOut && outside(ev)) dlg.close(); pressedOut = false; });
      });
    }
  }

  var _docBound = false;
  function boot(container) {
    var scope = container && container.querySelectorAll ? container : (root.document || null);
    if (!scope) return;
    scope.querySelectorAll('[data-period-stepper], .va-period-stepper').forEach(bindStepper);
    scope.querySelectorAll('.va-side-rail').forEach(bindRail);
    bindModalSheets(scope);
    if (!_docBound && root.document) {
      _docBound = true;
      var doc = root.document;
      doc.addEventListener('click', function (ev) {
        var openDlgBtn = ev.target && ev.target.closest ? ev.target.closest('[data-dialog-open]') : null;
        if (openDlgBtn) {
          bindModalSheets(doc);
          doc.querySelectorAll('.va-period-stepper').forEach(function (st) { closePopover(st, false); });
          var dlg = doc.getElementById(openDlgBtn.dataset.dialogOpen);
          if (dlg && typeof dlg.showModal === 'function' && !dlg.open) dlg.showModal();
          return;
        }
        var closeDlgBtn = ev.target && ev.target.closest ? ev.target.closest('[data-dialog-close]') : null;
        if (closeDlgBtn) {
          var parentDlg = closeDlgBtn.closest('dialog');
          if (parentDlg && typeof parentDlg.close === 'function') parentDlg.close();
          return;
        }
        var trig = ev.target && ev.target.closest ? ev.target.closest('[data-rail-trigger]') : null;
        if (trig) {
          var targetId = trig.getAttribute('aria-controls') || trig.dataset.railTrigger;
          var rail = targetId ? doc.getElementById(targetId) : doc.querySelector('.va-side-rail');
          if (rail) setRailOpen(rail, getBackdropFor(rail, doc), !(rail.dataset.open === 'true' || rail.classList.contains('is-open')), false);
        }
        doc.querySelectorAll('.va-period-stepper').forEach(function (st) {
          if (!st.contains(ev.target)) closePopover(st, false);
        });
      });
      doc.addEventListener('keydown', function (ev) {
        if (doc.querySelector('dialog.va-modal-sheet[open], dialog:modal')) return;
        if (ev.key === 'Escape') {
          doc.querySelectorAll('.va-period-stepper').forEach(function (st) { closePopover(st, true); });
          doc.querySelectorAll('.va-side-rail[data-open="true"], .va-side-rail.is-open').forEach(function (r) {
            setRailOpen(r, getBackdropFor(r, doc), false, true);
          });
        }
      });
      var reposRaf = 0;
      var repositionOpen = function () {
        if (reposRaf) return;
        var rafFn = typeof root.requestAnimationFrame === 'function' ? root.requestAnimationFrame.bind(root) : function (fn) { fn(); return 0; };
        reposRaf = rafFn(function () {
          reposRaf = 0;
          doc.querySelectorAll('.va-period-stepper').forEach(function (st) {
            var pop = st.querySelector('.va-preset-popover');
            var trig = st.querySelector('.va-period-trigger');
            if (pop && trig && isPopOpen(pop)) positionPopover(trig, pop);
          });
        });
      };
      if (typeof root.addEventListener === 'function') root.addEventListener('resize', repositionOpen);
      doc.addEventListener('scroll', repositionOpen, true);
    }
  }

  if (root.document) {
    if (root.document.readyState === 'loading') root.document.addEventListener('DOMContentLoaded', function () { boot(root.document); });
    else boot(root.document);
  }

  var stepperApi = { boot: boot, openPopover: openPopover, closePopover: closePopover, applyPresetChoice: applyPresetChoice, positionPopover: positionPopover };
  var railApi = { boot: boot, setRailOpen: setRailOpen, expandActiveBranches: expandActiveBranches, applyTreeChildCaps: applyTreeChildCaps };
  root.QuietPeriodStepper = stepperApi;
  root.QuietRailTree = railApi;
  if (typeof module === 'object' && module.exports) module.exports = { QuietPeriodStepper: stepperApi, QuietRailTree: railApi };
}(typeof window !== 'undefined' ? window : globalThis));
