#!/usr/bin/env python3
"""agy_nexus.polyglot_index — Incremental SHA-256 Workspace Semantic Index & Symbol Search.

Maintains a fast per-workspace JSON hash index in AGY_DATA_DIR/sidecar_data/polyglot_index/
using (mtime_ns, size) fast-stat checks + SHA-256 content hashes so unchanged files require
zero re-parsing while modified/added/deleted files update incrementally in milliseconds.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
from typing import Any

from agy_nexus.config import (
    AGY_CONFIG_DIR,
    AGY_DATA_DIR,
    AGY_GITLAB_DIR,
    AGY_PROJECTS_DIR,
    AGY_WORKSPACE_DIR,
    SESSION_STATE,
    get_antigravity_config_repo,
    get_umbrella_roots,
    get_workspace_pillar_roots,
)
from agy_nexus.hygiene import is_sensitive_filename
from agy_nexus.polyglot_outline import EXT_LANG, build_polyglot_outline

INDEX_SCHEMA_VERSION = 1
MAX_INDEX_FILE_BYTES = 524_288
MAX_INDEXED_FILES = 2_500
MEM_DEBOUNCE_SECONDS = 4.0

SKIP_DIRS: frozenset[str] = frozenset({
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "env", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist", "build", "out", ".next",
    ".nuxt", "coverage", ".tox", "backups", "scratch", "archive", ".cache", "vendor",
    ".idea", ".vscode", ".system_generated", "sidecar_data",
})

_INDEX_LOCK = threading.Lock()
_MEM_INDEX_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def get_polyglot_index_dir() -> Path:
    idx_dir = AGY_DATA_DIR / "sidecar_data" / "polyglot_index"
    idx_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(idx_dir, 0o700)
    except OSError:
        pass
    return idx_dir


def _allowed_workspace_roots() -> list[Path]:
    pkg_repo = Path(__file__).resolve().parents[2]
    roots = [
        AGY_WORKSPACE_DIR.resolve(),
        *get_workspace_pillar_roots(),
        (AGY_DATA_DIR / "worktrees").resolve(),
        AGY_CONFIG_DIR.resolve(),
        pkg_repo,
    ]
    home_res = Path.home().resolve()
    root_fs = Path("/").resolve()
    seen: set[Path] = set()
    result: list[Path] = []
    for r in roots:
        if r not in (home_res, root_fs) and r not in seen:
            seen.add(r)
            result.append(r)
    return result


def _is_safe_workspace(cand: Path) -> bool:
    try:
        res = cand.resolve()
    except Exception:
        return False
    if not res.is_dir():
        return False
    if res in get_umbrella_roots():
        return False
    return any(res == r or res.is_relative_to(r) for r in _allowed_workspace_roots())


def resolve_polyglot_workspace(workspace: str = "") -> Path:
    """Resolve an explicit path, repo short-name, or active session workspace safely."""
    raw = re.sub(r"^file://", "", (workspace or "").strip()).rstrip("/")
    candidates: list[Path] = []
    if raw:
        p = Path(raw).expanduser()
        if p.is_absolute():
            candidates.append(p)
        else:
            clean_slug = raw.strip("/")
            for pillar in get_workspace_pillar_roots():
                candidates.append(pillar / clean_slug)
            candidates.append(AGY_DATA_DIR / "worktrees" / clean_slug)
            wt_root = AGY_DATA_DIR / "worktrees"
            if wt_root.is_dir() and "/" not in clean_slug:
                for repo_dir in sorted(wt_root.iterdir()):
                    if repo_dir.is_dir() and repo_dir.name == clean_slug:
                        subs = [d for d in sorted(repo_dir.iterdir()) if d.is_dir()]
                        if subs:
                            candidates.append(subs[-1])
    sel_ws = str(SESSION_STATE.get("selected_workspace") or "").strip()
    if sel_ws:
        candidates.append(Path(sel_ws))
    candidates.extend([
        Path(__file__).resolve().parents[2],
        AGY_PROJECTS_DIR / "agy-nexus-mcp",
        AGY_GITLAB_DIR / "agy-nexus-mcp",
        get_antigravity_config_repo(),
        AGY_CONFIG_DIR,
    ])
    for cand in candidates:
        if _is_safe_workspace(cand):
            return cand.resolve()
    return Path(__file__).resolve().parents[2]


def _index_file_for_workspace(ws_root: Path) -> Path:
    res_str = str(ws_root.resolve())
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "_", ws_root.name)[:48] or "workspace"
    h8 = hashlib.sha256(res_str.encode("utf-8")).hexdigest()[:8]
    return get_polyglot_index_dir() / f"{slug}__{h8}.json"


def _iter_source_files(ws_root: Path) -> list[tuple[str, Path, os.stat_result]]:
    found: list[tuple[str, Path, os.stat_result]] = []
    root_str = str(ws_root)
    for dirpath, dirnames, filenames in os.walk(root_str, topdown=True, followlinks=False):
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in SKIP_DIRS and not (d.startswith(".") and d not in (".github", ".agents"))
        )
        for fname in sorted(filenames):
            if is_sensitive_filename(fname):
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext not in EXT_LANG or fname.endswith((".min.js", ".min.css", ".lock")):
                continue
            fpath = Path(dirpath) / fname
            try:
                if fpath.is_symlink():
                    continue
                st = fpath.stat()
            except OSError:
                continue
            if st.st_size <= 0 or st.st_size > MAX_INDEX_FILE_BYTES:
                continue
            rel = str(fpath.relative_to(ws_root)).replace("\\", "/")
            found.append((rel, fpath, st))
            if len(found) >= MAX_INDEXED_FILES:
                return found
    return found


def refresh_polyglot_index(ws_root: Path, force: bool = False, rebuild_all: bool = False) -> dict[str, Any]:
    """Incrementally update the SHA-256 Polyglot index for ws_root and return index + stats."""
    ws_res = ws_root.resolve()
    ws_key = str(ws_res)
    now = time.time()
    if not force and not rebuild_all:
        cached = _MEM_INDEX_CACHE.get(ws_key)
        if cached and (now - cached[0]) < MEM_DEBOUNCE_SECONDS:
            data = cached[1]
            return {
                "index": data,
                "stats": {
                    "workspace": ws_key, "index_file": str(_index_file_for_workspace(ws_res)),
                    "total_files": len(data.get("files", {})), "reindexed": 0,
                    "reused": len(data.get("files", {})), "pruned": 0, "elapsed_ms": 0, "from_memory": True,
                },
            }

    t0 = time.perf_counter()
    idx_path = _index_file_for_workspace(ws_res)
    prev_files: dict[str, dict[str, Any]] = {}
    if not rebuild_all and idx_path.is_file():
        try:
            loaded = json.loads(idx_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and loaded.get("schema_version") == INDEX_SCHEMA_VERSION:
                prev_files = loaded.get("files") or {}
        except Exception:
            prev_files = {}

    new_files: dict[str, dict[str, Any]] = {}
    reindexed = reused = 0
    for rel, fpath, st in _iter_source_files(ws_res):
        prev = prev_files.get(rel)
        if (
            not rebuild_all
            and isinstance(prev, dict)
            and prev.get("mtime_ns") == st.st_mtime_ns
            and prev.get("size") == st.st_size
        ):
            new_files[rel] = prev
            reused += 1
            continue

        try:
            raw_bytes = fpath.read_bytes()
        except OSError:
            continue
        sha = hashlib.sha256(raw_bytes).hexdigest()
        if not rebuild_all and isinstance(prev, dict) and prev.get("sha256") == sha:
            updated_prev = {**prev, "mtime_ns": st.st_mtime_ns, "size": st.st_size}
            new_files[rel] = updated_prev
            reused += 1
            continue

        text = raw_bytes.decode("utf-8", errors="replace")
        ol = build_polyglot_outline(fpath, full_text=text, max_chars=4800, include_callers=False)
        new_files[rel] = {
            "sha256": sha,
            "mtime_ns": st.st_mtime_ns,
            "size": st.st_size,
            "lang": ol["language"],
            "lines": ol["total_lines"],
            "summary": ol.get("summary", ""),
            "symbol_count": ol["symbol_count"],
            "long_functions": ol.get("long_functions", []),
            "syntax_error": ol.get("syntax_error"),
            "symbols": ol.get("symbol_items", []),
        }
        reindexed += 1

    pruned = max(0, len(set(prev_files) - set(new_files)))
    index_doc: dict[str, Any] = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "workspace": ws_key,
        "workspace_name": ws_res.name,
        "updated_at": now,
        "file_count": len(new_files),
        "total_symbols": sum(int(v.get("symbol_count", 0)) for v in new_files.values()),
        "files": new_files,
    }

    if reindexed > 0 or pruned > 0 or not idx_path.is_file():
        with _INDEX_LOCK:
            tmp_path = idx_path.with_suffix(".json.tmp")
            try:
                fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(json.dumps(index_doc, separators=(",", ":")))
                os.replace(tmp_path, idx_path)
            except OSError:
                tmp_path.unlink(missing_ok=True)

    _MEM_INDEX_CACHE[ws_key] = (time.time(), index_doc)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    return {
        "index": index_doc,
        "stats": {
            "workspace": ws_key, "index_file": str(idx_path),
            "total_files": len(new_files), "reindexed": reindexed,
            "reused": reused, "pruned": pruned, "elapsed_ms": elapsed_ms, "from_memory": False,
        },
    }


def polyglot_repo_map(
    workspace: str = "",
    path_prefix: str = "",
    limit: int = 120,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Return an up-to-date semantic repository map backed by the incremental SHA-256 index."""
    ws_root = resolve_polyglot_workspace(workspace)
    ref = refresh_polyglot_index(ws_root, force=force_refresh)
    files_map: dict[str, dict[str, Any]] = ref["index"].get("files", {})
    pfx = path_prefix.strip().lstrip("./")
    matched_keys = [k for k in sorted(files_map) if not pfx or k.startswith(pfx)]
    cap = max(1, min(int(limit or 120), 300))

    entries: list[dict[str, Any]] = []
    md_lines = [f"# Polyglot Map: {ws_root.name} ({len(matched_keys)} files matched)"]
    for rel in matched_keys[:cap]:
        info = files_map[rel]
        syms = info.get("symbols") or []
        top_syms = [
            f"L{s['start_line']}-L{s['end_line']} {s['name']}"
            for s in syms[:6]
            if isinstance(s, dict) and s.get("name")
        ]
        entries.append({
            "path": rel,
            "lang": info.get("lang", ""),
            "lines": info.get("lines", 0),
            "symbol_count": info.get("symbol_count", 0),
            "summary": info.get("summary", ""),
            "top_symbols": top_syms,
        })
        summ = f" — {info['summary']}" if info.get("summary") else ""
        md_lines.append(f"- `{rel}` ({info.get('lang')}, {info.get('lines')}L, {info.get('symbol_count')} syms){summ}")
        if top_syms:
            md_lines.append(f"  [{', '.join(top_syms)}]")

    return {
        "ok": True,
        "workspace": str(ws_root),
        "path_prefix": pfx,
        "matched_files": len(matched_keys),
        "shown_files": len(entries),
        "index_stats": ref["stats"],
        "files": entries,
        "formatted_map": "\n".join(md_lines),
    }


