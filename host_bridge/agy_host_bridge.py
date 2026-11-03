#!/usr/bin/env python3
"""
agy_host_bridge.py — Host Companion Daemon for ag-bridge-mcp

Listens on 0.0.0.0:8098 (configurable via BIND_HOST / BIND_PORT) using ThreadingHTTPServer
and provides two endpoints for the containerized ag-bridge-mcp server:
1. GET  /health   — Liveness probe
2. POST /agentapi — Executes Antigravity CLI actions (`discover`, `send-message`,
                    `new-conversation`, `get-conversation-metadata`) against the active
                    Antigravity Language Server on the host, plus `git-inspect` for
                    host-backed repositories and detached git worktrees.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BIND_HOST = os.getenv("HOST_BRIDGE_BIND_HOST", "0.0.0.0")
BIND_PORT = int(os.getenv("HOST_BRIDGE_BIND_PORT", "8098"))

AGY_DATA_DIR = Path(os.getenv("AGY_DATA_DIR", str(Path.home() / ".gemini/antigravity"))).expanduser()
AGY_CONFIG_DIR = Path(os.getenv("AGY_CONFIG_DIR", str(Path.home() / ".gemini/config"))).expanduser()
AGY_GITLAB_DIR = Path(os.getenv("AGY_GITLAB_DIR", str(Path.home() / "gitlab"))).expanduser()
AGENTAPI_BIN = os.getenv("AGENTAPI_BIN", str(AGY_DATA_DIR / "bin/agentapi"))
PROJECTS_DIR = AGY_CONFIG_DIR / "projects"
APP_STORAGE_PATH = Path(os.getenv("AGY_APP_STORAGE", str(Path.home() / ".config/Antigravity/app_storage.json"))).expanduser()


def discover_antigravity_env() -> dict[str, str]:
    """Discover the running Antigravity Language Server port and CSRF token on the host."""
    env = os.environ.copy()
    try:
        ps_out = subprocess.check_output(["ps", "-ef"], text=True, timeout=5)
    except Exception:
        return env

    csrf_token = None
    ls_pid = None
    for line in ps_out.splitlines():
        if "language_server_linux_x64" in line and "--csrf_token" in line:
            parts = line.split()
            if len(parts) > 1:
                ls_pid = parts[1]
            m = re.search(r"--csrf_token\s+([^\s]+)", line)
            if m:
                csrf_token = m.group(1)
            break

    if not ls_pid or not csrf_token:
        return env

    ls_port = None
    try:
        ss_out = subprocess.check_output(["ss", "-tlnp"], text=True, timeout=5)
        best_port = None
        for line in ss_out.splitlines():
            if f"pid={ls_pid}," in line:
                m_127 = re.search(r"127\.0\.0\.1:(\d+)", line)
                if m_127:
                    p = int(m_127.group(1))
                    if best_port is None or p < best_port:
                        best_port = p
        ls_port = best_port
    except Exception:
        pass

    if ls_port and csrf_token:
        env["ANTIGRAVITY_LS_ADDRESS"] = f"localhost:{ls_port}"
        env["ANTIGRAVITY_CSRF_TOKEN"] = csrf_token
        env["ANTIGRAVITY_APP_DATA_DIR"] = str(AGY_DATA_DIR)
    return env


def resolve_project_workspace(project_name: str = "", workspace_path: str = "", project_id: str = "") -> tuple[str | None, str | None, str]:
    """Resolve a project name, workspace path, or project UUID to (project_id, workspace_dir, display_name)."""
    target_dir = None
    resolved_id = project_id.strip() if project_id else None
    display_name = project_name.strip() or "New Project"

    projects: list[dict] = []
    if PROJECTS_DIR.is_dir():
        for pfile in sorted(PROJECTS_DIR.glob("*.json")):
            try:
                data = json.loads(pfile.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("id"):
                    projects.append(data)
            except Exception:
                continue

    if resolved_id:
        for p in projects:
            if p.get("id") == resolved_id:
                paths = p.get("paths") or []
                if paths:
                    target_dir = paths[0]
                display_name = p.get("name") or display_name
                break

    if not target_dir and project_name:
        q = project_name.strip().lower()
        for p in projects:
            pname = str(p.get("name") or "").lower()
            paths = p.get("paths") or []
            if q == pname or q in pname or any(q == Path(pt).name.lower() for pt in paths):
                resolved_id = p.get("id")
                if paths:
                    target_dir = paths[0]
                display_name = p.get("name") or display_name
                break

    if not target_dir and workspace_path:
        cand = Path(workspace_path).expanduser()
        if not cand.is_absolute():
            cand = AGY_GITLAB_DIR / workspace_path
        if cand.is_dir():
            target_dir = str(cand.resolve())
            display_name = cand.name
            for p in projects:
                if target_dir in (p.get("paths") or []):
                    resolved_id = p.get("id")
                    display_name = p.get("name") or display_name
                    break

    if not target_dir and project_name:
        slug = re.sub(r"[^a-zA-Z0-9._-]", "-", project_name.strip().lower()).strip("-")
        for entry in sorted(AGY_GITLAB_DIR.iterdir()) if AGY_GITLAB_DIR.is_dir() else []:
            if entry.is_dir() and (entry.name.lower() == slug or slug in entry.name.lower()):
                target_dir = str(entry.resolve())
                display_name = entry.name
                for p in projects:
                    if target_dir in (p.get("paths") or []):
                        resolved_id = p.get("id")
                        display_name = p.get("name") or display_name
                        break
                break

    return resolved_id, target_dir, display_name


def set_active_project_in_storage(project_id: str | None) -> bool:
    """Update lastActiveProjectId in ~/.config/Antigravity/app_storage.json when spawning a new session."""
    if not project_id or not APP_STORAGE_PATH.is_file():
        return False
    try:
        raw = json.loads(APP_STORAGE_PATH.read_text(encoding="utf-8"))
        state_str = raw.get("antigravityUnifiedStateSync.projectManager")
        if not isinstance(state_str, str):
            return False
        pm_state = json.loads(state_str)
        if pm_state.get("lastActiveProjectId") == project_id:
            return True
        pm_state["lastActiveProjectId"] = project_id
        raw["antigravityUnifiedStateSync.projectManager"] = json.dumps(pm_state, separators=(",", ":"))
        tmp_path = APP_STORAGE_PATH.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        tmp_path.replace(APP_STORAGE_PATH)
        return True
    except Exception:
        return False


def handle_agentapi_request(payload: dict) -> dict:
    """Handle /agentapi requests from ag-bridge-mcp."""
    action = str(payload.get("action") or "discover").strip().lower()

    if action == "git-inspect":
        ws_raw = str(payload.get("workspace_path") or "").strip()
        target_branch = re.sub(r"[^a-zA-Z0-9_./~^-]", "", str(payload.get("target_branch") or "HEAD")) or "HEAD"
        include_untracked = bool(payload.get("include_untracked", True))
        if not ws_raw:
            return {"ok": False, "error": "workspace_path is required"}
        ws_path = Path(ws_raw).expanduser().resolve()
        allowed_roots = [
            AGY_GITLAB_DIR.resolve(),
            (AGY_DATA_DIR / "worktrees").resolve(),
            Path.home().resolve(),
        ]
        if not any(ws_path == r or ws_path.is_relative_to(r) for r in allowed_roots):
            return {"ok": False, "error": f"Path '{ws_path}' is outside allowed roots."}
        if not ws_path.is_dir():
            return {"ok": False, "error": f"Directory '{ws_path}' does not exist."}

        def _git(args: list[str], timeout: int = 8) -> subprocess.CompletedProcess:
            return subprocess.run(
                ["git", "-c", "safe.directory=*"] + args,
                cwd=str(ws_path),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )

        b_proc = _git(["rev-parse", "--abbrev-ref", "HEAD"])
        if b_proc.returncode != 0:
            return {"ok": False, "error": b_proc.stderr.strip() or "Not a git repository"}
        branch = b_proc.stdout.strip()
        status_short = _git(["status", "--short"]).stdout.strip()
        diff_stat = _git(["diff", "--stat", target_branch, "--"]).stdout.strip()
        req_fp = str(payload.get("file_path") or "").strip()
        safe_fp = ""
        if req_fp:
            norm_fp = os.path.normpath(req_fp).lstrip("/")
            if not norm_fp.startswith(".."):
                safe_fp = norm_fp
        diff_args = ["diff", target_branch, "--"] + ([safe_fp] if safe_fp else [])
        diff_proc = _git(diff_args, timeout=12)
        if diff_proc.returncode != 0 and target_branch != "HEAD":
            diff_proc = _git(["diff", "HEAD", "--"] + ([safe_fp] if safe_fp else []), timeout=12)
        untracked: list[str] = []
        if include_untracked:
            u_proc = _git(["ls-files", "--others", "--exclude-standard"])
            if u_proc.returncode == 0 and u_proc.stdout.strip():
                untracked = u_proc.stdout.strip().splitlines()[:100]
        return {
            "ok": True,
            "workspace": str(ws_path),
            "branch": branch,
            "current_branch": branch,
            "status_short": status_short,
            "diff_stat": diff_stat,
            "diff": diff_proc.stdout[:60000],
            "diff_truncated": len(diff_proc.stdout) > 60000,
            "untracked_files": untracked,
        }

    env = discover_antigravity_env()
    if "ANTIGRAVITY_LS_ADDRESS" not in env:
        return {"ok": False, "error": "Could not discover running Antigravity Language Server"}

    if action == "discover":
        return {
            "ok": True,
            "ls_address": env.get("ANTIGRAVITY_LS_ADDRESS", ""),
            "app_data_dir": env.get("ANTIGRAVITY_APP_DATA_DIR", ""),
        }

    if action == "send-message":
        conv_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(payload.get("conversation_id") or ""))
        prompt = str(payload.get("prompt") or "").strip()
        title = str(payload.get("title") or "").strip()
        if not conv_id or not prompt:
            return {"ok": False, "error": "conversation_id and prompt are required"}
        cmd = [AGENTAPI_BIN, "send-message"]
        if title:
            cmd.append(f"--title={title}")
        cmd.extend([conv_id, prompt])
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=25)
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "conversation_id": conv_id,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }

    if action == "new-conversation":
        prompt = str(payload.get("prompt") or "").strip()
        if not prompt:
            return {"ok": False, "error": "prompt is required"}
        model = str(payload.get("model") or "pro").strip()
        if model not in ("flash_lite", "flash", "pro"):
            model = "pro"
        title = str(payload.get("title") or "").strip()
        req_project_name = str(payload.get("project_name") or "").strip()
        req_workspace_path = str(payload.get("workspace_path") or "").strip()
        req_project_id = str(payload.get("project_id") or "").strip()

        resolved_proj_id, resolved_dir, resolved_name = resolve_project_workspace(
            project_name=req_project_name,
            workspace_path=req_workspace_path,
            project_id=req_project_id,
        )
        if resolved_proj_id:
            set_active_project_in_storage(resolved_proj_id)

        run_cwd = resolved_dir if (resolved_dir and Path(resolved_dir).is_dir()) else str(AGY_GITLAB_DIR)
        cmd = [AGENTAPI_BIN, "new-conversation", f"--model={model}"]
        if title:
            cmd.append(f"--title={title}")
        cmd.append(prompt)
        proc = subprocess.run(cmd, env=env, cwd=run_cwd, capture_output=True, text=True, timeout=25)
        combined_out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        m_uuid = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", combined_out)
        new_conv_id = m_uuid.group(1) if m_uuid else ""
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "conversation_id": new_conv_id,
            "project_id": resolved_proj_id,
            "workspace_path": run_cwd,
            "project_name": resolved_name,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }

    if action == "get-conversation-metadata":
        conv_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(payload.get("conversation_id") or ""))
        if not conv_id:
            return {"ok": False, "error": "conversation_id is required"}
        cmd = [AGENTAPI_BIN, "get-conversation-metadata", conv_id]
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=15)
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "conversation_id": conv_id,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }

    return {"ok": False, "error": f"Unknown action: {action}"}


class HostBridgeHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, data: dict):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/health"):
            self._send_json(200, {"status": "ok", "service": "agy-host-bridge"})
            return
        self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            payload = json.loads(raw) if raw.strip() else {}
        except Exception:
            payload = {}

        if self.path.startswith("/agentapi"):
            try:
                res = handle_agentapi_request(payload)
                self._send_json(200, res)
            except Exception as e:
                self._send_json(500, {"ok": False, "error": str(e)})
            return

        self._send_json(404, {"error": "Not found"})


if __name__ == "__main__":
    print(f"Starting agy-host-bridge on {BIND_HOST}:{BIND_PORT} (threaded)...", flush=True)
    server = ThreadingHTTPServer((BIND_HOST, BIND_PORT), HostBridgeHandler)
    server.serve_forever()
