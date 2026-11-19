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
import agy_nexus.config as cfg
from agy_nexus.media import record_verified_public_origin
from agy_nexus.stats import record_wire_telemetry
from agy_nexus.web_routes import handle_web_request
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
    if not raw or "@" in raw or any(c.isspace() for c in raw):
        return False
    if raw.startswith("[") and "]" in raw:
        host = raw[1 : raw.index("]")].strip().lower()
    else:
        host = raw.split(":", 1)[0].strip().rstrip(".").lower()
    if not host:
        return False
    try:
        ip = ipaddress.ip_address(host)
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        return bool((ip.is_loopback or ip.is_private) and not ip.is_unspecified)
    except ValueError:
        pass
    return (
        host in ("localhost", "host.docker.internal", "testserver", "ag-bridge-mcp")
        or "." not in host
        or host.endswith((".lan", ".local", ".internal", ".home.arpa"))
    )


def _is_allowed_lan_client_ip(client_ip: str) -> bool:
    raw = (client_ip or "").strip()
    if raw == "testclient":
        return True
    if not raw:
        return False
    try:
        ip = ipaddress.ip_address(raw.split("%", 1)[0])
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        return bool((ip.is_loopback or ip.is_private) and not ip.is_unspecified)
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

    async def _route_praxis_doorway(
        self,
        scope: dict[str, Any],
        send: Any,
        method: str,
        req_path: str,
        headers: list[tuple[bytes, bytes]],
    ) -> tuple[bool, dict[str, Any], Any]:
        """Enforce zero-trust LAN/localhost guard and token routing for /praxis and /polyglot routes."""
        client_ip = str((scope.get("client") or ("", 0))[0] or "")
        has_proxy_hdr, host_val, origin_val = False, "", ""
        for hk, hv in headers:
            hkl = hk.lower()
            if hkl in _PROXY_HEADER_KEYS:
                has_proxy_hdr = True
                break
            if hkl == b"host":
                if host_val:
                    has_proxy_hdr = True
                    break
                host_val = hv.decode("latin-1", errors="ignore").strip()
            elif hkl == b"origin":
                if origin_val:
                    has_proxy_hdr = True
                    break
                origin_val = hv.decode("latin-1", errors="ignore").strip()
        origin_ok = True
        if origin_val:
            parsed_origin = urllib.parse.urlparse(origin_val)
            origin_ok = (
                origin_val.lower() != "null"
                and not parsed_origin.username
                and not parsed_origin.password
                and _is_allowed_lan_host(parsed_origin.hostname or "")
            )
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
            return True, scope, self.app
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
            return True, scope, self.app
        new_scope = {**scope, "path": self.praxis_mount_path, "raw_path": self.praxis_mount_path.encode("ascii")}
        return False, new_scope, self.praxis_app

    async def _handle_non_post_http(self, send: Any, method: str, req_path: str) -> bool:
        """Handle MCP Streamable HTTP preflight/405 responses and non-POST health/probe verbs."""
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
                return True
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
            return True
        if method == "HEAD":
            await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"application/json"), (b"content-length", b"0")]})
            await send({"type": "http.response.body", "body": b""})
            print("[agy-nexus] http=HEAD rpc=health tool=- status=200 bytes=0 ms=0", flush=True)
            return True
        if method == "OPTIONS":
            await send({"type": "http.response.start", "status": 204, "headers": [(b"allow", b"GET, POST, HEAD, OPTIONS"), (b"content-length", b"0")]})
            await send({"type": "http.response.body", "body": b""})
            print("[agy-nexus] http=OPTIONS rpc=preflight tool=- status=204 bytes=0 ms=0", flush=True)
            return True
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
            return True
        return False

    @staticmethod
    def _prepare_post_scope_and_summary(scope: dict[str, Any], method: str, headers: list[tuple[bytes, bytes]]) -> dict[str, Any]:
        """Normalize Accept header on POST requests and initialize JSON-RPC wire summary metadata."""
        new_headers: list[tuple[bytes, bytes]] = []
        found_accept = False
        user_agent_str, header_product_str = "", ""
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
        return {
            "method": method, "rpc": "", "tool": "", "status": 0, "bytes": 0,
            "req_bytes": 0, "product": header_product_str, "user_agent": user_agent_str, "reported_tokens": 0,
        }

    @staticmethod
    def _parse_rpc_request_body(full_body: bytes, rpc_summary: dict[str, Any]) -> None:
        """Extract JSON-RPC method, tool name, client product, and reported tokens from POST payload."""
        try:
            rpc_summary["req_bytes"] = len(full_body)
            data = json.loads(full_body.decode("utf-8", errors="ignore"))
            if not isinstance(data, dict):
                return
            rpc_summary["rpc"] = str(data.get("method") or "")
            params = data.get("params")
            if not isinstance(params, dict):
                return
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

    async def _proxy_post_and_log(
        self,
        scope: dict[str, Any],
        receive: Any,
        send: Any,
        target_asgi_app: Any,
        method: str,
        headers: list[tuple[bytes, bytes]],
        t0: float,
    ) -> None:
        """Proxy MCP POST request through target ASGI app and persist compact wire telemetry."""
        rpc_summary = self._prepare_post_scope_and_summary(scope, method, headers)
        body_chunks: list[bytes] = []

        async def wrapped_receive() -> dict[str, Any]:
            msg = await receive()
            if msg.get("type") == "http.request":
                chunk = msg.get("body") or b""
                if chunk:
                    body_chunks.append(chunk)
                if not msg.get("more_body", False) and body_chunks:
                    self._parse_rpc_request_body(b"".join(body_chunks), rpc_summary)
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

        is_praxis = target_asgi_app is self.praxis_app
        log_prefix = "[agy-praxis]" if is_praxis else "[agy-nexus]"
        try:
            await target_asgi_app(scope, wrapped_receive, wrapped_send)
        finally:
            elapsed_ms = int((time.time() - t0) * 1000)
            rpc_method = str(rpc_summary["rpc"] or "-").strip()
            tool_label = str(rpc_summary["tool"] or "").strip() or (f"[rpc:{rpc_method}]" if rpc_method and rpc_method != "-" else "-")
            tel_event = {
                "ts": datetime.now(timezone.utc).isoformat(), "http": rpc_summary["method"],
                "rpc": rpc_method, "tool": tool_label, "doorway": "praxis" if is_praxis else "nexus",
                "status": rpc_summary["status"], "bytes": rpc_summary["bytes"], "req_bytes": rpc_summary["req_bytes"],
                "product": rpc_summary["product"] or ("agy-praxis-mcp" if is_praxis else ""),
                "user_agent": rpc_summary["user_agent"], "reported_tokens": rpc_summary["reported_tokens"], "ms": elapsed_ms,
            }
            await anyio.to_thread.run_sync(record_wire_telemetry, tel_event, cfg.AGY_BG_DIR)
            print(
                f"{log_prefix} http={tel_event['http']} rpc={tel_event['rpc']} "
                f"tool={tel_event['tool']} status={tel_event['status']} bytes={tel_event['bytes']} ms={elapsed_ms}",
                flush=True,
            )

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
        if cfg.PATH_SECRET and req_path.startswith(f"/{cfg.PATH_SECRET}/"):
            record_verified_public_origin(headers, client_ip=str((scope.get("client") or ("", 0))[0] or ""))
        if req_path.startswith("/github-webhook-sync"):
            await handle_webhook_sync_proxy(method, req_path, raw_qs, headers, receive, send)
            return
        target_asgi_app = self.app
        if req_path in ("/praxis", "/polyglot") or req_path.startswith("/praxis/") or req_path.startswith("/polyglot/"):
            handled, scope, target_asgi_app = await self._route_praxis_doorway(scope, send, method, req_path, headers)
            if handled:
                return
        if await handle_web_request(scope, receive, send, self.web_dir, req_path, method, headers, raw_qs=raw_qs):
            return
        if await self._handle_non_post_http(send, method, req_path):
            return
        await self._proxy_post_and_log(scope, receive, send, target_asgi_app, method, headers, t0)
