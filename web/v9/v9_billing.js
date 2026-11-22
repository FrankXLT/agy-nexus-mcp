/* SPDX-License-Identifier: Apache-2.0 */
/* AGY-Nexus /web/v9 — Active-Day Hourly Min/Avg/Max Whiskers & Subscription Break-Even Card */
(() => {
  const V9 = window.AgyV9;

  function formatWhiskerVal(val, metric) {
    if (metric === "cost") return V9.fmtUsd(val);
    return V9.fmtNum(val);
  }

  function buildCadenceWhiskerOption(b, metric, t, cardW) {
    const hw = b && b.hourly_whiskers;
    const axisFont = V9.cssVar("--font-mono", "monospace");
    const mKey = metric === "cost" ? "cost" : (metric === "tokens" ? "tokens" : "steps");
    const yName = metric === "cost" ? "USD" : (metric === "tokens" ? "tokens" : "steps");

    if (!hw || !Array.isArray(hw.hours) || !Array.isArray(hw[mKey])) {
      const dowNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
      const dowTotals = new Array(7).fill(0);
      (b.heatmap_series || []).forEach((c) => {
        if (c.in_window && !c.future && c.weekday >= 0 && c.weekday < 7) {
          dowTotals[c.weekday] += Number(metric === "cost" ? c.cost_usd : (metric === "tokens" ? c.tokens : c.steps)) || 0;
        }
      });
      return {
        subNote: "Weekday summary",
        footNote: "Activity by weekday (fallback dataset)",
        opt: {
          animation: false, independentXSpan: true, yUnit: `cadence_${metric}`, backgroundColor: "transparent",
          tooltip: { trigger: "axis", confine: true, backgroundColor: t.elev, borderColor: t.spine, textStyle: { color: t.text, fontSize: 12 } },
          grid: { left: 54, right: 16, top: 32, bottom: 28, containLabel: false },
          xAxis: { type: "category", data: dowNames, axisLine: { lineStyle: { color: t.spine } }, axisTick: { show: false }, axisLabel: { color: t.muted, fontSize: 11, fontFamily: axisFont } },
          yAxis: { type: "value", name: yName, splitNumber: 4, axisLine: { show: false }, axisLabel: { color: t.muted, fontSize: 11, fontFamily: axisFont, formatter: (v) => formatWhiskerVal(v, metric) }, splitLine: { lineStyle: { color: t.grid, type: "dashed" } } },
          series: [{ name: "Weekday", type: "bar", barMaxWidth: 20, itemStyle: { color: V9.getSeriesColor(1) }, data: dowTotals }],
        },
      };
    }

    const rows = hw[mKey];
    const hasL24 = Boolean(hw.has_last_24h);
    const actDays = Number(hw.active_days_count || 0);
    const customData = rows.map((r, idx) => [idx, Number(r.min || 0), Number(r.avg || 0), Number(r.max || 0), Number(r.active_days || 0)]);
    const avgLineData = rows.map((r) => (Number(r.active_days || 0) > 0 && Number(r.max || 0) > 0 ? Number(r.avg || 0) : null));
    const l24Data = rows.map((r) => (hasL24 && r.last_24h != null && Number(r.last_24h) > 0 ? Number(r.last_24h) : null));

    const stemColor = V9.getSeriesColor(1);
    const avgColor = V9.getSeriesColor(0);
    const l24Color = V9.getSeriesColor(2);

    const series = [
      {
        name: "Min–Max Range",
        type: "custom",
        renderItem: (_params, api) => {
          const xIdx = api.value(0);
          const yMin = api.value(1);
          const yAvg = api.value(2);
          const yMax = api.value(3);
          const obs = api.value(4);
          if (!obs || yMax <= 0) return null;
          const pMax = api.coord([xIdx, yMax]);
          const pMin = api.coord([xIdx, yMin]);
          const pAvg = api.coord([xIdx, yAvg]);
          return {
            type: "group",
            children: [
              { type: "line", shape: { x1: pMin[0], y1: pMin[1], x2: pMax[0], y2: pMax[1] }, style: { stroke: stemColor, lineWidth: 1.6 } },
              { type: "line", shape: { x1: pMax[0] - 4, y1: pMax[1], x2: pMax[0] + 4, y2: pMax[1] }, style: { stroke: stemColor, lineWidth: 1.6 } },
              { type: "line", shape: { x1: pMin[0] - 4, y1: pMin[1], x2: pMin[0] + 4, y2: pMin[1] }, style: { stroke: stemColor, lineWidth: 1.6 } },
              { type: "line", shape: { x1: pAvg[0] - 5, y1: pAvg[1], x2: pAvg[0] + 5, y2: pAvg[1] }, style: { stroke: avgColor, lineWidth: 2.5 } },
            ],
          };
        },
        encode: { x: 0, y: [1, 3] },
        data: customData,
        z: 2,
      },
      {
        name: "Active Avg",
        type: "line",
        data: avgLineData,
        symbol: "none",
        connectNulls: false,
        lineStyle: { color: avgColor, width: 1.4, type: "dashed" },
        z: 3,
      },
    ];
    if (hasL24) {
      series.push({
        name: "Last 24h",
        type: "scatter",
        symbolSize: 7,
        itemStyle: { color: l24Color, borderColor: t.surface, borderWidth: 1.2 },
        data: l24Data,
        z: 4,
      });
    }

    const opt = {
      animation: false,
      independentXSpan: true,
      yUnit: `whiskers_${metric}`,
      backgroundColor: "transparent",
      legend: {
        show: true, top: 2, right: 8, itemWidth: 10, itemHeight: 8,
        textStyle: { color: t.sub, fontSize: 10, fontFamily: axisFont },
      },
      tooltip: {
        trigger: "axis",
        confine: true,
        backgroundColor: t.elev,
        borderColor: t.spine,
        textStyle: { color: t.text, fontSize: 12, fontFamily: axisFont },
        formatter: (params) => {
          const first = Array.isArray(params) ? params[0] : params;
          const idx = first ? first.dataIndex : 0;
          const row = rows[idx] || {};
          const hLbl = hw.hours[idx] || `${String(idx).padStart(2, "0")}h`;
          if (!row.active_days) return `${hLbl} · No active sessions in window`;
          const base = `${hLbl} (${row.active_days} active day${row.active_days === 1 ? "" : "s"})<br>`
            + `Max: ${formatWhiskerVal(row.max, metric)} · Avg: ${formatWhiskerVal(row.avg, metric)} · Min: ${formatWhiskerVal(row.min, metric)}`;
          return hasL24 && row.last_24h != null
            ? `${base}<br>Last 24h: ${formatWhiskerVal(row.last_24h, metric)}`
            : base;
        },
      },
      grid: { left: 54, right: 16, top: 34, bottom: 28, containLabel: false },
      xAxis: {
        type: "category", data: hw.hours,
        axisLine: { lineStyle: { color: t.spine } }, axisTick: { show: false },
        axisLabel: { color: t.muted, fontSize: 11, fontFamily: axisFont, interval: cardW < 480 ? 3 : 1, hideOverlap: true },
      },
      yAxis: {
        type: "value", name: yName, nameGap: 10,
        nameTextStyle: { color: t.muted, fontSize: 11, fontFamily: axisFont },
        splitNumber: 4,
        axisLine: { show: false },
        axisLabel: { color: t.muted, fontSize: 11, fontFamily: axisFont, margin: 8, formatter: (v) => formatWhiskerVal(v, metric) },
        splitLine: { lineStyle: { color: t.grid, type: "dashed" } },
      },
      series,
    };
    return {
      opt,
      subNote: `${actDays} active days · Min / Avg / Max${hasL24 ? " + Last 24h" : ""}`,
      footNote: `Local clock (00h–23h) · Range: active-day Min–Max · Dash: Avg${hasL24 ? " · Dot: Last 24h" : " · Past closed window"}`,
    };
  }

  function renderBillingCard(b) {
    const bodyEl = document.getElementById("v9BillingBody");
    const subEl = document.getElementById("v9BillingSub");
    const footEl = document.getElementById("v9BillingFoot");
    if (!bodyEl || !b) return;
    const bc = b.billing_comparison || {};
    const k = b.kpis || {};
    const drift = b.model_drift_status || bc.drift_status || {};
    const dStatus = String(drift.status || "NOT_RUN");
    const dCount = Number(drift.drift_count || 0);
    const pillState = dStatus === "DRIFT_DETECTED" ? "warn" : (dStatus === "OK" ? "nominal" : "neutral");
    const pillLabel = dStatus === "OK" ? "0 drift (01:45)" : (dStatus === "DRIFT_DETECTED" ? `${dCount} drift (01:45)` : "Drift check pending");

    if (subEl) {
      subEl.innerHTML = `<span class="va-pill" data-variant="status" data-state="${pillState}">${V9.escHtml(pillLabel)}</span>`;
    }

    const histUsd = Number(bc.historical_usd != null ? bc.historical_usd : (k.window_cost_usd || 0));
    const foreUsd = Number(bc.forecast_usd != null ? bc.forecast_usd : (k.forecast_cost_usd || histUsd));
    const deltaPct = Number(bc.forecast_delta_pct || (histUsd > 0 ? ((foreUsd - histUsd) / histUsd) * 100 : 0));
    const avgDay = Number(bc.avg_usd_per_active_day != null ? bc.avg_usd_per_active_day : (k.cost_per_day_usd || 0));

    const uIn = Number(k.uncached_input_tokens || 0);
    const cIn = Number(k.cached_input_tokens || 0);
    const oTok = Number(k.output_tokens || 0);
    const totSplit = Math.max(1, uIn + cIn + oTok);
    const uPct = Math.round((uIn / totSplit) * 100);
    const cPct = Math.round((cIn / totSplit) * 100);
    const oPct = Math.max(0, 100 - uPct - cPct);

    const tiers = Array.isArray(bc.tiers) ? bc.tiers : [];
    const activeProf = String(bc.active_profile || "");
    const fmtExactUsd = (val) => `$${Math.abs(Number(val || 0)).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    const tierRows = tiers.map((tier) => {
      const tid = String(tier.id || "");
      const isCur = (activeProf.includes("20x") && tid.includes("20x")) || (activeProf.includes("5x") && tid.includes("5x"));
      const subWin = Number(tier.window_cost_usd || tier.monthly_usd || 0);
      const mult = Number(tier.value_multiplier || (subWin > 0 ? histUsd / subWin : 0));
      const net = Number(tier.net_savings_usd != null ? tier.net_savings_usd : (histUsd - subWin));
      const netCls = net >= 0 ? "v9-delta-pos" : "v9-delta-neg";
      return `<tr class="${isCur ? "is-solo" : ""}">
        <td><span class="v9-cell-main">${V9.escHtml(tier.label)}</span><div class="v9-cell-sub">${V9.escHtml(tier.notes || "")}</div></td>
        <td class="num v9-mono-num">${fmtExactUsd(subWin)}</td>
        <td class="num v9-mono-num"><span class="${netCls}">${net >= 0 ? "+" : "-"}${V9.fmtUsd(Math.abs(net))}</span></td>
        <td class="num v9-mono-num"><strong>${mult.toFixed(1)}x</strong></td>
      </tr>`;
    }).join("");

    bodyEl.innerHTML = `
      <div class="v9-billing-kpis">
        <div class="v9-billing-kpi">
          <div class="v9-billing-lbl">Est. API Retail</div>
          <div class="v9-billing-val v9-mono-num">${V9.fmtUsd(histUsd)}</div>
          <div class="v9-billing-sub">${V9.fmtUsd(avgDay)}/act-d</div>
        </div>
        <div class="v9-billing-kpi">
          <div class="v9-billing-lbl">Dec Rate Forecast</div>
          <div class="v9-billing-val v9-mono-num">${V9.fmtUsd(foreUsd)}</div>
          <div class="v9-billing-sub">${deltaPct >= 0 ? "+" : ""}${deltaPct.toFixed(0)}% Dec rate</div>
        </div>
        <div class="v9-billing-kpi">
          <div class="v9-billing-lbl">Token Billing Split</div>
          <div class="v9-billing-val v9-mono-num">${cPct}% cache</div>
          <div class="v9-billing-sub">${uPct}% in · ${oPct}% out</div>
        </div>
      </div>
      <div class="va-table-wrap v9-table-scroll" tabindex="0" role="region" aria-label="Subscription break-even comparison">
        <table class="v9-table booktabs">
          <thead><tr><th>Subscription Tier</th><th class="num">Window Sub</th><th class="num">API Savings</th><th class="num">Value</th></tr></thead>
          <tbody>${tierRows || `<tr><td colspan="4" class="v9-cell-sub">Tier pricing loaded from catalog</td></tr>`}</tbody>
        </table>
      </div>`;

    if (footEl) {
      const fList = Array.isArray(drift.findings) ? drift.findings : [];
      footEl.textContent = dCount > 0 && fList.length
        ? `01:45 AM check: ${fList[0].detail || drift.summary}`
        : `${String(drift.summary || "Effective-dated integer micro-USD billing across cached + uncached tokens.")}`;
    }
  }

  V9.Billing = { buildCadenceWhiskerOption, renderBillingCard };
})();
