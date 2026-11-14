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
    viewMode: "session", // "session" | "queue"
    activeTab: "artifacts", // "uploads" | "artifacts"
    searchQuery: "",
    uploadsOpen: true,
  };

  function getApiHeaders() {
    const pass = (typeof state !== "undefined" && state.passphrase) || localStorage.getItem("nexus_passphrase") || "";
    return { "X-Nexus-Passphrase": pass, "X-Client-Product": "Workspace Explorer" };
  }

  function getBaseApiPath() {
    return (window.location.pathname || "/web").replace(/\/web\/?$/, "");
  }

  function formatUploadBatchLabel(ub) {
    if (!ub || !ub.folder_name) return "Upload batch";
    const m = ub.folder_name.match(/^uploads_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})(?:_(.*))?$/);
    return m ? `📂 ${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]}${m[7] ? ` · ${m[7]}` : ""} (${ub.file_count})` : `📂 ${ub.folder_name} (${ub.file_count})`;
  }

  function buildDemoWorkspaceTree() {
    const projs = [
      {
        project_name: "Core Infrastructure & Container GitOps",
        staged_count: 1,
        sessions: [
          { conversation_id: "demo-sess-01", title: "AGY-Nexus MCP v3.0 Overwatch", status: "RUNNING", is_pinned: true, step_count: 145 },
          { conversation_id: "demo-sess-02", title: "Perceptual OKLCH Palette", status: "IDLE", is_pinned: false, step_count: 280 },
        ],
      },
      {
        project_name: "NexusMesh ANMS (Network Telemetry)",
        staged_count: 0,
        sessions: [
          { conversation_id: "demo-sess-03", title: "Canvas Node Optimization", status: "IDLE", is_pinned: false, step_count: 320 },
        ],
      },
    ];
    return {
      ok: true,
      queue: {
        id: "__handoffs_queue__",
        title: "Visual Handoffs Queue",
        type: "queue",
        staged_count: 1,
        total_tickets: 2,
        tickets: [
          { ticket_id: "agy-nexus-mcp-01", repo_slug: "agy-nexus-mcp", title: "Overwatch Dashboard & Rendered HTML Workspace", status: "STAGED", timestamp: "15m ago", handoff_file: "scratch/gemini_research_handoff.md" },
          { ticket_id: "nexus-mesh-01", repo_slug: "nexus-mesh-telemetry", title: "Canvas Node Optimization", status: "IN_WORK", timestamp: "2h ago", handoff_file: "scratch/mesh_handoff.md" },
        ],
      },
      projects: projs,
      selected_session: "demo-sess-01",
    };
  }

  async function loadWorkspaceTree() {
    try {
      if (typeof state !== "undefined" && state.demoMode) {
        expState.treeData = buildDemoWorkspaceTree();
        renderLeftTree();
        const firstP = expState.treeData.projects[0];
        selectSession(firstP.sessions[0].conversation_id, firstP.project_name, firstP.sessions[0].title);
        return;
      }
      const resp = await fetch(getBaseApiPath() + "/web/api/workspace/tree", { headers: getApiHeaders() });
      if (resp.status === 401) {
        if (typeof state !== "undefined" && state.demoMode) {
          expState.treeData = buildDemoWorkspaceTree();
          renderLeftTree();
          const firstP = expState.treeData.projects[0];
          selectSession(firstP.sessions[0].conversation_id, firstP.project_name, firstP.sessions[0].title);
          return;
        }
        if (typeof showAuthModal === "function") return showAuthModal();
        return;
      }
      const data = await resp.json();
      if (!data.ok) return;
      expState.treeData = data;
      renderLeftTree();
      if (!expState.selectedSessionId && expState.viewMode !== "queue") {
        if (data.selected_session) selectSession(data.selected_session);
        else if (data.projects?.[0]?.sessions?.[0]) {
          const s0 = data.projects[0].sessions[0];
          selectSession(s0.conversation_id, data.projects[0].project_name, s0.title);
        }
      }
    } catch (err) {
      console.warn("Error loading workspace tree:", err);
    }
  }

  async function selectSession(convId, projectName, sessionTitle) {
    if (!convId) return;
    expState.selectedSessionId = convId;
    expState.viewMode = "session";
    if (projectName) expState.selectedProjectName = projectName;
    if (sessionTitle) expState.selectedSessionTitle = sessionTitle;
    renderSessionHeader();
    renderLeftTree();

    if (typeof state !== "undefined" && state.demoMode) {
      expState.selectedBucket = {
        ok: true,
        conversation_id: convId,
        title: expState.selectedSessionTitle,
        workspace_path: "/workspace/projects/agy-nexus-mcp",
        rollover: { posture: "FRESH", reason: "FRESH (0–319 steps): Optimal context headroom.", should_rollover: false },
        uploads: [
          {
            folder_name: "uploads_20261114_173000_audit_pack",
            file_count: 2,
            app_prompt: "Evaluate the 2 uploaded audit files in uploads_20261114_173000_audit_pack.",
            index_rel_path: "scratch/uploads_20261114_173000_audit_pack/INDEX.md",
            files: ["preview_desktop.png", "INDEX.md"],
            signed_images: [{ name: "preview_desktop.png", signed_url: "/web/icon.svg" }],
          },
        ],
        artifacts: [
          { name: "walkthrough.md", rel_path: "walkthrough.md", size: 4500, type: "artifact" },
          { name: "scratch/gemini_research_handoff.md", rel_path: "scratch/gemini_research_handoff.md", size: 5200, type: "handoff" },
          { name: "task.md", rel_path: "task.md", size: 3200, type: "artifact" },
        ],
        visual_artifacts: [{ name: "preview_desktop.png", signed_url: "/web/icon.svg", size: 48000 }],
      };
      renderSessionHeader();
      renderLeftTree();
      renderDualPane();
      viewFile("walkthrough.md", "walkthrough.md");
      return;
    }

    try {
      const resp = await fetch(getBaseApiPath() + `/web/api/sessions/${encodeURIComponent(convId)}/bucket`, { headers: getApiHeaders() });
      const data = await resp.json();
      if (data.ok) {
        expState.selectedBucket = data;
        expState.selectedSessionTitle = data.title || expState.selectedSessionTitle;
        renderSessionHeader();
        renderLeftTree();
        renderDualPane();
        if (data.artifacts?.length && !expState.selectedFilePath) {
          viewFile(data.artifacts[0].rel_path, data.artifacts[0].name);
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
    const viewer = document.getElementById("workspaceContentViewer");
    if (viewer) viewer.innerHTML = `<div class="viewer-loading mono">Loading ${escapeHtmlSafe(expState.selectedFileName)}...</div>`;

    if (typeof state !== "undefined" && state.demoMode) {
      const demoMd = `# AGY-Nexus v3.0.0 Walkthrough

<!-- Handshake Gemini Research Handoff -->
<!-- Execution Mode: fast | Handoff Mode: surgical_audit | Model: pro | MainChat: Gemini 4 Carbon -->

## Summary of Completed Capabilities

- [x] Topbar Workspace Link, Time-Horizon Controls & Settings Menu
- [x] Full 52-Week Muted Heatmap & Divisor-of-24 Plot Binning
- [x] Compact 24px-Row Borderless Tabular Legends
- [x] Hierarchical Workspace Explorer & Quiet UI Editorial HTML Reader
- [x] Continuity-Aware Rollover Posture: **FRESH (0–319 steps)**

> [!NOTE]
> All Markdown docs and handoffs are rendered using Tufte Booktabs, task check badges, GFM callouts, and DOMParser XSS sanitization.

| Feature Area | Status | Target Line Ceiling |
| :--- | :---: | :---: |
| Topbar Switcher | [x] Completed | <= 500 Lines |
| 52-Week Heatmap | [x] Completed | <= 500 Lines |
| Tabular Legends | [x] Completed | <= 500 Lines |
| Workspace Explorer | [x] Completed | <= 500 Lines |
`;
      if (viewer && MarkdownRenderer?.createMarkdownViewer) {
        MarkdownRenderer.createMarkdownViewer(viewer, demoMd, { fileName: expState.selectedFileName });
      }
      return;
    }

    try {
      const qPath = encodeURIComponent(relPath);
      const resp = await fetch(getBaseApiPath() + `/web/api/sessions/${encodeURIComponent(expState.selectedSessionId)}/file?path=${qPath}`, { headers: getApiHeaders() });
      const data = await resp.json();
      if (data.ok && viewer) {
        if (MarkdownRenderer?.createMarkdownViewer) {
          MarkdownRenderer.createMarkdownViewer(viewer, data.content, { fileName: expState.selectedFileName });
        } else {
          viewer.innerHTML = `<pre class="raw-pre mono">${escapeHtmlSafe(data.content)}</pre>`;
        }
      } else if (viewer) {
        viewer.innerHTML = `<div class="viewer-error mono">Failed to load file: ${escapeHtmlSafe(data.error || "Unknown error")}</div>`;
      }
    } catch (err) {
      if (viewer) viewer.innerHTML = `<div class="viewer-error mono">Error reading file: ${escapeHtmlSafe(String(err))}</div>`;
    }
  }

  function renderLeftTree() {
    const treeEl = document.getElementById("workspaceTreeRoot");
    if (!treeEl || !expState.treeData) return;
    const data = expState.treeData, q = (expState.searchQuery || "").toLowerCase().trim();
    let html = "";

    const qNode = data.queue || {};
    const qTotal = Number(qNode.total_tickets || qNode.total || 0);
    const qBadge = qTotal > 0 ? `<span class="tree-badge mono">${qTotal}</span>` : "";
    html += `<div class="tree-node tree-queue-node ${expState.viewMode === "queue" ? "active" : ""}" id="treeQueueNode" title="Visual Handoffs Queue"><span class="tree-icon">◈</span><span class="tree-label">Visual Handoffs Queue</span>${qBadge}</div>`;

    (data.projects || []).forEach((proj) => {
      const pName = proj.project_name || "Project", sessList = proj.sessions || [];
      if (q && !pName.toLowerCase().includes(q) && !sessList.some((s) => (s.title || "").toLowerCase().includes(q))) return;
      const stg = Number(proj.staged_count || 0);
      const projBadge = stg > 0 ? `<span class="tree-badge mono staged">${stg}</span>` : "";

      html += `<details class="tree-project-details" open><summary class="tree-project-hdr"><span class="tree-caret mono"></span><span class="tree-label"><strong>${escapeHtmlSafe(pName)}</strong></span>${projBadge}</summary><div class="tree-session-list">`;
      sessList.forEach((s) => {
        const sTitle = s.title || "Untitled Session";
        if (q && !sTitle.toLowerCase().includes(q) && !pName.toLowerCase().includes(q)) return;
        const cid = s.conversation_id, isActive = cid === expState.selectedSessionId && expState.viewMode === "session";
        const dotCls = s.status === "RUNNING" ? "running" : (s.is_pinned ? "pinned" : "idle");

        html += `<div class="tree-session-item ${isActive ? "active" : ""}" data-cid="${cid}" data-pname="${escapeHtmlSafe(pName)}" data-stitle="${escapeHtmlSafe(sTitle)}"><span class="status-dot-6px ${dotCls}"></span><span class="tree-session-title">${escapeHtmlSafe(sTitle)}</span></div>`;
        if (isActive && expState.selectedBucket) {
          const uploads = expState.selectedBucket.uploads || [], artifacts = expState.selectedBucket.artifacts || [];
          html += `<div class="tree-session-children">
            <details class="tree-sub-details" ${expState.uploadsOpen !== false ? "open" : ""} id="treeUploadsDetails">
              <summary class="tree-sub-hdr mono"><span class="tree-caret"></span><span>Uploads (${uploads.length})</span></summary>
              <div class="tree-sub-list">${uploads.map((ub) => `<div class="tree-sub-leaf tree-upload-leaf mono" data-folder="${escapeHtmlSafe(ub.folder_name)}" title="Focus ${escapeHtmlSafe(ub.folder_name)}"><span class="leaf-icon">📂</span><span class="leaf-text">${escapeHtmlSafe(formatUploadBatchLabel(ub))}</span></div>`).join("") || '<div class="tree-sub-leaf empty mono">No uploads</div>'}</div>
            </details>
            <details class="tree-sub-details" open id="treeArtifactsDetails">
              <summary class="tree-sub-hdr mono"><span class="tree-caret"></span><span>Artifacts &amp; Handoffs (${artifacts.length})</span></summary>
              <div class="tree-sub-list">${artifacts.map((art) => `<div class="tree-sub-leaf tree-art-leaf mono ${art.rel_path === expState.selectedFilePath ? "active" : ""}" data-path="${escapeHtmlSafe(art.rel_path)}" data-name="${escapeHtmlSafe(art.name)}" title="${escapeHtmlSafe(art.name)}"><span class="leaf-icon">${art.type === "handoff" || art.name.includes("handoff") ? "◈" : "📄"}</span><span class="leaf-text">${escapeHtmlSafe(art.name)}</span></div>`).join("") || '<div class="tree-sub-leaf empty mono">No artifacts</div>'}</div>
            </details></div>`;
        }
      });
      html += `</div></details>`;
    });

    treeEl.innerHTML = html;
    treeEl.querySelector("#treeQueueNode")?.addEventListener("click", () => {
      expState.viewMode = "queue";
      renderSessionHeader();
      renderLeftTree();
      renderHandoffsQueueBoard();
    });
    treeEl.querySelectorAll(".tree-session-item").forEach((it) => it.addEventListener("click", () => {
      selectSession(it.getAttribute("data-cid"), it.getAttribute("data-pname"), it.getAttribute("data-stitle"));
    }));
    treeEl.querySelectorAll(".tree-upload-leaf").forEach((leaf) => leaf.addEventListener("click", (e) => {
      e.stopPropagation();
      const folder = leaf.getAttribute("data-folder");
      document.getElementById("workspaceUploadsArea")?.classList.remove("hidden");
      document.getElementById("workspaceArtifactsArea")?.classList.add("hidden");
      const card = document.getElementById(`batch_${folder}`);
      if (card) {
        card.scrollIntoView({ behavior: "smooth", block: "center" });
        card.classList.add("highlight");
        setTimeout(() => card.classList.remove("highlight"), 2000);
      }
    }));
    treeEl.querySelectorAll(".tree-art-leaf").forEach((leaf) => leaf.addEventListener("click", (e) => {
      e.stopPropagation();
      document.getElementById("workspaceArtifactsArea")?.classList.remove("hidden");
      document.getElementById("workspaceUploadsArea")?.classList.add("hidden");
      viewFile(leaf.getAttribute("data-path"), leaf.getAttribute("data-name"));
      renderLeftTree();
    }));
    const upDet = treeEl.querySelector("#treeUploadsDetails");
    if (upDet) upDet.addEventListener("toggle", () => { expState.uploadsOpen = upDet.open; });
  }

  function renderHandoffsQueueBoard() {
    const qNode = expState.treeData?.queue || {}, tickets = qNode.tickets || [];
    const viewer = document.getElementById("workspaceContentViewer");
    if (!viewer) return;

    let html = `<div class="queue-board-wrapper"><div class="queue-board-hdr"><div class="q-title mono">◈ Cross-Project Visual Handoffs Queue</div><div class="q-subtitle mono">${tickets.length} total tickets · ${qNode.staged_count || 0} staged</div></div><div class="queue-tickets-grid">`;
    if (!tickets.length) html += `<div class="hier-empty mono">No handoff tickets staged in queue.</div>`;
    else {
      tickets.forEach((t) => {
        const tid = escapeHtmlSafe(t.ticket_id || "ticket"), st = String(t.status || "STAGED").toUpperCase();
        const stCls = st === "STAGED" ? "cyan" : (st === "IN_WORK" ? "amber" : (st === "COMPLETED" ? "green" : "dim"));
        html += `<div class="queue-ticket-card mono" data-tid="${tid}">
          <div class="q-card-top"><span class="q-tid mono"><strong>${tid}</strong></span><span class="q-repo mono">${escapeHtmlSafe(t.repo_slug || "workspace")}</span><span class="card-tag mono ${stCls}">${st}</span></div>
          <div class="q-card-title">${escapeHtmlSafe(t.title || "Gemini Research Handoff")}</div>
          <div class="q-card-meta">Timestamp: ${escapeHtmlSafe(t.created_at || t.timestamp || "recent")}</div>
          <div class="q-card-actions"><button type="button" class="btn btn-view-ticket" data-tid="${tid}" data-file="${escapeHtmlSafe(t.handoff_file || "")}">View Specification</button><button type="button" class="btn btn-copy-claim" data-cmd="praxis claim ${t.ticket_id}">Copy Praxis Command</button></div>
        </div>`;
      });
    }
    html += `</div></div>`;
    viewer.innerHTML = html;

    viewer.querySelectorAll(".btn-copy-claim").forEach((b) => b.addEventListener("click", (e) => {
      e.stopPropagation();
      const cmd = b.getAttribute("data-cmd");
      if (typeof copyTextWithFeedback === "function") copyTextWithFeedback(b, cmd, "Copied!", 1200);
      else { navigator.clipboard?.writeText(cmd); b.textContent = "Copied!"; setTimeout(() => { b.textContent = "Copy Praxis Command"; }, 1200); }
    }));
    viewer.querySelectorAll(".btn-view-ticket").forEach((b) => b.addEventListener("click", (e) => {
      e.stopPropagation();
      viewHandoffTicketFile(b.getAttribute("data-file"), b.getAttribute("data-tid"));
    }));
  }

  async function viewHandoffTicketFile(fPath, tid) {
    const viewer = document.getElementById("workspaceContentViewer");
    if (!viewer) return;
    viewer.innerHTML = `<div class="viewer-loading mono">Loading handoff ${escapeHtmlSafe(tid)}...</div>`;
    try {
      const qPath = encodeURIComponent(fPath.includes("staged_handoffs/") ? fPath.slice(fPath.indexOf("staged_handoffs/")) : fPath);
      const cid = expState.selectedSessionId || expState.treeData?.selected_session || "00000000-0000-0000-0000-000000000000";
      const resp = await fetch(getBaseApiPath() + `/web/api/sessions/${encodeURIComponent(cid)}/file?path=${qPath}`, { headers: getApiHeaders() });
      const data = await resp.json();
      if (data.ok && viewer) {
        if (MarkdownRenderer?.createMarkdownViewer) MarkdownRenderer.createMarkdownViewer(viewer, data.content, { fileName: `${tid}.md` });
        else viewer.innerHTML = `<pre class="raw-pre mono">${escapeHtmlSafe(data.content)}</pre>`;
      } else if (viewer) viewer.innerHTML = `<div class="viewer-error mono">Failed to load ticket: ${escapeHtmlSafe(data.error || "File error")}</div>`;
    } catch (err) {
      if (viewer) viewer.innerHTML = `<div class="viewer-error mono">Error loading handoff: ${escapeHtmlSafe(String(err))}</div>`;
    }
  }

  function renderSessionHeader() {
    const hdrEl = document.getElementById("workspaceSessionHeader");
    if (!hdrEl) return;
    if (expState.viewMode === "queue") {
      const qNode = expState.treeData?.queue || {};
      hdrEl.innerHTML = `<div class="ws-header-left"><span class="breadcrumb-proj">Workspace</span><span class="breadcrumb-sep">/</span><strong class="breadcrumb-session">Visual Handoffs Queue</strong><span class="card-tag mono cyan">${qNode.staged_count || 0} staged</span></div><div class="ws-header-right"><span class="mono" style="opacity:0.75; font-size:11px;">Cross-Project Queue Board</span></div>`;
      return;
    }
    const cid = expState.selectedSessionId;
    if (!cid) return (hdrEl.innerHTML = `<span class="workspace-empty-hdr mono">Select a session from the left tree</span>`);
    const pName = expState.selectedProjectName || "Project", sTitle = expState.selectedSessionTitle || "Untitled Session";
    const rollover = expState.selectedBucket?.rollover || {}, posture = rollover.posture || "FRESH";
    const postureCls = posture === "HARD_ROLLOVER" ? "red" : (posture.includes("HOLD") || posture.includes("CLOSEOUT") ? "amber" : "cyan");

    hdrEl.innerHTML = `<div class="ws-header-left"><span class="breadcrumb-proj">${escapeHtmlSafe(pName)}</span><span class="breadcrumb-sep">/</span><strong class="breadcrumb-session">${escapeHtmlSafe(sTitle)}</strong><span class="card-tag mono ${postureCls}" title="Continuity posture: ${escapeHtmlSafe(rollover.reason || posture)}">${escapeHtmlSafe(posture)}</span></div><div class="ws-header-right"><button type="button" class="btn-copy-cid btn mono" data-copy="${cid}" title="Copy Session ID">Copy ID</button></div>`;
    const copyBtn = hdrEl.querySelector(".btn-copy-cid");
    if (copyBtn) copyBtn.addEventListener("click", () => { if (typeof copyTextWithFeedback === "function") copyTextWithFeedback(copyBtn, cid, "Copy ID", 1000); });
  }

  function renderDualPane() {
    const bucket = expState.selectedBucket;
    if (!bucket) return;
    const artListEl = document.getElementById("workspaceArtifactsList");
    if (artListEl) {
      const artifacts = bucket.artifacts || [];
      artListEl.innerHTML = artifacts.length ? artifacts.map((art) => `<div class="artifact-nav-item ${art.rel_path === expState.selectedFilePath ? "active" : ""} mono" data-path="${escapeHtmlSafe(art.rel_path)}" data-name="${escapeHtmlSafe(art.name)}"><span class="art-icon">${art.type === "handoff" || art.name.includes("handoff") ? "◈" : "📄"}</span><span class="art-name">${escapeHtmlSafe(art.name)}</span><span class="art-size">${(Number(art.size || 0) / 1024).toFixed(1)}K</span></div>`).join("") : `<div class="hier-empty mono">No artifacts staged.</div>`;
      artListEl.querySelectorAll(".artifact-nav-item").forEach((it) => it.addEventListener("click", () => {
        viewFile(it.getAttribute("data-path"), it.getAttribute("data-name"));
        renderDualPane();
      }));
    }

    const upGridEl = document.getElementById("workspaceUploadsGrid");
    if (upGridEl) {
      const uploads = bucket.uploads || [], visuals = bucket.visual_artifacts || [];
      let upHtml = "";
      if (visuals.length > 0) {
        upHtml += `<div class="visuals-strip-hdr mono">Visual Artifacts &amp; Thumbnails (7-Day TTL)</div><div class="visuals-strip-grid">${visuals.map((v) => `<div class="visual-thumb-card"><a href="${escapeHtmlSafe(v.signed_url)}" target="_blank" rel="noopener noreferrer"><img src="${escapeHtmlSafe(v.signed_url)}" alt="${escapeHtmlSafe(v.name)}" class="visual-thumb-img" loading="lazy"/></a><span class="thumb-lbl mono">${escapeHtmlSafe(v.name)}</span></div>`).join("")}</div>`;
      }
      if (uploads.length > 0) {
        upHtml += `<div class="uploads-batch-hdr mono">Uploaded Scratch Batches</div>`;
        uploads.forEach((ub) => {
          const bFolder = ub.folder_name || "", signedImgs = ub.signed_images || [], appPrompt = ub.app_prompt || "";
          const idxRel = ub.index_rel_path || (bFolder ? `scratch/${bFolder}/INDEX.md` : "");
          upHtml += `<div class="upload-batch-card mono" id="batch_${escapeHtmlSafe(bFolder)}">
            <div class="batch-card-hdr"><div class="batch-title">📁 <strong>${escapeHtmlSafe(bFolder)}</strong> <span class="batch-cnt">(${ub.file_count} files)</span></div>
              <div class="batch-actions">
                ${appPrompt ? `<button type="button" class="btn btn-copy-prompt" data-prompt="${escapeHtmlSafe(appPrompt)}" title="Copy Evaluation Prompt">Copy Evaluation Prompt</button>` : ""}
                ${idxRel ? `<button type="button" class="btn btn-open-index" data-path="${escapeHtmlSafe(idxRel)}" title="Open INDEX.md">Open INDEX.md</button>` : ""}
              </div></div>
            ${signedImgs.length > 0 ? `<div class="batch-thumbs-strip">${signedImgs.map((img) => `<a href="${escapeHtmlSafe(img.signed_url)}" target="_blank" rel="noopener noreferrer" class="batch-thumb-link" title="${escapeHtmlSafe(img.name)}"><img src="${escapeHtmlSafe(img.signed_url)}" alt="${escapeHtmlSafe(img.name)}" class="batch-thumb-img" loading="lazy"/></a>`).join("")}</div>` : ""}
            <div class="batch-files">${(ub.files || []).map((f) => `<span class="batch-file-pill">${escapeHtmlSafe(typeof f === "object" ? f.name : f)}</span>`).join(" ")}</div>
          </div>`;
        });
      }
      upGridEl.innerHTML = upHtml || `<div class="hier-empty mono">No scratch uploads in this session yet.</div>`;
      upGridEl.querySelectorAll(".btn-copy-prompt").forEach((b) => b.addEventListener("click", (e) => {
        e.stopPropagation();
        const p = b.getAttribute("data-prompt");
        if (typeof copyTextWithFeedback === "function") copyTextWithFeedback(b, p, "Copied Prompt!", 1200);
        else { navigator.clipboard?.writeText(p); b.textContent = "Copied Prompt!"; setTimeout(() => { b.textContent = "Copy Evaluation Prompt"; }, 1200); }
      }));
      upGridEl.querySelectorAll(".btn-open-index").forEach((b) => b.addEventListener("click", (e) => {
        e.stopPropagation();
        viewFile(b.getAttribute("data-path"), "INDEX.md");
        document.getElementById("workspaceArtifactsArea")?.classList.remove("hidden");
        document.getElementById("workspaceUploadsArea")?.classList.add("hidden");
      }));
    }
  }

  function initExplorerEvents() {
    document.getElementById("workspaceTreeSearch")?.addEventListener("input", (e) => {
      expState.searchQuery = e.target.value;
      renderLeftTree();
    });
    const dropZone = document.getElementById("workspaceUploadDropzone");
    if (dropZone) {
      ["dragenter", "dragover"].forEach((evt) => dropZone.addEventListener(evt, (e) => { e.preventDefault(); e.stopPropagation(); dropZone.classList.add("drag-over"); }));
      ["dragleave", "drop"].forEach((evt) => dropZone.addEventListener(evt, (e) => { e.preventDefault(); e.stopPropagation(); dropZone.classList.remove("drag-over"); }));
      dropZone.addEventListener("drop", (e) => {
        if (e.dataTransfer?.files?.length) handleFilesUpload(e.dataTransfer.files);
      });
    }
    window.addEventListener("paste", (e) => {
      const wsMain = document.getElementById("workspaceMain");
      if (!wsMain || wsMain.classList.contains("hidden")) return;
      const items = (e.clipboardData || e.originalEvent?.clipboardData)?.items || [];
      const fileList = [];
      for (let i = 0; i < items.length; i++) {
        if (items[i].kind === "file") fileList.push(items[i].getAsFile());
      }
      if (fileList.length > 0) handleFilesUpload(fileList);
    });
  }

  async function handleFilesUpload(fileList) {
    if (!expState.selectedSessionId) return alert("Please select a session first before uploading files.");
    const tagInput = document.getElementById("uploadBatchTagInput");
    const label = tagInput ? tagInput.value.trim() : "";
    const fd = new FormData();
    for (let i = 0; i < fileList.length; i++) fd.append("files", fileList[i]);
    if (label) fd.append("label", label);

    const statusEl = document.getElementById("uploadStatusMsg");
    if (statusEl) statusEl.textContent = `Uploading ${fileList.length} files...`;
    try {
      const q = label ? `?label=${encodeURIComponent(label)}` : "";
      const resp = await fetch(getBaseApiPath() + `/web/api/sessions/${encodeURIComponent(expState.selectedSessionId)}/upload${q}`, {
        method: "POST", headers: getApiHeaders(), body: fd,
      });
      const data = await resp.json();
      if (data.ok) {
        if (statusEl) statusEl.textContent = `Uploaded ${data.saved_files ? data.saved_files.length : fileList.length} files successfully!`;
        if (tagInput) tagInput.value = "";
        expState.uploadsOpen = true;
        await selectSession(expState.selectedSessionId);
        loadWorkspaceTree();
      } else if (statusEl) statusEl.textContent = `Upload error: ${data.error || "Unknown"}`;
    } catch (err) {
      if (statusEl) statusEl.textContent = `Upload error: ${err.message}`;
    }
  }

  function initWorkspace() {
    initExplorerEvents();
    loadWorkspaceTree();
  }

  return { initWorkspace, loadWorkspaceTree, selectSession, viewFile };
});
