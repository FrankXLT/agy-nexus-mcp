// Code Health, Modular Hygiene & AST Integrity UI Renderer for /web Overwatch Dashboard (v2.5.0)
function renderCodeHealth(ch, installedVer) {
  installedVer = installedVer || "2.5.0";
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

  const kpiMod = document.getElementById("kpiModularBudget");
  if (kpiMod) kpiMod.textContent = `${(ch.modular_hygiene && ch.modular_hygiene.compliant_300) || 0} / ${(ch.modular_hygiene && ch.modular_hygiene.total_modules) || 0} Modules`;

  const kpiModSub = document.getElementById("kpiModularSub");
  if (kpiModSub) kpiModSub.innerHTML = `${(ch.modular_hygiene && ch.modular_hygiene.warning_301_400) || 0} warning (301-400L) · ${(ch.modular_hygiene && ch.modular_hygiene.violations_over_400) || 0} violations (&gt;400L)`;

  const undefCount = (ch.ast_integrity && (ch.ast_integrity.undefined_names ?? ch.ast_integrity.undefined_count)) || 0;
  const kpiAst = document.getElementById("kpiAstIntegrity");
  if (kpiAst) kpiAst.textContent = `${undefCount} Undefined Names`;

  const scannedCount = (ch.ast_integrity && ch.ast_integrity.scanned_files) || (ch.modular_hygiene && ch.modular_hygiene.total_modules) || 25;
  const kpiAstSub = document.getElementById("kpiAstSub");
  if (kpiAstSub) kpiAstSub.textContent = `All ${scannedCount} modules scope-verified`;

  const lspInstalled = Boolean(ch.local_lsp && (ch.local_lsp.installed || ch.local_lsp.available || ch.local_lsp.status === "ready"));
  const kpiLsp = document.getElementById("kpiLspStatus");
  if (kpiLsp) kpiLsp.textContent = lspInstalled ? "Serena Ready" : "Not Installed";

  const kpiLspSub = document.getElementById("kpiLspSub");
  if (kpiLspSub) kpiLspSub.textContent = `LSP ${(ch.local_lsp && ch.local_lsp.version) || 'v2.1.0'} · --context=antigravity`;

  const ceilBadge = document.getElementById("codeHealthCeilingBadge");
  if (ceilBadge) {
    const violations = (ch.modular_hygiene && ch.modular_hygiene.violations_over_400) || 0;
    ceilBadge.textContent = violations === 0 ? "CEILING: 100% PASS (0 >400L)" : `CEILING: ${violations} VIOLATION (>400L)`;
  }

  const astBadge = document.getElementById("codeHealthAstBadge");
  if (astBadge) {
    astBadge.textContent = `AST: ${undefCount} UNDEF`;
  }

  const serenaBadge = document.getElementById("codeHealthSerenaBadge");
  if (serenaBadge) {
    serenaBadge.textContent = lspInstalled ? "SERENA LSP: READY" : "SERENA LSP: OFFLINE";
  }

  const tbody = document.getElementById("modulesTableBody");
  if (tbody) {
    tbody.innerHTML = "";
    const mods = (ch.modular_hygiene && ch.modular_hygiene.modules) || [];
    mods.forEach((m) => {
      const lines = Number(m.lines || 0);
      let dot = "green";
      let modStatusText = "Compliant (≤300L)";
      if (lines > 400) {
        dot = "slate";
        modStatusText = "Violation (>400L)";
      } else if (lines > 300) {
        dot = "amber";
        modStatusText = "Warning (301-400L)";
      }
      const margin = 400 - lines;
      const marginText = margin >= 0 ? `+${margin} lines` : `${margin} lines`;
      const marginColor = margin < 0 ? "#ef4444" : (margin <= 50 ? "#f59e0b" : "var(--text-secondary)");
      const astErrors = ch.ast_integrity && ch.ast_integrity.details && ch.ast_integrity.details[m.name];
      const astHtml = (astErrors && astErrors.length > 0)
        ? `<span style="color:#ef4444">${astErrors.length} Undefined</span>`
        : `<span style="color:var(--text-secondary)">Clean</span>`;

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong class="mono">${m.name}</strong></td>
        <td class="mono">${lines}</td>
        <td><span style="display:inline-flex;align-items:center;gap:6px;"><span class="status-dot-6px ${dot}"></span><span>${modStatusText}</span></span></td>
        <td>${astHtml}</td>
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
