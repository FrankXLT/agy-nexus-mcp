#!/usr/bin/env python3
"""agy_nexus.web_routes — Static PWA Assets, Ephemeral Media & Telemetry Web Endpoints."""
from __future__ import annotations

import functools
import json
from pathlib import Path
import re
import time
from typing import Any

import anyio

from agy_nexus.bucket_api import handle_bucket_api_request
from agy_nexus.config import (
    AGY_BG_DIR,
    AGY_BRAIN_DIR,
    AGY_CONFIG_DIR,
    AGY_DATA_DIR,
    AGY_DB_FILE,
    verify_passphrase,
)
from agy_nexus.media import verify_and_resolve_media
from agy_nexus.stats import build_nexus_stats_bundle
from agy_nexus.uploads import handle_session_upload_request

PWA_ASSETS: dict[str, bytes] = {
    "styles.css": b"text/css; charset=utf-8",
    "workspace.css": b"text/css; charset=utf-8",
    "palettes.js": b"application/javascript; charset=utf-8",
    "demo_snapshot.js": b"application/javascript; charset=utf-8",
    "demo_data.js": b"application/javascript; charset=utf-8",
    "charts.js": b"application/javascript; charset=utf-8",
    "hierarchy.js": b"application/javascript; charset=utf-8",
    "health.js": b"application/javascript; charset=utf-8",
    "app.js": b"application/javascript; charset=utf-8",
    "uploads.js": b"application/javascript; charset=utf-8",
    "explorer.js": b"application/javascript; charset=utf-8",
    "gallery_select.js": b"application/javascript; charset=utf-8",
    "gallery_view.js": b"application/javascript; charset=utf-8",
    "sheet_builder.js": b"application/javascript; charset=utf-8",
    "markdown_renderer.js": b"application/javascript; charset=utf-8",
    "manifest.webmanifest": b"application/manifest+json; charset=utf-8",
    "sw.js": b"application/javascript; charset=utf-8",
    "icon.svg": b"image/svg+xml",
    "icon-192.png": b"image/png",
    "icon-512.png": b"image/png",
    "demo_thumb_desktop.png": b"image/png",
    "demo_thumb_workspace.png": b"image/png",
    "demo_thumb_foldable.png": b"image/png",
    "demo_thumb_mobile.png": b"image/png",
    "demo_thumb_health.png": b"image/png",
}


