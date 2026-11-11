// AGY-NEXUS Overwatch — LibreNMS / RRDTool Stacked Bar Engine, Adaptive DPI Binning & Foreground Axes (v2.6.0)

const THEME_META = {
  "obsidian":   { label: "Obsidian",   bg: "#0b0d10", border: "#10b981", themeColor: "#101318" },
  "dark-paper": { label: "Dark Paper", bg: "#21201c", border: "#ede8df", themeColor: "#1c1b18" },
  "warm-paper": { label: "Warm Paper", bg: "#f6f4f0", border: "#525a65", themeColor: "#edeae4" },
  "white":      { label: "Pure White", bg: "#ffffff", border: "#0f172a", themeColor: "#ffffff" },
  "pure-white": { label: "Pure White", bg: "#ffffff", border: "#0f172a", themeColor: "#ffffff" },
};
const VALID_DENSITIES = ["D1", "D2", "D3", "D4"];
const VALID_PERIODS = ["current_month", "last_month", "last_90d", "last_year"];
const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DOW_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const ALLOWED_BIN_HOURS = [1, 2, 3, 4, 6, 8, 12, 24, 48, 72, 168];

(function migrateLegacyStyle() {
  const legacy = localStorage.getItem("nexus_view_style");
  if (legacy && !localStorage.getItem("nexus_surface")) {
    const idx = legacy.lastIndexOf("-");
    if (idx > 0) {
      localStorage.setItem("nexus_surface", legacy.slice(0, idx));
      localStorage.setItem("nexus_density", legacy.slice(idx + 1));
    }
  }
})();

const initThemePref = localStorage.getItem("nexus_surface") || localStorage.getItem("nexus_theme") || "obsidian";
let fetchSeq = 0;
const state = {
  passphrase: localStorage.getItem("nexus_passphrase") || sessionStorage.getItem("nexus_passphrase") || "",
  period: VALID_PERIODS.includes(localStorage.getItem("nexus_period")) ? localStorage.getItem("nexus_period") : "current_month",
  surface: THEME_META[initThemePref] ? initThemePref : "obsidian",
  density: VALID_DENSITIES.includes(localStorage.getItem("nexus_density")) ? localStorage.getItem("nexus_density") : "D2",
  metric: localStorage.getItem("nexus_metric") === "tokens" ? "tokens" : "steps",
  selectedDate: localStorage.getItem("nexus_selected_date") || "",
  demoMode: localStorage.getItem("nexus_demo_mode") === "1",
  soloModel: "",
  soloSubagent: "",
  soloProject: "",
  bundle: null,
};

function formatCompactTokens(tok) {
  const n = Number(tok || 0);
  if (n >= 1_000_000_000) return (n / 1_000_000_000).toFixed(2) + "B";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "k";
  return String(Math.round(n));
}

function formatMetricVal(val, metric) {
  const n = Number(val || 0);
  if (metric === "tokens") return formatCompactTokens(n);
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + "M";
  if (n >= 10_000) return (n / 1_000).toFixed(1) + "k";
  if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, "") + "k";
  return String(Math.round(n));
}

function applyThemeAndDensity(surface, density) {
  const rawS = THEME_META[surface] ? surface : (THEME_META[localStorage.getItem("nexus_surface")] ? localStorage.getItem("nexus_surface") : "obsidian");
  const s = rawS === "pure-white" ? "white" : rawS;
  const d = VALID_DENSITIES.includes(density) ? density : "D2";
  state.surface = s;
  state.density = d;
  document.documentElement.setAttribute("data-surface", s);
  document.documentElement.setAttribute("data-theme", s === "white" ? "pure-white" : s);
  document.documentElement.setAttribute("data-density", d);
  localStorage.setItem("nexus_surface", s);
  localStorage.removeItem("nexus_theme");
  localStorage.setItem("nexus_density", d);
  const meta = THEME_META[s];
  const swatchEl = document.getElementById("triggerSwatch"), themeLabelEl = document.getElementById("triggerThemeLabel");
  const densityLabelEl = document.getElementById("triggerDensityLabel"), metaThemeEl = document.getElementById("metaThemeColor");
  if (swatchEl) { swatchEl.style.background = meta.bg; swatchEl.style.borderColor = meta.border; }
  if (themeLabelEl) themeLabelEl.textContent = meta.label;
  if (densityLabelEl) densityLabelEl.textContent = d;
  if (metaThemeEl) metaThemeEl.setAttribute("content", meta.themeColor);
  document.querySelectorAll(".theme-opt").forEach((btn) => btn.classList.toggle("active", btn.dataset.theme === s));
  document.querySelectorAll(".density-opt").forEach((btn) => btn.classList.toggle("active", btn.dataset.density === d));
  const mainEl = document.getElementById("dashboardMain");
  if (state.bundle && mainEl && !mainEl.classList.contains("hidden") && typeof renderDashboard === "function") {
    requestAnimationFrame(() => renderDashboard(state.bundle));
  }
}

