/* SPDX-License-Identifier: Apache-2.0 */
/* AGY-Nexus /web/v9 — 1-Click Price Book Update Banner, Diff <dialog> & Unmapped M* Alert */
(() => {
  "use strict";
  const V9 = (window.AgyV9 = window.AgyV9 || {});
  const rawEsc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  const esc = (s) => (V9.escHtml ? V9.escHtml(s) : rawEsc(s));
  let activeSync = null;
  let lastCheckedKey = "";
  let reloadBundleCb = null;

  function safeGithubIssueUrl(url) {
    const u = String(url || "").trim();
    return /^https:\/\/github\.com\/[A-Za-z0-9._-]+\/[A-Za-z0-9._-]+\/issues\/new\b/i.test(u) && !/[\s<>"'`]/.test(u) ? u : "";
  }

  function hashKey(str) {
    let h = 2166136261;
    for (let i = 0; i < str.length; i += 1) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return `${str.length}:${(h >>> 0).toString(16)}`;
  }

  function isPreviewForced() {
    try {
      const sp = new URLSearchParams(window.location.search || "");
      return sp.get("preview_catalog") === "1" || sp.get("preview_catalog_banner") === "1";
    } catch (_e) {
      return false;
    }
  }

  function formatRatesPair(inM, outM) {
    const i = (Number(inM || 0) / 1e6).toFixed(2);
    const o = (Number(outM || 0) / 1e6).toFixed(2);
    return `$${i}/$${o}`;
  }

  function renderDiffHtml(sync) {
    const d = (sync && sync.diff) || {};
    const rChanges = Array.isArray(d.rate_changes) ? d.rate_changes : [];
    const aChanges = Array.isArray(d.api_changes) ? d.api_changes : [];
    const newMods = Array.isArray(d.new_models) ? d.new_models : [];
    const ideLock = Array.isArray(d.ide_lock_violations) ? d.ide_lock_violations : [];
    const metaHtml = `<div class="v9-diff-meta"><span><strong>Revision</strong> rev ${esc(d.revision_from || sync.effective_revision || "?")} to rev ${esc(d.revision_to || sync.upstream_revision || "?")}</span><span><strong>Updated</strong> ${esc(d.updated_at || "latest")}</span><span><strong>IDE Locks</strong> ${ideLock.length ? `WARN: ${esc(ideLock.join(", "))}` : "antigravity_ide preserved"}</span></div>`;
    const rows = [];
    rChanges.forEach((rc) => {
      rows.push(`<li class="v9-diff-row"><span class="v9-diff-model">${esc(rc.label || rc.model_key)} rates (${esc(rc.effective_from || "current")})</span><span class="v9-diff-delta">${esc(formatRatesPair(rc.old_in, rc.old_out))} to ${esc(formatRatesPair(rc.new_in, rc.new_out))} / 1M</span></li>`);
    });
    aChanges.forEach((ac) => {
      rows.push(`<li class="v9-diff-row"><span class="v9-diff-model">${esc(ac.label || ac.model_key)} ${esc(ac.field)}</span><span class="v9-diff-delta">${esc(ac.old)} to ${esc(ac.new)}</span></li>`);
    });
    newMods.forEach((mk) => {
      rows.push(`<li class="v9-diff-row"><span class="v9-diff-model">New Model: ${esc(mk)}</span><span class="v9-diff-delta">Added to catalog</span></li>`);
    });
    if (!rows.length && Array.isArray(d.summary_lines)) {
      d.summary_lines.forEach((ln) => rows.push(`<li class="v9-diff-row"><span class="v9-diff-model">${esc(ln)}</span></li>`));
    }
    const listHtml = rows.length
      ? `<ul class="v9-diff-list">${rows.join("")}</ul>`
      : `<p class="v9-cat-detail">Metadata revision increment only; no pricing delta detected.</p>`;
    return `${metaHtml}${listHtml}`;
  }

  function openDiffModal(sync) {
    const dlg = document.getElementById("v9CatalogDiffDialog");
    const body = document.getElementById("v9CatalogDiffBody");
    const accBtn = document.getElementById("v9CatalogDiffAcceptBtn");
    if (!dlg || !body) return;
    dlg.returnValue = "";
    activeSync = sync;
    body.innerHTML = renderDiffHtml(sync);
    const canAccept = Boolean(!V9.state.demoMode && V9.state.passphrase && sync && sync.update_available);
    if (accBtn) {
      accBtn.disabled = !canAccept;
      accBtn.classList.toggle("hidden", !sync || !sync.update_available);
    }
    if (!dlg.open && typeof dlg.showModal === "function") dlg.showModal();
  }

  async function postCatalogAction(endpoint, busyBtn) {
    if (!V9.state.passphrase || V9.state.demoMode) return;
    if (busyBtn) busyBtn.disabled = true;
    try {
      const res = await V9.apiFetch(endpoint, { method: "POST", body: JSON.stringify({}) });
      activeSync = res.catalog_sync || activeSync;
      if (V9.showToast) {
        const msg = endpoint.endsWith("/accept")
          ? `Accepted Price Book rev ${res.catalog_revision || activeSync?.effective_revision || ""}`
          : "Reset to repo-bundled Price Book";
        V9.showToast(msg);
      }
      const dlg = document.getElementById("v9CatalogDiffDialog");
      if (dlg && dlg.open) dlg.close();
      if (typeof reloadBundleCb === "function") await reloadBundleCb();
    } catch (err) {
      if (V9.showToast) V9.showToast(`Catalog sync error: ${err.message || "failed"}`);
    } finally {
      if (busyBtn) busyBtn.disabled = false;
    }
  }

  function bindDialogControls() {
    const dlg = document.getElementById("v9CatalogDiffDialog");
    if (!dlg || dlg.dataset.bound === "1") return;
    dlg.dataset.bound = "1";
    document.getElementById("v9CatalogDiffCloseBtn")?.addEventListener("click", () => dlg.close());
    document.getElementById("v9CatalogDiffCancelBtn")?.addEventListener("click", () => dlg.close());
    document.getElementById("v9CatalogDiffAcceptBtn")?.addEventListener("click", (e) => {
      postCatalogAction("/web/api/catalog/accept", e.currentTarget);
    });
  }

  function renderPriceBookBannerHtml(sync) {
    const showDemo = isPreviewForced() || Boolean(sync && sync._preview);
    if (V9.state.demoMode && !showDemo) return "";
    if (!sync || (!sync.update_available && !sync.override_active && !sync.local_repo_dirty)) return "";

    let tone = "info";
    let tag = "Price Book";
    let title = `Price Book rev ${sync.effective_revision || 1}`;
    let detail = "";
    if (sync.update_available) {
      tag = "Update Available";
      title = `Price Book rev ${sync.upstream_revision} available (local rev ${sync.effective_revision})`;
      const nDiff = ((sync.diff && sync.diff.summary_lines) || []).length;
      detail = nDiff ? `${nDiff} change${nDiff === 1 ? "" : "s"} staged on main` : "Ready to preview";
    } else if (sync.override_active) {
      tone = "override";
      tag = "Override Active";
      title = `User Price Book rev ${sync.effective_revision} active (repo bundled rev ${sync.bundled_revision})`;
      detail = "Saved in AGY_DATA_DIR/catalog_override.json";
    } else if (sync.local_repo_dirty) {
      tag = "Local Edits";
      title = "Local repo Price Book edits active";
      detail = (sync.local_modified_files || []).join(", ");
    }

    const canMutate = Boolean(!V9.state.demoMode && V9.state.passphrase);
    const diffBtn = sync.update_available && sync.diff
      ? `<button type="button" class="v9-nav-btn" id="v9CatPreviewBtn">Preview Diff</button>` : "";
    const accBtn = sync.update_available
      ? `<button type="button" class="v9-nav-btn v9-btn-primary" id="v9CatAcceptBtn"${canMutate ? "" : " disabled"}>Accept Update</button>` : "";
    const rstBtn = sync.override_active
      ? `<button type="button" class="v9-nav-btn" id="v9CatResetBtn"${canMutate ? "" : " disabled"}>Reset Override</button>` : "";

    return `<div class="v9-cat-banner" data-tone="${tone}" role="region" aria-label="Price Book update status"><div class="v9-cat-banner-msg"><span class="v9-cat-tag">${esc(tag)}</span><span class="v9-cat-title">${esc(title)}</span><span class="v9-cat-detail">${esc(detail)}</span></div><div class="v9-cat-actions">${diffBtn}${accBtn}${rstBtn}</div></div>`;
  }

  function renderUnmappedBannerHtml(bundle) {
    const list = Array.isArray(bundle && bundle.unmapped_models) ? bundle.unmapped_models : [];
    if (!list.length) return "";
    const lead = list[0] || {};
    const extra = list.length > 1 ? ` (+${list.length - 1} more)` : "";
    const stepsN = Number(lead.steps || 0);
    const msg = `Unmapped model code ${lead.id || "unknown"}${extra} seen in ${stepsN} step${stepsN === 1 ? "" : "s"}`;
    const issueUrl = safeGithubIssueUrl((bundle && bundle.unmapped_issue_url) || lead.issue_url || "");
    const linkHtml = issueUrl
      ? `<a class="v9-nav-btn v9-btn-warn" id="v9UnmappedReportLink" target="_blank" rel="noopener noreferrer" href="${esc(issueUrl)}">Report Model Code</a>`
      : "";
    return `<div class="v9-cat-banner" data-tone="warn" role="status" aria-live="polite"><div class="v9-cat-banner-msg"><span class="v9-cat-tag">Unmapped Code</span><span class="v9-cat-title">${esc(msg)}</span><span class="v9-cat-detail">Fallback pricing applied until mapped in Price Book.</span></div><div class="v9-cat-actions">${linkHtml}</div></div>`;
  }

  function reset() {
    activeSync = null;
    lastCheckedKey = "";
    reloadBundleCb = null;
    const dlg = document.getElementById("v9CatalogDiffDialog");
    if (dlg && dlg.open) dlg.close();
  }

  function buildPreviewBundle(bundle) {
    const sync = Object.assign({
      _preview: true, effective_revision: 2, upstream_revision: 3, bundled_revision: 2,
      update_available: true, override_active: false,
      diff: {
        revision_from: 2, revision_to: 3, updated_at: "2026-12-01",
        rate_changes: [{ model_key: "carbon", label: "Gemini 4 Carbon", effective_from: "2026-12-01", old_in: 2e6, old_out: 10e6, new_in: 4e6, new_out: 20e6 }],
        api_changes: [], new_models: [], ide_lock_violations: [],
        summary_lines: ["$ Gemini 4 Carbon: $2.00/$10.00 -> $4.00/$20.00 per 1M"],
      },
    }, (bundle && bundle.catalog_sync) || {});
    sync._preview = true; sync.update_available = true; sync.upstream_revision = Math.max(3, Number(sync.effective_revision || 2) + 1);
    const unmapped = (bundle && Array.isArray(bundle.unmapped_models) && bundle.unmapped_models.length)
      ? bundle.unmapped_models : [{ id: "MODEL_PLACEHOLDER_M610", steps: 4, tokens: 1200 }];
    const issueUrl = (bundle && bundle.unmapped_issue_url) || "https://github.com/FrankXLT/agy-nexus-mcp/issues/new?title=Unmapped%20M610";
    return Object.assign({}, bundle || {}, { catalog_sync: sync, unmapped_models: unmapped, unmapped_issue_url: issueUrl });
  }

  function render(bundle, opts) {
    bindDialogControls();
    if (opts && typeof opts.onReload === "function") reloadBundleCb = opts.onReload;
    const host = document.getElementById("v9CatalogAlertHost");
    if (!host) return;
    const effBundle = (isPreviewForced() && (!bundle?.catalog_sync?.update_available || !(bundle?.unmapped_models || []).length))
      ? buildPreviewBundle(bundle) : bundle;
    const sync = (effBundle && effBundle.catalog_sync) || activeSync;
    if (effBundle && effBundle.catalog_sync) activeSync = effBundle.catalog_sync;
    const html = [renderPriceBookBannerHtml(sync), renderUnmappedBannerHtml(effBundle)].filter(Boolean).join("");
    host.innerHTML = html;
    document.getElementById("v9CatPreviewBtn")?.addEventListener("click", () => openDiffModal(sync));
    document.getElementById("v9CatAcceptBtn")?.addEventListener("click", (e) => {
      postCatalogAction("/web/api/catalog/accept", e.currentTarget);
    });
    document.getElementById("v9CatResetBtn")?.addEventListener("click", (e) => {
      postCatalogAction("/web/api/catalog/reset", e.currentTarget);
    });
  }

  async function refreshStatusOnce(bundle, rerenderCb) {
    if (V9.state.demoMode || !V9.state.passphrase) return;
    const key = `${hashKey(V9.state.passphrase)}:${bundle?.version || ""}`;
    if (lastCheckedKey === key) return;
    lastCheckedKey = key;
    try {
      const res = await V9.apiFetch("/web/api/catalog/status");
      if (res && res.ok && res.catalog_sync) {
        activeSync = res.catalog_sync;
        if (V9.state.bundle) {
          V9.state.bundle.catalog_sync = res.catalog_sync;
          render(V9.state.bundle, { onReload: rerenderCb });
        }
      }
    } catch (_err) {
      /* Fail-open when offline or unreachable */
    }
  }

  V9.CatalogBanner = { render, refreshStatusOnce, openDiffModal, renderDiffHtml, reset };
})();
