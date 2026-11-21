#!/usr/bin/env python3
"""agy_nexus.handoff_queue_store — Atomic Flock Storage, Slugifiers & Ticket Decoration Helpers."""
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


def _write_mode_600(path: Path, text: str) -> None:
    """Atomically write UTF-8 text via a 0600 sibling temp file and POSIX rename."""
    import threading
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
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


@contextmanager
def _locked_index(bg_dir: Path) -> Iterator[tuple[Path, dict[str, Any]]]:
    """Acquire exclusive flock on staged_handoffs/index.lock, yield (q_dir, doc), and persist changes."""
    import shutil
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
                    if idx_path.stat().st_size > 0:
                        shutil.copy2(idx_path, q_dir / f"index.corrupt.{int(datetime.now(timezone.utc).timestamp())}.json")
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
    slug = str(out.get("slug") or "")
    real_id = str(out.get("handoff_id") or out.get("ticket_id") or "")
    if (not real_id or real_id == "ticket") and slug:
        real_id = slug
    out["handoff_id"] = real_id
    out["ticket_id"] = real_id
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
