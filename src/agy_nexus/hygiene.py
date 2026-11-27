#!/usr/bin/env python3
"""
agy_nexus.hygiene — Modular Architecture Standards, Line-Range File Slicing,
and Diff Pagination Helpers for AGY-Nexus MCP.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any

# Configurable Session & Context Window Limits (via secrets.env or container env)
MIN_TTL_SECONDS = int(os.getenv("MIN_TTL_SECONDS", "300"))
TTL_SECONDS = max(int(os.getenv("TTL_SECONDS", "7200")), MIN_TTL_SECONDS)
MAX_FILE_CHARS = int(os.getenv("MAX_FILE_CHARS", "14000"))
MAX_TOTAL_FILE_CHARS = int(os.getenv("MAX_TOTAL_FILE_CHARS", "16500"))
MAX_FILES_PER_CALL = int(os.getenv("MAX_FILES_PER_CALL", "12"))
MAX_DIFF_CHARS = int(os.getenv("MAX_DIFF_CHARS", "15000"))
MAX_TRANSCRIPT_TURNS = int(os.getenv("MAX_TRANSCRIPT_TURNS", "8"))
MAX_TASK_DOC_CHARS = int(os.getenv("MAX_TASK_DOC_CHARS", "16000"))
ENFORCE_MODULAR_HYGIENE = os.getenv("ENFORCE_MODULAR_HYGIENE", "true").strip().lower() in ("1", "true", "yes", "on")
TARGET_FILE_LINES = int(os.getenv("TARGET_FILE_LINES", "500"))
HARD_MAX_FILE_LINES = int(os.getenv("HARD_MAX_FILE_LINES", "650"))

MODULAR_HYGIENE_STANDARDS: dict[str, Any] = {
    "enabled": ENFORCE_MODULAR_HYGIENE,
    "target_lines_per_file": f"100-{TARGET_FILE_LINES} lines (functions <= 100 lines)",
    "hard_split_ceiling_lines": HARD_MAX_FILE_LINES,
    "core_principles": [
        f"Keep source files cohesive up to {TARGET_FILE_LINES} lines (hard split ceiling at {HARD_MAX_FILE_LINES} lines, functions <= 100 lines); use Polyglot semantic outlines (`agy-praxis-mcp` / `outline:<path>`) to isolate exact line spans without micro-file sprawl.",
        "Decompose by cohesive domain capability (e.g., config, models/types, db/repository, services, routes/handlers, utils) with clean public interfaces and zero circular imports—never fragment cohesive modules into tiny files.",
        "Maintain strict root-directory hygiene: keep only project manifests (README.md, pyproject.toml/package.json, docker-compose.yml, .env.example, .gitignore) in the repository root; place code in src/ (or package dir), tests in tests/, and operational scripts in scripts/. Store temporary notes and scratch files strictly in the session brain directory (~/.gemini/antigravity/brain/<conv_id>/scratch/), NEVER in a repo-root scratch/ directory that could shadow handoff files.",
        f"When modifying a legacy file that already exceeds {HARD_MAX_FILE_LINES} lines, extract newly added subsystems into a cohesive companion module (<= {TARGET_FILE_LINES} lines) rather than growing the monolith.",
    ],
}

MODULAR_HYGIENE_MARKDOWN_BLOCK = f"""
---
## Mandatory Modular Architecture, Praxis/Polyglot Navigation & File Hygiene Standard
When standing up or modifying this project, enforce the following rules automatically:
1. **Verified Facts vs. Hypotheses Checklist**: Label any unverified assumption as a hypothesis; verify live state, configs, and schemas before mutating code.
2. **Polyglot-First Navigation & File Budget (`<= {TARGET_FILE_LINES} lines` Target, `{HARD_MAX_FILE_LINES} lines` Hard Ceiling, Functions `<= 100 lines`)**: Use `agy-praxis-mcp` (`polyglot_map`, `polyglot_search`, `polyglot_outline`) to locate exact `Lstart-Lend` spans first rather than creating micro-file sprawl. Keep cohesive modules `<= {TARGET_FILE_LINES}` lines (`<= {HARD_MAX_FILE_LINES}` ceiling) and individual functions `<= 100` lines.
3. **Cohesive Domain Decomposition**: Group code by domain responsibility (`config`, `models`, `repository`, `services`, `routes`, `utils`) with zero circular dependencies.
4. **Root-Directory Hygiene & Scratch File Isolation**: Keep the repo root clean (manifests only; code in `src/`, tests in `tests/`, scripts in `scripts/`). Store temporary scratch scripts/notes strictly in the session brain directory (`~/.gemini/antigravity/brain/<conv_id>/scratch/`), NEVER in a repo-root `scratch/` directory that could shadow handoff files.
"""


_SAFE_ENV_TEMPLATES: frozenset[str] = frozenset({
    ".env.example", ".env.sample", ".env.template", ".env.dist",
})


def is_sensitive_filename(filename: str) -> bool:
    """Return True if filename is a secret/credential file that must never be indexed, searched, or read."""
    low = os.path.basename(filename or "").strip().lower()
    if not low or low in _SAFE_ENV_TEMPLATES or low.endswith((".env.example", ".env.sample", ".env.template")):
        return False
    return (
        low.startswith(("config.json", "mcp_config.json", "secrets.env", ".env."))
        or low in (".env", "credentials.json", "session_state.json", "antigravity_state.pbtxt")
        or low.endswith((".env", ".pem", ".key", "secrets.env.bak"))
    )


def parse_inline_line_spec(raw_sub: str) -> tuple[str, int, int, int]:
    """
    Parse optional inline line range or target line from a file path specifier.
    Examples:
      'src/app.py:120-260'   -> ('src/app.py', 120, 260, 0)
      'src/app.py#L50-L180'  -> ('src/app.py', 50, 180, 0)
      'src/app.py:420:def x' -> ('src/app.py', 0, 0, 420)
    Returns (cleaned_path_no_line, start_line, end_line, center_line).
    """
    s = raw_sub.strip()
    if re.match(r"^(?:transcript|telemetry|polyglot):", s, flags=re.IGNORECASE):
        m_vrange = re.search(r":(\d+)-(\d+)$", s)
        if m_vrange:
            st, en = int(m_vrange.group(1)), int(m_vrange.group(2))
            return s[: m_vrange.start()].strip(), st, max(st, en), 0
        return s, 0, 0, 0
    m_hash = re.search(r"#L(\d+)(?:-L?(\d+))?$", s)
    if m_hash:
        base = s[: m_hash.start()].strip()
        st = int(m_hash.group(1))
        en = int(m_hash.group(2)) if m_hash.group(2) else 0
        if en > 0:
            return base, st, max(st, en), 0
        return base, 0, 0, st
    m_range = re.search(r":(\d+)-(\d+)(?::.*)?$", s)
    if m_range:
        base = s[: m_range.start()].strip()
        st = int(m_range.group(1))
        en = int(m_range.group(2))
        return base, st, max(st, en), 0
    m_single = re.search(r":(\d+)(?::.*)?$", s)
    if m_single:
        base = s[: m_single.start()].strip()
        return base, 0, 0, int(m_single.group(1))
    return s, 0, 0, 0


def slice_file_content(
    full_text: str,
    clean_path: str,
    per_file_cap: int,
    explicit_start_line: int = 0,
    explicit_end_line: int = 0,
    inline_start_line: int = 0,
    inline_end_line: int = 0,
    center_line: int = 0,
) -> dict[str, Any]:
    """
    Slice file content by line range or centered target line while staying within per_file_cap characters.
    Separates `hit_char_cap` (cap-induced truncation) from `truncated` (partial file view).
    """
    all_lines = full_text.splitlines(keepends=True)
    total_lines = len(all_lines)
    if total_lines == 0:
        return {
            "total_lines": 0,
            "shown_start_line": 0,
            "shown_end_line": 0,
            "shown_lines": "0-0 of 0",
            "truncated": False,
            "hit_char_cap": False,
            "content": "",
        }
    st = explicit_start_line if explicit_start_line > 0 else inline_start_line
    en = explicit_end_line if explicit_end_line > 0 else inline_end_line
    if st <= 0 and center_line > 0 and (len(full_text) > per_file_cap or total_lines > 140):
        st = max(1, center_line - 60)
        en = min(total_lines, center_line + 180)
    if st <= 0:
        st = 1
    st = max(1, min(st, total_lines))
    max_en = min(total_lines, en) if en >= st else total_lines
    out_chunks: list[str] = []
    char_count = 0
    actual_end = st - 1
    hit_char_cap = False
    for idx in range(st - 1, max_en):
        line_str = all_lines[idx]
        if char_count + len(line_str) > per_file_cap and out_chunks:
            hit_char_cap = True
            break
        if len(line_str) > per_file_cap and not out_chunks:
            out_chunks.append(line_str[:per_file_cap])
            actual_end = idx + 1
            hit_char_cap = True
            break
        out_chunks.append(line_str)
        char_count += len(line_str)
        actual_end = idx + 1
    content = "".join(out_chunks)
    truncated = (st > 1) or (actual_end < total_lines) or hit_char_cap
    result: dict[str, Any] = {
        "total_lines": total_lines,
        "shown_start_line": st,
        "shown_end_line": actual_end,
        "shown_lines": f"{st}-{actual_end} of {total_lines}",
        "truncated": truncated,
        "hit_char_cap": hit_char_cap,
        "content": content,
    }
    if actual_end < total_lines:
        next_st = actual_end + 1
        next_en = min(total_lines, next_st + 499)
        result["next_range_hint"] = (
            f"Showing lines {st}-{actual_end} of {total_lines}. "
            f"Pass start_line={next_st}, end_line={next_en} (or file_subpath='{clean_path}:{next_st}-{next_en}') via a sequential follow-up call if needed—never in parallel."
        )
    if ENFORCE_MODULAR_HYGIENE and total_lines > HARD_MAX_FILE_LINES:
        result["modularity_advisory"] = (
            f"File has {total_lines} lines (exceeds {HARD_MAX_FILE_LINES}-line modular ceiling). "
            f"If modifying this area, extract new logic into a cohesive module (<= {TARGET_FILE_LINES} lines)."
        )
    return result


def slice_git_diff(
    diff_out: str,
    offset_chars: int = 0,
    max_diff_chars: int = MAX_DIFF_CHARS,
    file_path: str = "",
    start_line: int = 0,
    end_line: int = 0,
) -> dict[str, Any]:
    """Slice a git diff output with character-offset or line-range pagination and explicit continuation hints."""
    if start_line > 0 or end_line > 0:
        line_meta = slice_file_content(
            full_text=diff_out,
            clean_path=file_path or "diff",
            per_file_cap=max(2000, max_diff_chars),
            explicit_start_line=max(1, start_line),
            explicit_end_line=end_line,
        )
        return {
            "file_path_filter": file_path,
            "total_diff_chars": len(diff_out),
            "shown_diff_range": f"lines {line_meta['shown_lines']}",
            "diff_truncated": line_meta["truncated"],
            "diff": line_meta["content"],
            **({"pagination_hint": line_meta["next_range_hint"]} if "next_range_hint" in line_meta else {}),
        }
    total_chars = len(diff_out)
    safe_offset = max(0, min(offset_chars, total_chars)) if total_chars > 0 else 0
    safe_cap = max(2000, max_diff_chars)
    sliced = diff_out[safe_offset : safe_offset + safe_cap]
    end_offset = safe_offset + len(sliced)
    truncated = (safe_offset > 0) or (end_offset < total_chars)
    res: dict[str, Any] = {
        "file_path_filter": file_path,
        "total_diff_chars": total_chars,
        "offset_chars": safe_offset,
        "shown_diff_range": f"{safe_offset}-{end_offset} of {total_chars}",
        "diff_truncated": truncated,
        "diff": sliced,
    }
    if end_offset < total_chars:
        res["pagination_hint"] = (
            f"Showing diff chars {safe_offset}-{end_offset} of {total_chars}. "
            f"Pass offset_chars={end_offset} (or start_line/end_line) via a sequential follow-up call if needed—never in parallel—or pass file_path='<subpath>'."
        )
    return res


def _compact_markdown(text: str, max_chars: int = 5500, source_hint: str = "...") -> str:
    """Keep markdown under max_chars while preserving headings, intro, and latest sections."""
    if len(text) <= max_chars:
        return text
    if max_chars < 420:
        cut = max(1, max_chars - 16)
        return text[:cut] + "\n... [compacted]"
    headings = [line.strip() for line in text.splitlines() if line.lstrip().startswith("#")][:40]
    hint_expr = f"'{source_hint}'" if source_hint != "..." else "..."
    hdr = f"[Document Outline ({len(text)} total chars — ask_workspace_readonly(file_subpath={hint_expr}) for middle)]:\n"
    sep_mid = "\n\n... [middle omitted] ...\n\n--- [End] ---\n"
    if max_chars < 1800:
        toc_cap = min(180, max(0, int(max_chars * 0.14))) if headings else 0
        toc = "\n".join(headings)[:toc_cap]
        overhead = len(hdr) + len(toc) + len("\n\n--- [Begin] ---\n") + len(sep_mid)
        rem = max(80, max_chars - overhead)
        head_cap = rem // 2
        tail_cap = rem - head_cap
    else:
        toc = "\n".join(headings)[:max(300, int(max_chars * 0.14))]
        head_cap, tail_cap = max(600, int(max_chars * 0.35)), max(800, int(max_chars * 0.43))
    out = f"{hdr}{toc}\n\n--- [Begin] ---\n{text[:head_cap]}{sep_mid}{text[-tail_cap:]}"
    return out if len(out) <= max_chars else out[:max_chars - 16] + "\n... [compacted]"


def _summarize_jsonl_line(raw_line: str) -> dict[str, Any]:
    """Parse a raw transcript.jsonl line into a compact, readable summary object."""
    try:
        entry = json.loads(raw_line)
        if not isinstance(entry, dict):
            return {"raw": raw_line[:300]}
        summary: dict[str, Any] = {
            "step_index": entry.get("step_index"),
            "type": entry.get("type") or entry.get("role") or "EVENT",
            "status": entry.get("status", ""),
            "created_at": entry.get("created_at", ""),
        }
        content = str(entry.get("content") or entry.get("text") or "").strip()
        if content:
            summary["content_preview"] = content[:350]
        tool_calls = entry.get("tool_calls")
        if isinstance(tool_calls, list) and tool_calls:
            summary["tools"] = [str(tc.get("name") or tc.get("toolAction") or "call") for tc in tool_calls[:5] if isinstance(tc, dict)]
        return summary
    except Exception:
        return {"raw": raw_line[:300]}


WIRE_INNER_CAP_BYTES = int(os.getenv("WIRE_INNER_CAP_BYTES", "18500"))
WIRE_ESCAPED_CAP_BYTES = int(os.getenv("WIRE_ESCAPED_CAP_BYTES", "19800"))


def within_wire_budget(
    raw_text: str,
    max_raw_bytes: int = WIRE_INNER_CAP_BYTES,
    max_escaped_bytes: int = WIRE_ESCAPED_CAP_BYTES,
) -> bool:
    """Return True when raw_text stays under both inner UTF-8 and JSON-RPC escaped outer wire caps."""
    if len(raw_text.encode("utf-8")) > max_raw_bytes:
        return False
    return len(json.dumps(raw_text, ensure_ascii=False).encode("utf-8")) <= max_escaped_bytes


def _wire_excess_bytes(raw_text: str, max_raw_bytes: int, max_escaped_bytes: int) -> int:
    raw_over = len(raw_text.encode("utf-8")) - max_raw_bytes
    esc_over = len(json.dumps(raw_text, ensure_ascii=False).encode("utf-8")) - max_escaped_bytes
    return max(raw_over, esc_over)


def _trim_drift_repos(repos: list[Any], max_repos: int, max_files: int) -> list[Any]:
    out: list[Any] = []
    txt_cap = max(120, max_files * 80)
    for r in repos[:max_repos]:
        if not isinstance(r, dict):
            out.append(r)
            continue
        item = dict(r)
        for lk in ("modified_files", "untracked_files", "changed_files", "files"):
            if isinstance(item.get(lk), list) and len(item[lk]) > max_files:
                item[lk] = item[lk][:max_files] + [f"... (+{len(item[lk]) - max_files})"]
        for sk in ("status_short", "diff_stat"):
            if isinstance(item.get(sk), str) and len(item[sk]) > txt_cap:
                item[sk] = item[sk][:txt_cap] + "\n... [compacted]"
        out.append(item)
    return out


def _shrink_aux_fields_step(payload: dict[str, Any]) -> bool:
    insp = payload.get("inspected_item")
    if isinstance(insp, dict) and isinstance(insp.get("content"), str) and len(insp["content"]) > 240:
        insp["content"] = insp["content"][: max(120, len(insp["content"]) // 2)] + "\n... [compacted]"
        insp["truncated"] = True
        return True
    for list_k, lim_n in (("skills", 10), ("plugin_skill_bundles", 8), ("agents", 8), ("transcript_tail", 6), ("sessions", 6), ("top_workspaces", 5), ("subagent_list", 6)):
        if isinstance(payload.get(list_k), list) and len(payload[list_k]) > lim_n:
            payload[list_k] = payload[list_k][:lim_n]
            return True
    for drop_k in ("top_session_detail", "search_results", "available_projects", "projects", "rules_inventory", "wire_telemetry", "modular_hygiene", "code_health", "quota_and_pools", "model_drift_status", "billing_comparison"):
        if drop_k in payload and payload[drop_k]:
            payload.pop(drop_k, None)
            return True
    for txt_k in ("ascii_mobile_report", "ascii_tree", "diff_stat", "status_short"):
        if isinstance(payload.get(txt_k), str) and len(payload[txt_k]) > 350:
            payload[txt_k] = payload[txt_k][:260] + "\n... [compacted]"
            return True
    return False


def _shrink_file_details_step(file_details: dict[str, Any], excess_bytes: int) -> bool:
    files_arr = (
        file_details.get("files")
        if isinstance(file_details.get("files"), list)
        else ([file_details] if any(k in file_details for k in ("content", "polyglot_outline", "existing_files_in_parent")) else [])
    )
    if not files_arr:
        return False
    for f_item in files_arr:
        if isinstance(f_item, dict) and f_item.pop("existing_files_in_parent", None):
            return True
    suffix = "\n... [compacted for <20KB wire cap — use start_line/end_line]"
    longest = max(
        (f for f in files_arr if isinstance(f, dict) and isinstance(f.get("content"), str) and not str(f.get("content")).startswith("[omitted for <20KB")),
        key=lambda f: len(str(f.get("content", ""))),
        default=None,
    )
    if longest is not None and len(str(longest.get("content", ""))) > 120:
        cur_c = str(longest["content"])
        cut = max(excess_bytes, 900, len(cur_c) // 3)
        new_len = max(0, len(cur_c) - cut)
        longest["content"] = (cur_c[:new_len] + suffix) if new_len >= 120 else "[omitted for <20KB wire cap — read fewer files or use start_line/end_line]"
        longest["truncated"] = True
        return True
    for f_item in files_arr:
        if not isinstance(f_item, dict):
            continue
        pol = f_item.get("polyglot_outline")
        if isinstance(pol, dict):
            syms = pol.get("symbols")
            if isinstance(syms, list) and len(syms) > 6:
                pol["symbols"] = syms[:6] + ["... [compacted]"]
                return True
            f_item.pop("polyglot_outline", None)
            return True
    if isinstance(file_details.get("files"), list) and len(file_details["files"]) > 2:
        file_details["files"].pop()
        file_details["wire_compacted_files_omitted"] = int(file_details.get("wire_compacted_files_omitted") or 0) + 1
        return True
    return False


def compact_payload_to_wire_budget(
    payload: dict[str, Any],
    serializer: Any = None,
    max_raw_bytes: int = WIRE_INNER_CAP_BYTES,
    max_escaped_bytes: int = WIRE_ESCAPED_CAP_BYTES,
) -> str:
    """Progressively trim secondary search lists, drift repos, diffs, and batched slices until payload fits <20KB wire limits."""
    ser = serializer or (lambda obj: json.dumps(obj, separators=(",", ":"), ensure_ascii=False))
    out_str = ser(payload)
    if within_wire_budget(out_str, max_raw_bytes, max_escaped_bytes):
        return out_str
    trim_stages: tuple[tuple[str, int], ...] = (
        ("historical_session_matches", 2), ("historical_session_matches", 0),
        ("symbol_callers", 2), ("symbol_callers", 0),
        ("polyglot_symbol_matches", 4), ("polyglot_symbol_matches", 0),
        ("code_search_matches", 8), ("code_search_matches", 3), ("code_search_matches", 0),
        ("pinned_session_matches", 4), ("pinned_session_matches", 1), ("pinned_session_matches", 0),
        ("untracked_files", 20), ("untracked_files", 5), ("untracked_files", 0),
        ("available_repositories", 0), ("configured_mcp_servers", 0),
        ("verified_urls", 6), ("verified_urls", 3), ("verified_urls", 0),
    )
    for key, keep in trim_stages:
        if within_wire_budget(out_str, max_raw_bytes, max_escaped_bytes):
            return out_str
        val = payload.get(key)
        if not val:
            continue
        payload.pop(key, None) if keep <= 0 else (payload.__setitem__(key, val[:keep]) if isinstance(val, list) and len(val) > keep else None)
        out_str = ser(payload)
    for rkey in ("repositories", "repos"):
        if not within_wire_budget(out_str, max_raw_bytes, max_escaped_bytes) and isinstance(payload.get(rkey), list):
            for r_cap, f_cap in ((20, 4), (10, 2), (6, 0), (3, 0)):
                payload[rkey] = _trim_drift_repos(payload[rkey], r_cap, f_cap)
                payload["repos_wire_compacted"] = True
                out_str = ser(payload)
                if within_wire_budget(out_str, max_raw_bytes, max_escaped_bytes):
                    return out_str
    if not within_wire_budget(out_str, max_raw_bytes, max_escaped_bytes) and isinstance(payload.get("diff"), str):
        for _ in range(10):
            ex = _wire_excess_bytes(out_str, max_raw_bytes, max_escaped_bytes)
            if ex <= 0 or not payload.get("diff"):
                break
            d_txt = str(payload["diff"])
            keep_d = max(0, len(d_txt) - max(ex, 1200, len(d_txt) // 3))
            payload["diff"] = d_txt[:keep_d] + ("\n... [diff compacted for <20KB wire cap — pass file_path or offset_chars]" if keep_d > 0 else "")
            payload["diff_truncated"] = True
            out_str = ser(payload)
    for _ in range(48):
        ex = _wire_excess_bytes(out_str, max_raw_bytes, max_escaped_bytes)
        if ex <= 0:
            break
        fd = payload.get("file_details")
        if isinstance(fd, dict) and _shrink_file_details_step(fd, ex):
            out_str = ser(payload)
            continue
        if _shrink_aux_fields_step(payload):
            out_str = ser(payload)
            continue
        break
    if not within_wire_budget(out_str, max_raw_bytes, max_escaped_bytes):
        payload.pop("assistant_guidance", None)
        payload.pop("selected_session_status", None)
        payload["wire_compacted"] = True
        out_str = ser(payload)
    return out_str


def resolve_package_resource_dir(dirname: str, anchor_file: str | Path | None = None) -> Path:
    """Resolve repo/wheel bundled directories (e.g. 'agents', 'web') across source-tree and site-packages installs."""
    base = Path(anchor_file).resolve() if anchor_file else Path(__file__).resolve()
    candidates: list[Path] = []
    if len(base.parents) >= 3:
        candidates.append(base.parents[2] / dirname)
    if len(base.parents) >= 2:
        candidates.append(base.parents[1] / dirname)
    candidates.append(Path.cwd() / dirname)
    candidates.append(Path("/app") / dirname)
    for cand in candidates:
        if cand.is_dir():
            return cand
    return candidates[0]


def resolve_package_root(pkg_dir: Path | None = None) -> Path:
    """Resolve package root containing src/ or installed site-packages resources."""
    pdir = (pkg_dir or Path(__file__).resolve().parent).resolve()
    if len(pdir.parents) >= 2:
        src_root = pdir.parents[1]
        if (src_root / "web").is_dir() or (src_root / "agents").is_dir():
            return src_root
    if len(pdir.parents) >= 1:
        wheel_root = pdir.parents[0]
        if (wheel_root / "web").is_dir() or (wheel_root / "agents").is_dir():
            return wheel_root
    return pdir.parents[1] if len(pdir.parents) >= 2 else pdir


def resolve_source_repo_root(anchor_file: str | Path | None = None) -> Path | None:
    """Resolve verified source checkout root containing src/agy_nexus/ and pyproject.toml, or None if wheel-only."""
    base = Path(anchor_file).resolve() if anchor_file else Path(__file__).resolve()
    candidates: list[Path] = []
    if len(base.parents) >= 3:
        candidates.append(base.parents[2])
    candidates.extend([Path.cwd().resolve(), Path("/app")])
    for cand in candidates:
        if (cand / "src" / "agy_nexus").is_dir() and (cand / "pyproject.toml").is_file():
            return cand
    return None


