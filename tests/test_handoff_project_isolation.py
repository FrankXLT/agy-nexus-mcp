#!/usr/bin/env python3
"""Regression suite for handoff project isolation, 3-pillar normalization, fail-closed greenfield guardrails, and JSON conversationId extraction."""
from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
from typing import Any

PKG_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PKG_ROOT / "src"
for p_add in (SRC_DIR, PKG_ROOT):
    if str(p_add) not in sys.path:
        sys.path.insert(0, str(p_add))

import agy_nexus.config as cfg
import agy_nexus.handoff as handoff_mod
from agy_nexus.handoff import send_handoff_and_resume
from host_bridge.project_manager import (
    extract_agentapi_conversation_id,
    normalize_host_workspace_path,
    resolve_or_create_project,
)


def _setup_isolated_env(tmp_root: Path) -> dict[str, Any]:
    fake_home = tmp_root / "home" / "dev"
    ws_dir = fake_home / "agentic_workspace"
    proj_dir = ws_dir / "projects"
    wb_dir = ws_dir / "workbooks"
    cfg_repo_dir = ws_dir / "configuration"
    agy_cfg_dir = fake_home / ".gemini" / "config"
    brain_dir = fake_home / ".gemini" / "antigravity" / "brain"
    bg_dir = fake_home / ".gemini" / "antigravity" / "sidecar_data" / "ag-bridge-bg"
    for d in (proj_dir, wb_dir, cfg_repo_dir / "antigravity-config", agy_cfg_dir / "projects", brain_dir, bg_dir):
        d.mkdir(parents=True, exist_ok=True)

    nexus_repo = proj_dir / "agy-nexus-mcp"
    nexus_repo.mkdir()
    nexus_pid = "11111111-2222-4333-8444-555555555555"
    cfg_pid = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    (agy_cfg_dir / "projects" / f"{nexus_pid}.json").write_text(
        json.dumps(
            {
                "id": nexus_pid,
                "name": "AGY Nexus MCP",
                "projectResources": {"resources": [{"gitFolder": {"folderUri": f"file://{nexus_repo}/", "defaultBranch": "main"}}]},
            }
        ),
        encoding="utf-8",
    )
    (agy_cfg_dir / "projects" / f"{cfg_pid}.json").write_text(
        json.dumps(
            {
                "id": cfg_pid,
                "name": "antigravity-config",
                "projectResources": {"resources": [{"gitFolder": {"folderUri": f"file://{cfg_repo_dir / 'antigravity-config'}/", "defaultBranch": "main"}}]},
            }
        ),
        encoding="utf-8",
    )
    prior_nexus_cid = "22222222-3333-4444-8555-666666666666"
    prior_logs = brain_dir / prior_nexus_cid / ".system_generated" / "logs"
    presence_dir = fake_home / ".gemini" / "antigravity" / "presence"
    prior_logs.mkdir(parents=True)
    presence_dir.mkdir(parents=True, exist_ok=True)
    (prior_logs / "transcript.jsonl").write_text(
        json.dumps({"type": "PLANNER_RESPONSE", "content": "Prior Nexus turn summary."}) + "\n",
        encoding="utf-8",
    )
    db_file = fake_home / ".gemini" / "antigravity" / "conversation_summaries.db"
    con = sqlite3.connect(str(db_file))
    try:
        con.execute(
            "CREATE TABLE conversation_summaries ("
            "conversation_id TEXT, title TEXT, preview TEXT, step_count INTEGER, "
            "last_modified_time TEXT, workspace_uris TEXT, status TEXT, "
            "not_fully_idle INTEGER, killed INTEGER, parent_conversation_id TEXT, project_id TEXT)"
        )
        con.execute(
            "INSERT INTO conversation_summaries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                prior_nexus_cid,
                "Refactor auth token handling in agy-nexus-mcp",
                "",
                12,
                "2026-11-14T10:00:00Z",
                json.dumps([f"file://{nexus_repo}/"]),
                "CASCADE_RUN_STATUS_IDLE",
                0,
                0,
                "",
                nexus_pid,
            ),
        )
        con.commit()
    finally:
        con.close()
    return {
        "fake_home": fake_home,
        "ws_dir": ws_dir,
        "proj_dir": proj_dir,
        "wb_dir": wb_dir,
        "cfg_repo_dir": cfg_repo_dir,
        "agy_cfg_dir": agy_cfg_dir,
        "brain_dir": brain_dir,
        "bg_dir": bg_dir,
        "db_file": db_file,
        "presence_dir": presence_dir,
        "state_file": bg_dir / "session_state.json",
        "nexus_repo": nexus_repo,
        "nexus_pid": nexus_pid,
        "cfg_pid": cfg_pid,
        "prior_nexus_cid": prior_nexus_cid,
    }


