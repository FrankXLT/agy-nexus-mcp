"""tests/test_v408_ghcr_stdio_and_registry.py — AGY-Nexus v4.0.8 GHCR OCI, --stdio Transport & MCP Registry."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import select
import subprocess
import sys
import time

import pytest

import agy_nexus
from agy_nexus import config as cfg, server as srv_mod
from agy_nexus.hygiene import resolve_package_resource_dir, resolve_package_root, resolve_source_repo_root
from agy_nexus.polyglot_outline import outline_python
from agy_nexus.workflows import export_notebook_bundle


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_v408_dockerfile_dockerignore_and_oci_labels() -> None:
    """Verify Dockerfile & .dockerignore match public GHCR OCI and secret-exclusion contracts."""
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM python:3.12-slim" in dockerfile
    assert "--no-install-recommends" in dockerfile and "git" in dockerfile and "grep" in dockerfile
    assert "rm -rf /var/lib/apt/lists/*" in dockerfile
    assert "pip install --no-cache-dir ." in dockerfile
    assert "EXPOSE 8765" in dockerfile
    assert 'ENTRYPOINT ["agy-nexus-mcp"]' in dockerfile
    assert 'LABEL io.modelcontextprotocol.server.name="io.github.FrankXLT/agy-nexus-mcp"' in dockerfile
    assert 'LABEL org.opencontainers.image.source="https://github.com/FrankXLT/agy-nexus-mcp"' in dockerfile

    ignore_lines = {
        ln.strip()
        for ln in (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    }
    for required in (
        ".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache",
        "build", "dist", "*.egg-info", ".env", ".env.*", "!.env.example",
        "secrets.env*", "*.secrets*", "!scripts/init_secrets.py",
    ):
        assert required in ignore_lines, f"Missing {required} in .dockerignore"


def test_v408_server_json_manifest_and_github_oidc_workflow() -> None:
    """Verify server.json 2025-12-11 schema fields and publish-mcp.yml OIDC/cosign/dispatch pipeline."""
    manifest = json.loads((REPO_ROOT / "server.json").read_text(encoding="utf-8"))
    assert manifest["$schema"] == "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json"
    assert manifest["name"] == "io.github.FrankXLT/agy-nexus-mcp"
    assert manifest["title"] == "AGY-Nexus MCP"
    assert 1 <= len(manifest["description"]) <= 100
    assert manifest["version"] == agy_nexus.__version__ == "4.1.0"
    assert manifest["repository"] == {"url": "https://github.com/FrankXLT/agy-nexus-mcp", "source": "github"}

    pkg = manifest["packages"][0]
    assert pkg["registryType"] == "oci"
    assert pkg["identifier"] == "ghcr.io/frankxlt/agy-nexus-mcp:4.1.0"
    assert pkg["transport"] == {"type": "stdio"}
    assert pkg["packageArguments"] == [{
        "type": "positional",
        "value": "--stdio",
        "isRequired": True,
        "description": "Run AGY-Nexus MCP over standard input/output without HTTP or PATH_SECRET.",
    }]
    pass_var = next(v for v in pkg["environmentVariables"] if v["name"] == "PASS_HASH")
    assert pass_var["isRequired"] is False and pass_var["isSecret"] is True

    wf = (REPO_ROOT / ".github" / "workflows" / "publish-mcp.yml").read_text(encoding="utf-8")
    for token in (
        '- "v*"', "workflow_dispatch:", "release_tag:", "contents: read",
        "packages: write", "id-token: write", "MCP_PUBLISHER_VERSION: v1.8.1",
        "pytest", "python3 ag_bridge.py --self-test", "python3 -m agy_nexus.tools_praxis --self-test",
        "--stdio", "docker/build-push-action@v7", "sigstore/cosign-installer@v4.1.2",
        "cosign verify-blob", "./mcp-publisher validate", "./mcp-publisher login github-oidc", "./mcp-publisher publish",
    ):
        assert token in wf, f"Missing workflow token: {token}"


def test_v408_readme_pyproject_workflows_agent_parity_and_budgets() -> None:
    """Verify README mcp-name & v4.1.0 headings, pyproject URLs, WF-07, 13/13 agent sync, and <=500L/<=100L budgets."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "<!-- mcp-name: io.github.FrankXLT/agy-nexus-mcp -->" in readme
    assert "ghcr.io/frankxlt/agy-nexus-mcp:4.1.0" in readme and "--stdio" in readme
    assert not re.search(r"^#{1,6}.*\bv4\.0\.6\b", readme, re.M), "Stale v4.0.6 heading left in README.md"

    pyproj = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "4.1.0"' in pyproj and "[project.urls]" in pyproj
    assert 'Repository = "https://github.com/FrankXLT/agy-nexus-mcp"' in pyproj

    dep_doc = (REPO_ROOT / "docs" / "DEPLOYMENT.md").read_text(encoding="utf-8")
    assert "First-Push GHCR Visibility Recovery" in dep_doc and "workflow_dispatch" in dep_doc

    wf_doc = (REPO_ROOT / "docs" / "WORKFLOWS.md").read_text(encoding="utf-8")
    assert "## Workflow 7: WF-07" in wf_doc and "v4.0.8" in wf_doc
    for banned in ("diurnal", "plain-english", "posture", "surface"):
        assert banned not in wf_doc.lower(), f"Banned term '{banned}' in docs/WORKFLOWS.md"

    agent_files = [p for p in (REPO_ROOT / "agents").glob("*.md") if p.name.upper() != "README.MD"]
    assert len(agent_files) == 13
    sync_proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "sync_agents.py"), "--check"],
        cwd=str(REPO_ROOT), capture_output=True, text=True, check=False,
    )
    assert sync_proc.returncode == 0, sync_proc.stdout + sync_proc.stderr
    global_agents = Path.home() / ".gemini" / "config" / "agents"
    if global_agents.is_dir() and len([p for p in global_agents.glob("*.md") if p.name.upper() != "README.MD"]) >= 13:
        assert "13/13 synced" in sync_proc.stdout

    v408_strict_modules = {
        "server.py", "hygiene.py", "tools_workspace.py", "ascii_models.py",
        "code_health.py", "uploads.py", "workflows.py", "project_stats.py",
    }
    for py_path in sorted((REPO_ROOT / "src" / "agy_nexus").glob("*.py")):
        raw = py_path.read_text(encoding="utf-8")
        lines = raw.splitlines()
        assert len(lines) <= 500, f"{py_path.name} exceeded 500L ({len(lines)}L)"
        if py_path.name in v408_strict_modules:
            ol = outline_python(lines, raw, filename=py_path.name)
            syms = [s for s in ol["symbol_items"] if s.get("kind") in ("function", "async_function", "method")]
            assert not any(int(s.get("lines") or 0) > 100 for s in syms), f"{py_path.name} has >100L function: {syms}"


