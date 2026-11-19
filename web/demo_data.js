// AGY-NEXUS Overwatch — Deterministic Multi-Window Demo Telemetry & Workspace Generator (v3.2.3)

const FALLBACK_CODE_HEALTH = {
  version: {
    installed: "3.2.3",
    remote: "v3.2.3",
    status: "up_to_date",
    status_label: "Up to Date (v3.2.3)",
    status_dot: "#10b981",
    repo: "github.com/FrankXLT/agy-nexus-mcp",
  },
  modular_hygiene: {
    target_lines: 500,
    ceiling_lines: 650,
    total_modules: 36,
    compliant_500: 33,
    warning_501_650: 3,
    violations_over_650: 0,
    compliant_300: 33,
    warning_301_400: 3,
    violations_over_400: 0,
    ceiling_pass: true,
    total_lines: 11890,
    total_symbols: 412,
    long_functions_over_100: 2,
    modules: [
      { name: "polyglot_outline.py", lines: 639, status: "warning", symbols: 15, long_functions: 1 },
      { name: "bucket_api.py", lines: 548, status: "warning", symbols: 9, long_functions: 0 },
      { name: "handoff_queue.py", lines: 538, status: "warning", symbols: 17, long_functions: 0 },
      { name: "server.py", lines: 498, status: "compliant", symbols: 5, long_functions: 1 },
      { name: "handoff.py", lines: 488, status: "compliant", symbols: 9, long_functions: 0 },
      { name: "workspace.py", lines: 477, status: "compliant", symbols: 10, long_functions: 0 },
      { name: "session_status.py", lines: 454, status: "compliant", symbols: 12, long_functions: 0 },
      { name: "polyglot_index.py", lines: 469, status: "compliant", symbols: 12, long_functions: 0 },
      { name: "tools_media.py", lines: 461, status: "compliant", symbols: 8, long_functions: 0 },
      { name: "stats.py", lines: 415, status: "compliant", symbols: 3, long_functions: 0 },
      { name: "middleware.py", lines: 413, status: "compliant", symbols: 6, long_functions: 0 },
      { name: "config.py", lines: 442, status: "compliant", symbols: 17, long_functions: 0 },
      { name: "tools_session.py", lines: 383, status: "compliant", symbols: 4, long_functions: 0 },
      { name: "target_resolver.py", lines: 335, status: "compliant", symbols: 11, long_functions: 0 },
      { name: "web_routes.py", lines: 233, status: "compliant", symbols: 1, long_functions: 0 },
      { name: "retirement.py", lines: 193, status: "compliant", symbols: 8, long_functions: 0 },
      { name: "tools_praxis.py", lines: 169, status: "compliant", symbols: 7, long_functions: 0 },
    ],
  },
  polyglot_health: { indexed_files: 87, total_symbols: 412, long_functions_over_100: 2 },
  ast_integrity: { clean: true, undefined_count: 0, undefined_names: 0, scanned_files: 36, flagged_modules: 0, total_symbols: 412, details: {} },
  local_lsp: { engine: "praxis+serena", installed: true, available: true, version: "v3.2.3", status: "ready" },
};
const SAMPLE_CODE_HEALTH = (typeof window !== "undefined" && window.DEMO_SNAPSHOT && window.DEMO_SNAPSHOT.code_health) ? window.DEMO_SNAPSHOT.code_health : FALLBACK_CODE_HEALTH;

