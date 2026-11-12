// Session Scratch Batch Uploads Modal — Quiet UI & Progress Manager (v2.7.0)
let currentUploadConvId = "";
let selectedUploadFiles = [];
let uploadBatchCompleted = false;
let pasteSeqCounter = 0;

function formatFileSize(bytes) {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return (bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1) + " " + units[i];
}

function renderUploadFileList() {
  const listEl = document.getElementById("uploadFileList");
  const itemsEl = document.getElementById("uploadFileItems");
  const countEl = document.getElementById("uploadFileCount");
  const sizeEl = document.getElementById("uploadTotalSize");
  const submitBtn = document.getElementById("uploadSubmitBtn");
  if (!listEl || !itemsEl) return;
  if (selectedUploadFiles.length === 0) {
    listEl.classList.add("hidden");
    itemsEl.innerHTML = "";
    if (submitBtn && !uploadBatchCompleted) submitBtn.disabled = true;
    return;
  }
  listEl.classList.remove("hidden");
  const totalBytes = selectedUploadFiles.reduce((acc, f) => acc + f.size, 0);
  if (countEl) countEl.textContent = `${selectedUploadFiles.length} file${selectedUploadFiles.length === 1 ? "" : "s"} selected`;
  if (sizeEl) sizeEl.textContent = formatFileSize(totalBytes);
  if (submitBtn) {
    submitBtn.disabled = false;
    submitBtn.textContent = "Upload Batch";
  }

  itemsEl.innerHTML = selectedUploadFiles.map((f, idx) => `
    <div class="upload-file-item mono">
      <span class="upload-file-name" title="${escapeHtmlSafe(f.name)}">${idx + 1}. ${escapeHtmlSafe(f.name)}</span>
      <span class="upload-file-sz">${formatFileSize(f.size)}</span>
      <button type="button" class="upload-file-del" data-idx="${idx}" aria-label="Remove file">&times;</button>
    </div>
  `).join("");

  itemsEl.querySelectorAll(".upload-file-del").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      selectedUploadFiles.splice(Number(btn.getAttribute("data-idx") || 0), 1);
      renderUploadFileList();
    });
  });
}

function addFilesToUploadQueue(fileList) {
  if (!fileList || fileList.length === 0) return;
  if (uploadBatchCompleted) {
    uploadBatchCompleted = false;
    selectedUploadFiles = [];
    const sWrap = document.getElementById("uploadSuccessWrap");
    if (sWrap) sWrap.classList.add("hidden");
  }
  const errEl = document.getElementById("uploadErrorMsg");
  if (errEl) { errEl.classList.add("hidden"); errEl.textContent = ""; }
  for (let i = 0; i < fileList.length; i++) {
    const f = fileList[i];
    if (selectedUploadFiles.length >= 100) break;
    if (!selectedUploadFiles.some((ex) => ex.name === f.name && ex.size === f.size)) {
      selectedUploadFiles.push(f);
    }
  }
  renderUploadFileList();
}

function window_openUploadModal(convId, sessionTitle) {
  const dialog = document.getElementById("uploadDialog");
  if (!dialog) return;
  currentUploadConvId = convId || "";
  selectedUploadFiles = [];
  uploadBatchCompleted = false;

  const metaEl = document.getElementById("uploadDialogSessionMeta");
  if (metaEl) metaEl.textContent = `${sessionTitle || "Session"} (${convId ? convId.slice(0, 8) : "-"})`;
  const labelInp = document.getElementById("uploadBatchLabel");
  if (labelInp) labelInp.value = "";
  const submitBtn = document.getElementById("uploadSubmitBtn");
  if (submitBtn) { submitBtn.textContent = "Upload Batch"; submitBtn.disabled = true; }
  const cancelBtn = document.getElementById("uploadCancelBtn");
  if (cancelBtn) cancelBtn.disabled = false;
  ["uploadProgressWrap", "uploadSuccessWrap", "uploadErrorMsg"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.classList.add("hidden");
  });
  renderUploadFileList();
  if (typeof dialog.showModal === "function") dialog.showModal();
  else dialog.classList.remove("hidden");
}
window.openUploadModal = window_openUploadModal;

function resolveNexusPassphrase() {
  return (typeof state !== "undefined" && state && state.passphrase)
    || localStorage.getItem("nexus_passphrase")
    || sessionStorage.getItem("nexus_passphrase")
    || "";
}

