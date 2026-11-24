#!/usr/bin/env python3
"""
agy_nexus.server — FastMCP Server Bootstrap, Tool Registration & Automated Self-Test Suite.
"""

from __future__ import annotations

import functools
import inspect
import sys
from typing import Any

import anyio
import uvicorn

from agy_nexus import __version__
from agy_nexus.config import (
    BIND_HOST, BIND_PORT, PASS_HASH, PATH_SECRET, get_polyglot_mcp_token, get_praxis_mcp_token, mcp,
)
import agy_nexus.handoff  # noqa: F401
from agy_nexus.middleware import BridgeCompatMiddleware
import agy_nexus.tools_media  # noqa: F401
import agy_nexus.tools_ops  # noqa: F401
import agy_nexus.tools_polyglot  # noqa: F401
from agy_nexus.tools_praxis import praxis_mcp
import agy_nexus.tools_session  # noqa: F401
import agy_nexus.tools_workspace  # noqa: F401


def _offload_sync_mcp_tools(mcp_server: Any) -> int:
    """Wrap synchronous FastMCP tool callables in anyio.to_thread.run_sync so tools/call never blocks Uvicorn's event loop."""
    wrapped_count = 0
    tool_dicts: list[dict[str, Any]] = []
    tm = getattr(mcp_server, "_tool_manager", None)
    if tm is not None and isinstance(getattr(tm, "_tools", None), dict):
        tool_dicts.append(tm._tools)
    lp = getattr(mcp_server, "_local_provider", None)
    if lp is not None and isinstance(getattr(lp, "_components", None), dict):
        tool_dicts.append(lp._components)
    for tdict in tool_dicts:
        for tool_obj in tdict.values():
            orig_fn = getattr(tool_obj, "fn", None)
            if callable(orig_fn) and not inspect.iscoroutinefunction(orig_fn) and not getattr(orig_fn, "_agy_async_offloaded", False):
                @functools.wraps(orig_fn)
                async def _async_fn(*args: Any, __fn: Any = orig_fn, **kwargs: Any) -> Any:
                    return await anyio.to_thread.run_sync(functools.partial(__fn, *args, **kwargs))

                _async_fn.__signature__ = inspect.signature(orig_fn)  # type: ignore[attr-defined]
                _async_fn._agy_async_offloaded = True  # type: ignore[attr-defined]
                tool_obj.fn = _async_fn
                if hasattr(tool_obj, "is_async"):
                    tool_obj.is_async = True
                if hasattr(tool_obj, "_is_async"):
                    tool_obj._is_async = True
                wrapped_count += 1
    return wrapped_count


def build_nexus_http_app(path_secret: str, polyglot_token: str = "", praxis_token: str = "") -> BridgeCompatMiddleware:
    """Construct the dual-MCP (Nexus + Praxis) stateless Streamable HTTP ASGI application."""
    _offload_sync_mcp_tools(mcp)
    _offload_sync_mcp_tools(praxis_mcp)
    eff_praxis_tok = (praxis_token or get_praxis_mcp_token(path_secret) or polyglot_token).strip()
    eff_poly_tok = (polyglot_token or get_polyglot_mcp_token(path_secret) or eff_praxis_tok).strip()
    raw_app = mcp.http_app(
        path=f"/{path_secret}/mcp",
        transport="http",
        stateless_http=True,
        json_response=True,
        host_origin_protection=False,
    )
    praxis_app = praxis_mcp.http_app(
        path=f"/praxis/{eff_praxis_tok}/mcp",
        transport="http",
        stateless_http=True,
        json_response=True,
        host_origin_protection=False,
    )
    return BridgeCompatMiddleware(
        raw_app,
        praxis_app=praxis_app,
        praxis_token=eff_praxis_tok,
        polyglot_token=eff_poly_tok,
    )


def run_self_test() -> int:
    """Run automated verification in an isolated STATE_FILE sandbox without mutating live session_state.json."""
    from agy_nexus.selftest_runner import run_self_test as _run_modular_self_test
    return _run_modular_self_test()


def _run_stdio_transport() -> None:
    """Start agy-nexus-mcp on stdio transport with zero stdout banner noise."""
    _offload_sync_mcp_tools(mcp)
    run_sig = inspect.signature(mcp.run)
    if "show_banner" in run_sig.parameters:
        mcp.run(transport="stdio", show_banner=False)
    else:
        mcp.run(transport="stdio")


def _has_valid_pass_hash(raw_hash: str) -> bool:
    clean = (raw_hash or "").strip().lower()
    return len(clean) == 64 and all(ch in "0123456789abcdef" for ch in clean)


def _is_stdio_flag_enabled(argv: list[str]) -> bool:
    for arg in argv:
        low = arg.strip().lower()
        if low == "--stdio" or low in ("--stdio=true", "--stdio=1", "--stdio=yes"):
            return True
    return False


def main() -> None:
    if "--self-test" in sys.argv:
        sys.exit(run_self_test())

    if _is_stdio_flag_enabled(sys.argv[1:]):
        if not _has_valid_pass_hash(PASS_HASH):
            print(
                f"[*] agy-nexus-mcp v{__version__} starting in --stdio mode without valid 64-hex PASS_HASH; "
                "deadbolt-safe tools are active and private session tools remain locked.",
                file=sys.stderr,
                flush=True,
            )
        else:
            print(f"[*] Starting agy-nexus-mcp v{__version__} (transport=stdio)", file=sys.stderr, flush=True)
        _run_stdio_transport()
        return

    if len(PATH_SECRET) < 32:
        sys.exit("FATAL: PATH_SECRET must be at least 32 hex characters. Ensure secrets.env exists with mode 600.")
    if not _has_valid_pass_hash(PASS_HASH):
        sys.exit("FATAL: PASS_HASH must be a 64-character SHA-256 hex string. Run init_secrets.py to configure.")

    praxis_tok = get_praxis_mcp_token(PATH_SECRET)
    poly_tok = get_polyglot_mcp_token(PATH_SECRET)
    print(f"[*] Starting agy-nexus-mcp v{__version__} on {BIND_HOST}:{BIND_PORT} (stateless_http=True, json_response=True)", flush=True)
    print(
        f"[*] Nexus MCP: /{PATH_SECRET[:6]}...{PATH_SECRET[-4:]}/mcp | "
        f"Praxis MCP (LAN-only): /praxis/{praxis_tok[:6]}...{praxis_tok[-4:]}/mcp (+ /polyglot/ compat) | "
        f"Web Overwatch: /{PATH_SECRET[:6]}...{PATH_SECRET[-4:]}/web",
        flush=True,
    )
    app = build_nexus_http_app(PATH_SECRET, polyglot_token=poly_tok, praxis_token=praxis_tok)
    uvicorn.run(app, host=BIND_HOST, port=BIND_PORT, log_level="info", access_log=False, timeout_keep_alive=65)


if __name__ == "__main__":
    main()
