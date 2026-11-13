#!/usr/bin/env python3
"""
agy_nexus.media — Ephemeral 30-Minute HMAC-Signed /web/media/ Serving & Visual Artifact Discovery.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import ipaddress
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
_VERIFIED_REQUEST_ORIGIN: str = ""
_SAFE_HOST_RE = re.compile(r"^[A-Za-z0-9.-]+(?::\d{1,5})?$")


def _sanitize_public_origin(raw_url: str) -> str:
    """Extract scheme://netloc only so capability PATH_SECRET paths are never leaked in media links."""
    cand = (raw_url or "").strip()
    if not cand:
        return ""
    parsed = urllib.parse.urlparse(cand if "://" in cand else f"https://{cand}")
    if parsed.scheme not in ("https", "http") or not parsed.netloc or not _SAFE_HOST_RE.match(parsed.netloc):
        return ""
    host_low = (parsed.hostname or "").lower()
    if not host_low or host_low == "example.com" or host_low.endswith(".example.com"):
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


def _is_public_hostname(h: str) -> bool:
    if not h or h in ("localhost", "host.docker.internal") or h.endswith((".lan", ".local", ".internal", ".home.arpa")):
        return False
    try:
        return ipaddress.ip_address(h).is_global
    except ValueError:
        return "." in h


def record_verified_public_origin(headers: list[tuple[bytes, bytes]], client_ip: str = "") -> None:
    """Capture public https origin from a request already authenticated by capability PATH_SECRET."""
    global _VERIFIED_REQUEST_ORIGIN
    if _VERIFIED_REQUEST_ORIGIN:
        return
    xfh, host_hdr, proto_val = "", "", "https"
    for hk, hv in headers:
        kl = hk.lower()
        if kl == b"x-forwarded-host" and not xfh:
            xfh = hv.decode("latin-1", errors="ignore").split(",", 1)[0].strip()
        elif kl == b"host" and not host_hdr:
            host_hdr = hv.decode("latin-1", errors="ignore").strip()
        elif kl == b"x-forwarded-proto":
            proto_val = hv.decode("latin-1", errors="ignore").split(",", 1)[0].strip().lower() or "https"
    trusted_proxy = False
    if client_ip:
        try:
            ip_obj = ipaddress.ip_address(client_ip)
            trusted_proxy = ip_obj.is_loopback or ip_obj.is_private
        except ValueError:
            trusted_proxy = False
    cand_host = (xfh or host_hdr) if trusted_proxy else host_hdr
    clean = _sanitize_public_origin(f"{proto_val if proto_val in ('https', 'http') else 'https'}://{cand_host}")
    if clean and _is_public_hostname((urllib.parse.urlparse(clean).hostname or "").lower()):
        _VERIFIED_REQUEST_ORIGIN = clean


def get_public_base_url() -> str:
    """Return configured or verified public https base origin, falling back to local host + BIND_PORT."""
    explicit = _sanitize_public_origin(os.getenv("AG_BRIDGE_PUBLIC_URL", ""))
    if explicit:
        return explicit
    sub_hash = os.getenv("SUBDOMAIN_HASH", "").strip()
    domain = os.getenv("AG_BRIDGE_DOMAIN", "").strip()
    if sub_hash and domain and domain.lower() != "example.com":
        built = _sanitize_public_origin(f"https://ag-{sub_hash}.{domain}")
        if built:
            return built
    derived = _sanitize_public_origin(os.getenv("_DERIVED_SECRETS_PUBLIC_URL", ""))
    if derived:
        return derived
    if _VERIFIED_REQUEST_ORIGIN:
        return _VERIFIED_REQUEST_ORIGIN
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
        brain_root = cfg.AGY_BRAIN_DIR.resolve()
        cand = (cfg.AGY_BRAIN_DIR / conv_id).resolve()
        if cand != brain_root and cand.is_relative_to(brain_root) and cand.is_dir():
            return cand
        return None
    if scope.startswith("repo:"):
        repo_name = re.sub(r"[^a-zA-Z0-9_.-]", "", scope.split(":", 1)[1])
        if not repo_name or repo_name in (".", ".."):
            return None
        pkg_root = Path(__file__).resolve().parents[2]
        if repo_name == pkg_root.name and pkg_root.is_dir():
            return pkg_root.resolve()
        candidate_roots = list(cfg.get_workspace_pillar_roots()) + [cfg.AGY_GITLAB_DIR, cfg.AGY_DATA_DIR / "worktrees"]
        for root_dir in candidate_roots:
            if root_dir.is_dir():
                root_res = root_dir.resolve()
                cand = (root_dir / repo_name).resolve()
                if cand != root_res and cand.is_relative_to(root_res) and cand.is_dir():
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
        if target == base_dir or not target.is_relative_to(base_dir):
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
        extra_dirs: list[Path] = []
        for sd in subdirs:
            parent_sd = base_dir / sd
            if parent_sd.is_dir():
                try:
                    for child in parent_sd.iterdir():
                        if child.is_dir() and child.name.startswith("uploads_"):
                            extra_dirs.append(child)
                except Exception:
                    pass
        search_dirs = [base_dir] + [base_dir / sd for sd in subdirs if (base_dir / sd).is_dir()] + extra_dirs
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

    safe_cid = re.sub(r"[^a-zA-Z0-9_-]", "", conv_id)
    if safe_cid:
        brain_root = cfg.AGY_BRAIN_DIR.resolve()
        brain_dir = (cfg.AGY_BRAIN_DIR / safe_cid).resolve()
        if brain_dir != brain_root and brain_dir.is_relative_to(brain_root) and brain_dir.is_dir():
            _scan_dir(brain_dir, f"brain:{safe_cid}", ("scratch", ".user_uploaded"))

    if workspace_path:
        ws_path = Path(workspace_path).resolve()
        pkg_root = Path(__file__).resolve().parents[2]
        forbidden = {Path("/").resolve(), Path.home().resolve(), *cfg.get_umbrella_roots()}
        ws_roots = (set(cfg.get_workspace_pillar_roots()) | {(cfg.AGY_DATA_DIR / "worktrees").resolve()}) - {
            Path("/").resolve(),
            Path.home().resolve(),
        }
        if ws_path.is_dir() and ws_path not in forbidden and (
            ws_path == pkg_root.resolve() or any(ws_path != r and ws_path.is_relative_to(r) for r in ws_roots)
        ):
            _scan_dir(ws_path, f"repo:{ws_path.name}", ("docs/assets", "screenshots", "scratch", "sidecars/ag-bridge-mcp/docs/assets"))

    candidates.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in candidates[: max(1, min(limit, 30))]]
