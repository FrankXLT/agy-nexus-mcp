#!/usr/bin/env python3
"""
agy_nexus.search — Pinned-Session Search, Polyglot Symbol Lookup, Time-Boxed Multi-Repo Grep & SQLite FTS5.
"""

from __future__ import annotations

from contextlib import closing
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time
from typing import Any

from agy_nexus.config import AGY_BRAIN_DIR, AGY_DATA_DIR, AGY_DB_FILE, AGY_GITLAB_DIR
from agy_nexus.hygiene import is_sensitive_filename
from agy_nexus.polyglot_index import polyglot_symbol_search
from agy_nexus.polyglot_outline import find_symbol_callers
from agy_nexus.virtual_uris import resolve_transcript_file

SEARCH_WALL_CLOCK_BUDGET_S = 3.2
PER_REPO_GREP_TIMEOUT_S = 1.5


def _run_repo_search(
    target_repo: Path,
    patterns: list[str],
    per_repo_cap: int,
    fixed_strings: bool = False,
    deadline: float | None = None,
) -> list[str]:
    """Run git grep (with fallback to GNU grep for host-backed worktrees) under strict wall-clock budget."""
    if not patterns:
        return []
    if deadline is not None and time.monotonic() >= deadline:
        return []
    rem_timeout = PER_REPO_GREP_TIMEOUT_S if deadline is None else min(PER_REPO_GREP_TIMEOUT_S, max(0.2, deadline - time.monotonic()))
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
            proc = subprocess.run(cmd, cwd=str(target_repo), capture_output=True, text=True, timeout=rem_timeout, check=False)
            if proc.returncode == 0 and proc.stdout:
                for line in proc.stdout.splitlines():
                    if is_sensitive_filename(line.split(":", 1)[0]):
                        continue
                    matches.append(f"[{target_repo.name}] {line[:220]}")
                    if len(matches) >= per_repo_cap:
                        break
                return matches
        except Exception:
            pass

    if deadline is not None and time.monotonic() >= deadline:
        return matches
    try:
        g_mode = ["-F"] if fixed_strings else ["-E"]
        gcmd = [
            "grep", "-rnIi", "-m", "5",
            "--exclude-dir=.git", "--exclude-dir=node_modules", "--exclude-dir=venv",
            "--exclude-dir=.venv", "--exclude-dir=__pycache__", "--exclude-dir=dist",
            "--exclude-dir=build", "--exclude-dir=backups",
            "--exclude=.env*", "--exclude=*.env", "--exclude=secrets.env*",
            "--exclude=config.json*", "--exclude=mcp_config.json*",
        ] + g_mode + e_args + ["."]
        rem_g = PER_REPO_GREP_TIMEOUT_S if deadline is None else min(PER_REPO_GREP_TIMEOUT_S, max(0.2, deadline - time.monotonic()))
        gproc = subprocess.run(gcmd, cwd=str(target_repo), capture_output=True, text=True, timeout=rem_g, check=False)
        if gproc.returncode == 0 and gproc.stdout:
            for line in gproc.stdout.splitlines():
                clean_line = line[2:] if line.startswith("./") else line
                if is_sensitive_filename(clean_line.split(":", 1)[0]):
                    continue
                matches.append(f"[{target_repo.name}] {clean_line[:220]}")
                if len(matches) >= per_repo_cap:
                    break
    except Exception:
        pass
    return matches


def _get_configured_mcp_servers() -> list[str]:
    """Return configured MCP server names WITHOUT exposing URLs, tokens, or env secrets."""
    mcp_cfg = AGY_DATA_DIR / "mcp_config.json"
    if not mcp_cfg.is_file():
        return []
    try:
        data = json.loads(mcp_cfg.read_text(encoding="utf-8"))
        servers = data.get("mcpServers") or {}
        if isinstance(servers, dict):
            return sorted(str(k) for k in servers.keys())
    except Exception:
        pass
    return []


