#!/usr/bin/env python3
"""
AGY-Nexus MCP v3.2.3 Showcase Privacy, PWA Parity & Session Load Compaction Regression Suite.
Verifies zero cleartext private strings, modular <=500L/<=100L budgets, 40-col mobile ASCII,
demo asset parity, and <20 KB HTTP wire size for load_session_into_gemini with 6 signed URLs.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sqlite3
import subprocess

import pytest
from starlette.testclient import TestClient

import agy_nexus.config as cfg
import agy_nexus.media as media_mod
import agy_nexus.media_discovery as mdisc_mod
import agy_nexus.sessions as sess_mod
import agy_nexus.tools_session as ts_mod
import agy_nexus.workspace as ws_mod
from agy_nexus.hygiene import _compact_markdown
from agy_nexus.server import build_nexus_http_app
from agy_nexus.web_routes import PWA_ASSETS

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = REPO_ROOT / "web"
SCRIPTS_DIR = REPO_ROOT / "scripts"
DEMO_THUMBS = (
    "demo_thumb_desktop.png",
    "demo_thumb_workspace.png",
    "demo_thumb_foldable.png",
    "demo_thumb_mobile.png",
    "demo_thumb_health.png",
)
HERO_ASSETS = (
    "dashboard-desktop.png",
    "workspace-desktop.png",
    "dashboard-mobile.png",
    "workspace-mobile.png",
)


def _load_exporter_module():
    exp_p = SCRIPTS_DIR / "export_depersonalized_showcase.py"
    spec = importlib.util.spec_from_file_location("export_depersonalized_showcase", exp_p)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_local_secret_strings() -> list[str]:
    vals: list[str] = []
    sec_p = Path.home() / ".config" / "ag-bridge-mcp" / "secrets.env"
    if sec_p.is_file():
        for ln in sec_p.read_text(encoding="utf-8", errors="ignore").splitlines():
            s = ln.strip()
            if s and not s.startswith("#") and "=" in s:
                v = s.split("=", 1)[1].strip().strip('"').strip("'")
                if len(v) >= 6 and "/" not in v:
                    vals.append(v)
    return vals


def test_v323_showcase_zero_private_strings_and_hash_leak_guard() -> None:
    """Assert README, web showcase files, exporter, and tests leak zero private names or secrets."""
    exp = _load_exporter_module()
    banned_hashes = set(exp._WS_HASH_ALIASES.keys()) | set(exp._SCRUB_TOKEN_REPLACEMENTS.keys())
    home_user = Path.home().name
    local_secrets = _load_local_secret_strings()

    check_files = [
        REPO_ROOT / "README.md",
        WEB_DIR / "demo_data.js",
        WEB_DIR / "demo_snapshot.js",
        SCRIPTS_DIR / "export_depersonalized_showcase.py",
        Path(__file__),
    ]
    for fp in check_files:
        raw = fp.read_text(encoding="utf-8")
        scrubbed = raw
        if home_user and len(home_user) >= 3:
            scrubbed = scrubbed.replace(f"github.com/{home_user}/agy-nexus-mcp", "github.com/ORG/agy-nexus-mcp")
            scrubbed = scrubbed.replace(f"{home_user}.github.io/agy-nexus-mcp", "ORG.github.io/agy-nexus-mcp")
            assert not re.search(rf"\b{re.escape(home_user)}\b", scrubbed), f"Home username leaked in {fp.name}"
        for sec in local_secrets:
            assert sec not in raw, f"Runtime secret value leaked in {fp.name}"
        lan_hits = [m.group(0) for m in re.finditer(r"(?<![<a-z0-9-])\b[a-z0-9-]+\.lan\b", raw, flags=re.I)]
        assert not lan_hits, f"Private .lan hostnames leaked in {fp.name}: {lan_hits}"
        home_dirs = [u for u in re.findall(r"/home/([A-Za-z0-9._-]+)/", scrubbed) if u not in {"dev", "ubuntu", "app"}]
        assert not home_dirs, f"Non-generic /home/ user path leaked in {fp.name}: {home_dirs}"
        rfc1918 = re.findall(r"\b192\.168\.\d+\.\d+\b", raw)
        assert not rfc1918, f"Private 192.168.x.x IP leaked in {fp.name}: {rfc1918}"

    live_brain_root = Path.home() / ".gemini" / "antigravity" / "brain"
    real_cids = {d.name.lower() for d in live_brain_root.iterdir() if d.is_dir() and len(d.name) == 36} if live_brain_root.is_dir() else set()
    for fp in (REPO_ROOT / "README.md", WEB_DIR / "demo_data.js", WEB_DIR / "demo_snapshot.js"):
        txt = fp.read_text(encoding="utf-8")
        assert "oss-service-" not in txt, f"Unmapped fallback oss-service-* found in {fp.name}"
        low_txt = txt.lower()
        for rcid in real_cids:
            assert rcid not in low_txt, f"Real session UUID leaked in {fp.name}: {rcid[:8]}"
        for tok in set(re.findall(r"[A-Za-z0-9][A-Za-z0-9&._:/-]{2,}", txt)):
            for part in [tok] + [p for p in re.split(r"[-_./:]", tok) if len(p) >= 3]:
                assert exp._h12(part) not in banned_hashes, f"Hashed private token/sub-token leaked in {fp.name}"
        for tag in set(re.findall(r"\[([A-Za-z0-9]{2,5})-", txt)):
            assert exp._h12(tag) not in banned_hashes, f"Hashed bracket prefix leaked in {fp.name}"

    snap_lines = (WEB_DIR / "demo_snapshot.js").read_text(encoding="utf-8").splitlines()
    for ln in snap_lines:
        if ln.strip().startswith("workspace_tree:"):
            wt = json.loads(ln.split(": ", 1)[1].rstrip(","))
            p_names = [str(p.get("project_name") or "").lower() for p in (wt.get("projects") or [])]
            assert len(p_names) == len(set(p_names)), f"Duplicate lowercase workspace project name in DEMO_SNAPSHOT: {p_names}"
            for tk in (wt.get("queue") or {}).get("tickets") or []:
                assert tk.get("ticket_id") == tk.get("handoff_id"), f"Unsanitized ticket_id: {tk.get('ticket_id')}"
                assert tk.get("topic_slug") == tk.get("handoff_id"), f"Unsanitized topic_slug: {tk.get('topic_slug')}"


def test_v323_showcase_asset_parity_readme_and_modular_budgets() -> None:
    """Verify PWA/SW/HTML registration of showcase files, 40-col quick lines, and <=500L/<=100L budgets."""
    for p in (
        REPO_ROOT / "README.md",
        WEB_DIR / "demo_data.js",
        WEB_DIR / "demo_snapshot.js",
        SCRIPTS_DIR / "export_depersonalized_showcase.py",
        Path(__file__),
    ):
        lines = p.read_text(encoding="utf-8").splitlines()
        assert len(lines) <= 500, f"{p.name} exceeded 500L modular ceiling ({len(lines)}L)"

    exp_src = (SCRIPTS_DIR / "export_depersonalized_showcase.py").read_text(encoding="utf-8")
    tree = ast.parse(exp_src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fn_len = (node.end_lineno or node.lineno) - node.lineno + 1
            assert fn_len <= 100, f"export_depersonalized_showcase.py:{node.name} exceeded 100L ({fn_len}L)"

    sw_js = (WEB_DIR / "sw.js").read_text(encoding="utf-8")
    index_html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    assert 'CACHE_NAME = "agy-nexus-v4.0.3"' in sw_js
    assert "demo_snapshot.js" in PWA_ASSETS and "demo_snapshot.js" in sw_js and "/web/demo_snapshot.js" in index_html
    for thumb in DEMO_THUMBS:
        assert thumb in PWA_ASSETS and thumb in sw_js, f"Missing showcase thumb {thumb} from PWA/SW"
        tp = WEB_DIR / thumb
        assert tp.is_file() and tp.read_bytes().startswith(b"\x89PNG"), f"Missing/invalid PNG: {tp}"
    for hero in HERO_ASSETS:
        hp = REPO_ROOT / "docs" / "assets" / hero
        assert hp.is_file() and hp.read_bytes().startswith(b"\x89PNG") and hp.stat().st_size > 10_000

    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```text\n([\s\S]*?)\n```", readme)
    assert len(blocks) >= 4
    quick_block, rich_block = blocks[2], blocks[3]
    for q_ln in quick_block.splitlines():
        assert len(q_ln) <= 40, f"Quick ASCII line exceeded 40 chars ({len(q_ln)}): {q_ln}"
    assert "v4.0.3" in rich_block and "WORKSPACES (" in rich_block and "SUBAGENTS (" in rich_block
    assert "v3.1.0" not in blocks[0] + blocks[1] + blocks[2] + blocks[3]
    snap_chk = subprocess.run(["node", "--check", str(WEB_DIR / "demo_snapshot.js")], capture_output=True, text=True, check=False)
    assert snap_chk.returncode == 0, snap_chk.stderr


def test_v323_load_session_into_gemini_wire_under_20kb_with_6_media_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify load_session_into_gemini over HTTP /mcp stays strictly <20 KB with 6 signed images + long docs."""
    brain_root = tmp_path / "brain"
    bg_dir = tmp_path / "bg"
    ws_dir = tmp_path / "ws"
    repo_dir = ws_dir / "projects" / "demo-showcase"
    db_file = tmp_path / "state.vscdb"
    cid = "99998888-7777-4666-8555-444433332222"
    sess_dir = brain_root / cid
    (sess_dir / ".system_generated" / "logs").mkdir(parents=True)
    bg_dir.mkdir(parents=True)
    repo_dir.mkdir(parents=True)
    (repo_dir / "sample_big.py").write_text("# big module\n" + ("def fn_item(x):\n    return x + 1\n" * 350), encoding="utf-8")

    for fname, txt in (
        ("task.md", "# Tasks\n" + ("- [x] Verify showcase wire cap item\n" * 160)),
        ("implementation_plan.md", "# Plan\n" + ("Step architecture details line.\n" * 180)),
        ("walkthrough.md", "# Walkthrough\n" + ("Screenshot verified across viewports.\n" * 180)),
    ):
        (sess_dir / fname).write_text(txt, encoding="utf-8")
    for idx in range(6):
        (sess_dir / f"long_capture_filename_for_media_budget_test_{idx:02d}.png").write_bytes(
            b"\x89PNG\r\n\x1a\n" + (b"\x00" * 64)
        )
    t_line = json.dumps({"step_index": 1, "type": "PLANNER_RESPONSE", "content": "Detailed reply. " * 220})
    (sess_dir / ".system_generated" / "logs" / "transcript_full.jsonl").write_text(t_line + "\n", encoding="utf-8")
    sqlite3.connect(str(db_file)).close()

    for mod in (cfg, ts_mod, media_mod, mdisc_mod, sess_mod, ws_mod):
        for attr, val in (
            ("AGY_BRAIN_DIR", brain_root), ("AGY_BG_DIR", bg_dir), ("AGY_DB_FILE", db_file),
            ("AGY_WORKSPACE_DIR", ws_dir), ("AGY_PROJECTS_DIR", ws_dir / "projects"), ("AGY_GITLAB_DIR", ws_dir / "projects"),
        ):
            if hasattr(mod, attr):
                monkeypatch.setattr(mod, attr, val)
    monkeypatch.setattr(ts_mod, "_collect_git_summary", lambda wp: {"branch": "main", "untracked_files": [f"tmp/f_{i}.txt" for i in range(40)]})
    for mod in (cfg, media_mod):
        if hasattr(mod, "PUBLIC_BASE_URL"):
            monkeypatch.setattr(mod, "PUBLIC_BASE_URL", "https://nexus-gateway.example.invalid/mcp-showcase")
    phrase = "canary test vault open"
    monkeypatch.setattr(cfg, "PASS_HASH", cfg.normalize_phrase(phrase))
    secret = "v323_showcase_wire_test_secret_token_32"
    app = build_nexus_http_app(secret, cfg.get_polyglot_mcp_token(secret), cfg.get_praxis_mcp_token(secret))

    with TestClient(app) as client:
        r_unl = client.post(
            f"/{secret}/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "unlock_sessions", "arguments": {"spoken_passphrase": phrase}}},
        )
        assert r_unl.status_code == 200
        r_load = client.post(
            f"/{secret}/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "load_session_into_gemini", "arguments": {"session_identifier": cid, "include_files": "sample_big.py"}}},
        )
        assert r_load.status_code == 200
        assert len(r_load.content) < 20_480, f"HTTP wire response exceeded 20 KB: {len(r_load.content)} bytes"
        payload = json.loads(r_load.json()["result"]["content"][0]["text"])
        assert len(payload.get("visual_artifacts") or []) in (4, 6)
        assert all("/web/media/" in str(v.get("signed_url") or "") for v in payload["visual_artifacts"])
        assert all(len(str(v.get("signed_url") or "")) >= 120 for v in payload["visual_artifacts"])


def test_v323_markdown_renderer_and_compact_markdown_bounds() -> None:
    """Verify _compact_markdown respects small max_chars and MarkdownRenderer strips obfuscated javascript: URLs."""
    big_md = "# H1\n## H2\n" + ("Body line of documentation.\n" * 150)
    for cap in (300, 750, 900):
        comp = _compact_markdown(big_md, max_chars=cap, source_hint="brain:task.md")
        assert len(comp) <= cap, f"_compact_markdown exceeded max_chars={cap} ({len(comp)} chars)"

    js_path = WEB_DIR / "markdown_renderer.js"
    node_script = (
        f"const mr = require({json.dumps(str(js_path))}); "
        f"const out = mr.renderMarkdown('[a](java\\tscript:alert(1)) ![b](\\x01javascript:alert(2)) [c](data:image/svg+xml,<svg/>) [ok](https://example.invalid)'); "
        f"if (/javascript:|vbscript:|data:image\\/svg\\+xml/i.test(out) || !out.includes('https://example.invalid')) process.exit(2);"
    )
    res = subprocess.run(["node", "-e", node_script], capture_output=True, text=True, check=False)
    assert res.returncode == 0, f"MarkdownRenderer URL sanitization failed: {res.stderr}"
