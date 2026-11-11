#!/usr/bin/env python3
"""
agy_nexus.uploads — Session Scratch Batch Uploads Handler, Traversal Guards & INDEX.md Generation.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any
import urllib.parse

from starlette.requests import Request
from starlette.responses import JSONResponse

import agy_nexus.config as cfg
from agy_nexus.config import AGY_BRAIN_DIR, verify_passphrase
from agy_nexus.media import ALLOWED_MEDIA_EXTENSIONS, sign_media_url

MAX_BATCH_FILES = 100
MAX_BATCH_BYTES = 200 * 1024 * 1024  # 200 MB
SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
SAFE_LABEL_RE = re.compile(r"^[a-z0-9_-]{1,32}$")


def validate_conv_id(conv_id: str) -> bool:
    """Validate conversation ID format against path traversal attacks."""
    if not conv_id or not isinstance(conv_id, str):
        return False
    clean = conv_id.strip()
    return bool(SAFE_ID_RE.match(clean) and ".." not in clean and "/" not in clean and "\\" not in clean)


def sanitize_filename(name: str, fallback_idx: int = 1) -> str:
    """Sanitize filename to safe ASCII/alphanumeric characters while preserving extension."""
    raw = Path(name).name
    stem = re.sub(r"[^a-zA-Z0-9_.-]", "_", raw).strip("._")
    if not stem:
        stem = f"file_{fallback_idx:02d}.bin"
    return stem[:80]


def format_byte_size(num_bytes: int) -> str:
    """Format bytes into human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024.0 or unit == "GB":
            return f"{num_bytes:.1f} {unit}" if unit != "B" else f"{num_bytes} B"
        num_bytes /= 1024.0
    return f"{num_bytes} B"


def save_scratch_upload_batch(
    conv_id: str,
    files_data: list[tuple[str, bytes, str]],
    label: str = "",
    brain_dir: Path = AGY_BRAIN_DIR,
) -> dict[str, Any]:
    """Save a batch of uploaded files into ~/.gemini/antigravity/brain/<conv_id>/scratch/uploads_YYYYMMDD_HHMMSS[_label]/."""
    if not validate_conv_id(conv_id):
        return {"ok": False, "status": "ERROR", "error": "Invalid conversation ID or path traversal detected."}

    session_dir = (brain_dir / conv_id).resolve()
    if not session_dir.is_relative_to(brain_dir.resolve()):
        return {"ok": False, "status": "ERROR", "error": "Path escapes session brain root boundary."}

    if not files_data:
        return {"ok": False, "status": "ERROR", "error": "No files provided in upload batch."}

    if len(files_data) > MAX_BATCH_FILES:
        return {"ok": False, "status": "ERROR", "error": f"Batch file count ({len(files_data)}) exceeds limit ({MAX_BATCH_FILES})."}

    total_bytes = sum(len(content) for _, content, _ in files_data)
    if total_bytes > MAX_BATCH_BYTES:
        return {"ok": False, "status": "ERROR", "error": f"Batch total size ({format_byte_size(total_bytes)}) exceeds 200 MB limit."}

    clean_label = label.strip().lower()
    if clean_label and not SAFE_LABEL_RE.match(clean_label):
        clean_label = re.sub(r"[^a-z0-9_-]", "", clean_label)[:32]

    now_utc = datetime.now(timezone.utc)
    ts_str = now_utc.strftime("%Y%m%d_%H%M%S")
    base_folder = f"uploads_{ts_str}_{clean_label}" if clean_label else f"uploads_{ts_str}"
    folder_name = base_folder
    seq_bump = 2
    while (session_dir / "scratch" / folder_name).exists():
        folder_name = f"{base_folder}_{seq_bump}"
        seq_bump += 1
    target_dir = session_dir / "scratch" / folder_name
    target_dir.mkdir(parents=True, exist_ok=True)

    saved_records: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    for idx, (orig_name, content, mime_type) in enumerate(files_data, 1):
        clean_name = sanitize_filename(orig_name, fallback_idx=idx)
        # Sequence-prefixed saved filename to maintain exact arrival order
        saved_name = f"{idx:02d}_{clean_name}"
        if saved_name in seen_names:
            saved_name = f"{idx:02d}_{idx}_{clean_name}"
        seen_names.add(saved_name)

        dest_file = target_dir / saved_name
        dest_file.write_bytes(content)

        file_sz = len(content)
        saved_records.append({
            "seq": idx,
            "original_name": orig_name,
            "saved_name": saved_name,
            "bytes": file_sz,
            "size_formatted": format_byte_size(file_sz),
            "mime_type": mime_type or "application/octet-stream",
            "is_image": dest_file.suffix.lower() in ALLOWED_MEDIA_EXTENSIONS,
        })

    # Generate Markdown INDEX.md
    index_lines = [
        f"# Scratch Upload Batch: {folder_name}",
        "",
        f"- **Session ID**: `{conv_id}`",
        f"- **Uploaded At**: {now_utc.isoformat()}",
        f"- **Batch Folder**: `~/.gemini/antigravity/brain/{conv_id}/scratch/{folder_name}/`",
        f"- **Total Files**: {len(saved_records)}",
        f"- **Total Bytes**: {total_bytes:,} bytes ({format_byte_size(total_bytes)})",
        f"- **Batch Label**: `{clean_label or 'none'}`",
        "",
        "## File Index",
        "",
        "| Seq | Original Filename | Saved Filename | Size | Type |",
        "| :-: | :--- | :--- | :-: | :--- |",
    ]
    for r in saved_records:
        index_lines.append(f"| {r['seq']:02d} | `{r['original_name']}` | `{r['saved_name']}` | {r['size_formatted']} | {r['mime_type']} |")

    index_lines.append("")
    index_file = target_dir / "INDEX.md"
    index_file.write_text("\n".join(index_lines), encoding="utf-8")

    app_prompt = f"Evaluate the {len(saved_records)} uploaded files in ~/.gemini/antigravity/brain/{conv_id}/scratch/{folder_name}/ (see INDEX.md for sequence order)."

    return {
        "ok": True,
        "status": "UPLOADED",
        "conversation_id": conv_id,
        "folder_name": folder_name,
        "batch_folder": str(target_dir),
        "relative_folder": f"scratch/{folder_name}",
        "file_count": len(saved_records),
        "total_bytes": total_bytes,
        "total_size_formatted": format_byte_size(total_bytes),
        "app_prompt": app_prompt,
        "index_file": str(index_file),
        "files": saved_records,
    }


