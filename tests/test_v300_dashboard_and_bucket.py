#!/usr/bin/env python3
"""
Unit and regression test suite for AGY Nexus v3.0.0:
Overwatch Dashboard, Rendered HTML Workspace & Continuity-Aware Rollover.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any
from unittest.mock import patch

import pytest

import agy_nexus
from agy_nexus.bucket_api import (
    build_workspace_tree_payload,
    get_session_bucket_payload,
    get_session_file_payload,
    handle_bucket_api_request,
    rewrite_markdown_media_links,
    scan_session_artifacts,
    scan_session_uploads,
)
from agy_nexus.code_health import get_modular_hygiene_summary
from agy_nexus.handoff_queue import (
    record_handoff_ticket,
    reconcile_completed_tickets,
)
from agy_nexus.media import (
    MEDIA_TTL_SECONDS,
    compute_media_hmac,
    sign_media_url,
    verify_and_resolve_media,
)
from agy_nexus.session_status import (
    check_uncommitted_work,
    count_open_task_items,
    evaluate_rollover_posture,
    get_session_context_budget,
    infer_continuity_intent,
)
from agy_nexus.stats import build_nexus_stats_bundle
from agy_nexus.stats_series import build_base_slot_grid


def test_v301_version_bump() -> None:
    """Verify package version is bumped to 4.0.8."""
    assert agy_nexus.__version__ == "4.0.8"


def test_media_ttl_is_7_days() -> None:
    """Verify default MEDIA_TTL_SECONDS is 7 days (604,800 seconds)."""
    assert MEDIA_TTL_SECONDS == 604800
    # Test signing produces signed media path containing /web/media/
    signed_url = sign_media_url("brain:test", "artifact.png", ttl_seconds=MEDIA_TTL_SECONDS)
    assert "/web/media/" in signed_url
    parts = signed_url.split("/web/media/", 1)[1].split("/")
    exp_ts = int(parts[0])
    now_ts = int(time.time())
    assert (exp_ts - now_ts) >= 604000  # approximately 7 days in the future

    # Test expired media route rejection
    expired_path = f"/web/media/{now_ts - 100}/invalidsig/brain%3Atest/artifact.png"
    _, _, status_code, err = verify_and_resolve_media(expired_path)
    assert status_code in (400, 403)


def test_plot_base_slots_1h_for_month_and_quarter() -> None:
    """Verify stats_series emits 1h base slots for Month (<=31d) and Quarter (<=92d)."""
    month_days = [f"2026-11-{d:02d}" for d in range(1, 31)]
    labels_m, groups_m, step_m, _ = build_base_slot_grid("month", month_days, "2026-11-30", 23)
    assert step_m == 1
    assert len(labels_m) == 30 * 24

    quarter_days = [f"2026-10-{d:02d}" for d in range(1, 32)] + [f"2026-11-{d:02d}" for d in range(1, 31)]
    labels_q, groups_q, step_q, _ = build_base_slot_grid("quarter", quarter_days, "2026-11-30", 23)
    assert step_q == 1

    year_days = [f"2026-01-{d:02d}" for d in range(1, 32)] * 4  # > 92 days
    labels_y, groups_y, step_y, _ = build_base_slot_grid("year", year_days, "2026-11-30", 23)
    assert step_y == 24


def test_52_week_heatmap_invariant() -> None:
    """Verify build_nexus_stats_bundle generates a 52-week heatmap grid with window tags."""
    bundle = build_nexus_stats_bundle(timeframe="month", horizon_mode="to_date", offset=0)
    assert "heatmap_series" in bundle
    hm = bundle["heatmap_series"]
    assert 364 <= len(hm) <= 378  # 52-54 weeks * 7 days
    in_win = [d for d in hm if d.get("in_window")]
    assert len(in_win) > 0
    for d in hm:
        assert "date" in d
        assert "in_window" in d
        assert isinstance(d["in_window"], bool)
        assert "future" in d


def test_continuity_aware_rollover_posture() -> None:
    """Verify evaluate_rollover_posture thresholds and flags."""
    # Fresh session (< 320 steps)
    p_fresh = evaluate_rollover_posture(conv_id="", step_count=50, compaction_count=0)
    assert p_fresh["posture"] == "FRESH"
    assert p_fresh["should_rollover"] is False

    # Seam-aware session (320-699 steps)
    p_seam = evaluate_rollover_posture(conv_id="", step_count=400, compaction_count=1)
    assert p_seam["posture"] == "SEAM_AWARE"

    # Hold for completion (700-949 steps)
    p_hold = evaluate_rollover_posture(conv_id="", step_count=750, compaction_count=2)
    assert p_hold["posture"] == "HOLD_FOR_COMPLETION"

    # Closeout only (950-1149 steps)
    p_close = evaluate_rollover_posture(conv_id="", step_count=1000, compaction_count=4)
    assert p_close["posture"] == "CLOSEOUT_ONLY"

    # Hard rollover (>= 1150 steps or compactions >= 7)
    p_hard1 = evaluate_rollover_posture(conv_id="", step_count=1200, compaction_count=2)
    assert p_hard1["posture"] == "HARD_ROLLOVER"
    assert p_hard1["should_rollover"] is True

    p_hard2 = evaluate_rollover_posture(conv_id="", step_count=100, compaction_count=8)
    assert p_hard2["posture"] == "HARD_ROLLOVER"
    assert p_hard2["should_rollover"] is True


def test_open_task_items_and_continuity_helpers(tmp_path: Path) -> None:
    """Verify task item counting and continuity intent parsing."""
    c_dir = tmp_path / "test-conv"
    c_dir.mkdir(parents=True)
    task_file = c_dir / "task.md"
    task_file.write_text("""# Task List
