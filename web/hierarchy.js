// AGY-NEXUS Overwatch — Unified Plot 3 Legend & Collapsed Project -> Chat -> Session Hierarchy (v2.7.0)

let hierarchyPinnedOnly = false;
let hierarchyShowIdle = false;
let hierarchyExpandAll = false;
const expandedProjectIds = new Set();
let lastHierarchyBundle = null;

function copyTextWithFeedback(el, textToCopy, origText, durationMs) {
  const txt = String(textToCopy || "");
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(txt).catch(() => {});
  } else {
    const ta = document.createElement("textarea");
    ta.value = txt; ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); } catch (_) {}
    document.body.removeChild(ta);
  }
  if (el) {
    if (el._copyTimer) clearTimeout(el._copyTimer);
    else el._origText = origText !== undefined ? origText : el.textContent;
    el.textContent = "Copied ✓";
    el.classList.add("copied");
    el._copyTimer = setTimeout(() => {
      el.textContent = el._origText;
      el.classList.remove("copied");
      el._copyTimer = 0;
    }, durationMs || 900);
  }
}

function formatShortWorkspace(wsPath) {
  const raw = String(wsPath || "").trim().replace(/\/+$/, "");
  if (!raw) return "-";
  if (raw.includes("/worktrees/") || raw.includes("/.worktrees/")) {
    return "wt:" + (raw.split(/\/(?:\.)?worktrees\//)[1] || raw);
  }
  return raw
    .replace(/^\/home\/[^/]+\/gitlab\//, "")
    .replace(/^\/home\/[^/]+\/workspaces\//, "")
    .replace(/^~\/gitlab\//, "")
    .replace(/^~\/workspaces\//, "");
}

function formatShortMode(modeStr) {
  const m = String(modeStr || "MAIN TREE").toUpperCase();
  if (m.includes("WRITER")) return { label: "WRITER", cls: "writer" };
  if (m.includes("SHARED")) return { label: "SHARED", cls: "warn" };
  if (m.includes("WORKTREE")) return { label: "WORKTREE", cls: "" };
  if (m.includes("PINNED")) return { label: "PINNED", cls: "" };
  return { label: "MAIN", cls: "" };
}

function formatShortUpdated(s) {
  if (s.relative_age) return String(s.relative_age);
  const raw = String(s.last_updated || "");
  return raw.length >= 16 ? raw.slice(5, 16).replace("T", " ") : (raw || "-");
}

function buildProjectSessionPlotBands(bundle, surface, metric, soloProjectId) {
  const ph = bundle && bundle.project_hierarchy;
  const bands = [];
  if (ph && Array.isArray(ph.top_projects)) {
    const validSolo = soloProjectId && (ph.top_projects.some((p) => String(p.project_id) === soloProjectId) || (ph.other_projects && soloProjectId === "__other_projects__")) ? soloProjectId : "";
    if (soloProjectId && !validSolo && typeof state !== "undefined") state.soloProject = "";
    ph.top_projects.forEach((proj) => {
      const pid = String(proj.project_id || "");
      const slotIdx = Number(proj.color_slot ?? 0);
      const isHidden = Boolean(validSolo && validSolo !== pid);
      (proj.sessions || []).forEach((s) => {
        const vals = metric === "tokens" ? s.tokens_series : s.steps_series;
        if (!Array.isArray(vals)) return;
        const shade = deriveSessionShade(slotIdx, s.shade_idx ?? 0, s.shade_count ?? 1, surface);
        const sLbl = s.title || s.conversation_id.slice(0, 8);
        bands.push({
          id: `${pid}::${s.conversation_id}`, projectId: pid, label: sLbl,
          tooltipLabel: `${proj.project_name} › ${sLbl}`,
          fill: shade.fill, cap: shade.cap, values: vals, hidden: isHidden,
        });
      });
      if (proj.overflow_sessions_series) {
        const ovf = proj.overflow_sessions_series;
        const shade = deriveSessionShade(slotIdx, ovf.shade_idx ?? 11, ovf.shade_count ?? 12, surface);
        bands.push({
          id: `${pid}::__overflow__`, projectId: pid, label: "Additional Sessions",
          tooltipLabel: `${proj.project_name} › Additional Sessions`,
          fill: shade.fill, cap: shade.cap,
          values: metric === "tokens" ? ovf.tokens_series : ovf.steps_series, hidden: isHidden,
        });
      }
    });
    if (ph.other_projects) {
      const op = ph.other_projects;
      const slate = getProjectBaseColor(10, surface);
      bands.push({
        id: "__other_projects__", projectId: "__other_projects__", label: "Other Projects",
        tooltipLabel: `Other Projects (${op.projects_count || 1} projects)`,
        fill: slate.fill, cap: slate.cap,
        values: metric === "tokens" ? op.tokens_series : op.steps_series,
        hidden: Boolean(validSolo && validSolo !== "__other_projects__"),
      });
    }
    return { dates: ph.dates || [], stepHours: ph.step_hours || 4, bands };
  }

  const ws = (bundle && bundle.workspace_series) || {};
  (Array.isArray(ws.keys) ? ws.keys : []).forEach((k, idx) => {
    const col = getProjectBaseColor(k === "other-projects" ? 10 : idx, surface);
    bands.push({
      id: k, projectId: k, label: k, tooltipLabel: k,
      fill: col.fill, cap: col.cap, values: (ws.layers && ws.layers[k]) || [], hidden: false,
    });
  });
  return { dates: ws.dates || [], stepHours: ws.step_hours || 4, bands };
}

function renderHierarchyPanel(bundle) {
  lastHierarchyBundle = bundle;
  const container = document.getElementById("hierarchyProjectList");
  if (!container) return;

  const tree = (bundle && bundle.project_session_tree) || {};
  const ph = (bundle && bundle.project_hierarchy) || null;
  const routing = (bundle && bundle.routing_telemetry) || tree.routing_telemetry || {};
  const b321 = (bundle && bundle.backup_321) || tree.backup_321 || {};
  const metric = (typeof state !== "undefined" && state.metric) || "steps";
  const surface = (typeof state !== "undefined" && state.surface) || "obsidian";
  const soloPid = (typeof state !== "undefined" && state.soloProject) || "";

  const backupBadge = document.getElementById("hierarchyBackupBadge");
  if (backupBadge) {
    if (b321 && (b321.ok || b321.short_sha)) {
      const sha = String(b321.short_sha || b321.head_sha_short || "sync");
      backupBadge.textContent = `3-2-1 SYNC: ${sha} ${b321.shas_match ? "✓" : "⚠"}`;
      backupBadge.className = "card-tag mono " + (b321.shas_match ? "tag-ok" : "tag-warn");
      backupBadge.title = `GitHub + GitLab + Offline Bundle (${b321.timestamp_utc || b321.age || ""})`;
    } else {
      backupBadge.textContent = "3-2-1 SYNC: STANDBY";
      backupBadge.className = "card-tag mono";
    }
  }

  const slotsBadge = document.getElementById("hierarchySlotsBadge");
  if (slotsBadge) {
    const slots = Number(routing.active_slots ?? routing.active_context_slots ?? 0);
    slotsBadge.textContent = `SLOTS: ${slots} · PINNED: ${Number(routing.pinned_calls || 0)} · AUTO: ${Number(routing.auto_resolved_calls || 0)}`;
  }

  const btnActive = document.getElementById("hierarchyFilterActiveBtn");
  const btnAll = document.getElementById("hierarchyFilterAllBtn");
  const btnIdle = document.getElementById("hierarchyShowIdleBtn");
  const expandBtn = document.getElementById("hierarchyExpandAllBtn");
  const clearSoloBtn = document.getElementById("clearProjectSoloBtn");
  if (btnActive && btnAll) {
    btnActive.classList.toggle("active", hierarchyPinnedOnly);
    btnAll.classList.toggle("active", !hierarchyPinnedOnly);
  }
  const idleCount = ph ? Number(ph.idle_projects_count || 0) : 0;
  if (btnIdle) {
    btnIdle.classList.toggle("active", hierarchyShowIdle);
    btnIdle.classList.toggle("hidden", idleCount === 0);
    btnIdle.textContent = `+ Idle (${idleCount})`;
  }
  if (expandBtn) expandBtn.textContent = hierarchyExpandAll ? "Collapse All" : "Expand All";
  if (clearSoloBtn) clearSoloBtn.classList.toggle("hidden", !soloPid);

  const sourceList = [];
  if (ph && Array.isArray(ph.top_projects)) {
    ph.top_projects.forEach((p) => sourceList.push({ ...p, rowKind: "top" }));
    if (ph.other_projects) sourceList.push({ ...ph.other_projects, rowKind: "other" });
    if (hierarchyShowIdle && Array.isArray(ph.idle_projects)) {
      ph.idle_projects.forEach((ip) => sourceList.push({ ...ip, rowKind: "idle", color_slot: -1 }));
    }
  }

  const visibleProjects = [];
  sourceList.forEach((proj) => {
    const sessList = Array.isArray(proj.sessions) ? proj.sessions : [];
    const visSess = hierarchyPinnedOnly
      ? sessList.filter((s) => s.is_pinned || s.is_running || s.status === "RUNNING" || s.status === "STALLED_WAITING_APPROVAL")
      : sessList;
    if (visSess.length > 0 || (!hierarchyPinnedOnly && Number(proj.window_steps || 0) > 0)) {
      visibleProjects.push({ ...proj, visibleSessions: visSess });
    }
  });

  if (!visibleProjects.length) {
    container.innerHTML = `<div class="hier-empty mono">No projects match the selected filter in this time window.</div>`;
    return;
  }

  container.innerHTML = visibleProjects.map((proj) => {
    const pid = String(proj.project_id || ""), pEsc = escapeHtmlSafe(pid);
    const pName = escapeHtmlSafe(proj.project_name || "Project");
    const isRollup = proj.rowKind === "other" || Boolean(proj.is_rollup);
    const isIdleRow = proj.rowKind === "idle";
    const slotIdx = isRollup ? 10 : (isIdleRow ? -1 : Number(proj.color_slot ?? 0));
    const swatchCss = isIdleRow
      ? "background:transparent;border:1.5px dashed var(--text-dim);"
      : buildProjectSwatchStyle(slotIdx, proj.active_sessions_count || proj.visibleSessions.length, surface);
    const rankTag = isRollup ? "[OTHER]" : (isIdleRow ? "[IDLE]" : `[${String(slotIdx + 1).padStart(2, "0")}]`);
    const idMeta = isRollup
      ? `<span class="hier-proj-id mono">${Number(proj.projects_count || 1)} projects rolled up</span>`
      : `<span class="hier-copy-inline hier-proj-id mono" data-copy="${pEsc}" title="Click to copy project_id">${pEsc}</span>`;
    const sharedTag = proj.shared_repo ? `<span class="hier-micro-tag mono" title="Multiple sessions share repository">SHARED</span>` : "";
    const runCnt = Number(proj.running_count || 0) + Number(proj.pinned_count || 0);
    const liveHtml = runCnt > 0 ? `<span class="hier-active-count">${runCnt} live</span><span>·</span>` : "";
    const actChats = Number(proj.active_sessions_count || proj.visibleSessions.filter((s) => Number(s.window_steps || 0) > 0).length);
    const chatSummary = (actChats > 0 && actChats < proj.visibleSessions.length)
      ? `${actChats}/${proj.visibleSessions.length} chats`
      : `${proj.visibleSessions.length} chats`;
    const winVal = metric === "tokens"
      ? `~${formatCompactTokens(proj.window_tokens || 0)} tok`
      : `${Number(proj.window_steps || 0).toLocaleString()} steps`;
    const sharePct = Number(proj.share_pct || 0);
    const isSolo = soloPid === pid, isDimmed = Boolean(soloPid && !isSolo);
    const isOpen = hierarchyExpandAll || expandedProjectIds.has(pid);

    const rowsHtml = proj.visibleSessions.map((s) => {
      const cid = escapeHtmlSafe(s.conversation_id || "");
      const title = escapeHtmlSafe(s.title || "Untitled Session");
      const rawWs = String(s.workspace_path || "(unscoped)");
      const wsFull = escapeHtmlSafe(rawWs);
      const wsShort = escapeHtmlSafe(s.workspace_short || formatShortWorkspace(rawWs));
      const status = String(s.status || "IDLE").toUpperCase();
      const isRun = Boolean(s.is_running || status === "RUNNING" || status === "STALLED_WAITING_APPROVAL");
      const dotCls = isRun ? "running" : (s.is_pinned ? "pinned" : "idle");
      const dotChar = isRun ? "●" : (s.is_pinned ? "◉" : "○");
      const modeObj = formatShortMode(s.mode);
      const updated = escapeHtmlSafe(formatShortUpdated(s));
      const sWinSteps = Number(s.window_steps || 0);
      const sShade = (!isIdleRow && sWinSteps > 0) ? deriveSessionShade(slotIdx, s.shade_idx ?? 0, s.shade_count ?? 1, surface) : null;
      const shadeStyle = sShade ? `background:${sShade.fill};border-color:${sShade.cap};` : `background:transparent;border:1px dashed var(--text-dim);opacity:0.5;`;
      const projPrefix = (isRollup && s.project_name) ? `<span class="hier-micro-tag mono">${escapeHtmlSafe(s.project_name)}</span>` : "";
      const cellMetric = metric === "tokens" ? (sWinSteps > 0 ? `~${formatCompactTokens(s.window_tokens || 0)}` : "0") : sWinSteps.toLocaleString();

      return `<tr class="hier-session-row ${sWinSteps === 0 ? "sess-zero-win" : ""}">
        <td><div class="sess-cell"><span class="sess-shade-swatch" style="${shadeStyle}" title="Plot 3 session bar color (${sWinSteps.toLocaleString()} window steps)"></span><span class="sess-dot ${dotCls}" title="${escapeHtmlSafe(status)}">${dotChar}</span><span class="hier-idx mono">#${Number(s.index || 0)}</span>${projPrefix}<span class="hier-copy-inline hier-title-txt" data-copy="${title}" title="Click to copy chat title">${title}</span></div></td>
        <td class="mono"><span class="hier-copy-inline hier-uuid" data-copy="${cid}" title="Click to copy full session_id">${cid}</span></td>
        <td class="mono"><span class="hier-copy-inline hier-ws" data-copy="${wsFull}" title="Click to copy full path: ${wsFull}">${wsShort}</span></td>
        <td class="mono"><span class="hier-mode-lbl ${modeObj.cls}">${modeObj.label}</span></td>
        <td class="mono num-col" title="Total lifetime steps: ${Number(s.step_count || 0).toLocaleString()}">${cellMetric}</td>
        <td class="mono num-col hier-updated">${updated}</td>
        <td class="hier-act-cell"><button type="button" class="hier-upload-btn btn" data-cid="${cid}" data-title="${title}" title="Upload files to session scratch directory">Upload</button></td>
      </tr>`;
    }).join("");

    const soloBtnHtml = !isIdleRow
      ? `<button type="button" class="btn-solo mono ${isSolo ? "active" : ""}" data-solo-pid="${pEsc}" title="Solo this project on Plot 3">${isSolo ? "Solo ✓" : "Solo"}</button>`
      : "";

    return `<details class="hier-proj-card ${isDimmed ? "is-dimmed" : ""} ${isSolo ? "is-solo" : ""}" data-pid="${pEsc}" ${isOpen ? "open" : ""}>
      <summary class="hier-proj-hdr">
        <div class="hier-proj-left"><span class="hier-caret mono"></span><span class="proj-swatch-pill" style="${swatchCss}" title="Project color family (${actChats} active session shades)"></span><span class="hier-proj-idx mono">${rankTag}</span><strong class="hier-proj-name">${pName}</strong>${idMeta}${sharedTag}</div>
        <div class="hier-proj-right mono">${liveHtml}<span>${chatSummary}</span><span>·</span><strong style="color:var(--text-main)">${winVal}</strong><span class="proj-share-pill">${sharePct.toFixed(1)}%</span>${soloBtnHtml}</div>
      </summary>
      <div class="hier-table-wrap" tabindex="0" role="region" aria-label="${pName} sessions">
        <table class="table-clean hier-table">
          <thead><tr><th class="hier-col-sess">Session (Plot Shade + Title)</th><th class="mono hier-col-uuid">Session ID</th><th class="mono hier-col-ws">Workspace</th><th class="mono hier-col-mode">Mode</th><th class="mono num-col hier-col-steps">${metric === "tokens" ? "Win Tok" : "Win Steps"}</th><th class="mono num-col hier-col-upd">Updated</th><th class="mono hier-col-act">Upload</th></tr></thead>
          <tbody>${rowsHtml}</tbody>
        </table>
      </div>
    </details>`;
  }).join("");

  container.querySelectorAll("details.hier-proj-card").forEach((det) => {
    det.addEventListener("toggle", () => {
      const pid = det.getAttribute("data-pid") || "";
      if (pid) { if (det.open) expandedProjectIds.add(pid); else expandedProjectIds.delete(pid); }
    });
  });

  container.querySelectorAll(".btn-solo").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const pid = btn.getAttribute("data-solo-pid") || "";
      if (typeof state !== "undefined") {
        state.soloProject = state.soloProject === pid ? "" : pid;
        if (state.bundle && typeof renderAllTimePlots === "function") renderAllTimePlots(state.bundle);
        renderHierarchyPanel(lastHierarchyBundle);
      }
    });
  });

  container.querySelectorAll(".hier-copy-inline").forEach((el) => {
    el.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      copyTextWithFeedback(el, el.getAttribute("data-copy") || "", undefined, 900);
    });
  });

  container.querySelectorAll(".hier-upload-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (typeof window.openUploadModal === "function") {
        window.openUploadModal(btn.getAttribute("data-cid") || "", btn.getAttribute("data-title") || "");
      }
    });
  });
}

