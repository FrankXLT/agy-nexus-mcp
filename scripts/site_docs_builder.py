#!/usr/bin/env python3
"""
scripts/site_docs_builder.py — Pure-Stdlib Markdown Compiler & Public Docs Site Builder.

Compiles repository Markdown documentation, curated plain-language guides, and Quiet UI
CSS-token SVG architecture diagrams into `build/gh-pages/` for the Three-Route Public
Project Site (`./`, `./demo/`, `./docs/`).
"""
from __future__ import annotations

from datetime import datetime, timezone
import html
import json
from pathlib import Path
import posixpath
import re
import shutil
from typing import Any

GITHUB_BLOB_BASE = "https://github.com/FrankXLT/agy-nexus-mcp/blob/main/"
_DOC_SLUG_MAP: dict[str, str] = {
    "README.md": "overview", "GUIDE.md": "quickstart", "HOW_IT_IS_BUILT.md": "how-it-is-built",
    "DEPLOYMENT.md": "deployment", "PRICING_HISTORY.md": "pricing", "WORKFLOWS.md": "workflows",
    "DISCOVERABILITY.md": "discoverability", "QUIET_UI_V9_FIELD_REPORT.md": "changelog",
    "CHANGELOG.md": "changelog", "CHANGELOG_ARCHIVE.md": "changelog",
}
_CALLOUT_TONES: dict[str, tuple[str, str]] = {
    "NOTE": ("note", "Note"), "TIP": ("tip", "Tip"), "IMPORTANT": ("important", "Important"),
    "WARNING": ("warn", "Warning"), "CAUTION": ("danger", "Caution"),
}
_HEADING_RE = re.compile(r"^(#{1,4})\s+(.*?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^```([A-Za-z0-9_+-]*)\s*$")
_UL_RE = re.compile(r"^(\s*)[-*+]\s+(.*)$")
_OL_RE = re.compile(r"^(\s*)\d+\.\s+(.*)$")
_TASK_RE = re.compile(r"^\[([ xX])\]\s+(.*)$")
_CALLOUT_RE = re.compile(r"^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*(.*)$", re.I)


def _slugify(text: str, used_ids: set[str]) -> str:
    clean = re.sub(r"`([^`]*)`", r"\1", re.sub(r"<[^>]+>", "", text))
    base = re.sub(r"[^a-z0-9]+", "-", clean.lower()).strip("-") or "section"
    cand, idx = base, 2
    while cand in used_ids:
        cand, idx = f"{base}-{idx}", idx + 1
    used_ids.add(cand)
    return cand


def _rewrite_doc_url(raw_url: str, source_rel: str, *, is_image: bool) -> tuple[str, bool]:
    url = raw_url.strip().split()[0] if raw_url.strip() else ""
    if not url or url.startswith(("http://", "https://", "mailto:")):
        return url, url.startswith(("http://", "https://"))
    if url.startswith("#"):
        return url, False
    if url in {"./demo/", "../demo/"} or url.startswith("./demo/#"):
        return ("../demo/" + url.split("./demo/", 1)[1]), False
    if url in {"./docs/", "../docs/"}:
        return "./", False
    base_part, sep, frag = url.partition("#")
    norm = posixpath.normpath(posixpath.join(posixpath.dirname(source_rel), base_part)) if base_part else ""
    if norm.startswith("./"):
        norm = norm[2:]
    if is_image:
        fname = posixpath.basename(norm)
        if fname.startswith("demo_thumb_"):
            return f"../demo/{fname}", False
        if "assets/" in norm or norm.startswith("docs/assets/"):
            return f"../assets/{fname}", False
        return f"{GITHUB_BLOB_BASE}{norm}", True
    fname = posixpath.basename(norm)
    if fname in _DOC_SLUG_MAP and norm in {fname, f"docs/{fname}"}:
        return f"#doc-{_DOC_SLUG_MAP[fname]}", False
    if norm in {"", "."} and sep:
        return f"#{frag}", False
    target = f"{GITHUB_BLOB_BASE}{norm.lstrip('/')}" + (f"#{frag}" if frag else "")
    return target, True


def _apply_emphasis(text: str) -> str:
    text = re.sub(r"\*\*([^\n*]+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__([^\n_]+?)__", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^\n*]+?)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"(?<![A-Za-z0-9_])_([^\n_]+?)_(?![A-Za-z0-9_])", r"<em>\1</em>", text)
    return re.sub(r"~~([^\n~]+?)~~", r"<del>\1</del>", text)


