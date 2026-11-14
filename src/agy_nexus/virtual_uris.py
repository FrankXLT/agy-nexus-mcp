#!/usr/bin/env python3
"""
agy_nexus.virtual_uris — Virtual URI Resolver for Untruncated Transcripts, Brain Scratch, Telemetry & Polyglot.

Resolves synthetic read-only URIs inside `ask_workspace_readonly` and `load_session_into_gemini`:
- `transcript:latest`, `transcript:turn:<offset>`, `transcript:step:<N>` (from `transcript_full.jsonl` with <=140-char line wrapping)
- `brain:<subpath>` and `brain:<conv_id>/<subpath>` (nested session artifacts & upload batches)
- `telemetry:stats[:<period>[:<style>]]`, `telemetry:quota`, `telemetry:wire`, `telemetry:export_notebook`
- `polyglot:map[:<path_prefix>]`, `polyglot:search:<query>`
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import textwrap
from typing import Any

from agy_nexus.config import AGY_BG_DIR, AGY_BRAIN_DIR, AGY_CONFIG_DIR, AGY_DATA_DIR, SESSION_STATE
from agy_nexus.hygiene import slice_file_content


def wrap_long_lines(text: str, max_col: int = 136) -> str:
    """Wrap ultra-long lines (> max_col) so line-based pagination (start_line/end_line) works on JSONL turns."""
    if not text:
        return ""
    wrapped: list[str] = []
    for raw_line in text.splitlines():
        if len(raw_line) <= max_col:
            wrapped.append(raw_line)
        else:
            chunks = textwrap.wrap(
                raw_line,
                width=max_col,
                break_long_words=True,
                break_on_hyphens=False,
                replace_whitespace=False,
                drop_whitespace=False,
            )
            wrapped.extend(chunks or [raw_line[:max_col]])
    return "\n".join(wrapped)


def resolve_transcript_file(session_dir: Path | None) -> Path | None:
    """Prefer untruncated transcript_full.jsonl over pre-truncated transcript.jsonl."""
    if not session_dir or not session_dir.is_dir():
        return None
    logs_dir = session_dir / ".system_generated" / "logs"
    full_p = logs_dir / "transcript_full.jsonl"
    if full_p.is_file():
        return full_p
    comp_p = logs_dir / "transcript.jsonl"
    return comp_p if comp_p.is_file() else None


def resolve_brain_uri_path(raw_uri: str, default_session_dir: Path | None) -> tuple[Path | None, str]:
    """Resolve `brain:<subpath>` or `brain:<conv_id>/<subpath>` strictly inside AGY_BRAIN_DIR/<conv_id>."""
    m = re.match(r"^brain:(.*)$", (raw_uri or "").strip(), flags=re.IGNORECASE)
    if not m:
        return None, ""
    rest = m.group(1).strip().lstrip("/")
    if not rest:
        return None, "Empty brain: URI subpath."

    brain_root = AGY_BRAIN_DIR.resolve()
    parts = [p for p in rest.replace("\\", "/").split("/") if p]
    if not parts or ".." in parts:
        return None, "Invalid traversal in brain: URI."

    target_sdir: Path | None = None
    rel_parts = parts
    first_clean = re.sub(r"[^a-zA-Z0-9_-]", "", parts[0])
    if first_clean and first_clean == parts[0] and len(first_clean) >= 32:
        cand_sdir = (AGY_BRAIN_DIR / first_clean).resolve()
        if cand_sdir != brain_root and cand_sdir.is_relative_to(brain_root) and cand_sdir.is_dir():
            target_sdir = cand_sdir
            rel_parts = parts[1:]

    if target_sdir is None:
        if default_session_dir and default_session_dir.is_dir():
            cand_def = default_session_dir.resolve()
            if cand_def != brain_root and cand_def.is_relative_to(brain_root):
                target_sdir = cand_def
        if target_sdir is None:
            sel_cid = re.sub(r"[^a-zA-Z0-9_-]", "", str(SESSION_STATE.get("selected_session") or ""))
            if sel_cid:
                cand_sel = (AGY_BRAIN_DIR / sel_cid).resolve()
                if cand_sel != brain_root and cand_sel.is_relative_to(brain_root) and cand_sel.is_dir():
                    target_sdir = cand_sel

    if target_sdir is None or not rel_parts:
        return None, f"Active session directory unavailable for '{raw_uri}'."

    norm_rel = os.path.normpath("/".join(rel_parts)).lstrip("/")
    for probe in (target_sdir / norm_rel, target_sdir / "scratch" / norm_rel):
        resolved = probe.resolve()
        if resolved != target_sdir and resolved.is_relative_to(target_sdir) and resolved.is_file():
            return resolved, ""

    fallback = (target_sdir / norm_rel).resolve()
    if fallback != target_sdir and fallback.is_relative_to(target_sdir):
        return fallback, f"File not found in session brain directory: {norm_rel}"
    return None, f"Access denied outside session brain directory: {raw_uri}"


def _format_transcript_entry(entry: dict[str, Any]) -> str:
    step = entry.get("step_index", "?")
    etype = entry.get("type") or entry.get("role") or "EVENT"
    ts = entry.get("created_at", "")
    content = str(entry.get("content") or entry.get("text") or "").strip()
    thinking = str(entry.get("thinking") or "").strip()
    tcalls = entry.get("tool_calls") or []
    parts = [f"# Transcript Step {step} ({etype}) — {ts}"]
    if content:
        parts.append(content)
    if tcalls and isinstance(tcalls, list):
        tc_lines = [
            f"- `{tc.get('name', 'tool')}`: {tc.get('args', {}).get('toolSummary') or tc.get('toolAction') or ''}"
            for tc in tcalls[:12] if isinstance(tc, dict)
        ]
        if tc_lines:
            parts.append("## Tool Calls\n" + "\n".join(tc_lines))
    if thinking and not content:
        parts.append("## Thinking\n" + thinking)
    return wrap_long_lines("\n\n".join(parts), max_col=136)


def _resolve_transcript_virtual(spec: str, session_dir: Path | None) -> tuple[str, str]:
    tpath = resolve_transcript_file(session_dir)
    if not tpath:
        return "", "Transcript log file not found for active/pinned session."

    entries: list[dict[str, Any]] = []
    try:
        with tpath.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        entries.append(obj)
                except Exception:
                    continue
    except Exception as exc:
        return "", f"Failed reading {tpath.name}: {exc}"

    if not entries:
        return "", f"Transcript {tpath.name} is empty."

    sub = spec.strip().lower()
    if sub.startswith("step:"):
        try:
            want_step = int(sub.split(":", 1)[1].strip())
        except ValueError:
            return "", f"Invalid step index in 'transcript:{spec}'."
        hit = next((e for e in entries if e.get("step_index") == want_step), None)
        if not hit:
            return "", f"Step {want_step} not found in {tpath.name} (max step: {entries[-1].get('step_index')})."
        return _format_transcript_entry(hit), str(tpath)

    turns = [
        e for e in entries
        if (e.get("type") or e.get("role")) in ("USER_INPUT", "user", "PLANNER_RESPONSE", "assistant", "model")
        and (str(e.get("content") or e.get("text") or "").strip() or e.get("tool_calls"))
    ]
    if not turns:
        return "", f"No conversational turns found in {tpath.name}."
    assistant_with_text = [
        e for e in turns
        if (e.get("type") or e.get("role")) in ("PLANNER_RESPONSE", "assistant", "model")
        and str(e.get("content") or e.get("text") or "").strip()
    ]

    if sub in ("", "latest", "last", "assistant"):
        chosen = assistant_with_text[-1] if assistant_with_text else turns[-1]
        return _format_transcript_entry(chosen), str(tpath)

    if sub.startswith("turn:"):
        try:
            off = abs(int(sub.split(":", 1)[1].strip()))
        except ValueError:
            off = 0
        pool = assistant_with_text or turns
        idx = max(0, len(pool) - 1 - off)
        return _format_transcript_entry(pool[idx]), str(tpath)

    recent_slice = turns[-10:]
    joined = "\n\n---\n\n".join(_format_transcript_entry(e) for e in recent_slice)
    return joined, str(tpath)


def _resolve_telemetry_virtual(spec: str, session_dir: Path | None) -> tuple[str, str]:
    from agy_nexus.config import AGY_DB_FILE
    from agy_nexus.sessions import _load_projects_map
    from agy_nexus.stats import (
        build_nexus_stats_bundle,
        get_live_quota_and_pool_status,
        get_wire_telemetry_summary,
    )
    from agy_nexus.workflows import export_notebook_bundle

    parts = [p.strip() for p in spec.split(":") if p.strip()]
    kind = (parts[0] if parts else "stats").lower()
    if kind in ("stats", "heatmap", "activity"):
        period = parts[1] if len(parts) >= 2 else "last_90d"
        style = parts[2] if len(parts) >= 3 else "default"
        bundle = build_nexus_stats_bundle(
            data_dir=AGY_DATA_DIR,
            brain_dir=AGY_BRAIN_DIR,
            db_file=AGY_DB_FILE,
            config_dir=AGY_CONFIG_DIR,
            bg_dir=AGY_BG_DIR,
            period=period,
            style=style,
        )
        ascii_rep = str(bundle.get("ascii_mobile_report") or "")
        meta = json.dumps({
            "period_key": bundle.get("period_key"),
            "totals": bundle.get("totals"),
            "quota_and_pools": bundle.get("quota_and_pools"),
        }, indent=2)
        return f"{ascii_rep}\n\n```json\n{meta}\n```", f"virtual://telemetry/{spec or 'stats'}"
    if kind in ("quota", "pools"):
        q = get_live_quota_and_pool_status(AGY_DATA_DIR, AGY_CONFIG_DIR)
        return json.dumps(q, indent=2), "virtual://telemetry/quota"
    if kind in ("wire", "logs"):
        w = get_wire_telemetry_summary(AGY_BG_DIR, limit=25)
        return json.dumps(w, indent=2), "virtual://telemetry/wire"
    if kind in ("export_notebook", "notebook"):
        nb = export_notebook_bundle(
            brain_dir=AGY_BRAIN_DIR,
            db_file=AGY_DB_FILE,
            bg_dir=AGY_BG_DIR,
            projects_map=_load_projects_map(),
            dry_run=True,
        )
        return json.dumps(nb, indent=2), "virtual://telemetry/export_notebook"
    return "", f"Unknown telemetry virtual URI 'telemetry:{spec}'."


def resolve_virtual_uri_entry(
    raw_sub: str,
    ws: Path,
    session_dir: Path | None,
    per_file_cap: int,
    start_line: int = 0,
    end_line: int = 0,
    in_start: int = 0,
    in_end: int = 0,
    in_center: int = 0,
) -> dict[str, Any] | None:
    """Resolve `transcript:*`, `telemetry:*`, or `polyglot:*` virtual URIs into sliced file payloads."""
    cleaned = raw_sub.strip()
    m = re.match(r"^(transcript|telemetry|polyglot|praxis):(.*)$", cleaned, flags=re.IGNORECASE)
    if not m:
        return None
    scheme = m.group(1).lower()
    rest_raw = m.group(2).strip()
    # Strip optional trailing :start-end inline range ONLY when the prefix isn't a multi-part scheme token
    rest_clean = rest_raw
    if in_start > 0 or in_end > 0:
        rest_clean = re.sub(r":\d+-\d+$", "", rest_raw)
    elif in_center > 0 and scheme == "transcript" and not re.match(r"^(?:step|turn):\d+$", rest_raw, flags=re.I):
        rest_clean = re.sub(r":\d+$", "", rest_raw)

    if scheme == "transcript":
        text, src_path = _resolve_transcript_virtual(rest_clean, session_dir)
        if not text:
            return {"requested": raw_sub, "error": src_path}
    elif scheme == "telemetry":
        text, src_path = _resolve_telemetry_virtual(rest_clean, session_dir)
        if not text:
            return {"requested": raw_sub, "error": src_path}
    elif rest_clean.lower().startswith("handoff"):
        import agy_nexus.config as cfg
        from agy_nexus.handoff_queue import list_handoff_tickets
        sub_arg = rest_clean.split(":", 1)[1].strip() if ":" in rest_clean else ""
        if sub_arg.lower() in ("all", "*"):
            res = list_handoff_tickets(cfg.AGY_BG_DIR, limit=30)
        elif sub_arg:
            res = list_handoff_tickets(cfg.AGY_BG_DIR, repo_slug=sub_arg, limit=30)
        else:
            res = list_handoff_tickets(cfg.AGY_BG_DIR, workspace=str(ws), limit=30)
        text = json.dumps(res, indent=2)
        src_path = f"virtual://praxis/handoffs/{sub_arg or ws.name}"
    else:
        from agy_nexus.polyglot_index import polyglot_repo_map, polyglot_symbol_search
        if rest_clean.lower().startswith("search:"):
            q = rest_clean.split(":", 1)[1].strip()
            res = polyglot_symbol_search(q, workspace=str(ws), limit=30)
            text = json.dumps(res, indent=2)
            src_path = f"virtual://{scheme}/search/{q}"
        else:
            pfx = rest_clean.split(":", 1)[1].strip() if rest_clean.lower().startswith("map:") else ("" if rest_clean.lower() in ("", "map") else rest_clean)
            res = polyglot_repo_map(workspace=str(ws), path_prefix=pfx, limit=120)
            text = str(res.get("formatted_map") or json.dumps(res, indent=2))
            src_path = f"virtual://{scheme}/map/{pfx}"

    use_in_start = 0 if (scheme == "transcript" and re.match(r"^(?:step|turn):\d+$", rest_raw, flags=re.I)) else in_start
    use_in_center = 0 if (scheme == "transcript" and re.match(r"^(?:step|turn):\d+$", rest_raw, flags=re.I)) else in_center
    slice_meta = slice_file_content(
        full_text=text,
        clean_path=f"{scheme}:{rest_clean}" if rest_clean else f"{scheme}:latest",
        per_file_cap=per_file_cap,
        explicit_start_line=start_line,
        explicit_end_line=end_line,
        inline_start_line=use_in_start,
        inline_end_line=in_end,
        center_line=use_in_center,
    )
    slice_meta.pop("modularity_advisory", None)
    return {
        "requested": raw_sub,
        "path": src_path,
        "mode": f"virtual_{scheme}",
        "bytes": len(text.encode("utf-8")),
        **slice_meta,
    }
