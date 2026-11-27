#!/usr/bin/env python3
"""agy_nexus.session_gallery — Capability-Signed Session Screenshot & Verified Links Gallery."""

from __future__ import annotations

import hashlib
import hmac
import html
import json
from pathlib import Path
import sqlite3
import time
from typing import Any
import urllib.parse

from agy_nexus import __version__
import agy_nexus.config as cfg
from agy_nexus.config import SESSION_STATE
from agy_nexus.media import MEDIA_TTL_SECONDS, _resolve_scope_base_dir, discover_visual_buckets, get_public_base_url
from agy_nexus.media_discovery import read_image_dimensions_fast
from agy_nexus.sessions import _load_projects_map, pick_primary_workspace_uri, resolve_canonical_project_for_workspace
from agy_nexus.uploads import validate_conv_id
from agy_nexus.verified_urls import describe_verified_url, extract_verified_urls_for_session

EMBEDDED_LINK_GUIDANCE = (
    "Render `gallery_url`, `workspace_url`, and `verified_urls` as clickable Markdown links with "
    "plain English labels (`[Open Session Gallery](...)`, `[Open in Antigravity Web](...)`). "
    "Never put raw domains/URLs in `[...]` or URLs in fenced code blocks."
)
COPY_READY_LINK_GUIDANCE = EMBEDDED_LINK_GUIDANCE


def _format_size_label(num_bytes: int) -> str:
    """Format byte size into compact human-readable label (e.g. '142 KB')."""
    n = max(0, int(num_bytes))
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{max(1, round(n / 1024))} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{n / (1024 * 1024 * 1024):.1f} GB"


def _safe_json_for_script(payload: dict[str, Any]) -> str:
    """Serialize JSON safely for embedding inside <script type='application/json'>."""
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def compute_gallery_hmac(exp_ts: int, conv_id: str, pass_hash: str | None = None) -> str:
    """Compute domain-separated 32-char lowercase hex HMAC-SHA256 for /web/gallery/ links."""
    secret_hex = (pass_hash if pass_hash is not None else cfg.PASS_HASH) or "default-unconfigured-hash"
    clean_cid = (conv_id or "").strip()
    msg = f"gallery-v1:{int(exp_ts)}:{clean_cid}".encode("utf-8")
    return hmac.new(secret_hex.encode("utf-8"), msg, hashlib.sha256).hexdigest()[:32].lower()


def sign_gallery_url(
    conv_id: str, ttl_seconds: int = MEDIA_TTL_SECONDS, exp_ts: int | None = None, relative: bool = False,
) -> str:
    """Generate a capability-signed /web/gallery/<exp_val>/<sig>/<conv_id> URL."""
    clean_cid = (conv_id or "").strip()
    if not clean_cid or not validate_conv_id(clean_cid):
        return ""
    exp_val = int(exp_ts) if exp_ts is not None else int(time.time()) + int(ttl_seconds)
    path_part = f"/web/gallery/{exp_val}/{compute_gallery_hmac(exp_val, clean_cid)}/{clean_cid}"
    if relative:
        return path_part
    base = get_public_base_url()
    return f"{base}{path_part}" if base else path_part