def _stash_code_pair(m: re.Match[str], slots: list[str]) -> str:
    raw = m.group(1) if m.group(1) is not None else (m.group(2) or "")
    slots.append(f"<code>{html.escape(raw, quote=False)}</code>")
    return f"\x00CODE{len(slots) - 1}\x00"


def _render_inline(text: str, source_rel: str) -> str:
    code_slots: list[str] = []
    link_slots: list[str] = []
    work = html.escape(re.sub(r"``([^`]+)``|`([^`\n]+)`", lambda m: _stash_code_pair(m, code_slots), text), quote=False)

    def _stash_img(m: re.Match[str]) -> str:
        raw_alt = html.unescape(re.sub(r"\x00CODE\d+\x00", "", m.group(1)))
        raw_src = html.unescape(m.group(2))
        src, _ = _rewrite_doc_url(raw_src, source_rel, is_image=True)
        link_slots.append(f'<img src="{html.escape(src, quote=True)}" alt="{html.escape(raw_alt, quote=True)}" loading="lazy" decoding="async" />')
        return f"\x00LINK{len(link_slots) - 1}\x00"

    def _stash_link(m: re.Match[str]) -> str:
        raw_href = html.unescape(m.group(2))
        href, is_ext = _rewrite_doc_url(raw_href, source_rel, is_image=False)
        rel_attr = ' rel="noopener noreferrer"' if is_ext else ""
        link_slots.append(f'<a href="{html.escape(href, quote=True)}"{rel_attr}>{_apply_emphasis(m.group(1))}</a>')
        return f"\x00LINK{len(link_slots) - 1}\x00"

    work = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _stash_img, work)
    work = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _stash_link, work)
    work = re.sub(r"  \n", "<br />\n", _apply_emphasis(work))
    while re.search(r"\x00LINK\d+\x00", work):
        work = re.sub(r"\x00LINK(\d+)\x00", lambda m: link_slots[int(m.group(1))], work)
    return re.sub(r"\x00CODE(\d+)\x00", lambda m: code_slots[int(m.group(1))], work)


def _split_pipe_row(line: str) -> list[str]:
    s = line.strip().removeprefix("|").removesuffix("|")
    return [cell.replace(r"\|", "|").strip() for cell in re.split(r"(?<!\\)\|", s)]


def _is_table_sep(line: str) -> bool:
    cells = _split_pipe_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", c.strip()) for c in cells)


def _parse_fenced_code(lines: list[str], idx: int, base_indent: int = 0) -> tuple[str, int]:
    m = _FENCE_RE.match(lines[idx][base_indent:] if len(lines[idx]) >= base_indent else lines[idx])
    lang = m.group(1) if m else ""
    i, buf = idx + 1, []
    while i < len(lines):
        raw = lines[i]
        stripped = raw[base_indent:] if raw.startswith(" " * base_indent) else raw.lstrip()
        if stripped.strip() == "```":
            i += 1
            break
        buf.append(raw[base_indent:] if raw.startswith(" " * base_indent) else raw)
        i += 1
    cls = f' class="language-{html.escape(lang, quote=True)}"' if lang else ""
    return f"<pre><code{cls}>{html.escape(chr(10).join(buf), quote=False)}</code></pre>", i


def _parse_svg_block(lines: list[str], idx: int) -> tuple[str, int]:
    buf, i = [], idx
    while i < len(lines):
        ln = lines[i]
        if "</svg>" in ln:
            buf.append(ln.split("</svg>", 1)[0] + "</svg>")
            i += 1
            break
        buf.append(ln)
        i += 1
    svg_raw = re.sub(r"<(?:script|foreignObject|animate|set|iframe)\b[\s\S]*?</(?:script|foreignObject|animate|set|iframe)>", "", "\n".join(buf), flags=re.I)
    svg_raw = re.sub(r"\s+on[a-z]+\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)", "", svg_raw, flags=re.I)
    svg_raw = re.sub(r"(?:javascript|vbscript):", "", svg_raw, flags=re.I)
    aria = re.search(r'aria-label="([^"]+)"', svg_raw)
    cap = f"<figcaption>{html.escape(html.unescape(aria.group(1)), quote=False)}</figcaption>" if aria else ""
    return f'<figure class="doc-diagram-frame">{svg_raw}{cap}</figure>', i


