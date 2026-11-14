#!/usr/bin/env python3
"""
project_manager.py — Antigravity Language Server Discovery, Project Registry & Conversation ID Parser.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import threading
from typing import Any
import urllib.error
import urllib.request
import uuid

try:
    from host_bridge.bridge_security import resolve_allowed_git_roots, sanitize_conv_id, sanitize_git_ref
except ImportError:
    from bridge_security import resolve_allowed_git_roots, sanitize_conv_id, sanitize_git_ref  # type: ignore[no-redef]

_UUID_RE = re.compile(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})")
_PILLAR_NAMES = ("projects", "workbooks", "configuration")


def slugify_project(name: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", (name or "").strip().lower()).strip("-._")
    return slug or "new-project"


def _probe_ls_http_port(candidate_ports: list[int]) -> int | None:
    for port in candidate_ports:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/", method="POST")
        try:
            with urllib.request.urlopen(req, timeout=0.8) as resp:
                if "JetskiWeb" in (resp.headers.get("Content-Security-Policy") or ""):
                    return port
        except urllib.error.HTTPError as e:
            if "JetskiWeb" in ((e.headers.get("Content-Security-Policy") if e.headers else "") or ""):
                return port
        except Exception:
            continue
    return min(candidate_ports) if candidate_ports else None


def discover_antigravity_env(project_id: str = "", data_dir: Path | None = None) -> dict[str, str]:
    """Discover running Antigravity Language Server address/CSRF token and scope ANTIGRAVITY_PROJECT_ID."""
    eff_data_dir = data_dir or Path(os.getenv("AGY_DATA_DIR", str(Path.home() / ".gemini/antigravity"))).expanduser()
    env = os.environ.copy()
    env.pop("ANTIGRAVITY_LS_ADDRESS", None)
    env.pop("ANTIGRAVITY_CSRF_TOKEN", None)
    ls_pid, csrf_token, ls_exe = "", "", "/opt/antigravity/resources/bin/language_server"

    proc_root = Path("/proc")
    if proc_root.is_dir():
        for proc_dir in proc_root.iterdir():
            if not proc_dir.name.isdigit():
                continue
            try:
                cmdline = (proc_dir / "cmdline").read_bytes().decode("utf-8", errors="ignore").split("\x00")
                if cmdline and "language_server" in cmdline[0] and any("--csrf_token" in a for a in cmdline):
                    if "--standalone" in cmdline or not ls_pid:
                        ls_pid, ls_exe = proc_dir.name, cmdline[0]
                        for i, arg in enumerate(cmdline):
                            if arg == "--csrf_token" and i + 1 < len(cmdline):
                                csrf_token = cmdline[i + 1]
                            elif arg.startswith("--csrf_token="):
                                csrf_token = arg.split("=", 1)[1]
                        if "--standalone" in cmdline and csrf_token:
                            break
            except Exception:
                continue

    if not ls_pid or not csrf_token:
        try:
            ps_out = subprocess.check_output(["ps", "-ef"], text=True, timeout=5)
            for line in ps_out.splitlines():
                if "language_server" in line and "--csrf_token" in line:
                    parts = line.split()
                    m = re.search(r"--csrf_token[=\s]+([^\s]+)", line)
                    if len(parts) > 1 and m:
                        ls_pid, csrf_token = parts[1], m.group(1)
                        break
        except Exception:
            return env

    if not ls_pid or not csrf_token:
        return env

    candidate_ports: list[int] = []
    try:
        ss_out = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True, timeout=5, check=False).stdout
        for line in ss_out.splitlines():
            if f"pid={ls_pid}," in line:
                m_port = re.search(r"127\.0\.0\.1:(\d+)", line)
                if m_port:
                    candidate_ports.append(int(m_port.group(1)))
    except Exception:
        pass

    ls_port = _probe_ls_http_port(candidate_ports)
    if not ls_port:
        return env

    env["ANTIGRAVITY_AGENT"] = "1"
    if Path(ls_exe).exists():
        env["ANTIGRAVITY_AGENTAPI_EXE"] = ls_exe
    env["ANTIGRAVITY_APP_DATA_DIR"] = str(eff_data_dir)
    env["ANTIGRAVITY_CSRF_TOKEN"] = csrf_token
    env["ANTIGRAVITY_LS_ADDRESS"] = f"localhost:{ls_port}"
    clean_pid = sanitize_conv_id(project_id)
    if clean_pid:
        env["ANTIGRAVITY_PROJECT_ID"] = clean_pid
    else:
        env.pop("ANTIGRAVITY_PROJECT_ID", None)
    return env


def list_antigravity_projects(projects_dir: Path) -> list[dict[str, Any]]:
    """Read all Antigravity project definitions from ~/.gemini/config/projects/*.json."""
    projects: list[dict[str, Any]] = []
    if not projects_dir.is_dir():
        return projects
    for pfile in sorted(projects_dir.glob("*.json")):
        try:
            data = json.loads(pfile.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            pid = str(data.get("id") or pfile.stem)
            name = str(data.get("name") or pid)
            uris: list[str] = []
            paths: list[str] = []
            for res in (data.get("projectResources") or {}).get("resources") or []:
                uri = (res.get("gitFolder") or {}).get("folderUri") or res.get("folderUri") or ""
                if uri:
                    uris.append(str(uri))
                    paths.append(str(uri).replace("file://", "").rstrip("/"))
            for legacy_p in data.get("paths") or []:
                clean_lp = str(legacy_p).replace("file://", "").rstrip("/")
                if clean_lp and clean_lp not in paths:
                    paths.append(clean_lp)
            projects.append({"project_id": pid, "name": name, "workspace_uris": uris, "workspace_paths": paths})
        except Exception:
            continue
    return projects


def normalize_host_workspace_path(raw_path: str, workspace_root: Path, gitlab_root: Path) -> Path | None:
    """Normalize shorthand ('projects/foo', '~/projects/foo', '/home/u/projects/foo') while leaving $HOME and / untouched."""
    cleaned = re.sub(r"^file://", "", (raw_path or "").strip()).rstrip("/")
    if not cleaned:
        return None
    if any(pt in (".", "..") for pt in cleaned.split("/")):
        return Path("/__invalid_traversal__")
    exp_str = os.path.expanduser(cleaned)
    ws_abs = Path(os.path.abspath(str(workspace_root)))
    home_roots = {Path(os.path.abspath(str(Path.home()))), ws_abs.parent} - {Path("/")}

    if not Path(exp_str).is_absolute():
        parts = [pt for pt in cleaned.strip("/").split("/") if pt]
        if len(parts) == 2 and parts[0].lower() in _PILLAR_NAMES:
            return ws_abs / parts[0].lower() / parts[1]
        if len(parts) == 1:
            for p_name in _PILLAR_NAMES:
                cand = ws_abs / p_name / parts[0]
                if cand.is_dir():
                    return cand.resolve()
            if (gitlab_root / parts[0]).is_dir():
                return (gitlab_root / parts[0]).resolve()
            return (ws_abs / "projects" / parts[0]) if (ws_abs / "projects").is_dir() else (gitlab_root / parts[0])
        return Path(os.path.abspath(exp_str))

    abs_p = Path(os.path.abspath(exp_str))
    if abs_p.parent and Path(os.path.abspath(str(abs_p.parent.parent))) in home_roots and abs_p.parent.name.lower() in _PILLAR_NAMES:
        return ws_abs / abs_p.parent.name.lower() / abs_p.name
    return abs_p


def sync_project_in_app_storage(app_storage_path: Path, project_id: str, storage_lock: threading.Lock, newly_created: bool = False) -> bool:
    """Atomically update lastActiveProjectId (and projectsOrder when newly_created) in app_storage.json."""
    if not project_id or not app_storage_path.is_file():
        return False
    try:
        with storage_lock:
            raw = json.loads(app_storage_path.read_text(encoding="utf-8"))
            if newly_created:
                order_raw = raw.get("projectsOrder", "[]")
                order_list = json.loads(order_raw) if isinstance(order_raw, str) else list(order_raw)
                if project_id not in order_list:
                    order_list.insert(0, project_id)
                    raw["projectsOrder"] = json.dumps(order_list)
                raw["lastCreatedProjectId"] = project_id
            state_str = raw.get("antigravityUnifiedStateSync.projectManager")
            if isinstance(state_str, str):
                pm_state = json.loads(state_str)
                pm_state["lastActiveProjectId"] = project_id
                raw["antigravityUnifiedStateSync.projectManager"] = json.dumps(pm_state, separators=(",", ":"))
            tmp_p = app_storage_path.with_suffix(f".json.tmp.{os.getpid()}_{threading.get_ident()}")
            tmp_p.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
            tmp_p.replace(app_storage_path)
        return True
    except Exception:
        return False


def _pick_project_ws(p_paths: list[str], req_ws: str, slug_hint: str = "") -> str:
    """Select matching workspace path inside multi-repo Antigravity projects instead of clobbering with workspace_paths[0]."""
    if req_ws and (req_ws in p_paths or any(req_ws.startswith(pp + "/") for pp in p_paths) or Path(req_ws).is_dir()):
        return req_ws
    if slug_hint:
        for pp in p_paths:
            if Path(pp).name.lower() == slug_hint.lower():
                return pp
    return p_paths[0] if p_paths else req_ws


def _sanitize_init_branch(raw_branch: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_./-]", "", (raw_branch or "main").strip()).strip("./-")
    if not cleaned or ".." in cleaned or cleaned.endswith(".lock") or cleaned.upper() == "HEAD":
        return "main"
    return cleaned[:64]


def resolve_or_create_project(
    env: dict[str, str],
    *,
    project_id: str = "",
    project_name: str = "",
    workspace_path: str = "",
    create_if_missing: bool = False,
    default_branch: str = "main",
    projects_dir: Path,
    workspace_root: Path,
    gitlab_root: Path,
    data_dir: Path,
    app_storage_path: Path,
    storage_lock: threading.Lock,
) -> dict[str, Any]:
    """Match an existing Antigravity project or register a new one via LanguageServerService/CreateProject."""
    projects = list_antigravity_projects(projects_dir)
    pid_clean = sanitize_conv_id(project_id)
    pname_clean = (project_name or "").strip()
    norm_ws_path = normalize_host_workspace_path(workspace_path, workspace_root, gitlab_root)
    wpath_clean = str(norm_ws_path.resolve() if norm_ws_path else "").rstrip("/")

    if pid_clean:
        for p in projects:
            if p["project_id"] == pid_clean:
                return {"ok": True, "project_id": p["project_id"], "project_name": p["name"], "workspace_path": _pick_project_ws(p["workspace_paths"], wpath_clean), "created": False}

    if wpath_clean:
        for p in projects:
            if wpath_clean in p["workspace_paths"]:
                return {"ok": True, "project_id": p["project_id"], "project_name": p["name"], "workspace_path": wpath_clean, "created": False}

    if pname_clean:
        target_slug = slugify_project(pname_clean)
        for p in projects:
            if p["name"].lower() == pname_clean.lower() or slugify_project(p["name"]) == target_slug or any(Path(wp).name.lower() == target_slug for wp in p["workspace_paths"]):
                return {"ok": True, "project_id": p["project_id"], "project_name": p["name"], "workspace_path": _pick_project_ws(p["workspace_paths"], wpath_clean, target_slug), "created": False}

    if not pname_clean and not wpath_clean:
        fallback_ws = str((workspace_root / "projects") if (workspace_root / "projects").is_dir() else gitlab_root)
        return {"ok": True, "project_id": "", "project_name": "", "workspace_path": fallback_ws, "created": False}

    slug = slugify_project(Path(wpath_clean).name if wpath_clean else pname_clean)
    display_name = pname_clean or slug
    allowed_roots = resolve_allowed_git_roots(gitlab_root, data_dir, workspace_root)
    default_proj_base = (workspace_root / "projects") if (workspace_root / "projects").is_dir() else gitlab_root
    cand_dir = Path(wpath_clean) if wpath_clean else (default_proj_base / slug)
    cand_res = Path(os.path.abspath(str(cand_dir))).resolve()
    if not any(cand_res != r and cand_res.is_relative_to(r) for r in allowed_roots):
        return {"ok": False, "error": f"Path '{cand_res}' is outside allowed roots.", "project_id": "", "project_name": display_name, "workspace_path": str(cand_res), "created": False}
    if not cand_res.is_dir() and create_if_missing and cand_res.parent not in allowed_roots:
        return {"ok": False, "error": f"Greenfield project '{cand_res}' must be a direct child of a workspace pillar root.", "project_id": "", "project_name": display_name, "workspace_path": str(cand_res), "created": False}
    if not cand_res.is_dir() and not create_if_missing:
        return {
            "ok": False, "project_not_found": True, "project_id": "", "project_name": display_name,
            "workspace_path": str(cand_res), "created": False,
            "error": f"Target repository '{cand_res}' does not exist and create_new_project=False.",
        }

    safe_branch = _sanitize_init_branch(default_branch or "main")
    cand_res.mkdir(parents=True, exist_ok=True)
    if not (cand_res / ".git").exists():
        init_p = subprocess.run(["git", "init", "-b", safe_branch], cwd=str(cand_res), capture_output=True, text=True, check=False)
        if init_p.returncode != 0:
            safe_branch = "main"
            subprocess.run(["git", "init", "-b", "main"], cwd=str(cand_res), capture_output=True, text=True, check=False)
    elif not default_branch:
        b_proc = subprocess.run(["git", "-c", "safe.directory=*", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(cand_res), capture_output=True, text=True, check=False)
        if b_proc.returncode == 0 and b_proc.stdout.strip() and b_proc.stdout.strip() != "HEAD":
            safe_branch = _sanitize_init_branch(b_proc.stdout.strip())

    new_pid = str(uuid.uuid4())
    create_payload = {
        "project": {
            "id": new_pid, "name": display_name,
            "projectResources": {"resources": [{"gitFolder": {"folderUri": f"file://{cand_res}/", "defaultBranch": safe_branch}}]},
            "settings": {}, "isWorkspaceOnly": False,
        }
    }
    ls_addr, csrf = env.get("ANTIGRAVITY_LS_ADDRESS", ""), env.get("ANTIGRAVITY_CSRF_TOKEN", "")
    req = urllib.request.Request(
        f"http://{ls_addr}/exa.language_server_pb.LanguageServerService/CreateProject",
        data=json.dumps(create_payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Connect-Protocol-Version": "1", "x-codeium-csrf-token": csrf},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            resp.read()
    except Exception as exc:
        return {"ok": False, "error": f"CreateProject RPC failed: {exc}", "project_id": "", "project_name": display_name, "workspace_path": str(cand_res), "created": False}
    sync_project_in_app_storage(app_storage_path, new_pid, storage_lock, newly_created=True)
    return {"ok": True, "project_id": new_pid, "project_name": display_name, "workspace_path": str(cand_res), "default_branch": safe_branch, "created": True}


def extract_agentapi_conversation_id(stdout: str, stderr: str = "", disallow_ids: set[str] | None = None) -> str:
    """Extract spawned conversationId from agentapi JSON stdout without matching prompt-embedded Prior Session Baton UUIDs."""
    banned = {x.lower() for x in (disallow_ids or set()) if x}
    raw_out = (stdout or "").strip()
    if raw_out:
        candidates = [raw_out]
        i_brace, j_brace = raw_out.find("{"), raw_out.rfind("}")
        if 0 <= i_brace < j_brace:
            candidates.append(raw_out[i_brace : j_brace + 1])
        candidates.extend(ln.strip() for ln in reversed(raw_out.splitlines()) if ln.strip().startswith("{"))
        for chunk in candidates:
            try:
                obj = json.loads(chunk)
                if isinstance(obj, dict):
                    cid = (
                        ((obj.get("response") or {}).get("newConversation") or {}).get("conversationId")
                        or (obj.get("newConversation") or {}).get("conversationId")
                        or obj.get("conversationId")
                        or obj.get("conversation_id")
                        or ""
                    )
                    if isinstance(cid, str) and _UUID_RE.fullmatch(cid.strip()) and cid.strip().lower() not in banned:
                        return cid.strip()
            except Exception:
                continue

    combined = f"{stdout or ''}\n{stderr or ''}"
    keyed = re.findall(r'"conversationId"\s*:\s*"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"', combined)
    for cid in reversed(keyed):
        if cid.lower() not in banned:
            return cid

    all_uuids = _UUID_RE.findall(combined)
    for cid in reversed(all_uuids):
        if cid.lower() not in banned:
            return cid
    return ""