def test_greenfield_fail_closed_and_explicit_create_new_project() -> None:
    phrase = "Isolation Guard 2026!"
    saved = {
        "PASS_HASH": cfg.PASS_HASH,
        "AGY_WORKSPACE_DIR": cfg.AGY_WORKSPACE_DIR,
        "AGY_PROJECTS_DIR": cfg.AGY_PROJECTS_DIR,
        "AGY_WORKBOOKS_DIR": cfg.AGY_WORKBOOKS_DIR,
        "AGY_CONFIGURATION_DIR": cfg.AGY_CONFIGURATION_DIR,
        "AGY_GITLAB_DIR": cfg.AGY_GITLAB_DIR,
        "AGY_CONFIG_DIR": cfg.AGY_CONFIG_DIR,
        "AGY_BRAIN_DIR": cfg.AGY_BRAIN_DIR,
        "AGY_BG_DIR": cfg.AGY_BG_DIR,
        "AGY_DB_FILE": cfg.AGY_DB_FILE,
        "AGY_PRESENCE_DIR": cfg.AGY_PRESENCE_DIR,
        "STATE_FILE": cfg.STATE_FILE,
        "post_bridge": handoff_mod._post_bridge,
        "sel_sess": cfg.SESSION_STATE.get("selected_session", ""),
        "sel_ws": cfg.SESSION_STATE.get("selected_workspace", ""),
        "sel_proj": cfg.SESSION_STATE.get("selected_project", ""),
    }
    cfg.PASS_HASH = hashlib.sha256(b"isolationguard2026").hexdigest()

    with tempfile.TemporaryDirectory() as tmp_str:
        env = _setup_isolated_env(Path(tmp_str))
        cfg.AGY_WORKSPACE_DIR = env["ws_dir"]
        cfg.AGY_PROJECTS_DIR = env["proj_dir"]
        cfg.AGY_WORKBOOKS_DIR = env["wb_dir"]
        cfg.AGY_CONFIGURATION_DIR = env["cfg_repo_dir"]
        cfg.AGY_GITLAB_DIR = env["proj_dir"]
        cfg.AGY_CONFIG_DIR = env["agy_cfg_dir"]
        cfg.AGY_BRAIN_DIR = env["brain_dir"]
        cfg.AGY_BG_DIR = env["bg_dir"]
        cfg.AGY_DB_FILE = env["db_file"]
        cfg.AGY_PRESENCE_DIR = env["presence_dir"]
        cfg.STATE_FILE = env["state_file"]
        cfg.SESSION_STATE["selected_session"] = env["prior_nexus_cid"]
        cfg.SESSION_STATE["selected_workspace"] = str(env["nexus_repo"])
        cfg.SESSION_STATE["selected_project"] = env["nexus_pid"]
        cfg.SESSION_STATE["session_workspace_map"][env["prior_nexus_cid"]] = str(env["nexus_repo"])
        cfg.SESSION_STATE["session_project_map"][env["prior_nexus_cid"]] = env["nexus_pid"]
        cfg.SESSION_STATE["session_title_map"][env["prior_nexus_cid"]] = "Refactor auth token handling in agy-nexus-mcp"

        captured_bridge_calls: list[dict[str, Any]] = []
        spawned_cid = "33333333-4444-4555-8666-777777777777"
        created_pid = "77777777-8888-4999-aaaa-bbbbbbbbbbbb"

        def _fake_bridge(payload: dict[str, Any]) -> dict[str, Any]:
            captured_bridge_calls.append(payload)
            return {
                "ok": True,
                "returncode": 0,
                "conversation_id": spawned_cid if payload.get("action") == "new-conversation" else "",
                "project_id": payload.get("project_id") or created_pid,
                "project_name": payload.get("project_name") or "Civic Atlas",
                "workspace_path": payload.get("workspace_path") or "",
                "project_created": True,
            }

        handoff_mod._post_bridge = _fake_bridge
        try:
            spec_md = (
                "# [Civic Atlas] Init & Sprint 0\n\n"
                "Initialize repository on branch `develop` using `modern-web-guidance` and `agy-polyglot-mcp`."
            )
            # 1. Fail-closed when create_new_project=False (never falls back to agy-nexus-mcp!)
            blocked = json.loads(
                send_handoff_and_resume(
                    research_markdown=spec_md,
                    workspace_path=str(env["fake_home"] / "projects" / "civic-atlas"),
                    activate_skills="agy-nexus-stats, modern-web-guidance, dual-review",
                    resume_headless=True,
                    create_new_project=False,
                    spoken_passphrase=phrase,
                )
            )
            assert blocked["ok"] is False and blocked["status"] == "PROJECT_NOT_FOUND"
            assert blocked["repo_slug"] == "civic-atlas"
            assert blocked["suggested_workspace_path"] == str(env["proj_dir"] / "civic-atlas")
            assert blocked["suggested_default_branch"] == "develop"
            assert len(captured_bridge_calls) == 0

            # 1b. Substring 'projects/nexus' or 'projects/auth' must NOT fuzzy-match AGY Nexus MCP or title words!
            for sub_ws in ("projects/nexus", "projects/auth"):
                sub_blk = json.loads(
                    send_handoff_and_resume(
                        research_markdown="# Substring Service\nInit.",
                        workspace_path=sub_ws,
                        create_new_project=False,
                        spoken_passphrase=phrase,
                    )
                )
                assert sub_blk["ok"] is False and sub_blk["status"] == "PROJECT_NOT_FOUND", f"Fuzzy match leaked on {sub_ws}: {sub_blk}"

            # 1c. Symlink escape, dot-segments, and unauthorized paths fail closed with OUTSIDE_ALLOWED_ROOTS
            outside_dir = Path(tmp_str) / "outside_escape"
            outside_dir.mkdir()
            (env["proj_dir"] / "symlink-escape").symlink_to(outside_dir)
            for bad_ws in ("/etc/forbidden-repo", "projects/.", "projects/symlink-escape", "projects/symlink-escape/child"):
                bad_res = json.loads(
                    send_handoff_and_resume(
                        research_markdown=spec_md,
                        workspace_path=bad_ws,
                        create_new_project=True,
                        spoken_passphrase=phrase,
                    )
                )
                assert bad_res["ok"] is False and bad_res["status"] == "OUTSIDE_ALLOWED_ROOTS", f"Expected OUTSIDE_ALLOWED_ROOTS for {bad_ws}: {bad_res}"

            # 2. Explicit create_new_project=True normalizes ~/projects/<slug>, infers branch='develop', and omits foreign Baton!
            res_ok = json.loads(
                send_handoff_and_resume(
                    research_markdown=spec_md,
                    workspace_path=str(env["fake_home"] / "projects" / "civic-atlas"),
                    activate_skills="agy-nexus-stats, modern-web-guidance, dual-review",
                    resume_headless=True,
                    create_new_project=True,
                    spoken_passphrase=phrase,
                )
            )
            assert res_ok["ok"] is True and res_ok["status"] == "RESUMED"
            assert res_ok["handoff_id"] == "civic-atlas-01"
            assert res_ok["project_id"] == created_pid
            assert res_ok["project_name"] == "Civic Atlas"
            assert res_ok["workspace_path"] == str(env["proj_dir"] / "civic-atlas")
            assert res_ok["conversation_id"] == spawned_cid
            assert len(captured_bridge_calls) == 1
            b_call = captured_bridge_calls[0]
            assert b_call["create_new_project"] is True and b_call["default_branch"] == "develop" and b_call["project_id"] == ""
            assert "Prior Session Baton" not in b_call["prompt"] and env["prior_nexus_cid"] not in b_call["prompt"]

            # 3. Two-step STAGED_ONLY (+ append_to_existing=True) -> RESUME_STAGED preserves both turns + greenfield flags
            captured_bridge_calls.clear()
            staged_gf = json.loads(
                send_handoff_and_resume(
                    research_markdown="# Greenfield Studio Spec\n\nPart 1 on branch `develop`.",
                    workspace_path="projects/greenfield-studio",
                    create_new_project=True,
                    resume_headless=False,
                    spoken_passphrase=phrase,
                )
            )
            assert staged_gf["ok"] is True and staged_gf["handoff_id"] == "greenfield-studio-01"
            appended_gf = json.loads(
                send_handoff_and_resume(
                    research_markdown="Part 2 appended requirements.",
                    workspace_path="projects/greenfield-studio",
                    create_new_project=True,
                    append_to_existing=True,
                    resume_headless=False,
                    spoken_passphrase=phrase,
                )
            )
            assert appended_gf["ok"] is True and appended_gf["handoff_id"] == "greenfield-studio-01"
            captured_bridge_calls.clear()
            resumed_gf = json.loads(
                send_handoff_and_resume(
                    research_markdown="RESUME_STAGED",
                    handoff_id="greenfield-studio-01",
                    resume_headless=True,
                    spoken_passphrase=phrase,
                )
            )
            assert resumed_gf["ok"] is True and resumed_gf["status"] == "RESUMED"
            assert "Part 1 on branch `develop`." in captured_bridge_calls[0]["prompt"]
            assert "Part 2 appended requirements." in captured_bridge_calls[0]["prompt"]
            assert captured_bridge_calls[0]["create_new_project"] is True and captured_bridge_calls[0]["default_branch"] == "develop"

            # 4. customization_edit_scope='global' isolates STAGED_ONLY onto antigravity-config & blocks /etc/evil
            bad_glob = json.loads(
                send_handoff_and_resume(
                    research_markdown="# Global Skill Edit",
                    workspace_path="/etc/evil",
                    customization_edit_scope="global",
                    spoken_passphrase=phrase,
                )
            )
            assert bad_glob["ok"] is False and bad_glob["status"] == "OUTSIDE_ALLOWED_ROOTS"
            glob_staged = json.loads(
                send_handoff_and_resume(
                    research_markdown="# Global Skill Edit\nUpdate global skill.",
                    customization_edit_scope="global",
                    resume_headless=False,
                    spoken_passphrase=phrase,
                )
            )
            assert glob_staged["ok"] is True and glob_staged["repo_slug"] == "antigravity-config"
            assert glob_staged["project_id"] == env["cfg_pid"]
            assert glob_staged["conversation_id"] == ""

            # 5. Prose filenames ('create configuration/settings.json') on existing session do NOT trigger PROJECT_NOT_FOUND
            existing_ok = json.loads(
                send_handoff_and_resume(
                    research_markdown="# Follow-up\nPlease create configuration/settings.json inside the module.",
                    session_identifier=env["prior_nexus_cid"],
                    resume_headless=False,
                    spoken_passphrase=phrase,
                )
            )
            assert existing_ok["ok"] is True and existing_ok["conversation_id"] == env["prior_nexus_cid"]
        finally:
            cfg.PASS_HASH = saved["PASS_HASH"]
            cfg.AGY_WORKSPACE_DIR = saved["AGY_WORKSPACE_DIR"]
            cfg.AGY_PROJECTS_DIR = saved["AGY_PROJECTS_DIR"]
            cfg.AGY_WORKBOOKS_DIR = saved["AGY_WORKBOOKS_DIR"]
            cfg.AGY_CONFIGURATION_DIR = saved["AGY_CONFIGURATION_DIR"]
            cfg.AGY_GITLAB_DIR = saved["AGY_GITLAB_DIR"]
            cfg.AGY_CONFIG_DIR = saved["AGY_CONFIG_DIR"]
            cfg.AGY_BRAIN_DIR = saved["AGY_BRAIN_DIR"]
            cfg.AGY_BG_DIR = saved["AGY_BG_DIR"]
            cfg.AGY_DB_FILE = saved["AGY_DB_FILE"]
            cfg.AGY_PRESENCE_DIR = saved["AGY_PRESENCE_DIR"]
            cfg.STATE_FILE = saved["STATE_FILE"]
            handoff_mod._post_bridge = saved["post_bridge"]
            cfg.SESSION_STATE["selected_session"] = saved["sel_sess"]
            cfg.SESSION_STATE["selected_workspace"] = saved["sel_ws"]
            cfg.SESSION_STATE["selected_project"] = saved["sel_proj"]
            cfg.SESSION_STATE["session_workspace_map"].pop(env["prior_nexus_cid"], None)
            cfg.SESSION_STATE["session_project_map"].pop(env["prior_nexus_cid"], None)
            cfg.SESSION_STATE["session_title_map"].pop(env["prior_nexus_cid"], None)


