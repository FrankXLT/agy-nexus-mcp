// AGY-NEXUS Overwatch — Deterministic Multi-Window Demo Telemetry & Workspace Generator (v3.1.0)

const SAMPLE_CODE_HEALTH = {
  version: {
    installed: "3.1.0",
    remote: "v3.1.0",
    status: "up_to_date",
    status_label: "Up to Date (v3.1.0)",
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
      { name: "polyglot_index.py", lines: 426, status: "compliant", symbols: 10, long_functions: 0 },
      { name: "tools_media.py", lines: 426, status: "compliant", symbols: 7, long_functions: 0 },
      { name: "stats.py", lines: 415, status: "compliant", symbols: 3, long_functions: 0 },
      { name: "middleware.py", lines: 407, status: "compliant", symbols: 6, long_functions: 0 },
      { name: "config.py", lines: 387, status: "compliant", symbols: 16, long_functions: 0 },
      { name: "tools_session.py", lines: 370, status: "compliant", symbols: 4, long_functions: 0 },
      { name: "target_resolver.py", lines: 335, status: "compliant", symbols: 11, long_functions: 0 },
      { name: "web_routes.py", lines: 230, status: "compliant", symbols: 1, long_functions: 0 },
      { name: "retirement.py", lines: 177, status: "compliant", symbols: 8, long_functions: 0 },
      { name: "tools_praxis.py", lines: 167, status: "compliant", symbols: 7, long_functions: 0 },
    ],
  },
  polyglot_health: { indexed_files: 87, total_symbols: 412, long_functions_over_100: 2 },
  ast_integrity: { clean: true, undefined_count: 0, undefined_names: 0, scanned_files: 36, flagged_modules: 0, total_symbols: 412, details: {} },
  local_lsp: { engine: "praxis+serena", installed: true, available: true, version: "v3.1.0", status: "ready" },
};

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
    version: "3.1.0",
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
    wire_telemetry: { total_recorded_calls: 184, avg_kb: 9.8, max_kb: 18.9, total_mcp_tokens: 412800, budget_compliance_pct: 100.0, by_product: { "Gemini Mobile": { calls: 112 }, "Gemini Web / Cloud MCP": { calls: 72 } } },
    routing_telemetry: { active_slots: 3, pinned_calls: 18, auto_resolved_calls: 7 },
    backup_321: { ok: true, short_sha: "55d0304", shas_match: true, age: "1h ago" },
    project_session_tree: { ascii_tree: "AGY-NEXUS // DEMO PROJECT -> CHAT -> SESSION ID HIERARCHY\n[PROJECT 1] NexusMesh ANMS\n  ├─ [HANDOFF nexus-mesh-telemetry-01] IN-WORK -> claimed\n  └─ [#1] Canvas Node Optimization & Redis\n[PROJECT 2] Core Infrastructure & Container GitOps\n  ├─ [HANDOFF agy-nexus-mcp-02] STAGED (unclaimed / new chat)\n  └─ [#2] AGY-Nexus v3.1.0 Unified Studio Shell\n[PROJECT 3] quiet-ui-skills (0 sessions · 1 staged)\n  └─ [HANDOFF quiet-ui-skills-02] STAGED (unclaimed / new chat)" },
    code_health: JSON.parse(JSON.stringify(SAMPLE_CODE_HEALTH)),
  };
}

function makeDemoThumbSvg(title, sub, accent, badge) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="400" viewBox="0 0 640 400"><rect width="640" height="400" fill="#f8fafc"/><rect x="16" y="16" width="608" height="36" rx="6" fill="#ffffff" stroke="#e2e8f0"/><circle cx="34" cy="34" r="5" fill="${accent}"/><text x="48" y="39" font-family="monospace" font-size="13" font-weight="700" fill="#0f172a">AGY-NEXUS v3.1.0 // ${badge}</text><rect x="16" y="66" width="192" height="318" rx="6" fill="#ffffff" stroke="#e2e8f0"/><rect x="30" y="84" width="130" height="10" rx="3" fill="${accent}" opacity="0.85"/><rect x="30" y="108" width="160" height="8" rx="3" fill="#cbd5e1"/><rect x="30" y="126" width="144" height="8" rx="3" fill="#e2e8f0"/><rect x="30" y="144" width="152" height="8" rx="3" fill="#e2e8f0"/><rect x="222" y="66" width="402" height="148" rx="6" fill="#ffffff" stroke="#e2e8f0"/><text x="240" y="96" font-family="sans-serif" font-size="16" font-weight="700" fill="#0f172a">${title}</text><text x="240" y="120" font-family="monospace" font-size="12" fill="#475569">${sub}</text><rect x="240" y="142" width="110" height="52" rx="5" fill="${accent}" opacity="0.14"/><rect x="362" y="142" width="110" height="52" rx="5" fill="${accent}" opacity="0.28"/><rect x="484" y="142" width="120" height="52" rx="5" fill="${accent}" opacity="0.52"/><rect x="222" y="228" width="402" height="156" rx="6" fill="#ffffff" stroke="#e2e8f0"/><polyline points="242,352 292,318 342,332 392,282 442,296 492,258 542,272 598,248" fill="none" stroke="${accent}" stroke-width="3.5"/></svg>`;
  return "data:image/svg+xml;utf8," + encodeURIComponent(svg);
}

