/* SPDX-License-Identifier: Apache-2.0 */
/* AGY-Nexus /web/v9 — Shared State, Safe Tablist WeakMap, Auth Isolation & Helpers */
(() => {
  const DEFAULT_THEME = "white";
  const DEFAULT_DENSITY = "d2";
  const rawParams = new URLSearchParams(window.location.search);
  const urlDemo = rawParams.get("demo") === "1";
  const urlPass = rawParams.get("pass") || "";
  if (urlPass && window.history && typeof window.history.replaceState === "function") {
    rawParams.delete("pass");
    const qs = rawParams.toString();
    window.history.replaceState(null, "", `${window.location.pathname}${qs ? `?${qs}` : ""}${window.location.hash}`);
  }
  const urlParams = new URLSearchParams(window.location.search);

  function normalizeDensity(d) {
    return d === "d3" || d === "d4" ? "d3" : DEFAULT_DENSITY;
  }

  function isStaticShowcase() {
    return Boolean(window.AGY_STATIC_SHOWCASE) || window.location.hostname.endsWith(".github.io");
  }

  const staticShowcase = isStaticShowcase();

  const state = {
    theme: localStorage.getItem("nexus_v9_theme") || DEFAULT_THEME,
    density: normalizeDensity(localStorage.getItem("nexus_v9_density")),
    surfaceView: window.location.hash === "#workspace" ? "workspace" : "analytics",
    metric: "steps",
    timeframe: "month",
    mode: "to_date",
    offset: 0,
    demoMode: staticShowcase || urlDemo || (!urlPass && localStorage.getItem("nexus_demo_mode") === "1"),
    passphrase: (staticShowcase || urlDemo) ? "" : (urlPass || localStorage.getItem("nexus_passphrase") || sessionStorage.getItem("nexus_passphrase") || ""),
    bundle: null,
    soloModel: "",
    soloSubagent: "",
    soloProject: (urlParams.get("project") || "").trim(),
    heatWeeks: window.innerWidth <= 560 ? 26 : 53,
    heatPinned: false,
    wsMode: "split",
    docMode: "rendered",
    railOpen: false,
    railPinned: localStorage.getItem("nexus_v9_rail_pinned") === "1",
    openProjects: new Set(),
    showAllSessionsForProject: new Set(),
    projectCapturesLoaded: new Set(),
    projectCapturesPending: new Set(),
    projectCaptureCounts: {},
    wsTree: null,
    wsTreePending: null,
    selectedSession: null,
    bucket: null,
    currentDocPath: "",
    comparePair: null,
    pendingArtifact: "",
  };

  function syncUrlState() {
    if (!window.history || typeof window.history.replaceState !== "function") return;
    const params = new URLSearchParams(window.location.search);
    if (state.demoMode && !isStaticShowcase()) params.set("demo", "1");
    else params.delete("demo");
    if (state.soloProject) params.set("project", state.soloProject);
    else params.delete("project");
    if (state.surfaceView === "workspace" && state.selectedSession) params.set("session", state.selectedSession);
    else if (state.surfaceView !== "workspace") params.delete("session");
    const qs = params.toString();
    const hash = state.surfaceView === "workspace" ? "#workspace" : "#analytics";
    window.history.replaceState(null, "", `${window.location.pathname}${qs ? `?${qs}` : ""}${hash}`);
  }

  function getBasePath() {
    return window.location.pathname.replace(/\/web(?:\/v9)?(?:\/index\.html)?\/?$/, "");
  }

  function toAssetUrl(rel) {
    const clean = String(rel || "").replace(/^\.?\/+/, "").replace(/^web\/+/, "");
    return isStaticShowcase() ? `./${clean}` : `${getBasePath()}/web/${clean}`;
  }

  function toAbsUrl(u) {
    const s = String(u || "").trim();
    if (!s) return "";
    if (/^https?:\/\//i.test(s)) return s;
    if (s.startsWith("./")) return `${window.location.href.split(/[?#]/)[0].replace(/[^/]*$/, "")}${s.slice(2)}`;
    return `${window.location.origin}${s.startsWith("/") ? "" : "/"}${s}`;
  }

  function escHtml(val) {
    return String(val == null ? "" : val)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function fmtNum(val) {
    const n = Number(val || 0);
    if (!Number.isFinite(n)) return "0";
    if (Math.abs(n) >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
    if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
    if (Math.abs(n) >= 1e4) return `${(n / 1e3).toFixed(1)}k`;
    return Math.round(n).toLocaleString();
  }

  function fmtUsd(val) {
    const n = Number(val || 0);
    if (!Number.isFinite(n)) return "$0.00";
    const abs = Math.abs(n);
    const sign = n < 0 ? "-" : "";
    if (abs >= 1000) return `${sign}$${Math.round(abs).toLocaleString()}`;
    if (abs >= 100) return `${sign}$${abs.toFixed(1)}`;
    return `${sign}$${abs.toFixed(2)}`;
  }

  function fmtBytes(bytes) {
    const b = Number(bytes || 0);
    if (b >= 1024 * 1024) return `${(b / (1024 * 1024)).toFixed(1)} MB`;
    if (b >= 1024) return `${(b / 1024).toFixed(1)} KB`;
    return `${b} B`;
  }

  function cssVar(name, fallback) {
    try {
      const val = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
      return val || fallback;
    } catch (_e) {
      return fallback;
    }
  }

  function getPalette() {
    return [
      cssVar("--v9-chart-1", "#1D4ED8"),
      cssVar("--v9-chart-2", "#0F766E"),
      cssVar("--v9-chart-3", "#6D28D9"),
      cssVar("--v9-chart-4", "#B45309"),
      cssVar("--v9-chart-5", "#475569"),
      "#0284C7", "#059669", "#9333EA", "#D97706", "#64748B",
    ];
  }

  function getSeriesColor(index) {
    const pal = getPalette();
    return pal[Math.abs(Number(index || 0)) % pal.length];
  }

  function applyTheme(theme) {
    const allowed = new Set(["white", "paper", "dark-paper", "dark"]);
    const next = allowed.has(theme) ? theme : DEFAULT_THEME;
    state.theme = next;
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("nexus_v9_theme", next);
    const metaTheme = document.querySelector('meta[name="theme-color"]');
    if (metaTheme) metaTheme.setAttribute("content", next.startsWith("dark") ? "#090D16" : "#FFFFFF");
    document.querySelectorAll("[data-v9-theme]").forEach((btn) => {
      btn.setAttribute("aria-pressed", String(btn.getAttribute("data-v9-theme") === next));
    });
    window.dispatchEvent(new CustomEvent("v9-theme-changed", { detail: { theme: next } }));
  }

  function applyDensity(density) {
    const next = normalizeDensity(density);
    state.density = next;
    document.documentElement.setAttribute("data-density", next);
    localStorage.setItem("nexus_v9_density", next);
    document.querySelectorAll("[data-v9-density]").forEach((btn) => {
      btn.setAttribute("aria-pressed", String(btn.getAttribute("data-v9-density") === next));
    });
  }

  let toastTimer = null;
  function showToast(msg) {
    const el = document.getElementById("v9Toast");
    if (!el || !msg) return;
    el.textContent = msg;
    el.classList.remove("hidden");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.add("hidden"), 2400);
  }

  async function copyText(text, label) {
    if (!text) return false;
    try {
      await navigator.clipboard.writeText(String(text));
      showToast(label || "Copied to clipboard");
      return true;
    } catch (_e) {
      return false;
    }
  }

  async function apiFetch(subPath, init) {
    const opts = Object.assign({}, init || {});
    const hdrs = new Headers(opts.headers || {});
    if (state.passphrase && !hdrs.has("X-Nexus-Passphrase")) {
      hdrs.set("X-Nexus-Passphrase", state.passphrase);
    }
    opts.headers = hdrs;
    const url = `${getBasePath()}${subPath.startsWith("/") ? subPath : `/${subPath}`}`;
    const res = await fetch(url, opts);
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const j = await res.json();
        if (j && j.error) detail = j.error;
      } catch (_e) {}
      const err = new Error(detail);
      err.status = res.status;
      throw err;
    }
    return res.json();
  }

  function bindDialogLightDismiss() {
    if ("closedBy" in HTMLDialogElement.prototype) return;
    document.querySelectorAll('dialog[closedby="any"]').forEach((dlg) => {
      let downOut = false;
      const isOutside = (ev) => {
        const r = dlg.getBoundingClientRect();
        return ev.clientX < r.left || ev.clientX > r.right || ev.clientY < r.top || ev.clientY > r.bottom;
      };
      dlg.addEventListener("pointerdown", (ev) => { downOut = ev.target === dlg && isOutside(ev); });
      dlg.addEventListener("pointerup", (ev) => { if (downOut && ev.target === dlg && isOutside(ev)) dlg.close(); });
    });
  }

  const tablistHandlers = new WeakMap();
  function initTabsA11y(tablist, onSelect) {
    if (!tablist) return;
    tablistHandlers.set(tablist, onSelect);
    if (tablist.dataset.v9TabsBound === "1") return;
    tablist.dataset.v9TabsBound = "1";
    tablist.addEventListener("keydown", (ev) => {
      const tabs = Array.from(tablist.querySelectorAll('[role="tab"]'));
      const idx = tabs.indexOf(document.activeElement);
      if (idx < 0 || !tabs.length) return;
      let next = idx;
      if (ev.key === "ArrowRight") next = (idx + 1) % tabs.length;
      else if (ev.key === "ArrowLeft") next = (idx - 1 + tabs.length) % tabs.length;
      else if (ev.key === "Home") next = 0;
      else if (ev.key === "End") next = tabs.length - 1;
      else return;
      ev.preventDefault();
      tabs[next].focus();
      const cb = tablistHandlers.get(tablist);
      if (typeof cb === "function") cb(tabs[next]);
    });
  }

  function registerServiceWorker() {
    if (isStaticShowcase() || !("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register(`${getBasePath()}/web/sw.js`, { scope: `${getBasePath() || ""}/` }).catch(() => {});
    let swReloading = false;
    navigator.serviceWorker.addEventListener("controllerchange", () => {
      if (swReloading || sessionStorage.getItem("nexus_sw_reloaded") === "4.0.5") return;
      swReloading = true;
      sessionStorage.setItem("nexus_sw_reloaded", "4.0.5");
      window.location.reload();
    });
  }

  window.AgyV9 = Object.assign(window.AgyV9 || {}, {
    state,
    urlParams,
    isStaticShowcase,
    syncUrlState,
    getBasePath,
    toAssetUrl,
    toAbsUrl,
    escHtml,
    fmtNum,
    fmtUsd,
    fmtBytes,
    cssVar,
    getPalette,
    getSeriesColor,
    applyTheme,
    applyDensity,
    showToast,
    copyText,
    apiFetch,
    registerServiceWorker,
    bindDialogLightDismiss,
    initTabsA11y,
  });
})();
