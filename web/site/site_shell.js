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
    const anchored = hasAnchorCss();
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

  function initTopbarPopovers() {
    const entries = [
      { popId: "oawContextPopover", alignRight: false },
      { popId: "oawPillarPopover", alignRight: true },
      { popId: "oawUserPopover", alignRight: true },
    ]
      .map((item) => ({
        ...item,
        el: document.getElementById(item.popId),
        trigger: document.querySelector(`[popovertarget="${item.popId}"]`),
      }))
      .filter((item) => item.el && item.trigger);
    if (!entries.length) return;

    const native = hasNativePopover();
    const isOpen = (el) => (native ? el.matches(":popover-open") : el.classList.contains("is-open"));
    const closeAll = (exceptEl = null) => {
      entries.forEach(({ el, trigger }) => {
        if (el === exceptEl) return;
        if (native) {
          try { if (el.matches(":popover-open")) el.hidePopover(); } catch (_e) {}
          return;
        }
        el.classList.remove("is-open");
        clearPopoverPosition(el);
        trigger.setAttribute("aria-expanded", "false");
      });
    };

    entries.forEach((entry) => {
      if (!native) {
        entry.trigger.addEventListener("click", () => {
          const opening = !isOpen(entry.el);
          closeAll(opening ? entry.el : null);
          entry.el.classList.toggle("is-open", opening);
          entry.trigger.setAttribute("aria-expanded", String(opening));
          if (opening) clampPopover(entry.el, entry.trigger, entry.alignRight);
          else clearPopoverPosition(entry.el);
        });
      }
      entry.el.addEventListener("toggle", (ev) => {
        const open = ev.newState === "open";
        entry.trigger.setAttribute("aria-expanded", String(open));
        if (open) requestAnimationFrame(() => clampPopover(entry.el, entry.trigger, entry.alignRight));
        else clearPopoverPosition(entry.el);
      });
      entry.el.addEventListener("click", (ev) => {
        const origin = ev.target instanceof Element ? ev.target : ev.target?.parentElement;
        if (origin && origin.closest("a[href]")) closeAll(null);
      });
    });

    document.addEventListener("keydown", (ev) => {
      if (ev.key !== "Escape") return;
      const openEntry = entries.find(({ el }) => isOpen(el));
      if (!openEntry) return;
      if (!native) closeAll(null);
      requestAnimationFrame(() => openEntry.trigger.focus({ preventScroll: true }));
    });
    if (!native) {
      document.addEventListener("click", (ev) => {
        const path = typeof ev.composedPath === "function" ? ev.composedPath() : [ev.target];
        if (!entries.some(({ el, trigger }) => path.includes(el) || path.includes(trigger))) closeAll(null);
      });
    }
    window.addEventListener("resize", () => {
      entries.forEach((entry) => {
        if (isOpen(entry.el)) clampPopover(entry.el, entry.trigger, entry.alignRight);
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

  window.AgySiteShell = { setTheme, getTheme: () => currentTheme };
})();
