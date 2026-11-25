#!/usr/bin/env python3
"""
agy_nexus.ls_quota_probe — Shared Read-Only Loopback Language Server Probe & Host-to-Docker Bridge.

Supports both HTTPS (self-signed cert restricted strictly to 127.0.0.1 loopback) and HTTP Connect-RPC
listeners for `RetrieveUserQuotaSummary` (5h + Weekly pool buckets) and `GetUserStatus`, writing sanitized
0600 snapshots to `${AGY_BG_DIR}/live_quota_snapshot.json` with zero tokens, emails, or PII persisted.
"""
from __future__ import annotations

from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import re
import ssl
import subprocess
import tempfile
import time
from typing import Any
import urllib.error
import urllib.request

from agy_nexus.model_pricing import classify_model_key, get_model_specs_map

SNAPSHOT_FILENAME = "live_quota_snapshot.json"
MAX_SNAPSHOT_BYTES = 131_072
DEFAULT_MAX_STALE_SECONDS = 900
_LOOPBACK_TIMEOUT_SEC = 1.5
_EMPTY_SSL_CTX = ssl.create_default_context()
_EMPTY_SSL_CTX.check_hostname = False
_EMPTY_SSL_CTX.verify_mode = ssl.CERT_NONE


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def _reject_nonfinite(tok: str) -> Any:
    raise ValueError(f"Non-finite JSON token: {tok}")


def _as_dict(val: Any) -> dict[str, Any]:
    return val if isinstance(val, dict) else {}


def _safe_float(val: Any, default: float = 0.0) -> float:
    if isinstance(val, bool) or val is None:
        return default
    try:
        num = float(val)
        return num if math.isfinite(num) else default
    except (TypeError, ValueError, OverflowError):
        return default


def _safe_int(val: Any, default: int = 0) -> int:
    num = _safe_float(val, float("nan"))
    if not math.isfinite(num):
        return default
    try:
        return int(num)
    except (TypeError, ValueError, OverflowError):
        return default


