#!/usr/bin/env python3
"""agy_nexus.handoff_queue — Repo-Prefixed Incremental Handoff Queue & Pass-Off Registry.

Manages collision-free staged handoff tickets (`<repo-slug>-01`, `<repo-slug>-02`, ...)
under `sidecar_data/ag-bridge-bg/staged_handoffs/` with `fcntl.flock` atomic locking
and explicit lifecycle states: `STAGED` (unclaimed), `IN_WORK`, `SUPERSEDED`, `COMPLETED`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

from agy_nexus.handoff_queue_store import (
    STATE_DISPLAY_LABELS,
    VALID_HANDOFF_STATES,
    _decorate_ticket,
    _locked_index,
    _prune_old_tickets,
    _queue_dir,
    _read_index_unlocked,
    _supersede_matching_tickets,
    _write_mode_600,
    canonicalize_handoff_id,
    normalize_repo_slug,
    slugify_token,
)


def _normalize_wf_id_list(workflow_ids: list[str] | tuple[str, ...] | str) -> list[str]:
    raw_items = list(workflow_ids) if isinstance(workflow_ids, (list, tuple)) else re.split(r"[\s,;]+", workflow_ids or "")
    out: list[str] = []
    for item in raw_items:
        m = re.fullmatch(r"WF[-_ ]?0*([1-9]\d?)", str(item or "").strip(), re.IGNORECASE)
        if m:
            tag = f"WF-{int(m.group(1)):02d}"
            if tag not in out:
                out.append(tag)
    return out[:12]


def record_handoff_ticket(
    bg_dir: Path, *, full_markdown: str, chars_written: int, repo_slug: str, title: str,
    project_id: str = "", project_name: str = "", workspace_path: str = "", target_conversation_id: str = "",
    rollover_from: str = "", execution_mode: str = "plan", handoff_mode: str = "intent",
    allow_chained_publish: bool = False, initial_status: str = "STAGED", claimed_by_conversation_id: str = "",
    job_id: str = "", supersede_handoff_id: str = "", append_to_existing: bool = False,
    create_new_project: bool = False, default_branch: str = "", retire_after_closeout: bool = False,
    workflow_ids: list[str] | tuple[str, ...] | str = "", workflow_delta: str = "",
    workflows_doc_mtime: float | None = None, workflows_doc_sha256: str = "",
) -> dict[str, Any]:
    """Atomically mint `<repo-slug>-NN` (or append), auto-supersede matching unclaimed tickets, and write file."""
    ts_iso = datetime.now(timezone.utc).isoformat()
    clean_slug = slugify_token(repo_slug, "general", 36)
    title_clean = (title or "Gemini Research Handoff").strip()[:120]
    topic_slug = slugify_token(title_clean, "handoff", 32)
    sup_target = canonicalize_handoff_id(supersede_handoff_id)
    eff_status = initial_status.upper() if initial_status.upper() in VALID_HANDOFF_STATES else "STAGED"
    wf_id_list = _normalize_wf_id_list(workflow_ids)
    wf_delta_str = str(workflow_delta or "").strip().lower()
    if workspace_path and workflows_doc_mtime is None and not workflows_doc_sha256:
        try:
            from agy_nexus.workflow_gate import get_workflows_doc_fingerprint
            fp_mtime, fp_sha = get_workflows_doc_fingerprint(workspace_path)
        except Exception:
            fp_mtime, fp_sha = 0.0, ""
    else:
        fp_mtime, fp_sha = float(workflows_doc_mtime or 0.0), str(workflows_doc_sha256 or "")

    with _locked_index(bg_dir) as (q_dir, doc):
        tickets, counters = doc["tickets"], doc["counters"]
        if append_to_existing:
            for ex in reversed(tickets):
                if str(ex.get("status")) == "STAGED" and ex.get("repo_slug") == clean_slug and (not sup_target or ex.get("handoff_id") == sup_target):
                    t_path = Path(str(ex.get("handoff_file") or ""))
                    ex_txt = t_path.read_text(encoding="utf-8", errors="replace") if t_path.is_file() else ""
                    if "<!-- END_USER_HANDOFF_BODY -->" in ex_txt and "<!-- BEGIN_USER_HANDOFF_BODY -->" in full_markdown:
                        i_end = ex_txt.rindex("<!-- END_USER_HANDOFF_BODY -->")
                        m_nb = re.search(r"<!-- BEGIN_USER_HANDOFF_BODY -->([\s\S]*?)<!-- END_USER_HANDOFF_BODY -->", full_markdown)
                        nb = m_nb.group(1).strip() if m_nb else full_markdown
                        _write_mode_600(t_path, f"{ex_txt[:i_end].rstrip()}\n\n---\n<!-- Appended: {ts_iso} -->\n\n{nb}\n{ex_txt[i_end:].rstrip()}\n")
                    else:
                        _write_mode_600(t_path, f"{ex_txt.rstrip()}\n\n---\n<!-- Appended: {ts_iso} -->\n\n{full_markdown}\n" if ex_txt else full_markdown)
                    ex["chars_written"], ex["updated_at"] = int(ex.get("chars_written") or 0) + chars_written, ts_iso
                    if project_id and not ex.get("project_id"):
                        ex["project_id"] = project_id
                    if create_new_project:
                        ex["create_new_project"] = True
                    if default_branch and (not ex.get("default_branch") or default_branch != "main"):
                        ex["default_branch"] = str(default_branch)
                    if retire_after_closeout:
                        ex["retire_after_closeout"] = True
                    if wf_id_list:
                        ex["workflow_ids"] = list(dict.fromkeys([*(ex.get("workflow_ids") or []), *wf_id_list]))
                    if wf_delta_str and wf_delta_str != "unchanged":
                        ex["workflow_delta"] = wf_delta_str
                        if not ex.get("workflows_doc_sha256"):
                            ex["workflows_doc_mtime"], ex["workflows_doc_sha256"] = fp_mtime, fp_sha
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
            "allow_chained_publish": allow_chained_publish, "create_new_project": bool(create_new_project),
            "default_branch": str(default_branch or ""), "retire_after_closeout": bool(retire_after_closeout),
            "workflow_ids": wf_id_list, "workflow_delta": wf_delta_str,
            "workflows_doc_mtime": fp_mtime, "workflows_doc_sha256": fp_sha,
            "chars_written": chars_written, "handoff_file": str(ticket_file),
            "job_id": job_id, "superseded_ids": superseded_ids, "superseded_by": "",
            "created_at": ts_iso, "updated_at": ts_iso, "claimed_at": ts_iso if eff_status == "IN_WORK" else "",
        }
        tickets.append(entry)
        doc["tickets"] = _prune_old_tickets(q_dir, tickets)
        return _decorate_ticket(entry)


def get_handoff_ticket(bg_dir: Path, handoff_id: str) -> dict[str, Any] | None:
    """Return decorated handoff ticket by canonical ID, or None if not found."""
    cid_norm = canonicalize_handoff_id(handoff_id)
    if not cid_norm:
        return None
    doc = _read_index_unlocked(bg_dir)
    for t in reversed(doc.get("tickets") or []):
        if t.get("handoff_id") == cid_norm:
            return _decorate_ticket(t)
    return None


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
    retire_after_closeout: bool | None = None,
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
                if retire_after_closeout is not None:
                    t["retire_after_closeout"] = bool(retire_after_closeout)
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


def reconcile_completed_tickets(bg_dir: Path, db_file: Path | None = None, brain_dir: Path | None = None) -> list[str]:
    """Auto-transition claimed IN_WORK/STAGED tickets to COMPLETED once their session finishes running, rolls over, or is retired."""
    import agy_nexus.config as cfg
    eff_db = db_file if db_file is not None else cfg.AGY_DB_FILE
    eff_brain = brain_dir if brain_dir is not None else cfg.AGY_BRAIN_DIR
    completed_ids: list[str] = []
    ts_iso = datetime.now(timezone.utc).isoformat()
    try:
        import sqlite3
        con = sqlite3.connect(f"file:{eff_db}?mode=ro", uri=True, timeout=2.0) if eff_db.is_file() else None
        try:
            with _locked_index(bg_dir) as (_, doc):
                tickets = doc.get("tickets") or []
                newer_claimed = {
                    str(t.get("claimed_by_conversation_id") or ""): str(t.get("handoff_id") or "")
                    for t in tickets if str(t.get("status") or "").upper() in ("IN_WORK", "STAGED") and t.get("claimed_by_conversation_id")
                }
                from agy_nexus.workflow_gate import verify_workflow_doc_updated_for_completion
                for t in tickets:
                    st_val = str(t.get("status") or "").upper()
                    if st_val not in ("IN_WORK", "STAGED"):
                        continue
                    cid = str(t.get("claimed_by_conversation_id") or t.get("target_conversation_id") or "").strip()
                    if not cid:
                        continue
                    if (eff_brain / cid / "RETIRED.json").is_file():
                        if verify_workflow_doc_updated_for_completion(t).get("ok"):
                            t.update({"status": "COMPLETED", "completed_at": ts_iso, "updated_at": ts_iso})
                            completed_ids.append(str(t.get("handoff_id")))
                        continue
                    if st_val != "IN_WORK" or not con:
                        continue
                    row = con.execute("SELECT status, not_fully_idle FROM conversation_summaries WHERE conversation_id = ?", (cid,)).fetchone()
                    if row:
                        raw_st = str(row[0] or "").upper()
                        is_running = ("RUNNING" in raw_st) or bool(row[1])
                        newer_hid = newer_claimed.get(cid)
                        has_newer = bool(newer_hid and newer_hid != str(t.get("handoff_id")))
                        if (not is_running or has_newer) and verify_workflow_doc_updated_for_completion(t).get("ok"):
                            t.update({"status": "COMPLETED", "completed_at": ts_iso, "updated_at": ts_iso})
                            completed_ids.append(str(t.get("handoff_id")))
        finally:
            if con:
                con.close()
    except Exception:
        pass
    return completed_ids


def list_handoff_tickets(
    bg_dir: Path,
    *,
    workspace: str = "",
    status_filter: str = "ALL",
    include_superseded: bool = True,
    auto_reconcile: bool = True,
    limit: int = 50,
) -> dict[str, Any]:
    """List staged, in-work, completed, and superseded handoff tickets with workspace prioritization."""
    if auto_reconcile:
        try:
            reconcile_completed_tickets(bg_dir)
        except Exception:
            pass
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

    rank_order = {"STAGED": 0, "IN_WORK": 1, "COMPLETED": 2, "SUPERSEDED": 3}
    filtered.sort(key=lambda x: (rank_order.get(x["status"], 9), -int(x.get("sequence") or 0)))
    capped = filtered[: max(1, min(limit, 200))]
    counts = {
        "staged_unclaimed": sum(1 for x in filtered if x["status"] == "STAGED"),
        "in_work": sum(1 for x in filtered if x["status"] == "IN_WORK"),
        "completed": sum(1 for x in filtered if x["status"] == "COMPLETED"),
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
