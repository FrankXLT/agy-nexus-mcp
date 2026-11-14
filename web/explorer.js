// AGY-NEXUS Overwatch — Hierarchical Workspace Explorer & Dual-Area Right Pane (v3.0.0)

(function (root, factory) {
  if (typeof define === "function" && define.amd) {
    define(["./markdown_renderer"], factory);
  } else if (typeof module === "object" && module.exports) {
    module.exports = factory(require("./markdown_renderer"));
  } else {
    root.WorkspaceExplorer = factory(root.MarkdownRenderer);
  }
})(typeof self !== "undefined" ? self : this, function (MarkdownRenderer) {
  "use strict";

  const expState = {
    treeData: null,
    selectedSessionId: "",
    selectedProjectName: "",
    selectedSessionTitle: "",
    selectedBucket: null,
    selectedFilePath: "",
    selectedFileName: "",
    activeTab: "artifacts", // "uploads" | "artifacts"
    searchQuery: "",
  };

  function getApiHeaders() {
    const pass = (typeof state !== "undefined" && state.passphrase) || localStorage.getItem("nexus_passphrase") || "";
    return {
      "X-Nexus-Passphrase": pass,
      "X-Client-Product": "Workspace Explorer",
    };
  }

  function getBaseApiPath() {
    return (window.location.pathname || "/web").replace(/\/web\/?$/, "");
  }

  async function loadWorkspaceTree() {
    try {
      const resp = await fetch(getBaseApiPath() + "/web/api/workspace/tree", {
        headers: getApiHeaders(),
      });
      if (resp.status === 401) {
        if (typeof showAuthModal === "function") showAuthModal();
        return;
      }
      const data = await resp.json();
      if (data.ok) {
        expState.treeData = data;
        renderLeftTree();
        // Auto-select session if none selected
        if (!expState.selectedSessionId) {
          const selId = data.selected_session;
          if (selId) {
            selectSession(selId);
          } else if (data.projects && data.projects[0] && data.projects[0].sessions && data.projects[0].sessions[0]) {
            const firstS = data.projects[0].sessions[0];
            selectSession(firstS.conversation_id, data.projects[0].project_name, firstS.title);
          }
        }
      }
    } catch (err) {
      console.warn("Error loading workspace tree:", err);
    }
  }

  async function selectSession(convId, projectName, sessionTitle) {
    if (!convId) return;
    expState.selectedSessionId = convId;
    if (projectName) expState.selectedProjectName = projectName;
    if (sessionTitle) expState.selectedSessionTitle = sessionTitle;

    renderSessionHeader();
    renderLeftTree(); // update active class in tree

    try {
      const resp = await fetch(getBaseApiPath() + `/web/api/sessions/${convId}/bucket`, {
        headers: getApiHeaders(),
      });
      const data = await resp.json();
      if (data.ok) {
        expState.selectedBucket = data;
        expState.selectedSessionTitle = data.title || expState.selectedSessionTitle;
        renderSessionHeader();
        renderDualPane();

        // Auto-select first artifact if available
        if (data.artifacts && data.artifacts.length && !expState.selectedFilePath) {
          const firstArt = data.artifacts[0];
          viewFile(firstArt.rel_path, firstArt.name);
        }
      }
    } catch (err) {
      console.warn("Error loading session bucket:", err);
    }
  }

  async function viewFile(relPath, fileName) {
    if (!expState.selectedSessionId || !relPath) return;
    expState.selectedFilePath = relPath;
    expState.selectedFileName = fileName || relPath.split("/").pop();

    const viewerContainer = document.getElementById("workspaceContentViewer");
    if (viewerContainer) {
      viewerContainer.innerHTML = `<div class="viewer-loading mono">Loading ${escapeHtmlSafe(expState.selectedFileName)}...</div>`;
    }

    try {
      const qPath = encodeURIComponent(relPath);
      const resp = await fetch(getBaseApiPath() + `/web/api/sessions/${expState.selectedSessionId}/file?path=${qPath}`, {
        headers: getApiHeaders(),
      });
      const data = await resp.json();
      if (data.ok && viewerContainer) {
        if (MarkdownRenderer && typeof MarkdownRenderer.createMarkdownViewer === "function") {
          MarkdownRenderer.createMarkdownViewer(viewerContainer, data.content, {
            fileName: expState.selectedFileName,
          });
        } else {
          viewerContainer.innerHTML = `<pre class="raw-pre mono">${escapeHtmlSafe(data.content)}</pre>`;
        }
      } else if (viewerContainer) {
        viewerContainer.innerHTML = `<div class="viewer-error mono">Failed to load file: ${escapeHtmlSafe(data.error || "Unknown error")}</div>`;
      }
    } catch (err) {
      if (viewerContainer) {
        viewerContainer.innerHTML = `<div class="viewer-error mono">Error reading file: ${escapeHtmlSafe(String(err))}</div>`;
      }
    }
  }

  function renderLeftTree() {
    const treeEl = document.getElementById("workspaceTreeRoot");
    if (!treeEl || !expState.treeData) return;

    const data = expState.treeData;
    const q = (expState.searchQuery || "").toLowerCase().trim();
    let html = "";

    // Node 1: Visual Handoffs Queue
    const qNode = data.queue || {};
    const qTotal = Number(qNode.total || 0);
    const qBadge = qTotal > 0 ? `<span class="tree-badge mono">${qTotal}</span>` : "";
    html += `
      <div class="tree-node tree-queue-node" id="treeQueueNode" title="Visual Handoffs Queue">
        <span class="tree-icon">◈</span>
        <span class="tree-label">Visual Handoffs Queue</span>
        ${qBadge}
      </div>
    `;

    // Projects -> Sessions
    (data.projects || []).forEach((proj) => {
      const pName = proj.project_name || "Project";
      const sessList = proj.sessions || [];
      const matchProj = !q || pName.toLowerCase().includes(q) || sessList.some((s) => (s.title || "").toLowerCase().includes(q));
      if (!matchProj) return;

      const stagedCount = Number(proj.staged_count || 0);
      const projBadge = stagedCount > 0 ? `<span class="tree-badge mono staged">${stagedCount}</span>` : "";

      html += `<details class="tree-project-details" open>`;
      html += `
        <summary class="tree-project-hdr">
          <span class="tree-caret mono"></span>
          <span class="tree-label"><strong>${escapeHtmlSafe(pName)}</strong></span>
          ${projBadge}
        </summary>
        <div class="tree-session-list">
      `;

      sessList.forEach((s) => {
        const sTitle = s.title || "Untitled Session";
        if (q && !sTitle.toLowerCase().includes(q) && !pName.toLowerCase().includes(q)) return;
        const cid = s.conversation_id;
        const isActive = cid === expState.selectedSessionId;
        const isRun = s.status === "RUNNING";
        const dotCls = isRun ? "running" : (s.is_pinned ? "pinned" : "idle");

        html += `
          <div class="tree-session-item ${isActive ? "active" : ""}" data-cid="${cid}" data-pname="${escapeHtmlSafe(pName)}" data-stitle="${escapeHtmlSafe(sTitle)}">
            <span class="status-dot-6px ${dotCls}"></span>
            <span class="tree-session-title">${escapeHtmlSafe(sTitle)}</span>
          </div>
        `;
      });

      html += `</div></details>`;
    });

    treeEl.innerHTML = html;

    // Attach tree event handlers
    treeEl.querySelectorAll(".tree-session-item").forEach((item) => {
      item.addEventListener("click", () => {
        const cid = item.getAttribute("data-cid");
        const pName = item.getAttribute("data-pname");
        const sTitle = item.getAttribute("data-stitle");
        selectSession(cid, pName, sTitle);
      });
    });
  }

  function renderSessionHeader() {
    const hdrEl = document.getElementById("workspaceSessionHeader");
    if (!hdrEl) return;

    const cid = expState.selectedSessionId;
    if (!cid) {
      hdrEl.innerHTML = `<span class="workspace-empty-hdr mono">Select a session from the left tree</span>`;
      return;
    }

    const pName = expState.selectedProjectName || "Project";
    const sTitle = expState.selectedSessionTitle || "Untitled Session";
    const bucket = expState.selectedBucket || {};
    const rollover = bucket.rollover || {};
    const posture = rollover.posture || "FRESH";
    const postureCls = posture === "HARD_ROLLOVER" ? "red" : (posture.includes("HOLD") || posture.includes("CLOSEOUT") ? "amber" : "cyan");

    hdrEl.innerHTML = `
      <div class="ws-header-left">
        <span class="breadcrumb-proj">${escapeHtmlSafe(pName)}</span>
        <span class="breadcrumb-sep">/</span>
        <strong class="breadcrumb-session">${escapeHtmlSafe(sTitle)}</strong>
        <span class="card-tag mono ${postureCls}" title="Continuity posture: ${escapeHtmlSafe(rollover.reason || posture)}">${escapeHtmlSafe(posture)}</span>
      </div>
      <div class="ws-header-right">
        <button type="button" class="btn-copy-cid btn mono" data-copy="${cid}" title="Copy Session ID">Copy ID</button>
      </div>
    `;

    const copyBtn = hdrEl.querySelector(".btn-copy-cid");
    if (copyBtn) {
      copyBtn.addEventListener("click", () => {
        if (typeof copyTextWithFeedback === "function") {
          copyTextWithFeedback(copyBtn, cid, "Copy ID", 1000);
        }
      });
    }
  }

  function renderDualPane() {
    const bucket = expState.selectedBucket;
    if (!bucket) return;

    // Render Artifacts List in right sidebar / sublist
    const artListEl = document.getElementById("workspaceArtifactsList");
    if (artListEl) {
      const artifacts = bucket.artifacts || [];
      if (!artifacts.length) {
        artListEl.innerHTML = `<div class="hier-empty mono">No artifacts staged.</div>`;
      } else {
        artListEl.innerHTML = artifacts.map((art) => {
          const isSel = art.rel_path === expState.selectedFilePath;
          const isHandoff = art.is_handoff || art.name.endsWith(".md");
          return `
            <div class="artifact-nav-item ${isSel ? "active" : ""} mono" data-path="${escapeHtmlSafe(art.rel_path)}" data-name="${escapeHtmlSafe(art.name)}">
              <span class="art-icon">${isHandoff ? "◈" : "📄"}</span>
              <span class="art-name">${escapeHtmlSafe(art.name)}</span>
              <span class="art-size">${(Number(art.size || 0) / 1024).toFixed(1)}K</span>
            </div>
          `;
        }).join("");

        artListEl.querySelectorAll(".artifact-nav-item").forEach((it) => {
          it.addEventListener("click", () => {
            const p = it.getAttribute("data-path");
            const n = it.getAttribute("data-name");
            viewFile(p, n);
            renderDualPane();
          });
        });
      }
    }

    // Render Uploads area thumbnails and batches
    const upGridEl = document.getElementById("workspaceUploadsGrid");
    if (upGridEl) {
      const uploads = bucket.uploads || [];
      const visuals = bucket.visual_artifacts || [];

      let upHtml = "";
      if (visuals.length > 0) {
        upHtml += `<div class="visuals-strip-hdr mono">Visual Artifacts &amp; Thumbnails (7-Day TTL)</div><div class="visuals-strip-grid">`;
        visuals.forEach((v) => {
          upHtml += `
            <div class="visual-thumb-card">
              <a href="${escapeHtmlSafe(v.signed_url)}" target="_blank" rel="noopener noreferrer">
                <img src="${escapeHtmlSafe(v.signed_url)}" alt="${escapeHtmlSafe(v.name)}" class="visual-thumb-img" loading="lazy"/>
              </a>
              <span class="thumb-lbl mono">${escapeHtmlSafe(v.name)}</span>
            </div>
          `;
        });
        upHtml += `</div>`;
      }

      if (uploads.length > 0) {
        upHtml += `<div class="uploads-batch-hdr mono">Uploaded Scratch Batches</div>`;
        uploads.forEach((ub) => {
          upHtml += `
            <div class="upload-batch-card mono">
              <div class="batch-title">📁 ${escapeHtmlSafe(ub.folder_name)} (${ub.file_count} files)</div>
              <div class="batch-files">${(ub.files || []).map((f) => `<span class="batch-file-pill">${escapeHtmlSafe(f)}</span>`).join(" ")}</div>
            </div>
          `;
        });
      }

      upGridEl.innerHTML = upHtml || `<div class="hier-empty mono">No scratch uploads in this session yet.</div>`;
    }
  }

  function initExplorerEvents() {
    const searchInput = document.getElementById("workspaceTreeSearch");
    if (searchInput) {
      searchInput.addEventListener("input", (e) => {
        expState.searchQuery = e.target.value;
        renderLeftTree();
      });
    }

    // Drag and Drop Upload Zone
    const dropZone = document.getElementById("workspaceUploadDropzone");
    if (dropZone) {
      ["dragenter", "dragover"].forEach((evt) => {
        dropZone.addEventListener(evt, (e) => {
          e.preventDefault(); e.stopPropagation();
          dropZone.classList.add("drag-over");
        });
      });
      ["dragleave", "drop"].forEach((evt) => {
        dropZone.addEventListener(evt, (e) => {
          e.preventDefault(); e.stopPropagation();
          dropZone.classList.remove("drag-over");
        });
      });
      dropZone.addEventListener("drop", (e) => {
        const files = e.dataTransfer && e.dataTransfer.files;
        if (files && files.length) {
          handleFilesUpload(files);
        }
      });
    }

    // Ctrl+V Paste Handler
    window.addEventListener("paste", (e) => {
      // Only handle if in workspace view
      const wsMain = document.getElementById("workspaceMain");
      if (!wsMain || wsMain.classList.contains("hidden")) return;

      const items = (e.clipboardData || e.originalEvent.clipboardData).items;
      const fileList = [];
      for (let i = 0; i < items.length; i++) {
        if (items[i].kind === "file") {
          fileList.push(items[i].getAsFile());
        }
      }
      if (fileList.length > 0) {
        handleFilesUpload(fileList);
      }
    });
  }

  async function handleFilesUpload(fileList) {
    if (!expState.selectedSessionId) {
      alert("Please select a session first before uploading files.");
      return;
    }

    const tagInput = document.getElementById("uploadBatchTagInput");
    const label = tagInput ? tagInput.value.trim() : "";

    const fd = new FormData();
    for (let i = 0; i < fileList.length; i++) {
      fd.append("files", fileList[i]);
    }

    const statusEl = document.getElementById("uploadStatusMsg");
    if (statusEl) statusEl.textContent = `Uploading ${fileList.length} files...`;

    try {
      const q = label ? `?label=${encodeURIComponent(label)}` : "";
      const resp = await fetch(getBaseApiPath() + `/api/sessions/${expState.selectedSessionId}/upload${q}`, {
        method: "POST",
        headers: getApiHeaders(),
        body: fd,
      });
      const data = await resp.json();
      if (data.ok) {
        if (statusEl) statusEl.textContent = `Uploaded ${data.saved_files ? data.saved_files.length : fileList.length} files successfully!`;
        // Refresh session bucket
        selectSession(expState.selectedSessionId);
      } else {
        if (statusEl) statusEl.textContent = `Upload error: ${data.error || "Unknown"}`;
      }
    } catch (err) {
      if (statusEl) statusEl.textContent = `Upload error: ${err.message}`;
    }
  }

  function initWorkspace() {
    initExplorerEvents();
    loadWorkspaceTree();
  }

  return {
    initWorkspace: initWorkspace,
    loadWorkspaceTree: loadWorkspaceTree,
    selectSession: selectSession,
    viewFile: viewFile,
  };
});