def _parse_table(lines: list[str], idx: int, src: str) -> tuple[str, int]:
    headers = _split_pipe_row(lines[idx])
    i, rows = idx + 2, []
    while i < len(lines) and "|" in lines[i] and lines[i].strip():
        rows.append(_split_pipe_row(lines[i]))
        i += 1
    ths = "".join(f"<th>{_render_inline(h, src)}</th>" for h in headers)
    body = []
    for row in rows:
        padded = row + [""] * max(0, len(headers) - len(row))
        body.append("<tr>" + "".join(f"<td>{_render_inline(c, src)}</td>" for c in padded[: len(headers)]) + "</tr>")
    return (
        '<div class="doc-table-wrap" tabindex="0" role="region" aria-label="Reference table">'
        f"<table><thead><tr>{ths}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
    ), i


def _parse_blockquote(lines: list[str], idx: int, src: str) -> tuple[str, int]:
    q_lines, i = [], idx
    while i < len(lines) and lines[i].lstrip().startswith(">"):
        q_lines.append(re.sub(r"^\s*>\s?", "", lines[i]))
        i += 1
    tone_attr, parts = "", []
    if q_lines and (cm := _CALLOUT_RE.match(q_lines[0].strip())):
        tone, label = _CALLOUT_TONES[cm.group(1).upper()]
        tone_attr = f' class="docs-callout" data-tone="{tone}"'
        parts.append(f'<p class="docs-callout-title"><strong>{label}</strong></p>')
        q_lines[0] = cm.group(2).strip()
    for p in (p.strip() for p in "\n".join(q_lines).split("\n\n") if p.strip()):
        parts.append(f"<p>{_render_inline(p, src)}</p>")
    return f"<blockquote{tone_attr}>{''.join(parts)}</blockquote>", i


def _parse_list(lines: list[str], idx: int, src: str) -> tuple[str, int]:
    first_ul = _UL_RE.match(lines[idx])
    ordered = first_ul is None
    base_indent = len((first_ul or _OL_RE.match(lines[idx])).group(1))
    items: list[str] = []
    has_task, i = False, idx
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            if i + 1 < len(lines) and (_UL_RE.match(lines[i + 1]) or _OL_RE.match(lines[i + 1])):
                i += 1
                continue
            break
        m = (_OL_RE if ordered else _UL_RE).match(line)
        if not m or len(m.group(1)) != base_indent:
            break
        item_lines, sub_blocks, i = [m.group(2)], [], i + 1
        while i < len(lines) and lines[i].strip():
            nxt = lines[i]
            nm_ul, nm_ol = _UL_RE.match(nxt), _OL_RE.match(nxt)
            if (nm_ul and len(nm_ul.group(1)) > base_indent) or (nm_ol and len(nm_ol.group(1)) > base_indent):
                sub_html, i = _parse_list(lines, i, src)
                sub_blocks.append(sub_html)
                continue
            ind = len(nxt) - len(nxt.lstrip(" "))
            if ind >= base_indent + 2 and _FENCE_RE.match(nxt.lstrip()):
                code_html, i = _parse_fenced_code(lines, i, ind)
                sub_blocks.append(code_html)
                continue
            if ind >= base_indent + 2 and not nm_ul and not nm_ol:
                (sub_blocks.append(f"<p>{_render_inline(nxt.strip(), src)}</p>") if sub_blocks else item_lines.append(nxt.strip()))
                i += 1
                continue
            break
        tm = _TASK_RE.match(item_lines[0]) if not ordered else None
        if tm:
            has_task = True
            chk = " checked" if tm.group(1).lower() == "x" else ""
            txt = _render_inline(" ".join([tm.group(2)] + item_lines[1:]), src)
            items.append(f'<li class="task-list-item"><input type="checkbox" disabled{chk} /><span>{txt}</span>{"".join(sub_blocks)}</li>')
        else:
            items.append(f'<li>{_render_inline(" ".join(item_lines), src)}{"".join(sub_blocks)}</li>')
    tag = "ol" if ordered else "ul"
    return f'<{tag}{" class=\"contains-task-list\"" if has_task else ""}>{"".join(items)}</{tag}>', i


