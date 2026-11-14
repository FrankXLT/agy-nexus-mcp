// AGY-NEXUS Overwatch — Unified 10-Hue Perceptual OKLCH Color System & Session Shaders (v2.8.0)

// Master 10-Slot Perceptual Palette (Alternating Cool <-> Warm >=95 deg apart; calibrated for Light & Dark surfaces)
const PRAXIS_MASTER_SLOTS = [
  { key: "cobalt",     name: "Ultramarine Cobalt",  light: "#1d5bd6", dark: "#5496ff" },
  { key: "vermilion",  name: "Vermilion Tangerine", light: "#d94e14", dark: "#ff8538" },
  { key: "viridian",   name: "Viridian Teal",       light: "#0b8478", dark: "#28d0bc" },
  { key: "crimson",    name: "Crimson Rose",        light: "#d41e47", dark: "#ff5c7c" },
  { key: "gold",       name: "Imperial Gold",       light: "#b87a08", dark: "#f5be33" },
  { key: "amethyst",   name: "Royal Amethyst",      light: "#7331e0", dark: "#b37bff" },
  { key: "emerald",    name: "Botanical Emerald",   light: "#1b8a42", dark: "#46dc7d" },
  { key: "magenta",    name: "Orchid Magenta",      light: "#b81d80", dark: "#f46ec0" },
  { key: "cerulean",   name: "Cerulean Sky",        light: "#0373b5", dark: "#38bdf8" },
  { key: "terracotta", name: "Copper Terracotta",   light: "#9e3f14", dark: "#e8955b" },
];

const OTHER_PROJECTS_SLATE = { name: "Other Projects", light: "#64748b", dark: "#94a3b8" };

// Unified Model Palette: Google Pool = Cool Triad (Cobalt / Amethyst / Viridian), Partner Pool = Warm Duo (Vermilion / Crimson)
const MODEL_PALETTE = {
  carbon:         { label: "Gemini 4 Carbon",        short: "Carbon 4",    role: "Main / Apex",  light: "#1d5bd6", dark: "#5496ff" },
  argon_pro:      { label: "Gemini 4 Argon",         short: "Argon 4 Pro", role: "Deep / Pro",   light: "#7331e0", dark: "#b37bff" },
  flash:          { label: "Gemini 3.8 Flash",       short: "Flash 3.8",   role: "Fast Tier",    light: "#0b8478", dark: "#28d0bc" },
  claude_partner: { label: "Claude Sonnet/Opus 5.5", short: "Claude 5.5",  role: "Partner 1x",   light: "#d94e14", dark: "#ff8538" },
  gpt_oss:        { label: "GPT-OSS 120B",           short: "GPT-OSS 120", role: "Failover",     light: "#d41e47", dark: "#ff5c7c" },
};

// Unified Subagent Palette: Drawn from the exact same 10 master perceptual tokens so Plots 1-3 share one visual language
const SUBAGENT_ROLE_PALETTE = {
  "flash-surgeon":     { light: "#0b8478", dark: "#28d0bc" },
  "flash-auditor":     { light: "#0373b5", dark: "#38bdf8" },
  "flash-scout":       { light: "#1b8a42", dark: "#46dc7d" },
  "argon-sentinel":    { light: "#7331e0", dark: "#b37bff" },
  "argon-surgeon":     { light: "#1d5bd6", dark: "#5496ff" },
  "argon-architect":   { light: "#b81d80", dark: "#f46ec0" },
  "research":          { light: "#9e3f14", dark: "#e8955b" },
  "self":              { light: "#b87a08", dark: "#f5be33" },
  "claude-specialist": { light: "#d94e14", dark: "#ff8538" },
  "claude-sentinel":   { light: "#b87a08", dark: "#f5be33" },
  "pool-failover":     { light: "#d41e47", dark: "#ff5c7c" },
  "other-subagents":   { light: "#64748b", dark: "#94a3b8" },
};

const SUBAGENT_FALLBACK_SLOTS = PRAXIS_MASTER_SLOTS.map((s) => ({ light: s.light, dark: s.dark }));
const PROJECT_RRD_PALETTE = PRAXIS_MASTER_SLOTS;

