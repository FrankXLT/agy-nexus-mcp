/* SPDX-License-Identifier: Apache-2.0 */
/* AGY-Nexus /web/v9 — M2 Editorial Markdown Renderer & Allowlist Sanitizer */
(() => {
  const V9 = window.AgyV9;
  const ALLOWED_TAGS = new Set([
    "H1", "H2", "H3", "H4", "P", "PRE", "CODE", "STRONG", "EM", "BR",
    "A", "IMG", "UL", "OL", "LI", "INPUT", "TABLE", "THEAD", "TBODY", "TR",
    "TH", "TD", "DIV", "SPAN", "BLOCKQUOTE", "ASIDE",
  ]);
  const ALLOWED_ATTRS = new Set([
    "href", "src", "alt", "class", "type", "disabled", "checked",
    "aria-label", "role", "tabindex", "loading", "data-tone", "data-lang",
    "data-v9-md-img", "target", "rel",
  ]);

  function sanitizeUrl(rawUrl, allowHash) {
    const cleaned = String(rawUrl || "").replace(/[\u0000-\u0020\u007f]/g, "").trim();
    if (!cleaned || cleaned.startsWith("//") || cleaned.includes("\\")) return "";
    if (allowHash && cleaned.startsWith("#")) return cleaned;
    const pathPart = cleaned.split(/[?#]/, 1)[0];
    if (!/^https?:\/\//i.test(cleaned) && (/(?:^|\/)\.\.(?:\/|$)/.test(pathPart) || /%2e%2e/i.test(pathPart))) return "";
    if (/^\.\/[A-Za-z0-9._\/-]+$/.test(cleaned)) return cleaned;
    if (/^\/(?![\/\\])/.test(cleaned)) return cleaned;
    if (/^https?:\/\//i.test(cleaned)) return cleaned;
    return "";
  }

  function resolveImageUrl(rawSrc, bucket) {
    const src = String(rawSrc || "").trim();
    if (!src) return "";
    const direct = sanitizeUrl(src, false);
    if (direct && /^(?:https?:|\/web\/|\.\/)/i.test(direct)) return direct;
    const baseName = src.split("/").pop();
    const pool = [...((bucket && bucket.visual_artifacts) || []), ...((bucket && bucket.repo_visual_assets) || [])];
    const hit = pool.find((item) => item.rel_path === src || item.name === baseName);
    if (hit && hit.signed_url) return sanitizeUrl(hit.signed_url, false);
    return direct;
  }

  function renderInline(raw, bucket) {
    const tokens = [];
    const stash = (html) => {
      const idx = tokens.length;
      tokens.push(html);
      return `\u0000TOK${idx}\u0000`;
    };
    let s = String(raw || "");
    s = s.replace(/`([^`]+)`/g, (_m, c) => stash(`<code>${V9.escHtml(c)}</code>`));
    s = s.replace(/!\[([^\]]*)\]\(([^)\s]+)\)/g, (_m, alt, url) => {
      const safe = resolveImageUrl(url, bucket);
      if (!safe) return V9.escHtml(alt || "");
      return stash(`<img class="v9-md-img" src="${V9.escHtml(safe)}" alt="${V9.escHtml(alt)}" data-v9-md-img="${V9.escHtml(safe)}" loading="lazy" />`);
    });
    s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_m, lbl, rawHref) => {
      const safeHref = sanitizeUrl(rawHref, true);
      if (!safeHref) return V9.escHtml(lbl);
      const ext = /^https?:/i.test(safeHref) ? ` target="_blank" rel="noopener noreferrer"` : "";
      return stash(`<a href="${V9.escHtml(safeHref)}"${ext}>${V9.escHtml(lbl)}</a>`);
    });
    s = V9.escHtml(s);
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    s = s.replace(/\u0000TOK(\d+)\u0000/g, (_m, i) => tokens[Number(i)] || "");
    return s;
  }

  function parseTableBlock(lines, startIdx, bucket) {
    let end = startIdx;
    while (end < lines.length && lines[end].trim().startsWith("|")) end += 1;
    const tblLines = lines.slice(startIdx, end);
    if (tblLines.length < 2 || !/^\s*\|?[\s:|-]+\|/.test(tblLines[1])) return null;
    const splitRow = (line) => line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
    const headers = splitRow(tblLines[0]);
    const bodyRows = tblLines.slice(2).map(splitRow);
    const thead = `<thead><tr>${headers.map((h) => `<th>${renderInline(h, bucket)}</th>`).join("")}</tr></thead>`;
    const tbody = `<tbody>${bodyRows.map((row) => `<tr>${row.map((c) => `<td>${renderInline(c, bucket)}</td>`).join("")}</tr>`).join("")}</tbody>`;
    return { nextIdx: end - 1, html: `<div class="va-table-wrap" tabindex="0" role="region" aria-label="Markdown table"><table class="v9-table booktabs">${thead}${tbody}</table></div>` };
  }

  function markdownToHtml(mdText, bucket) {
    const lines = String(mdText || "").replace(/\r\n/g, "\n").split("\n");
    const out = [];
    let i = 0;
    while (i < lines.length) {
      const trim = lines[i].trim();
      if (!trim) { i += 1; continue; }
      const fence = trim.match(/^```([a-zA-Z0-9_-]*)/);
      if (fence) {
        const codeLines = [];
        i += 1;
        while (i < lines.length && !lines[i].trim().startsWith("```")) { codeLines.push(V9.escHtml(lines[i])); i += 1; }
        out.push(`<pre><code data-lang="${V9.escHtml(fence[1] || "text")}">${codeLines.join("\n")}</code></pre>`);
        i += 1;
        continue;
      }
      const h = trim.match(/^(#{1,4})\s+(.+)$/);
      if (h) {
        const lvl = h[1].length;
        out.push(`<h${lvl}>${renderInline(h[2], bucket)}</h${lvl}>`);
        i += 1;
        continue;
      }
      if (trim.startsWith(">")) {
        const qLines = [];
        while (i < lines.length && lines[i].trim().startsWith(">")) { qLines.push(lines[i].trim().replace(/^>\s?/, "")); i += 1; }
        const first = qLines[0] || "";
        const cm = first.match(/^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]$/i);
        if (cm) {
          const kind = cm[1].toUpperCase();
          const tone = kind === "WARNING" ? "warn" : (kind === "CAUTION" ? "err" : "info");
          out.push(`<aside class="v9-md-callout" data-tone="${tone}"><strong>${kind}</strong><br>${qLines.slice(1).map((l) => renderInline(l, bucket)).join("<br>")}</aside>`);
        } else {
          out.push(`<aside class="v9-md-callout">${qLines.map((l) => renderInline(l, bucket)).join("<br>")}</aside>`);
        }
        continue;
      }
      if (trim.startsWith("|")) {
        const tbl = parseTableBlock(lines, i, bucket);
        if (tbl) { out.push(tbl.html); i = tbl.nextIdx + 1; continue; }
      }
      if (/^[-*+]\s+/.test(trim) || /^\d+\.\s+/.test(trim)) {
        const isOrd = /^\d+\.\s+/.test(trim);
        const listLines = [];
        while (i < lines.length && (/^\s*[-*+]\s+/.test(lines[i]) || /^\s*\d+\.\s+/.test(lines[i]))) {
          listLines.push(lines[i].trim());
          i += 1;
        }
        const isTask = listLines.some((l) => /^[-*+]\s+\[[ xX]\]\s+/.test(l));
        const tag = isOrd ? "ol" : "ul";
        const ulCls = isTask ? ` class="contains-task-list"` : "";
        const items = listLines.map((l) => {
          const tm = l.match(/^[-*+]\s+\[([ xX])\]\s+(.+)$/);
          if (tm) {
            const chk = tm[1].toLowerCase() === "x" ? " checked" : "";
            return `<li class="task-list-item"><input type="checkbox" disabled${chk} aria-label="Task item" /><span>${renderInline(tm[2], bucket)}</span></li>`;
          }
          return `<li>${renderInline(l.replace(/^([-*+]|\d+\.)\s+/, ""), bucket)}</li>`;
        }).join("");
        out.push(`<${tag}${ulCls}>${items}</${tag}>`);
        continue;
      }
      const pLines = [trim];
      i += 1;
      while (i < lines.length && lines[i].trim() && !/^(#{1,4}\s+|```|>|\||[-*+]\s+|\d+\.\s+)/.test(lines[i].trim())) {
        pLines.push(lines[i].trim());
        i += 1;
      }
      out.push(`<p>${renderInline(pLines.join(" "), bucket)}</p>`);
    }
    return sanitizeHtml(out.join("\n"));
  }

  function sanitizeHtml(rawHtml) {
    const doc = new DOMParser().parseFromString(rawHtml, "text/html");
    Array.from(doc.body.querySelectorAll("*")).forEach((el) => {
      if (!ALLOWED_TAGS.has(el.tagName)) { el.remove(); return; }
      Array.from(el.attributes).forEach((attr) => {
        const nm = attr.name.toLowerCase();
        if (!ALLOWED_ATTRS.has(nm) || nm.startsWith("on")) { el.removeAttribute(attr.name); return; }
        if (nm === "href" || nm === "src" || nm === "data-v9-md-img") {
          const safe = sanitizeUrl(attr.value, nm === "href");
          if (!safe) el.removeAttribute(attr.name);
          else el.setAttribute(attr.name, safe);
        }
      });
    });
    return doc.body.innerHTML;
  }

  function renderDocument(docResp, bucket, onOpenImageFn) {
    const contentEl = document.getElementById("v9DocContent");
    const metaEl = document.getElementById("v9DocMeta");
    if (!contentEl) return;
    if (!docResp || (!docResp.content && !docResp.raw_content)) {
      contentEl.innerHTML = `<div class="v9-empty">No Markdown document selected.</div>`;
      if (metaEl) metaEl.textContent = "";
      return;
    }
    const isRaw = V9.state.docMode === "raw";
    const text = String(isRaw ? (docResp.raw_content || docResp.content || "") : (docResp.content || docResp.raw_content || ""));
    if (metaEl) metaEl.textContent = `${docResp.rel_path || "document.md"} · ${V9.fmtBytes(docResp.size || text.length)}`;
    if (isRaw) {
      contentEl.innerHTML = `<pre><code>${V9.escHtml(text)}</code></pre>`;
    } else {
      contentEl.innerHTML = markdownToHtml(text, bucket);
      contentEl.querySelectorAll("img[data-v9-md-img]").forEach((im) => {
        im.addEventListener("click", () => {
          const safe = sanitizeUrl(im.getAttribute("data-v9-md-img"), false);
          if (safe && typeof onOpenImageFn === "function") onOpenImageFn(safe, im.getAttribute("alt") || "Image");
        });
      });
    }
  }

  V9.Markdown = { renderDocument, sanitizeUrl, resolveImageUrl };
})();
