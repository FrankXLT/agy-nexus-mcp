#!/usr/bin/env python3
"""
agy_nexus.search — Multi-Repository Git Grep & SQLite FTS5 Conversation Search.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import sqlite3
import subprocess
from typing import Any

from agy_nexus.config import AGY_DATA_DIR, AGY_DB_FILE, AGY_GITLAB_DIR

def _run_repo_search(target_repo: Path, patterns: list[str], per_repo_cap: int, fixed_strings: bool = False) -> list[str]:
    """Run git grep (with fallback to GNU grep for host-backed worktrees) and return formatted matches."""
    if not patterns:
        return []
    matches: list[str] = []
    e_args: list[str] = []
    for pat in patterns:
        if pat:
            e_args.extend(["-e", pat])
    if not e_args:
        return []

    flag_mode = ["-F"] if fixed_strings else []
    if (target_repo / ".git").exists():
        try:
            cmd = ["git", "-c", "safe.directory=*", "grep", "-n", "-I", "-i", "--max-count=5"] + flag_mode + e_args
            proc = subprocess.run(cmd, cwd=str(target_repo), capture_output=True, text=True, timeout=4, check=False)
            if proc.returncode == 0 and proc.stdout:
                for line in proc.stdout.splitlines()[:per_repo_cap]:
                    matches.append(f"[{target_repo.name}] {line[:220]}")
                return matches
            if proc.returncode == 2 and not fixed_strings:
                return _run_repo_search(target_repo, patterns, per_repo_cap, fixed_strings=True)
            if proc.returncode in (0, 1):
                return []
        except Exception:
            pass

    # Fallback to GNU grep (handles worktrees whose parent .git lives outside container mounts)
    try:
        g_cmd = [
            "grep", "-rnI", "-i",
            "--exclude-dir=.git", "--exclude-dir=node_modules", "--exclude-dir=dist",
            "--exclude-dir=build", "--exclude-dir=.next", "--exclude-dir=coverage",
            "-m", "5",
        ] + flag_mode + e_args + ["."]
        proc = subprocess.run(g_cmd, cwd=str(target_repo), capture_output=True, text=True, timeout=4, check=False)
        if proc.returncode == 0 and proc.stdout:
            for line in proc.stdout.splitlines()[:per_repo_cap]:
                clean_line = line[2:] if line.startswith("./") else line
                matches.append(f"[{target_repo.name}] {clean_line[:220]}")
        elif proc.returncode == 2 and not fixed_strings:
            return _run_repo_search(target_repo, patterns, per_repo_cap, fixed_strings=True)
    except Exception:
        pass
    return matches

def _get_configured_mcp_servers() -> list[str]:
    """Return sorted list of configured MCP server names from AGY_DATA_DIR / 'mcp'."""
    mcp_dir = AGY_DATA_DIR / "mcp"
    if mcp_dir.is_dir():
        try:
            return sorted([d.name for d in mcp_dir.iterdir() if d.is_dir() and not d.name.startswith(".")])
        except Exception:
            pass
    return []

def _search_workspaces_and_history(search_query: str, primary_ws: Path | None = None) -> dict[str, Any]:
    """Search across all local Git repositories, worktrees, configured MCP servers, and SQLite conversation history."""
    available_repos: list[str] = []
    repo_dirs: list[Path] = []
    if AGY_GITLAB_DIR.is_dir():
        for entry in sorted(AGY_GITLAB_DIR.iterdir()):
            if entry.is_dir() and not entry.name.startswith(".") and not entry.is_symlink():
                available_repos.append(entry.name)
                if (entry / ".git").exists():
                    repo_dirs.append(entry)

    # Dynamically include any active worktrees under AGY_DATA_DIR / "worktrees"
    wt_root = AGY_DATA_DIR / "worktrees"
    if wt_root.is_dir():
        for proj_wt in sorted(wt_root.iterdir()):
            if proj_wt.is_dir() and not proj_wt.name.startswith("."):
                wt_dirs = sorted([d for d in proj_wt.iterdir() if d.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)
                if wt_dirs:
                    available_repos.append(f"{proj_wt.name} ({wt_dirs[0].name})")
                    repo_dirs.append(wt_dirs[0])

    configured_mcps = _get_configured_mcp_servers()

    grep_matches: list[str] = []
    fts_matches: list[dict[str, Any]] = []
    q = (search_query or "").strip()
    if q:
        search_targets: list[Path] = []
        if primary_ws and primary_ws.is_dir() and primary_ws != AGY_GITLAB_DIR:
            search_targets.append(primary_ws)
        priority_env = [p.strip() for p in os.getenv("AGY_PRIORITY_REPOS", "antigravity-config").split(",") if p.strip()]
        for priority_name in priority_env:
            pdir = AGY_GITLAB_DIR / priority_name
            if pdir in repo_dirs and pdir not in search_targets:
                search_targets.append(pdir)
        for rdir in repo_dirs:
            if rdir not in search_targets:
                search_targets.append(rdir)

        for idx, target_repo in enumerate(search_targets):
            if len(grep_matches) >= 35:
                break
            per_repo_cap = 10 if idx == 0 else 6
            grep_matches.extend(_run_repo_search(target_repo, [q], per_repo_cap))

        # If exact phrase returned 0 matches and query has multiple words, retry with OR-ed keywords
        if not grep_matches:
            keywords = [w for w in re.findall(r"[A-Za-z0-9_.-]{3,}", q) if w.lower() not in {"and", "the", "for", "with", "from"}][:5]
            if len(keywords) > 1:
                for idx, target_repo in enumerate(search_targets):
                    if len(grep_matches) >= 35:
                        break
                    per_repo_cap = 10 if idx == 0 else 6
                    grep_matches.extend(_run_repo_search(target_repo, keywords, per_repo_cap))

        if AGY_DB_FILE.is_file():
            try:
                con = sqlite3.connect(f"file:{AGY_DB_FILE}?mode=ro", uri=True)
                cur = con.cursor()
                like_pat = f"%{q}%"
                title_sql = """
                    SELECT conversation_id, title, substr(preview, 1, 200), last_modified_time
                    FROM conversation_summaries
                    WHERE title LIKE ? OR preview LIKE ?
                    ORDER BY last_modified_time DESC
                    LIMIT 5
                """
                seen_ids: set[str] = set()
                for r in cur.execute(title_sql, (like_pat, like_pat)).fetchall():
                    seen_ids.add(str(r[0]))
                    fts_matches.append({
                        "conversation_id": r[0],
                        "title": r[1],
                        "preview": r[2],
                        "last_modified": r[3],
                    })

                tokens = [t for t in re.findall(r"[A-Za-z0-9_]{2,}", q) if t.upper() not in ("AND", "OR", "NOT", "NEAR")][:6]
                if tokens:
                    fts_expr = " OR ".join(f'"{t}"' for t in tokens)
                    fts_sql = """
                        SELECT conversation_id, title,
                               snippet(conversations_fts, 13, '[', ']', '...', 15),
                               snippet(conversations_fts, 14, '[', ']', '...', 15)
                        FROM conversations_fts
                        WHERE conversations_fts MATCH ?
                        LIMIT 6
                    """
                    for r in cur.execute(fts_sql, (fts_expr,)).fetchall():
                        if str(r[0]) not in seen_ids:
                            seen_ids.add(str(r[0]))
                            fts_matches.append({
                                "conversation_id": r[0],
                                "title": r[1],
                                "user_snippet": r[2],
                                "agent_snippet": r[3],
                            })
                con.close()
            except Exception:
                pass

    return {
        "available_repositories": available_repos,
        "configured_mcp_servers": configured_mcps,
        "code_search_matches": grep_matches[:35],
        "historical_session_matches": fts_matches[:8],
    }