def _is_block_start(lines: list[str], i: int) -> bool:
    s = lines[i].strip()
    if not s or _FENCE_RE.match(s) or _HEADING_RE.match(lines[i]) or _UL_RE.match(lines[i]) or _OL_RE.match(lines[i]):
        return True
    if s.startswith((">", "<svg", "<details", "</details>", "---", "***")):
        return True
    return i + 1 < len(lines) and "|" in lines[i] and _is_table_sep(lines[i + 1])


def markdown_to_html(
    md_text: str, *, source_rel: str, used_ids: set[str], skip_top_h1: bool = True, heading_shift: int = 0,
) -> str:
    """Compile GitHub-flavored Markdown + inline SVG blocks into Quiet UI docs HTML."""
    lines = re.sub(r"<!--[\s\S]*?-->", "", md_text.replace("\r\n", "\n")).splitlines()
    out: list[str] = []
    i, skipped_h1 = 0, False
    while i < len(lines):
        raw, s = lines[i], lines[i].strip()
        if not s:
            i += 1
        elif _FENCE_RE.match(s):
            blk, i = _parse_fenced_code(lines, i, len(raw) - len(raw.lstrip(" ")))
            out.append(blk)
        elif s.startswith("<svg"):
            blk, i = _parse_svg_block(lines, i)
            out.append(blk)
        elif s in {"<details>", "</details>"}:
            out.append(s)
            i += 1
        elif s.startswith("<summary>") and s.endswith("</summary>"):
            out.append(f"<summary>{_render_inline(s[9:-10], source_rel)}</summary>")
            i += 1
        elif re.fullmatch(r"[-*_]{3,}", s):
            out.append("<hr />")
            i += 1
        elif (hm := _HEADING_RE.match(raw)):
            lvl = len(hm.group(1))
            if skip_top_h1 and lvl == 1 and not skipped_h1:
                skipped_h1, i = True, i + 1
                continue
            shifted = max(2, min(4, lvl + heading_shift))
            out.append(f'<h{shifted} id="{_slugify(hm.group(2), used_ids)}">{_render_inline(hm.group(2), source_rel)}</h{shifted}>')
            i += 1
        elif i + 1 < len(lines) and "|" in raw and _is_table_sep(lines[i + 1]):
            blk, i = _parse_table(lines, i, source_rel)
            out.append(blk)
        elif raw.lstrip().startswith(">"):
            blk, i = _parse_blockquote(lines, i, source_rel)
            out.append(blk)
        elif _UL_RE.match(raw) or _OL_RE.match(raw):
            blk, i = _parse_list(lines, i, source_rel)
            out.append(blk)
        else:
            p_lines = [s]
            i += 1
            while i < len(lines) and not _is_block_start(lines, i):
                p_lines.append(lines[i].strip())
                i += 1
            out.append(f"<p>{_render_inline(chr(10).join(p_lines), source_rel)}</p>")
    return "\n".join(out)


def _html_to_plain_text(html_str: str) -> str:
    no_svg = re.sub(r"<svg[\s\S]*?</svg>", " ", html_str)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", no_svg))).strip()


def _render_token_svg(
    title: str, accent_var: str, pfx: str, boxes: list[tuple[int, int, int, int, str, str, list[str]]],
    arrows: list[tuple[int, int, int, int, str]], height: int,
) -> str:
    parts = [
        f'<svg viewBox="0 0 880 {height}" width="100%" role="img" aria-label="{html.escape(title, quote=True)}" xmlns="http://www.w3.org/2000/svg">',
        f'<defs><marker id="{pfx}-p" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 1 1 L 9 5 L 1 9 z" fill="var(--accent-primary)" /></marker>'
        f'<marker id="{pfx}-ok" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 1 1 L 9 5 L 1 9 z" fill="var(--status-ok)" /></marker></defs>',
        f'<rect x="2" y="2" width="876" height="{height - 4}" rx="10" fill="var(--bg-surface)" stroke="var(--border-subtle)" stroke-width="1.5" />',
        f'<rect x="2" y="2" width="876" height="4" rx="2" fill="var({accent_var})" />',
        f'<text x="22" y="32" font-family="sans-serif" font-size="13" font-weight="700" fill="var(--text-primary)">{html.escape(title, quote=False)}</text>',
    ]
    for x, y, w, h, fill_v, stroke_v, lines_txt in boxes:
        sw = ' stroke-width="1.5"' if stroke_v in {"--accent-primary", "--status-ok"} else ""
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="var({fill_v})" stroke="var({stroke_v})"{sw} />')
        parts.append(f'<text x="{x + 16}" y="{y + 24}" font-family="sans-serif" font-size="12" font-weight="700" fill="var(--text-primary)">{html.escape(lines_txt[0], quote=False)}</text>')
        for idx, sub in enumerate(lines_txt[1:]):
            fam = "monospace" if idx < 2 else "sans-serif"
            parts.append(f'<text x="{x + 16}" y="{y + 44 + idx * 19}" font-family="{fam}" font-size="10.5" fill="var(--text-secondary)">{html.escape(sub, quote=False)}</text>')
    for x1, y1, x2, y2, kind in arrows:
        col = "--accent-primary" if kind == "p" else "--status-ok"
        parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="var({col})" stroke-width="1.8" marker-end="url(#{pfx}-{kind})" />')
    parts.append("</svg>")
    return "".join(parts)


