#!/usr/bin/env python3
"""
agy_nexus.workspace — Multi-File Reader, Path Sandboxing & Git Status/Diff Helpers.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any
import urllib.request

from agy_nexus.config import (
    AGY_BRAIN_DIR,
    AGY_CONFIG_DIR,
    AGY_DATA_DIR,
    AGY_GITLAB_DIR,
    AGY_HOST_BRIDGE_URL,
    SESSION_STATE,
)
from agy_nexus.hygiene import (
    MAX_FILE_CHARS,
    MAX_FILES_PER_CALL,
    MAX_TOTAL_FILE_CHARS,
    parse_inline_line_spec,
    slice_file_content,
)
from agy_nexus.inventory import resolve_customization_file
from agy_nexus.sessions import _load_projects_map

def _resolve_workspace_str(ws_input: str) -> str:
    """Resolve short repo names, case-insensitive project names, or URIs to a canonical workspace path."""
    raw = re.sub(r"^file://", "", (ws_input or "").strip()).rstrip("/")
    if not raw:
        raw = SESSION_STATE.get("selected_workspace") or str(AGY_GITLAB_DIR / "antigravity-config")

    # 1. If it's an existing directory on disk (and not the bare AGY_GITLAB_DIR parent when a repo is needed)
    p = Path(raw)
    if p.is_absolute() and p.is_dir():
        return str(p.resolve())

    # 2. Check case-insensitive match under AGY_GITLAB_DIR
    target_name = p.name if p.is_absolute() else raw.strip("/")
    if AGY_GITLAB_DIR.is_dir() and target_name:
        exact_gitlab = AGY_GITLAB_DIR / target_name
        if exact_gitlab.is_dir():
            return str(exact_gitlab.resolve())
        for entry in AGY_GITLAB_DIR.iterdir():
            if entry.is_dir() and entry.name.lower() == target_name.lower():
                return str(entry.resolve())

    # 3. Check project map by project name or project_id
    projects_map = _load_projects_map()
    q_lower = target_name.lower()
    for pid, pinfo in projects_map.items():
        pname = str(pinfo.get("name") or "").lower()
        p_paths = pinfo.get("workspace_paths") or []
        if q_lower and (q_lower == pid.lower() or q_lower == pname or q_lower in pname):
            if p_paths:
                return str(p_paths[0])

    # 4. Check worktrees under AGY_DATA_DIR / "worktrees"
    wt_root = AGY_DATA_DIR / "worktrees"
    if wt_root.is_dir() and target_name:
        for proj_wt in wt_root.iterdir():
            if proj_wt.is_dir() and proj_wt.name.lower() == q_lower:
                sub_wts = sorted([d for d in proj_wt.iterdir() if d.is_dir()], key=lambda x: x.stat().st_mtime, reverse=True)
                if sub_wts:
                    return str(sub_wts[0].resolve())

    return raw

def _resolve_and_read_files(
    file_subpath_csv: str,
    ws: Path,
    session_dir: Path | None = None,
    max_chars_per_file: int = MAX_FILE_CHARS,
    max_total_chars: int = MAX_TOTAL_FILE_CHARS,
    start_line: int = 0,
    end_line: int = 0,
) -> dict[str, Any]:
    """Read one or more comma/semicolon-separated file subpaths across workspace, worktrees, brain session directory, or GitLab root, supporting line ranges and centered target lines."""
    raw_items = [p.strip() for p in re.split(r"[,;\n]+", file_subpath_csv or "") if p.strip()]
    if not raw_items:
        return {}

    search_roots: list[Path] = []
    if ws.is_dir():
        search_roots.append(ws.resolve())
    elif (AGY_DATA_DIR / "worktrees" / ws.name).is_dir():
        proj_wt = AGY_DATA_DIR / "worktrees" / ws.name
        sub_wts = sorted([d for d in proj_wt.iterdir() if d.is_dir()], key=lambda x: x.stat().st_mtime, reverse=True)
        if sub_wts:
            search_roots.append(sub_wts[0].resolve())

    for extra_uri in SESSION_STATE.get("selected_workspace_uris", []):
        clean_u = re.sub(r"^file://", "", str(extra_uri)).rstrip("/")
        if clean_u:
            ep = Path(clean_u)
            if ep.is_dir() and ep.resolve() not in search_roots:
                search_roots.append(ep.resolve())

    if not search_roots:
        search_roots.append(AGY_GITLAB_DIR.resolve())

    allowed = tuple(
        set(search_roots)
        | {
            AGY_GITLAB_DIR.resolve(),
            AGY_DATA_DIR.resolve(),
            AGY_BRAIN_DIR.resolve(),
            (AGY_DATA_DIR / "worktrees").resolve(),
            AGY_CONFIG_DIR.resolve(),
            (AGY_DATA_DIR / "builtin").resolve(),
        }
    )
    items_slice = raw_items[:MAX_FILES_PER_CALL]
    remaining_total_chars = max_total_chars
    files_list: list[dict[str, Any]] = []

    for raw_sub in items_slice:
        per_file_cap = min(max_chars_per_file, max(4000, remaining_total_chars))
        cleaned = re.sub(r"^file://", "", raw_sub.strip())
        # Strip leading "[repo_name] " prefix if copied from code_search_matches
        cleaned = re.sub(r"^\[[^\]]+\]\s*", "", cleaned)
        cleaned_no_line, in_start, in_end, in_center = parse_inline_line_spec(cleaned)

        candidates: list[Path] = []
        cust_match = resolve_customization_file(cleaned_no_line or cleaned, AGY_CONFIG_DIR, AGY_DATA_DIR, ws if ws.is_dir() else None)
        if cust_match:
            candidates.append(cust_match)
        for variant in (cleaned, cleaned_no_line):
            if not variant:
                continue
            if variant.startswith("/"):
                candidates.append(Path(os.path.normpath(variant)).resolve())
            norm_sub = os.path.normpath(variant).lstrip("/")
            for sroot in search_roots:
                candidates.append((sroot / norm_sub).resolve())
                if norm_sub.startswith("packages/"):
                    candidates.append((sroot / norm_sub[len("packages/"):]).resolve())
                else:
                    candidates.append((sroot / "packages" / norm_sub).resolve())
                if norm_sub.startswith(f"{sroot.name}/"):
                    candidates.append((sroot / norm_sub[len(sroot.name) + 1:]).resolve())
            if session_dir and session_dir.is_dir():
                candidates.append((session_dir / norm_sub).resolve())
                candidates.append((session_dir / "scratch" / Path(norm_sub).name).resolve())
                candidates.append((session_dir / Path(norm_sub).name).resolve())
            candidates.append((AGY_GITLAB_DIR / norm_sub).resolve())
            candidates.append((AGY_CONFIG_DIR / norm_sub).resolve())

        target_path = candidates[0] if candidates else (ws / raw_sub).resolve()
        for cand in candidates:
            try:
                if cand.is_file():
                    target_path = cand
                    break
            except Exception:
                continue

        is_sensitive_cfg = target_path.name.startswith(("config.json", "mcp_config.json", "secrets.env"))
        is_safe = (not is_sensitive_cfg) and any(target_path.is_relative_to(a) for a in allowed)
        if not is_safe:
            files_list.append({"requested": raw_sub, "error": "Access denied: path outside authorized workspace boundaries."})
        elif target_path.is_file():
            try:
                full_text = target_path.read_text(encoding="utf-8", errors="replace")
                slice_meta = slice_file_content(
                    full_text=full_text,
                    clean_path=cleaned_no_line or target_path.name,
                    per_file_cap=per_file_cap,
                    explicit_start_line=start_line,
                    explicit_end_line=end_line,
                    inline_start_line=in_start,
                    inline_end_line=in_end,
                    center_line=in_center,
                )
                remaining_total_chars = max(4000, remaining_total_chars - len(slice_meta.get("content", "")))
                entry_obj: dict[str, Any] = {
                    "requested": raw_sub,
                    "path": str(target_path),
                    "bytes": target_path.stat().st_size,
                    **slice_meta,
                }
                files_list.append(entry_obj)
            except Exception as e:
                files_list.append({"requested": raw_sub, "error": f"Error reading file: {e}"})
        else:
            nearby: list[str] = []
            try:
                base_root = search_roots[0]
                probe = (base_root / os.path.normpath(cleaned_no_line).lstrip("/")).resolve()
                cur_dir = probe.parent
                while cur_dir != base_root and not cur_dir.is_dir() and cur_dir.is_relative_to(base_root):
                    cur_dir = cur_dir.parent
                if cur_dir.is_dir() and cur_dir.is_relative_to(base_root):
                    for p_item in sorted(cur_dir.rglob("*")):
                        if p_item.is_file() and ".git" not in p_item.parts and "node_modules" not in p_item.parts:
                            nearby.append(str(p_item.relative_to(base_root)))
                            if len(nearby) >= 15:
                                break
            except Exception:
                pass
            err_entry: dict[str, Any] = {"requested": raw_sub, "error": f"File not found: {raw_sub}"}
            if nearby:
                err_entry["existing_files_in_parent"] = nearby
            files_list.append(err_entry)

    if len(files_list) == 1:
        return files_list[0]
    return {"count": len(files_list), "files": files_list}

def _host_git_inspect(
    ws_path: str,
    target_branch: str = "HEAD",
    include_untracked: bool = True,
    summary_only: bool = False,
    file_path: str = "",
) -> dict[str, Any]:
    """Fallback to agy-incident-bridge host git-inspect when a workspace or worktree parent .git lives on the host."""
    try:
        req = urllib.request.Request(
            AGY_HOST_BRIDGE_URL,
            data=json.dumps({
                "action": "git-inspect",
                "workspace_path": ws_path,
                "target_branch": target_branch,
                "include_untracked": include_untracked,
                "summary_only": summary_only,
                "file_path": file_path,
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
            if isinstance(data, dict) and data.get("ok"):
                return data
    except Exception:
        pass
    return {}

def _collect_git_summary(ws: Path | str) -> dict[str, Any]:
    """Return branch, short status, diff stat, and untracked files list for a workspace (with host-bridge fallback)."""
    ws_str = str(ws)
    ws_path = Path(ws_str)
    if ws_path.is_dir() and ws_path.resolve() != AGY_GITLAB_DIR.resolve():
        try:
            branch_proc = subprocess.run(
                ["git", "-c", "safe.directory=*", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(ws_path), capture_output=True, text=True, timeout=4, check=False,
            )
            if branch_proc.returncode == 0:
                status_proc = subprocess.run(
                    ["git", "-c", "safe.directory=*", "status", "--short"],
                    cwd=str(ws_path), capture_output=True, text=True, timeout=4, check=False,
                )
                stat_proc = subprocess.run(
                    ["git", "-c", "safe.directory=*", "diff", "--stat", "HEAD", "--"],
                    cwd=str(ws_path), capture_output=True, text=True, timeout=4, check=False,
                )
                untracked_proc = subprocess.run(
                    ["git", "-c", "safe.directory=*", "ls-files", "--others", "--exclude-standard"],
                    cwd=str(ws_path), capture_output=True, text=True, timeout=4, check=False,
                )
                untracked = [l.strip() for l in untracked_proc.stdout.splitlines() if l.strip()][:80]
                return {
                    "current_branch": branch_proc.stdout.strip(),
                    "status_short": status_proc.stdout.strip(),
                    "diff_stat": stat_proc.stdout.strip(),
                    "untracked_files": untracked,
                }
        except Exception:
            pass

    if ws_str and Path(ws_str) != AGY_GITLAB_DIR:
        host_res = _host_git_inspect(ws_str, target_branch="HEAD", include_untracked=True, summary_only=True)
        if host_res:
            return {
                "current_branch": host_res.get("current_branch", ""),
                "status_short": host_res.get("status_short", ""),
                "diff_stat": host_res.get("diff_stat", ""),
                "untracked_files": host_res.get("untracked_files", [])[:80],
            }
    return {}
