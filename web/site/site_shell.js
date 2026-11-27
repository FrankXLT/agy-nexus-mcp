/* SPDX-License-Identifier: Apache-2.0 */
/* Antigravity Nexus Public Site — Unified 46px Topbar Popovers, 4-Theme Sync, Quickstart & Copy */
(() => {
  const THEME_KEY = "nexus_v9_theme";
  const THEMES = {
    white: { id: "white", scheme: "light", bg: "#FFFFFF" },
    paper: { id: "paper", scheme: "light", bg: "#F6F4EF" },
    "dark-paper": { id: "dark-paper", scheme: "dark", bg: "#141312" },
    dark: { id: "dark", scheme: "dark", bg: "#090D16" },
  };
  const QUICKSTARTS = {
    stdio: {
      cmd: "docker run -i --rm ghcr.io/frankxlt/agy-nexus-mcp:4.2.0 --stdio",
      caption: "Runs the Two-Doorway Setup locally in terminal mode — safe catalog tools work immediately without secrets.",
    },
    http: {
      cmd: "git clone https://github.com/FrankXLT/agy-nexus-mcp.git && cd agy-nexus-mcp && python3 ag_bridge.py",
      caption: "Launches the full local coding bridge, live Analytics & Workspace studio, and Thirty-Minute Passphrase Lock.",
    },
  };
  const DARK_MQL = typeof window.matchMedia === "function" ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  const VIEWPORT_PAD = 8;
  let currentTheme = "white";
  let lastCopyMsg = "";
  const copyTimers = new WeakMap();

  function normalizeTheme(raw) {
    const key = String(raw || "").trim();
    if (Object.hasOwn(THEMES, key)) return key;
    if (key === "system") return DARK_MQL && DARK_MQL.matches ? "dark" : "white";
    return null;
  }

  function readUrlTheme() {
    try {
      return normalizeTheme(new URLSearchParams(window.location.search).get("theme"));
    } catch (_err) {
      return null;
    }
  }

  function readStoredTheme() {
    try {
      return normalizeTheme(localStorage.getItem(THEME_KEY));
    } catch (_err) {
      return null;
    }
  }

  function writeStoredTheme(theme) {
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch (_err) {
      /* Safe no-op in restricted browsing storage */
    }
  }

  function syncThemeUI(rawTheme) {
    const theme = normalizeTheme(rawTheme) || "white";
    const meta = THEMES[theme];
    currentTheme = theme;
    document.documentElement.setAttribute("data-theme", theme);
    const metaScheme = document.querySelector('meta[name="color-scheme"]');
    if (metaScheme) metaScheme.setAttribute("content", meta.scheme);
    const metaColor = document.querySelector('meta[name="theme-color"]');
    if (metaColor) metaColor.setAttribute("content", meta.bg);
    document.querySelectorAll("[data-theme-opt]").forEach((btn) => {
      const active = btn.getAttribute("data-theme-opt") === theme;
      btn.setAttribute("aria-pressed", String(active));
      btn.classList.toggle("is-active", active);
    });
    return theme;
  }

  function setTheme(rawTheme, persist = true) {
    const theme = syncThemeUI(rawTheme);
    if (persist) writeStoredTheme(theme);
    if (window.AgyV9 && typeof window.AgyV9.applyTheme === "function") {
      if (window.AgyV9.state?.theme !== theme) window.AgyV9.applyTheme(theme);
      return theme;
    }
    window.dispatchEvent(new CustomEvent("v9-theme-changed", { detail: { theme } }));
    return theme;
  }

  function initThemeControls() {
    const urlTheme = readUrlTheme();
    const initial = urlTheme || readStoredTheme() || normalizeTheme(document.documentElement.getAttribute("data-theme")) || "white";
    setTheme(initial, Boolean(urlTheme));
    document.querySelectorAll("[data-theme-opt]").forEach((btn) => {
      btn.addEventListener("click", () => {
        setTheme(btn.getAttribute("data-theme-opt"), true);
      });
    });
    window.addEventListener("storage", (ev) => {
      if (ev.key === null || ev.key === THEME_KEY) syncThemeUI(readStoredTheme() || "white");
    });
    window.addEventListener("v9-theme-changed", (ev) => {
      const next = normalizeTheme(ev?.detail?.theme);
      if (next && next !== currentTheme) syncThemeUI(next);
    });
  }

  function hasNativePopover() {
    return typeof HTMLElement !== "undefined" && Object.hasOwn(HTMLElement.prototype, "popover");
  }

  function hasAnchorCss() {
    return typeof CSS !== "undefined" && typeof CSS.supports === "function" && CSS.supports("position-area", "block-end");
  }

  function clearPopoverPosition(pop) {
    if (!pop) return;
    Object.assign(pop.style, { position: "", margin: "", inset: "", top: "", left: "" });
    pop.style.removeProperty("position-anchor");
  }

  function clampPopover(pop, trigger, alignRight) {
    if (!pop || !trigger) return;
    clearPopoverPosition(pop);
    const rect = pop.getBoundingClientRect();
    const trig = trigger.getBoundingClientRect();
    const computedAnchor = typeof getComputedStyle === "function" ? getComputedStyle(pop).positionAnchor : "";
    const hasComputedAnchor = Boolean(computedAnchor && computedAnchor !== "none" && computedAnchor !== "auto");
    const anchored = hasAnchorCss() && hasComputedAnchor;
    const overflows = rect.right > window.innerWidth - VIEWPORT_PAD || rect.left < VIEWPORT_PAD;
    if (anchored && !overflows && rect.bottom <= window.innerHeight - VIEWPORT_PAD) return;

    const maxLeft = Math.max(VIEWPORT_PAD, window.innerWidth - rect.width - VIEWPORT_PAD);
    const rawLeft = alignRight ? trig.right - rect.width : trig.left;
    const rawTop = Math.min(trig.bottom + 6, Math.max(VIEWPORT_PAD, window.innerHeight - rect.height - VIEWPORT_PAD));
    pop.style.setProperty("position-anchor", "none");
    Object.assign(pop.style, {
      position: "fixed",
      margin: "0",
      inset: "auto",
      top: `${Math.round(Math.max(VIEWPORT_PAD, rawTop))}px`,
      left: `${Math.round(Math.min(Math.max(VIEWPORT_PAD, rawLeft), maxLeft))}px`,
    });
  }

  function isPopoverActive(entry) {
    return !entry.responsiveMq || !entry.responsiveMq.matches;
  }

  function isPopoverOpen(entry, native) {
    if (!isPopoverActive(entry)) return false;
    if (native) {
      try { return entry.el.hasAttribute("popover") && entry.el.matches(":popover-open"); } catch (_e) { return false; }
    }
    return entry.el.classList.contains("is-open");
  }

  function syncResponsiveViewMenu(entry, native) {
    const { el: viewMenu, trigger: btnViewSwitcher, responsiveMq } = entry;
    if (!responsiveMq) return;
    if (responsiveMq.matches) {
      if (native) {
        try { if (viewMenu.matches(":popover-open")) viewMenu.hidePopover(); } catch (_e) {}
      } else {
        viewMenu.classList.remove("is-open");
      }
      viewMenu.removeAttribute("popover");
      clearPopoverPosition(viewMenu);
      btnViewSwitcher.setAttribute("aria-expanded", "false");
      return;
    }
    if (viewMenu.getAttribute("popover") !== "auto") viewMenu.setAttribute("popover", "auto");
    if (native && !btnViewSwitcher.hasAttribute("popovertarget")) {
      btnViewSwitcher.setAttribute("popovertarget", entry.popId);
    }
  }

  function bindPopoverEntry(entry, native, closeAll) {
    if (entry.responsiveMq) {
      syncResponsiveViewMenu(entry, native);
      const onMqChange = () => syncResponsiveViewMenu(entry, native);
      if (typeof entry.responsiveMq.addEventListener === "function") entry.responsiveMq.addEventListener("change", onMqChange);
      else if (typeof entry.responsiveMq.addListener === "function") entry.responsiveMq.addListener(onMqChange);
    }
    if (!native) {
      entry.trigger.addEventListener("click", () => {
        if (!isPopoverActive(entry)) return;
        const opening = !isPopoverOpen(entry, native);
        closeAll(opening ? entry.el : null);
        entry.el.classList.toggle("is-open", opening);
        entry.trigger.setAttribute("aria-expanded", String(opening));
        if (opening) clampPopover(entry.el, entry.trigger, entry.alignRight);
        else clearPopoverPosition(entry.el);
      });
    }
    entry.el.addEventListener("toggle", (ev) => {
      if (!isPopoverActive(entry)) return;
      const open = ev.newState === "open";
      entry.trigger.setAttribute("aria-expanded", String(open));
      if (open) requestAnimationFrame(() => clampPopover(entry.el, entry.trigger, entry.alignRight));
      else clearPopoverPosition(entry.el);
    });
    entry.el.addEventListener("click", (ev) => {
      const origin = ev.target instanceof Element ? ev.target : ev.target?.parentElement;
      if (origin && origin.closest("a[href]") && isPopoverOpen(entry, native)) closeAll(null);
    });
  }

  function initTopbarPopovers() {
    const viewMq = typeof window.matchMedia === "function" ? window.matchMedia("(min-width: 900px)") : null;
    const entries = [
      { popId: "oawContextPopover", triggerId: "btnContextSwitcher", alignRight: false },
      { popId: "oawViewMenu", triggerId: "btnViewSwitcher", alignRight: false, responsiveMq: viewMq },
      { popId: "oawPillarPopover", triggerId: "btnPillarSwitcher", alignRight: true },
      { popId: "oawUserPopover", triggerId: "btnUserMenu", alignRight: true },
    ]
      .map((item) => ({
        ...item,
        el: document.getElementById(item.popId),
        trigger: document.querySelector(`[popovertarget="${item.popId}"]`) || document.getElementById(item.triggerId),
      }))
      .filter((item) => item.el && item.trigger);
    if (!entries.length) return;

    const native = hasNativePopover();
    const closeAll = (exceptEl = null) => {
      entries.forEach((entry) => {
        const { el, trigger } = entry;
        if (el === exceptEl || !isPopoverActive(entry)) return;
        if (native) {
          try { if (el.hasAttribute("popover") && el.matches(":popover-open")) el.hidePopover(); } catch (_e) {}
          return;
        }
        el.classList.remove("is-open");
        clearPopoverPosition(el);
        trigger.setAttribute("aria-expanded", "false");
      });
    };

    entries.forEach((entry) => bindPopoverEntry(entry, native, closeAll));

    document.addEventListener("keydown", (ev) => {
      if (ev.key !== "Escape") return;
      if (document.querySelector("dialog[open]")) return;
      const openEntry = entries.find((entry) => isPopoverOpen(entry, native));
      if (!openEntry) return;
      if (!native) closeAll(null);
      requestAnimationFrame(() => openEntry.trigger.focus({ preventScroll: true }));
    });
    if (!native) {
      document.addEventListener("click", (ev) => {
        const path = typeof ev.composedPath === "function" ? ev.composedPath() : [ev.target];
        if (!entries.some((entry) => isPopoverActive(entry) && (path.includes(entry.el) || path.includes(entry.trigger)))) {
          closeAll(null);
        }
      });
    }
    window.addEventListener("resize", () => {
      entries.forEach((entry) => {
        if (entry.responsiveMq) syncResponsiveViewMenu(entry, native);
        if (isPopoverOpen(entry, native)) clampPopover(entry.el, entry.trigger, entry.alignRight);
      });
    });
  }

  function initQuickstartSwitcher() {
    const cmdEl = document.getElementById("quickstart-cmd");
    if (!cmdEl) return;
    const capEl = document.getElementById("quickstartCaption");
    const boxEl = document.getElementById("quickstartBox");
    const setMode = (mode, scrollIntoView = false) => {
      const cfg = Object.hasOwn(QUICKSTARTS, mode) ? QUICKSTARTS[mode] : QUICKSTARTS.stdio;
      const key = Object.hasOwn(QUICKSTARTS, mode) ? mode : "stdio";
      cmdEl.textContent = cfg.cmd;
      if (capEl) capEl.textContent = cfg.caption;
      document.querySelectorAll("[data-quickstart-mode]").forEach((btn) => {
        const active = btn.getAttribute("data-quickstart-mode") === key;
        btn.setAttribute("aria-pressed", String(active));
        if (btn.classList.contains("hero-cmd-pill")) btn.classList.toggle("is-selected", active);
      });
      if (scrollIntoView && boxEl) boxEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
    };
    document.querySelectorAll("[data-quickstart-mode]").forEach((btn) => {
      btn.addEventListener("click", () => {
        setMode(btn.getAttribute("data-quickstart-mode"), btn.classList.contains("hero-cmd-pill"));
      });
    });
  }

  function findStatusBubble(button) {
    const sib = button?.nextElementSibling;
    if (sib && sib.getAttribute("role") === "status") return sib;
    return button?.parentElement ? button.parentElement.querySelector('[role="status"]') : null;
  }

  function reportCopy(button, ok) {
    if (!button) return;
    const tip = findStatusBubble(button);
    clearTimeout(copyTimers.get(button));
    button.removeAttribute("data-copied");
    button.removeAttribute("data-failed");
    let message = ok ? "Copied" : "Copy failed";
    if (message === lastCopyMsg) message += "\u00A0";
    lastCopyMsg = message;
    if (tip) tip.textContent = "";
    void button.offsetWidth;
    button.setAttribute(ok ? "data-copied" : "data-failed", "true");
    requestAnimationFrame(() => { if (tip) tip.textContent = message; });
    copyTimers.set(button, setTimeout(() => {
      button.removeAttribute("data-copied");
      button.removeAttribute("data-failed");
      if (tip) tip.textContent = "";
    }, 2000));
  }

  async function runCopyCommand(button, targetEl) {
    if (!button) return;
    const target = targetEl || document.getElementById(button.getAttribute("commandfor") || "quickstart-cmd");
    const raw = target ? (target.matches("input, textarea") ? target.value : (target.innerText || target.textContent || "")) : "";
    const text = String(raw).trim();
    if (!text) return reportCopy(button, false);
    try {
      if (!navigator.clipboard || typeof navigator.clipboard.writeText !== "function") throw new Error("no clipboard");
      await navigator.clipboard.writeText(text);
      reportCopy(button, true);
    } catch (_err) {
      reportCopy(button, false);
    }
  }

  function initCopyCommands() {
    document.addEventListener("command", (ev) => {
      if (ev.command === "--copy") runCopyCommand(ev.source, ev.target);
    }, true);
    if (!("CommandEvent" in window)) {
      document.addEventListener("click", (ev) => {
        if (ev.defaultPrevented) return;
        const origin = ev.target instanceof Element ? ev.target : ev.target?.parentElement;
        const button = origin ? origin.closest('button[command="--copy"]') : null;
        if (button) runCopyCommand(button, document.getElementById(button.getAttribute("commandfor") || "quickstart-cmd"));
      });
    }
  }

  function boot() {
    initThemeControls();
    initTopbarPopovers();
    initQuickstartSwitcher();
    initCopyCommands();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();

  window.AgySiteShell = { setTheme, applyTheme: setTheme, getTheme: () => currentTheme };
})();
