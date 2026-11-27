"""tests/test_v421_session_gallery_and_verified_urls.py — Signed gallery, verified URLs, %3A media, and wire-cap suite."""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import time

import pytest
from starlette.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agy_nexus import bucket_api as bapi_mod, bucket_scanner as bscan_mod, config as cfg, handoff as handoff_mod, media as media_mod  # noqa: E402
from agy_nexus import media_discovery as mdisc_mod, retirement as ret_mod, routing as routing_mod, search as search_mod  # noqa: E402
from agy_nexus import session_gallery as sg_mod, session_status as ss_mod, session_tree as st_mod, sessions as sess_mod  # noqa: E402
from agy_nexus import target_resolver as tr_mod, tools_media as tmedia_mod, tools_ops as tops_mod, tools_session as tsession_mod  # noqa: E402
from agy_nexus import tools_workspace as tws_mod, verified_urls as vurl_mod, virtual_uris as vu_mod, web_routes as wr_mod  # noqa: E402
from agy_nexus import workflows as wf_mod, workspace as ws_mod  # noqa: E402
from agy_nexus.media import compute_media_hmac, discover_visual_buckets, sign_media_url, verify_and_resolve_media  # noqa: E402
from agy_nexus.server import build_nexus_http_app  # noqa: E402
from agy_nexus.session_gallery import compute_gallery_hmac, sign_gallery_url  # noqa: E402
from agy_nexus.verified_urls import extract_verified_urls_from_texts, normalize_github_remote_url, resolve_repo_github_url  # noqa: E402


def _setup_sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path, Path, str, str]:
    brain_root, bg_dir, ws_dir, cfg_dir = tmp_path / "brain", tmp_path / "bg", tmp_path / "ws", tmp_path / "cfg"
    repo_dir = ws_dir / "projects" / "demo-gallery-repo"
    db_file = tmp_path / "state.vscdb"
    for d in (cfg_dir / "projects", bg_dir, brain_root, repo_dir):
        d.mkdir(parents=True, exist_ok=True)
    (repo_dir / "app.py").write_text("def ok():\n    return True\n", encoding="utf-8")
    con = sqlite3.connect(str(db_file))
    con.execute(
        "CREATE TABLE conversation_summaries (conversation_id TEXT PRIMARY KEY, title TEXT, preview TEXT, "
        "project_id TEXT, status TEXT, step_count INTEGER, last_modified_time TEXT, not_fully_idle INTEGER, "
        "killed INTEGER, workspace_uris TEXT, parent_conversation_id TEXT)"
    )
    con.commit()
    con.close()
    mods = (
        cfg, handoff_mod, tsession_mod, tws_mod, tops_mod, tmedia_mod, media_mod, mdisc_mod, sess_mod, ss_mod,
        st_mod, search_mod, routing_mod, tr_mod, ret_mod, vu_mod, wf_mod, ws_mod, sg_mod, vurl_mod, bapi_mod,
        bscan_mod, wr_mod,
    )
    attrs = {
        "AGY_BRAIN_DIR": brain_root, "AGY_BG_DIR": bg_dir, "AGY_DB_FILE": db_file,
        "AGY_CONFIG_DIR": cfg_dir, "AGY_DATA_DIR": tmp_path, "AGY_WORKSPACE_DIR": ws_dir,
        "AGY_PROJECTS_DIR": ws_dir / "projects", "AGY_WORKBOOKS_DIR": ws_dir / "workbooks",
        "AGY_CONFIGURATION_DIR": ws_dir / "configuration", "AGY_GITLAB_DIR": ws_dir / "projects",
    }
    for mod in mods:
        for attr, val in attrs.items():
            if hasattr(mod, attr):
                monkeypatch.setattr(mod, attr, val)
    phrase = "canary gallery shield open"
    secret = "v421_secret_token_001122334455667788"
    monkeypatch.setattr(cfg, "PASS_HASH", cfg.normalize_phrase(phrase))
    monkeypatch.setattr(cfg, "PATH_SECRET", secret)
    monkeypatch.setattr(media_mod, "_VERIFIED_REQUEST_ORIGIN", "")
    monkeypatch.setenv("AG_BRIDGE_PUBLIC_URL", "https://ag-test99.example.net")
    return brain_root, bg_dir, db_file, repo_dir, phrase, secret


def _make_png(path: Path, size: tuple[int, int] = (64, 64), textured: bool = False) -> None:
    from PIL import Image as PilImage

    path.parent.mkdir(parents=True, exist_ok=True)
    if textured:
        w, h = size
        raw = bytes(((x * 13 ^ y * 29) + (x * y) % 97) & 0xFF for y in range(h) for x in range(w) for _ in range(3))
        PilImage.frombytes("RGB", size, raw).save(path, format="PNG")
    else:
        PilImage.new("RGB", size, (24, 96, 180)).save(path, format="PNG")


