#!/usr/bin/env python3
"""
agy_host_bridge.py — Authenticated Host Companion Daemon for ag-bridge-mcp
Listens on 127.0.0.1:8098 by default (configurable via HOST_BRIDGE_BIND_HOST / HOST_BRIDGE_BIND_PORT)
using ThreadingHTTPServer and provides two endpoints for ag-bridge-mcp:
1. GET  /health   — Minimal liveness probe (no sensitive paths or tokens)
2. POST /agentapi — Requires constant-time `X-Bridge-Token` authentication and peer CIDR verification
                    before executing Antigravity CLI actions (`discover`, `send-message`,
                    `new-conversation`, `get-conversation-metadata`) or sandboxed `git-inspect`.
"""
from __future__ import annotations
import json
import os
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    from host_bridge.bridge_security import (
        DEFAULT_BIND_HOST,
        derive_bridge_token,
        guard_cli_positional,
        load_bridge_env_file,
        resolve_allowed_git_roots,
        sanitize_conv_id,
        sanitize_git_ref,
        validate_agentapi_request,
    )
except ImportError:
    from bridge_security import (  # type: ignore[no-redef]
        DEFAULT_BIND_HOST,
        derive_bridge_token,
        guard_cli_positional,
        load_bridge_env_file,
        resolve_allowed_git_roots,
        sanitize_conv_id,
        sanitize_git_ref,
        validate_agentapi_request,
    )

load_bridge_env_file()

BIND_HOST = os.getenv("HOST_BRIDGE_BIND_HOST", DEFAULT_BIND_HOST)
BIND_PORT = int(os.getenv("HOST_BRIDGE_BIND_PORT", "8098"))
AGY_DATA_DIR = Path(os.getenv("AGY_DATA_DIR", str(Path.home() / ".gemini/antigravity"))).expanduser()
AGY_CONFIG_DIR = Path(os.getenv("AGY_CONFIG_DIR", str(Path.home() / ".gemini/config"))).expanduser()
AGY_WORKSPACE_DIR = Path(os.getenv("AGY_WORKSPACE_DIR", str(Path.home() / "agentic_workspace"))).expanduser()
AGY_GITLAB_DIR = Path(os.getenv("AGY_GITLAB_DIR", str(Path.home() / "gitlab"))).expanduser()
AGENTAPI_BIN = os.getenv("AGENTAPI_BIN", str(AGY_DATA_DIR / "bin/agentapi"))
PROJECTS_DIR = AGY_CONFIG_DIR / "projects"
APP_STORAGE_PATH = Path(os.getenv("AGY_APP_STORAGE", str(Path.home() / ".config/Antigravity/app_storage.json"))).expanduser()
BRIDGE_TOKEN_OVERRIDE: str = ""
_STORAGE_LOCK = threading.Lock()


