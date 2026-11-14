// Quiet UI Editorial HTML Markdown Renderer (v3.0.0)
// Tufte Booktabs, Task Badges, GFM Callouts, Code Blocks with Copy, XSS Sanitization & View Modes

(function (root, factory) {
  if (typeof define === "function" && define.amd) {
    define([], factory);
  } else if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.MarkdownRenderer = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function escapeHtml(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  const ALLOWED_TAGS = new Set([
    "a", "abbr", "b", "bdi", "bdo", "blockquote", "br", "caption", "cite", "code",
    "col", "colgroup", "dd", "del", "details", "dfn", "div", "dl", "dt", "em",
    "figcaption", "figure", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i", "img",
    "ins", "kbd", "li", "mark", "ol", "p", "pre", "q", "rp", "rt", "ruby", "s",
    "samp", "small", "span", "strong", "sub", "summary", "sup", "table", "tbody",
    "td", "tfoot", "th", "thead", "time", "tr", "u", "ul", "var", "wbr"
  ]);

  const ALLOWED_ATTRS = new Set([
    "href", "src", "alt", "title", "class", "id", "target", "rel", "loading",
    "open", "data-copy", "aria-label", "aria-hidden", "colspan", "rowspan", "width", "height"
  ]);

  const DANGEROUS_PROTO_RE = /^(?:\s*javascript:|\s*vbscript:|\s*data:text\/html)/i;

  function sanitizeHtml(dirtyHtml) {
    if (!dirtyHtml) return "";
    if (typeof window !== "undefined" && window.DOMPurify && typeof window.DOMPurify.sanitize === "function") {
      return window.DOMPurify.sanitize(dirtyHtml, {
        ADD_TAGS: ["summary", "details"],
        ADD_ATTR: ["target", "rel", "data-copy", "open"],
      });
    }

    if (typeof DOMParser !== "undefined") {
      try {
        const parser = new DOMParser();
        const doc = parser.parseFromString("<!DOCTYPE html><body>" + dirtyHtml, "text/html");
        const body = doc.body;

        function cleanNode(node) {
          if (!node) return;
          const children = Array.from(node.childNodes);
          for (const child of children) {
            if (child.nodeType === 1) { // Element
              const tag = child.tagName.toLowerCase();
              if (!ALLOWED_TAGS.has(tag) || tag === "script" || tag === "iframe" || tag === "object" || tag === "embed") {
                child.remove();
                continue;
              }
              const attrs = Array.from(child.attributes);
              for (const attr of attrs) {
                const name = attr.name.toLowerCase();
                const val = attr.value;
                if (name.startsWith("on") || !ALLOWED_ATTRS.has(name)) {
                  child.removeAttribute(attr.name);
                } else if ((name === "href" || name === "src") && DANGEROUS_PROTO_RE.test(val)) {
                  child.removeAttribute(attr.name);
                }
              }
              cleanNode(child);
            }
          }
        }

        cleanNode(body);
        return body.innerHTML;
      } catch (e) {
        // Fall through to regex fallback
      }
    }

    return dirtyHtml
      .replace(/<(?:script|iframe|object|embed)\b[^<]*(?:(?!<\/(?:script|iframe|object|embed)>)<[^<]*)*<\/(?:script|iframe|object|embed)>/gi, "")
      .replace(/<(?:script|iframe|object|embed)\b[^>]*>/gi, "")
      .replace(/&lt;(?:script|iframe|object|embed)\b[\s\S]*?&lt;\/(?:script|iframe|object|embed)&gt;/gi, "")
      .replace(/&lt;(?:script|iframe|object|embed)\b[\s\S]*?&gt;/gi, "")
      .replace(/\s+on\w+\s*=\s*(?:"[^"]*"|'[^']*'|&quot;[^&]*&quot;|&#39;[^&]*&#39;|[^\s>]+)/gi, "")
      .replace(/(?:href|src)\s*=\s*["']?\s*(?:javascript:|vbscript:|data:text\/html)[^"'>\s]*/gi, "")
      .replace(/(?:href|src)\s*=\s*&quot;\s*(?:javascript:|vbscript:|data:text\/html)[^&]*&quot;/gi, "");
  }

  function parseHandoffMetadata(mdText) {
    const meta = {};
    const commentRegex = /<!--\s*([\s\S]*?)\s*-->/g;
    let match;
    while ((match = commentRegex.exec(mdText)) !== null) {
      const content = match[1].trim();
      if (content.includes("Handshake Gemini Research Handoff") || content.includes("Execution Mode:")) {
        const parts = content.split("|");
        parts.forEach((p) => {
          const kv = p.split(":");
          if (kv.length === 2) {
            meta[kv[0].trim().toLowerCase().replace(/\s+/g, "_")] = kv[1].trim();
          }
        });
      }
    }
    return meta;
  }

  function renderMetadataBanner(meta) {
    if (!meta || Object.keys(meta).length === 0) return "";
    const items = [];
    if (meta.execution_mode) items.push(`<span class="meta-pill"><span class="meta-k">Mode:</span> <strong>${escapeHtml(meta.execution_mode)}</strong></span>`);
    if (meta.handoff_mode) items.push(`<span class="meta-pill"><span class="meta-k">Handoff:</span> <strong>${escapeHtml(meta.handoff_mode)}</strong></span>`);
    if (meta.model) items.push(`<span class="meta-pill"><span class="meta-k">Tier:</span> <strong>${escapeHtml(meta.model)}</strong></span>`);
    if (meta.mainchat) items.push(`<span class="meta-pill"><span class="meta-k">Main Chat:</span> <strong>${escapeHtml(meta.mainchat)}</strong></span>`);
    if (meta.effort) items.push(`<span class="meta-pill"><span class="meta-k">Effort:</span> <strong>${escapeHtml(meta.effort)}</strong></span>`);
    if (meta.chained_publish) items.push(`<span class="meta-pill"><span class="meta-k">Publish:</span> <strong>${escapeHtml(meta.chained_publish)}</strong></span>`);

    return `
      <div class="editorial-meta-banner mono">
        <div class="banner-title">◈ GEMINI HANDOFF SPECIFICATION</div>
        <div class="banner-pills">${items.join("")}</div>
      </div>
    `;
  }

  function parseInlineMarkdown(text) {
    if (!text) return "";
    let s = text;
    const tokens = [];

    // Step 1: Tokenize inline code: `code`
    s = s.replace(/`([^`]+)`/g, function (_, code) {
      const idx = tokens.length;
      tokens.push(`<code class="mono inline-code">${escapeHtml(code)}</code>`);
      return `__MK_TOKEN_${idx}__`;
    });

    // Step 2: Tokenize Images: ![alt](url) (BEFORE links!)
    s = s.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, function (_, alt, url) {
      const idx = tokens.length;
      tokens.push(
        `<figure class="editorial-figure"><img src="${escapeHtml(url)}" alt="${escapeHtml(alt)}" loading="lazy" class="editorial-img"/><figcaption>${escapeHtml(alt)}</figcaption></figure>`
      );
      return `__MK_TOKEN_${idx}__`;
    });

    // Step 3: Tokenize Links: (?<!!)\[([^\]]+)\]\(([^)]+)\)
    s = s.replace(/(?<!!)\[([^\]]+)\]\(([^)]+)\)/g, function (_, label, url) {
      const idx = tokens.length;
      const cleanUrl = url.trim();
      const isExternal = cleanUrl.startsWith("http://") || cleanUrl.startsWith("https://");
      const targetAttr = isExternal ? ' target="_blank" rel="noopener noreferrer"' : "";
      tokens.push(`<a href="${escapeHtml(cleanUrl)}" class="editorial-link"${targetAttr}>${escapeHtml(label)}</a>`);
      return `__MK_TOKEN_${idx}__`;
    });

    // Step 4: Escape remaining untrusted HTML characters
    s = escapeHtml(s);

    // Step 5: Format bold, italic, strikethrough, task badges
    s = s.replace(/\*\*\*([^*]+)\*\*\*/g, "<strong><em>$1</em></strong>");
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    s = s.replace(/\b_([^_]+)_\b/g, "<em>$1</em>");
    s = s.replace(/~~([^~]+)~~/g, "<del>$1</del>");

    s = s.replace(/\[x\]/gi, '<span class="task-badge task-done mono">✓ Done</span>');
    s = s.replace(/\[\/\]/g, '<span class="task-badge task-prog mono">▶ In-Progress</span>');
    s = s.replace(/\[ \]/g, '<span class="task-badge task-pending mono">○ Pending</span>');

    // Step 6: Restore token placeholders
    s = s.replace(/__MK_TOKEN_(\d+)__/g, function (_, idx) {
      return tokens[Number(idx)] || "";
    });

    return s;
  }

  function renderTable(lines) {
    if (lines.length < 2) return "";
    const headerCols = lines[0].split("|").map((c) => c.trim()).filter((c) => c !== "");
    // Line 1 is delimiter: |--|--|
    const rowLines = lines.slice(2);

    let html = '<div class="table-editorial-wrap"><table class="table-clean booktabs">';
    html += "<thead><tr>";
    headerCols.forEach((col) => {
      html += `<th>${parseInlineMarkdown(col)}</th>`;
    });
    html += "</tr></thead><tbody>";

    rowLines.forEach((r) => {
      const cols = r.split("|").map((c) => c.trim()).filter((c) => c !== "");
      if (cols.length) {
        html += "<tr>";
        cols.forEach((col, idx) => {
          const isNumeric = /^[\d.,%$~+-]+$/.test(col);
          const cls = isNumeric ? ' class="num-col mono"' : "";
          html += `<td${cls}>${parseInlineMarkdown(col)}</td>`;
        });
        html += "</tr>";
      }
    });

    html += "</tbody></table></div>";
    return html;
  }

  function renderMarkdownToEditorialHtml(mdText, opts) {
    if (!mdText) return '<div class="editorial-empty">Empty document</div>';
    opts = opts || {};

    const meta = parseHandoffMetadata(mdText);
    const metaBanner = renderMetadataBanner(meta);

    const lines = mdText.split(/\r?\n/);
    const out = [];
    let inCode = false;
    let codeLang = "";
    let codeBuffer = [];
    let tableBuffer = [];
    let inCallout = false;
    let calloutType = "";
    let calloutBuffer = [];

    function flushTable() {
      if (tableBuffer.length) {
        out.push(renderTable(tableBuffer));
        tableBuffer = [];
      }
    }

    function flushCallout() {
      if (inCallout) {
        const typeCls = (calloutType || "note").toLowerCase();
        const bodyHtml = calloutBuffer.map((l) => parseInlineMarkdown(l)).join("<br/>");
        out.push(`
          <aside class="editorial-callout callout-${typeCls}">
            <div class="callout-hdr mono">◈ ${calloutType.toUpperCase()}</div>
            <div class="callout-body">${bodyHtml}</div>
          </aside>
        `);
        inCallout = false;
        calloutType = "";
        calloutBuffer = [];
      }
    }

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      // Code blocks: ```lang or ~~~lang
      const codeMatch = line.match(/^(\`\`\`|~~~)([\w-]*)/);
      if (codeMatch) {
        flushTable();
        flushCallout();
        if (inCode) {
          const rawCode = codeBuffer.join("\n");
          if (codeLang === "mermaid") {
            out.push(`<div class="mermaid-diagram-wrap"><pre class="mermaid">${escapeHtml(rawCode)}</pre></div>`);
          } else {
            out.push(`
              <div class="editorial-code-block">
                <div class="code-hdr mono">
                  <span class="code-lang">${escapeHtml(codeLang || "text")}</span>
                  <button type="button" class="btn-copy-code mono" data-copy="${escapeHtml(rawCode)}" title="Copy code">Copy</button>
                </div>
                <pre class="code-pre mono"><code>${escapeHtml(rawCode)}</code></pre>
              </div>
            `);
          }
          inCode = false;
          codeLang = "";
          codeBuffer = [];
        } else {
          inCode = true;
          codeLang = codeMatch[2] ? codeMatch[2].trim().toLowerCase() : "";
          codeBuffer = [];
        }
        continue;
      }

      if (inCode) {
        codeBuffer.push(line);
        continue;
      }

      // GFM Callout: > [!NOTE], > [!WARNING], > [!IMPORTANT], > [!TIP], > [!CAUTION]
      const calloutMatch = line.match(/^>\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]/i);
      if (calloutMatch) {
        flushTable();
        flushCallout();
        inCallout = true;
        calloutType = calloutMatch[1];
        calloutBuffer = [];
        continue;
      }

      if (inCallout) {
        if (line.startsWith(">")) {
          calloutBuffer.push(line.replace(/^>\s?/, ""));
          continue;
        } else if (!line.trim()) {
          continue;
        } else {
          flushCallout();
        }
      }

      // Markdown Table
      if (line.trim().startsWith("|") && line.trim().endsWith("|")) {
        tableBuffer.push(line.trim());
        continue;
      } else {
        flushTable();
      }

      // Headings: # H1, ## H2, ### H3, #### H4
      const hMatch = line.match(/^(#{1,6})\s+(.*)/);
      if (hMatch) {
        const level = hMatch[1].length;
        const text = parseInlineMarkdown(hMatch[2]);
        const id = hMatch[2].toLowerCase().replace(/[^\w\s-]/g, "").trim().replace(/\s+/g, "-");
        out.push(`<h${level} id="${id}" class="editorial-h${level}">${text}</h${level}>`);
        continue;
      }

      // Horizontal rule: ---, ***, ___
      if (/^(\*{3,}|-{3,}|_{3,})$/.test(line.trim())) {
        out.push('<hr class="editorial-hr"/>');
        continue;
      }

      // Unordered lists: - item, * item
      const ulMatch = line.match(/^(\s*)([-*+])\s+(.*)/);
      if (ulMatch) {
        out.push(`<li class="editorial-li">${parseInlineMarkdown(ulMatch[3])}</li>`);
        continue;
      }

      // Ordered lists: 1. item
      const olMatch = line.match(/^(\s*)(\d+)\.\s+(.*)/);
      if (olMatch) {
        out.push(`<li class="editorial-li" value="${olMatch[2]}">${parseInlineMarkdown(olMatch[3])}</li>`);
        continue;
      }

      // Blockquotes: > quote
      if (line.startsWith(">")) {
        out.push(`<blockquote class="editorial-blockquote">${parseInlineMarkdown(line.replace(/^>\s?/, ""))}</blockquote>`);
        continue;
      }

      // Empty line
      if (!line.trim()) {
        continue;
      }

      // Paragraph
      out.push(`<p class="editorial-p">${parseInlineMarkdown(line)}</p>`);
    }

    flushTable();
    flushCallout();

    const fullHtml = `
      <article class="editorial-article">
        ${metaBanner}
        ${out.join("\n")}
      </article>
    `;

    return sanitizeHtml(fullHtml);
  }

  function createMarkdownViewer(container, mdText, opts) {
    if (!container) return;
    opts = opts || {};
    const rawContent = mdText || "";
    const renderedHtml = renderMarkdownToEditorialHtml(rawContent, opts);

    container.innerHTML = `
      <div class="editorial-viewer-container">
        <div class="editorial-toolbar">
          <div class="toolbar-left mono">
            <span class="file-name">${escapeHtml(opts.fileName || "document.md")}</span>
            <span class="file-size">${(rawContent.length / 1024).toFixed(1)} KB</span>
          </div>
          <div class="toolbar-right">
            <button type="button" class="view-mode-btn active mono" data-mode="editorial">Editorial HTML</button>
            <button type="button" class="view-mode-btn mono" data-mode="raw">Raw Markdown</button>
            <button type="button" class="view-mode-btn mono" data-mode="print">Printable View</button>
            <button type="button" class="btn-copy-raw btn mono" title="Copy raw markdown">Copy All</button>
          </div>
        </div>
        <div class="editorial-body-view mode-editorial">
          <div class="view-content-editorial">${renderedHtml}</div>
          <textarea class="view-content-raw mono hidden" readonly spellcheck="false">${escapeHtml(rawContent)}</textarea>
        </div>
      </div>
    `;

    const edBody = container.querySelector(".editorial-body-view");
    const edView = container.querySelector(".view-content-editorial");
    const rawView = container.querySelector(".view-content-raw");
    const modeBtns = container.querySelectorAll(".view-mode-btn");

    modeBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        modeBtns.forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        const mode = btn.getAttribute("data-mode");
        if (mode === "raw") {
          edView.classList.add("hidden");
          rawView.classList.remove("hidden");
          edBody.classList.remove("mode-print");
        } else if (mode === "print") {
          edView.classList.remove("hidden");
          rawView.classList.add("hidden");
          edBody.classList.add("mode-print");
          window.print();
        } else {
          edView.classList.remove("hidden");
          rawView.classList.add("hidden");
          edBody.classList.remove("mode-print");
        }
      });
    });

    const copyRawBtn = container.querySelector(".btn-copy-raw");
    if (copyRawBtn) {
      copyRawBtn.addEventListener("click", () => {
        if (typeof copyTextWithFeedback === "function") {
          copyTextWithFeedback(copyRawBtn, rawContent, "Copy All", 1000);
        } else if (navigator.clipboard) {
          navigator.clipboard.writeText(rawContent).then(() => {
            copyRawBtn.textContent = "Copied ✓";
            setTimeout(() => { copyRawBtn.textContent = "Copy All"; }, 1000);
          });
        }
      });
    }

    // Code copy buttons
    container.querySelectorAll(".btn-copy-code").forEach((btn) => {
      btn.addEventListener("click", () => {
        const txt = btn.getAttribute("data-copy") || "";
        if (typeof copyTextWithFeedback === "function") {
          copyTextWithFeedback(btn, txt, "Copy", 1000);
        } else if (navigator.clipboard) {
          navigator.clipboard.writeText(txt).then(() => {
            btn.textContent = "Copied ✓";
            setTimeout(() => { btn.textContent = "Copy"; }, 1000);
          });
        }
      });
    });
  }

  return {
    renderMarkdown: renderMarkdownToEditorialHtml,
    renderMarkdownToEditorialHtml: renderMarkdownToEditorialHtml,
    createMarkdownViewer: createMarkdownViewer,
    sanitizeHtml: sanitizeHtml,
  };
});
