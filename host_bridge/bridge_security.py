#!/usr/bin/env python3
"""
bridge_security.py — Zero-Trust Authentication, CIDR Guard & Sandbox Policy for Host Bridge (:8098).

Remediates CWE-306 (Missing Authentication for Critical Function) and CWE-88 (Argument Injection):
1. Defaults socket binding strictly to loopback (`127.0.0.1`).
2. Restricts `/agentapi` client peers to loopback + local Docker bridge CIDRs (`127.0.0.0/8,::1/128,172.16.0.0/12`).
3. Enforces constant-time `X-Bridge-Token` verification (`HOST_BRIDGE_TOKEN` or domain-separated
   `HMAC-SHA256(PATH_SECRET, "agy-host-bridge-agentapi-v1")` loaded from `secrets.env`), failing closed.
4. Blocks browser CSRF / DNS-rebinding requests (`Origin` header rejection, `application/json` enforcement, 1 MB body cap).
5. Sandboxes `git-inspect` strictly to `AGY_GITLAB_DIR` and `AGY_DATA_DIR/worktrees` (never `$HOME` or `/`).
"""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import hmac
import ipaddress
import os
from pathlib import Path
import re

DEFAULT_BIND_HOST = "127.0.0.1"
DEFAULT_ALLOWED_CIDRS = "127.0.0.0/8,::1/128,172.16.0.0/12"
MAX_BODY_BYTES = 1_048_576
TOKEN_DERIVATION_CONTEXT = b"agy-host-bridge-agentapi-v1"
AGY_WORKSPACE_DIR = Path(os.getenv("AGY_WORKSPACE_DIR", str(Path.home() / "agentic_workspace"))).expanduser()


def load_bridge_env_file(env_file: str | Path | None = None) -> dict[str, str]:
    """Load secrets.env into os.environ (if unset) and return parsed key-value pairs."""
    candidates: list[Path] = []
    if env_file:
        candidates.append(Path(env_file).expanduser())
    env_override = os.getenv("AG_BRIDGE_ENV_FILE", "").strip()
    if env_override:
        candidates.append(Path(env_override).expanduser())
    candidates.extend([
        Path.home() / ".config/ag-bridge-mcp/secrets.env",
        Path("/config/secrets.env"),
    ])
    loaded: dict[str, str] = {}
    for cand in candidates:
        try:
            if cand.is_file():
                for raw_line in cand.read_text(encoding="utf-8").splitlines():
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    k_clean = key.strip()
                    v_clean = val.strip().strip("'\"")
                    loaded[k_clean] = v_clean
                    os.environ.setdefault(k_clean, v_clean)
                break
        except Exception:
            continue
    return loaded


def derive_bridge_token(path_secret: str | None = None, explicit_token: str | None = None) -> str:
    """Resolve explicit HOST_BRIDGE_TOKEN (>=32 chars) or HMAC-SHA256 derived from PATH_SECRET (>=32 chars)."""
    exp = (os.getenv("HOST_BRIDGE_TOKEN", "") if explicit_token is None else explicit_token).strip()
    if len(exp) >= 32:
        return exp
    sec = (os.getenv("PATH_SECRET", "") if path_secret is None else path_secret).strip()
    if len(sec) >= 32:
        return hmac.new(sec.encode("utf-8"), TOKEN_DERIVATION_CONTEXT, hashlib.sha256).hexdigest()
    return ""


def verify_bridge_token(provided: str, expected: str) -> bool:
    """Constant-time verification of X-Bridge-Token against expected secret."""
    prov = (provided or "").strip()
    exp = (expected or "").strip()
    if len(exp) < 32 or len(prov) < 32:
        return False
    return hmac.compare_digest(prov.encode("utf-8"), exp.encode("utf-8"))


def is_client_ip_allowed(client_ip: str, allowed_cidrs_raw: str | None = None) -> bool:
    """Verify client_ip belongs to loopback or local container bridge CIDRs."""
    raw_cidrs = (os.getenv("HOST_BRIDGE_ALLOWED_CIDRS", DEFAULT_ALLOWED_CIDRS) if allowed_cidrs_raw is None else allowed_cidrs_raw).strip()
    if not raw_cidrs:
        return False
    try:
        addr = ipaddress.ip_address((client_ip or "").strip())
        if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
            addr = addr.ipv4_mapped
    except ValueError:
        return False
    for item in raw_cidrs.split(","):
        cidr = item.strip()
        if not cidr:
            continue
        try:
            net = ipaddress.ip_network(cidr, strict=False)
            if addr.version == net.version and addr in net:
                return True
        except ValueError:
            continue
    return False


