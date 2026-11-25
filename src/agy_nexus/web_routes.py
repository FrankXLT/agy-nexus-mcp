#!/usr/bin/env python3
"""agy_nexus.web_routes — Static PWA Assets, Ephemeral Media & Telemetry Web Endpoints."""
from __future__ import annotations

import functools
import json
from pathlib import Path
import re
import time
from typing import Any
import urllib.parse

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
    "heatmap.js": b"application/javascript; charset=utf-8",
    "workspace_resizer.js": b"application/javascript; charset=utf-8",
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
    "v9/index.html": b"text/html; charset=utf-8",
    "v9/v9_layers.css": b"text/css; charset=utf-8",
    "v9/v9_shell.css": b"text/css; charset=utf-8",
    "v9/v9_rail.css": b"text/css; charset=utf-8",
    "v9/v9_analytics.css": b"text/css; charset=utf-8",
    "v9/v9_quota_cards.css": b"text/css; charset=utf-8",
    "v9/v9_workspace.css": b"text/css; charset=utf-8",
    "v9/v9_tables_and_rail.css": b"text/css; charset=utf-8",
    "v9/v9_catalog_banner.css": b"text/css; charset=utf-8",
    "v9/v9_state.js": b"application/javascript; charset=utf-8",
    "v9/v9_table_sort.js": b"application/javascript; charset=utf-8",
    "v9/v9_spark_bars.js": b"application/javascript; charset=utf-8",
    "v9/v9_demo_docs.js": b"application/javascript; charset=utf-8",
    "v9/v9_demo_adapter.js": b"application/javascript; charset=utf-8",
    "v9/v9_catalog_banner.js": b"application/javascript; charset=utf-8",
    "v9/v9_billing.js": b"application/javascript; charset=utf-8",
    "v9/v9_charts.js": b"application/javascript; charset=utf-8",
    "v9/v9_heatmap.js": b"application/javascript; charset=utf-8",
    "v9/v9_quota_cards.js": b"application/javascript; charset=utf-8",
    "v9/v9_analytics.js": b"application/javascript; charset=utf-8",
    "v9/v9_project_view.js": b"application/javascript; charset=utf-8",
    "v9/v9_hierarchy.js": b"application/javascript; charset=utf-8",
    "v9/v9_markdown.js": b"application/javascript; charset=utf-8",
    "v9/v9_workspace.js": b"application/javascript; charset=utf-8",
    "v9/v9_gallery.js": b"application/javascript; charset=utf-8",
    "v9/v9_lightbox.js": b"application/javascript; charset=utf-8",
    "v9/v9_app.js": b"application/javascript; charset=utf-8",
    "v9/vendor/echarts.min.js": b"application/javascript; charset=utf-8",
    "v9/vendor/THIRD_PARTY_LICENSES.txt": b"text/plain; charset=utf-8",
    "v9/vendor/quiet-ui-tokens.css": b"text/css; charset=utf-8",
    "v9/vendor/quiet-evidence-bundle.css": b"text/css; charset=utf-8",
    "v9/vendor/quiet-evidence-bundle.js": b"application/javascript; charset=utf-8",
    "v9/vendor/echarts-layout-defaults.js": b"application/javascript; charset=utf-8",
    "v9/vendor/echarts-layers.js": b"application/javascript; charset=utf-8",
    "v9/vendor/echarts-schedule-heatmap.js": b"application/javascript; charset=utf-8",
    "v9/vendor/echarts-quiet-adapter.js": b"application/javascript; charset=utf-8",
}


def _extract_passphrase(headers: list[tuple[bytes, bytes]]) -> str:
    for hk, hv in headers:
        if hk.lower() == b"x-nexus-passphrase":
            return hv.decode("utf-8", errors="ignore").strip()
    return ""


async def _send_json_resp(send: Any, status: int, payload: dict[str, Any]) -> None:
    body_b = json.dumps(payload).encode("utf-8")
    await send({
        "type": "http.response.start", "status": status,
        "headers": [
            (b"content-type", b"application/json"), (b"content-length", str(len(body_b)).encode("ascii")),
            (b"cache-control", b"no-store, no-cache, private"), (b"x-content-type-options", b"nosniff"),
        ],
    })
    await send({"type": "http.response.body", "body": body_b})