const DEMO_PROJECTS_CATALOG = [
  { id: "p-nexus-mesh", name: "NexusMesh ANMS (Network Telemetry)", repo: "nexus-mesh-telemetry", chats: ["Canvas Node Optimization & Redis", "Dynamic Device Graph", "SNMP Poller Tuning", "RRD Export Bridge"] },
  { id: "p-core-gitops", name: "Core Infrastructure & Container GitOps", repo: "agy-nexus-mcp", chats: ["AGY-Nexus v3.1.0 Unified Studio Shell", "Praxis MCP Doorway & Handoff Queue", "Host Bridge Zero-Trust", "Multi-Select Visual Gallery", "3-2-1 Bundle Cron"] },
  { id: "p-auto-edge", name: "Automation & Edge Security GitOps", repo: "automation-gitops", chats: ["Surveillance 4AM Daily Refinement", "Mobile Wall Panel Redesign", "Presence Sensor Debounce"] },
  { id: "p-chronos", name: "chronos-board", repo: "chronos-board", chats: ["Phase 1 Sprints & Counter-Events", "Sunburst & Chord Legend", "Time-Block Sync"] },
  { id: "p-qdsp", name: "quantum-dsp-workbench", repo: "quantum-dsp-workbench", chats: ["[QDSP-Core] Chief Architect", "[QDSP-Learn-RF] Data Comms", "[QDSP-Portal] Shell UI"] },
  { id: "p-rf-lab", name: "rf-signal-lab", repo: "rf-signal-lab", chats: ["RF Spectrum Lab Edition 6", "IQ Constellation Demod"] },
  { id: "p-mail-ai", name: "mail-taxonomy-ai", repo: "mail-taxonomy-ai", chats: ["Classifier Pipeline & Rules", "Batch Triage Worker"] },
  { id: "p-edge-node", name: "edge-sensor-node", repo: "edge-sensor-node", chats: ["ESPHome BLE Gateway", "MQTT Sparkplug Payloads"] },
  { id: "p-doc-forge", name: "knowledge-vault-sync", repo: "knowledge-vault-sync", chats: ["SHA-256 Notebook Deduplication"] },
  { id: "p-sec-audit", name: "zero-trust-auditor", repo: "zero-trust-auditor", chats: ["CIDR & Token Rotation Gate", "TLS Cert Inspector"] },
  { id: "p-legacy-cli", name: "cli-bench-harness", repo: "cli-bench-harness", chats: ["Latency Micro-Benchmarks"] },
  { id: "p-lab-sandbox", name: "wasm-dsp-sandbox", repo: "wasm-dsp-sandbox", chats: ["SIMD FFT Prototype"] },
];

function seededWave(seed, idx) {
  const x = Math.sin((idx + 1) * 0.43 + seed * 1.91) * 0.5 + 0.5;
  const burst = Math.pow(Math.sin((idx + 3) * 0.17 + seed * 2.73) * 0.5 + 0.5, 3.0);
  return Math.max(0, x * 0.38 + burst * 0.92 - 0.18);
}