async function fetchStats(period) {
  const mySeq = ++fetchSeq;
  if (state.demoMode) {
    localStorage.setItem("nexus_demo_mode", "1");
    state.bundle = generateDemoBundle(period);
    document.getElementById("authOverlay").classList.add("hidden");
    document.getElementById("dashboardMain").classList.remove("hidden");
    renderDashboard(state.bundle);
    return;
  }
  const statusEl = document.getElementById("authStatus");
  if (statusEl) statusEl.textContent = "Verifying passphrase...";
  try {
    const apiPath = window.location.pathname.replace(/\/web\/?$/, "") + "/web/api/stats?period=" + encodeURIComponent(period);
    const resp = await fetch(apiPath, {
      method: "GET",
      headers: { "X-Nexus-Passphrase": state.passphrase, "X-Client-Product": "Web Dashboard" },
    });
    if (mySeq !== fetchSeq) return;
    if (resp.status === 401 || resp.status === 403) {
      if (statusEl) statusEl.textContent = "Invalid passphrase. Try again or click Preview Sample Data.";
      localStorage.removeItem("nexus_passphrase"); sessionStorage.removeItem("nexus_passphrase");
      if (typeof clearSensitiveView === "function") clearSensitiveView();
      document.getElementById("authOverlay").classList.remove("hidden");
      document.getElementById("dashboardMain").classList.add("hidden");
      return;
    }
    const data = await resp.json();
    if (mySeq !== fetchSeq) return;
    if (data.ok === false) {
      if (statusEl) statusEl.textContent = data.error || "Unable to load dashboard data.";
      return;
    }
    localStorage.setItem("nexus_passphrase", state.passphrase); sessionStorage.setItem("nexus_passphrase", state.passphrase);
    localStorage.removeItem("nexus_demo_mode");
    if (statusEl) statusEl.textContent = "";
    state.bundle = data;
    document.getElementById("authOverlay").classList.add("hidden");
    document.getElementById("dashboardMain").classList.remove("hidden");
    renderDashboard(data);
  } catch (err) {
    if (mySeq === fetchSeq && statusEl) statusEl.textContent = "Connection or render error: " + (err && err.message ? err.message : String(err));
  }
}

function formatBinLabel(binHours) {
  if (binHours >= 168) return `${Math.round(binHours / 168)}W`;
  if (binHours >= 24 && binHours % 24 === 0) return `${binHours / 24}D`;
  return `${binHours}H`;
}

function computeOptimalBinning(plotW, baseStepHours, nRaw) {
  const baseH = Math.max(1, Number(baseStepHours || 4));
  if (nRaw <= 1) return { groupSize: 1, binHours: baseH, label: formatBinLabel(baseH), dpr: 1 };
  const dpr = Math.max(1, Math.min(4, Number(window.devicePixelRatio || 1)));
  const targetPitch = dpr >= 2 ? 5.2 : 6.8;
  const minPitch = dpr >= 2 ? 3.4 : 4.6;
  const cands = ALLOWED_BIN_HOURS.filter((h) => h >= baseH && h % baseH === 0);
  if (!cands.length) cands.push(baseH);
  let bestH = cands[cands.length - 1];
  let bestDist = Infinity;
  cands.forEach((h) => {
    const g = Math.max(1, Math.round(h / baseH));
    const pitch = plotW / Math.max(1, Math.ceil(nRaw / g));
    if (pitch >= minPitch && Math.abs(pitch - targetPitch) < bestDist) {
      bestDist = Math.abs(pitch - targetPitch);
      bestH = h;
    }
  });
  return { groupSize: Math.max(1, Math.round(bestH / baseH)), binHours: bestH, label: formatBinLabel(bestH), dpr };
}

