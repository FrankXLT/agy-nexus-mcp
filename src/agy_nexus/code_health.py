#!/usr/bin/env python3
"""
agy_nexus.code_health — Package Version Tracking, Modular Hygiene & AST/LSP Verification.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import threading
import time
from typing import Any
import urllib.error
import urllib.request

from . import __version__
from .ast_outline import scan_package_undefined_names
from .config import AGY_BG_DIR

GITHUB_REPO = "github.com/FrankXLT/agy-nexus-mcp"
_REFRESH_LOCK = threading.Lock()
_REFRESH_IN_PROGRESS = False

_CACHE_SUMMARY: dict[str, Any] | None = None
_CACHE_SUMMARY_TIME: float = 0.0
_CACHE_TTL: float = 30.0


def _parse_semver(ver: str | None) -> tuple[int, ...]:
    """Parse semantic version string into integer tuple (e.g. 'v2.6.0' -> (2, 6, 0))."""
    if not ver:
        return ()
    cleaned = str(ver).strip().lstrip("vV")
    parts: list[int] = []
    for segment in re.split(r"[^\d]+", cleaned):
        if segment.isdigit():
            parts.append(int(segment))
    return tuple(parts)


def compare_versions(installed: str, remote: str | None) -> dict[str, Any]:
    """Compare installed version with remote release tag."""
    inst_tag = f"v{str(installed).strip().lstrip('vV')}"
    if not remote or str(remote).strip().lower() == "unknown":
        return {
            "installed": installed, "remote": "unknown", "status": "offline",
            "status_label": f"Offline ({inst_tag})", "status_dot": "#94a3b8",
        }

    rem_str = str(remote).strip()
    rem_tag = f"v{rem_str.lstrip('vV')}"
    i_tup, r_tup = _parse_semver(installed), _parse_semver(rem_str)
    if not r_tup:
        status, label, dot = "offline", f"Offline ({inst_tag})", "#94a3b8"
    elif i_tup == r_tup:
        status, label, dot = "up_to_date", f"Up to Date ({inst_tag})", "#10b981"
    elif i_tup < r_tup:
        status, label, dot = "update_available", f"Update Available ({inst_tag} -> {rem_tag})", "#f59e0b"
    else:
        status, label, dot = "staged_locally", f"Staged Locally ({inst_tag} > {rem_tag})", "#38bdf8"

    return {
        "installed": installed, "remote": rem_str, "status": status,
        "status_label": label, "status_dot": dot,
    }


def _fetch_remote_version() -> str | None:
    """Fetch latest release or tag from GitHub with 2.0s timeout."""
    headers = {"User-Agent": "agy-nexus-mcp", "Accept": "application/vnd.github.v3+json"}
    repo = GITHUB_REPO.replace("github.com/", "")
    endpoints = [
        (f"https://api.github.com/repos/{repo}/releases/latest", False),
        (f"https://api.github.com/repos/{repo}/tags", True),
    ]
    for url, is_tags in endpoints:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if not is_tags and isinstance(data, dict):
                    tag = data.get("tag_name") or data.get("name")
                    if tag:
                        return str(tag).strip()
                elif is_tags and isinstance(data, list):
                    valid: list[tuple[tuple[int, ...], str]] = []
                    for t in data:
                        raw = t.get("name", "") if isinstance(t, dict) else str(t)
                        tup = _parse_semver(raw)
                        if tup:
                            valid.append((tup, raw))
                    if valid:
                        valid.sort(key=lambda x: x[0], reverse=True)
                        return valid[0][1]
        except Exception:
            continue
    return None


def _write_release_cache(data: dict[str, Any]) -> None:
    cache_path = AGY_BG_DIR / "github_release_cache.json"
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def _cache_payload(tag: str | None) -> dict[str, Any]:
    payload = {
        "repo": GITHUB_REPO, "remote_version": tag, "latest_tag": tag,
        "checked_at": time.time(), "status": "ok" if tag else "offline",
    }
    _write_release_cache(payload)
    return payload


def _background_refresh() -> None:
    global _REFRESH_IN_PROGRESS
    with _REFRESH_LOCK:
        if _REFRESH_IN_PROGRESS:
            return
        _REFRESH_IN_PROGRESS = True
    try:
        tag = _fetch_remote_version()
        _cache_payload(tag)
    finally:
        with _REFRESH_LOCK:
            _REFRESH_IN_PROGRESS = False


def get_github_version_info(force_refresh: bool = False) -> dict[str, Any]:
    """Retrieve latest GitHub release/tag info with 1h file caching and non-blocking refresh."""
    cache_path = AGY_BG_DIR / "github_release_cache.json"
    if cache_path.is_file():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            age = time.time() - cached.get("checked_at", 0)
            if age < 3600 and not force_refresh:
                return cached
            threading.Thread(target=_background_refresh, daemon=True).start()
            return cached
        except Exception:
            pass

    return _cache_payload(_fetch_remote_version())


def get_modular_hygiene_summary(pkg_dir: Path | None = None) -> dict[str, Any]:
    """Scan agy_nexus modules for line count limits (<=300 compliant, 301-400 warning, >400 ceiling)."""
    if pkg_dir is None:
        pkg_dir = Path(__file__).resolve().parent

    modules: list[dict[str, Any]] = []
    compliant_300 = warning_301_400 = violations_over_400 = total_lines = 0

    if pkg_dir.is_dir():
        for py_file in pkg_dir.glob("*.py"):
            try:
                line_count = len(py_file.read_text(encoding="utf-8", errors="replace").splitlines())
            except Exception:
                line_count = 0

            if line_count <= 300:
                status, compliant_300 = "compliant", compliant_300 + 1
            elif line_count <= 400:
                status, warning_301_400 = "warning", warning_301_400 + 1
            else:
                status, violations_over_400 = "violation", violations_over_400 + 1

            total_lines += line_count
            modules.append({"name": py_file.name, "lines": line_count, "status": status})

    modules.sort(key=lambda m: m["lines"], reverse=True)
    return {
        "total_modules": len(modules),
        "compliant_300": compliant_300,
        "warning_301_400": warning_301_400,
        "violations_over_400": violations_over_400,
        "ceiling_pass": violations_over_400 == 0,
        "total_lines": total_lines,
        "modules": modules,
    }


def get_ast_integrity_summary(pkg_dir: Path | None = None) -> dict[str, Any]:
    """Run AST scope verifier across package modules to detect undefined names."""
    if pkg_dir is None:
        pkg_dir = Path(__file__).resolve().parent

    undefined_map = scan_package_undefined_names(pkg_dir)
    undef_cnt = sum(len(items) for items in undefined_map.values())
    return {
        "clean": len(undefined_map) == 0,
        "undefined_count": undef_cnt,
        "undefined_names": undef_cnt,
        "flagged_modules": len(undefined_map),
        "details": undefined_map,
    }


def get_local_lsp_summary() -> dict[str, Any]:
    """Check availability of Serena local LSP binary and configuration."""
    serena_bin = shutil.which("serena")
    config_path = Path.home() / ".serena" / "serena_config.yml"
    config_exists = config_path.is_file()
    available = bool(serena_bin and config_exists)
    return {
        "engine": "serena",
        "available": available,
        "binary_path": serena_bin,
        "config_path": str(config_path) if config_exists else None,
        "config_exists": config_exists,
        "status": "ready" if available else ("missing_config" if serena_bin else "not_installed"),
    }


def get_code_health_summary(force_refresh: bool = False) -> dict[str, Any]:
    """Aggregate package health status with 30s in-memory caching."""
    global _CACHE_SUMMARY, _CACHE_SUMMARY_TIME
    now = time.time()
    if not force_refresh and _CACHE_SUMMARY is not None and (now - _CACHE_SUMMARY_TIME) < _CACHE_TTL:
        return _CACHE_SUMMARY

    gh_info = get_github_version_info(force_refresh=force_refresh)
    remote_ver = gh_info.get("remote_version") or gh_info.get("latest_tag")
    version_comp = compare_versions(__version__, remote_ver)
    version_comp["repo"] = gh_info.get("repo", GITHUB_REPO)
    version_comp["checked_at"] = gh_info.get("checked_at", now)

    summary = {
        "version": version_comp,
        "modular_hygiene": get_modular_hygiene_summary(),
        "ast_integrity": get_ast_integrity_summary(),
        "local_lsp": get_local_lsp_summary(),
        "timestamp": now,
    }
    _CACHE_SUMMARY = summary
    _CACHE_SUMMARY_TIME = now
    return summary
