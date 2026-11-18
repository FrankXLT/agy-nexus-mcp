#!/usr/bin/env python3
"""agy_nexus.bucket_api — Hierarchical Workspace Tree, Session Bucket Inventory & Image URL Rewriting."""
from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3
import time
from typing import Any
import urllib.parse

import anyio

from agy_nexus.bucket_zip import (
    build_session_zip as _bz_build_session_zip,
    handle_download_zip as _handle_download_zip,
    resolve_zip_entry as _resolve_zip_entry,
    send_json as _send_json,
)
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
    count_brain_visual_captures,
    discover_visual_buckets,
    sign_media_url,
)
from agy_nexus.session_status import check_uncommitted_work, evaluate_rollover_posture
from agy_nexus.session_tree import build_project_session_tree
from agy_nexus.sessions import (
    _load_projects_map,
    pick_primary_workspace_uri,
    resolve_canonical_project_for_workspace,
)
from agy_nexus.uploads import validate_conv_id


def _resolve_session_workspace_info(conv_id: str) -> tuple[str, str, str]:
    """Resolve (ws_path, project_name, title) for conv_id from SESSION_STATE or SQLite without cross-session leakage."""
    contexts = SESSION_STATE.get("active_contexts") or {}
    slot = contexts.get(conv_id, {}) if isinstance(contexts, dict) else {}
    ws_map = SESSION_STATE.get("session_workspace_map") or {}
    pname_map = SESSION_STATE.get("session_project_name_map") or {}
    pid_map = SESSION_STATE.get("session_project_map") or {}
    title_map = SESSION_STATE.get("session_title_map") or {}

    ws_path = str(slot.get("workspace") or ws_map.get(conv_id) or "").strip()
    ws_path = re.sub(r"^file://", "", ws_path).rstrip("/")
    project_name = str(slot.get("project_name") or pname_map.get(conv_id) or "").strip()
    project_id = str(slot.get("project_id") or pid_map.get(conv_id) or "").strip()
    title = str(slot.get("title") or title_map.get(conv_id) or "").strip()

    if (not ws_path or not project_id or not title) and AGY_DB_FILE.is_file():
        try:
            with closing(sqlite3.connect(f"file:{AGY_DB_FILE}?mode=ro", uri=True, timeout=3)) as conn:
                row = conn.execute(
                    "SELECT title, project_id, workspace_uris FROM conversation_summaries WHERE conversation_id = ? LIMIT 1",
                    (conv_id,),
                ).fetchone()
            if row:
                if not title and row[0]:
                    title = str(row[0]).strip()
                    SESSION_STATE.setdefault("session_title_map", {})[conv_id] = title
                if not project_id and row[1]:
                    project_id = str(row[1]).strip()
                    SESSION_STATE.setdefault("session_project_map", {})[conv_id] = project_id
                if not ws_path and row[2]:
                    uris = json.loads(row[2])
                    if isinstance(uris, list) and uris:
                        clean_uris = [re.sub(r"^file://", "", str(u)).rstrip("/") for u in uris if u]
                        ws_path = pick_primary_workspace_uri(clean_uris, title, project_id)
                        if ws_path:
                            SESSION_STATE.setdefault("session_workspace_map", {})[conv_id] = ws_path
        except Exception:
            pass

    if not project_name and project_id:
        project_name = str(_load_projects_map().get(project_id, {}).get("name") or "").strip()
    if not project_name and (ws_path or project_id):
        _, resolved_pname = resolve_canonical_project_for_workspace(ws_path, project_id)
        project_name = str(resolved_pname or "").strip()
    if not project_name and ws_path:
        project_name = Path(ws_path).name
    return ws_path, (project_name or "Workspace"), (title or conv_id[:8])


