/* SPDX-License-Identifier: Apache-2.0 */
/* AGY-Nexus /web/v9 — Card 3 Pool Split & Card 4 Quota Pacing Race Cards */
(() => {
  const V9 = (window.AgyV9 = window.AgyV9 || {});
  const CARET_SVG = '<svg width="8" height="5" viewBox="0 0 8 6" aria-hidden="true"><path d="M4 6L0.4 0.5H7.6L4 6Z" fill="currentColor"/></svg>';
  const MODEL_SHORT_MAP = {
    carbon: "Carbon 4", neon: "Neon 4", argon: "Argon 4", hydrogen: "Hydrogen 4",
    flash_3_8: "Flash 3.8", claude_opus_5_5: "Opus 5.5", claude_sonnet_5_5: "Sonnet 5.5", gpt_oss_120b: "GPT-OSS 120B",
  };

  const clampPct = (v) => Math.max(0, Math.min(100, Number.isFinite(Number(v)) ? Number(v) : 0));
  const fmtSplitPair = (g, p) => {
    const f = (n) => (Math.abs(n - Math.round(n)) < 0.05 ? String(Math.round(n)) : n.toFixed(1));
    return `${f(g)}/${f(p)}`;
  };
  const isGoogle = (m) => {
    const pk = String(m?.pool_key || "").toLowerCase();
    return pk ? pk === "google" : String(m?.pool || "").toLowerCase().includes("google");
  };

  function shortModelName(mainObj) {
    if (mainObj && typeof mainObj === "object") {
      if (mainObj.short_label) return String(mainObj.short_label);
      if (mainObj.model_key && MODEL_SHORT_MAP[mainObj.model_key]) return MODEL_SHORT_MAP[mainObj.model_key];
      const lbl = String(mainObj.label || "").trim();
      if (/^Gemini\s+4\s+([A-Za-z]+)/i.test(lbl)) return `${lbl.replace(/^Gemini\s+4\s+/i, "")} 4`;
      if (/^Gemini\s+([\d.]+)\s+Flash/i.test(lbl)) return lbl.replace(/^Gemini\s+([\d.]+)\s+Flash.*/i, "Flash $1");
      if (lbl) return lbl;
    }
    return "Carbon 4";
  }

  function formatCompactReset(bucket) {
    if (!bucket || typeof bucket !== "object" || !bucket.has_active_reset || !bucket.reset_time) {
      return { short: Number(bucket?.used_pct || 0) > 0.05 ? "Active" : "Standby", clock: "" };
    }
    const ms = Date.parse(String(bucket.reset_time));
    if (!Number.isFinite(ms)) return { short: "Active", clock: "" };
    const diff = ms - Date.now();
    if (diff <= 0) return { short: "Due", clock: "" };
    const totMin = Math.max(1, Math.floor(diff / 60000));
    const totHr = Math.floor(totMin / 60);
    const remMin = totMin % 60;
    const days = Math.floor(totHr / 24);
    const remHr = totHr % 24;
    const short = days >= 1 ? `${days}d ${remHr}h` : (totHr >= 1 ? `${totHr}h ${remMin}m` : `${totMin}m`);
    let clock = "";
    try {
      const opts = days >= 1 ? { weekday: "short", hour: "numeric", minute: "2-digit" } : { hour: "numeric", minute: "2-digit" };
      clock = new Intl.DateTimeFormat(undefined, opts).format(new Date(ms));
    } catch (_err) { clock = ""; }
    return { short, clock };
  }

  function computeClockPct(bucket, defaultWinSec) {
    if (!bucket || typeof bucket !== "object" || !bucket.has_active_reset) return 0;
    const winSec = Math.max(1, Number(bucket.window_seconds || defaultWinSec));
    const rtMs = bucket.reset_time ? Date.parse(String(bucket.reset_time)) : NaN;
    if (Number.isFinite(rtMs)) {
      const remSec = Math.max(0, Math.min(winSec, (rtMs - Date.now()) / 1000));
      return clampPct(Number((((winSec - remSec) / winSec) * 100).toFixed(1)));
    }
    return bucket.elapsed_pct != null ? clampPct(bucket.elapsed_pct) : 0;
  }

  function derivePoolSplit(bundle, metric) {
    const qp = bundle.quota_and_pools || {};
    const pools = qp.pools || {};
    const gPool = pools.google || {};
    const pPool = pools.claude || {};
    const models = Array.isArray(bundle.model_usage_vs_target) ? bundle.model_usage_vs_target : [];
    const computed = (V9.SparkBars && V9.SparkBars.computeModelRows && models.length)
      ? V9.SparkBars.computeModelRows(models, metric || "steps", bundle.model_series)
      : null;

    let gPct = 0, pPct = 0, gTgt = 0, pTgt = 0, g24 = null, p24 = null, has24 = false;
    if (computed && computed.length) {
      let gAct = 0, pAct = 0, gL = 0, pL = 0, anyL = false;
      computed.forEach((r) => {
        const g = isGoogle(r.m);
        if (g) { gAct += r.actualPct; gTgt += r.targetPct; } else { pAct += r.actualPct; pTgt += r.targetPct; }
        if (r.last24hPct != null) { anyL = true; if (g) gL += r.last24hPct; else pL += r.last24hPct; }
      });
      const sumAct = gAct + pAct;
      if (sumAct > 0.01) { gPct = Number(((gAct / sumAct) * 100).toFixed(1)); pPct = Number((100 - gPct).toFixed(1)); }
      has24 = models.some((m) => m.has_last_24h !== false);
      if (anyL && (gL + pL) > 0.01) { g24 = Number(((gL / (gL + pL)) * 100).toFixed(1)); p24 = Number((100 - g24).toFixed(1)); }
    } else if (gPool.call_share_pct != null || pPool.call_share_pct != null) {
      const gRaw = Number(gPool.call_share_pct || 0), pRaw = Number(pPool.call_share_pct || 0);
      if ((gRaw + pRaw) > 0.01) { gPct = Number(((gRaw / (gRaw + pRaw)) * 100).toFixed(1)); pPct = Number((100 - gPct).toFixed(1)); }
    }
    const tts = qp.tier_target_split;
    if ((gTgt + pTgt) < 0.5 && tts && Number.isFinite(Number(tts.google_target_pct))) {
      gTgt = clampPct(Number(tts.google_target_pct));
      pTgt = clampPct(Number(tts.partner_target_pct != null ? tts.partner_target_pct : (100 - gTgt)));
    } else if ((gTgt + pTgt) < 0.5) {
      const is5x = String(qp.active_tier_profile || "").toLowerCase() === "ultra-5x";
      gTgt = is5x ? 75 : 90; pTgt = is5x ? 25 : 10;
    } else {
      const sumT = gTgt + pTgt;
      gTgt = Number(((gTgt / sumT) * 100).toFixed(1));
      pTgt = Number((100 - gTgt).toFixed(1));
    }
    return { gPct, pPct, gTgt, pTgt, targetLabel: fmtSplitPair(gTgt, pTgt), g24, p24, has24, isZero: (gPct + pPct) < 0.05 };
  }

  function renderPoolSplitCard(bundle, metric) {
    const qp = bundle.quota_and_pools || {};
    const pools = qp.pools || {};
    const sp = derivePoolSplit(bundle, metric);
    const tier = String(qp.active_tier_profile || "ultra-20x");
    const tierHtml = tier.startsWith("ultra-")
      ? `<span class="v9-tier-pfx">ultra-</span>${V9.escHtml(tier.slice(6))}` : V9.escHtml(tier);
    const tot429 = Number((pools.google && pools.google.total_429_count) || 0) + Number((pools.claude && pools.claude.total_429_count) || 0);
    const mainShort = shortModelName(qp.active_mainchat_model);
    const metricLbl = metric === "cost" ? "$ Cost" : (metric === "tokens" ? "Tokens" : "Steps");
    const sub24hText = sp.g24 != null ? `24h: ${sp.g24.toFixed(1)}% G · ${sp.p24.toFixed(1)}% P` : (sp.has24 ? "24h: 0% activity" : "");
    const tip = `${metricLbl} Pool Split: ${sp.gPct.toFixed(1)}% Gemini / ${sp.pPct.toFixed(1)}% Partner · Target ${sp.targetLabel} (${tier})${sub24hText ? ` · Last ${sub24hText}` : ""}`;

    let fillsHtml = "";
    if (!sp.isZero) {
      if (sp.gPct > 0.01 && sp.pPct > 0.01) {
        fillsHtml = `<span class="v9-split-fill-g" style="flex:${sp.gPct.toFixed(2)} 1 0;min-inline-size:3px"></span><span class="v9-split-fill-p" style="flex:${sp.pPct.toFixed(2)} 1 0;min-inline-size:3px"></span>`;
      } else if (sp.gPct > 0.01) {
        fillsHtml = `<span class="v9-split-fill-g" style="inline-size:${sp.gPct.toFixed(2)}%"></span>`;
      } else {
        fillsHtml = `<span class="v9-split-fill-p" style="inline-size:${sp.pPct.toFixed(2)}%"></span>`;
      }
    }
    const cap24Html = sub24hText
      ? `<div class="v9-split-24h"><span class="v9-24h-word">Last </span>${V9.escHtml(sub24hText)}</div>` : "";
    return `
      <div class="va-kpi-gauge-card" data-state="nominal" title="${V9.escHtml(tip)}">
        <div class="va-kpi-gauge-head">
          <span class="va-kpi-gauge-label">Pool Split</span>
          <span class="va-meta-inline v9-mono-num">Target ${V9.escHtml(sp.targetLabel)}</span>
        </div>
        <div class="v9-split-hero">
          <span class="v9-split-side is-gemini"><strong class="v9-split-pct">${sp.gPct.toFixed(1)}%</strong> <span class="v9-split-lbl">Gemini</span></span>
          <span class="v9-split-side is-partner"><strong class="v9-split-pct">${sp.pPct.toFixed(1)}%</strong> <span class="v9-split-lbl">Partner</span></span>
        </div>
        <div class="v9-split-bar-wrap" role="img" aria-label="${V9.escHtml(tip)}">
          <span class="v9-split-caret" style="inset-inline-start:${sp.gTgt.toFixed(1)}%">${CARET_SVG}</span>
          <div class="v9-split-track">${fillsHtml}</div>
          <span class="v9-split-guide" style="inset-inline-start:${sp.gTgt.toFixed(1)}%"></span>
        </div>
        ${cap24Html}
        <div class="va-kpi-gauge-stats v9-kpi-foot">
          <span>${V9.escHtml(mainShort)} · ${tierHtml} · 429s: ${tot429}</span>
        </div>
      </div>`;
  }

  function classifyZone(usedPct, clkPct, hasReset, isCooldown) {
    if (!hasReset && usedPct <= 0.05) return "standby";
    const lead = hasReset ? (usedPct - clkPct) : 0;
    if (isCooldown || usedPct >= 85 || (hasReset && lead > 15)) return "hot";
    if (hasReset && lead > 0) return "warm";
    return "cool";
  }

  function renderPaceRow({ label, fullName, bucket, defaultWinSec, burn, isCooldown }) {
    const used = clampPct(Number(bucket?.used_pct || 0));
    const hasReset = Boolean(bucket && bucket.has_active_reset);
    const standby = !hasReset && used <= 0.05;
    const clk = standby ? 0 : computeClockPct(bucket, defaultWinSec);
    const zone = classifyZone(used, clk, hasReset, isCooldown);
    const rst = formatCompactReset(bucket);
    const uRnd = Math.round(used);
    const cRnd = Math.round(clk);
    const burnTxt = burn && Number(burn.steps || 0) > 0
      ? ` · Burn: ${V9.fmtNum(burn.steps)}s · ${V9.fmtUsd(burn.cost_usd || 0)}` : "";
    const leadStr = hasReset ? `${used - clk >= 0 ? "+" : ""}${(used - clk).toFixed(1)}pp` : "";
    const tip = standby
      ? `${fullName}: Standby (0% used · untouched rolling timer)${burnTxt}`
      : `${fullName}: ${used.toFixed(1)}% used${hasReset ? ` vs ${clk.toFixed(1)}% elapsed (${leadStr})` : ""} · Resets ${rst.short}${rst.clock ? ` (${rst.clock})` : ""}${burnTxt}`;
    const lblHtml = standby
      ? `<strong>${V9.escHtml(label)}</strong> · Standby`
      : (hasReset
        ? `<strong>${V9.escHtml(label)}</strong> · ${uRnd}%<span class="v9-pace-gap"> </span>/<span class="v9-pace-gap"> </span>${cRnd}%<span class="v9-pace-clk-txt"> clk</span>`
        : `<strong>${V9.escHtml(label)}</strong> · ${uRnd}% used`);
    const rstHtml = standby ? "Ready" : (rst.short === "Due" ? "Due" : `<span class="v9-pace-rst-pfx">rst </span>${V9.escHtml(rst.short)}`);
    return `
      <div class="v9-pace-row" title="${V9.escHtml(tip)}">
        <div class="v9-pace-lbl-row">
          <span class="v9-pace-lbl">${lblHtml}</span>
          <span class="v9-pace-rst">${rstHtml}</span>
        </div>
        <div class="v9-pace-bars">
          <div class="v9-pace-clk-track" aria-hidden="true"><div class="v9-pace-clk-fill" style="inline-size:${clk.toFixed(1)}%"></div></div>
          <progress class="v9-pace-prog" data-zone="${zone}" value="${used.toFixed(1)}" max="100" aria-label="${V9.escHtml(tip)}"></progress>
        </div>
      </div>`;
  }

  function renderQuotaPacingCard(bundle) {
    const qp = bundle.quota_and_pools || {};
    const pools = qp.pools || {};
    const gPool = pools.google || {};
    const pPool = pools.claude || {};
    const lq = qp.live_quota || {};
    const stateCode = String(lq.state || (lq.ls_alive ? "LIVE" : "IDE_OFFLINE"));
    const ageFmt = (V9.Analytics && V9.Analytics.formatSnapshotAge) ? V9.Analytics.formatSnapshotAge(lq.snapshot_age_seconds) : "";
    const ageShort = (ageFmt && ageFmt !== "live" && ageFmt !== "offline") ? ageFmt.replace(" ago", "") : "";
    const hasG = Boolean((gPool.bucket_5h && gPool.bucket_5h.used_pct != null) || (gPool.bucket_weekly && gPool.bucket_weekly.used_pct != null));
    if (!hasG) {
      return `
        <div class="va-kpi-gauge-card" data-state="nominal">
          <div class="va-kpi-gauge-head">
            <span class="va-kpi-gauge-label">Quota Pacing</span>
            <span class="va-pill v9-pace-pill" data-variant="status" data-state="muted" aria-label="IDE OFFLINE"><span class="v9-off-pfx">IDE </span>OFFLINE</span>
          </div>
          <div class="va-kpi-gauge-val v9-quota-main"><span>IDE Offline</span></div>
          <div class="v9-pace-offline-note">Run IDE or quota sync for 5h/Wk clock meters</div>
          <div class="va-kpi-gauge-stats v9-kpi-foot"><span>Partner: Standby · 0% Wk</span></div>
        </div>`;
    }
    const g5 = gPool.bucket_5h || { used_pct: 0, has_active_reset: false };
    const gw = gPool.bucket_weekly || { used_pct: 0, has_active_reset: false };
    const p5 = pPool.bucket_5h || { used_pct: 0, has_active_reset: false };
    const pw = pPool.bucket_weekly || { used_pct: 0, has_active_reset: false };
    const p5Used = clampPct(Number(p5.used_pct || 0));
    const pWkUsed = clampPct(Number(pw.used_pct || 0));
    const partnerActive = p5Used > 0.05 || pWkUsed > 0.05;
    const rows = [
      { label: "G 5h", fullName: "Gemini 5h", bucket: g5, defaultWinSec: 18000, burn: gPool.burn_5h, isCooldown: gPool.status === "COOLDOWN_429" },
      { label: "G Wk", fullName: "Gemini Weekly", bucket: gw, defaultWinSec: 604800, burn: gPool.burn_7d, isCooldown: false },
    ];
    if (p5Used > 0.05) rows.push({ label: "P 5h", fullName: "Partner 5h", bucket: p5, defaultWinSec: 18000, burn: pPool.burn_5h, isCooldown: pPool.status === "COOLDOWN_429" });
    if (pWkUsed > 0.05) rows.push({ label: "P Wk", fullName: "Partner Weekly", bucket: pw, defaultWinSec: 604800, burn: pPool.burn_7d, isCooldown: false });

    const zones = rows.map((r) => classifyZone(clampPct(Number(r.bucket?.used_pct || 0)), computeClockPct(r.bucket, r.defaultWinSec), Boolean(r.bucket?.has_active_reset), r.isCooldown));
    const isStale = stateCode === "STALE";
    const isOff = stateCode === "IDE_OFFLINE" || lq.ls_alive === false;
    let pillHtml = "ON PACE", pillAria = "", pillState = "nominal", pillCls = "v9-pace-pill is-cool", cardState = "nominal";
    if (isStale) {
      pillHtml = ageShort ? `STALE · ${V9.escHtml(ageShort)}` : "STALE";
      pillState = "warn"; pillCls = "v9-pace-pill"; cardState = "warn";
    } else if (isOff && !lq.is_fresh) {
      pillAria = ageShort ? `IDE OFFLINE · ${ageShort}` : "IDE OFFLINE";
      pillHtml = ageShort ? `<span class="v9-off-pfx">IDE </span>OFFLINE · ${V9.escHtml(ageShort)}` : `<span class="v9-off-pfx">IDE </span>OFFLINE`;
      pillState = "muted"; pillCls = "v9-pace-pill";
    } else if (zones.includes("hot") || gPool.status === "COOLDOWN_429" || pPool.status === "COOLDOWN_429") {
      pillHtml = "HOT"; pillState = "fault"; pillCls = "v9-pace-pill"; cardState = "warn";
    } else if (zones.includes("warm")) {
      pillHtml = "WARM"; pillState = "warn"; pillCls = "v9-pace-pill"; cardState = "warn";
    }
    const pWkRst = formatCompactReset(pw);
    const pWkClk = pw.has_active_reset ? ` (${computeClockPct(pw, 604800).toFixed(0)}% clk${pWkRst.clock ? ` · ${pWkRst.clock}` : ""})` : "";
    const pFootText = partnerActive
      ? (p5Used <= 0.05 ? `P 5h: Standby · 7d burn ${V9.fmtUsd((gPool.burn_7d?.cost_usd || 0) + (pPool.burn_7d?.cost_usd || 0))}` : `7d burn ${V9.fmtUsd((gPool.burn_7d?.cost_usd || 0) + (pPool.burn_7d?.cost_usd || 0))}`)
      : `<span class="v9-p-standby-full">Partner: </span>Standby · 0% Wk${pw.has_active_reset ? ` · <span class="v9-pace-rst-pfx">rst </span>${V9.escHtml(pWkRst.short)}` : ""}`;
    const pFootTip = partnerActive ? "Active quota window burn" : `Partner Pool Standby: 5h 0% · Wk 0% used${pWkClk}`;
    return `
      <div class="va-kpi-gauge-card" data-state="${cardState}">
        <div class="va-kpi-gauge-head">
          <span class="va-kpi-gauge-label">Quota Pacing</span>
          <span class="va-pill ${pillCls}" data-variant="status" data-state="${pillState}"${pillAria ? ` aria-label="${V9.escHtml(pillAria)}"` : ""}>${pillHtml}</span>
        </div>
        <div class="v9-pace-list${(isStale || (isOff && !lq.is_fresh)) ? " is-dimmed" : ""}">
          ${rows.map((r) => renderPaceRow(r)).join("")}
        </div>
        <div class="va-kpi-gauge-stats v9-kpi-foot" title="${V9.escHtml(pFootTip)}"><span>${pFootText}</span></div>
      </div>`;
  }

  V9.QuotaCards = { renderPoolSplitCard, renderQuotaPacingCard, derivePoolSplit, computeClockPct, classifyZone };
})();
