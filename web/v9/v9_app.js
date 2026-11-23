/* SPDX-License-Identifier: Apache-2.0 */
/* AGY-Nexus /web/v9 — App Bootstrap, Sticky Topbar Controller, Lazy Loading & Deep Links */
(() => {
  const V9 = window.AgyV9;
  const st = V9.state;
  let statsSeq = 0;
  let lastMobileHeat = window.innerWidth <= 560;

  function syncActiveProjChip(b) {
    const wrap = document.getElementById("v9ActiveProjWrap");
    const dotEl = document.getElementById("v9ActiveProjDot");
    const nameEl = document.getElementById("v9ActiveProjName");
    if (!wrap) return;
    const pid = st.soloProject || "";
    if (!pid) {
      wrap.classList.add("hidden");
      return;
    }
    const ps = (b && b.project_scope) || (V9.ProjectView && V9.ProjectView.findProjectInBundle(b, pid));
    const slot = ps && ps.color_slot != null ? ps.color_slot : 0;
    const label = (ps && ps.project_name) || pid;
    if (dotEl) dotEl.style.background = V9.getSeriesColor(slot);
    if (nameEl) {
      nameEl.textContent = label;
      nameEl.title = label;
    }
    wrap.classList.remove("hidden");
  }

  function updateVisibility() {
    const unlocked = Boolean(st.passphrase || st.demoMode);
    const isAnal = unlocked && st.surfaceView === "analytics";
    const isWs = unlocked && st.surfaceView === "workspace";
    document.getElementById("v9MenuBtn")?.classList.toggle("hidden", !unlocked);
    document.getElementById("v9AuthOverlay")?.classList.toggle("hidden", unlocked);
    document.getElementById("v9AppShell")?.classList.toggle("hidden", !unlocked);
    document.getElementById("v9TopbarRight")?.classList.toggle("hidden", !unlocked);
    document.getElementById("v9TopbarAnalyticsCtrl")?.classList.toggle("hidden", !isAnal);
    document.getElementById("v9TopbarWorkspaceCtrl")?.classList.toggle("hidden", !isWs);
    document.getElementById("v9AnalyticsView")?.classList.toggle("hidden", !isAnal);
    document.getElementById("v9WorkspaceView")?.classList.toggle("hidden", !isWs);

    const tabAn = document.getElementById("v9TabAnalytics");
    const tabWs = document.getElementById("v9TabWorkspace");
    tabAn?.setAttribute("aria-selected", String(!isWs));
    tabAn?.setAttribute("tabindex", isWs ? "-1" : "0");
    tabWs?.setAttribute("aria-selected", String(isWs));
    tabWs?.setAttribute("tabindex", isWs ? "0" : "-1");
    V9.Hierarchy?.syncRailLayout?.();
  }

  function lockAndReset(reasonMsg) {
    statsSeq += 1;
    localStorage.removeItem("nexus_passphrase");
    sessionStorage.removeItem("nexus_passphrase");
    localStorage.removeItem("nexus_demo_mode");
    st.passphrase = "";
    st.demoMode = false;
    st.bundle = null;
    st.wsTree = null;
    st.wsTreePending = null;
    st.selectedSession = null;
    st.bucket = null;
    st.currentDocPath = "";
    st.soloModel = "";
    st.soloSubagent = "";
    st.soloProject = "";
    st.pendingArtifact = "";
    st.heatPinned = false;
    st.projectCaptureCounts = {};
    if (st.openProjects instanceof Set) st.openProjects.clear();
    if (st.showAllSessionsForProject instanceof Set) st.showAllSessionsForProject.clear();
    if (st.projectCapturesLoaded instanceof Set) st.projectCapturesLoaded.clear();
    if (st.projectCapturesPending instanceof Set) st.projectCapturesPending.clear();

    ["v9LightboxDialog", "sheetExportDialog", "v9UploadDialog"].forEach((id) => {
      const dlg = document.getElementById(id);
      if (dlg && dlg.open) dlg.close();
    });
    if (V9.Charts?.disposeAll) V9.Charts.disposeAll();
    if (V9.Lightbox?.reset) V9.Lightbox.reset();
    if (V9.Gallery?.reset) V9.Gallery.reset();
    if (window.GallerySelect) {
      window.GallerySelect.clearSelection();
      window.GallerySelect.cleanupGestures();
    }
    if (V9.Workspace?.resetSensitiveState) V9.Workspace.resetSensitiveState();
    if (V9.Hierarchy?.reset) V9.Hierarchy.reset();

    ["v9KpiGrid", "v9HeatHost", "v9ModelTableBody", "v9SubagentTableBody", "v9ProjTableWrap", "v9WireClientHost", "v9WireCallsHost", "v9HealthBody", "v9HeatSummary", "v9ModelPlotSub", "v9SubPlotSub", "v9ProjPlotSub", "v9ProjFoot", "v9CadenceSub", "v9CadenceFoot", "v9BillingBody", "v9BillingSub", "v9BillingFoot", "v9WireSub", "v9HealthSummary", "v9PeriodTriggerLabel"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.innerHTML = "";
    });
    const inp = document.getElementById("v9PassInput");
    if (inp) inp.value = "";
    const statusEl = document.getElementById("v9AuthStatus");
    if (statusEl) statusEl.textContent = reasonMsg || "";
    syncActiveProjChip(null);
    V9.syncUrlState?.();
    updateVisibility();
  }

  V9.handleUnauthorized = lockAndReset;
  V9.openProjectAnalytics = openProjectAnalytics;

  async function ensureWorkspaceTree(force) {
    if (st.demoMode && V9.DemoAdapter) {
      if (!st.wsTree || force) {
        st.wsTree = V9.DemoAdapter.getDemoWorkspaceTree();
        V9.Workspace?.updateSessionCountBadges(st.wsTree);
      }
      return st.wsTree;
    }
    if (!force && st.wsTree) return st.wsTree;
    if (!force && st.wsTreePending) return st.wsTreePending;
    if (!st.passphrase) return null;
    st.wsTreePending = V9.apiFetch("/web/api/workspace/tree?include_captures=0")
      .then((t) => {
        if (!st.passphrase || st.demoMode) return null;
        st.wsTree = t;
        localStorage.setItem("nexus_passphrase", st.passphrase);
        sessionStorage.setItem("nexus_passphrase", st.passphrase);
        V9.Workspace?.updateSessionCountBadges(t);
        return t;
      })
      .catch((err) => {
        if (err && (err.status === 401 || err.status === 403)) lockAndReset("Session locked — enter passphrase to continue.");
        return null;
      })
      .finally(() => {
        st.wsTreePending = null;
      });
    return st.wsTreePending;
  }

  function openProjectAnalytics(pid) {
    st.soloProject = pid || "";
    st.soloModel = "";
    st.soloSubagent = "";
    V9.syncUrlState?.();
    st.surfaceView = "analytics";
    updateVisibility();
    window.scrollTo(0, 0);
    loadStats();
  }

  async function openSessionWorkspace(sid) {
    if (!sid) return;
    st.selectedSession = sid;
    st.surfaceView = "workspace";
    V9.syncUrlState?.();
    updateVisibility();
    window.scrollTo(0, 0);
    if (V9.Workspace) {
      await V9.Workspace.initWorkspace();
      if (st.selectedSession !== sid || st.surfaceView !== "workspace") return;
      if (!st.bucket || st.bucket.conversation_id !== sid) await V9.Workspace.selectSession(sid);
    }
  }

  async function openProjectWorkspace(pid, explicitSid) {
    let sid = explicitSid || "";
    if (!sid && st.bundle && V9.ProjectView) {
      sid = V9.ProjectView.latestProjectSessionId(V9.ProjectView.findProjectInBundle(st.bundle, pid));
    }
    if (!sid) {
      const tree = await ensureWorkspaceTree(false);
      if (tree && V9.Workspace?.pickLatestSessionId) sid = V9.Workspace.pickLatestSessionId(tree, pid);
    }
    if (sid) return openSessionWorkspace(sid);
    st.soloProject = pid || st.soloProject;
    switchSurface("workspace");
  }

  function clearProjectScope() {
    if (!st.soloProject && st.surfaceView === "analytics") return;
    openProjectAnalytics("");
  }

  const appActions = {
    openProjectAnalytics,
    openProjectWorkspace,
    openSessionWorkspace,
    clearProjectScope,
    ensureWorkspaceTree,
  };

  function isDemoPresetAvailable(tf, hm) {
    if (!st.demoMode) return true;
    if (V9.DemoAdapter && typeof V9.DemoAdapter.isPresetAvailable === "function") {
      return V9.DemoAdapter.isPresetAvailable(tf, hm);
    }
    return (tf === "month" && hm === "to_date")
      || (tf === "quarter" && hm === "rolling")
      || (tf === "year" && (hm === "to_date" || hm === "rolling"));
  }

  function syncControlButtons() {
    document.querySelectorAll(".v9-period-opt[data-v9-tf]").forEach((btn) => {
      const tf = btn.getAttribute("data-v9-tf") || "month";
      const hm = btn.getAttribute("data-v9-mode") || "to_date";
      const avail = isDemoPresetAvailable(tf, hm);
      btn.disabled = !avail;
      btn.setAttribute("aria-disabled", String(!avail));
      if (!avail) btn.title = "Unlock live workstation for this window";
      else btn.removeAttribute("title");
      const active = avail && st.offset === 0 && tf === st.timeframe && hm === st.mode;
      btn.setAttribute("aria-checked", String(active));
      btn.classList.toggle("is-active", active);
    });
    document.querySelectorAll("[data-v9-metric]").forEach((b) => {
      b.setAttribute("aria-pressed", String(b.getAttribute("data-v9-metric") === st.metric));
    });
    const todayBtn = document.getElementById("v9PeriodTodayBtn");
    if (todayBtn) todayBtn.classList.toggle("hidden", st.offset === 0);

    const prevBtn = document.getElementById("v9PrevPeriodBtn");
    const nextBtn = document.getElementById("v9NextPeriodBtn");
    if (st.demoMode && V9.DemoAdapter) {
      const bounds = V9.DemoAdapter.getDemoBounds(st.timeframe, st.mode, st.offset);
      if (prevBtn) prevBtn.disabled = !bounds.canPrev;
      if (nextBtn) nextBtn.disabled = !bounds.canNext;
    } else {
      if (prevBtn) prevBtn.disabled = false;
      if (nextBtn) nextBtn.disabled = st.offset >= 0;
    }
  }

  function renderBundle(b) {
    if (!b) return;
    st.bundle = b;
    const totalSess = b.project_hierarchy && b.project_hierarchy.total_sessions_count;
    const wsBadge = document.getElementById("v9WsCount");
    if (wsBadge && totalSess != null && !st.wsTree) wsBadge.textContent = String(totalSess);
    V9.Analytics.renderAnalytics(b, () => renderBundle(st.bundle), appActions);
    V9.Heatmap.renderHeatmap(b);
    V9.Charts.renderAllCharts(b);
    V9.Hierarchy.renderHierarchy(b, appActions);
    syncActiveProjChip(b);
    syncControlButtons();
  }

  async function loadStats() {
    const seq = ++statsSeq;
    const authStatus = document.getElementById("v9AuthStatus");
    if (st.demoMode) {
      const b = V9.DemoAdapter.getDemoStatsBundle(st.timeframe, st.mode, st.offset, st.soloProject || "");
      if (b && seq === statsSeq) {
        updateVisibility();
        renderBundle(b);
        return true;
      }
      return false;
    }
    try {
      const q = new URLSearchParams({
        timeframe: st.timeframe,
        horizon_mode: st.mode,
        offset: String(st.offset),
        include_ascii: "0",
      });
      if (st.soloProject) q.set("project_id", st.soloProject);
      else q.set("compact_sessions", "1");
      const b = await V9.apiFetch(`/web/api/stats?${q.toString()}`);
      if (seq !== statsSeq) return false;
      if (authStatus) authStatus.textContent = "";
      localStorage.setItem("nexus_passphrase", st.passphrase);
      sessionStorage.setItem("nexus_passphrase", st.passphrase);
      updateVisibility();
      renderBundle(b);
      return true;
    } catch (err) {
      if (seq !== statsSeq) return false;
      if (err.status === 401 || err.status === 403) {
        lockAndReset("Invalid or locked passphrase. Try again or preview Demo.");
      } else {
        if (authStatus) authStatus.textContent = `Stats unavailable: ${err.message}`;
        updateVisibility();
      }
      return false;
    }
  }

  function switchSurface(target) {
    const next = target === "workspace" ? "workspace" : "analytics";
    const changed = st.surfaceView !== next;
    st.surfaceView = next;
    if (next === "analytics") {
      ["v9CapturesDialog", "v9LightboxDialog", "v9UploadDialog", "sheetExportDialog"].forEach((id) => {
        const d = document.getElementById(id);
        if (d && d.open) d.close();
      });
    }
    V9.syncUrlState?.();
    updateVisibility();
    if (changed) window.scrollTo(0, 0);
    if (next === "workspace" && (st.passphrase || st.demoMode) && V9.Workspace) {
      V9.Workspace.initWorkspace();
    } else if (next === "analytics" && st.bundle) {
      requestAnimationFrame(() => {
        V9.Heatmap.renderHeatmap(st.bundle);
        V9.Charts.renderAllCharts(st.bundle);
      });
    }
  }

  function bindHeaderEvents() {
    document.getElementById("v9TabAnalytics")?.addEventListener("click", () => switchSurface("analytics"));
    document.getElementById("v9TabWorkspace")?.addEventListener("click", () => switchSurface("workspace"));
    document.getElementById("v9BrandLink")?.addEventListener("click", (e) => {
      e.preventDefault();
      clearProjectScope();
    });
    document.getElementById("v9ResetProjBtn")?.addEventListener("click", () => clearProjectScope());
    V9.initTabsA11y(document.querySelector('[role="tablist"]'), (tab) => {
      switchSurface(tab.id === "v9TabWorkspace" ? "workspace" : "analytics");
    });

    function closePeriodPopover(restoreFocus) {
      const pBtn = document.getElementById("v9PeriodPickerBtn");
      const pPop = document.getElementById("v9PeriodPopover");
      if (!pPop || pPop.classList.contains("hidden")) return;
      pPop.classList.add("hidden");
      pPop.style.removeProperty("inset-inline-start");
      pPop.style.removeProperty("inset-inline-end");
      pBtn?.setAttribute("aria-expanded", "false");
      if (restoreFocus) pBtn?.focus();
    }

    function openPeriodPopover(focusItem) {
      const pBtn = document.getElementById("v9PeriodPickerBtn");
      const pPop = document.getElementById("v9PeriodPopover");
      if (!pPop || !pBtn) return;
      pPop.style.removeProperty("inset-inline-start");
      pPop.style.removeProperty("inset-inline-end");
      pPop.classList.remove("hidden");
      pBtn.setAttribute("aria-expanded", "true");
      const r = pPop.getBoundingClientRect();
      const parentLeft = pPop.parentElement ? pPop.parentElement.getBoundingClientRect().left : 0;
      if (r.left < 12) {
        pPop.style.insetInlineEnd = "auto";
        pPop.style.insetInlineStart = `${Math.ceil(12 - parentLeft)}px`;
      }
      const r2 = pPop.getBoundingClientRect();
      if (r2.right > window.innerWidth - 12) {
        const cur = parseFloat(pPop.style.insetInlineStart || "0");
        pPop.style.insetInlineStart = `${cur - Math.ceil(r2.right - (window.innerWidth - 12))}px`;
      }
      if (focusItem) {
        const enabled = Array.from(pPop.querySelectorAll(".v9-period-opt")).filter((el) => !el.disabled);
        const cur = enabled.find((el) => el.getAttribute("aria-checked") === "true") || enabled[0];
        cur?.focus();
      }
    }

    document.addEventListener("click", (e) => {
      const periodWrap = document.getElementById("v9PeriodWrap");
      if (periodWrap && !periodWrap.contains(e.target)) closePeriodPopover(false);
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closePeriodPopover(true);
    });
    V9._periodPopover = { openPeriodPopover, closePeriodPopover };
  }

  function bindAnalyticsAndAuthEvents() {
    document.getElementById("v9UnlockForm")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      st.demoMode = false;
      localStorage.removeItem("nexus_demo_mode");
      st.passphrase = document.getElementById("v9PassInput")?.value.trim() || "";
      const ok = await loadStats();
      if (ok && st.surfaceView === "workspace" && V9.Workspace) V9.Workspace.initWorkspace();
    });
    document.getElementById("v9PreviewDemoBtn")?.addEventListener("click", () => {
      localStorage.removeItem("nexus_passphrase");
      sessionStorage.removeItem("nexus_passphrase");
      st.passphrase = "";
      st.demoMode = true;
      st.offset = 0;
      if (!isDemoPresetAvailable(st.timeframe, st.mode)) {
        st.timeframe = "month";
        st.mode = "to_date";
      }
      localStorage.setItem("nexus_demo_mode", "1");
      V9.syncUrlState?.();
      loadStats().then((ok) => {
        if (ok && st.surfaceView === "workspace" && V9.Workspace) V9.Workspace.initWorkspace();
      });
    });

    const pBtn = document.getElementById("v9PeriodPickerBtn");
    const pPop = document.getElementById("v9PeriodPopover");
    pBtn?.addEventListener("click", (e) => {
      e.stopPropagation();
      const isClosed = !pPop || pPop.classList.contains("hidden");
      if (isClosed) V9._periodPopover?.openPeriodPopover(e.detail === 0);
      else V9._periodPopover?.closePeriodPopover(false);
    });
    pBtn?.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") { e.preventDefault(); V9._periodPopover?.openPeriodPopover(true); }
    });
    pPop?.addEventListener("keydown", (e) => {
      const opts = Array.from(pPop.querySelectorAll(".v9-period-opt")).filter((el) => !el.disabled);
      if (!opts.length) return;
      const idx = opts.indexOf(document.activeElement);
      if (e.key === "ArrowDown") { e.preventDefault(); opts[(idx + 1) % opts.length].focus(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); opts[(idx - 1 + opts.length) % opts.length].focus(); }
      else if (e.key === "Home") { e.preventDefault(); opts[0].focus(); }
      else if (e.key === "End") { e.preventDefault(); opts[opts.length - 1].focus(); }
      else if (e.key === "Tab") { V9._periodPopover?.closePeriodPopover(false); }
    });
    document.querySelectorAll(".v9-period-opt[data-v9-tf]").forEach((opt) => {
      opt.addEventListener("click", (e) => {
        if (opt.disabled) return;
        st.timeframe = opt.getAttribute("data-v9-tf") || "month";
        st.mode = opt.getAttribute("data-v9-mode") || "to_date";
        st.offset = 0;
        V9._periodPopover?.closePeriodPopover(e.detail === 0);
        loadStats();
      });
    });
    document.getElementById("v9PeriodTodayBtn")?.addEventListener("click", () => { st.offset = 0; loadStats(); });
    document.getElementById("v9PrevPeriodBtn")?.addEventListener("click", () => { st.offset -= 1; loadStats(); });
    document.getElementById("v9NextPeriodBtn")?.addEventListener("click", () => { if (st.offset < 0) { st.offset += 1; loadStats(); } });
    document.querySelectorAll("[data-v9-metric]").forEach((b) => {
      b.addEventListener("click", () => { st.metric = b.getAttribute("data-v9-metric") || "steps"; if (st.bundle) renderBundle(st.bundle); });
    });
    document.getElementById("v9HeatWeeksBtn")?.addEventListener("click", () => {
      st.heatPinned = true;
      st.heatWeeks = st.heatWeeks <= 26 ? 53 : 26;
      if (st.bundle) V9.Heatmap.renderHeatmap(st.bundle);
    });
    let lastDesktopRail = window.innerWidth >= 1100;
    let resizeRailTimer = null;
    window.addEventListener("resize", () => {
      const nowMob = window.innerWidth <= 560;
      if (nowMob !== lastMobileHeat) {
        lastMobileHeat = nowMob;
        if (!st.heatPinned) st.heatWeeks = nowMob ? 26 : 53;
        if (st.bundle) V9.Heatmap.renderHeatmap(st.bundle);
      }
      const nowDesktop = window.innerWidth >= 1100;
      if (nowDesktop !== lastDesktopRail) {
        lastDesktopRail = nowDesktop;
        V9.Hierarchy?.syncRailLayout?.();
      } else {
        clearTimeout(resizeRailTimer);
        resizeRailTimer = setTimeout(() => V9.Hierarchy?.syncRailLayout?.(), 80);
      }
      if (st.bundle && st.surfaceView === "analytics") V9.Charts.scheduleRealign();
      if ((st.passphrase || st.demoMode) && V9.Workspace?.syncResponsiveMode) V9.Workspace.syncResponsiveMode();
    });
  }

  function handleDeepLink() {
    const p = V9.urlParams;
    const view = p.get("view");
    const sess = /^[a-zA-Z0-9_-]{1,64}$/.test(p.get("session") || "") ? p.get("session") : "";
    const proj = /^[a-zA-Z0-9._-]{1,96}$/.test(p.get("project") || "") ? p.get("project") : "";
    if (proj) st.soloProject = proj;
    const artifact = p.get("artifact") || "";
    const t = p.get("t");
    const sig = p.get("sig");
    const scopeParam = p.get("scope") || (sess ? ["brain", sess].join(":") : "");
    if (view === "workspace" || sess || window.location.hash === "#workspace") st.surfaceView = "workspace";
    if (sess) st.selectedSession = sess;
    if (artifact) {
      if (!st.passphrase && !st.demoMode && t && sig && scopeParam && V9.Lightbox) {
        const encArt = artifact.split("/").map(encodeURIComponent).join("/");
        const mUrl = `${V9.getBasePath()}/web/media/${encodeURIComponent(t)}/${encodeURIComponent(sig)}/${encodeURIComponent(scopeParam).replace(/%3A/gi, ":")}/${encArt}`;
        V9.Lightbox.openSingle([{ name: artifact.split("/").pop(), signed_url: mUrl }], 0);
      } else {
        st.pendingArtifact = artifact;
      }
    }
  }

  V9.applyTheme(st.theme);
  V9.applyDensity(st.density);
  V9.registerServiceWorker?.();
  V9.bindDialogLightDismiss();
  V9.Hierarchy.wireRailEvents(appActions);
  bindHeaderEvents();
  bindAnalyticsAndAuthEvents();
  handleDeepLink();
  window.addEventListener("hashchange", () => switchSurface(window.location.hash === "#workspace" ? "workspace" : "analytics"));
  window.addEventListener("v9-theme-changed", () => {
    if (st.bundle && st.surfaceView === "analytics") requestAnimationFrame(() => renderBundle(st.bundle));
  });
  updateVisibility();
  if (st.passphrase || st.demoMode) {
    loadStats().then((ok) => {
      if (ok && (st.passphrase || st.demoMode) && st.surfaceView === "workspace" && V9.Workspace) {
        V9.Workspace.initWorkspace();
      }
    });
  }
})();