window.DEMO_WORKSPACE_TREE = {
  ok: true,
  selected_session: "b31d6672-9375-4a94-ae14-100000000100",
  queue: {
    staged_count: 2,
    tickets: [
      { handoff_id: "agy-nexus-mcp-02", repo_slug: "agy-nexus-mcp", title: "Unified 42px Studio Shell & Multi-Select Gallery", status: "STAGED", execution_mode: "fast", handoff_mode: "surgical_audit", relative_age: "4m ago", handoff_file: "staged_handoffs/agy-nexus-mcp-02.md" },
      { handoff_id: "nexus-mesh-telemetry-01", repo_slug: "nexus-mesh-telemetry", title: "Canvas Node Optimization & Redis Pipeline", status: "IN_WORK", execution_mode: "auto", handoff_mode: "intent", relative_age: "14m ago", handoff_file: "staged_handoffs/nexus-mesh-telemetry-01.md" },
      { handoff_id: "agy-nexus-mcp-01", repo_slug: "agy-nexus-mcp", title: "Praxis MCP 6-Tool Workstation Doorway", status: "COMPLETED", execution_mode: "plan", handoff_mode: "intent", relative_age: "2h ago", handoff_file: "staged_handoffs/agy-nexus-mcp-01.md" },
    ],
  },
  projects: [
    {
      project_name: "Core Infrastructure & Container GitOps",
      staged_count: 1,
      sessions: [
        { conversation_id: "b31d6672-9375-4a94-ae14-100000000100", title: "AGY-Nexus v3.1.0 Unified Studio Shell", status: "RUNNING", is_running: true, is_pinned: true, step_count: 342 },
        { conversation_id: "b31d6672-9375-4a94-ae14-100000000101", title: "Praxis MCP Doorway & Handoff Queue", status: "IDLE", is_pinned: true, step_count: 218 },
        { conversation_id: "b31d6672-9375-4a94-ae14-100000000102", title: "Host Bridge Zero-Trust CIDR Guard", status: "IDLE", is_pinned: false, step_count: 164 },
      ],
    },
    {
      project_name: "NexusMesh ANMS (Network Telemetry)",
      staged_count: 0,
      sessions: [
        { conversation_id: "a31d6672-9375-4a94-ae14-100000000000", title: "Canvas Node Optimization & Redis", status: "RUNNING", is_running: true, is_pinned: true, step_count: 486 },
        { conversation_id: "a31d6672-9375-4a94-ae14-100000000001", title: "Dynamic Device Graph & SNMP Poller", status: "IDLE", is_pinned: false, step_count: 295 },
      ],
    },
    {
      project_name: "Automation & Edge Security GitOps",
      staged_count: 0,
      sessions: [
        { conversation_id: "c31d6672-9375-4a94-ae14-100000000200", title: "Surveillance 4AM Daily Refinement", status: "IDLE", is_pinned: false, step_count: 412 },
      ],
    },
    {
      project_name: "quantum-dsp-workbench",
      staged_count: 0,
      sessions: [
        { conversation_id: "e31d6672-9375-4a94-ae14-100000000400", title: "[QDSP-Core] Chief Architect & FFT Pipeline", status: "IDLE", is_pinned: false, step_count: 520 },
      ],
    },
  ],
};

const DEMO_THUMBS = [
  { name: "preview_1440x900_analytics.png", rel_path: "preview_1440x900_analytics.png", size: 94200, mtime: Date.now() / 1000 - 240, signed_url: makeDemoThumbSvg("Analytics Surface (1440x900)", "52w Single-Hue #2563eb Matrix + 1h Stacked Bars", "#2563eb", "DESKTOP") },
  { name: "preview_1440x900_workspace.png", rel_path: "preview_1440x900_workspace.png", size: 81600, mtime: Date.now() / 1000 - 210, signed_url: makeDemoThumbSvg("2-Pane Workspace Explorer", "Collapsible Tree + Editorial Reader + Gallery", "#0d9488", "WORKSPACE") },
  { name: "preview_900x1000_foldable.png", rel_path: "preview_900x1000_foldable.png", size: 76400, mtime: Date.now() / 1000 - 180, signed_url: makeDemoThumbSvg("Foldable Inner View (900x1000)", "4-Across KPI Grid + Non-Wrapping Topbar", "#4f46e5", "FOLDABLE") },
  { name: "preview_390x844_mobile.png", rel_path: "preview_390x844_mobile.png", size: 62800, mtime: Date.now() / 1000 - 150, signed_url: makeDemoThumbSvg("Mobile Portrait (390x844)", "1-Row Header + 26w Heatmap + 2x2 KPIs", "#0284c7", "MOBILE") },
];

