#!/usr/bin/env python3
"""
agy_nexus.middleware — Stateless Cloud MCP Compatibility, /web Dashboard & Wire Telemetry ASGI Middleware.
"""

from __future__ import annotations

from datetime import datetime, timezone
import functools
import hmac
import ipaddress
import json
from pathlib import Path
import re
import time
from typing import Any
import urllib.parse

import anyio

from agy_nexus import __version__
from agy_nexus.config import (
    AGY_BG_DIR,
    AGY_BRAIN_DIR,
    AGY_CONFIG_DIR,
    AGY_DATA_DIR,
    AGY_DB_FILE,
    PATH_SECRET,
    verify_passphrase,
)
from agy_nexus.media import record_verified_public_origin, verify_and_resolve_media
from agy_nexus.stats import build_nexus_stats_bundle, record_wire_telemetry
from agy_nexus.webhook_proxy import handle_webhook_sync_proxy

_PROXY_HEADER_KEYS: frozenset[bytes] = frozenset({
    b"x-forwarded-for",
    b"x-real-ip",
    b"forwarded",
    b"cf-connecting-ip",
    b"x-forwarded-proto",
    b"x-forwarded-host",
    b"x-forwarded-port",
    b"true-client-ip",
    b"cf-ray",
    b"via",
})


def _is_allowed_lan_host(raw_host: str) -> bool:
    """Allow only loopback/RFC1918 IPs, localhost, Docker internal names, or local .lan/.local domains."""
    raw = (raw_host or "").strip()
    if not raw:
        return False
    if raw.startswith("[") and "]" in raw:
        host = raw[1 : raw.index("]")].strip().lower()
    else:
        host = raw.split(":", 1)[0].strip().rstrip(".").lower()
    if not host:
        return False
    try:
        ip = ipaddress.ip_address(host)
        return bool(ip.is_loopback or ip.is_private)
    except ValueError:
        pass
    return (
        host in ("localhost", "host.docker.internal", "testserver", "ag-bridge-mcp")
        or "." not in host
        or host.endswith((".lan", ".local", ".internal", ".home.arpa"))
    )


def _is_allowed_lan_client_ip(client_ip: str) -> bool:
    raw = (client_ip or "").strip()
    if raw in ("", "testclient"):
        return True
    try:
        ip = ipaddress.ip_address(raw.split("%", 1)[0])
        return bool(ip.is_loopback or ip.is_private)
    except ValueError:
        return False


async def _multiplex_lifespan(app_a: Any, app_b: Any, scope: dict[str, Any], receive: Any, send: Any) -> None:
    """Run ASGI lifespans for both FastMCP servers (agy-nexus-mcp + agy-polyglot-mcp) in lockstep."""
    in_a_w, in_a_r = anyio.create_memory_object_stream[dict[str, Any]](4)
    in_b_w, in_b_r = anyio.create_memory_object_stream[dict[str, Any]](4)
    out_a_w, out_a_r = anyio.create_memory_object_stream[dict[str, Any]](4)
    out_b_w, out_b_r = anyio.create_memory_object_stream[dict[str, Any]](4)
    try:
        async with anyio.create_task_group() as tg:
            tg.start_soon(app_a, dict(scope), in_a_r.receive, out_a_w.send)
            tg.start_soon(app_b, dict(scope), in_b_r.receive, out_b_w.send)

            msg = await receive()
            if msg.get("type") != "lifespan.startup":
                tg.cancel_scope.cancel()
                return
            await in_a_w.send(msg)
            await in_b_w.send(msg)
            res_a = await out_a_r.receive()
            res_b = await out_b_r.receive()
            if res_a.get("type") == "lifespan.startup.failed":
                await send(res_a)
                tg.cancel_scope.cancel()
                return
            if res_b.get("type") == "lifespan.startup.failed":
                await send(res_b)
                tg.cancel_scope.cancel()
                return
            await send({"type": "lifespan.startup.complete"})

            msg_shut = await receive()
            if msg_shut.get("type") != "lifespan.shutdown":
                tg.cancel_scope.cancel()
                return
            await in_a_w.send(msg_shut)
            await in_b_w.send(msg_shut)
            shut_a = await out_a_r.receive()
            shut_b = await out_b_r.receive()
            if shut_a.get("type") == "lifespan.shutdown.failed":
                await send(shut_a)
            elif shut_b.get("type") == "lifespan.shutdown.failed":
                await send(shut_b)
            else:
                await send({"type": "lifespan.shutdown.complete"})
    finally:
        for stream in (in_a_w, in_b_w, out_a_w, out_b_w, in_a_r, in_b_r, out_a_r, out_b_r):
            await stream.aclose()