function generateDemoBundle(periodKey) {
  const pk = VALID_PERIODS.includes(periodKey) ? periodKey : "current_month";
  const snap = (typeof window !== "undefined" && window.DEMO_SNAPSHOT && window.DEMO_SNAPSHOT.bundles) ? window.DEMO_SNAPSHOT : null;
  if (snap && snap.bundles && snap.bundles[pk]) {
    const out = JSON.parse(JSON.stringify(snap.bundles[pk]));
    out.code_health = JSON.parse(JSON.stringify(snap.code_health || SAMPLE_CODE_HEALTH));
    return out;
  }
  const cfgMap = {
    current_month: { days: 15, stepH: 1, label: "Current Month · Nov 2026", res: "1h sub-daily", nProj: 8, startIso: "2026-11-01" },
    last_month:    { days: 31, stepH: 1, label: "Last Month · Oct 2026",    res: "1h sub-daily", nProj: 10, startIso: "2026-10-01" },
    last_90d:      { days: 90, stepH: 1, label: "Rolling 90 Days",          res: "1h sub-daily", nProj: 12, startIso: "2026-08-18" },
    last_year:     { days: 364, stepH: 24, label: "Rolling 52 Weeks",       res: "daily",        nProj: 12, startIso: "2025-11-17" },
  };
  const cfg = cfgMap[pk];
  const sParts = cfg.startIso.split("-").map(Number);
  const startUtc = Date.UTC(sParts[0], sParts[1] - 1, sParts[2]);
  const endUtc = startUtc + (cfg.days - 1) * 86400000;
  const todayUtc = Date.UTC(2026, 10, 15);
  const calStartUtc = Date.UTC(2025, 10, 17); // Monday 52w anchor
  const calEndUtc = pk === "current_month" ? Date.UTC(2026, 10, 30) : todayUtc;
  const dates = [];
  const heatmap_series = [];

  for (let d = 0; d < cfg.days; d++) {
    const dt = new Date(startUtc + d * 86400000);
    const dIso = dt.toISOString().slice(0, 10);
    if (cfg.stepH === 24) {
      dates.push(dIso);
    } else {
      for (let h = 0; h < 24; h += cfg.stepH) {
        if (pk === "current_month" && d === cfg.days - 1 && h > 16) continue;
        dates.push(`${dIso} ${String(h).padStart(2, "0")}:00`);
      }
    }
  }
  for (let ts = calStartUtc, idx = 0; ts <= calEndUtc; ts += 86400000, idx++) {
    const dt = new Date(ts);
    const dIso = dt.toISOString().slice(0, 10);
    const wd = (dt.getUTCDay() + 6) % 7;
    if (ts > todayUtc) {
      heatmap_series.push({ date: dIso, weekday: wd, steps: 0, tools: 0, tokens: 0, sessions: 0, level: -1, future: true, in_window: false });
      continue;
    }
    const daySteps = Math.round(seededWave(3.1, idx) * (wd >= 5 ? 2400 : 4800));
    const lvl = daySteps === 0 ? 0 : (daySteps < 900 ? 1 : (daySteps < 2100 ? 2 : (daySteps < 3400 ? 3 : 4)));
    const inWin = ts >= startUtc && ts <= endUtc;
    heatmap_series.push({ date: dIso, weekday: wd, steps: daySteps, tools: Math.round(daySteps * 0.52), tokens: daySteps * 380, sessions: daySteps > 0 ? (2 + (idx % 6)) : 0, level: lvl, future: false, in_window: inWin });
  }

  const nBins = dates.length;
  const scale = cfg.stepH === 1 ? 85 : (cfg.stepH === 2 ? 165 : (cfg.stepH === 6 ? 480 : 1850));
  const activeCatalog = DEMO_PROJECTS_CATALOG.slice(0, cfg.nProj);
  const builtProjs = activeCatalog.map((pDef, pIdx) => {
    const pStepsArr = new Array(nBins).fill(0);
    const pToksArr = new Array(nBins).fill(0);
    let pWinSteps = 0;
    let pWinToks = 0;
    const sessions = pDef.chats.map((cTitle, sIdx) => {
      const sSteps = new Array(nBins).fill(0);
      const sToks = new Array(nBins).fill(0);
      const phaseStart = (sIdx / Math.max(1, pDef.chats.length)) * 0.65;
      const phaseEnd = Math.min(1.0, phaseStart + 0.52);
      let sw = 0;
      for (let i = 0; i < nBins; i++) {
        const rel = i / Math.max(1, nBins - 1);
        const env = (rel >= phaseStart && rel <= phaseEnd) ? 1.0 : 0.18;
        const rawW = seededWave(pIdx * 3.7 + sIdx * 1.9 + 1.1, i) * env;
        const v = rawW > 0.24 ? Math.max(2, Math.round(rawW * Math.pow(0.83, pIdx) * scale)) : 0;
        sSteps[i] = v;
        sToks[i] = v * 385;
        pStepsArr[i] += v;
        pToksArr[i] += v * 385;
        sw += v;
      }
      pWinSteps += sw;
      pWinToks += sw * 385;
      return {
        index: String(pIdx * 4 + sIdx + 1),
        conversation_id: `${(pIdx + 10).toString(16)}31d667-9375-4a94-ae14-${String(100000000000 + pIdx * 100 + sIdx)}`,
        title: cTitle,
        project_id: pDef.id,
        project_name: pDef.name,
        workspace_path: sIdx > 0 ? `/home/dev/.gemini/antigravity/worktrees/${pDef.repo}/feat_${sIdx}` : `/home/dev/gitlab/${pDef.repo}`,
        workspace_short: sIdx > 0 ? `feat_${sIdx}` : pDef.repo,
        status: (pIdx === 0 && sIdx === 0) ? "RUNNING" : "IDLE",
        is_running: pIdx === 0 && sIdx === 0,
        is_pinned: pIdx < 2 && sIdx === 0,
        mode: sIdx > 0 ? "WORKTREE" : (pIdx === 0 ? "MAIN WRITER" : "MAIN TREE"),
        window_steps: sw,
        window_tokens: sw * 385,
        step_count: sw + 420,
        subagent_runs: Math.max(1, Math.round(sw / 450)),
        relative_age: `${pIdx * 2 + sIdx + 1}h ago`,
        shade_idx: sIdx,
        shade_count: pDef.chats.length,
        steps_series: sSteps,
        tokens_series: sToks,
      };
    });
    return {
      project_id: pDef.id,
      project_name: pDef.name,
      shared_repo: pDef.chats.length >= 3,
      running_count: pIdx === 0 ? 1 : 0,
      pinned_count: pIdx < 2 ? 1 : 0,
      window_steps: pWinSteps,
      window_tokens: pWinToks,
      total_steps: pWinSteps + 900,
      active_sessions_count: sessions.length,
      steps_series: pStepsArr,
      tokens_series: pToksArr,
      sessions,
    };
  }).sort((a, b) => b.window_steps - a.window_steps);

  const velSteps = new Array(nBins).fill(0);
  const velToks = new Array(nBins).fill(0);
  builtProjs.forEach((p) => {
    for (let i = 0; i < nBins; i++) {
      velSteps[i] += p.steps_series[i];
      velToks[i] += p.tokens_series[i];
    }
  });
  const totWinSteps = Math.max(1, velSteps.reduce((a, b) => a + b, 0));
  const totWinToks = velToks.reduce((a, b) => a + b, 0);

  builtProjs.forEach((p, idx) => {
    p.color_slot = idx < 10 ? idx : 10;
    p.share_pct = Number(((p.window_steps / totWinSteps) * 100).toFixed(1));
    p.sessions.forEach((s) => { s.share_pct = Number(((s.window_steps / totWinSteps) * 100).toFixed(1)); });
  });

  const top_projects = builtProjs.slice(0, 10);
  const nexusMeshProj = top_projects.find((p) => p.project_id === "p-nexus-mesh");
  if (nexusMeshProj && nexusMeshProj.sessions[0]) {
    nexusMeshProj.staged_count = 0;
    nexusMeshProj.in_work_handoff_count = 1;
    nexusMeshProj.superseded_count = 0;
    nexusMeshProj.staged_handoffs = [{
      handoff_id: "nexus-mesh-telemetry-01", repo_slug: "nexus-mesh-telemetry",
      title: "Canvas Node Optimization & Redis Pipeline", status: "IN_WORK",
      execution_mode: "auto", handoff_mode: "intent",
      workspace_path: "/home/dev/workspaces/nexus-mesh-telemetry",
      claimed_by_conversation_id: nexusMeshProj.sessions[0].conversation_id,
      chars_written: 4820, relative_age: "14m ago",
    }];
  }
  const coreGitopsProj = top_projects.find((p) => p.project_id === "p-core-gitops");
  if (coreGitopsProj) {
    coreGitopsProj.staged_count = 1;
    coreGitopsProj.in_work_handoff_count = 0;
    coreGitopsProj.superseded_count = 1;
    coreGitopsProj.staged_handoffs = [
      {
        handoff_id: "agy-nexus-mcp-02", repo_slug: "agy-nexus-mcp",
        title: "Unified Perceptual OKLCH Heatmap & Praxis Doorway", status: "STAGED",
        execution_mode: "plan", handoff_mode: "intent",
        workspace_path: "/home/dev/workspaces/agy-nexus-mcp",
        chars_written: 6410, relative_age: "4m ago",
      },
      {
        handoff_id: "agy-nexus-mcp-01", repo_slug: "agy-nexus-mcp",
        title: "Initial Polyglot Doorway Rename Draft", status: "SUPERSEDED",
        superseded_by: "agy-nexus-mcp-02", execution_mode: "plan", handoff_mode: "intent",
        workspace_path: "/home/dev/workspaces/agy-nexus-mcp",
        chars_written: 3120, relative_age: "28m ago",
      },
    ];
  }
  const idle_projects = [{
    project_id: "ws:quiet-ui-skills", project_name: "quiet-ui-skills",
    is_rollup: false, color_slot: -1, running_count: 0, pinned_count: 0,
    staged_count: 1, in_work_handoff_count: 0, superseded_count: 1,
    window_steps: 0, window_tokens: 0, share_pct: 0,
    steps_series: new Array(nBins).fill(0), tokens_series: new Array(nBins).fill(0),
    sessions: [],
    staged_handoffs: [
      {
        handoff_id: "quiet-ui-skills-02", repo_slug: "quiet-ui-skills",
        title: "4-Surface Multi-Hue Sequential Heatmap Spec", status: "STAGED",
        execution_mode: "plan", handoff_mode: "research",
        workspace_path: "/home/dev/workspaces/quiet-ui-skills",
        chars_written: 5280, relative_age: "2m ago",
      },
      {
        handoff_id: "quiet-ui-skills-01", repo_slug: "quiet-ui-skills",
        title: "Tableau-10 Palette Exploration", status: "SUPERSEDED",
        superseded_by: "quiet-ui-skills-02", execution_mode: "plan", handoff_mode: "research",
        workspace_path: "/home/dev/workspaces/quiet-ui-skills",
        chars_written: 2890, relative_age: "19m ago",
      },
    ],
  }];
  let other_projects = null;
  if (builtProjs.length > 10) {
    const ovf = builtProjs.slice(10);
    const oSteps = new Array(nBins).fill(0);
    const oToks = new Array(nBins).fill(0);
    let oWin = 0;
    const oSess = [];
    ovf.forEach((op) => {
      oWin += op.window_steps;
      for (let i = 0; i < nBins; i++) { oSteps[i] += op.steps_series[i]; oToks[i] += op.tokens_series[i]; }
      op.sessions.forEach((s) => oSess.push(s));
    });
    other_projects = {
      project_id: "__other_projects__", project_name: "Other Projects", is_rollup: true, color_slot: 10,
      projects_count: ovf.length, running_count: 0, pinned_count: 0, window_steps: oWin, window_tokens: oWin * 385,
      share_pct: Number(((oWin / totWinSteps) * 100).toFixed(1)), steps_series: oSteps, tokens_series: oToks, sessions: oSess,
    };
  }

  // Split velSteps exactly across the 5 model families (with strong Carbon 4 + Argon + Flash shares)
  const mShares = pk === "current_month" ? [0.26, 0.42, 0.27, 0.04, 0.01] : [0.18, 0.46, 0.30, 0.05, 0.01];
  const mKeys = ["carbon", "argon_pro", "flash", "claude_partner", "gpt_oss"];
  const modLayers = { carbon: [], argon_pro: [], flash: [], claude_partner: [], gpt_oss: [] };
  const modTokLayers = { carbon: [], argon_pro: [], flash: [], claude_partner: [], gpt_oss: [] };
  for (let i = 0; i < nBins; i++) {
    const tot = velSteps[i];
    let rem = tot;
    mKeys.forEach((mk, mi) => {
      const v = mi === mKeys.length - 1 ? rem : Math.min(rem, Math.round(tot * mShares[mi]));
      rem -= v;
      modLayers[mk].push(v);
      modTokLayers[mk].push(v * 385);
    });
  }

  const subRoles = [
    ["flash-surgeon", 0.34, "Flash 3.8"],
    ["flash-auditor", 0.21, "Flash 3.8"],
    ["argon-sentinel", 0.16, "Argon 4 Pro"],
    ["argon-surgeon", 0.12, "Argon 4 Pro"],
    ["flash-scout", 0.10, "Flash 3.8"],
    ["research", 0.05, "Carbon 4 (inherit)"],
    ["claude-specialist", 0.02, "Claude 5.5"],
  ];
  const subLayers = {};
  const subTokLayers = {};
  const subBreakdown = {};
  subRoles.forEach(([rk, sh, domLbl], rIdx) => {
    const arr = velSteps.map((v, i) => Math.round(v * 0.28 * sh * (0.7 + 0.6 * seededWave(rIdx + 5, i))));
    const sSum = arr.reduce((a, b) => a + b, 0);
    subLayers[rk] = arr;
    subTokLayers[rk] = arr.map((v) => v * 360);
    subBreakdown[rk] = { runs: Math.max(2, Math.round(sSum / 190)), steps: sSum, tokens: sSum * 360, share_pct: Number((sh * 100).toFixed(1)), dominant_model_label: domLbl };
  });

  const mMeta = [
    ["carbon", "Gemini 4 Carbon", "20x Google Ultra", 25.0],
    ["argon_pro", "Gemini 4 Argon (Pro)", "20x Google Ultra", 40.0],
    ["flash", "Gemini 3.8 Flash", "20x Google Ultra", 25.0],
    ["claude_partner", "Claude Sonnet/Opus 5.5", "Partner Pool (Weekly)", 8.0],
    ["gpt_oss", "GPT-OSS 120B", "Partner Pool (Failover)", 2.0],
  ];
  const model_usage_vs_target = mMeta.map(([mk, lbl, pool, tp], idx) => {
    const calls = Math.round(modLayers[mk].reduce((a, b) => a + b, 0) * 0.46);
    const ap = Number((mShares[idx] * 100).toFixed(1));
    return { model_key: mk, label: lbl, pool, actual_calls: calls, est_tokens: calls * 820, actual_pct: ap, target_pct: tp, delta_pct: Number((ap - tp).toFixed(1)), status: "ON_TARGET" };
  });

  const winActiveDays = heatmap_series.filter((d) => d.in_window && d.steps > 0).length;
  return {
    server: "agy-nexus-mcp",
    version: "3.2.3",
    period: { key: pk, label: cfg.label, resolution: cfg.res, active_days: winActiveDays, total_days: cfg.days },
    kpis: { total_conversations: builtProjs.reduce((a, p) => a + p.sessions.length, 0), total_subagents_spawned: 148, window_steps: totWinSteps, period_steps: totWinSteps, window_tool_calls: Math.round(totWinSteps * 0.51), window_tokens: totWinToks, active_days: winActiveDays },
    quota_and_pools: { active_tier_profile: "ultra-20x", pools: { google: { status: "HEALTHY" }, claude: { status: "HEALTHY" } }, partner_weekly_pacing: { day_of_week_index: 3, daily_target_pct: 14.28, recommended_cumulative_ceiling_pct: 42.8 } },
    model_usage_vs_target,
    subagent_role_breakdown: subBreakdown,
    top_workspaces: top_projects.map((p) => ({ workspace: p.project_name, sessions: p.sessions.length, steps: p.window_steps, tokens: p.window_tokens, share_pct: p.share_pct })),
    velocity_series: { dates, step_hours: cfg.stepH, values: velSteps, token_values: velToks, resolution: cfg.res },
    model_series: { keys: mKeys, dates, step_hours: cfg.stepH, layers: modLayers, token_layers: modTokLayers, resolution: cfg.res },
    subagent_series: { keys: subRoles.map((r) => r[0]), dates, step_hours: cfg.stepH, layers: subLayers, token_layers: subTokLayers, resolution: cfg.res },
    project_hierarchy: { dates, step_hours: cfg.stepH, resolution: cfg.res, active_projects_count: builtProjs.length, idle_projects_count: 1, top_projects, other_projects, idle_projects },
    heatmap_series,
    wire_telemetry: {
      total_recorded_calls: 184, avg_kb: 8.6, max_kb: 17.4, total_mcp_tokens: 392400, budget_compliance_pct: 100.0,
      protocol_handshakes: { calls: 42, bytes: 382200, tokens: 95550, tools_list_kb: 9.1 },
      by_product: { "Gemini Mobile": { calls: 86 }, "Gemini Web / Cloud MCP": { calls: 52 }, "Antigravity IDE (Praxis MCP)": { calls: 46 } },
    },
    routing_telemetry: { active_slots: 3, pinned_calls: 18, auto_resolved_calls: 7 },
    backup_321: { ok: true, short_sha: "55d0304", shas_match: true, age: "1h ago" },
    project_session_tree: { ascii_tree: "AGY-NEXUS // DEMO PROJECT -> CHAT -> SESSION ID HIERARCHY\n[PROJECT 1] NexusMesh ANMS\n  ├─ [HANDOFF nexus-mesh-telemetry-01] IN-WORK -> claimed\n  └─ [#1] Canvas Node Optimization & Redis\n[PROJECT 2] Core Infrastructure & Container GitOps\n  ├─ [HANDOFF agy-nexus-mcp-02] STAGED (unclaimed / new chat)\n  └─ [#2] AGY-Nexus v3.2.3 Wire Caps & Surgical Fast-Path\n[PROJECT 3] quiet-ui-skills (0 sessions · 1 staged)\n  └─ [HANDOFF quiet-ui-skills-02] STAGED (unclaimed / new chat)" },
    code_health: JSON.parse(JSON.stringify(SAMPLE_CODE_HEALTH)),
  };
}

