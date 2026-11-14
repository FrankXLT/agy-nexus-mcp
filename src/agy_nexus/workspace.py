#!/usr/bin/env python3
"""
agy_nexus.workspace — Multi-File Reader, Virtual URI & Brain Sandboxing, and Git Helpers.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any
import urllib.request

import agy_nexus.config as cfg
from agy_nexus.config import (
    AGY_BRAIN_DIR,
    AGY_CONFIG_DIR,
    AGY_DATA_DIR,
    AGY_GITLAB_DIR,
    AGY_PROJECTS_DIR,
    AGY_WORKSPACE_DIR,
    SESSION_STATE,
    _save_session_state,
    get_antigravity_config_repo,
    get_umbrella_roots,
    get_workspace_pillar_roots,
)
from agy_nexus.hygiene import (
    MAX_FILE_CHARS, MAX_FILES_PER_CALL, MAX_TOTAL_FILE_CHARS,
    is_sensitive_filename, parse_inline_line_spec, slice_file_content,
)
from agy_nexus.inventory import resolve_customization_file
from agy_nexus.polyglot_outline import build_file_outline
from agy_nexus.sessions import _load_projects_map
from agy_nexus.virtual_uris import resolve_brain_uri_path, resolve_virtual_uri_entry


def _default_nexus_repo_dir() -> Path:
    cand_proj = AGY_PROJECTS_DIR / "agy-nexus-mcp"
    if cand_proj.is_dir():
        return cand_proj
    standalone = AGY_GITLAB_DIR / "agy-nexus-mcp"
    return standalone if standalone.is_dir() else get_antigravity_config_repo()


def _pillar_root_map() -> dict[str, Path]:
    proj_base = cfg.AGY_PROJECTS_DIR if (cfg.AGY_PROJECTS_DIR.is_dir() or cfg.AGY_WORKSPACE_DIR.is_dir()) else cfg.AGY_GITLAB_DIR
    return {
        "projects": proj_base,
        "workbooks": cfg.AGY_WORKBOOKS_DIR,
        "configuration": cfg.AGY_CONFIGURATION_DIR,
    }


def _allowed_project_bases(pillars: dict[str, Path], home_roots: set[Path]) -> tuple[set[Path], set[Path]]:
    raw_bases = (
        *pillars.values(),
        *get_workspace_pillar_roots(),
        cfg.AGY_GITLAB_DIR,
        cfg.AGY_GITLAB_DIR.parent / "github",
        Path.home() / "github",
        cfg.AGY_DATA_DIR / "worktrees",
    )
    resolved_home = {h.resolve() for h in home_roots} | {Path("/")}
    umbrella_res = {u.resolve() for u in get_umbrella_roots()} | resolved_home
    bases_res = {Path(os.path.abspath(str(r))).resolve() for r in raw_bases} - resolved_home
    return bases_res, umbrella_res


def normalize_pillar_target_path(raw_input: str) -> tuple[str, str, bool]:
    """Normalize shorthand ('projects/foo', '~/projects/foo', bare 'foo', or canonical pillar paths) to (abs_path, slug, exists_on_disk). Rejects symlinks/paths outside allowed roots with ('', '', False)."""
    cleaned = re.sub(r"^file://", "", (raw_input or "").strip()).rstrip("/")
    if not cleaned or any(pt in (".", "..") for pt in cleaned.split("/")):
        return "", "", False
    home_abs = Path(os.path.abspath(str(Path.home())))
    exp_str = os.path.expanduser(cleaned)
    pillars = _pillar_root_map()
    ws_owner_home = Path(os.path.abspath(str(cfg.AGY_WORKSPACE_DIR.parent)))
    home_roots = {home_abs, ws_owner_home} - {Path("/")}
    allowed_bases, umbrella_res = _allowed_project_bases(pillars, home_roots)

    def _validated(cand_path: Path, slug_override: str = "") -> tuple[str, str, bool]:
        res_p = Path(os.path.abspath(str(cand_path))).resolve()
        if res_p in umbrella_res:
            return "", "", False
        if any(res_p != base and res_p.is_relative_to(base) for base in allowed_bases):
            return str(res_p), (slug_override or res_p.name).lower(), res_p.is_dir()
        return "", "", False

    if not Path(exp_str).is_absolute():
        parts = [pt for pt in cleaned.strip("/").split("/") if pt]
        if len(parts) == 2 and parts[0].lower() in pillars:
            return _validated(pillars[parts[0].lower()] / parts[1], parts[1])
        if len(parts) == 1:
            slug = parts[0]
            for host_dir in get_workspace_pillar_roots():
                if host_dir.is_dir():
                    for entry in host_dir.iterdir():
                        if entry.is_dir() and entry.name.lower() == slug.lower():
                            v_path, v_slug, v_ok = _validated(entry, entry.name)
                            if v_path:
                                return v_path, v_slug, v_ok
            return _validated(pillars["projects"] / slug, slug)
        return "", "", False

    abs_p = Path(os.path.abspath(exp_str))
    if abs_p.parent and Path(os.path.abspath(str(abs_p.parent.parent))) in home_roots and abs_p.parent.name.lower() in pillars:
        return _validated(pillars[abs_p.parent.name.lower()] / abs_p.name, abs_p.name)

    pkg_root = Path(__file__).resolve().parents[2].resolve()
    res_abs = abs_p.resolve()
    if res_abs == pkg_root or (pkg_root != Path("/") and res_abs.is_relative_to(pkg_root)):
        return str(res_abs), res_abs.name.lower(), res_abs.is_dir()
    return _validated(abs_p)


def _slugify_exact(val: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (val or "").strip().lower()).strip("-")


def _resolve_workspace_str(ws_input: str) -> str:
    """Resolve short repo names, exact project names, pillar shorthands, or URIs without fuzzy substring fallback to agy-nexus-mcp."""
    raw = re.sub(r"^file://", "", (ws_input or "").strip()).rstrip("/")
    if not raw:
        return SESSION_STATE.get("selected_workspace") or str(_default_nexus_repo_dir())
    norm_path, norm_slug, exists_disk = normalize_pillar_target_path(raw)
    if exists_disk and norm_path:
        return norm_path
    exp_abs = Path(os.path.abspath(os.path.expanduser(raw)))
    if exp_abs.is_dir() and exp_abs.resolve() == cfg.AGY_CONFIG_DIR.resolve():
        return str(exp_abs.resolve())
    if "/" in raw:
        return norm_path

    q_lower = (norm_slug or raw.strip("/")).lower()
    if q_lower == "ag-bridge-mcp":
        return str(_default_nexus_repo_dir().resolve())
    q_slug = _slugify_exact(q_lower)
    for pid, pinfo in _load_projects_map().items():
        pname = str(pinfo.get("name") or "").lower()
        p_paths = [str(x) for x in (pinfo.get("workspace_paths") or []) if x]
        if not q_lower or not p_paths:
            continue
        for pp in p_paths:
            if Path(pp).name.lower() == q_lower:
                cp = Path(pp)
                return str(cp.resolve()) if cp.is_dir() else pp
        if q_lower in (pid.lower(), pname) or (q_slug and _slugify_exact(pname) == q_slug):
            cp0 = Path(p_paths[0])
            return str(cp0.resolve()) if cp0.is_dir() else p_paths[0]

    wt_root = cfg.AGY_DATA_DIR / "worktrees"
    if wt_root.is_dir() and q_lower:
        for proj_wt in wt_root.iterdir():
            if proj_wt.is_dir() and proj_wt.name.lower() == q_lower:
                sub_wts = sorted([d for d in proj_wt.iterdir() if d.is_dir()], key=lambda x: x.stat().st_mtime, reverse=True)
                if sub_wts:
                    return str(sub_wts[0].resolve())
    return norm_path or raw


def _should_probe_customization(spec: str) -> bool:
    low = spec.lower()
    if low.startswith(("skill:", "agent:", "rule:", "global:", "workspace:")):
        return True
    return "/" not in spec and low.endswith(".md")


def _resolve_and_read_files(
    file_subpath_csv: str,
    ws: Path,
    session_dir: Path | None = None,
    max_chars_per_file: int = MAX_FILE_CHARS,
    max_total_chars: int = MAX_TOTAL_FILE_CHARS,
    start_line: int = 0,
    end_line: int = 0,
    extra_workspace_uris: list[str] | None = None,
) -> dict[str, Any]:
    """Read 1..12 comma/semicolon-separated file subpaths or virtual URIs (`transcript:*`, `brain:*`, `telemetry:*`, `polyglot:*`)."""
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
    uris_source = extra_workspace_uris if extra_workspace_uris is not None else SESSION_STATE.get("selected_workspace_uris", [])
    for extra_uri in uris_source:
        clean_u = re.sub(r"^file://", "", str(extra_uri)).rstrip("/")
        if clean_u:
            ep = Path(clean_u)
            if ep.is_dir() and ep.resolve() not in search_roots:
                search_roots.append(ep.resolve())
    if not search_roots:
        pillar_roots = get_workspace_pillar_roots()
        if pillar_roots:
            search_roots.append(pillar_roots[0])
        else:
            search_roots.append(AGY_GITLAB_DIR.resolve())

    allowed = tuple(
        (
            set(get_workspace_pillar_roots())
            | {
                AGY_BRAIN_DIR.resolve(),
                (AGY_DATA_DIR / "worktrees").resolve(),
                AGY_CONFIG_DIR.resolve(),
                (AGY_DATA_DIR / "builtin").resolve(),
                Path(__file__).resolve().parents[2],
            }
        )
        - {Path("/").resolve(), Path.home().resolve()}
    )
    items_slice = raw_items[:MAX_FILES_PER_CALL]
    remaining_total_chars = max_total_chars
    files_list: list[dict[str, Any]] = []
    top_auto_ws = ""

    for raw_sub in items_slice:
        per_file_cap = min(max_chars_per_file, max(4000, remaining_total_chars))
        cleaned = re.sub(r"^file://", "", raw_sub.strip())
        outline_only = False
        if cleaned.startswith("outline:"):
            outline_only = True
            cleaned = cleaned[8:].strip()
        m_repo_prefix = re.match(r"^\[([^\]]+)\]\s*(.*)", cleaned)
        repo_prefix = m_repo_prefix.group(1).strip() if m_repo_prefix else ""
        if m_repo_prefix:
            cleaned = m_repo_prefix.group(2).strip()
        if cleaned.startswith("outline:"):
            outline_only = True
            cleaned = cleaned[8:].strip()
        cleaned_no_line, in_start, in_end, in_center = parse_inline_line_spec(cleaned)

        virt_entry = resolve_virtual_uri_entry(
            cleaned, ws=search_roots[0], session_dir=session_dir, per_file_cap=per_file_cap,
            start_line=start_line, end_line=end_line, in_start=in_start, in_end=in_end, in_center=in_center,
        )
        if virt_entry is not None:
            virt_entry["requested"] = raw_sub
            remaining_total_chars = max(4000, remaining_total_chars - len(str(virt_entry.get("content", ""))))
            files_list.append(virt_entry)
            continue

        if (cleaned_no_line or cleaned).lower().startswith("brain:"):
            b_path, b_err = resolve_brain_uri_path(cleaned_no_line or cleaned, session_dir)
            if b_path is None or b_err:
                files_list.append({"requested": raw_sub, "error": b_err or f"File not found: {raw_sub}"})
                continue
            candidates = [b_path]
        else:
            candidates = []
            probe_spec = cleaned_no_line or cleaned
            if _should_probe_customization(probe_spec):
                cust_match = resolve_customization_file(probe_spec, AGY_CONFIG_DIR, AGY_DATA_DIR, ws if ws.is_dir() else None)
                if cust_match:
                    candidates.append(cust_match)
            for variant in (cleaned, cleaned_no_line):
                if not variant:
                    continue
                if variant.startswith("/"):
                    candidates.append(Path(os.path.normpath(variant)).resolve())
                norm_sub = os.path.normpath(variant).lstrip("/")
                is_session_artifact = norm_sub.startswith("scratch/") or norm_sub in (
                    "task.md", "implementation_plan.md", "walkthrough.md", "gemini_research_handoff.md"
                )
                if is_session_artifact and session_dir and session_dir.is_dir() and not repo_prefix:
                    candidates.append((session_dir / norm_sub).resolve())
                    if not norm_sub.startswith("scratch/"):
                        candidates.append((session_dir / "scratch" / norm_sub).resolve())
                if repo_prefix:
                    prefix_name = repo_prefix.split(" ")[0]
                    for host_dir in get_workspace_pillar_roots():
                        candidates.append((host_dir / prefix_name / norm_sub).resolve())
                    candidates.append((AGY_GITLAB_DIR / prefix_name / norm_sub).resolve())
                for sroot in search_roots:
                    candidates.append((sroot / norm_sub).resolve())
                    if norm_sub.startswith("packages/"):
                        candidates.append((sroot / norm_sub[len("packages/"):]).resolve())
                    else:
                        candidates.append((sroot / "packages" / norm_sub).resolve())
                    candidates.append((sroot / "sidecars/ag-bridge-mcp" / norm_sub).resolve())
                    if norm_sub.startswith("sidecars/ag-bridge-mcp/"):
                        candidates.append((sroot / norm_sub[len("sidecars/ag-bridge-mcp/"):]).resolve())
                    if norm_sub.startswith(f"{sroot.name}/"):
                        candidates.append((sroot / norm_sub[len(sroot.name) + 1:]).resolve())
                if session_dir and session_dir.is_dir():
                    candidates.append((session_dir / norm_sub).resolve())
                    candidates.append((session_dir / "scratch" / norm_sub).resolve())
                    candidates.append((session_dir / "scratch" / Path(norm_sub).name).resolve())
                    candidates.append((session_dir / Path(norm_sub).name).resolve())
                for host_dir in get_workspace_pillar_roots():
                    candidates.append((host_dir / norm_sub).resolve())
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

        auto_resolved_ws = ""
        if (
            not target_path.is_file()
            and cleaned_no_line
            and not cleaned_no_line.startswith(("/", "brain:"))
        ):
            norm_rel = os.path.normpath(cleaned_no_line).lstrip("/")
            if not norm_rel.startswith(".."):
                repo_hits: list[tuple[Path, Path]] = []
                for p_root in get_workspace_pillar_roots():
                    if p_root.is_dir():
                        for rdir in sorted(p_root.iterdir()):
                            if rdir.is_dir() and not rdir.name.startswith(".") and not rdir.is_symlink():
                                for probe_rel in (norm_rel, f"packages/{norm_rel}"):
                                    p_cand = (rdir / probe_rel).resolve()
                                    if p_cand.is_file():
                                        repo_hits.append((rdir.resolve(), p_cand))
                                        break
                if len(repo_hits) == 1:
                    auto_resolved_ws, target_path = str(repo_hits[0][0]), repo_hits[0][1]
                    SESSION_STATE["auto_resolved_calls"] = int(SESSION_STATE.get("auto_resolved_calls") or 0) + 1
                    _save_session_state()
        elif target_path.is_file():
            extracted_cand_repo: Path | None = None
            for p_root in get_workspace_pillar_roots():
                try:
                    if target_path.is_relative_to(p_root):
                        rel_parts = target_path.relative_to(p_root).parts
                        if rel_parts:
                            cand = (p_root / rel_parts[0]).resolve()
                            if cand.is_dir() and cand not in search_roots:
                                extracted_cand_repo = cand
                                break
                except Exception:
                    pass
            if not extracted_cand_repo:
                try:
                    ws_dir_res = AGY_WORKSPACE_DIR.resolve()
                    if target_path.is_relative_to(ws_dir_res):
                        rel_parts = target_path.relative_to(ws_dir_res).parts
                        if len(rel_parts) >= 2:
                            cand = (ws_dir_res / rel_parts[0] / rel_parts[1]).resolve()
                            if cand.is_dir() and cand not in search_roots:
                                extracted_cand_repo = cand
                except Exception:
                    pass
            if extracted_cand_repo:
                auto_resolved_ws = str(extracted_cand_repo)
                SESSION_STATE["auto_resolved_calls"] = int(SESSION_STATE.get("auto_resolved_calls") or 0) + 1
                _save_session_state()

        if auto_resolved_ws and not top_auto_ws:
            top_auto_ws = auto_resolved_ws

        is_safe = (not is_sensitive_filename(target_path.name)) and any(target_path.is_relative_to(a) for a in allowed)
        if not is_safe:
            files_list.append({"requested": raw_sub, "error": "Access denied: path outside authorized workspace boundaries."})
        elif target_path.is_file():
            try:
                full_text = target_path.read_text(encoding="utf-8", errors="replace")
                if outline_only:
                    ol = build_file_outline(target_path, full_text, ws_root=search_roots[0], max_chars=3800, include_callers=True)
                    compact_ol = {k: v for k, v in ol.items() if k not in ("symbol_items", "formatted_outline")}
                    entry_obj = {
                        "requested": raw_sub, "path": str(target_path), "bytes": target_path.stat().st_size,
                        "mode": "polyglot_outline", "total_lines": ol["total_lines"], "truncated": False,
                        "polyglot_outline": compact_ol, "content": ol["formatted_outline"],
                    }
                    if auto_resolved_ws:
                        entry_obj["auto_resolved_workspace"] = auto_resolved_ws
                    files_list.append(entry_obj)
                else:
                    slice_meta = slice_file_content(
                        full_text=full_text, clean_path=cleaned_no_line or target_path.name,
                        per_file_cap=per_file_cap, explicit_start_line=start_line, explicit_end_line=end_line,
                        inline_start_line=in_start, inline_end_line=in_end, center_line=in_center,
                    )
                    remaining_total_chars = max(4000, remaining_total_chars - len(slice_meta.get("content", "")))
                    entry_obj = {"requested": raw_sub, "path": str(target_path), "bytes": target_path.stat().st_size, **slice_meta}
                    is_full_head_read = (
                        start_line <= 1 and end_line == 0 and in_start <= 1 and in_end == 0 and in_center == 0
                    )
                    if slice_meta.get("hit_char_cap") and is_full_head_read:
                        ol_trunc = build_file_outline(target_path, full_text, ws_root=search_roots[0], max_chars=1400, include_callers=False)
                        entry_obj["polyglot_outline"] = {
                            k: v for k, v in ol_trunc.items() if k not in ("symbol_items", "formatted_outline")
                        }
                    if auto_resolved_ws:
                        entry_obj["auto_resolved_workspace"] = auto_resolved_ws
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
    out_bundle: dict[str, Any] = {"count": len(files_list), "files": files_list}
    if top_auto_ws:
        out_bundle["auto_resolved_workspace"] = top_auto_ws
    return out_bundle


def _host_git_inspect(
    ws_path: str, target_branch: str = "HEAD", include_untracked: bool = True, summary_only: bool = False, file_path: str = ""
) -> dict[str, Any]:
    """Fallback to agy-host-bridge git-inspect when a workspace or worktree parent .git lives on the host."""
    try:
        payload = {"action": "git-inspect", "workspace_path": ws_path, "target_branch": target_branch, "include_untracked": include_untracked, "summary_only": summary_only, "file_path": file_path}
        req = urllib.request.Request(cfg.AGY_HOST_BRIDGE_URL, data=json.dumps(payload).encode("utf-8"), headers=cfg.get_host_bridge_headers(), method="POST")
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
            if isinstance(data, dict) and data.get("ok"):
                return data
    except Exception:
        pass
    return {}


def _collect_git_summary(ws_path: Path) -> dict[str, Any]:
    """Return compact branch + status_short + diff_stat + untracked_files for a workspace (with host fallback for worktrees)."""
    ws_str = str(ws_path) if ws_path else ""
    umbrella_roots = get_umbrella_roots()
    if ws_path.is_dir() and ws_path.resolve() not in umbrella_roots:
        try:
            branch_proc = subprocess.run(["git", "-c", "safe.directory=*", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(ws_path), capture_output=True, text=True, timeout=4, check=False)
            if branch_proc.returncode == 0:
                status_proc = subprocess.run(["git", "-c", "safe.directory=*", "status", "--short"], cwd=str(ws_path), capture_output=True, text=True, timeout=4, check=False)
                stat_proc = subprocess.run(["git", "-c", "safe.directory=*", "diff", "--stat", "HEAD", "--"], cwd=str(ws_path), capture_output=True, text=True, timeout=4, check=False)
                untracked_proc = subprocess.run(["git", "-c", "safe.directory=*", "ls-files", "--others", "--exclude-standard"], cwd=str(ws_path), capture_output=True, text=True, timeout=4, check=False)
                return {
                    "current_branch": branch_proc.stdout.strip(),
                    "status_short": status_proc.stdout.strip(),
                    "diff_stat": stat_proc.stdout.strip(),
                    "untracked_files": [ln.strip() for ln in untracked_proc.stdout.splitlines() if ln.strip()][:80],
                }
        except Exception:
            pass
    if ws_str and Path(ws_str).resolve() not in umbrella_roots:
        host_res = _host_git_inspect(ws_str, target_branch="HEAD", include_untracked=True, summary_only=True)
        if host_res:
            return {
                "current_branch": host_res.get("current_branch", ""),
                "status_short": host_res.get("status_short", ""),
                "diff_stat": host_res.get("diff_stat", ""),
                "untracked_files": host_res.get("untracked_files", [])[:80],
            }
    return {}