def verify_and_resolve_gallery(req_path: str) -> tuple[str, int, str]:
    """Verify HMAC signature, expiry, and brain directory containment for /web/gallery/."""
    clean_req = (req_path or "").split("?", 1)[0]
    if "/web/gallery/" not in clean_req:
        return "", 404, "Session gallery not found."
    tail = clean_req.split("/web/gallery/", 1)[1].lstrip("/").rstrip("/")
    parts = tail.split("/")
    if len(parts) != 3 or not all(parts):
        return "", 403, "Invalid or expired gallery link."

    exp_str, supplied_sig, raw_cid = parts[0].strip(), parts[1].strip(), parts[2].strip()
    try:
        exp_ts = int(exp_str)
    except ValueError:
        return "", 403, "Invalid or expired gallery link."
    if exp_ts < int(time.time()):
        return "", 403, "Invalid or expired gallery link."

    conv_id = urllib.parse.unquote(raw_cid).strip()
    if not validate_conv_id(conv_id) or not cfg.PASS_HASH or not supplied_sig:
        return "", 403, "Invalid or expired gallery link."

    expected_sig = compute_gallery_hmac(exp_ts, conv_id)
    if not hmac.compare_digest(supplied_sig.lower(), expected_sig.lower()):
        return "", 403, "Invalid or expired gallery link."

    try:
        brain_root = cfg.AGY_BRAIN_DIR.resolve()
        cand = cfg.AGY_BRAIN_DIR / conv_id
        if cand.is_symlink():
            return "", 403, "Invalid or expired gallery link."
        resolved = cand.resolve()
        if resolved == brain_root or not resolved.is_relative_to(brain_root) or not resolved.is_dir():
            return "", 404, "Session gallery not found."
    except Exception:
        return "", 404, "Session gallery not found."
    return conv_id, 200, "OK"


def _normalize_ws_path(raw_ws: str) -> str:
    """Strip file:// URI prefix, URL-decode, and trim trailing slashes."""
    s = (raw_ws or "").strip()
    if s.startswith("file://"):
        s = urllib.parse.unquote(s[7:])
    return s.rstrip("/")


def _resolve_session_meta_readonly(conv_id: str) -> tuple[str, str, str]:
    """Pure read-only lookup of (ws_path, project_name, title) without mutating SESSION_STATE."""
    with cfg._STATE_LOCK:
        ws_path = str((SESSION_STATE.get("session_workspace_map") or {}).get(conv_id) or "")
        project_id = str((SESSION_STATE.get("session_project_map") or {}).get(conv_id) or "")
        title = str((SESSION_STATE.get("session_title_map") or {}).get(conv_id) or "")
        slot_proj_name = ""
        slot = (SESSION_STATE.get("active_contexts") or {}).get(conv_id)
        if isinstance(slot, dict):
            ws_path = ws_path or str(slot.get("workspace") or slot.get("workspace_path") or "")
            project_id = project_id or str(slot.get("project_id") or "")
            title = title or str(slot.get("title") or "")
            slot_proj_name = str(slot.get("project_name") or "")
    ws_path = _normalize_ws_path(ws_path)

    if (not ws_path or not project_id or not title) and cfg.AGY_DB_FILE.is_file():
        try:
            con = sqlite3.connect(f"file:{cfg.AGY_DB_FILE}?mode=ro", uri=True)
            try:
                row = con.execute(
                    "SELECT title, workspace_uris, project_id FROM conversation_summaries WHERE conversation_id = ? LIMIT 1",
                    (conv_id,),
                ).fetchone()
            finally:
                con.close()
            if row:
                title = title or str(row[0] or "")
                project_id = project_id or str(row[2] or "")
                if not ws_path and row[1]:
                    raw_list = json.loads(str(row[1]))
                    if isinstance(raw_list, list):
                        clean_uris = [_normalize_ws_path(str(u)) for u in raw_list if u]
                        ws_path = _normalize_ws_path(pick_primary_workspace_uri(clean_uris, title, project_id))
        except Exception:
            pass

    project_name = slot_proj_name
    projects_map = _load_projects_map()
    if not ws_path and project_id in projects_map:
        p_paths = projects_map[project_id].get("workspace_paths") or []
        if p_paths:
            ws_path = _normalize_ws_path(str(p_paths[0]))
    if not project_name and project_id in projects_map:
        project_name = str(projects_map[project_id].get("name") or "")
    if not project_name:
        _, project_name = resolve_canonical_project_for_workspace(ws_path, project_id)
    if not project_name and ws_path:
        project_name = Path(ws_path).name
    return ws_path, project_name, title