async def _handle_catalog_api(headers: list[tuple[bytes, bytes]], req_path: str, method: str, raw_qs: str, send: Any) -> bool:
    """Authenticate and handle /web/api/catalog/{status,accept,reset} Price Book sync endpoints."""
    from agy_nexus.catalog_sync import accept_catalog_override, get_catalog_sync_status, reset_catalog_override
    from agy_nexus.model_pricing import clear_model_catalog_cache

    if not verify_passphrase(_extract_passphrase(headers)):
        await _send_json_resp(send, 401, {"ok": False, "error": "Invalid spoken deadbolt passphrase."})
        return True
    action = req_path.rsplit("/web/api/catalog/", 1)[-1].strip("/")
    qs_map = urllib.parse.parse_qs(raw_qs, keep_blank_values=True) if raw_qs else {}
    if action == "status" and method in ("GET", "POST"):
        refresh = (qs_map.get("refresh", ["0"])[0] or "0").strip().lower() in ("1", "true", "yes")
        st = await anyio.to_thread.run_sync(
            functools.partial(get_catalog_sync_status, data_dir=AGY_DATA_DIR, bg_dir=AGY_BG_DIR, allow_network=True, refresh=refresh)
        )
        await _send_json_resp(send, 200, {"ok": True, "catalog_sync": st})
        return True
    if action == "accept" and method == "POST":
        res = await anyio.to_thread.run_sync(
            functools.partial(accept_catalog_override, data_dir=AGY_DATA_DIR, bg_dir=AGY_BG_DIR, allow_fetch=True, on_change=clear_model_catalog_cache)
        )
        if not res.get("ok"):
            await _send_json_resp(send, 400, res)
            return True
        st = await anyio.to_thread.run_sync(
            functools.partial(get_catalog_sync_status, data_dir=AGY_DATA_DIR, bg_dir=AGY_BG_DIR, allow_network=False)
        )
        await _send_json_resp(send, 200, {**res, "catalog_sync": st})
        return True
    if action == "reset" and method == "POST":
        res = reset_catalog_override(data_dir=AGY_DATA_DIR, on_change=clear_model_catalog_cache)
        st = await anyio.to_thread.run_sync(
            functools.partial(get_catalog_sync_status, data_dir=AGY_DATA_DIR, bg_dir=AGY_BG_DIR, allow_network=False)
        )
        await _send_json_resp(send, 200, {**res, "catalog_sync": st})
        return True
    await _send_json_resp(send, 405, {"ok": False, "error": "Unsupported catalog sync action or method."})
    return True


async def _serve_static_or_media(web_dir: Path, req_path: str, method: str, send: Any) -> bool:
    """Serve signed /web/media/ files, PWA static assets, or JSON 404 for unknown non-API paths."""
    if "/web/media/" in req_path:
        target_file, mime_bytes, status_code, msg_text = verify_and_resolve_media(req_path)
        if status_code == 200 and target_file is not None:
            if target_file.stat().st_size > 45 * 1024 * 1024:
                status_code, msg_text = 413, "Media file exceeds 45 MB limit."
            else:
                media_bytes = await anyio.to_thread.run_sync(target_file.read_bytes)
                await send({
                    "type": "http.response.start", "status": 200,
                    "headers": [
                        (b"content-type", mime_bytes), (b"content-length", str(len(media_bytes)).encode("ascii")),
                        (b"cache-control", b"private, max-age=604800"), (b"x-content-type-options", b"nosniff"),
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
            cc_val = b"no-store, no-cache, must-revalidate" if asset_name == "sw.js" else b"no-cache"
            resp_hdrs = [
                (b"content-type", PWA_ASSETS[asset_name]),
                (b"content-length", str(len(asset_bytes)).encode("ascii")),
                (b"cache-control", cc_val),
                (b"x-content-type-options", b"nosniff"),
            ]
            if asset_name == "sw.js":
                resp_hdrs.append((b"service-worker-allowed", b"/"))
            await send({"type": "http.response.start", "status": 200, "headers": resp_hdrs})
            await send({"type": "http.response.body", "body": b"" if method == "HEAD" else asset_bytes})
            return True

    if "/api/" not in req_path:
        nf_b = b'{"ok":false,"error":"Asset not found"}'
        await send({
            "type": "http.response.start", "status": 404,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(nf_b)).encode("ascii")), (b"x-content-type-options", b"nosniff")],
        })
        await send({"type": "http.response.body", "body": b"" if method == "HEAD" else nf_b})
        return True
    return False


