const SERIES_COLORS = ["#10b981", "#3b82f6", "#f59e0b", "#8b5cf6", "#ec4899", "#06b6d4"];
    const THEME_META = {
      "obsidian":   { label: "Obsidian",   bg: "#0b0d10", border: "#10b981", themeColor: "#101318" },
      "dark-paper": { label: "Dark Paper", bg: "#21201c", border: "#ede8df", themeColor: "#1c1b18" },
      "warm-paper": { label: "Warm Paper", bg: "#f6f4f0", border: "#525a65", themeColor: "#edeae4" },
      "white":      { label: "Pure White", bg: "#ffffff", border: "#0f172a", themeColor: "#ffffff" }, };
    const VALID_DENSITIES = ["D1", "D2", "D3", "D4"];
    const VALID_PERIODS = ["current_month", "last_month", "last_90d", "last_year"];
    const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const DOW_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    (function migrateLegacyStyle() {
      const legacy = localStorage.getItem("nexus_view_style");
      if (legacy && !localStorage.getItem("nexus_surface")) {
        const idx = legacy.lastIndexOf("-");
        if (idx > 0) {
          localStorage.setItem("nexus_surface", legacy.slice(0, idx));
          localStorage.setItem("nexus_density", legacy.slice(idx + 1)); }
      }
    })();
    const state = {
      passphrase: localStorage.getItem("nexus_passphrase") || sessionStorage.getItem("nexus_passphrase") || "",
      period: VALID_PERIODS.includes(localStorage.getItem("nexus_period")) ? localStorage.getItem("nexus_period") : "current_month",
      surface: THEME_META[localStorage.getItem("nexus_surface")] ? localStorage.getItem("nexus_surface") : "obsidian",
      density: VALID_DENSITIES.includes(localStorage.getItem("nexus_density")) ? localStorage.getItem("nexus_density") : "D2",
      selectedDate: localStorage.getItem("nexus_selected_date") || "",
      demoMode: localStorage.getItem("nexus_demo_mode") === "1",
      bundle: null, };
    function formatCompactTokens(tok) {
      const n = Number(tok || 0);
      if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
      if (n >= 1_000) return (n / 1_000).toFixed(1) + "k";
      return String(n); }
    function applyThemeAndDensity(surface, density) {
      const s = THEME_META[surface] ? surface : "obsidian";
      const d = VALID_DENSITIES.includes(density) ? density : "D2";
      state.surface = s;
      state.density = d;
      document.documentElement.setAttribute("data-surface", s);
      document.documentElement.setAttribute("data-density", d);
      localStorage.setItem("nexus_surface", s);
      localStorage.setItem("nexus_density", d);
      const meta = THEME_META[s];
      const swatchEl = document.getElementById("triggerSwatch");
      const themeLabelEl = document.getElementById("triggerThemeLabel");
      const densityLabelEl = document.getElementById("triggerDensityLabel");
      const metaThemeEl = document.getElementById("metaThemeColor");
      if (swatchEl) {
        swatchEl.style.background = meta.bg;
        swatchEl.style.borderColor = meta.border; }
      if (themeLabelEl) themeLabelEl.textContent = meta.label;
      if (densityLabelEl) densityLabelEl.textContent = d;
      if (metaThemeEl) metaThemeEl.setAttribute("content", meta.themeColor);
      document.querySelectorAll(".theme-opt").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.theme === s); });
      document.querySelectorAll(".density-opt").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.density === d); });
    }
    function generateDemoBundle(period) {
      const daysSpan = period === "last_year" ? 364 : (period === "last_90d" ? 90 : (period === "last_month" ? 31 : 28));
      const now = new Date();
      const series = [];
      let totalSteps = 0, totalTools = 0, totalTokens = 0, activeDays = 0, peakSteps = 0, peakDate = "";
      const startMs = now.getTime() - (daysSpan - 1) * 86400000;
      const startDateObj = new Date(startMs);
      const startDow = (startDateObj.getUTCDay() + 6) % 7;
      const alignedStartMs = startMs - startDow * 86400000;
      const totalGridDays = daysSpan + startDow;
      for (let idx = 0; idx < totalGridDays; idx++) {
        const d = new Date(alignedStartMs + idx * 86400000);
        const dStr = d.toISOString().slice(0, 10);
        const dow = (d.getUTCDay() + 6) % 7;
        const seed = (d.getUTCFullYear() * 373 + (d.getUTCMonth() + 1) * 31 + d.getUTCDate() * 17) % 100;
        const isQuiet = (dow === 6 && seed < 40);
        const daysAgo = Math.round((now.getTime() - d.getTime()) / 86400000);
        const steps = isQuiet ? 0 : Math.max(85, Math.round((seed * 48) + (daysAgo < 14 ? 1200 : 280)));
        const tools = Math.round(steps * 0.50);
        const tokens = steps * 215;
        const sessions = steps > 0 ? Math.max(1, Math.round(steps / 650)) : 0;
        const level = steps === 0 ? 0 : (steps < 900 ? 1 : (steps < 2200 ? 2 : (steps < 3900 ? 3 : 4)));
        if (steps > 0) activeDays++;
        if (steps > peakSteps) { peakSteps = steps; peakDate = dStr; }
        totalSteps += steps; totalTools += tools; totalTokens += tokens;
        series.push({ date: dStr, weekday: dow, steps, tools, tokens, sessions, level, future: false, in_window: true }); }
      const subDailyLabels = [], subDailyVel = [];
      const recentDays = series.slice(-18);
      recentDays.forEach((dObj, dIdx) => {
        ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00"].forEach((hr, hIdx) => {
          const ptIdx = dIdx * 6 + hIdx;
          const wave = 0.55 + 0.45 * Math.sin(ptIdx * 0.35);
          subDailyLabels.push(`${dObj.date} ${hr}`);
          subDailyVel.push(Math.round(((dObj.steps || 300) / 6) * wave));
        });
      });
      const periodLabels = { "current_month": "This Month — MTD", "last_month": "Last Month", "last_90d": "Rolling 90 Days", "last_year": "Rolling 52 Weeks" };
      return {
        server: "agy-nexus-mcp", version: "2.4.0",
        period: { key: period, label: periodLabels[period] || "Rolling 90 Days", total_days: series.length, active_days: activeDays, resolution: "4h sub-daily" },
        kpis: {
          total_conversations: 54, total_subagents_spawned: 227, window_steps: totalSteps,
          window_tool_calls: totalTools, window_tokens: totalTokens,
          avg_daily_steps: Math.round(totalSteps / Math.max(1, activeDays)),
          peak_day: { date: peakDate, steps: peakSteps },
        },
        quota_and_pools: {
          active_tier_profile: "ultra-20x",
          pools: {
            google: { status: "HEALTHY", cooldown_remaining_seconds: 0 },
            claude: { status: "HEALTHY", cooldown_remaining_seconds: 0 },
            gpt_oss: { status: "HEALTHY", cooldown_remaining_seconds: 0 },
          },
          partner_weekly_pacing: { day_of_week_index: 2, daily_target_pct: 14.28, recommended_cumulative_ceiling_pct: 28.6 },
        },
        model_usage_vs_target: [
          { model_key: "argon_pro", label: "Gemini 4 Argon (Pro)", actual_pct: 70.3, target_pct: 65.0 },
          { model_key: "flash", label: "Gemini 3.8 Flash", actual_pct: 29.6, target_pct: 25.0 },
          { model_key: "claude_partner", label: "Claude Sonnet/Opus 5.5", actual_pct: 0.1, target_pct: 8.0 },
          { model_key: "gpt_oss", label: "GPT-OSS 120B", actual_pct: 0.0, target_pct: 2.0 },
        ],
        subagent_role_breakdown: {
          "flash-surgeon": { runs: 116, steps: 21704, tokens: 4520000 },
          "flash-auditor": { runs: 78, steps: 8084, tokens: 1680000 },
          "argon-sentinel": { runs: 3, steps: 3037, tokens: 890000 },
          "flash-scout": { runs: 20, steps: 2801, tokens: 610000 },
          "argon-surgeon": { runs: 2, steps: 2287, tokens: 540000 },
          "research": { runs: 5, steps: 862, tokens: 210000 },
          "argon-architect": { runs: 2, steps: 132, tokens: 42000 },
          "claude-specialist": { runs: 1, steps: 31, tokens: 12000 },
        },
        top_workspaces: [
          { workspace: "quantum-dsp-workbench", sessions: 14, steps: 65811, tokens: 29200000 },
          { workspace: "cloud-gitops-stack", sessions: 19, steps: 45032, tokens: 17200000 },
          { workspace: "neural-mesh-anms", sessions: 7, steps: 20107, tokens: 16500000 },
          { workspace: "chronos-tasks", sessions: 8, steps: 5991, tokens: 2200000 },
          { workspace: "mobile-sync-engine", sessions: 4, steps: 5092, tokens: 2000000 },
          { workspace: "telemetry-pipeline", sessions: 3, steps: 2878, tokens: 897000 },
          { workspace: "auth-gateway", sessions: 2, steps: 2691, tokens: 1000000 },
        ],
        velocity_series: { dates: subDailyLabels, values: subDailyVel, resolution: "4h sub-daily" },
        wire_telemetry: {
          total_recorded_calls: 77, avg_kb: 11.4, max_kb: 18.9, total_mcp_tokens: 186400, budget_compliance_pct: 100.0,
          by_product: { "Gemini Mobile": { calls: 48, tokens: 124000 }, "Gemini Web / Cloud MCP": { calls: 29, tokens: 62400 } },
        },
        routing_telemetry: { active_slots: 3, active_context_slots: 3, pinned_calls: 42, auto_resolved_calls: 2, ttl_remaining_min: 118.0 },
        backup_321: { ok: true, short_sha: "9f4a2c1", head_sha_short: "9f4a2c1", shas_match: true, status_label: "SYNCED ✓", bundle_size_kb: 842.0, age: "12m ago", timestamp_utc: "2026-11-07T18:35:00Z" },
        project_session_tree: {
          ok: true, projects_count: 4, sessions_count: 7, active_context_slots: 3,
          ascii_tree: "╔══════════════════════════════════════════════════════════════════════════╗\n║ AGY-NEXUS // PROJECT -> CHAT -> SESSION ID HIERARCHY (COPY-READY)        ║\n╚══════════════════════════════════════════════════════════════════════════╝",
          projects: [
            {
              project_id: "quantum-dsp-workbench", project_name: "quantum-dsp-workbench", workspace_path: "/home/dev/workspaces/quantum-dsp-workbench",
              total_sessions: 3, running_count: 1, pinned_count: 2, shared_repo: true,
              sessions: [
                { index: 1, conversation_id: "7a4e91c2-8b3d-4f10-9a6e-2c5d8f01e3b4", title: "Real-Time FFT Kernel & SIMD Pipeline Optimization", status: "RUNNING", is_pinned: true, mode: "MAIN WRITER", workspace_path: "/home/dev/workspaces/quantum-dsp-workbench", step_count: 486, last_updated: "2026-11-07T18:42:00Z", other_running_sessions: [] },
                { index: 2, conversation_id: "3f8b12d9-5c4a-4e21-b871-9d0e4a62c1f8", title: "Spectral Waterfall Shader & WebGPU Buffer Audit", status: "IDLE", is_pinned: true, mode: "SHARED (READ-ONLY)", workspace_path: "/home/dev/workspaces/quantum-dsp-workbench", step_count: 214, last_updated: "2026-11-07T18:19:00Z", other_running_sessions: ["7a4e91c2-8b3d-4f10-9a6e-2c5d8f01e3b4"] },
                { index: 3, conversation_id: "c91d40e6-2a7b-4d83-9c15-6e3f8b20a4d1", title: "Lock-Free Ring Buffer Benchmark Suite", status: "IDLE", is_pinned: false, mode: "WORKTREE", workspace_path: "/home/dev/workspaces/.worktrees/quantum-dsp-c91d40e6", step_count: 158, last_updated: "2026-11-07T16:05:00Z", other_running_sessions: [] },
              ],
            },
            {
              project_id: "cloud-gitops-stack", project_name: "cloud-gitops-stack", workspace_path: "/home/dev/workspaces/cloud-gitops-stack",
              total_sessions: 2, running_count: 1, pinned_count: 1, shared_repo: false,
              sessions: [
                { index: 4, conversation_id: "e52a90b4-6d1c-4a72-8f39-1b4c7d92e0a5", title: "Declarative Multi-Node Compose & 3-2-1 Bundle Sync", status: "RUNNING", is_pinned: true, mode: "MAIN WRITER", workspace_path: "/home/dev/workspaces/cloud-gitops-stack", step_count: 342, last_updated: "2026-11-07T18:40:00Z", other_running_sessions: [] },
                { index: 5, conversation_id: "9b3c61f0-4e8a-4c19-a254-7f1e3d80b6c2", title: "Zero-Downtime Ingress & TLS Certificate Rotation", status: "COMPLETED", is_pinned: false, mode: "MAIN TREE", workspace_path: "/home/dev/workspaces/cloud-gitops-stack", step_count: 275, last_updated: "2026-11-07T14:22:00Z", other_running_sessions: [] },
              ],
            },
            {
              project_id: "neural-mesh-anms", project_name: "neural-mesh-anms", workspace_path: "/home/dev/workspaces/neural-mesh-anms",
              total_sessions: 1, running_count: 0, pinned_count: 0, shared_repo: false,
              sessions: [
                { index: 6, conversation_id: "4d7e23a1-9f0b-4b68-8c42-5a9d1e73f2b0", title: "Anomaly Detection Graph & Telemetry Ingestion", status: "IDLE", is_pinned: false, mode: "MAIN TREE", workspace_path: "/home/dev/workspaces/neural-mesh-anms", step_count: 194, last_updated: "2026-11-06T22:15:00Z", other_running_sessions: [] },
              ],
            },
            {
              project_id: "chronos-tasks", project_name: "chronos-tasks", workspace_path: "/home/dev/workspaces/chronos-tasks",
              total_sessions: 1, running_count: 0, pinned_count: 0, shared_repo: false,
              sessions: [
                { index: 7, conversation_id: "1a8f54c7-3b2e-4d91-9e06-8c2b4f19d7e3", title: "Calendar Time-Block Counter-Event Scheduler", status: "COMPLETED", is_pinned: false, mode: "MAIN TREE", workspace_path: "/home/dev/workspaces/chronos-tasks", step_count: 312, last_updated: "2026-11-06T19:48:00Z", other_running_sessions: [] },
              ],
            },
          ],
        },
        heatmap_series: series, };
    }
    async function fetchStats(period) {
      if (state.demoMode) {
        localStorage.setItem("nexus_demo_mode", "1");
        state.bundle = generateDemoBundle(period);
        document.getElementById("authOverlay").classList.add("hidden");
        document.getElementById("dashboardMain").classList.remove("hidden");
        renderDashboard(state.bundle);
        return; }
      const statusEl = document.getElementById("authStatus");
      if (statusEl) statusEl.textContent = "Verifying passphrase...";
      try {
        const apiPath = window.location.pathname.replace(/\/web\/?$/, "") + "/web/api/stats?period=" + encodeURIComponent(period);
        const resp = await fetch(apiPath, {
          method: "GET",
          headers: { "X-Nexus-Passphrase": state.passphrase, "X-Client-Product": "Web Dashboard" }, });
        if (resp.status === 401 || resp.status === 403) {
          if (statusEl) statusEl.textContent = "Invalid passphrase. Try again or click Preview Sample Data.";
          localStorage.removeItem("nexus_passphrase");
          sessionStorage.removeItem("nexus_passphrase");
          document.getElementById("authOverlay").classList.remove("hidden");
          document.getElementById("dashboardMain").classList.add("hidden");
          return; }
        const data = await resp.json();
        if (data.ok === false) {
          if (statusEl) statusEl.textContent = data.error || "Unable to load dashboard data.";
          return; }
        localStorage.setItem("nexus_passphrase", state.passphrase);
        sessionStorage.setItem("nexus_passphrase", state.passphrase);
        localStorage.removeItem("nexus_demo_mode");
        if (statusEl) statusEl.textContent = "";
        state.bundle = data;
        document.getElementById("authOverlay").classList.add("hidden");
        document.getElementById("dashboardMain").classList.remove("hidden");
        renderDashboard(data);
      } catch (err) {
        if (statusEl) statusEl.textContent = "Connection or render error: " + (err && err.message ? err.message : String(err));
      }
    }
    function renderStackedAreaChart(svgId, legendId, resTagId, seriesBundle, heatDays, fallbackItems) {
      const svg = document.getElementById(svgId);
      const legendEl = document.getElementById(legendId);
      if (!svg || !legendEl) return;
      const resLabel = (seriesBundle && seriesBundle.resolution) ? seriesBundle.resolution.toUpperCase() : "4H SUB-DAILY";
      const resEl = document.getElementById(resTagId);
      if (resEl) resEl.textContent = resLabel + " STACKED";
      let keys = (seriesBundle && Array.isArray(seriesBundle.keys) && seriesBundle.keys.length) ? seriesBundle.keys.slice(0, 6) : [];
      let dates = (seriesBundle && Array.isArray(seriesBundle.dates) && seriesBundle.dates.length) ? seriesBundle.dates : [];
      let layers = (seriesBundle && seriesBundle.layers) ? seriesBundle.layers : {};
      if (!keys.length || !dates.length) {
        const recentDays = (heatDays || []).filter(d => !d.future).slice(-18);
        dates = [];
        recentDays.forEach((d) => {
          ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00"].forEach((hr) => {
            dates.push(`${d.date} ${hr}`); });
        });
        keys = (fallbackItems || []).slice(0, 6).map(x => x.name);
        const totalWeight = Math.max(1, (fallbackItems || []).slice(0, 6).reduce((a, b) => a + (b.steps || 1), 0));
        layers = {};
        keys.forEach((k, kIdx) => {
          const item = fallbackItems[kIdx] || { steps: 100 };
          const baseShare = (item.steps || 100) / totalWeight;
          layers[k] = dates.map((_, ptIdx) => {
            const dObj = recentDays[Math.floor(ptIdx / 6)] || { steps: 300 };
            const wave = 0.55 + 0.45 * Math.sin((ptIdx * 0.35) + kIdx * 1.2);
            return Math.round(((dObj.steps || 0) / 6) * baseShare * wave); });
        }); }
      if (!dates.length || !keys.length) {
        svg.innerHTML = `<text class="axis-label" x="20" y="95">No activity recorded for this time period.</text>`;
        legendEl.innerHTML = "";
        return; }
      const nPts = dates.length;
      const W = 620, H = 185, padL = 44, padR = 14, padT = 14, padB = 24;
      const plotW = W - padL - padR;
      const plotH = H - padT - padB;
      const cumMatrix = [];
      let maxStack = 50;
      for (let i = 0; i < nPts; i++) {
        let running = 0;
        const col = [0];
        keys.forEach((k) => {
          const val = Number((layers[k] && layers[k][i]) || 0);
          running += val;
          col.push(running); });
        if (running > maxStack) maxStack = running;
        cumMatrix.push(col); }
      const xAt = (i) => padL + (nPts === 1 ? plotW / 2 : (i / (nPts - 1)) * plotW);
      const yAt = (v) => padT + plotH - (Math.min(maxStack, v) / maxStack) * plotH;
      let shapesHtml = `
        <line class="grid-line" x1="${padL}" y1="${padT}" x2="${W - padR}" y2="${padT}" />
        <line class="grid-line" x1="${padL}" y1="${padT + plotH / 2}" x2="${W - padR}" y2="${padT + plotH / 2}" />
        <line class="grid-line" x1="${padL}" y1="${padT + plotH}" x2="${W - padR}" y2="${padT + plotH}" />
        <text class="axis-label" x="2" y="${padT + 4}">${maxStack >= 1000 ? (maxStack / 1000).toFixed(1) + "k" : maxStack}</text>
        <text class="axis-label" x="2" y="${padT + plotH / 2 + 3}">${Math.round(maxStack / 2) >= 1000 ? (maxStack / 2000).toFixed(1) + "k" : Math.round(maxStack / 2)}</text>
        <text class="axis-label" x="2" y="${padT + plotH}">0</text>
      `;
      keys.forEach((k, kIdx) => {
        const color = SERIES_COLORS[kIdx % SERIES_COLORS.length];
        const topPts = [];
        const botPts = [];
        for (let i = 0; i < nPts; i++) {
          const x = xAt(i).toFixed(1);
          const yTop = yAt(cumMatrix[i][kIdx + 1]).toFixed(1);
          const yBot = yAt(cumMatrix[i][kIdx]).toFixed(1);
          topPts.push(`${x},${yTop}`);
          botPts.unshift(`${x},${yBot}`); }
        const polyPts = topPts.concat(botPts).join(" ");
        shapesHtml += `<polygon points="${polyPts}" fill="${color}" fill-opacity="0.30" />`;
        shapesHtml += `<polyline fill="none" stroke="${color}" stroke-width="1.6" points="${topPts.join(" ")}" />`; });
      shapesHtml += `
        <text class="axis-label" x="${padL}" y="${H - 4}">${dates[0]}</text>
        <text class="axis-label" x="${W - padR - 92}" y="${H - 4}">${dates[nPts - 1]}</text>
      `;
      svg.innerHTML = shapesHtml;
      legendEl.innerHTML = keys.map((k, kIdx) => {
        const color = SERIES_COLORS[kIdx % SERIES_COLORS.length];
        const tot = (layers[k] || []).reduce((a, b) => a + Number(b || 0), 0);
        return `<span class="legend-item"><span class="swatch-dot" style="background:${color}"></span><span>${k} (${tot.toLocaleString()})</span></span>`;
      }).join(""); }
    function computeIsoWeekday(dateStr, fallbackWeekday) {
      if (typeof fallbackWeekday === "number" && fallbackWeekday >= 0 && fallbackWeekday <= 6) {
        return fallbackWeekday;
      }
      const parts = String(dateStr || "").split("-").map(Number);
      if (parts.length === 3 && !isNaN(parts[0])) {
        const dt = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2]));
        return (dt.getUTCDay() + 6) % 7;
      }
      return 0;
    }