def test_v408_fail_closed_pass_hash_and_wheel_resource_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify PASS_HASH rejects invalid hashes, --stdio flags parse strictly, and wheels stay isolated."""
    monkeypatch.setattr(cfg, "PASS_HASH", "")
    assert cfg.verify_passphrase("open sesame") is False
    assert cfg.is_unlocked("open sesame") is False and cfg.is_unlocked("") is False
    assert srv_mod._has_valid_pass_hash("") is False
    assert srv_mod._is_stdio_flag_enabled(["--stdio"]) is True
    assert srv_mod._is_stdio_flag_enabled(["--stdio=false"]) is False

    for bad_hash in ("short", "z" * 64, "ab12" * 15 + "xyza"):
        monkeypatch.setattr(cfg, "PASS_HASH", bad_hash)
        assert srv_mod._has_valid_pass_hash(bad_hash) is False
        assert cfg.verify_passphrase("open sesame", expected_hash=bad_hash) is False
        assert cfg.is_unlocked("open sesame") is False

    valid_hash = cfg.normalize_phrase("open sesame")
    assert srv_mod._has_valid_pass_hash(valid_hash) is True
    assert cfg.verify_passphrase("open sesame", expected_hash=valid_hash) is True
    assert "PASS_HASH" in cfg.LOCKED_RESPONSE and "AG_BRIDGE_ENV_FILE" in cfg.LOCKED_RESPONSE

    empty_nb = export_notebook_bundle(tmp_path / "missing_brain", tmp_path / "missing.db", tmp_path / "out", {})
    assert empty_nb["total_exported"] == 0

    assert (resolve_package_resource_dir("agents") / "README.md").is_file()
    assert (resolve_package_resource_dir("web") / "index.html").is_file()

    site_pkg = tmp_path / "lib" / "python3.12" / "site-packages"
    wheel_pkg = site_pkg / "agy_nexus"
    wheel_pkg.mkdir(parents=True)
    (site_pkg / "agents").mkdir()
    (site_pkg / "web").mkdir()
    anchor = wheel_pkg / "server.py"
    anchor.write_text("", encoding="utf-8")
    assert resolve_package_resource_dir("agents", anchor_file=anchor) == site_pkg / "agents"
    assert resolve_package_resource_dir("web", anchor_file=anchor) == site_pkg / "web"
    assert resolve_package_root(wheel_pkg) == site_pkg
    monkeypatch.chdir(tmp_path)
    if not (Path("/app/src/agy_nexus").is_dir() and Path("/app/pyproject.toml").is_file()):
        assert resolve_source_repo_root(anchor) is None


def test_v408_stdio_subprocess_zero_stdout_noise_and_deadbolt(tmp_path: Path) -> None:
    """Verify ag_bridge.py --stdio runs clean JSON-RPC on stdout without secrets and keeps deadbolt closed."""
    clean_home = tmp_path / "clean_home"
    clean_home.mkdir()
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(clean_home),
        "AG_BRIDGE_ENV_FILE": str(tmp_path / "nonexistent.env"),
        "AG_BRIDGE_STATE_FILE": str(tmp_path / "stdio_state.json"),
        "PATH_SECRET": "",
        "PASS_HASH": "",
        "PYTHONUNBUFFERED": "1",
    }
    requests = [
        {
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "pytest", "version": "1.0"}},
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "list_models_and_agents", "arguments": {"style": "ascii", "include_skills": False, "include_rules": False}},
        },
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "list_saved_sessions", "arguments": {}}},
    ]
    proc = subprocess.Popen(
        [sys.executable, str(REPO_ROOT / "ag_bridge.py"), "--stdio"],
        cwd=str(REPO_ROOT), env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    parsed: dict[int, dict] = {}
    try:
        assert proc.stdin is not None and proc.stdout is not None and proc.stderr is not None
        for req in requests[:2]:
            proc.stdin.write(json.dumps(req) + "\n")
        proc.stdin.flush()
        for req in requests[2:]:
            proc.stdin.write(json.dumps(req) + "\n")
        proc.stdin.flush()

        deadline = time.monotonic() + 20.0
        while len(parsed) < 4 and time.monotonic() < deadline:
            ready, _, _ = select.select([proc.stdout], [], [], max(0.1, deadline - time.monotonic()))
            if not ready:
                break
            ln = proc.stdout.readline()
            if not ln:
                break
            stripped = ln.strip()
            if not stripped:
                continue
            msg = json.loads(stripped)
            assert msg.get("jsonrpc") == "2.0", f"Non-JSON-RPC line on stdout: {stripped!r}"
            if "id" in msg:
                parsed[msg["id"]] = msg

        proc.stdin.close()
        stderr_out = proc.stderr.read()
        rc = proc.wait(timeout=10)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)

    assert rc == 0, stderr_out
    assert "--stdio" in stderr_out
    assert set(parsed.keys()) >= {1, 2, 3, 4}
    assert parsed[1]["result"]["serverInfo"]["name"] == "agy-nexus-mcp"
    tools = parsed[2]["result"]["tools"]
    assert len(tools) == 11
    assert {"list_models_and_agents", "list_saved_sessions", "inspect_visual_artifacts", "send_handoff_and_resume"} <= {t["name"] for t in tools}

    models_text = "\n".join(part.get("text", "") for part in parsed[3]["result"]["content"])
    assert "SUBAGENT ROSTER (13)" in models_text and "Gemini 4 Carbon" in models_text

    locked_text = "\n".join(part.get("text", "") for part in parsed[4]["result"]["content"])
    assert '"locked": true' in locked_text and "Security Deadbolt Active" in locked_text