def rewrite_markdown_media_links(
    md_content: str, conv_id: str, ws_path: str = "", ttl_seconds: int = 604800
) -> str:
    """Rewrite local file:///... and relative image references into 7-day signed /web/media/ URLs."""
    if not md_content or not conv_id:
        return md_content or ""

    brain_dir = (AGY_BRAIN_DIR / conv_id).resolve()
    ws_dir = Path(ws_path).resolve() if ws_path else None

    def _replace_target(target_path_str: str, preserve_title: bool = False) -> str:
        raw_s = target_path_str.strip()
        title_suffix = ""
        url_token = raw_s
        if preserve_title:
            m_ang = re.match(r"^<([^>]+)>(.*)$", raw_s)
            if m_ang:
                url_token, title_suffix = m_ang.group(1).strip(), m_ang.group(2)
            else:
                m_tit = re.match(r'^(\S+)(\s+(?:"[^"]*"|\'[^\']*\'))\s*$', raw_s)
                if m_tit:
                    url_token, title_suffix = m_tit.group(1), m_tit.group(2)
        clean = url_token.strip().strip("'\"")
        if clean.startswith(("/web/media/", "http://", "https://", "data:", "#")):
            return target_path_str

        fs_raw = urllib.parse.unquote(re.sub(r"^file://(?:localhost)?", "", clean, flags=re.IGNORECASE))
        target_path = Path(fs_raw)
        if not fs_raw or ".." in target_path.parts or is_sensitive_filename(target_path.name):
            return target_path_str

        if target_path.is_absolute():
            try:
                res_path = target_path.resolve()
                if (
                    res_path.is_file()
                    and res_path.suffix.lower() in ALLOWED_MEDIA_EXTENSIONS
                    and not is_sensitive_filename(res_path.name)
                ):
                    if res_path != brain_dir and res_path.is_relative_to(brain_dir):
                        rel = str(res_path.relative_to(brain_dir)).replace("\\", "/")
                        return sign_media_url(f"brain:{conv_id}", rel, ttl_seconds=ttl_seconds, relative=True) + title_suffix
                    if ws_dir is not None and res_path != ws_dir and res_path.is_relative_to(ws_dir):
                        rel_ws = str(res_path.relative_to(ws_dir)).replace("\\", "/")
                        return sign_media_url(f"repo:{ws_dir.name or 'repo'}", rel_ws, ttl_seconds=ttl_seconds, relative=True) + title_suffix
            except Exception:
                pass
        else:
            rel_clean = fs_raw.lstrip("/")
            if rel_clean.startswith("./"):
                rel_clean = rel_clean[2:]
            for base_dir, scope_lbl in (
                (brain_dir, f"brain:{conv_id}"),
                *(([(ws_dir, f"repo:{ws_dir.name or 'repo'}")] if ws_dir is not None else [])),
            ):
                try:
                    cand = (base_dir / rel_clean).resolve()
                    if cand != base_dir and cand.is_relative_to(base_dir) and cand.is_file():
                        if cand.suffix.lower() in ALLOWED_MEDIA_EXTENSIONS and not is_sensitive_filename(cand.name):
                            rel_s = str(cand.relative_to(base_dir)).replace("\\", "/")
                            return sign_media_url(scope_lbl, rel_s, ttl_seconds=ttl_seconds, relative=True) + title_suffix
                except Exception:
                    continue
        return target_path_str

    rewritten = re.sub(r"!\[(.*?)\]\(([^)]+)\)", lambda m: f"![{m.group(1)}]({_replace_target(m.group(2), preserve_title=True)})", md_content)
    return re.sub(
        r"(<img\b[^>]*?\bsrc=[\"'])([^\"']+)([\"'][^>]*>)",
        lambda m: f"{m.group(1)}{_replace_target(m.group(2), preserve_title=False)}{m.group(3)}",
        rewritten,
        flags=re.IGNORECASE,
    )


