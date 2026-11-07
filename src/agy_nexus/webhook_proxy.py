#!/usr/bin/env python3
"""
agy_nexus.webhook_proxy — ASGI Reverse-Proxy Bridge for Signed GitHub Webhooks (/github-webhook-sync).
"""

from __future__ import annotations

import json
import os
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

from agy_nexus.config import AGY_HOST_BRIDGE_URL


def _resolve_webhook_sync_base() -> str:
    env_url = os.getenv("AGY_WEBHOOK_SYNC_URL", "").strip()
    if env_url:
        return env_url.rstrip("/")
    parsed = urllib.parse.urlparse(AGY_HOST_BRIDGE_URL)
    host = parsed.hostname or "127.0.0.1"
    return f"http://{host}:8768"


async def handle_webhook_sync_proxy(
    method: str,
    req_path: str,
    raw_qs: str,
    headers: list[tuple[bytes, bytes]],
    receive: Any,
    send: Any,
) -> None:
    """Forward /github-webhook-sync requests to the local oaw-webhook-sync daemon (:8768)."""
    body_chunks: list[bytes] = []
    if method == "POST":
        while True:
            msg = await receive()
            if msg.get("type") == "http.request":
                chunk = msg.get("body") or b""
                if chunk:
                    body_chunks.append(chunk)
                if not msg.get("more_body", False):
                    break
            else:
                break
    raw_body = b"".join(body_chunks) if body_chunks else None

    base = _resolve_webhook_sync_base()
    suffix = "/status" if req_path.endswith("/status") else ("/health" if req_path.endswith("/health") else "/webhook")
    target_url = f"{base}{suffix}" + (f"?{raw_qs}" if raw_qs else "")

    fwd_headers: dict[str, str] = {"Content-Type": "application/json"}
    for hk, hv in headers:
        k_str = hk.decode("latin-1", errors="ignore").lower()
        if k_str in ("x-hub-signature-256", "x-github-event", "x-github-delivery", "content-type"):
            fwd_headers[k_str] = hv.decode("latin-1", errors="ignore")

    status_code = 502
    resp_bytes = b'{"ok":false,"error":"Upstream webhook sync daemon unreachable"}'
    try:
        req = urllib.request.Request(target_url, data=raw_body, headers=fwd_headers, method=method)
        with urllib.request.urlopen(req, timeout=30) as resp:
            status_code = resp.status
            resp_bytes = resp.read()
    except urllib.error.HTTPError as e:
        status_code = e.code
        resp_bytes = e.read()
    except Exception as exc:
        resp_bytes = json.dumps({"ok": False, "error": str(exc)}).encode("utf-8")

    await send({
        "type": "http.response.start",
        "status": status_code,
        "headers": [
            (b"content-type", b"application/json; charset=utf-8"),
            (b"content-length", str(len(resp_bytes)).encode("ascii")),
            (b"cache-control", b"no-store"),
            (b"access-control-allow-origin", b"*"),
        ],
    })
    await send({"type": "http.response.body", "body": resp_bytes})