def _build_architecture_svgs() -> tuple[str, str]:
    doorway_svg = _render_token_svg(
        "Two-Doorway Setup & Thirty-Minute Passphrase Lock", "--accent-primary", "arch",
        [
            (22, 54, 210, 96, "--bg-elevated", "--border-strong", ["Gemini Web & Mobile", "/{PATH_SECRET}/mcp", "Remote HTTPS Doorway", "ag-bridge-mcp (:8765)"]),
            (22, 172, 210, 96, "--bg-elevated", "--border-strong", ["Antigravity IDE & CLI", "/praxis/{TOKEN}/mcp", "Local LAN / --stdio Mode", "403 Proxy & Origin Guard"]),
            (296, 54, 268, 96, "--bg-surface", "--accent-primary", ["Thirty-Minute Passphrase Lock", "PASS_HASH + compare_digest", "TTL_SECONDS=1800 (min 300s)", "Fail-Closed Until Unlock"]),
            (296, 172, 268, 96, "--bg-surface", "--status-ok", ["Local Code Index & Handoffs", "polyglot_map / outline / search", "<repo-slug>-NN Queue", "No Passphrase on LAN"]),
            (628, 54, 230, 214, "--bg-elevated", "--border-strong", ["Workstation & Companion", "127.0.0.1:8098 Host Bridge", "conversation_summaries.db?mode=ro", "< 20 KB Wire Compaction", "7-Day HMAC /web/media/ URLs", "840px WebP + Studio /web"]),
        ],
        [(232, 102, 294, 102, "p"), (232, 220, 294, 220, "ok"), (564, 102, 626, 102, "p"), (564, 220, 626, 220, "ok")],
        296,
    )
    routing_svg = _render_token_svg(
        "Dual-Pool Quota & Model Routing Check", "--status-ok", "dp",
        [
            (22, 54, 232, 202, "--bg-elevated", "--border-strong", ["Quota & Resets % Left", "100% -> 0% Remaining Bars", "OK (>=25%) | LOW | NEAR", "resets in 4h 0m / Weekly", "model_catalog + cost_ledger", "Plus / Pro / Ultra 5x & 20x"]),
            (312, 54, 244, 92, "--bg-surface", "--accent-primary", ["Google 20x Pool (Primary)", "Flash 3.8 / Hydrogen / Neon", "Argon / Carbon 4 (0% Partner)", "Routine Scouts & Mode A"]),
            (312, 164, 244, 92, "--bg-surface", "--border-strong", ["Partner 1x Pool (Reserved)", "Claude Opus 5.5 / Sonnet 5.5", "GPT-OSS 120B Failover", "Strike-2 & Security Review"]),
            (614, 54, 244, 202, "--bg-elevated", "--status-ok", ["Model Routing Check", "quota-router.sh status|route", "Intended targetModel vs Actual", "Inherited Fallback Flag", "12 Canonical Subagents", "Visible in /web & ASCII"]),
        ],
        [(254, 100, 310, 100, "p"), (254, 210, 310, 210, "ok"), (556, 100, 612, 120, "p"), (556, 210, 612, 190, "ok")],
        286,
    )
    return doorway_svg, routing_svg


def _make_chapter(slug: str, title: str, group: str, summary: str, keywords: list[str], body_html: str) -> dict[str, Any]:
    return {
        "slug": slug, "id": f"doc-{slug}", "title": title, "group": group,
        "summary": summary, "keywords": keywords, "html": body_html, "plainText": _html_to_plain_text(body_html),
    }