def scan_session_uploads(conv_id: str) -> list[dict[str, Any]]:
    """Scan scratch/uploads_YYYYMMDD_HHMMSS[_label] directories for a session."""
    if not conv_id or not validate_conv_id(conv_id):
        return []
    scratch_dir = AGY_BRAIN_DIR / conv_id / "scratch"
    if not scratch_dir.is_dir() or scratch_dir.is_symlink():
        return []
    scratch_res = scratch_dir.resolve()

    batches: list[dict[str, Any]] = []
    try:
        subdirs = sorted(
            [
                d for d in scratch_dir.iterdir()
                if d.is_dir() and not d.is_symlink() and d.name.startswith("uploads_") and d.resolve().is_relative_to(scratch_res)
            ],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for sd in subdirs:
            sd_res = sd.resolve()
            folder_name = sd.name
            files_meta: list[dict[str, Any]] = []
            signed_images: list[dict[str, Any]] = []
            total_size = 0
            index_md_content = ""
            for item in sorted(sd.iterdir(), key=lambda p: p.name.lower()):
                if item.is_symlink() or not item.is_file():
                    continue
                res_item = item.resolve()
                if res_item == sd_res or not res_item.is_relative_to(sd_res) or is_sensitive_filename(res_item.name):
                    continue
                st = res_item.stat()
                sz = int(st.st_size)
                total_size += sz
                ext = res_item.suffix.lower()
                is_img = ext in ALLOWED_MEDIA_EXTENSIONS
                rel = f"scratch/{folder_name}/{item.name}"
                thumb_url = sign_media_url(f"brain:{conv_id}", rel, relative=True) if is_img else ""
                files_meta.append({"name": item.name, "rel_path": rel, "size": sz, "is_image": is_img, "thumbnail_url": thumb_url})
                if is_img and thumb_url:
                    signed_images.append({
                        "name": item.name, "rel_path": rel, "scope": f"brain:{conv_id}",
                        "mtime": float(st.st_mtime), "signed_url": thumb_url,
                    })
                if item.name.upper() == "INDEX.MD":
                    try:
                        index_md_content = res_item.read_text(encoding="utf-8", errors="replace")[:4000]
                    except Exception:
                        pass
            non_index_count = len([f for f in files_meta if f["name"].upper() != "INDEX.MD"])
            app_prompt = f"Evaluate the {non_index_count} uploaded files in ~/.gemini/antigravity/brain/{conv_id}/scratch/{folder_name}/ (see INDEX.md for sequence order)."
            sd_st = sd_res.stat()
            batches.append({
                "folder_name": folder_name,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(sd_st.st_mtime)),
                "mtime": sd_st.st_mtime, "total_size": total_size, "file_count": len(files_meta),
                "files": files_meta, "signed_images": signed_images, "app_prompt": app_prompt,
                "index_rel_path": f"scratch/{folder_name}/INDEX.md", "index_preview": index_md_content,
            })
    except Exception:
        pass
    return batches