def polyglot_symbol_search(
    query: str,
    workspace: str = "",
    kind: str = "",
    limit: int = 25,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Search symbols, signatures, and 1-liner semantic docstrings across the workspace index."""
    ws_root = resolve_polyglot_workspace(workspace)
    ref = refresh_polyglot_index(ws_root, force=force_refresh)
    q_raw = (query or "").strip()
    q_low = q_raw.lower()
    tokens = [t for t in re.findall(r"[a-z0-9_]{2,}", q_low)][:8]
    kind_low = (kind or "").strip().lower()
    cap = max(1, min(int(limit or 25), 100))

    scored: list[tuple[int, dict[str, Any]]] = []
    for rel, info in ref["index"].get("files", {}).items():
        rel_low = rel.lower()
        file_sum_low = str(info.get("summary") or "").lower()
        for sym in info.get("symbols") or []:
            s_kind = str(sym.get("kind") or "").lower()
            if kind_low and kind_low not in s_kind:
                continue
            name = str(sym.get("name") or "")
            name_low = name.lower()
            sig_low = str(sym.get("signature") or "").lower()
            sum_low = str(sym.get("summary") or "").lower()
            hay = f"{name_low} {sig_low} {sum_low} {rel_low} {file_sum_low}"

            score = 0
            if q_raw and name == q_raw:
                score = 100
            elif q_low and (name_low == q_low or name_low.endswith(f".{q_low}")):
                score = 95
            elif q_low and name_low.startswith(q_low):
                score = 82
            elif q_low and q_low in name_low:
                score = 70
            elif q_low and q_low in hay:
                score = 55
            elif tokens:
                hits = sum(1 for t in tokens if t in hay)
                if hits == len(tokens):
                    score = 50
                elif hits >= max(1, len(tokens) - 1) and len(tokens) >= 2:
                    score = 35
            if score > 0:
                st, en = int(sym.get("start_line", 1)), int(sym.get("end_line", 1))
                scored.append((score, {
                    "score": score,
                    "file": rel,
                    "lang": info.get("lang", ""),
                    "name": name,
                    "kind": sym.get("kind", ""),
                    "start_line": st,
                    "end_line": en,
                    "lines": sym.get("lines", en - st + 1),
                    "signature": sym.get("signature", ""),
                    "summary": sym.get("summary", ""),
                    "slice_hint": f"{rel}:{st}-{en}",
                }))

    scored.sort(key=lambda pair: (-pair[0], pair[1]["file"], pair[1]["start_line"]))
    matches = [item for _, item in scored[:cap]]
    return {
        "ok": True,
        "query": q_raw,
        "workspace": str(ws_root),
        "total_matches": len(scored),
        "matches": matches,
        "index_stats": ref["stats"],
    }


def polyglot_file_outline(
    file_subpath: str,
    workspace: str = "",
    include_callers: bool = False,
) -> dict[str, Any]:
    """Return a rich Polyglot semantic outline (with Lstart-Lend spans & 1-liners) for one file."""
    ws_root = resolve_polyglot_workspace(workspace).resolve()
    cleaned = re.sub(r"^(?:outline:|file://)", "", (file_subpath or "").strip()).strip()
    if not cleaned:
        return {"ok": False, "error": "file_subpath is required."}

    raw_p = Path(cleaned).expanduser()
    if not raw_p.is_absolute():
        cand = (ws_root / raw_p).resolve()
        if not cand.is_relative_to(ws_root):
            return {"ok": False, "error": "Access denied: relative path escapes workspace boundary.", "workspace": str(ws_root)}
    else:
        cand = raw_p.resolve()

    if is_sensitive_filename(cand.name):
        return {"ok": False, "error": "Access denied: sensitive configuration or credential file.", "workspace": str(ws_root)}

    allowed = _allowed_workspace_roots()
    if not cand.is_file() or not any(cand == r or cand.is_relative_to(r) for r in allowed):
        return {"ok": False, "error": f"File not found inside allowed workspaces: {cleaned}", "workspace": str(ws_root)}

    ol = build_polyglot_outline(cand, ws_root=ws_root, max_chars=6000, include_callers=include_callers)
    rel = str(cand.relative_to(ws_root)).replace("\\", "/") if cand.is_relative_to(ws_root) else str(cand)
    return {
        "ok": True,
        "workspace": str(ws_root),
        "path": rel,
        "abs_path": str(cand),
        **ol,
    }