def parse_utc_epoch(iso_str: str | None) -> float | None:
    """Parse an ISO-8601 UTC timestamp string safely to Unix epoch seconds."""
    raw = str(iso_str or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return None


def _discover_ls_listeners() -> tuple[str, list[int]]:
    """Discover local Antigravity Language Server CSRF token and 127.0.0.1 listening ports."""
    ps_out = subprocess.run(
        ["ps", "-u", str(os.getuid()), "-o", "args"],
        capture_output=True, text=True, timeout=1.5, check=False,
    ).stdout
    csrf, ext_port = "", None
    for line in ps_out.splitlines():
        if "language_server" in line and "--csrf_token" in line:
            m = re.search(r"--csrf_token[=\s]+([^\s]+)", line)
            if m:
                csrf = m.group(1).strip()
            ep = re.search(r"--extension_server_port[=\s]+(\d+)", line)
            if ep:
                ext_port = int(ep.group(1))
            if csrf:
                break
    if not csrf:
        return "", []
    uid_tag = f"uid:{os.getuid()}"
    ss_out = subprocess.run(["ss", "-tlnep"], capture_output=True, text=True, timeout=1.5, check=False).stdout
    ports, ephemeral, other_hi = [], [], []
    for ln in ss_out.splitlines():
        if ("uid:" in ln and uid_tag not in ln) or "/system.slice/" in ln:
            continue
        has_ls = "language_server" in ln
        for pm in re.finditer(r"127\.0\.0\.1:(\d+)", ln):
            p = int(pm.group(1))
            if has_ls and p not in ports:
                ports.append(p)
            elif p >= 32768 and p not in ephemeral:
                ephemeral.append(p)
            elif 1024 <= p < 32768 and p not in (8098, 8765) and p not in other_hi:
                other_hi.append(p)
    if not ports:
        ports.extend(ephemeral + other_hi)
    if ext_port and ext_port not in ports:
        ports.append(ext_port)
    return csrf, ports


def _build_loopback_opener(scheme: str) -> urllib.request.OpenerDirector:
    handlers: list[Any] = [urllib.request.ProxyHandler({}), _NoRedirect()]
    if scheme == "https":
        handlers.append(urllib.request.HTTPSHandler(context=_EMPTY_SSL_CTX))
    return urllib.request.build_opener(*handlers)


def _is_connect_ls_port(scheme: str, port: int, timeout: float) -> bool:
    """Preflight 127.0.0.1:port without CSRF; only true LS answers HTTP 401 unauthenticated JSON."""
    url = f"{scheme}://127.0.0.1:{int(port)}/exa.language_server_pb.LanguageServerService/GetUserStatus"
    req = urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json", "Connect-Protocol-Version": "1"}, method="POST")
    try:
        with _build_loopback_opener(scheme).open(req, timeout=timeout):
            return False
    except urllib.error.HTTPError as exc:
        if exc.code != 401:
            return False
        try:
            body = json.loads(exc.read(4096).decode("utf-8", errors="replace"), parse_constant=_reject_nonfinite)
            return isinstance(body, dict) and body.get("code") == "unauthenticated"
        except Exception:
            return False
    except Exception:
        return False


def _post_loopback_rpc(scheme: str, port: int, method: str, csrf: str, timeout: float = _LOOPBACK_TIMEOUT_SEC) -> dict[str, Any] | None:
    """Execute one Connect-RPC POST strictly against 127.0.0.1 (no proxy, no redirect, loopback-only TLS)."""
    if scheme not in ("https", "http") or not (1 <= int(port) <= 65535):
        return None
    if method == "GetUserStatus" and not _is_connect_ls_port(scheme, port, timeout):
        return None
    url = f"{scheme}://127.0.0.1:{int(port)}/exa.language_server_pb.LanguageServerService/{method}"
    req = urllib.request.Request(
        url, data=b"{}",
        headers={"Content-Type": "application/json", "Connect-Protocol-Version": "1", "X-Codeium-Csrf-Token": csrf},
        method="POST",
    )
    with _build_loopback_opener(scheme).open(req, timeout=timeout) as resp:
        data = json.loads(resp.read(MAX_SNAPSHOT_BYTES * 4).decode("utf-8", errors="replace"), parse_constant=_reject_nonfinite)
        return data if isinstance(data, dict) else None


def is_untouched_rolling_reset(
    rem_fraction: float,
    description: str,
    reset_epoch: float | None,
    now_epoch: float,
    window_seconds: int,
) -> bool:
    """Return True when a 100%-remaining bucket carries only a synthetic rolling `now + window` timer."""
    if rem_fraction < 0.9999 or description.strip():
        return False
    if reset_epoch is None:
        return True
    delta = reset_epoch - now_epoch
    return 0 <= delta <= (window_seconds + 1800)


def _normalize_bucket(raw: dict[str, Any], default_window: str, now_epoch: float) -> dict[str, Any]:
    """Normalize one 5h or weekly bucket into sanitized percentage, reset, and active-window metadata."""
    try:
        rf = max(0.0, min(1.0, float(raw.get("remainingFraction", 1.0))))
    except (TypeError, ValueError):
        rf = 1.0
    win = str(raw.get("window") or default_window or "5h").strip().lower()
    win_sec = 7 * 86400 if "week" in win else 5 * 3600
    desc = str(raw.get("description") or "").strip()[:180]
    rt_raw = str(raw.get("resetTime") or "").strip() or None
    rt_epoch = parse_utc_epoch(rt_raw) if rt_raw else None
    if is_untouched_rolling_reset(rf, desc, rt_epoch, now_epoch, win_sec):
        rt_raw, rt_epoch = None, None
    has_reset = bool(rt_raw and rt_epoch and rt_epoch > (now_epoch - 60))
    win_start_epoch = round(rt_epoch - win_sec, 3) if (has_reset and rt_epoch and rt_epoch > now_epoch) else None
    elapsed_pct = 0.0
    if has_reset and rt_epoch is not None:
        rem_sec = max(0.0, min(float(win_sec), rt_epoch - now_epoch))
        elapsed_pct = round(max(0.0, min(100.0, (1.0 - rem_sec / float(win_sec)) * 100.0)), 1)
    return {
        "bucket_id": str(raw.get("bucketId") or "")[:32],
        "window": "weekly" if win_sec > 86400 else "5h",
        "window_seconds": win_sec,
        "remaining_fraction": round(rf, 6),
        "used_pct": round((1.0 - rf) * 100.0, 1),
        "remaining_pct": round(rf * 100.0, 1),
        "elapsed_pct": elapsed_pct,
        "reset_time": rt_raw if has_reset else None,
        "reset_epoch": round(rt_epoch, 3) if (has_reset and rt_epoch) else None,
        "window_start_epoch": win_start_epoch,
        "has_active_reset": has_reset,
        "description": desc,
    }


def _extract_sanitized_configs(status_data: dict[str, Any], now_epoch: float) -> list[dict[str, Any]]:
    """Extract only safe model/quota fields from GetUserStatus.cascadeModelConfigData.clientModelConfigs."""
    specs = get_model_specs_map()
    us = _as_dict(status_data.get("userStatus"))
    cfgs = _as_dict(us.get("cascadeModelConfigData")).get("clientModelConfigs") or []
    out: list[dict[str, Any]] = []
    for c in cfgs if isinstance(cfgs, list) else []:
        if not isinstance(c, dict):
            continue
        mid = str(_as_dict(c.get("modelOrAlias")).get("model") or "").strip()[:128]
        lbl = str(c.get("label") or "").strip()[:64]
        if not mid and not lbl:
            continue
        mk = classify_model_key(mid, lbl)
        pk = "google" if str((specs.get(mk) or {}).get("pool_key") or "google") == "google" else "claude"
        qinfo = _as_dict(c.get("quotaInfo"))
        rf = max(0.0, min(1.0, _safe_float(qinfo.get("remainingFraction"), 1.0)))
        rt_raw = str(qinfo.get("resetTime") or "").strip() or None
        rt_epoch = parse_utc_epoch(rt_raw) if rt_raw else None
        if rt_epoch is None or is_untouched_rolling_reset(rf, "", rt_epoch, now_epoch, 5 * 3600):
            rt_raw = None
        out.append({
            "modelOrAlias": {"model": mid},
            "label": lbl,
            "model_key": mk,
            "pool_key": pk,
            "quotaInfo": {"remainingFraction": round(rf, 6), **({"resetTime": rt_raw} if rt_raw else {})},
            "used_pct": round((1.0 - rf) * 100.0, 1),
            "remaining_pct": round(rf * 100.0, 1),
        })
    return out


def _build_pools_from_summary(summary_data: dict[str, Any] | None, cfgs: list[dict[str, Any]], now_epoch: float) -> dict[str, Any]:
    """Assemble google & claude pool 5h/weekly buckets from RetrieveUserQuotaSummary with GetUserStatus fallback."""
    pools: dict[str, dict[str, Any]] = {"google": {"display_name": "Gemini Models"}, "claude": {"display_name": "Claude and GPT models"}}
    raw_sum = _as_dict(summary_data)
    resp = _as_dict(raw_sum.get("response") or raw_sum)
    for grp in (resp.get("groups") or []) if isinstance(resp.get("groups"), list) else []:
        if not isinstance(grp, dict):
            continue
        dname = str(grp.get("displayName") or "")
        low = dname.lower()
        pk = "claude" if ("claude" in low or "gpt" in low or "3p" in low or "partner" in low) else "google"
        pools[pk]["display_name"] = dname[:48]
        for b in (grp.get("buckets") or []) if isinstance(grp.get("buckets"), list) else []:
            if not isinstance(b, dict):
                continue
            b_win = str(b.get("window") or ("weekly" if "week" in str(b.get("bucketId") or "").lower() else "5h")).lower()
            norm = _normalize_bucket(b, b_win, now_epoch)
            pools[pk]["bucket_weekly" if norm["window"] == "weekly" else "bucket_5h"] = norm

    for pk in ("google", "claude"):
        if "bucket_5h" in pools[pk]:
            continue
        pool_cfgs = [c for c in cfgs if c.get("pool_key") == pk]
        if pool_cfgs:
            lowest = min(pool_cfgs, key=lambda c: _safe_float(_as_dict(c.get("quotaInfo")).get("remainingFraction"), 1.0))
            qi = _as_dict(lowest.get("quotaInfo"))
            pools[pk]["bucket_5h"] = _normalize_bucket(
                {"bucketId": f"{pk}-5h", "window": "5h", "remainingFraction": qi.get("remainingFraction", 1.0), "resetTime": qi.get("resetTime")},
                "5h", now_epoch,
            )
    return pools


def sanitize_ls_responses(
    status_data: dict[str, Any] | None,
    summary_data: dict[str, Any] | None,
    *,
    transport: str = "",
    now_epoch: float | None = None,
) -> dict[str, Any]:
    """Convert raw LS GetUserStatus + RetrieveUserQuotaSummary payloads into a sanitized zero-PII snapshot."""
    now_ep = float(now_epoch if now_epoch is not None else time.time())
    st_dict = _as_dict(status_data)
    us = _as_dict(st_dict.get("userStatus"))
    ut = _as_dict(us.get("userTier"))
    ps = _as_dict(us.get("planStatus"))
    pi = _as_dict(ps.get("planInfo"))
    creds = ut.get("availableCredits") if isinstance(ut.get("availableCredits"), list) else []
    ai_credits = sum(_safe_int(c.get("creditAmount")) for c in creds if isinstance(c, dict))
    cfgs = _extract_sanitized_configs(st_dict, now_ep)
    pools = _build_pools_from_summary(summary_data, cfgs, now_ep)
    now_iso = datetime.fromtimestamp(now_ep, tz=timezone.utc).isoformat()
    return {
        "schema_version": 1,
        "captured_at": now_iso,
        "captured_epoch": round(now_ep, 3),
        "last_live_at": now_iso,
        "last_live_epoch": round(now_ep, 3),
        "checked_at": now_iso,
        "checked_epoch": round(now_ep, 3),
        "source": "antigravity_ls",
        "transport": transport[:48],
        "ls_alive": True,
        "user_tier": {"id": str(ut.get("id") or "")[:40], "description": str(ut.get("description") or "")[:48], "available_credits": ai_credits},
        "plan_status": {
            "plan_name": str(pi.get("planName") or "")[:32],
            "available_prompt_credits": _safe_int(ps.get("availablePromptCredits")),
            "available_flow_credits": _safe_int(ps.get("availableFlowCredits")),
        },
        "pools": pools,
        "client_model_configs": cfgs,
    }


def probe_local_language_server(timeout: float = _LOOPBACK_TIMEOUT_SEC, *, now_epoch: float | None = None) -> dict[str, Any] | None:
    """Probe running local Antigravity Language Server over both HTTPS (loopback self-signed) and HTTP."""
    try:
        csrf, ports = _discover_ls_listeners()
    except Exception:
        return None
    if not csrf or not ports:
        return None
    deadline = time.monotonic() + max(4.0, timeout * 4.0)
    for port in ports[:12]:
        if time.monotonic() > deadline:
            break
        for scheme in ("https", "http"):
            try:
                status_data = _post_loopback_rpc(scheme, port, "GetUserStatus", csrf, timeout=timeout)
            except Exception:
                continue
            if not isinstance(status_data, dict) or not isinstance(status_data.get("userStatus"), dict):
                continue
            try:
                summary_data = _post_loopback_rpc(scheme, port, "RetrieveUserQuotaSummary", csrf, timeout=timeout)
            except Exception:
                summary_data = None
            try:
                return sanitize_ls_responses(status_data, summary_data, transport=f"{scheme}://127.0.0.1:{port}", now_epoch=now_epoch)
            except Exception:
                continue
    return None


def _atomic_write_json_600(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.parent / f".{path.name}.lock"
    with open(lock_path, "a+", encoding="utf-8") as lf:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fd = -1
                json.dump(payload, fh, indent=2)
                fh.write("\n")
            os.replace(tmp_name, path)
        except Exception:
            for fn in ((lambda: os.close(fd)) if fd >= 0 else None, lambda: os.unlink(tmp_name)):
                if fn:
                    try:
                        fn()
                    except OSError:
                        pass
            raise
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


def write_quota_snapshot(bg_dir: Path, live_payload: dict[str, Any] | None, *, now_epoch: float | None = None) -> dict[str, Any]:
    """Persist live LS snapshot atomically (0600); when LS is offline, preserve prior buckets and mark ls_alive=False."""
    now_ep = float(now_epoch if now_epoch is not None else time.time())
    snap_path = bg_dir / SNAPSHOT_FILENAME
    if live_payload and live_payload.get("ls_alive"):
        _atomic_write_json_600(snap_path, live_payload)
        return live_payload
    prev: dict[str, Any] = {}
    if snap_path.is_file() and not snap_path.is_symlink():
        try:
            if snap_path.stat().st_size <= MAX_SNAPSHOT_BYTES:
                loaded = json.loads(snap_path.read_text(encoding="utf-8"), parse_constant=_reject_nonfinite)
                if isinstance(loaded, dict) and loaded.get("schema_version") == 1:
                    prev = loaded
        except Exception:
            prev = {}
    now_iso = datetime.fromtimestamp(now_ep, tz=timezone.utc).isoformat()
    offline_payload = {
        **prev, "schema_version": 1, "source": prev.get("source") or "antigravity_ls", "ls_alive": False,
        "checked_at": now_iso, "checked_epoch": round(now_ep, 3),
        "pools": prev.get("pools") or {}, "client_model_configs": prev.get("client_model_configs") or [],
    }
    _atomic_write_json_600(snap_path, offline_payload)
    return offline_payload


def read_quota_snapshot(
    bg_dir: Path | None, *, max_stale_seconds: int = DEFAULT_MAX_STALE_SECONDS, now_epoch: float | None = None,
) -> dict[str, Any]:
    """Read and validate `${AGY_BG_DIR}/live_quota_snapshot.json`, returning freshness and state metadata."""
    now_ep = float(now_epoch if now_epoch is not None else time.time())
    empty = {"state": "UNAVAILABLE", "ls_alive": False, "is_fresh": False, "source": "none", "snapshot_age_seconds": None, "pools": {}, "client_model_configs": []}
    if not bg_dir:
        return empty
    snap_path = bg_dir / SNAPSHOT_FILENAME
    try:
        if not snap_path.is_file() or snap_path.is_symlink() or snap_path.stat().st_size > MAX_SNAPSHOT_BYTES:
            return empty
        data = json.loads(snap_path.read_text(encoding="utf-8"), parse_constant=_reject_nonfinite)
    except Exception:
        return empty
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        return empty
    ref_raw = data.get("last_live_epoch") if data.get("last_live_epoch") is not None else data.get("captured_epoch")
    ref_ep = _safe_float(ref_raw, float("nan"))
    age_sec = max(0, int(round(now_ep - ref_ep))) if math.isfinite(ref_ep) else None
    ls_alive = bool(data.get("ls_alive"))
    is_fresh = bool(ls_alive and age_sec is not None and age_sec <= max_stale_seconds)
    state = "LIVE" if is_fresh else ("IDE_OFFLINE" if not ls_alive else "STALE")
    return {**data, "state": state, "is_fresh": is_fresh, "source": "host_snapshot", "snapshot_age_seconds": age_sec}


def probe_or_read_quota_snapshot(
    bg_dir: Path | None, *, allow_subprocess: bool = True, write_if_live: bool = False,
    max_stale_seconds: int = DEFAULT_MAX_STALE_SECONDS, now_epoch: float | None = None,
) -> dict[str, Any]:
    """Try live loopback LS probe first (host), falling back transparently to host snapshot (Docker/CLI)."""
    if allow_subprocess:
        live = probe_local_language_server(now_epoch=now_epoch)
        if live and live.get("ls_alive"):
            if write_if_live and bg_dir:
                try:
                    write_quota_snapshot(bg_dir, live, now_epoch=now_epoch)
                except Exception:
                    pass
            return {**live, "state": "LIVE", "is_fresh": True, "source": "ls_direct", "snapshot_age_seconds": 0}
    return read_quota_snapshot(bg_dir, max_stale_seconds=max_stale_seconds, now_epoch=now_epoch)


def enrich_quota_and_pools(
    pools_out: dict[str, dict[str, Any]], *, bg_dir: Path | None = None,
    allow_subprocess: bool = True, write_if_live: bool = False, now_epoch: float | None = None,
) -> dict[str, Any]:
    """Attach live or snapshot 5h/weekly quota buckets and freshness metadata into pools_out; return live_quota dict."""
    snap = probe_or_read_quota_snapshot(bg_dir, allow_subprocess=allow_subprocess, write_if_live=write_if_live, now_epoch=now_epoch)
    s_pools = _as_dict(snap.get("pools"))
    for pk in ("google", "claude"):
        sp = _as_dict(s_pools.get(pk))
        if not sp:
            continue
        dst = pools_out.setdefault(pk, {})
        for bk_key in ("bucket_5h", "bucket_weekly"):
            if isinstance(sp.get(bk_key), dict):
                dst[bk_key] = dict(sp[bk_key])
    ut, ps = _as_dict(snap.get("user_tier")), _as_dict(snap.get("plan_status"))
    return {
        "state": str(snap.get("state") or "UNAVAILABLE"),
        "ls_alive": bool(snap.get("ls_alive")),
        "is_fresh": bool(snap.get("is_fresh")),
        "source": str(snap.get("source") or "none"),
        "captured_at": str(snap.get("last_live_at") or snap.get("captured_at") or ""),
        "snapshot_age_seconds": snap.get("snapshot_age_seconds"),
        "tier_id": str(ut.get("id") or ""),
        "tier_label": str(ut.get("description") or ""),
        "credits": {
            "ai_credits": _safe_int(ut.get("available_credits")),
            "prompt_credits": _safe_int(ps.get("available_prompt_credits")),
            "flow_credits": _safe_int(ps.get("available_flow_credits")),
        },
    }

