// Code Health, Polyglot Semantic Index & Modular Hygiene UI Renderer for /web Overwatch Dashboard (v2.7.0)
function renderCodeHealth(ch, installedVer) {
  installedVer = installedVer || "2.7.0";
  let dotClass = "cyan";
  const status = (ch && ch.version && ch.version.status) || "staged_locally";
  if (status === "up_to_date") dotClass = "green";
  else if (status === "update_available") dotClass = "amber";
  else if (status === "staged_locally") dotClass = "cyan";
  else if (status === "offline") dotClass = "slate";

  const vDot = document.getElementById("versionDot");
  if (vDot) vDot.className = "status-dot-6px " + dotClass;

  const vLabel = document.getElementById("versionLabel");
  if (vLabel) vLabel.textContent = `v${(ch && ch.version && ch.version.installed) || installedVer}`;

  const vTag = document.getElementById("versionTag");
  if (vTag) {
    vTag.title = (ch && ch.version && ch.version.status_label) || `Installed version v${installedVer}`;
  }

  if (!ch) return;

  const statusMap = {
    staged_locally: "Staged Locally",
    up_to_date: "Up to Date",
    update_available: "Update Available",
    offline: "Offline",
  };
  const statusText = statusMap[status] || (ch.version && ch.version.status_label) || "Staged Locally";

  const rawRemote = (ch.version && ch.version.remote) || "unknown";
  const remoteTag = rawRemote === "unknown" ? "unknown" : (String(rawRemote).startsWith("v") ? rawRemote : `v${rawRemote}`);
  const rawInst = (ch.version && ch.version.installed) || installedVer;
  const instTag = String(rawInst).startsWith("v") ? rawInst : `v${rawInst}`;

  const vMeta = document.getElementById("versionCompareMeta");
  if (vMeta) {
    const metaLabel = (ch.version && ch.version.status_label) ? ch.version.status_label : statusText;
    vMeta.textContent = `Installed: ${instTag} · Remote: ${remoteTag} (${metaLabel})`;
  }

  const kpiVComp = document.getElementById("kpiVersionComp");
  if (kpiVComp) kpiVComp.innerHTML = `<span class="status-dot-6px ${dotClass}"></span> ${statusText}`;

  const kpiVSub = document.getElementById("kpiVersionSub");
  if (kpiVSub) kpiVSub.textContent = `${instTag} installed · ${remoteTag} GitHub release`;

  const mh = ch.modular_hygiene || {};
  const targetL = mh.target_lines || 500;
  const ceilingL = mh.ceiling_lines || 650;
  const compliantCnt = mh.compliant_500 ?? mh.compliant_300 ?? 0;
  const warnCnt = mh.warning_501_650 ?? mh.warning_301_400 ?? 0;
  const violCnt = mh.violations_over_650 ?? mh.violations_over_400 ?? 0;

  const kpiMod = document.getElementById("kpiModularBudget");
  if (kpiMod) kpiMod.textContent = `${compliantCnt} / ${mh.total_modules || 0} Modules`;

  const kpiModSub = document.getElementById("kpiModularSub");
  if (kpiModSub) kpiModSub.innerHTML = `${warnCnt} warning (${targetL + 1}-${ceilingL}L) · ${violCnt} violations (&gt;${ceilingL}L)`;

  const poly = ch.polyglot_health || ch.ast_integrity || {};
  const symTotal = poly.total_symbols ?? mh.total_symbols ?? 0;
  const indexedFiles = poly.indexed_files || mh.total_modules || 0;
  const longFnCnt = poly.long_functions_over_100 ?? mh.long_functions_over_100 ?? 0;

  const kpiAst = document.getElementById("kpiAstIntegrity");
  if (kpiAst) kpiAst.textContent = `${symTotal} Symbols Indexed`;

  const kpiAstSub = document.getElementById("kpiAstSub");
  if (kpiAstSub) kpiAstSub.textContent = `${indexedFiles} files hashed · ${longFnCnt} funcs >100L`;

  const lspInstalled = Boolean(ch.local_lsp && (ch.local_lsp.installed || ch.local_lsp.available || ch.local_lsp.status === "ready"));
  const kpiLsp = document.getElementById("kpiLspStatus");
  if (kpiLsp) kpiLsp.textContent = lspInstalled ? "Polyglot + Serena" : "Polyglot MCP Ready";

  const kpiLspSub = document.getElementById("kpiLspSub");
  if (kpiLspSub) kpiLspSub.textContent = lspInstalled ? "agy-polyglot-mcp + Serena LSP" : "agy-polyglot-mcp incremental SHA-256";

  const ceilBadge = document.getElementById("codeHealthCeilingBadge");
  if (ceilBadge) {
    ceilBadge.textContent = violCnt === 0 ? `CEILING: 100% PASS (0 >${ceilingL}L)` : `CEILING: ${violCnt} VIOLATION (>${ceilingL}L)`;
  }

  const astBadge = document.getElementById("codeHealthAstBadge");
  if (astBadge) {
    astBadge.textContent = `POLYGLOT: ${symTotal} SYMS`;
  }

  const serenaBadge = document.getElementById("codeHealthSerenaBadge");
  if (serenaBadge) {
    serenaBadge.textContent = lspInstalled ? "POLYGLOT + SERENA: READY" : "POLYGLOT MCP: READY";
  }

  const tbody = document.getElementById("modulesTableBody");
  if (tbody) {
    tbody.innerHTML = "";
    const mods = mh.modules || [];
    mods.forEach((m) => {
      const lines = Number(m.lines || 0);
      let dot = "green";
      let modStatusText = `Compliant (≤${targetL}L)`;
      if (lines > ceilingL) {
        dot = "slate";
        modStatusText = `Violation (>${ceilingL}L)`;
      } else if (lines > targetL) {
        dot = "amber";
        modStatusText = `Warning (${targetL + 1}-${ceilingL}L)`;
      }
      const margin = ceilingL - lines;
      const marginText = margin >= 0 ? `+${margin} lines` : `${margin} lines`;
      const marginColor = margin < 0 ? "#ef4444" : (margin <= 60 ? "#f59e0b" : "var(--text-secondary)");
      const symCount = Number(m.symbols || 0);
      const longFns = Number(m.long_functions || 0);
      const polyHtml = longFns > 0
        ? `<span style="color:#f59e0b">${symCount} syms (${longFns} >100L)</span>`
        : `<span style="color:var(--text-secondary)">${symCount} syms · Clean</span>`;

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong class="mono">${m.name}</strong></td>
        <td class="mono">${lines}</td>
        <td><span style="display:inline-flex;align-items:center;gap:6px;"><span class="status-dot-6px ${dot}"></span><span>${modStatusText}</span></span></td>
        <td>${polyHtml}</td>
        <td class="mono" style="color:${marginColor}">${marginText}</td>
      `;
      tbody.appendChild(tr);
    });
  }
}

if (typeof window !== "undefined") {
  window.renderCodeHealth = renderCodeHealth;
}
if (typeof module !== "undefined" && module.exports) {
  module.exports = { renderCodeHealth };
}
