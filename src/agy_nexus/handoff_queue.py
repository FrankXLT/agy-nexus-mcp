#!/usr/bin/env python3
"""agy_nexus.handoff_queue — Repo-Prefixed Incremental Handoff Queue & Pass-Off Registry.

Manages collision-free staged handoff tickets (`<repo-slug>-01`, `<repo-slug>-02`, ...)
under `sidecar_data/ag-bridge-bg/staged_handoffs/` with `fcntl.flock` atomic locking
and explicit lifecycle states: `STAGED` (unclaimed), `IN_WORK`, `SUPERSEDED`, `COMPLETED`.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
from typing import Any, Iterator

VALID_HANDOFF_STATES = ("STAGED", "IN_WORK", "SUPERSEDED", "COMPLETED")
STATE_DISPLAY_LABELS = {
    "STAGED": "STAGED · UNCLAIMED",
    "IN_WORK": "IN-WORK",
    "SUPERSEDED": "SUPERSEDED",
    "COMPLETED": "COMPLETED",
}


def slugify_token(value: str, fallback: str = "general", max_len: int = 36) -> str:
    """Convert a repository, project, or title string into a clean lowercase slug."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return (cleaned[:max_len].rstrip("-") if cleaned else fallback) or fallback


def normalize_repo_slug(
    workspace_path: str = "",
    project_name: str = "",
    repo_hint: str = "",
    umbrella_roots: set[Path] | None = None,
) -> str:
    """Derive canonical repository slug for `<repo-slug>-NN` ticket numbering."""
    ws_clean = (workspace_path or "").strip().rstrip("/")
    if ws_clean:
        p = Path(ws_clean)
        try:
            resolved = p.resolve()
        except OSError:
            resolved = p
        if not umbrella_roots or resolved not in umbrella_roots:
            if p.name and not p.name.startswith("."):
                return slugify_token(p.name, "general", 36)
    if (repo_hint or "").strip():
        return slugify_token(repo_hint, "general", 36)
    if (project_name or "").strip():
        return slugify_token(project_name, "general", 36)
    return "general"


def canonicalize_handoff_id(raw_id: str) -> str:
    """Normalize `<repo>-1` and `<repo>-01` into canonical `<repo>-01` lowercase form."""
    s = (raw_id or "").strip().lower()
    if s.startswith("resume_staged:"):
        s = s.split(":", 1)[1].strip()
    m = re.match(r"^([a-z0-9][a-z0-9_-]*?)-(\d+)$", s)
    if not m:
        return ""
    slug = slugify_token(m.group(1), "general", 36)
    num = int(m.group(2))
    return f"{slug}-{num:02d}" if num < 100 else f"{slug}-{num}"


def _queue_dir(bg_dir: Path) -> Path:
    q_dir = bg_dir / "staged_handoffs"
    q_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(q_dir, 0o700)
    except OSError:
        pass
    return q_dir