def get_expected_bridge_token() -> str:
    """Resolve active expected X-Bridge-Token for /agentapi requests."""
    if BRIDGE_TOKEN_OVERRIDE:
        return BRIDGE_TOKEN_OVERRIDE
    return derive_bridge_token()
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
            found_rel = None
            for base in (
                AGY_WORKSPACE_DIR / "projects",
                AGY_WORKSPACE_DIR / "workbooks",
                AGY_WORKSPACE_DIR / "configuration",
                AGY_GITLAB_DIR,
            ):
                if (base / workspace_path).is_dir():
                    found_rel = base / workspace_path
                    break
            cand = found_rel if found_rel else (AGY_WORKSPACE_DIR / "projects" / workspace_path if (AGY_WORKSPACE_DIR / "projects").is_dir() else AGY_GITLAB_DIR / workspace_path)
        resolved_cand = cand.resolve()
        allowed_roots = resolve_allowed_git_roots(AGY_GITLAB_DIR, AGY_DATA_DIR, AGY_WORKSPACE_DIR)
        pkg_root = Path(__file__).resolve().parents[1]
        if cand.is_dir() and (resolved_cand == pkg_root.resolve() or any(resolved_cand != r and resolved_cand.is_relative_to(r) for r in allowed_roots)):
            target_dir = str(resolved_cand)
            display_name = resolved_cand.name
            for p in projects:
                if target_dir in (p.get("paths") or []):
                    resolved_id = p.get("id")
                    display_name = p.get("name") or display_name
                    break
    if not target_dir and project_name:
        slug = re.sub(r"[^a-zA-Z0-9._-]", "-", project_name.strip().lower()).strip("-")
        search_roots = [
            AGY_WORKSPACE_DIR / "projects",
            AGY_WORKSPACE_DIR / "workbooks",
            AGY_WORKSPACE_DIR / "configuration",
            AGY_GITLAB_DIR,
        ]
        for sroot in search_roots:
            if sroot.is_dir():
                for entry in sorted(sroot.iterdir()):
                    if entry.is_dir() and (entry.name.lower() == slug or slug in entry.name.lower()):
                        target_dir = str(entry.resolve())
                        display_name = entry.name
                        for p in projects:
                            if target_dir in (p.get("paths") or []):
                                resolved_id = p.get("id")
                                display_name = p.get("name") or display_name
                                break
                        break
            if target_dir:
                break
    if target_dir:
        res_td = Path(target_dir).expanduser().resolve()
        allowed_roots = resolve_allowed_git_roots(AGY_GITLAB_DIR, AGY_DATA_DIR, AGY_WORKSPACE_DIR)
        pkg_root = Path(__file__).resolve().parents[1]
        if not (res_td == pkg_root.resolve() or any(res_td != r and res_td.is_relative_to(r) for r in allowed_roots)):
            default_ws = (AGY_WORKSPACE_DIR / "projects") if (AGY_WORKSPACE_DIR / "projects").is_dir() else AGY_GITLAB_DIR
            target_dir = str(default_ws)
    return resolved_id, target_dir, display_name
def set_active_project_in_storage(project_id: str | None) -> bool:
    """Update lastActiveProjectId in ~/.config/Antigravity/app_storage.json when spawning a new session."""
    if not project_id or not APP_STORAGE_PATH.is_file():
        return False
    try:
        with _STORAGE_LOCK:
            raw = json.loads(APP_STORAGE_PATH.read_text(encoding="utf-8"))
            state_str = raw.get("antigravityUnifiedStateSync.projectManager")
            if not isinstance(state_str, str):
                return False
            pm_state = json.loads(state_str)
            if pm_state.get("lastActiveProjectId") == project_id:
                return True
            pm_state["lastActiveProjectId"] = project_id
            raw["antigravityUnifiedStateSync.projectManager"] = json.dumps(pm_state, separators=(",", ":"))
            tmp_path = APP_STORAGE_PATH.with_suffix(f".json.tmp.{os.getpid()}_{threading.get_ident()}")
            tmp_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
            tmp_path.replace(APP_STORAGE_PATH)
        return True
    except Exception:
        return False
MOCK_ACTION_HANDLER = None


