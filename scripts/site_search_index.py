"""
scripts/site_search_index.py — Static Search Index Builder for Antigravity Nexus.

Builds `search-index.json` indexing:
  - Overview sections and cards parsed from `web/site/index.html`
  - Live Demo views & capabilities (`Analytics`, `Workspace`, `Session Gallery`, `Heatmap`, `Hierarchy`)
  - All compiled Docs chapters (`./docs/#doc-*`) and subsections from `docs_data["chapters"]`
"""
from __future__ import annotations

import html
import json
import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

CANONICAL_BASE = "https://projects.oaworkbench.org/agy-nexus-mcp/"
_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
    "in", "into", "is", "it", "of", "on", "or", "that", "the", "this", "to",
    "with", "your", "you", "all", "can", "per", "via", "vs",
})


def _clean_text(raw: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(raw or "")).strip()


def _truncate(text: str, limit: int = 180) -> str:
    clean = _clean_text(text)
    if len(clean) <= limit:
        return clean
    cut = clean[: limit - 3].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return (cut or clean[: limit - 3]) + "..."


def _strip_html(raw_html: str) -> str:
    return _clean_text(re.sub(r"<[^>]+>", " ", re.sub(r"<svg[\s\S]*?</svg>", " ", raw_html)))


_URL_COORD_RE = re.compile(
    r"(?:https?://|ghcr\.io/|io\.github\.|raw\.githubusercontent\.com/|github\.com/)[^\s)\],;\"']+"
)


def _tokenize(*parts: str, extra: list[str] | None = None, limit: int = 14) -> list[str]:
    seen: set[str] = set()
    tokens: list[str] = []
    for raw in list(extra or []) + list(parts):
        cleaned = _URL_COORD_RE.sub(" ", str(raw or ""))
        for tok in re.findall(r"[A-Za-z0-9][A-Za-z0-9._+-]{1,}", cleaned):
            low = tok.lower().strip("._+-")
            if len(low) < 2 or low in _STOPWORDS or low in seen:
                continue
            seen.add(low)
            tokens.append(low)
            if len(tokens) >= limit:
                return tokens
    return tokens


def _make_item(item_id: str, title: str, summary: str, section: str, path: str, keywords: list[str]) -> dict[str, Any]:
    rel_path = path if path.startswith("./") else f"./{path.lstrip('/')}"
    return {
        "id": item_id,
        "title": _clean_text(title),
        "summary": _truncate(summary, 180),
        "section": section,
        "scope": "projects",
        "pillar": "Projects",
        "project": "Antigravity Nexus",
        "path": rel_path,
        "url": CANONICAL_BASE + rel_path[2:],
        "keywords": keywords,
    }


