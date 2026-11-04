#!/usr/bin/env python3
"""
agy_nexus.media — Ephemeral 30-Minute HMAC-Signed /web/media/ Serving & Visual Artifact Discovery.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import os
from pathlib import Path
import re
import time
from typing import Any
import urllib.parse

import agy_nexus.config as cfg

ALLOWED_MEDIA_EXTENSIONS: dict[str, bytes] = {
    ".png": b"image/png",
    ".jpg": b"image/jpeg",
    ".jpeg": b"image/jpeg",
    ".webp": b"image/webp",
    ".svg": b"image/svg+xml",
    ".gif": b"image/gif",
}

MEDIA_TTL_SECONDS = int(os.getenv("AG_BRIDGE_MEDIA_TTL", "1800"))


def get_public_base_url() -> str:
    """Return configured public base URL, falling back to the host bridge hostname + BIND_PORT."""
    explicit = os.getenv("AG_BRIDGE_PUBLIC_URL", "").strip().rstrip("/")
    if explicit:
        return explicit
    parsed = urllib.parse.urlparse(cfg.AGY_HOST_BRIDGE_URL)
    host = parsed.hostname or "127.0.0.1"
    return f"http://{host}:{cfg.BIND_PORT}"


def compute_media_hmac(exp_ts: int, scope: str, rel_path: str, pass_hash: str | None = None) -> str:
    """Compute 32-char hex HMAC-SHA256 signature for an ephemeral media link."""
    secret_hex = (pass_hash if pass_hash is not None else cfg.PASS_HASH) or "default-unconfigured-hash"
    clean_rel = rel_path.lstrip("/")
    msg = f"{int(exp_ts)}:{scope}:{clean_rel}".encode("utf-8")
    return hmac.new(secret_hex.encode("utf-8"), msg, hashlib.sha256).hexdigest()[:32]


def sign_media_url(scope: str, rel_path: str, ttl_seconds: int = MEDIA_TTL_SECONDS, exp_ts: int | None = None) -> str:
    """Generate a 30-minute HMAC-signed /web/media/<exp_ts>/<hmac_sig>/<scope>/<rel_path> URL."""
    exp_val = int(exp_ts) if exp_ts is not None else int(time.time()) + int(ttl_seconds)
    clean_rel = rel_path.lstrip("/")
    sig = compute_media_hmac(exp_val, scope, clean_rel)
    quoted_scope = urllib.parse.quote(scope, safe=":")
    quoted_rel = urllib.parse.quote(clean_rel, safe="/")
    path_part = f"/web/media/{exp_val}/{sig}/{quoted_scope}/{quoted_rel}"
    base = get_public_base_url()
    return f"{base}{path_part}" if base else path_part


def _resolve_scope_base_dir(scope: str) -> Path | None:
    """Resolve 'brain:<conv_id>' or 'repo:<repo_name>' to a canonical base directory."""
    if scope.startswith("brain:"):
        conv_id = re.sub(r"[^a-zA-Z0-9_-]", "", scope.split(":", 1)[1])
        if not conv_id:
            return None
        cand = (cfg.AGY_BRAIN_DIR / conv_id).resolve()
        if cand.is_relative_to(cfg.AGY_BRAIN_DIR.resolve()) and cand.is_dir():
            return cand
        return None
    if scope.startswith("repo:"):
        repo_name = re.sub(r"[^a-zA-Z0-9_.-]", "", scope.split(":", 1)[1])
        if not repo_name:
            return None
        for root_dir in (cfg.AGY_GITLAB_DIR, cfg.AGY_DATA_DIR / "worktrees"):
            if root_dir.is_dir():
                cand = (root_dir / repo_name).resolve()
                if cand.is_relative_to(root_dir.resolve()) and cand.is_dir():
                    return cand
        return None
    return None


def verify_and_resolve_media(req_path: str) -> tuple[Path | None, bytes, int, str]:
    """Verify HMAC signature, expiration, and path sandboxing for GET /web/media/<exp>/<sig>/<scope>/<rel_path>."""
    if "/web/media/" not in req_path:
        return None, b"application/json", 404, "Not a media route."
    tail = req_path.split("/web/media/", 1)[1].lstrip("/")
    parts = tail.split("/", 3)
    if len(parts) < 4:
        return None, b"application/json", 400, "Malformed media URL path."
    exp_str, supplied_sig, raw_scope, raw_rel = parts[0], parts[1].strip().lower(), parts[2], parts[3]
    try:
        exp_ts = int(exp_str)
    except ValueError:
        return None, b"application/json", 400, "Invalid expiration timestamp."
    if exp_ts < int(time.time()):
        return None, b"application/json", 403, "Ephemeral media link has expired."

    scope = urllib.parse.unquote(raw_scope)
    rel_path = urllib.parse.unquote(raw_rel).lstrip("/")
    if not rel_path or ".." in Path(rel_path).parts:
        return None, b"application/json", 403, "Path traversal rejected."

    expected_sig = compute_media_hmac(exp_ts, scope, rel_path).lower()
    if not hmac.compare_digest(supplied_sig, expected_sig):
        return None, b"application/json", 403, "Invalid media HMAC signature."

    base_dir = _resolve_scope_base_dir(scope)
    if base_dir is None:
        return None, b"application/json", 404, "Media scope directory not found."

    try:
        target = (base_dir / rel_path).resolve()
        if not target.is_relative_to(base_dir):
            return None, b"application/json", 403, "Path escapes scope boundary."
    except Exception:
        return None, b"application/json", 403, "Invalid target path."

    ext = target.suffix.lower()
    if ext not in ALLOWED_MEDIA_EXTENSIONS:
        return None, b"application/json", 403, f"Unsupported media extension '{ext}'."
    if not target.is_file():
        return None, b"application/json", 404, "Media file not found."
    return target, ALLOWED_MEDIA_EXTENSIONS[ext], 200, "OK"


def discover_visual_artifacts(conv_id: str, workspace_path: str = "", limit: int = 15) -> list[dict[str, Any]]:
    """Scan session brain directory and active workspace for recent visual artifacts (.png/.jpg/.webp/.svg)."""
    candidates: list[tuple[float, dict[str, Any]]] = []
    seen_realpaths: set[str] = set()

    def _scan_dir(base_dir: Path, scope: str, subdirs: tuple[str, ...]) -> None:
        if not base_dir.is_dir():
            return
        search_dirs = [base_dir] + [base_dir / sd for sd in subdirs if (base_dir / sd).is_dir()]
        for sdir in search_dirs:
            try:
                for entry in sdir.iterdir():
                    if not entry.is_file() or entry.suffix.lower() not in ALLOWED_MEDIA_EXTENSIONS:
                        continue
                    rp = str(entry.resolve())
                    if rp in seen_realpaths:
                        continue
                    seen_realpaths.add(rp)
                    st = entry.stat()
                    rel_str = str(entry.resolve().relative_to(base_dir.resolve())).replace("\\", "/")
                    candidates.append((
                        st.st_mtime,
                        {
                            "name": entry.name,
                            "scope": scope,
                            "rel_path": rel_str,
                            "bytes": st.st_size,
                            "modified_at": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
                            "signed_url": sign_media_url(scope, rel_str),
                        },
                    ))
            except Exception:
                continue

    if conv_id:
        brain_dir = (cfg.AGY_BRAIN_DIR / conv_id).resolve()
        if brain_dir.is_dir():
            _scan_dir(brain_dir, f"brain:{conv_id}", ("scratch", ".user_uploaded"))

    if workspace_path:
        ws_path = Path(workspace_path).resolve()
        if ws_path.is_dir() and (
            ws_path.is_relative_to(cfg.AGY_GITLAB_DIR.resolve())
            or ws_path.is_relative_to((cfg.AGY_DATA_DIR / "worktrees").resolve())
        ):
            _scan_dir(ws_path, f"repo:{ws_path.name}", ("docs/assets", "screenshots", "scratch", "sidecars/ag-bridge-mcp/docs/assets"))

    candidates.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in candidates[: max(1, min(limit, 30))]]
