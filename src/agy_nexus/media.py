#!/usr/bin/env python3
"""
agy_nexus.media — 7-Day HMAC-Signed /web/media/ Serving & Visual Artifact Discovery.
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
from agy_nexus.hygiene import is_sensitive_filename, resolve_source_repo_root
from agy_nexus.media_discovery import (
    classify_repo_media as _classify_repo_media,
    collect_git_status_media as _md_collect_git_status_media,
    collect_repo_folder_media as _collect_repo_folder_media,
    count_brain_visual_captures,
    is_visual_folder_name as _is_visual_folder_name,
    resolve_session_ownership_window as _resolve_session_ownership_window,
    walk_media_tree as _walk_media_tree,
)

ALLOWED_MEDIA_EXTENSIONS: dict[str, bytes] = {
    ".png": b"image/png",
    ".jpg": b"image/jpeg",
    ".jpeg": b"image/jpeg",
    ".webp": b"image/webp",
    ".svg": b"image/svg+xml",
    ".gif": b"image/gif",
}

MEDIA_TTL_SECONDS = int(os.getenv("AG_BRIDGE_MEDIA_TTL", "604800"))
_VERIFIED_REQUEST_ORIGIN: str = ""
_SAFE_HOST_RE = re.compile(r"^[A-Za-z0-9.-]+(?::\d{1,5})?$")
_CONTAINER_HEX_RE = re.compile(r"^[0-9a-f]{12}(?:\.|$)", re.I)


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
    """Check if hostname is public and reject Docker 12-hex container hostnames."""
    if not h or h in ("localhost", "host.docker.internal") or h.endswith((".lan", ".local", ".internal", ".home.arpa")):
        return False
    if h == "example.com" or h.endswith(".example.com"):
        return False
    if _CONTAINER_HEX_RE.search(h):
        return False
    try:
        return ipaddress.ip_address(h).is_global
    except ValueError:
        return "." in h


def record_verified_public_origin(headers: list[tuple[bytes, bytes]], client_ip: str = "") -> None:
    """Capture public https origin from a request already authenticated by capability PATH_SECRET."""
    global _VERIFIED_REQUEST_ORIGIN
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
    if clean:
        cand_h = (urllib.parse.urlparse(clean).hostname or "").lower()
        if _is_public_hostname(cand_h):
            _VERIFIED_REQUEST_ORIGIN = clean


def get_public_base_url() -> str:
    """Return configured or verified public https base origin, falling back to local host + BIND_PORT."""
    explicit = _sanitize_public_origin(os.getenv("AG_BRIDGE_PUBLIC_URL", ""))
    if explicit:
        return explicit
    if _VERIFIED_REQUEST_ORIGIN:
        return _VERIFIED_REQUEST_ORIGIN
    sub_hash = os.getenv("SUBDOMAIN_HASH", "").strip()
    domain = os.getenv("AG_BRIDGE_DOMAIN", "").strip()
    if sub_hash and domain and domain.lower() != "example.com":
        built = _sanitize_public_origin(f"https://ag-{sub_hash}.{domain}")
        if built:
            h = (urllib.parse.urlparse(built).hostname or "").lower()
            if _is_public_hostname(h):
                return built
    derived = _sanitize_public_origin(os.getenv("_DERIVED_SECRETS_PUBLIC_URL", ""))
    if derived:
        h = (urllib.parse.urlparse(derived).hostname or "").lower()
        if _is_public_hostname(h):
            return derived
    parsed = urllib.parse.urlparse(cfg.AGY_HOST_BRIDGE_URL)
    host = parsed.hostname or "127.0.0.1"
    return f"http://{host}:{cfg.BIND_PORT}"


def compute_media_hmac(exp_ts: int, scope: str, rel_path: str, pass_hash: str | None = None) -> str:
    """Compute 32-char hex HMAC-SHA256 signature for a 7-day signed media link."""
    secret_hex = (pass_hash if pass_hash is not None else cfg.PASS_HASH) or "default-unconfigured-hash"
    clean_rel = rel_path.lstrip("/")
    msg = f"{int(exp_ts)}:{scope}:{clean_rel}".encode("utf-8")
    return hmac.new(secret_hex.encode("utf-8"), msg, hashlib.sha256).hexdigest()[:32]


def sign_media_url(
    scope: str,
    rel_path: str,
    ttl_seconds: int = MEDIA_TTL_SECONDS,
    exp_ts: int | None = None,
    relative: bool = False,
) -> str:
    """Generate a 7-day HMAC-signed /web/media/<exp_ts>/<hmac_sig>/<scope>/<rel_path> URL."""
    exp_val = int(exp_ts) if exp_ts is not None else int(time.time()) + int(ttl_seconds)
    clean_rel = rel_path.lstrip("/")
    sig = compute_media_hmac(exp_val, scope, clean_rel)
    quoted_scope = urllib.parse.quote(scope, safe=":")
    quoted_rel = urllib.parse.quote(clean_rel, safe="/")
    path_part = f"/web/media/{exp_val}/{sig}/{quoted_scope}/{quoted_rel}"
    if relative:
        return path_part
    base = get_public_base_url()
    return f"{base}{path_part}" if base else path_part


def is_allowed_workspace_dir(ws_path: Path | str) -> bool:
    """Return True when ws_path is an existing directory strictly inside an allowed workspace or worktree root."""
    if not ws_path:
        return False
    try:
        resolved = Path(ws_path).resolve()
        if not resolved.is_dir():
            return False
        pkg_root = resolve_source_repo_root(__file__)
        forbidden = {Path("/").resolve(), Path.home().resolve(), *cfg.get_umbrella_roots()}
        if resolved in forbidden:
            return False
        if pkg_root is not None and resolved == pkg_root.resolve():
            return True
        ws_roots = (
            set(cfg.get_workspace_pillar_roots())
            | {cfg.AGY_GITLAB_DIR.resolve(), (cfg.AGY_DATA_DIR / "worktrees").resolve()}
        ) - {Path("/").resolve(), Path.home().resolve()}
        return any(resolved != r and resolved.is_relative_to(r) for r in ws_roots)
    except Exception:
        return False


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
        pkg_root = resolve_source_repo_root(__file__)
        if pkg_root is not None and repo_name == pkg_root.name and pkg_root.is_dir():
            return pkg_root.resolve()
        candidate_roots = list(cfg.get_workspace_pillar_roots()) + [cfg.AGY_GITLAB_DIR, cfg.AGY_DATA_DIR / "worktrees"]
        for root_dir in candidate_roots:
            if root_dir.is_dir():
                root_res = root_dir.resolve()
                cand = (root_dir / repo_name).resolve()
                if cand != root_res and cand.is_relative_to(root_res) and cand.is_dir():
                    return cand
        wt_root = cfg.AGY_DATA_DIR / "worktrees"
        if wt_root.is_dir():
            wt_res = wt_root.resolve()
            for wt_sub in sorted(wt_root.iterdir(), key=lambda p: p.name):
                if not wt_sub.is_dir() or wt_sub.is_symlink():
                    continue
                cand = (wt_sub / repo_name).resolve()
                if cand != wt_res and cand.is_relative_to(wt_res) and cand.is_dir():
                    return cand
        return None
    return None


def verify_and_resolve_media(req_path: str) -> tuple[Path | None, bytes, int, str]:
    """Verify HMAC signature, expiration, and path sandboxing for GET /web/media/<exp>/<sig>/<scope>/<rel_path>."""
    clean_req_path = req_path.split("?", 1)[0]
    if "/web/media/" not in clean_req_path:
        return None, b"application/json", 404, "Not a media route."
    tail = clean_req_path.split("/web/media/", 1)[1].lstrip("/")
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
    if not cfg.PASS_HASH:
        return None, b"application/json", 403, "Media signing is not configured."

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


def _collect_git_status_media(ws_path: Path) -> list[Path]:
    """Query git status --porcelain -uall -z (1.5s cap) to detect newly created or modified repo media."""
    return _md_collect_git_status_media(ws_path, ALLOWED_MEDIA_EXTENSIONS)


def build_workspace_deep_link(
    conv_id: str,
    rel_path: str,
    scope: str = "",
    ttl_seconds: int = MEDIA_TTL_SECONDS,
    exp_ts: int | None = None,
) -> str:
    """Generate https://<base>/web?view=workspace&session=<conv_id>&artifact=<rel_path>&t=<exp_ts>&sig=<hmac_sig>&scope=<scope>."""
    exp_val = int(exp_ts) if exp_ts is not None else int(time.time()) + int(ttl_seconds)
    clean_rel = rel_path.lstrip("/")
    eff_scope = scope or (f"brain:{conv_id}" if conv_id else "")
    sig = compute_media_hmac(exp_val, eff_scope, clean_rel)
    base = get_public_base_url()
    params_dict: dict[str, str] = {
        "view": "workspace",
        "session": conv_id,
        "artifact": clean_rel,
        "t": str(exp_val),
        "sig": sig,
    }
    if eff_scope:
        params_dict["scope"] = eff_scope
    params = urllib.parse.urlencode(params_dict)
    return f"{base}/web?{params}" if base else f"/web?{params}"