def _build_common_terms_chapter(used_ids: set[str]) -> dict[str, Any]:
    md = "\n".join([
        "Every concept in AGY-Nexus MCP has a plain-language meaning alongside its configuration key or UI element.", "",
        "| Plain-Language Term | Technical Equivalent | What It Means in Practice |",
        "| :--- | :--- | :--- |",
        "| **Two-Doorway Setup** | `ag-bridge-mcp` + `agy-praxis-mcp` | Separates the remote HTTPS doorway (`/{PATH_SECRET}/mcp` for phone/web Gemini) from the local LAN-only IDE doorway (`/praxis/{PRAXIS_MCP_TOKEN}/mcp` and `--stdio`), blocking proxy headers with `403`. |",
        "| **Thirty-Minute Passphrase Lock** | `TTL_SECONDS=1800` + `PASS_HASH` | Protects private files, git diffs, and transcripts with a SHA-256 voice-normalized passphrase (`300s` minimum floor, `7200s` default) that re-locks automatically on idle. |",
        "| **Quota & Resets Percentage Left** | Card 4 `quota_and_resets` (`100%` -> `0%`) | Shows remaining pool capacity with `OK` (`>=25%` left), `LOW LEFT` (`10%–24.9%`), and `NEAR LIMIT` (`<10%` or cooldown) pills plus `resets in ...` countdowns and subscription API comparison. |",
        "| **Model Routing Check** | `quota-router.sh` + `targetModel` vs actual | Checks pool health before dispatching subagents and flags when `model: inherit` redirected a subagent to another main-chat model or an unmapped `M*` code appeared. |",
        "| **Portfolio Header Switcher** | `46px` `.oaw-topbar` across all 3 routes | Sticky top bar with `OAW Projects`, two-stage `Antigravity Nexus` dropdown, `Overview`/`Demo`/`Docs` underline tabs, 9-dot pillar switcher, and `@FrankXLT` 4-theme menu. |",
        "| **Search Topics** | Live `#docsSearchInput` & 14 registry tags | Instant client-side keyword filtering across every doc chapter on `./docs/` plus 14 curated GitHub and MCP Registry discovery topics. |",
        "| **Carets (`▾`)** | Trailing `24h` / `700`-step bar markers | Downward triangle markers above table bars indicating trailing `24h` share/burn (on Model Workload and Token/$ Project Sessions) or the `700`-step rollover seam (on Steps). |",
        "| **Range Whiskers** | `Min–Max` span + `│` Avg + `●` Last 24h | Horizontal table ranges and vertical hourly I-beam whiskers showing active-day `Min–Max` spread, average tick, and trailing `24h` dot. |", "",
        "> [!TIP]",
        "> Jump straight to [Architecture](#doc-architecture) for visual diagrams of both doorways and quota pools, or [Deployment](#doc-deployment) to configure `TTL_SECONDS=1800`.",
    ])
    body_html = markdown_to_html(md, source_rel="docs/GUIDE.md", used_ids=used_ids, skip_top_h1=False)
    return _make_chapter(
        "common-terms", "Common Terms Translated", "Plain-Language Concepts",
        "Everyday translations for Two-Doorway Setup, Thirty-Minute Passphrase Lock, Quota & Resets Percentage Left, Model Routing Check, Carets, and Range Whiskers.",
        ["Two-Doorway Setup", "Thirty-Minute Passphrase Lock", "Quota & Resets", "Model Routing Check", "Portfolio Header Switcher", "Search Topics", "Carets", "Range Whiskers", "PASS_HASH"],
        body_html,
    )


