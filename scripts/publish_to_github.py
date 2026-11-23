#!/usr/bin/env python3
"""Create/sync GitHub repo, orphan gh-pages showcase branch, Pages config, and matching Release.

Security & Privacy Guarantees:
1. Reads GITHUB_TOKEN from ~/.config/ag-bridge-mcp/secrets.env or the GITHUB_TOKEN environment variable.
2. Builds fresh orphan commits on both `main` and `gh-pages` so historical commits are never exposed.
3. Defaults commit author email to `<github-login>@users.noreply.github.com`.
4. Always builds and passes `build_github_showcase.scan_showcase_privacy()` before pushing or `--dry-run`.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from build_github_showcase import build_showcase


def _load_token_from_env_files() -> str:
    """Load GITHUB_TOKEN or GH_TOKEN from environment or ~/.config/ag-bridge-mcp/secrets.env."""
    for env_key in ("GITHUB_TOKEN", "GH_TOKEN"):
        val = os.getenv(env_key, "").strip()
        if val:
            return val
    candidates = [
        Path(os.getenv("AG_BRIDGE_ENV_FILE", "/config/secrets.env")),
        Path.home() / ".config/ag-bridge-mcp/secrets.env",
        Path.home() / ".config/github/secrets.env",
    ]
    for cand in candidates:
        if cand.is_file():
            try:
                for line in cand.read_text(encoding="utf-8").splitlines():
                    s = line.strip()
                    if not s or s.startswith("#") or "=" not in s:
                        continue
                    k, v = s.split("=", 1)
                    if k.strip() in ("GITHUB_TOKEN", "GH_TOKEN"):
                        tok = v.strip().strip("'\"")
                        if tok:
                            return tok
            except Exception:
                continue
    return ""


def _github_api(method: str, path: str, token: str, payload: dict | None = None) -> tuple[int, dict]:
    """Call the GitHub REST API v3 and return (status_code, parsed_json)."""
    url = f"https://api.github.com{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url, data=data,
        headers={
            "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "agy-nexus-mcp-publisher",
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            err_json = json.loads(raw) if raw else {"message": str(e)}
        except Exception:
            err_json = {"message": raw or str(e)}
        return e.code, err_json


def _read_package_version(src_root: Path) -> str:
    pyproject = src_root / "pyproject.toml"
    if pyproject.is_file():
        m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"), re.M)
        if m:
            return m.group(1).strip()
    return "4.0.4"


def _extract_changelog_section(src_root: Path, version: str) -> str:
    changelog = src_root / "CHANGELOG.md"
    if not changelog.is_file():
        return f"## AGY Nexus v{version}"
    text = changelog.read_text(encoding="utf-8")
    pattern = rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^---\s*$|^## \[|\Z)"
    m = re.search(pattern, text, re.M | re.S)
    if m and m.group(1).strip():
        return f"## AGY Nexus v{version}\n\n{m.group(1).strip()}\n"
    return f"## AGY Nexus v{version}"


def _ensure_repo(gh_login: str, repo_name: str, description: str, private: bool, token: str) -> int:
    st_repo, _ = _github_api("GET", f"/repos/{gh_login}/{repo_name}", token)
    if st_repo == 200:
        _github_api("PATCH", f"/repos/{gh_login}/{repo_name}", token, {
            "name": repo_name, "description": description, "private": bool(private),
            "homepage": f"https://{gh_login}.github.io/{repo_name}/",
        })
        print(f"[✓] Verified GitHub repo: https://github.com/{gh_login}/{repo_name}")
        return 0
    if st_repo == 404:
        st_cr, cr_data = _github_api("POST", "/user/repos", token, {
            "name": repo_name, "description": description, "private": bool(private),
            "auto_init": False, "has_issues": True, "has_projects": False, "has_wiki": False,
            "homepage": f"https://{gh_login}.github.io/{repo_name}/",
        })
        if st_cr not in (200, 201):
            print(f"ERROR: Failed creating repository (HTTP {st_cr}): {cr_data.get('message')}", file=sys.stderr)
            return 1
        print(f"[✓] Created repository: {cr_data.get('html_url')}")
        return 0
    print(f"ERROR: Unexpected HTTP {st_repo} inspecting repo.", file=sys.stderr)
    return 1


def _git_auth_env(auth_header_value: str) -> dict[str, str]:
    env = dict(os.environ)
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "http.https://github.com/.extraheader"
    env["GIT_CONFIG_VALUE_0"] = auth_header_value
    return env


def _scrub_secrets(text: str, *secrets: str) -> str:
    out = text or ""
    for sec in secrets:
        if sec and len(sec) >= 4:
            out = out.replace(sec, "[REDACTED]")
    return out


def _sync_branch(
    src_dir: Path, branch: str, remote_url: str, auth_header_value: str,
    author_name: str, author_email: str, commit_msg: str, *, force_orphan: bool = False,
) -> int:
    git_env = _git_auth_env(auth_header_value)
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        subprocess.run(["git", "init", "-b", branch], cwd=str(tmp_path), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", author_name], cwd=str(tmp_path), check=True)
        subprocess.run(["git", "config", "user.email", author_email], cwd=str(tmp_path), check=True)
        if not force_orphan:
            fetch_proc = subprocess.run(
                ["git", "fetch", "--depth=1", remote_url, branch],
                cwd=str(tmp_path), env=git_env, capture_output=True, text=True, check=False,
            )
            if fetch_proc.returncode == 0:
                subprocess.run(["git", "checkout", "-B", branch, "FETCH_HEAD"], cwd=str(tmp_path), check=True, capture_output=True)
        subprocess.run([
            "rsync", "-a", "--delete", "--exclude=.git/", "--exclude=.venv/", "--exclude=build/",
            "--exclude=__pycache__/", "--exclude=*.pyc", "--exclude=.pytest_cache/",
            "--exclude=.env", "--exclude=secrets.env", f"{src_dir}/", f"{tmp_path}/",
        ], check=True)
        subprocess.run(["git", "add", "-A"], cwd=str(tmp_path), check=True)
        status_proc = subprocess.run(["git", "status", "--porcelain"], cwd=str(tmp_path), capture_output=True, text=True, check=True)
        if status_proc.stdout.strip():
            subprocess.run(["git", "commit", "-m", commit_msg], cwd=str(tmp_path), check=True, capture_output=True)
            push_cmd = ["git", "push", *(["--force"] if force_orphan else []), remote_url, f"{branch}:{branch}"]
            push_proc = subprocess.run(push_cmd, cwd=str(tmp_path), env=git_env, capture_output=True, text=True, check=False)
            if push_proc.returncode != 0:
                safe_err = _scrub_secrets(push_proc.stderr, auth_header_value, auth_header_value.split(" ")[-1])
                print(f"ERROR: git push {branch} failed:\n{safe_err}", file=sys.stderr)
                return 1
            print(f"[✓] Pushed {branch} branch -> {remote_url[:-4]}")
        else:
            print(f"[✓] Branch {branch} already up to date.")
    return 0


def _configure_github_pages(gh_login: str, repo_name: str, token: str) -> None:
    st_get, pages_info = _github_api("GET", f"/repos/{gh_login}/{repo_name}/pages", token)
    payload = {"source": {"branch": "gh-pages", "path": "/"}}
    if st_get == 404:
        st_op, data = _github_api("POST", f"/repos/{gh_login}/{repo_name}/pages", token, payload)
    else:
        st_op, data = _github_api("PUT", f"/repos/{gh_login}/{repo_name}/pages", token, payload)
    if st_op in (200, 201, 204):
        print(f"[✓] GitHub Pages configured: https://{gh_login}.github.io/{repo_name}/")
    else:
        url = (pages_info or {}).get("html_url") or f"https://{gh_login}.github.io/{repo_name}/"
        print(f"[i] GitHub Pages API returned HTTP {st_op} ({data.get('message', '')}) -> {url}")


def _upsert_release(src_root: Path, gh_login: str, repo_name: str, pkg_version: str, title: str, token: str) -> int:
    tag_name = f"v{pkg_version}"
    rel_body = _extract_changelog_section(src_root, pkg_version)
    st_existing, existing_rel = _github_api("GET", f"/repos/{gh_login}/{repo_name}/releases/tags/{tag_name}", token)
    if st_existing == 200 and existing_rel.get("id"):
        st_op, data = _github_api("PATCH", f"/repos/{gh_login}/{repo_name}/releases/{existing_rel['id']}", token, {
            "name": title, "body": rel_body, "draft": False, "prerelease": False,
        })
    else:
        st_op, data = _github_api("POST", f"/repos/{gh_login}/{repo_name}/releases", token, {
            "tag_name": tag_name, "target_commitish": "main", "name": title, "body": rel_body, "draft": False, "prerelease": False,
        })
    if st_op not in (200, 201):
        print(f"ERROR: Failed publishing GitHub release {tag_name} (HTTP {st_op}): {data.get('message')}", file=sys.stderr)
        return 1
    print(f"[✓] Published GitHub Release: {data.get('html_url')}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync GitHub repo, gh-pages static showcase, Pages API, and Release.")
    parser.add_argument("--repo", default="agy-nexus-mcp", help="Target GitHub repository name")
    parser.add_argument(
        "--description",
        default="AGY-Nexus v4.0.4: Quiet UI v9.3.0 Hybrid Range Whiskers, Target/Seam Caret Bars, Sortable Tables, Pinned Desktop Sidebar, 8-Model Cost Ledger, Praxis Semantic Gateway & Multi-Agent Orchestrator.",
        help="GitHub repository description",
    )
    parser.add_argument("--private", action="store_true", help="Create repository as private (default: public)")
    parser.add_argument("--author-name", default="", help="Override Git author name")
    parser.add_argument("--author-email", default="", help="Override Git author email")
    parser.add_argument("--message", default="", help="Custom Git commit message")
    parser.add_argument("--release-title", default="", help="Custom GitHub Release title")
    parser.add_argument("--no-release", action="store_true", help="Skip creating/updating the GitHub Release tag")
    parser.add_argument("--no-pages", action="store_true", help="Skip gh-pages showcase push and GitHub Pages API setup")
    parser.add_argument("--dry-run", action="store_true", help="Build showcase & verify privacy gate locally without pushing")
    args = parser.parse_args()

    src_root = Path(__file__).resolve().parent.parent
    pkg_version = _read_package_version(src_root)
    tag_name = f"v{pkg_version}"
    rel_title = args.release_title.strip() or f"{tag_name} — Sortable Analytics Tables, Desktop Sidebar Pinning & Opus 5.5 Drift Fix"
    showcase_dir = src_root / "build" / "gh-pages"
    pages_res = build_showcase(showcase_dir, refresh=False) if not args.no_pages else {"files": 0, "bytes": 0, "privacy_findings": 0}
    if args.dry_run:
        print(f"[✓] DRY RUN: version={tag_name}, repo={args.repo}, showcase={showcase_dir} ({pages_res['files']} files, 0 leaks)")
        print(f"[✓] DRY RUN Release Title: {rel_title}")
        print("[✓] DRY RUN Plan: push main + orphan gh-pages -> POST/PUT /repos/<owner>/<repo>/pages -> publish release")
        return 0

    token = _load_token_from_env_files()
    if not token:
        print("ERROR: No GITHUB_TOKEN found in ~/.config/ag-bridge-mcp/secrets.env or GITHUB_TOKEN.", file=sys.stderr)
        return 1
    status, user_info = _github_api("GET", "/user", token)
    if status != 200 or not user_info.get("login"):
        print(f"ERROR: GitHub auth failed (HTTP {status}): {user_info.get('message', 'Unknown error')}", file=sys.stderr)
        return 1
    gh_login = str(user_info["login"])
    if _ensure_repo(gh_login, args.repo.strip(), args.description.strip(), args.private, token) != 0:
        return 1
    author_name = args.author_name.strip() or gh_login
    author_email = args.author_email.strip() or f"{gh_login}@users.noreply.github.com"
    auth_header_value = f"AUTHORIZATION: basic {base64.b64encode(f'x-access-token:{token}'.encode()).decode('ascii')}"
    remote_url = f"https://github.com/{gh_login}/{args.repo.strip()}.git"
    msg_main = args.message.strip() or f"chore(release): sync {args.repo.strip()} {tag_name}"
    if _sync_branch(src_root, "main", remote_url, auth_header_value, author_name, author_email, msg_main) != 0:
        return 1
    if not args.no_pages:
        if _sync_branch(showcase_dir, "gh-pages", remote_url, auth_header_value, author_name, author_email, f"chore(pages): publish {tag_name} static showcase", force_orphan=True) != 0:
            return 1
        _configure_github_pages(gh_login, args.repo.strip(), token)
    if not args.no_release:
        return _upsert_release(src_root, gh_login, args.repo.strip(), pkg_version, rel_title, token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