def handle_agentapi_request(payload: dict) -> dict:
    """Handle authenticated /agentapi requests from ag-bridge-mcp."""
    if callable(MOCK_ACTION_HANDLER):
        return MOCK_ACTION_HANDLER(payload)
    action = str(payload.get("action") or "discover").strip().lower()
    if action == "ping":
        return {"ok": True, "service": "agy-host-bridge"}
    if action == "new-conversation":
        raw_ws_chk = str(payload.get("workspace_path") or "").strip()
        if raw_ws_chk:
            cand_ws = Path(raw_ws_chk).expanduser()
            if not cand_ws.is_absolute():
                found_cand = None
                for base in (
                    AGY_WORKSPACE_DIR / "projects",
                    AGY_WORKSPACE_DIR / "workbooks",
                    AGY_WORKSPACE_DIR / "configuration",
                    AGY_GITLAB_DIR,
                ):
                    if (base / raw_ws_chk).is_dir():
                        found_cand = base / raw_ws_chk
                        break
                cand_ws = found_cand if found_cand else (AGY_WORKSPACE_DIR / "projects" / raw_ws_chk if (AGY_WORKSPACE_DIR / "projects").is_dir() else AGY_GITLAB_DIR / raw_ws_chk)
            res_ws = cand_ws.resolve()
            allowed_ws_roots = resolve_allowed_git_roots(AGY_GITLAB_DIR, AGY_DATA_DIR, AGY_WORKSPACE_DIR)
            pkg_root = Path(__file__).resolve().parents[1]
            if not (res_ws == pkg_root.resolve() or any(res_ws != r and res_ws.is_relative_to(r) for r in allowed_ws_roots)):
                return {"ok": False, "error": f"Path '{res_ws}' is outside allowed roots."}
    if action == "git-inspect":
        ws_raw = str(payload.get("workspace_path") or "").strip()
        target_branch = sanitize_git_ref(str(payload.get("target_branch") or "HEAD"))
        include_untracked = bool(payload.get("include_untracked", True))
        summary_only = bool(payload.get("summary_only", False))
        if not ws_raw:
            return {"ok": False, "error": "workspace_path is required"}
        ws_path = Path(ws_raw).expanduser().resolve()
        allowed_roots = resolve_allowed_git_roots(AGY_GITLAB_DIR, AGY_DATA_DIR, AGY_WORKSPACE_DIR)
        pkg_root = Path(__file__).resolve().parents[1]
        if not (ws_path == pkg_root.resolve() or any(ws_path != r and ws_path.is_relative_to(r) for r in allowed_roots)):
            return {"ok": False, "error": f"Path '{ws_path}' is outside allowed roots."}
        if not ws_path.is_dir():
            return {"ok": False, "error": f"Directory '{ws_path}' does not exist."}
        def _git(args: list[str], timeout: int = 8) -> subprocess.CompletedProcess:
            return subprocess.run(
                ["git", "-c", "safe.directory=*"] + args,
                cwd=str(ws_path), capture_output=True, text=True, timeout=timeout, check=False,
            )
        b_proc = _git(["rev-parse", "--abbrev-ref", "HEAD"])
        if b_proc.returncode != 0:
            return {"ok": False, "error": b_proc.stderr.strip() or "Not a git repository"}
        branch = b_proc.stdout.strip()
        status_short = _git(["status", "--short"]).stdout.strip()
        diff_stat = _git(["diff", "--stat", target_branch, "--"]).stdout.strip()
        if not diff_stat and target_branch != "HEAD":
            st_check = _git(["rev-parse", "--verify", target_branch])
            if st_check.returncode != 0:
                target_branch = "HEAD"
                diff_stat = _git(["diff", "--stat", "HEAD", "--"]).stdout.strip()
        req_fp = str(payload.get("file_path") or "").strip()
        safe_fp = ""
        if req_fp:
            norm_fp = os.path.normpath(req_fp).lstrip("/")
            if not norm_fp.startswith(".."):
                safe_fp = norm_fp
        diff_out = ""
        if not summary_only:
            diff_proc = _git(["diff", target_branch, "--"] + ([safe_fp] if safe_fp else []), timeout=12)
            diff_out = diff_proc.stdout
        untracked: list[str] = []
        if include_untracked:
            u_proc = _git(["ls-files", "--others", "--exclude-standard"])
            if u_proc.returncode == 0 and u_proc.stdout.strip():
                untracked = u_proc.stdout.strip().splitlines()[:100]
        return {
            "ok": True, "workspace": str(ws_path),
            "branch": branch, "current_branch": branch,
            "status_short": status_short, "diff_stat": diff_stat,
            "diff": diff_out[:60000],
            "diff_truncated": len(diff_out) > 60000,
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
        conv_id = sanitize_conv_id(str(payload.get("conversation_id") or ""))
        prompt = guard_cli_positional(str(payload.get("prompt") or ""))
        title = str(payload.get("title") or "").strip()
        if not conv_id or not prompt.strip():
            return {"ok": False, "error": "conversation_id and prompt are required"}
        cmd = [AGENTAPI_BIN, "send-message"]
        if title:
            cmd.append(f"--title={title}")
        cmd.extend([conv_id, prompt])
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=25)
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode, "conversation_id": conv_id,
            "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip(),
        }
    if action == "new-conversation":
        prompt = guard_cli_positional(str(payload.get("prompt") or ""))
        if not prompt.strip():
            return {"ok": False, "error": "prompt is required"}
        model = str(payload.get("model") or "pro").strip()
        if model not in ("flash_lite", "flash", "pro"):
            model = "pro"
        title = str(payload.get("title") or "").strip()
        resolved_proj_id, resolved_dir, resolved_name = resolve_project_workspace(
            project_name=str(payload.get("project_name") or "").strip(),
            workspace_path=str(payload.get("workspace_path") or "").strip(),
            project_id=str(payload.get("project_id") or "").strip(),
        )
        if resolved_proj_id:
            set_active_project_in_storage(resolved_proj_id)
        default_run_cwd = (AGY_WORKSPACE_DIR / "projects") if (AGY_WORKSPACE_DIR / "projects").is_dir() else AGY_GITLAB_DIR
        run_cwd = resolved_dir if (resolved_dir and Path(resolved_dir).is_dir()) else str(default_run_cwd)
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
            "returncode": proc.returncode, "conversation_id": new_conv_id,
            "project_id": resolved_proj_id, "workspace_path": run_cwd,
            "project_name": resolved_name, "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    if action == "get-conversation-metadata":
        conv_id = sanitize_conv_id(str(payload.get("conversation_id") or ""))
        if not conv_id:
            return {"ok": False, "error": "conversation_id is required"}
        cmd = [AGENTAPI_BIN, "get-conversation-metadata", conv_id]
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=15)
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode, "conversation_id": conv_id,
            "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip(),
        }
    return {"ok": False, "error": f"Unknown action: {action}"}


