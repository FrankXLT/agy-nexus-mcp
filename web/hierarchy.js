// Project, Chat & Session Hierarchy Renderer for /web Overwatch Dashboard (v2.4.0)
let hierarchyShowAll = localStorage.getItem("nexus_hier_all") !== "0";
let lastHierarchyBundle = null;

function escapeHtmlSafe(val) {
  return String(val ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function copyTextWithFeedback(btnEl, textToCopy, origLabel) {
  if (!navigator.clipboard) return;
  navigator.clipboard.writeText(String(textToCopy || "")).catch(() => {});
  if (btnEl) {
    const prev = origLabel || btnEl.innerHTML;
    btnEl.textContent = "Copied!";
    btnEl.classList.add("copied");
    setTimeout(() => {
      btnEl.innerHTML = prev;
      btnEl.classList.remove("copied");
    }, 1300);
  }
}

function getWorkspaceSessionBadgesHtml(workspaceName, treeBundle) {
  if (!treeBundle || !Array.isArray(treeBundle.projects)) return "";
  const wsNorm = String(workspaceName || "").trim().toLowerCase();
  let running = 0;
  let pinned = 0;
  let shared = false;
  treeBundle.projects.forEach((p) => {
    const pName = String(p.project_name || "").trim().toLowerCase();
    const pId = String(p.project_id || "").trim().toLowerCase();
    if (pName === wsNorm || pId === wsNorm || pId.endsWith("/" + wsNorm)) {
      running += Number(p.running_count || 0);
      pinned += Number(p.pinned_count || 0);
      if (p.shared_repo) shared = true;
    }
  });
  const badges = [];
  if (running > 0) {
    badges.push(`<span class="ws-live-pill running" title="${running} running session(s)">● ${running} run</span>`);
  }
  if (pinned > 0) {
    badges.push(`<span class="ws-live-pill pinned" title="${pinned} pinned session slot(s)">◉ ${pinned} pin</span>`);
  }
  if (shared) {
    badges.push(`<span class="ws-live-pill shared" title="Multiple active/pinned sessions share this repository">SHARED</span>`);
  }
  return badges.length ? `<span class="ws-badge-group mono">${badges.join("")}</span>` : "";
}

function renderHierarchyPanel(bundle) {
  lastHierarchyBundle = bundle;
  const container = document.getElementById("hierarchyProjectList");
  if (!container) return;

  const tree = (bundle && bundle.project_session_tree) || {};
  const routing = (bundle && bundle.routing_telemetry) || tree.routing_telemetry || {};
  const b321 = (bundle && bundle.backup_321) || tree.backup_321 || {};
  const projects = Array.isArray(tree.projects) ? tree.projects : [];

  const backupBadge = document.getElementById("hierarchyBackupBadge");
  if (backupBadge) {
    if (b321 && (b321.ok || b321.short_sha)) {
      const sha = escapeHtmlSafe(b321.short_sha || b321.head_sha_short || "sync");
      const check = b321.shas_match ? "✓" : "⚠";
      backupBadge.textContent = `3-2-1 SYNC: ${sha} ${check}`;
      backupBadge.className = "card-tag mono " + (b321.shas_match ? "tag-ok" : "tag-warn");
      backupBadge.title = `GitHub + GitLab + Offline Bundle (${b321.timestamp_utc || b321.age || ""})`;
    } else {
      backupBadge.textContent = "3-2-1 SYNC: STANDBY";
      backupBadge.className = "card-tag mono";
    }
  }

  const slotsBadge = document.getElementById("hierarchySlotsBadge");
  if (slotsBadge) {
    const slots = Number(routing.active_slots ?? routing.active_context_slots ?? tree.active_context_slots ?? 0);
    const pinCalls = Number(routing.pinned_calls || 0);
    const autoCalls = Number(routing.auto_resolved_calls || 0);
    slotsBadge.textContent = `SLOTS: ${slots} · PINNED: ${pinCalls} · AUTO-RESOLVED: ${autoCalls}`;
  }

  const btnActive = document.getElementById("hierarchyFilterActiveBtn");
  const btnAll = document.getElementById("hierarchyFilterAllBtn");
  if (btnActive && btnAll) {
    btnActive.classList.toggle("active", !hierarchyShowAll);
    btnAll.classList.toggle("active", hierarchyShowAll);
  }

  const filteredProjects = [];
  projects.forEach((proj) => {
    const sessList = Array.isArray(proj.sessions) ? proj.sessions : [];
    const visibleSessions = hierarchyShowAll
      ? sessList
      : sessList.filter((s) => s.is_pinned || s.status === "RUNNING" || s.status === "STALLED_WAITING_APPROVAL");
    if (visibleSessions.length > 0) {
      filteredProjects.push({ ...proj, visibleSessions, totalSessionsCount: sessList.length });
    }
  });

  if (filteredProjects.length === 0) {
    const totSess = tree.sessions_count || tree.total_sessions || 0;
    container.innerHTML = `<div class="hier-empty mono">No sessions match the current filter. Click "All Sessions" to inspect all ${totSess} indexed conversations.</div>`;
    return;
  }

  container.innerHTML = filteredProjects.map((proj, pIdx) => {
    const pName = escapeHtmlSafe(proj.project_name || "Project");
    const pId = escapeHtmlSafe(proj.project_id || "");
    const wsPath = escapeHtmlSafe(proj.workspace_path || "");
    const sharedBadge = proj.shared_repo
      ? `<span class="hier-badge warn mono" title="Multiple active or pinned sessions target this repository">SHARED REPO</span>`
      : "";
    const runBadge = proj.running_count > 0
      ? `<span class="hier-badge ok mono">● ${proj.running_count} RUNNING</span>`
      : "";
    const pinBadge = proj.pinned_count > 0
      ? `<span class="hier-badge focal mono">◉ ${proj.pinned_count} PINNED</span>`
      : "";

    const rowsHtml = proj.visibleSessions.map((s) => {
      const cid = escapeHtmlSafe(s.conversation_id || "");
      const title = escapeHtmlSafe(s.title || "Untitled Session");
      const wsFull = escapeHtmlSafe(s.workspace_path || proj.workspace_path || "(unscoped)");
      const status = String(s.status || "IDLE").toUpperCase();
      const statusCls = status === "RUNNING" ? "ok" : (status === "STALLED_WAITING_APPROVAL" ? "warn" : "muted");
      const statusDot = status === "RUNNING" ? "●" : (status === "STALLED_WAITING_APPROVAL" ? "◐" : (status === "COMPLETED" ? "✓" : "○"));
      const modeStr = escapeHtmlSafe(s.mode || "MAIN TREE");
      const pinnedPill = s.is_pinned ? `<span class="hier-badge focal mono">◉ PINNED</span>` : "";
      const others = Array.isArray(s.other_running_sessions) ? s.other_running_sessions : [];
      const conflictPill = others.length > 0
        ? `<span class="hier-badge warn mono" title="Other running session(s) on same repo: ${escapeHtmlSafe(others.join(", "))}">⚠ ${others.length} CONCURRENT</span>`
        : "";
      const updated = escapeHtmlSafe(String(s.last_updated || "").slice(0, 16).replace("T", " "));

      return `
        <div class="hier-session-row ${s.is_pinned ? "is-pinned" : ""}">
          <div class="hier-sess-top">
            <div class="hier-sess-title-group">
              <span class="hier-idx mono">#${Number(s.index || 0)}</span>
              <span class="hier-status-pill ${statusCls} mono">${statusDot} ${escapeHtmlSafe(status)}</span>
              ${pinnedPill}
              <span class="hier-badge mode mono">${modeStr}</span>
              ${conflictPill}
              <strong class="hier-chat-title">${title}</strong>
              <button type="button" class="copy-pill mono" data-copy="${title}" title="Copy chat title">📋 Title</button>
            </div>
            <div class="hier-sess-meta mono">
              <span>${Number(s.step_count || 0).toLocaleString()} steps</span>
              <span>·</span>
              <span>${updated || "-"}</span>
            </div>
          </div>
          <div class="hier-sess-ids mono">
            <span class="hier-kv">
              <span class="hier-k">session_id:</span>
              <code class="hier-v">${cid}</code>
              <button type="button" class="copy-pill mono" data-copy="${cid}" title="Copy full session_id">📋 ID</button>
            </span>
            <span class="hier-kv">
              <span class="hier-k">workspace:</span>
              <code class="hier-v">${wsFull}</code>
              <button type="button" class="copy-pill mono" data-copy="${wsFull}" title="Copy workspace path">📋 Path</button>
            </span>
          </div>
        </div>
      `;
    }).join("");

    return `
      <details class="hier-proj-card" open>
        <summary class="hier-proj-hdr">
          <div class="hier-proj-left">
            <span class="hier-proj-idx mono">[PROJECT ${pIdx + 1}]</span>
            <strong class="hier-proj-name">${pName}</strong>
            <code class="hier-proj-id mono">(${pId})</code>
            <button type="button" class="copy-pill mono" data-copy="${pId}" title="Copy project_id">📋 Project</button>
            ${sharedBadge}
            ${runBadge}
            ${pinBadge}
          </div>
          <div class="hier-proj-right mono">
            <span>${proj.visibleSessions.length} / ${proj.totalSessionsCount || proj.total_sessions || proj.visibleSessions.length} chats</span>
          </div>
        </summary>
        <div class="hier-proj-body">${rowsHtml}</div>
      </details>
    `;
  }).join("");

  container.querySelectorAll(".copy-pill").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      copyTextWithFeedback(btn, btn.getAttribute("data-copy") || "", btn.innerHTML);
    });
  });
}

(function initHierarchyControls() {
  const btnActive = document.getElementById("hierarchyFilterActiveBtn");
  const btnAll = document.getElementById("hierarchyFilterAllBtn");
  const copyTreeBtn = document.getElementById("copyAsciiTreeBtn");

  if (btnActive) {
    btnActive.addEventListener("click", () => {
      hierarchyShowAll = false;
      localStorage.setItem("nexus_hier_all", "0");
      if (lastHierarchyBundle) renderHierarchyPanel(lastHierarchyBundle);
    });
  }
  if (btnAll) {
    btnAll.addEventListener("click", () => {
      hierarchyShowAll = true;
      localStorage.setItem("nexus_hier_all", "1");
      if (lastHierarchyBundle) renderHierarchyPanel(lastHierarchyBundle);
    });
  }
  if (copyTreeBtn) {
    copyTreeBtn.addEventListener("click", () => {
      const tree = (lastHierarchyBundle && lastHierarchyBundle.project_session_tree) || {};
      const ascii = tree.ascii_tree || "No ASCII session tree available.";
      copyTextWithFeedback(copyTreeBtn, ascii, "Copy ASCII Tree");
    });
  }
})();
