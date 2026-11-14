// AGY-NEXUS Overwatch — Deterministic Multi-Window Demo Telemetry Generator (v2.8.0)

const SAMPLE_CODE_HEALTH = {
  version: {
    installed: "2.8.0",
    remote: "v2.7.0",
    status: "staged_locally",
    status_label: "Staged Locally (v2.8.0 > v2.7.0)",
    status_dot: "#5496ff",
    repo: "github.com/FrankXLT/agy-nexus-mcp",
  },
  modular_hygiene: {
    target_lines: 500,
    ceiling_lines: 650,
    total_modules: 33,
    compliant_500: 31,
    warning_501_650: 2,
    violations_over_650: 0,
    compliant_300: 31,
    warning_301_400: 2,
    violations_over_400: 0,
    ceiling_pass: true,
    total_lines: 10140,
    total_symbols: 368,
    long_functions_over_100: 2,
    modules: [
      { name: "polyglot_outline.py", lines: 639, status: "warning", symbols: 15, long_functions: 1 },
      { name: "middleware.py", lines: 543, status: "warning", symbols: 8, long_functions: 1 },
      { name: "server.py", lines: 483, status: "compliant", symbols: 9, long_functions: 0 },
      { name: "handoff_queue.py", lines: 445, status: "compliant", symbols: 13, long_functions: 0 },
      { name: "polyglot_index.py", lines: 412, status: "compliant", symbols: 9, long_functions: 0 },
      { name: "tools_media.py", lines: 398, status: "compliant", symbols: 6, long_functions: 0 },
      { name: "session_tree.py", lines: 372, status: "compliant", symbols: 6, long_functions: 0 },
      { name: "tools_session.py", lines: 371, status: "compliant", symbols: 5, long_functions: 0 },
      { name: "tools_ops.py", lines: 358, status: "compliant", symbols: 4, long_functions: 0 },
      { name: "workspace.py", lines: 357, status: "compliant", symbols: 6, long_functions: 0 },
      { name: "handoff.py", lines: 345, status: "compliant", symbols: 8, long_functions: 0 },
      { name: "session_status.py", lines: 345, status: "compliant", symbols: 8, long_functions: 0 },
      { name: "stats.py", lines: 325, status: "compliant", symbols: 7, long_functions: 0 },
      { name: "config.py", lines: 332, status: "compliant", symbols: 15, long_functions: 0 },
      { name: "tools_praxis.py", lines: 164, status: "compliant", symbols: 7, long_functions: 0 },
      { name: "tools_polyglot.py", lines: 19, status: "compliant", symbols: 1, long_functions: 0 },
    ],
  },
  polyglot_health: { indexed_files: 78, total_symbols: 368, long_functions_over_100: 2 },
  ast_integrity: { clean: true, undefined_count: 0, undefined_names: 0, scanned_files: 33, flagged_modules: 0, total_symbols: 368, details: {} },
  local_lsp: { engine: "praxis+serena", installed: true, available: true, version: "v2.8.0", status: "ready" },
};

const DEMO_PROJECTS_CATALOG = [
  { id: "p-nexus-mesh", name: "NexusMesh ANMS (Network Telemetry)", repo: "nexus-mesh-telemetry", chats: ["Canvas Node Optimization & Redis", "Dynamic Device Graph", "SNMP Poller Tuning", "RRD Export Bridge"] },
  { id: "p-core-gitops", name: "Core Infrastructure & Container GitOps", repo: "agy-nexus-mcp", chats: ["AGY-Praxis MCP v2.8 & Handoff Queue", "Perceptual OKLCH Palette & Heatmap", "Host Bridge Zero-Trust", "Scratch Upload Modal", "3-2-1 Bundle Cron"] },
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
    current_month: { days: 11, stepH: 1, label: "This Month — MTD (Nov 2026)", res: "1h sub-daily", nProj: 8, startIso: "2026-11-01" },
    last_month:    { days: 31, stepH: 2, label: "Last Month (Oct 2026)",       res: "2h sub-daily", nProj: 10, startIso: "2026-10-01" },
    last_90d:      { days: 90, stepH: 6, label: "Rolling 90 Days",             res: "6h sub-daily", nProj: 12, startIso: "2026-08-14" },
    last_year:     { days: 364, stepH: 24, label: "Rolling 52 Weeks",          res: "daily",        nProj: 12, startIso: "2025-11-13" },
  };
  const cfg = cfgMap[pk];
  const sParts = cfg.startIso.split("-").map(Number);
  const startUtc = Date.UTC(sParts[0], sParts[1] - 1, sParts[2]);
  const dates = [];
  const heatmap_series = [];

  for (let d = 0; d < cfg.days; d++) {
    const dt = new Date(startUtc + d * 86400000);
    const dIso = dt.toISOString().slice(0, 10);
    const wd = (dt.getUTCDay() + 6) % 7;
    if (cfg.stepH === 24) {
      dates.push(dIso);
    } else {
      for (let h = 0; h < 24; h += cfg.stepH) {
        if (pk === "current_month" && d === cfg.days - 1 && h > 15) continue;
        dates.push(`${dIso} ${String(h).padStart(2, "0")}:00`);
      }
    }
    const daySteps = Math.round(seededWave(3.1, d) * (wd >= 5 ? 2400 : 4800));
    const lvl = daySteps === 0 ? 0 : (daySteps < 900 ? 1 : (daySteps < 2100 ? 2 : (daySteps < 3400 ? 3 : 4)));
    heatmap_series.push({ date: dIso, weekday: wd, steps: daySteps, tools: Math.round(daySteps * 0.52), tokens: daySteps * 380, sessions: daySteps > 0 ? (2 + (d % 6)) : 0, level: lvl, future: false, in_window: true });
  }
  if (pk === "current_month") {
    for (let f = cfg.days; f < 30; f++) {
      const dt = new Date(startUtc + f * 86400000);
      heatmap_series.push({ date: dt.toISOString().slice(0, 10), weekday: (dt.getUTCDay() + 6) % 7, steps: 0, tools: 0, tokens: 0, sessions: 0, level: -1, future: true, in_window: false });
    }
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

  return {
    server: "agy-nexus-mcp",
    version: "2.8.0",
    period: { key: pk, label: cfg.label, resolution: cfg.res, active_days: heatmap_series.filter((d) => d.steps > 0).length, total_days: cfg.days },
    kpis: { total_conversations: builtProjs.reduce((a, p) => a + p.sessions.length, 0), total_subagents_spawned: 148, window_steps: totWinSteps, period_steps: totWinSteps, window_tool_calls: Math.round(totWinSteps * 0.51), window_tokens: totWinToks, active_days: heatmap_series.filter((d) => d.steps > 0).length },
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
    project_session_tree: { ascii_tree: "AGY-NEXUS // DEMO PROJECT -> CHAT -> SESSION ID HIERARCHY\n[PROJECT 1] NexusMesh ANMS\n  ├─ [HANDOFF nexus-mesh-telemetry-01] IN-WORK -> claimed\n  └─ [#1] Canvas Node Optimization & Redis\n[PROJECT 2] Core Infrastructure & Container GitOps\n  ├─ [HANDOFF agy-nexus-mcp-02] STAGED (unclaimed / new chat)\n  └─ [#2] AGY-Praxis MCP v2.8 & Handoff Queue\n[PROJECT 3] quiet-ui-skills (0 sessions · 1 staged)\n  └─ [HANDOFF quiet-ui-skills-02] STAGED (unclaimed / new chat)" },
    code_health: JSON.parse(JSON.stringify(SAMPLE_CODE_HEALTH)),
  };
}