def list_scratch_upload_batches(conv_id: str, brain_dir: Path = AGY_BRAIN_DIR) -> list[dict[str, Any]]:
    """Scan and list all timestamped upload batches in ~/.gemini/antigravity/brain/<conv_id>/scratch/uploads_*/."""
    if not validate_conv_id(conv_id):
        return []
    scratch_dir = brain_dir / conv_id / "scratch"
    if not scratch_dir.is_dir():
        return []

    batches: list[dict[str, Any]] = []
    for d in sorted(scratch_dir.glob("uploads_*"), reverse=True):
        if not d.is_dir():
            continue
        try:
            files = [f for f in d.iterdir() if f.is_file() and f.name != "INDEX.md"]
            total_bytes = sum(f.stat().st_size for f in files)
            idx_file = d / "INDEX.md"
            signed_images: list[dict[str, str]] = []
            for img in sorted(files, key=lambda f: f.name):
                if img.suffix.lower() in ALLOWED_MEDIA_EXTENSIONS:
                    rel_p = f"scratch/{d.name}/{img.name}"
                    signed_images.append({
                        "name": img.name,
                        "rel_path": rel_p,
                        "signed_url": sign_media_url(f"brain:{conv_id}", rel_p),
                    })
            batches.append({
                "folder_name": d.name,
                "folder_path": str(d),
                "relative_folder": f"scratch/{d.name}",
                "file_count": len(files),
                "total_bytes": total_bytes,
                "total_size_formatted": format_byte_size(total_bytes),
                "index_file": str(idx_file) if idx_file.is_file() else "",
                "signed_images": signed_images,
                "app_prompt": f"Evaluate the {len(files)} uploaded files in ~/.gemini/antigravity/brain/{conv_id}/scratch/{d.name}/ (see INDEX.md for sequence order).",
            })
        except Exception:
            continue
    return batches


async def handle_session_upload_request(scope: dict[str, Any], receive: Any, send: Any, conv_id: str, headers: list[tuple[bytes, bytes]]) -> None:
    """Handle POST [/web]/api/sessions/{conv_id}/upload ASGI request supporting multipart/form-data and JSON bodies."""
    supplied_pass = ""
    for hk, hv in headers:
        if hk.lower() == b"x-nexus-passphrase":
            supplied_pass = hv.decode("utf-8", errors="ignore").strip()
            break
    if not supplied_pass:
        raw_qs = (scope.get("query_string") or b"").decode("latin-1")
        for kv in raw_qs.split("&"):
            if kv.startswith("passphrase="):
                supplied_pass = urllib.parse.unquote(kv.split("=", 1)[1]).strip()
                break

    if cfg.PASS_HASH and not verify_passphrase(supplied_pass):
        resp = JSONResponse({"ok": False, "status": "UNAUTHORIZED", "error": "Invalid deadbolt passphrase."}, status_code=401)
        await resp(scope, receive, send)
        return

    if not validate_conv_id(conv_id):
        resp = JSONResponse({"ok": False, "status": "BAD_REQUEST", "error": "Invalid conversation ID."}, status_code=400)
        await resp(scope, receive, send)
        return

    req = Request(scope, receive)
    content_type = req.headers.get("content-type", "").lower()
    files_data: list[tuple[str, bytes, str]] = []
    label = ""

    try:
        if "multipart/form-data" in content_type:
            form = await req.form(max_files=MAX_BATCH_FILES + 5, max_fields=50)
            label = str(form.get("label") or "").strip()
            for key, val in form.multi_items():
                if hasattr(val, "filename") and hasattr(val, "read"):
                    data = await val.read()
                    if val.filename:
                        files_data.append((val.filename, data, getattr(val, "content_type", "") or ""))
        else:
            body = await req.json()
            label = str(body.get("label") or "").strip()
            import base64
            for item in body.get("files", []):
                fname = str(item.get("name") or "file.bin")
                b64 = str(item.get("content_base64") or "")
                raw_bytes = base64.b64decode(b64) if b64 else str(item.get("content") or "").encode("utf-8")
                files_data.append((fname, raw_bytes, str(item.get("type") or "")))
    except Exception as e:
        resp = JSONResponse({"ok": False, "status": "ERROR", "error": f"Failed parsing upload body: {e}"}, status_code=400)
        await resp(scope, receive, send)
        return

    result = save_scratch_upload_batch(conv_id, files_data, label=label)
    status_code = 200 if result.get("ok") else 400
    resp = JSONResponse(result, status_code=status_code)
    await resp(scope, receive, send)