def scan_session_artifacts(conv_id: str) -> list[dict[str, Any]]:
    """Scan markdown artifacts and handoffs in session brain folder."""
    if not conv_id or not validate_conv_id(conv_id):
        return []
    b_dir = AGY_BRAIN_DIR / conv_id
    if not b_dir.is_dir() or b_dir.is_symlink():
        return []
    b_res = b_dir.resolve()

    artifacts: list[dict[str, Any]] = []
    try:
        scan_dirs: list[tuple[Path, str]] = [(b_res, "")]
        scratch_dir = b_dir / "scratch"
        if scratch_dir.is_dir() and not scratch_dir.is_symlink():
            s_res = scratch_dir.resolve()
            if s_res.is_relative_to(b_res):
                scan_dirs.append((s_res, "scratch/"))
        for folder_res, prefix in scan_dirs:
            for item in folder_res.iterdir():
                if item.is_symlink() or not item.is_file() or item.suffix.lower() != ".md":
                    continue
                res_item = item.resolve()
                if res_item == folder_res or not res_item.is_relative_to(folder_res) or is_sensitive_filename(res_item.name):
                    continue
                st = res_item.stat()
                rel_p = f"{prefix}{item.name}"
                kind = ("handoff" if "handoff" in item.name.lower() else "scratch") if prefix else "artifact"
                artifacts.append({"name": rel_p, "rel_path": rel_p, "size": st.st_size, "mtime": st.st_mtime, "type": kind})
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

    uncommitted_cache: dict[str, bool] = {}
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
            ws_s = str(s.get("workspace_path") or "")
            if ws_s not in uncommitted_cache:
                uncommitted_cache[ws_s] = check_uncommitted_work(ws_s)
            posture = evaluate_rollover_posture(
                cid,
                ws_path=ws_s,
                brain_dir=AGY_BRAIN_DIR,
                step_count=int(s.get("step_count") or 0),
                has_uncommitted_work=uncommitted_cache[ws_s],
            )
            sessions_out.append({
                "conversation_id": cid,
                "title": title,
                "workspace_path": str(s.get("workspace_path") or ""),
                "is_running": bool(s.get("is_running")),
                "is_pinned": bool(s.get("is_pinned")),
                "step_count": int(s.get("step_count") or 0),
                "relative_age": str(s.get("relative_age") or ""),
                "last_updated_ts": float(s.get("last_updated_ts") or 0.0),
                "rollover_posture": posture.get("posture", "FRESH"),
                "capture_count": count_brain_visual_captures(cid, ALLOWED_MEDIA_EXTENSIONS, AGY_BRAIN_DIR),
                "upload_batches": uploads,
                "artifacts": artifacts,
            })

        projects_out.append({
            "project_id": p_id,
            "project_name": p_name,
            "last_updated_ts": float(proj.get("last_updated_ts") or 0.0),
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


def _format_bucket_visual(v: dict[str, Any]) -> dict[str, Any]:
    item_vis: dict[str, Any] = {
        "name": v.get("name") or "image",
        "scope": v.get("scope") or "",
        "rel_path": v.get("rel_path") or "",
        "category": v.get("category") or "session",
        "signed_url": v.get("signed_url") or "",
        "size": v.get("bytes") or v.get("size") or 0,
        "mtime": v.get("mtime") or 0,
    }
    if v.get("workspace_url"):
        item_vis["workspace_url"] = v["workspace_url"]
    return item_vis


def get_session_bucket_payload(conv_id: str) -> dict[str, Any]:
    """Assemble session bucket data (uploads, artifacts, session captures vs shared repo assets, rollover)."""
    if not conv_id or not validate_conv_id(conv_id):
        return {"ok": False, "error": "Missing or invalid conversation_id"}

    ws_path, project_name, title = _resolve_session_workspace_info(conv_id)
    repo_slug = Path(ws_path).name if ws_path else project_name.lower().replace(" ", "-")

    uploads = scan_session_uploads(conv_id)
    artifacts = scan_session_artifacts(conv_id)
    session_raw, repo_raw = discover_visual_buckets(
        conv_id, workspace_path=ws_path, session_limit=40, repo_limit=30, relative=True, db_file=AGY_DB_FILE,
    )
    visual_items = [_format_bucket_visual(v) for v in session_raw]
    repo_visual_items = [_format_bucket_visual(v) for v in repo_raw[:30]]

    posture = evaluate_rollover_posture(conv_id, ws_path=ws_path, brain_dir=AGY_BRAIN_DIR)
    return {
        "ok": True,
        "conversation_id": conv_id,
        "title": title,
        "project_name": project_name,
        "repo_slug": repo_slug,
        "workspace_path": ws_path,
        "uploads": uploads,
        "artifacts": artifacts,
        "visual_artifacts": visual_items,
        "repo_visual_assets": repo_visual_items,
        "rollover": posture,
    }


def build_session_zip(
    conv_id: str,
    requested_files: list[str] | None = None,
    brain_dir: Path | None = None,
    ws_path: str = "",
) -> tuple[int, bytes, str]:
    """Delegate session ZIP assembly while binding module-level AGY_BRAIN_DIR and SQLite resolver."""
    return _bz_build_session_zip(
        conv_id,
        requested_files=requested_files,
        brain_dir=brain_dir,
        ws_path=ws_path,
        ws_resolver=_resolve_session_workspace_info,
        default_brain_dir=AGY_BRAIN_DIR,
    )


MAX_DOC_BYTES = 10 * 1024 * 1024


def get_session_file_payload(conv_id: str, rel_path: str) -> tuple[int, dict[str, Any]]:
    """Safely fetch file content with path traversal guard, 10 MB cap, and media link rewriting."""
    if not conv_id or not validate_conv_id(conv_id) or not rel_path:
        return 400, {"ok": False, "error": "Missing or invalid conversation_id or rel_path"}

    clean_rel = rel_path.strip().lstrip("/")
    if ".." in Path(clean_rel).parts or is_sensitive_filename(clean_rel):
        return 403, {"ok": False, "error": "Path traversal or sensitive file rejected"}

    brain_dir = (AGY_BRAIN_DIR / conv_id).resolve()
    raw_brain = brain_dir / clean_rel
    if raw_brain.is_symlink():
        return 403, {"ok": False, "error": "Symlink rejected"}
    target = raw_brain.resolve()
    if target == brain_dir or not target.is_relative_to(brain_dir) or not target.is_file():
        if clean_rel.startswith("staged_handoffs/"):
            staged_root = (AGY_BG_DIR / "staged_handoffs").resolve()
            raw_stg = AGY_BG_DIR / clean_rel
            if raw_stg.is_symlink():
                return 403, {"ok": False, "error": "Symlink rejected"}
            stg_file = raw_stg.resolve()
            if stg_file != staged_root and stg_file.is_relative_to(staged_root) and stg_file.is_file():
                target = stg_file
            else:
                return 404, {"ok": False, "error": "File not found"}
        else:
            return 404, {"ok": False, "error": "File not found"}

    if target.is_symlink() or is_sensitive_filename(target.name):
        return 403, {"ok": False, "error": "Sensitive or symlink file rejected"}

    try:
        st = target.stat()
        if st.st_size > MAX_DOC_BYTES:
            return 413, {"ok": False, "error": "File exceeds 10 MB preview limit"}
        raw_text = target.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return 500, {"ok": False, "error": f"Failed reading file: {e}"}

    ws_path, _, _ = _resolve_session_workspace_info(conv_id)
    rewritten_text = rewrite_markdown_media_links(raw_text, conv_id, ws_path=ws_path)
    return 200, {
        "ok": True,
        "conversation_id": conv_id,
        "rel_path": clean_rel,
        "content": rewritten_text,
        "raw_content": raw_text,
        "size": st.st_size,
        "mtime": st.st_mtime,
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
    supplied_pass = ""
    for hk, hv in headers:
        if hk.lower() == b"x-nexus-passphrase":
            supplied_pass = hv.decode("utf-8", errors="ignore").strip()
            break

    if not verify_passphrase(supplied_pass):
        await _send_json(send, 401, {"ok": False, "error": "Invalid spoken deadbolt passphrase."}, [(b"cache-control", b"no-store")])
        return

    if req_path.endswith("/web/api/workspace/tree") or req_path.endswith("/api/workspace/tree"):
        await _send_json(send, 200, await anyio.to_thread.run_sync(build_workspace_tree_payload))
        return

    for pattern, kind in (
        (r"/api/sessions/([^/]+)/bucket$", "bucket"),
        (r"/api/sessions/([^/]+)/file$", "file"),
        (r"/api/sessions/([^/]+)/download-zip$", "zip"),
    ):
        m_route = re.search(pattern, req_path)
        if not m_route:
            continue
        cid = m_route.group(1).strip()
        if not validate_conv_id(cid):
            await _send_json(send, 400, {"ok": False, "error": "Invalid conversation_id"})
            return
        if kind == "bucket":
            await _send_json(send, 200, await anyio.to_thread.run_sync(get_session_bucket_payload, cid))
        elif kind == "file":
            rel_path = ""
            for kv in raw_qs.split("&"):
                if kv.startswith("path="):
                    rel_path = urllib.parse.unquote(kv.split("=", 1)[1].strip())
            status_code, payload = await anyio.to_thread.run_sync(get_session_file_payload, cid, rel_path)
            await _send_json(send, status_code, payload)
        else:
            ws_path, _, _ = await anyio.to_thread.run_sync(_resolve_session_workspace_info, cid)
            await _handle_download_zip(receive, send, cid, ws_path=ws_path, brain_dir=AGY_BRAIN_DIR)
        return

    await _send_json(send, 404, {"ok": False, "error": "Endpoint not found"})