const FALLBACK_WORKSPACE_TREE = {
  ok: true,
  selected_session: "b31d6672-9375-4a94-ae14-100000000100",
  queue: {
    staged_count: 1,
    tickets: [
      { handoff_id: "agy-nexus-mcp-20", repo_slug: "agy-nexus-mcp", title: "v3.2.3 Real Depersonalized Showcase & Direct PNG Pass", status: "IN_WORK", execution_mode: "plan", handoff_mode: "feature_update", relative_age: "14m ago", handoff_file: "staged_handoffs/agy-nexus-mcp-20.md" },
      { handoff_id: "net-topology-anms-12", repo_slug: "net-topology-anms", title: "Canvas Engine, Bento Solver & Light UI Portal", status: "STAGED", execution_mode: "auto", handoff_mode: "feature_update", relative_age: "28m ago", handoff_file: "staged_handoffs/net-topology-anms-12.md" },
      { handoff_id: "agy-nexus-mcp-19", repo_slug: "agy-nexus-mcp", title: "Wire Caps, Praxis Repo-Map Budget & Surgical Fast-Path", status: "COMPLETED", execution_mode: "plan", handoff_mode: "feature_update", relative_age: "2h ago", handoff_file: "staged_handoffs/agy-nexus-mcp-19.md" },
    ],
  },
  projects: [
    {
      project_name: "AGY Nexus MCP",
      staged_count: 1,
      sessions: [
        { conversation_id: "b31d6672-9375-4a94-ae14-100000000100", title: "AGY-Nexus MCP v3.2.3 — Real Showcase & Privacy Pass", status: "RUNNING", is_running: true, is_pinned: true, step_count: 496, capture_count: 4, relative_age: "5s ago", last_updated_ts: 1795050000 },
        { conversation_id: "b31d6672-9375-4a94-ae14-100000000101", title: "Wire Caps, Praxis Repo-Map & Surgical Fast-Path", status: "COMPLETED", is_pinned: true, step_count: 588, capture_count: 2, relative_age: "2h ago", last_updated_ts: 1795042800 },
      ],
    },
    {
      project_name: "Quiet UI Skills",
      staged_count: 0,
      sessions: [
        { conversation_id: "a31d6672-9375-4a94-ae14-100000000000", title: "Quiet UI v9.0 — Smart Telemetry Domain & Optical Framing", status: "RUNNING", is_running: true, is_pinned: true, step_count: 271, capture_count: 2, relative_age: "12s ago", last_updated_ts: 1795049900 },
      ],
    },
    {
      project_name: "Cloud GitOps Stack",
      staged_count: 0,
      sessions: [
        { conversation_id: "c31d6672-9375-4a94-ae14-100000000200", title: "Infra Ops v2.0 — Portainer Guardrails & MCP Observability", status: "IDLE", is_pinned: false, step_count: 412, capture_count: 0, relative_age: "6h ago", last_updated_ts: 1795028400 },
      ],
    },
  ],
};