def _read_item_dimensions(item: dict[str, Any]) -> tuple[int, int, str]:
    """Safely resolve physical screenshot file and read header dimensions without decoding pixels."""
    scope = str(item.get("scope") or "")
    rel_path = str(item.get("rel_path") or "").lstrip("/")
    base_dir = _resolve_scope_base_dir(scope)
    if base_dir is None or not rel_path or ".." in Path(rel_path).parts:
        return 0, 0, ""
    cand = base_dir / rel_path
    try:
        if cand.is_symlink():
            return 0, 0, ""
        rp = cand.resolve()
        if rp == base_dir or not rp.is_relative_to(base_dir) or not rp.is_file():
            return 0, 0, ""
        dims = read_image_dimensions_fast(rp)
        if dims and dims[0] > 0 and dims[1] > 0:
            w, h = int(dims[0]), int(dims[1])
            return w, h, f"{w}\u00d7{h}"
    except Exception:
        pass
    return 0, 0, ""


def build_session_gallery_payload(conv_id: str) -> dict[str, Any]:
    """Assemble safe display payload of session screenshots and verified URLs."""
    ws_path, project_name, title = _resolve_session_meta_readonly(conv_id)
    session_items, _ = discover_visual_buckets(
        conv_id, workspace_path=ws_path, session_limit=60, repo_limit=0, relative=True, db_file=cfg.AGY_DB_FILE,
    )
    screenshots: list[dict[str, Any]] = []
    for idx, item in enumerate(session_items, 1):
        width, height, resolution = _read_item_dimensions(item)
        size_bytes = int(item.get("bytes") or 0)
        screenshots.append({
            "index": idx, "name": str(item.get("name") or ""), "rel_path": str(item.get("rel_path") or ""),
            "signed_url": str(item.get("signed_url") or ""), "bytes": size_bytes,
            "size_label": _format_size_label(size_bytes), "modified_at": str(item.get("modified_at") or ""),
            "width": width, "height": height, "resolution": resolution,
        })
    verified_urls = extract_verified_urls_for_session(conv_id, ws_path=ws_path, brain_dir=cfg.AGY_BRAIN_DIR)
    return {
        "conversation_id": conv_id, "short_id": conv_id[:8], "title": title or f"Session {conv_id[:8]}",
        "project_name": project_name, "screenshot_count": len(screenshots), "screenshots": screenshots,
        "verified_urls": verified_urls, "verified_links": [describe_verified_url(u) for u in verified_urls],
    }


def build_tool_gallery_links(
    conv_id: str, ws_path: str = "", *, raw_latest_assistant: str = "",
    raw_walkthrough: str = "", raw_task: str = "", max_urls: int = 16,
) -> dict[str, Any]:
    """Return signed gallery_url and extracted verified_urls for MCP tool payloads."""
    clean_cid = (conv_id or "").strip()
    if not clean_cid or not validate_conv_id(clean_cid):
        return {"gallery_url": "", "verified_urls": []}
    return {
        "gallery_url": sign_gallery_url(clean_cid, relative=False),
        "verified_urls": extract_verified_urls_for_session(
            clean_cid, ws_path=ws_path, brain_dir=cfg.AGY_BRAIN_DIR,
            raw_latest_assistant=raw_latest_assistant, raw_walkthrough=raw_walkthrough,
            raw_task=raw_task, max_urls=max_urls,
        ),
    }


