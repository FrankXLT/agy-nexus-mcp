#!/usr/bin/env python3
"""agy_nexus.bucket_zip — Repository-Aware Session Visual ZIP Archiver & Download Handler."""
from __future__ import annotations

import anyio
import functools
import io
import json
from pathlib import Path
import re
from typing import Any, Callable
import zipfile

from agy_nexus.config import AGY_BRAIN_DIR
from agy_nexus.hygiene import is_sensitive_filename
from agy_nexus.media import (
    ALLOWED_MEDIA_EXTENSIONS,
    _walk_media_tree,
    discover_visual_artifacts,
    is_allowed_workspace_dir,
)
from agy_nexus.uploads import validate_conv_id

MAX_ZIP_REQ_BODY = 256 * 1024
MAX_ZIP_FILES = 100
MAX_ZIP_FILE_BYTES = 45 * 1024 * 1024
MAX_ZIP_TOTAL_BYTES = 200 * 1024 * 1024


def resolve_zip_entry(
    raw_f: str,
    conv_id: str,
    target_brain: Path,
    ws_dir: Path | None,
) -> tuple[int, Path | None, str]:
    """Resolve one requested ZIP item across brain:<conv_id>/ and validated repo:<slug>/ boundaries."""
    if not raw_f or raw_f.startswith(("/", "\\")) or ".." in Path(raw_f).parts:
        return 403, None, "Path traversal rejected"

    scope_mode, clean_rel = "auto", raw_f.lstrip("/")
    if raw_f.startswith("brain:"):
        if not raw_f.startswith(f"brain:{conv_id}/"):
            return 403, None, "Cross-session brain path rejected"
        scope_mode = "brain"
        clean_rel = raw_f.split("/", 1)[1].lstrip("/")
    elif raw_f.startswith("repo:"):
        if "/" not in raw_f:
            return 400, None, "Malformed repo path"
        prefix, tail = raw_f.split("/", 1)
        req_slug = prefix.split(":", 1)[1]
        if ws_dir is None or ws_dir.name != req_slug:
            return 404, None, "Repository scope mismatch"
        scope_mode = "repo"
        clean_rel = tail.lstrip("/")

    if not clean_rel or ".." in Path(clean_rel).parts or is_sensitive_filename(clean_rel):
        return 403, None, "Path traversal or sensitive file rejected"

    roots: list[Path] = []
    if scope_mode in ("brain", "auto") and target_brain.is_dir():
        roots.append(target_brain)
    if scope_mode in ("repo", "auto") and ws_dir is not None:
        roots.append(ws_dir)

    for root in roots:
        raw_target = root / clean_rel
        if raw_target.is_symlink():
            return 403, None, "Symlink rejected"
        target = raw_target.resolve()
        if target == root or not target.is_relative_to(root):
            return 403, None, "Path traversal rejected"
        if target.is_file():
            if target.suffix.lower() not in ALLOWED_MEDIA_EXTENSIONS or is_sensitive_filename(target.name):
                return 403, None, "Unsupported or sensitive file rejected"
            return 200, target, ""
    return 200, None, ""


def _append_safe_zip_candidate(raw_cand: Path, boundary: Path, seen_real: set[str], out: list[Path]) -> None:
    try:
        if raw_cand.is_symlink():
            return
        rp = raw_cand.resolve()
        if (
            rp != boundary
            and rp.is_relative_to(boundary)
            and rp.is_file()
            and rp.suffix.lower() in ALLOWED_MEDIA_EXTENSIONS
            and not is_sensitive_filename(rp.name)
            and str(rp) not in seen_real
        ):
            seen_real.add(str(rp))
            out.append(rp)
    except Exception:
        return