class _OverviewHtmlParser(HTMLParser):
    """Extract headings (h1-h3), their section/element IDs, and paired paragraph summaries inside <main>."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_main = False
        self.skip_depth = 0
        self.el_stack: list[tuple[str, str, bool, bool]] = []
        self.active_heading: dict[str, Any] | None = None
        self.active_p: list[str] | None = None
        self.active_term: list[str] | None = None
        self.pending_term = ""
        self.entries: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "main":
            self.in_main = True
            return
        if not self.in_main:
            return
        if tag in {"svg", "script", "style", "pre"}:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        attr_map = {k: (v or "") for k, v in attrs}
        el_id, classes = attr_map.get("id", "").strip(), set(attr_map.get("class", "").split())
        is_sec = tag == "section"
        is_card = tag == "article" or bool(classes & {"payoff-card", "bridge-card", "how-step-item"})
        self.el_stack.append((tag, el_id, is_sec, is_card))
        if is_sec:
            self.pending_term = ""
        if tag == "span" and "bridge-term" in classes:
            self.active_term = []
        if tag in {"h1", "h2", "h3"}:
            sec_id = next((eid for _t, eid, sec, _c in reversed(self.el_stack) if sec and eid), "")
            card_id = next((eid for _t, eid, _s, crd in reversed(self.el_stack) if crd and eid), "")
            self.active_heading = {
                "tag": tag, "id": el_id, "section_id": sec_id,
                "card_id": card_id, "term": self.pending_term, "buf": [],
            }
            self.pending_term = ""
        elif tag == "p" and self.entries and not self.entries[-1]["summary"]:
            self.active_p = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "main":
            self.in_main = False
            self.el_stack.clear()
            return
        if not self.in_main:
            return
        if tag in {"svg", "script", "style", "pre"}:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth:
            return
        if tag == "span" and self.active_term is not None:
            self.pending_term = _clean_text("".join(self.active_term))
            self.active_term = None
        elif tag in {"h1", "h2", "h3"} and self.active_heading is not None:
            title = _clean_text("".join(self.active_heading["buf"]))
            if title:
                self.entries.append({
                    "tag": self.active_heading["tag"], "id": self.active_heading["id"],
                    "section_id": self.active_heading["section_id"], "card_id": self.active_heading["card_id"],
                    "term": self.active_heading["term"], "title": title, "summary": "",
                })
            self.active_heading = None
        elif tag == "p" and self.active_p is not None:
            if self.entries and not self.entries[-1]["summary"]:
                self.entries[-1]["summary"] = _clean_text("".join(self.active_p))
            self.active_p = None
        for idx in range(len(self.el_stack) - 1, -1, -1):
            if self.el_stack[idx][0] == tag:
                del self.el_stack[idx:]
                break

    def handle_data(self, data: str) -> None:
        if not self.in_main or self.skip_depth:
            return
        if self.active_heading is not None:
            self.active_heading["buf"].append(data)
        elif self.active_p is not None:
            self.active_p.append(data)
        elif self.active_term is not None:
            self.active_term.append(data)


def _index_overview(repo_root: Path) -> list[dict[str, Any]]:
    index_path = repo_root / "web" / "site" / "index.html"
    if not index_path.is_file():
        return []
    parser = _OverviewHtmlParser()
    parser.feed(index_path.read_text(encoding="utf-8"))
    items: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for idx, entry in enumerate(parser.entries):
        tag, el_id = entry["tag"], entry["id"]
        anchor = "" if tag == "h1" else (
            (entry["section_id"] or el_id) if tag == "h2" else (el_id or entry["card_id"] or entry["section_id"])
        )
        anchor = "" if anchor == "heroTitle" else anchor
        path = f"./#{anchor}" if anchor else "./"
        slug = re.sub(r"[^a-z0-9]+", "-", (el_id or entry["title"]).lower()).strip("-") or f"section-{idx}"
        item_id = f"overview-{slug}" if f"overview-{slug}" not in used_ids else f"overview-{slug}-{idx}"
        used_ids.add(item_id)
        summary = entry["summary"] or entry["title"]
        kw = _tokenize(entry["title"], entry["term"], summary, extra=["overview", anchor])
        items.append(_make_item(item_id, entry["title"], summary, "Overview", path, kw))
    return items


def _index_demo_views() -> list[dict[str, Any]]:
    specs = [
        ("demo-analytics", "Analytics Studio & Quota Gauges", "Interactive 8-model telemetry KPIs, Gemini 20x and Partner 1x quota % left gauges, reset countdowns, and step analytics.", "./demo/", ["demo", "analytics", "quota", "kpis", "models", "countdown", "pool", "telemetry"]),
        ("demo-heatmap", "Activity Heatmap & Hourly Whiskers", "Active-day hourly Min/Avg/Max range whiskers, trailing 24h markers, and daily step heatmap inside the Analytics view.", "./demo/", ["demo", "heatmap", "whiskers", "hourly", "activity", "steps", "24h", "analytics"]),
        ("demo-hierarchy", "Project & Subagent Hierarchy", "Model workload distribution, subagent pool routing breakdown, and project token/cost hierarchy tables.", "./demo/", ["demo", "hierarchy", "subagent", "routing", "workload", "projects", "models", "analytics"]),
        ("demo-workspace", "Workspace Session & Plan Explorer", "Two-pane workspace explorer with bundled depersonalized project trees, implementation plans, and markdown artifacts.", "./demo/#workspace", ["demo", "workspace", "sessions", "artifacts", "markdown", "plans", "explorer", "tree"]),
        ("demo-session-gallery", "Session Screenshot & Capture Gallery", "Inspect desktop, foldable, and mobile viewport captures and repository visual assets side by side in Workspace.", "./demo/#workspace", ["demo", "gallery", "screenshots", "captures", "visuals", "mobile", "desktop", "workspace"]),
    ]
    return [_make_item(iid, title, summary, "Demo", path, kw) for iid, title, summary, path, kw in specs]


def _index_docs(docs_data: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    heading_re = re.compile(r'<h([2-4])\s+id="([^"]+)">([\s\S]*?)</h\1>')
    for ch in docs_data.get("chapters") or []:
        ch_id = str(ch.get("id") or f"doc-{ch.get('slug', 'chapter')}")
        ch_title = str(ch.get("title") or ch_id)
        ch_summary = str(ch.get("summary") or ch.get("plainText") or ch_title)
        ch_kw = _tokenize(ch_title, str(ch.get("group") or ""), ch_summary, extra=list(ch.get("keywords") or []) + ["docs"])
        items.append(_make_item(f"docs-{ch_id}", ch_title, ch_summary, "Docs", f"./docs/#{ch_id}", ch_kw))
        ch_html = str(ch.get("html") or "")
        matches = list(heading_re.finditer(ch_html))
        for i, m in enumerate(matches):
            sub_id, sub_title = m.group(2).strip(), _strip_html(m.group(3))
            if not sub_id or not sub_title:
                continue
            body_end = matches[i + 1].start() if i + 1 < len(matches) else len(ch_html)
            snippet = _strip_html(ch_html[m.end() : body_end])
            summary = f"{ch_title}: {snippet}" if snippet else f"{ch_title} — {sub_title}"
            kw = _tokenize(sub_title, ch_title, snippet[:240], extra=list(ch.get("keywords") or [])[:4] + ["docs"])
            items.append(_make_item(f"docs-{sub_id}", sub_title, summary, "Docs", f"./docs/#{sub_id}", kw))
    return items


def build_search_index(repo_root: Path, docs_data: dict[str, Any], version: str) -> dict[str, Any]:
    """Build the unified `search-index.json` payload for Overview, Demo, and Docs."""
    items = _index_overview(repo_root) + _index_demo_views() + _index_docs(docs_data)
    return {
        "version": "1",
        "project": "agy-nexus-mcp",
        "projectTitle": "Antigravity Nexus",
        "mcpPackage": version,
        "generatedAt": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "items": items,
    }


def write_search_index(repo_root: Path, out_dir: Path, docs_data: dict[str, Any], version: str) -> Path:
    """Write `out_dir / 'search-index.json'` and return its path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "search-index.json"
    out_path.write_text(json.dumps(build_search_index(repo_root, docs_data, version), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out_path