class BridgeCompatMiddleware:
    """ASGI wrapper serving /web Overwatch dashboard, dual Nexus + Praxis MCP routing, Streamable HTTP 405 compliance, and sanitized JSON-RPC telemetry."""

    def __init__(
        self,
        app: Any,
        polyglot_app: Any = None,
        polyglot_token: str = "",
        praxis_app: Any = None,
        praxis_token: str = "",
    ) -> None:
        self.app = app
        self.praxis_app = praxis_app if praxis_app is not None else polyglot_app
        self.polyglot_app = self.praxis_app
        self.praxis_token = (praxis_token or polyglot_token or "").strip()
        self.polyglot_token = (polyglot_token or praxis_token or "").strip()
        self.praxis_mount_path = f"/praxis/{self.praxis_token}/mcp" if self.praxis_token else "/praxis/mcp"
        self.web_dir = Path(__file__).resolve().parent.parent.parent / "web"
        self.web_html_path = self.web_dir / "index.html"
        self.pwa_assets = {
            "styles.css": b"text/css; charset=utf-8", "palettes.js": b"application/javascript; charset=utf-8",
            "demo_data.js": b"application/javascript; charset=utf-8", "charts.js": b"application/javascript; charset=utf-8",
            "hierarchy.js": b"application/javascript; charset=utf-8", "health.js": b"application/javascript; charset=utf-8",
            "app.js": b"application/javascript; charset=utf-8", "uploads.js": b"application/javascript; charset=utf-8",
            "manifest.webmanifest": b"application/manifest+json; charset=utf-8", "sw.js": b"application/javascript; charset=utf-8",
            "icon.svg": b"image/svg+xml", "icon-192.png": b"image/png", "icon-512.png": b"image/png",
        }

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        scope_type = scope.get("type")
        if scope_type == "lifespan" and self.praxis_app is not None:
            await _multiplex_lifespan(self.app, self.praxis_app, scope, receive, send)
            return
        if scope_type != "http":
            await self.app(scope, receive, send)
            return

        t0 = time.time()
        method = str(scope.get("method", "")).upper()
        req_path = str(scope.get("path", "") or "").rstrip("/")
        raw_qs = (scope.get("query_string") or b"").decode("latin-1", errors="ignore")
        headers = list(scope.get("headers", []))
        if PATH_SECRET and req_path.startswith(f"/{PATH_SECRET}/"):
            client_ip = str((scope.get("client") or ("", 0))[0] or "")
            record_verified_public_origin(headers, client_ip=client_ip)

        if req_path.startswith("/github-webhook-sync"):
            await handle_webhook_sync_proxy(method, req_path, raw_qs, headers, receive, send)
            return

        # Zero-Trust LAN/Localhost Guard for agy-praxis-mcp (/praxis/{TOKEN}/mcp + legacy /polyglot/{TOKEN}/mcp alias)
        target_asgi_app = self.app
        if req_path in ("/praxis", "/polyglot") or req_path.startswith("/praxis/") or req_path.startswith("/polyglot/"):
            client_ip = str((scope.get("client") or ("", 0))[0] or "")
            has_proxy_hdr = False
            host_val = ""
            origin_val = ""
            for hk, hv in headers:
                hkl = hk.lower()
                if hkl in _PROXY_HEADER_KEYS:
                    has_proxy_hdr = True
                    break
                if hkl == b"host" and not host_val:
                    host_val = hv.decode("latin-1", errors="ignore").strip()
                elif hkl == b"origin" and not origin_val:
                    origin_val = hv.decode("latin-1", errors="ignore").strip()
            origin_ok = True
            if origin_val:
                parsed_origin = urllib.parse.urlparse(origin_val)
                origin_ok = origin_val.lower() != "null" and _is_allowed_lan_host(parsed_origin.netloc)
            if has_proxy_hdr or not _is_allowed_lan_host(host_val) or not origin_ok or not _is_allowed_lan_client_ip(client_ip):
                deny_b = b'{"ok":false,"error":"agy-praxis-mcp is restricted to direct LAN/localhost IDE clients."}'
                await send({
                    "type": "http.response.start",
                    "status": 403,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(deny_b)).encode("ascii")),
                        (b"cache-control", b"no-store"),
                        (b"x-content-type-options", b"nosniff"),
                    ],
                })
                await send({"type": "http.response.body", "body": deny_b})
                print(f"[agy-praxis] http={method} rpc=lan_guard_blocked tool=- status=403 bytes={len(deny_b)} ms=0", flush=True)
                return
            parts = req_path.split("/")
            cand_tok = parts[2].encode("utf-8") if len(parts) == 4 else b""
            valid_tokens = [t.encode("utf-8") for t in {self.praxis_token, self.polyglot_token} if len(t) >= 32]
            token_valid = (
                self.praxis_app is not None
                and len(parts) == 4
                and parts[1] in ("praxis", "polyglot")
                and parts[3] == "mcp"
                and any(hmac.compare_digest(cand_tok, vt) for vt in valid_tokens)
            )
            if not token_valid:
                nf_poly = b'{"ok":false,"error":"Not found"}'
                await send({
                    "type": "http.response.start",
                    "status": 404,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(nf_poly)).encode("ascii"))],
                })
                await send({"type": "http.response.body", "body": nf_poly})
                return
            scope = {**scope, "path": self.praxis_mount_path, "raw_path": self.praxis_mount_path.encode("ascii")}
            target_asgi_app = self.praxis_app

        # 0. Redirect bare root GET / -> /web
        if method == "GET" and req_path == "":
            await send({"type": "http.response.start", "status": 302, "headers": [(b"location", b"/web"), (b"content-length", b"0")]})
            await send({"type": "http.response.body", "body": b""})
            return

        # 1. Serve /web dashboard HTML (accessible at /web or /{PATH_SECRET}/web)
        if method == "GET" and (req_path.endswith("/web") or req_path.endswith("/web/index.html")):
            html_bytes = self.web_html_path.read_bytes() if self.web_html_path.is_file() else b"<h1>Dashboard not found</h1>"
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/html; charset=utf-8"), (b"content-length", str(len(html_bytes)).encode("ascii")), (b"cache-control", b"no-cache")],
            })
            await send({"type": "http.response.body", "body": html_bytes})
            print(f"[agy-nexus] http=GET rpc=web_ui tool=- status=200 bytes={len(html_bytes)} ms=1", flush=True)
            return

        # 1b. Serve Chromium PWA static assets (/web/manifest.webmanifest, /web/sw.js, /web/icon-*.png, /web/icon.svg)
        if method == "GET" and "/web/" in req_path:
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
                                (b"cache-control", b"private, max-age=1800"),
                                (b"x-content-type-options", b"nosniff"),
                                (b"content-security-policy", b"default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; sandbox"),
                            ],
                        })
                        await send({"type": "http.response.body", "body": media_bytes})
                        return
                err_b = json.dumps({"ok": False, "error": msg_text}).encode("utf-8")
                await send({"type": "http.response.start", "status": status_code, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(err_b)).encode("ascii"))]})
                await send({"type": "http.response.body", "body": err_b})
                return
            asset_name = req_path.rsplit("/web/", 1)[-1]
            if asset_name in self.pwa_assets:
                asset_path = self.web_dir / asset_name
                if asset_path.is_file():
                    asset_bytes = asset_path.read_bytes()
                    resp_hdrs = [
                        (b"content-type", self.pwa_assets[asset_name]),
                        (b"content-length", str(len(asset_bytes)).encode("ascii")),
                        (b"cache-control", b"no-cache"),
                        (b"x-content-type-options", b"nosniff"),
                    ]
                    if asset_name == "sw.js":
                        resp_hdrs.append((b"service-worker-allowed", b"/"))
                    await send({"type": "http.response.start", "status": 200, "headers": resp_hdrs})
                    await send({"type": "http.response.body", "body": asset_bytes})
                    return
            if not req_path.endswith("/web/api/stats"):
                nf_b = b'{"ok":false,"error":"Asset not found"}'
                await send({"type": "http.response.start", "status": 404, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(nf_b)).encode("ascii")), (b"x-content-type-options", b"nosniff")]})
                await send({"type": "http.response.body", "body": nf_b})
                return

        # 2. Serve /web/api/stats JSON (authenticated by X-Nexus-Passphrase header, offloaded from event loop)
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
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(err_b)).encode("ascii")), (b"cache-control", b"no-store")],
                })
                await send({"type": "http.response.body", "body": err_b})
                print("[agy-nexus] http=GET rpc=web_stats_unauthorized tool=- status=401 bytes=0 ms=1", flush=True)
                return
            bundle = await anyio.to_thread.run_sync(
                functools.partial(
                    build_nexus_stats_bundle,
                    data_dir=AGY_DATA_DIR,
                    brain_dir=AGY_BRAIN_DIR,
                    db_file=AGY_DB_FILE,
                    config_dir=AGY_CONFIG_DIR,
                    bg_dir=AGY_BG_DIR,
                    period=period_val,
                )
            )
            ok_b = json.dumps({"ok": True, **bundle}).encode("utf-8")
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(ok_b)).encode("ascii")),
                    (b"cache-control", b"no-store, no-cache, private"),
                    (b"x-content-type-options", b"nosniff"),
                ],
            })
            await send({"type": "http.response.body", "body": ok_b})
            elapsed_ms = int((time.time() - t0) * 1000)
            safe_period = re.sub(r"[^a-z0-9_-]", "", period_val.lower())[:24] or "current_month"
            print(f"[agy-nexus] http=GET rpc=web_stats tool={safe_period} status=200 bytes={len(ok_b)} ms={elapsed_ms}", flush=True)
            return

        # 2b. Serve POST [/web]/api/sessions/{conv_id}/upload (works under /web, /{PATH_SECRET}/web, and LAN)
        if method == "POST" and ("/api/sessions/" in req_path and req_path.endswith("/upload")):
            m_conv = re.search(r"/api/sessions/([^/]+)/upload$", req_path)
            if m_conv:
                conv_id_req = m_conv.group(1).strip()
                from agy_nexus.uploads import handle_session_upload_request
                await handle_session_upload_request(scope, receive, send, conv_id_req, headers)
                elapsed_ms = int((time.time() - t0) * 1000)
                safe_conv = re.sub(r"[^A-Za-z0-9_-]", "", conv_id_req)[:48] or "invalid"
                print(f"[agy-nexus] http=POST rpc=session_upload conv={safe_conv} ms={elapsed_ms}", flush=True)
                return

        # 3. MCP Streamable HTTP Transport Spec Compliance on */mcp routes (POST + OPTIONS only; 405 on GET/DELETE/HEAD)
        is_mcp_route = req_path == "/mcp" or req_path.endswith("/mcp")
        if is_mcp_route and method != "POST":
            if method == "OPTIONS":
                await send({
                    "type": "http.response.start",
                    "status": 204,
                    "headers": [
                        (b"allow", b"POST, OPTIONS"),
                        (b"cache-control", b"no-store"),
                        (b"x-accel-buffering", b"no"),
                        (b"content-length", b"0"),
                    ],
                })
                await send({"type": "http.response.body", "body": b""})
                print("[agy-nexus] http=OPTIONS rpc=mcp_preflight tool=- status=204 bytes=0 ms=0", flush=True)
                return
            mna_body = (
                b""
                if method == "HEAD"
                else b'{"jsonrpc":"2.0","error":{"code":-32000,"message":"Method Not Allowed: stateless streamable-http endpoint accepts POST only."},"id":null}'
            )
            await send({
                "type": "http.response.start",
                "status": 405,
                "headers": [
                    (b"allow", b"POST, OPTIONS"),
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(mna_body)).encode("ascii")),
                    (b"cache-control", b"no-store"),
                    (b"x-accel-buffering", b"no"),
                ],
            })
            await send({"type": "http.response.body", "body": mna_body})
            print(f"[agy-nexus] http={method} rpc=mcp_405 tool=- status=405 bytes={len(mna_body)} ms=0", flush=True)
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
                    (b"allow", b"GET, POST, HEAD, OPTIONS"),
                    (b"content-length", b"0"),
                ],
            })
            await send({"type": "http.response.body", "body": b""})
            print("[agy-nexus] http=OPTIONS rpc=preflight tool=- status=204 bytes=0 ms=0", flush=True)
            return

        if method in ("GET", "DELETE"):
            body = json.dumps({"ok": True, "service": "agy-nexus-mcp", "version": __version__, "transport": "streamable-http", "stateless": True, "web_dashboard": "/web"}).encode("utf-8")
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

        log_prefix = "[agy-praxis]" if target_asgi_app is self.praxis_app else "[agy-nexus]"
        try:
            await target_asgi_app(scope, wrapped_receive, wrapped_send)
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
                "product": rpc_summary["product"] or ("agy-praxis-mcp" if target_asgi_app is self.praxis_app else ""),
                "user_agent": rpc_summary["user_agent"],
                "reported_tokens": rpc_summary["reported_tokens"],
                "ms": elapsed_ms,
            }
            await anyio.to_thread.run_sync(record_wire_telemetry, tel_event, AGY_BG_DIR)
            print(
                f"{log_prefix} http={tel_event['http']} rpc={tel_event['rpc']} "
                f"tool={tel_event['tool']} status={tel_event['status']} bytes={tel_event['bytes']} ms={elapsed_ms}",
                flush=True,
            )