@contextmanager
def _locked_index(bg_dir: Path) -> Iterator[tuple[Path, dict[str, Any]]]:
    """Acquire exclusive flock on staged_handoffs/index.lock, yield (q_dir, doc), and persist changes."""
    q_dir = _queue_dir(bg_dir)
    lock_path = q_dir / "index.lock"
    idx_path = q_dir / "index.json"
    with lock_path.open("a+", encoding="utf-8") as lf:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        try:
            doc: dict[str, Any] = {"version": 1, "counters": {}, "tickets": []}
            if idx_path.is_file():
                try:
                    loaded = json.loads(idx_path.read_text(encoding="utf-8", errors="replace"))
                    if isinstance(loaded, dict):
                        doc["counters"] = dict(loaded.get("counters") or {})
                        doc["tickets"] = list(loaded.get("tickets") or [])
                except Exception:
                    pass
            yield q_dir, doc
            _write_mode_600(idx_path, json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        finally:
            fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


def _read_index_unlocked(bg_dir: Path) -> dict[str, Any]:
    idx_path = bg_dir / "staged_handoffs" / "index.json"
    if not idx_path.is_file():
        return {"version": 1, "counters": {}, "tickets": []}
    try:
        loaded = json.loads(idx_path.read_text(encoding="utf-8", errors="replace"))
        if isinstance(loaded, dict):
            return {
                "version": 1,
                "counters": dict(loaded.get("counters") or {}),
                "tickets": list(loaded.get("tickets") or []),
            }
    except Exception:
        pass
    return {"version": 1, "counters": {}, "tickets": []}


def _decorate_ticket(t: dict[str, Any], now_utc: datetime | None = None) -> dict[str, Any]:
    """Attach computed display badges and relative age onto a ticket copy."""
    out = dict(t)
    st = str(out.get("status") or "STAGED").upper()
    out["status"] = st
    out["is_unclaimed"] = st == "STAGED"
    out["status_label"] = STATE_DISPLAY_LABELS.get(st, st)
    now_ref = now_utc or datetime.now(timezone.utc)
    ts_str = str(out.get("updated_at") or out.get("created_at") or "")
    age = ""
    if ts_str:
        try:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            sec = max(0, int((now_ref - dt).total_seconds()))
            age = f"{sec}s ago" if sec < 60 else (f"{sec // 60}m ago" if sec < 3600 else (f"{sec // 3600}h ago" if sec < 86400 else f"{sec // 86400}d ago"))
        except Exception:
            age = ""
    out["relative_age"] = age
    return out


def _prune_old_tickets(q_dir: Path, tickets: list[dict[str, Any]], max_closed: int = 80) -> list[dict[str, Any]]:
    """Keep all STAGED/IN_WORK tickets and bound historical SUPERSEDED/COMPLETED entries."""
    active = [t for t in tickets if str(t.get("status") or "").upper() in ("STAGED", "IN_WORK")]
    closed = [t for t in tickets if str(t.get("status") or "").upper() not in ("STAGED", "IN_WORK")]
    if len(closed) <= max_closed:
        return tickets
    closed.sort(key=lambda x: str(x.get("updated_at") or x.get("created_at") or ""), reverse=True)
    keep_closed = closed[:max_closed]
    drop_closed = closed[max_closed:]
    for d in drop_closed:
        fp = str(d.get("handoff_file") or "")
        if fp:
            p = Path(fp)
            if p.is_file() and p.parent == q_dir:
                try:
                    p.unlink()
                except OSError:
                    pass
    keep_ids = {str(x.get("handoff_id")) for x in (active + keep_closed)}
    return [t for t in tickets if str(t.get("handoff_id")) in keep_ids]


def _write_mode_600(path: Path, text: str) -> None:
    """Atomically write UTF-8 text via a 0600 sibling temp file and POSIX rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".{path.name}.{os.getpid()}.tmp"
    fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        try:
            os.chmod(tmp_path, 0o600)
        except OSError:
            pass
        tmp_path.replace(path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _supersede_matching_tickets(
    tickets: list[dict[str, Any]], clean_slug: str, sup_target: str, target_conv: str, topic_slug: str, new_id: str, ts_iso: str
) -> list[str]:
    superseded_ids: list[str] = []
    for t in tickets:
        if str(t.get("status") or "").upper() != "STAGED" or t.get("repo_slug") != clean_slug:
            continue
        if (sup_target and t.get("handoff_id") == sup_target) or (target_conv and t.get("target_conversation_id") == target_conv) or (topic_slug and t.get("topic_slug") == topic_slug):
            t.update({"status": "SUPERSEDED", "superseded_by": new_id, "superseded_at": ts_iso, "updated_at": ts_iso})
            superseded_ids.append(str(t.get("handoff_id")))
    return superseded_ids


def record_handoff_ticket(
    bg_dir: Path, *, full_markdown: str, chars_written: int, repo_slug: str, title: str,
    project_id: str = "", project_name: str = "", workspace_path: str = "", target_conversation_id: str = "",
    rollover_from: str = "", execution_mode: str = "plan", handoff_mode: str = "intent",
    allow_chained_publish: bool = False, initial_status: str = "STAGED", claimed_by_conversation_id: str = "",
    job_id: str = "", supersede_handoff_id: str = "", append_to_existing: bool = False,
) -> dict[str, Any]:
    """Atomically mint `<repo-slug>-NN` (or append), auto-supersede matching unclaimed tickets, and write file."""
    ts_iso = datetime.now(timezone.utc).isoformat()
    clean_slug = slugify_token(repo_slug, "general", 36)
    title_clean = (title or "Gemini Research Handoff").strip()[:120]
    topic_slug = slugify_token(title_clean, "handoff", 32)
    sup_target = canonicalize_handoff_id(supersede_handoff_id)
    eff_status = initial_status.upper() if initial_status.upper() in VALID_HANDOFF_STATES else "STAGED"

    with _locked_index(bg_dir) as (q_dir, doc):
        tickets, counters = doc["tickets"], doc["counters"]
        if append_to_existing:
            for ex in reversed(tickets):
                if str(ex.get("status")) == "STAGED" and ex.get("repo_slug") == clean_slug and (not sup_target or ex.get("handoff_id") == sup_target):
                    _write_mode_600(Path(str(ex.get("handoff_file") or "")), full_markdown)
                    ex["chars_written"], ex["updated_at"] = int(ex.get("chars_written") or 0) + chars_written, ts_iso
                    if eff_status == "IN_WORK":
                        ex.update({"status": "IN_WORK", "claimed_at": ts_iso, "claimed_by_conversation_id": claimed_by_conversation_id or target_conversation_id, "job_id": job_id})
                    return _decorate_ticket(ex)

        next_num = int(counters.get(clean_slug) or 0) + 1
        counters[clean_slug] = next_num
        handoff_id = f"{clean_slug}-{next_num:02d}" if next_num < 100 else f"{clean_slug}-{next_num}"
        ticket_file = q_dir / f"{handoff_id}__{topic_slug}.md"
        superseded_ids = _supersede_matching_tickets(tickets, clean_slug, sup_target, target_conversation_id, topic_slug, handoff_id, ts_iso)

        env_line = (
            f"<!-- Handoff-ID: {handoff_id} | Status: {eff_status} | Repo: {clean_slug} | Project: {project_name or clean_slug} "
            f"| Workspace: {workspace_path or '(auto)'} | Target-Session: {target_conversation_id or '(new-chat)'} | Rollover-From: {rollover_from or 'none'} -->\n"
        )
        hdr = "<!-- Handshake Gemini Research Handoff -->\n"
        _write_mode_600(ticket_file, full_markdown.replace(hdr, f"{hdr}{env_line}", 1) if hdr in full_markdown else (env_line + full_markdown))

        entry: dict[str, Any] = {
            "handoff_id": handoff_id, "sequence": next_num, "repo_slug": clean_slug, "topic_slug": topic_slug,
            "title": title_clean, "status": eff_status, "project_id": project_id, "project_name": project_name or clean_slug,
            "workspace_path": workspace_path, "target_conversation_id": target_conversation_id,
            "claimed_by_conversation_id": claimed_by_conversation_id or (target_conversation_id if eff_status == "IN_WORK" else ""),
            "rollover_from": rollover_from, "execution_mode": execution_mode, "handoff_mode": handoff_mode,
            "allow_chained_publish": allow_chained_publish, "chars_written": chars_written, "handoff_file": str(ticket_file),
            "job_id": job_id, "superseded_ids": superseded_ids, "superseded_by": "",
            "created_at": ts_iso, "updated_at": ts_iso, "claimed_at": ts_iso if eff_status == "IN_WORK" else "",
        }
        tickets.append(entry)
        doc["tickets"] = _prune_old_tickets(q_dir, tickets)
        return _decorate_ticket(entry)


def resolve_staged_ticket_for_resume(
    bg_dir: Path,
    *,
    handoff_id: str = "",
    conv_id: str = "",
    repo_slug: str = "",
    workspace_path: str = "",
) -> dict[str, Any] | None:
    """Locate a STAGED ticket for RESUME_STAGED without ever crossing repository boundaries."""
    doc = _read_index_unlocked(bg_dir)
    tickets = list(doc.get("tickets") or [])
    cid_norm = canonicalize_handoff_id(handoff_id)
    ws_clean = (workspace_path or "").strip().rstrip("/")
    slug_clean = slugify_token(repo_slug, "", 36) if repo_slug else ""
    if cid_norm:
        for t in reversed(tickets):
            if t.get("handoff_id") != cid_norm:
                continue
            if str(t.get("status") or "").upper() != "STAGED":
                return None
            if not Path(str(t.get("handoff_file") or "")).is_file():
                return None
            t_ws = str(t.get("workspace_path") or "").rstrip("/")
            if ws_clean and t_ws and t_ws != ws_clean:
                return None
            if slug_clean and slug_clean != "general" and t.get("repo_slug") != slug_clean:
                return None
            return _decorate_ticket(t)
        return None

    for t in reversed(tickets):
        if str(t.get("status") or "").upper() != "STAGED":
            continue
        if not Path(str(t.get("handoff_file") or "")).is_file():
            continue
        if conv_id and t.get("target_conversation_id") == conv_id:
            return _decorate_ticket(t)
        if ws_clean and str(t.get("workspace_path") or "").rstrip("/") == ws_clean:
            return _decorate_ticket(t)
        if slug_clean and t.get("repo_slug") == slug_clean:
            return _decorate_ticket(t)
    return None


def mark_ticket_status(
    bg_dir: Path,
    handoff_id: str,
    new_status: str,
    *,
    conversation_id: str = "",
    job_id: str = "",
    claim_method: str = "",
    notes: str = "",
) -> dict[str, Any] | None:
    """Transition an existing handoff ticket to IN_WORK, STAGED, SUPERSEDED, or COMPLETED."""
    cid_norm = canonicalize_handoff_id(handoff_id)
    if not cid_norm:
        return None
    st_up = new_status.strip().upper()
    if st_up not in VALID_HANDOFF_STATES:
        return None
    ts_iso = datetime.now(timezone.utc).isoformat()
    with _locked_index(bg_dir) as (_, doc):
        for t in doc["tickets"]:
            if t.get("handoff_id") == cid_norm:
                cur_st = str(t.get("status") or "STAGED").upper()
                if st_up == "SUPERSEDED" and cur_st in ("IN_WORK", "COMPLETED"):
                    return None
                t["status"] = st_up
                t["updated_at"] = ts_iso
                if notes:
                    t["notes"] = notes[:500]
                if st_up == "IN_WORK":
                    t["claimed_at"] = ts_iso
                    if conversation_id:
                        t["claimed_by_conversation_id"] = conversation_id
                    if job_id:
                        t["job_id"] = job_id
                    if claim_method:
                        t["claim_method"] = claim_method
                elif st_up == "STAGED":
                    t["claimed_by_conversation_id"] = ""
                    t["claimed_at"] = ""
                elif conversation_id and not t.get("claimed_by_conversation_id"):
                    t["claimed_by_conversation_id"] = conversation_id
                return _decorate_ticket(t)
    return None


def claim_handoff_for_ide(
    bg_dir: Path, brain_dir: Path, *, handoff_id: str = "", workspace: str = "", conversation_id: str = "", force: bool = False
) -> dict[str, Any]:
    """Claim a staged handoff ticket from Antigravity IDE (`agy-praxis-mcp`), disambiguating multiple items."""
    cid_norm = canonicalize_handoff_id(handoff_id)
    ws_clean = (workspace or "").strip().rstrip("/")
    ws_slug = normalize_repo_slug(workspace_path=ws_clean) if ws_clean else ""
    conv_clean = (conversation_id or "").strip()
    ts_iso = datetime.now(timezone.utc).isoformat()

    with _locked_index(bg_dir) as (_, doc):
        tickets: list[dict[str, Any]] = doc["tickets"]
        chosen: dict[str, Any] | None = None
        if cid_norm:
            chosen = next((t for t in reversed(tickets) if t.get("handoff_id") == cid_norm), None)
            if not chosen:
                return {"ok": False, "status": "NOT_FOUND", "error": f"Handoff ticket '{handoff_id}' was not found in staged_handoffs."}
            cur_st, cur_owner = str(chosen.get("status") or "STAGED").upper(), str(chosen.get("claimed_by_conversation_id") or "")
            if not force:
                if cur_st == "COMPLETED":
                    return {"ok": False, "status": "ALREADY_COMPLETED", "handoff_id": cid_norm, "message": f"Ticket {cid_norm} is already COMPLETED. Pass force=True to re-open."}
                if cur_st == "SUPERSEDED":
                    sup_by = str(chosen.get("superseded_by") or "")
                    return {"ok": False, "status": "SUPERSEDED", "handoff_id": cid_norm, "superseded_by": sup_by, "message": f"Ticket {cid_norm} was SUPERSEDED{f' by {sup_by}' if sup_by else ''}. Claim the newer ticket or pass force=True."}
                if cur_st == "IN_WORK" and (not conv_clean or (cur_owner and cur_owner != conv_clean)):
                    return {"ok": False, "status": "ALREADY_IN_WORK", "handoff_id": cid_norm, "claimed_by_conversation_id": cur_owner, "message": f"Ticket {cid_norm} is already IN-WORK{f' by session {cur_owner}' if cur_owner else ''}. Pass force=True to re-claim."}
        else:
            staged_all = [t for t in tickets if str(t.get("status") or "").upper() == "STAGED" and Path(str(t.get("handoff_file") or "")).is_file()]
            matched = [
                t for t in staged_all
                if (ws_clean and str(t.get("workspace_path") or "").rstrip("/") == ws_clean) or (ws_slug and ws_slug != "general" and t.get("repo_slug") == ws_slug)
            ] if ws_clean else staged_all
            if len(matched) > 1:
                cands = [_decorate_ticket(t) for t in reversed(matched)]
                return {
                    "ok": False, "status": "AMBIGUOUS_MULTIPLE_STAGED", "workspace": ws_clean,
                    "candidates": [{"handoff_id": c["handoff_id"], "title": c["title"], "handoff_mode": c["handoff_mode"], "execution_mode": c["execution_mode"], "relative_age": c["relative_age"]} for c in cands],
                    "message": f"Found {len(cands)} unclaimed STAGED handoffs for '{ws_slug or 'workspace'}'. Ask the user which handoff_id to run and call praxis_claim_handoff(handoff_id=...).",
                }
            if len(matched) == 1:
                chosen = matched[0]
            else:
                other_unclaimed = [_decorate_ticket(t) for t in reversed(staged_all)]
                return {
                    "ok": False, "status": "NONE_STAGED", "workspace": ws_clean,
                    "other_workspaces_staged": [{"handoff_id": c["handoff_id"], "repo_slug": c["repo_slug"], "title": c["title"], "relative_age": c["relative_age"]} for c in other_unclaimed[:10]],
                    "message": f"No unclaimed STAGED handoffs found for '{ws_slug or ws_clean or 'current workspace'}'.",
                }

        fp = Path(str(chosen.get("handoff_file") or ""))
        if not fp.is_file():
            return {"ok": False, "status": "MISSING_FILE", "error": f"Handoff markdown file missing at {fp}."}
        chosen.update({"status": "IN_WORK", "claimed_at": ts_iso, "updated_at": ts_iso, "claim_method": "praxis_ide"})
        if conv_clean:
            chosen["claimed_by_conversation_id"] = conv_clean
        content = fp.read_text(encoding="utf-8", errors="replace")
        copied_to = ""
        if conv_clean and re.match(r"^[0-9a-fA-F-]{8,64}$", conv_clean):
            s_dir = brain_dir / conv_clean / "scratch"
            s_dir.mkdir(parents=True, exist_ok=True)
            dst = s_dir / "gemini_research_handoff.md"
            _write_mode_600(dst, content)
            copied_to = str(dst)
        dec = _decorate_ticket(chosen)
        return {"ok": True, "status": "CLAIMED", "ticket": dec, "handoff_id": dec["handoff_id"], "copied_to_session_scratch": copied_to, "markdown": content}


def list_handoff_tickets(
    bg_dir: Path,
    *,
    workspace: str = "",
    status_filter: str = "ALL",
    include_superseded: bool = True,
    limit: int = 50,
) -> dict[str, Any]:
    """List staged, in-work, and superseded handoff tickets with workspace prioritization."""
    doc = _read_index_unlocked(bg_dir)
    now_utc = datetime.now(timezone.utc)
    ws_clean = (workspace or "").strip().rstrip("/")
    ws_slug = normalize_repo_slug(workspace_path=ws_clean) if ws_clean else ""
    sf = (status_filter or "ALL").strip().upper()

    decorated = [_decorate_ticket(t, now_utc) for t in reversed(doc.get("tickets") or [])]
    filtered: list[dict[str, Any]] = []
    other_staged: list[dict[str, Any]] = []
    for t in decorated:
        st = t["status"]
        if not include_superseded and st == "SUPERSEDED":
            continue
        if sf not in ("", "ALL"):
            if sf in ("UNCLAIMED", "STAGED") and st != "STAGED":
                continue
            elif sf in ("IN_WORK", "IN-WORK", "CLAIMED") and st != "IN_WORK":
                continue
            elif sf in VALID_HANDOFF_STATES and st != sf:
                continue
        matches_ws = (
            not ws_clean
            or str(t.get("workspace_path") or "").rstrip("/") == ws_clean
            or (ws_slug and ws_slug != "general" and t.get("repo_slug") == ws_slug)
        )
        if matches_ws:
            filtered.append(t)
        elif st == "STAGED":
            other_staged.append({"handoff_id": t["handoff_id"], "repo_slug": t["repo_slug"], "title": t["title"], "relative_age": t["relative_age"]})

    rank_order = {"STAGED": 0, "IN_WORK": 1, "SUPERSEDED": 2, "COMPLETED": 3}
    filtered.sort(key=lambda x: (rank_order.get(x["status"], 9), -int(x.get("sequence") or 0)))
    capped = filtered[: max(1, min(limit, 200))]
    counts = {
        "staged_unclaimed": sum(1 for x in filtered if x["status"] == "STAGED"),
        "in_work": sum(1 for x in filtered if x["status"] == "IN_WORK"),
        "superseded": sum(1 for x in filtered if x["status"] == "SUPERSEDED"),
    }
    return {"ok": True, "workspace": ws_clean, "repo_slug": ws_slug, "counts": counts, "tickets": capped, "other_workspaces_staged": other_staged[:15]}


def resolve_session_from_handoff_id(bg_dir: Path, identifier: str) -> str:
    """Resolve `<repo-slug>-NN` to its claimed or target Antigravity conversation_id."""
    cid_norm = canonicalize_handoff_id(identifier)
    if not cid_norm:
        return ""
    doc = _read_index_unlocked(bg_dir)
    for t in reversed(doc.get("tickets") or []):
        if t.get("handoff_id") == cid_norm:
            return str(t.get("claimed_by_conversation_id") or t.get("target_conversation_id") or "").strip()
    return ""