window.DEMO_WORKSPACE_TREE = (typeof window !== "undefined" && window.DEMO_SNAPSHOT && window.DEMO_SNAPSHOT.workspace_tree)
  ? window.DEMO_SNAPSHOT.workspace_tree
  : FALLBACK_WORKSPACE_TREE;

const demoTreeProjs = Array.isArray(window.DEMO_WORKSPACE_TREE.projects) ? window.DEMO_WORKSPACE_TREE.projects : [];
const demoSelCid = window.DEMO_WORKSPACE_TREE.selected_session || (demoTreeProjs[0]?.sessions?.[0]?.conversation_id) || "b31d6672-9375-4a94-ae14-100000000100";
let demoSelProj = null, demoSelSess = null;
for (const dp of demoTreeProjs) {
  const hit = (dp.sessions || []).find((s) => s.conversation_id === demoSelCid);
  if (hit) { demoSelProj = dp; demoSelSess = hit; break; }
}

const DEMO_THUMBS = [
  { name: "01_analytics_desktop_1440x900.png", scope: `brain:${demoSelCid}`, rel_path: "01_analytics_desktop_1440x900.png", category: "session", size: 94200, width: 960, height: 600, mtime: Date.now() / 1000 - 240, signed_url: "/web/demo_thumb_desktop.png" },
  { name: "02_workspace_explorer_1440x900.png", scope: `brain:${demoSelCid}`, rel_path: "02_workspace_explorer_1440x900.png", category: "session", size: 81600, width: 960, height: 600, mtime: Date.now() / 1000 - 210, signed_url: "/web/demo_thumb_workspace.png" },
  { name: "03_foldable_inner_900x1000.png", scope: `brain:${demoSelCid}`, rel_path: "03_foldable_inner_900x1000.png", category: "session", size: 76400, width: 720, height: 800, mtime: Date.now() / 1000 - 180, signed_url: "/web/demo_thumb_foldable.png" },
  { name: "04_mobile_portrait_390x844.png", scope: `brain:${demoSelCid}`, rel_path: "04_mobile_portrait_390x844.png", category: "session", size: 62800, width: 390, height: 844, mtime: Date.now() / 1000 - 150, signed_url: "/web/demo_thumb_mobile.png" },
];

