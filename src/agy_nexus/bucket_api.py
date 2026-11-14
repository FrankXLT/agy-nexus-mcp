#!/usr/bin/env python3
"""agy_nexus.bucket_api — Hierarchical Workspace Tree, Session Bucket Inventory & Image URL Rewriting."""
from __future__ import annotations

import json
from pathlib import Path
import re
import time
from typing import Any
import urllib.parse

from agy_nexus.config import (
    AGY_BG_DIR,
    AGY_BRAIN_DIR,
    AGY_DB_FILE,
    SESSION_STATE,
    verify_passphrase,
)
from agy_nexus.handoff_queue import list_handoff_tickets
from agy_nexus.hygiene import is_sensitive_filename
from agy_nexus.media import (
    ALLOWED_MEDIA_EXTENSIONS,
    discover_visual_artifacts,
    sign_media_url,
)
from agy_nexus.session_status import evaluate_rollover_posture
from agy_nexus.session_tree import build_project_session_tree
from agy_nexus.uploads import validate_conv_id


def rewrite_markdown_media_links(
    md_content: str, conv_id: str, ws_path: str = "", ttl_seconds: int = 604800
) -> str:
    """Rewrite local file:///... and relative image references into 7-day signed /web/media/ URLs."""
    if not md_content or not conv_id:
        return md_content or ""

    brain_dir = (AGY_BRAIN_DIR / conv_id).resolve()

    def _replace_target(target_path_str: str) -> str:
        clean = target_path_str.strip().strip("'\"")
        if clean.startswith(("/web/media/", "http://", "https://", "data:")):
            return target_path_str

        # Strip file:// prefix
        fs_path_str = re.sub(r"^file://", "", clean)
        target_path = Path(fs_path_str)

        # Check if absolute path inside brain_dir
        if target_path.is_absolute():
            try:
                res_path = target_path.resolve()
                if res_path.is_relative_to(brain_dir) and res_path.is_file():
                    rel = str(res_path.relative_to(brain_dir))
                    if res_path.suffix.lower() in ALLOWED_MEDIA_EXTENSIONS:
                        return sign_media_url(f"brain:{conv_id}", rel, ttl_seconds=ttl_seconds)
            except Exception:
                pass
        else:
            # Relative path within brain_dir
            try:
                cand = (brain_dir / fs_path_str.lstrip("/")).resolve()
                if cand.is_relative_to(brain_dir) and cand.is_file():
                    rel = str(cand.relative_to(brain_dir))
                    if cand.suffix.lower() in ALLOWED_MEDIA_EXTENSIONS:
                        return sign_media_url(f"brain:{conv_id}", rel, ttl_seconds=ttl_seconds)
            except Exception:
                pass

        # Check if inside ws_path
        if ws_path:
            ws_dir = Path(ws_path).resolve()
            try:
                cand_ws = (ws_dir / fs_path_str.lstrip("/")).resolve() if not target_path.is_absolute() else target_path.resolve()
                if cand_ws.is_relative_to(ws_dir) and cand_ws.is_file() and cand_ws.suffix.lower() in ALLOWED_MEDIA_EXTENSIONS:
                    repo_slug = ws_dir.name or "repo"
                    rel_ws = str(cand_ws.relative_to(ws_dir))
                    return sign_media_url(f"repo:{repo_slug}", rel_ws, ttl_seconds=ttl_seconds)
            except Exception:
                pass

        return target_path_str

    # Rewrite Markdown image syntax: ![alt](url)
    def _md_img_sub(match: re.Match[str]) -> str:
        alt, url = match.group(1), match.group(2)
        signed = _replace_target(url)
        return f"![{alt}]({signed})"

    rewritten = re.sub(r"!\[(.*?)\]\(([^)]+)\)", _md_img_sub, md_content)

    # Rewrite HTML <img> tags: <img src="url" ...>
    def _html_img_sub(match: re.Match[str]) -> str:
        tag_start, src, tag_end = match.group(1), match.group(2), match.group(3)
        signed = _replace_target(src)
        return f"{tag_start}{signed}{tag_end}"

    rewritten = re.sub(
        r"(<img\b[^>]*?\bsrc=[\"'])([^\"']+)([\"'][^>]*>)",
        _html_img_sub,
        rewritten,
        flags=re.IGNORECASE,
    )
    return rewritten