class HostBridgeHandler(BaseHTTPRequestHandler):
    quiet_logs: bool = False

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        if not self.quiet_logs:
            super().log_message(format, *args)

    def _send_json(self, status: int, data: dict) -> None:
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self._send_json(405, {"ok": False, "error": "Method not allowed"})

    def do_GET(self) -> None:
        if self.path.startswith("/health"):
            self._send_json(200, {"status": "ok", "service": "agy-host-bridge"})
            return
        self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        client_ip = self.client_address[0] if self.client_address else ""
        status, err_msg, length = validate_agentapi_request(
            client_ip=client_ip,
            headers=self.headers,
            expected_token=get_expected_bridge_token(),
        )
        if status != 200:
            self._send_json(status, {"ok": False, "error": err_msg})
            return
        if not self.path.startswith("/agentapi"):
            self._send_json(404, {"ok": False, "error": "Not found"})
            return
        raw = self.rfile.read(length).decode("utf-8", errors="replace") if length > 0 else "{}"
        try:
            payload = json.loads(raw) if raw.strip() else {}
        except Exception:
            self._send_json(400, {"ok": False, "error": "Invalid JSON payload."})
            return
        if not isinstance(payload, dict):
            self._send_json(400, {"ok": False, "error": "JSON payload must be an object."})
            return
        try:
            res = handle_agentapi_request(payload)
            self._send_json(200, res)
        except Exception as e:
            self._send_json(500, {"ok": False, "error": str(e)})


def main() -> None:
    expected = get_expected_bridge_token()
    if len(expected) < 32:
        sys.exit(
            "FATAL: agy-host-bridge requires HOST_BRIDGE_TOKEN or PATH_SECRET (>=32 chars) "
            "in ~/.config/ag-bridge-mcp/secrets.env (fail-closed)."
        )
    print(f"Starting agy-host-bridge on {BIND_HOST}:{BIND_PORT} (authenticated, threaded)...", flush=True)
    server = ThreadingHTTPServer((BIND_HOST, BIND_PORT), HostBridgeHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
