/* SPDX-License-Identifier: Apache-2.0 */
/* AGY-Nexus /web/v9 — Flat Borderless Overlay Menu, Top-5 Session Cap & 40px Swatch Footer */
(function () {
  const V9 = (window.AgyV9 = window.AgyV9 || {});
  let activeActions = {};
  let chromeBound = false;
  let capturesSeq = 0;

  function sessionTs(s) {
    if (!s) return 0;
    const raw = Number(s.last_updated_ts || 0);
    if (raw > 0) return raw;
    if (s.last_updated) {
      const ms = Date.parse(s.last_updated);
      if (Number.isFinite(ms)) return ms / 1000;
    }
    return 0;
  }

  function mergeProjectEntry(dst, src, defaultSlot) {
    if (!src) return dst;
    if (!dst.project_name && src.project_name) dst.project_name = src.project_name;
    if (src.color_slot != null) dst.color_slot = src.color_slot;
    else if (dst.color_slot == null) dst.color_slot = defaultSlot;
    if (src.share_pct != null) dst.share_pct = Number(src.share_pct);
    if (src.window_steps != null) dst.window_steps = Number(src.window_steps);
    if (Array.isArray(src.staged_handoffs) && src.staged_handoffs.length) dst.staged_handoffs = src.staged_handoffs;
    for (const s of (src.sessions || [])) {
      if (!s || !s.conversation_id) continue;
      const cur = dst.sessMap.get(s.conversation_id) || {};
      dst.sessMap.set(s.conversation_id, Object.assign({}, cur, s));
    }
    return dst;
  }

  function collectUnifiedProjects(b, wsTree) {
    const byId = new Map();
    const h = (b && b.project_hierarchy) || {};
    const statsProjs = [...(h.top_projects || []), ...(Array.isArray(h.idle_projects) ? h.idle_projects : [])];
    statsProjs.forEach((p, idx) => {
      if (!p || !p.project_id || p.is_rollup) return;
      const entry = byId.get(p.project_id) || {
        project_id: p.project_id, project_name: p.project_name || p.project_id,
        color_slot: idx, share_pct: 0, window_steps: 0, staged_handoffs: [], sessMap: new Map(),
      };
      byId.set(p.project_id, mergeProjectEntry(entry, p, idx));
    });
    if (h.other_projects && Array.isArray(h.other_projects.sessions)) {
      const topIds = new Set((h.top_projects || []).map((tp) => tp && tp.project_id).filter(Boolean));
      h.other_projects.sessions.forEach((s) => {
        if (!s || !s.project_id || s.project_id === "__other_projects__" || !s.conversation_id) return;
        const entry = byId.get(s.project_id) || {
          project_id: s.project_id, project_name: s.project_name || s.project_id,
          color_slot: 10, share_pct: 0, window_steps: 0, staged_handoffs: [], sessMap: new Map(),
        };
        if (!topIds.has(s.project_id)) {
          entry.share_pct = Number((entry.share_pct + Number(s.share_pct || 0)).toFixed(2));
        }
        entry.window_steps += Number(s.window_steps || 0);
        entry.sessMap.set(s.conversation_id, s);
        byId.set(s.project_id, entry);
      });
    }
    ((wsTree && wsTree.projects) || []).forEach((wp, idx) => {
      if (!wp || !wp.project_id) return;
      const entry = byId.get(wp.project_id) || {
        project_id: wp.project_id, project_name: wp.project_name || wp.project_id,
        color_slot: idx, share_pct: 0, window_steps: 0, staged_handoffs: [], sessMap: new Map(),
      };
      byId.set(wp.project_id, mergeProjectEntry(entry, wp, idx));
    });

    return Array.from(byId.values()).map((entry) => {
      const sessions = Array.from(entry.sessMap.values()).sort((a, z) => sessionTs(z) - sessionTs(a));
      const maxTs = sessions.reduce((mx, s) => Math.max(mx, sessionTs(s)), 0);
      return {
        project_id: entry.project_id,
        project_name: entry.project_name,
        color_slot: entry.color_slot != null ? entry.color_slot : 0,
        share_pct: Number(entry.share_pct || 0),
        window_steps: Number(entry.window_steps || 0),
        staged_handoffs: entry.staged_handoffs || [],
        sessions,
        latest_session_id: (sessions[0] && sessions[0].conversation_id) || "",
        max_ts: maxTs,
      };
    }).sort((a, z) => (z.window_steps - a.window_steps) || (z.max_ts - a.max_ts));
  }

  function findOwningProjectId(projects, sessionId) {
    if (!sessionId) return "";
    const hit = projects.find((p) => (p.sessions || []).some((s) => s.conversation_id === sessionId));
    return hit ? hit.project_id : "";
  }

  async function maybeFetchProjectCaptures(pid) {
    const st = V9.state;
    if (!pid || st.projectCapturesLoaded.has(pid) || st.projectCapturesPending.has(pid)) return;
    if (st.demoMode) {
      st.projectCapturesLoaded.add(pid);
      ((st.wsTree && st.wsTree.projects) || []).forEach((wp) => {
        if (wp.project_id === pid) {
          (wp.sessions || []).forEach((s) => {
            if (s.capture_count != null) st.projectCaptureCounts[s.conversation_id] = Number(s.capture_count);
          });
        }
      });
      return;
    }
    if (!st.passphrase) return;
    const seq = capturesSeq;
    st.projectCapturesPending.add(pid);
    try {
      const data = await V9.apiFetch(`/web/api/workspace/project-captures?project_id=${encodeURIComponent(pid)}`);
      if (seq !== capturesSeq || st.demoMode || !st.passphrase) return;
      if (data && data.counts) Object.assign(st.projectCaptureCounts, data.counts);
      st.projectCapturesLoaded.add(pid);
    } catch (err) {
      if (seq !== capturesSeq) return;
      if (err && (err.status === 401 || err.status === 403)) {
        V9.handleUnauthorized?.("Session locked (401) — enter passphrase to continue.");
      }
    } finally {
      st.projectCapturesPending.delete(pid);
      if (seq === capturesSeq && (isDesktopPinned() || st.railOpen) && (st.demoMode || st.passphrase)) {
        renderHierarchy(st.bundle, activeActions);
      }
    }
  }

  function applySmartContext(projects) {
    const st = V9.state;
    const owner = findOwningProjectId(projects, st.selectedSession);
    const activePid = st.soloProject || owner;
    if (!activePid) return;
    st.openProjects.add(activePid);
    const proj = projects.find((p) => p.project_id === activePid);
    if (proj && st.selectedSession) {
      const idx = proj.sessions.findIndex((s) => s.conversation_id === st.selectedSession);
      if (idx >= 5) st.showAllSessionsForProject.add(activePid);
    }
    maybeFetchProjectCaptures(activePid);
  }

  function isDesktopWidth() {
    return window.innerWidth >= 1100;
  }

  function isDesktopPinned() {
    return Boolean(V9.state.railPinned && isDesktopWidth());
  }

  function syncMenuButtonUi(desktopPin, drawerOpen) {
    const menuBtn = document.getElementById("v9MenuBtn");
    if (!menuBtn) return;
    menuBtn.querySelector(".v9-menu-icon-burger")?.classList.toggle("hidden", desktopPin);
    menuBtn.querySelector(".v9-menu-icon-panel")?.classList.toggle("hidden", !desktopPin);
    menuBtn.setAttribute("aria-expanded", String(Boolean(desktopPin || drawerOpen)));
    if (desktopPin) {
      menuBtn.setAttribute("aria-label", "Collapse pinned sidebar");
      menuBtn.title = "Collapse pinned sidebar (Ctrl+B)";
    } else {
      menuBtn.setAttribute("aria-label", drawerOpen ? "Close projects and sessions menu" : "Open projects and sessions menu");
      menuBtn.title = "Projects & Sessions menu (Ctrl+B)";
    }
  }

  function ensureRailPopulated() {
    const st = V9.state;
    const projects = collectUnifiedProjects(st.bundle, st.wsTree);
    applySmartContext(projects);
    renderHierarchy(st.bundle, activeActions);
    if (!st.wsTree && activeActions.ensureWorkspaceTree) {
      activeActions.ensureWorkspaceTree().then(() => {
        const merged = collectUnifiedProjects(st.bundle, st.wsTree);
        applySmartContext(merged);
        if ((isDesktopPinned() || st.railOpen) && (st.demoMode || st.passphrase)) {
          renderHierarchy(st.bundle, activeActions);
        }
      });
    }
  }

  function syncRailLayout(opts) {
    const o = opts || {};
    const st = V9.state;
    const unlocked = Boolean(st.passphrase || st.demoMode);
    const shell = document.getElementById("v9AppShell");
    const rail = document.getElementById("v9NavRail");
    const backdrop = document.getElementById("v9WsBackdrop");
    const menuBtn = document.getElementById("v9MenuBtn");
    const wasPinnedDom = Boolean(shell && shell.classList.contains("is-rail-pinned"));
    const desktopPin = Boolean(unlocked && st.railPinned && isDesktopWidth());
    const drawerOpen = Boolean(unlocked && !desktopPin && st.railOpen);

    shell?.classList.toggle("is-rail-pinned", desktopPin);
    if (rail) {
      rail.classList.toggle("is-pinned", desktopPin);
      rail.classList.toggle("is-drawer-open", drawerOpen);
      rail.setAttribute("aria-hidden", String(!(desktopPin || drawerOpen)));
      if (drawerOpen) {
        rail.setAttribute("role", "dialog");
        rail.setAttribute("aria-modal", "true");
      } else {
        rail.removeAttribute("role");
        rail.removeAttribute("aria-modal");
      }
    }
    backdrop?.classList.toggle("hidden", !drawerOpen);
    syncMenuButtonUi(desktopPin, drawerOpen);

    const pinBtn = document.getElementById("v9RailPinBtn");
    if (pinBtn) {
      pinBtn.setAttribute("aria-pressed", String(Boolean(st.railPinned)));
      pinBtn.setAttribute("aria-label", st.railPinned ? "Unpin sidebar" : "Pin sidebar open");
      pinBtn.title = st.railPinned ? "Unpin sidebar" : "Pin sidebar open";
    }

    if ((desktopPin || drawerOpen) && (o.forceRender || (rail && !rail.innerHTML.trim()))) {
      ensureRailPopulated();
    }
    if (drawerOpen && o.focusClose) {
      document.getElementById("v9RailCloseBtn")?.focus({ preventScroll: true });
    } else if (!desktopPin && !drawerOpen && menuBtn && rail && rail.contains(document.activeElement)) {
      menuBtn.focus({ preventScroll: true });
    }
    if (wasPinnedDom !== desktopPin && st.bundle && st.surfaceView === "analytics" && V9.Charts) {
      V9.Charts.scheduleRealign(st.bundle);
    }
  }

  function applyRailVisibility(open) {
    const st = V9.state;
    const next = Boolean(open);
    if (!next && isDesktopPinned()) {
      st.railPinned = false;
      localStorage.setItem("nexus_v9_rail_pinned", "0");
    }
    st.railOpen = next;
    syncRailLayout({ forceRender: next, focusClose: next && !isDesktopPinned() });
  }

  function toggleRailPin() {
    const st = V9.state;
    const nextPinned = !st.railPinned;
    st.railPinned = nextPinned;
    localStorage.setItem("nexus_v9_rail_pinned", nextPinned ? "1" : "0");
    if (!nextPinned) st.railOpen = isDesktopWidth();
    else st.railOpen = false;
    syncRailLayout({ forceRender: true });
  }

  function renderFooterHtml() {
    const st = V9.state;
    const themes = [
      { id: "white", label: "White theme", cls: "v9-swatch-white" },
      { id: "paper", label: "Warm Paper theme", cls: "v9-swatch-paper" },
      { id: "dark-paper", label: "Dark Paper theme", cls: "v9-swatch-dark-paper" },
      { id: "dark", label: "Obsidian theme", cls: "v9-swatch-dark" },
    ];
    const swatches = themes.map((th) => `<button type="button" class="v9-swatch-btn" data-v9-theme="${th.id}" aria-label="${th.label}" title="${th.label}" aria-pressed="${st.theme === th.id}"><span class="v9-swatch-circle ${th.cls}"></span></button>`).join("");
    return `<div class="v9-rail-footer">
      <div class="v9-swatch-row" role="group" aria-label="Surface theme">${swatches}</div>
      <div class="va-tb-group" role="group" aria-label="Information density">
        <button type="button" class="va-tb-btn" data-v9-density="d3" aria-pressed="${st.density === "d3"}">Compact</button>
        <button type="button" class="va-tb-btn" data-v9-density="d2" aria-pressed="${st.density === "d2"}">Comfortable</button>
      </div>
    </div>`;
  }

  function renderProjectGroupHtml(p) {
    const st = V9.state;
    const pid = p.project_id;
    const isExpanded = st.openProjects.has(pid);
    const isSolo = st.soloProject === pid;
    const hasActiveSess = (p.sessions || []).some((s) => s.conversation_id === st.selectedSession);
    const color = V9.getSeriesColor(p.color_slot || 0);
    const pctTxt = p.share_pct > 0 && p.share_pct < 1 ? "<1%" : `${Math.round(p.share_pct)}%`;
    const analyticsActive = isSolo && st.surfaceView === "analytics";

    const stagedOnly = (p.staged_handoffs || []).filter(
      (ho) => String((ho && ho.status) || "").toUpperCase() === "STAGED" && ho.is_unclaimed !== false && !ho.claimed_by_conversation_id
    );
    const handoffRows = stagedOnly.slice(0, 3).map((ho) => {
      const hid = ho.handoff_id || "";
      const targetCid = ho.target_conversation_id || p.latest_session_id;
      return `<button type="button" class="v9-handoff-tag" data-rail-sess="${V9.escHtml(targetCid)}" title="${V9.escHtml(ho.title || hid)}"><span class="v9-handoff-ring" aria-hidden="true"></span><span class="v9-handoff-id">${V9.escHtml(hid)} · STAGED</span></button>`;
    }).join("");

    const allSess = p.sessions || [];
    const showAll = st.showAllSessionsForProject instanceof Set && st.showAllSessionsForProject.has(pid);
    const visibleSess = showAll ? allSess : allSess.slice(0, 5);
    const hiddenCount = Math.max(0, allSess.length - visibleSess.length);
    const capCounts = st.projectCaptureCounts || {};

    const sessRows = visibleSess.map((s) => {
      const cid = s.conversation_id || "";
      const shortId = cid.slice(0, 8);
      const isCur = cid === st.selectedSession;
      const cnt = Number(capCounts[cid] != null ? capCounts[cid] : (s.capture_count || 0));
      const imgSuffix = cnt > 0 ? ` · ${cnt} img` : "";
      return `<button type="button" class="v9-tree-item" data-rail-sess="${V9.escHtml(cid)}" aria-current="${isCur ? "true" : "false"}">
        <span class="v9-tree-item-top"><span class="v9-sess-dot${s.is_running ? " is-run" : ""}" aria-hidden="true"></span><span class="v9-tree-item-title">${V9.escHtml(s.title || shortId)}</span></span>
        <span class="v9-tree-item-meta">${V9.escHtml(shortId)} · ${V9.escHtml(s.relative_age || "recent")}${V9.escHtml(imgSuffix)}</span>
      </button>`;
    }).join("");

    const olderBtn = hiddenCount > 0
      ? `<button type="button" class="v9-show-older-btn" data-show-older="${V9.escHtml(pid)}">Show ${hiddenCount} older...</button>`
      : "";

    return `<div class="v9-tree-group${isSolo ? " is-filtered" : ""}${hasActiveSess ? " is-active-context" : ""}">
      <div class="v9-tree-proj-summary">
        <button type="button" class="v9-rail-proj-main" data-proj-toggle="${V9.escHtml(pid)}" aria-expanded="${isExpanded}">
          <svg class="v9-rail-caret" width="11" height="11" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M6 3.5L10.5 8L6 12.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
          <span class="v9-swatch-dot" style="background:${color}"></span>
          <span class="v9-rail-proj-name" title="${V9.escHtml(p.project_name)}">${V9.escHtml(p.project_name)}</span>
          <span class="v9-rail-proj-pct">${V9.escHtml(pctTxt)}</span>
        </button>
        <button type="button" class="v9-rail-chart-btn${analyticsActive ? " is-active" : ""}" data-rail-analytics="${V9.escHtml(pid)}" aria-label="${V9.escHtml(p.project_name)} Analytics" title="Open Project Analytics">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true"><rect x="2" y="8" width="2.8" height="6" rx="0.6" fill="currentColor"/><rect x="6.6" y="4.5" width="2.8" height="9.5" rx="0.6" fill="currentColor"/><rect x="11.2" y="2" width="2.8" height="12" rx="0.6" fill="currentColor"/></svg>
        </button>
      </div>
      <div class="v9-tree-panel${isExpanded ? "" : " hidden"}">${handoffRows}${sessRows || `<div class="v9-meta-inline">No sessions</div>`}${olderBtn}</div>
    </div>`;
  }

  function escAttrVal(v) {
    return typeof CSS !== "undefined" && typeof CSS.escape === "function"
      ? CSS.escape(String(v))
      : String(v).replace(/["\\]/g, "\\$&");
  }

  function captureRailFocusSelector(rail) {
    const ae = document.activeElement;
    if (!ae || typeof rail.contains !== "function" || !rail.contains(ae)) return "";
    if (ae.id) return `#${escAttrVal(ae.id)}`;
    if (typeof ae.getAttribute !== "function") return "";
    for (const attr of ["data-proj-toggle", "data-show-older", "data-rail-analytics", "data-rail-sess", "data-v9-theme", "data-v9-density"]) {
      const val = ae.getAttribute(attr);
      if (val) return `[${attr}="${escAttrVal(val)}"]`;
    }
    return "";
  }

  function renderHierarchy(b, actions) {
    if (actions) activeActions = actions;
    const rail = document.getElementById("v9NavRail");
    if (!rail) return;
    const st = V9.state;
    const restoreSel = captureRailFocusSelector(rail);
    const projects = collectUnifiedProjects(b, st.wsTree);
    const totalSess = (b && b.project_hierarchy && b.project_hierarchy.total_sessions_count)
      || projects.reduce((acc, p) => acc + p.sessions.length, 0);

    rail.innerHTML = `<div class="v9-rail-hdr">
        <div class="v9-analytics-bar-grp">
          <span class="va-kicker">Projects &amp; Sessions</span>
          <span class="v9-meta-inline">${projects.length} · ${totalSess}</span>
        </div>
        <div class="v9-rail-hdr-actions">
          <button type="button" id="v9RailPinBtn" class="v9-ghost-btn v9-ghost-btn-sm v9-rail-pin-btn" aria-pressed="${Boolean(st.railPinned)}" aria-label="${st.railPinned ? "Unpin sidebar" : "Pin sidebar open"}" title="${st.railPinned ? "Unpin sidebar" : "Pin sidebar open"}">
            <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M5.5 2.5H10.5L9.5 6.5L12 8.5V10H8.7V13.8L8 14.5L7.3 13.8V10H4V8.5L6.5 6.5L5.5 2.5Z" stroke="currentColor" stroke-width="1.35" stroke-linejoin="round"${st.railPinned ? ' fill="currentColor" fill-opacity="0.22"' : ""}/></svg>
          </button>
          <button type="button" id="v9RailCloseBtn" class="v9-ghost-btn v9-ghost-btn-sm" aria-label="Close menu" title="Close sidebar">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M4 4L12 12M12 4L4 12" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
          </button>
        </div>
      </div>
      <div class="v9-rail-body">
        <button type="button" id="v9RailAllBtn" class="v9-rail-all-btn" aria-current="${!st.soloProject ? "true" : "false"}">
          <span>All Projects</span>
          <span class="v9-meta-inline">${projects.length} proj · ${totalSess} sess</span>
        </button>
        ${projects.map(renderProjectGroupHtml).join("")}
      </div>
      ${renderFooterHtml()}`;

    bindRailBodyEvents(rail);
    if (restoreSel && typeof rail.querySelector === "function") {
      const target = rail.querySelector(restoreSel) || document.getElementById("v9RailCloseBtn");
      target?.focus?.({ preventScroll: true });
    }
  }

  function closeUnpinnedDrawer() {
    if (!isDesktopPinned()) applyRailVisibility(false);
  }

  function bindRailBodyEvents(rail) {
    document.getElementById("v9RailPinBtn")?.addEventListener("click", () => toggleRailPin());
    document.getElementById("v9RailCloseBtn")?.addEventListener("click", () => applyRailVisibility(false));
    document.getElementById("v9RailAllBtn")?.addEventListener("click", () => {
      closeUnpinnedDrawer();
      if (activeActions.clearProjectScope) activeActions.clearProjectScope();
      if (isDesktopPinned()) renderHierarchy(V9.state.bundle, activeActions);
    });
    rail.querySelectorAll("[data-proj-toggle]").forEach((el) => {
      el.addEventListener("click", () => {
        const pid = el.getAttribute("data-proj-toggle");
        if (!pid) return;
        if (V9.state.openProjects.has(pid)) V9.state.openProjects.delete(pid);
        else { V9.state.openProjects.add(pid); maybeFetchProjectCaptures(pid); }
        renderHierarchy(V9.state.bundle, activeActions);
      });
    });
    rail.querySelectorAll("[data-show-older]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const pid = btn.getAttribute("data-show-older");
        if (pid) V9.state.showAllSessionsForProject.add(pid);
        renderHierarchy(V9.state.bundle, activeActions);
      });
    });
    rail.querySelectorAll("[data-rail-analytics]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const pid = btn.getAttribute("data-rail-analytics");
        closeUnpinnedDrawer();
        if (pid && activeActions.openProjectAnalytics) activeActions.openProjectAnalytics(pid);
      });
    });
    rail.querySelectorAll("[data-rail-sess]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const sid = btn.getAttribute("data-rail-sess");
        closeUnpinnedDrawer();
        if (sid && activeActions.openSessionWorkspace) activeActions.openSessionWorkspace(sid);
        if (isDesktopPinned()) renderHierarchy(V9.state.bundle, activeActions);
      });
    });
    rail.querySelectorAll("[data-v9-theme]").forEach((btn) => {
      btn.addEventListener("click", () => {
        V9.applyTheme(btn.getAttribute("data-v9-theme"));
        if (V9.state.bundle && V9.state.surfaceView === "analytics" && V9.Charts) V9.Charts.renderAllCharts(V9.state.bundle);
      });
    });
    rail.querySelectorAll("[data-v9-density]").forEach((btn) => {
      btn.addEventListener("click", () => {
        V9.applyDensity(btn.getAttribute("data-v9-density"));
        if (V9.state.bundle && V9.state.surfaceView === "analytics" && V9.Charts) V9.Charts.scheduleRealign(V9.state.bundle);
      });
    });
  }

  function wireRailEvents(actions) {
    if (actions) activeActions = actions;
    if (chromeBound) return;
    chromeBound = true;
    document.getElementById("v9MenuBtn")?.addEventListener("click", () => {
      if (isDesktopPinned()) applyRailVisibility(false);
      else applyRailVisibility(!V9.state.railOpen);
    });
    document.getElementById("v9WsBackdrop")?.addEventListener("click", () => applyRailVisibility(false));
    document.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && String(e.key).toLowerCase() === "b") {
        if ((!V9.state.passphrase && !V9.state.demoMode) || document.querySelector("dialog[open]")) return;
        e.preventDefault();
        if (isDesktopPinned()) applyRailVisibility(false);
        else applyRailVisibility(!V9.state.railOpen);
      } else if (e.key === "Escape" && V9.state.railOpen && !isDesktopPinned()) {
        applyRailVisibility(false);
      }
    });
  }

  function reset() {
    capturesSeq += 1;
    V9.state.railOpen = false;
    syncRailLayout();
    const rail = document.getElementById("v9NavRail");
    if (rail) rail.innerHTML = "";
  }

  V9.Hierarchy = { renderHierarchy, wireRailEvents, applyRailVisibility, syncRailLayout, toggleRailPin, isDesktopPinned, reset };
})();