def scan_session_uploads(conv_id: str) -> list[dict[str, Any]]:
    """Scan scratch/uploads_YYYYMMDD_HHMMSS[_label] directories for a session."""
    if not conv_id or not validate_conv_id(conv_id):
        return []
    scratch_dir = AGY_BRAIN_DIR / conv_id / "scratch"
    if not scratch_dir.is_dir():
        return []

    batches: list[dict[str, Any]] = []
    try:
        subdirs = sorted(
            [d for d in scratch_dir.iterdir() if d.is_dir() and d.name.startswith("uploads_")],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for sd in subdirs:
            folder_name = sd.name
            files_meta: list[dict[str, Any]] = []
            signed_images: list[dict[str, str]] = []
            total_size = 0
            index_md_content = ""
            for item in sorted(sd.iterdir(), key=lambda p: p.name.lower()):
                if not item.is_file() or is_sensitive_filename(item.name):
                    continue
                sz = item.stat().st_size
                total_size += sz
                ext = item.suffix.lower()
                is_img = ext in ALLOWED_MEDIA_EXTENSIONS
                rel = f"scratch/{folder_name}/{item.name}"
                thumb_url = sign_media_url(f"brain:{conv_id}", rel) if is_img else ""
                files_meta.append({
                    "name": item.name,
                    "rel_path": rel,
                    "size": sz,
                    "is_image": is_img,
                    "thumbnail_url": thumb_url,
                })
                if is_img and thumb_url:
                    signed_images.append({
                        "name": item.name,
                        "rel_path": rel,
                        "signed_url": thumb_url,
                    })
                if item.name.upper() == "INDEX.MD":
                    try:
                        index_md_content = item.read_text(encoding="utf-8", errors="replace")[:4000]
                    except Exception:
                        pass
            non_index_count = len([f for f in files_meta if f["name"].upper() != "INDEX.MD"])
            app_prompt = f"Evaluate the {non_index_count} uploaded files in ~/.gemini/antigravity/brain/{conv_id}/scratch/{folder_name}/ (see INDEX.md for sequence order)."
            batches.append({
                "folder_name": folder_name,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(sd.stat().st_mtime)),
                "mtime": sd.stat().st_mtime,
                "total_size": total_size,
                "file_count": len(files_meta),
                "files": files_meta,
                "signed_images": signed_images,
                "app_prompt": app_prompt,
                "index_rel_path": f"scratch/{folder_name}/INDEX.md",
                "index_preview": index_md_content,
            })
    except Exception:
        pass
    return batches


def scan_session_artifacts(conv_id: str) -> list[dict[str, Any]]:
    """Scan markdown artifacts and handoffs in session brain folder."""
    if not conv_id or not validate_conv_id(conv_id):
        return []
    b_dir = AGY_BRAIN_DIR / conv_id
    if not b_dir.is_dir():
        return []

    artifacts: list[dict[str, Any]] = []
    try:
        # Check root of brain/<id>
        for item in b_dir.iterdir():
            if item.is_file() and item.suffix.lower() == ".md" and not is_sensitive_filename(item.name):
                sz = item.stat().st_size
                mtime = item.stat().st_mtime
                artifacts.append({
                    "name": item.name,
                    "rel_path": item.name,
                    "size": sz,
                    "mtime": mtime,
                    "type": "artifact",
                })
        # Check scratch/*.md
        scratch_dir = b_dir / "scratch"
        if scratch_dir.is_dir():
            for item in scratch_dir.iterdir():
                if item.is_file() and item.suffix.lower() == ".md" and not is_sensitive_filename(item.name):
                    sz = item.stat().st_size
                    mtime = item.stat().st_mtime
                    artifacts.append({
                        "name": f"scratch/{item.name}",
                        "rel_path": f"scratch/{item.name}",
                        "size": sz,
                        "mtime": mtime,
                        "type": "handoff" if "handoff" in item.name.lower() else "scratch",
                    })
    except Exception:
        pass
    artifacts.sort(key=lambda a: a["mtime"], reverse=True)
    return artifacts