def _build_architecture_chapter(used_ids: set[str]) -> dict[str, Any]:
    doorway_svg, routing_svg = _build_architecture_svgs()
    intro_md = (
        "AGY-Nexus MCP splits remote control from local IDE indexing so neither surface carries unnecessary risk or token overhead.\n\n"
        "## Two-Doorway Isolation & Passphrase Deadbolt\n"
        "- **External Doorway (`ag-bridge-mcp`)**: Accepts stateless Streamable HTTP calls on `/{PATH_SECRET}/mcp` behind a 12-character subdomain hash and requires `PASS_HASH` verification (supporting spoken phrases) before private reads or handoffs execute.\n"
        "- **Internal IDE Doorway (`agy-praxis-mcp`)**: Serves `polyglot_map`, `polyglot_search`, `polyglot_outline`, and `<repo-slug>-NN` handoff queues locally on `/praxis/{PRAXIS_MCP_TOKEN}/mcp` or `--stdio`, rejecting reverse-proxy headers and browser origins with `403`.\n"
        "- **Host Companion (`127.0.0.1:8098`)**: Bridges Antigravity Language Server discovery, `CreateProject` RPC, and `agentapi` wakeups behind `X-Bridge-Token`."
    )
    routing_md = (
        "## Dual-Pool Quota & Model Routing Check\n"
        "- **Google 20x Pool vs. Partner 1x Pool**: Keeps high-volume reconnaissance, documentation, and mechanical edits on `Flash 3.8`, `Hydrogen`, `Neon`, and `Argon` / `Carbon 4`, preserving `Claude Opus 5.5` and `Sonnet 5.5` for Strike-2 escalations and security review.\n"
        "- **Quota & Resets Gauges**: Tracks `100%` down to `0%` remaining capacity alongside reset countdowns and effective-dated two-file Price Book rates (`model_catalog.json` + `cost_ledger.json`).\n"
        "- **Next**: Dive into [How It Is Built](#doc-how-it-is-built) for module line budgets, `< 20 KB` wire compaction, and SQLite isolation internals."
    )
    full_html = "\n".join([
        markdown_to_html(intro_md, source_rel="docs/HOW_IT_IS_BUILT.md", used_ids=used_ids, skip_top_h1=False),
        f'<figure class="doc-diagram-frame">{doorway_svg}<figcaption>Two-Doorway Setup &amp; Thirty-Minute Passphrase Lock</figcaption></figure>',
        markdown_to_html(routing_md, source_rel="docs/HOW_IT_IS_BUILT.md", used_ids=used_ids, skip_top_h1=False),
        f'<figure class="doc-diagram-frame">{routing_svg}<figcaption>Dual-Pool Quota &amp; Model Routing Check</figcaption></figure>',
    ])
    return _make_chapter(
        "architecture", "Architecture & Data Flow", "How It Works",
        "Visual tour of the Two-Doorway Setup, Thirty-Minute Passphrase Lock, Dual-Pool Quota gauges, and Model Routing Check.",
        ["architecture", "two-doorway", "praxis", "passphrase", "routing", "quota", "dual-pool", "svg"],
        full_html,
    )


def _compile_file_chapter(repo_root: Path, spec: tuple[str, str, str, str, list[str], str], used_ids: set[str]) -> dict[str, Any]:
    slug, title, group, rel_path, keywords, summary = spec
    body_html = markdown_to_html((repo_root / rel_path).read_text(encoding="utf-8"), source_rel=rel_path, used_ids=used_ids, skip_top_h1=True)
    return _make_chapter(slug, title, group, summary, keywords, body_html)


def _build_changelog_chapter(repo_root: Path, used_ids: set[str]) -> dict[str, Any]:
    parts = [
        markdown_to_html((repo_root / rel).read_text(encoding="utf-8"), source_rel=rel, used_ids=used_ids, skip_top_h1=False, heading_shift=1)
        for rel in ("CHANGELOG.md", "docs/QUIET_UI_V9_FIELD_REPORT.md", "docs/CHANGELOG_ARCHIVE.md")
    ]
    return _make_chapter(
        "changelog", "Changelog & Quiet UI Field Report", "Release & History",
        "Full release history (v1.0.0 through v4.2.0) alongside the Quiet UI v9.3.0 visual grammar and production parity report.",
        ["changelog", "v4.2.0", "quiet ui", "field report", "archive", "release notes"],
        "\n<hr />\n".join(parts),
    )