def _append_media_candidate(
    entry: Path,
    base_res: Path,
    scope: str,
    safe_cid: str,
    relative: bool,
    seen_realpaths: set[str],
    candidates: list[tuple[float, dict[str, Any]]],
    category: str = "session",
) -> None:
    try:
        if entry.is_symlink():
            return
        rp = entry.resolve()
        if rp == base_res or not rp.is_relative_to(base_res):
            return
        if not rp.is_file() or rp.suffix.lower() not in ALLOWED_MEDIA_EXTENSIONS:
            return
        if is_sensitive_filename(entry.name) or is_sensitive_filename(rp.name):
            return
        rp_str = str(rp)
        if rp_str in seen_realpaths:
            return
        seen_realpaths.add(rp_str)
        st = rp.stat()
        rel_str = str(rp.relative_to(base_res)).replace("\\", "/")
        item_dict: dict[str, Any] = {
            "name": rp.name,
            "scope": scope,
            "rel_path": rel_str,
            "category": category,
            "bytes": st.st_size,
            "mtime": st.st_mtime,
            "modified_at": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
            "signed_url": sign_media_url(scope, rel_str, relative=relative),
        }
        if safe_cid:
            item_dict["workspace_url"] = build_workspace_deep_link(safe_cid, rel_str, scope=scope)
        candidates.append((st.st_mtime, item_dict))
    except Exception:
        return


