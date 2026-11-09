#!/usr/bin/env python3
"""Create a GitHub repository via the GitHub REST API and push a clean, single-commit export.

Security & Privacy Guarantees:
1. Reads GITHUB_TOKEN from ~/.config/ag-bridge-mcp/secrets.env or the GITHUB_TOKEN environment variable
   (never requires passing secrets in chat or storing tokens in .git/config).
2. Builds a fresh orphan commit from the current depersonalized working tree so historical GitLab commits
   are never exposed in public `git log -p` history on GitHub.
3. Defaults commit author email to `<github-login>@users.noreply.github.com` so personal email addresses
   are not leaked in public commit metadata.
"""

import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request


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
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "agy-nexus-mcp-publisher",
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a GitHub repo and push a clean single-commit export.")
    parser.add_argument("--repo", default="agy-nexus-mcp", help="Target GitHub repository name (default: agy-nexus-mcp)")
    parser.add_argument(
        "--description",
        default="Streamable HTTP MCP server, Chromium PWA dashboard, and 3-tier ASCII telemetry connecting Google Gemini to Antigravity IDE.",
        help="GitHub repository description",
    )
    parser.add_argument("--private", action="store_true", help="Create the GitHub repository as private (default: public)")
    parser.add_argument("--author-name", default="", help="Override Git author name (defaults to GitHub login)")
    parser.add_argument("--author-email", default="", help="Override Git author email (defaults to <login>@users.noreply.github.com)")
    parser.add_argument("--message", default="", help="Custom Git commit message")
    args = parser.parse_args()

    token = _load_token_from_env_files()
    if not token:
        print(
            "ERROR: No GITHUB_TOKEN found.\n"
            "Add GITHUB_TOKEN=<your_pat> to ~/.config/ag-bridge-mcp/secrets.env (chmod 600) and re-run.",
            file=sys.stderr,
        )
        return 1

    # 1. Verify authenticated GitHub user
    status_user, user_data = _github_api("GET", "/user", token)
    if status_user != 200 or not user_data.get("login"):
        print(f"ERROR: GitHub authentication failed (HTTP {status_user}): {user_data.get('message')}", file=sys.stderr)
        return 1

    gh_login = str(user_data["login"])
    gh_id = user_data.get("id", "")
    print(f"[*] Authenticated to GitHub as: {gh_login}")

    # 2. Check or create repository
    repo_name = args.repo.strip()
    status_repo, repo_data = _github_api("GET", f"/repos/{gh_login}/{repo_name}", token)
    if status_repo == 404:
        print(f"[*] Creating {'private' if args.private else 'public'} GitHub repository {gh_login}/{repo_name}...")
        status_create, repo_data = _github_api(
            "POST",
            "/user/repos",
            token,
            {
                "name": repo_name,
                "description": args.description,
                "private": bool(args.private),
                "has_issues": True,
                "has_wiki": False,
                "auto_init": False,
            },
        )
        if status_create not in (200, 201):
            print(f"ERROR: Failed creating repository (HTTP {status_create}): {repo_data.get('message')}", file=sys.stderr)
            return 1
        print(f"[+] Created repository: {repo_data.get('html_url')}")
    elif status_repo == 200:
        print(f"[*] Repository already exists: {repo_data.get('html_url')}")
    else:
        print(f"ERROR: Unexpected response checking repo (HTTP {status_repo}): {repo_data.get('message')}", file=sys.stderr)
        return 1

    # 3. Export clean working tree into a temporary Git repo (incremental fast-forward if main exists)
    src_root = Path(__file__).resolve().parent.parent
    author_name = args.author_name.strip() or gh_login
    author_email = args.author_email.strip() or (
        f"{gh_id}+{gh_login}@users.noreply.github.com" if gh_id else f"{gh_login}@users.noreply.github.com"
    )
    basic_auth = base64.b64encode(f"x-access-token:{token}".encode("utf-8")).decode("ascii")
    auth_header = f"http.https://github.com/.extraheader=AUTHORIZATION: basic {basic_auth}"
    remote_url = f"https://github.com/{gh_login}/{repo_name}.git"

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        subprocess.run(["git", "init", "-b", "main"], cwd=str(tmp_path), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", author_name], cwd=str(tmp_path), check=True)
        subprocess.run(["git", "config", "user.email", author_email], cwd=str(tmp_path), check=True)

        fetch_proc = subprocess.run(
            ["git", "-c", auth_header, "fetch", "--depth=1", remote_url, "main"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            check=False,
        )
        has_existing_main = fetch_proc.returncode == 0
        if has_existing_main:
            subprocess.run(["git", "checkout", "-B", "main", "FETCH_HEAD"], cwd=str(tmp_path), check=True, capture_output=True)

        subprocess.run(
            [
                "rsync", "-a", "--delete",
                "--exclude=.git/",
                "--exclude=.venv/",
                "--exclude=__pycache__/",
                "--exclude=*.pyc",
                "--exclude=.pytest_cache/",
                "--exclude=.env",
                "--exclude=secrets.env",
                f"{src_root}/",
                f"{tmp_path}/",
            ],
            check=True,
        )
        subprocess.run(["git", "add", "-A"], cwd=str(tmp_path), check=True)
        diff_proc = subprocess.run(["git", " status", "--porcelain"], cwd=str(tmp_path), capture_output=True, text=True, check=False)
        status_proc = subprocess.run(["git", "status", "--porcelain"], cwd=str(tmp_path), capture_output=True, text=True, check=True)
        if not status_proc.stdout.strip():
            print(f"[✓] GitHub repository https://github.com/{gh_login}/{repo_name} is already up to date.")
            return 0

        commit_msg = args.message.strip() or (
            "chore(release): sync agy-nexus-mcp v2.4.1"
            if has_existing_main
            else "feat: initial public release of agy-nexus-mcp (v2.4.1)"
        )
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=str(tmp_path),
            check=True,
            capture_output=True,
        )

        # Push using transient HTTP header so the token is never written to .git/config or process argv URL
        push_proc = subprocess.run(
            [
                "git",
                "-c",
                auth_header,
                "push",
                remote_url,
                "main:main",
            ],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            check=False,
        )
        if push_proc.returncode != 0:
            print(f"ERROR: git push failed:\n{push_proc.stderr}", file=sys.stderr)
            return 1

    print(f"[✓] Successfully published to https://github.com/{gh_login}/{repo_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