const DEMO_REPO_ASSETS = [
  { name: "code-health-watchlist.png", scope: "repo:agy-nexus-mcp", rel_path: "docs/assets/code-health-watchlist.png", category: "repo_asset", size: 51200, width: 960, height: 600, mtime: Date.now() / 1000 - 86400 * 3, signed_url: "/web/demo_thumb_health.png" },
];

const DEMO_ARTIFACTS_BASE = [
  { name: "walkthrough.md", rel_path: "walkthrough.md", size: 6840, mtime: Date.now() / 1000 - 180, type: "artifact" },
  { name: "implementation_plan.md", rel_path: "implementation_plan.md", size: 9120, mtime: Date.now() / 1000 - 900, type: "artifact" },
  { name: "task.md", rel_path: "task.md", size: 4120, mtime: Date.now() / 1000 - 120, type: "artifact" },
  { name: "gemini_research_handoff.md", rel_path: "scratch/gemini_research_handoff.md", size: 9590, mtime: Date.now() / 1000 - 1500, type: "handoff" },
];

window.DEMO_SESSION_BUCKET = {
  ok: true,
  conversation_id: demoSelCid,
  title: (demoSelSess && demoSelSess.title) || "AGY-Nexus MCP v3.2.3 — Real Showcase & Privacy Pass",
  project_name: (demoSelProj && demoSelProj.project_name) || "AGY Nexus MCP",
  repo_slug: "agy-nexus-mcp",
  rollover: { posture: (demoSelSess && demoSelSess.rollover_posture) || "SEAM_AWARE", reason: `${(demoSelSess && demoSelSess.step_count) || 496} steps · clean working tree`, should_rollover: false },
  artifacts: DEMO_ARTIFACTS_BASE,
  uploads: [
    { folder_name: "uploads_20261118_showcase_desktop", file_count: 3, files: ["analytics_desktop.png", "workspace_gallery.png", "INDEX.md"], index_rel_path: "scratch/uploads_20261118_showcase_desktop/INDEX.md", app_prompt: "Evaluate session upload batch uploads_20261118_showcase_desktop/INDEX.md", signed_images: DEMO_THUMBS.slice(0, 2) },
    { folder_name: "uploads_20261118_responsive_pass", file_count: 3, files: ["foldable_900px.png", "mobile_390px.png", "INDEX.md"], index_rel_path: "scratch/uploads_20261118_responsive_pass/INDEX.md", app_prompt: "Evaluate session upload batch uploads_20261118_responsive_pass/INDEX.md", signed_images: DEMO_THUMBS.slice(2, 4) },
  ],
  visual_artifacts: DEMO_THUMBS,
  repo_visual_assets: DEMO_REPO_ASSETS,
};