def build_workspace_tree_payload() -> dict[str, Any]:
    """Build complete hierarchical tree for /web#workspace using human-readable names only."""
    tree_bundle = build_project_session_tree(active_only=False, limit=120)
    inbox = list_handoff_tickets(AGY_BG_DIR, include_superseded=True, limit=60)
    all_tickets = inbox.get("tickets") or []
    staged_tickets = [t for t in all_tickets if str(t.get("status") or "").upper() == "STAGED"]

    queue_node = {
        "id": "__handoffs_queue__",
        "title": "Visual Handoffs Queue",
        "type": "queue",
        "staged_count": len(staged_tickets),
        "total_tickets": len(all_tickets),
        "tickets": all_tickets[:40],
    }

    projects_out: list[dict[str, Any]] = []
    for proj in tree_bundle.get("projects") or []:
        p_name = str(proj.get("project_name") or "Workspace")
        p_id = str(proj.get("project_id") or "")
        sessions_out: list[dict[str, Any]] = []

        for s in proj.get("sessions") or []:
            cid = str(s.get("conversation_id") or "")
            if not cid:
                continue
            title = str(s.get("title") or cid[:8])
            uploads = scan_session_uploads(cid)
            artifacts = scan_session_artifacts(cid)
            posture = evaluate_rollover_posture(
                cid,
                ws_path=str(s.get("workspace_path") or ""),
                brain_dir=AGY_BRAIN_DIR,
                step_count=int(s.get("step_count") or 0),
            )
            sessions_out.append({
                "conversation_id": cid,
                "title": title,
                "workspace_path": str(s.get("workspace_path") or ""),
                "is_running": bool(s.get("is_running")),
                "is_pinned": bool(s.get("is_pinned")),
                "step_count": int(s.get("step_count") or 0),
                "relative_age": str(s.get("relative_age") or ""),
                "rollover_posture": posture.get("posture", "FRESH"),
                "upload_batches": uploads,
                "artifacts": artifacts,
            })

        projects_out.append({
            "project_id": p_id,
            "project_name": p_name,
            "staged_count": int(proj.get("staged_count") or 0),
            "in_work_count": int(proj.get("in_work_handoff_count") or 0),
            "completed_count": int(proj.get("completed_count") or 0),
            "sessions": sessions_out,
            "staged_handoffs": proj.get("staged_handoffs") or [],
        })

    return {
        "ok": True,
        "queue": queue_node,
        "projects": projects_out,
        "selected_session": SESSION_STATE.get("selected_session", ""),
    }


def get_session_bucket_payload(conv_id: str) -> dict[str, Any]:
    """Assemble session bucket data (uploads, artifacts, visual thumbnails, rollover posture)."""
    if not conv_id or not validate_conv_id(conv_id):
        return {"ok": False, "error": "Missing or invalid conversation_id"}

    ws_map = SESSION_STATE.get("session_workspace_map") or {}
    ws_path = str(ws_map.get(conv_id) or SESSION_STATE.get("selected_workspace") or "")
    uploads = scan_session_uploads(conv_id)
    artifacts = scan_session_artifacts(conv_id)
    visual_raw = discover_visual_artifacts(conv_id, workspace_path=ws_path, limit=20)
    visual_items = []
    for v in visual_raw:
        visual_items.append({
            "name": v.get("name") or "image",
            "rel_path": v.get("rel_path") or "",
            "signed_url": v.get("signed_url") or "",
            "size": v.get("size") or 0,
            "mtime": v.get("mtime") or 0,
        })

    posture = evaluate_rollover_posture(conv_id, ws_path=ws_path, brain_dir=AGY_BRAIN_DIR)
    title_map = SESSION_STATE.get("session_title_map") or {}
    title = str(title_map.get(conv_id) or conv_id[:8])

    return {
        "ok": True,
        "conversation_id": conv_id,
        "title": title,
        "workspace_path": ws_path,
        "uploads": uploads,
        "artifacts": artifacts,
        "visual_artifacts": visual_items,
        "rollover": posture,
    }


def get_session_file_payload(conv_id: str, rel_path: str) -> tuple[int, dict[str, Any]]:
    """Safely fetch file content with path traversal guard and media link rewriting."""
    if not conv_id or not validate_conv_id(conv_id) or not rel_path:
        return 400, {"ok": False, "error": "Missing or invalid conversation_id or rel_path"}

    clean_rel = rel_path.strip().lstrip("/")
    if ".." in Path(clean_rel).parts or is_sensitive_filename(clean_rel):
        return 403, {"ok": False, "error": "Path traversal or sensitive file rejected"}

    brain_dir = (AGY_BRAIN_DIR / conv_id).resolve()
    target = (brain_dir / clean_rel).resolve()
    if target == brain_dir or not target.is_relative_to(brain_dir) or not target.is_file():
        # Check if staged handoffs queue file
        if clean_rel.startswith("staged_handoffs/"):
            stg_file = (AGY_BG_DIR / clean_rel).resolve()
            if stg_file.is_file() and stg_file.is_relative_to(AGY_BG_DIR.resolve()):
                target = stg_file
            else:
                return 404, {"ok": False, "error": "File not found"}
        else:
            return 404, {"ok": False, "error": "File not found"}

    try:
        raw_text = target.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return 500, {"ok": False, "error": f"Failed reading file: {e}"}

    ws_map = SESSION_STATE.get("session_workspace_map") or {}
    ws_path = str(ws_map.get(conv_id) or "")
    rewritten_text = rewrite_markdown_media_links(raw_text, conv_id, ws_path=ws_path)

    return 200, {
        "ok": True,
        "conversation_id": conv_id,
        "rel_path": clean_rel,
        "content": rewritten_text,
        "raw_content": raw_text,
        "size": target.stat().st_size,
        "mtime": target.stat().st_mtime,
    }