- [x] Item 1 completed
- [ ] Item 2 pending
- [/] Item 3 in progress
- [x] Item 4 completed
""", encoding="utf-8")

    assert count_open_task_items("test-conv", brain_dir=tmp_path) == 2

    clean_file = c_dir / "task.md"
    clean_file.write_text("""# Done List
- [x] Item 1
- [x] Item 2
""", encoding="utf-8")
    assert count_open_task_items("test-conv", brain_dir=tmp_path) == 0

    assert infer_continuity_intent("continue from previous step", allow_chained_publish=False, is_clean_seam=False) == "continuation"
    assert infer_continuity_intent("closeout release", allow_chained_publish=True, is_clean_seam=True) == "closeout"
    assert infer_continuity_intent("# v3.0.0 new topic", allow_chained_publish=False, is_clean_seam=True) == "new_topic"


def test_reconcile_completed_tickets(tmp_path: Path) -> None:
    """Verify reconcile_completed_tickets transitions IN_WORK tickets to COMPLETED."""
    import sqlite3
    db_file = tmp_path / "test_summaries.db"
    con = sqlite3.connect(str(db_file))
    con.execute("CREATE TABLE conversation_summaries (conversation_id TEXT PRIMARY KEY, status TEXT, not_fully_idle INTEGER)")
    con.execute("INSERT INTO conversation_summaries VALUES ('conv-completed-1', 'IDLE', 0)")
    con.commit()
    con.close()

    t = record_handoff_ticket(
        tmp_path,
        full_markdown="# Spec",
        chars_written=100,
        repo_slug="test-repo",
        title="Test Handoff",
        initial_status="IN_WORK",
        claimed_by_conversation_id="conv-completed-1",
    )
    assert t["status"] == "IN_WORK"

    reconciled = reconcile_completed_tickets(bg_dir=tmp_path, db_file=db_file)
    assert t["handoff_id"] in reconciled


def test_rewrite_markdown_media_links(tmp_path: Path) -> None:
    """Verify rewrite_markdown_media_links converts brain images to signed /web/media/ URLs."""
    conv_dir = tmp_path / "test-conv"
    conv_dir.mkdir(parents=True)
    img_file = conv_dir / "screenshot.png"
    img_file.write_bytes(b"\x89PNG\r\n\x1a\n")

    raw_md = f"Look at this screenshot: ![]({img_file}) and link [image]({img_file})"
    with patch("agy_nexus.bucket_api.AGY_BRAIN_DIR", tmp_path):
        rewritten = rewrite_markdown_media_links(raw_md, conv_id="test-conv")
        assert "/web/media/" in rewritten
        assert "screenshot.png" in rewritten


def test_bucket_api_traversal_and_sensitive_guards() -> None:
    """Verify get_session_file_payload rejects directory traversal and sensitive files."""
    code_trav, payload_trav = get_session_file_payload("test-cid", "../../etc/passwd")
    assert code_trav == 403
    assert payload_trav["ok"] is False

    code_sens, payload_sens = get_session_file_payload("test-cid", "secrets.env")
    assert code_sens == 403
    assert payload_sens["ok"] is False


def test_bucket_api_workspace_tree_and_session_bucket() -> None:
    """Verify build_workspace_tree_payload and get_session_bucket_payload return structured payloads."""
    tree_data = build_workspace_tree_payload()
    assert tree_data["ok"] is True
    assert "queue" in tree_data
    assert "projects" in tree_data
    assert tree_data["queue"]["type"] == "queue"
    assert isinstance(tree_data["projects"], list)

    bucket_data = get_session_bucket_payload("test-cid")
    assert bucket_data["ok"] is True
    assert bucket_data["conversation_id"] == "test-cid"
    assert "uploads" in bucket_data
    assert "artifacts" in bucket_data
    assert "rollover" in bucket_data


@pytest.mark.asyncio
async def test_handle_bucket_api_request_asgi() -> None:
    """Verify handle_bucket_api_request handles tree and auth checks."""
    sent_events: list[dict[str, Any]] = []

    async def dummy_send(event: dict[str, Any]) -> None:
        sent_events.append(event)

    async def dummy_receive() -> dict[str, Any]:
        return {"type": "http.request"}

    # Unauthorized request (empty headers)
    with patch("agy_nexus.bucket_api.verify_passphrase", return_value=False):
        await handle_bucket_api_request(
            scope={"type": "http", "method": "GET", "path": "/web/api/workspace/tree"},
            receive=dummy_receive,
            send=dummy_send,
            req_path="/web/api/workspace/tree",
            method="GET",
            headers=[],
        )
        assert len(sent_events) >= 2
        assert sent_events[0]["status"] == 401

    # Authorized request for tree
    sent_events.clear()
    with patch("agy_nexus.bucket_api.verify_passphrase", return_value=True):
        await handle_bucket_api_request(
            scope={"type": "http", "method": "GET", "path": "/web/api/workspace/tree"},
            receive=dummy_receive,
            send=dummy_send,
            req_path="/web/api/workspace/tree",
            method="GET",
            headers=[(b"x-nexus-passphrase", b"valid-pass")],
        )
        assert len(sent_events) >= 2
        assert sent_events[0]["status"] == 200
        body = json.loads(sent_events[1]["body"].decode("utf-8"))
        assert body["ok"] is True
        assert "queue" in body
        assert "projects" in body


def test_modular_hygiene_summary() -> None:
    """Verify get_modular_hygiene_summary audits modules and includes watchlist_and_exceptions."""
    summary = get_modular_hygiene_summary()
    assert summary["ceiling_pass"] is True
    assert summary["violations_over_650"] == 0
    assert "modules" in summary
    assert "watchlist_and_exceptions" in summary
    assert len(summary["modules"]) > 10


def test_validate_conv_id_rejection_in_bucket_api() -> None:
    """Verify validate_conv_id rejects path traversal across bucket APIs."""
    bad_cid = "../etc/passwd"
    b_res = get_session_bucket_payload(bad_cid)
    assert b_res["ok"] is False
    assert "invalid" in b_res["error"].lower()

    status, f_res = get_session_file_payload(bad_cid, "test.txt")
    assert status == 400
    assert f_res["ok"] is False

    assert scan_session_uploads(bad_cid) == []
    assert scan_session_artifacts(bad_cid) == []


def test_get_session_context_budget_thresholds() -> None:
    """Verify get_session_context_budget uses the v3.0.0 posture scale."""
    assert get_session_context_budget(0) == "GREEN (<500 steps)"
    assert get_session_context_budget(499) == "GREEN (<500 steps)"
    assert get_session_context_budget(500) == "AMBER (500-749 steps)"
    assert get_session_context_budget(749) == "AMBER (500-749 steps)"
    assert get_session_context_budget(750) == "ROLLOVER_RECOMMENDED (>=750 steps or context exceeded)"
    assert get_session_context_budget(1200) == "ROLLOVER_RECOMMENDED (>=750 steps or context exceeded)"
    assert get_session_context_budget(50, context_exceeded=True) == "ROLLOVER_RECOMMENDED (>=750 steps or context exceeded)"


def test_markdown_renderer_js_image_link_and_sanitizer() -> None:
    """Verify Node.js execution of markdown_renderer.js renders images before links and sanitizes dangerous HTML."""
    js_test_code = """
    const MarkdownRenderer = require('./web/markdown_renderer.js');
    const mdImg = '![Alt Figure](https://example.com/fig.png)';
    const outImg = MarkdownRenderer.renderMarkdown(mdImg);
    if (!outImg.includes('<figure class="editorial-figure"><img src="https://example.com/fig.png"') || outImg.includes('!<a')) {
      console.error('Image rendered as link instead of figure:', outImg);
      process.exit(1);
    }
    const mdLink = '[Click Here](https://example.com/page)';
    const outLink = MarkdownRenderer.renderMarkdown(mdLink);
    if (!outLink.includes('<a href="https://example.com/page"') || !outLink.includes('Click Here')) {
      console.error('Link rendering failed:', outLink);
      process.exit(2);
    }
    const xss = '<img src=x onerror=alert(1)><iframe src="javascript:alert(2)"></iframe>';
    const outSan = MarkdownRenderer.sanitizeHtml(xss);
    if (outSan.includes('onerror') || outSan.includes('iframe') || outSan.includes('javascript:')) {
      console.error('Sanitizer failed to strip XSS:', outSan);
      process.exit(3);
    }
    const outRendered = MarkdownRenderer.renderMarkdown(xss);
    if (outRendered.includes('onerror') || outRendered.includes('iframe') || outRendered.includes('javascript:')) {
      console.error('Rendered Markdown failed to strip XSS:', outRendered);
      process.exit(4);
    }
    console.log('OK');
    """
    res = subprocess.run(["node", "-e", js_test_code], capture_output=True, text=True)
    assert res.returncode == 0, f"Node test failed: {res.stderr}"
    assert "OK" in res.stdout


def test_v301_markdown_renderer_article_and_svg_preserved() -> None:
    """Verify markdown_renderer.js ALLOWED_TAGS preserves article, section, header, and svg tags."""
    js_test_code = """
    const MarkdownRenderer = require('./web/markdown_renderer.js');
    const inputHtml = '<article class="editorial-article"><header><h1>Doc</h1></header><section><p>Text</p><svg viewBox="0 0 100 100"><path d="M10 10 H 90 V 90 H 10 Z" fill="red"/></svg></section></article>';
    const sanitized = MarkdownRenderer.sanitizeHtml(inputHtml);
    if (!sanitized.includes('<article class="editorial-article">')) {
      console.error('Article tag was removed by sanitizer:', sanitized);
      process.exit(1);
    }
    if (!sanitized.includes('<svg') || !sanitized.includes('<path')) {
      console.error('SVG elements removed by sanitizer:', sanitized);
      process.exit(2);
    }
    const md = '# Sample\\n\\nSome paragraph content.\\n';
    const editorialHtml = MarkdownRenderer.renderMarkdownToEditorialHtml(md);
    if (!editorialHtml.includes('<article class="editorial-article">') || !editorialHtml.includes('Sample')) {
      console.error('renderMarkdownToEditorialHtml wiped content:', editorialHtml);
      process.exit(3);
    }
    console.log('OK');
    """
    res = subprocess.run(["node", "-e", js_test_code], capture_output=True, text=True)
    assert res.returncode == 0, f"Node test failed: {res.stderr}"
    assert "OK" in res.stdout


def test_v301_relative_media_urls_and_bucket() -> None:
    """Verify sign_media_url with relative=True produces /web/media/... paths."""
    rel_url = sign_media_url("brain:test-conv", "test.png", relative=True)
    assert rel_url.startswith("/web/media/")
    assert not rel_url.startswith("http://")
    assert not rel_url.startswith("https://")

    abs_url = sign_media_url("brain:test-conv", "test.png", relative=False)
    assert abs_url.startswith("http://") or abs_url.startswith("https://")
    assert "/web/media/" in abs_url


def test_v301_handoff_queue_real_ticket_id_decoration() -> None:
    """Verify _decorate_ticket sets both ticket_id and handoff_id to real slug."""
    from agy_nexus.handoff_queue import _decorate_ticket
    raw = {
        "slug": "agy-nexus-mcp-01",
        "repo_slug": "agy-nexus-mcp",
        "title": "Clean 2-Pane Workspace & Foldable UI Bug Fixes",
        "status": "STAGED",
    }
    dec = _decorate_ticket(raw)
    assert dec["ticket_id"] == "agy-nexus-mcp-01"
    assert dec["handoff_id"] == "agy-nexus-mcp-01"
    assert dec["ticket_id"] != "ticket"