def build_docs_data(repo_root: Path, version: str) -> dict[str, Any]:
    """Compile all 10 curated documentation chapters into the `AGY_DOCS_DATA` payload."""
    used_ids: set[str] = {
        "doc-overview", "doc-quickstart", "doc-common-terms", "doc-architecture", "doc-how-it-is-built",
        "doc-deployment", "doc-pricing", "doc-workflows", "doc-discoverability", "doc-changelog",
        "oawTopbar", "btnContextSwitcher", "oawContextPopover", "btnViewSwitcher", "oawViewMenu",
        "btnGlobalSearch", "oawSearchDialog", "btnPillarSwitcher", "oawPillarPopover", "btnUserMenu",
        "oawUserPopover", "mainContent", "docsMobileSubbar", "docsCurrentChapterTitle",
        "docsTocNav", "docsTocList", "docsArticleHost",
        "docsTocDialog", "docsTocDialogTitle", "docsTocModalNav", "docsTocModalList", "docsTocToggle",
        "docsSearchInput", "docsSearchClearBtn", "docsSearchStatus", "docsEmptyState", "docsEmptyQuery",
        "docsResetSearchBtn", "docsHeroMeta", "docsPager",
    }
    specs: list[Any] = [
        ("overview", "Project Overview", "Getting Started", "README.md", ["overview", "stdio", "mcp", "bridge", "agplv3"], "Three everyday payoffs, container quickstart, 17 MCP tools, and live Studio preview."),
        ("quickstart", "Quickstart & Plain-Language Guide", "Getting Started", "docs/GUIDE.md", ["quickstart", "guide", "PASS_HASH", "TTL_SECONDS", "routing"], "Plain-language introduction, doorway selection table, and first-time verification checks."),
        _build_common_terms_chapter,
        _build_architecture_chapter,
        ("how-it-is-built", "How It Is Built", "How It Works", "docs/HOW_IT_IS_BUILT.md", ["internals", "wire budget", "polyglot", "sqlite", "hmac", "praxis"], "Modular <=500L layout, BridgeCompatMiddleware, <20 KB compaction, and 13-agent routing."),
        ("deployment", "Setup & Deployment", "Operations & Reference", "docs/DEPLOYMENT.md", ["docker", "systemd", "nginx", "cloudflare", "172.17.0.1", "init_secrets"], "Secrets setup, host companion service, Docker/systemd, reverse proxy headers, and GHCR --stdio."),
        ("pricing", "Price Book & Rate History", "Operations & Reference", "docs/PRICING_HISTORY.md", ["pricing", "tiers", "ultra", "pro", "plus", "rate epochs"], "Official subscription tiers and effective-dated API rate epochs from the two-file Price Book."),
        ("workflows", "Workflows & Operational Baseline", "Operations & Reference", "docs/WORKFLOWS.md", ["workflows", "WF-01", "handoff", "catalog", "ci", "oidc"], "End-to-end user journeys WF-01 through WF-09 from mobile voice check-ins to release closeout."),
        ("discoverability", "Discoverability & Release Metadata", "Release & History", "docs/DISCOVERABILITY.md", ["topics", "registry", "server.json", "social preview", "metadata"], "Repository summary, 14 GitHub search topics, registry URLs, and manifest alignment checklist."),
        lambda ids: _build_changelog_chapter(repo_root, ids),
    ]
    chapters = [entry(used_ids) if callable(entry) else _compile_file_chapter(repo_root, entry, used_ids) for entry in specs]
    return {"version": version, "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "chapters": chapters}


def build_site_pages(repo_root: Path, out_dir: Path, version: str) -> dict[str, Any]:
    """Emit Overview (`./`), Docs shell (`./docs/`), shared site assets, and `docs_data.js`."""
    site_dir, assets_out, docs_out = repo_root / "web" / "site", out_dir / "assets", out_dir / "docs"
    assets_out.mkdir(parents=True, exist_ok=True)
    docs_out.mkdir(parents=True, exist_ok=True)

    ver_pat = re.compile(r"((?:v9_layers|quiet-ui-tokens|oaw_topbar|oaw_search|site_shell|docs|docs_data|docs_app)\.(?:css|js))\?v=[^\"'\s>]+")
    (out_dir / "index.html").write_text(ver_pat.sub(rf"\1?v={version}", (site_dir / "index.html").read_text(encoding="utf-8")), encoding="utf-8")
    (docs_out / "index.html").write_text(ver_pat.sub(rf"\1?v={version}", (site_dir / "docs.html").read_text(encoding="utf-8")), encoding="utf-8")
    for asset_name in ("oaw_topbar.css", "oaw_search.css", "oaw_search.js", "site_shell.css", "site_shell.js", "docs.css", "docs_app.js"):
        shutil.copy2(site_dir / asset_name, assets_out / asset_name)

    data = build_docs_data(repo_root, version)
    json_payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    docs_js = f"/* AGY-Nexus Public Docs Data v{version} */\nwindow.AGY_DOCS_DATA = {json_payload};\n"
    (docs_out / "docs_data.js").write_text(docs_js, encoding="utf-8")
    return {"chapters": len(data["chapters"]), "docs_data_bytes": len(docs_js.encode("utf-8"))}
