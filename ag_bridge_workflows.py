"""Companion module for advanced Gemini Notebook & Gemini Tasks workflows.

Provides:
1. Incremental Walkthrough & Plan export (`export_notebook_bundle`) for Google Drive / Gemini Notebook sync without duplicate write loops.
2. Single-turn multi-repository Git drift auditing (`inspect_multi_repo_drift`) for scheduled Gemini Tasks.
3. Split-trust quarantine handoff staging (`stage_quarantine_handoff`) for unattended scheduled runs when opted in via `AG_BRIDGE_ALLOW_LOCKED_STAGING=true`.
"""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
from typing import Any


def _slugify(value: str, fallback: str = "session", max_len: int = 36) -> str:
    """Convert arbitrary title or project string into a filesystem-safe lowercase slug."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    if not cleaned:
        return fallback
    return cleaned[:max_len].rstrip("-") or fallback


def export_notebook_bundle(
    brain_dir: Path, db_file: Path, bg_dir: Path, projects_map: dict[str, dict[str, Any]], limit: int = 25
) -> dict[str, Any]:
    """Export completed session implementation_plan.md and walkthrough.md artifacts with SHA-256 deduplication."""
    export_root = Path(os.getenv("AGY_NOTEBOOK_EXPORT_DIR", str(bg_dir / "notebook_exports"))).expanduser()
    export_root.mkdir(parents=True, exist_ok=True)

    meta_by_id: dict[str, dict[str, Any]] = {}
    if db_file.is_file():
        try:
            con = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
            rows = con.execute(
                "SELECT conversation_id, title, step_count, last_modified_time, workspace_uris, project_id "
                "FROM conversation_summaries WHERE parent_conversation_id IS NULL OR parent_conversation_id = '' "
                "ORDER BY last_modified_time DESC LIMIT ?",
                (max(limit * 3, 60),),
            ).fetchall()
            con.close()
            for row in rows:
                cid, pid = str(row[0] or ""), str(row[5] or "")
                pname = projects_map.get(pid, {}).get("name", pid or "workspace")
                ws_name = pname
                try:
                    uris = json.loads(str(row[4] or "[]"))
                    if uris and isinstance(uris, list):
                        first_u = re.sub(r"^file://", "", str(uris[0])).rstrip("/")
                        if first_u:
                            ws_name = Path(first_u).name
                except Exception:
                    pass
                meta_by_id[cid] = {
                    "title": str(row[1] or cid),
                    "step_count": int(row[2] or 0),
                    "last_modified": str(row[3] or ""),
                    "project_name": pname,
                    "workspace_name": ws_name,
                }
        except Exception:
            pass

    created_count, updated_count, unchanged_count = 0, 0, 0
    exported_files: list[dict[str, Any]] = []
    if not brain_dir.is_dir():
        return {"export_dir": str(export_root), "created": 0, "updated": 0, "unchanged": 0, "files": []}

    candidate_dirs = sorted(
        [d for d in brain_dir.iterdir() if d.is_dir() and not d.name.startswith(".")],
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
        reverse=True,
    )

    for sdir in candidate_dirs:
        if len(exported_files) >= limit:
            break
        walk_path = sdir / "walkthrough.md"
        plan_path = sdir / "implementation_plan.md"
        has_walk = walk_path.is_file() and walk_path.stat().st_size > 40
        has_plan = plan_path.is_file() and plan_path.stat().st_size > 40
        if not has_walk and not has_plan:
            continue

        cid = sdir.name
        meta = meta_by_id.get(cid, {})
        title = str(meta.get("title") or cid)
        ws_name = str(meta.get("workspace_name") or meta.get("project_name") or "workspace")
        last_mod = str(meta.get("last_modified") or "")
        date_prefix = last_mod[:10] if len(last_mod) >= 10 and last_mod[4:5] == "-" else datetime.fromtimestamp(
            sdir.stat().st_mtime, tz=timezone.utc
        ).strftime("%Y-%m-%d")

        fname = f"{date_prefix}_{_slugify(ws_name, 'repo', 20)}_{_slugify(title, 'session', 32)}_{cid[:8]}.md"
        target_path = export_root / fname

        walk_text = walk_path.read_text(encoding="utf-8", errors="replace").strip() if has_walk else ""
        plan_text = plan_path.read_text(encoding="utf-8", errors="replace").strip() if has_plan else ""

        sections = [
            f"# {title}",
            "",
            f"- **Session ID**: `{cid}`",
            f"- **Repository / Project**: `{ws_name}`",
            f"- **Date**: `{date_prefix}`",
            f"- **Steps**: `{meta.get('step_count', 0)}`",
            "",
        ]
        if walk_text:
            sections.extend(["## Walkthrough & Verification Summary", "", walk_text, ""])
        if plan_text:
            sections.extend(["## Implementation Plan & Architecture", "", plan_text, ""])

        compiled_md = "\n".join(sections).rstrip() + "\n"
        new_digest = hashlib.sha256(compiled_md.encode("utf-8")).hexdigest()

        state_label = "created"
        if target_path.is_file():
            try:
                old_digest = hashlib.sha256(target_path.read_bytes()).hexdigest()
                if old_digest == new_digest:
                    state_label = "unchanged"
                    unchanged_count += 1
                else:
                    target_path.write_text(compiled_md, encoding="utf-8")
                    state_label = "updated"
                    updated_count += 1
            except Exception:
                target_path.write_text(compiled_md, encoding="utf-8")
                state_label = "updated"
                updated_count += 1
        else:
            target_path.write_text(compiled_md, encoding="utf-8")
            created_count += 1

        exported_files.append({
            "file": fname,
            "conversation_id": cid,
            "title": title,
            "repository": ws_name,
            "sync_state": state_label,
            "bytes": len(compiled_md.encode("utf-8")),
        })

    return {
        "export_dir": str(export_root),
        "total_exported": len(exported_files),
        "created": created_count,
        "updated": updated_count,
        "unchanged": unchanged_count,
        "files": exported_files,
    }


def inspect_multi_repo_drift(
    gitlab_dir: Path,
    data_dir: Path,
    workspace_override: str = "ALL",
    include_untracked: bool = True,
) -> dict[str, Any]:
    """Scan all (or comma-separated) local Git repositories in a single turn and return uncommitted drift status."""
    raw = (workspace_override or "ALL").strip()
    is_all = raw.upper() in ("ALL", "*", "ALL_REPOS")
    requested_names = {
        p.strip().lower().rstrip("/")
        for p in re.split(r"[,;]+", raw)
        if p.strip()
    }

    candidates: list[Path] = []
    if gitlab_dir.is_dir():
        for entry in sorted(gitlab_dir.iterdir()):
            if entry.is_dir() and not entry.name.startswith(".") and (entry / ".git").exists():
                if is_all or entry.name.lower() in requested_names:
                    candidates.append(entry)

    wt_root = data_dir / "worktrees"
    if wt_root.is_dir():
        for proj_wt in sorted(wt_root.iterdir()):
            if proj_wt.is_dir() and not proj_wt.name.startswith("."):
                if is_all or proj_wt.name.lower() in requested_names:
                    sub_wts = sorted([d for d in proj_wt.iterdir() if d.is_dir()], key=lambda x: x.stat().st_mtime, reverse=True)
                    if sub_wts:
                        candidates.append(sub_wts[0])

    repo_reports: list[dict[str, Any]] = []
    dirty_count = 0
    clean_count = 0

    for repo_path in candidates[:25]:
        try:
            br_proc = subprocess.run(
                ["git", "-c", "safe.directory=*", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(repo_path), capture_output=True, text=True, timeout=4, check=False,
            )
            if br_proc.returncode != 0:
                continue
            branch = br_proc.stdout.strip()
            st_proc = subprocess.run(
                ["git", "-c", "safe.directory=*", "status", "--short"],
                cwd=str(repo_path), capture_output=True, text=True, timeout=4, check=False,
            )
            status_lines = [l for l in st_proc.stdout.splitlines() if l.strip()]
            if not include_untracked:
                status_lines = [l for l in status_lines if not l.startswith("??")]
            is_dirty = len(status_lines) > 0
            if is_dirty:
                dirty_count += 1
            else:
                clean_count += 1

            stat_str = ""
            if is_dirty:
                stat_proc = subprocess.run(
                    ["git", "-c", "safe.directory=*", "diff", "--stat", "HEAD", "--"],
                    cwd=str(repo_path), capture_output=True, text=True, timeout=4, check=False,
                )
                stat_str = stat_proc.stdout.strip()[:400]

            repo_reports.append({
                "repository": repo_path.name,
                "path": str(repo_path),
                "branch": branch,
                "is_dirty": is_dirty,
                "changed_files_count": len(status_lines),
                "status_short": "\n".join(status_lines[:15]),
                "diff_stat": stat_str,
            })
        except Exception:
            continue

    # Sort dirty repositories first so drift stands out immediately
    repo_reports.sort(key=lambda r: (not r["is_dirty"], r["repository"]))
    return {
        "ok": True,
        "mode": "multi_repo_drift_audit",
        "scanned_repositories_count": len(repo_reports),
        "dirty_repositories_count": dirty_count,
        "clean_repositories_count": clean_count,
        "repositories": repo_reports,
    }


def stage_quarantine_handoff(
    bg_dir: Path,
    research_markdown: str,
    session_title: str = "",
    project_name: str = "",
    workspace_path: str = "",
) -> dict[str, Any]:
    """Stage an incoming unattended research brief into the quarantine folder while the deadbolt is locked."""
    q_dir = bg_dir / "quarantine_handoffs"
    q_dir.mkdir(parents=True, exist_ok=True)
    now_utc = datetime.now(timezone.utc)
    ts_iso = now_utc.isoformat()
    ts_slug = now_utc.strftime("%Y%m%d-%H%M%S")
    title_slug = _slugify(session_title or project_name or "scheduled-handoff", "handoff", 32)
    target_file = q_dir / f"{ts_slug}_{title_slug}.md"

    body = research_markdown.strip()
    content = (
        f"<!-- Unattended Quarantine Handoff (Staged While Locked) -->\n"
        f"<!-- Staged At: {ts_iso} | Title: {session_title} | Project: {project_name} | Workspace: {workspace_path} -->\n\n"
        f"{body}\n"
    )
    target_file.write_text(content, encoding="utf-8")
    (q_dir / "latest_quarantine_handoff.md").write_text(content, encoding="utf-8")
    return {
        "ok": True,
        "status": "QUARANTINE_STAGED",
        "locked": True,
        "resumed": False,
        "chars_written": len(body),
        "quarantine_file": str(target_file),
        "message": (
            "Unattended handoff safely staged in quarantine while deadbolt is locked. "
            "No live session files were modified and headless execution was not triggered."
        ),
    }