def _call_mcp(
    client: TestClient, secret: str, req_id: int, tool_name: str, arguments: dict, headers: dict[str, str] | None = None
) -> tuple[bytes, dict, list]:
    resp = client.post(
        f"/{secret}/mcp",
        headers=headers or {},
        json={"jsonrpc": "2.0", "id": req_id, "method": "tools/call", "params": {"name": tool_name, "arguments": arguments}},
    )
    assert resp.status_code == 200
    assert len(resp.content) <= 20_480, f"{tool_name} exceeded 20 KB wire limit ({len(resp.content)}B)"
    blocks = resp.json()["result"]["content"]
    return resp.content, json.loads(blocks[0]["text"]), blocks


def test_v421_percent_encoded_media_scope_and_legacy_compat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify %3A media URL encoding, legacy colon compatibility, and repo_limit=0 isolation."""
    brain_root, _bg, _db, repo_dir, _phrase, _secret = _setup_sandbox(tmp_path, monkeypatch)
    my_repo = repo_dir.parent / "my-repo"
    _make_png(brain_root / "cid-1" / "shot.png", size=(320, 200))
    _make_png(my_repo / "docs" / "a.png", size=(320, 200))
    _make_png(my_repo / "screenshots" / "repo_cap.png", size=(320, 200))

    brain_url = sign_media_url("brain:cid-1", "shot.png", relative=True)
    repo_url = sign_media_url("repo:my-repo", "docs/a.png", relative=True)
    assert "/brain%3Acid-1/shot.png" in brain_url and "/brain:cid-1/" not in brain_url
    assert "/repo%3Amy-repo/docs/a.png" in repo_url and "/repo:my-repo/" not in repo_url

    p_enc, _, st_enc, _ = verify_and_resolve_media(f"{brain_url}?hl=en-US")
    assert st_enc == 200 and p_enc is not None and p_enc.name == "shot.png"

    legacy_url = brain_url.replace("brain%3Acid-1", "brain:cid-1")
    p_leg, _, st_leg, _ = verify_and_resolve_media(legacy_url)
    assert st_leg == 200 and p_leg is not None and p_leg.name == "shot.png"

    parts = brain_url.split("/")
    parts[4] = "0" * 32
    _, _, st_bad, _ = verify_and_resolve_media("/".join(parts))
    assert st_bad == 403

    expired = sign_media_url("brain:cid-1", "shot.png", exp_ts=int(time.time()) - 60, relative=True)
    _, _, st_exp, _ = verify_and_resolve_media(expired)
    assert st_exp == 403

    s_items, r_items = discover_visual_buckets("cid-1", workspace_path=str(my_repo), repo_limit=0, relative=True)
    assert [i["name"] for i in s_items] == ["shot.png"] and r_items == []


def test_v421_verified_urls_github_and_showcase_expansion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify GitHub remote normalization, showcase relative expansion, PR/CI linking, and URL filtering."""
    _brain, _bg, _db, _repo, _phrase, secret = _setup_sandbox(tmp_path, monkeypatch)
    assert normalize_github_remote_url("git@github.com:Org/Repo.git") == "https://github.com/Org/Repo"
    assert normalize_github_remote_url("https://tok@github.com/Org/Repo.git") == "https://github.com/Org/Repo"
    assert normalize_github_remote_url("ssh://git@github.com/Org/Repo.git") == "https://github.com/Org/Repo"
    assert normalize_github_remote_url("https://github.com/features/actions") == ""
    assert normalize_github_remote_url("https://gitlab.com/Org/Repo.git") == ""

    git_repo = tmp_path / "git_proj"
    git_repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(git_repo), check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", "git@github.com:Org/MyRepo.git"], cwd=str(git_repo), check=True, capture_output=True)
    gh_url = resolve_repo_github_url(git_repo)
    assert gh_url == "https://github.com/Org/MyRepo"

    texts = [
        "Published https://FrankXLT.github.io/my-app/ with [Demo](./demo/), ./demo/#workspace, docs/, [Overview](./), and docs/WORKFLOWS.md.",
        "Duplicate https://frankxlt.github.io/my-app/demo/ plus PR #14, Pull Request #22, CI run #998877, run #12345, and screenshot #01.",
        (
            f"Ignore http://plain.example.com/a https://nas.lan/x https://192.168.1.5/d https://localhost:8080/a "
            f"https://ag-test99.example.net/web/media/1/a/b/c.png https://ag-test99.example.net/web/gallery/1/a/cid "
            f"https://ag-test99.example.net/mcp https://example.org/{secret}/leak "
            f"https://developers.google.com/crawling/docs/crawlers-fetchers/google-agent"
        ),
    ]
    urls = extract_verified_urls_from_texts(texts, repo_github_url=gh_url, max_urls=16)
    lower_urls = [u.lower() for u in urls]
    for expected in (
        "https://FrankXLT.github.io/my-app/",
        "https://FrankXLT.github.io/my-app/demo/#workspace",
        "https://FrankXLT.github.io/my-app/docs/",
        "https://github.com/Org/MyRepo/pull/14",
        "https://github.com/Org/MyRepo/pull/22",
        "https://github.com/Org/MyRepo/actions/runs/998877",
        "https://github.com/Org/MyRepo/actions/runs/12345",
    ):
        assert expected in urls
    assert "https://frankxlt.github.io/my-app/demo/" in lower_urls
    assert not any("WORKFLOWS.md" in u or u.endswith("/pull/01") or "192.168.1.5" in u or ".lan" in u for u in urls)
    assert not any(bad in u for u in urls for bad in ("http://", "localhost", "/web/media/", "/web/gallery/", "/mcp", secret, "developers.google.com/crawling/"))
    assert len([u for u in urls if u.lower() == "https://frankxlt.github.io/my-app/demo/"]) == 1
    assert len(extract_verified_urls_from_texts(texts, repo_github_url=gh_url, max_urls=3)) == 3