window.DEMO_SESSION_BUCKET = {
  ok: true,
  conversation_id: "b31d6672-9375-4a94-ae14-100000000100",
  title: "AGY-Nexus v3.1.0 Unified Studio Shell",
  project_name: "Core Infrastructure & Container GitOps",
  repo_slug: "agy-nexus-mcp",
  rollover: { posture: "SEAM_AWARE", reason: "342 steps · 0 compactions · clean working tree", should_rollover: false },
  artifacts: [
    { name: "walkthrough.md", rel_path: "walkthrough.md", size: 6840, mtime: Date.now() / 1000 - 180, type: "artifact" },
    { name: "implementation_plan.md", rel_path: "implementation_plan.md", size: 9120, mtime: Date.now() / 1000 - 900, type: "artifact" },
    { name: "task.md", rel_path: "task.md", size: 4120, mtime: Date.now() / 1000 - 120, type: "artifact" },
    { name: "gemini_research_handoff.md", rel_path: "scratch/gemini_research_handoff.md", size: 9590, mtime: Date.now() / 1000 - 1500, type: "handoff" },
  ],
  uploads: [
    {
      folder_name: "uploads_20261115_064512_ui_audit",
      file_count: 3,
      files: ["topbar_before.png", "mobile_heatmap_notes.png", "INDEX.md"],
      index_rel_path: "scratch/uploads_20261115_064512_ui_audit/INDEX.md",
      app_prompt: "Inspect session upload batch uploads_20261115_064512_ui_audit/INDEX.md",
      signed_images: DEMO_THUMBS.slice(0, 2),
    },
    {
      folder_name: "uploads_20261114_192004_foldable_ux",
      file_count: 2,
      files: ["foldable_kpi_900px.png", "INDEX.md"],
      index_rel_path: "scratch/uploads_20261114_192004_foldable_ux/INDEX.md",
      app_prompt: "Inspect session upload batch uploads_20261114_192004_foldable_ux/INDEX.md",
      signed_images: DEMO_THUMBS.slice(2, 4),
    },
  ],
  visual_artifacts: DEMO_THUMBS,
};

window.DEMO_DOC_FILES = {
  "walkthrough.md": "# AGY-Nexus v3.1.0 Walkthrough\n\n> [!TIP]\n> Unified 42px Studio Shell, 2-Pane Workspace Explorer, Multi-Select Gallery, and In-Place Session Retirement verified across Desktop (`1440x900`), Foldable (`900x1000`), and Mobile (`390x844`).\n\n## Verification Summary\n\n| Gate | Target | Result |\n| :--- | :--- | :--- |\n| `pytest` Suite | 50 unit & regression tests | **50 passed** |\n| `ag_bridge.py --self-test` | 11 Nexus + 6 Praxis MCP tools | **100% PASS** |\n| Modular Hygiene | `<= 500L` target / `650L` ceiling | **0 violations** |\n",
  "implementation_plan.md": "# Implementation Plan — AGY-Nexus v3.1.0\n\n- [x] Unified 42px Studio Topbar (`Analytics` | `Workspace`)\n- [x] Multi-Select Gallery (`gallery_select.js`) + Streaming `.zip` (`bucket_api.py`)\n- [x] Canonical PWA Deep Links & 7-Day Signed `/web/media/`\n- [x] In-Place Terminal Closeout (`retirement.py`, `RETIRED.json`)\n",
  "task.md": "# Session Task Checklist\n\n- [x] Scout repository via `agy-praxis-mcp`\n- [x] Implement 2-Pane Workspace & Multi-Select Gallery\n- [x] Run `flash-auditor` & headless viewport assertions\n",
  "scratch/gemini_research_handoff.md": "# Gemini High Task Handoff (`agy-nexus-mcp-02`)\n\n- **Handoff Mode**: `surgical_audit`\n- **Execution Mode**: `fast`\n- **Workspace**: `/home/dev/workspaces/agy-nexus-mcp`\n\n Verify unified 42px studio header, 26w/53w `#2563eb` heatmap, and Multi-Select Visual Gallery.\n",
};