async def _handle_web_stats(headers: list[tuple[bytes, bytes]], raw_qs: str, t0: float, send: Any) -> bool:
    """Authenticate and return /web/api/stats JSON bundle."""
    supplied_pass = _extract_passphrase(headers)

    qs_map = urllib.parse.parse_qs(raw_qs, keep_blank_values=True) if raw_qs else {}
    period_val = (qs_map.get("period", ["current_month"])[0] or "current_month").strip()
    timeframe_val = (qs_map.get("timeframe", [""])[0] or "").strip()
    horizon_val = (qs_map.get("horizon_mode", [""])[0] or "").strip()
    try:
        offset_val = int((qs_map.get("offset", ["0"])[0] or "0").strip())
    except ValueError:
        offset_val = 0
    anchor_val = (qs_map.get("anchor_date", [""])[0] or "").strip()
    project_id_val = (qs_map.get("project_id", [""])[0] or "").strip()
    include_ascii_val = (qs_map.get("include_ascii", ["1"])[0] or "1").strip().lower() not in ("0", "false", "no")
    compact_sessions_val = (qs_map.get("compact_sessions", ["0"])[0] or "0").strip().lower() in ("1", "true", "yes")

    if not verify_passphrase(supplied_pass):
        await _send_json_resp(send, 401, {"ok": False, "error": "Invalid spoken deadbolt passphrase."})
        print("[agy-nexus] http=GET rpc=web_stats_unauthorized tool=- status=401 bytes=0 ms=1", flush=True)
        return True

    bundle = await anyio.to_thread.run_sync(
        functools.partial(
            build_nexus_stats_bundle,
            data_dir=AGY_DATA_DIR, brain_dir=AGY_BRAIN_DIR, db_file=AGY_DB_FILE,
            config_dir=AGY_CONFIG_DIR, bg_dir=AGY_BG_DIR, period=period_val,
            timeframe=timeframe_val, horizon_mode=horizon_val, offset=offset_val,
            anchor_date=anchor_val, project_id=project_id_val,
            include_ascii=include_ascii_val, compact_sessions=compact_sessions_val,
        )
    )
    ok_b = json.dumps({"ok": True, **bundle}).encode("utf-8")
    await send({
        "type": "http.response.start", "status": 200,
        "headers": [
            (b"content-type", b"application/json"), (b"content-length", str(len(ok_b)).encode("ascii")),
            (b"cache-control", b"no-store, no-cache, private"), (b"x-content-type-options", b"nosniff"),
        ],
    })
    await send({"type": "http.response.body", "body": ok_b})
    elapsed_ms = int((time.time() - t0) * 1000)
    safe_period = re.sub(r"[^a-z0-9_-]", "", (timeframe_val or period_val).lower())[:24] or "current_month"
    print(f"[agy-nexus] http=GET rpc=web_stats tool={safe_period} status=200 bytes={len(ok_b)} ms={elapsed_ms}", flush=True)
    return True


async def handle_web_request(
    scope: dict[str, Any], receive: Any, send: Any, web_dir: Path,
    req_path: str, method: str, headers: list[tuple[bytes, bytes]], raw_qs: str = "",
) -> bool:
    """Handle /web static assets, media endpoints, and Overwatch JSON APIs."""
    t0 = time.time()
    if method in ("GET", "HEAD") and req_path == "":
        await send({"type": "http.response.start", "status": 302, "headers": [(b"location", b"/web"), (b"content-length", b"0")]})
        await send({"type": "http.response.body", "body": b""})
        return True

    if method in ("GET", "HEAD"):
        target_html: Path | None = None
        if req_path.endswith("/web/v9") or req_path.endswith("/web/v9/index.html"):
            target_html = web_dir / "v9" / "index.html"
        elif req_path.endswith("/web") or req_path.endswith("/web/index.html"):
            target_html = web_dir / "index.html"
        if target_html is not None:
            html_bytes = target_html.read_bytes() if target_html.is_file() else b"<h1>Dashboard not found</h1>"
            await send({
                "type": "http.response.start", "status": 200,
                "headers": [
                    (b"content-type", b"text/html; charset=utf-8"),
                    (b"content-length", str(len(html_bytes)).encode("ascii")),
                    (b"cache-control", b"no-store, no-cache, must-revalidate"),
                ],
            })
            await send({"type": "http.response.body", "body": b"" if method == "HEAD" else html_bytes})
            print(f"[agy-nexus] http={method} rpc=web_ui tool=- status=200 bytes={len(html_bytes)} ms=1", flush=True)
            return True

    if "/web/api/catalog/" in req_path:
        return await _handle_catalog_api(headers, req_path, method, raw_qs, send)

    if method in ("GET", "HEAD") and "/web/" in req_path and not req_path.endswith("/web/api/stats"):
        if await _serve_static_or_media(web_dir, req_path, method, send):
            return True

    if ("/api/workspace/" in req_path or "/api/sessions/" in req_path) and not req_path.endswith("/upload"):
        await handle_bucket_api_request(scope, receive, send, req_path, method, headers, raw_qs=raw_qs)
        return True

    if method == "POST" and ("/api/sessions/" in req_path and req_path.endswith("/upload")):
        m_conv = re.search(r"/api/sessions/([^/]+)/upload$", req_path)
        if m_conv:
            conv_id_req = m_conv.group(1).strip()
            await handle_session_upload_request(scope, receive, send, conv_id_req, headers)
            elapsed_ms = int((time.time() - t0) * 1000)
            safe_conv = re.sub(r"[^A-Za-z0-9_-]", "", conv_id_req)[:48] or "invalid"
            print(f"[agy-nexus] http=POST rpc=session_upload conv={safe_conv} ms={elapsed_ms}", flush=True)
            return True

    if method in ("GET", "POST") and req_path.endswith("/web/api/stats"):
        return await _handle_web_stats(headers, raw_qs, t0, send)

    return False
