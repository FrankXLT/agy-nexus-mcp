#!/usr/bin/env python3
"""Automated 3-2-1 Git Synchronization & Offline Bundle Archiver for agy-nexus-mcp.

3-2-1 Backup Topology:
- Copy 1 (Offsite Primary — GitHub `origin`): Pulls external PRs, commits, and tags from GitHub (`origin/main`).
- Copy 2 (Local GitLab Mirror — `gitlab`): Mirrors all commits and tags to the self-hosted GitLab remote (`gitlab/main`).
- Copy 3 (Offline Portable Archive — `.bundle`): Creates and verifies a full `git bundle` (`agy-nexus-mcp-latest.bundle`)
  with a SHA-256 integrity manifest in `~/.local/share/ag-bridge-mcp/backups/`.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def _load_env_file() -> None:
    """Load optional environment variables from ~/.config/ag-bridge-mcp/secrets.env."""
    for cand in (
        Path(os.getenv("AG_BRIDGE_ENV_FILE", "/config/secrets.env")),
        Path.home() / ".config/ag-bridge-mcp/secrets.env",
    ):
        if cand.is_file():
            try:
                for line in cand.read_text(encoding="utf-8").splitlines():
                    s = line.strip()
                    if not s or s.startswith("#") or "=" not in s:
                        continue
                    k, v = s.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("'\""))
            except Exception:
                continue


def _run_git(repo_dir: Path, args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        timeout=60,
        check=check,
    )


def main() -> int:
    _load_env_file()
    parser = argparse.ArgumentParser(description="Run 3-2-1 backup sync (GitHub origin -> Local GitLab -> .bundle).")
    default_repo = Path.home() / "gitlab/agy-nexus-mcp"
    script_repo = Path(__file__).resolve().parent.parent
    if (script_repo / ".git").exists() and not default_repo.exists():
        default_repo = script_repo
    parser.add_argument(
        "--repo-dir",
        default=os.getenv("AGY_NEXUS_REPO_DIR", str(default_repo)),
        help="Path to the standalone agy-nexus-mcp Git checkout",
    )
    parser.add_argument(
        "--backup-dir",
        default=os.getenv("AGY_BACKUP_DIR", str(Path.home() / ".local/share/ag-bridge-mcp/backups")),
        help="Directory for verified .bundle archives and SHA-256 manifest",
    )
    args = parser.parse_args()

    repo_dir = Path(args.repo_dir).expanduser().resolve()
    backup_dir = Path(args.backup_dir).expanduser().resolve()
    if not (repo_dir / ".git").exists():
        print(f"ERROR: Git repository not found at {repo_dir}", file=sys.stderr)
        return 1

    print(f"[*] Starting 3-2-1 backup sync in {repo_dir}...")

    # 1. Copy 1 (Offsite Primary — GitHub `origin`): Fetch & fast-forward
    print("  [1/3] Fetching latest commits and tags from primary remote (origin)...")
    fetch_res = _run_git(repo_dir, ["fetch", "origin", "--prune", "--tags"], check=False)
    if fetch_res.returncode != 0:
        print(f"ERROR: git fetch origin failed:\n{fetch_res.stderr}", file=sys.stderr)
        return 1

    status_res = _run_git(repo_dir, ["status", "--porcelain"])
    if not status_res.stdout.strip():
        ff_res = _run_git(repo_dir, ["merge", "--ff-only", "origin/main"], check=False)
        if ff_res.returncode != 0:
            print(f"WARN: Fast-forward merge skipped: {ff_res.stderr.strip()}", file=sys.stderr)
    origin_sha = _run_git(repo_dir, ["rev-parse", "origin/main"]).stdout.strip()
    head_sha = _run_git(repo_dir, ["rev-parse", "HEAD"]).stdout.strip()
    print(f"        Primary (origin/main) SHA : {origin_sha}")
    print(f"        Local HEAD SHA            : {head_sha}")

    # 2. Copy 2 (Local GitLab Mirror — `gitlab`): Push branches and tags
    remotes = _run_git(repo_dir, ["remote"]).stdout.split()
    gitlab_sha = ""
    if "gitlab" in remotes:
        print("  [2/3] Mirroring commits and tags to local GitLab remote (gitlab)...")
        push_main = _run_git(repo_dir, ["push", "gitlab", "HEAD:refs/heads/main", "--tags"], check=False)
        if push_main.returncode != 0:
            print(f"ERROR: git push gitlab failed:\n{push_main.stderr}", file=sys.stderr)
            return 1
        gitlab_sha = _run_git(repo_dir, ["rev-parse", "gitlab/main"], check=False).stdout.strip() or head_sha
        print(f"        Local GitLab (gitlab/main): {gitlab_sha}")
    else:
        print("  [2/3] WARN: No 'gitlab' remote configured; skipping Copy 2 push.")

    # 3. Copy 3 (Offline Portable Archive — Verified .bundle + SHA-256 manifest)
    print(f"  [3/3] Creating and verifying offline Git bundle in {backup_dir}...")
    backup_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = backup_dir / "agy-nexus-mcp-latest.bundle"
    tmp_bundle = backup_dir / "agy-nexus-mcp-latest.bundle.tmp"
    _run_git(repo_dir, ["bundle", "create", str(tmp_bundle), "--all"])
    verify_res = _run_git(repo_dir, ["bundle", "verify", str(tmp_bundle)], check=False)
    if verify_res.returncode != 0:
        print(f"ERROR: git bundle verify failed:\n{verify_res.stderr}", file=sys.stderr)
        return 1
    tmp_bundle.replace(bundle_path)

    bundle_bytes = bundle_path.read_bytes()
    bundle_sha256 = hashlib.sha256(bundle_bytes).hexdigest()
    manifest = {
        "ok": True,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "repo_dir": str(repo_dir),
        "head_sha": head_sha,
        "origin_sha": origin_sha,
        "gitlab_sha": gitlab_sha,
        "shas_match": (head_sha == origin_sha) and (not gitlab_sha or head_sha == gitlab_sha),
        "bundle_path": str(bundle_path),
        "bundle_size_bytes": len(bundle_bytes),
        "bundle_sha256": bundle_sha256,
    }
    manifest_path = backup_dir / "backup_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    nas_dir_raw = os.getenv("AGY_NAS_BACKUP_DIR", "").strip()
    if nas_dir_raw:
        nas_dir = Path(nas_dir_raw).expanduser()
        if nas_dir.is_dir():
            shutil.copy2(bundle_path, nas_dir / bundle_path.name)
            shutil.copy2(manifest_path, nas_dir / manifest_path.name)

    print(f"        Verified Bundle           : {bundle_path} ({len(bundle_bytes):,} bytes)")
    print(f"        Bundle SHA-256            : {bundle_sha256}")
    print(f"[✓] 3-2-1 Backup Sync Complete (SHAs identical: {manifest['shas_match']})!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