def _search_pinned_session(conv_id: str, q: str, tokens: list[str]) -> list[dict[str, Any]]:
    """Tier-0 search inside the pinned session's brain markdown artifacts and untruncated transcript_full.jsonl."""
    safe_cid = re.sub(r"[^a-zA-Z0-9_-]", "", (conv_id or "").strip())
    if not safe_cid or not q:
        return []
    brain_root = AGY_BRAIN_DIR.resolve()
    sdir = (AGY_BRAIN_DIR / safe_cid).resolve()
    if sdir == brain_root or not sdir.is_relative_to(brain_root) or not sdir.is_dir():
        return []

    hits: list[dict[str, Any]] = []
    q_low = q.lower()
    tok_low = [t.lower() for t in tokens[:6]]

    md_candidates = sorted(
        p for p in sdir.rglob("*")
        if p.is_file()
        and ".system_generated" not in p.parts
        and not is_sensitive_filename(p.name)
        and p.suffix.lower() in (".md", ".txt", ".json", ".py")
    )[:40]
    for md_p in md_candidates:
        try:
            if md_p.stat().st_size > 524_288:
                continue
            for lno, raw_ln in enumerate(md_p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                low_ln = raw_ln.lower()
                if q_low in low_ln or (len(tok_low) >= 2 and all(t in low_ln for t in tok_low[:3])):
                    rel_b = str(md_p.relative_to(sdir)).replace("\\", "/")
                    hits.append({
                        "source": f"brain:{safe_cid}/{rel_b}",
                        "line": lno,
                        "snippet": raw_ln.strip()[:220],
                    })
                    if len(hits) >= 8:
                        break
        except Exception:
            continue
        if len(hits) >= 8:
            break

    tfile = resolve_transcript_file(sdir)
    if tfile and len(hits) < 12:
        try:
            with tfile.open("r", encoding="utf-8", errors="replace") as fh:
                for raw_line in fh:
                    low_raw = raw_line.lower()
                    if q_low not in low_raw and not (len(tok_low) >= 2 and all(t in low_raw for t in tok_low[:3])):
                        continue
                    try:
                        entry = json.loads(raw_line)
                    except Exception:
                        continue
                    content = str(entry.get("content") or entry.get("text") or "")
                    low_c = content.lower()
                    pos = low_c.find(q_low)
                    if pos == -1 and tok_low:
                        pos = max((low_c.find(t) for t in tok_low), default=-1)
                    if pos >= 0:
                        start = max(0, pos - 60)
                        step_idx = entry.get("step_index", "?")
                        hits.append({
                            "source": f"transcript:step:{step_idx}",
                            "type": entry.get("type") or entry.get("role") or "TURN",
                            "snippet": content[start : start + 220].replace("\n", " "),
                        })
                        if len(hits) >= 12:
                            break
        except Exception:
            pass
    return hits


def _search_workspaces_and_history(
    search_query: str = "",
    primary_ws: Path | None = None,
    conv_id: str = "",
    workspace_pinned: bool = False,
) -> dict[str, Any]:
    """Search pinned session artifacts/transcript, Polyglot index, local git repos (<=3.2s cap), and SQLite FTS5."""
    t_start = time.monotonic()
    deadline = t_start + SEARCH_WALL_CLOCK_BUDGET_S

    gh_dir = AGY_GITLAB_DIR.parent / "github"
    repo_names: set[str] = set()
    for host_dir in (AGY_GITLAB_DIR, gh_dir):
        if host_dir.is_dir():
            repo_names.update(d.name for d in host_dir.iterdir() if d.is_dir() and not d.name.startswith("."))
    available_repos = sorted(repo_names)
    configured_mcps = _get_configured_mcp_servers()
    grep_matches: list[str] = []
    fts_matches: list[dict[str, Any]] = []
    pinned_matches: list[dict[str, Any]] = []
    polyglot_matches: list[dict[str, Any]] = []

    q = (search_query or "").strip()
    if q:
        stopwords = {"the", "and", "for", "with", "from", "that", "this", "what", "where", "how", "existing", "project", "current"}
        kw_tokens = [w for w in re.findall(r"[A-Za-z0-9_.-]{3,}", q) if w.lower() not in stopwords][:6]

        if conv_id:
            pinned_matches = _search_pinned_session(conv_id, q, kw_tokens)

        if primary_ws and primary_ws.is_dir() and primary_ws.resolve() not in (AGY_GITLAB_DIR.resolve(), gh_dir.resolve()):
            try:
                poly_res = polyglot_symbol_search(q, workspace=str(primary_ws), limit=8)
                polyglot_matches = poly_res.get("matches") or []
            except Exception:
                polyglot_matches = []

        repo_targets: list[Path] = []
        if primary_ws and primary_ws.is_dir() and primary_ws.resolve() not in (AGY_GITLAB_DIR.resolve(), gh_dir.resolve()):
            repo_targets.append(primary_ws.resolve())
        if not workspace_pinned:
            for host_dir in (AGY_GITLAB_DIR, gh_dir):
                if host_dir.is_dir():
                    for d in sorted(host_dir.iterdir()):
                        if d.is_dir() and not d.name.startswith(".") and not d.is_symlink() and d.resolve() not in repo_targets:
                            repo_targets.append(d.resolve())
            wt_root = AGY_DATA_DIR / "worktrees"
            if wt_root.is_dir():
                for proj_wt in sorted(wt_root.iterdir()):
                    if proj_wt.is_dir():
                        sub_wts = sorted([d for d in proj_wt.iterdir() if d.is_dir()], key=lambda x: x.stat().st_mtime, reverse=True)
                        for sw in sub_wts[:1]:
                            if sw.resolve() not in repo_targets:
                                repo_targets.append(sw.resolve())

        for target_repo in repo_targets:
            if len(grep_matches) >= 35 or time.monotonic() >= deadline:
                break
            cap = 15 if (primary_ws and target_repo == primary_ws.resolve()) else 5
            grep_matches.extend(_run_repo_search(target_repo, [q], per_repo_cap=cap, fixed_strings=True, deadline=deadline))

        if not grep_matches and len(kw_tokens) >= 2 and time.monotonic() < deadline:
            for target_repo in repo_targets[:8]:
                if len(grep_matches) >= 35 or time.monotonic() >= deadline:
                    break
                cap = 15 if (primary_ws and target_repo == primary_ws.resolve()) else 5
                grep_matches.extend(_run_repo_search(target_repo, kw_tokens, per_repo_cap=cap, fixed_strings=True, deadline=deadline))

        if AGY_DB_FILE.is_file():
            try:
                with closing(sqlite3.connect(f"file:{AGY_DB_FILE}?mode=ro", uri=True)) as con:
                    cur = con.cursor()
                    like_pat = f"%{q}%"
                    sql_like = """
                        SELECT conversation_id, title, substr(latest_user_input, 1, 200), last_modified_time
                        FROM conversation_summaries
                        WHERE (parent_conversation_id IS NULL OR parent_conversation_id = '')
                          AND (title LIKE ? OR latest_user_input LIKE ? OR latest_agent_response LIKE ? OR workspace_uris LIKE ?)
                        ORDER BY last_modified_time DESC
                        LIMIT 6
                    """
                    seen_ids: set[str] = set()
                    for r in cur.execute(sql_like, (like_pat, like_pat, like_pat, like_pat)).fetchall():
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
            except Exception:
                pass

    res: dict[str, Any] = {
        "available_repositories": available_repos,
        "configured_mcp_servers": configured_mcps,
        "pinned_session_matches": pinned_matches[:10],
        "polyglot_symbol_matches": polyglot_matches[:8],
        "code_search_matches": grep_matches[:35],
        "historical_session_matches": fts_matches[:8],
    }
    if q and re.match(r"^[a-zA-Z_][a-zA-Z0-9_]{2,64}$", q) and primary_ws and primary_ws.is_dir():
        res["symbol_callers"] = find_symbol_callers(q, primary_ws, max_refs=6)
    return res
