// Project, Chat & Session Hierarchy — Quiet UI Tabular Renderer for /web Overwatch Dashboard (v2.6.0)
let hierarchyShowAll = localStorage.getItem("nexus_hier_all") !== "0";
let hierarchyExpandAll = false;
let lastHierarchyBundle = null;

function escapeHtmlSafe(val) {
  return String(val ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function copyTextWithFeedback(el, textToCopy, origHtml, durationMs) {
  if (!navigator.clipboard) return;
  navigator.clipboard.writeText(String(textToCopy || "")).catch(() => {});
  if (el) {
    const prev = origHtml !== undefined ? origHtml : el.innerHTML;
    el.textContent = "Copied ✓";
    el.classList.add("copied");
    setTimeout(() => {
      el.innerHTML = prev;
      el.classList.remove("copied");
    }, durationMs || 900);
  }
}

function formatShortWorkspace(wsPath) {
  const raw = String(wsPath || "").trim().replace(/\/+$/, "");
  if (!raw) return "-";
  if (raw.includes("/worktrees/") || raw.includes("/.worktrees/")) {
    const tail = raw.split(/\/(?:\.)?worktrees\//)[1] || raw;
    return "wt:" + tail;
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
  if (raw.length >= 16) return raw.slice(5, 16).replace("T", " ");
  return raw || "-";
}

function getWorkspaceSessionBadgesHtml(workspaceName, treeBundle) {
  if (!treeBundle || !Array.isArray(treeBundle.projects)) return "";
  const wsNorm = String(workspaceName || "").trim().toLowerCase();
  let running = 0;
  let pinned = 0;
  treeBundle.projects.forEach((p) => {
    const pName = String(p.project_name || "").trim().toLowerCase();
    const pId = String(p.project_id || "").trim().toLowerCase();
    if (pName === wsNorm || pId === wsNorm || pId.endsWith("/" + wsNorm)) {
      running += Number(p.running_count || 0);
      pinned += Number(p.pinned_count || 0);
    }
  });
  const parts = [];
  if (running > 0) parts.push(`${running} active`);
  if (pinned > 0 && pinned !== running) parts.push(`${pinned} pin`);
  return parts.length ? `<span class="ws-quiet-meta mono">· ${parts.join(" · ")}</span>` : "";
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
  const expandBtn = document.getElementById("hierarchyExpandAllBtn");
  if (expandBtn) {
    expandBtn.textContent = hierarchyExpandAll ? "Collapse Idle" : "Expand All";
  }

  const filteredProjects = [];
  projects.forEach((proj) => {
    const sessList = Array.isArray(proj.sessions) ? proj.sessions : [];
    const visibleSessions = hierarchyShowAll
      ? sessList
      : sessList.filter((s) => s.is_pinned || s.status === "RUNNING" || s.status === "STALLED_WAITING_APPROVAL");
    if (visibleSessions.length > 0) {
      const projSteps = sessList.reduce((acc, s) => acc + Number(s.step_count || 0), 0);
      filteredProjects.push({ ...proj, visibleSessions, totalSessionsCount: sessList.length, projSteps });
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
    const sharedTag = proj.shared_repo
      ? `<span class="hier-micro-tag mono" title="Multiple sessions share this repository">SHARED</span>`
      : "";
    const activeCnt = Number(proj.running_count || 0) + Number(proj.pinned_count || 0);
    const activeHtml = activeCnt > 0 ? `<span class="hier-active-count">${activeCnt} active</span><span>·</span>` : "";
    const isOpen = hierarchyExpandAll || !hierarchyShowAll || activeCnt > 0 || pIdx < 2;

    const rowsHtml = proj.visibleSessions.map((s) => {
      const cid = escapeHtmlSafe(s.conversation_id || "");
      const title = escapeHtmlSafe(s.title || "Untitled Session");
      const wsFull = escapeHtmlSafe(s.workspace_path || proj.workspace_path || "(unscoped)");
      const wsShort = escapeHtmlSafe(s.workspace_short || formatShortWorkspace(wsFull));
      const status = String(s.status || "IDLE").toUpperCase();
      const isRun = status === "RUNNING" || status === "STALLED_WAITING_APPROVAL";
      const dotCls = isRun ? "running" : (s.is_pinned ? "pinned" : "idle");
      const dotChar = isRun ? "●" : (s.is_pinned ? "◉" : "○");
      const dotTitle = isRun ? status : (s.is_pinned ? `PINNED (${status})` : status);
      const modeObj = formatShortMode(s.mode);
      const updated = escapeHtmlSafe(formatShortUpdated(s));

      return `
        <tr class="hier-session-row">
          <td>
            <div class="sess-cell">
              <span class="sess-dot ${dotCls}" title="${escapeHtmlSafe(dotTitle)}">${dotChar}</span>
              <span class="hier-idx mono">#${Number(s.index || 0)}</span>
              <span class="hier-copy-inline hier-title-txt" data-copy="${title}" title="Click to copy chat title">${title}</span>
            </div>
          </td>
          <td class="mono"><span class="hier-copy-inline hier-uuid" data-copy="${cid}" title="Click to copy full session_id">${cid}</span></td>
          <td class="mono"><span class="hier-copy-inline hier-ws" data-copy="${wsFull}" title="Click to copy full path: ${wsFull}">${wsShort}</span></td>
          <td class="mono"><span class="hier-mode-lbl ${modeObj.cls}">${modeObj.label}</span></td>
          <td class="mono num-col">${Number(s.step_count || 0).toLocaleString()}</td>
          <td class="mono num-col hier-updated">${updated}</td>
          <td class="hier-act-cell">
            <button type="button" class="hier-upload-btn btn" data-cid="${cid}" data-title="${title}" title="Upload files to this session scratch directory">Upload</button>
          </td>
        </tr>
      `;
    }).join("");

    return `
      <details class="hier-proj-card" ${isOpen ? "open" : ""}>
        <summary class="hier-proj-hdr">
          <div class="hier-proj-left">
            <span class="hier-caret mono"></span>
            <span class="hier-proj-idx mono">[${String(pIdx + 1).padStart(2, "0")}]</span>
            <strong class="hier-proj-name">${pName}</strong>
            <span class="hier-copy-inline hier-proj-id mono" data-copy="${pId}" title="Click to copy project_id">${pId}</span>
            ${sharedTag}
          </div>
          <div class="hier-proj-right mono">
            ${activeHtml}
            <span>${proj.visibleSessions.length} chats</span>
            <span>·</span>
            <span>${Number(proj.projSteps || 0).toLocaleString()} steps</span>
          </div>
        </summary>
        <div class="hier-table-wrap">
          <table class="table-clean hier-table">
            <thead>
              <tr>
                <th class="hier-col-sess">Session</th>
                <th class="mono hier-col-uuid">Session ID</th>
                <th class="mono hier-col-ws">Workspace</th>
                <th class="mono hier-col-mode">Mode</th>
                <th class="mono num-col hier-col-steps">Steps</th>
                <th class="mono num-col hier-col-upd">Updated</th>
                <th class="mono hier-col-act">Upload</th>
              </tr>
            </thead>
            <tbody>${rowsHtml}</tbody>
          </table>
        </div>
      </details>
    `;
  }).join("");

  container.querySelectorAll(".hier-copy-inline").forEach((el) => {
    el.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      copyTextWithFeedback(el, el.getAttribute("data-copy") || "", el.innerHTML, 900);
    });
  });

  container.querySelectorAll(".hier-upload-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const cid = btn.getAttribute("data-cid") || "";
      const t = btn.getAttribute("data-title") || "";
      if (typeof window.openUploadModal === "function") {
        window.openUploadModal(cid, t);
      }
    });
  });
}

(function initHierarchyControls() {
  const btnActive = document.getElementById("hierarchyFilterActiveBtn");
  const btnAll = document.getElementById("hierarchyFilterAllBtn");
  const expandBtn = document.getElementById("hierarchyExpandAllBtn");
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
  if (expandBtn) {
    expandBtn.addEventListener("click", () => {
      hierarchyExpandAll = !hierarchyExpandAll;
      if (lastHierarchyBundle) renderHierarchyPanel(lastHierarchyBundle);
    });
  }
  if (copyTreeBtn) {
    copyTreeBtn.addEventListener("click", () => {
      const tree = (lastHierarchyBundle && lastHierarchyBundle.project_session_tree) || {};
      const ascii = tree.ascii_tree || "No ASCII session tree available.";
      copyTextWithFeedback(copyTreeBtn, ascii, "Copy ASCII Tree", 1200);
    });
  }
})();