async def handle_web_request(
    scope: dict[str, Any],
    receive: Any,
    send: Any,
    web_dir: Path,
    req_path: str,
    method: str,
    headers: list[tuple[bytes, bytes]],
    raw_qs: str = "",
) -> bool:
    """Handle /web static assets, media endpoints, and Overwatch JSON APIs.

    Returns True if the request was handled, False if it should pass to MCP.
    """
    t0 = time.time()

    # 1. Root redirect GET / -> /web
    if method in ("GET", "HEAD") and req_path == "":
        await send({"type": "http.response.start", "status": 302, "headers": [(b"location", b"/web"), (b"content-length", b"0")]})
        await send({"type": "http.response.body", "body": b""})
        return True

    # 2. Serve /web dashboard HTML
    if method in ("GET", "HEAD") and (req_path.endswith("/web") or req_path.endswith("/web/index.html")):
        html_file = web_dir / "index.html"
        html_bytes = html_file.read_bytes() if html_file.is_file() else b"<h1>Dashboard not found</h1>"
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"content-type", b"text/html; charset=utf-8"),
                (b"content-length", str(len(html_bytes)).encode("ascii")),
                (b"cache-control", b"no-cache"),
            ],
        })
        await send({"type": "http.response.body", "body": b"" if method == "HEAD" else html_bytes})
        print(f"[agy-nexus] http={method} rpc=web_ui tool=- status=200 bytes={len(html_bytes)} ms=1", flush=True)
        return True

    # 3. Serve PWA static assets & /web/media/
    if method in ("GET", "HEAD") and "/web/" in req_path and not req_path.endswith("/web/api/stats"):
        # Ephemeral Media route
        if "/web/media/" in req_path:
            target_file, mime_bytes, status_code, msg_text = verify_and_resolve_media(req_path)
            if status_code == 200 and target_file is not None:
                if target_file.stat().st_size > 45 * 1024 * 1024:
                    status_code, msg_text = 413, "Media file exceeds 45 MB limit."
                else:
                    media_bytes = await anyio.to_thread.run_sync(target_file.read_bytes)
                    await send({
                        "type": "http.response.start",
                        "status": 200,
                        "headers": [
                            (b"content-type", mime_bytes),
                            (b"content-length", str(len(media_bytes)).encode("ascii")),
                            (b"cache-control", b"private, max-age=604800"),
                            (b"x-content-type-options", b"nosniff"),
                            (b"content-security-policy", b"default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; sandbox"),
                        ],
                    })
                    await send({"type": "http.response.body", "body": b"" if method == "HEAD" else media_bytes})
                    return True
            err_b = json.dumps({"ok": False, "error": msg_text}).encode("utf-8")
            await send({
                "type": "http.response.start", "status": status_code,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(err_b)).encode("ascii"))],
            })
            await send({"type": "http.response.body", "body": b"" if method == "HEAD" else err_b})
            return True

        asset_name = req_path.rsplit("/web/", 1)[-1]
        if asset_name in PWA_ASSETS:
            asset_path = web_dir / asset_name
            if asset_path.is_file():
                asset_bytes = asset_path.read_bytes()
                resp_hdrs = [
                    (b"content-type", PWA_ASSETS[asset_name]),
                    (b"content-length", str(len(asset_bytes)).encode("ascii")),
                    (b"cache-control", b"no-cache"),
                    (b"x-content-type-options", b"nosniff"),
                ]
                if asset_name == "sw.js":
                    resp_hdrs.append((b"service-worker-allowed", b"/"))
                await send({"type": "http.response.start", "status": 200, "headers": resp_hdrs})
                await send({"type": "http.response.body", "body": b"" if method == "HEAD" else asset_bytes})
                return True

        # Check if asset request that is not an API
        if not ("/api/" in req_path):
            nf_b = b'{"ok":false,"error":"Asset not found"}'
            await send({
                "type": "http.response.start", "status": 404,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(nf_b)).encode("ascii")), (b"x-content-type-options", b"nosniff")],
            })
            await send({"type": "http.response.body", "body": b"" if method == "HEAD" else nf_b})
            return True

    # 4. Workspace Tree & Session Bucket APIs
    if ("/api/workspace/" in req_path or "/api/sessions/" in req_path) and not req_path.endswith("/upload"):
        await handle_bucket_api_request(scope, receive, send, req_path, method, headers, raw_qs=raw_qs)
        return True

    # 5. Scratch Session Uploads
    if method == "POST" and ("/api/sessions/" in req_path and req_path.endswith("/upload")):
        m_conv = re.search(r"/api/sessions/([^/]+)/upload$", req_path)
        if m_conv:
            conv_id_req = m_conv.group(1).strip()
            await handle_session_upload_request(scope, receive, send, conv_id_req, headers)
            elapsed_ms = int((time.time() - t0) * 1000)
            safe_conv = re.sub(r"[^A-Za-z0-9_-]", "", conv_id_req)[:48] or "invalid"
            print(f"[agy-nexus] http=POST rpc=session_upload conv={safe_conv} ms={elapsed_ms}", flush=True)
            return True

    # 6. /web/api/stats JSON
    if method in ("GET", "POST") and req_path.endswith("/web/api/stats"):
        supplied_pass = ""
        for hk, hv in headers:
            if hk.lower() == b"x-nexus-passphrase":
                supplied_pass = hv.decode("utf-8", errors="ignore").strip()
                break

        period_val = "current_month"
        timeframe_val = ""
        horizon_val = ""
        offset_val = 0
        anchor_val = ""

        for kv in raw_qs.split("&"):
            if kv.startswith("period="):
                period_val = kv.split("=", 1)[1].strip() or "current_month"
            elif kv.startswith("timeframe="):
                timeframe_val = kv.split("=", 1)[1].strip()
            elif kv.startswith("horizon_mode="):
                horizon_val = kv.split("=", 1)[1].strip()
            elif kv.startswith("offset="):
                try:
                    offset_val = int(kv.split("=", 1)[1].strip())
                except ValueError:
                    offset_val = 0
            elif kv.startswith("anchor_date="):
                anchor_val = kv.split("=", 1)[1].strip()

        if not verify_passphrase(supplied_pass):
            err_b = json.dumps({"ok": False, "error": "Invalid spoken deadbolt passphrase."}).encode("utf-8")
            await send({
                "type": "http.response.start", "status": 401,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(err_b)).encode("ascii")), (b"cache-control", b"no-store")],
            })
            await send({"type": "http.response.body", "body": err_b})
            print("[agy-nexus] http=GET rpc=web_stats_unauthorized tool=- status=401 bytes=0 ms=1", flush=True)
            return True

        bundle = await anyio.to_thread.run_sync(
            functools.partial(
                build_nexus_stats_bundle,
                data_dir=AGY_DATA_DIR,
                brain_dir=AGY_BRAIN_DIR,
                db_file=AGY_DB_FILE,
                config_dir=AGY_CONFIG_DIR,
                bg_dir=AGY_BG_DIR,
                period=period_val,
                timeframe=timeframe_val,
                horizon_mode=horizon_val,
                offset=offset_val,
                anchor_date=anchor_val,
            )
        )
        ok_b = json.dumps({"ok": True, **bundle}).encode("utf-8")
        await send({
            "type": "http.response.start", "status": 200,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(ok_b)).encode("ascii")),
                (b"cache-control", b"no-store, no-cache, private"),
                (b"x-content-type-options", b"nosniff"),
            ],
        })
        await send({"type": "http.response.body", "body": ok_b})
        elapsed_ms = int((time.time() - t0) * 1000)
        safe_period = re.sub(r"[^a-z0-9_-]", "", (timeframe_val or period_val).lower())[:24] or "current_month"
        print(f"[agy-nexus] http=GET rpc=web_stats tool={safe_period} status=200 bytes={len(ok_b)} ms={elapsed_ms}", flush=True)
        return True

    return False