def build_session_zip(
    conv_id: str,
    requested_files: list[str] | None = None,
    brain_dir: Path | None = None,
    ws_path: str = "",
    ws_resolver: Callable[[str], tuple[str, str, str]] | None = None,
    default_brain_dir: Path | None = None,
) -> tuple[int, bytes, str]:
    """Build in-memory zipfile of requested visual files inside brain/<conv_id>/ and validated ws_path."""
    if not conv_id or not validate_conv_id(conv_id):
        return 400, b'{"ok":false,"error":"Invalid conversation_id"}', "application/json"
    target_brain = ((brain_dir or default_brain_dir or AGY_BRAIN_DIR) / conv_id).resolve()
    eff_ws = ws_path or (ws_resolver(conv_id)[0] if (ws_resolver and brain_dir is None) else "")
    ws_dir = Path(eff_ws).resolve() if eff_ws and is_allowed_workspace_dir(eff_ws) else None
    if not target_brain.is_dir() and ws_dir is None:
        return 404, b'{"ok":false,"error":"Session brain or workspace not found"}', "application/json"

    files_to_add: list[Path] = []
    seen_real: set[str] = set()
    total_raw_bytes = 0
    if requested_files is not None:
        if len(requested_files) > MAX_ZIP_FILES:
            return 400, json.dumps({"ok": False, "error": f"Too many files requested (max {MAX_ZIP_FILES})"}).encode("utf-8"), "application/json"
        for f in requested_files:
            code, target, err_msg = resolve_zip_entry(str(f).strip(), conv_id, target_brain, ws_dir)
            if code != 200:
                return code, json.dumps({"ok": False, "error": err_msg}).encode("utf-8"), "application/json"
            if target is not None and str(target) not in seen_real:
                try:
                    sz = int(target.stat().st_size)
                except OSError:
                    sz = 0
                if sz > MAX_ZIP_FILE_BYTES:
                    return 413, json.dumps({"ok": False, "error": f"File '{target.name}' exceeds 45 MB ZIP limit"}).encode("utf-8"), "application/json"
                if total_raw_bytes + sz > MAX_ZIP_TOTAL_BYTES:
                    return 413, json.dumps({"ok": False, "error": "Selected files exceed 200 MB uncompressed ZIP limit"}).encode("utf-8"), "application/json"
                total_raw_bytes += sz
                seen_real.add(str(target))
                files_to_add.append(target)
    else:
        cands: list[tuple[Path, Path]] = []
        if target_brain.is_dir():
            for p in _walk_media_tree(target_brain, max_depth=3, allow_dot_dirs=frozenset({".user_uploaded"})):
                cands.append((p, target_brain))
        if ws_dir is not None:
            for item in discover_visual_artifacts("", str(ws_dir), limit=40, relative=True):
                cands.append((ws_dir / str(item.get("rel_path") or ""), ws_dir))
        for raw_p, bnd in cands:
            if len(files_to_add) >= MAX_ZIP_FILES:
                break
            pre_len = len(files_to_add)
            _append_safe_zip_candidate(raw_p, bnd, seen_real, files_to_add)
            if len(files_to_add) > pre_len:
                added = files_to_add[-1]
                try:
                    sz = int(added.stat().st_size)
                except OSError:
                    sz = 0
                if sz > MAX_ZIP_FILE_BYTES or total_raw_bytes + sz > MAX_ZIP_TOTAL_BYTES:
                    files_to_add.pop()
                    seen_real.discard(str(added))
                    continue
                total_raw_bytes += sz

    buf = io.BytesIO()
    used_arcnames: set[str] = set()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fpath in files_to_add:
            arcname = fpath.name
            if arcname in used_arcnames:
                n = 2
                while f"{fpath.stem}_{n}{fpath.suffix}" in used_arcnames:
                    n += 1
                arcname = f"{fpath.stem}_{n}{fpath.suffix}"
            used_arcnames.add(arcname)
            try:
                zf.write(fpath, arcname=arcname)
            except Exception:
                pass
    buf.seek(0)
    return 200, buf.getvalue(), "application/zip"


async def send_json(send: Any, status: int, data: dict[str, Any], extra_headers: list[tuple[bytes, bytes]] | None = None) -> None:
    """Serialize JSON payload and emit ASGI HTTP response."""
    body_b = json.dumps(data).encode("utf-8")
    hdrs = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body_b)).encode("ascii")),
        (b"cache-control", b"no-store, no-cache, private"),
        (b"x-content-type-options", b"nosniff"),
    ]
    if extra_headers:
        hdrs.extend(extra_headers)
    await send({"type": "http.response.start", "status": status, "headers": hdrs})
    await send({"type": "http.response.body", "body": body_b})


async def handle_download_zip(
    receive: Any,
    send: Any,
    cid: str,
    ws_path: str,
    brain_dir: Path | None = None,
) -> None:
    """Parse requested file list and stream a ZIP archive covering brain and repository captures."""
    chunks: list[bytes] = []
    total_body = 0
    more_body = True
    while more_body:
        message = await receive()
        chunk = message.get("body", b"") or b""
        total_body += len(chunk)
        if total_body > MAX_ZIP_REQ_BODY:
            await send_json(send, 413, {"ok": False, "error": "ZIP request payload exceeds 256 KB limit"})
            return
        chunks.append(chunk)
        more_body = message.get("more_body", False)
    body_bytes = b"".join(chunks)

    requested_files = None
    if body_bytes:
        try:
            b_json = json.loads(body_bytes.decode("utf-8", errors="replace"))
        except Exception:
            await send_json(send, 400, {"ok": False, "error": "Invalid JSON body"})
            return
        if isinstance(b_json, dict) and "files" in b_json:
            requested_files = b_json["files"]
        elif isinstance(b_json, list):
            requested_files = b_json
        if requested_files is not None and not isinstance(requested_files, list):
            await send_json(send, 400, {"ok": False, "error": "'files' must be a JSON array"})
            return

    status_code, payload_b, ctype = await anyio.to_thread.run_sync(
        functools.partial(build_session_zip, cid, requested_files, brain_dir=brain_dir, ws_path=ws_path)
    )
    raw_slug = Path(ws_path).name if ws_path else "session"
    safe_slug = re.sub(r"[^A-Za-z0-9_.-]", "_", raw_slug).strip("._") or "session"
    n_count = len(requested_files) if requested_files is not None else 1
    zip_name = f"captures_{safe_slug}_{n_count}.zip"

    headers_out = [
        (b"content-type", ctype.encode("ascii")),
        (b"content-length", str(len(payload_b)).encode("ascii")),
        (b"cache-control", b"no-store, no-cache, private"),
        (b"x-content-type-options", b"nosniff"),
    ]
    if status_code == 200 and ctype == "application/zip":
        headers_out.append((b"content-disposition", f'attachment; filename="{zip_name}"'.encode("ascii")))

    await send({"type": "http.response.start", "status": status_code, "headers": headers_out})
    await send({"type": "http.response.body", "body": payload_b})