async def handle_bucket_api_request(
    scope: dict[str, Any],
    receive: Any,
    send: Any,
    req_path: str,
    method: str,
    headers: list[tuple[bytes, bytes]],
    raw_qs: str = "",
) -> None:
    """ASGI handler for /web/api/workspace/tree, /web/api/sessions/{id}/bucket, and file access."""
    # Authenticate via X-Nexus-Passphrase
    supplied_pass = ""
    for hk, hv in headers:
        if hk.lower() == b"x-nexus-passphrase":
            supplied_pass = hv.decode("utf-8", errors="ignore").strip()
            break

    if not verify_passphrase(supplied_pass):
        err_b = json.dumps({"ok": False, "error": "Invalid spoken deadbolt passphrase."}).encode("utf-8")
        await send({
            "type": "http.response.start", "status": 401,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(err_b)).encode("ascii")), (b"cache-control", b"no-store")],
        })
        await send({"type": "http.response.body", "body": err_b})
        return

    # Route 1: Workspace Tree
    if req_path.endswith("/web/api/workspace/tree") or req_path.endswith("/api/workspace/tree"):
        payload = build_workspace_tree_payload()
        body_b = json.dumps(payload).encode("utf-8")
        await send({
            "type": "http.response.start", "status": 200,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body_b)).encode("ascii")), (b"cache-control", b"no-cache")],
        })
        await send({"type": "http.response.body", "body": body_b})
        return

    # Route 2: Session Bucket
    m_bucket = re.search(r"/api/sessions/([^/]+)/bucket$", req_path)
    if m_bucket:
        cid = m_bucket.group(1).strip()
        if not validate_conv_id(cid):
            err_b = json.dumps({"ok": False, "error": "Invalid conversation_id"}).encode("utf-8")
            await send({
                "type": "http.response.start", "status": 400,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(err_b)).encode("ascii")), (b"cache-control", b"no-cache")],
            })
            await send({"type": "http.response.body", "body": err_b})
            return
        payload = get_session_bucket_payload(cid)
        body_b = json.dumps(payload).encode("utf-8")
        await send({
            "type": "http.response.start", "status": 200,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body_b)).encode("ascii")), (b"cache-control", b"no-cache")],
        })
        await send({"type": "http.response.body", "body": body_b})
        return

    # Route 3: Session File
    m_file = re.search(r"/api/sessions/([^/]+)/file$", req_path)
    if m_file:
        cid = m_file.group(1).strip()
        if not validate_conv_id(cid):
            err_b = json.dumps({"ok": False, "error": "Invalid conversation_id"}).encode("utf-8")
            await send({
                "type": "http.response.start", "status": 400,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(err_b)).encode("ascii")), (b"cache-control", b"no-cache")],
            })
            await send({"type": "http.response.body", "body": err_b})
            return
        rel_path = ""
        for kv in raw_qs.split("&"):
            if kv.startswith("path="):
                rel_path = urllib.parse.unquote(kv.split("=", 1)[1].strip())
        status_code, payload = get_session_file_payload(cid, rel_path)
        body_b = json.dumps(payload).encode("utf-8")
        await send({
            "type": "http.response.start", "status": status_code,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body_b)).encode("ascii")), (b"cache-control", b"no-cache")],
        })
        await send({"type": "http.response.body", "body": body_b})
        return

    # Fallback 404
    nf_b = b'{"ok":false,"error":"Endpoint not found"}'
    await send({
        "type": "http.response.start", "status": 404,
        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(nf_b)).encode("ascii"))],
    })
    await send({"type": "http.response.body", "body": nf_b})