def test_agentapi_conversation_id_parser_and_host_project_manager() -> None:
    baton_uuid = "22222222-3333-4444-8555-666666666666"
    real_uuid = "33333333-4444-4555-8666-777777777777"
    agentapi_stdout = "[INFO] Connecting to LS...\n" + json.dumps(
        {
            "method": "newConversation",
            "request": {"prompt": f"# Sprint 0\n\n## Prior Session Baton ({baton_uuid})\nOld summary..."},
            "response": {"newConversation": {"conversationId": real_uuid}},
        },
        indent=2,
    ) + "\n[INFO] Done."
    assert extract_agentapi_conversation_id(agentapi_stdout, disallow_ids={baton_uuid}) == real_uuid
    assert extract_agentapi_conversation_id(agentapi_stdout) == real_uuid
    truncated_stdout = f'{{"prompt": "Baton {baton_uuid}", "conversationId": "{real_uuid}"'
    assert extract_agentapi_conversation_id(truncated_stdout) == real_uuid

    with tempfile.TemporaryDirectory() as tmp_str:
        env = _setup_isolated_env(Path(tmp_str))
        norm = normalize_host_workspace_path(
            str(env["fake_home"] / "projects" / "civic-maps"),
            env["ws_dir"],
            env["proj_dir"],
        )
        assert norm == env["proj_dir"] / "civic-maps"

        # Multi-repo project preserves secondary workspace_path instead of clobbering with workspace_paths[0]
        repo_a = env["proj_dir"] / "alpha-ops"
        repo_b = env["proj_dir"] / "beta-ops"
        repo_a.mkdir()
        repo_b.mkdir()
        multi_pid = "44444444-5555-4666-8777-888888888888"
        (env["agy_cfg_dir"] / "projects" / f"{multi_pid}.json").write_text(
            json.dumps(
                {
                    "id": multi_pid,
                    "name": "Ops Suite",
                    "projectResources": {
                        "resources": [
                            {"gitFolder": {"folderUri": f"file://{repo_a}/", "defaultBranch": "main"}},
                            {"gitFolder": {"folderUri": f"file://{repo_b}/", "defaultBranch": "main"}},
                        ]
                    },
                }
            ),
            encoding="utf-8",
        )
        lock = threading.Lock()
        app_storage = env["fake_home"] / "app_storage.json"
        app_storage.write_text(
            json.dumps({"projectsOrder": "[]", "antigravityUnifiedStateSync.projectManager": json.dumps({"lastActiveProjectId": ""})}),
            encoding="utf-8",
        )
        multi_res = resolve_or_create_project(
            {},
            project_id=multi_pid,
            workspace_path=str(repo_b),
            create_if_missing=False,
            projects_dir=env["agy_cfg_dir"] / "projects",
            workspace_root=env["ws_dir"],
            gitlab_root=env["proj_dir"],
            data_dir=env["fake_home"] / ".gemini" / "antigravity",
            app_storage_path=app_storage,
            storage_lock=lock,
        )
        assert multi_res["ok"] is True and multi_res["workspace_path"] == str(repo_b.resolve())

        # Symlink outside allowed roots and nested greenfield subrepos are blocked
        ext_target = Path(tmp_str) / "ext_outside"
        ext_target.mkdir()
        (env["proj_dir"] / "evil_sym").symlink_to(ext_target)
        for blocked_path in (str(env["proj_dir"] / "evil_sym"), str(env["nexus_repo"] / "nested" / "subrepo")):
            bad_proj = resolve_or_create_project(
                {},
                project_name="Bad",
                workspace_path=blocked_path,
                create_if_missing=True,
                projects_dir=env["agy_cfg_dir"] / "projects",
                workspace_root=env["ws_dir"],
                gitlab_root=env["proj_dir"],
                data_dir=env["fake_home"] / ".gemini" / "antigravity",
                app_storage_path=app_storage,
                storage_lock=lock,
            )
            assert bad_proj["ok"] is False

        miss = resolve_or_create_project(
            {},
            project_name="Civic Maps",
            workspace_path=str(env["fake_home"] / "projects" / "civic-maps"),
            create_if_missing=False,
            projects_dir=env["agy_cfg_dir"] / "projects",
            workspace_root=env["ws_dir"],
            gitlab_root=env["proj_dir"],
            data_dir=env["fake_home"] / ".gemini" / "antigravity",
            app_storage_path=app_storage,
            storage_lock=lock,
        )
        assert miss["ok"] is False and miss.get("project_not_found") is True

        created_reqs: list[dict[str, Any]] = []

        class _MockLSHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
                pass

            def do_POST(self) -> None:
                n = int(self.headers.get("Content-Length") or "0")
                body = json.loads(self.rfile.read(n).decode("utf-8"))
                created_reqs.append({"path": self.path, "body": body, "csrf": self.headers.get("x-codeium-csrf-token")})
                proj = body["project"]
                (env["agy_cfg_dir"] / "projects" / f"{proj['id']}.json").write_text(json.dumps(proj), encoding="utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b"{}")

        srv = ThreadingHTTPServer(("127.0.0.1", 0), _MockLSHandler)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            ls_env = {"ANTIGRAVITY_LS_ADDRESS": f"127.0.0.1:{srv.server_port}", "ANTIGRAVITY_CSRF_TOKEN": "mock_csrf_tok"}
            created = resolve_or_create_project(
                ls_env,
                project_name="Civic Maps",
                workspace_path=str(env["fake_home"] / "projects" / "civic-maps"),
                create_if_missing=True,
                default_branch="develop",
                projects_dir=env["agy_cfg_dir"] / "projects",
                workspace_root=env["ws_dir"],
                gitlab_root=env["proj_dir"],
                data_dir=env["fake_home"] / ".gemini" / "antigravity",
                app_storage_path=app_storage,
                storage_lock=lock,
            )
            assert created["ok"] is True and created["created"] is True
            assert created["workspace_path"] == str((env["proj_dir"] / "civic-maps").resolve())
            gf = created_reqs[0]["body"]["project"]["projectResources"]["resources"][0]["gitFolder"]
            assert gf["defaultBranch"] == "develop"
            head_branch = subprocess.check_output(
                ["git", "symbolic-ref", "--short", "HEAD"], cwd=created["workspace_path"], text=True
            ).strip()
            assert head_branch == "develop"
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    test_greenfield_fail_closed_and_explicit_create_new_project()
    test_agentapi_conversation_id_parser_and_host_project_manager()
    print("[✓] All handoff project isolation, greenfield guardrail & conversationId parser tests PASSED!")
