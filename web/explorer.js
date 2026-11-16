// AGY-NEXUS Overwatch — 2-Pane Workspace Explorer & Stage Reader (v3.2.1)
(function (root, factory) {
  if (typeof define === "function" && define.amd) {
    define(["./markdown_renderer", "./gallery_select"], factory);
  } else if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./markdown_renderer"), require("./gallery_select"));
  } else {
    root.WorkspaceExplorer = factory(root.MarkdownRenderer, root.GallerySelect);
  }
})(typeof self !== "undefined" ? self : this, function (MarkdownRenderer, GallerySelect) {
  "use strict";

  const expState = {
    treeData: null, selectedSessionId: "", selectedProjectName: "", selectedRepoSlug: "",
    selectedSessionTitle: "", selectedBucket: null, selectedFilePath: "", selectedFileName: "",
    selectedFileSize: 0, rawFileContent: "", renderedHtmlContent: "", docViewMode: "html",
    selectedBatchFolder: "", stageMode: "overview", queueDocFile: "", queueDocTid: "",
    docBackTarget: "overview", searchQuery: "", showCompletedQueue: false,
    expandedProjects: new Set(), isSidebarCollapsed: false, isZenMode: false,
  };

  const escapeHtmlSafe = (s) => String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  const getApiHeaders = () => ({ "X-Nexus-Passphrase": (typeof state !== "undefined" && state.passphrase) || localStorage.getItem("nexus_passphrase") || "", "X-Client-Product": "Workspace Explorer" });
  const getBaseApiPath = () => (window.location.pathname || "/web").replace(/\/web\/?$/, "");
  const toAbsoluteMediaUrl = (url) => (!url || url.startsWith("http://") || url.startsWith("https://")) ? (url || "") : `${window.location.origin}${url.startsWith("/") ? "" : "/"}${url}`;

  function formatRelativeAge(mtime) {
    if (!mtime) return "";
    const sec = Math.max(0, Math.floor(Date.now() / 1000 - Number(mtime)));
    return sec < 60 ? `${sec}s ago` : (sec < 3600 ? `${Math.floor(sec / 60)}m ago` : (sec < 86400 ? `${Math.floor(sec / 3600)}h ago` : `${Math.floor(sec / 86400)}d ago`));
  }

  function formatUploadBatchLabel(ub) {
    if (!ub?.folder_name) return "Upload batch";
    const m = ub.folder_name.match(/^uploads_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})(?:_(.*))?$/);
    return m ? `📂 ${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]}${m[7] ? ` · ${m[7]}` : ""} (${ub.file_count})` : `📂 ${ub.folder_name} (${ub.file_count})`;
  }

  function openLightbox(imgUrl, title, meta) {
    const dlg = document.getElementById("lightboxModal");
    if (!dlg) return window.open(imgUrl, "_blank");
    const imgEl = document.getElementById("lightboxImg"), titleEl = document.getElementById("lightboxTitle");
    const metaEl = document.getElementById("lightboxMeta"), copyBtn = document.getElementById("lightboxCopyLinkBtn");
    if (imgEl) imgEl.src = imgUrl;
    if (titleEl) titleEl.textContent = title || "Visual Artifact Preview";
    if (metaEl) metaEl.textContent = meta || "";
    if (copyBtn) copyBtn.onclick = () => { const fl = toAbsoluteMediaUrl(imgUrl); navigator.clipboard?.writeText(fl); copyBtn.textContent = "Copied!"; setTimeout(() => { copyBtn.textContent = "Copy 7d Link"; }, 1200); };
    document.getElementById("lightboxCloseBtn")?.addEventListener("click", () => dlg.close(), { once: true });
    dlg.onclick = (e) => { if (e.target === dlg) dlg.close(); };
    typeof dlg.showModal === "function" ? dlg.showModal() : dlg.setAttribute("open", "");
  }

  async function loadWorkspaceTree() {
    try {
      if (typeof state !== "undefined" && state.demoMode) {
        expState.treeData = window.DEMO_WORKSPACE_TREE || { ok: true, selected_session: "demo-sess-01", queue: { staged_count: 1, tickets: [{ handoff_id: "agy-nexus-mcp-01", repo_slug: "agy-nexus-mcp", title: "Clean 2-Pane Workspace & Foldable UI Bug Fixes", status: "STAGED", relative_age: "15m ago", handoff_file: "scratch/gemini_research_handoff.md" }] }, projects: [{ project_name: "Core Infrastructure & Container GitOps", staged_count: 1, sessions: [{ conversation_id: "demo-sess-01", title: "AGY-Nexus MCP v3.1.0 Overwatch", status: "RUNNING", is_pinned: true, step_count: 152 }] }] };
        renderLeftTree(); selectSession("demo-sess-01", "Core Infrastructure & Container GitOps", "AGY-Nexus MCP v3.1.0 Overwatch"); return;
      }
      const resp = await fetch(getBaseApiPath() + "/web/api/workspace/tree", { headers: getApiHeaders() });
      if (resp.status === 401 && typeof showAuthModal === "function") return showAuthModal();
      const data = await resp.json();
      if (!data.ok) return;
      expState.treeData = data; renderLeftTree();
      if (!expState.selectedSessionId && expState.stageMode !== "queue") {
        if (data.selected_session) selectSession(data.selected_session);
        else if (data.projects?.[0]?.sessions?.[0]) selectSession(data.projects[0].sessions[0].conversation_id, data.projects[0].project_name, data.projects[0].sessions[0].title);
      }
    } catch (err) { console.warn("Error loading workspace tree:", err); }
  }

  async function selectSession(convId, projectName, sessionTitle) {
    if (!convId) return;
    expState.selectedSessionId = convId; expState.stageMode = "overview";
    if (projectName) expState.selectedProjectName = projectName;
    if (sessionTitle) expState.selectedSessionTitle = sessionTitle;
    window.GallerySelect?.clearSelection?.(); renderSessionHeader(); renderLeftTree();
    if (typeof state !== "undefined" && state.demoMode) {
      expState.selectedBucket = window.DEMO_SESSION_BUCKET || { ok: true, conversation_id: convId, title: expState.selectedSessionTitle, project_name: expState.selectedProjectName, repo_slug: "agy-nexus-mcp", rollover: { posture: "FRESH", reason: "FRESH: Optimal context headroom.", should_rollover: false }, uploads: [], artifacts: [{ name: "walkthrough.md", rel_path: "walkthrough.md", size: 4500, mtime: Date.now() / 1000 - 600, type: "artifact" }], visual_artifacts: [{ name: "preview_desktop.png", signed_url: "/web/icon.svg", rel_path: "scratch/preview_desktop.png", size: 48000, mtime: Date.now() / 1000 - 600 }] };
      renderSessionHeader(); renderLeftTree(); renderStage(); return;
    }
    try {
      const resp = await fetch(getBaseApiPath() + `/web/api/sessions/${encodeURIComponent(convId)}/bucket`, { headers: getApiHeaders() });
      const data = await resp.json();
      if (data.ok) {
        expState.selectedBucket = data;
        expState.selectedProjectName = data.project_name || expState.selectedProjectName;
        expState.selectedRepoSlug = data.repo_slug || expState.selectedRepoSlug;
        expState.selectedSessionTitle = data.title || expState.selectedSessionTitle;
        renderSessionHeader(); renderLeftTree(); renderStage();
      }
    } catch (err) { console.warn("Error loading session bucket:", err); }
  }

  async function viewFile(relPath, fileName, backTarget, isQueue, qTid) {
    if (!relPath) return;
    expState.selectedFilePath = relPath; expState.selectedFileName = fileName || relPath.split("/").pop();
    expState.stageMode = "doc"; expState.docViewMode = "html";
    if (backTarget) expState.docBackTarget = backTarget;
    if (isQueue) { expState.queueDocFile = relPath; expState.queueDocTid = qTid; }
    renderSessionHeader(); renderStage();
    const viewer = document.getElementById("workspaceContentViewer");
    if (!viewer) return;
    viewer.innerHTML = `<div class="viewer-loading mono">Loading ${escapeHtmlSafe(expState.selectedFileName)}...</div>`;
    if (typeof state !== "undefined" && state.demoMode && window.DEMO_DOC_FILES?.[relPath]) {
      const docMd = window.DEMO_DOC_FILES[relPath];
      expState.selectedFileSize = docMd.length; expState.rawFileContent = docMd; expState.renderedHtmlContent = docMd;
      renderDocViewerContent(viewer); renderSessionHeader(); return;
    }
    try {
      const qPath = encodeURIComponent(relPath.includes("staged_handoffs/") ? relPath.slice(relPath.indexOf("staged_handoffs/")) : relPath);
      const cid = isQueue ? (expState.selectedSessionId || expState.treeData?.selected_session || "00000000-0000-0000-0000-000000000000") : expState.selectedSessionId;
      const resp = await fetch(getBaseApiPath() + `/web/api/sessions/${encodeURIComponent(cid)}/file?path=${qPath}`, { headers: getApiHeaders() });
      const data = await resp.json();
      if (data.ok && viewer) {
        expState.selectedFileSize = data.size || 0; expState.rawFileContent = data.raw_content || data.content;
        expState.renderedHtmlContent = data.content; renderDocViewerContent(viewer); renderSessionHeader();
      } else if (viewer) viewer.innerHTML = `<div class="viewer-error mono">Failed: ${escapeHtmlSafe(data.error || "File error")}</div>`;
    } catch (err) { if (viewer) viewer.innerHTML = `<div class="viewer-error mono">Error: ${escapeHtmlSafe(String(err))}</div>`; }
  }

  function renderDocViewerContent(viewer) {
    if (!viewer) return;
    if (expState.docViewMode === "raw") viewer.innerHTML = `<pre class="raw-pre mono">${escapeHtmlSafe(expState.rawFileContent)}</pre>`;
    else if (MarkdownRenderer?.createMarkdownViewer) MarkdownRenderer.createMarkdownViewer(viewer, expState.renderedHtmlContent, { fileName: expState.selectedFileName });
    else viewer.innerHTML = `<div class="editorial-html-body">${expState.renderedHtmlContent}</div>`;
  }

  function renderLeftTree() {
    const treeEl = document.getElementById("workspaceTreeRoot"), railEl = document.getElementById("slimRailProjects");
    if (!treeEl || !expState.treeData) return;
    const data = expState.treeData, q = (expState.searchQuery || "").toLowerCase().trim();
    const qNode = data.queue || {}, tickets = qNode.tickets || [];
    const activeCount = tickets.filter((t) => ["STAGED", "IN_WORK"].includes(String(t.status || "").toUpperCase())).length;
    const qBadge = activeCount > 0 ? `<span class="tree-badge mono staged">${activeCount}</span>` : "";
    let html = `<div class="tree-node tree-queue-node ${expState.stageMode === "queue" ? "active" : ""}" id="treeQueueNode" title="Visual Handoffs Queue"><span class="tree-icon">◈</span><span class="tree-label">Visual Handoffs Queue</span>${qBadge}</div>`, railHtml = "";
    document.getElementById("slimQueueBadge") && (document.getElementById("slimQueueBadge").textContent = activeCount > 0 ? String(activeCount) : "");
    const wsBadge = document.getElementById("navWorkspaceBadge");
    if (wsBadge) {
      wsBadge.textContent = String(activeCount);
      wsBadge.classList.toggle("hidden", activeCount === 0);
      wsBadge.style.display = activeCount === 0 ? "none" : "";
    }

    (data.projects || []).forEach((proj) => {
      const pName = proj.project_name || "Project", sessList = proj.sessions || [];
      const initials = pName.split(/[\s_-]+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase() || "PR";
      const s0 = sessList[0];
      railHtml += `<button type="button" class="slim-project-pill mono" data-cid="${s0 ? s0.conversation_id : ""}" data-pname="${escapeHtmlSafe(pName)}" data-stitle="${s0 ? escapeHtmlSafe(s0.title) : ""}" title="${escapeHtmlSafe(pName)}">${initials}</button>`;
      if (q && !pName.toLowerCase().includes(q) && !sessList.some((s) => (s.title || "").toLowerCase().includes(q))) return;
      const stg = Number(proj.staged_count || 0), pBadge = stg > 0 ? `<span class="tree-badge mono staged">${stg}</span>` : "";
      const isExpanded = expState.expandedProjects.has(pName), visibleSess = isExpanded ? sessList : sessList.slice(0, 4);
      const olderCount = Math.max(0, sessList.length - visibleSess.length);

      html += `<details class="tree-project-details" open><summary class="tree-project-hdr"><span class="tree-label"><strong>${escapeHtmlSafe(pName)}</strong></span>${pBadge}</summary><div class="tree-session-list">`;
      visibleSess.forEach((s) => {
        const sTitle = s.title || "Untitled Session";
        if (q && !sTitle.toLowerCase().includes(q) && !pName.toLowerCase().includes(q)) return;
        const cid = s.conversation_id, isActive = cid === expState.selectedSessionId && expState.stageMode !== "queue";
        const dotCls = (s.is_running || s.status === "RUNNING") ? "running" : (s.is_pinned ? "pinned" : "idle");
        html += `<div class="tree-session-item ${isActive ? "active" : ""}" data-cid="${cid}" data-pname="${escapeHtmlSafe(pName)}" data-stitle="${escapeHtmlSafe(sTitle)}"><span class="status-dot-6px ${dotCls}"></span><span class="tree-session-title">${escapeHtmlSafe(sTitle)}</span></div>`;
        if (isActive && expState.selectedBucket) {
          const uploads = expState.selectedBucket.uploads || [], artifacts = expState.selectedBucket.artifacts || [], visuals = expState.selectedBucket.visual_artifacts || [];
          html += `<div class="tree-session-children">
            <details class="tree-sub-details" open><summary class="tree-sub-hdr mono"><span>Uploads (${uploads.length})</span></summary><div class="tree-sub-list">${uploads.map((ub) => `<div class="tree-sub-leaf tree-upload-leaf mono ${expState.stageMode === "batch" && expState.selectedBatchFolder === ub.folder_name ? "active" : ""}" data-folder="${escapeHtmlSafe(ub.folder_name)}"><span class="leaf-icon">📂</span><span class="leaf-text">${escapeHtmlSafe(formatUploadBatchLabel(ub))}</span></div>`).join("") || '<div class="tree-sub-leaf empty mono">No uploads</div>'}</div></details>
            <details class="tree-sub-details" open><summary class="tree-sub-hdr mono"><span>Artifacts (${artifacts.length + (visuals.length ? 1 : 0)})</span></summary><div class="tree-sub-list">
              ${visuals.length ? `<div class="tree-sub-leaf tree-visuals-leaf mono"><span class="leaf-icon">🖼</span><span class="leaf-text">Visual Captures (${visuals.length})</span></div>` : ""}
              ${artifacts.map((art) => `<div class="tree-sub-leaf tree-art-leaf mono ${expState.stageMode === "doc" && art.rel_path === expState.selectedFilePath ? "active" : ""}" data-path="${escapeHtmlSafe(art.rel_path)}" data-name="${escapeHtmlSafe(art.name)}"><span class="leaf-icon">${art.type === "handoff" || art.name.includes("handoff") ? "◈" : "📄"}</span><span class="leaf-text">${escapeHtmlSafe(art.name)}</span></div>`).join("") || '<div class="tree-sub-leaf empty mono">No artifacts</div>'}
            </div></details></div>`;
        }
      });
      if (olderCount > 0 && !isExpanded) html += `<button type="button" class="tree-toggle-older-btn mono" data-pname="${escapeHtmlSafe(pName)}">▸ +${olderCount} older sessions</button>`;
      else if (isExpanded && sessList.length > 4) html += `<button type="button" class="tree-toggle-older-btn mono" data-pname="${escapeHtmlSafe(pName)}">▾ Hide older sessions</button>`;
      html += `</div></details>`;
    });

    treeEl.innerHTML = html;
    if (railEl) railEl.innerHTML = railHtml;
    treeEl.querySelector("#treeQueueNode")?.addEventListener("click", () => { expState.stageMode = "queue"; closeMobileDrawer(); renderSessionHeader(); renderLeftTree(); renderStage(); });
    treeEl.querySelectorAll(".tree-session-item").forEach((it) => it.addEventListener("click", () => { closeMobileDrawer(); selectSession(it.getAttribute("data-cid"), it.getAttribute("data-pname"), it.getAttribute("data-stitle")); }));
    treeEl.querySelectorAll(".tree-upload-leaf").forEach((l) => l.addEventListener("click", (e) => { e.stopPropagation(); closeMobileDrawer(); expState.selectedBatchFolder = l.getAttribute("data-folder"); expState.stageMode = "batch"; renderSessionHeader(); renderLeftTree(); renderStage(); }));
    treeEl.querySelectorAll(".tree-visuals-leaf").forEach((l) => l.addEventListener("click", (e) => { e.stopPropagation(); closeMobileDrawer(); expState.stageMode = "overview"; renderSessionHeader(); renderStage(); document.getElementById("secVisualArtifacts")?.scrollIntoView({ behavior: "smooth" }); }));
    treeEl.querySelectorAll(".tree-art-leaf").forEach((l) => l.addEventListener("click", (e) => { e.stopPropagation(); closeMobileDrawer(); viewFile(l.getAttribute("data-path"), l.getAttribute("data-name"), "overview"); renderLeftTree(); }));
    treeEl.querySelectorAll(".tree-toggle-older-btn").forEach((b) => b.addEventListener("click", (e) => { e.stopPropagation(); const pn = b.getAttribute("data-pname"); if (expState.expandedProjects.has(pn)) expState.expandedProjects.delete(pn); else expState.expandedProjects.add(pn); renderLeftTree(); }));
    railEl?.querySelectorAll(".slim-project-pill").forEach((p) => p.addEventListener("click", () => { const cid = p.getAttribute("data-cid"); if (cid) selectSession(cid, p.getAttribute("data-pname"), p.getAttribute("data-stitle")); }));
  }

  function renderSessionHeader() {
    const hdrEl = document.getElementById("workspaceSessionHeader");
    if (!hdrEl) return;
    if (expState.stageMode === "queue") {
      const activeCount = (expState.treeData?.queue?.tickets || []).filter((t) => ["STAGED", "IN_WORK"].includes(String(t.status || "").toUpperCase())).length;
      hdrEl.innerHTML = `<div class="ws-header-left"><span class="breadcrumb-proj">Workspace</span><span class="breadcrumb-sep">/</span><strong class="breadcrumb-session">Visual Handoffs Queue</strong><span class="card-tag mono cyan">${activeCount} active</span></div>`;
      return;
    }
    const cid = expState.selectedSessionId;
    if (!cid) return (hdrEl.innerHTML = `<span class="workspace-empty-hdr mono">Select a session from the left tree</span>`);
    const pName = expState.selectedProjectName || "Project", sTitle = expState.selectedSessionTitle || "Untitled Session";
    const rollover = expState.selectedBucket?.rollover || {}, posture = rollover.posture || "FRESH";
    const postureCls = posture === "HARD_ROLLOVER" ? "red" : (posture.includes("HOLD") || posture.includes("CLOSEOUT") ? "amber" : (posture === "RETIRED" ? "dim" : "cyan"));
    hdrEl.innerHTML = `<div class="ws-header-left"><span class="breadcrumb-proj">${escapeHtmlSafe(pName)}</span><span class="breadcrumb-sep">/</span><strong class="breadcrumb-session">${escapeHtmlSafe(sTitle)}</strong><span class="card-tag mono ${postureCls}" title="${escapeHtmlSafe(rollover.reason || posture)}">${escapeHtmlSafe(posture)}</span></div><div class="ws-header-right"><button type="button" class="btn btn-xs mono btn-copy-cid" data-copy="${cid}">Copy ID</button></div>`;
    hdrEl.querySelector(".btn-copy-cid")?.addEventListener("click", (e) => { navigator.clipboard?.writeText(cid); e.currentTarget.textContent = "Copied!"; setTimeout(() => { e.currentTarget.textContent = "Copy ID"; }, 1000); });
  }

  function renderStage() {
    const stageEl = document.getElementById("workspaceStage");
    if (!stageEl) return;
    if (expState.stageMode === "queue") return renderQueueStage(stageEl);
    if (!expState.selectedSessionId) return (stageEl.innerHTML = `<div class="stage-placeholder mono">Select a session or handoff ticket from the left tree</div>`);
    if (expState.stageMode === "doc") return renderDocStage(stageEl);
    if (expState.stageMode === "batch") return renderBatchStage(stageEl);
    return renderOverviewStage(stageEl);
  }

  function getInlineUploadHtml(tagVal) {
    return `<div class="inline-upload-strip mono"><div class="upload-strip-left"><span class="upload-strip-icon">📁</span><span>Drop files, paste (Ctrl+V), or</span><button type="button" class="btn btn-xs mono upload-browse-btn">Browse...</button><input type="file" class="hidden-file-input" multiple style="display:none;" /></div><div class="upload-strip-right"><input type="text" class="upload-tag-input mono" placeholder="Batch label (opt)..." value="${escapeHtmlSafe(tagVal || "")}" /><span class="upload-status-lbl"></span></div></div>`;
  }

  function bindInlineUploadStrip(container) {
    const strip = container.querySelector(".inline-upload-strip");
    if (!strip) return;
    const fi = strip.querySelector(".hidden-file-input"), bBtn = strip.querySelector(".upload-browse-btn"), tagIn = strip.querySelector(".upload-tag-input"), stLbl = strip.querySelector(".upload-status-lbl");
    if (bBtn && fi) bBtn.onclick = () => fi.click();
    if (fi) fi.onchange = () => { if (fi.files?.length) handleFilesUpload(fi.files, tagIn.value, stLbl); };
    ["dragenter", "dragover"].forEach((e) => strip.addEventListener(e, (ev) => { ev.preventDefault(); ev.stopPropagation(); strip.classList.add("drag-over"); }));
    ["dragleave", "drop"].forEach((e) => strip.addEventListener(e, (ev) => { ev.preventDefault(); ev.stopPropagation(); strip.classList.remove("drag-over"); }));
    strip.addEventListener("drop", (e) => { e.preventDefault(); if (e.dataTransfer?.files?.length) handleFilesUpload(e.dataTransfer.files, tagIn.value, stLbl); });
  }

  function renderVisualsGridHtml(items, hdrText, hdrId) {
    if (!items || !items.length) return "";
    const idAttr = hdrId ? ` id="${escapeHtmlSafe(hdrId)}"` : "", dragMode = GallerySelect.getDragSelectMode();
    let out = `<div class="stage-sec-hdr mono"${idAttr} style="display:flex;justify-content:space-between;align-items:center;"><span>${escapeHtmlSafe(hdrText)} (${items.length})</span><button type="button" class="btn btn-xs mono btn-toggle-drag-select ${dragMode ? "active" : ""}" title="Toggle Rubber-Band Drag-Select">⬚ Drag-Select</button></div>`;
    out += GallerySelect.renderBulkActionBarHtml(expState.selectedSessionId, items.length);
    out += `<div class="visuals-strip-grid">${items.map((v, idx) => {
      const isSel = GallerySelect.isSelected(v.rel_path);
      return `<div class="visual-thumb-card mono ${isSel ? "selected" : ""}" data-idx="${idx}" data-url="${escapeHtmlSafe(v.signed_url)}" data-name="${escapeHtmlSafe(v.name)}" data-rel="${escapeHtmlSafe(v.rel_path)}"><label class="gallery-item-cb-wrap" onclick="event.stopPropagation();"><input type="checkbox" class="gallery-item-cb" data-idx="${idx}" ${isSel ? "checked" : ""} /><span class="cb-custom"></span></label><img src="${escapeHtmlSafe(v.signed_url)}" alt="${escapeHtmlSafe(v.name)}" class="visual-thumb-img" loading="lazy" style="cursor:zoom-in;"/><span class="thumb-lbl" title="${escapeHtmlSafe(v.name)}">${escapeHtmlSafe(v.name)}</span><button type="button" class="btn mono btn-copy-link" style="font-size:10px;padding:2px 6px;margin-top:4px;">Copy Link</button></div>`;
    }).join("")}</div>`;
    return out;
  }

  function bindVisualGridInteractions(container, items) {
    const grid = container.querySelector(".visuals-strip-grid");
    if (!grid) return;
    GallerySelect.bindRubberBandMarquee(grid, () => items, () => renderStage());
    container.querySelector(".btn-toggle-drag-select")?.addEventListener("click", () => { GallerySelect.setDragSelectMode(!GallerySelect.getDragSelectMode()); renderStage(); });
    container.querySelectorAll(".gallery-item-cb").forEach((cb) => {
      cb.addEventListener("click", (e) => {
        e.stopPropagation(); const idx = Number(cb.getAttribute("data-idx"));
        if (e.shiftKey) GallerySelect.handleShiftSelect(items, idx, cb.checked);
        else GallerySelect.toggleItem(items[idx], cb.checked, idx);
        renderStage();
      });
    });
    container.querySelectorAll(".visual-thumb-card").forEach((card) => {
      const img = card.querySelector(".visual-thumb-img"), btn = card.querySelector(".btn-copy-link");
      const url = card.getAttribute("data-url"), name = card.getAttribute("data-name");
      if (img) img.onclick = () => openLightbox(url, name);
      if (btn) btn.onclick = (e) => { e.stopPropagation(); navigator.clipboard?.writeText(toAbsoluteMediaUrl(url)); btn.textContent = "Copied!"; setTimeout(() => { btn.textContent = "Copy Link"; }, 1200); };
    });
    const bulkMap = {
      "#bulkSelectAllBtn": () => { GallerySelect.selectAll(items); renderStage(); },
      "#bulkClearBtn": () => { GallerySelect.clearSelection(); renderStage(); },
      "#bulkShareBtn": () => GallerySelect.shareToGemini(),
      "#bulkContactSheetBtn": () => GallerySelect.copyContactSheetForChat(openLightbox),
      "#bulkDownloadZipBtn": () => GallerySelect.downloadZip(expState.selectedSessionId, getApiHeaders, getBaseApiPath),
      "#bulkDownloadPngsBtn": () => GallerySelect.downloadSequentialPngs(),
    };
    Object.entries(bulkMap).forEach(([sel, fn]) => container.querySelector(sel)?.addEventListener("click", fn));
  }

  function renderOverviewStage(stageEl) {
    const b = expState.selectedBucket || {}, artifacts = b.artifacts || [], uploads = b.uploads || [], visuals = b.visual_artifacts || [];
    let html = getInlineUploadHtml("");
    if (artifacts.length > 0) {
      html += `<div class="stage-sec-hdr mono">Session Documents &amp; Handoffs (${artifacts.length})</div><div class="cards-grid">${artifacts.map((a) => `<div class="doc-card mono" data-path="${escapeHtmlSafe(a.rel_path)}" data-name="${escapeHtmlSafe(a.name)}"><div class="doc-card-title"><span class="leaf-icon">${a.type === "handoff" || a.name.includes("handoff") ? "◈" : "📄"}</span><strong>${escapeHtmlSafe(a.name)}</strong></div><div class="doc-card-meta"><span>${(Number(a.size || 0) / 1024).toFixed(1)} KB</span><span>${formatRelativeAge(a.mtime)}</span></div></div>`).join("")}</div>`;
    }
    if (uploads.length > 0) {
      html += `<div class="stage-sec-hdr mono">Date-Stamped Upload Batches (${uploads.length})</div><div class="cards-grid">${uploads.map((ub) => {
        const imgs = ub.signed_images || [];
        return `<div class="batch-card mono" data-folder="${escapeHtmlSafe(ub.folder_name)}"><div class="batch-card-top"><span class="batch-card-title">📁 ${escapeHtmlSafe(ub.folder_name)}</span><span class="card-tag mono">${ub.file_count} files</span></div>${imgs.length ? `<div class="batch-card-thumbs">${imgs.slice(0, 4).map((im) => `<img src="${escapeHtmlSafe(im.signed_url)}" class="batch-card-thumb-img" alt="${escapeHtmlSafe(im.name)}" loading="lazy"/>`).join("")}</div>` : ""}<div class="batch-files">${(ub.files || []).slice(0, 5).map((f) => `<span class="batch-file-pill">${escapeHtmlSafe(typeof f === "object" ? f.name : f)}</span>`).join(" ")}</div></div>`;
      }).join("")}</div>`;
    }
    html += renderVisualsGridHtml(visuals, "Visual Artifacts & Captures", "secVisualArtifacts");
    if (!artifacts.length && !uploads.length && !visuals.length) html += `<div class="stage-placeholder mono">Session workspace is clean. Use the upload strip above to stage artifacts.</div>`;
    stageEl.innerHTML = html;
    bindInlineUploadStrip(stageEl); bindVisualGridInteractions(stageEl, visuals);
    stageEl.querySelectorAll(".doc-card").forEach((c) => c.addEventListener("click", () => viewFile(c.getAttribute("data-path"), c.getAttribute("data-name"), "overview")));
    stageEl.querySelectorAll(".batch-card").forEach((c) => c.addEventListener("click", () => { expState.selectedBatchFolder = c.getAttribute("data-folder"); expState.stageMode = "batch"; renderSessionHeader(); renderLeftTree(); renderStage(); }));
  }

  function renderBatchStage(stageEl) {
    const uploads = expState.selectedBucket?.uploads || [], ub = uploads.find((u) => u.folder_name === expState.selectedBatchFolder) || uploads[0];
    if (!ub) {
      stageEl.innerHTML = `<button type="button" class="btn btn-xs mono stage-back-btn" id="batchBackBtn">← Session Bucket</button><div class="stage-placeholder mono">Batch not found.</div>`;
      stageEl.querySelector("#batchBackBtn")?.addEventListener("click", () => { expState.stageMode = "overview"; renderStage(); }); return;
    }
    const imgs = ub.signed_images || [];
    stageEl.innerHTML = `<div class="stage-header-bar mono"><div class="stage-hdr-left"><button type="button" class="btn btn-xs mono stage-back-btn" id="batchBackBtn">← Bucket</button><span class="stage-hdr-crumb">📁 <strong>${escapeHtmlSafe(ub.folder_name)}</strong> (${ub.file_count} files)</span></div><div class="stage-hdr-actions">${ub.app_prompt ? `<button type="button" class="btn btn-xs btn-focal btn-copy-app-prompt mono">Copy App Prompt</button>` : ""}${ub.index_rel_path ? `<button type="button" class="btn btn-xs mono btn-open-idx">Read INDEX.md</button>` : ""}</div></div>${getInlineUploadHtml(ub.folder_name.replace(/^uploads_\d{8}_\d{6}_?/, ""))}${renderVisualsGridHtml(imgs, "Batch Visual Media")}`;
    bindInlineUploadStrip(stageEl); bindVisualGridInteractions(stageEl, imgs);
    stageEl.querySelector("#batchBackBtn")?.addEventListener("click", () => { expState.stageMode = "overview"; renderSessionHeader(); renderLeftTree(); renderStage(); });
    stageEl.querySelector(".btn-copy-app-prompt")?.addEventListener("click", (e) => { navigator.clipboard?.writeText(ub.app_prompt); e.currentTarget.textContent = "Copied!"; setTimeout(() => { e.currentTarget.textContent = "Copy App Prompt"; }, 1200); });
    stageEl.querySelector(".btn-open-idx")?.addEventListener("click", () => viewFile(ub.index_rel_path, "INDEX.md", "batch"));
  }

  function renderDocStage(stageEl) {
    const backLbl = expState.docBackTarget === "queue" ? "← Queue" : (expState.docBackTarget === "batch" ? "← Batch" : "← Bucket");
    const pName = expState.selectedProjectName || "Project", fName = expState.selectedFileName || "Document";
    const sizeStr = expState.selectedFileSize ? ` (${(expState.selectedFileSize / 1024).toFixed(1)} KB)` : "";
    stageEl.innerHTML = `<div class="stage-header-bar mono"><div class="stage-hdr-left"><button type="button" class="btn btn-xs mono stage-back-btn" id="docBackBtn">${backLbl}</button><span class="stage-hdr-crumb">${escapeHtmlSafe(pName)} / <strong>${escapeHtmlSafe(fName)}</strong>${sizeStr}</span></div><div class="stage-hdr-actions"><div class="doc-view-mode-toggle mono" role="group"><button type="button" class="btn btn-xs mono ${expState.docViewMode === "html" ? "active" : ""}" id="docModeHtmlBtn">HTML</button><button type="button" class="btn btn-xs mono ${expState.docViewMode === "raw" ? "active" : ""}" id="docModeRawBtn">Raw</button></div><button type="button" class="btn btn-xs mono" id="docPrintBtn" title="Print">Print</button><button type="button" class="btn btn-xs mono ${expState.isZenMode ? "active" : ""}" id="docZenBtn" title="Toggle Zen Mode">⤢ Zen</button><button type="button" class="btn btn-xs mono" id="docCopyBtn" title="Copy Markdown">Copy</button></div></div><div class="artifacts-viewer" id="workspaceContentViewer"></div>`;
    stageEl.querySelector("#docBackBtn")?.addEventListener("click", () => { expState.stageMode = expState.docBackTarget; renderSessionHeader(); renderLeftTree(); renderStage(); });
    stageEl.querySelector("#docModeHtmlBtn")?.addEventListener("click", () => { expState.docViewMode = "html"; stageEl.querySelector("#docModeHtmlBtn")?.classList.add("active"); stageEl.querySelector("#docModeRawBtn")?.classList.remove("active"); renderDocViewerContent(document.getElementById("workspaceContentViewer")); });
    stageEl.querySelector("#docModeRawBtn")?.addEventListener("click", () => { expState.docViewMode = "raw"; stageEl.querySelector("#docModeRawBtn")?.classList.add("active"); stageEl.querySelector("#docModeHtmlBtn")?.classList.remove("active"); renderDocViewerContent(document.getElementById("workspaceContentViewer")); });
    stageEl.querySelector("#docPrintBtn")?.addEventListener("click", () => window.print());
    stageEl.querySelector("#docZenBtn")?.addEventListener("click", () => toggleZenMode());
    stageEl.querySelector("#docCopyBtn")?.addEventListener("click", (e) => { navigator.clipboard?.writeText(expState.rawFileContent); e.currentTarget.textContent = "Copied!"; setTimeout(() => { e.currentTarget.textContent = "Copy"; }, 1000); });
  }

  function renderQueueStage(stageEl) {
    const qNode = expState.treeData?.queue || {}, allTickets = qNode.tickets || [];
    const active = allTickets.filter((t) => ["STAGED", "IN_WORK"].includes(String(t.status || "").toUpperCase()));
    const visible = expState.showCompletedQueue ? allTickets : active, completedCount = allTickets.length - active.length;
    stageEl.innerHTML = `<div class="queue-board-hdr mono"><div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;"><div><div class="q-title mono">◈ Cross-Project Visual Handoffs Queue</div><div class="q-subtitle mono">${active.length} active (${allTickets.length} total across all repos)</div></div>${completedCount > 0 ? `<button type="button" class="btn btn-xs mono" id="toggleQueueHistoryBtn">${expState.showCompletedQueue ? "▾ Hide Completed History" : `+ Show Completed History (${completedCount})`}</button>` : ""}</div></div><div class="queue-tickets-grid">${visible.map((t) => {
      const rawTid = String(t.handoff_id || t.ticket_id || "ticket");
      const tid = escapeHtmlSafe(rawTid), st = String(t.status || "STAGED").toUpperCase();
      const stCls = st === "STAGED" ? "cyan" : (st === "IN_WORK" ? "amber" : (st === "COMPLETED" ? "green" : "dim"));
      const rawRepo = String(t.repo_slug || "");
      const showRepo = rawRepo && !rawTid.startsWith(rawRepo);
      const repoHtml = showRepo ? `<span class="q-repo mono">${escapeHtmlSafe(rawRepo)}</span>` : "";
      return `<div class="queue-ticket-card mono" data-tid="${tid}"><div class="q-card-top"><span class="q-tid mono"><strong>${tid}</strong></span>${repoHtml}<span class="card-tag mono ${stCls}">${st}</span></div><div class="q-card-title">${escapeHtmlSafe(t.title || "Gemini Research Handoff")}</div><div class="q-card-meta">${escapeHtmlSafe(t.relative_age || t.timestamp || "recent")}</div><div class="q-card-actions"><button type="button" class="btn btn-xs btn-view-ticket" data-file="${escapeHtmlSafe(t.handoff_file || "")}" data-tid="${tid}">Read Spec</button><button type="button" class="btn btn-xs btn-copy-claim" data-cmd="praxis claim ${tid}">Copy Claim</button></div></div>`;
    }).join("") || '<div class="hier-empty mono">No handoff tickets currently staged in queue.</div>'}</div>`;
    stageEl.querySelector("#toggleQueueHistoryBtn")?.addEventListener("click", () => { expState.showCompletedQueue = !expState.showCompletedQueue; renderQueueStage(stageEl); });
    stageEl.querySelectorAll(".btn-view-ticket").forEach((b) => b.addEventListener("click", () => viewFile(b.getAttribute("data-file") || "", b.getAttribute("data-tid") || "ticket.md", "queue", true, b.getAttribute("data-tid") || "")));
    stageEl.querySelectorAll(".btn-copy-claim").forEach((b) => b.addEventListener("click", (e) => { const cmd = e.currentTarget.getAttribute("data-cmd"); navigator.clipboard?.writeText(cmd); e.currentTarget.textContent = "Copied!"; setTimeout(() => { e.currentTarget.textContent = "Copy Claim"; }, 1200); }));
  }

  async function handleFilesUpload(fileList, batchLabel, statusEl) {
    if (!expState.selectedSessionId) return alert("Please select a session first before uploading files.");
    const fd = new FormData();
    for (let i = 0; i < fileList.length; i++) fd.append("files", fileList[i]);
    const label = (batchLabel || "").trim();
    if (label) fd.append("label", label);
    if (statusEl) statusEl.textContent = `Uploading ${fileList.length} files...`;
    try {
      const q = label ? `?label=${encodeURIComponent(label)}` : "";
      const resp = await fetch(getBaseApiPath() + `/web/api/sessions/${encodeURIComponent(expState.selectedSessionId)}/upload${q}`, { method: "POST", headers: getApiHeaders(), body: fd });
      const data = await resp.json();
      if (data.ok) {
        if (statusEl) statusEl.textContent = `Uploaded ${data.saved_files ? data.saved_files.length : fileList.length} files!`;
        if (data.batch_folder) expState.selectedBatchFolder = data.batch_folder;
        await selectSession(expState.selectedSessionId); loadWorkspaceTree();
      } else if (statusEl) statusEl.textContent = `Upload error: ${data.error || "Unknown"}`;
    } catch (err) { if (statusEl) statusEl.textContent = `Upload error: ${err.message}`; }
  }

  function toggleSidebar(forceState) {
    const pane = document.getElementById("workspaceTreePane");
    if (!pane) return;
    if (window.innerWidth < 780) { toggleMobileDrawer(); return; }
    expState.isSidebarCollapsed = typeof forceState === "boolean" ? forceState : !expState.isSidebarCollapsed;
    pane.classList.toggle("slim", expState.isSidebarCollapsed);
    const rail = document.getElementById("workspaceSlimRail"), full = document.getElementById("workspaceFullTree");
    if (rail && full) { rail.classList.toggle("hidden", !expState.isSidebarCollapsed); full.classList.toggle("hidden", expState.isSidebarCollapsed); }
    localStorage.setItem("nexus_ws_sidebar_collapsed", expState.isSidebarCollapsed ? "true" : "false");
  }

  function toggleZenMode() {
    const pane = document.getElementById("workspaceTreePane");
    expState.isZenMode = !expState.isZenMode;
    if (pane) pane.classList.toggle("zen", expState.isZenMode);
    document.getElementById("docZenBtn")?.classList.toggle("active", expState.isZenMode);
  }

  function toggleMobileDrawer() {
    const pane = document.getElementById("workspaceTreePane");
    if (!pane) return;
    const isOpen = pane.classList.toggle("drawer-open");
    let backdrop = document.getElementById("wsDrawerBackdrop");
    if (isOpen) {
      if (!backdrop) {
        backdrop = document.createElement("div"); backdrop.id = "wsDrawerBackdrop"; backdrop.className = "ws-drawer-backdrop";
        backdrop.onclick = closeMobileDrawer; document.body.appendChild(backdrop);
      }
    } else closeMobileDrawer();
  }

  function closeMobileDrawer() {
    document.getElementById("workspaceTreePane")?.classList.remove("drawer-open");
    document.getElementById("wsDrawerBackdrop")?.remove();
  }

  function initExplorerEvents() {
    document.getElementById("workspaceTreeSearch")?.addEventListener("input", (e) => { expState.searchQuery = e.target.value; renderLeftTree(); });
    document.getElementById("sidebarToggleBtn")?.addEventListener("click", () => toggleSidebar());
    document.getElementById("treeCollapseBtn")?.addEventListener("click", () => toggleSidebar(true));
    document.getElementById("slimRailExpandBtn")?.addEventListener("click", () => toggleSidebar(false));
    document.getElementById("slimRailQueueBtn")?.addEventListener("click", () => { expState.stageMode = "queue"; renderSessionHeader(); renderLeftTree(); renderStage(); });
    window.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b") {
        const wsMain = document.getElementById("workspaceMain");
        if (wsMain && !wsMain.classList.contains("hidden")) { e.preventDefault(); toggleSidebar(); }
      }
    });
    window.addEventListener("paste", (e) => {
      const wsMain = document.getElementById("workspaceMain");
      if (!wsMain || wsMain.classList.contains("hidden")) return;
      const items = (e.clipboardData || e.originalEvent?.clipboardData)?.items || [], fileList = [];
      for (let i = 0; i < items.length; i++) { if (items[i].kind === "file") fileList.push(items[i].getAsFile()); }
      if (fileList.length > 0) handleFilesUpload(fileList, document.querySelector(".upload-tag-input")?.value || "", document.querySelector(".upload-status-lbl"));
    });
    if (localStorage.getItem("nexus_ws_sidebar_collapsed") === "true" && window.innerWidth >= 780) toggleSidebar(true);
  }

  function initWorkspace() { initExplorerEvents(); loadWorkspaceTree(); }
  return { initWorkspace, loadWorkspaceTree, selectSession, viewFile, openLightbox, toggleSidebar, toggleZenMode };
});