def validate_agentapi_request(
    client_ip: str,
    headers: Mapping[str, str],
    expected_token: str,
    allowed_cidrs_raw: str | None = None,
    max_bytes: int = MAX_BODY_BYTES,
) -> tuple[int, str, int]:
    """Validate peer IP, browser Origin absence, X-Bridge-Token, Content-Type, and Content-Length."""
    if not is_client_ip_allowed(client_ip, allowed_cidrs_raw=allowed_cidrs_raw):
        return 403, "Forbidden: client IP is outside HOST_BRIDGE_ALLOWED_CIDRS.", 0
    if (headers.get("Origin") or "").strip():
        return 403, "Forbidden: cross-origin browser requests are not permitted.", 0
    if len((expected_token or "").strip()) < 32:
        return 503, "Service unavailable: host bridge authentication secret is not configured.", 0
    provided_token = headers.get("X-Bridge-Token") or ""
    if not verify_bridge_token(provided_token, expected_token):
        return 401, "Unauthorized: valid X-Bridge-Token header required.", 0
    ctype = (headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
    if ctype != "application/json":
        return 415, "Unsupported Media Type: Content-Type must be application/json.", 0
    if (headers.get("Transfer-Encoding") or "").strip():
        return 411, "Length Required: chunked Transfer-Encoding is not supported.", 0
    raw_len = (headers.get("Content-Length") or "0").strip()
    try:
        length = int(raw_len)
    except ValueError:
        return 400, "Bad Request: invalid Content-Length header.", 0
    if length < 0:
        return 400, "Bad Request: negative Content-Length.", 0
    if length > max_bytes:
        return 413, f"Payload Too Large: request exceeds {max_bytes} bytes.", 0
    return 200, "", length


def resolve_allowed_git_roots(
    gitlab_dir: Path,
    data_dir: Path,
    workspace_dir: Path | str | None = None,
    extra_roots_raw: str | None = None,
) -> list[Path]:
    """Return canonicalized git-inspect roots, strictly forbidding '/' and '$HOME'."""
    home_res = Path.home().resolve()
    root_fs = Path("/").resolve()
    ws_base = Path(workspace_dir).expanduser().resolve() if workspace_dir else AGY_WORKSPACE_DIR.resolve()
    candidates = [
        gitlab_dir.expanduser().resolve(),
        (gitlab_dir.parent / "github").resolve(),
        (data_dir.expanduser() / "worktrees").resolve(),
        (ws_base / "projects").resolve(),
        (ws_base / "workbooks").resolve(),
        (ws_base / "configuration").resolve(),
    ]
    raw_extra = os.getenv("HOST_BRIDGE_EXTRA_ROOTS", "") if extra_roots_raw is None else extra_roots_raw
    for part in re.split(r"[,:]", raw_extra):
        cleaned = part.strip()
        if cleaned:
            candidates.append(Path(cleaned).expanduser().resolve())
    allowed: list[Path] = []
    for cand in candidates:
        if cand in (root_fs, home_res):
            continue
        if cand not in allowed:
            allowed.append(cand)
    return allowed


def sanitize_git_ref(raw_ref: str | None) -> str:
    """Sanitize branch/commit ref and strip leading dashes to block git option injection (CWE-88)."""
    cleaned = re.sub(r"[^a-zA-Z0-9_./~^-]", "", (raw_ref or "").strip()).lstrip("-")
    return cleaned or "HEAD"


def sanitize_conv_id(raw_id: str | None) -> str:
    """Sanitize conversation ID and strip leading dashes so it cannot be parsed as a CLI option."""
    return re.sub(r"[^a-zA-Z0-9_-]", "", (raw_id or "").strip()).lstrip("-")


def guard_cli_positional(text: str | None) -> str:
    """Ensure a positional CLI text argument never starts with '-' (agentapi does not use '--' sentinel)."""
    cleaned = (text or "").strip()
    if cleaned.startswith("-"):
        return "\n" + cleaned
    return cleaned


def sanitize_alert_field(raw: str | None, max_len: int = 120, shell_safe: bool = False) -> str:
    """Sanitize untrusted incident webhook strings against shell metacharacters and control chars."""
    txt = re.sub(r"[\x00-\x1f\x7f]+", " ", str(raw or "")).strip()
    if shell_safe:
        txt = re.sub(r"[^a-zA-Z0-9_.:/()\[\] -]", "", txt).strip()
    return txt[:max_len]