def enforce_visual_wire_budget(
    summary_payload: dict[str, Any], b64_images: list[str], max_wire_bytes: int = 19500,
) -> str:
    """Compact summary_payload until [text, *webp_images] MCP content fits within max_wire_bytes."""
    img_blocks = [{"type": "image", "data": d, "mimeType": "image/webp"} for d in b64_images]

    def _wire_len(t: str) -> int:
        return len(json.dumps([{"type": "text", "text": t}, *img_blocks], separators=(",", ":"), ensure_ascii=False).encode("utf-8"))

    text_str = cfg._compact_json(summary_payload)
    if _wire_len(text_str) <= max_wire_bytes:
        return text_str

    items = summary_payload.get("items_meta")
    if isinstance(items, list):
        for it in items:
            if isinstance(it, dict):
                it.pop("svg_excerpt", None)
        text_str = cfg._compact_json(summary_payload)
        if _wire_len(text_str) <= max_wire_bytes:
            return text_str

    vurls = summary_payload.get("verified_urls")
    if isinstance(vurls, list):
        for keep in (4, 0):
            if keep == 0 or len(vurls) > keep:
                summary_payload["verified_urls"] = vurls[:keep] if keep > 0 else []
                text_str = cfg._compact_json(summary_payload)
                if _wire_len(text_str) <= max_wire_bytes:
                    return text_str

    if isinstance(items, list):
        for field in ("rel_path", "signed_url"):
            for it in items:
                if isinstance(it, dict):
                    it.pop(field, None)
            text_str = cfg._compact_json(summary_payload)
            if _wire_len(text_str) <= max_wire_bytes:
                return text_str
    return text_str


def _render_head_links() -> str:
    """Build shared stylesheet links for gallery and gallery error pages."""
    ver = urllib.parse.quote(str(__version__), safe="")
    return (
        f'<link rel="stylesheet" href="/web/v9/v9_layers.css?v={ver}">\n'
        f'<link rel="stylesheet" href="/web/v9/vendor/quiet-ui-tokens.css?v={ver}">\n'
        f'<link rel="stylesheet" href="/web/gallery_page.css?v={ver}">'
    )


def _render_links_nav(verified_links: list[dict[str, Any]]) -> str:
    """Render conditional verified links bar, or empty string when there are none."""
    pills: list[str] = []
    for link in verified_links:
        url = str(link.get("url") or "")
        if not url.startswith(("https://", "http://")):
            continue
        label = html.escape(str(link.get("label") or url), quote=True)
        kind = html.escape(str(link.get("kind") or "link"), quote=True)
        href = html.escape(url, quote=True)
        pills.append(
            f'<a class="gal-link-pill" href="{href}" target="_blank" '
            f'rel="noopener noreferrer" data-kind="{kind}">{label}</a>'
        )
    if not pills:
        return ""
    return '<nav class="gal-links-bar" aria-label="Verified session links">\n' + "\n".join(pills) + "\n</nav>"


def _render_cards_html(screenshots: list[dict[str, Any]]) -> str:
    """Render SSR <article class='gal-card'> items or empty-state message."""
    if not screenshots:
        return '<p class="gal-empty">No session screenshots found yet.</p>'
    cards: list[str] = []
    for idx, item in enumerate(screenshots):
        num = idx + 1
        name_esc = html.escape(str(item.get("name") or f"screenshot_{num:02d}"), quote=True)
        url_esc = html.escape(str(item.get("signed_url") or ""), quote=True)
        size_esc = html.escape(str(item.get("size_label") or ""), quote=True)
        res = str(item.get("resolution") or "")
        res_badge = f'<span class="gal-badge-res">{html.escape(res, quote=True)}</span>' if res else ""
        cards.append(
            f'<article class="gal-card" data-index="{idx}">'
            f'<div class="gal-thumb-wrap">'
            f'<button type="button" class="gal-thumb-btn" data-gal-index="{idx}" aria-label="View {name_esc}">'
            f'<img class="gal-thumb-img" src="{url_esc}" alt="{name_esc}" loading="lazy" decoding="async"></button>'
            f'<span class="gal-badge-seq">#{num:02d}</span>{res_badge}</div>'
            f'<div class="gal-card-foot"><div class="gal-card-meta">'
            f'<span class="gal-card-name" title="{name_esc}">{name_esc}</span>'
            f'<span class="gal-card-size">{size_esc}</span></div>'
            f'<a class="gal-raw-link" href="{url_esc}" target="_blank" rel="noopener noreferrer">Raw</a></div>'
            f'</article>'
        )
    return "\n".join(cards)