window.DEMO_SESSION_BUCKETS = { [demoSelCid]: window.DEMO_SESSION_BUCKET };
demoTreeProjs.forEach((dp) => {
  (dp.sessions || []).forEach((s) => {
    if (!s || !s.conversation_id || window.DEMO_SESSION_BUCKETS[s.conversation_id]) return;
    const repoS = (s.workspace_path && String(s.workspace_path).split("/").filter(Boolean).pop()) || "agy-nexus-mcp";
    window.DEMO_SESSION_BUCKETS[s.conversation_id] = {
      ok: true, conversation_id: s.conversation_id, title: s.title, project_name: dp.project_name, repo_slug: repoS,
      rollover: { posture: s.rollover_posture || "FRESH", reason: `${s.step_count || 0} steps · ${s.relative_age || "recent"}`, should_rollover: false },
      artifacts: DEMO_ARTIFACTS_BASE.slice(0, 3), uploads: [], visual_artifacts: Number(s.capture_count) > 0 ? DEMO_THUMBS.slice(0, 2) : [], repo_visual_assets: DEMO_REPO_ASSETS,
    };
  });
});

window.DEMO_DOC_FILES = {
  "walkthrough.md": "# AGY-Nexus v3.2.3 Showcase Walkthrough\n\n> [!TIP]\n> Real depersonalized 52w analytics, 16-workspace hierarchy, Praxis semantic index metrics, and 2-Pane Multi-Select PNG exports verified across Desktop (`1440x900`), Foldable (`900x1000`), and Mobile (`390x844`).\n\n## Verification Summary\n\n| Gate | Target | Result |\n| :--- | :--- | :--- |\n| `pytest` Suite | Regression, privacy & compaction suites | **100% PASS** |\n| `ag_bridge.py --self-test` | 11 Nexus + 6 Praxis MCP tools | **100% PASS** |\n| Modular Hygiene | `<= 500L` target / `650L` ceiling | **0 violations** |\n",
  "implementation_plan.md": "# Implementation Plan — AGY-Nexus v3.2.3\n\n- [x] Praxis Repo-Map Budget (`<= 17.5 KB`) & IDE Client Classification (`polyglot_index.py`, `telemetry_scanner.py`)\n- [x] Proportional Surgical Fast-Path (`handoff_templates.py`, `handoff.py`)\n- [x] Test-Slot Isolation & 17.5 KB Session Tree Cap (`tests/conftest.py`, `config.py`, `tools_ops.py`)\n- [x] Real Depersonalized Showcase Exporter (`scripts/export_depersonalized_showcase.py`, `web/demo_snapshot.js`)\n",
  "task.md": "# Session Task Checklist\n\n- [x] Scout repository via `agy-praxis-mcp`\n- [x] Generate depersonalized `DEMO_SNAPSHOT` & README ASCII tables\n- [x] Capture real desktop & mobile hero assets + run Intra-Google Dual-Review\n",
  "scratch/gemini_research_handoff.md": "# Gemini High Task Handoff (`agy-nexus-mcp-20`)\n\n- **Handoff Mode**: `feature_update`\n- **Execution Mode**: `plan`\n- **Workspace**: `/home/dev/agentic_workspace/projects/agy-nexus-mcp`\n\nReplace synthetic preview cards with real UI captures, hydrate `/web?demo=1` from depersonalized real workstation metrics, and verify `< 20 KB` wire budgets.\n",
};