function escapeHtmlSafe(val) {
  return String(val ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function isLightSurfaceMode(surface) {
  const s = String(surface || "obsidian").toLowerCase();
  return s === "white" || s === "pure-white" || s === "warm-paper" || s === "paper";
}

function hexToHsl(hex) {
  const raw = String(hex || "#5496ff").replace("#", "");
  const r = parseInt(raw.slice(0, 2), 16) / 255;
  const g = parseInt(raw.slice(2, 4), 16) / 255;
  const b = parseInt(raw.slice(4, 6), 16) / 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  let h = 0;
  let s = 0;
  const l = (max + min) / 2;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    if (max === r) h = (g - b) / d + (g < b ? 6 : 0);
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h *= 60;
  }
  return { h, s: s * 100, l: l * 100 };
}

function hslToHex(h, s, l) {
  const hn = ((h % 360) + 360) % 360;
  const sn = Math.max(0, Math.min(100, s)) / 100;
  const ln = Math.max(0, Math.min(100, l)) / 100;
  const c = (1 - Math.abs(2 * ln - 1)) * sn;
  const x = c * (1 - Math.abs(((hn / 60) % 2) - 1));
  const m = ln - c / 2;
  let r1 = 0, g1 = 0, b1 = 0;
  if (hn < 60) { r1 = c; g1 = x; }
  else if (hn < 120) { r1 = x; g1 = c; }
  else if (hn < 180) { g1 = c; b1 = x; }
  else if (hn < 240) { g1 = x; b1 = c; }
  else if (hn < 300) { r1 = x; b1 = c; }
  else { r1 = c; b1 = x; }
  const toHex = (v) => Math.round((v + m) * 255).toString(16).padStart(2, "0");
  return "#" + toHex(r1) + toHex(g1) + toHex(b1);
}

function makeCapStroke(fillHex, surface) {
  const hsl = hexToHsl(fillHex);
  const light = isLightSurfaceMode(surface);
  const capL = light ? Math.max(16, hsl.l - 11) : Math.min(86, hsl.l + 12);
  return hslToHex(hsl.h, Math.min(96, hsl.s + 5), capL);
}

function getModelColor(modelKey, surface) {
  const entry = MODEL_PALETTE[modelKey] || MODEL_PALETTE.argon_pro;
  const fill = isLightSurfaceMode(surface) ? entry.light : entry.dark;
  return { fill, cap: makeCapStroke(fill, surface), label: entry.label, short: entry.short, role: entry.role };
}

function getSubagentColor(roleName, fallbackIdx, surface) {
  const key = String(roleName || "").toLowerCase();
  const entry = SUBAGENT_ROLE_PALETTE[key] || SUBAGENT_FALLBACK_SLOTS[(fallbackIdx || 0) % SUBAGENT_FALLBACK_SLOTS.length];
  const fill = isLightSurfaceMode(surface) ? entry.light : entry.dark;
  return { fill, cap: makeCapStroke(fill, surface) };
}

function getProjectBaseColor(slotIdx, surface) {
  const light = isLightSurfaceMode(surface);
  if (slotIdx === 10 || slotIdx < 0 || slotIdx === undefined || slotIdx === null) {
    const fill = light ? OTHER_PROJECTS_SLATE.light : OTHER_PROJECTS_SLATE.dark;
    return { fill, cap: makeCapStroke(fill, surface), isRollup: true };
  }
  const slot = PROJECT_RRD_PALETTE[slotIdx % PROJECT_RRD_PALETTE.length];
  const fill = light ? slot.light : slot.dark;
  return { fill, cap: makeCapStroke(fill, surface), isRollup: false };
}

/**
 * Derive distinct per-session shades within a project's base hue family.
 * Interleaves Lightness steps (>=15% L contrast between adjacent stacked sessions)
 * with +/-5 deg micro-hue shift while preserving vibrant chroma (>=50% S).
 */
function deriveSessionShade(slotIdx, shadeIdx, shadeCount, surface) {
  const base = getProjectBaseColor(slotIdx, surface);
  if (base.isRollup || shadeCount <= 1 || shadeIdx < 0) {
    return { fill: base.fill, cap: base.cap };
  }
  const light = isLightSurfaceMode(surface);
  const hsl = hexToHsl(base.fill);
  const k = Math.min(12, Math.max(2, Number(shadeCount || 2)));
  const idx = Math.max(0, Math.min(k - 1, Number(shadeIdx || 0)));

  const passIdx = Math.floor(idx / 4);
  const hueOffsets = [0, 5, -5];
  const microHue = k <= 4 ? (idx % 2 === 1 ? 4 : 0) : (hueOffsets[passIdx % 3] || 0);

  let targetL;
  let targetS;
  if (k <= 4) {
    const ladder4Dark = [44, 63, 53, 72];
    const ladder4Light = [32, 50, 41, 60];
    targetL = (light ? ladder4Light : ladder4Dark)[idx];
    targetS = Math.max(52, hsl.s * (1 - 0.08 * idx));
  } else {
    const ladderDark = [38, 57, 47, 67, 42, 62, 51, 72, 36, 55, 45, 69];
    const ladderLight = [28, 47, 37, 58, 32, 52, 42, 63, 26, 45, 35, 60];
    targetL = (light ? ladderLight : ladderDark)[idx % 12];
    const normT = (targetL - 26) / 46;
    targetS = Math.max(50, hsl.s * (1 - 0.12 * normT));
  }

  const fill = hslToHex(hsl.h + microHue, targetS, targetL);
  return { fill, cap: makeCapStroke(fill, surface) };
}

function buildProjectSwatchStyle(slotIdx, activeCount, surface) {
  const cnt = Number(activeCount || 1);
  if (slotIdx === 10 || cnt <= 1) {
    const b = getProjectBaseColor(slotIdx, surface);
    return `background:${b.fill};border-color:${b.cap};`;
  }
  const s0 = deriveSessionShade(slotIdx, 0, Math.max(3, cnt), surface).fill;
  const s1 = deriveSessionShade(slotIdx, 1, Math.max(3, cnt), surface).fill;
  const s2 = deriveSessionShade(slotIdx, 2, Math.max(3, cnt), surface).fill;
  return `background:linear-gradient(90deg, ${s0} 0% 34%, ${s1} 34% 67%, ${s2} 67% 100%);border-color:${s0};`;
}
