#!/usr/bin/env python3
"""agy_nexus.bucket_scanner — Session Upload/Artifact Scanners & Markdown Media URL Rewriter."""
from __future__ import annotations

from pathlib import Path
import re
import time
from typing import Any
import urllib.parse

import agy_nexus.config as cfg
from agy_nexus.hygiene import is_sensitive_filename
from agy_nexus.media import ALLOWED_MEDIA_EXTENSIONS, sign_media_url
from agy_nexus.uploads import validate_conv_id


def rewrite_markdown_media_links(
    md_content: str,
    conv_id: str,
    ws_path: str = "",
    ttl_seconds: int = 604800,
    brain_dir: Path | None = None,
) -> str:
    """Rewrite local file:///... and relative image references into 7-day signed /web/media/ URLs."""
    if not md_content or not conv_id or not validate_conv_id(conv_id):
        return md_content or ""

    base_brain = (brain_dir if brain_dir is not None else cfg.AGY_BRAIN_DIR).resolve()
    raw_s_dir = (brain_dir if brain_dir is not None else cfg.AGY_BRAIN_DIR) / conv_id
    if raw_s_dir.is_symlink():
        return md_content
    s_brain_dir = raw_s_dir.resolve()
    if not s_brain_dir.is_relative_to(base_brain):
        return md_content
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
                    if res_path != s_brain_dir and res_path.is_relative_to(s_brain_dir):
                        rel = str(res_path.relative_to(s_brain_dir)).replace("\\", "/")
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
                (s_brain_dir, f"brain:{conv_id}"),
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


def scan_session_uploads(conv_id: str, brain_dir: Path | None = None) -> list[dict[str, Any]]:
    """Scan scratch/uploads_YYYYMMDD_HHMMSS[_label] directories for a session."""
    if not conv_id or not validate_conv_id(conv_id):
        return []
    raw_brain = brain_dir if brain_dir is not None else cfg.AGY_BRAIN_DIR
    base_res = raw_brain.resolve()
    conv_root = raw_brain / conv_id
    if not conv_root.is_dir() or conv_root.is_symlink() or not conv_root.resolve().is_relative_to(base_res):
        return []
    scratch_dir = conv_root / "scratch"
    if not scratch_dir.is_dir() or scratch_dir.is_symlink():
        return []
    scratch_res = scratch_dir.resolve()
    if not scratch_res.is_relative_to(conv_root.resolve()):
        return []

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


def scan_session_artifacts(conv_id: str, brain_dir: Path | None = None) -> list[dict[str, Any]]:
    """Scan markdown artifacts and handoffs in session brain folder."""
    if not conv_id or not validate_conv_id(conv_id):
        return []
    raw_brain = brain_dir if brain_dir is not None else cfg.AGY_BRAIN_DIR
    base_res = raw_brain.resolve()
    b_dir = raw_brain / conv_id
    if not b_dir.is_dir() or b_dir.is_symlink() or not b_dir.resolve().is_relative_to(base_res):
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