def render_session_gallery_html(data: dict[str, Any]) -> str:
    """Render SSR HTML page for a signed session gallery without inline JS or CSS."""
    ver = urllib.parse.quote(str(__version__), safe="")
    title_esc = html.escape(str(data.get("title") or "Session Gallery"), quote=True)
    short_id_esc = html.escape(str(data.get("short_id") or ""), quote=True)
    proj = str(data.get("project_name") or "")
    proj_html = f'<span class="gal-chip">{html.escape(proj, quote=True)}</span>' if proj else ""
    screenshots = list(data.get("screenshots") or [])
    count = int(data.get("screenshot_count") if data.get("screenshot_count") is not None else len(screenshots))
    cap_word = "capture" if count == 1 else "captures"
    links_nav = _render_links_nav(list(data.get("verified_links") or []))
    cards_html = _render_cards_html(screenshots)
    json_blob = _safe_json_for_script(data)
    nav_block = f"{links_nav}\n" if links_nav else ""
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="color-scheme" content="light dark">\n'
        f"<title>{title_esc} — Session Gallery</title>\n{_render_head_links()}\n"
        f'<script defer src="/web/gallery_page.js?v={ver}"></script>\n</head>\n<body>\n'
        '<header class="gal-topbar"><div class="gal-topbar-inner"><div class="gal-topbar-brand">'
        f'<h1>{title_esc}</h1>{proj_html}<span class="gal-id-chip">{short_id_esc}</span>'
        f'<span class="gal-count-pill">{count} {cap_word}</span></div>'
        '<div class="gal-topbar-actions"><button type="button" id="galThemeBtn" class="gal-btn" '
        'aria-label="Toggle color theme">Theme</button></div></div></header>\n'
        f'<main class="gal-main">\n{nav_block}<section class="gal-grid" id="galGrid">\n'
        f'{cards_html}\n</section>\n</main>\n'
        '<dialog id="galLightbox" class="gal-dialog" closedby="any" aria-labelledby="galLbTitle">'
        '<div class="gal-lb-hdr"><div class="gal-lb-heading"><h2 id="galLbTitle"></h2>'
        '<div id="galLbMeta"></div></div><div class="gal-lb-actions">'
        '<button type="button" id="galLbFitBtn" class="gal-lb-btn" aria-pressed="true">Fit</button>'
        '<button type="button" id="galLbNativeBtn" class="gal-lb-btn" aria-pressed="false">1:1</button>'
        '<button type="button" id="galLbPrevBtn" class="gal-lb-btn" aria-label="Previous screenshot">Prev</button>'
        '<button type="button" id="galLbNextBtn" class="gal-lb-btn" aria-label="Next screenshot">Next</button>'
        '<a id="galLbRawLink" class="gal-lb-btn" href="#" target="_blank" rel="noopener noreferrer">Raw</a>'
        '<button type="button" id="galLbCloseBtn" class="gal-lb-btn" aria-label="Close lightbox">Close</button>'
        '</div></div><div id="galLbStage" class="gal-lb-stage is-fit">'
        '<img id="galLbImg" class="gal-lb-img is-fit" alt=""></div></dialog>\n'
        f'<script id="galleryData" type="application/json">{json_blob}</script>\n</body>\n</html>\n'
    )


def render_gallery_error_html(status_code: int, message: str) -> str:
    """Render clean static HTML error page for invalid/expired/missing gallery requests."""
    code = int(status_code)
    msg_esc = html.escape(str(message or "Gallery unavailable."), quote=True)
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="color-scheme" content="light dark">\n'
        f"<title>{code} — Session Gallery</title>\n{_render_head_links()}\n</head>\n<body>\n"
        f'<main class="gal-main"><section class="gal-empty"><h1>{code}</h1><p>{msg_esc}</p>'
        '</section></main>\n</body>\n</html>\n'
    )
