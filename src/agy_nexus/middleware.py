#!/usr/bin/env python3
"""
agy_nexus.middleware — Stateless Cloud MCP Compatibility, /web Dashboard & Wire Telemetry ASGI Middleware.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any

from agy_nexus.config import (
    AGY_BG_DIR,
    AGY_BRAIN_DIR,
    AGY_CONFIG_DIR,
    AGY_DATA_DIR,
    AGY_DB_FILE,
    verify_passphrase,
)
from agy_nexus.stats import build_nexus_stats_bundle, record_wire_telemetry

class BridgeCompatMiddleware:
    """ASGI wrapper serving /web Overwatch dashboard, HTTP method discovery, and sanitized JSON-RPC telemetry."""

    def __init__(self, app: Any) -> None:
        self.app = app
        self.web_dir = Path(__file__).resolve().parent.parent.parent / "web"
        self.web_html_path = self.web_dir / "index.html"
        self.pwa_assets = {
            "styles.css": b"text/css; charset=utf-8",
            "charts.js": b"application/javascript; charset=utf-8",
            "app.js": b"application/javascript; charset=utf-8",
            "manifest.webmanifest": b"application/manifest+json; charset=utf-8",
            "sw.js": b"application/javascript; charset=utf-8",
            "icon.svg": b"image/svg+xml",
            "icon-192.png": b"image/png",
            "icon-512.png": b"image/png",
        }

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        t0 = time.time()
        method = str(scope.get("method", "")).upper()
        req_path = str(scope.get("path", "") or "").rstrip("/")
        raw_qs = (scope.get("query_string") or b"").decode("latin-1", errors="ignore")
        headers = list(scope.get("headers", []))

        # 0. Redirect bare root GET / -> /web
        if method == "GET" and req_path == "":
            await send({
                "type": "http.response.start",
                "status": 302,
                "headers": [(b"location", b"/web"), (b"content-length", b"0")],
            })
            await send({"type": "http.response.body", "body": b""})
            return

        # 1. Serve /web dashboard HTML (accessible at /web or /{PATH_SECRET}/web)
        if method == "GET" and (req_path.endswith("/web") or req_path.endswith("/web/index.html")):
            html_bytes = self.web_html_path.read_bytes() if self.web_html_path.is_file() else b"<h1>Dashboard not found</h1>"
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"text/html; charset=utf-8"),
                    (b"content-length", str(len(html_bytes)).encode("ascii")),
                    (b"cache-control", b"no-cache"),
                ],
            })
            await send({"type": "http.response.body", "body": html_bytes})
            print(f"[agy-nexus] http=GET rpc=web_ui tool=- status=200 bytes={len(html_bytes)} ms=1", flush=True)
            return

        # 1b. Serve Chromium PWA static assets (/web/manifest.webmanifest, /web/sw.js, /web/icon-*.png, /web/icon.svg)
        if method == "GET" and "/web/" in req_path:
            asset_name = req_path.rsplit("/web/", 1)[-1]
            if asset_name in self.pwa_assets:
                asset_path = self.web_dir / asset_name
                if asset_path.is_file():
                    asset_bytes = asset_path.read_bytes()
                    resp_hdrs = [
                        (b"content-type", self.pwa_assets[asset_name]),
                        (b"content-length", str(len(asset_bytes)).encode("ascii")),
                        (b"cache-control", b"no-cache"),
                    ]
                    if asset_name == "sw.js":
                        resp_hdrs.append((b"service-worker-allowed", b"/"))
                    await send({"type": "http.response.start", "status": 200, "headers": resp_hdrs})
                    await send({"type": "http.response.body", "body": asset_bytes})
                    return

        # 2. Serve /web/api/stats JSON (authenticated by X-Nexus-Passphrase header)
        if method in ("GET", "POST") and req_path.endswith("/web/api/stats"):
            supplied_pass = ""
            for hk, hv in headers:
                if hk.lower() == b"x-nexus-passphrase":
                    supplied_pass = hv.decode("utf-8", errors="ignore").strip()
                    break
            period_val = "current_month"
            for kv in raw_qs.split("&"):
                if kv.startswith("period="):
                    period_val = kv.split("=", 1)[1].strip() or "current_month"
            if not verify_passphrase(supplied_pass):
                err_b = json.dumps({"ok": False, "error": "Invalid spoken deadbolt passphrase."}).encode("utf-8")
                await send({
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(err_b)).encode("ascii"))],
                })
                await send({"type": "http.response.body", "body": err_b})
                print("[agy-nexus] http=GET rpc=web_stats_unauthorized tool=- status=401 bytes=0 ms=1", flush=True)
                return
            bundle = build_nexus_stats_bundle(
                data_dir=AGY_DATA_DIR,
                brain_dir=AGY_BRAIN_DIR,
                db_file=AGY_DB_FILE,
                config_dir=AGY_CONFIG_DIR,
                bg_dir=AGY_BG_DIR,
                period=period_val,
            )
            ok_b = json.dumps({"ok": True, **bundle}).encode("utf-8")
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(ok_b)).encode("ascii")),
                    (b"cache-control", b"no-cache"),
                ],
            })
            await send({"type": "http.response.body", "body": ok_b})
            elapsed_ms = int((time.time() - t0) * 1000)
            print(f"[agy-nexus] http=GET rpc=web_stats tool={period_val} status=200 bytes={len(ok_b)} ms={elapsed_ms}", flush=True)
            return

        if method == "HEAD":
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json"), (b"content-length", b"0")],
            })
            await send({"type": "http.response.body", "body": b""})
            print("[agy-nexus] http=HEAD rpc=health tool=- status=200 bytes=0 ms=0", flush=True)
            return

        if method == "OPTIONS":
            await send({
                "type": "http.response.start",
                "status": 204,
                "headers": [
                    (b"allow", b"GET, POST, HEAD, DELETE, OPTIONS"),
                    (b"content-length", b"0"),
                ],
            })
            await send({"type": "http.response.body", "body": b""})
            print("[agy-nexus] http=OPTIONS rpc=preflight tool=- status=204 bytes=0 ms=0", flush=True)
            return

        if method in ("GET", "DELETE"):
            body = json.dumps({"ok": True, "service": "agy-nexus-mcp", "version": "2.2.0", "transport": "streamable-http", "stateless": True, "web_dashboard": "/web"}).encode("utf-8")
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"x-accel-buffering", b"no"),
                    (b"cache-control", b"no-cache, no-transform"),
                ],
            })
            await send({"type": "http.response.body", "body": body})
            print(f"[agy-nexus] http={method} rpc=probe tool=- status=200 bytes={len(body)} ms=0", flush=True)
            return

        # Normalize Accept header on POST so cloud MCP clients sending only application/json never get 406
        new_headers: list[tuple[bytes, bytes]] = []
        found_accept = False
        user_agent_str = ""
        header_product_str = ""
        for k, v in headers:
            kl = k.lower()
            if kl == b"accept":
                found_accept = True
                val_str = v.decode("latin-1", errors="ignore")
                if "application/json" not in val_str or "text/event-stream" not in val_str:
                    v = b"application/json, text/event-stream"
            elif kl == b"user-agent":
                user_agent_str = v.decode("utf-8", errors="ignore").strip()
            elif kl == b"x-client-product":
                header_product_str = v.decode("utf-8", errors="ignore").strip()
            new_headers.append((k, v))
        if not found_accept:
            new_headers.append((b"accept", b"application/json, text/event-stream"))
        scope["headers"] = new_headers

        rpc_summary: dict[str, Any] = {
            "method": method,
            "rpc": "",
            "tool": "",
            "status": 0,
            "bytes": 0,
            "req_bytes": 0,
            "product": header_product_str,
            "user_agent": user_agent_str,
            "reported_tokens": 0,
        }
        body_chunks: list[bytes] = []

        async def wrapped_receive() -> dict[str, Any]:
            msg = await receive()
            if msg.get("type") == "http.request":
                chunk = msg.get("body") or b""
                if chunk:
                    body_chunks.append(chunk)
                if not msg.get("more_body", False) and body_chunks:
                    try:
                        full_body = b"".join(body_chunks)
                        rpc_summary["req_bytes"] = len(full_body)
                        data = json.loads(full_body.decode("utf-8", errors="ignore"))
                        if isinstance(data, dict):
                            rpc_summary["rpc"] = str(data.get("method") or "")
                            params = data.get("params")
                            if isinstance(params, dict):
                                if params.get("name"):
                                    rpc_summary["tool"] = str(params.get("name"))
                                c_info = params.get("clientInfo")
                                if isinstance(c_info, dict) and c_info.get("name") and not rpc_summary["product"]:
                                    rpc_summary["product"] = str(c_info.get("name"))
                                t_args = params.get("arguments")
                                if isinstance(t_args, dict):
                                    if t_args.get("client_product"):
                                        rpc_summary["product"] = str(t_args.get("client_product"))
                                    if t_args.get("client_tokens_reported"):
                                        rpc_summary["reported_tokens"] = int(t_args.get("client_tokens_reported") or 0)
                    except Exception:
                        pass
            return msg

        async def wrapped_send(msg: dict[str, Any]) -> None:
            if msg.get("type") == "http.response.start":
                rpc_summary["status"] = int(msg.get("status", 0))
                resp_headers = list(msg.get("headers") or [])
                existing_keys = {k.lower() for k, _ in resp_headers}
                if b"x-accel-buffering" not in existing_keys:
                    resp_headers.append((b"x-accel-buffering", b"no"))
                if b"cache-control" not in existing_keys:
                    resp_headers.append((b"cache-control", b"no-cache, no-transform"))
                msg = {**msg, "headers": resp_headers}
            elif msg.get("type") == "http.response.body":
                rpc_summary["bytes"] = int(rpc_summary["bytes"]) + len(msg.get("body") or b"")
            await send(msg)

        try:
            await self.app(scope, wrapped_receive, wrapped_send)
        finally:
            elapsed_ms = int((time.time() - t0) * 1000)
            tel_event = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "http": rpc_summary["method"],
                "rpc": rpc_summary["rpc"] or "-",
                "tool": rpc_summary["tool"] or "-",
                "status": rpc_summary["status"],
                "bytes": rpc_summary["bytes"],
                "req_bytes": rpc_summary["req_bytes"],
                "product": rpc_summary["product"],
                "user_agent": rpc_summary["user_agent"],
                "reported_tokens": rpc_summary["reported_tokens"],
                "ms": elapsed_ms,
            }
            record_wire_telemetry(tel_event, AGY_BG_DIR)
            print(
                f"[agy-nexus] http={tel_event['http']} rpc={tel_event['rpc']} "
                f"tool={tel_event['tool']} status={tel_event['status']} bytes={tel_event['bytes']} ms={elapsed_ms}",
                flush=True,
            )