function computeNiceYScale(rawMax, plotH) {
  const safeMax = Math.max(10, Number(rawMax || 0) * 1.06);
  const rough = safeMax / (plotH >= 155 ? 4 : 3);
  const pow10 = Math.pow(10, Math.floor(Math.log10(rough)));
  const norm = rough / pow10;
  const niceNorm = norm <= 1 ? 1 : (norm <= 2 ? 2 : (norm <= 2.5 ? 2.5 : (norm <= 5 ? 5 : 10)));
  const majorStep = niceNorm * pow10;
  const maxY = Math.max(majorStep, Math.ceil(safeMax / majorStep) * majorStep);
  const majorVals = [], minorVals = [], minorStep = majorStep / 2;
  for (let v = 0; v <= maxY + minorStep * 0.1; v += minorStep) {
    const rounded = Number(v.toFixed(4));
    if (Math.abs((rounded / majorStep) - Math.round(rounded / majorStep)) < 0.01) majorVals.push(rounded);
    else if (rounded > 0 && rounded < maxY) minorVals.push(rounded);
  }
  return { maxY, majorVals, minorVals };
}

function formatXTickLabel(dateStr, binHours, nBins) {
  const raw = String(dateStr || "");
  const m = Number(raw.slice(5, 7)), d = raw.slice(8, 10);
  const mon = (m >= 1 && m <= 12) ? MONTH_NAMES[m - 1] : raw.slice(5, 7);
  return (binHours < 24 && nBins <= 48 && raw.length >= 16) ? `${mon} ${d} ${raw.slice(11, 16)}` : `${mon} ${d}`;
}

function aggregateSeriesBins(dates, rawBands, groupSize) {
  const nRaw = dates.length, binDates = [], binEnds = [];
  for (let i = 0; i < nRaw; i += groupSize) {
    binDates.push(dates[i]);
    binEnds.push(dates[Math.min(nRaw - 1, i + groupSize - 1)]);
  }
  const nBins = binDates.length;
  const bands = rawBands.map((b) => {
    const src = b.values || [], agg = new Array(nBins).fill(0);
    for (let bi = 0; bi < nBins; bi++) {
      let sum = 0;
      const start = bi * groupSize, end = Math.min(nRaw, start + groupSize);
      for (let k = start; k < end; k++) sum += Number(src[k] || 0);
      agg[bi] = sum;
    }
    return { ...b, agg };
  });
  return { binDates, binEnds, nBins, bands };
}

function attachPlotHoverEvents(svg) {
  if (svg._hoverBound) return;
  svg._hoverBound = true;
  svg.addEventListener("pointermove", (e) => {
    const ctx = svg._chartCtx;
    if (!ctx || !ctx.nBins) return;
    const boxRect = svg.getBoundingClientRect();
    const relX = e.clientX - boxRect.left;
    const idx = Math.floor((relX - ctx.padL) / ctx.stepPx);
    const cross = svg.querySelector(".hover-crosshair");
    const tip = svg.parentElement && svg.parentElement.querySelector(".plot-tooltip");
    if (idx < 0 || idx >= ctx.nBins || !tip) {
      if (cross) cross.classList.add("hidden");
      if (tip) tip.classList.add("hidden");
      return;
    }
    const cx = Math.round(ctx.padL + (idx + 0.5) * ctx.stepPx) + 0.5;
    if (cross) { cross.setAttribute("x1", String(cx)); cross.setAttribute("x2", String(cx)); cross.classList.remove("hidden"); }
    const tot = ctx.binTotals[idx] || 0;
    const items = ctx.bands
      .filter((b) => !b.hidden)
      .map((b) => ({ label: b.tooltipLabel || b.label, val: b.agg[idx] || 0, fill: b.fill }))
      .filter((x) => x.val > 0)
      .sort((a, b) => b.val - a.val);
    const rangeTxt = ctx.binDates[idx] === ctx.binEnds[idx] ? ctx.binDates[idx] : `${ctx.binDates[idx]} → ${ctx.binEnds[idx].slice(-5)}`;
    const unit = ctx.metric === "tokens" ? "tok" : "steps";
    const rowsHtml = items.slice(0, 6).map((it) => {
      const pct = tot > 0 ? ((it.val / tot) * 100).toFixed(0) + "%" : "";
      return `<div class="tip-row"><span class="tip-lbl"><span class="swatch-dot" style="background:${it.fill}"></span>${escapeHtmlSafe(it.label)}</span><span class="mono">${formatMetricVal(it.val, ctx.metric)} <span class="tip-pct">${pct}</span></span></div>`;
    }).join("");
    const extra = items.length > 6 ? `<div class="tip-more mono">+${items.length - 6} more active in bin</div>` : "";
    tip.innerHTML = `<div class="tip-hdr mono"><span>${escapeHtmlSafe(rangeTxt)} (${ctx.binLabel})</span><strong>${formatMetricVal(tot, ctx.metric)} ${unit}</strong></div>${rowsHtml || '<div class="tip-more mono">0 activity in bin</div>'}${extra}`;
    tip.classList.remove("hidden");
    const tipW = tip.offsetWidth || 230;
    tip.style.left = `${Math.round((relX + tipW + 20 > boxRect.width) ? Math.max(6, relX - tipW - 12) : (relX + 12))}px`;
  });
  svg.addEventListener("pointerleave", () => {
    const cross = svg.querySelector(".hover-crosshair");
    const tip = svg.parentElement && svg.parentElement.querySelector(".plot-tooltip");
    if (cross) cross.classList.add("hidden");
    if (tip) tip.classList.add("hidden");
  });
}