function executeUploadBatch() {
  const dialog = document.getElementById("uploadDialog");
  if (uploadBatchCompleted) {
    if (dialog) dialog.close();
    return;
  }
  if (!currentUploadConvId || selectedUploadFiles.length === 0) return;
  const progWrap = document.getElementById("uploadProgressWrap");
  const progBar = document.getElementById("uploadProgressBar");
  const progStatus = document.getElementById("uploadProgressStatus");
  const submitBtn = document.getElementById("uploadSubmitBtn");
  const cancelBtn = document.getElementById("uploadCancelBtn");
  const successWrap = document.getElementById("uploadSuccessWrap");
  const summaryPath = document.getElementById("uploadSummaryPath");
  const promptText = document.getElementById("uploadPromptText");
  const copyPromptBtn = document.getElementById("copyUploadPromptBtn");
  const errEl = document.getElementById("uploadErrorMsg");
  const labelInp = document.getElementById("uploadBatchLabel");

  const storedPass = resolveNexusPassphrase();
  if (!storedPass && typeof state !== "undefined" && state.demoMode) {
    if (errEl) {
      errEl.classList.remove("hidden");
      errEl.textContent = "Unlock the dashboard with your passphrase first before uploading files.";
    }
    return;
  }

  if (errEl) { errEl.classList.add("hidden"); errEl.textContent = ""; }
  if (progWrap) progWrap.classList.remove("hidden");
  if (progBar) progBar.style.width = "0%";
  if (progStatus) progStatus.textContent = "Uploading... 0%";
  if (submitBtn) submitBtn.disabled = true;
  if (cancelBtn) cancelBtn.disabled = true;

  const formData = new FormData();
  if (labelInp && labelInp.value.trim()) formData.append("label", labelInp.value.trim());
  selectedUploadFiles.forEach((file) => formData.append("files", file, file.name));

  const basePrefix = window.location.pathname.replace(/\/web\/?$/, "");
  const uploadUrl = `${basePrefix}/web/api/sessions/${encodeURIComponent(currentUploadConvId)}/upload`;
  const xhr = new XMLHttpRequest();
  xhr.open("POST", uploadUrl, true);
  if (storedPass) xhr.setRequestHeader("X-Nexus-Passphrase", storedPass);

  xhr.upload.onprogress = (e) => {
    if (e.lengthComputable) {
      const pct = Math.round((e.loaded / e.total) * 100);
      if (progBar) progBar.style.width = pct + "%";
      if (progStatus) progStatus.textContent = `Uploading... ${pct}% (${formatFileSize(e.loaded)} / ${formatFileSize(e.total)})`;
    }
  };

  xhr.onload = () => {
    if (cancelBtn) cancelBtn.disabled = false;
    let res = null;
    try {
      res = JSON.parse(xhr.responseText);
    } catch {
      res = { ok: false, error: `Server returned non-JSON response (HTTP ${xhr.status || 0}).` };
    }
    if (xhr.status >= 200 && xhr.status < 300 && res && res.ok) {
      uploadBatchCompleted = true;
      if (progWrap) progWrap.classList.add("hidden");
      if (successWrap) successWrap.classList.remove("hidden");
      if (summaryPath) summaryPath.textContent = res.batch_folder || res.relative_folder || "";
      if (promptText) promptText.textContent = res.app_prompt || "";
      if (copyPromptBtn) copyPromptBtn.onclick = () => copyTextWithFeedback(copyPromptBtn, res.app_prompt, "Copy App Prompt", 1200);
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = "Done";
      }
    } else {
      if (progWrap) progWrap.classList.add("hidden");
      if (submitBtn) submitBtn.disabled = false;
      if (errEl) {
        errEl.classList.remove("hidden");
        errEl.textContent = (res && res.error) ? res.error : `Upload failed (HTTP ${xhr.status})`;
      }
    }
  };

  xhr.onerror = () => {
    if (cancelBtn) cancelBtn.disabled = false;
    if (submitBtn) submitBtn.disabled = false;
    if (progWrap) progWrap.classList.add("hidden");
    if (errEl) { errEl.classList.remove("hidden"); errEl.textContent = "Network error during batch upload."; }
  };
  xhr.send(formData);
}

(function initUploadModal() {
  const dialog = document.getElementById("uploadDialog");
  if (!dialog) return;
  const dropzone = document.getElementById("uploadDropzone");
  const fileInput = document.getElementById("uploadFileInput");
  const submitBtn = document.getElementById("uploadSubmitBtn");
  const cancelBtn = document.getElementById("uploadCancelBtn");
  const closeBtn = document.getElementById("uploadDialogCloseBtn");

  if (dropzone && fileInput) {
    dropzone.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", (e) => { addFilesToUploadQueue(e.target.files); fileInput.value = ""; });
    dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("dragover"); });
    dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
      if (e.dataTransfer && e.dataTransfer.files) addFilesToUploadQueue(e.dataTransfer.files);
    });
  }

  window.addEventListener("paste", (e) => {
    if (!dialog.open) return;
    const items = (e.clipboardData || (e.originalEvent && e.originalEvent.clipboardData))?.items;
    if (!items) return;
    const pasted = [];
    for (let i = 0; i < items.length; i++) {
      if (items[i].kind === "file") {
        const f = items[i].getAsFile();
        if (f) {
          pasteSeqCounter += 1;
          const ext = (f.name && f.name.includes(".")) ? f.name.slice(f.name.lastIndexOf(".")) : ".png";
          const safeFile = (!f.name || f.name === "image.png")
            ? new File([f], `paste_${String(pasteSeqCounter).padStart(2, "0")}${ext}`, { type: f.type })
            : f;
          pasted.push(safeFile);
        }
      }
    }
    if (pasted.length > 0) addFilesToUploadQueue(pasted);
  });

  if (submitBtn) submitBtn.addEventListener("click", executeUploadBatch);
  if (cancelBtn) cancelBtn.addEventListener("click", () => dialog.close());
  if (closeBtn) closeBtn.addEventListener("click", () => dialog.close());

  if (!("closedBy" in HTMLDialogElement.prototype)) {
    dialog.addEventListener("click", (e) => {
      if (e.target !== dialog) return;
      const r = dialog.getBoundingClientRect();
      if (!(r.top <= e.clientY && e.clientY <= r.bottom && r.left <= e.clientX && e.clientX <= r.right)) dialog.close();
    });
  }
})();
