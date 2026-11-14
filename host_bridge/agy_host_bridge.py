#!/usr/bin/env python3
"""
agy_host_bridge.py — Authenticated Host Companion Daemon & Unified /agentapi Handler (:8098).
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import subprocess
import threading

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
    from host_bridge.project_manager import (
        discover_antigravity_env,
        extract_agentapi_conversation_id,
        list_antigravity_projects,
        normalize_host_workspace_path,
        resolve_or_create_project,
        sync_project_in_app_storage,
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
    from project_manager import (  # type: ignore[no-redef]
        discover_antigravity_env,
        extract_agentapi_conversation_id,
        list_antigravity_projects,
        normalize_host_workspace_path,
        resolve_or_create_project,
        sync_project_in_app_storage,
    )

load_bridge_env_file()

BIND_HOST = os.getenv("HOST_BRIDGE_BIND_HOST", DEFAULT_BIND_HOST)
BIND_PORT = int(os.getenv("HOST_BRIDGE_BIND_PORT", "8098"))
AGY_DATA_DIR = Path(os.getenv("AGY_DATA_DIR", str(Path.home() / ".gemini/antigravity"))).expanduser()
AGY_CONFIG_DIR = Path(os.getenv("AGY_CONFIG_DIR", str(Path.home() / ".gemini/config"))).expanduser()
AGY_WORKSPACE_DIR = Path(os.getenv("AGY_WORKSPACE_DIR", str(Path.home() / "agentic_workspace"))).expanduser()
_DEFAULT_PROJ_DIR = AGY_WORKSPACE_DIR / "projects"
AGY_GITLAB_DIR = Path(
    os.getenv("AGY_GITLAB_DIR") or (str(_DEFAULT_PROJ_DIR) if _DEFAULT_PROJ_DIR.is_dir() else str(Path.home() / "gitlab"))
).expanduser()
AGENTAPI_BIN = os.getenv("AGENTAPI_BIN", str(AGY_DATA_DIR / "bin/agentapi"))
PROJECTS_DIR = AGY_CONFIG_DIR / "projects"
APP_STORAGE_PATH = Path(os.getenv("AGY_APP_STORAGE", str(Path.home() / ".config/Antigravity/app_storage.json"))).expanduser()
BRIDGE_TOKEN_OVERRIDE: str = ""
MOCK_ACTION_HANDLER = None
_STORAGE_LOCK = threading.Lock()
_UUID_PROMPT_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def get_expected_bridge_token() -> str:
    """Resolve active expected X-Bridge-Token for /agentapi requests."""
    return BRIDGE_TOKEN_OVERRIDE if BRIDGE_TOKEN_OVERRIDE else derive_bridge_token()


def _is_path_allowed(cand: Path) -> bool:
    allowed_roots = resolve_allowed_git_roots(AGY_GITLAB_DIR, AGY_DATA_DIR, AGY_WORKSPACE_DIR)
    pkg_root = Path(__file__).resolve().parents[1].resolve()
    res = Path(os.path.abspath(str(cand))).resolve()
    return res == pkg_root or any(res != r and res.is_relative_to(r) for r in allowed_roots)


def _run_git_inspect(payload: dict) -> dict:
    ws_raw = str(payload.get("workspace_path") or "").strip()
    target_branch = sanitize_git_ref(str(payload.get("target_branch") or "HEAD"))
    include_untracked = bool(payload.get("include_untracked", True))
    summary_only = bool(payload.get("summary_only", False))
    if not ws_raw:
        return {"ok": False, "error": "workspace_path is required"}
    norm_ws = normalize_host_workspace_path(ws_raw, AGY_WORKSPACE_DIR, AGY_GITLAB_DIR)
    ws_path = norm_ws.resolve() if (norm_ws and norm_ws.exists()) else Path(ws_raw).expanduser().resolve()
    if not _is_path_allowed(ws_path):
        return {"ok": False, "error": f"Path '{ws_path}' is outside allowed roots."}
    if not ws_path.is_dir():
        return {"ok": False, "error": f"Directory '{ws_path}' does not exist."}

    def _git(args: list[str], timeout: int = 8) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-c", "safe.directory=*"] + args, cwd=str(ws_path), capture_output=True, text=True, timeout=timeout, check=False)

    b_proc = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    if b_proc.returncode != 0:
        return {"ok": False, "error": b_proc.stderr.strip() or "Not a git repository"}
    branch = b_proc.stdout.strip()
    status_short = _git(["status", "--short"]).stdout.strip()
    diff_stat = _git(["diff", "--stat", target_branch, "--"]).stdout.strip()
    if not diff_stat and target_branch != "HEAD":
        if _git(["rev-parse", "--verify", target_branch]).returncode != 0:
            target_branch = "HEAD"
            diff_stat = _git(["diff", "--stat", "HEAD", "--"]).stdout.strip()
    req_fp = str(payload.get("file_path") or "").strip()
    safe_fp = os.path.normpath(req_fp).lstrip("/") if req_fp else ""
    if safe_fp.startswith(".."):
        safe_fp = ""
    diff_out = _git(["diff", target_branch, "--"] + ([safe_fp] if safe_fp else []), timeout=12).stdout if not summary_only else ""
    untracked: list[str] = []
    if include_untracked:
        u_proc = _git(["ls-files", "--others", "--exclude-standard"])
        if u_proc.returncode == 0 and u_proc.stdout.strip():
            untracked = u_proc.stdout.strip().splitlines()[:120]
    return {
        "ok": True, "workspace": str(ws_path), "branch": branch, "current_branch": branch,
        "target_branch": target_branch, "status_short": status_short, "diff_stat": diff_stat,
        "diff": diff_out[:120000], "diff_truncated": len(diff_out) > 120000, "untracked_files": untracked,
    }


def _clean_cli_title(raw_title: str) -> str:
    return re.sub(r"[\x00-\x1f\x7f]+", " ", str(raw_title or "")).strip()[:200]


def _run_new_conversation(payload: dict, env: dict[str, str]) -> dict:
    prompt = guard_cli_positional(str(payload.get("prompt") or ""))
    if not prompt.strip():
        return {"ok": False, "error": "prompt is required"}
    model = str(payload.get("model") or "pro").strip()
    model = model if model in ("flash_lite", "flash", "pro") else "pro"
    title = _clean_cli_title(str(payload.get("title") or ""))
    proj_info = resolve_or_create_project(
        env,
        project_id=str(payload.get("project_id") or ""),
        project_name=str(payload.get("project_name") or ""),
        workspace_path=str(payload.get("workspace_path") or ""),
        create_if_missing=bool(payload.get("create_new_project", False)),
        default_branch=str(payload.get("default_branch") or "main"),
        projects_dir=PROJECTS_DIR,
        workspace_root=AGY_WORKSPACE_DIR,
        gitlab_root=AGY_GITLAB_DIR,
        data_dir=AGY_DATA_DIR,
        app_storage_path=APP_STORAGE_PATH,
        storage_lock=_STORAGE_LOCK,
    )
    if not proj_info.get("ok", True):
        return proj_info
    resolved_pid = str(proj_info.get("project_id") or "")
    if resolved_pid:
        env["ANTIGRAVITY_PROJECT_ID"] = resolved_pid
        sync_project_in_app_storage(APP_STORAGE_PATH, resolved_pid, _STORAGE_LOCK, newly_created=False)

    default_cwd = (AGY_WORKSPACE_DIR / "projects") if (AGY_WORKSPACE_DIR / "projects").is_dir() else AGY_GITLAB_DIR
    cand_cwd = Path(str(proj_info.get("workspace_path") or default_cwd)).expanduser().resolve()
    run_cwd = str(cand_cwd) if (cand_cwd.is_dir() and (_is_path_allowed(cand_cwd) or cand_cwd == default_cwd.resolve())) else str(default_cwd)

    cmd = [AGENTAPI_BIN, "new-conversation", f"--model={model}"]
    if title:
        cmd.append(f"--title={title}")
    cmd.append(prompt)
    proc = subprocess.run(cmd, env=env, cwd=run_cwd, capture_output=True, text=True, timeout=25)
    prompt_uuids = set(_UUID_PROMPT_RE.findall(prompt))
    new_conv_id = extract_agentapi_conversation_id(proc.stdout or "", proc.stderr or "", disallow_ids=prompt_uuids)
    return {
        "ok": proc.returncode == 0, "returncode": proc.returncode, "conversation_id": new_conv_id,
        "project_id": resolved_pid, "project_name": proj_info.get("project_name", ""),
        "workspace_path": run_cwd, "project_created": bool(proj_info.get("created")),
        "stdout": (proc.stdout or "").strip(), "stderr": (proc.stderr or "").strip(),
    }


def handle_agentapi_request(payload: dict) -> dict:
    """Handle authenticated /agentapi requests from ag-bridge-mcp."""
    if callable(MOCK_ACTION_HANDLER):
        return MOCK_ACTION_HANDLER(payload)
    action = str(payload.get("action") or "discover").strip().lower()
    if action == "ping":
        return {"ok": True, "service": "agy-host-bridge"}
    if action == "list-projects":
        return {"ok": True, "projects": list_antigravity_projects(PROJECTS_DIR)}

    req_ws = str(payload.get("workspace_path") or "").strip()
    if action in ("ensure-project", "new-conversation") and req_ws:
        norm_ws = normalize_host_workspace_path(req_ws, AGY_WORKSPACE_DIR, AGY_GITLAB_DIR)
        if norm_ws is None or not _is_path_allowed(norm_ws):
            return {"ok": False, "error": f"Path '{norm_ws or req_ws}' is outside allowed roots."}

    if action == "git-inspect":
        return _run_git_inspect(payload)

    req_pid = sanitize_conv_id(str(payload.get("project_id") or ""))
    env = discover_antigravity_env(project_id=req_pid, data_dir=AGY_DATA_DIR)
    if "ANTIGRAVITY_LS_ADDRESS" not in env:
        return {"ok": False, "error": "Could not discover running Antigravity Language Server"}

    if action == "discover":
        return {
            "ok": True, "ls_address": env.get("ANTIGRAVITY_LS_ADDRESS", ""),
            "app_data_dir": env.get("ANTIGRAVITY_APP_DATA_DIR", ""),
            "projects": list_antigravity_projects(PROJECTS_DIR),
        }
    if action == "ensure-project":
        return resolve_or_create_project(
            env, project_id=req_pid, project_name=str(payload.get("project_name") or ""),
            workspace_path=req_ws, create_if_missing=bool(payload.get("create_new_project", True)),
            default_branch=str(payload.get("default_branch") or "main"), projects_dir=PROJECTS_DIR,
            workspace_root=AGY_WORKSPACE_DIR, gitlab_root=AGY_GITLAB_DIR, data_dir=AGY_DATA_DIR,
            app_storage_path=APP_STORAGE_PATH, storage_lock=_STORAGE_LOCK,
        )
    if action == "send-message":
        conv_id = sanitize_conv_id(str(payload.get("conversation_id") or ""))
        prompt = guard_cli_positional(str(payload.get("prompt") or ""))
        title = _clean_cli_title(str(payload.get("title") or ""))
        if not conv_id or not prompt.strip():
            return {"ok": False, "error": "conversation_id and prompt are required"}
        cmd = [AGENTAPI_BIN, "send-message"] + ([f"--title={title}"] if title else []) + [conv_id, prompt]
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=25)
        return {"ok": proc.returncode == 0, "returncode": proc.returncode, "conversation_id": conv_id, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}
    if action == "new-conversation":
        return _run_new_conversation(payload, env)
    if action == "get-conversation-metadata":
        conv_id = sanitize_conv_id(str(payload.get("conversation_id") or ""))
        if not conv_id:
            return {"ok": False, "error": "conversation_id is required"}
        proc = subprocess.run([AGENTAPI_BIN, "get-conversation-metadata", conv_id], env=env, capture_output=True, text=True, timeout=15)
        return {"ok": proc.returncode == 0, "returncode": proc.returncode, "conversation_id": conv_id, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}
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
        status, err_msg, length = validate_agentapi_request(client_ip=client_ip, headers=self.headers, expected_token=get_expected_bridge_token())
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
            self._send_json(200, handle_agentapi_request(payload))
        except Exception as e:
            self._send_json(500, {"ok": False, "error": str(e)})


def main() -> None:
    expected_tok = get_expected_bridge_token()
    if len(expected_tok) < 32:
        raise SystemExit("FATAL: HOST_BRIDGE_TOKEN or PATH_SECRET (>=32 chars) must be configured in secrets.env before starting agy_host_bridge.")
    server = ThreadingHTTPServer((BIND_HOST, BIND_PORT), HostBridgeHandler)
    print(f"[*] Antigravity Host Bridge listening on http://{BIND_HOST}:{BIND_PORT} (Zero-Trust token + CIDR guard active)")
    server.serve_forever()


if __name__ == "__main__":
    main()