def discover_visual_buckets(
    conv_id: str,
    workspace_path: str = "",
    session_limit: int = 40,
    repo_limit: int = 30,
    relative: bool = False,
    db_file: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Scan and separate session-owned captures ('session') from shared/committed repo assets ('repo_asset')."""
    session_cands: list[tuple[float, dict[str, Any]]] = []
    repo_cands: list[tuple[float, dict[str, Any]]] = []
    seen_realpaths: set[str] = set()

    safe_cid = re.sub(r"[^a-zA-Z0-9_-]", "", conv_id)
    brain_dir: Path | None = None
    if safe_cid:
        brain_root = cfg.AGY_BRAIN_DIR.resolve()
        cand_brain = (cfg.AGY_BRAIN_DIR / safe_cid).resolve()
        if cand_brain != brain_root and cand_brain.is_relative_to(brain_root) and cand_brain.is_dir():
            brain_dir = cand_brain
            b_scope = f"brain:{safe_cid}"
            for fpath in _walk_media_tree(brain_dir, max_depth=3, allow_dot_dirs=frozenset({".user_uploaded"})):
                _append_media_candidate(
                    fpath, brain_dir, b_scope, safe_cid, relative, seen_realpaths, session_cands, category="session",
                )

    if workspace_path and is_allowed_workspace_dir(workspace_path):
        ws_res = Path(workspace_path).resolve()
        r_scope = f"repo:{ws_res.name}"
        git_paths = _collect_git_status_media(ws_res)
        git_real = {str(p.resolve()) for p in git_paths if not p.is_symlink() and p.exists()}
        has_git = (ws_res / ".git").exists()
        is_latest, win_start, win_end = _resolve_session_ownership_window(safe_cid, ws_res, brain_dir, db_file=db_file)
        for fpath in (*git_paths, *_collect_repo_folder_media(ws_res)):
            try:
                if fpath.is_symlink():
                    continue
                rp = fpath.resolve()
                if rp == ws_res or not rp.is_relative_to(ws_res) or not rp.is_file():
                    continue
                cat = _classify_repo_media(rp, ws_res, git_real, has_git, is_latest, win_start, win_end, rp.stat().st_mtime)
            except Exception:
                continue
            target_list = session_cands if cat == "session" else repo_cands
            _append_media_candidate(fpath, ws_res, r_scope, safe_cid, relative, seen_realpaths, target_list, category=cat)

    session_cands.sort(key=lambda item: item[0], reverse=True)
    repo_cands.sort(key=lambda item: item[0], reverse=True)
    s_lim = max(1, min(int(session_limit or 40), 60))
    r_lim = max(1, min(int(repo_limit or 30), 60))
    return [i[1] for i in session_cands[:s_lim]], [i[1] for i in repo_cands[:r_lim]]


def discover_visual_artifacts(
    conv_id: str,
    workspace_path: str = "",
    limit: int = 30,
    relative: bool = False,
    category: str = "",
    db_file: Path | None = None,
) -> list[dict[str, Any]]:
    """Scan session brain and active workspace for visual artifacts, sorted newest-first with category tags."""
    s_items, r_items = discover_visual_buckets(
        conv_id, workspace_path=workspace_path, session_limit=40, repo_limit=40, relative=relative, db_file=db_file,
    )
    if category == "session":
        merged = s_items
    elif category == "repo_asset":
        merged = r_items
    else:
        merged = sorted([*s_items, *r_items], key=lambda item: float(item.get("mtime") or 0.0), reverse=True)
    return merged[: max(1, min(int(limit or 30), 40))]


VISUAL_INSPECTION_HINT = (
    "Share clickable signed_url links at zero extra token cost, and prompt via a 1-tap choice before fetching "
    "screenshots or published HTML into Gemini's Linux VM (curl -A 'Mozilla/5.0 (compatible; Google-Agent; "
    "+https://developers.google.com/crawling/docs/crawlers-fetchers/google-agent)' + view_file; uses extra tokens)."
)


def decorate_suggested_actions_with_visual_audit(
    res: dict[str, Any], phase: str, is_running: bool, has_visuals: bool, tgt: str, cid: str, hid: str,
) -> dict[str, Any]:
    """Attach the opt-in VM screenshot audit Elicitation chip without bloating retirement.py over 220L."""
    import html
    clean = lambda s: re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f-\x9f\ufffe\uffff]+", " ", str(s or ""))).strip()
    esc = lambda s: html.escape(clean(s), quote=True)
    ref = clean(cid or hid or tgt) or "workspace"
    tgt_c = clean(tgt) or "workspace"
    tgt_short = tgt_c if len(tgt_c) <= 24 else tgt_c[:21] + "..."
    audit_lbl = "Have Gemini audit screenshots in VM (uses extra tokens)"
    audit_qry = f"@Agy Nexus Mcp Pull the latest signed /web/media/ screenshots and published HTML links for {ref} ({tgt_c}) into your Linux workspace using the Google-Agent User-Agent and visually audit them."
    if phase == "inspect_visual_artifacts":
        q_ok = f"@Agy Nexus Mcp I checked the signed visual links for {tgt_c} ({ref}) — looks good; continue."
        inner = f'<Elicitation label="{esc(audit_lbl)}" query="{esc(audit_qry)}" /><Elicitation label="I checked the links — looks good" query="{esc(q_ok)}" />'
        return {
            "phase": "inspect_visual_artifacts", "prompt": "Audit screenshots in Gemini VM or inspect links yourself?",
            "actions": ["Share links or opt in to Gemini VM visual audit"],
            "options": [{"label": audit_lbl, "value": audit_qry}, {"label": "I checked the links — looks good", "value": q_ok}],
            "followup_xml": f'<ElicitationsGroup message="{esc(f"Open signed links directly or ask Gemini to audit {tgt_short} (uses extra tokens)?")}">{inner}</ElicitationsGroup>',
        }
    if not has_visuals or is_running:
        return res
    opts = list(res.get("options") or [])
    opts.append({"label": audit_lbl, "value": audit_qry})
    res["options"] = opts
    xml = str(res.get("followup_xml") or "")
    chip = f'<Elicitation label="{esc(audit_lbl)}" query="{esc(audit_qry)}" />'
    if "</ElicitationsGroup>" in xml:
        res["followup_xml"] = xml.replace("</ElicitationsGroup>", f"{chip}</ElicitationsGroup>")
    return res

