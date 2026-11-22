/* SPDX-License-Identifier: Apache-2.0 */
/* AGY-Nexus /web/v9 — Workspace Pane Controller, Sequence-Guarded Loaders, 1-Tap MD Tabs & Uploads */
(() => {
  const V9 = window.AgyV9;
  let queuedFiles = [];
  let bucketSeq = 0;
  let docSeq = 0;
  let initSeq = 0;

  function countTotalSessions(treeData) {
    const projs = Array.isArray(treeData && treeData.projects) ? treeData.projects : [];
    return projs.reduce((sum, p) => sum + (Array.isArray(p.sessions) ? p.sessions.length : 0), 0);
  }

  function updateSessionCountBadges(treeData) {
    const total = countTotalSessions(treeData);
    const navBadge = document.getElementById("v9WsCount");
    const paneBadge = document.getElementById("v9WsPaneCount");
    if (navBadge) navBadge.textContent = String(total);
    if (paneBadge) paneBadge.textContent = String(total);
  }

  function closeCapturesModal() {
    const dlg = document.getElementById("v9CapturesDialog");
    if (dlg && dlg.open) dlg.close();
    const splitEl = document.getElementById("v9WsSplit");
    const galPane = document.getElementById("v9GalPane");
    if (splitEl && galPane && galPane.parentElement !== splitEl) {
      splitEl.appendChild(galPane);
    }
  }

  function openCapturesModal() {
    const dlg = document.getElementById("v9CapturesDialog");
    const body = document.getElementById("v9CapturesDialogBody");
    const galPane = document.getElementById("v9GalPane");
    if (!dlg || !body || !galPane) return;
    if (galPane.parentElement !== body) body.appendChild(galPane);
    galPane.classList.remove("hidden");
    const cnt = document.getElementById("v9CapturesBtnCount")?.textContent || "0";
    const ttl = document.getElementById("v9CapturesTitle");
    if (ttl) ttl.textContent = `Session Captures (${cnt})`;
    if (!dlg.open) dlg.showModal();
  }

  function applyWorkspaceMode(mode) {
    const allowed = new Set(["split", "docs", "captures"]);
    const next = allowed.has(mode) ? mode : "split";
    V9.state.wsMode = next;
    const isPhone = window.innerWidth < 760;
    if (!isPhone) closeCapturesModal();
    const effective = isPhone ? "docs" : next;
    const splitEl = document.getElementById("v9WsSplit");
    const docPane = document.getElementById("v9DocPane");
    const galPane = document.getElementById("v9GalPane");
    const capBtn = document.getElementById("v9OpenCapturesBtn");
    if (splitEl) splitEl.setAttribute("data-ws-mode", effective);
    if (docPane) docPane.classList.toggle("hidden", effective === "captures");
    if (galPane && (!galPane.closest("dialog"))) galPane.classList.toggle("hidden", effective === "docs");
    if (capBtn) capBtn.classList.toggle("hidden", !isPhone);
    document.querySelectorAll("[data-v9-wsmode]").forEach((b) => {
      b.setAttribute("aria-pressed", String(b.getAttribute("data-v9-wsmode") === effective));
    });
  }

  function shortDocTabLabel(doc) {
    const raw = String((doc && (doc.name || doc.rel_path)) || "");
    const base = raw.split("/").pop() || raw;
    const low = base.toLowerCase();
    if (low === "implementation_plan.md") return "plan.md";
    if (low === "gemini_research_handoff.md") return "handoff.md";
    return base;
  }

  function renderDocTabs(docs) {
    const host = document.getElementById("v9DocTabs");
    if (!host) return;
    if (!docs.length) {
      host.innerHTML = `<span class="va-meta-inline">No markdown files</span>`;
      return;
    }
    host.innerHTML = docs.map((d) => {
      const active = d.rel_path === V9.state.currentDocPath;
      const lbl = shortDocTabLabel(d);
      return `<button type="button" role="tab" class="va-tab" data-doc-tab="${V9.escHtml(d.rel_path)}" title="${V9.escHtml(d.rel_path)}" aria-selected="${active}" tabindex="${active ? 0 : -1}">${V9.escHtml(lbl)}</button>`;
    }).join("");
    host.querySelectorAll("[data-doc-tab]").forEach((tab) => {
      tab.addEventListener("click", () => viewDoc(tab.getAttribute("data-doc-tab")));
    });
    V9.initTabsA11y(host, (tab) => viewDoc(tab.getAttribute("data-doc-tab")));
  }

  async function viewDoc(relPath) {
    if (!relPath || !V9.state.selectedSession) return;
    const seq = ++docSeq;
    V9.state.currentDocPath = relPath;
    document.querySelectorAll("#v9DocTabs [data-doc-tab]").forEach((tab) => {
      const hit = tab.getAttribute("data-doc-tab") === relPath;
      tab.setAttribute("aria-selected", String(hit));
      tab.setAttribute("tabindex", hit ? "0" : "-1");
    });
    try {
      const resp = V9.state.demoMode
        ? await V9.DemoAdapter.getDemoDocFile(relPath, V9.state.bucket)
        : await V9.apiFetch(`/web/api/sessions/${encodeURIComponent(V9.state.selectedSession)}/file?path=${encodeURIComponent(relPath)}`);
      if (seq !== docSeq) return;
      V9.Markdown.renderDocument(resp, V9.state.bucket, (url, alt) => {
        V9.Lightbox.openSingle([{ name: alt, signed_url: url, rel_path: url }], 0);
      });
    } catch (err) {
      if (seq !== docSeq) return;
      if (err.status === 401 || err.status === 403) {
        V9.handleUnauthorized?.("Session locked (401) — enter passphrase to read artifacts.");
        return;
      }
      const contentEl = document.getElementById("v9DocContent");
      if (contentEl) contentEl.innerHTML = `<div class="v9-empty">Could not load document: ${V9.escHtml(err.message)}</div>`;
    }
  }

  function pickDefaultDoc(docs) {
    if (!docs.length) return "";
    const pref = ["walkthrough.md", "task.md", "implementation_plan.md", "INDEX.md"];
    for (const p of pref) {
      const hit = docs.find((d) => String(d.name || "").toLowerCase() === p.toLowerCase());
      if (hit) return hit.rel_path;
    }
    return docs[0].rel_path;
  }

  function maybeOpenPendingArtifact(bucket) {
    const target = V9.state.pendingArtifact;
    if (!target || !bucket || !V9.Lightbox) return;
    V9.state.pendingArtifact = "";
    const allImgs = [...(bucket.visual_artifacts || []), ...(bucket.repo_visual_assets || [])];
    const base = target.split("/").pop();
    const hitIdx = allImgs.findIndex((it) => it.rel_path === target || it.name === target || it.name === base);
    if (hitIdx >= 0) V9.Lightbox.openSingle(allImgs, hitIdx);
  }

  async function selectSession(cid) {
    if (!cid) return;
    const seq = ++bucketSeq;
    const expectedDemo = Boolean(V9.state.demoMode);
    V9.state.selectedSession = cid;
    document.querySelectorAll("#v9NavRail [data-rail-sess]").forEach((b) => {
      b.setAttribute("aria-current", String(b.getAttribute("data-rail-sess") === cid));
    });
    try {
      const bucket = expectedDemo
        ? await V9.DemoAdapter.getDemoSessionBucket(cid)
        : await V9.apiFetch(`/web/api/sessions/${encodeURIComponent(cid)}/bucket`);
      if (seq !== bucketSeq || Boolean(V9.state.demoMode) !== expectedDemo) return;
      if (!expectedDemo && !V9.state.passphrase) return;
      V9.state.bucket = bucket;
      const titleEl = document.getElementById("v9WsTitle");
      const sidEl = document.getElementById("v9WsShortId");
      const projBtn = document.getElementById("v9WsProjBtn");
      const sepEl = document.getElementById("v9WsSep");
      const projNameEl = document.getElementById("v9WsProjName");
      const projDotEl = document.getElementById("v9WsProjDot");
      const hasProj = Boolean(bucket.project_id && bucket.project_name);
      if (projBtn) projBtn.classList.toggle("hidden", !hasProj);
      if (sepEl) sepEl.classList.toggle("hidden", !hasProj);
      if (projNameEl) projNameEl.textContent = bucket.project_name || "";
      if (projDotEl && hasProj) {
        const proj = V9.ProjectView?.findProjectInBundle?.(V9.state.bundle, bucket.project_id);
        const slot = proj && proj.color_slot != null ? proj.color_slot : 0;
        projDotEl.style.background = V9.getSeriesColor ? V9.getSeriesColor(slot) : "var(--accent-primary)";
      }
      if (titleEl) titleEl.textContent = bucket.title || cid.slice(0, 8);
      if (sidEl) sidEl.textContent = cid.slice(0, 8);
      const docs = (bucket.artifacts || []).filter((a) => /\.(md|markdown|txt)$/i.test(a.name || a.rel_path || ""));
      const initialDoc = pickDefaultDoc(docs);
      V9.state.currentDocPath = initialDoc;
      renderDocTabs(docs);
      if (V9.Gallery) V9.Gallery.renderBucketGallery(bucket);
      maybeOpenPendingArtifact(bucket);
      if (initialDoc) {
        await viewDoc(initialDoc);
        if (seq !== bucketSeq) return;
      } else {
        V9.Markdown.renderDocument(null, bucket);
      }
    } catch (err) {
      if (seq !== bucketSeq) return;
      if (err.status === 401 || err.status === 403) {
        V9.handleUnauthorized?.("Session locked (401) — enter passphrase to continue.");
        return;
      }
      V9.showToast(`Session load failed: ${err.message}`);
    }
  }

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

  function pickLatestSessionId(tree, projectId) {
    const projs = (tree && tree.projects) || [];
    const scope = projectId ? projs.filter((p) => p && p.project_id === projectId) : projs;
    let bestId = "";
    let bestTs = -1;
    for (const p of scope) {
      for (const s of (p.sessions || [])) {
        if (!s || !s.conversation_id) continue;
        const ts = sessionTs(s);
        if (!bestId || ts >= bestTs) {
          bestTs = ts;
          bestId = s.conversation_id;
        }
      }
    }
    return bestId || (tree && tree.selected_session) || "";
  }

  async function initWorkspace(forceRefresh) {
    const seq = ++initSeq;
    const expectedDemo = Boolean(V9.state.demoMode);
    if (!expectedDemo && !V9.state.passphrase) return;
    try {
      let tree = V9.state.wsTree;
      if (!tree || forceRefresh) {
        tree = expectedDemo
          ? V9.DemoAdapter.getDemoWorkspaceTree()
          : await V9.apiFetch("/web/api/workspace/tree?include_captures=0");
        if (seq !== initSeq || Boolean(V9.state.demoMode) !== expectedDemo) return;
        if (!expectedDemo && !V9.state.passphrase) return;
        V9.state.wsTree = tree;
        if (!expectedDemo && V9.state.passphrase) {
          localStorage.setItem("nexus_passphrase", V9.state.passphrase);
          sessionStorage.setItem("nexus_passphrase", V9.state.passphrase);
        }
      }
      updateSessionCountBadges(tree);
      if (V9.Hierarchy && V9.state.railOpen) V9.Hierarchy.renderHierarchy(V9.state.bundle);
      applyWorkspaceMode(V9.state.wsMode);
      const firstSid = V9.state.selectedSession
        || pickLatestSessionId(tree, V9.state.soloProject || "")
        || pickLatestSessionId(tree);
      if (!firstSid) {
        const titleEl = document.getElementById("v9WsTitle");
        if (titleEl) titleEl.textContent = "No workspace sessions found";
        return;
      }
      if (!V9.state.bucket || V9.state.bucket.conversation_id !== firstSid) {
        await selectSession(firstSid);
        if (seq !== initSeq || Boolean(V9.state.demoMode) !== expectedDemo) return;
        V9.syncUrlState?.();
      }
    } catch (err) {
      if (seq !== initSeq) return;
      if (err.status === 401 || err.status === 403) {
        V9.handleUnauthorized?.("Session locked (401) — enter passphrase to continue.");
        return;
      }
      const host = document.getElementById("v9DocContent");
      if (host) host.innerHTML = `<div class="v9-empty">${V9.escHtml(err.message)}</div>`;
    }
  }

  function resetSensitiveState() {
    initSeq += 1;
    bucketSeq += 1;
    docSeq += 1;
    queuedFiles = [];
    V9.state.docMode = "rendered";
    document.getElementById("v9DocRawBtn")?.setAttribute("aria-pressed", "false");
    document.getElementById("v9WsProjBtn")?.classList.add("hidden");
    document.getElementById("v9WsSep")?.classList.add("hidden");
    const dlg = document.getElementById("v9UploadDialog");
    if (dlg && dlg.open) dlg.close();
    closeCapturesModal();
    const inp = document.getElementById("v9UploadInput");
    if (inp) inp.value = "";
    ["v9DocTabs", "v9DocContent", "v9DocMeta", "v9WsProjName", "v9WsTitle", "v9WsShortId", "v9UploadList", "v9UploadResult"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.innerHTML = "";
    });
    const navBadge = document.getElementById("v9WsCount");
    const paneBadge = document.getElementById("v9WsPaneCount");
    if (navBadge) navBadge.textContent = "0";
    if (paneBadge) paneBadge.textContent = "0";
  }

  function bindUploadModal() {
    const dlg = document.getElementById("v9UploadDialog");
    const drop = document.getElementById("v9UploadDrop");
    const inp = document.getElementById("v9UploadInput");
    const listEl = document.getElementById("v9UploadList");
    const resEl = document.getElementById("v9UploadResult");
    const submitBtn = document.getElementById("v9UploadSubmitBtn");
    const setFiles = (fileList) => {
      queuedFiles = Array.from(fileList || []).slice(0, 20);
      if (listEl) listEl.textContent = queuedFiles.length ? `${queuedFiles.length} file(s): ${queuedFiles.map((f) => f.name).join(", ")}` : "No files queued.";
      if (submitBtn) submitBtn.disabled = queuedFiles.length === 0 || V9.state.demoMode;
    };
    document.getElementById("v9OpenUploadBtn")?.addEventListener("click", () => {
      queuedFiles = [];
      if (inp) inp.value = "";
      setFiles([]);
      if (resEl) {
        resEl.textContent = V9.isStaticShowcase?.()
          ? "Read-only interactive showcase — file staging is disabled in static preview."
          : (V9.state.demoMode ? "Demo preview mode: unlock live session to upload files." : "");
      }
      dlg?.showModal();
    });
    document.getElementById("v9UploadCloseBtn")?.addEventListener("click", () => dlg?.close());
    document.getElementById("v9UploadCancelBtn")?.addEventListener("click", () => dlg?.close());
    drop?.addEventListener("click", () => inp?.click());
    drop?.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("is-over"); });
    drop?.addEventListener("dragleave", () => drop.classList.remove("is-over"));
    drop?.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("is-over"); setFiles(e.dataTransfer?.files); });
    inp?.addEventListener("change", () => setFiles(inp.files));
    submitBtn?.addEventListener("click", async () => {
      if (!queuedFiles.length || !V9.state.selectedSession || V9.state.demoMode) return;
      const fd = new FormData();
      queuedFiles.forEach((f) => fd.append("files", f));
      const lbl = document.getElementById("v9UploadLabelInput")?.value.trim() || "";
      if (lbl) fd.append("label", lbl);
      submitBtn.disabled = true;
      try {
        const r = await V9.apiFetch(`/web/api/sessions/${encodeURIComponent(V9.state.selectedSession)}/upload`, { method: "POST", body: fd });
        if (resEl) resEl.textContent = `Uploaded ${r.file_count || queuedFiles.length} file(s) -> ${r.folder_name || "uploads"}`;
        await selectSession(V9.state.selectedSession);
      } catch (err) {
        if (err.status === 401 || err.status === 403) {
          V9.handleUnauthorized?.("Session locked (401) — enter passphrase to upload.");
          return;
        }
        if (resEl) resEl.textContent = `Upload error: ${err.message}`;
      } finally {
        submitBtn.disabled = false;
      }
    });
  }

  function bindWorkspaceControls() {
    document.querySelectorAll("[data-v9-wsmode]").forEach((btn) => {
      btn.addEventListener("click", () => applyWorkspaceMode(btn.getAttribute("data-v9-wsmode")));
    });
    document.getElementById("v9DocRawBtn")?.addEventListener("click", (e) => {
      const isRaw = V9.state.docMode === "raw";
      V9.state.docMode = isRaw ? "rendered" : "raw";
      e.currentTarget.setAttribute("aria-pressed", String(!isRaw));
      if (V9.state.currentDocPath) viewDoc(V9.state.currentDocPath);
    });
    document.getElementById("v9WsProjBtn")?.addEventListener("click", () => {
      const pid = V9.state.bucket && V9.state.bucket.project_id;
      if (pid && V9.openProjectAnalytics) V9.openProjectAnalytics(pid);
    });
    document.getElementById("v9DocPrintBtn")?.addEventListener("click", () => window.print());
    document.getElementById("v9CopySessBtn")?.addEventListener("click", () => {
      if (V9.state.selectedSession) V9.copyText(V9.state.selectedSession, `Copied ${V9.state.selectedSession.slice(0, 8)}`);
    });
    document.getElementById("v9OpenCapturesBtn")?.addEventListener("click", () => openCapturesModal());
    document.getElementById("v9CapturesCloseBtn")?.addEventListener("click", () => {
      closeCapturesModal();
      applyWorkspaceMode(V9.state.wsMode);
    });
    document.getElementById("v9CapturesDialog")?.addEventListener("close", (e) => {
      if (e.currentTarget && e.currentTarget.open) return;
      closeCapturesModal();
      applyWorkspaceMode(V9.state.wsMode);
    });
    bindUploadModal();
  }

  bindWorkspaceControls();
  V9.Workspace = {
    initWorkspace,
    selectSession,
    updateSessionCountBadges,
    resetSensitiveState,
    pickLatestSessionId,
    syncResponsiveMode: () => applyWorkspaceMode(V9.state.wsMode),
  };
})();