def test_v421_verified_urls_ssrf_secrets_and_redos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify SSRF/secret/redirect filtering, ReDoS bound, .html showcase root, and non-primary bare docs guard."""
    _setup_sandbox(tmp_path, monkeypatch)
    p_tok = cfg.get_praxis_mcp_token()
    pass_h = cfg.PASS_HASH
    pct_pass = f"%{ord(pass_h[0]):02x}{pass_h[1:]}"
    pct_tok = f"%{ord(p_tok[0]):02x}{p_tok[1:]}"
    bad_urls = [
        "https://example.org/a?token=abc", "https://example.org/b?api_key=xyz",
        "https://example.org/c?sig=123", "https://example.org/d#secret=abc",
        "https://ag-test99.example.net/web?view=workspace&session=s1&sig=deadbeef",
        f"https://example.org/{pass_h.upper()}", f"https://example.org/{pct_pass}",
        f"https://example.org/{p_tok.upper()}", f"https://example.org/{pct_tok}",
        "https://ag-test99.example.net/%77eb/gallery/1/abc/cid",
        "https://ag-test99.example.net/WEB/GALLERY/1/abc/cid",
        "https://www.google.com/search?q=test", "https://google.com/url?q=https://example.org",
        "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQ",
        "https://localhost./", "https://nas.lan./", "https://[::ffff:127.0.0.1]/",
        "https://[::ffff:169.254.169.254%eth0]/", "https://127.1/", "https://0177.0.0.1/",
        "https://[invalid-host]/", "https://example.org:badport/",
        "https://git.example.org/org/repo.git", "https://api.github.com/repos/Org/MyRepo",
        "https://github.com/login/oauth/access_token",
        "https://ag-34260fda204e.example.net/github-webhook-sync",
        "https://sync-06fc92bb932d5425.example.org/webhook",
    ]
    assert extract_verified_urls_from_texts([" ".join(bad_urls)], repo_github_url="https://github.com/Org/MyRepo") == []
    md_leak = extract_verified_urls_from_texts(["See [https://dev.oaworkbench.org/](file:///home/dev/.gemini/antigravity/x.md)"])
    assert md_leak == ["https://dev.oaworkbench.org/"]

    t0 = time.monotonic()
    redos_urls = extract_verified_urls_from_texts(["CI run" + (" " * 20000) + "abc"], repo_github_url="https://github.com/Org/MyRepo")
    assert (time.monotonic() - t0) < 0.25 and redos_urls == []

    html_urls = extract_verified_urls_from_texts(["Guide https://FrankXLT.github.io/my-app/guide.html and [Demo](./demo/)."])
    assert "https://FrankXLT.github.io/my-app/guide.html" in html_urls
    assert "https://FrankXLT.github.io/my-app/demo/" in html_urls

    ext_urls = extract_verified_urls_from_texts(["Site https://docs.example.org/app/ with bare docs/ and [Demo](./demo/)."])
    assert "https://docs.example.org/app/" in ext_urls and "https://docs.example.org/app/demo/" in ext_urls
    assert "https://docs.example.org/app/docs/" not in ext_urls


def test_v421_gallery_http_security_deadbolt_and_empty_states(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify gallery HMAC domain separation, locked deadbolt isolation, security headers, errors, and empty state."""
    brain_root, _bg, db_file, repo_dir, _phrase, secret = _setup_sandbox(tmp_path, monkeypatch)
    cid = "11112222-3333-4444-8555-666677778888"
    empty_cid = "44445555-6666-4777-8888-999900001111"
    sym_cid = "22223333-4444-4555-8666-777788889999"
    missing_cid = "33334444-5555-4666-8777-888899990000"

    _make_png(brain_root / cid / "scratch" / "01_desktop.png", size=(1440, 900))
    (brain_root / cid / "walkthrough.md").write_text("Live https://FrankXLT.github.io/my-app/ and PR #7.", encoding="utf-8")
    (brain_root / empty_cid).mkdir(parents=True)
    (brain_root / sym_cid).symlink_to(repo_dir)

    con = sqlite3.connect(str(db_file))
    con.execute(
        "INSERT INTO conversation_summaries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (cid, "Gallery Sec Check", "", "proj-1", "CASCADE_RUN_STATUS_IDLE", 12, "2026-11-26T10:00:00Z", 0, 0, json.dumps([f"file://{repo_dir}"]), ""),
    )
    con.commit()
    con.close()

    assert cfg.SESSION_STATE["unlocked_at"] == 0.0 and not cfg.is_unlocked()
    app = build_nexus_http_app(secret, cfg.get_polyglot_mcp_token(secret), cfg.get_praxis_mcp_token(secret))
    exp = int(time.time()) + 3600
    with TestClient(app) as client:
        gal_sig = compute_gallery_hmac(exp, cid)
        med_sig = compute_media_hmac(exp, f"brain:{cid}", "scratch/01_desktop.png")
        assert client.get(f"/web/gallery/{exp}/{med_sig}/{cid}").status_code == 403
        assert client.get(f"/web/media/{exp}/{gal_sig}/brain%3A{cid}/scratch/01_desktop.png").status_code == 403

        signed_media = sign_media_url(f"brain:{cid}", "scratch/01_desktop.png", relative=True)
        assert f"/brain%3A{cid}/" in signed_media
        r_med = client.get(signed_media)
        assert r_med.status_code == 200 and r_med.headers["content-type"] == "image/png"

        gal_path = sign_gallery_url(cid, relative=True)
        r_get = client.get(f"{gal_path}?hl=en-US")
        assert r_get.status_code == 200
        assert "no-store" in r_get.headers["cache-control"]
        assert r_get.headers["referrer-policy"] == "no-referrer"
        csp = r_get.headers["content-security-policy"]
        assert "default-src 'self'" in csp and "script-src 'self'" in csp and "'unsafe-inline'" not in csp
        assert cfg.SESSION_STATE["unlocked_at"] == 0.0 and not cfg.is_unlocked()
        assert str(tmp_path) not in r_get.text and "/home/" not in r_get.text and secret not in r_get.text
        assert 'class="gal-link-pill"' in r_get.text and "#01" in r_get.text and "1440\u00d7900" in r_get.text

        r_head = client.head(f"{gal_path}?hl=en-US")
        assert r_head.status_code == 200 and r_head.content == b""
        for bad_head in (f"/web/gallery/{exp}/{'0'*32}/{cid}", sign_gallery_url(cid, exp_ts=int(time.time()) - 10, relative=True)):
            rh = client.head(bad_head)
            assert rh.status_code == 403 and rh.content == b""
        assert client.get("/web/gallery_page.css").status_code == 200
        assert client.get("/web/gallery_page.js").status_code == 200

        sw_text = (REPO_ROOT / "web" / "sw.js").read_text(encoding="utf-8")
        assert "/web/gallery/" not in sw_text
        shell_block = sw_text.split("const SHELL_NAMES = new Set([", 1)[1].split("]);", 1)[0]
        assert '"gallery_page.css"' in shell_block and '"gallery_page.js"' in shell_block and '"gallery/' not in shell_block

        err_checks = [
            (client.get(f"/web/gallery/{exp}/{'0'*32}/{cid}"), 403),
            (client.get(f"/web/gallery/{exp}/{gal_sig}/{empty_cid}"), 403),
            (client.get(sign_gallery_url(cid, exp_ts=int(time.time()) - 10, relative=True)), 403),
            (client.get("/web/gallery/bad-ts/abc/cid"), 403),
            (client.get("/web/gallery/onlyone"), 403),
            (client.get(sign_gallery_url(sym_cid, relative=True)), 403),
            (client.get(sign_gallery_url(missing_cid, relative=True)), 404),
        ]
        for resp, code in err_checks:
            assert resp.status_code == code
            for leak in ("Gallery Sec Check", "01_desktop.png", str(tmp_path)):
                assert leak not in resp.text

        monkeypatch.setattr(cfg, "PASS_HASH", "")
        r_nopass = client.get(f"/web/gallery/{exp}/{compute_gallery_hmac(exp, cid, pass_hash='')}/{cid}")
        assert r_nopass.status_code == 403
        monkeypatch.setattr(cfg, "PASS_HASH", cfg.normalize_phrase("canary gallery shield open"))

        r_empty = client.get(sign_gallery_url(empty_cid, relative=True))
        assert r_empty.status_code == 200
        assert '<nav class="gal-links-bar"' not in r_empty.text
        grid_html = r_empty.text.split('<section class="gal-grid"', 1)[1].split("</section>", 1)[0]
        assert 'class="gal-empty"' in grid_html and "<img" not in grid_html


