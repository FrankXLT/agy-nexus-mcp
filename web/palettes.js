// AGY-NEXUS Overwatch — LibreNMS / RRDTool-Aligned Color Palettes & Coupled Lightness + Hue Session Shaders (v2.7.0)

const MODEL_PALETTE = {
  carbon:         { label: "Gemini 4 Carbon",        short: "Carbon 4",    role: "Main / Apex",  light: "#15803d", dark: "#22c55e" },
  argon_pro:      { label: "Gemini 4 Argon",         short: "Argon 4 Pro", role: "Deep / Pro",   light: "#1d4ed8", dark: "#3b82f6" },
  flash:          { label: "Gemini 3.8 Flash",       short: "Flash 3.8",   role: "Fast Tier",    light: "#0e7490", dark: "#06b6d4" },
  claude_partner: { label: "Claude Sonnet/Opus 5.5", short: "Claude 5.5",  role: "Partner 1x",   light: "#b45309", dark: "#f59e0b" },
  gpt_oss:        { label: "GPT-OSS 120B",           short: "GPT-OSS 120", role: "Failover",     light: "#be123c", dark: "#fb7185" },
};

const SUBAGENT_ROLE_PALETTE = {
  "flash-surgeon":     { light: "#0f766e", dark: "#14b8a6" },
  "flash-auditor":     { light: "#0284c7", dark: "#38bdf8" },
  "flash-scout":       { light: "#4d7c0f", dark: "#84cc16" },
  "argon-sentinel":    { light: "#6d28d9", dark: "#a78bfa" },
  "argon-surgeon":     { light: "#1d4ed8", dark: "#60a5fa" },
  "argon-architect":   { light: "#4338ca", dark: "#818cf8" },
  "research":          { light: "#15803d", dark: "#22c55e" },
  "self":              { light: "#166534", dark: "#4ade80" },
  "claude-specialist": { light: "#c2410c", dark: "#fb923c" },
  "claude-sentinel":   { light: "#b45309", dark: "#f59e0b" },
  "pool-failover":     { light: "#be123c", dark: "#fb7185" },
  "other-subagents":   { light: "#64748b", dark: "#94a3b8" },
};

const SUBAGENT_FALLBACK_SLOTS = [
  { light: "#0f766e", dark: "#14b8a6" },
  { light: "#0284c7", dark: "#38bdf8" },
  { light: "#6d28d9", dark: "#a78bfa" },
  { light: "#1d4ed8", dark: "#60a5fa" },
  { light: "#4d7c0f", dark: "#84cc16" },
  { light: "#15803d", dark: "#22c55e" },
  { light: "#c2410c", dark: "#fb923c" },
  { light: "#be185d", dark: "#ec4899" },
];

// 10-Slot RRD-Nexus Chromatic Project Base Palette (Zero Grays) + Exclusive Roll-Up Slate (#10)
const PROJECT_RRD_PALETTE = [
  { name: "Forest Emerald",       light: "#15803d", dark: "#22c55e" },
  { name: "Deep Cobalt",          light: "#1d4ed8", dark: "#3b82f6" },
  { name: "RRD Olive-Chartreuse", light: "#65a30d", dark: "#84cc16" },
  { name: "RRD Aubergine",        light: "#7e22ce", dark: "#a855f7" },
  { name: "Ocean Cerulean",       light: "#0284c7", dark: "#38bdf8" },
  { name: "Signal Ochre",         light: "#d97706", dark: "#f59e0b" },
  { name: "Abyssal Teal",         light: "#0f766e", dark: "#14b8a6" },
  { name: "Mulberry Rose",        light: "#be185d", dark: "#ec4899" },
  { name: "RRD Indigo",           light: "#4338ca", dark: "#818cf8" },
  { name: "Burnt Copper",         light: "#c2410c", dark: "#fb923c" },
];

const OTHER_PROJECTS_SLATE = { name: "Other Projects", light: "#64748b", dark: "#94a3b8" };

function escapeHtmlSafe(val) {
  return String(val ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function isLightSurfaceMode(surface) {
  const s = String(surface || "obsidian").toLowerCase();
  return s === "white" || s === "pure-white" || s === "warm-paper" || s === "paper";
}

function hexToHsl(hex) {
  const raw = String(hex || "#22c55e").replace("#", "");
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
  const capL = light ? Math.max(18, hsl.l - 10) : Math.min(84, hsl.l + 11);
  return hslToHex(hsl.h, Math.min(95, hsl.s + 4), capL);
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
 * Derive distinct per-session shades within a project's RRD base color family.
 * Uses coupled Lightness stepping (interleaved so adjacent stacked sessions have >=14% L contrast)
 * plus bounded +/-5 deg micro-hue separation across multi-session passes while keeping Saturation >=46%.
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

  // Interleave lightness steps so adjacent stacked bars (idx and idx+1) never blend together
  const passIdx = Math.floor(idx / 4);
  const hueOffsets = [0, 5, -5];
  const microHue = k <= 4 ? (idx % 2 === 1 ? 3 : 0) : (hueOffsets[passIdx % 3] || 0);

  let targetL;
  let targetS;
  if (k <= 4) {
    const t = idx / Math.max(1, k - 1);
    targetL = light ? (31 + t * 33) : (38 + t * 32);
    targetS = Math.max(48, hsl.s * (1 - 0.12 * t));
  } else {
    // Interleaved high/low lightness ladder across up to 12 sessions
    const ladderDark = [36, 55, 44, 66, 39, 60, 49, 71, 34, 53, 46, 68];
    const ladderLight = [29, 48, 37, 59, 32, 52, 42, 65, 27, 45, 39, 62];
    targetL = (light ? ladderLight : ladderDark)[idx % 12];
    const normT = (targetL - 28) / 44;
    targetS = Math.max(46, hsl.s * (1 - 0.14 * normT));
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
