#!/usr/bin/env python3
"""
agy_nexus.code_health — Package Version Tracking, <=500L Modular Hygiene & Polyglot Health.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import threading
import time
from typing import Any
import urllib.request

from . import __version__
from .config import AGY_BG_DIR
from .hygiene import HARD_MAX_FILE_LINES, TARGET_FILE_LINES
from .polyglot_index import refresh_polyglot_index
from .polyglot_outline import build_polyglot_outline

GITHUB_REPO = "github.com/FrankXLT/agy-nexus-mcp"
_REFRESH_LOCK = threading.Lock()
_REFRESH_IN_PROGRESS = False

_CACHE_SUMMARY: dict[str, Any] | None = None
_CACHE_SUMMARY_TIME: float = 0.0
_CACHE_TTL: float = 30.0


def _parse_semver(ver: str | None) -> tuple[int, ...]:
    """Parse semantic version string into integer tuple (e.g. 'v2.6.1' -> (2, 6, 1))."""
    if not ver:
        return ()
    cleaned = str(ver).strip().lstrip("vV")
    return tuple(int(seg) for seg in re.split(r"[^\d]+", cleaned) if seg.isdigit())


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
                    valid = [(_parse_semver(raw := (t.get("name", "") if isinstance(t, dict) else str(t))), raw) for t in data]
                    valid = [v for v in valid if v[0]]
                    if valid:
                        valid.sort(key=lambda x: x[0], reverse=True)
                        return valid[0][1]
        except Exception:
            continue
    return None


def _cache_payload(tag: str | None) -> dict[str, Any]:
    payload = {
        "repo": GITHUB_REPO, "remote_version": tag, "latest_tag": tag,
        "checked_at": time.time(), "status": "ok" if tag else "offline",
    }
    cache_path = AGY_BG_DIR / "github_release_cache.json"
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        pass
    return payload


def _background_refresh() -> None:
    global _REFRESH_IN_PROGRESS
    with _REFRESH_LOCK:
        if _REFRESH_IN_PROGRESS:
            return
        _REFRESH_IN_PROGRESS = True
    try:
        _cache_payload(_fetch_remote_version())
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
    """Scan agy_nexus modules for <=500L target, 501-650L warning, >650L ceiling, and >100L functions."""
    if pkg_dir is None:
        pkg_dir = Path(__file__).resolve().parent

    modules: list[dict[str, Any]] = []
    compliant = warning = violations = total_lines = total_symbols = total_long_funcs = 0
    syntax_errors: dict[str, str] = {}

    if pkg_dir.is_dir():
        for py_file in sorted(pkg_dir.glob("*.py")):
            try:
                text = py_file.read_text(encoding="utf-8", errors="replace")
                ol = build_polyglot_outline(py_file, full_text=text, max_chars=2400)
            except Exception:
                ol = {"total_lines": 0, "symbol_count": 0, "long_functions": [], "summary": ""}

            line_count = int(ol.get("total_lines", 0))
            sym_count = int(ol.get("symbol_count", 0))
            long_fns = ol.get("long_functions") or []
            if ol.get("syntax_error"):
                syntax_errors[py_file.name] = str(ol["syntax_error"])

            if line_count <= TARGET_FILE_LINES:
                status, compliant = "compliant", compliant + 1
            elif line_count <= HARD_MAX_FILE_LINES:
                status, warning = "warning", warning + 1
            else:
                status, violations = "violation", violations + 1

            total_lines += line_count
            total_symbols += sym_count
            total_long_funcs += len(long_fns)
            modules.append({
                "name": py_file.name,
                "lines": line_count,
                "symbols": sym_count,
                "long_functions": len(long_fns),
                "summary": ol.get("summary", ""),
                "status": status,
            })

    modules.sort(key=lambda m: m["lines"], reverse=True)
    return {
        "target_lines": TARGET_FILE_LINES,
        "ceiling_lines": HARD_MAX_FILE_LINES,
        "total_modules": len(modules),
        "compliant_500": compliant,
        "warning_501_650": warning,
        "violations_over_650": violations,
        "compliant_300": compliant,
        "warning_301_400": warning,
        "violations_over_400": violations,
        "ceiling_pass": violations == 0,
        "total_lines": total_lines,
        "total_symbols": total_symbols,
        "long_functions_over_100": total_long_funcs,
        "syntax_errors": syntax_errors,
        "modules": modules,
    }


def get_polyglot_health_summary(pkg_dir: Path | None = None) -> dict[str, Any]:
    """Summarize Polyglot incremental index health and Python syntax integrity."""
    if pkg_dir is None:
        pkg_dir = Path(__file__).resolve().parent
    repo_root = pkg_dir.parents[1] if len(pkg_dir.parents) >= 2 else pkg_dir
    ref = refresh_polyglot_index(repo_root, force=False)
    idx_doc = ref["index"]
    files_map = idx_doc.get("files", {})
    syntax_errs = {k: [v["syntax_error"]] for k, v in files_map.items() if v.get("syntax_error")}
    long_fn_cnt = sum(len(v.get("long_functions") or []) for v in files_map.values())
    return {
        "clean": len(syntax_errs) == 0,
        "indexed_files": idx_doc.get("file_count", len(files_map)),
        "scanned_files": len(list(pkg_dir.glob("*.py"))) if pkg_dir.is_dir() else 0,
        "total_symbols": idx_doc.get("total_symbols", 0),
        "long_functions_over_100": long_fn_cnt,
        "undefined_count": len(syntax_errs),
        "undefined_names": len(syntax_errs),
        "flagged_modules": len(syntax_errs),
        "details": syntax_errs,
        "index_file": ref["stats"].get("index_file", ""),
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

    mod_hyg = get_modular_hygiene_summary()
    poly_health = get_polyglot_health_summary()
    summary = {
        "version": version_comp,
        "modular_hygiene": mod_hyg,
        "polyglot_health": poly_health,
        "ast_integrity": poly_health,
        "local_lsp": get_local_lsp_summary(),
        "timestamp": now,
    }
    _CACHE_SUMMARY = summary
    _CACHE_SUMMARY_TIME = now
    return summary