def test_v421_compaction_preservation_mcp_tools_and_hygiene(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify middle-compaction verified_urls preservation, MCP wire budgets, Rule 7, closeout, docs, and line caps."""
    brain_root, _bg, db_file, repo_dir, phrase, secret = _setup_sandbox(tmp_path, monkeypatch)
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", "git@github.com:FrankXLT/demo-gallery-repo.git"], cwd=str(repo_dir), check=True, capture_output=True)

    cid = "55556666-7777-4888-9999-000011112222"
    sdir = brain_root / cid
    (sdir / "scratch").mkdir(parents=True)
    (sdir / ".system_generated" / "logs").mkdir(parents=True)
    _make_png(sdir / "scratch" / "01_shot.png", size=(1440, 900))
    _make_png(sdir / "scratch" / "02_shot.png", size=(800, 600))

    pad_head = "Alpha filler line for middle compaction check. " * 70
    pad_tail = "Omega filler line for middle compaction check. " * 70
    (sdir / "task.md").write_text(f"# Task\n{pad_head}\nMiddle https://FrankXLT.github.io/demo-site/ and ./demo/ and PR #42.\n{pad_tail}", encoding="utf-8")
    (sdir / "walkthrough.md").write_text(f"# Walkthrough\n{pad_head}\nMiddle [Docs](./docs/) and CI run #556677.\n{pad_tail}", encoding="utf-8")
    t_entry = json.dumps({"type": "PLANNER_RESPONSE", "created_at": "2026-11-26T10:00:00Z", "content": f"{pad_head}\nUpdated [Overview](./) and ./demo/#workspace.\n{pad_tail}"})
    (sdir / ".system_generated" / "logs" / "transcript_full.jsonl").write_text(t_entry + "\n", encoding="utf-8")
    con = sqlite3.connect(str(db_file))
    con.execute("INSERT INTO conversation_summaries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (cid, "Compaction Gallery Test", "", "", "CASCADE_RUN_STATUS_IDLE", 20, "2026-11-26T10:00:00Z", 0, 0, json.dumps([f"file://{repo_dir}"]), ""))
    con.commit()
    con.close()
    cfg.pin_session_context(cid, title="Compaction Gallery Test", project_name="Demo Gallery", workspace=str(repo_dir), set_default=True)
    monkeypatch.setattr(tsession_mod, "_collect_git_summary", lambda _p: {"branch": "main", "status_short": ""})

    app = build_nexus_http_app(secret, cfg.get_polyglot_mcp_token(secret), cfg.get_praxis_mcp_token(secret))
    with TestClient(app) as client:
        _, load_pay, _ = _call_mcp(client, secret, 1, "load_session_into_gemini", {"session_identifier": cid, "spoken_passphrase": phrase})
        assert "/web/gallery/" in load_pay["gallery_url"]
        for u in (
            "https://FrankXLT.github.io/demo-site/",
            "https://FrankXLT.github.io/demo-site/demo/",
            "https://FrankXLT.github.io/demo-site/demo/#workspace",
            "https://FrankXLT.github.io/demo-site/docs/",
            "https://github.com/FrankXLT/demo-gallery-repo/pull/42",
            "https://github.com/FrankXLT/demo-gallery-repo/actions/runs/556677",
        ):
            assert u in load_pay["verified_urls"]
        assert "556677" not in load_pay["walkthrough"] and "PR #42" not in load_pay["task_content"]
        assert "#workspace" not in load_pay["latest_assistant_response"]
        assert sg_mod.COPY_READY_LINK_GUIDANCE == sg_mod.EMBEDDED_LINK_GUIDANCE
        assert sg_mod.EMBEDDED_LINK_GUIDANCE in load_pay["assistant_guidance"]
        assert cfg.REPLY_PROMPT_GUIDANCE in load_pay["assistant_guidance"]
        assert load_pay["visual_inspection_hint"] == media_mod.VISUAL_INSPECTION_HINT

        _, cloud_pay, cloud_blocks = _call_mcp(
            client, secret, 2, "inspect_visual_artifacts", {"session_identifier": cid},
            headers={"User-Agent": "google-http-client/2.0"},
        )
        assert cloud_pay["cloud_fast_path"] is True and cloud_pay["returned_images"] == 0 and len(cloud_blocks) == 1
        assert "/web/gallery/" in cloud_pay["gallery_url"] and "https://FrankXLT.github.io/demo-site/demo/" in cloud_pay["verified_urls"]
        assert sg_mod.EMBEDDED_LINK_GUIDANCE in cloud_pay["assistant_guidance"] and cfg.REPLY_PROMPT_GUIDANCE in cloud_pay["assistant_guidance"]

        _, local_pay, local_blocks = _call_mcp(
            client, secret, 3, "inspect_visual_artifacts", {"session_identifier": cid, "targets": "1-2"},
            headers={"User-Agent": "local-cli/1.0"},
        )
        assert local_pay["returned_images"] == 2 and len(local_blocks) == 3 and local_blocks[1]["type"] == "image"
        assert "/web/gallery/" in local_pay["gallery_url"] and local_pay["verified_urls"]
        assert sg_mod.EMBEDDED_LINK_GUIDANCE in local_pay["assistant_guidance"] and cfg.REPLY_PROMPT_GUIDANCE in local_pay["assistant_guidance"]

    assert "7. EMBEDDED PLAIN-LABEL WEB LINKS" in cfg.mcp.instructions and "gallery_url" in cfg.mcp.instructions
    assert "7. COPY-READY CODE BLOCK LINK RULE" not in cfg.mcp.instructions
    for txt in (sg_mod.EMBEDDED_LINK_GUIDANCE, cfg.mcp.instructions, media_mod.VISUAL_INSPECTION_HINT):
        low = txt.lower()
        assert "never" in low and "code blocks" in low and "[...]" in txt
        assert "Open Session Gallery" in txt and "Open in Antigravity Web" in txt
    assert "Google-Agent" in media_mod.VISUAL_INSPECTION_HINT and "uses extra tokens" in media_mod.VISUAL_INSPECTION_HINT
    closeout_txt = ret_mod.get_closeout_directives(str(repo_dir), cid)
    assert "Full HTTPS Closeout Links" in closeout_txt and "https://" in closeout_txt
    wf_doc = (REPO_ROOT / "docs" / "WORKFLOWS.md").read_text(encoding="utf-8")
    for term in ("Signed Session Gallery Page", "Top-Level Verified URL List", "Embedded Plain-Label Web Links", "Percent-Encoded Media Scope"):
        assert term in wf_doc
    for banned in ("diurnal", "plain-english", "posture", "surface"):
        assert banned not in wf_doc.lower()
    dep_doc = (REPO_ROOT / "docs" / "DEPLOYMENT.md").read_text(encoding="utf-8")
    assert "/web/gallery/" in dep_doc and "if ($request_uri !~" in dep_doc
    for rel in ("src/agy_nexus/verified_urls.py", "src/agy_nexus/session_gallery.py", "src/agy_nexus/web_routes.py", "src/agy_nexus/tools_session.py", "src/agy_nexus/tools_media.py", "src/agy_nexus/media.py", "web/gallery_page.css", "web/gallery_page.js"):
        assert len((REPO_ROOT / rel).read_text(encoding="utf-8").splitlines()) <= 500
    assert len((REPO_ROOT / "src" / "agy_nexus" / "retirement.py").read_text(encoding="utf-8").splitlines()) <= 220


def test_v421_wire_cap_stress_media_and_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Stress-test <= 20 KB wire caps with 4 textured PNGs + 1 SVG + long verified_urls + >25 KB task.md."""
    brain_root, _bg, db_file, repo_dir, phrase, secret = _setup_sandbox(tmp_path, monkeypatch)
    cid = "66667777-8888-4999-8000-111122223333"
    sdir = brain_root / cid
    (sdir / "scratch").mkdir(parents=True)
    for i in range(1, 5):
        _make_png(sdir / "scratch" / f"{i:02d}_textured.png", size=(480, 320), textured=True)
    (sdir / "scratch" / "05_chart.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg' width='200' height='100'></svg>", encoding="utf-8")
    long_walk_urls = [f"https://sub{i}.example.org/" + ("path/" * 30) + f"v{i}" for i in range(10)]
    long_task_urls = [f"https://t{i}.example.org/" + ("seg/" * 92) + f"p{i}" for i in range(12)]
    (sdir / "walkthrough.md").write_text("# Walk\n" + "\n".join(long_walk_urls), encoding="utf-8")
    (sdir / "task.md").write_text("# Task\n" + "\n".join(long_task_urls) + "\n" + ("Detail line. " * 2200), encoding="utf-8")
    con = sqlite3.connect(str(db_file))
    con.execute("INSERT INTO conversation_summaries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (cid, "Wire Stress Test", "", "", "CASCADE_RUN_STATUS_IDLE", 10, "2026-11-26T10:00:00Z", 0, 0, json.dumps([f"file://{repo_dir}"]), ""))
    con.commit()
    con.close()
    cfg.pin_session_context(cid, title="Wire Stress Test", project_name="Demo Gallery", workspace=str(repo_dir), set_default=True)
    monkeypatch.setattr(tsession_mod, "_collect_git_summary", lambda _p: {"branch": "main", "status_short": ""})

    app = build_nexus_http_app(secret, cfg.get_polyglot_mcp_token(secret), cfg.get_praxis_mcp_token(secret))
    with TestClient(app) as client:
        raw_m, pay_m, blocks_m = _call_mcp(
            client, secret, 1, "inspect_visual_artifacts",
            {"session_identifier": cid, "targets": "1-4", "limit": 4, "spoken_passphrase": phrase},
            headers={"User-Agent": "local-cli/1.0"},
        )
        assert len(raw_m) <= 20_480 and "/web/gallery/" in pay_m["gallery_url"] and pay_m["returned_images"] == 4 and len(blocks_m) == 5
        raw_s, pay_s, _ = _call_mcp(client, secret, 2, "load_session_into_gemini", {"session_identifier": cid, "spoken_passphrase": phrase})
        assert len(raw_s) <= 20_480 and "/web/gallery/" in pay_s["gallery_url"]


def test_v421_gallery_css_contracts() -> None:
    """Verify gallery_page.css layout, scroll-lock, truncation, and zero !important contracts."""
    css_text = (REPO_ROOT / "web" / "gallery_page.css").read_text(encoding="utf-8")
    js_text = (REPO_ROOT / "web" / "gallery_page.js").read_text(encoding="utf-8")
    assert "!important" not in css_text
    assert "innerHTML" not in js_text
    assert not re.search(r"[\u2600-\u27BF\U0001F300-\U0001FAFF]", js_text)
    assert re.search(r"\.gal-lb-stage\.is-native[^{]*\{[^}]*display:\s*block", css_text)
    assert re.search(r"\.gal-empty\s*\{[^}]*grid-column:\s*1\s*/\s*-1", css_text)
    assert ":modal" in css_text and re.search(r"body:has\(dialog\.gal-dialog:modal\)\s*\{\s*overflow:\s*hidden", css_text)
    assert re.search(r"\.gal-chip[^{]*\{[^}]*text-overflow:\s*ellipsis", css_text)


def test_v421_frontend_gallery_page_node_vm_checks() -> None:
    """Verify gallery_page.js theme query/fallback, unsafe URL blocking, closedBy fallback, and lightbox."""
    node_bin = shutil.which("node")
    assert node_bin, "Node.js is required for frontend gallery_page.js tests"
    driver = r"""
const vm = require("vm"), fs = require("fs");
const code = fs.readFileSync(process.argv[1], "utf8");
const mkList = () => { const s = new Set(); return { add: (...a) => a.forEach((x) => s.add(x)), remove: (...a) => a.forEach((x) => s.delete(x)), toggle: (x, f) => (f === undefined ? (s.has(x) ? (s.delete(x), false) : (s.add(x), true)) : (f ? (s.add(x), true) : (s.delete(x), false))), contains: (x) => s.has(x) }; };
function makeEl(id, extra = {}) {
  const attrs = {}, listeners = {};
  return Object.assign({ id, textContent: "", disabled: false, open: false, clientWidth: 800, scrollWidth: 800, classList: mkList(), style: {}, parentElement: null,
    setAttribute: (k, v) => { attrs[k] = String(v); }, getAttribute: (k) => (k in attrs ? attrs[k] : null), removeAttribute: (k) => { delete attrs[k]; },
    addEventListener: (t, fn) => { (listeners[t] = listeners[t] || []).push(fn); }, dispatch: (t, ev = {}) => { (listeners[t] || []).forEach((fn) => fn(ev)); },
    querySelector: () => null, querySelectorAll: () => [], closest: () => null, getBoundingClientRect: () => ({ left: 10, right: 90, top: 10, bottom: 90 }) }, extra);
}
function runCase(search, items, hasClosedBy) {
  class Element {}
  const btns = items.map((_, i) => { const b = makeEl("b" + i); b.setAttribute("data-gal-index", String(i)); b.closest = (s) => (s === "[data-gal-index]" ? b : null); Object.setPrototypeOf(b, Element.prototype); return b; });
  const grid = makeEl("galGrid", { querySelectorAll: () => btns });
  const dlg = makeEl("galLightbox", { showModal() { this.open = true; }, close() { this.open = false; } });
  const els = { galThemeBtn: makeEl("galThemeBtn"), galGrid: grid, galLightbox: dlg, galLbImg: makeEl("galLbImg", { complete: false, naturalWidth: 0 }),
    galLbStage: makeEl("galLbStage"), galLbTitle: makeEl("galLbTitle"), galLbMeta: makeEl("galLbMeta"), galLbRawLink: makeEl("galLbRawLink"),
    galLbFitBtn: makeEl("galLbFitBtn"), galLbNativeBtn: makeEl("galLbNativeBtn"), galLbPrevBtn: makeEl("galLbPrevBtn"), galLbNextBtn: makeEl("galLbNextBtn"),
    galLbCloseBtn: makeEl("galLbCloseBtn"), galleryData: makeEl("galleryData", { textContent: JSON.stringify({ screenshots: items }) }) };
  const store = {}, proto = hasClosedBy ? { closedBy: "any" } : {};
  const sb = { Element, URLSearchParams, HTMLDialogElement: { prototype: proto },
    window: { location: { search }, localStorage: { getItem: (k) => store[k] || null, setItem: (k, v) => { store[k] = String(v); } }, matchMedia: () => ({ matches: false, addEventListener: () => {} }) },
    document: { documentElement: { dataset: {} }, getElementById: (id) => els[id] || null, addEventListener: () => {} } };
  if (!hasClosedBy) delete sb.HTMLDialogElement.prototype.closedBy;
  vm.runInNewContext(code, sb);
  return { sb, els, dlg, grid, btns, store };
}
const c1 = runCase("", [{ index: 1, name: "01.png", signed_url: "/web/media/99/sig1/brain%3Acid/01.png", width: 1440, height: 900, size_label: "42 KB" },
  { index: 2, name: "02.png", signed_url: "/web/media/99/sig2/brain%3Acid/02.png", width: 800, height: 600, size_label: "21 KB" }], true);
const themesSeen = [c1.sb.document.documentElement.dataset.theme];
for (let i = 0; i < 3; i++) { c1.els.galThemeBtn.dispatch("click"); themesSeen.push(c1.sb.document.documentElement.dataset.theme); }
c1.grid.dispatch("click", { target: c1.btns[0], preventDefault: () => {} });
const opened = c1.dlg.open, src0 = c1.els.galLbImg.getAttribute("src"), fit0 = c1.els.galLbStage.classList.contains("is-fit");
c1.els.galLbNextBtn.dispatch("click"); const src1 = c1.els.galLbImg.getAttribute("src");
c1.els.galLbNativeBtn.dispatch("click"); const nat = c1.els.galLbStage.classList.contains("is-native") && c1.els.galLbNativeBtn.getAttribute("aria-pressed") === "true";
c1.els.galLbFitBtn.dispatch("click"); const fitBack = c1.els.galLbStage.classList.contains("is-fit") && c1.els.galLbFitBtn.getAttribute("aria-pressed") === "true";
c1.els.galLbCloseBtn.dispatch("click");
const cPaper = runCase("?theme=paper&hl=en-US", [{ index: 1, name: "x.png", signed_url: "/web/media/1/s/b/x.png" }], true);
const cBogus = runCase("?theme=bogus", [{ index: 1, name: "x.png", signed_url: "/web/media/1/s/b/x.png" }], true);
const cBad = runCase("", [{ index: 1, name: "a", signed_url: "javascript:alert(1)", raw_url: "\tjavascript:alert(2)" },
  { index: 2, name: "b", signed_url: "data:text/html,alert(1)", raw_url: "data:text/html,alert(1)" }], false);
cBad.grid.dispatch("click", { target: cBad.btns[0], preventDefault: () => {} });
const bad0 = [cBad.els.galLbImg.getAttribute("src"), cBad.els.galLbRawLink.getAttribute("href")];
cBad.els.galLbNextBtn.dispatch("click");
const bad1 = [cBad.els.galLbImg.getAttribute("src"), cBad.els.galLbRawLink.getAttribute("href")];
cBad.dlg.dispatch("pointerdown", { target: cBad.dlg, clientX: 2, clientY: 2 });
cBad.dlg.dispatch("pointerup", { target: cBad.dlg, clientX: 2, clientY: 2 });
console.log(JSON.stringify({ themesSeen, stored: c1.store.agy_gallery_theme, opened, src0, fit0, src1, nat, fitBack, closed: !c1.dlg.open,
  tPaper: cPaper.sb.document.documentElement.dataset.theme, tBogus: cBogus.sb.document.documentElement.dataset.theme, bad0, bad1, closedFallback: !cBad.dlg.open }));
"""
    out = json.loads(subprocess.run([node_bin, "-e", driver, str(REPO_ROOT / "web" / "gallery_page.js")], capture_output=True, text=True, check=True).stdout.strip())
    assert out["themesSeen"] == ["white", "paper", "dark-paper", "dark"] and out["stored"] == "dark"
    assert out["opened"] and out["fit0"] and out["nat"] and out["fitBack"] and out["closed"]
    assert out["src0"] == "/web/media/99/sig1/brain%3Acid/01.png" and out["src1"] == "/web/media/99/sig2/brain%3Acid/02.png"
    assert out["tPaper"] == "paper" and out["tBogus"] == "white"
    assert out["bad0"] == [None, None] and out["bad1"] == [None, None] and out["closedFallback"] is True