(function initHierarchyControls() {
  window.addEventListener("DOMContentLoaded", () => {
    const bind = (id, fn) => { const el = document.getElementById(id); if (el) el.addEventListener("click", fn); };
    bind("hierarchyFilterActiveBtn", () => { hierarchyPinnedOnly = true; if (lastHierarchyBundle) renderHierarchyPanel(lastHierarchyBundle); });
    bind("hierarchyFilterAllBtn", () => { hierarchyPinnedOnly = false; if (lastHierarchyBundle) renderHierarchyPanel(lastHierarchyBundle); });
    bind("hierarchyShowIdleBtn", () => { hierarchyShowIdle = !hierarchyShowIdle; if (lastHierarchyBundle) renderHierarchyPanel(lastHierarchyBundle); });
    bind("hierarchyExpandAllBtn", () => {
      hierarchyExpandAll = !hierarchyExpandAll;
      if (!hierarchyExpandAll) expandedProjectIds.clear();
      if (lastHierarchyBundle) renderHierarchyPanel(lastHierarchyBundle);
    });
    bind("clearProjectSoloBtn", () => {
      if (typeof state !== "undefined") {
        state.soloProject = "";
        if (state.bundle && typeof renderAllTimePlots === "function") renderAllTimePlots(state.bundle);
        if (lastHierarchyBundle) renderHierarchyPanel(lastHierarchyBundle);
      }
    });
    bind("copyAsciiTreeBtn", () => {
      const btn = document.getElementById("copyAsciiTreeBtn");
      const tree = (lastHierarchyBundle && lastHierarchyBundle.project_session_tree) || {};
      copyTextWithFeedback(btn, tree.ascii_tree || "No ASCII session tree available.", "Copy ASCII Tree", 1200);
    });
  });
})();