function renderLibreStackedPlot(svgId, tagId, opts) {
  const svg = document.getElementById(svgId);
  if (!svg) return { nBins: 0, binLabel: "-", avgVal: 0, p95Val: 0, peakVal: 0, bandPeaks: {} };
  const box = svg.parentElement, tipEl = box && box.querySelector(".plot-tooltip");
  if (tipEl) tipEl.classList.add("hidden");
  const W = Math.max(300, Math.round((box && box.clientWidth) || 960)), H = Math.max(132, Math.round((box && box.clientHeight) || 195));
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.removeAttribute("preserveAspectRatio");

  const dates = Array.isArray(opts.dates) ? opts.dates : [], rawBands = Array.isArray(opts.bands) ? opts.bands : [];
  if (!dates.length || !rawBands.length) {
    svg.innerHTML = `<text class="axis-label" x="52" y="${Math.round(H / 2)}">No activity recorded in this window.</text>`;
    svg._chartCtx = null;
    return { nBins: 0, binLabel: "-", avgVal: 0, p95Val: 0, peakVal: 0, bandPeaks: {} };
  }

  const padL = 48, padR = opts.showRefLines ? 54 : 16, padT = 14, padB = 24;
  const plotW = Math.max(120, W - padL - padR), plotH = Math.max(72, H - padT - padB);
  const binCfg = computeOptimalBinning(plotW, opts.stepHours || 4, dates.length);
  const { binDates, binEnds, nBins, bands } = aggregateSeriesBins(dates, rawBands, binCfg.groupSize);

  const binTotals = new Array(nBins).fill(0), bandPeaks = {};
  let peakVal = 0;
  bands.forEach((b) => { bandPeaks[b.id] = 0; });
  for (let i = 0; i < nBins; i++) {
    let s = 0;
    bands.forEach((b) => {
      const v = b.agg[i] || 0;
      if (v > bandPeaks[b.id]) bandPeaks[b.id] = v;
      if (!b.hidden) s += v;
    });
    binTotals[i] = s;
    if (s > peakVal) peakVal = s;
  }

  const nzTotals = binTotals.filter((v) => v > 0).sort((a, b) => a - b);
  const avgVal = nzTotals.length ? (nzTotals.reduce((a, b) => a + b, 0) / nzTotals.length) : 0;
  const p95Val = nzTotals.length ? nzTotals[Math.min(nzTotals.length - 1, Math.floor(nzTotals.length * 0.95))] : 0;
  const yScale = computeNiceYScale(Math.max(peakVal, p95Val), plotH);
  const stepPx = plotW / Math.max(1, nBins), gapPx = stepPx >= 4.8 ? 1 : 0;
  const yAt = (val) => padT + plotH - (Math.min(yScale.maxY, Math.max(0, val)) / yScale.maxY) * plotH;

  let barsSvg = "";
  const visBands = bands.filter((b) => !b.hidden);
  for (let i = 0; i < nBins; i++) {
    if (binTotals[i] <= 0) continue;
    const x0 = Math.round(padL + i * stepPx), bw = Math.max(1, Math.round(padL + (i + 1) * stepPx) - gapPx - x0);
    let cum = 0;
    for (let k = 0; k < visBands.length; k++) {
      const b = visBands[k], v = b.agg[i] || 0;
      if (v <= 0) continue;
      const yBot = Math.round(yAt(cum));
      cum += v;
      const yTop = Math.min(yBot - 1, Math.round(yAt(cum))), bh = Math.max(1, yBot - yTop);
      barsSvg += `<rect x="${x0}" y="${yTop}" width="${bw}" height="${bh}" fill="${b.fill}" fill-opacity="0.88"/>`;
      if (bh >= 2 && bw >= 2) barsSvg += `<line x1="${x0}" y1="${yTop + 0.5}" x2="${x0 + bw}" y2="${yTop + 0.5}" stroke="${b.cap}" stroke-width="1"/>`;
    }
  }

  let refSvg = "";
  if (opts.showRefLines && peakVal > 0) {
    if (avgVal > 0) {
      const ay = Math.round(yAt(avgVal)) + 0.5;
      refSvg += `<line x1="${padL}" y1="${ay}" x2="${padL + plotW}" y2="${ay}" class="ref-line-avg"/><text class="ref-label avg" x="${padL + plotW + 4}" y="${ay + 3}">Avg ${formatMetricVal(avgVal, opts.metric)}</text>`;
    }
    if (p95Val > 0 && Math.abs(yAt(p95Val) - yAt(avgVal)) >= 11) {
      const py = Math.round(yAt(p95Val)) + 0.5;
      refSvg += `<line x1="${padL}" y1="${py}" x2="${padL + plotW}" y2="${py}" class="ref-line-p95"/><text class="ref-label p95" x="${padL + plotW + 4}" y="${py + 3}">P95</text>`;
    }
  }

  // Foreground Major & Minor Gridlines + Spines + LibreNMS Arrowheads (Rendered Strictly OVER Bars)
  let fgGrid = "";
  yScale.minorVals.forEach((v) => {
    const y = Math.round(yAt(v)) + 0.5;
    fgGrid += `<line class="fg-grid-minor" x1="${padL}" y1="${y}" x2="${padL + plotW}" y2="${y}"/>`;
  });
  yScale.majorVals.forEach((v) => {
    const y = Math.round(yAt(v)) + 0.5;
    if (v > 0) fgGrid += `<line class="fg-grid-major" x1="${padL}" y1="${y}" x2="${padL + plotW}" y2="${y}"/>`;
    fgGrid += `<text class="axis-label" x="${padL - 6}" y="${y + 3}" text-anchor="end">${formatMetricVal(v, opts.metric)}</text>`;
  });

  const maxXTicks = Math.max(2, Math.floor(plotW / 96));
  let majorStride = Math.max(1, Math.ceil(nBins / maxXTicks));
  if (binCfg.binHours < 24) {
    const dayBins = Math.max(1, Math.round(24 / binCfg.binHours));
    if (nBins > dayBins * 2) majorStride = Math.max(1, Math.ceil((nBins / dayBins) / maxXTicks)) * dayBins;
  }
  const majorXIdxs = [];
  for (let i = 0; i < nBins; i += majorStride) majorXIdxs.push(i);
  if (nBins > 1 && (nBins - 1 - majorXIdxs[majorXIdxs.length - 1]) > majorStride * 0.55) majorXIdxs.push(nBins - 1);
  const minorDivs = majorStride >= 4 ? (majorStride % 4 === 0 ? 4 : (majorStride % 3 === 0 ? 3 : 2)) : 0;
  majorXIdxs.forEach((idx, mPos) => {
    const x = Math.round(padL + (idx + 0.5) * stepPx) + 0.5;
    if (idx > 0) fgGrid += `<line class="fg-grid-major" x1="${x}" y1="${padT}" x2="${x}" y2="${padT + plotH}"/>`;
    fgGrid += `<line class="fg-axis-tick" x1="${x}" y1="${padT + plotH}" x2="${x}" y2="${padT + plotH + 4}"/>`;
    const anchor = idx === 0 ? "start" : (idx >= nBins - 2 ? "end" : "middle");
    fgGrid += `<text class="axis-label" x="${x}" y="${H - 5}" text-anchor="${anchor}">${escapeHtmlSafe(formatXTickLabel(binDates[idx], binCfg.binHours, nBins))}</text>`;
    if (minorDivs > 0 && mPos < majorXIdxs.length - 1) {
      const nextIdx = majorXIdxs[mPos + 1];
      for (let md = 1; md < minorDivs; md++) {
        const mx = Math.round(padL + (idx + ((nextIdx - idx) * md) / minorDivs + 0.5) * stepPx) + 0.5;
        fgGrid += `<line class="fg-grid-minor" x1="${mx}" y1="${padT}" x2="${mx}" y2="${padT + plotH}"/>`;
      }
    }
  });

  const yBase = padT + plotH + 0.5, xSpine = padL + 0.5, xRight = padL + plotW + 5, yTopArrow = Math.max(3, padT - 6);
  const spinesSvg = `<line class="fg-axis-spine" x1="${xSpine}" y1="${yBase}" x2="${xSpine}" y2="${yTopArrow + 3}"/><polygon class="fg-axis-arrow" points="${xSpine},${yTopArrow - 1} ${xSpine - 3},${yTopArrow + 5} ${xSpine + 3},${yTopArrow + 5}"/><line class="fg-axis-spine" x1="${padL}" y1="${yBase}" x2="${xRight - 3}" y2="${yBase}"/><polygon class="fg-axis-arrow" points="${xRight + 1},${yBase} ${xRight - 5},${yBase - 3} ${xRight - 5},${yBase + 3}"/>`;

  svg.innerHTML = `<rect x="${padL}" y="${padT}" width="${plotW}" height="${plotH}" fill="var(--plot-canvas-bg)" rx="2"/><g class="layer-bars" shape-rendering="crispEdges">${barsSvg}</g><g class="layer-ref">${refSvg}</g><g class="layer-fg-axes" pointer-events="none">${fgGrid}${spinesSvg}</g><line class="hover-crosshair hidden" x1="${padL}" y1="${padT}" x2="${padL}" y2="${padT + plotH}" pointer-events="none"/>`;
  svg._chartCtx = { padL, stepPx, nBins, binDates, binEnds, binTotals, bands, binLabel: binCfg.label, metric: opts.metric };
  attachPlotHoverEvents(svg);

  const tagEl = tagId ? document.getElementById(tagId) : null;
  if (tagEl) {
    const suffix = opts.tagSuffix ? ` · ${opts.tagSuffix}` : "";
    tagEl.textContent = `${binCfg.label} BINS (${nBins} BARS · ${Math.round(binCfg.dpr)}X DPI)${suffix}`;
  }
  return { nBins, binLabel: binCfg.label, avgVal, p95Val, peakVal, bandPeaks };
}

function computeIsoWeekday(dateStr, fallbackWeekday) {
  if (typeof fallbackWeekday === "number" && fallbackWeekday >= 0 && fallbackWeekday <= 6) return fallbackWeekday;
  const parts = String(dateStr || "").split("-").map(Number);
  if (parts.length === 3 && !isNaN(parts[0])) return (new Date(Date.UTC(parts[0], parts[1] - 1, parts[2])).getUTCDay() + 6) % 7;
  return 0;
}

(function initPlotResizeObserver() {
  if (typeof ResizeObserver === "undefined") return;
  let rafId = 0, lastW = 0;
  const ro = new ResizeObserver((entries) => {
    const w = entries[0] && Math.round(entries[0].contentRect.width);
    if (!w || Math.abs(w - lastW) < 4 || !state.bundle) return;
    lastW = w;
    cancelAnimationFrame(rafId);
    rafId = requestAnimationFrame(() => {
      if (state.bundle && typeof renderAllTimePlots === "function") renderAllTimePlots(state.bundle);
    });
  });
  window.addEventListener("DOMContentLoaded", () => {
    const main = document.getElementById("dashboardMain");
    if (main) ro.observe(main);
  });
})();
