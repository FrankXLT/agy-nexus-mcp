#!/usr/bin/env python3
"""
Parameterized End-to-End Permutation Test Suite for ag-bridge-mcp (v2.0).

Exercises HTTP/2 transport probes, header normalization, deadbolt lock/unlock
and voice variations, session listing filters, session loading identifiers,
line-range & centered file slicing, per-file & paginated git diffs,
modular architecture hygiene contracts, and concurrent burst requests.

Usage:
  python3 tests/run_permutation_suite.py \
    --env-file ~/.config/ag-bridge-mcp/secrets.env \
    --domain <your-domain> \
    --passphrase "<your spoken passphrase>"
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

RESULTS: list[dict[str, Any]] = []


def parse_env_file(env_path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("'\"")
    return env


def record(category: str, name: str, passed: bool, detail: str = "") -> None:
    status = "PASS" if passed else "FAIL"
    RESULTS.append({"category": category, "name": name, "passed": passed, "detail": detail})
    print(f"[{status}] [{category}] {name}" + (f" -> {detail}" if detail else ""), flush=True)


def parse_mcp_response(raw_text: str) -> dict[str, Any]:
    for line in raw_text.splitlines():
        s = line.strip()
        if s.startswith("data:"):
            payload = s[5:].strip()
            if payload:
                try:
                    return json.loads(payload)
                except Exception:
                    pass
    try:
        return json.loads(raw_text.strip())
    except Exception:
        return {"_raw": raw_text[:500]}


def make_caller(mcp_url: str):
    def call_mcp(method: str, params: dict[str, Any] | None = None, req_id: int = 1, extra_headers: list[str] | None = None) -> tuple[int, dict[str, Any]]:
        body: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if req_id is not None:
            body["id"] = req_id
        if params is not None:
            body["params"] = params
        payload_str = json.dumps(body)

        cmd = [
            "curl", "-sS", "--http2", "-w", "\n__HTTP_CODE__:%{http_code}",
            "-X", "POST", mcp_url,
            "-H", "Content-Type: application/json",
            "-H", "Accept: application/json, text/event-stream",
        ]
        if extra_headers:
            for h in extra_headers:
                cmd.extend(["-H", h])
        cmd.extend(["--data-binary", payload_str])
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        out = proc.stdout
        http_code = 0
        if "__HTTP_CODE__:" in out:
            body_part, code_part = out.rsplit("__HTTP_CODE__:", 1)
            try:
                http_code = int(code_part.strip())
            except Exception:
                http_code = 0
        else:
            body_part = out
        return http_code, parse_mcp_response(body_part)

    def call_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> tuple[int, dict[str, Any], dict[str, Any]]:
        code, rpc = call_mcp("tools/call", {"name": tool_name, "arguments": arguments or {}})
        res = rpc.get("result", {})
        is_error = res.get("isError", False)
        content_list = res.get("content", [])
        text_val = content_list[0].get("text", "") if content_list else ""
        try:
            parsed = json.loads(text_val) if text_val else {}
        except Exception:
            parsed = {"_raw_text": text_val}
        if is_error:
            parsed["_mcp_is_error"] = True
        return code, rpc, parsed

    return call_mcp, call_tool


def main() -> int:
    parser = argparse.ArgumentParser(description="Run end-to-end permutation tests against ag-bridge-mcp")
    parser.add_argument("--env-file", default=str(Path.home() / ".config/ag-bridge-mcp/secrets.env"), help="Path to secrets.env")
    parser.add_argument("--domain", default=os.getenv("AG_BRIDGE_DOMAIN", "example.com"), help="Base domain")
    parser.add_argument("--url", default=os.getenv("AG_BRIDGE_URL", ""), help="Explicit full MCP URL (overrides --env-file + --domain)")
    parser.add_argument("--passphrase", default=os.getenv("AG_BRIDGE_PASSPHRASE", ""), help="Spoken passphrase for unlock verification")
    args = parser.parse_args()

    env_map = parse_env_file(Path(args.env_file).expanduser())
    mcp_url = args.url.strip()
    if not mcp_url:
        sub_hash = env_map.get("SUBDOMAIN_HASH", "")
        path_secret = env_map.get("PATH_SECRET", "")
        if not sub_hash or not path_secret:
            print("ERROR: Either --url or a valid --env-file with SUBDOMAIN_HASH and PATH_SECRET is required.", file=sys.stderr)
            return 2
        mcp_url = f"https://ag-{sub_hash}.{args.domain}/{path_secret}/mcp"

    passphrase = args.passphrase.strip()
    if not passphrase:
        print("ERROR: Provide --passphrase or set AG_BRIDGE_PASSPHRASE environment variable.", file=sys.stderr)
        return 2

    call_mcp, call_tool = make_caller(mcp_url)

    # 1. Transport & Protocol Layer
    for method in ["HEAD", "GET", "OPTIONS", "DELETE"]:
        cmd = ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}", "--http2", "-X", method, mcp_url]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        code = int(p.stdout.strip() or "0")
        record("1. Transport", f"HTTP {method} probe", code in (200, 202, 204), f"HTTP {code}")

    code, rpc = call_mcp("initialize", {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "permutation-tester-v2", "version": "2.0.0"},
    })
    record("1. Transport", "MCP initialize handshake", code == 200 and "result" in rpc, f"HTTP {code}")

    code, rpc = call_mcp("tools/list", {})
    tools = rpc.get("result", {}).get("tools", [])
    record("1. Transport", "tools/list exposes 9 tools", code == 200 and len(tools) == 9, f"count={len(tools)}")

    # 2. Deadbolt & Passphrase Permutations
    _, _, r_lock = call_tool("lock_bridge", {})
    record("2. Deadbolt", "lock_bridge() engages deadbolt", r_lock.get("locked") is True, f"locked={r_lock.get('locked')}")

    locked_cases = [
        ("list_saved_sessions", {}),
        ("load_session_into_gemini", {"session_identifier": "1"}),
        ("ask_workspace_readonly", {"question": "locked check"}),
        ("send_handoff_and_resume", {"research_markdown": "locked check", "resume_headless": False}),
        ("manage_background_run", {}),
        ("inspect_git_diff", {}),
        ("list_models_and_agents", {}),
    ]
    for tname, targs in locked_cases:
        _, _, r_t = call_tool(tname, targs)
        record("2. Deadbolt", f"Locked guard on {tname}", r_t.get("locked") is True, f"locked={r_t.get('locked')}")

    _, _, r_bad = call_tool("unlock_sessions", {"spoken_passphrase": "wrong passphrase test 999"})
    record("2. Deadbolt", "Reject wrong passphrase", r_bad.get("locked") is True, f"locked={r_bad.get('locked')}")

    _, _, r_ok = call_tool("unlock_sessions", {"spoken_passphrase": passphrase})
    record("2. Deadbolt", "Unlock with exact passphrase", r_ok.get("locked") is False, f"ttl={r_ok.get('ttl_seconds')}")

    call_tool("lock_bridge", {})
    _, _, r_wrap = call_tool("unlock_sessions", {"spoken_passphrase": f"The passphrase is {passphrase} please"})
    record("2. Deadbolt", "Unlock with spoken wrapper phrase", r_wrap.get("locked") is False, f"locked={r_wrap.get('locked')}")

    # 3. Session Listing, Loading & Modular Hygiene Standards
    _, _, r_all = call_tool("list_saved_sessions", {"limit": 15, "status_filter": "ALL"})
    record("3. Sessions", "list_saved_sessions(ALL)", r_all.get("count", 0) >= 1, f"count={r_all.get('count')}")

    _, _, r_l1 = call_tool("load_session_into_gemini", {"session_identifier": "1"})
    record(
        "4. LoadSession",
        "Load session #1 + project_hygiene_standards",
        r_l1.get("ok") is True and "project_hygiene_standards" in r_l1,
        f"hygiene={r_l1.get('project_hygiene_standards', {}).get('target_lines_per_file')}",
    )

    # 5. Workspace Line-Range Slicing, Centered Line Reads & Modularity Advisories
    _, _, r_range = call_tool("ask_workspace_readonly", {
        "question": "Read lines 50 to 90 of ag_bridge.py",
        "file_subpath": "ag-bridge-mcp/ag_bridge.py",
        "start_line": 50,
        "end_line": 90,
    })
    fd_range = r_range.get("file_details", {})
    record(
        "5. WorkspaceV2",
        "Explicit start_line=50, end_line=90 slice",
        fd_range.get("shown_start_line") == 50 and fd_range.get("shown_end_line") == 90,
        f"shown={fd_range.get('shown_lines')}",
    )

    _, _, r_inline = call_tool("ask_workspace_readonly", {
        "question": "Read inline range 100-140 of ag_bridge.py",
        "file_subpath": "ag-bridge-mcp/ag_bridge.py:100-140",
    })
    fd_inline = r_inline.get("file_details", {})
    record(
        "5. WorkspaceV2",
        "Inline 'file.py:100-140' range syntax",
        fd_inline.get("shown_start_line") == 100 and fd_inline.get("shown_end_line") == 140,
        f"shown={fd_inline.get('shown_lines')}",
    )

    _, _, r_center = call_tool("ask_workspace_readonly", {
        "question": "Center around line 1200 of ag_bridge.py",
        "file_subpath": "ag-bridge-mcp/ag_bridge.py:1200",
    })
    fd_center = r_center.get("file_details", {})
    st_c = fd_center.get("shown_start_line", 0)
    en_c = fd_center.get("shown_end_line", 0)
    record(
        "5. WorkspaceV2",
        "Auto-center window around grep match ':1200' + modularity_advisory",
        st_c <= 1200 <= en_c and st_c > 1000 and "modularity_advisory" in fd_center,
        f"shown={fd_center.get('shown_lines')}",
    )

    # 6. Git Diff File-Scoped & Offset Pagination
    _, _, r_d = call_tool("inspect_git_diff", {
        "target_branch": "HEAD",
        "workspace_override": "ag-bridge-mcp",
        "file_path": "ag_bridge.py",
        "offset_chars": 0,
    })
    record(
        "6. GitDiffV2",
        "inspect_git_diff with file_path + pagination metadata",
        r_d.get("ok") is True and "total_diff_chars" in r_d and r_d.get("file_path_filter") == "ag_bridge.py",
        f"range={r_d.get('shown_diff_range')}",
    )

    # 7. Modular Hygiene + Skill/Agent Interjection & Scope Isolation in send_handoff_and_resume
    _, _, r_h = call_tool("send_handoff_and_resume", {
        "research_markdown": "## Test V2.1 Handoff\nVerify modular hygiene and skill/agent interjection.",
        "resume_headless": False,
        "enforce_modular_hygiene": True,
        "activate_skills": "agy-nexus-stats,visual-architecture-system",
        "target_agent_role": "argon-surgeon",
        "customization_edit_scope": "project",
    })
    hf_path = Path(r_h.get("handoff_file", ""))
    hf_text = hf_path.read_text(encoding="utf-8") if hf_path.is_file() else ""
    record(
        "7. HandoffV2.1",
        "send_handoff_and_resume attaches Modular Hygiene + Activated Skills & Agent Role directive",
        r_h.get("modular_hygiene_enforced") is True
        and "Mandatory Modular Architecture & File Hygiene Standard" in hf_text
        and "agy-nexus-stats" in hf_text
        and "argon-surgeon" in hf_text,
        f"skills={len(r_h.get('customization_scope_info', {}).get('activated_skills', []))}",
    )

    _, _, r_scope = call_tool("send_handoff_and_resume", {
        "research_markdown": "## Test Global Scope Isolation\nAttempt global ~/.gemini/config/skills edit inside project.",
        "resume_headless": False,
        "workspace_path": "feature-app",
        "customization_edit_scope": "global",
    })
    scope_warn = str(r_scope.get("customization_scope_info", {}).get("scope_isolation_warning", ""))
    if hf_path.is_file():
        hf_path.unlink(missing_ok=True)
    record(
        "7. HandoffV2.1",
        "Scope-Isolation warns when global skill/rule edit is staged inside a feature project",
        "SCOPE-ISOLATION WARNING" in scope_warn and "create_new_session=True" in scope_warn,
        f"warn_present={bool(scope_warn)}",
    )

    # 8. 4-Layer Skills, Rules & Agent Roles Inventory + Shorthand Inspection
    _, _, r_m = call_tool("list_models_and_agents", {
        "include_skills": True,
        "include_rules": True,
        "inspect_name": "agy-nexus-stats",
    })
    record(
        "8. InventoryV2.1",
        "list_models_and_agents returns 4-layer skills, parsed agent frontmatter, rules & scope policy",
        r_m.get("skills_count", 0) >= 10
        and r_m.get("agents_count", 0) >= 8
        and "customization_scope_policy" in r_m
        and "global_gemini_sections" in r_m.get("rules_inventory", {}),
        f"agents={r_m.get('agents_count')}, skills={r_m.get('skills_count')}",
    )
    insp = r_m.get("inspected_item", {})
    record(
        "8. InventoryV2.1",
        "list_models_and_agents(inspect_name='agy-nexus-stats') reads full SKILL.md",
        "SKILL.md" in str(insp.get("path", "")) and len(str(insp.get("content", ""))) > 200,
        f"path={Path(str(insp.get('path', 'none'))).name}",
    )

    _, _, r_shorthand = call_tool("ask_workspace_readonly", {
        "question": "Read skill and agent via shorthand",
        "file_subpath": "skill:visual-architecture-system,agent:argon-sentinel",
    })
    sh_files = r_shorthand.get("file_details", {}).get("files", [])
    record(
        "8. InventoryV2.1",
        "ask_workspace_readonly resolves 'skill:<name>' and 'agent:<name>' shorthands",
        len(sh_files) == 2 and all("content" in f for f in sh_files),
        f"resolved_count={len(sh_files)}",
    )

    # 9. Cross-Platform setup.sh CLI Verification
    repo_root = Path(__file__).resolve().parent.parent
    setup_sh = repo_root / "scripts/setup.sh"
    if setup_sh.is_file():
        with tempfile.TemporaryDirectory() as tmpd:
            tmp_env = Path(tmpd) / "test_secrets.env"
            sp = subprocess.run(
                [str(setup_sh), "--domain", "example.com", "--passphrase", "Example Bridge 2026!", "--ttl", "3600", "--env-file", str(tmp_env), "--quiet"],
                capture_output=True, text=True, timeout=10,
            )
            gen_map = parse_env_file(tmp_env)
            record(
                "9. SetupCLI",
                "scripts/setup.sh generates valid SHA-256 PASS_HASH & configurable TTL",
                sp.returncode == 0 and gen_map.get("TTL_SECONDS") == "3600" and len(gen_map.get("PASS_HASH", "")) == 64,
                f"ttl={gen_map.get('TTL_SECONDS')}, hash_len={len(gen_map.get('PASS_HASH', ''))}",
            )

    def _burst(i: int) -> bool:
        c, _, d = call_tool("list_saved_sessions", {"limit": 3})
        return c == 200 and d.get("ok") is True

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        burst_ok = all(ex.map(_burst, range(5)))
    record("10. Concurrency", "5 parallel HTTP requests", burst_ok, f"all_ok={burst_ok}")

    passed = sum(1 for r in RESULTS if r["passed"])
    failed = sum(1 for r in RESULTS if not r["passed"])
    print(f"\nTOTAL: {len(RESULTS)} | PASSED: {passed} | FAILED: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
